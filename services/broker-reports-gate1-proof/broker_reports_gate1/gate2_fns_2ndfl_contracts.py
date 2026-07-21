from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any


ADAPTER_ID = "broker_reports_fns_2ndfl_source_facts_v1"
ADAPTER_VERSION = "1.0.0"
TYPED_FACTS_SCHEMA_VERSION = "broker_reports_fns_2ndfl_source_facts_v1"
TYPED_FACT_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_fns_2ndfl_source_facts_validation_v1"
)
SAFE_REPORT_SCHEMA_VERSION = "broker_reports_fns_2ndfl_source_facts_safe_report_v1"
FNS_SCHEMA_FAMILY = "FNS_2_NDFL_XML"

XML_EVENT_COLUMNS = (
    "event_ordinal",
    "depth",
    "event_type",
    "node_path",
    "name",
    "attribute_name",
    "value",
)

FACT_FAMILIES = {
    "source_certificate_identity",
    "tax_agent_identity",
    "recipient_identity",
    "income_source_row",
    "deduction_source_row",
    "tax_summary_source_fact",
    "certificate_metadata",
}

FACT_RESTRICTIONS = (
    "source_local_meaning_only",
    "no_tax_declaration_calculation",
    "no_cross_document_reconciliation",
    "no_tax_entitlement_decision",
    "no_gate3_or_gate4_output",
    "private_case_values",
)

FACTORY_REQUIRED = (
    "Gate2Fns2NdflAdapterFactory.create is the only production FNS 2-NDFL "
    "typed-adapter entrypoint"
)
FORBIDDEN = (
    "Gate 1 must remain financially neutral; callers must not use a model, "
    "silently select the newest schema, mint source refs, or bypass typed "
    "validation"
)


def integrity_ref(prefix: str, value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()}"


