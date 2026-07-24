from __future__ import annotations

from typing import Any

from .gate2_financial_evidence_decision import DECISION_SCHEMA_VERSION
from .gate2_financial_evidence_materialization_contracts import (
    COMPLETENESS_VALUES,
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    MATERIALIZATION_POLICY_VERSION,
    MEASUREMENT_ROLES,
    SHA256_RE,
    TEMPORAL_ROLES,
    fail,
    normalize_comparison_value,
    role_projection,
    sha256_json,
    source_sign,
    unique_lineage,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)


def validate_financial_evidence_inputs(
    *,
    payload: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "schema_version",
        "materialization_policy_version",
        "artifact_id",
        "registry",
        "source_package",
        "terminal_disposition",
        "typed_inputs",
        "unclassified_inputs",
        "coverage",
        "execution",
        "integrity_hash",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        fail("financial_evidence_inputs_shape_invalid")
    if (
        payload["schema_version"]
        != FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
        or payload["materialization_policy_version"]
        != MATERIALIZATION_POLICY_VERSION
    ):
        fail("financial_evidence_inputs_version_invalid")
    if payload["registry"] != {
        "registry_id": REGISTRY_ID,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
    }:
        fail("financial_evidence_inputs_registry_invalid")
    integrity_hash = payload["integrity_hash"]
    unsigned = dict(payload)
    unsigned.pop("integrity_hash")
    if integrity_hash != sha256_json(unsigned):
        fail("financial_evidence_inputs_integrity_invalid")

    typed = payload["typed_inputs"]
    unclassified = payload["unclassified_inputs"]
    disposition = payload["terminal_disposition"]
    if not isinstance(typed, list) or not isinstance(unclassified, list):
        fail("financial_evidence_inputs_terminal_shape_invalid")
    expected_counts = {
        "typed_input": (1, 0),
        "unclassified_financial_input": (0, 1),
        "no_financial_input": (0, 0),
        "unsupported": (0, 0),
    }
    if (
        disposition not in expected_counts
        or (len(typed), len(unclassified))
        != expected_counts[disposition]
    ):
        fail("financial_evidence_inputs_terminal_shape_invalid")
    for item in typed:
        _validate_terminal_integrity(item, "input_id", "finin_")
        _validate_typed_input(item, registry)
    for item in unclassified:
        _validate_terminal_integrity(
            item,
            "unclassified_input_id",
            "finun_",
        )
        _validate_unclassified_input(item, registry)

    coverage = payload["coverage"]
    if (
        not isinstance(coverage, dict)
        or set(coverage)
        != {
            "coverage_id",
            "source_scope_ref",
            "scope_accounted",
            "terminal_disposition",
            "reason_code",
            "candidate_refs_total",
            "bound_source_value_refs",
        }
        or coverage.get("scope_accounted") is not True
        or coverage.get("terminal_disposition") != disposition
        or not str(coverage.get("coverage_id") or "").startswith(
            "finclose_"
        )
    ):
        fail("financial_evidence_coverage_invalid")
    terminal_ids = [
        item["input_id"] for item in typed
    ] + [
        item["unclassified_input_id"] for item in unclassified
    ]
    source_package = payload["source_package"]
    if not isinstance(source_package, dict) or set(source_package) != {
        "schema_version",
        "package_ref",
        "integrity_hash",
        "source_scope_ref",
        "source_family_id",
        "source_values_total",
        "source_value_refs_hash",
    }:
        fail("financial_evidence_inputs_source_package_invalid")
    for item in [*typed, *unclassified]:
        ownership = item["source_ownership"]
        if (
            item["source_scope_ref"]
            != source_package["source_scope_ref"]
            or not isinstance(ownership, dict)
            or ownership.get("source_package_ref")
            != source_package["package_ref"]
            or ownership.get("source_scope_ref")
            != source_package["source_scope_ref"]
        ):
            fail("financial_evidence_inputs_source_ownership_invalid")
    if coverage["source_scope_ref"] != source_package["source_scope_ref"]:
        fail("financial_evidence_coverage_scope_invalid")
    if (
        coverage["candidate_refs_total"]
        != source_package["source_values_total"]
        or not SHA256_RE.fullmatch(
            source_package["source_value_refs_hash"]
        )
    ):
        fail("financial_evidence_coverage_candidate_count_invalid")
    expected_bound_refs = sorted(
        value["source_value_ref"]
        for item in [*typed, *unclassified]
        for value in item["source_values"]
    )
    if coverage["bound_source_value_refs"] != expected_bound_refs:
        fail("financial_evidence_coverage_bound_refs_invalid")
    if (
        disposition == "unclassified_financial_input"
        and sha256_json(expected_bound_refs)
        != source_package["source_value_refs_hash"]
    ):
        fail("financial_evidence_unclassified_value_loss")
    expected_coverage_id = "finclose_" + sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "source_package_integrity_hash": source_package[
                "integrity_hash"
            ],
            "source_scope_ref": source_package["source_scope_ref"],
            "terminal_disposition": disposition,
            "reason_code": coverage["reason_code"],
            "bound_source_value_refs": coverage[
                "bound_source_value_refs"
            ],
        }
    )[:32]
    if coverage["coverage_id"] != expected_coverage_id:
        fail("financial_evidence_coverage_id_invalid")
    expected_artifact_id = "finset_" + sha256_json(
        {
            "schema_version": FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
            "registry_hash": registry.registry_hash,
            "source_package_integrity_hash": source_package[
                "integrity_hash"
            ],
            "terminal_disposition": disposition,
            "terminal_ids": terminal_ids,
            "coverage_id": coverage["coverage_id"],
        }
    )[:32]
    if payload["artifact_id"] != expected_artifact_id:
        fail("financial_evidence_inputs_artifact_id_invalid")
    execution = payload["execution"]
    if not isinstance(execution, dict) or set(execution) != {
        "execution_ref",
        "decision_validation_ref",
        "decision_schema_version",
        "decision_schema_hash",
    }:
        fail("financial_evidence_inputs_execution_invalid")
    if (
        execution["decision_schema_version"] != DECISION_SCHEMA_VERSION
        or not SHA256_RE.fullmatch(execution["decision_schema_hash"])
    ):
        fail("financial_evidence_inputs_execution_invalid")
    if _contains_gate3_field(payload):
        fail("financial_evidence_inputs_gate3_field_forbidden")


