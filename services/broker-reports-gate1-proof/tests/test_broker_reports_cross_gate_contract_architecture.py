"""Executable cross-gate architecture invariants through G5.50."""

from __future__ import annotations

import ast
from pathlib import Path

from broker_reports_gate1.architecture_policy import (
    COMPATIBILITY_ONLY_CROSS_DOMAIN_MODULES,
    DOMAIN_BOUNDARY_SEQUENCE,
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE_OWNERSHIP,
    LLM_BOUNDARY_CLASSES,
    PROVIDER_CALL_SITE_CLASSIFICATIONS,
)
from broker_reports_gate1.gate5_human_gap_closure import _KNOWN_FACT_KEYS
from broker_reports_gate1.gate3_metadata_source_facts import _metadata_facts


PACKAGE = Path(__file__).parents[1] / "broker_reports_gate1"
REPOSITORY_ROOT = PACKAGE.parents[2]
CONTRACTS = REPOSITORY_ROOT / "docs" / "stage2" / "contracts"


def _source(module_name: str) -> str:
    return (PACKAGE / f"{module_name}.py").read_text(encoding="utf-8")


def test_current_pipeline_has_one_explicit_owner_per_semantic_layer() -> None:
    assert GATE_OWNERSHIP == {
        "gate1": "authenticated_source_intake_and_custody",
        "gate2": "canonical_source_preservation",
        "adaptive_context": "structure_preserving_context_packaging",
        "gate3": "source_financial_labeling_and_role_binding",
        "gate4": "normalized_source_facts_and_case_query",
        "gate5": "deterministic_tax_methodology_and_calculation",
        "human_adapter": "typed_factual_human_evidence",
        "external_reference_facts": "typed_authoritative_external_evidence",
        "methodology_adapter": "reviewed_methodology_proposals_only",
        "declaration_semantics": "target_independent_declaration_meaning",
        "release": "evidence_completeness_and_release_decision",
        "projection": "representation_only",
    }
    assert DOMAIN_BOUNDARY_SEQUENCE == (
        "gate1",
        "gate2",
        "adaptive_context",
        "gate3",
        "gate4",
        "gate5",
        "declaration_semantics",
        "release",
        "projection",
    )


def test_gate3_metadata_source_adapter_does_not_cross_into_gate4_or_gate5() -> None:
    source = _source("gate3_metadata_source_facts")
    assert "ArtifactResolver(self._store)" in source
    assert "CanonicalReaderFactory(" in source
    for forbidden in (
        "from .gate4_",
        "from .gate5_",
        "gate3_context_manifest",
        ".extract(",
        ".label_gate3_once(",
        "income_source",
        "taxpayer_residency",
    ):
        assert forbidden not in source


def test_organization_inn_is_not_promoted_to_person_tax_identity() -> None:
    facts = _metadata_facts(
        artifact={
            "nodes": [
                {
                    "node_id": "node_header",
                    "node_type": "TEXT",
                    "source_refs": ["source_header"],
                    "content": {
                        "text": "ОГРН / ИНН: 1234567890 (INN) / 1234567890123 (OGRN)"
                    },
                }
            ]
        },
        document_id="brdoc_test",
        canonical_version_id="brcanon_test",
    )

    assert facts == []


def test_gate5_evidence_intake_composes_contracts_without_reinterpreting_them() -> None:
    source = _source("gate5_evidence_intake")
    assert "Gate3MetadataSourceFactRuntimeFactory(" in source
    assert "Gate4FinancialCaseRuntimeFactory(" in source
    for forbidden in (
        "CanonicalReaderFactory(",
        "ArtifactResolver(",
        "SqliteArtifactStoreAdapter(",
        ".extract(",
        "candidate_relation_set",
        "selected_relation_ids",
    ):
        assert forbidden not in source


def test_declaration_scope_resolution_and_activation_have_one_module_owner() -> None:
    assert not (PACKAGE / "gate5_declaration_scope_activation.py").exists()
    scope_source = _source("gate5_declaration_scope_resolution")
    assert "class Gate5DeclarationScopeResolutionRuntimeFactory" in scope_source
    assert "class Gate5DeclarationScopeActivationRuntimeFactory" in scope_source
    assert "from .gate5_declaration_scope_resolution import (" in _source(
        "gate5_declaration_preparation"
    )
    assert "from .gate5_declaration_scope_resolution import (" in _source(
        "gate5_human_gap_closure"
    )


def test_user_case_facts_cannot_be_tax_conclusions() -> None:
    assert _KNOWN_FACT_KEYS == {
        "taxpayer_identity_confirmed",
        "filing_instance_identity",
        "signer_and_representation",
        "budget_disposition",
        "residency_evidence",
    }
    forbidden_conclusions = {
        "income_source_classification",
        "taxpayer_residency",
        "taxable_income",
        "deduction_eligibility",
        "expense_allowability",
        "tax_amount",
    }
    assert _KNOWN_FACT_KEYS.isdisjoint(forbidden_conclusions)


