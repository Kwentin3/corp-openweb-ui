from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
DOC_ROOT = REPO_ROOT / "docs" / "stage2"

DOMAIN_MAP = (
    DOC_ROOT / "architecture" / "BROKER_REPORTS_DOMAIN_MAP.v1.md"
)
ROUTE_STATUS = (
    DOC_ROOT / "architecture" / "BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md"
)
OWNER_MATRIX = (
    DOC_ROOT / "contracts" / "BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md"
)
CONVERGENCE_ADR = (
    DOC_ROOT / "adr" / "BROKER_REPORTS_GATE2_SEMANTIC_CONVERGENCE.v1.md"
)
PRE_TASK_PROTOCOL = (
    DOC_ROOT / "agent" / "BROKER_REPORTS_PRE_TASK_CONTEXT_PROTOCOL.v1.md"
)
COMMENT_POLICY = (
    DOC_ROOT / "agent" / "BROKER_REPORTS_CODE_COMMENT_POLICY.v1.md"
)
KT1_DOCS = (
    DOMAIN_MAP,
    ROUTE_STATUS,
    OWNER_MATRIX,
    CONVERGENCE_ADR,
    PRE_TASK_PROTOCOL,
    COMMENT_POLICY,
)

BOUNDARY_COMMENT_FILES = (
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

ALLOWED_DISPOSITIONS = {
    "KEEP_AS_SOLE_OWNER",
    "REUSE",
    "EXTEND",
    "HISTORICAL_READ_ONLY",
    "PROOF_ONLY",
    "TO_BE_SUPERSEDED",
    "DUPLICATE_DO_NOT_ACTIVATE",
    "REQUIRES_DECISION",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def _matrix_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in _read(OWNER_MATRIX).splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        responsibility = cells[0].strip("`")
        assert responsibility not in rows
        rows[responsibility] = cells
    return rows


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
    result = []
    for line in tracked:
        status, path = line.split("\t", maxsplit=1)
        result.append((status, path.replace("\\", "/")))
    result.extend(("A", path.replace("\\", "/")) for path in untracked)
    return result


def test_each_key_responsibility_has_one_declared_sole_owner() -> None:
    rows = _matrix_rows()
    required = {
        "visual_transcription",
        "logical_table_materialization",
        "gate2_table_package",
        "source_unit_segmentation",
        "financial_type_authority",
        "product_semantic_classification",
        "model_facing_response_schema",
        "semantic_response_parser",
        "prebound_option_construction",
        "exact_choice_restoration",
        "reason_derivation",
        "canonical_financial_validator",
        "canonical_financial_materializer",
        "financial_evidence_replay",
        "answer_context_selection",
        "release_parity",
    }
    assert required <= rows.keys()
    assert len(rows) == 18
    for cells in rows.values():
        assert len(cells) == 6
        assert cells[1]
        dispositions = set(re.findall(r"`([A-Z_]+)`", cells[5]))
        assert dispositions
        assert dispositions <= ALLOWED_DISPOSITIONS


def test_historical_source_fact_selection_is_not_product_reachable() -> None:
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


def test_goal17_type_first_is_not_product_reachable_on_main() -> None:
    assert not (
        DOC_ROOT
        / "contracts"
        / "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.md"
    ).exists()
    assert not (
        SERVICE_ROOT / "scripts" / "build_type_first_zero_call_e2e_evidence.py"
    ).exists()
    forbidden_by_file = {
        "gate2_financial_semantic_v6_choice.py": (
            "def create_type_first_response_profile",
        ),
        "gate2_financial_semantic_v6_context_linter.py": (
            "def create_type_first(",
        ),
        "gate2_model_requests.py": ("build_from_sealed_type_first",),
    }
    for filename, markers in forbidden_by_file.items():
        source = _read(PACKAGE_ROOT / filename)
        assert all(marker not in source for marker in markers)
    assert _route_markers()["goal17_type_first_v6"] == "CONTRACT_ONLY"


def test_semantic_visual_route_does_not_classify_finance() -> None:
    visual_files = (
        PACKAGE_ROOT / "semantic_visual_table_contracts.py",
        PACKAGE_ROOT / "semantic_visual_table_validator.py",
        PACKAGE_ROOT / "semantic_visual_table_materialization.py",
        PACKAGE_ROOT / "pdf_dual_vlm_runtime.py",
    )
    for path in visual_files:
        assert all(
            "gate2_financial" not in module for module in _imports(path)
        )
    contract = _read(PACKAGE_ROOT / "semantic_visual_table_contracts.py")
    assert (
        'SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS = frozenset({"description", "rows"})'
        in contract
    )
    materializer = _read(
        PACKAGE_ROOT / "semantic_visual_table_materialization.py"
    )
    assert '"tax_meaning_inferred": False' in materializer


def test_financial_semantic_model_has_no_crop_byte_input() -> None:
    files = tuple(PACKAGE_ROOT.glob("gate2_financial_semantic*.py")) + (
        PACKAGE_ROOT / "gate2_financial_evidence_materialization.py",
    )
    forbidden_markers = (
        "crop_bytes",
        "private_png_base64",
        "image_bytes",
        "PdfDualVlmRuntime",
    )
    for path in files:
        source = _read(path)
        assert all(marker not in source for marker in forbidden_markers)
        assert all(
            "pdf_dual_vlm" not in module for module in _imports(path)
        )


def test_canonical_financial_materializer_has_one_authority() -> None:
    owners = [
        path
        for path in PACKAGE_ROOT.glob("*.py")
        if "Gate2FinancialEvidenceMaterializerFactory"
        in _defined_symbols(path)
    ]
    assert owners == [
        PACKAGE_ROOT / "gate2_financial_evidence_materialization.py"
    ]
    source = _read(owners[0])
    assert (
        "the only production financial evidence materialization path" in source
    )


def test_answer_context_is_post_gate2_and_not_financial_model_input() -> None:
    owner = PACKAGE_ROOT / "answer_context_selection.py"
    source = _read(owner)
    assert 'run.get("run_status") != "completed"' in source
    assert '"answer_context_gate2_run_not_completed"' in source
    assert all(
        "gate2_financial" not in module for module in _imports(owner)
    )
    domain_runtime = _read(PACKAGE_ROOT / "gate2_domain_runtime.py")
    assert "AnswerContextSelectionFactory" in domain_runtime
    assert domain_runtime.index(
        'terminal_status == "completed"'
    ) < domain_runtime.index("AnswerContextSelectionFactory(")


def test_route_status_matches_current_imports_and_guards() -> None:
    assert _route_markers() == {
        "semantic_visual_table": "ACTIVE_PRODUCT",
        "current_broad_source_facts": "ACTIVE_PRODUCT",
        "source_fact_selection_v3": "HISTORICAL_READ_ONLY",
        "goal17_type_first_v6": "CONTRACT_ONLY",
        "fns_2ndfl_adapter": "ACTIVE_PRODUCT",
        "answer_context": "ACTIVE_PRODUCT",
        "gate3_context_manifest": "ACTIVE_PRODUCT",
        "gate4_contracts": "CONTRACT_ONLY",
        "release_live_bundle_state": "UNVERIFIED_LIVE",
    }
    domain_pipe = _read(
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate2_domain_source_fact_pipe.py"
    )
    assert "Gate2DomainSourceFactRuntimeFactory" in domain_pipe
    assert all(
        "gate2_model" not in module
        for module in _imports(PACKAGE_ROOT / "gate2_fns_2ndfl_adapter.py")
    )


def test_docs_never_name_historical_route_active() -> None:
    route_text = _read(ROUTE_STATUS)
    historical_section = route_text.split(
        "## 3. Historical `source_fact_selection_v3`", maxsplit=1
    )[1].split("## 4.", maxsplit=1)[0]
    assert "status=HISTORICAL_READ_ONLY" in historical_section
    assert "status=ACTIVE_PRODUCT" not in historical_section
    assert "Production reachability:** `false`" in historical_section
    assert "source_fact_selection_v3;status=ACTIVE_PRODUCT" not in "\n".join(
        _read(path) for path in KT1_DOCS
    )


def test_pr232_is_not_treated_as_part_of_main() -> None:
    route_text = _read(ROUTE_STATUS)
    adr_text = _read(CONVERGENCE_ADR)
    assert "Draft PR #232" in route_text
    assert "not part of `main`" in route_text
    assert "Recommendation: `CLOSE_AFTER_EXTRACTION`." in route_text
    assert "Recommendation: `CLOSE_AFTER_EXTRACTION`." in adr_text
    assert "KT1 makes no state change to PR #232." in adr_text


def test_openwebui_core_imports_are_unchanged() -> None:
    changed = [path for _, path in _changed_paths()]
    forbidden_core_prefixes = (
        "backend/open_webui/",
        "open-webui/backend/open_webui/",
        "services/open_webui/",
    )
    assert not any(
        path.startswith(forbidden_core_prefixes) for path in changed
    )
    assert not any(
        path.startswith(
            "services/broker-reports-gate1-proof/openwebui_actions/"
        )
        for path in changed
    )


def test_architecture_docs_reference_existing_symbols() -> None:
    symbols_by_file = {
        "semantic_visual_table_validator.py": {
            "SemanticVisualTableValidatorFactory"
        },
        "pdf_dual_vlm_runtime.py": {"PdfDualVlmRuntimeFactory"},
        "semantic_visual_table_materialization.py": {
            "SemanticVisualTableMaterializationFactory"
        },
        "gate2_table_packages.py": {"Gate2TablePackageFactory"},
        "gate2_source_unit_segmentation.py": {
            "Gate2SourceUnitSegmenterFactory"
        },
        "gate2_domain_runtime.py": {"Gate2DomainSourceFactRuntimeFactory"},
        "gate2_financial_semantic_contract.py": {
            "Gate2FinancialSemanticContractFactory"
        },
        "gate2_financial_semantic_v6_choice.py": {
            "Gate2FinancialSemanticV6ChoiceContractFactory"
        },
        "gate2_financial_semantic_v6_packet.py": {
            "Gate2FinancialSemanticV6PacketFactory"
        },
        "gate2_financial_semantic_v5_projection.py": {
            "Gate2FinancialSemanticV5ProjectionFactory"
        },
        "gate2_financial_semantic_v6_expansion.py": {
            "Gate2FinancialSemanticV6DecisionExpansionFactory"
        },
        "gate2_financial_evidence_materialization.py": {
            "Gate2FinancialEvidenceValidatedDecisionFactory",
            "Gate2FinancialEvidenceMaterializerFactory",
        },
        "gate2_financial_semantic_v6_evidence.py": {
            "Gate2FinancialSemanticV6DecisionEvidenceFactory",
            "replay_financial_semantic_v6_decision",
        },
        "answer_context_selection.py": {"AnswerContextSelectionFactory"},
        "artifact_store.py": {"ArtifactStoreFactory"},
        "artifact_resolver.py": {"ArtifactResolver"},
        "gate3_context_manifest.py": {"Gate3ContextManifestFactory"},
    }
    docs = "\n".join(_read(path) for path in KT1_DOCS)
    for filename, symbols in symbols_by_file.items():
        definitions = _defined_symbols(PACKAGE_ROOT / filename)
        assert symbols <= definitions
        assert all(f"`{symbol}" in docs for symbol in symbols)


def test_selected_owner_modules_have_boundary_comments() -> None:
    required_fields = (
        "# Domain:",
        "# Input contract:",
        "# Output contract:",
        "# Owns:",
        "# Does not own:",
        "# Allowed consumers:",
        "# Runtime status:",
        "# Related ADR:",
        "# Contract tests:",
    )
    for path in BOUNDARY_COMMENT_FILES:
        source = _read(path)
        assert source.count("# Architecture boundary (KT1)") == 1
        assert all(field in source for field in required_fields)


def test_historical_route_has_containment_comment() -> None:
    source = _read(PACKAGE_ROOT / "gate2_source_fact_selection.py")
    assert source.count("# Historical containment (KT1)") == 1
    assert "# Why retained:" in source
    assert "# Why product reachability is forbidden:" in source
    assert "# Allowed consumers:" in source
    assert "# ADR required to change status:" in source


def test_kt1_adds_no_owner_module_and_ci_runs_this_test() -> None:
    added_package_modules = [
        path
        for status, path in _changed_paths()
        if status.startswith("A")
        and path.startswith(
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
        )
        and path.endswith(".py")
    ]
    assert added_package_modules == []
    workflow = _read(REPO_ROOT / ".github" / "workflows" / "broker-reports-ci.yml")
    assert "tests/test_broker_reports_kt1_architecture_stabilization.py" in workflow
