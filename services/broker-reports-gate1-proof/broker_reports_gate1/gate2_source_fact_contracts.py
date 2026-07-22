from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


FACTORY_REQUIRED = (
    "Gate2ManagedPromptResolverFactory.create is the only production Gate 2 prompt resolver entrypoint"
)
FORBIDDEN = (
    "Gate 2 pipes, runners and smoke scripts must not read OpenWebUI prompt tables or hardcode the final prompt body"
)

EXTRACTION_RUN_SCHEMA_VERSION = "broker_reports_source_fact_extraction_run_v0"
PACKAGE_SCHEMA_VERSION = "broker_reports_source_fact_package_v0"
RAW_OUTPUT_SCHEMA_VERSION = "broker_reports_source_fact_raw_output_v0"
SOURCE_FACTS_SCHEMA_VERSION = "broker_reports_source_facts_v0"
VALIDATION_SCHEMA_VERSION = "broker_reports_source_fact_validation_v0"
ISSUE_LINKAGE_SCHEMA_VERSION = "broker_reports_issue_fact_linkage_v0"
SUMMARY_SCHEMA_VERSION = "broker_reports_source_fact_extraction_summary_v0"

PROMPT_CONTRACT_ID = "broker_reports_source_fact_prompt_v0"
PROMPT_TEMPLATE_ID = "broker_reports.source_fact_extraction.v0"
PROMPT_TEMPLATE_KIND = "broker_reports_source_fact_extraction"
PROMPT_COMMAND = "broker_gate2_source_facts_v0"
PROMPT_REQUIRED_TAG = "broker-reports-gate2"
OUTPUT_SCHEMA_ID = "broker_reports.source_facts.schema.v0"
OUTPUT_SCHEMA_NAME = "broker_reports_source_facts_v0"
STRUCTURED_OUTPUT_MODE = "openwebui_response_format_json_schema"
RESPONSE_FORMAT_TYPE = "json_schema"
RESPONSE_FORMAT_SCHEMA_MODE = "strict_json_schema"

FACT_TYPES = {
    "trade_operation",
    "income",
    "withholding_tax",
    "fee_commission",
    "cash_movement",
    "currency_fx",
    "position_snapshot",
    "document_summary_evidence",
    "unknown_source_row",
}
CONFIDENCE_VALUES = {"high", "medium", "low", "none"}
COMPLETENESS_VALUES = {"complete", "partial", "uncertain", "blocked"}
SOURCE_GRANULARITY_VALUES = {
    "table_row",
    "table_cell_group",
    "table_summary_row",
    "text_segment",
    "section",
    "document_summary",
    "unknown",
}
NO_FACT_REASON_VALUES = {
    "header_row",
    "blank_row",
    "layout_only",
    "repeated_header",
    "non_fact_annotation",
    "package_scope_excluded",
    "blocked_by_issue",
    "unsupported_source_shape",
}
NORMALIZED_VALUE_FIELDS = (
    "date",
    "amount",
    "currency",
    "quantity",
    "rate",
    "converted_amount",
    "identifier",
    "label",
)


class Gate2PromptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Gate2PromptUserContext:
    user_id: str
    user_role: str = "user"
    user_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gate2PromptConfig:
    source: str = "openwebui_sqlite"
    db_path: Path | None = None
    prompt_id: str | None = None
    command: str | None = PROMPT_COMMAND
    required_template_id: str = PROMPT_TEMPLATE_ID
    required_template_kind: str = PROMPT_TEMPLATE_KIND
    required_prompt_contract_id: str = PROMPT_CONTRACT_ID
    required_input_schema_version: str = PACKAGE_SCHEMA_VERSION
    required_output_schema_id: str = OUTPUT_SCHEMA_ID
    required_output_schema_version: str = SOURCE_FACTS_SCHEMA_VERSION
    required_tag: str = PROMPT_REQUIRED_TAG


