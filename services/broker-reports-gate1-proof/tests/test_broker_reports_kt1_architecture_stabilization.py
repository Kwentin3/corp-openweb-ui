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
ROUTE_STATUS = (
    DOC_ROOT / "architecture" / "BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md"
)
OWNER_CONTEXT = (
    DOC_ROOT / "architecture" / "BROKER_REPORTS_OWNER_CONTEXT.v1.json"
)
OWNER_CONTEXT_GUIDE = (
    DOC_ROOT / "architecture" / "BROKER_REPORTS_OWNER_CONTEXT.v1.md"
)
OWNER_MATRIX = (
    DOC_ROOT / "contracts" / "BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md"
)
CONVERGENCE_ADR = (
    DOC_ROOT / "adr" / "BROKER_REPORTS_GATE2_SEMANTIC_CONVERGENCE.v1.md"
)
COMMENT_POLICY = (
    DOC_ROOT / "agent" / "BROKER_REPORTS_CODE_COMMENT_POLICY.v1.md"
)

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
    pattern = re.compile(
        r"<!-- route_id=([a-z0-9_]+);status=([A-Z_]+) -->"
    )
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
    result.extend(
        ("A", path.replace("\\", "/")) for path in untracked
    )
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
        "semantic_visual_validation": (
            "SemanticVisualTableValidatorFactory",
        ),
        "logical_table_materialization": (
            "SemanticVisualTableMaterializationFactory",
        ),
        "gate2_table_package": ("Gate2TablePackageFactory",),
        "current_source_fact_orchestration": (
            "Gate2DomainSourceFactRuntimeFactory",
        ),
        "historical_source_fact_selection": ("source_fact_selection_v3",),
        "financial_type_authority": (
            "Gate2FinancialSemanticContractFactory",
        ),
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
    assert _route_markers()["source_fact_selection_v3"] == (
        "HISTORICAL_READ_ONLY"
    )


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
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate2_source_fact_pipe.py"
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
    assert (
        "gate2_source_fact_selection"
        not in _imports(PACKAGE_ROOT / "gate2_domain_runtime.py")
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
        "goal17" in owner_id or "type_first" in owner_id
        for owner_id in _owners()
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
            "one Pack-backed Type-First classifier inside the existing "
            "product boundary"
        )
        == 1
    )
    assert "**Option D is rejected**" in adr


def test_11_canonical_materializer_has_one_authority() -> None:
    owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialEvidenceMaterializerFactory"
        in _defined_symbols(path)
    ]
    assert owners == [
        PACKAGE_ROOT / "gate2_financial_evidence_materialization.py"
    ]
    assert _owners()["canonical_financial_materializer"]["symbols"] == [
        "Gate2FinancialEvidenceMaterializerFactory"
    ]


def test_12_financial_type_authority_is_singular() -> None:
    owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialSemanticContractFactory" in _defined_symbols(path)
    ]
    assert owners == [
        PACKAGE_ROOT / "gate2_financial_semantic_contract.py"
    ]
    assert _owners()["financial_type_authority"]["symbols"] == [
        "Gate2FinancialSemanticContractFactory"
    ]


def test_13_evidence_and_replay_authority_is_singular() -> None:
    evidence_owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialSemanticV6DecisionEvidenceFactory"
        in _defined_symbols(path)
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


def test_17_new_package_module_is_declared_subordinate_and_ci_runs_this_suite() -> None:
    added_package_modules = [
        path
        for status, path in _changed_paths()
        if status.startswith("A")
        and path.startswith(
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
        )
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
    assert set(added_package_modules) <= allowed_subordinates
    if added_package_modules:
        capabilities = _owners()["current_source_fact_orchestration"][
            "inactive_subordinate_capabilities"
        ]
        assert set(added_package_modules) <= {
            item["module"] for item in capabilities
        }
        assert all(item["canonical_owner_delta"] == 0 for item in capabilities)
    workflow = _read(
        REPO_ROOT / ".github" / "workflows" / "broker-reports-ci.yml"
    )
    assert "tests/test_broker_reports_kt1_architecture_stabilization.py" in (
        workflow
    )
    assert DOMAIN_MAP.is_file()
