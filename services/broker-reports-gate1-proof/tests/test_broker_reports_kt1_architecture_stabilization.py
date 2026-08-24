from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
DOC_ROOT = REPO_ROOT / "docs" / "stage2"

DOMAIN_MAP = DOC_ROOT / "architecture" / "BROKER_REPORTS_DOMAIN_MAP.v1.md"
ROUTE_STATUS = DOC_ROOT / "architecture" / "BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md"
OWNER_CONTEXT = DOC_ROOT / "architecture" / "BROKER_REPORTS_OWNER_CONTEXT.v1.json"
OWNER_CONTEXT_GUIDE = DOC_ROOT / "architecture" / "BROKER_REPORTS_OWNER_CONTEXT.v1.md"
OWNER_MATRIX = DOC_ROOT / "contracts" / "BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md"
ARCHITECTURE_AUTHORITIES = (
    DOC_ROOT / "contracts" / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
)
CONVERGENCE_ADR = DOC_ROOT / "adr" / "BROKER_REPORTS_GATE2_SEMANTIC_CONVERGENCE.v1.md"
COMMENT_POLICY = DOC_ROOT / "agent" / "BROKER_REPORTS_CODE_COMMENT_POLICY.v1.md"

EXPECTED_OWNER_IDS = {
    "pdf_vlm_visual_execution",
    "semantic_visual_validation",
    "logical_table_materialization",
    "gate2_table_package",
    "current_source_fact_orchestration",
    "historical_source_fact_selection",
    "financial_type_authority",
    "semantic_choice_and_expansion",
    "canonical_financial_validator",
    "canonical_financial_materializer",
    "financial_evidence_replay",
    "artifact_store_and_resolver",
    "answer_context_selection",
    "gate3_context_manifest",
    "release_live_parity_verifier",
}

REQUIRED_OWNER_FIELDS = {
    "owner_id",
    "module",
    "symbols",
    "domain",
    "runtime_status",
    "input_contracts",
    "output_contracts",
    "owns",
    "does_not_own",
    "allowed_consumers",
    "forbidden_consumers",
    "historical_routes_nearby",
    "related_adr",
    "related_contract_tests",
    "change_requires",
}

ALLOWED_RUNTIME_STATUSES = {
    "ACTIVE_PRODUCT",
    "HISTORICAL_READ_ONLY",
    "PROOF_ONLY",
    "VERIFIED_LIVE",
}

ALLOWED_DOMAINS = {
    "Semantic visual table transcription",
    "Deterministic logical table materialization",
    "Gate 2 table package",
    "Source-fact extraction",
    "Historical and compatibility routes",
    "Financial semantic decision",
    "Canonical financial materialization",
    "Replay and comparators",
    "Artifact persistence",
    "AnswerContext",
    "Gate 3 context manifest",
    "Release and parity verification",
}

