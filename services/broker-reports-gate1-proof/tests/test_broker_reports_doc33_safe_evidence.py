from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs" / "stage2"
REPORT = (
    REPO
    / "docs"
    / "reports"
    / "2026-08-06"
    / "BROKER_REPORTS_DOC33_UNIFIED_GATE2_MACHINE_PROJECTION.report.md"
)
SAFE_FILES = (
    "BROKER_REPORTS_DOC33_COHORT_READER_PROOF.safe.json",
    "BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.safe.json",
    "BROKER_REPORTS_DOC33_SEMANTIC_EQUIVALENCE.safe.json",
    "BROKER_REPORTS_DOC33_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC33_DECISION.safe.json",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_sha(value: dict) -> str:
    material = dict(value)
    material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_doc33_safe_evidence_is_integral_and_private_free() -> None:
    forbidden = (
        '"document_id"',
        '"user_id"',
        '"tenant_id"',
        '"source_sha256"',
        '"canonical_version_id"',
        '"normalization_run_id"',
        '"openwebui_file_id"',
        '"generic_projection"',
        '"private_path"',
        "private.json",
        "/opt/",
        "\\local\\stage2\\",
    )
    for name in SAFE_FILES:
        path = STAGE2 / name
        assert path.is_file(), name
        value = _read(path)
        assert value["private_content_in_output"] is False, name
        assert value["integrity_sha256"] == _json_sha(value), name
        text = path.read_text(encoding="utf-8").lower()
        assert all(marker.lower() not in text for marker in forbidden), name


def test_doc33_one_reader_cohort_and_format_opacity_are_exact() -> None:
    proof = _read(STAGE2 / SAFE_FILES[0])
    assert proof["status"] == "PASS"
    assert proof["documents_total"] == 16
    assert proof["format_counts"] == {"csv": 2, "html": 4, "pdf": 8, "xlsx": 2}
    assert proof["canonical_schema_versions"] == ["canonical_artifact_v1"]
    assert proof["reader_authority"] == "CanonicalReaderFactory.create"
    assert proof["reader_implementations"] == ["CanonicalReader"]
    assert proof["completeness_passed"] == 16
    assert proof["root_hashes_matched"] == 16
    assert proof["nonempty_neutral_projections"] == 16
    assert proof["renderer_format_branches"] == 0
    assert proof["renderer_forbidden_dependency_hits"] == []
    assert proof["physical_layout_counts"] == {"chunked": 5, "single_payload": 11}
    assert proof["provider_calls"] == 0
    assert proof["product_writes"] == 0
    assert proof["activation_changes"] == 0
    assert proof["legacy_fallbacks"] == 0
    assert proof["gate3_started"] is False


def test_doc33_conformance_and_semantic_equivalence_are_explicit() -> None:
    conformance = _read(STAGE2 / SAFE_FILES[1])
    assert conformance["status"] == "PASS"
    assert conformance["supported_formats"] == ["pdf", "html", "csv", "xlsx"]
    assert conformance["ambiguous_contract_fields"] == []
    assert conformance["unresolved_mandatory_content"] == 0
    assert conformance["parallel_schema_created"] is False
    assert len(conformance["explicit_divergences"]) == 4
    for row in conformance["matrix"]:
        assert set(row) == {"contract_field", "pdf", "html", "csv", "xlsx"}
        assert set(row.values()) - {row["contract_field"]} <= {
            "supported",
            "absent",
            "divergent",
            "ambiguous",
        }

    equivalence = _read(STAGE2 / SAFE_FILES[2])
    assert equivalence["semantic_equivalence"] == "CONFIRMED"
    assert equivalence["reader_roundtrips"] == 4
    assert equivalence["canonical_schema_versions"] == ["canonical_artifact_v1"]
    assert equivalence["logical_table_signatures"] == 1
    assert equivalence["ordered_cells_per_format"] == 6
    assert equivalence["table_values_match"] is True
    assert equivalence["table_order_matches"] is True
    assert equivalence["neutral_projections_nonempty"] == 4
    assert set(equivalence["physical_layouts_exercised"]) == {
        "single_payload",
        "chunked",
    }
    assert equivalence["format_branches_in_renderer"] == 0


def test_doc33_decision_report_and_current_contracts_keep_scope_closed() -> None:
    tests = _read(STAGE2 / SAFE_FILES[3])
    assert tests["focused_closure"]["passed"] == 57
    assert tests["focused_closure"]["failed"] == 0
    assert tests["full_suite_terminal_before_bundle_rebuild"] == {
        "terminal": True,
        "timeout": False,
        "passed": 2972,
        "failed": 7,
        "errors": 11,
        "skipped": 5,
        "warnings": 6,
        "duration_seconds": 927.98,
    }
    assert tests["post_rebuild_targeted"]["passed"] == 12
    assert tests["post_rebuild_targeted"]["failed"] == 0
    assert tests["post_terminal_triage"]["doc33_regressions"] == 0
    assert tests["post_terminal_triage"]["new_unexplained_failures"] == 0
    assert tests["post_terminal_triage"]["historical_hashes_rewritten"] == 0

    decision = _read(STAGE2 / SAFE_FILES[4])
    expected = {
        "DOC33_PROGRAM": "COMPLETED",
        "GATE2_MACHINE_PROJECTION_AUTHORITY": "REFINED",
        "SUPPORTED_FORMATS": "PDF_HTML_CSV_XLSX",
        "CROSS_FORMAT_CONFORMANCE": "PASS",
        "ONE_PUBLIC_CONTRACT": "CONFIRMED",
        "ONE_PUBLIC_READER": "CONFIRMED",
        "DOWNSTREAM_FORMAT_OPACITY": "CONFIRMED",
        "EVIDENCE_BOUNDARY": "CONFIRMED",
        "LLM_PROJECTION_BOUNDARY": "CONFIRMED",
        "CROSS_FORMAT_EQUIVALENCE": "CONFIRMED",
        "DURABLE_ROUNDTRIP": "CONFIRMED",
        "GATE2_UNIFIED_MACHINE_PROJECTION": "CONFIRMED",
        "WAVE2_CUTOVER": "NOT_PERFORMED",
        "PRIMARY_PRODUCT_CUTOVER": "NOT_PERFORMED",
        "GATE3": "NOT_STARTED",
    }
    assert {key: decision[key] for key in expected} == expected
    assert decision["separate_wave2_cutover_goal_allowed"] is True
    assert decision["separate_wave2_cutover_goal_authorized_by_doc33"] is False

    report_text = REPORT.read_text(encoding="utf-8")
    for number in range(1, 12):
        assert f"## {number}." in report_text
    for key, value in expected.items():
        assert f"{key} = {value}" in report_text

    exit_contract = STAGE2 / "contracts" / "BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md"
    current_contracts = (
        exit_contract,
        STAGE2 / "contracts" / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_CANONICAL_READER.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_PIPELINE_GATES.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md",
    )
    joined = "\n".join(path.read_text(encoding="utf-8") for path in current_contracts)
    assert "CanonicalNormalizerFactory.create" in joined
    assert "CanonicalArtifactStoreFactory.create" in joined
    assert "CanonicalReaderFactory.create" in joined
    assert "PDF, HTML, CSV and XLSX" in joined
    assert "Gate 3" in joined
    assert "format-neutral" in joined
