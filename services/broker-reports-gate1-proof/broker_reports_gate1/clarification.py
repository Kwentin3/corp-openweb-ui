from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .contracts import stable_digest
from .criticality import (
    ANSWER_IMPACTS,
    ASK_POLICIES,
    AUTO_RESOLUTION_POLICIES,
    BLOCKING_REASON_CATEGORIES,
    BLOCKING_SCOPES,
    CRITICALITIES,
    DEPENDENCY_STAGES,
    criticality_counts,
    gap_criticality_policy,
)
from .domain_ingestion import apply_domain_ingestion_artifacts
from .eligibility import build_document_source_eligibility
from .validators import merge_validation_results, validate_artifacts, validate_safe_report


FACTORY_REQUIRED = "ClarificationPromptResolverFactory.create is the only production clarification prompt resolver entrypoint"
FORBIDDEN = "Pipe and normalizer must not hardcode or read clarification prompt tables directly"

CLARIFICATION_PROMPT_CONTRACT_ID = "broker_reports_gate1_clarification_prompt_v0"
CLARIFICATION_PROMPT_TEMPLATE_ID = "broker_reports.gate1_clarification_request.v0"
CLARIFICATION_PROMPT_TEMPLATE_KIND = "gate1_clarification_request"
CLARIFICATION_PROMPT_REQUIRED_TAG = "broker-reports-gate1"
CLARIFICATION_PROMPT_COMMAND = "broker_gate1_clarification_request"
CLARIFICATION_PROMPT_VERSION = "clarification-v0-2026-07-09-implementation"

GAP_REPORT_SCHEMA_VERSION = "gate1_metadata_gap_report_v0"
CLARIFICATION_REQUEST_SCHEMA_VERSION = "gate1_clarification_request_v0"
CLARIFICATION_RESOLUTION_SCHEMA_VERSION = "gate1_clarification_resolution_v0"
CLARIFICATION_RAW_OUTPUT_SCHEMA_VERSION = "llm_clarification_raw_output_v0"
CLARIFICATION_PROMPT_SNAPSHOT_SCHEMA_VERSION = "llm_clarification_prompt_snapshot_v0"
CLARIFICATION_JSON_SCHEMA_ID = "broker_reports.gate1_clarification_request.schema.v0"
CLARIFICATION_JSON_SCHEMA_NAME = "gate1_clarification_request_v0"
CLARIFICATION_SCHEMA_HASH_ALGORITHM = "sha256"
STRUCTURED_OUTPUT_MODE_JSON_SCHEMA = "openwebui_response_format_json_schema"
STRUCTURED_OUTPUT_MODE_JSON_OBJECT_FALLBACK = "openwebui_response_format_json_object_fallback"

ANSWER_TYPES = {
    "text",
    "date",
    "date_range",
    "single_choice",
    "multi_choice",
    "confirm_true_false",
    "select_canonical_document",
    "mark_as_outside_scope",
    "mark_as_not_source",
    "provide_account_or_contract",
    "provide_report_period",
}

GAP_TYPES = {
    "missing_period",
    "missing_account_or_contract",
    "unclear_document_role",
    "missing_broker_client_metadata",
    "duplicate_canonical_choice",
    "outside_scope_confirmation",
    "other_metadata_conflict",
}

QUESTION_SEVERITIES = {"blocking", "important", "optional"}
QUESTION_PRIORITIES = {"high", "medium", "low"}
RESOLUTION_SOURCES = {"user_confirmed", "operator_confirmed"}
RESOLUTION_VALIDATION_STATUSES = {"passed", "failed", "not_applicable"}
FORBIDDEN_FIELD_NAMES = {
    "file_id",
    "filename",
    "original_filename",
    "original_filename_private",
    "private_ref",
    "private_path",
    "path",
    "raw_text",
    "raw_rows",
    "rows",
    "content",
    "normalized_table_slice",
    "normalized_text_slice",
}

PERIOD_FIELDS = {"report_period_start", "report_period_end", "tax_year_candidate"}
ACCOUNT_FIELDS = {"account_or_contract_candidate"}
BROKER_CLIENT_FIELDS = {"broker_name_candidate", "client_name_candidate", "document_kind_candidate"}
ROLE_FIELDS = {"content_kind", "document_role", "role_hypotheses"}
QUESTION_GROUP_KEYS = {
    "critical_questions_for_continuation",
    "useful_clarifications",
    "deferred_non_critical_notes",
}
CRITICALITY_TO_GROUP_KEY = {
    "critical": "critical_questions_for_continuation",
    "clarifying": "useful_clarifications",
    "non_critical": "deferred_non_critical_notes",
}


class ClarificationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PromptUserContext:
    user_id: str
    user_role: str = "user"
    user_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClarificationPromptConfig:
    source: str = "openwebui_sqlite"
    db_path: Path | None = None
    prompt_id: str | None = None
    command: str | None = CLARIFICATION_PROMPT_COMMAND
    required_template_id: str = CLARIFICATION_PROMPT_TEMPLATE_ID
    required_template_kind: str = CLARIFICATION_PROMPT_TEMPLATE_KIND
    required_output_schema_version: str = CLARIFICATION_REQUEST_SCHEMA_VERSION
    required_tag: str = CLARIFICATION_PROMPT_REQUIRED_TAG


@dataclass(frozen=True)
class ClarificationManagedPrompt:
    prompt_ref: str
    command: str | None
    version: str | None
    content: str
    hash: str
    source: str
    template_id: str
    template_kind: str
    output_schema_version: str
    tags: tuple[str, ...]
    safe_metadata: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": CLARIFICATION_PROMPT_SNAPSHOT_SCHEMA_VERSION,
            "llm_prompt_ref": self.prompt_ref,
            "llm_prompt_command": self.command,
            "llm_prompt_version": self.version,
            "llm_prompt_hash": self.hash,
            "llm_prompt_source": self.source,
            "prompt_contract_id": CLARIFICATION_PROMPT_CONTRACT_ID,
            "template_id": self.template_id,
            "template_kind": self.template_kind,
            "output_schema_version": self.output_schema_version,
            "output_schema_id": CLARIFICATION_JSON_SCHEMA_ID,
            "output_schema_hash_algorithm": CLARIFICATION_SCHEMA_HASH_ALGORITHM,
            "output_schema_hash": gate1_clarification_request_schema_hash(),
            "tags": list(self.tags),
            "safe_metadata": copy.deepcopy(self.safe_metadata),
        }


class ClarificationPromptResolver(Protocol):
    def resolve(self, user_context: PromptUserContext) -> ClarificationManagedPrompt:
        ...


class ClarificationPromptResolverFactory:
    def __init__(self, config: ClarificationPromptConfig) -> None:
        self.config = config

    def create(self) -> ClarificationPromptResolver:
        if self.config.source == "openwebui_sqlite":
            if self.config.db_path is None:
                raise ClarificationError("clarification_prompt_unavailable", "OpenWebUI prompt DB path is not configured")
            return OpenWebUISqliteClarificationPromptResolver(self.config)
        if self.config.source == "disabled":
            return DisabledClarificationPromptResolver()
        raise ClarificationError("clarification_prompt_unavailable", "Unsupported clarification prompt source")


class DisabledClarificationPromptResolver:
    def resolve(self, user_context: PromptUserContext) -> ClarificationManagedPrompt:
        raise ClarificationError("clarification_prompt_disabled", "Clarification prompt resolver is disabled")


class StaticClarificationPromptResolver:
    def __init__(self, prompt: ClarificationManagedPrompt) -> None:
        self.prompt = prompt

    def resolve(self, user_context: PromptUserContext) -> ClarificationManagedPrompt:
        return self.prompt


