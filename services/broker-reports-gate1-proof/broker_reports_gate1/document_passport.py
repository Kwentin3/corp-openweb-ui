from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import blockers as blocker_factory
from .contracts import stable_digest
from .domain_ingestion import apply_domain_ingestion_artifacts
from .eligibility import build_document_source_eligibility
from .safe_report import render_privacy_failed_report, render_safe_report
from .validators import merge_validation_results, validate_artifacts, validate_safe_report


FACTORY_REQUIRED = "DocumentPassportPromptResolverFactory.create is the only production prompt resolver entrypoint"
FORBIDDEN = "Pipe and normalizer must not read OpenWebUI prompt tables directly"

PROMPT_CONTRACT_ID = "broker_reports_document_metadata_passport_prompt_v0"
PROMPT_TEMPLATE_ID = "broker_reports.document_metadata_passport.v0"
PROMPT_TEMPLATE_KIND = "document_metadata_passport"
PROMPT_REQUIRED_TAG = "broker-reports-gate1"
INPUT_SCHEMA_VERSION = "broker_reports_llm_document_package_v0"
PASSPORT_SCHEMA_VERSION = "document_metadata_passport_v0"
PASSPORT_VALIDATION_SCHEMA_VERSION = "document_metadata_passport_validation_v0"
PROMPT_SNAPSHOT_SCHEMA_VERSION = "llm_prompt_snapshot_v0"
RAW_OUTPUT_SCHEMA_VERSION = "llm_passport_raw_output_v0"
PASSPORT_JSON_SCHEMA_ID = "broker_reports.document_metadata_passport.schema.v0"
PASSPORT_JSON_SCHEMA_NAME = "document_metadata_passport_v0"
PASSPORT_SCHEMA_HASH_ALGORITHM = "sha256"
STRUCTURED_OUTPUT_MODE_JSON_SCHEMA = "openwebui_response_format_json_schema"
STRUCTURED_OUTPUT_MODE_JSON_OBJECT_FALLBACK = "openwebui_response_format_json_object_fallback"
STRUCTURED_OUTPUT_MODE_UNCONSTRAINED_TEST = "test_client_unconstrained"

REQUIRED_PASSPORT_FIELDS = {
    "schema_version",
    "passport_id",
    "normalization_run_id",
    "case_group_id",
    "document_id",
    "source_file_ref",
    "passport_status",
    "document_title_candidate",
    "document_kind_candidate",
    "broker_name_candidate",
    "client_name_candidate",
    "account_or_contract_candidate",
    "report_period_start",
    "report_period_end",
    "tax_year_candidate",
    "created_at_candidate",
    "document_language",
    "document_format",
    "container_format",
    "content_kind",
    "sections_detected",
    "tables_detected",
    "operation_sections_detected",
    "cashflow_sections_detected",
    "income_sections_detected",
    "withholding_sections_detected",
    "tax_sections_detected",
    "role_hypotheses",
    "source_candidate_confidence",
    "metadata_confidence",
    "evidence_refs",
    "missing_metadata_fields",
    "conflict_flags",
    "review_required",
    "llm_prompt_ref",
    "llm_prompt_command",
    "llm_prompt_version",
    "llm_prompt_hash",
    "llm_model_id",
    "llm_input_refs",
    "validator_status",
    "validator_errors",
    "created_at",
}

CRITICAL_METADATA_FIELDS = {
    "document_kind_candidate",
    "broker_name_candidate",
    "account_or_contract_candidate",
    "report_period_start",
    "report_period_end",
    "content_kind",
}

CONFIDENCE_VALUES = {"none", "low", "medium", "high"}
PASSPORT_STATUSES = {"draft", "validated", "blocked", "privacy_failed"}
VALIDATOR_STATUSES = {"pending", "passed", "failed", "privacy_failed"}
DOCUMENT_KIND_VALUES = {
    "broker_activity_statement",
    "broker_annual_report",
    "broker_tax_report",
    "dividend_report",
    "withholding_report",
    "fees_report",
    "cashflow_report",
    "operations_table",
    "currency_rate_table",
    "methodology_document",
    "calculation_template",
    "tax_output_or_declaration_artifact",
    "official_form",
    "duplicate_or_cover",
    "unknown",
}
CONTENT_KIND_VALUES = {
    "source_report_candidate",
    "methodology_or_reference",
    "output_or_calculation_artifact",
    "duplicate_candidate",
    "outside_case_scope",
    "unsupported_or_unreadable",
    "unknown",
}
SECTION_LABEL_VALUES = {
    "summary",
    "account_information",
    "report_period",
    "positions",
    "operations",
    "trades",
    "cashflow",
    "dividends",
    "coupons",
    "interest",
    "fees",
    "withholding",
    "tax",
    "currency",
    "other_income",
    "unknown",
}
ROWS_COUNT_BUCKET_VALUES = {"none", "present", "many", "unknown"}
ROLE_VALUES = {
    "source_broker_report",
    "source_operations_table",
    "source_dividend_report",
    "source_withholding_report",
    "source_cashflow_report",
    "methodology_or_reference",
    "calculation_or_output_artifact",
    "official_form_or_declaration",
    "duplicate_candidate",
    "outside_case_scope",
    "unknown",
}
SOURCE_POLICY_EFFECT_VALUES = {
    "accepted_candidate_if_policy_allows",
    "requires_policy_review",
    "metadata_review_required",
    "excluded_from_gate2",
    "no_effect",
}
DOCUMENT_LANGUAGE_VALUES = {"ru", "en", "mixed", "unknown"}

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


class DocumentPassportError(RuntimeError):
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
class DocumentPassportPromptConfig:
    source: str = "openwebui_sqlite"
    db_path: Path | None = None
    prompt_id: str | None = None
    command: str | None = None
    required_template_id: str = PROMPT_TEMPLATE_ID
    required_template_kind: str = PROMPT_TEMPLATE_KIND
    required_output_schema_version: str = PASSPORT_SCHEMA_VERSION
    required_tag: str = PROMPT_REQUIRED_TAG