PRODUCTION_OWNER_FILES = (
    PACKAGE_ROOT / "semantic_visual_table_contracts.py",
    PACKAGE_ROOT / "semantic_visual_table_materialization.py",
    PACKAGE_ROOT / "gate2_table_packages.py",
    PACKAGE_ROOT / "gate2_domain_runtime.py",
    PACKAGE_ROOT / "gate2_source_fact_selection.py",
    PACKAGE_ROOT / "gate2_financial_evidence_materialization.py",
    PACKAGE_ROOT / "gate2_financial_semantic_v6_evidence.py",
    PACKAGE_ROOT / "answer_context_selection.py",
    SERVICE_ROOT / "scripts" / "live_verify_broker_reports_stage2_delivery.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _metadata() -> dict[str, Any]:
    return json.loads(_read(OWNER_CONTEXT))


def _owners() -> dict[str, dict[str, Any]]:
    owners = _metadata()["owners"]
    return {owner["owner_id"]: owner for owner in owners}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(_read(path), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _defined_symbols(path: Path) -> set[str]:
    tree = ast.parse(_read(path), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _route_markers() -> dict[str, str]:
    pattern = re.compile(r"<!-- route_id=([a-z0-9_]+);status=([A-Z_]+) -->")
    return dict(pattern.findall(_read(ROUTE_STATUS)))


def _changed_paths() -> list[tuple[str, str]]:
    merge_base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracked = subprocess.run(
        ["git", "diff", "--name-status", merge_base, "--"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    result: list[tuple[str, str]] = []
    for line in tracked:
        status, path = line.split("\t", maxsplit=1)
        result.append((status, path.replace("\\", "/")))
    result.extend(("A", path.replace("\\", "/")) for path in untracked)
    return result


def test_01_owner_metadata_exists_and_is_versioned() -> None:
    assert OWNER_CONTEXT.is_file()
    assert OWNER_CONTEXT_GUIDE.is_file()
    metadata = _metadata()
    assert metadata["schema_version"] == "broker_reports_owner_context_v1"
    assert metadata["owner_context_policy"] == "SIDECAR_OWNER_METADATA"


def test_02_all_key_owners_have_complete_metadata_entries() -> None:
    owners = _owners()
    assert set(owners) == EXPECTED_OWNER_IDS
    assert len(owners) == 15
    for owner_id, owner in owners.items():
        assert REQUIRED_OWNER_FIELDS <= owner.keys(), owner_id
        assert all(owner[field] for field in REQUIRED_OWNER_FIELDS), owner_id


def test_03_metadata_symbols_exist_in_maintained_code() -> None:
    for owner_id, owner in _owners().items():
        module_paths = [REPO_ROOT / owner["module"]]
        module_paths.extend(
            REPO_ROOT / path for path in owner.get("related_modules", [])
        )
        definitions: set[str] = set()
        for module_path in module_paths:
            assert module_path.is_file(), (owner_id, module_path)
            definitions.update(_defined_symbols(module_path))
        assert set(owner["symbols"]) <= definitions, owner_id


def test_04_metadata_domains_statuses_and_adr_references_are_valid() -> None:
    for owner_id, owner in _owners().items():
        assert owner["domain"] in ALLOWED_DOMAINS, owner_id
        assert owner["runtime_status"] in ALLOWED_RUNTIME_STATUSES, owner_id
        adr = REPO_ROOT / owner["related_adr"]
        assert adr == CONVERGENCE_ADR
        assert adr.is_file()
        for field in (
            "input_contracts",
            "output_contracts",
            "related_contract_tests",
        ):
            assert all((REPO_ROOT / path).is_file() for path in owner[field])


def test_05_sole_owner_matrix_is_consistent_with_metadata() -> None:
    matrix = _read(OWNER_MATRIX)
    required_matrix_markers = {
        "pdf_vlm_visual_execution": ("PdfDualVlmRuntimeFactory",),
        "semantic_visual_validation": ("SemanticVisualTableValidatorFactory",),
        "logical_table_materialization": ("SemanticVisualTableMaterializationFactory",),
        "gate2_table_package": ("Gate2TablePackageFactory",),
        "current_source_fact_orchestration": ("Gate2DomainSourceFactRuntimeFactory",),
        "historical_source_fact_selection": ("source_fact_selection_v3",),
        "financial_type_authority": ("Gate2FinancialSemanticContractFactory",),
        "semantic_choice_and_expansion": (
            "Gate2FinancialSemanticV6ChoiceContractFactory",
            "Gate2FinancialSemanticV6DecisionExpansionFactory",
        ),
        "canonical_financial_validator": (
            "Gate2FinancialEvidenceValidatedDecisionFactory",
        ),
        "canonical_financial_materializer": (
            "Gate2FinancialEvidenceMaterializerFactory",
        ),
        "financial_evidence_replay": (
            "Gate2FinancialSemanticV6DecisionEvidenceFactory",
            "replay_financial_semantic_v6_decision",
        ),
        "artifact_store_and_resolver": (
            "ArtifactStoreFactory",
            "ArtifactResolver",
        ),
        "answer_context_selection": ("AnswerContextSelectionFactory",),
        "gate3_context_manifest": ("Gate3ContextManifestFactory",),
        "release_live_parity_verifier": (
            "live_verify_broker_reports_stage2_delivery.py",
        ),
    }
    assert set(required_matrix_markers) == set(_owners())
    for owner_id, markers in required_matrix_markers.items():
        assert all(marker in matrix for marker in markers), owner_id


def test_06_historical_route_is_read_only() -> None:
    owner = _owners()["historical_source_fact_selection"]
    assert owner["runtime_status"] == "HISTORICAL_READ_ONLY"
    assert _route_markers()["source_fact_selection_v3"] == ("HISTORICAL_READ_ONLY")


def test_07_historical_product_and_provider_reachability_are_forbidden() -> None:
    owner = _owners()["historical_source_fact_selection"]
    assert owner["product_reachability"] == "FORBIDDEN"
    assert owner["provider_reachability"] == "FORBIDDEN"
    assert owner["allowed_consumers"] == [
        "replay",
        "validation",
        "historical_evidence",
    ]
    assert owner["reactivation_requires"] == [
        "new_adr",
        "qualification",
        "explicit_product_decision",
    ]
    pipe = _read(
        SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe.py"
    )
    tree = ast.parse(pipe)
    guard = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_semantic_selection_containment_guard"
    )
    returns = [node for node in guard.body if isinstance(node, ast.Return)]
    assert len(returns) == 1
    assert isinstance(returns[0].value, ast.Constant)
    assert returns[0].value.value is False
    assert "gate2_source_fact_selection" not in _imports(
        PACKAGE_ROOT / "gate2_domain_runtime.py"
    )


def test_08_goal17_is_not_a_current_main_implementation() -> None:
    assert not (
        DOC_ROOT
        / "contracts"
        / "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.md"
    ).exists()
    assert not (
        SERVICE_ROOT / "scripts" / "build_type_first_zero_call_e2e_evidence.py"
    ).exists()
    assert _route_markers()["goal17_type_first_v6"] == "CONTRACT_ONLY"
    assert not any(
        "goal17" in owner_id or "type_first" in owner_id for owner_id in _owners()
    )


def test_09_pr232_reuse_is_limited_to_contract_and_test_ideas() -> None:
    references = _metadata()["external_candidate_references"]
    assert references == [
        {
            "external_candidate_reference": "PR_232",
            "current_main_status": (
                "CLOSED_WITHOUT_MERGE_NOT_PRESENT_AS_IMPLEMENTATION"
            ),
            "approved_reuse_scope": "contract_and_test_ideas_only",
            "forbidden_reuse_scope": [
                "synthetic_source_projection_as_product_input",
                "separate_product_runtime",
                "separate_pipe",
                "separate_coordinator",
                "new_valves_or_admissions",
                "duplicate_request_authority",
                "duplicate_materializer",
                "parallel_v6_product_orchestration",
            ],
        }
    ]


def test_10_future_semantic_route_is_singular() -> None:
    decisions = _metadata()["program_owner_decisions"]
    assert decisions["preferred_option"] == "A"
    assert decisions["reserve_option"] == "B_IF_DISTINCT_DOMAIN_IS_PROVEN"
    assert decisions["kt2_authorized"] is True
    subordinate = _owners()["current_source_fact_orchestration"][
        "inactive_subordinate_capabilities"
    ][0]
    assert subordinate["product_reachability"] == "FORBIDDEN"
    assert subordinate["provider_reachability"] == "FORBIDDEN"
    assert subordinate["canonical_owner_delta"] == 0
    adr = _read(CONVERGENCE_ADR)
    assert (
        adr.count(
            "one Pack-backed Type-First classifier inside the existing product boundary"
        )
        == 1
    )
    assert "**Option D is rejected**" in adr


def test_11_canonical_materializer_has_one_authority() -> None:
    owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialEvidenceMaterializerFactory" in _defined_symbols(path)
    ]
    assert owners == [PACKAGE_ROOT / "gate2_financial_evidence_materialization.py"]
    assert _owners()["canonical_financial_materializer"]["symbols"] == [
        "Gate2FinancialEvidenceMaterializerFactory"
    ]


def test_12_financial_type_authority_is_singular() -> None:
    owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialSemanticContractFactory" in _defined_symbols(path)
    ]
    assert owners == [PACKAGE_ROOT / "gate2_financial_semantic_contract.py"]
    assert _owners()["financial_type_authority"]["symbols"] == [
        "Gate2FinancialSemanticContractFactory"
    ]


def test_13_evidence_and_replay_authority_is_singular() -> None:
    evidence_owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialSemanticV6DecisionEvidenceFactory" in _defined_symbols(path)
    ]
    replay_owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "replay_financial_semantic_v6_decision" in _defined_symbols(path)
    ]
    expected = PACKAGE_ROOT / "gate2_financial_semantic_v6_evidence.py"
    assert evidence_owners == [expected]
    assert replay_owners == [expected]


