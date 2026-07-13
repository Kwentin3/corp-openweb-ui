from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    PdfCompactCanonicalError,
    PdfCompactCanonicalFactory,
    PdfCompactCanonicalValidator,
    PdfCompactGate2AdapterFactory,
    PdfCompactGate2MappingValidator,
    PdfNormalizationAcceptanceFactory,
    PdfNormalizationAcceptanceValidator,
    build_retention_policy,
    persist_gate1_result,
    resolve_compact_source_value,
)
from broker_reports_gate1.pdf_compact_canonical import (
    FACTORY_REQUIRED as COMPACT_FACTORY_REQUIRED,
    FORBIDDEN as COMPACT_FORBIDDEN,
    canonical_json_bytes,
    compact_table_cells,
)
from broker_reports_gate1.pdf_compact_gate2_adapter import (
    FACTORY_REQUIRED as ADAPTER_FACTORY_REQUIRED,
    FORBIDDEN as ADAPTER_FORBIDDEN,
)
from broker_reports_gate1.pdf_normalization_acceptance import (
    FACTORY_REQUIRED as ACCEPTANCE_FACTORY_REQUIRED,
    FORBIDDEN as ACCEPTANCE_FORBIDDEN,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes, _ruled_table_pdf
from tests.test_broker_reports_table_projection import _repeated_header_wrapped_pdf


def _normalize(pdf_bytes: bytes, *, enabled: bool = False):
    return Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="compact-synthetic",
                filename="compact-synthetic.pdf",
                content=pdf_bytes,
                mime_type="application/pdf",
            )
        ],
        input_context={"pdf_compact_canonical_dual_write": enabled},
    )


def _compact(result, *, payload=None, units=None, projections=None, decisions=None):
    package = result.package
    document = package["document_inventory"]["documents"][0]
    return PdfCompactCanonicalFactory().create().build(
        normalization_run_id=package["normalization_run"]["run_id"],
        document=document,
        original_pdf_artifact_ref="art_original_pdf",
        source_payload=payload or package["private_normalized_source_payloads"][0],
        source_units=units or package["private_normalized_source_units"],
        table_projections=(
            projections
            if projections is not None
            else package["private_normalized_table_projections"]
        ),
        table_decisions=(
            decisions if decisions is not None else package["table_projection_decisions"]
        ),
    )


def _empty_cell_pdf() -> bytes:
    texts = [
        (30, 220, "Date"),
        (125, 220, "Amount"),
        (225, 220, "Currency"),
        (30, 195, "2026-01-01"),
        (225, 195, "USD"),
        (30, 170, "2026-01-02"),
        (125, 170, "20.00"),
        (225, 170, "EUR"),
    ]
    vectors = [
        "20 155 m 300 155 l S",
        "20 180 m 300 180 l S",
        "20 205 m 300 205 l S",
        "20 230 m 300 230 l S",
        "20 155 m 20 230 l S",
        "110 155 m 110 230 l S",
        "210 155 m 210 230 l S",
        "300 155 m 300 230 l S",
    ]
    return _pdf_bytes([{"texts": texts, "vectors": vectors}])


def _persist(result):
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    run_id = result.package["normalization_run"]["run_id"]
    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=ArtifactAccessContext(
            user_id="compact-test-user",
            normalization_run_id=run_id,
            case_id="compact-test-case",
        ),
        retention_policy=build_retention_policy(
            mode="api_smoke", ttl_seconds=3600, explicit=True
        ),
        source_file_refs=[
            {
                "provider": "openwebui_process_false",
                "openwebui_file_id": "synthetic-process-false-file",
            }
        ],
    )
    return temporary, store, manifest


def test_factory_anchors_and_default_flag_are_fail_closed() -> None:
    assert "PdfCompactCanonicalFactory.create" in COMPACT_FACTORY_REQUIRED
    assert "must not bypass" in COMPACT_FORBIDDEN
    assert "PdfCompactGate2AdapterFactory.create" in ADAPTER_FACTORY_REQUIRED
    assert "production Gate 2 selection must not use it" in ADAPTER_FORBIDDEN
    assert "PdfNormalizationAcceptanceFactory.create" in ACCEPTANCE_FACTORY_REQUIRED
    assert "must not be bypassed" in ACCEPTANCE_FORBIDDEN
    from openwebui_actions.broker_reports_gate1_pipe import Pipe

    assert Pipe.Valves().pdf_compact_canonical_dual_write is False


def test_builder_accepts_grid_preserves_empty_cell_headers_and_source_resolution() -> None:
    result = _normalize(_empty_cell_pdf())
    compact = _compact(result)
    assert PdfCompactCanonicalValidator().validate(compact)["passed"]
    table = compact["tables"][0]
    assert table["status"] == "accepted"
    assert table["cell_count"] == table["row_count"] * table["column_count"]
    cells = compact_table_cells(table)
    empty = next(item for item in cells if item["empty_cell"])
    assert empty["text"] == ""
    assert empty["source_value_refs"] == []
    nonempty = next(item for item in cells if item["source_value_refs"])
    source_ref = nonempty["source_value_refs"][0]
    assert resolve_compact_source_value(compact, source_ref) in nonempty["text"]
    assert table["header_model"]["header_to_column_mapping_status"] == "mapped"
    assert "char_inventory" not in canonical_json_bytes(compact).decode("utf-8")
    assert "word_inventory" not in canonical_json_bytes(compact).decode("utf-8")


