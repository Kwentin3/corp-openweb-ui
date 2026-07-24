from __future__ import annotations

from typing import Any

from .gate2_financial_context_contracts import (
    AGGREGATE_SEMANTICS,
    FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION,
    FINANCIAL_CONTEXT_SCHEMA_VERSION,
    STATUSES,
    fail,
)
from .gate2_financial_evidence_decision import (
    NO_FINANCIAL_REASON_CODES,
    TYPED_REASON_CODES,
    UNCLASSIFIED_REASON_CODES,
    UNSUPPORTED_REASON_CODES,
)
from .gate2_financial_evidence_materialization_contracts import (
    COMPLETENESS_VALUES,
    MEASUREMENT_ROLES,
    SHA256_RE,
    TEMPORAL_ROLES,
    normalize_comparison_value,
    sha256_json,
    source_sign,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)


_FORBIDDEN_FIELDS = {
    "answer_instruction",
    "calculated_aggregate",
    "crop_image",
    "declaration_mapping",
    "full_text",
    "gate1_raw",
    "internal_audit",
    "pdf_bytes",
    "provider_response",
    "raw_pdf",
    "tax_methodology",
}


def validate_financial_context(
    *,
    payload: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "projection_policy_version",
        "registry",
        "entries",
        "scope_coverage",
        "integrity_hash",
    }:
        fail("financial_context_shape_invalid")
    if (
        payload["schema_version"] != FINANCIAL_CONTEXT_SCHEMA_VERSION
        or payload["projection_policy_version"]
        != FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION
    ):
        fail("financial_context_version_invalid")
    if payload["registry"] != {
        "registry_id": REGISTRY_ID,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
    }:
        fail("financial_context_registry_invalid")
    unsigned = dict(payload)
    integrity_hash = unsigned.pop("integrity_hash")
    if integrity_hash != sha256_json(unsigned):
        fail("financial_context_integrity_invalid")
    entries = payload["entries"]
    if not isinstance(entries, list):
        fail("financial_context_entries_invalid")
    scopes: list[str] = []
    status_counts = {status: 0 for status in sorted(STATUSES)}
    for entry in entries:
        _validate_entry(entry, registry)
        scopes.append(entry["source_scope_ref"])
        status_counts[entry["status"]] += 1
    if scopes != sorted(set(scopes)):
        fail("financial_context_duplicate_interpretation_scope")
    coverage = payload["scope_coverage"]
    expected_coverage = {
        "source_scopes_total": len(entries),
        "interpretation_representations_total": len(entries),
        "provenance_only_representations_total": sum(
            len(item["provenance_only_representations"])
            for item in entries
        ),
        "status_counts": status_counts,
        "duplicate_interpretation_representations_total": 0,
        "calculated_aggregates_total": 0,
    }
    if coverage != expected_coverage:
        fail("financial_context_coverage_invalid")
    if _contains_forbidden_field(payload):
        fail("financial_context_forbidden_field")


