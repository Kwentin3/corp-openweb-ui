from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.qualified_projection_fact_v3 import (
    QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION,
    QualifiedProjectionFactV3Error,
    build_qualified_projection_fact_v3,
    qualified_projection_binding,
    qualified_projection_fact_v3_id,
    validate_qualified_projection_fact_v3,
)


def _fact() -> dict:
    return build_qualified_projection_fact_v3(
        case_binding={"scope_kind": "case", "scope_id": "case-1"},
        projection_artifact_id="art_projection_1",
        canonical_binding={"document_id": "document-1", "canonical_version_id": "version-1", "canonical_root_sha256": "a" * 64},
        source_observation_id="observation-1",
        semantic_mapping_case_ref="mapping-case-1",
        runtime_record_id="runtime-record-1",
        semantic_kind="normalized_source_fact",
        semantic_binding={"dictionary": {"authority_id": "mapping:1", "semantic_version": "1"}, "role_pack": {"authority_id": "runtime:1", "semantic_version": "1"}},
        financial_type="SECURITY_PURCHASE",
        annotation_target={"kind": "runtime_record", "record_id": "runtime-record-1"},
        roles=[{"role": "currency", "requirement": "required", "status": "value", "value": "RUB", "source_binding": {"target": {"kind": "table_cell", "node_id": "node-1", "row": 1, "column": 2}, "exact_text": "RUB", "source_literal": "RUB"}}],
        status="role_complete",
    )


def test_valid_v3_fact_has_deterministic_identity_and_provenance() -> None:
    fact = _fact()
    assert fact["schema_version"] == QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION
    assert fact["fact_id"] == qualified_projection_fact_v3_id(fact)
    assert validate_qualified_projection_fact_v3(fact) == fact
    assert qualified_projection_binding(fact)["runtime_record_id"] == "runtime-record-1"


def test_optional_source_role_is_preserved_without_semantic_reclassification() -> None:
    fact = _fact()
    fact["roles"].append(
        {
            "role": "position_effect",
            "requirement": "optional",
            "status": "value",
            "value": "OPEN_SHORT",
            "source_binding": {
                "target": {"kind": "table_cell", "node_id": "node-1", "row": 1, "column": 3},
                "exact_text": "OPEN_SHORT",
                "source_literal": "OPEN_SHORT",
            },
        }
    )
    fact["fact_id"] = qualified_projection_fact_v3_id(fact)

    assert validate_qualified_projection_fact_v3(fact) == fact


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value["qualified_projection_binding"].__setitem__("source_observation_id", "other"), "qualified_projection_fact_v3_identity_invalid"),
        (lambda value: value["qualified_projection_binding"].pop("runtime_record_id"), "qualified_projection_fact_v3_binding_invalid"),
        (lambda value: value["qualified_projection_binding"]["canonical_binding"].__setitem__("source_sha256", "b" * 64), "qualified_projection_fact_v3_canonical_binding_invalid"),
        (lambda value: value["roles"][0].__setitem__("value", "USD"), "qualified_projection_fact_v3_identity_invalid"),
    ],
)
def test_tampered_fact_fails_closed(mutation, code) -> None:
    fact = copy.deepcopy(_fact())
    mutation(fact)
    with pytest.raises(QualifiedProjectionFactV3Error) as exc:
        validate_qualified_projection_fact_v3(fact)
    assert exc.value.code == code