def test_builder_preserves_repeated_header_model_and_explicit_blocked_table() -> None:
    repeated_result = _normalize(_repeated_header_wrapped_pdf())
    repeated = _compact(repeated_result)
    assert repeated["tables"][0]["header_model"]["repeated_header_row_refs"]

    blocked_result = _normalize(_ruled_table_pdf())
    projections = copy.deepcopy(
        blocked_result.package["private_normalized_table_projections"]
    )
    projections[0]["projection_status"] = "blocked"
    projections[0]["table_candidate_status"] = "rejected_to_line_cluster"
    decisions = copy.deepcopy(blocked_result.package["table_projection_decisions"])
    decisions[0]["status"] = "rejected_to_line_cluster"
    blocked = _compact(blocked_result, projections=projections, decisions=decisions)
    table = blocked["tables"][0]
    assert table["status"] == "blocked"
    assert compact_table_cells(table) == []
    assert blocked["coverage"]["tables_blocked_total"] == 1


def test_builder_is_idempotent_and_fails_on_missing_duplicate_or_inconsistent_refs() -> None:
    result = _normalize(_ruled_table_pdf())
    first = _compact(result)
    second = _compact(result)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    unknown = copy.deepcopy(first)
    unknown["unknown_field"] = True
    assert not PdfCompactCanonicalValidator().validate(unknown)["passed"]
    forbidden = copy.deepcopy(first)
    forbidden["tables"][0]["char_inventory"] = []
    assert not PdfCompactCanonicalValidator().validate(forbidden)["passed"]

    with pytest.raises(PdfCompactCanonicalError) as missing:
        _compact(result, projections=[])
    assert missing.value.code == "pdf_compact_table_projection_missing"

    projections = result.package["private_normalized_table_projections"]
    with pytest.raises(PdfCompactCanonicalError) as duplicate:
        _compact(result, projections=[projections[0], copy.deepcopy(projections[0])])
    assert duplicate.value.code == "pdf_compact_duplicate_projection_table_ref"

    duplicate_source = copy.deepcopy(projections)
    first_ref = duplicate_source[0]["cells"][0]["source_value_refs"][0]
    duplicate_source[0]["cells"][1]["source_value_refs"].append(first_ref)
    with pytest.raises(PdfCompactCanonicalError) as duplicate_owner:
        _compact(result, projections=duplicate_source)
    assert duplicate_owner.value.code == "pdf_compact_duplicate_source_ownership"

    inconsistent = copy.deepcopy(projections)
    inconsistent[0]["source_value_index"][0]["source_object_ref"] = "missing_word_ref"
    with pytest.raises(PdfCompactCanonicalError) as bad_source:
        _compact(result, projections=inconsistent)
    assert bad_source.value.code == "pdf_compact_source_word_missing"

    bad_grid = copy.deepcopy(projections)
    bad_grid[0]["cells"][0]["row_ordinal"] = 999
    with pytest.raises(PdfCompactCanonicalError) as inconsistent_grid:
        _compact(result, projections=bad_grid)
    assert inconsistent_grid.value.code == "pdf_compact_cell_grid_invalid"


def test_differential_mapping_is_validator_accepted_and_identity_equivalent() -> None:
    result = _normalize(_empty_cell_pdf())
    compact = _compact(result)
    current = result.package["private_normalized_table_projections"]
    comparison = PdfCompactGate2MappingValidator().validate(
        compact_document=compact, current_projections=current
    )
    assert comparison == {
        "schema_version": "broker_reports_pdf_compact_gate2_mapping_v1",
        "passed": True,
        "validator_status": "passed",
        "accepted_tables_compared": 1,
        "blocked_tables_compared": 0,
        "table_decisions_compared": 1,
        "status_equivalent": True,
        "errors_count": 0,
        "errors": [],
        "production_gate2_selection_changed": False,
    }
    mapped = PdfCompactGate2AdapterFactory().create().map_table(
        compact_document=compact, table_ref=compact["tables"][0]["table_ref"]
    )
    assert mapped["table_projection_id"] == current[0]["table_projection_id"]
    assert mapped["header_model"] == current[0]["header_model"]
    assert [item["empty_cell"] for item in mapped["cells"]] == [
        item["empty_cell"] for item in current[0]["cells"]
    ]