def _validate_entry(
    entry: Any,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(entry, dict) or set(entry) != {
        "context_entry_id",
        "source_scope_ref",
        "status",
        "interpretation_representation",
        "provenance_only_representations",
    }:
        fail("financial_context_entry_shape_invalid")
    if entry["status"] not in STATUSES:
        fail("financial_context_status_invalid")
    interpretation = entry["interpretation_representation"]
    _validate_interpretation(
        interpretation,
        status=entry["status"],
        source_scope_ref=entry["source_scope_ref"],
        registry=registry,
    )
    provenance = entry["provenance_only_representations"]
    if not isinstance(provenance, list):
        fail("financial_context_provenance_representations_invalid")
    representation_ids: list[str] = []
    for representation in provenance:
        if not isinstance(representation, dict) or set(representation) != {
            "representation_id",
            "representation_role",
            "source_ref",
            "source_value_refs",
            "source_evidence_refs",
            "lineage",
        }:
            fail("financial_context_provenance_representation_shape_invalid")
        if representation["representation_role"] != "provenance_only":
            fail("financial_context_representation_role_invalid")
        representation_ids.append(representation["representation_id"])
        if (
            representation["source_value_refs"]
            != sorted(set(representation["source_value_refs"]))
            or representation["source_evidence_refs"]
            != sorted(set(representation["source_evidence_refs"]))
        ):
            fail("financial_context_provenance_identity_invalid")
        lineages = representation["lineage"]
        if not isinstance(lineages, list) or any(
            not isinstance(lineage, dict)
            or set(lineage)
            != {
                "document_ref",
                "page_ref",
                "table_ref",
                "row_ref",
                "cell_ref",
                "text_segment_ref",
            }
            for lineage in lineages
        ):
            fail("financial_context_provenance_lineage_invalid")
        expected_representation_id = "finprov_" + sha256_json(
            {
                "source_package_integrity_hash": interpretation[
                    "evidence_identity"
                ]["source_package_integrity_hash"],
                "source_ref": representation["source_ref"],
                "source_value_refs": representation[
                    "source_value_refs"
                ],
                "source_evidence_refs": representation[
                    "source_evidence_refs"
                ],
                "lineage": lineages,
            }
        )[:32]
        if representation["representation_id"] != (
            expected_representation_id
        ):
            fail("financial_context_provenance_representation_id_invalid")
    if representation_ids != sorted(set(representation_ids)):
        fail("financial_context_provenance_representation_duplicate")
    expected_entry_id = "finctx_" + sha256_json(
        {
            "source_scope_ref": entry["source_scope_ref"],
            "status": entry["status"],
            "interpretation_representation_id": interpretation[
                "representation_id"
            ],
            "evidence_identity": interpretation["evidence_identity"],
        }
    )[:32]
    if entry["context_entry_id"] != expected_entry_id:
        fail("financial_context_entry_id_invalid")


def _validate_interpretation(
    interpretation: Any,
    *,
    status: str,
    source_scope_ref: str,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(interpretation, dict) or set(interpretation) != {
        "representation_id",
        "representation_role",
        "status",
        "input_type",
        "aggregate_semantics",
        "literal_source_labels",
        "values",
        "date_period",
        "currency_unit",
        "source_location",
        "restrictions",
        "evidence_identity",
        "terminal_reason_code",
    }:
        fail("financial_context_interpretation_shape_invalid")
    if (
        interpretation["representation_role"] != "interpretation"
        or interpretation["status"] != status
        or interpretation["aggregate_semantics"]
        not in AGGREGATE_SEMANTICS
    ):
        fail("financial_context_interpretation_state_invalid")
    source_location = interpretation["source_location"]
    if (
        not isinstance(source_location, dict)
        or source_location.get("source_scope_ref") != source_scope_ref
        or set(source_location)
        != {"document_ref", "page_refs", "source_scope_ref"}
    ):
        fail("financial_context_source_location_invalid")
    if source_location["page_refs"] != sorted(
        set(source_location["page_refs"])
    ):
        fail("financial_context_source_location_invalid")
    input_type = interpretation["input_type"]
    semantics = interpretation["aggregate_semantics"]
    if status == "typed_input":
        if not isinstance(input_type, dict) or set(input_type) != {
            "input_type_id",
            "title",
            "semantic_class",
        }:
            fail("financial_context_input_type_invalid")
        declaration = registry.get(input_type["input_type_id"])
        if input_type != {
            "input_type_id": declaration.input_type_id,
            "title": declaration.title,
            "semantic_class": declaration.semantic_class,
        }:
            fail("financial_context_input_type_invalid")
        expected_semantics = (
            "source_printed"
            if declaration.input_type_id == "printed_financial_metric_v1"
            else "not_aggregate"
        )
        if semantics != expected_semantics:
            fail("financial_context_aggregate_semantics_invalid")
    elif input_type is not None:
        fail("financial_context_input_type_forbidden")
    elif status == "unclassified_financial_input":
        if semantics != "unclassified":
            fail("financial_context_aggregate_semantics_invalid")
    elif semantics != "not_applicable":
        fail("financial_context_aggregate_semantics_invalid")
    values = interpretation["values"]
    if not isinstance(values, list):
        fail("financial_context_values_invalid")
    if status in {"typed_input", "unclassified_financial_input"}:
        if not values:
            fail("financial_context_values_missing")
    elif values:
        fail("financial_context_terminal_values_forbidden")
    for value in values:
        if not isinstance(value, dict) or set(value) != {
            "role_id",
            "source_value_ref",
            "value_type",
            "literal_value",
            "source_sign",
        }:
            fail("financial_context_value_shape_invalid")
        if value["source_sign"] != source_sign(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        ):
            fail("financial_context_source_sign_invalid")
    if values != sorted(
        values,
        key=lambda item: (item["role_id"], item["source_value_ref"]),
    ):
        fail("financial_context_values_order_invalid")
    labels = interpretation["literal_source_labels"]
    if labels != sorted(
        {
            value["literal_value"]
            for value in values
            if value["role_id"] == "source_label"
        }
    ):
        fail("financial_context_source_labels_invalid")
    expected_date_period = {
        value["role_id"]: normalize_comparison_value(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        )
        for value in values
        if value["role_id"] in TEMPORAL_ROLES
    }
    expected_currency_unit = {
        value["role_id"]: normalize_comparison_value(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        )
        for value in values
        if value["role_id"] in MEASUREMENT_ROLES
    }
    if (
        interpretation["date_period"] != expected_date_period
        or interpretation["currency_unit"] != expected_currency_unit
    ):
        fail("financial_context_dimension_projection_invalid")
    restrictions = interpretation["restrictions"]
    if not isinstance(restrictions, dict) or set(restrictions) != {
        "completeness",
        "restriction_codes",
        "issue_refs",
    }:
        fail("financial_context_restrictions_invalid")
    if restrictions["completeness"] not in COMPLETENESS_VALUES:
        fail("financial_context_restrictions_invalid")
    for field in ("restriction_codes", "issue_refs"):
        if restrictions[field] != sorted(set(restrictions[field])):
            fail("financial_context_restrictions_invalid")
    evidence = interpretation["evidence_identity"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "financial_evidence_artifact_id",
        "financial_evidence_artifact_integrity_hash",
        "terminal_object_id",
        "terminal_object_integrity_hash",
        "source_package_ref",
        "source_package_integrity_hash",
        "source_value_refs",
        "source_evidence_refs",
    }:
        fail("financial_context_evidence_identity_invalid")
    if (
        interpretation["representation_id"]
        != evidence["terminal_object_id"]
        or not SHA256_RE.fullmatch(
            evidence["financial_evidence_artifact_integrity_hash"]
        )
        or not SHA256_RE.fullmatch(
            evidence["source_package_integrity_hash"]
        )
        or (
            evidence["terminal_object_integrity_hash"] is not None
            and not SHA256_RE.fullmatch(
                evidence["terminal_object_integrity_hash"]
            )
        )
        or evidence["source_value_refs"]
        != sorted(set(evidence["source_value_refs"]))
        or evidence["source_evidence_refs"]
        != sorted(set(evidence["source_evidence_refs"]))
        or evidence["source_value_refs"]
        != sorted(value["source_value_ref"] for value in values)
    ):
        fail("financial_context_evidence_identity_invalid")
    reason_codes = {
        "typed_input": TYPED_REASON_CODES,
        "unclassified_financial_input": UNCLASSIFIED_REASON_CODES,
        "no_financial_input": NO_FINANCIAL_REASON_CODES,
        "unsupported": UNSUPPORTED_REASON_CODES,
    }
    if interpretation["terminal_reason_code"] not in reason_codes[status]:
        fail("financial_context_terminal_reason_invalid")


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(set(value) & _FORBIDDEN_FIELDS) or any(
            _contains_forbidden_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False