@dataclass(frozen=True)
class ManagedPrompt:
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
            "schema_version": PROMPT_SNAPSHOT_SCHEMA_VERSION,
            "llm_prompt_ref": self.prompt_ref,
            "llm_prompt_command": self.command,
            "llm_prompt_version": self.version,
            "llm_prompt_hash": self.hash,
            "llm_prompt_source": self.source,
            "prompt_contract_id": PROMPT_CONTRACT_ID,
            "template_id": self.template_id,
            "template_kind": self.template_kind,
            "output_schema_version": self.output_schema_version,
            "output_schema_id": PASSPORT_JSON_SCHEMA_ID,
            "output_schema_hash_algorithm": PASSPORT_SCHEMA_HASH_ALGORITHM,
            "output_schema_hash": document_metadata_passport_schema_hash(),
            "tags": list(self.tags),
            "safe_metadata": copy.deepcopy(self.safe_metadata),
        }


class DocumentPassportPromptResolver(Protocol):
    def resolve(self, user_context: PromptUserContext) -> ManagedPrompt:
        ...


class DocumentPassportPromptResolverFactory:
    def __init__(self, config: DocumentPassportPromptConfig) -> None:
        self.config = config

    def create(self) -> DocumentPassportPromptResolver:
        if self.config.source == "openwebui_sqlite":
            if self.config.db_path is None:
                raise DocumentPassportError("passport_prompt_unavailable", "OpenWebUI prompt DB path is not configured")
            return OpenWebUISqliteDocumentPassportPromptResolver(self.config)
        if self.config.source == "disabled":
            return DisabledDocumentPassportPromptResolver()
        raise DocumentPassportError("passport_prompt_unavailable", "Unsupported document passport prompt source")


class DisabledDocumentPassportPromptResolver:
    def resolve(self, user_context: PromptUserContext) -> ManagedPrompt:
        raise DocumentPassportError("passport_prompt_disabled", "Document metadata passport prompt resolver is disabled")


class StaticDocumentPassportPromptResolver:
    def __init__(self, prompt: ManagedPrompt) -> None:
        self.prompt = prompt

    def resolve(self, user_context: PromptUserContext) -> ManagedPrompt:
        return self.prompt


class OpenWebUISqliteDocumentPassportPromptResolver:
    def __init__(self, config: DocumentPassportPromptConfig) -> None:
        self.config = config
        self.db_path = config.db_path

    def resolve(self, user_context: PromptUserContext) -> ManagedPrompt:
        conn = self._connect()
        try:
            row = self._find_prompt(conn)
            if row is None:
                raise DocumentPassportError("passport_prompt_not_found", "Document metadata passport prompt was not found")
            if not self._has_read_access(row, user_context, conn):
                raise DocumentPassportError("passport_prompt_access_denied", "Document metadata passport prompt is not readable")
            return self._row_to_prompt(row)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None or not self.db_path.exists():
            raise DocumentPassportError("passport_prompt_unavailable", "OpenWebUI prompt DB file is not available")
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
        raise DocumentPassportError("passport_prompt_not_found", "Prompt id or command is required")

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

    def _row_to_prompt(self, row: sqlite3.Row) -> ManagedPrompt:
        content = str(row["content"] or "")
        meta = _json_dict(row["meta"])
        tags = tuple(_json_list(row["tags"]))
        template_id = str(meta.get("template_id") or meta.get("stage2_template_id") or self.config.required_template_id)
        template_kind = str(meta.get("template_kind") or self.config.required_template_kind)
        output_schema = str(meta.get("output_schema_version") or self.config.required_output_schema_version)
        return ManagedPrompt(
            prompt_ref=str(row["id"]),
            command=str(row["command"] or "") or None,
            version=str(row["version_id"] or "") or None,
            content=content,
            hash=prompt_hash(content, PROMPT_CONTRACT_ID, output_schema),
            source="openwebui_prompt",
            template_id=template_id,
            template_kind=template_kind,
            output_schema_version=output_schema,
            tags=tags,
            safe_metadata={
                "name": str(row["name"] or row["command"] or ""),
                "prompt_contract_id": PROMPT_CONTRACT_ID,
            },
        )

    def _has_read_access(
        self,
        row: sqlite3.Row,
        user_context: PromptUserContext,
        conn: sqlite3.Connection,
    ) -> bool:
        role = str(user_context.user_role or "").lower()
        user_id = str(user_context.user_id or "")
        groups = {str(group) for group in user_context.user_groups if group}
        if role == "admin":
            return True
        if user_id and user_id == row["user_id"]:
            return True
        try:
            grants = conn.execute(
                """
                SELECT principal_type, principal_id, permission
                FROM access_grant
                WHERE resource_type = 'prompt'
                  AND resource_id = ?
                  AND permission = 'read'
                """,
                (row["id"],),
            ).fetchall()
        except sqlite3.Error:
            grants = []
        for grant in grants:
            principal_type = str(grant["principal_type"] or "")
            principal_id = str(grant["principal_id"] or "")
            if principal_type == "user" and principal_id == "*":
                return True
            if user_id and principal_type == "user" and principal_id == user_id:
                return True
            if principal_type == "group" and principal_id in groups:
                return True
        return False


class DocumentPassportModelClient(Protocol):
    def create_passport(
        self,
        *,
        prompt: ManagedPrompt,
        document_package: dict[str, Any],
        model_id: str,
    ) -> Any:
        ...