def _validate_terminal_integrity(
    item: Any,
    id_field: str,
    id_prefix: str,
) -> None:
    if not isinstance(item, dict):
        fail("financial_evidence_terminal_object_invalid")
    integrity_hash = item.get("integrity_hash")
    unsigned = dict(item)
    unsigned.pop("integrity_hash", None)
    if integrity_hash != sha256_json(unsigned):
        fail("financial_evidence_terminal_integrity_invalid")
    if not str(item.get(id_field) or "").startswith(id_prefix):
        fail("financial_evidence_terminal_id_invalid")


def _validate_typed_input(
    item: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "input_id",
        "input_type_id",
        "semantic_class",
        "registry_version",
        "registry_hash",
        "materialization_profile_id",
        "validation_profile_id",
        "source_scope_ref",
        "source_values",
        "normalized_comparison_values",
        "date_period",
        "currency_unit",
        "source_sign_policy",
        "source_sign_by_value_ref",
        "identity_policy",
        "source_evidence_refs",
        "lineage",
        "source_ownership",
        "completeness",
        "restriction_codes",
        "issue_refs",
        "integrity_hash",
    }
    if set(item) != expected_keys:
        fail("financial_evidence_typed_input_shape_invalid")
    declaration = registry.get(item["input_type_id"])
    if (
        item["semantic_class"] != declaration.semantic_class
        or item["registry_version"] != registry.registry_version
        or item["registry_hash"] != registry.registry_hash
        or item["materialization_profile_id"]
        != declaration.materialization_profile_id
        or item["validation_profile_id"]
        != declaration.validation_profile_id
        or item["source_sign_policy"] != declaration.source_sign_policy
    ):
        fail("financial_evidence_typed_input_registry_mismatch")
    values = _validate_materialized_values(item["source_values"])
    _validate_materialized_projections(item, values)
    bound_roles = {value["role_id"] for value in values}
    if (
        not set(declaration.required_roles) <= bound_roles
        or not bound_roles
        <= set(declaration.required_roles + declaration.optional_roles)
    ):
        fail("financial_evidence_typed_input_roles_invalid")
    identity_policy = item["identity_policy"]
    if identity_policy != {
        "identity_roles": list(
            declaration.identity_policy.identity_roles
        ),
        "include_source_scope": (
            declaration.identity_policy.include_source_scope
        ),
        "include_source_evidence_refs": (
            declaration.identity_policy.include_source_evidence_refs
        ),
    }:
        fail("financial_evidence_typed_input_identity_policy_invalid")
    identity_roles = set(declaration.identity_policy.identity_roles)
    expected_id = "finin_" + sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "input_type_id": item["input_type_id"],
            "source_scope_ref": item["source_scope_ref"],
            "identity_values": [
                {
                    "role_id": value["role_id"],
                    "source_value_ref": value["source_value_ref"],
                    "normalized_comparison_value": value[
                        "normalized_comparison_value"
                    ],
                }
                for value in values
                if value["role_id"] in identity_roles
            ],
            "source_evidence_refs": item["source_evidence_refs"],
        }
    )[:32]
    if item["input_id"] != expected_id:
        fail("financial_evidence_typed_input_id_invalid")