def test_14_answer_context_remains_a_post_gate2_consumer() -> None:
    owner = PACKAGE_ROOT / "answer_context_selection.py"
    source = _read(owner)
    assert 'run.get("run_status") != "completed"' in source
    assert '"answer_context_gate2_run_not_completed"' in source
    assert all("gate2_financial" not in module for module in _imports(owner))
    domain_runtime = _read(PACKAGE_ROOT / "gate2_domain_runtime.py")
    assert "AnswerContextSelectionFactory" in domain_runtime
    assert domain_runtime.index(
        'terminal_status == "completed"'
    ) < domain_runtime.index("AnswerContextSelectionFactory(")


def test_15_live_parity_is_closed_without_authorizing_kt2() -> None:
    owner = _owners()["release_live_parity_verifier"]
    route = _read(ROUTE_STATUS)
    adr = _read(CONVERGENCE_ADR)
    assert owner["runtime_status"] == "VERIFIED_LIVE"
    assert "fresh_live_parity_checkpoint_after_change" in owner["change_requires"]
    assert "Debt: `CLOSED_BY_KT1_5`." in route
    assert "db009421b68c8b09df728239d23c217e5482d3a1" in route
    assert "live qualification or release" in route
    assert "kt2_authorized = false" in adr


def test_16_production_source_does_not_require_boundary_comments() -> None:
    forbidden_markers = (
        "# Architecture boundary (KT1)",
        "# Historical containment (KT1)",
    )
    for path in PRODUCTION_OWNER_FILES:
        source = _read(path)
        assert all(marker not in source for marker in forbidden_markers)
    policy = _read(COMMENT_POLICY)
    assert "sidecar owner metadata" in policy
    assert "does not require architecture" in policy