def prompt_hash(prompt_content: str, contract_id: str, output_schema_version: str) -> str:
    material = (
        prompt_content.replace("\r\n", "\n").strip()
        + "\ncontract:"
        + contract_id
        + "\nschema:"
        + output_schema_version
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def document_metadata_passport_json_schema() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    evidence_array = {"type": "array", "items": {"type": "string"}}
    section_descriptor = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string"},
            "normalized_label": {"type": "string", "enum": sorted(SECTION_LABEL_VALUES)},
            "present": {"type": "boolean"},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "evidence_refs": evidence_array,
        },
        "required": ["label", "normalized_label", "present", "confidence", "evidence_refs"],
    }
    table_descriptor = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "table_ref": {"type": "string"},
            "normalized_label": {"type": "string", "enum": sorted(SECTION_LABEL_VALUES)},
            "header_signals": string_array,
            "rows_count_bucket": {"type": "string", "enum": sorted(ROWS_COUNT_BUCKET_VALUES)},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "evidence_refs": evidence_array,
        },
        "required": [
            "table_ref",
            "normalized_label",
            "header_signals",
            "rows_count_bucket",
            "confidence",
            "evidence_refs",
        ],
    }
    role_hypothesis = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "role": {"type": "string", "enum": sorted(ROLE_VALUES)},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "reason_codes": string_array,
            "evidence_refs": evidence_array,
            "source_policy_effect": {"type": "string", "enum": sorted(SOURCE_POLICY_EFFECT_VALUES)},
        },
        "required": ["role", "confidence", "reason_codes", "evidence_refs", "source_policy_effect"],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [PASSPORT_SCHEMA_VERSION]},
            "passport_id": {"type": "string"},
            "normalization_run_id": {"type": "string"},
            "case_group_id": {"type": ["string", "null"]},
            "document_id": {"type": "string"},
            "source_file_ref": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": ["string", "null"]},
                    "safe_ref": {"type": "string"},
                },
                "required": ["provider", "safe_ref"],
            },
            "passport_status": {"type": "string", "enum": sorted(PASSPORT_STATUSES)},
            "document_title_candidate": {"type": ["string", "null"]},
            "document_kind_candidate": {"type": ["string", "null"], "enum": [None, *sorted(DOCUMENT_KIND_VALUES)]},
            "broker_name_candidate": {"type": ["string", "null"]},
            "client_name_candidate": {"type": ["string", "null"]},
            "account_or_contract_candidate": {"type": ["string", "null"]},
            "report_period_start": {"type": ["string", "null"]},
            "report_period_end": {"type": ["string", "null"]},
            "tax_year_candidate": {"type": ["integer", "null"]},
            "created_at_candidate": {"type": ["string", "null"]},
            "document_language": {"type": ["string", "null"], "enum": [None, *sorted(DOCUMENT_LANGUAGE_VALUES)]},
            "document_format": {"type": ["string", "null"]},
            "container_format": {"type": ["string", "null"]},
            "content_kind": {"type": ["string", "null"], "enum": [None, *sorted(CONTENT_KIND_VALUES)]},
            "sections_detected": {"type": "array", "items": section_descriptor},
            "tables_detected": {"type": "array", "items": table_descriptor},
            "operation_sections_detected": {"type": "array", "items": section_descriptor},
            "cashflow_sections_detected": {"type": "array", "items": section_descriptor},
            "income_sections_detected": {"type": "array", "items": section_descriptor},
            "withholding_sections_detected": {"type": "array", "items": section_descriptor},
            "tax_sections_detected": {"type": "array", "items": section_descriptor},
            "role_hypotheses": {"type": "array", "items": role_hypothesis},
            "source_candidate_confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "metadata_confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "evidence_refs": evidence_array,
            "missing_metadata_fields": string_array,
            "conflict_flags": string_array,
            "review_required": {"type": "boolean"},
            "llm_prompt_ref": {"type": "string"},
            "llm_prompt_command": {"type": ["string", "null"]},
            "llm_prompt_version": {"type": ["string", "null"]},
            "llm_prompt_hash": {"type": "string"},
            "llm_model_id": {"type": "string"},
            "llm_input_refs": string_array,
            "validator_status": {"type": "string", "enum": sorted(VALIDATOR_STATUSES)},
            "validator_errors": string_array,
            "created_at": {"type": "string"},
        },
        "required": sorted(REQUIRED_PASSPORT_FIELDS),
    }
    return copy.deepcopy(schema)


def document_metadata_passport_schema_hash() -> str:
    payload = json.dumps(document_metadata_passport_json_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def passport_json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": PASSPORT_JSON_SCHEMA_NAME,
            "strict": True,
            "schema": document_metadata_passport_json_schema(),
        },
    }


def passport_json_object_response_format() -> dict[str, str]:
    return {"type": "json_object"}


def passport_schema_audit_metadata() -> dict[str, Any]:
    return {
        "output_schema_id": PASSPORT_JSON_SCHEMA_ID,
        "output_schema_version": PASSPORT_SCHEMA_VERSION,
        "output_schema_hash_algorithm": PASSPORT_SCHEMA_HASH_ALGORITHM,
        "output_schema_hash": document_metadata_passport_schema_hash(),
    }


def model_call_audit_metadata(
    *,
    prompt: ManagedPrompt,
    model_id: str,
    structured_output_mode: str,
    response_format_type: str,
    response_format_schema_mode: str | None,
    schema_attempted: bool,
    fallback_used: bool = False,
    native_error_code: str | None = None,
    repair_attempted: bool = False,
    repair_attempt_count: int = 0,
    validator_error_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "structured_output_mode": structured_output_mode,
        "response_format_type": response_format_type,
        "response_format_schema_mode": response_format_schema_mode,
        "schema_attempted": schema_attempted,
        "fallback_used": fallback_used,
        "native_structured_output_error_code": native_error_code,
        "repair_attempted": repair_attempted,
        "repair_attempt_count": repair_attempt_count,
        "llm_model_id": model_id,
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_command": prompt.command,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
        "validator_error_summary": copy.deepcopy(validator_error_summary or {}),
        **passport_schema_audit_metadata(),
    }


def parse_document_passport_model_output(value: Any) -> Any:
    return _parse_model_output(value)


