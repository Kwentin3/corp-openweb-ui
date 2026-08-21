from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
PACKAGE = SERVICE_ROOT / "broker_reports_gate1"
PRODUCT_ACTIONS = SERVICE_ROOT / "openwebui_actions"
SCRIPTS = SERVICE_ROOT / "scripts"
AUTHORITY = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
)
G572_SCRIPT = SCRIPTS / "live_g572_visual_markdown_microstand.py"


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
    assert "METADATA_REGION_SELECTION_GENERALIZATION_GAP_LOCALIZED" in authority


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
    assert G572_SCRIPT.exists()
    assert "PROOF/RESEARCH ONLY" in AUTHORITY.read_text(encoding="utf-8")


def test_visual_markdown_contract_is_semantically_blind() -> None:
    spec = importlib.util.spec_from_file_location(
        "g572_consolidation_guard", G572_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    visible = json.dumps(module.transcription_model_view(), ensure_ascii=False).lower()
    forbidden_roles = {
        "account_identifier",
        "account_contract_identifier",
        "party_name",
        "statement_period",
        "broker_legal_name",
        "taxpayer_tax_identifier",
    }

    assert forbidden_roles.isdisjoint(visible)
    assert set(module.transcription_response_schema()["properties"]) == {
        "schema_version",
        "markdown",
    }
    assert "do not classify the content" in module.TRANSCRIPTION_INSTRUCTION.lower()
    assert "rename any label" in module.TRANSCRIPTION_INSTRUCTION.lower()


def test_existing_region_owner_is_table_only_not_a_hidden_metadata_selector() -> None:
    table_intake = _source(PACKAGE / "pdf_table_intake_runtime.py")
    locator = _source(PACKAGE / "pdf_table_locator.py")
    authority = AUTHORITY.read_text(encoding="utf-8")

    assert "PDF_TABLE_LOCATOR_PROMPT" in table_intake
    assert "Do not treat prose" in locator
    assert "Do not transcribe text" in locator
    assert "model_values_used_as_source_literals" in table_intake
    assert "table-only" in authority
    assert "broker-neutral automatic metadata-region selector exists yet" in authority
    assert not (PACKAGE / "metadata_region_selector.py").exists()


def test_cold_agent_navigation_answers_are_unambiguous() -> None:
    authority = AUTHORITY.read_text(encoding="utf-8")

    assert (
        "Canonical -> exact qualified mapping -> Source Observation/runtime record "
        "-> Gate 4 Fact v2 adapter"
        in authority
    )
    assert "Current Gate 3 is not executed" in authority
    assert (
        "visual region -> existing VLM -> faithful Markdown -> metadata adapter"
        in authority
    )
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
