"""G5.62 sterile Canonical metadata source-truth requalification guards."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "requalify_g562_canonical_metadata_oracle.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g562_requalification", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G562 = _load_script()


def _minimal_inputs():
    adjudication_cases = [
        {"alias": alias, "canonical_artifact_id": f"artifact-{alias}", "facts": []}
        for alias in G562.EXPECTED_ALIASES
    ]
    frozen_cases = [
        {"alias": alias, "canonical_artifact_id": f"artifact-{alias}"}
        for alias in G562.EXPECTED_ALIASES
    ]
    return (
        {
            "schema_version": (
                "broker_reports_g562_visual_source_truth_adjudication_private_v1"
            ),
            "contract_version": G562.GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
            "provider_calls": 0,
            "oracle_source": "visual_source_plus_canonical_provenance",
            "old_oracle_authority": False,
            "llm_output_authority": False,
            "cases": adjudication_cases,
        },
        {"frozen_before_code": True, "cases": frozen_cases},
        {"goal": "G5.61"},
    )


def test_matcher_requires_page_provenance_and_returns_exact_field_path():
    artifact = {
        "nodes": [
            {
                "node_id": "wrong-page",
                "node_type": "TEXT",
                "order": 1,
                "source_refs": ["page-2"],
                "content": {"text": "Client value"},
            },
            {
                "node_id": "right-page",
                "node_type": "TEXT",
                "order": 2,
                "source_refs": ["page-1"],
                "content": {"text": "Heading\nClient value\nFooter"},
            },
        ]
    }
    provenance = {
        "page-1": {"source_locator": {"page": 1}},
        "page-2": {"source_locator": {"page": 2}},
    }

    matches = G562.find_canonical_matches(
        artifact=artifact,
        provenance=provenance,
        page=1,
        node_type="TEXT",
        literal="Client value",
    )

    assert matches == [
        {
            "node_id": "right-page",
            "field_path": "content.text.lines[1]",
            "source_refs": ["page-1"],
            "node_order": 2,
        }
    ]


def test_old_oracle_comparison_is_case_scoped():
    old_result = {
        "cases": [
            {
                "alias": "case-a",
                "oracle_facts": [{"fact_type": "REPORTING_PERIOD", "value": "same"}],
            }
        ]
    }
    new_facts = [
        {"case_alias": "case-b", "fact_type": "REPORTING_PERIOD", "value": "same"}
    ]

    assert G562.classify_old_oracle(
        old_result=old_result,
        new_facts=new_facts,
    ) == {
        "old_oracle_facts": 1,
        "correct": 0,
        "false_binding": 1,
        "missing_from_oracle": 1,
    }
    assert {
        item["classification"]
        for item in G562.classify_old_oracle_entries(
            old_result=old_result,
            new_facts=new_facts,
        )
    } == {"FALSE_BINDING", "MISSING_FROM_ORACLE"}


def test_frozen_contract_rejects_provider_calls_and_new_fact_types():
    adjudication, frozen, old_result = _minimal_inputs()
    adjudication["provider_calls"] = 1
    with pytest.raises(G562.G562RequalificationError, match="g562_provider_calls_forbidden"):
        G562._validate_inputs(
            adjudication=adjudication,
            frozen=frozen,
            old_result=old_result,
        )

    adjudication, frozen, old_result = _minimal_inputs()
    adjudication["cases"][0]["facts"] = [
        {
            "fact_id": "outside-contract",
            "fact_type": "TAX_RESIDENCY",
            "canonical_node_type": "TEXT",
            "source_page": 1,
            "source_visible_literal": "x",
            "canonical_literal": "x",
            "structural_representation": "x",
        }
    ]
    with pytest.raises(G562.G562RequalificationError, match="g562_fact_type_outside_contract"):
        G562._validate_inputs(
            adjudication=adjudication,
            frozen=frozen,
            old_result=old_result,
        )


def test_script_is_offline_and_uses_canonical_factories():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.startswith("broker_reports_gate1.gate2_") for name in imports)
    assert "broker_reports_gate1.gate3_llm_metadata_adapter" not in imports
    assert "ArtifactResolver(store).catalog_case(context)" in source
    assert "CanonicalReaderFactory(store=store, read_enabled=True)" in source
    assert '"provider_calls": 0' in source