def validation_error_summary(validation: dict[str, Any]) -> dict[str, Any]:
    errors = validation.get("errors") if isinstance(validation, dict) else []
    code_counts: dict[str, int] = {}
    subjects_by_code: dict[str, list[str]] = {}
    if isinstance(errors, list):
        for error in errors:
            if not isinstance(error, dict):
                continue
            code = str(error.get("code") or "unknown")
            code_counts[code] = code_counts.get(code, 0) + 1
            subject = str(error.get("subject") or "")
            if subject:
                subjects = subjects_by_code.setdefault(code, [])
                if subject not in subjects and len(subjects) < 20:
                    subjects.append(subject)
    return {
        "validator_status": validation.get("validator_status") if isinstance(validation, dict) else "failed",
        "errors_count": int(validation.get("errors_count") or sum(code_counts.values())) if isinstance(validation, dict) else sum(code_counts.values()),
        "error_codes": sorted(code_counts),
        "error_code_counts": dict(sorted(code_counts.items())),
        "error_subjects_by_code": {key: subjects_by_code[key] for key in sorted(subjects_by_code)},
    }


def build_llm_document_packages(
    *,
    package: dict[str, Any],
    prompt: ManagedPrompt,
    model_id: str,
    case_group_id: str | None = None,
    max_documents: int | None = None,
    max_text_chars: int = 1800,
    max_table_rows: int = 5,
) -> list[dict[str, Any]]:
    documents = list(package.get("document_inventory", {}).get("documents", []))
    profiles_by_doc = {
        item.get("document_id"): item
        for item in package.get("technical_readability_profiles", [])
        if item.get("document_id")
    }
    taxonomy_by_doc = {
        item.get("document_id"): item
        for item in package.get("taxonomy_candidates", [])
        if item.get("document_id")
    }
    blockers_by_doc: dict[str, list[dict[str, Any]]] = {}
    for blocker in package.get("normalization_blockers", []):
        document_id = blocker.get("document_id")
        if document_id:
            blockers_by_doc.setdefault(str(document_id), []).append(blocker)
    processing_batch = package.get("file_processing_outcomes")
    if not isinstance(processing_batch, dict):
        processing_batch = {}
    processing_outcomes_by_doc = {
        str(item.get("file_ref")): copy.deepcopy(item)
        for item in processing_batch.get("outcomes", [])
        if isinstance(item, dict) and item.get("file_ref")
    }
    structural_shadow = package.get("pdf_structural_repair_shadow")
    structural_summary = (
        structural_shadow.get("summary", {})
        if isinstance(structural_shadow, dict)
        else {}
    )
    structural_processing_outcomes = structural_summary.get(
        "file_processing_outcomes"
    )
    if not isinstance(structural_processing_outcomes, dict):
        structural_processing_outcomes = {}
    structural_outcomes_by_doc = {
        str(item.get("file_ref")): copy.deepcopy(item)
        for item in structural_processing_outcomes.get("outcomes", [])
        if isinstance(item, dict) and item.get("file_ref")
    }
    slices_by_doc: dict[str, list[dict[str, Any]]] = {}
    for private_slice in package.get("private_normalized_slices", []):
        document_id = private_slice.get("document_id")
        if document_id:
            slices_by_doc.setdefault(str(document_id), []).append(private_slice)

    selected = documents[:max_documents] if max_documents else documents
    result = []
    for document in selected:
        document_id = str(document.get("document_id") or "")
        profile = profiles_by_doc.get(document_id) or {}
        taxonomy = taxonomy_by_doc.get(document_id) or {}
        private_slices = slices_by_doc.get(document_id, [])
        evidence_refs = _evidence_refs(document=document, profile=profile, private_slices=private_slices)
        package_id = f"llmpkg_{stable_digest([package['normalization_run']['run_id'], document_id, prompt.hash], length=16)}"
        result.append(
            {
                "schema_version": INPUT_SCHEMA_VERSION,
                "llm_input_package_id": package_id,
                "normalization_run_id": package["normalization_run"]["run_id"],
                "case_group_id": case_group_id or _case_group_id(package),
                "document_id": document_id,
                "source_file_ref": {
                    "provider": document.get("source_kind"),
                    "safe_ref": document_id,
                },
                "document_summary": {
                    "container_format": document.get("container_format"),
                    "declared_mime_type": document.get("declared_mime_type"),
                    "extension": document.get("extension"),
                    "machine_readable": document.get("machine_readable"),
                    "readable": document.get("readable"),
                    "duplicate_group_id": document.get("duplicate_group_id"),
                    "duplicate_of_document_id": document.get("duplicate_of_document_id"),
                },
                "processing_outcome": processing_outcomes_by_doc.get(document_id),
                "structural_repair_outcome": structural_outcomes_by_doc.get(
                    document_id
                ),
                "technical_profile_summary": _profile_summary(profile),
                "taxonomy_candidate": _taxonomy_summary(taxonomy),
                "blocker_codes": [str(item.get("code")) for item in blockers_by_doc.get(document_id, []) if item.get("code")],
                "evidence_refs": evidence_refs,
                "text_summaries": _text_summaries(private_slices, max_chars=max_text_chars),
                "table_summaries": _table_summaries(private_slices, max_rows=max_table_rows),
                "prompt_contract": {
                    "prompt_contract_id": PROMPT_CONTRACT_ID,
                    "llm_prompt_ref": prompt.prompt_ref,
                    "llm_prompt_command": prompt.command,
                    "llm_prompt_version": prompt.version,
                    "llm_prompt_hash": prompt.hash,
                    "llm_model_id": model_id,
                    "output_schema_version": prompt.output_schema_version,
                },
                "output_schema": passport_schema_audit_metadata(),
                "forbidden_tasks": [
                    "source_fact_extraction",
                    "tax_calculation",
                    "declaration_generation",
                    "xlsx_generation",
                    "ocr_vlm",
                    "knowledge_loading",
                ],
            }
        )
    return result