def test_acceptance_has_independent_gates_and_measured_storage() -> None:
    result = _normalize(_ruled_table_pdf())
    compact = _compact(result)
    projections = result.package["private_normalized_table_projections"]
    mapping = PdfCompactGate2MappingValidator().validate(
        compact_document=compact, current_projections=projections
    )
    acceptance = PdfNormalizationAcceptanceFactory().create().build(
        compact_document=compact,
        compact_canonical_artifact_ref="art_compact",
        source_payloads=result.package["private_normalized_source_payloads"],
        source_units=result.package["private_normalized_source_units"],
        table_projections=projections,
        current_artifact_refs={
            "source_payloads": ["art_full"],
            "source_units": ["art_unit"],
            "table_projections": ["art_projection"],
        },
        mapping_validation=mapping,
        reproducibility_passed=True,
    )
    assert PdfNormalizationAcceptanceValidator().validate(acceptance)["passed"]
    assert set(acceptance["gates"]) == {
        "structural_correctness",
        "provenance_correctness",
        "source_ref_accounting",
        "storage_proportionality",
        "llm_projection_readiness",
        "reproducibility",
        "artifact_classification",
        "cleanup_readiness",
    }
    assert acceptance["metrics"]["compact_json_bytes"] == len(
        canonical_json_bytes(compact)
    )
    assert acceptance["metrics"]["full_forensic_json_bytes"] > acceptance["metrics"][
        "compact_json_bytes"
    ]
    assert acceptance["cleanup_status"] == "deferred_dual_write_safety"
    assert acceptance["metrics"]["permanent_artifact_total_bytes"] == acceptance[
        "metrics"
    ]["intended_permanent_bytes"]


def test_storage_dual_write_uses_actual_source_ref_and_keeps_gate2_authoritative() -> None:
    result = _normalize(_ruled_table_pdf(), enabled=True)
    temporary, store, manifest = _persist(result)
    try:
        compact_records = store.list_by_type(
            manifest.normalization_run_id,
            "broker_reports_pdf_compact_canonical_document_v1",
        )
        acceptance_records = store.list_by_type(
            manifest.normalization_run_id,
            "broker_reports_pdf_normalization_acceptance_v1",
        )
        source_records = store.list_by_type(
            manifest.normalization_run_id, "source_file_ref_v0"
        )
        assert len(compact_records) == len(acceptance_records) == len(source_records) == 1
        compact = store.read_payload(compact_records[0])
        acceptance = store.read_payload(acceptance_records[0])
        assert compact["original_pdf_artifact_ref"] == source_records[0].artifact_id
        assert acceptance["compact_canonical_artifact_ref"] == compact_records[0].artifact_id
        assert compact_records[0].storage_backend == "project_artifact_payload"
        assert acceptance_records[0].storage_backend == "project_artifact_store"
        assert all(
            item.storage_backend != "openwebui_knowledge"
            for item in store.list_by_run(manifest.normalization_run_id)
        )
        handoff_record = store.list_by_type(
            manifest.normalization_run_id, "gate2_handoff_v0"
        )[0]
        handoff = store.read_payload(handoff_record)
        assert not any("compact" in key for key in handoff)
        assert compact_records[0].artifact_id not in handoff["private_slice_refs"]
        assert acceptance_records[0].artifact_id not in handoff["safe_refs"]
    finally:
        temporary.cleanup()


def test_feature_off_and_non_pdf_regression_create_no_shadow_artifacts() -> None:
    off = _normalize(_ruled_table_pdf(), enabled=False)
    temporary, _, manifest = _persist(off)
    try:
        assert "broker_reports_pdf_compact_canonical_document_v1" not in (
            manifest.artifact_refs_by_type
        )
    finally:
        temporary.cleanup()

    csv_result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="compact-csv",
                filename="compact.csv",
                content=b"Date,Amount\n2026-01-01,10\n",
                mime_type="text/csv",
            )
        ],
        input_context={"pdf_compact_canonical_dual_write": True},
    )
    temporary, _, manifest = _persist(csv_result)
    try:
        assert "broker_reports_pdf_compact_canonical_document_v1" not in (
            manifest.artifact_refs_by_type
        )
    finally:
        temporary.cleanup()


def test_typed_shadow_failure_keeps_current_artifacts_and_accepts_no_partial_compact() -> None:
    result = _normalize(_ruled_table_pdf(), enabled=True)
    result.package["private_normalized_source_payloads"] = []
    temporary, store, manifest = _persist(result)
    try:
        failures = store.list_by_type(
            manifest.normalization_run_id,
            "broker_reports_pdf_compact_build_failure_v1",
        )
        assert len(failures) == 1
        failure = store.read_payload(failures[0])
        assert failure["failure_code"] == "pdf_compact_source_payload_cardinality_invalid"
        assert failure["current_normalization_available"] is True
        assert failure["partial_compact_accepted"] is False
        assert store.list_by_type(
            manifest.normalization_run_id,
            "broker_reports_normalized_table_projection_v0",
        )
        assert not store.list_by_type(
            manifest.normalization_run_id,
            "broker_reports_pdf_compact_canonical_document_v1",
        )
    finally:
        temporary.cleanup()