@dataclass(frozen=True)
class Gate2ManagedPrompt:
    prompt_ref: str
    command: str | None
    version: str | None
    content: str
    hash: str
    source: str
    template_id: str
    template_kind: str
    prompt_contract_id: str
    input_schema_version: str
    output_schema_id: str
    output_schema_version: str
    tags: tuple[str, ...]
    safe_metadata: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "broker_reports_source_fact_prompt_snapshot_v0",
            "prompt_ref": self.prompt_ref,
            "prompt_command": self.command,
            "prompt_version": self.version,
            "prompt_hash": self.hash,
            "prompt_source": self.source,
            "prompt_contract_id": self.prompt_contract_id,
            "template_id": self.template_id,
            "template_kind": self.template_kind,
            "input_schema_version": self.input_schema_version,
            "output_schema_id": self.output_schema_id,
            "output_schema_version": self.output_schema_version,
            "output_schema_hash": source_facts_schema_hash(),
            "provider_response_schema_hash": source_facts_provider_schema_hash(),
            "provider_union_keyword": "anyOf",
            "tags": list(self.tags),
            "safe_metadata": copy.deepcopy(self.safe_metadata),
        }


class Gate2PromptResolver(Protocol):
    def resolve(self, user_context: Gate2PromptUserContext) -> Gate2ManagedPrompt:
        ...


class Gate2ManagedPromptResolverFactory:
    def __init__(self, config: Gate2PromptConfig) -> None:
        self.config = config

    def create(self) -> Gate2PromptResolver:
        if self.config.source == "openwebui_sqlite":
            if self.config.db_path is None:
                raise Gate2PromptError(
                    "gate2_prompt_unavailable",
                    "OpenWebUI prompt database path is not configured",
                )
            return OpenWebUISqliteGate2PromptResolver(self.config)
        if self.config.source == "disabled":
            return DisabledGate2PromptResolver()
        raise Gate2PromptError("gate2_prompt_unavailable", "Unsupported Gate 2 prompt source")


class DisabledGate2PromptResolver:
    def resolve(self, user_context: Gate2PromptUserContext) -> Gate2ManagedPrompt:
        raise Gate2PromptError("gate2_prompt_disabled", "Gate 2 prompt resolver is disabled")


class StaticGate2PromptResolver:
    def __init__(self, prompt: Gate2ManagedPrompt) -> None:
        self.prompt = prompt

    def resolve(self, user_context: Gate2PromptUserContext) -> Gate2ManagedPrompt:
        if not user_context.user_id:
            raise Gate2PromptError("gate2_prompt_access_denied", "Authenticated user is required")
        return self.prompt