def run_document_passport_stage_sync(
    *,
    package: dict[str, Any],
    prompt: ManagedPrompt,
    model_client: DocumentPassportModelClient,
    model_id: str,
    private_markers: list[str],
    case_group_id: str | None = None,
    max_documents: int | None = None,
) -> dict[str, Any]:
    llm_packages = build_llm_document_packages(
        package=package,
        prompt=prompt,
        model_id=model_id,
        case_group_id=case_group_id,
        max_documents=max_documents,
    )
    raw_outputs = []
    for document_package in llm_packages:
        audit = model_call_audit_metadata(
            prompt=prompt,
            model_id=model_id,
            structured_output_mode=STRUCTURED_OUTPUT_MODE_UNCONSTRAINED_TEST,
            response_format_type="not_applicable",
            response_format_schema_mode=None,
            schema_attempted=False,
        )
        try:
            model_output = model_client.create_passport(
                prompt=prompt,
                document_package=document_package,
                model_id=model_id,
            )
            raw_outputs.append(
                {
                    "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                    "document_id": document_package["document_id"],
                    "normalization_run_id": document_package["normalization_run_id"],
                    "llm_input_package_id": document_package["llm_input_package_id"],
                    "model_call_status": "passed",
                    "raw_output": model_output,
                    "error_code": None,
                    **audit,
                }
            )
        except DocumentPassportError as exc:
            raw_outputs.append(
                {
                    "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                    "document_id": document_package["document_id"],
                    "normalization_run_id": document_package["normalization_run_id"],
                    "llm_input_package_id": document_package["llm_input_package_id"],
                    "model_call_status": "failed",
                    "raw_output": None,
                    "error_code": exc.code,
                    **audit,
                }
            )
    return apply_document_passport_stage(
        package=package,
        prompt=prompt,
        model_id=model_id,
        llm_packages=llm_packages,
        raw_outputs=raw_outputs,
        private_markers=private_markers,
    )


def apply_document_passport_stage(
    *,
    package: dict[str, Any],
    prompt: ManagedPrompt,
    model_id: str,
    llm_packages: list[dict[str, Any]],
    raw_outputs: list[dict[str, Any]],
    private_markers: list[str],
    criticality_refinement_enabled: bool = False,
) -> dict[str, Any]:
    updated = copy.deepcopy(package)
    updated["clarification_criticality_refinement_enabled"] = bool(criticality_refinement_enabled)
    run_id = updated["normalization_run"]["run_id"]
    passports = []
    validation_items = []
    blockers = list(updated.get("normalization_blockers", []))
    llm_packages_by_id = {item.get("llm_input_package_id"): item for item in llm_packages}

    for raw_output in raw_outputs:
        document_id = str(raw_output.get("document_id") or "")
        llm_package = llm_packages_by_id.get(raw_output.get("llm_input_package_id")) or {}
        if raw_output.get("model_call_status") != "passed":
            blockers.append(
                blocker_factory.llm_passport_model_failed(
                    run_id,
                    document_id,
                    str(raw_output.get("error_code") or "model_call_failed"),
                )
            )
            validation_items.append(_passport_validation_failed(run_id, document_id, ["model_call_failed"]))
            continue
        parsed = _parse_model_output(raw_output.get("raw_output"))
        validation = validate_document_metadata_passport(
            passport=parsed if isinstance(parsed, dict) else {},
            document_package=llm_package,
            prompt=prompt,
            model_id=model_id,
        )
        if validation["validator_status"] != "passed" and isinstance(parsed, dict):
            repaired = _validator_guided_passport_repair(parsed, validation)
            if repaired is not None:
                repaired_validation = validate_document_metadata_passport(
                    passport=repaired,
                    document_package=llm_package,
                    prompt=prompt,
                    model_id=model_id,
                )
                if repaired_validation["validator_status"] == "passed":
                    parsed = repaired
                    validation = repaired_validation
                    raw_output["raw_output"] = repaired
                    raw_output["validator_guided_repair_applied"] = True
        validation_items.append(validation)
        passport_payload = parsed if isinstance(parsed, dict) else {}
        if validation["validator_status"] == "passed":
            passport_payload = _validated_passport(passport_payload)
            passports.append(passport_payload)
        else:
            blockers.append(
                blocker_factory.llm_passport_validation_failed(
                    run_id,
                    document_id,
                    ",".join(validation.get("error_codes") or ["validation_failed"])[:128],
                )
            )
            passport_payload = _blocked_passport(passport_payload, validation, llm_package, prompt, model_id)
            passports.append(passport_payload)

    updated["llm_prompt_snapshot"] = prompt.snapshot()
    updated["llm_document_packages"] = llm_packages
    updated["llm_passport_raw_outputs"] = raw_outputs
    updated["document_metadata_passports"] = passports
    updated["document_metadata_passport_validation"] = {
        "schema_version": PASSPORT_VALIDATION_SCHEMA_VERSION,
        "normalization_run_id": run_id,
        "validator_status": "passed" if validation_items and all(item["validator_status"] == "passed" for item in validation_items) else "failed",
        "items": validation_items,
        "passports_total": len(passports),
        "passed": sum(1 for item in validation_items if item["validator_status"] == "passed"),
        "failed": sum(1 for item in validation_items if item["validator_status"] != "passed"),
        "error_code_summary": _validation_error_code_summary(validation_items),
        "structured_output_mode_counts": _raw_output_counts(raw_outputs, "structured_output_mode"),
        "response_format_type_counts": _raw_output_counts(raw_outputs, "response_format_type"),
        "repair_attempted_count": sum(1 for item in raw_outputs if item.get("repair_attempted") is True),
        "validator_guided_repair_count": sum(1 for item in raw_outputs if item.get("validator_guided_repair_applied") is True),
        "fallback_used_count": sum(1 for item in raw_outputs if item.get("fallback_used") is True),
        **passport_schema_audit_metadata(),
        "llm_model_id": model_id,
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
    }
    updated["normalization_blockers"] = blockers
    updated["summary_counts"]["blockers_total"] = len(blockers)
    updated["summary_counts"]["document_metadata_passport_counts"] = _passport_summary_counts(passports, validation_items)
    updated["supported_contracts"] = list(dict.fromkeys([*updated.get("supported_contracts", []), *[
        INPUT_SCHEMA_VERSION,
        PROMPT_SNAPSHOT_SCHEMA_VERSION,
        RAW_OUTPUT_SCHEMA_VERSION,
        PASSPORT_SCHEMA_VERSION,
        PASSPORT_VALIDATION_SCHEMA_VERSION,
    ]]))

    document_source_eligibility, source_eligibility_summary, gate2_handoff = build_document_source_eligibility(
        run_id=run_id,
        documents=updated["document_inventory"]["documents"],
        taxonomy_candidates=updated["taxonomy_candidates"],
        blockers=updated["normalization_blockers"],
        ocr_policy_status=_ocr_policy_status(updated.get("input_context") or {}),
        document_metadata_passports=passports,
        input_context=updated.get("input_context") or {},
        criticality_refinement_enabled=criticality_refinement_enabled,
    )
    updated["document_source_eligibility"] = document_source_eligibility
    updated["source_eligibility_summary"] = source_eligibility_summary
    updated["gate2_handoff"] = gate2_handoff
    updated["summary_counts"]["source_eligibility_counts"] = dict(source_eligibility_summary.get("status_counts", {}))
    updated["normalization_run"]["gate2_handoff_status"] = gate2_handoff["gate2_handoff_status"]
    updated["normalization_run"]["gate2_handoff_mode"] = gate2_handoff["handoff_mode"]
    updated["normalization_run"]["run_status"] = _run_status_with_passports(
        current_status=updated["normalization_run"]["run_status"],
        blockers=updated["normalization_blockers"],
    )
    updated["recommended_next_step"] = _recommended_next_step_with_passports(updated)
    updated = apply_domain_ingestion_artifacts(updated)

    artifact_validation = validate_artifacts(updated)
    updated["validation_result"] = artifact_validation
    safe_report = render_safe_report(updated)
    safe_validation = validate_safe_report(
        safe_report=safe_report,
        private_markers=private_markers,
        run_id=run_id,
    )
    merged = merge_validation_results(artifact_validation, safe_validation)
    updated["validation_result"] = merged
    updated["normalization_run"]["privacy_validation_status"] = merged["status"]
    if merged["status"] == "privacy_failed":
        privacy_blocker = merged["privacy_blocker"]
        updated["normalization_blockers"].append(privacy_blocker)
        updated["normalization_run"]["run_status"] = "privacy_failed"
        updated["normalization_run"]["gate2_handoff_status"] = "blocked"
        updated["normalization_run"]["gate2_handoff_mode"] = "gate2_blocked_no_eligible_sources"
        updated["gate2_handoff"]["handoff_mode"] = "gate2_blocked_no_eligible_sources"
        updated["gate2_handoff"]["gate2_handoff_status"] = "blocked"
        updated["summary_counts"]["blockers_total"] = len(updated["normalization_blockers"])
        safe_report = render_privacy_failed_report(
            run_id=run_id,
            files_total=updated["summary_counts"]["files_total"],
            input_context=updated.get("input_context"),
        )
    else:
        safe_report = render_safe_report(updated)
    return {"package": updated, "safe_report": safe_report}