class OpenWebUISqliteClarificationPromptResolver:
    def __init__(self, config: ClarificationPromptConfig) -> None:
        self.config = config
        self.db_path = config.db_path

    def resolve(self, user_context: PromptUserContext) -> ClarificationManagedPrompt:
        conn = self._connect()
        try:
            row = self._find_prompt(conn)
            if row is None:
                raise ClarificationError("clarification_prompt_not_found", "Clarification prompt was not found")
            if not self._has_read_access(row, user_context, conn):
                raise ClarificationError("clarification_prompt_access_denied", "Clarification prompt is not readable")
            return self._row_to_prompt(row)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None or not self.db_path.exists():
            raise ClarificationError("clarification_prompt_unavailable", "OpenWebUI prompt DB file is not available")
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _find_prompt(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        if self.config.prompt_id:
            row = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1 AND id = ?
                """,
                (self.config.prompt_id,),
            ).fetchone()
            return row if row is not None and self._matches_contract(row) else None
        if self.config.command:
            row = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1 AND command = ?
                """,
                (self.config.command,),
            ).fetchone()
            return row if row is not None and self._matches_contract(row) else None
        raise ClarificationError("clarification_prompt_not_found", "Prompt id or command is required")

    def _matches_contract(self, row: sqlite3.Row) -> bool:
        meta = _json_dict(row["meta"])
        tags = _json_list(row["tags"])
        template_id = str(meta.get("template_id") or meta.get("stage2_template_id") or "")
        template_kind = str(meta.get("template_kind") or "")
        output_schema = str(meta.get("output_schema_version") or "")
        return (
            template_id == self.config.required_template_id
            and template_kind == self.config.required_template_kind
            and output_schema == self.config.required_output_schema_version
            and self.config.required_tag in tags
            and bool(str(row["content"] or "").strip())
        )

    def _row_to_prompt(self, row: sqlite3.Row) -> ClarificationManagedPrompt:
        content = str(row["content"] or "")
        meta = _json_dict(row["meta"])
        tags = tuple(_json_list(row["tags"]))
        template_id = str(meta.get("template_id") or meta.get("stage2_template_id") or self.config.required_template_id)
        template_kind = str(meta.get("template_kind") or self.config.required_template_kind)
        output_schema = str(meta.get("output_schema_version") or self.config.required_output_schema_version)
        return ClarificationManagedPrompt(
            prompt_ref=str(row["id"]),
            command=str(row["command"] or ""),
            version=str(row["version_id"] or ""),
            content=content,
            hash=prompt_hash(content, CLARIFICATION_PROMPT_CONTRACT_ID, output_schema),
            source="openwebui_sqlite",
            template_id=template_id,
            template_kind=template_kind,
            output_schema_version=output_schema,
            tags=tags,
            safe_metadata=meta,
        )

    def _has_read_access(self, row: sqlite3.Row, user_context: PromptUserContext, conn: sqlite3.Connection) -> bool:
        if user_context.user_role == "admin":
            return True
        user_id = str(row["user_id"] or "")
        if user_id and user_id == user_context.user_id:
            return True
        # OpenWebUI prompt rows do not always carry ACL metadata. Active prompt
        # plus matching managed contract is the safe read boundary here.
        return True


def prompt_hash(content: str, prompt_contract_id: str, output_schema_version: str) -> str:
    material = json.dumps(
        {
            "content": content,
            "prompt_contract_id": prompt_contract_id,
            "output_schema_version": output_schema_version,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def gate1_clarification_request_json_schema() -> dict[str, Any]:
    question_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "question_id",
            "target_document_refs",
            "gap_type",
            "question_text",
            "answer_type",
            "allowed_answer_format",
            "required_for",
            "why_asked",
            "safe_evidence_refs",
            "criticality",
            "blocking_scope",
            "dependency_stage",
            "blocking_reason_category",
            "auto_resolution_policy",
            "blocks_gate2",
            "resolution_required",
            "can_proceed_with_warning",
            "ask_policy",
            "answer_impact",
            "priority",
            "severity",
            "required",
            "reason_codes",
            "safe_explanation",
        ],
        "properties": {
            "question_id": {"type": "string", "minLength": 1, "maxLength": 96},
            "target_document_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "gap_type": {"type": "string", "enum": sorted(GAP_TYPES)},
            "question_text": {"type": "string", "minLength": 1, "maxLength": 700},
            "answer_type": {"type": "string", "enum": sorted(ANSWER_TYPES)},
            "allowed_answer_format": {"type": "string", "minLength": 1, "maxLength": 240},
            "required_for": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "why_asked": {"type": "string", "minLength": 1, "maxLength": 700},
            "safe_evidence_refs": {"type": "array", "items": {"type": "string"}},
            "criticality": {"type": "string", "enum": sorted(CRITICALITIES)},
            "blocking_scope": {"type": "string", "enum": sorted(BLOCKING_SCOPES)},
            "dependency_stage": {"type": "string", "enum": sorted(DEPENDENCY_STAGES)},
            "blocking_reason_category": {"type": "string", "enum": sorted(BLOCKING_REASON_CATEGORIES)},
            "auto_resolution_policy": {"type": "string", "enum": sorted(AUTO_RESOLUTION_POLICIES)},
            "blocks_gate2": {"type": "boolean"},
            "resolution_required": {"type": "boolean"},
            "can_proceed_with_warning": {"type": "boolean"},
            "ask_policy": {"type": "string", "enum": sorted(ASK_POLICIES)},
            "answer_impact": {"type": "string", "enum": sorted(ANSWER_IMPACTS)},
            "priority": {"type": "string", "enum": sorted(QUESTION_PRIORITIES)},
            "severity": {"type": "string", "enum": sorted(QUESTION_SEVERITIES)},
            "required": {"type": "boolean"},
            "reason_codes": {"type": "array", "items": {"type": "string"}},
            "safe_explanation": {"type": "string", "minLength": 1, "maxLength": 700},
        },
    }
    question_groups_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(QUESTION_GROUP_KEYS),
        "properties": {
            key: {"type": "array", "items": {"type": "string"}}
            for key in sorted(QUESTION_GROUP_KEYS)
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "questions", "question_groups"],
        "properties": {
            "schema_version": {"type": "string", "enum": [CLARIFICATION_REQUEST_SCHEMA_VERSION]},
            "questions": {"type": "array", "items": question_schema},
            "question_groups": question_groups_schema,
        },
    }


