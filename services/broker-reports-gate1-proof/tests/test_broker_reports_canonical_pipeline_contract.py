from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "docs" / "stage2" / "contracts"
STAGE2 = REPO_ROOT / "docs" / "stage2"


def test_current_pipeline_contract_assigns_canonical_only_to_gate2():
    pipeline = (CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `CURRENT`" in pipeline
    assert "CanonicalArtifactV1 = OUTPUT OF GATE 2" in pipeline
    assert "Gate 3 Minimal Labeling v1" in pipeline
    assert "`CURRENT_ACTIVE_IN_NDFL`" in pipeline
    assert "current Gate 3 projection" in pipeline
    assert "`ACTIVE_IN_NDFL`" in pipeline
    assert "current Gate 3 financial-label dictionary" in pipeline
    assert "`G3.C5_ACTIVE`" in pipeline
    assert "current Gate 3 bounded labeling" in pipeline
    assert "current Gate 3 FinancialAnnotations persistence" in pipeline


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


def test_current_pipeline_scopes_gate3_route_without_gate2_importing_gate3():
    pipe = (
        REPO_ROOT
        / "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py"
    ).read_text(encoding="utf-8")
    assert re.search(
        r"canonical_gate2_read_enabled:\s*bool\s*=\s*Field\(\s*default=False",
        pipe,
    )
    assert re.search(
        r"ndfl_gate3_enabled:\s*bool\s*=\s*Field\(\s*default=False",
        pipe,
    )
    assert "NDFL_WORKSPACE_MODEL_STABLE_ID" in pipe
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


def test_gate3_context_recovery_documentation_guard():
    pipeline_path = CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
    handoff_path = CONTRACTS / "BROKER_REPORTS_GATE3_HANDOFF.v1.md"
    pipeline = pipeline_path.read_text(encoding="utf-8")
    handoff = handoff_path.read_text(encoding="utf-8")
    context_index = (STAGE2 / "CONTEXT_INDEX.md").read_text(encoding="utf-8")
    context_rules = (STAGE2 / "CONTEXT_USAGE_RULES.md").read_text(
        encoding="utf-8"
    )

    authority_markers = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in STAGE2.rglob("*.md")
        if "CURRENT_PIPELINE_AUTHORITY = ONE" in path.read_text(encoding="utf-8")
    ]
    assert authority_markers == [
        "docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md"
    ]

    required_pipeline = {
        "GATE3_STATUS = CLOSED",
        "GATE4_STATUS = G4.3 MULTI-DOCUMENT FINANCIAL CASE ASSEMBLY CLOSED",
        "financial semantic labeling",
        "validated immutable `CanonicalArtifactV1`",
        "immutable `FinancialAnnotationsV2` sidecar",
        "Gate4FinancialCaseFactV1",
        "Canonical version B != Annotations A",
    }
    assert all(marker in pipeline for marker in required_pipeline)

    required_handoff = {
        "Gate 3 status: `CLOSED`",
        "CanonicalReaderFactory.create",
        "FinancialAnnotationsV2",
        "creates structural chunks when needed",
        "document is labeled independently",
        "broker-reports-financial-labels@1.0.0",
        "broker-reports-ndfl",
        "broker_reports_gate1_pipe",
        "Workspace -> Skills -> Broker Reports Financial Labels",
        "Display names are UI text, not lookup or routing authority",
        "reimplement Gate 3 labeling",
        "G4.3 assembles all current Gate 3 V2 sidecars into one deterministic case projection",
    }
    assert all(marker in handoff for marker in required_handoff)

    route = context_index.index("## Брокерские отчеты / 3-НДФЛ")
    pipeline_link = context_index.index("Pipeline Gates v1 — sole current authority", route)
    handoff_link = context_index.index("Gate 3 short context handoff", route)
    upstream_link = context_index.index("Gate 2 Exit Contract v1", route)
    assert route < pipeline_link < handoff_link < upstream_link
    assert "Do not start from the superseded global gate architecture" in context_index
    assert "Broker Reports / NDFL / Gate 4 override" in context_rules

    superseded_or_historical = [
        STAGE2 / "blueprints" / "BROKER_REPORTS_GATE_ARCHITECTURE.md",
        STAGE2 / "blueprints" / "BROKER_REPORTS_3NDFL.blueprint.md",
        STAGE2 / "architecture" / "BROKER_REPORTS_DOMAIN_MAP.v1.md",
        STAGE2 / "BROKER_REPORTS_CURRENT_STATE.v1.md",
        STAGE2 / "BROKER_REPORTS_EVIDENCE_INDEX.v1.md",
        STAGE2 / "BROKER_REPORTS_DOCUMENT_PIPELINE_MAP.v1.md",
        CONTRACTS / "BROKER_REPORTS_CONTRACT_FLOW_MAPPING.v0.md",
        CONTRACTS / "BROKER_REPORTS_DATA_CONTRACT_FAMILY.v0.md",
        CONTRACTS / "BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md",
    ]
    for path in superseded_or_historical:
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:20])
        assert "BROKER_REPORTS_PIPELINE_GATES.v1.md" in head, path
        assert "SUPERSEDED" in head or "HISTORICAL" in head, path