def _validate_unclassified_input(
    item: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "unclassified_input_id",
        "registry_version",
        "registry_hash",
        "registry_gap",
        "gap_reason_code",
        "typed_input_published",
        "source_scope_ref",
        "source_values",
        "normalized_comparison_values",
        "date_period",
        "currency_unit",
        "source_sign_by_value_ref",
        "source_evidence_refs",
        "lineage",
        "source_ownership",
        "completeness",
        "restriction_codes",
        "issue_refs",
        "integrity_hash",
    }
    if set(item) != expected_keys:
        fail("financial_evidence_unclassified_shape_invalid")
    if (
        item["registry_version"] != registry.registry_version
        or item["registry_hash"] != registry.registry_hash
        or item["registry_gap"] is not True
        or item["typed_input_published"] is not False
    ):
        fail("financial_evidence_unclassified_state_invalid")
    values = _validate_materialized_values(item["source_values"])
    _validate_materialized_projections(item, values)
    expected_id = "finun_" + sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "source_scope_ref": item["source_scope_ref"],
            "source_values": [
                {
                    "role_id": value["role_id"],
                    "source_value_ref": value["source_value_ref"],
                    "normalized_comparison_value": value[
                        "normalized_comparison_value"
                    ],
                }
                for value in values
            ],
            "source_evidence_refs": item["source_evidence_refs"],
        }
    )[:32]
    if item["unclassified_input_id"] != expected_id:
        fail("financial_evidence_unclassified_id_invalid")


def _validate_materialized_values(
    values: Any,
) -> list[dict[str, Any]]:
    expected_keys = {
        "role_id",
        "source_value_ref",
        "source_ref",
        "value_type",
        "literal_value",
        "normalized_comparison_value",
        "source_sign",
        "source_evidence_refs",
        "lineage",
    }
    if not isinstance(values, list) or not values:
        fail("financial_evidence_source_values_invalid")
    previous_key: tuple[str, str] | None = None
    for value in values:
        if not isinstance(value, dict) or set(value) != expected_keys:
            fail("financial_evidence_source_value_shape_invalid")
        key = (value["role_id"], value["source_value_ref"])
        if previous_key is not None and key <= previous_key:
            fail("financial_evidence_source_values_order_invalid")
        previous_key = key
        expected_normalized = normalize_comparison_value(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        )
        if value["normalized_comparison_value"] != expected_normalized:
            fail("financial_evidence_comparison_value_invalid")
        if value["source_sign"] != source_sign(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        ):
            fail("financial_evidence_source_sign_invalid")
        lineage = value["lineage"]
        if not isinstance(lineage, dict) or set(lineage) != {
            "document_ref",
            "page_ref",
            "table_ref",
            "row_ref",
            "cell_ref",
            "text_segment_ref",
        }:
            fail("financial_evidence_lineage_shape_invalid")
    return values


def _validate_materialized_projections(
    item: dict[str, Any],
    values: list[dict[str, Any]],
) -> None:
    if item["normalized_comparison_values"] != {
        value["source_value_ref"]: value["normalized_comparison_value"]
        for value in values
    }:
        fail("financial_evidence_comparison_projection_invalid")
    if item["date_period"] != role_projection(values, TEMPORAL_ROLES):
        fail("financial_evidence_date_period_projection_invalid")
    if item["currency_unit"] != role_projection(
        values,
        MEASUREMENT_ROLES,
    ):
        fail("financial_evidence_currency_unit_projection_invalid")
    if item["source_sign_by_value_ref"] != {
        value["source_value_ref"]: value["source_sign"]
        for value in values
        if value["source_sign"] != "not_applicable"
    }:
        fail("financial_evidence_source_sign_projection_invalid")
    evidence_refs = item["source_evidence_refs"]
    if (
        not isinstance(evidence_refs, list)
        or evidence_refs != sorted(set(evidence_refs))
        or any(
            not set(value["source_evidence_refs"]) <= set(evidence_refs)
            for value in values
        )
    ):
        fail("financial_evidence_source_evidence_refs_invalid")
    if item["lineage"] != unique_lineage(values):
        fail("financial_evidence_lineage_projection_invalid")
    if item["completeness"] not in COMPLETENESS_VALUES:
        fail("financial_evidence_completeness_invalid")
    for field in ("restriction_codes", "issue_refs"):
        field_values = item[field]
        if (
            not isinstance(field_values, list)
            or field_values != sorted(set(field_values))
        ):
            fail(f"financial_evidence_{field}_invalid")


def _contains_gate3_field(value: Any) -> bool:
    forbidden = {
        "answer_instruction",
        "gate3",
        "ledger_candidate",
        "relevance",
        "tax_calculation",
    }
    if isinstance(value, dict):
        return bool(set(value) & forbidden) or any(
            _contains_gate3_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_gate3_field(item) for item in value)
    return False