def validate_fns_2ndfl_typed_output(
    payload: dict[str, Any],
    *,
    allowed_source_value_refs: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    facts = _dict_list(payload.get("facts"))
    document_ref = str(payload.get("source_document_ref") or "")
    package_ref = str(payload.get("source_package_ref") or "")
    allowed_refs = set(str(item) for item in (allowed_source_value_refs or []))

    if payload.get("schema_version") != TYPED_FACTS_SCHEMA_VERSION:
        errors.append(_error("fns_2ndfl_output_schema_invalid", document_ref))
    if payload.get("adapter_id") != ADAPTER_ID:
        errors.append(_error("fns_2ndfl_adapter_id_invalid", document_ref))
    if payload.get("adapter_version") != ADAPTER_VERSION:
        errors.append(_error("fns_2ndfl_adapter_version_invalid", document_ref))
    if payload.get("schema_family") != FNS_SCHEMA_FAMILY:
        errors.append(_error("fns_2ndfl_schema_family_invalid", document_ref))
    if payload.get("terminal_status") != "validated":
        errors.append(_error("fns_2ndfl_terminal_status_invalid", document_ref))
    if not document_ref or not package_ref:
        errors.append(_error("fns_2ndfl_source_identity_missing", document_ref))
    if not payload.get("schema_version_id") or not payload.get("report_period"):
        errors.append(_error("fns_2ndfl_schema_period_selection_missing", document_ref))
    if payload.get("vendor_extensions") != []:
        errors.append(_error("fns_2ndfl_vendor_extensions_not_empty", document_ref))
    for item in _dict_list(payload.get("non_fact_source_nodes")):
        if item.get("reason_code") != (
            "income_row_without_amount_not_material_source_fact"
        ):
            errors.append(_error("fns_2ndfl_non_fact_reason_invalid", document_ref))
        refs = {
            str(item.get("node_ref") or ""),
            str(item.get("node_path_ref") or ""),
            *_string_list(item.get("attribute_name_refs")),
            *_string_list(item.get("attribute_value_refs")),
        }
        if "" in refs or (allowed_refs and not refs <= allowed_refs):
            errors.append(_error("fns_2ndfl_non_fact_ref_out_of_scope", document_ref))

    provider = _object(payload.get("provider_accounting"))
    for field in ("calls", "tokens", "cost"):
        if provider.get(field) != 0:
            errors.append(_error("fns_2ndfl_provider_accounting_nonzero", field))
    if provider.get("llm_fallback_allowed") is not False:
        errors.append(_error("fns_2ndfl_llm_fallback_not_forbidden", document_ref))

    fact_ids: set[str] = set()
    family_counts: Counter[str] = Counter()
    for fact in facts:
        fact_id = str(fact.get("fact_id") or "")
        family = str(fact.get("fact_family") or "")
        if not fact_id or fact_id in fact_ids:
            errors.append(_error("fns_2ndfl_fact_id_duplicate_or_missing", fact_id))
        fact_ids.add(fact_id)
        family_counts[family] += 1
        if family not in FACT_FAMILIES:
            errors.append(_error("fns_2ndfl_fact_family_invalid", fact_id))
        if fact.get("source_document_ref") != document_ref:
            errors.append(_error("fns_2ndfl_fact_document_scope_mismatch", fact_id))
        if fact.get("source_package_ref") != package_ref:
            errors.append(_error("fns_2ndfl_fact_package_scope_mismatch", fact_id))
        if fact.get("adapter_id") != ADAPTER_ID or fact.get(
            "adapter_version"
        ) != ADAPTER_VERSION:
            errors.append(_error("fns_2ndfl_fact_adapter_identity_invalid", fact_id))
        if fact.get("schema_family") != FNS_SCHEMA_FAMILY or fact.get(
            "schema_version_id"
        ) != payload.get("schema_version_id"):
            errors.append(_error("fns_2ndfl_fact_schema_identity_invalid", fact_id))
        if fact.get("validation_status") != "validated":
            errors.append(_error("fns_2ndfl_fact_validation_status_invalid", fact_id))
        if tuple(fact.get("restrictions") or ()) != FACT_RESTRICTIONS:
            errors.append(_error("fns_2ndfl_fact_restrictions_invalid", fact_id))
        node_refs = _string_list(fact.get("original_node_refs"))
        value_refs = _string_list(fact.get("original_value_refs"))
        if not node_refs or not value_refs:
            errors.append(_error("fns_2ndfl_fact_original_refs_missing", fact_id))
        if allowed_refs and not set(node_refs + value_refs) <= allowed_refs:
            errors.append(_error("fns_2ndfl_fact_source_ref_out_of_scope", fact_id))
        fields = _dict_list(fact.get("fields"))
        if family in {
            "income_source_row",
            "deduction_source_row",
            "tax_summary_source_fact",
        }:
            section_ref = str(fact.get("source_section_ref") or "")
            if not section_ref or section_ref not in node_refs:
                errors.append(_error("fns_2ndfl_fact_section_link_missing", fact_id))
        if not fields:
            errors.append(_error("fns_2ndfl_fact_fields_missing", fact_id))
        for field in fields:
            field_ref = str(field.get("original_value_ref") or "")
            node_ref = str(field.get("original_node_ref") or "")
            if not field.get("field_code") or not field.get("value_type"):
                errors.append(_error("fns_2ndfl_fact_field_contract_invalid", fact_id))
            if not field_ref or not node_ref:
                errors.append(_error("fns_2ndfl_fact_field_refs_missing", fact_id))
            if allowed_refs and not {field_ref, node_ref} <= allowed_refs:
                errors.append(_error("fns_2ndfl_fact_field_ref_out_of_scope", fact_id))
        expected_fact_integrity = integrity_ref(
            "fnsfactchk",
            {key: value for key, value in fact.items() if key != "integrity_ref"},
        )
        if fact.get("integrity_ref") != expected_fact_integrity:
            errors.append(_error("fns_2ndfl_fact_integrity_mismatch", fact_id))

    required_families = {
        "source_certificate_identity",
        "tax_agent_identity",
        "recipient_identity",
        "income_source_row",
        "tax_summary_source_fact",
        "certificate_metadata",
    }
    for missing in sorted(required_families - set(family_counts)):
        errors.append(_error("fns_2ndfl_required_fact_family_missing", missing))

    expected_output_integrity = integrity_ref(
        "fnsoutchk",
        {key: value for key, value in payload.items() if key != "integrity_ref"},
    )
    if payload.get("integrity_ref") != expected_output_integrity:
        errors.append(_error("fns_2ndfl_output_integrity_mismatch", document_ref))

    return {
        "schema_version": TYPED_FACT_VALIDATION_SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "source_document_ref": document_ref,
        "source_package_ref": package_ref,
        "validator_status": "passed" if not errors else "failed",
        "facts_total": len(facts),
        "fact_family_counts": dict(sorted(family_counts.items())),
        "source_refs_validated_total": (
            len(
                {
                    ref
                    for fact in facts
                    for ref in (
                        _string_list(fact.get("original_node_refs"))
                        + _string_list(fact.get("original_value_refs"))
                    )
                }
            )
            if not errors
            else 0
        ),
        "provider_calls": provider.get("calls"),
        "errors": errors,
    }


def render_fns_2ndfl_safe_report(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_fns_2ndfl_typed_output(payload)
    facts = _dict_list(payload.get("facts"))
    family_counts = Counter(str(item.get("fact_family") or "unknown") for item in facts)
    safe = {
        "schema_version": SAFE_REPORT_SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "opaque_source_document_id": integrity_ref(
            "fnsdoc", str(payload.get("source_document_ref") or "")
        ),
        "schema_family": payload.get("schema_family"),
        "schema_version_id": payload.get("schema_version_id"),
        "report_period": payload.get("report_period"),
        "terminal_status": payload.get("terminal_status"),
        "validator_status": validation.get("validator_status"),
        "facts_total": len(facts),
        "fact_family_counts": dict(sorted(family_counts.items())),
        "vendor_extensions_total": len(payload.get("vendor_extensions") or []),
        "non_fact_source_nodes_total": len(
            payload.get("non_fact_source_nodes") or []
        ),
        "provider_calls": _object(payload.get("provider_accounting")).get("calls"),
        "provider_tokens": _object(payload.get("provider_accounting")).get("tokens"),
        "provider_cost": _object(payload.get("provider_accounting")).get("cost"),
        "customer_values_in_report": False,
        "source_refs_only": True,
        "typed_output_integrity_ref": payload.get("integrity_ref"),
    }
    safe["integrity_ref"] = integrity_ref("fnssafechk", safe)
    return safe


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in value or [] if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)]


def _error(code: str, subject: object) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "unknown")}