def validate_document_metadata_passport(
    *,
    passport: dict[str, Any],
    document_package: dict[str, Any],
    prompt: ManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    document_id = str(document_package.get("document_id") or "")
    run_id = str(document_package.get("normalization_run_id") or "")
    known_refs = _known_evidence_refs(document_package)

    if not isinstance(passport, dict):
        errors.append(_error("passport_not_object", document_id))
        passport = {}
    missing = sorted(REQUIRED_PASSPORT_FIELDS - set(passport))
    for field in missing:
        errors.append(_error("passport_missing_field", field))
    unknown = sorted(set(passport) - REQUIRED_PASSPORT_FIELDS)
    for field in unknown:
        errors.append(_error("passport_unknown_field", field))
    if passport.get("schema_version") != PASSPORT_SCHEMA_VERSION:
        errors.append(_error("passport_schema_mismatch", passport.get("schema_version")))
    if passport.get("normalization_run_id") != run_id:
        errors.append(_error("passport_run_mismatch", passport.get("normalization_run_id")))
    if passport.get("document_id") != document_id:
        errors.append(_error("passport_document_mismatch", passport.get("document_id")))
    if passport.get("llm_prompt_ref") != prompt.prompt_ref:
        errors.append(_error("passport_prompt_ref_mismatch", passport.get("llm_prompt_ref")))
    if passport.get("llm_prompt_hash") != prompt.hash:
        errors.append(_error("passport_prompt_hash_mismatch", passport.get("llm_prompt_hash")))
    if passport.get("llm_model_id") != model_id:
        errors.append(_error("passport_model_mismatch", passport.get("llm_model_id")))
    if passport.get("source_candidate_confidence") not in CONFIDENCE_VALUES:
        errors.append(_error("passport_source_confidence_invalid", passport.get("source_candidate_confidence")))
    if passport.get("metadata_confidence") not in CONFIDENCE_VALUES:
        errors.append(_error("passport_metadata_confidence_invalid", passport.get("metadata_confidence")))
    if passport.get("passport_status") not in PASSPORT_STATUSES:
        errors.append(_error("passport_status_invalid", passport.get("passport_status")))
    if passport.get("validator_status") not in VALIDATOR_STATUSES:
        errors.append(_error("validator_status_invalid", passport.get("validator_status")))
    if passport.get("llm_prompt_hash") and not re.fullmatch(r"[0-9a-f]{64}", str(passport.get("llm_prompt_hash"))):
        errors.append(_error("passport_prompt_hash_invalid", passport.get("llm_prompt_hash")))

    refs = _string_list(passport.get("evidence_refs"))
    input_refs = _string_list(passport.get("llm_input_refs"))
    if passport.get("source_candidate_confidence") == "high" and not refs:
        errors.append(_error("high_confidence_without_evidence", document_id))
    for ref in [*refs, *input_refs]:
        if ref not in known_refs:
            errors.append(_error("passport_unknown_evidence_ref", ref))
    forbidden_paths = _find_forbidden_fields(passport)
    for path in forbidden_paths:
        errors.append(_error("passport_forbidden_field", path))
    missing_fields = set(_string_list(passport.get("missing_metadata_fields")))
    for field in CRITICAL_METADATA_FIELDS:
        if _missing_value(passport.get(field)) and field not in missing_fields:
            errors.append(_error("passport_missing_metadata_not_declared", field))
    if (missing_fields or passport.get("conflict_flags")) and passport.get("review_required") is not True:
        errors.append(_error("passport_review_required_not_true", document_id))

    status = "passed" if not errors else "failed"
    return {
        "schema_version": PASSPORT_VALIDATION_SCHEMA_VERSION,
        "normalization_run_id": run_id,
        "document_id": document_id,
        "validator_status": status,
        "passed": status == "passed",
        "errors_count": len(errors),
        "errors": errors,
        "error_codes": sorted({item["code"] for item in errors}),
    }


def _parse_model_output(value: Any) -> Any:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except ValueError:
            return {"_parse_error": "invalid_json"}
    return {"_parse_error": "unsupported_model_output"}


def _validated_passport(passport: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(passport)
    result["passport_status"] = "validated"
    result["validator_status"] = "passed"
    result["validator_errors"] = []
    return result


def _blocked_passport(
    passport: dict[str, Any],
    validation: dict[str, Any],
    document_package: dict[str, Any],
    prompt: ManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    result = _blank_passport(document_package=document_package, prompt=prompt, model_id=model_id)
    for key, value in passport.items():
        if key in REQUIRED_PASSPORT_FIELDS:
            result[key] = value
    result["passport_status"] = "blocked"
    result["validator_status"] = "failed"
    result["validator_errors"] = validation.get("error_codes") or ["validation_failed"]
    result["review_required"] = True
    return result


def _validator_guided_passport_repair(
    passport: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any] | None:
    errors = validation.get("errors") if isinstance(validation, dict) else []
    if not isinstance(errors, list) or not errors:
        return None
    codes = {str(error.get("code") or "") for error in errors if isinstance(error, dict)}
    if codes - {"passport_missing_metadata_not_declared"}:
        return None
    subjects = [
        str(error.get("subject") or "")
        for error in errors
        if isinstance(error, dict)
        and error.get("code") == "passport_missing_metadata_not_declared"
        and str(error.get("subject") or "") in CRITICAL_METADATA_FIELDS
    ]
    if not subjects:
        return None
    repaired = copy.deepcopy(passport)
    missing_fields = _string_list(repaired.get("missing_metadata_fields"))
    for subject in subjects:
        if subject not in missing_fields:
            missing_fields.append(subject)
    repaired["missing_metadata_fields"] = missing_fields
    repaired["review_required"] = True
    repaired["validator_status"] = "pending"
    repaired["validator_errors"] = []
    return repaired


def _blank_passport(
    *,
    document_package: dict[str, Any],
    prompt: ManagedPrompt,
    model_id: str,
) -> dict[str, Any]:
    run_id = str(document_package.get("normalization_run_id") or "")
    document_id = str(document_package.get("document_id") or "")
    return {
        "schema_version": PASSPORT_SCHEMA_VERSION,
        "passport_id": f"passport_{stable_digest([run_id, document_id, prompt.hash], length=16)}",
        "normalization_run_id": run_id,
        "case_group_id": document_package.get("case_group_id"),
        "document_id": document_id,
        "source_file_ref": document_package.get("source_file_ref") or {"provider": None, "safe_ref": document_id},
        "passport_status": "blocked",
        "document_title_candidate": None,
        "document_kind_candidate": None,
        "broker_name_candidate": None,
        "client_name_candidate": None,
        "account_or_contract_candidate": None,
        "report_period_start": None,
        "report_period_end": None,
        "tax_year_candidate": None,
        "created_at_candidate": None,
        "document_language": None,
        "document_format": None,
        "container_format": document_package.get("document_summary", {}).get("container_format"),
        "content_kind": None,
        "sections_detected": [],
        "tables_detected": [],
        "operation_sections_detected": [],
        "cashflow_sections_detected": [],
        "income_sections_detected": [],
        "withholding_sections_detected": [],
        "tax_sections_detected": [],
        "role_hypotheses": [],
        "source_candidate_confidence": "none",
        "metadata_confidence": "none",
        "evidence_refs": [],
        "missing_metadata_fields": sorted(CRITICAL_METADATA_FIELDS),
        "conflict_flags": ["passport_validation_failed"],
        "review_required": True,
        "llm_prompt_ref": prompt.prompt_ref,
        "llm_prompt_command": prompt.command,
        "llm_prompt_version": prompt.version,
        "llm_prompt_hash": prompt.hash,
        "llm_model_id": model_id,
        "llm_input_refs": [document_package.get("llm_input_package_id")],
        "validator_status": "failed",
        "validator_errors": ["validation_failed"],
        "created_at": "",
    }


def _passport_validation_failed(run_id: str, document_id: str, error_codes: list[str]) -> dict[str, Any]:
    return {
        "schema_version": PASSPORT_VALIDATION_SCHEMA_VERSION,
        "normalization_run_id": run_id,
        "document_id": document_id,
        "validator_status": "failed",
        "passed": False,
        "errors_count": len(error_codes),
        "errors": [_error(code, document_id) for code in error_codes],
        "error_codes": error_codes,
    }


def _profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "profile_id",
        "document_id",
        "container_format",
        "parser",
        "profile_status",
        "machine_readable",
        "machine_readable_table",
        "section_count",
        "table_candidate",
        "html_table_count",
        "clean_text_available",
        "pages_count",
        "has_text_layer",
        "text_layer",
        "pdf_content_kind",
        "raster_or_scan_likelihood",
        "rows_count",
        "columns_count",
        "tables_count",
        "headings_count",
    }
    return {key: copy.deepcopy(profile.get(key)) for key in sorted(allowed) if key in profile}


def _taxonomy_summary(taxonomy: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "taxonomy_candidate_id",
        "document_id",
        "document_class_candidate",
        "primary_class",
        "confidence",
        "safe_reason_codes",
        "can_be_source_evidence",
        "can_be_methodology",
        "source_role_policy_status",
        "source_policy_review_required",
        "requires_review",
    }
    return {key: copy.deepcopy(taxonomy.get(key)) for key in sorted(allowed) if key in taxonomy}


def _evidence_refs(
    *,
    document: dict[str, Any],
    profile: dict[str, Any],
    private_slices: list[dict[str, Any]],
) -> list[str]:
    refs = [str(document.get("document_id") or "")]
    if profile.get("profile_id"):
        refs.append(str(profile["profile_id"]))
    refs.extend(str(item.get("slice_id")) for item in private_slices if item.get("slice_id"))
    return list(dict.fromkeys(ref for ref in refs if ref))


def _text_summaries(private_slices: list[dict[str, Any]], *, max_chars: int) -> list[dict[str, Any]]:
    result = []
    for item in private_slices:
        if item.get("slice_type") != "text_excerpt":
            continue
        text = str(item.get("text") or "")
        result.append(
            {
                "evidence_ref": item.get("slice_id"),
                "source_location": item.get("source_location"),
                "chars_count": len(text),
                "text_excerpt": text[:max_chars],
                "truncated": len(text) > max_chars or bool(item.get("truncated")),
            }
        )
    return result


def _table_summaries(private_slices: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    result = []
    for item in private_slices:
        if item.get("slice_type") != "table_rows":
            continue
        rows = item.get("rows") or item.get("cells") or []
        if not isinstance(rows, list):
            rows = []
        header = rows[0] if rows and isinstance(rows[0], list) else []
        result.append(
            {
                "evidence_ref": item.get("slice_id"),
                "source_location": item.get("source_location"),
                "rows_count": item.get("rows_count") or item.get("rows_in_slice") or len(rows),
                "columns_count": item.get("columns_count") or (len(header) if isinstance(header, list) else None),
                "header_signals": [_safe_header_signal(cell) for cell in header[:20]],
                "sample_rows": rows[1 : max_rows + 1],
                "truncated": bool(item.get("truncated")) or len(rows) > max_rows + 1,
            }
        )
    return result


def _safe_header_signal(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-zа-я0-9_ -]+", "", text)
    return text[:64]


def _known_evidence_refs(document_package: dict[str, Any]) -> set[str]:
    refs = set(_string_list(document_package.get("evidence_refs")))
    package_id = document_package.get("llm_input_package_id")
    if package_id:
        refs.add(str(package_id))
    return refs


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


def _missing_value(value: Any) -> bool:
    return value is None or value == "" or value == []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        parsed = value
    elif not value:
        parsed = []
    else:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _case_group_id(package: dict[str, Any]) -> str | None:
    context = package.get("input_context") if isinstance(package.get("input_context"), dict) else {}
    broker_context = context.get("broker_reports_gate1") if isinstance(context.get("broker_reports_gate1"), dict) else {}
    value = context.get("case_group_id") or broker_context.get("case_group_id")
    return str(value) if value else None


def _ocr_policy_status(input_context: dict[str, Any]) -> str:
    value = (
        input_context.get("ocr_policy_status")
        or input_context.get("ocr_policy")
        or input_context.get("ocr_gate1_policy")
    )
    if value in {"enabled", "ocr_enabled"}:
        return "enabled-not-executed"
    if value in {"required-before-gate2", "manual-review-only", "enabled-not-executed", "disabled"}:
        return str(value)
    return "disabled"


def _passport_summary_counts(
    passports: list[dict[str, Any]],
    validation_items: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "packages_total": len(validation_items),
        "passports_total": len(passports),
        "validated": sum(1 for item in validation_items if item.get("validator_status") == "passed"),
        "failed": sum(1 for item in validation_items if item.get("validator_status") != "passed"),
        "review_required": sum(1 for item in passports if item.get("review_required") is True),
    }


def _validation_error_code_summary(validation_items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in validation_items:
        for code in _string_list(item.get("error_codes")):
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _raw_output_counts(raw_outputs: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in raw_outputs:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _run_status_with_passports(*, current_status: str, blockers: list[dict[str, Any]]) -> str:
    if current_status == "failed_safe":
        return current_status
    blocking = any(blocker.get("blocks_gate2") for blocker in blockers)
    return "completed_with_blockers" if blocking or blockers else "completed"


def _recommended_next_step_with_passports(package: dict[str, Any]) -> str:
    mode = package.get("gate2_handoff", {}).get("handoff_mode")
    if mode == "reduced_subset_ready_for_gate2":
        return "continue_with_reduced_gate2_subset_after_specialist_confirmation"
    if mode == "full_package_ready_for_gate2":
        return "ready_for_gui_smoke"
    summary = package.get("source_eligibility_summary") or {}
    if mode == "gate2_blocked_requires_policy_review":
        return "confirm_source_policy_for_candidate_documents"
    if mode == "gate2_blocked_requires_duplicate_resolution":
        return "choose_canonical_duplicate_documents"
    if mode == "gate2_blocked_requires_ocr":
        return "route_ocr_candidates_to_future_ocr_gate_or_manual_review"
    if int(summary.get("metadata_review") or 0) > 0:
        return "review_document_metadata_passports"
    if mode == "gate2_blocked_no_eligible_sources":
        return "attach_supported_source_documents_or_review_package"
    return str(package.get("recommended_next_step") or "review_gate1_blockers")


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