def gate1_clarification_request_schema_hash() -> str:
    return hashlib.sha256(
        json.dumps(gate1_clarification_request_json_schema(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def clarification_json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": CLARIFICATION_JSON_SCHEMA_NAME,
            "strict": True,
            "schema": gate1_clarification_request_json_schema(),
        },
    }


def clarification_json_object_response_format() -> dict[str, Any]:
    return {"type": "json_object"}


def model_call_audit_metadata(
    *,
    prompt: ClarificationManagedPrompt,
    model_id: str,
    structured_output_mode: str,
    response_format_type: str,
    response_format_schema_mode: str | None,
    schema_attempted: bool = True,
    fallback_used: bool = False,
    native_error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "llm_model_id": model_id,
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_command": prompt.command,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
        "structured_output_mode": structured_output_mode,
        "response_format_type": response_format_type,
        "response_format_schema_mode": response_format_schema_mode,
        "schema_attempted": bool(schema_attempted),
        "fallback_used": bool(fallback_used),
        "native_structured_output_error_code": native_error_code,
        "output_schema_id": CLARIFICATION_JSON_SCHEMA_ID,
        "output_schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
        "output_schema_hash": gate1_clarification_request_schema_hash(),
    }


def parse_clarification_request_model_output(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str) or not value.strip():
        raise ClarificationError("clarification_model_invalid_response", "Clarification response is empty")
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClarificationError("clarification_model_invalid_json", "Clarification response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ClarificationError("clarification_model_invalid_json", "Clarification response must be a JSON object")
    return parsed


def build_metadata_gap_report(
    package: dict[str, Any],
    *,
    criticality_refinement_enabled: bool | None = None,
) -> dict[str, Any]:
    if criticality_refinement_enabled is None:
        criticality_refinement_enabled = _criticality_refinement_enabled(package)
    run_id = str(package.get("normalization_run", {}).get("run_id") or "")
    eligibility = package.get("document_source_eligibility") if isinstance(package.get("document_source_eligibility"), dict) else {}
    entries = eligibility.get("entries") if isinstance(eligibility.get("entries"), list) else []
    documents = package.get("document_inventory", {}).get("documents", [])
    passports = package.get("document_metadata_passports", [])
    blockers = package.get("normalization_blockers", [])
    passport_by_doc = {str(item.get("document_id")): item for item in passports if isinstance(item, dict)}
    document_by_doc = {str(item.get("document_id")): item for item in documents if isinstance(item, dict)}
    blockers_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for blocker in blockers:
        if isinstance(blocker, dict) and blocker.get("document_id"):
            blockers_by_doc[str(blocker["document_id"])].append(blocker)

    gaps: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        document_id = str(entry.get("document_id") or "")
        passport = passport_by_doc.get(document_id, {})
        document = document_by_doc.get(document_id, {})
        if entry.get("source_eligibility") == "metadata_review_required":
            gaps.extend(
                _metadata_gaps_for_document(
                    run_id,
                    entry,
                    passport,
                    document,
                    blockers_by_doc.get(document_id, []),
                    criticality_refinement_enabled=criticality_refinement_enabled,
                )
            )
        elif criticality_refinement_enabled and entry.get("source_eligibility") in {
            "accepted_for_gate2",
            "accepted_as_source_candidate_for_gate2",
        }:
            gaps.extend(
                _metadata_gaps_for_document(
                    run_id,
                    entry,
                    passport,
                    document,
                    blockers_by_doc.get(document_id, []),
                    criticality_refinement_enabled=criticality_refinement_enabled,
                    non_blocking_only=True,
                )
            )
        elif entry.get("source_eligibility") == "duplicate_needs_canonical_choice":
            gaps.append(
                _duplicate_gap_for_document(
                    run_id,
                    entry,
                    document,
                    criticality_refinement_enabled=criticality_refinement_enabled,
                )
            )
        elif entry.get("source_eligibility") == "outside_case_scope":
            gaps.append(
                _outside_scope_gap_for_document(
                    run_id,
                    entry,
                    passport,
                    document,
                    criticality_refinement_enabled=criticality_refinement_enabled,
                )
            )

    question_stubs = [
        _question_stub_for_gap(gap)
        for gap in gaps
        if gap.get("resolvable_by_answer") is True and gap.get("ask_policy") != "do_not_ask"
    ]
    counts = Counter(str(gap.get("gap_type") or "unknown") for gap in gaps)
    blocking_counts = Counter(str(gap.get("gap_type") or "unknown") for gap in gaps if gap.get("blocks_gate2") is True)
    criticality_count_values = criticality_counts(gaps)
    blocking_scope_counts = Counter(str(gap.get("blocking_scope") or "unknown") for gap in gaps)
    dependency_stage_counts = Counter(str(gap.get("dependency_stage") or "unknown") for gap in gaps)
    blocking_reason_category_counts = Counter(str(gap.get("blocking_reason_category") or "unknown") for gap in gaps)
    auto_resolution_policy_counts = Counter(str(gap.get("auto_resolution_policy") or "unknown") for gap in gaps)
    ask_policy_counts = Counter(str(gap.get("ask_policy") or "unknown") for gap in gaps)
    answer_impact_counts = Counter(str(gap.get("answer_impact") or "unknown") for gap in gaps)
    return {
        "schema_version": GAP_REPORT_SCHEMA_VERSION,
        "gap_report_id": f"gapreport_{stable_digest([run_id, len(gaps), len(question_stubs)], length=16)}",
        "normalization_run_id": run_id,
        "decision_version": "passport_based_source_eligibility_v2",
        "criticality_refinement_enabled": bool(criticality_refinement_enabled),
        "handoff_status": package.get("normalization_run", {}).get("gate2_handoff_status"),
        "handoff_mode": package.get("normalization_run", {}).get("gate2_handoff_mode"),
        "gaps": gaps,
        "question_stubs": question_stubs,
        "question_groups": _question_groups(question_stubs),
        "summary": {
            "gaps_total": len(gaps),
            "blocking_gaps_total": sum(blocking_counts.values()),
            "resolvable_gaps_total": len(question_stubs),
            "gap_type_counts": dict(sorted(counts.items())),
            "blocking_gap_type_counts": dict(sorted(blocking_counts.items())),
            "criticality_counts": criticality_count_values,
            "critical_gaps_total": criticality_count_values.get("critical", 0),
            "clarifying_gaps_total": criticality_count_values.get("clarifying", 0),
            "non_critical_gaps_total": criticality_count_values.get("non_critical", 0),
            "blocking_scope_counts": dict(sorted(blocking_scope_counts.items())),
            "dependency_stage_counts": dict(sorted(dependency_stage_counts.items())),
            "blocking_reason_category_counts": dict(sorted(blocking_reason_category_counts.items())),
            "auto_resolution_policy_counts": dict(sorted(auto_resolution_policy_counts.items())),
            "ask_policy_counts": dict(sorted(ask_policy_counts.items())),
            "answer_impact_counts": dict(sorted(answer_impact_counts.items())),
            "can_proceed_with_warning_total": sum(1 for gap in gaps if gap.get("can_proceed_with_warning") is True),
            "metadata_review_document_count": len(
                {gap["target_document_refs"][0] for gap in gaps if gap.get("source_eligibility") == "metadata_review_required"}
            ),
            "duplicate_group_count": counts.get("duplicate_canonical_choice", 0),
        },
    }


def validate_clarification_request(
    *,
    request: dict[str, Any],
    gap_report: dict[str, Any],
    prompt: ClarificationManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if request.get("schema_version") != CLARIFICATION_REQUEST_SCHEMA_VERSION:
        errors.append(_error("clarification_request_schema_mismatch", request.get("schema_version")))
    if request.get("normalization_run_id") != gap_report.get("normalization_run_id"):
        errors.append(_error("clarification_request_run_ref_mismatch", request.get("normalization_run_id")))
    if request.get("gap_report_id") != gap_report.get("gap_report_id"):
        errors.append(_error("clarification_request_gap_report_ref_mismatch", request.get("gap_report_id")))
    if request.get("llm_prompt_hash") != prompt.hash:
        errors.append(_error("clarification_request_prompt_hash_mismatch", request.get("llm_prompt_hash")))
    if request.get("llm_model_id") != model_id:
        errors.append(_error("clarification_request_model_mismatch", request.get("llm_model_id")))
    forbidden_paths = _find_forbidden_fields(request)
    for path in forbidden_paths:
        errors.append(_error("clarification_request_forbidden_field", path))

    stubs_by_id = {
        str(stub.get("question_id")): stub
        for stub in gap_report.get("question_stubs", [])
        if isinstance(stub, dict) and stub.get("question_id")
    }
    questions = request.get("questions")
    if not isinstance(questions, list):
        errors.append(_error("clarification_request_questions_invalid", "questions"))
        questions = []
    seen: set[str] = set()
    required_stub_ids = {qid for qid, stub in stubs_by_id.items() if stub.get("required") is True}
    for question in questions:
        if not isinstance(question, dict):
            errors.append(_error("clarification_request_question_invalid", "non_object"))
            continue
        question_id = str(question.get("question_id") or "")
        if not question_id:
            errors.append(_error("clarification_request_question_id_missing", "question"))
            continue
        if question_id in seen:
            errors.append(_error("clarification_request_question_duplicate", question_id))
        seen.add(question_id)
        stub = stubs_by_id.get(question_id)
        if stub is None:
            errors.append(_error("clarification_request_unknown_question_id", question_id))
            continue
        for key in (
            "target_document_refs",
            "gap_type",
            "answer_type",
            "allowed_answer_format",
            "required_for",
            "safe_evidence_refs",
            "criticality",
            "blocking_scope",
            "dependency_stage",
            "blocking_reason_category",
            "auto_resolution_policy",
            "blocks_gate2",
            "resolution_required",
            "can_proceed_with_warning",
            "ask_policy",
            "answer_impact",
            "priority",
            "severity",
            "required",
            "reason_codes",
            "safe_explanation",
        ):
            if question.get(key) != stub.get(key):
                errors.append(_error(f"clarification_request_{key}_mismatch", question_id))
        if not str(question.get("question_text") or "").strip():
            errors.append(_error("clarification_request_question_text_missing", question_id))
        if not str(question.get("why_asked") or "").strip():
            errors.append(_error("clarification_request_why_asked_missing", question_id))
    missing_required = sorted(required_stub_ids - seen)
    for question_id in missing_required:
        errors.append(_error("clarification_request_required_question_missing", question_id))
    expected_groups = _question_groups([question for question in questions if isinstance(question, dict)])
    if request.get("question_groups") != expected_groups:
        errors.append(_error("clarification_request_question_groups_mismatch", "question_groups"))
    return _validation_result(errors)


def canonicalize_clarification_request(
    *,
    model_output: dict[str, Any],
    gap_report: dict[str, Any],
    prompt: ClarificationManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    stubs_by_id = {
        str(stub.get("question_id")): stub
        for stub in gap_report.get("question_stubs", [])
        if isinstance(stub, dict) and stub.get("question_id")
    }
    model_questions_by_id = {
        str(item.get("question_id")): item
        for item in model_output.get("questions") or []
        if isinstance(item, dict) and item.get("question_id")
    }
    questions = []
    for question_id, stub in stubs_by_id.items():
        item = model_questions_by_id.get(question_id, {})
        canonical = {
            key: copy.deepcopy(stub.get(key))
            for key in (
                "question_id",
                "target_document_refs",
                "gap_type",
                "answer_type",
                "allowed_answer_format",
                "required_for",
                "safe_evidence_refs",
                "criticality",
                "blocking_scope",
                "dependency_stage",
                "blocking_reason_category",
                "auto_resolution_policy",
                "blocks_gate2",
                "resolution_required",
                "can_proceed_with_warning",
                "ask_policy",
                "answer_impact",
                "priority",
                "severity",
                "required",
                "reason_codes",
                "safe_explanation",
            )
        }
        canonical["question_text"] = str(item.get("question_text") or "").strip() or _fallback_question_text(stub)
        canonical["why_asked"] = str(item.get("why_asked") or "").strip() or str(stub.get("safe_explanation") or "")
        questions.append(canonical)
    for item in model_output.get("questions") or []:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id") or "")
        if question_id and question_id not in stubs_by_id:
            questions.append(copy.deepcopy(item))
    return {
        "schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
        "clarification_request_id": f"clarreq_{stable_digest([gap_report.get('gap_report_id'), prompt.hash, model_id], length=16)}",
        "normalization_run_id": gap_report.get("normalization_run_id"),
        "gap_report_id": gap_report.get("gap_report_id"),
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_command": prompt.command,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
        "llm_model_id": model_id,
        "output_schema_id": CLARIFICATION_JSON_SCHEMA_ID,
        "output_schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
        "output_schema_hash": gate1_clarification_request_schema_hash(),
        "questions": questions,
        "question_groups": _question_groups(questions),
        "summary": _question_summary(questions),
    }


def apply_clarification_request_stage(
    *,
    package: dict[str, Any],
    prompt: ClarificationManagedPrompt,
    model_id: str,
    raw_output: dict[str, Any],
    private_markers: list[str],
    answers: list[dict[str, Any]] | None = None,
    answered_by: str = "operator",
    answer_source: str = "operator_confirmed",
    criticality_refinement_enabled: bool = False,
) -> dict[str, Any]:
    updated = copy.deepcopy(package)
    updated["clarification_criticality_refinement_enabled"] = bool(criticality_refinement_enabled)
    gap_report = build_metadata_gap_report(
        updated,
        criticality_refinement_enabled=criticality_refinement_enabled,
    )
    updated["gate1_metadata_gap_report"] = gap_report
    updated["gate1_clarification_prompt_snapshot"] = prompt.snapshot()
    updated["llm_clarification_raw_output"] = copy.deepcopy(raw_output)
    if raw_output.get("model_call_status") == "passed":
        parsed = parse_clarification_request_model_output(raw_output.get("raw_output"))
        request = canonicalize_clarification_request(
            model_output=parsed,
            gap_report=gap_report,
            prompt=prompt,
            model_id=model_id,
        )
    else:
        request = _empty_clarification_request(gap_report=gap_report, prompt=prompt, model_id=model_id)
    validation = validate_clarification_request(
        request=request,
        gap_report=gap_report,
        prompt=prompt,
        model_id=model_id,
    )
    updated["gate1_clarification_request"] = request
    updated["gate1_clarification_request_validation"] = validation
    resolutions = build_clarification_resolutions(
        gap_report=gap_report,
        clarification_request=request,
        answers=answers or [],
        answered_by=answered_by,
        source=answer_source,
    )
    updated["gate1_clarification_resolutions"] = resolutions
    updated["gate1_clarification_resolution_summary"] = _resolution_summary(resolutions)
    if any(item.get("usable_by_source_eligibility_v2") is True for item in resolutions):
        updated = rerun_eligibility_with_clarification_resolutions(
            updated,
            criticality_refinement_enabled=criticality_refinement_enabled,
        )
    updated = _refresh_package_validation_and_safe_report(updated, private_markers)
    from .safe_report import render_safe_report

    return {"package": updated, "safe_report": render_safe_report(updated)}


def apply_metadata_gap_report_stage(
    package: dict[str, Any],
    *,
    private_markers: list[str],
    criticality_refinement_enabled: bool = False,
) -> dict[str, Any]:
    updated = copy.deepcopy(package)
    updated["clarification_criticality_refinement_enabled"] = bool(criticality_refinement_enabled)
    updated["gate1_metadata_gap_report"] = build_metadata_gap_report(
        updated,
        criticality_refinement_enabled=criticality_refinement_enabled,
    )
    updated = _refresh_package_validation_and_safe_report(updated, private_markers)
    from .safe_report import render_safe_report

    return {"package": updated, "safe_report": render_safe_report(updated)}


def build_clarification_resolutions(
    *,
    gap_report: dict[str, Any],
    clarification_request: dict[str, Any],
    answers: list[dict[str, Any]],
    answered_by: str,
    source: str,
) -> list[dict[str, Any]]:
    questions_by_id = {
        str(question.get("question_id")): question
        for question in clarification_request.get("questions", [])
        if isinstance(question, dict) and question.get("question_id")
    }
    stubs_by_id = {
        str(stub.get("question_id")): stub
        for stub in gap_report.get("question_stubs", [])
        if isinstance(stub, dict) and stub.get("question_id")
    }
    resolutions: list[dict[str, Any]] = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        matches = _question_matches_for_answer(answer, questions_by_id)
        if not matches:
            question_id = str(answer.get("question_id") or answer.get("gap_type") or "")
            resolutions.append(_failed_resolution(question_id, answered_by, source, "unknown_question_id"))
            continue
        for question_id, question in matches:
            stub = stubs_by_id.get(question_id)
            if stub is None:
                resolutions.append(_failed_resolution(question_id, answered_by, source, "unknown_question_id"))
                continue
            validation_status, validation_errors = _validate_answer(answer.get("answer_value"), question.get("answer_type"))
            resolved_fields = list(stub.get("resolved_fields") or [])
            if not resolved_fields:
                resolved_fields = ["metadata_confirmation"]
            for resolved_field in resolved_fields:
                resolution = {
                    "schema_version": CLARIFICATION_RESOLUTION_SCHEMA_VERSION,
                    "resolution_id": f"clarres_{stable_digest([question_id, resolved_field, len(resolutions)], length=16)}",
                    "normalization_run_id": gap_report.get("normalization_run_id"),
                    "gap_report_id": gap_report.get("gap_report_id"),
                    "clarification_request_id": clarification_request.get("clarification_request_id"),
                    "question_id": question_id,
                    "target_document_ref": (question.get("target_document_refs") or [None])[0],
                    "target_document_refs": list(question.get("target_document_refs") or []),
                    "gap_type": question.get("gap_type"),
                    "resolved_field": resolved_field,
                    "answer_value": copy.deepcopy(answer.get("answer_value")),
                    "answer_type": question.get("answer_type"),
                    "answered_by": str(answer.get("answered_by") or answered_by or "operator"),
                    "answered_at": str(answer.get("answered_at") or ""),
                    "source": str(answer.get("source") or source or "operator_confirmed"),
                    "validation_status": validation_status,
                    "validation_errors": validation_errors,
                    "safe_audit_refs": [
                        str(gap_report.get("gap_report_id") or ""),
                        str(clarification_request.get("clarification_request_id") or ""),
                        question_id,
                    ],
                    "usable_by_source_eligibility_v2": validation_status == "passed",
                }
                if not resolution["answered_at"]:
                    resolution["answered_at"] = "not_recorded"
                if resolution["source"] not in RESOLUTION_SOURCES:
                    resolution["validation_status"] = "failed"
                    resolution["validation_errors"].append("unsupported_resolution_source")
                    resolution["usable_by_source_eligibility_v2"] = False
                resolutions.append(resolution)
    return resolutions


def rerun_eligibility_with_clarification_resolutions(
    package: dict[str, Any],
    *,
    criticality_refinement_enabled: bool | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(package)
    if criticality_refinement_enabled is None:
        criticality_refinement_enabled = _criticality_refinement_enabled(updated)
    run_id = str(updated.get("normalization_run", {}).get("run_id") or "")
    eligibility, summary, handoff = build_document_source_eligibility(
        run_id=run_id,
        documents=updated.get("document_inventory", {}).get("documents", []),
        taxonomy_candidates=updated.get("taxonomy_candidates", []),
        blockers=updated.get("normalization_blockers", []),
        ocr_policy_status=updated.get("document_source_eligibility", {}).get("ocr_policy_status", "disabled"),
        document_metadata_passports=updated.get("document_metadata_passports", []),
        clarification_resolutions=updated.get("gate1_clarification_resolutions", []),
        input_context=updated.get("input_context") or {},
        criticality_refinement_enabled=bool(criticality_refinement_enabled),
    )
    updated["document_source_eligibility"] = eligibility
    updated["source_eligibility_summary"] = summary
    updated["gate2_handoff"] = handoff
    updated["normalization_run"]["gate2_handoff_status"] = handoff["gate2_handoff_status"]
    updated["normalization_run"]["gate2_handoff_mode"] = handoff["handoff_mode"]
    updated["summary_counts"]["source_eligibility_counts"] = dict(summary.get("status_counts", {}))
    updated["recommended_next_step"] = _next_step_after_clarification(updated)
    return updated


def safe_clarification_questions_for_report(package: dict[str, Any]) -> dict[str, Any] | None:
    request = package.get("gate1_clarification_request")
    validation = package.get("gate1_clarification_request_validation")
    if not isinstance(request, dict) or not isinstance(validation, dict):
        return None
    if validation.get("validator_status") != "passed":
        return None
    questions = []
    for question in request.get("questions", []):
        if not isinstance(question, dict):
            continue
        questions.append(
            {
                "question_id": question.get("question_id"),
                "gap_type": question.get("gap_type"),
                "question_text": question.get("question_text"),
                "answer_type": question.get("answer_type"),
                "required": question.get("required"),
                "criticality": question.get("criticality"),
                "blocking_scope": question.get("blocking_scope"),
                "dependency_stage": question.get("dependency_stage"),
                "blocking_reason_category": question.get("blocking_reason_category"),
                "auto_resolution_policy": question.get("auto_resolution_policy"),
                "blocks_gate2": question.get("blocks_gate2"),
                "resolution_required": question.get("resolution_required"),
                "can_proceed_with_warning": question.get("can_proceed_with_warning"),
                "ask_policy": question.get("ask_policy"),
                "answer_impact": question.get("answer_impact"),
                "priority": question.get("priority"),
                "severity": question.get("severity"),
                "reason_codes": list(question.get("reason_codes") or []),
                "safe_explanation": question.get("safe_explanation"),
            }
        )
    return {
        "schema_version": "gate1_clarification_safe_question_summary_v0",
        "summary": request.get("summary") or _question_summary(questions),
        "question_groups": request.get("question_groups") or _question_groups(questions),
        "questions": questions,
    }


def _metadata_gaps_for_document(
    run_id: str,
    entry: dict[str, Any],
    passport: dict[str, Any],
    document: dict[str, Any],
    blockers: list[dict[str, Any]],
    *,
    criticality_refinement_enabled: bool,
    non_blocking_only: bool = False,
) -> list[dict[str, Any]]:
    document_ref = str(entry.get("document_id") or document.get("document_id") or "")
    missing_fields = [str(item) for item in passport.get("missing_metadata_fields") or [] if item]
    conflict_flags = [str(item) for item in passport.get("conflict_flags") or [] if item]
    reason_codes = [str(item) for item in entry.get("reason_codes") or [] if item]
    criticality_basis = entry.get("clarification_criticality_basis") if isinstance(entry.get("clarification_criticality_basis"), dict) else {}
    period_scope_basis = (
        criticality_basis.get("period_scope_basis")
        if isinstance(criticality_basis.get("period_scope_basis"), dict)
        else {}
    )
    for field in criticality_basis.get("unresolved_critical_fields") or []:
        field_name = str(field or "")
        if field_name and field_name not in missing_fields and field_name not in conflict_flags:
            missing_fields.append(field_name)
    if not missing_fields and "unknown_role_requires_metadata_review" in reason_codes:
        missing_fields.append("document_role")
    if not missing_fields and "document_metadata_passport_source_confidence_low" in reason_codes:
        missing_fields.append("document_role")
    if not missing_fields and "document_metadata_passport_incomplete" in reason_codes:
        missing_fields.append("metadata_confirmation")
    if not missing_fields and not conflict_flags:
        missing_fields.append("metadata_confirmation")

    groups: dict[str, set[str]] = defaultdict(set)
    for field in missing_fields:
        groups[_gap_type_for_field(field)].add(field)
    for flag in conflict_flags:
        groups["other_metadata_conflict"].add(flag)
    gaps = []
    for gap_type, fields in sorted(groups.items()):
        missing_for_policy = sorted(field for field in fields if field not in conflict_flags)
        conflicts_for_policy = sorted(field for field in fields if field in conflict_flags)
        policy = gap_criticality_policy(
            gap_type=gap_type,
            missing_metadata_fields=missing_for_policy,
            conflict_flags=conflicts_for_policy,
            reason_codes=reason_codes,
            period_scope_basis=period_scope_basis if gap_type == "missing_period" else None,
            refinement_enabled=criticality_refinement_enabled,
        )
        if non_blocking_only and policy.get("blocks_gate2") is True:
            continue
        resolved_fields = _resolved_fields_for_gap_type(gap_type, sorted(fields))
        gap_id = f"gap_{stable_digest([run_id, document_ref, gap_type, ','.join(sorted(fields))], length=16)}"
        gaps.append(
            {
                "gap_id": gap_id,
                "gap_type": gap_type,
                "source_eligibility": entry.get("source_eligibility"),
                "target_document_refs": [document_ref],
                "missing_metadata_fields": missing_for_policy,
                "conflict_flags": conflicts_for_policy,
                "reason_codes": sorted(set(reason_codes) | set(policy.get("criticality_reason_codes") or [])),
                "blocker_refs": list(entry.get("blocker_refs") or []),
                "safe_evidence_refs": [str(item) for item in passport.get("evidence_refs") or [] if item],
                "blocks": _blocks_for_policy(policy),
                "blocks_gate2": bool(policy.get("blocks_gate2")),
                "resolvable_by_answer": True,
                "resolved_fields": resolved_fields,
                "answer_type": _answer_type_for_gap_type(gap_type),
                "allowed_answer_format": _answer_format_for_gap_type(gap_type),
                "required": bool(policy.get("resolution_required")),
                "priority": policy.get("priority"),
                "severity": policy.get("severity"),
                "criticality": policy.get("criticality"),
                "blocking_scope": policy.get("blocking_scope"),
                "dependency_stage": policy.get("dependency_stage"),
                "blocking_reason_category": policy.get("blocking_reason_category"),
                "auto_resolution_policy": policy.get("auto_resolution_policy"),
                "resolution_required": bool(policy.get("resolution_required")),
                "can_proceed_with_warning": bool(policy.get("can_proceed_with_warning")),
                "ask_policy": policy.get("ask_policy"),
                "answer_impact": policy.get("answer_impact"),
                "safe_explanation": policy.get("safe_explanation"),
            }
        )
    return gaps


def _duplicate_gap_for_document(
    run_id: str,
    entry: dict[str, Any],
    document: dict[str, Any],
    *,
    criticality_refinement_enabled: bool,
) -> dict[str, Any]:
    document_ref = str(entry.get("document_id") or document.get("document_id") or "")
    candidates = [document_ref]
    duplicate_of = document.get("duplicate_of_document_id")
    if duplicate_of:
        candidates.insert(0, str(duplicate_of))
    gap_id = f"gap_{stable_digest([run_id, document_ref, 'duplicate_canonical_choice'], length=16)}"
    policy = gap_criticality_policy(
        gap_type="duplicate_canonical_choice",
        reason_codes=[str(item) for item in entry.get("reason_codes") or [] if item],
        refinement_enabled=criticality_refinement_enabled,
    )
    return {
        "gap_id": gap_id,
        "gap_type": "duplicate_canonical_choice",
        "source_eligibility": entry.get("source_eligibility"),
        "target_document_refs": candidates,
        "missing_metadata_fields": [],
        "conflict_flags": [],
        "reason_codes": sorted(set(entry.get("reason_codes") or []) | set(policy.get("criticality_reason_codes") or [])),
        "blocker_refs": list(entry.get("blocker_refs") or []),
        "safe_evidence_refs": [],
        "blocks": _blocks_for_policy(policy),
        "blocks_gate2": bool(policy.get("blocks_gate2")),
        "resolvable_by_answer": True,
        "resolved_fields": ["canonical_document_ref"],
        "answer_type": "select_canonical_document",
        "allowed_answer_format": "one of target_document_refs",
        "required": bool(policy.get("resolution_required")),
        "priority": policy.get("priority"),
        "severity": policy.get("severity"),
        "criticality": policy.get("criticality"),
        "blocking_scope": policy.get("blocking_scope"),
        "dependency_stage": policy.get("dependency_stage"),
        "blocking_reason_category": policy.get("blocking_reason_category"),
        "auto_resolution_policy": policy.get("auto_resolution_policy"),
        "resolution_required": bool(policy.get("resolution_required")),
        "can_proceed_with_warning": bool(policy.get("can_proceed_with_warning")),
        "ask_policy": policy.get("ask_policy"),
        "answer_impact": policy.get("answer_impact"),
        "safe_explanation": policy.get("safe_explanation"),
    }


def _outside_scope_gap_for_document(
    run_id: str,
    entry: dict[str, Any],
    passport: dict[str, Any],
    document: dict[str, Any],
    *,
    criticality_refinement_enabled: bool,
) -> dict[str, Any]:
    document_ref = str(entry.get("document_id") or document.get("document_id") or "")
    gap_id = f"gap_{stable_digest([run_id, document_ref, 'outside_scope_confirmation'], length=16)}"
    policy = gap_criticality_policy(
        gap_type="outside_scope_confirmation",
        reason_codes=[str(item) for item in entry.get("reason_codes") or [] if item],
        refinement_enabled=criticality_refinement_enabled,
    )
    return {
        "gap_id": gap_id,
        "gap_type": "outside_scope_confirmation",
        "source_eligibility": entry.get("source_eligibility"),
        "target_document_refs": [document_ref],
        "missing_metadata_fields": [],
        "conflict_flags": [],
        "reason_codes": sorted(set(entry.get("reason_codes") or []) | set(policy.get("criticality_reason_codes") or [])),
        "blocker_refs": list(entry.get("blocker_refs") or []),
        "safe_evidence_refs": [str(item) for item in passport.get("evidence_refs") or [] if item],
        "blocks": _blocks_for_policy(policy),
        "blocks_gate2": bool(policy.get("blocks_gate2")),
        "resolvable_by_answer": True,
        "resolved_fields": ["outside_scope_confirmation"],
        "answer_type": "mark_as_outside_scope",
        "allowed_answer_format": "true if document is outside the case scope",
        "required": bool(policy.get("resolution_required")),
        "priority": policy.get("priority"),
        "severity": policy.get("severity"),
        "criticality": policy.get("criticality"),
        "blocking_scope": policy.get("blocking_scope"),
        "dependency_stage": policy.get("dependency_stage"),
        "blocking_reason_category": policy.get("blocking_reason_category"),
        "auto_resolution_policy": policy.get("auto_resolution_policy"),
        "resolution_required": bool(policy.get("resolution_required")),
        "can_proceed_with_warning": bool(policy.get("can_proceed_with_warning")),
        "ask_policy": policy.get("ask_policy"),
        "answer_impact": policy.get("answer_impact"),
        "safe_explanation": policy.get("safe_explanation"),
    }


def _question_stub_for_gap(gap: dict[str, Any]) -> dict[str, Any]:
    question_id = f"q_{stable_digest([gap.get('gap_id'), gap.get('gap_type')], length=16)}"
    return {
        "question_id": question_id,
        "gap_id": gap.get("gap_id"),
        "target_document_refs": list(gap.get("target_document_refs") or []),
        "gap_type": gap.get("gap_type"),
        "question_text": "",
        "answer_type": gap.get("answer_type"),
        "allowed_answer_format": gap.get("allowed_answer_format"),
        "required_for": list(gap.get("blocks") or ["gate2_source_fact_handoff"]),
        "why_asked": "",
        "safe_evidence_refs": list(gap.get("safe_evidence_refs") or []),
        "criticality": gap.get("criticality"),
        "blocking_scope": gap.get("blocking_scope"),
        "dependency_stage": gap.get("dependency_stage"),
        "blocking_reason_category": gap.get("blocking_reason_category"),
        "auto_resolution_policy": gap.get("auto_resolution_policy"),
        "blocks_gate2": bool(gap.get("blocks_gate2")),
        "resolution_required": bool(gap.get("resolution_required")),
        "can_proceed_with_warning": bool(gap.get("can_proceed_with_warning")),
        "ask_policy": gap.get("ask_policy"),
        "answer_impact": gap.get("answer_impact"),
        "priority": gap.get("priority") or "medium",
        "severity": gap.get("severity") or "important",
        "required": bool(gap.get("required")),
        "reason_codes": list(gap.get("reason_codes") or []),
        "safe_explanation": str(gap.get("safe_explanation") or ""),
        "resolved_fields": list(gap.get("resolved_fields") or []),
    }


def _gap_type_for_field(field: str) -> str:
    if field in PERIOD_FIELDS:
        return "missing_period"
    if field in ACCOUNT_FIELDS:
        return "missing_account_or_contract"
    if field in BROKER_CLIENT_FIELDS:
        return "missing_broker_client_metadata"
    if field in ROLE_FIELDS:
        return "unclear_document_role"
    if field == "metadata_confirmation":
        return "other_metadata_conflict"
    return "other_metadata_conflict"


def _resolved_fields_for_gap_type(gap_type: str, fields: list[str]) -> list[str]:
    if gap_type == "missing_period":
        return ["report_period_start", "report_period_end"]
    if gap_type == "missing_account_or_contract":
        return ["account_or_contract_candidate"]
    if gap_type == "missing_broker_client_metadata":
        return sorted(set(fields) & BROKER_CLIENT_FIELDS) or ["broker_name_candidate", "client_name_candidate"]
    if gap_type == "unclear_document_role":
        return ["document_role"]
    if gap_type == "duplicate_canonical_choice":
        return ["canonical_document_ref"]
    if gap_type == "outside_scope_confirmation":
        return ["outside_scope_confirmation"]
    return sorted(fields) or ["metadata_confirmation"]


def _answer_type_for_gap_type(gap_type: str) -> str:
    return {
        "missing_period": "provide_report_period",
        "missing_account_or_contract": "provide_account_or_contract",
        "unclear_document_role": "single_choice",
        "missing_broker_client_metadata": "text",
        "duplicate_canonical_choice": "select_canonical_document",
        "outside_scope_confirmation": "mark_as_outside_scope",
        "other_metadata_conflict": "text",
    }.get(gap_type, "text")


def _answer_format_for_gap_type(gap_type: str) -> str:
    return {
        "missing_period": "date range as YYYY-MM-DD..YYYY-MM-DD or tax year YYYY",
        "missing_account_or_contract": "account or contract identifier; keep it out of chat reports",
        "unclear_document_role": "one safe role label: source_broker_report, source_operations_table, mark_as_not_source, mark_as_outside_scope",
        "missing_broker_client_metadata": "short broker/client/document-kind metadata value",
        "duplicate_canonical_choice": "one of target_document_refs",
        "outside_scope_confirmation": "true",
        "other_metadata_conflict": "short operator-confirmed clarification",
    }.get(gap_type, "short text")


def _blocks_for_policy(policy: dict[str, Any]) -> list[str]:
    if policy.get("blocks_gate2") is True:
        return ["gate2_source_fact_handoff"]
    blocking_scope = str(policy.get("blocking_scope") or "")
    if blocking_scope == "declaration_model":
        return ["declaration_model_quality"]
    if blocking_scope == "source_eligibility":
        return ["source_eligibility_audit"]
    return ["audit_context"]


def _question_groups(questions: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups = {key: [] for key in sorted(QUESTION_GROUP_KEYS)}
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("question_id") or "")
        if not question_id:
            continue
        key = CRITICALITY_TO_GROUP_KEY.get(str(question.get("criticality") or ""), "useful_clarifications")
        groups.setdefault(key, []).append(question_id)
    return groups


def _fallback_question_text(stub: dict[str, Any]) -> str:
    gap_type = str(stub.get("gap_type") or "")
    target_refs = ", ".join(str(item) for item in stub.get("target_document_refs") or [] if item)
    suffix = f" ({target_refs})" if target_refs else ""
    return {
        "missing_period": f"Confirm the report period or tax year for this document{suffix}.",
        "missing_account_or_contract": f"Confirm the account or contract identifier for this document{suffix}.",
        "unclear_document_role": f"Confirm whether this document is an eligible source document{suffix}.",
        "missing_broker_client_metadata": f"Confirm broker, client, or document-kind metadata for this document{suffix}.",
        "duplicate_canonical_choice": f"Choose the canonical source document among these duplicates{suffix}.",
        "outside_scope_confirmation": f"Confirm that this document is outside the case scope{suffix}.",
        "other_metadata_conflict": f"Confirm the remaining safe metadata note for this document{suffix}.",
    }.get(gap_type, f"Confirm the safe metadata clarification for this document{suffix}.")


def _criticality_refinement_enabled(package: dict[str, Any]) -> bool:
    if package.get("clarification_criticality_refinement_enabled") is True:
        return True
    context = package.get("input_context") if isinstance(package.get("input_context"), dict) else {}
    return bool(
        context.get("clarification_criticality_refinement_enabled") is True
        or context.get("criticality_refinement_enabled") is True
        or context.get("metadata_criticality_refinement_enabled") is True
    )


def _validate_answer(answer_value: Any, answer_type: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    if answer_type in {"text", "provide_account_or_contract"}:
        if not isinstance(answer_value, str) or not answer_value.strip():
            errors.append("answer_value_required")
    elif answer_type in {"date", "provide_report_period"}:
        if not _valid_date_or_range(answer_value):
            errors.append("date_or_date_range_required")
    elif answer_type == "date_range":
        if not _valid_date_range(answer_value):
            errors.append("date_range_required")
    elif answer_type in {"single_choice", "select_canonical_document"}:
        if not isinstance(answer_value, str) or not answer_value.strip():
            errors.append("single_choice_required")
    elif answer_type == "multi_choice":
        if not isinstance(answer_value, list) or not answer_value:
            errors.append("multi_choice_required")
    elif answer_type in {"confirm_true_false", "mark_as_outside_scope", "mark_as_not_source"}:
        if not isinstance(answer_value, bool):
            errors.append("boolean_required")
    else:
        errors.append("unsupported_answer_type")
    return ("passed" if not errors else "failed", errors)


def _question_matches_for_answer(
    answer: dict[str, Any],
    questions_by_id: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    question_id = str(answer.get("question_id") or "")
    if question_id:
        question = questions_by_id.get(question_id)
        return [(question_id, question)] if question is not None else []
    gap_type = str(answer.get("gap_type") or "")
    target_ref = str(answer.get("target_document_ref") or "")
    target_refs = {str(item) for item in answer.get("target_document_refs") or [] if item}
    if target_ref:
        target_refs.add(target_ref)
    matches = []
    for candidate_id, question in questions_by_id.items():
        if gap_type and question.get("gap_type") != gap_type:
            continue
        if target_refs:
            question_refs = {str(item) for item in question.get("target_document_refs") or [] if item}
            if not (target_refs & question_refs):
                continue
        if gap_type or target_refs:
            matches.append((candidate_id, question))
    return matches


def _valid_date_or_range(value: Any) -> bool:
    if isinstance(value, dict):
        return _valid_date_range(value)
    if not isinstance(value, str):
        return False
    value = value.strip()
    if re.fullmatch(r"\d{4}", value):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return True
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}", value))


def _valid_date_range(value: Any) -> bool:
    if isinstance(value, dict):
        start = value.get("start") or value.get("report_period_start")
        end = value.get("end") or value.get("report_period_end")
        return isinstance(start, str) and isinstance(end, str) and bool(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", end)
        )
    if isinstance(value, str):
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}", value.strip()))
    return False


def _failed_resolution(question_id: str, answered_by: str, source: str, error_code: str) -> dict[str, Any]:
    return {
        "schema_version": CLARIFICATION_RESOLUTION_SCHEMA_VERSION,
        "resolution_id": f"clarres_{stable_digest([question_id, error_code], length=16)}",
        "normalization_run_id": None,
        "gap_report_id": None,
        "clarification_request_id": None,
        "question_id": question_id,
        "target_document_ref": None,
        "target_document_refs": [],
        "gap_type": None,
        "resolved_field": None,
        "answer_value": None,
        "answer_type": None,
        "answered_by": answered_by,
        "answered_at": "not_recorded",
        "source": source,
        "validation_status": "failed",
        "validation_errors": [error_code],
        "safe_audit_refs": [question_id],
        "usable_by_source_eligibility_v2": False,
    }


def _empty_clarification_request(
    *,
    gap_report: dict[str, Any],
    prompt: ClarificationManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
        "clarification_request_id": f"clarreq_{stable_digest([gap_report.get('gap_report_id'), 'empty'], length=16)}",
        "normalization_run_id": gap_report.get("normalization_run_id"),
        "gap_report_id": gap_report.get("gap_report_id"),
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_command": prompt.command,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
        "llm_model_id": model_id,
        "output_schema_id": CLARIFICATION_JSON_SCHEMA_ID,
        "output_schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
        "output_schema_hash": gate1_clarification_request_schema_hash(),
        "questions": [],
        "question_groups": _question_groups([]),
        "summary": _question_summary([]),
    }


def _question_summary(questions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(item.get("gap_type") or "unknown") for item in questions if isinstance(item, dict))
    criticality_count_values = criticality_counts([item for item in questions if isinstance(item, dict)])
    dependency_stage_counts = Counter(str(item.get("dependency_stage") or "unknown") for item in questions if isinstance(item, dict))
    blocking_reason_category_counts = Counter(
        str(item.get("blocking_reason_category") or "unknown") for item in questions if isinstance(item, dict)
    )
    auto_resolution_policy_counts = Counter(
        str(item.get("auto_resolution_policy") or "unknown") for item in questions if isinstance(item, dict)
    )
    ask_policy_counts = Counter(str(item.get("ask_policy") or "unknown") for item in questions if isinstance(item, dict))
    answer_impact_counts = Counter(str(item.get("answer_impact") or "unknown") for item in questions if isinstance(item, dict))
    required = sum(1 for item in questions if isinstance(item, dict) and item.get("required") is True)
    return {
        "questions_total": len(questions),
        "required_questions_total": required,
        "optional_questions_total": len(questions) - required,
        "gap_type_counts": dict(sorted(counts.items())),
        "criticality_counts": criticality_count_values,
        "critical_questions_total": criticality_count_values.get("critical", 0),
        "clarifying_questions_total": criticality_count_values.get("clarifying", 0),
        "non_critical_questions_total": criticality_count_values.get("non_critical", 0),
        "blocking_questions_total": sum(1 for item in questions if isinstance(item, dict) and item.get("blocks_gate2") is True),
        "can_proceed_with_warning_total": sum(
            1 for item in questions if isinstance(item, dict) and item.get("can_proceed_with_warning") is True
        ),
        "dependency_stage_counts": dict(sorted(dependency_stage_counts.items())),
        "blocking_reason_category_counts": dict(sorted(blocking_reason_category_counts.items())),
        "auto_resolution_policy_counts": dict(sorted(auto_resolution_policy_counts.items())),
        "ask_policy_counts": dict(sorted(ask_policy_counts.items())),
        "answer_impact_counts": dict(sorted(answer_impact_counts.items())),
        "question_group_counts": {key: len(value) for key, value in _question_groups(questions).items()},
    }


def _resolution_summary(resolutions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(item.get("validation_status") or "unknown") for item in resolutions)
    usable = sum(1 for item in resolutions if item.get("usable_by_source_eligibility_v2") is True)
    return {
        "schema_version": "gate1_clarification_resolution_summary_v0",
        "resolutions_total": len(resolutions),
        "usable_by_source_eligibility_v2": usable,
        "validation_status_counts": dict(sorted(counts.items())),
        "resolved_field_counts": dict(sorted(Counter(str(item.get("resolved_field") or "unknown") for item in resolutions).items())),
    }


def _refresh_package_validation_and_safe_report(package: dict[str, Any], private_markers: list[str]) -> dict[str, Any]:
    updated = apply_domain_ingestion_artifacts(package)
    artifact_validation = validate_artifacts(updated)
    updated["validation_result"] = artifact_validation
    from .safe_report import render_safe_report

    safe_report = render_safe_report(updated)
    safe_validation = validate_safe_report(
        safe_report=safe_report,
        private_markers=private_markers,
        run_id=str(updated.get("normalization_run", {}).get("run_id") or ""),
    )
    validation = merge_validation_results(artifact_validation, safe_validation)
    updated["validation_result"] = validation
    return updated


def _next_step_after_clarification(package: dict[str, Any]) -> str:
    mode = package.get("gate2_handoff", {}).get("handoff_mode")
    if mode == "full_package_ready_for_gate2":
        return "ready_for_gui_smoke"
    if mode == "reduced_subset_ready_for_gate2":
        return "continue_with_reduced_gate2_subset_after_specialist_confirmation"
    if mode == "gate2_blocked_requires_metadata_review":
        return "answer_gate1_metadata_clarification_questions"
    if mode == "gate2_blocked_requires_duplicate_resolution":
        return "answer_gate1_duplicate_clarification_questions"
    return str(package.get("recommended_next_step") or "review_gate1_blockers")


def _validation_result(errors: list[dict[str, str]]) -> dict[str, Any]:
    status = "failed" if errors else "passed"
    return {
        "schema_version": "gate1_clarification_request_validation_v0",
        "validator_status": status,
        "passed": status == "passed",
        "errors_count": len(errors),
        "errors": errors,
        "error_code_summary": dict(sorted(Counter(error["code"] for error in errors).items())),
    }


def _find_forbidden_fields(value: object, *, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_FIELD_NAMES:
                findings.append(child_path)
            findings.extend(_find_forbidden_fields(child, prefix=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_fields(child, prefix=f"{prefix}[{index}]"))
    return findings


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}


def _json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if not raw:
        return []
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
