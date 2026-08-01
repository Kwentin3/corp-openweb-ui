from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


SEMANTIC_RESPONSE_SCHEMA_VERSION = "broker_reports_doc4_semantic_response_v1"
GOLD_CHECKLIST_SCHEMA_VERSION = "broker_reports_doc4_gold_checklist_v1"
SEMANTIC_COMPARISON_SCHEMA_VERSION = (
    "broker_reports_doc4_semantic_comparison_v1"
)
ADJUDICATION_SCHEMA_VERSION = "broker_reports_doc4_adjudication_v1"
EXPERIMENT_PROTOCOL_VERSION = "broker_reports_doc4_experiment_protocol_v1"
EXPERIMENT_RUN_PLAN_SCHEMA_VERSION = "broker_reports_doc4_run_plan_v1"
PROVIDER_AUTHORIZATION_SCHEMA_VERSION = (
    "broker_reports_doc4_provider_transfer_authorization_v1"
)

CORPUS_IDS = ("real_pdf_1", "real_pdf_2", "real_pdf_4", "real_pdf_5")
RUN_ORDER = {
    "real_pdf_1": ("PDF", "LLM_VIEW"),
    "real_pdf_2": ("LLM_VIEW", "PDF"),
    "real_pdf_4": ("PDF", "LLM_VIEW"),
    "real_pdf_5": ("LLM_VIEW", "PDF"),
}
PASSPORT_FIELDS = (
    "document_type",
    "title",
    "issuer",
    "document_date",
    "reporting_period",
    "owner_or_account",
    "language",
    "primary_currency",
    "page_count",
)
STATUS_VALUES = {"PRESENT", "UNKNOWN", "NOT_APPLICABLE", "CONFLICTING"}
CRITICAL_FACT_KINDS = {
    "OPERATION_DATE",
    "QUANTITY",
    "PRICE",
    "AMOUNT",
    "CURRENCY",
    "COMMISSION",
    "TAX",
    "BALANCE",
    "TOTAL",
    "SUBTOTAL",
    "OPENING_BALANCE",
    "CLOSING_BALANCE",
}
COMPARISON_CATEGORIES = {
    "MATCH_EXACT",
    "MATCH_NORMALIZED",
    "PDF_ONLY_FACT",
    "VIEW_ONLY_FACT",
    "VALUE_CONFLICT",
    "STATUS_CONFLICT",
    "ORDER_CONFLICT",
    "MISSING_POINTER",
    "INVALID_POINTER",
    "UNSUPPORTED_FACT",
    "UNCOMPARABLE",
}
ADJUDICATION_DISPOSITIONS = {
    "PDF_ARM_CORRECT",
    "VIEW_ARM_CORRECT",
    "BOTH_CORRECT",
    "PDF_ARM_WRONG",
    "VIEW_ARM_WRONG",
    "BOTH_WRONG",
    "ARTIFACT_SEMANTIC_GAP",
    "PDF_NATIVE_MODEL_GAP",
    "MODEL_GENERAL_FAILURE",
    "PROMPT_OR_SCHEMA_FAILURE",
    "SOURCE_AMBIGUOUS",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE_DMY = re.compile(r"^(\d{2})[./-](\d{2})[./-](\d{4})$")
_DATE_MDY = re.compile(r"^(\d{2})[./-](\d{2})[./-](\d{4})$")


class Doc4ContractError(ValueError):
    pass


@dataclass(frozen=True)
class ViewPointerRegistry:
    block_anchor_ids: Mapping[str, frozenset[str]]
    tables: Mapping[str, tuple[str, tuple[int, ...]]]
    block_types: Mapping[str, str] | None = None


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def integrity_sha256(value: Mapping[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "integrity_sha256"}
    return sha256_bytes(canonical_json_bytes(payload))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Doc4ContractError(f"json_read_failed:{path.name}:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise Doc4ContractError(f"json_root_not_object:{path.name}")
    return value


def validate_schema_document(schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise Doc4ContractError("json_schema_invalid") from exc
    _require_closed_objects(schema)


def validate_json_contract(value: Any, schema: dict[str, Any], *, label: str) -> None:
    validate_schema_document(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "$"
        raise Doc4ContractError(f"{label}_schema_invalid:{location}:{first.validator}")


def validate_semantic_response(
    value: dict[str, Any],
    schema: dict[str, Any],
    *,
    expected_source_mode: str,
    pdf_pages_total: int | None = None,
    view_registry: ViewPointerRegistry | None = None,
) -> dict[str, Any]:
    validate_json_contract(value, schema, label="semantic_response")
    if value.get("schema_version") != SEMANTIC_RESPONSE_SCHEMA_VERSION:
        raise Doc4ContractError("semantic_response_schema_version_mismatch")
    if value.get("source_mode") != expected_source_mode:
        raise Doc4ContractError("semantic_response_source_mode_mismatch")
    passport = value.get("document_passport")
    if not isinstance(passport, list):
        raise Doc4ContractError("semantic_response_passport_invalid")
    field_ids = [item.get("field_id") for item in passport if isinstance(item, dict)]
    if tuple(field_ids) != PASSPORT_FIELDS:
        raise Doc4ContractError("semantic_response_passport_order_invalid")
    _require_unique_ids(value)
    for item in passport:
        _validate_status_item(item, critical=item["field_id"] in {"reporting_period", "owner_or_account"})
        _validate_pointers(
            item["evidence"],
            expected_source_mode=expected_source_mode,
            pdf_pages_total=pdf_pages_total,
            view_registry=view_registry,
        )
    for item in value["document_structure"]:
        _validate_status_item(item, critical=item["type"] in {"TABLE", "TABLE_ROW"})
        _validate_pointers(
            item["evidence"],
            expected_source_mode=expected_source_mode,
            pdf_pages_total=pdf_pages_total,
            view_registry=view_registry,
        )
    for item in value["tables"]:
        _validate_status_item(item, critical=True)
        _validate_pointers(
            item["evidence"],
            expected_source_mode=expected_source_mode,
            pdf_pages_total=pdf_pages_total,
            view_registry=view_registry,
        )
    for item in value["financial_facts"]:
        if item["fact_kind"] in CRITICAL_FACT_KINDS and item["critical"] is not True:
            raise Doc4ContractError("required_critical_fact_downgraded")
        _validate_status_item(item, critical=bool(item["critical"]))
        if item["status"] != "PRESENT" and any(
            item[name] is not None
            for name in ("normalized_decimal", "normalized_date", "currency", "unit", "sign")
        ):
            raise Doc4ContractError("nonpresent_financial_fact_has_normalized_value")
        _validate_pointers(
            item["evidence"],
            expected_source_mode=expected_source_mode,
            pdf_pages_total=pdf_pages_total,
            view_registry=view_registry,
        )
    for item in value["uncertainties"]:
        _validate_pointers(
            item["evidence"],
            expected_source_mode=expected_source_mode,
            pdf_pages_total=pdf_pages_total,
            view_registry=view_registry,
        )
    _validate_pointers(
        value["source_quality"]["evidence"],
        expected_source_mode=expected_source_mode,
        pdf_pages_total=pdf_pages_total,
        view_registry=view_registry,
    )
    return value


def validate_provider_authorization(
    value: dict[str, Any],
    *,
    expected_provider: str,
    expected_model_id: str,
) -> None:
    required = {
        "schema_version",
        "provider",
        "request_model_id",
        "authorized",
        "authorization_basis_status",
        "verification_date",
        "explicit_authorization_statement_sha256",
        "organization_api_account_verified",
        "client_document_transfer_permitted",
        "data_retention_verified",
        "training_use_verified",
        "processing_region_verified",
        "provider_logging_verified",
        "provider_operator_access_verified",
        "contractual_restrictions_verified",
        "organization_settings_verified",
        "integrity_sha256",
    }
    if set(value) != required:
        raise Doc4ContractError("provider_authorization_shape_invalid")
    if value["schema_version"] != PROVIDER_AUTHORIZATION_SCHEMA_VERSION:
        raise Doc4ContractError("provider_authorization_version_invalid")
    if value["provider"] != expected_provider or value["request_model_id"] != expected_model_id:
        raise Doc4ContractError("provider_authorization_candidate_mismatch")
    if value["authorization_basis_status"] != "APPROVED":
        raise Doc4ContractError("provider_transfer_not_authorized")
    boolean_fields = (
        "authorized",
        "organization_api_account_verified",
        "client_document_transfer_permitted",
        "data_retention_verified",
        "training_use_verified",
        "processing_region_verified",
        "provider_logging_verified",
        "provider_operator_access_verified",
        "contractual_restrictions_verified",
        "organization_settings_verified",
    )
    if any(value.get(field) is not True for field in boolean_fields):
        raise Doc4ContractError("provider_transfer_not_authorized")
    if not _SHA256.fullmatch(str(value["explicit_authorization_statement_sha256"])):
        raise Doc4ContractError("provider_authorization_statement_hash_invalid")
    _parse_timestamp(value["verification_date"])
    if value["integrity_sha256"] != integrity_sha256(value):
        raise Doc4ContractError("provider_authorization_integrity_invalid")


def normalize_decimal_literal(literal: str, rule: str) -> str:
    text = literal.strip().replace("\u00a0", " ").replace("\u202f", " ")
    if rule == "DECIMAL_DOT":
        compact = text.replace(" ", "").replace(",", "")
    elif rule == "DECIMAL_COMMA":
        compact = text.replace(" ", "").replace(".", "").replace(",", ".")
    elif rule == "INTEGER":
        compact = text.replace(" ", "")
        if "." in compact or "," in compact:
            raise Doc4ContractError("integer_literal_has_decimal_separator")
    else:
        raise Doc4ContractError("decimal_normalization_rule_invalid")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", compact):
        raise Doc4ContractError("decimal_literal_invalid")
    try:
        number = Decimal(compact)
    except InvalidOperation as exc:
        raise Doc4ContractError("decimal_literal_invalid") from exc
    normalized = format(number, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in {"-0", "+0", ""}:
        normalized = "0"
    return normalized


def normalize_date_literal(literal: str, rule: str) -> str:
    text = literal.strip()
    if rule == "DATE_ISO":
        try:
            return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise Doc4ContractError("date_literal_invalid") from exc
    matcher = _DATE_DMY if rule == "DATE_DMY" else _DATE_MDY if rule == "DATE_MDY" else None
    if matcher is None:
        raise Doc4ContractError("date_normalization_rule_invalid")
    match = matcher.fullmatch(text)
    if not match:
        raise Doc4ContractError("date_literal_invalid")
    first, second, year = (int(item) for item in match.groups())
    day, month = (first, second) if rule == "DATE_DMY" else (second, first)
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError as exc:
        raise Doc4ContractError("date_literal_invalid") from exc


def _validate_status_item(item: dict[str, Any], *, critical: bool) -> None:
    status = item.get("status")
    if status not in STATUS_VALUES:
        raise Doc4ContractError("semantic_status_invalid")
    source_literal = item.get("source_literal")
    normalized = item.get("normalized_value")
    evidence = item.get("evidence")
    if status == "PRESENT":
        if source_literal is None and normalized is None:
            raise Doc4ContractError("present_value_missing")
        if not evidence:
            raise Doc4ContractError("present_evidence_missing")
    elif status in {"UNKNOWN", "NOT_APPLICABLE"}:
        if source_literal is not None or normalized is not None:
            raise Doc4ContractError("unknown_or_na_value_present")
    if critical and status in {"PRESENT", "CONFLICTING"} and not evidence:
        raise Doc4ContractError("critical_fact_pointer_missing")


def _validate_pointers(
    pointers: list[dict[str, Any]],
    *,
    expected_source_mode: str,
    pdf_pages_total: int | None,
    view_registry: ViewPointerRegistry | None,
) -> None:
    for pointer in pointers:
        if pointer["source_mode"] != expected_source_mode:
            raise Doc4ContractError("source_pointer_mode_mismatch")
        if expected_source_mode == "PDF":
            page = pointer["page"]
            evidence_text = pointer["evidence_text"]
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                raise Doc4ContractError("pdf_pointer_page_invalid")
            if pdf_pages_total is not None and page > pdf_pages_total:
                raise Doc4ContractError("pdf_pointer_page_out_of_range")
            if not isinstance(evidence_text, str) or not evidence_text or len(evidence_text) > 160:
                raise Doc4ContractError("pdf_pointer_evidence_text_invalid")
            if any(pointer[name] is not None for name in ("block_id", "anchor_id", "table_id", "row_index", "column_index")):
                raise Doc4ContractError("pdf_pointer_contains_view_coordinates")
        else:
            if view_registry is None:
                raise Doc4ContractError("view_pointer_registry_missing")
            block_id = pointer["block_id"]
            anchor_id = pointer["anchor_id"]
            if block_id not in view_registry.block_anchor_ids:
                raise Doc4ContractError("view_pointer_block_id_invalid")
            if anchor_id not in view_registry.block_anchor_ids[block_id]:
                raise Doc4ContractError("view_pointer_anchor_id_invalid")
            if any(pointer[name] is not None for name in ("page", "visible_label", "evidence_text", "table_visible_title", "row_visible_label", "column_visible_label")):
                raise Doc4ContractError("view_pointer_contains_pdf_coordinates")
            table_id = pointer["table_id"]
            row_index = pointer["row_index"]
            column_index = pointer["column_index"]
            if table_id is None:
                if row_index is not None or column_index is not None:
                    raise Doc4ContractError("view_pointer_table_coordinates_without_table")
                continue
            table = view_registry.tables.get(block_id)
            if table is None or table[0] != table_id:
                raise Doc4ContractError("view_pointer_table_id_invalid")
            if row_index is None or column_index is None:
                raise Doc4ContractError("view_pointer_table_coordinates_missing")
            row_lengths = table[1]
            if row_index < 0 or row_index >= len(row_lengths):
                raise Doc4ContractError("view_pointer_row_index_invalid")
            if column_index < 0 or column_index >= row_lengths[row_index]:
                raise Doc4ContractError("view_pointer_column_index_invalid")


def _require_unique_ids(value: dict[str, Any]) -> None:
    paths = (
        ("document_structure", "element_id"),
        ("tables", "table_key"),
        ("financial_facts", "fact_id"),
        ("uncertainties", "uncertainty_id"),
    )
    for collection_name, id_name in paths:
        identifiers = [item[id_name] for item in value[collection_name]]
        if len(identifiers) != len(set(identifiers)):
            raise Doc4ContractError(f"duplicate_{id_name}")


def _require_closed_objects(value: Any) -> None:
    if isinstance(value, dict):
        if value.get("type") == "object" and value.get("additionalProperties") is not False:
            raise Doc4ContractError("json_schema_object_not_closed")
        for item in value.values():
            _require_closed_objects(item)
    elif isinstance(value, list):
        for item in value:
            _require_closed_objects(item)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Doc4ContractError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise Doc4ContractError(f"nonfinite_json_constant:{value}")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise Doc4ContractError("timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Doc4ContractError("timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise Doc4ContractError("timestamp_timezone_missing")
    return parsed