def test_all_structured_model_call_sites_are_explicit_and_gate5_is_bounded() -> None:
    markers = (".extract(", ".label_gate3_once(", ".propose_gate3_metadata_once(")
    actual = {
        path.stem
        for path in PACKAGE.glob("gate*.py")
        if any(marker in path.read_text(encoding="utf-8") for marker in markers)
    }
    assert actual == {
        "gate2_domain_runtime",
        "gate2_financial_context_checksum",
        "gate2_financial_evidence_production_runtime",
        "gate2_financial_evidence_shadow_qualification",
        "gate2_financial_evidence_successor",
        "gate2_financial_semantic_v5_qualification_run",
        "gate2_financial_semantic_v6_model_diagnostic",
        "gate2_financial_semantic_v6_qualification_run",
        "gate2_source_fact_runtime",
        "gate3_bounded_labeling",
        "gate3_llm_metadata_adapter",
        "gate3_role_labeling",
        "gate5_single_input_human_loop",
    }
    assert not {name for name in actual if name.startswith("gate4_")}
    assert {name for name in actual if name.startswith("gate5_")} == {
        "gate5_single_input_human_loop"
    }
    assert set(PROVIDER_CALL_SITE_CLASSIFICATIONS) == actual
    for module_name, (
        classification,
        uncertainty,
        contract,
    ) in PROVIDER_CALL_SITE_CLASSIFICATIONS.items():
        assert classification in LLM_BOUNDARY_CLASSES, module_name
        assert uncertainty, module_name
        assert contract, module_name
        assert not module_name.startswith("gate4_")
        if module_name.startswith("gate5_"):
            assert classification == "HUMAN_ADAPTER"
    demand_source = _source("gate5_evidence_demand")
    assert "canonical_documents" not in demand_source
    assert "CanonicalReaderFactory" not in demand_source
    assert "semantic_adapter" not in demand_source
    assert not (PACKAGE / "gate5_real_semantic_recovery.py").exists()
    assert "Gate4CanonicalRecoveryProjector" not in _source(
        "gate4_financial_case_materialization"
    )


def test_gate3_has_no_reverse_dependency_on_tax_or_projection_domains() -> None:
    violations = []
    for path in sorted(PACKAGE.glob("gate3_*.py")):
        for imported in _local_imports(path.stem):
            if imported.startswith("gate4_") or imported.startswith("gate5_"):
                violations.append(f"{path.stem}->{imported}")
    assert violations == []


def test_gate5_source_semantic_dependencies_use_only_published_ports() -> None:
    forbidden_exact = {
        "canonical_store",
        "canonical_artifact",
        "gate2_handoff",
        "gate2_model_clients",
        "gate2_provider_adapters",
        "gate3_projection",
        "gate3_structural_chunking",
        "gate3_bounded_labeling",
        "gate3_chunk_batch_labeling",
        "gate3_role_labeling",
        "gate3_financial_annotations_persistence",
    }
    violations: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.glob("gate5_*.py")):
        bad = sorted(
            imported
            for imported in _local_imports(path.stem)
            if imported in forbidden_exact or imported.startswith("pdf_")
        )
        if bad:
            violations[path.stem] = bad
    assert set(violations) == set(COMPATIBILITY_ONLY_CROSS_DOMAIN_MODULES)
    assert violations == {
        "gate5_end_to_end_full_target_xml": [
            "canonical_store",
            "gate2_handoff",
            "gate3_chunk_batch_labeling",
            "gate3_financial_annotations_persistence",
        ]
    }
    demand_source = _source("gate5_evidence_demand")
    assert "from .gate3_evidence_demand_port import" in demand_source
    assert "Gate3EvidenceDemandPortFactory.create" in FACTORY_REQUIRED
    assert "Gate 5 Canonical/source reads" in FORBIDDEN


def test_projection_modules_are_representation_only_import_boundaries() -> None:
    allowed = {
        "gate5_declaration_projection": {"declaration_semantics"},
        "gate5_full_target_xml_projection": {"gate5_declaration_semantic_input"},
    }
    for module_name, allowed_imports in allowed.items():
        assert _local_imports(module_name) == allowed_imports, module_name
        source = _source(module_name)
        for forbidden in (
            "Gate5IncomeGroupTaxBaseRuntimeFactory",
            "Gate5TrustedMethodology",
            "Gate4FinancialCase",
            "CanonicalReaderFactory",
            "Gate5EvidenceDemand",
        ):
            assert forbidden not in source, f"{module_name}:{forbidden}"


