from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "docs" / "stage2" / "contracts"


def test_current_pipeline_contract_assigns_canonical_only_to_gate2():
    pipeline = (CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `CURRENT`" in pipeline
    assert "CanonicalArtifactV1 = OUTPUT OF GATE 2" in pipeline
    assert "Gate 3" in pipeline and "not created" in pipeline.lower()


def test_active_canonical_docs_have_no_gate1_output_claim():
    active = [
        CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md",
        CONTRACTS / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md",
        CONTRACTS / "BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md",
        CONTRACTS / "BROKER_REPORTS_CANONICAL_READER.v1.md",
        CONTRACTS / "BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md",
        CONTRACTS / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md",
    ]
    forbidden = re.compile(
        r"(?:CanonicalArtifact|Canonical Artifact).{0,100}Gate 1 output|"
        r"Gate 1 output.{0,100}(?:CanonicalArtifact|Canonical Artifact)",
        re.IGNORECASE | re.DOTALL,
    )
    for path in active:
        text = path.read_text(encoding="utf-8")
        assert "Status: `CURRENT`" in text
        assert forbidden.search(text) is None, path


def test_superseded_architecture_points_to_current_contract():
    architecture = (
        REPO_ROOT
        / "docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")
    assert "Status: `SUPERSEDED`" in architecture
    assert "BROKER_REPORTS_PIPELINE_GATES.v1.md" in architecture


def test_schema_and_factory_descriptions_are_gate2_current():
    schema = json.loads(
        (CONTRACTS / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "output of Broker Reports Gate 2" in schema["$comment"]
    artifact_source = (
        REPO_ROOT
        / "services/broker-reports-gate1-proof/broker_reports_gate1/canonical_artifact.py"
    ).read_text(encoding="utf-8")
    store_source = (
        REPO_ROOT
        / "services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py"
    ).read_text(encoding="utf-8")
    assert artifact_source.startswith(
        '"""Gate 2 non-financial CanonicalArtifactV1 construction authority.'
    )
    assert store_source.startswith(
        '"""Gate 2 canonical version, physical-layout and reader facade.'
    )
    assert "CanonicalNormalizerFactory.create" in artifact_source
    assert "CanonicalArtifactStoreFactory.create" in store_source
    assert "CanonicalReaderFactory" in store_source


def test_doc26_did_not_enable_product_read_or_create_gate3_route():
    pipe = (
        REPO_ROOT
        / "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py"
    ).read_text(encoding="utf-8")
    assert re.search(
        r"canonical_gate2_read_enabled:\s*bool\s*=\s*Field\(\s*default=False",
        pipe,
    )
    canonical_files = [
        REPO_ROOT
        / "services/broker-reports-gate1-proof/broker_reports_gate1/canonical_artifact.py",
        REPO_ROOT
        / "services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py",
    ]
    assert all(
        re.search(
            r"(?:from\s+\.gate3|import\s+gate3)",
            path.read_text(encoding="utf-8"),
        )
        is None
        for path in canonical_files
    )