class OpenWebUISqliteGate2PromptResolver:
    def __init__(self, config: Gate2PromptConfig) -> None:
        self.config = config
        self.db_path = config.db_path

    def resolve(self, user_context: Gate2PromptUserContext) -> Gate2ManagedPrompt:
        conn = self._connect()
        try:
            row = self._find_prompt(conn)
            if row is None:
                raise Gate2PromptError("gate2_prompt_not_found", "Gate 2 managed Prompt was not found")
            if not self._has_read_access(row, user_context, conn):
                raise Gate2PromptError("gate2_prompt_access_denied", "Gate 2 managed Prompt is not readable")
            return self._row_to_prompt(row)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None or not self.db_path.exists():
            raise Gate2PromptError("gate2_prompt_unavailable", "OpenWebUI prompt database is unavailable")
        conn = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
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
        elif self.config.command:
            row = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1 AND command = ?
                """,
                (self.config.command,),
            ).fetchone()
        else:
            raise Gate2PromptError("gate2_prompt_not_found", "Prompt id or command is required")
        return row if row is not None and self._matches_contract(row) else None

    def _matches_contract(self, row: sqlite3.Row) -> bool:
        meta = _json_dict(row["meta"])
        tags = _json_list(row["tags"])
        return (
            str(meta.get("template_id") or "") == self.config.required_template_id
            and str(meta.get("template_kind") or "") == self.config.required_template_kind
            and str(meta.get("prompt_contract_id") or "")
            == self.config.required_prompt_contract_id
            and str(meta.get("input_contract") or "")
            == self.config.required_input_schema_version
            and str(meta.get("output_schema_id") or "")
            == self.config.required_output_schema_id
            and str(meta.get("output_schema_version") or "")
            == self.config.required_output_schema_version
            and meta.get("structured_output_required") is True
            and self.config.required_tag in tags
            and bool(str(row["content"] or "").strip())
            and "{{source_fact_package_json}}" in str(row["content"] or "")
        )

    def _row_to_prompt(self, row: sqlite3.Row) -> Gate2ManagedPrompt:
        content = str(row["content"] or "")
        meta = _json_dict(row["meta"])
        tags = tuple(_json_list(row["tags"]))
        return Gate2ManagedPrompt(
            prompt_ref=str(row["id"]),
            command=str(row["command"] or "") or None,
            version=str(row["version_id"] or "") or None,
            content=content,
            hash=gate2_prompt_hash(content),
            source="openwebui_prompt",
            template_id=str(meta["template_id"]),
            template_kind=str(meta["template_kind"]),
            prompt_contract_id=str(meta["prompt_contract_id"]),
            input_schema_version=str(meta["input_contract"]),
            output_schema_id=str(meta["output_schema_id"]),
            output_schema_version=str(meta["output_schema_version"]),
            tags=tags,
            safe_metadata={
                "name": str(row["name"] or row["command"] or ""),
                "gate": str(meta.get("gate") or "gate2"),
                "extractor_domain": str(meta.get("extractor_domain") or "")
                or None,
            },
        )

    def _has_read_access(
        self,
        row: sqlite3.Row,
        user_context: Gate2PromptUserContext,
        conn: sqlite3.Connection,
    ) -> bool:
        role = str(user_context.user_role or "").lower()
        user_id = str(user_context.user_id or "")
        groups = {str(group) for group in user_context.user_groups if group}
        if role == "admin":
            return True
        if user_id and user_id == str(row["user_id"] or ""):
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
            if principal_type == "user" and principal_id in {"*", user_id}:
                return True
            if principal_type == "group" and principal_id in groups:
                return True
        return False


def gate2_prompt_hash(prompt_content: str) -> str:
    material = (
        prompt_content.replace("\r\n", "\n").strip()
        + "\nprompt_contract:"
        + PROMPT_CONTRACT_ID
        + "\ninput_schema:"
        + PACKAGE_SCHEMA_VERSION
        + "\noutput_schema_id:"
        + OUTPUT_SCHEMA_ID
        + "\noutput_schema_version:"
        + SOURCE_FACTS_SCHEMA_VERSION
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def source_facts_json_schema() -> dict[str, Any]:
    string_array = _array({"type": "string"})
    nullable_string = {"type": ["string", "null"]}
    normalized_values = _strict_object(
        {field: copy.deepcopy(nullable_string) for field in NORMALIZED_VALUE_FIELDS}
    )
    original_value_refs = _strict_object(
        {field: copy.deepcopy(string_array) for field in NORMALIZED_VALUE_FIELDS}
    )
    source_location = _strict_object(
        {
            "private_slice_artifact_ref": {"type": "string"},
            "slice_ref": {"type": "string"},
            "source_granularity": {
                "type": "string",
                "enum": sorted(SOURCE_GRANULARITY_VALUES),
            },
            "page_ref": copy.deepcopy(nullable_string),
            "section_ref": copy.deepcopy(nullable_string),
            "table_ref": copy.deepcopy(nullable_string),
            "row_ref": copy.deepcopy(nullable_string),
            "row_range_ref": copy.deepcopy(nullable_string),
            "cell_refs": copy.deepcopy(string_array),
            "text_segment_refs": copy.deepcopy(string_array),
            "parser_ref": {"type": "string"},
            "source_checksum_ref": {"type": "string"},
        }
    )
    date_value = _nullable_object(
        {
            "value": {"type": "string"},
            "role": {"type": "string"},
            "precision": {"type": "string", "enum": ["day", "month", "year", "unknown"]},
            "original_value_refs": copy.deepcopy(string_array),
        }
    )
    amount_value = _nullable_object(
        {
            "value_decimal": {"type": "string"},
            "amount_role": {"type": "string"},
            "currency": copy.deepcopy(nullable_string),
            "original_value_refs": copy.deepcopy(string_array),
        }
    )
    currency_value = _nullable_object(
        {
            "code": {"type": "string"},
            "code_kind": {"type": "string", "enum": ["iso_4217_visible", "source_visible_unknown"]},
            "original_value_refs": copy.deepcopy(string_array),
        }
    )
    quantity_value = _nullable_object(
        {
            "value_decimal": {"type": "string"},
            "unit": {"type": "string"},
            "original_value_refs": copy.deepcopy(string_array),
        }
    )
    identifier = _strict_object(
        {
            "identifier_type": {
                "type": "string",
                "enum": ["isin", "ticker", "cusip", "sedol", "broker_instrument_id", "unknown_visible_identifier"],
            },
            "identifier_value": {"type": "string"},
            "original_value_refs": copy.deepcopy(string_array),
        }
    )
    instrument_value = _nullable_object(
        {
            "safe_label": copy.deepcopy(nullable_string),
            "safe_label_ref": copy.deepcopy(nullable_string),
            "identifiers": _array(identifier),
        }
    )
    issue_impact = _strict_object(
        {
            "warning_issue_refs": copy.deepcopy(string_array),
            "limits_confirmation_issue_refs": copy.deepcopy(string_array),
            "blocks_fact_issue_refs": copy.deepcopy(string_array),
            "blocks_consolidation_issue_refs": copy.deepcopy(string_array),
            "blocks_declaration_issue_refs": copy.deepcopy(string_array),
            "forbidden_assumption_codes": copy.deepcopy(string_array),
        }
    )
    downstream_use = _strict_object(
        {
            "downstream_usable": {"type": "boolean"},
            "gate3_ledger_candidate": {"type": "boolean"},
            "cross_document_consolidation_allowed": {"type": "boolean"},
            "tax_calculation_allowed": {"type": "boolean"},
            "declaration_mapping_allowed": {"type": "boolean"},
            "restriction_codes": copy.deepcopy(string_array),
        }
    )
    extraction_audit = _strict_object(
        {
            "prompt_ref": {"type": "string"},
            "prompt_command": copy.deepcopy(nullable_string),
            "prompt_version": copy.deepcopy(nullable_string),
            "prompt_hash": {"type": "string"},
            "prompt_contract_id": {"type": "string"},
            "template_id": {"type": "string"},
            "output_schema_id": {"type": "string"},
            "output_schema_version": {"type": "string"},
            "output_schema_hash": {"type": "string"},
            "provider_response_schema_hash": {"type": "string"},
            "provider_union_keyword": {"type": "string", "const": "anyOf"},
            "model_id": {"type": "string"},
            "structured_output_mode": {"type": "string"},
            "response_format_type": {"type": "string"},
            "fallback_used": {"type": "boolean"},
            "repair_attempt_count": {"type": "integer", "minimum": 0, "maximum": 1},
            "raw_output_artifact_ref": copy.deepcopy(nullable_string),
            "extraction_attempt_ordinal": {"type": "integer", "minimum": 1},
            "created_at": {"type": "string"},
        }
    )
    fact_variants = []
    for fact_type, extracted_schema in _extracted_field_schemas().items():
        properties = {
            "fact_id": {"type": "string"},
            "fact_type": {"type": "string", "const": fact_type},
            "fact_subtype": copy.deepcopy(nullable_string),
            "document_ref": {"type": "string"},
            "extraction_package_ref": {"type": "string"},
            "source_unit_ref": {"type": "string"},
            "source_location": copy.deepcopy(source_location),
            "extracted_fields": extracted_schema,
            "normalized_values": copy.deepcopy(normalized_values),
            "original_value_refs": copy.deepcopy(original_value_refs),
            "date": copy.deepcopy(date_value),
            "amount": copy.deepcopy(amount_value),
            "currency": copy.deepcopy(currency_value),
            "quantity": copy.deepcopy(quantity_value),
            "instrument": copy.deepcopy(instrument_value),
            "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
            "completeness": {"type": "string", "enum": sorted(COMPLETENESS_VALUES)},
            "evidence_refs": copy.deepcopy(string_array),
            "linked_issue_refs": copy.deepcopy(string_array),
            "issue_impact": copy.deepcopy(issue_impact),
            "extraction_warnings": copy.deepcopy(string_array),
            "downstream_use": copy.deepcopy(downstream_use),
            "extraction_audit": copy.deepcopy(extraction_audit),
            "validator_status": {"type": "string", "enum": ["pending"]},
            "validation_ref": {"type": "null"},
        }
        fact_variants.append(_strict_object(properties))
    no_fact_result = _strict_object(
        {
            "source_ref": {"type": "string"},
            "reason_code": {"type": "string", "enum": sorted(NO_FACT_REASON_VALUES)},
        }
    )
    coverage = _strict_object(
        {
            "unit_coverage_ref": {"type": "string"},
            "selected_source_refs": copy.deepcopy(string_array),
            "fact_covered_refs": copy.deepcopy(string_array),
            "no_fact_results": _array(no_fact_result),
            "rejected_refs": copy.deepcopy(string_array),
            "pending_refs": copy.deepcopy(string_array),
            "coverage_status": {"type": "string", "enum": ["complete", "partial", "blocked"]},
        }
    )
    issue_linkage_summary = _strict_object(
        {
            "package_issue_refs": copy.deepcopy(string_array),
            "fact_issue_links_total": {"type": "integer", "minimum": 0},
            "unresolved_issue_refs": copy.deepcopy(string_array),
        }
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": SOURCE_FACTS_SCHEMA_VERSION},
            "source_facts_set_id": {"type": "string"},
            "extraction_run_id": {"type": "string"},
            "normalization_run_id": {"type": "string"},
            "case_id": {"type": ["string", "null"]},
            "package_refs": copy.deepcopy(string_array),
            "document_refs": copy.deepcopy(string_array),
            "facts": {"type": "array", "items": {"oneOf": fact_variants}},
            "coverage": coverage,
            "issue_linkage_summary": issue_linkage_summary,
            "extraction_audit": extraction_audit,
            "validation_ref": {"type": "null"},
            "validator_status": {"type": "string", "enum": ["pending"]},
            "created_at": {"type": "string"},
        },
        "required": [
            "schema_version",
            "source_facts_set_id",
            "extraction_run_id",
            "normalization_run_id",
            "case_id",
            "package_refs",
            "document_refs",
            "facts",
            "coverage",
            "issue_linkage_summary",
            "extraction_audit",
            "validation_ref",
            "validator_status",
            "created_at",
        ],
    }


def source_facts_response_format(
    package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": RESPONSE_FORMAT_TYPE,
        "json_schema": {
            "name": OUTPUT_SCHEMA_NAME,
            "strict": True,
            "schema": source_facts_provider_json_schema(package),
        },
    }


def source_facts_provider_json_schema(
    package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema = source_facts_json_schema()
    fact_items = schema["properties"]["facts"]["items"]
    fact_items["anyOf"] = fact_items.pop("oneOf")
    if package is not None:
        _bind_provider_schema_to_package(schema, package)
    return schema


def source_facts_schema_hash() -> str:
    encoded = json.dumps(
        source_facts_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_facts_provider_schema_hash(
    package: dict[str, Any] | None = None,
) -> str:
    encoded = json.dumps(
        source_facts_provider_json_schema(package),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bind_provider_schema_to_package(
    schema: dict[str, Any],
    package: dict[str, Any],
) -> None:
    properties = schema["properties"]
    exact_top = {
        "source_facts_set_id": package.get("expected_source_facts_set_id"),
        "extraction_run_id": package.get("extraction_run_id"),
        "normalization_run_id": package.get("normalization_run_id"),
        "case_id": package.get("case_id"),
        "package_refs": [package.get("package_artifact_ref")],
        "document_refs": [package.get("document_ref")],
        "validation_ref": None,
        "validator_status": "pending",
        "created_at": package.get("created_at"),
    }
    for field, value in exact_top.items():
        _set_provider_const(properties, field, value)
    expected_audit = copy.deepcopy(package.get("expected_candidate_audit") or {})
    properties["extraction_audit"] = _strict_const_object(expected_audit)

    allowed_issues = sorted(_string_values(package.get("allowed_issue_refs")))
    allowed_evidence = sorted(_string_values(package.get("allowed_evidence_refs")))
    allowed_values = sorted(_string_values(package.get("allowed_source_value_refs")))
    deterministic_candidates = _provider_value_candidates_by_field(package)
    issue_policy = _provider_issue_policy(package)
    unresolved_issues = [
        item
        for item in package.get("issue_context") or []
        if isinstance(item, dict) and item.get("status") == "unresolved"
    ]
    unit = package.get("source_unit") if isinstance(package.get("source_unit"), dict) else {}
    cell_refs = _string_values(unit.get("cell_refs"))
    text_refs = _string_values(unit.get("text_segment_refs"))
    hinted_fact_types = _provider_fact_type_hints(unit)
    allowed_fact_types = set(_string_values(package.get("allowed_fact_types")))
    if allowed_fact_types:
        properties["facts"]["items"]["anyOf"] = [
            variant
            for variant in properties["facts"]["items"]["anyOf"]
            if variant["properties"]["fact_type"].get("const")
            in allowed_fact_types
        ]
        properties["facts"]["maxItems"] = len(
            _string_values(
                _object_value(package.get("coverage_expectation")).get(
                    "selected_source_refs"
                )
            )
        )
    if hinted_fact_types:
        properties["facts"]["items"]["anyOf"] = [
            variant
            for variant in properties["facts"]["items"]["anyOf"]
            if variant["properties"]["fact_type"].get("const")
            in hinted_fact_types
        ]

    for variant in properties["facts"]["items"]["anyOf"]:
        fact_properties = variant["properties"]
        _set_provider_const(fact_properties, "fact_id", "pending")
        _set_provider_const(
            fact_properties, "document_ref", package.get("document_ref")
        )
        _set_provider_const(
            fact_properties,
            "extraction_package_ref",
            package.get("package_artifact_ref"),
        )
        _set_provider_const(fact_properties, "source_unit_ref", unit.get("unit_id"))
        _set_provider_const(fact_properties, "linked_issue_refs", allowed_issues)
        fact_properties["evidence_refs"]["description"] = (
            "Use only package allowed_evidence_refs. Include the selected row_ref "
            "or text_segment_ref for this fact plus every source_location ref."
        )
        if allowed_fact_types:
            fact_properties["evidence_refs"] = _provider_restricted_ref_array(
                allowed_evidence
            )
            original_properties = fact_properties["original_value_refs"][
                "properties"
            ]
            normalized_properties = fact_properties["normalized_values"][
                "properties"
            ]
            for field in NORMALIZED_VALUE_FIELDS:
                field_candidates = deterministic_candidates.get(field, [])
                candidate_values = sorted(
                    {
                        str(item["normalized_value"])
                        for item in field_candidates
                    }
                )
                candidate_refs = sorted(
                    {
                        str(item["source_value_ref"])
                        for item in field_candidates
                    }
                )
                if candidate_values:
                    normalized_properties[field] = {
                        "type": ["string", "null"],
                        "enum": [*candidate_values, None],
                    }
                    original_properties[field] = _provider_restricted_ref_array(
                        candidate_refs
                    )
                    original_properties[field]["maxItems"] = 1
                elif unit.get("source_input_mode") == "normalized_table_projection":
                    normalized_properties[field] = {"type": "null"}
                    original_properties[field] = {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 0,
                    }
                else:
                    original_properties[field] = _provider_restricted_ref_array(
                        allowed_values
                    )
            extracted_properties = fact_properties["extracted_fields"][
                "properties"
            ]
            for field in (
                "source_visible_direction_refs",
                "source_country_value_refs",
                "description_value_refs",
            ):
                if field in extracted_properties:
                    extracted_properties[field] = _provider_restricted_ref_array(
                        allowed_values
                    )
            for field in (
                "related_income_source_refs",
                "related_operation_source_refs",
            ):
                if field in extracted_properties:
                    extracted_properties[field] = _provider_restricted_ref_array(
                        allowed_evidence
                    )
        if unresolved_issues:
            fact_properties["completeness"]["enum"] = [
                "partial",
                "uncertain",
                "blocked",
            ]
        if (
            variant["properties"]["fact_type"].get("const")
            == "unknown_source_row"
        ):
            fact_properties["completeness"]["enum"] = ["uncertain", "blocked"]
            fact_properties["confidence"]["enum"] = ["low", "none"]
            fact_properties["extracted_fields"]["properties"][
                "unknown_reason_codes"
            ]["description"] = (
                "Provide at least one concise reason code for the visible unknown row; "
                "never return an empty array."
            )
        fact_properties["issue_impact"] = _strict_const_object(
            issue_policy["issue_impact"]
        )
        fact_properties["extraction_audit"] = _strict_const_object(expected_audit)
        _set_provider_const(fact_properties, "validator_status", "pending")
        _set_provider_const(fact_properties, "validation_ref", None)
        location = fact_properties["source_location"]["properties"]
        _set_provider_const(
            location,
            "private_slice_artifact_ref",
            unit.get("private_slice_artifact_ref"),
        )
        _set_provider_const(location, "slice_ref", unit.get("slice_ref"))
        _set_provider_const(location, "parser_ref", unit.get("parser_ref"))
        _set_provider_const(
            location, "source_checksum_ref", unit.get("source_checksum_ref")
        )
        _set_provider_const(location, "table_ref", unit.get("table_ref"))
        _set_provider_const(location, "row_range_ref", unit.get("row_range_ref"))
        location["cell_refs"] = (
            _provider_restricted_ref_array(cell_refs)
            if allowed_fact_types
            else _provider_ref_array(cell_refs)
        )
        location["text_segment_refs"] = (
            _provider_restricted_ref_array(text_refs)
            if allowed_fact_types
            else _provider_ref_array(text_refs)
        )

    expectation = package.get("coverage_expectation")
    expectation = expectation if isinstance(expectation, dict) else {}
    coverage = properties["coverage"]["properties"]
    selected = _string_values(expectation.get("selected_source_refs"))
    _set_provider_const(
        coverage, "unit_coverage_ref", expectation.get("coverage_ref")
    )
    _set_provider_const(coverage, "selected_source_refs", selected)
    coverage["no_fact_results"]["description"] = (
        "Must include these mandatory header/blank/layout results exactly once, "
        "plus only any other justified no-fact result: "
        + json.dumps(
            expectation.get("mandatory_no_fact_results") or [],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    _set_provider_const(coverage, "rejected_refs", [])
    _set_provider_const(coverage, "pending_refs", [])
    _set_provider_const(coverage, "coverage_status", "complete")
    issue_summary = properties["issue_linkage_summary"]["properties"]
    _set_provider_const(issue_summary, "package_issue_refs", allowed_issues)
    _set_provider_const(
        issue_summary,
        "unresolved_issue_refs",
        sorted(
            str(item.get("issue_ref"))
            for item in package.get("issue_context") or []
            if isinstance(item, dict)
            and item.get("status") == "unresolved"
            and item.get("issue_ref")
        ),
    )


def _strict_const_object(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            str(key): _typed_provider_const(value)
            for key, value in values.items()
        },
        "required": [str(key) for key in values],
    }


def _provider_issue_policy(package: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "warning_issue_refs": [],
        "limits_confirmation_issue_refs": [],
        "blocks_fact_issue_refs": [],
        "blocks_consolidation_issue_refs": [],
        "blocks_declaration_issue_refs": [],
        "forbidden_assumption_codes": sorted(
            _string_values(package.get("forbidden_assumptions"))
        ),
    }
    mapping = {
        "warning": "warning_issue_refs",
        "limits_confirmation": "limits_confirmation_issue_refs",
        "blocks_fact": "blocks_fact_issue_refs",
        "blocks_consolidation": "blocks_consolidation_issue_refs",
        "blocks_declaration": "blocks_declaration_issue_refs",
    }
    for item in package.get("issue_context") or []:
        if not isinstance(item, dict):
            continue
        key = mapping.get(str(item.get("impact") or ""))
        if key and item.get("issue_ref"):
            impact[key].append(str(item["issue_ref"]))
    for key in mapping.values():
        impact[key] = sorted(set(impact[key]))
    return {"issue_impact": impact}


def _provider_value_candidates_by_field(
    package: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for item in package.get("deterministic_value_candidates") or []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "")
        source_value_ref = str(item.get("source_value_ref") or "")
        normalized_value = item.get("normalized_value")
        if (
            field not in NORMALIZED_VALUE_FIELDS
            or not source_value_ref
            or normalized_value is None
        ):
            continue
        result.setdefault(field, []).append(
            {
                "source_value_ref": source_value_ref,
                "normalized_value": str(normalized_value),
            }
        )
    return result


def _string_values(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []


def _provider_ref_array(values: list[str]) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _provider_restricted_ref_array(values: list[str]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": len(values),
    }
    if values:
        schema["items"]["enum"] = sorted(set(values))
    return schema


def _object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _provider_fact_type_hints(source_unit: dict[str, Any]) -> set[str]:
    projection = source_unit.get("model_source_projection")
    projection = projection if isinstance(projection, dict) else {}
    rows = [item for item in projection.get("rows") or [] if isinstance(item, dict)]
    if not rows or any(not row.get("fact_type_hint") for row in rows):
        return set()
    return {
        str(row["fact_type_hint"])
        for row in rows
        if str(row.get("fact_type_hint") or "") in FACT_TYPES
    }


def _set_provider_const(
    properties: dict[str, Any],
    field: str,
    value: Any,
) -> None:
    if isinstance(value, list):
        field_schema = copy.deepcopy(properties[field])
        field_schema["description"] = (
            "Must equal this exact JSON array: "
            + json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
        properties[field] = field_schema
        return
    field_schema = copy.deepcopy(properties[field])
    field_schema["const"] = copy.deepcopy(value)
    properties[field] = field_schema


def _typed_provider_const(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "const": None}
    if isinstance(value, bool):
        return {"type": "boolean", "const": value}
    if isinstance(value, int):
        return {"type": "integer", "const": value}
    if isinstance(value, float):
        return {"type": "number", "const": value}
    if isinstance(value, list):
        return {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Must equal this exact JSON array: "
                + json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            ),
        }
    return {"type": "string", "const": str(value)}


def parse_source_facts_model_output(value: Any) -> dict[str, Any]:
    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise Gate2PromptError(
                "source_fact_structured_output_required",
                "Model output is not one JSON object",
            )
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise Gate2PromptError("source_fact_schema_mismatch", "Model output is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise Gate2PromptError("source_fact_schema_mismatch", "Model output is not an object")
    return copy.deepcopy(parsed)


def model_call_audit_metadata(
    *,
    prompt: Gate2ManagedPrompt,
    model_id: str,
    raw_output_artifact_ref: str | None,
    provider_response_schema_hash: str | None = None,
    extraction_attempt_ordinal: int = 1,
    repair_attempt_count: int = 0,
    created_at: str,
) -> dict[str, Any]:
    return {
        "prompt_ref": prompt.prompt_ref,
        "prompt_command": prompt.command,
        "prompt_version": prompt.version,
        "prompt_hash": prompt.hash,
        "prompt_contract_id": prompt.prompt_contract_id,
        "template_id": prompt.template_id,
        "output_schema_id": prompt.output_schema_id,
        "output_schema_version": prompt.output_schema_version,
        "output_schema_hash": source_facts_schema_hash(),
        "provider_response_schema_hash": (
            provider_response_schema_hash
            or source_facts_provider_schema_hash()
        ),
        "provider_union_keyword": "anyOf",
        "model_id": model_id,
        "structured_output_mode": STRUCTURED_OUTPUT_MODE,
        "response_format_type": RESPONSE_FORMAT_TYPE,
        "fallback_used": False,
        "repair_attempt_count": repair_attempt_count,
        "raw_output_artifact_ref": raw_output_artifact_ref,
        "extraction_attempt_ordinal": extraction_attempt_ordinal,
        "created_at": created_at,
    }


def _extracted_field_schemas() -> dict[str, dict[str, Any]]:
    string_array = _array({"type": "string"})
    nullable_string = {"type": ["string", "null"]}
    return {
        "trade_operation": _strict_object(
            {
                "operation_type_candidate": {
                    "type": "string",
                    "enum": ["buy", "sell", "redemption", "transfer", "corporate_action", "unknown"],
                },
                "source_visible_direction_refs": copy.deepcopy(string_array),
            }
        ),
        "income": _strict_object(
            {
                "income_type_candidate": {
                    "type": "string",
                    "enum": ["dividend", "coupon", "interest", "sale_proceeds", "other", "unknown"],
                },
                "source_country_candidate": copy.deepcopy(nullable_string),
                "source_country_value_refs": copy.deepcopy(string_array),
            }
        ),
        "withholding_tax": _strict_object(
            {
                "withholding_type_candidate": {
                    "type": "string",
                    "enum": ["domestic", "foreign", "unknown"],
                },
                "source_country_candidate": copy.deepcopy(nullable_string),
                "related_income_source_refs": copy.deepcopy(string_array),
            }
        ),
        "fee_commission": _strict_object(
            {
                "fee_type_candidate": {
                    "type": "string",
                    "enum": ["broker_commission", "exchange_fee", "custody_fee", "other", "unknown"],
                },
                "related_operation_source_refs": copy.deepcopy(string_array),
            }
        ),
        "cash_movement": _strict_object(
            {
                "movement_type_candidate": {
                    "type": "string",
                    "enum": ["deposit", "withdrawal", "credit", "debit", "unknown"],
                },
                "description_safe_label": copy.deepcopy(nullable_string),
                "description_value_refs": copy.deepcopy(string_array),
            }
        ),
        "currency_fx": _strict_object(
            {
                "fx_fact_kind": {
                    "type": "string",
                    "enum": ["currency_amount", "explicit_rate", "source_provided_conversion", "unknown"],
                }
            }
        ),
        "position_snapshot": _strict_object(
            {
                "position_kind_candidate": {
                    "type": "string",
                    "enum": ["security_position", "cash_position", "other", "unknown"],
                }
            }
        ),
        "document_summary_evidence": _strict_object(
            {
                "summary_kind_candidate": {"type": "string"},
                "source_provided": {"type": "boolean", "const": True},
            }
        ),
        "unknown_source_row": _strict_object(
            {"unknown_reason_codes": copy.deepcopy(string_array)}
        ),
    }


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": copy.deepcopy(properties),
        "required": list(properties),
    }


def _nullable_object(properties: dict[str, Any]) -> dict[str, Any]:
    schema = _strict_object(properties)
    schema["type"] = ["object", "null"]
    return schema


def _array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": copy.deepcopy(items)}


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []
