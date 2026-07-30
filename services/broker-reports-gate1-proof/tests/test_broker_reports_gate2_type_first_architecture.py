from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
SCRIPTS_ROOT = SERVICE_ROOT / "scripts"
OPENWEBUI_ACTIONS_ROOT = SERVICE_ROOT / "openwebui_actions"
GOAL17_BASE_COMMIT = "9a4cc2c9f3dce4b4d4c55bff667d12089e62b614"

CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.json"
)
PRODUCT_PIPE_PATHS = (
    OPENWEBUI_ACTIONS_ROOT / "broker_reports_gate1_pipe.py",
    OPENWEBUI_ACTIONS_ROOT / "broker_reports_gate2_source_fact_pipe.py",
    OPENWEBUI_ACTIONS_ROOT
    / "broker_reports_gate2_domain_source_fact_pipe.py",
)
UNCHANGED_SUPPORT_PATHS = (
    PACKAGE_ROOT / "gate2_provider_adapters.py",
    PACKAGE_ROOT / "gate2_financial_semantic_v6_totality.py",
    PACKAGE_ROOT
    / "gate2_financial_semantic_v6_context_v2_1_provider_proof.py",
)
BUNDLE_BUILDER_PATH = SCRIPTS_ROOT / "build_openwebui_pipe_bundle.py"
GENERATED_BUNDLE_PATHS = (
    OPENWEBUI_ACTIONS_ROOT / "broker_reports_gate1_pipe_bundled.py",
    OPENWEBUI_ACTIONS_ROOT
    / "broker_reports_gate2_source_fact_pipe_bundled.py",
    OPENWEBUI_ACTIONS_ROOT
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)

EXPECTED_OWNER_LOCATIONS = {
    "Gate2FinancialSemanticV6PacketFactory": (
        "gate2_financial_semantic_v6_packet.py"
    ),
    "Gate2FinancialSemanticV6ChoiceContractFactory": (
        "gate2_financial_semantic_v6_choice.py"
    ),
    "Gate2FinancialSemanticV6ContextLinterFactory": (
        "gate2_financial_semantic_v6_context_linter.py"
    ),
    "Gate2OpenWebUIRequestBuilder": "gate2_model_requests.py",
    "Gate2FinancialSemanticV6DecisionExpansionFactory": (
        "gate2_financial_semantic_v6_expansion.py"
    ),
    "Gate2FinancialSemanticV6DecisionEvidenceFactory": (
        "gate2_financial_semantic_v6_evidence.py"
    ),
    "Gate2EconomyBudgetSessionFactory": "gate2_economy_budget.py",
    "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator": (
        "gate2_financial_semantic_v6_context_v2_1_budget_smoke.py"
    ),
}


def test_type_first_contract_is_inactive_and_changes_no_admission_or_valve():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["status"] == {
        "active": False,
        "transport_eligible": False,
        "runtime_activation": False,
        "provider_calls_total": 0,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "semantic_repair_total": 0,
        "fallback_total": 0,
        "production_admissions_change_total": 0,
        "new_authorities_total": 0,
    }
    compatibility = contract["compatibility_contract"]
    assert compatibility["feature_valves_changed"] is False
    assert compatibility["product_pipes_changed"] is False
    assert compatibility["production_admissions_changed"] is False
    assert compatibility["openwebui_imports_changed"] is False
    assert compatibility["generated_bundle_type_first_product_consumer_total"] == 0

    sys.path.insert(0, str(SERVICE_ROOT))
    try:
        from broker_reports_gate1.gate2_economy_workload_policy import (
            Gate2EconomyWorkloadPolicyFactory,
        )

        policy = Gate2EconomyWorkloadPolicyFactory().create()
    finally:
        sys.path.remove(str(SERVICE_ROOT))
    assert policy.routes
    assert all(route.production_admissions == () for route in policy.routes)
    assert "type_first" not in json.dumps(policy.to_dict(), sort_keys=True)


def test_type_first_traceability_resolves_symbols_and_pytest_nodes() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    traceability = contract["traceability"]
    clauses = [row["clause"] for row in traceability]
    assert clauses == [f"TF-{index:02d}" for index in range(1, 17)]
    assert len(clauses) == len(set(clauses))

    for row in traceability:
        assert "required_additive_symbol" not in row
        symbols = row["required_symbols"]
        tests = row["required_tests"]
        assert isinstance(symbols, list)
        assert isinstance(tests, list) and tests
        assert len(symbols) == len(set(symbols))
        assert len(tests) == len(set(tests))
        if row["clause"] != "TF-16":
            assert symbols

        for symbol in symbols:
            module_name, separator, qualname = symbol.partition(":")
            assert separator and module_name and qualname, symbol
            resolved: Any = importlib.import_module(module_name)
            for part in qualname.split("."):
                assert hasattr(resolved, part), symbol
                resolved = getattr(resolved, part)

        for node_id in tests:
            parts = node_id.split("::")
            test_path = SERVICE_ROOT / parts[0]
            assert (
                len(parts) >= 2
                and parts[0].startswith("tests/")
                and test_path.is_file()
            ), node_id
            candidates: list[ast.AST] = list(
                ast.parse(test_path.read_text(encoding="utf-8")).body
            )
            for name in parts[1:]:
                match = next(
                    (
                        node
                        for node in candidates
                        if isinstance(
                            node,
                            (
                                ast.ClassDef,
                                ast.FunctionDef,
                                ast.AsyncFunctionDef,
                            ),
                        )
                        and node.name == name
                    ),
                    None,
                )
                assert match is not None, node_id
                candidates = (
                    list(match.body)
                    if isinstance(match, ast.ClassDef)
                    else []
                )


def test_type_first_reuses_exact_existing_owners_and_adds_no_factory_module():
    observed: dict[str, list[str]] = {
        owner: [] for owner in EXPECTED_OWNER_LOCATIONS
    }
    forbidden_type_first_factories: list[str] = []

    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name in observed:
                observed[node.name].append(path.name)
            if (
                "typefirst" in node.name.casefold().replace("_", "")
                and node.name.endswith(
                    ("Factory", "Coordinator", "Adapter", "Materializer")
                )
            ):
                forbidden_type_first_factories.append(
                    f"{path.name}:{node.name}"
                )

    assert observed == {
        owner: [path] for owner, path in EXPECTED_OWNER_LOCATIONS.items()
    }
    assert forbidden_type_first_factories == []
    assert [
        path.name
        for path in PACKAGE_ROOT.glob("*.py")
        if "type_first" in path.stem
    ] == []


def test_type_first_request_builder_seal_is_issued_only_by_linter_owner():
    issue_calls: list[tuple[str, int]] = []
    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id
                == "_issue_type_first_request_builder_seal"
            ):
                issue_calls.append((path.name, node.lineno))

    assert len(issue_calls) == 1
    assert issue_calls[0][0] == (
        "gate2_financial_semantic_v6_context_linter.py"
    )


def test_product_pipes_imports_valves_and_consumers_are_immutable():
    for path in PRODUCT_PIPE_PATHS:
        current = _repository_lf_bytes(path.read_bytes())
        baseline = _repository_lf_bytes(_git_blob(path))
        assert current == baseline, path.name

        current_tree = ast.parse(current.decode("utf-8"))
        baseline_tree = ast.parse(baseline.decode("utf-8"))
        assert _import_contract(current_tree) == _import_contract(baseline_tree)
        assert _valve_fields(current_tree) == _valve_fields(baseline_tree)
        assert all(
            "type_first" not in field.casefold()
            for field in _valve_fields(current_tree)
        )
        assert "broker_reports_gate2_type_first" not in current.decode("utf-8")
        assert "create_type_first" not in current.decode("utf-8")
        assert "build_from_sealed_type_first" not in current.decode("utf-8")


def test_adapter_totality_and_provider_proof_remain_byte_exact():
    for path in UNCHANGED_SUPPORT_PATHS:
        assert _repository_lf_bytes(
            path.read_bytes()
        ) == _repository_lf_bytes(_git_blob(path)), path.name


def test_active_packet_and_choice_api_signatures_are_unchanged():
    governed = (
        (
            PACKAGE_ROOT / "gate2_financial_semantic_v6_packet.py",
            "Gate2FinancialSemanticV6PacketFactory",
            ("__init__", "create", "_build"),
            "Gate2FinancialSemanticV6Packet",
        ),
        (
            PACKAGE_ROOT / "gate2_financial_semantic_v6_choice.py",
            "Gate2FinancialSemanticV6ChoiceContractFactory",
            ("__init__", "create", "_build"),
            "Gate2FinancialSemanticV6ChoiceContract",
        ),
    )
    for path, factory_name, active_methods, active_dataclass in governed:
        current_tree = ast.parse(path.read_text(encoding="utf-8"))
        baseline_tree = ast.parse(_git_blob(path).decode("utf-8"))

        assert _method_signatures(
            current_tree,
            class_name=factory_name,
            method_names=active_methods,
        ) == _method_signatures(
            baseline_tree,
            class_name=factory_name,
            method_names=active_methods,
        )
        assert _annotated_class_fields(
            current_tree,
            class_name=active_dataclass,
        ) == _annotated_class_fields(
            baseline_tree,
            class_name=active_dataclass,
        )


def test_generated_bundle_module_topology_is_unchanged():
    assert _repository_lf_bytes(
        BUNDLE_BUILDER_PATH.read_bytes()
    ) == _repository_lf_bytes(_git_blob(BUNDLE_BUILDER_PATH))
    builder = _load_bundle_builder()
    expected_orders = (
        tuple(builder.GATE1_MODULE_ORDER),
        tuple(builder.GATE2_MODULE_ORDER),
        tuple(builder.GATE2_DOMAIN_MODULE_ORDER),
    )

    for path, expected in zip(
        GENERATED_BUNDLE_PATHS,
        expected_orders,
        strict=True,
    ):
        observed = tuple(
            _literal_assignment(
                ast.parse(path.read_text(encoding="utf-8")),
                "_BUNDLED_MODULE_ORDER",
            )
        )
        assert observed == expected, path.name
        assert all("type_first" not in module_name for module_name in observed)


def _git_blob(path: Path) -> bytes:
    repository_path = path.relative_to(REPO_ROOT).as_posix()
    completed = subprocess.run(
        [
            "git",
            "cat-file",
            "blob",
            f"{GOAL17_BASE_COMMIT}:{repository_path}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _repository_lf_bytes(value: bytes) -> bytes:
    assert b"\r" not in value.replace(b"\r\n", b"")
    return value.replace(b"\r\n", b"\n")


def _class_node(tree: ast.Module, class_name: str) -> ast.ClassDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    assert len(matches) == 1, class_name
    return matches[0]


def _method_signatures(
    tree: ast.Module,
    *,
    class_name: str,
    method_names: tuple[str, ...],
) -> dict[str, tuple[str, str | None, tuple[str, ...]]]:
    class_node = _class_node(tree, class_name)
    methods = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }
    assert set(methods) == set(method_names)
    return {
        name: (
            ast.dump(methods[name].args, include_attributes=False),
            (
                ast.dump(methods[name].returns, include_attributes=False)
                if methods[name].returns is not None
                else None
            ),
            tuple(
                ast.dump(decorator, include_attributes=False)
                for decorator in methods[name].decorator_list
            ),
        )
        for name in method_names
    }


def _annotated_class_fields(
    tree: ast.Module,
    *,
    class_name: str,
) -> tuple[tuple[str, str, str | None], ...]:
    class_node = _class_node(tree, class_name)
    result = []
    for node in class_node.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(
            node.target,
            ast.Name,
        ):
            continue
        result.append(
            (
                node.target.id,
                ast.dump(node.annotation, include_attributes=False),
                (
                    ast.dump(node.value, include_attributes=False)
                    if node.value is not None
                    else None
                ),
            )
        )
    return tuple(result)


def _import_contract(tree: ast.Module) -> tuple[str, ...]:
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(
                f"import:{alias.name}:{alias.asname or ''}"
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            imports.extend(
                (
                    f"from:{node.level}:{node.module or ''}:"
                    f"{alias.name}:{alias.asname or ''}"
                )
                for alias in node.names
            )
    return tuple(imports)


def _valve_fields(tree: ast.Module) -> tuple[str, ...]:
    fields = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Valves":
            continue
        for member in node.body:
            if isinstance(member, ast.AnnAssign) and isinstance(
                member.target,
                ast.Name,
            ):
                fields.append(member.target.id)
            elif isinstance(member, ast.Assign):
                fields.extend(
                    target.id
                    for target in member.targets
                    if isinstance(target, ast.Name)
                )
    return tuple(fields)


def _load_bundle_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "goal17_bundle_builder_architecture_test",
        BUNDLE_BUILDER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _literal_assignment(tree: ast.Module, name: str) -> Any:
    matches = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    ]
    assert len(matches) == 1, name
    return ast.literal_eval(matches[0])