def test_high_risk_boundaries_have_local_road_signs() -> None:
    assert "Gate 3 source meaning only" in _source("gate3_bounded_labeling")
    assert "Gate 5 owns WHAT is required" in _source("gate5_evidence_demand")
    assert "Representation-only projection" in _source("gate5_declaration_projection")
    assert "Representation-only XML projection" in _source(
        "gate5_full_target_xml_projection"
    )
    assert "compatibility-only full-pipeline proof orchestrator" in _source(
        "gate5_end_to_end_full_target_xml"
    )


def test_public_surface_exposes_the_one_evidence_demand_route() -> None:
    public_surface = _source("__init__")
    assert "Gate5EvidenceDemandRuntimeFactory" in public_surface
    assert "Gate3EvidenceDemandPortFactory" in public_surface
    assert not (PACKAGE / "gate3_evidence_demand_adapter.py").exists()
    assert not (PACKAGE / "gate5_real_semantic_recovery.py").exists()


def test_cold_agent_navigation_is_unambiguous_in_current_authority() -> None:
    authority = (CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md").read_text(
        encoding="utf-8"
    )
    required = {
        "CURRENT_PIPELINE_AUTHORITY = ONE",
        "Gate5EvidenceDemandRuntimeFactory.create",
        "Gate3EvidenceDemandPortFactory.create",
        "Never read Canonical in Gate 5.",
        "Human Adapter factual evidence",
        "Never ask an LLM for the tax conclusion.",
        "Never calculate in Projection.",
        "SOURCE_MEANING_ADMISSION = NAMED_DOWNSTREAM_CONSUMER + REQUIRED_FACTUAL_DISTINCTION",
        "TAX_CRITICAL_SOURCE_MEANING_ADMISSION = SOURCE_MEANING_ADMISSION + VERSIONED_METHODOLOGY_INPUT",
        "NO_NAMED_CONSUMER = RETAIN_AS_UNMAPPED_SOURCE_CONTENT",
        "METHODOLOGY_INPUT_CONTRACT_GAP_PROVEN",
        "G5.x reports remain evidence",
        "WHICH DOMAIN OWNS THIS QUESTION?",
        "WHAT CONTRACT SHOULD CROSS THE BOUNDARY?",
    }
    assert sorted(item for item in required if item not in authority) == []


def test_rejected_recovery_docs_cannot_look_like_current_authority() -> None:
    for name in (
        "BROKER_REPORTS_GATE5_METHODOLOGY_DRIVEN_EVIDENCE_DEMAND.v1.md",
        "BROKER_REPORTS_GATE5_REAL_CANONICAL_SEMANTIC_RECOVERY.v1.md",
    ):
        source = (CONTRACTS / name).read_text(encoding="utf-8")
        assert "HISTORICAL_ONLY — NOT CURRENT ARCHITECTURE AUTHORITY" in source
        assert "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md" in source
    compatibility = (
        CONTRACTS / "BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md"
    ).read_text(encoding="utf-8")
    assert "Status: `COMPATIBILITY_ONLY`" in compatibility
    assert "BROKER_REPORTS_PIPELINE_GATES.v1.md" in compatibility


def test_demand_port_binds_contracts_without_reading_or_executing_source() -> None:
    source = _source("gate3_evidence_demand_port")
    assert "Gate3FinancialLabelDictionaryFactory.create()" in source
    assert "Gate3FinancialRolePackFactory.create()" in source
    for forbidden in (
        "CanonicalReaderFactory",
        "ArtifactResolver",
        ".extract(",
        ".label_gate3_once(",
        "Gate4FinancialCase",
        "from .gate5_",
    ):
        assert forbidden not in source


def test_no_relation_contract_enters_gate4_or_gate5() -> None:
    assert not (PACKAGE / "gate5_related_securities_events.py").exists()
    forbidden = (
        "candidate_relation_set",
        "selected_relation_ids",
        "transaction_graph",
        "gate3_context_manifest",
    )
    for path in [*PACKAGE.glob("gate4_*.py"), *PACKAGE.glob("gate5_*.py")]:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name}:{token}"
    assert "gate3_context_manifest_enabled: bool = False" in _source(
        "gate2_domain_runtime"
    )


def test_projection_decimal_use_is_representation_validation_only() -> None:
    allowed_decimal_functions = {
        "gate5_declaration_projection": {"_validated_input"},
        "gate5_full_target_xml_projection": {"_transformed"},
    }
    for module_name, expected_functions in allowed_decimal_functions.items():
        tree = ast.parse(_source(module_name))
        actual_functions = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "Decimal"
                for child in ast.walk(node)
            ):
                actual_functions.add(node.name)
        assert actual_functions == expected_functions
        source = _source(module_name)
        for forbidden in (
            "from .gate4_",
            "from .canonical_",
            "ArtifactResolver(",
            ".extract(",
            ".label_gate3_once(",
        ):
            assert forbidden not in source


def _local_imports(module_name: str) -> set[str]:
    tree = ast.parse(_source(module_name))
    return {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is not None
    }
