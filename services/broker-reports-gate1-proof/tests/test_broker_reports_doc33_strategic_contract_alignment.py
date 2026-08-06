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
    / "BROKER_REPORTS_DOC33_STRATEGIC_CONTRACT_ALIGNMENT.report.md"
)
EXIT_CONTRACT = STAGE2 / "contracts" / "BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md"
CONFORMANCE_V1 = STAGE2 / "BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.safe.json"
DECISION_V1 = STAGE2 / "BROKER_REPORTS_DOC33_DECISION.safe.json"
CONFORMANCE_V2 = STAGE2 / "BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.v2.safe.json"
DECISION_V2 = STAGE2 / "BROKER_REPORTS_DOC33_STRATEGIC_DECISION.v2.safe.json"

IMMUTABLE_V1_FILE_HASHES = {
    "BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.safe.json": (
        "057fec8e735c6c085d816503168981e4ae56f59f2eed11322260b05ed633eb69"
    ),
    "BROKER_REPORTS_DOC33_DECISION.safe.json": (
        "5a6bb8d22e89c4d9488d3f3ab91240a00c26598071dacc852d479bf9f8ebebc4"
    ),
    "BROKER_REPORTS_DOC33_COHORT_READER_PROOF.safe.json": (
        "f620be96368adfa8db2f3665c3d5e3018150522c3d953cf15057213c9a1cc85b"
    ),
    "BROKER_REPORTS_DOC33_SEMANTIC_EQUIVALENCE.safe.json": (
        "5bfb60500cea3f99296c86bf78835e42cc1bdd8932d4648927fc1fde1030dcc3"
    ),
    "BROKER_REPORTS_DOC33_TEST_RESULTS.safe.json": (
        "e2179be2db3662be1fc8d4e0c892b8d7ec7867dc44b2bc0aba8c73700322d8fe"
    ),
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_doc33_v1_evidence_remains_immutable() -> None:
    for name, expected in IMMUTABLE_V1_FILE_HASHES.items():
        assert _file_sha(STAGE2 / name) == expected, name
    assert (
        _file_sha(
            REPO
            / "docs"
            / "reports"
            / "2026-08-06"
            / "BROKER_REPORTS_DOC33_UNIFIED_GATE2_MACHINE_PROJECTION.report.md"
        )
        == "80945052f1c774a4a644cb8a50db21cbbc4ea1cc335cffb6fa972b33b71831d3"
    )


def test_doc33_v2_conformance_uses_the_exact_strategic_vocabulary() -> None:
    value = _read(CONFORMANCE_V2)
    assert value["integrity_sha256"] == _json_sha(value)
    assert value["status_values"] == [
        "conformant",
        "divergent",
        "absent",
        "unsupported",
    ]
    assert value["supported_formats"] == ["pdf", "html", "csv", "xlsx"]
    assert value["mandatory_elements_all_conformant"] is True
    assert value["unsupported_mandatory_elements"] == []
    assert value["unexplained_dropped_content"] == 0
    assert value["previous_v1_file_sha256"] == _file_sha(CONFORMANCE_V1)
    allowed = set(value["status_values"])
    for row in value["matrix"]:
        statuses = {row[name] for name in value["supported_formats"]}
        assert statuses <= allowed
        if row["requirement"] == "mandatory":
            assert statuses == {"conformant"}


def test_doc33_v2_decision_is_exact_hash_bound_and_private_free() -> None:
    value = _read(DECISION_V2)
    assert value["integrity_sha256"] == _json_sha(value)
    expected = {
        "DOC33_PROGRAM": "COMPLETED",
        "GATE2_CONTRACT_AUTHORITY": "REFINED",
        "SUPPORTED_FORMATS": "PDF_HTML_CSV_XLSX",
        "CROSS_FORMAT_CONFORMANCE": "PASS",
        "ONE_PUBLIC_SCHEMA": "CONFIRMED",
        "ONE_PUBLIC_READER": "CONFIRMED",
        "DOWNSTREAM_FORMAT_OPACITY": "CONFIRMED",
        "EVIDENCE_BOUNDARY": "CONFIRMED",
        "LLM_PROJECTION_BOUNDARY": "CONFIRMED",
        "COMPLETENESS_FAIL_CLOSED": "CONFIRMED",
        "CROSS_FORMAT_EQUIVALENCE": "CONFIRMED_WITH_LIMITS",
        "DURABLE_ROUNDTRIP": "CONFIRMED",
        "GATE2_UNIFIED_MACHINE_PROJECTION": "CONFIRMED",
        "WAVE2_CUTOVER": "NOT_PERFORMED",
        "PRIMARY_PRODUCT_CUTOVER": "NOT_PERFORMED",
        "GATE3": "NOT_STARTED",
    }
    assert {key: value[key] for key in expected} == expected
    assert all(value["confirmation_conditions"].values())
    assert value["documents_read_through_one_contract"] == 16
    assert value["downstream_format_branches"] == 0
    assert value["mandatory_format_specific_fields"] == 0
    assert value["private_evidence_reads_by_projection"] == 0
    assert value["historical_artifacts_rewritten"] == 0
    assert value["evidence_links"]["previous_decision_file_sha256"] == _file_sha(
        DECISION_V1
    )
    assert (
        value["evidence_links"]["conformance_v2_integrity_sha256"]
        == _read(CONFORMANCE_V2)["integrity_sha256"]
    )
    assert value["evidence_links"]["gate2_exit_contract_file_sha256"] == _file_sha(
        EXIT_CONTRACT
    )
    forbidden = (
        '"document_id"',
        '"user_id"',
        '"tenant_id"',
        '"source_sha256"',
        '"canonical_version_id"',
        '"normalization_run_id"',
        '"openwebui_file_id"',
        '"private_path"',
        "private.json",
        "/opt/",
        "\\local\\stage2\\",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (CONFORMANCE_V2, DECISION_V2)
    )
    assert all(marker.lower() not in combined for marker in forbidden)


def test_doc33_report_has_fourteen_disclosures_and_one_current_exit_contract() -> None:
    decision = _read(DECISION_V2)
    report = REPORT.read_text(encoding="utf-8")
    for number in range(1, 15):
        assert f"## {number}." in report
    for key in (
        "DOC33_PROGRAM",
        "GATE2_CONTRACT_AUTHORITY",
        "SUPPORTED_FORMATS",
        "CROSS_FORMAT_CONFORMANCE",
        "ONE_PUBLIC_SCHEMA",
        "ONE_PUBLIC_READER",
        "DOWNSTREAM_FORMAT_OPACITY",
        "EVIDENCE_BOUNDARY",
        "LLM_PROJECTION_BOUNDARY",
        "COMPLETENESS_FAIL_CLOSED",
        "CROSS_FORMAT_EQUIVALENCE",
        "DURABLE_ROUNDTRIP",
        "GATE2_UNIFIED_MACHINE_PROJECTION",
        "WAVE2_CUTOVER",
        "PRIMARY_PRODUCT_CUTOVER",
        "GATE3",
    ):
        assert f"{key} = {decision[key]}" in report

    contract = EXIT_CONTRACT.read_text(encoding="utf-8")
    assert "Status: `CURRENT`" in contract
    assert "CanonicalArtifactV1 / schema_version = canonical_artifact_v1" in contract
    assert "CanonicalReaderFactory.create" in contract
    assert all(
        f"`{status}`" in contract
        for status in ("conformant", "divergent", "absent", "unsupported")
    )
    assert "requires an explicit schema-version decision" in contract
    assert "Readers reject unknown schema versions" in contract