def test_17_new_package_module_is_declared_and_ci_runs_this_suite() -> None:
    added_package_modules = [
        path
        for status, path in _changed_paths()
        if status.startswith("A")
        and path.startswith("services/broker-reports-gate1-proof/broker_reports_gate1/")
        and path.endswith(".py")
    ]
    allowed_subordinates = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_same_source_type_first_proof.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_bounded_semantic_context.py"
        ),
    }
    allowed_standalone_contract_authorities = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "authenticated_case_taxpayer_binding.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_declaration_mvp.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "active_category_declaration_assembly.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_right_side_assembly.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate4_ordinary_trade_candidate.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_semantic_compiler.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_projection.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_candidate_runtime.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_qualified_mappings.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_production_runtime.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "ordinary_trade_tax_model_bridge.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_table_locator.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_table_locator_provider.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_financial_label_dictionary.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_financial_role_pack.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_role_labeling.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_financial_annotations_persistence.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_ndfl_case_readiness.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_ndfl_workflow.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_evidence_demand_port.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate4_financial_case_materialization.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate4_financial_case_cache.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_methodology_selection.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_supplemental_fact.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_combined_requirement_check.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_supplemental_fact_discovery.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_single_input_human_loop.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_methodology_calculation.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_trusted_methodology.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_deterministic_source_fact_consumption.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_metadata_source_facts.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_llm_metadata_adapter.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_evidence_intake.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_evidence_demand.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_evidence_demand_contract.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_methodology_evidence.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_residency_evidence.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_real_tax_case_assembly.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_client_evidence_review.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_scope_resolution.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_human_gap_closure.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_preparation.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_external_evidence.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_projection.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_securities_disposal_tax_model.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_tax_period_category_aggregation.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_income_group_tax_base.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_runtime_capabilities.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_published_typed_behavior.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_definition.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_clean_context_declaration_trial.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_authoring_language.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_full_declaration_definition.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_scope_resolution.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_filing_context.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_budget_outcome.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_tax_settlement.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_income_sources.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_financial_investment_results.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_resolved_declaration_package.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_declaration_semantic_input.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_full_target_xml_projection.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_end_to_end_full_target_xml.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate5_openwebui_product.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "declaration_semantics.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_contracts.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_coverage.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_parity.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_pdf_document.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_audit.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_parity.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_view_semantic_contracts.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_view_semantic_experiment.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_view_semantic_adjudication.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_contracts_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "logical_row_table_recovery.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_pdf_document_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_audit_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_parity_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "canonical_artifact.py"
        ),
        ("services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py"),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "canonical_consumer_migration.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "canonical_wave2_shadow.py"
        ),
        ("services/broker-reports-gate1-proof/broker_reports_gate1/xlsx_streaming.py"),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_projection.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_structural_chunking.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_bounded_labeling.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_chunk_batch_labeling.py"
        ),
    }
    allowed_support_modules = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gemini_normalized_table_boxes.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_native_navigation_overlay.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "visual_pdfplumber_table_plan.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "pdf_grid_experiment_provider.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate3_financial_label_dictionary_cli.py"
        ),
    }
    assert set(added_package_modules) <= (
        allowed_subordinates
        | allowed_standalone_contract_authorities
        | allowed_support_modules
    )
    added_subordinates = set(added_package_modules) & allowed_subordinates
    if added_subordinates:
        capabilities = _owners()["current_source_fact_orchestration"][
            "inactive_subordinate_capabilities"
        ]
        assert added_subordinates <= {item["module"] for item in capabilities}
        assert all(item["canonical_owner_delta"] == 0 for item in capabilities)
    added_contract_authorities = (
        set(added_package_modules) & allowed_standalone_contract_authorities
    )
    managed_document_contracts = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "managed_document_contracts.py"
    )
    if managed_document_contracts in added_contract_authorities:
        managed_contract = (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.md"
        )
        managed_test = (
            SERVICE_ROOT / "tests" / "test_broker_reports_managed_document_contract.py"
        )
        module = PACKAGE_ROOT / "managed_document_contracts.py"
        assert managed_contract.is_file()
        assert managed_test.is_file()
        assert "CONTRACTED_INACTIVE" in _read(managed_contract)
        assert "def main(" not in _read(module)
        assert "openwebui_actions" not in _imports(module)
    doc2_authorities = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_coverage.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_parity.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_pdf_document.py"
        ),
    }
    if added_contract_authorities & doc2_authorities:
        coverage_contract = (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_MANAGED_DOCUMENT_COVERAGE.v1.md"
        )
        parity_contract = (
            DOC_ROOT
            / "contracts"
            / "BROKER_REPORTS_PDF_ARTIFACT_PARITY_CHECKLIST.v1.md"
        )
        doc2_test = (
            SERVICE_ROOT / "tests" / "test_broker_reports_managed_pdf_document.py"
        )
        assert coverage_contract.is_file()
        assert parity_contract.is_file()
        assert doc2_test.is_file()
        for authority in doc2_authorities:
            module = REPO_ROOT / authority
            assert "def main(" not in _read(module)
            assert "openwebui_actions" not in _imports(module)
    doc3_authorities = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_audit.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_parity.py"
        ),
    }
    if added_contract_authorities & doc3_authorities:
        view_contract = (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_LLM_DOCUMENT_VIEW.v1.md"
        )
        view_test = (
            SERVICE_ROOT / "tests" / "test_broker_reports_managed_document_llm_view.py"
        )
        assert view_contract.is_file()
        assert view_test.is_file()
        for authority in doc3_authorities:
            module = REPO_ROOT / authority
            assert "def main(" not in _read(module)
            assert "openwebui_actions" not in _imports(module)
    doc6_authorities = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_contracts_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "logical_row_table_recovery.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_pdf_document_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_audit_v2.py"
        ),
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "managed_document_llm_view_parity_v2.py"
        ),
    }
    if added_contract_authorities & doc6_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_LLM_DOCUMENT_VIEW.v2.md",
            DOC_ROOT / "BROKER_REPORTS_DOC6_LOGICAL_ROW_MODEL_DECISION.v1.md",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_managed_document_contract_v2.py",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_logical_row_table_recovery.py",
            SERVICE_ROOT / "tests" / "test_broker_reports_managed_pdf_document_v2.py",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_managed_document_llm_view_v2.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        for owner in (
            "ManagedDocumentContractV2Validator",
            "LogicalRowTableFactory",
            "ManagedPdfDocumentV2Factory",
            "ManagedDocumentLlmViewV2Factory",
            "ManagedDocumentLlmViewV2Auditor",
        ):
            assert owner in authority_map
        for authority in doc6_authorities:
            module = REPO_ROOT / authority
            assert "def main(" not in _read(module)
            assert "openwebui_actions" not in _imports(module)
    doc26_authorities = {
        (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "canonical_artifact.py"
        ),
        ("services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py"),
    }
    if added_contract_authorities & doc26_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_PIPELINE_GATES.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_CANONICAL_READER.v1.md",
            SERVICE_ROOT / "tests" / "test_broker_reports_canonical_artifact_v1.py",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_canonical_storage_lifecycle_v1.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        for owner in (
            "CanonicalNormalizerFactory.create",
            "CanonicalArtifactStoreFactory.create",
            "CanonicalReaderFactory.create",
        ):
            assert owner in authority_map
        for authority in doc26_authorities:
            module = REPO_ROOT / authority
            source = _read(module)
            assert "FACTORY_REQUIRED" in source
            assert source.startswith('"""Gate 2 ')
            assert "def main(" not in source
            assert "openwebui_actions" not in _imports(module)
    doc27_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "canonical_consumer_migration.py"
    )
    if doc27_authority in added_contract_authorities:
        for path in (
            DOC_ROOT
            / "contracts"
            / "BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_CANONICAL_READER.v1.md",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_canonical_consumer_compatibility.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        for owner in (
            "Gate1ArtifactStoreCanonicalAdapterFactory",
            "PdfCompactCanonicalAdapterFactory",
            "LocalPdfCompactResearchCanonicalAdapterFactory",
        ):
            assert owner in authority_map
        module = REPO_ROOT / doc27_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    gate3_projection_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py"
    )
    if gate3_projection_authority in added_contract_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md",
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_PROJECTION.v1.schema.json",
            SERVICE_ROOT / "tests" / "test_broker_reports_gate3_projection.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        assert "Gate3ProjectionFactory.create" in authority_map
        module = REPO_ROOT / gate3_projection_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "CanonicalReaderFactory" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    gate3_chunking_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_structural_chunking.py"
    )
    if gate3_chunking_authority in added_contract_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md",
            DOC_ROOT
            / "contracts"
            / "BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json",
            SERVICE_ROOT / "tests" / "test_broker_reports_gate3_structural_chunking.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        assert "Gate3StructuralChunkFactory.create" in authority_map
        module = REPO_ROOT / gate3_chunking_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "Gate3ProjectionFactory" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    gate3_dictionary_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_financial_label_dictionary.py"
    )
    if gate3_dictionary_authority in added_contract_authorities:
        for path in (
            DOC_ROOT
            / "contracts"
            / "BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md",
            PACKAGE_ROOT / "gate3_financial_label_dictionary.v1.json",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_gate3_financial_label_dictionary.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        assert "Gate3FinancialLabelDictionaryFactory.create" in authority_map
        module = REPO_ROOT / gate3_dictionary_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "resources.files(__package__)" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    gate3_labeling_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_bounded_labeling.py"
    )
    if gate3_labeling_authority in added_contract_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md",
            PACKAGE_ROOT / "gate3_labeling_response.v1.schema.json",
            SERVICE_ROOT / "tests" / "test_broker_reports_gate3_bounded_labeling.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        assert "Gate3BoundedLabelingFactory.create" in authority_map
        module = REPO_ROOT / gate3_labeling_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "Gate3ProjectionFactory" in source
        assert "Gate3FinancialLabelDictionaryFactory" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    gate3_chunk_batch_authority = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_chunk_batch_labeling.py"
    )
    if gate3_chunk_batch_authority in added_contract_authorities:
        for path in (
            DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING.v1.md",
            SERVICE_ROOT
            / "tests"
            / "test_broker_reports_gate3_chunk_batch_labeling.py",
        ):
            assert path.is_file()
        authority_map = _read(ARCHITECTURE_AUTHORITIES)
        assert "Gate3ChunkBatchLabelingFactory.create" in authority_map
        module = REPO_ROOT / gate3_chunk_batch_authority
        source = _read(module)
        assert "FACTORY_REQUIRED" in source
        assert "FORBIDDEN" in source
        assert "Gate3StructuralChunkFactory" in source
        assert "Gate3BoundedLabelingFactory" in source
        assert "def main(" not in source
        assert "openwebui_actions" not in _imports(module)
    workflow = _read(REPO_ROOT / ".github" / "workflows" / "broker-reports-ci.yml")
    for doc6_suite in (
        "tests/test_broker_reports_managed_document_contract_v2.py",
        "tests/test_broker_reports_logical_row_table_recovery.py",
        "tests/test_broker_reports_managed_pdf_document_v2.py",
        "tests/test_broker_reports_managed_document_llm_view_v2.py",
    ):
        assert doc6_suite in workflow
    for gate3_suite in (
        "tests/test_broker_reports_gate3_minimal_labeling_contract.py",
        "tests/test_broker_reports_gate3_projection.py",
        "tests/test_broker_reports_gate3_structural_chunking.py",
        "tests/test_broker_reports_gate3_financial_label_dictionary.py",
        "tests/test_broker_reports_gate3_financial_role_pack.py",
        "tests/test_broker_reports_gate3_bounded_labeling.py",
        "tests/test_broker_reports_gate3_role_labeling.py",
        "tests/test_broker_reports_gate3_chunk_batch_labeling.py",
        "tests/test_broker_reports_gate3_financial_annotations_persistence.py",
        "tests/test_broker_reports_gate3_ndfl_case_readiness.py",
        "tests/test_broker_reports_gate3_ndfl_workflow.py",
        "tests/test_broker_reports_gate3_openwebui_managed_dictionary.py",
    ):
        assert gate3_suite in workflow
    assert DOMAIN_MAP.is_file()


