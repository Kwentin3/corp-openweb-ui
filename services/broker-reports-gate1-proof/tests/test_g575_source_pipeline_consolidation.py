from __future__ import annotations

import ast
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
PACKAGE = SERVICE_ROOT / "broker_reports_gate1"
PRODUCT_ACTIONS = SERVICE_ROOT / "openwebui_actions"
AUTHORITY = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
)


def test_one_financial_runtime_path_and_one_inactive_metadata_candidate() -> None:
    authority = AUTHORITY.read_text(encoding="utf-8")

    assert "ORDINARY SECURITY TRADES — ACTIVE PRODUCT/NORMATIVE" in authority
    assert "OrdinaryTradeProductionRuntimeFactory.create" in authority
    assert "OrdinaryTradeQualifiedMappingAuthorityFactory.create" in authority
    assert "Gate3ChunkBatchLabelingFactory.create" in authority
    assert "Gate4FinancialCaseRuntimeFactory.create" in authority
    assert "HISTORICAL GATE 3 ROUTE — DEPLOYMENT ROLLBACK ONLY" in authority
    assert "VISUAL METADATA — SINGLE SUPPORTING CANDIDATE, NOT PRODUCT-ACTIVE" in (
        authority
    )
    assert "faithful neutral Markdown" in authority
    assert "Gate3LlmMetadataAdapterFactory.create" in authority


def test_metadata_is_supporting_and_gate4_has_no_metadata_classifier_dependency() -> (
    None
):
    metadata_adapter = _source(PACKAGE / "gate3_llm_metadata_adapter.py")
    metadata_publication = _source(PACKAGE / "gate3_metadata_source_facts.py")
    gate4_materialization = _source(PACKAGE / "gate4_financial_case_materialization.py")
    gate4_cache = _source(PACKAGE / "gate4_financial_case_cache.py")
    evidence_intake = _source(PACKAGE / "gate5_evidence_intake.py")

    for source in (metadata_adapter, metadata_publication):
        assert "from .gate4_" not in source
        assert "from .gate5_" not in source
        assert "tax calculation" not in source.lower()
    for source in (gate4_materialization, gate4_cache):
        assert "gate3_llm_metadata_adapter" not in source
        assert "gate3_metadata_source_facts" not in source
        assert "ACCOUNT_IDENTIFIER" not in source
        assert "STATEMENT_PERIOD" not in source
    assert '"metadata_facts"' in evidence_intake
    assert '"financial_fact_counts"' in evidence_intake
    assert "Gate3MetadataSourceFactRuntimeFactory(" in evidence_intake
    assert "Gate4FinancialCaseRuntimeFactory(" in evidence_intake


def test_normative_runtime_cannot_import_g561_g573_research_harnesses() -> None:
    violations: list[str] = []
    forbidden_prefixes = (
        "live_g56",
        "live_g57",
        "qualify_g56",
        "prepare_g569",
        "requalify_g562",
    )
    for path in sorted((*PACKAGE.glob("*.py"), *PRODUCT_ACTIONS.glob("*.py"))):
        for imported in _imports(path):
            leaf = imported.rsplit(".", 1)[-1]
            if imported.startswith("scripts") or leaf.startswith(forbidden_prefixes):
                violations.append(f"{path.name}:{imported}")
        source = _source(path)
        for prefix in forbidden_prefixes:
            if prefix in source:
                violations.append(f"{path.name}:literal:{prefix}")

    assert violations == []
    assert "PROOF/RESEARCH ONLY" in AUTHORITY.read_text(encoding="utf-8")


def test_pdf_understanding_has_one_fail_closed_document_ai_owner() -> None:
    boundary = _source(PACKAGE / "pdf_document_ai.py")
    pipe = _source(PRODUCT_ACTIONS / "broker_reports_gate1_pipe.py")
    normalizer = _source(PACKAGE / "normalizer.py")

    assert "class PdfDocumentExtractor" in boundary
    assert "class PdfDocumentExtraction" in boundary
    assert "class PdfDocumentExtractorFactory" in boundary
    assert "PDF_DOCUMENT_AI_NOT_CONFIGURED" in boundary
    assert "PdfDocumentExtractorFactory.create()" in normalizer
    assert "PdfDocumentExtractorFactory" not in pipe
    assert not (PACKAGE / "metadata_region_selector.py").exists()


def test_cold_agent_navigation_answers_are_unambiguous() -> None:
    authority = AUTHORITY.read_text(encoding="utf-8")

    assert (
        "Canonical -> exact qualified mapping -> Source Observation/runtime record "
        "-> Gate 4 Fact v2 adapter"
        in authority
    )
    assert "Current Gate 3 is not executed" in authority
    assert "Metadata account mismatch: `NO`; retain financial facts" in authority
    assert "Do not\ncreate a parallel reader" in authority


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(_source(path), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result