def test_18_doc6_runtime_is_inactive_and_factory_routed() -> None:
    doc6_modules = {
        "managed_document_contracts_v2",
        "logical_row_table_recovery",
        "managed_pdf_document_v2",
        "managed_document_llm_view_v2",
        "managed_document_llm_view_audit_v2",
        "managed_document_llm_view_parity_v2",
    }
    allowed_import_edges = {
        (
            PACKAGE_ROOT / "managed_pdf_document_v2.py",
            "managed_document_contracts_v2",
        ),
        (
            PACKAGE_ROOT / "managed_pdf_document_v2.py",
            "logical_row_table_recovery",
        ),
        (
            PACKAGE_ROOT / "managed_document_llm_view_v2.py",
            "managed_document_contracts_v2",
        ),
        (
            PACKAGE_ROOT / "managed_document_llm_view_parity_v2.py",
            "managed_document_llm_view_audit_v2",
        ),
    }
    factory_internal_constructors = {
        "LogicalRowTableRecoveryRuntime": (
            PACKAGE_ROOT / "logical_row_table_recovery.py"
        ),
        "ManagedPdfDocumentV2Builder": (PACKAGE_ROOT / "managed_pdf_document_v2.py"),
        "_ManagedDocumentLlmViewV2Renderer": (
            PACKAGE_ROOT / "managed_document_llm_view_v2.py"
        ),
    }
    import_violations: list[str] = []
    constructor_violations: list[str] = []

    roots = (
        PACKAGE_ROOT,
        SERVICE_ROOT / "scripts",
        SERVICE_ROOT / "openwebui_actions",
    )
    for root in roots:
        for path in root.glob("*.py"):
            tree = ast.parse(_read(path), filename=str(path))
            imported_candidates: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_candidates.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module:
                        imported_candidates.add(module)
                    imported_candidates.update(
                        f"{module}.{alias.name}" if module else alias.name
                        for alias in node.names
                    )
                elif isinstance(node, ast.Call) and isinstance(
                    node.func,
                    ast.Name,
                ):
                    allowed_path = factory_internal_constructors.get(node.func.id)
                    if allowed_path is not None and path != allowed_path:
                        constructor_violations.append(
                            f"{path.relative_to(SERVICE_ROOT).as_posix()}:"
                            f"{node.lineno}:{node.func.id}"
                        )

            imported_doc6 = {
                part
                for candidate in imported_candidates
                for part in candidate.split(".")
                if part in doc6_modules
            }
            for target_module in imported_doc6:
                if (path, target_module) not in allowed_import_edges:
                    import_violations.append(
                        f"{path.relative_to(SERVICE_ROOT).as_posix()}->{target_module}"
                    )

    assert sorted(import_violations) == []
    assert sorted(constructor_violations) == []
