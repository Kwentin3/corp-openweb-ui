from __future__ import annotations

import ast
import unittest
from pathlib import Path

from broker_reports_gate1.architecture_policy import (
    ARCHITECTURE_AUTHORITY,
    CANONICAL_PROMOTION_AUTHORITY,
    COMPONENT_RUNTIME_STATUSES,
    GATE1_INTERMEDIATE_LIFETIME,
    GATE1_PRIVATE_REPRESENTATION_AUTHORITY,
    GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED,
    KNOWLEDGE_RAG_VECTORIZATION_ALLOWED,
    LOCAL_OCR_WORKER_POOL_ALLOWED,
    LOCAL_OCR_PRODUCTION_ALLOWED,
    MODEL_CANONICAL_AUTHORITY,
    NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED,
    PROVIDER_OUTPUT_AUTHORITY,
    WORKLOAD_ADMISSION,
    WORKLOAD_AUTHORITY,
    WORKLOAD_PRIMARY_WALL_TIMEOUT,
    VISUAL_RECOVERY_INPUT_SCOPES,
    VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES,
    WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (
    SEMANTIC_CHOICE_OUTPUT_FIELDS,
    _choice_schema,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    COMPATIBILITY_WRAPPER_DELEGATES_ONLY,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "broker_reports_gate1"
REPOSITORY_ROOT = ROOT.parents[1]
ARCHITECTURE_DOCUMENT = REPOSITORY_ROOT / ARCHITECTURE_AUTHORITY
OPENWEBUI_ACTIONS = ROOT / "openwebui_actions"
GENERATED_BUNDLES = (
    OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe_bundled.py",
    OPENWEBUI_ACTIONS / "broker_reports_gate2_source_fact_pipe_bundled.py",
    OPENWEBUI_ACTIONS / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)

GATE2_MODULES = {
    path.stem for path in PACKAGE.glob("gate2_*.py") if path.stem != "gate2_handoff"
} | {"gate3_context_manifest"}
GATE1_PRIVATE_IMPLEMENTATIONS = {
    "csv_profile",
    "bounded_graph",
    "document_memory",
    "full_source",
    "pdf_layout_units",
    "pdf_text_layer",
    "source_provenance",
    "table_projection",
    "visual_table_review_contracts",
}
PLATFORM_IMPLEMENTATIONS = {"artifact_store"}
PROVIDER_TRANSPORT_MODULES = {"gate2_model_clients", "gate2_provider_adapters"}
GATE2_BUSINESS_RUNTIME_MODULES = {
    "gate2_candidate_binding",
    "gate2_candidate_binding_runtime",
    "gate2_domain_finalization",
    "gate2_domain_packages",
    "gate2_domain_routing",
    "gate2_domain_runtime",
    "gate2_input_readiness",
    "gate2_source_fact_runtime",
    "gate2_source_fact_stitching",
    "gate2_source_fact_validation",
    "gate2_source_unit_segmentation",
    "gate2_table_packages",
    "gate3_context_manifest",
}
GATE3_FINANCIAL_DOMAIN_SUCCESSOR = "gate3_financial_domain_context"


class BrokerReportsGateArchitectureTest(unittest.TestCase):
    def test_canonical_architecture_contains_runtime_authority_markers(self):
        authority = ARCHITECTURE_DOCUMENT.read_text(encoding="utf-8")
        required = {
            "separate controlled source-processing pipeline",
            "Knowledge, RAG, embeddings or vectorization",
            "Production visual-table provider profiles are exactly `google_gemini` and",
            "`openai_gpt`",
            "whole-document provider upload is",
            "PaddleOCR, PaddleOCR-VL",
            "MODEL_CANONICAL_AUTHORITY:",
            "BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md",
            "ArtifactResolver",
            "Gate1BoundedGraphFactory.create",
            "Run-wide decoded private graphs",
            "WorkloadAuthorityFactory.create",
            "Gate 1 heavy work at concurrency 1",
            "maximum concurrency 2",
            "worker_lease_expired",
        }
        self.assertEqual(
            sorted(marker for marker in required if marker not in authority),
            [],
        )

    def test_machine_readable_policy_is_fail_closed(self):
        self.assertFalse(NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED)
        self.assertFalse(KNOWLEDGE_RAG_VECTORIZATION_ALLOWED)
        self.assertEqual(
            VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES,
            frozenset({"google_gemini", "openai_gpt"}),
        )
        self.assertEqual(
            VISUAL_RECOVERY_INPUT_SCOPES,
            frozenset({"declared_page", "table_crop"}),
        )
        self.assertFalse(WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED)
        self.assertFalse(LOCAL_OCR_PRODUCTION_ALLOWED)
        self.assertFalse(LOCAL_OCR_WORKER_POOL_ALLOWED)
        self.assertEqual(PROVIDER_OUTPUT_AUTHORITY, "semantic_transcription_only")
        self.assertEqual(
            CANONICAL_PROMOTION_AUTHORITY,
            "deterministic_validator_for_accepted_profile_else_review_or_fail_closed",
        )
        self.assertEqual(MODEL_CANONICAL_AUTHORITY, 0)
        self.assertFalse(GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED)
        self.assertEqual(
            GATE1_INTERMEDIATE_LIFETIME,
            "one_document_then_seal_persist_release",
        )
        self.assertEqual(
            GATE1_PRIVATE_REPRESENTATION_AUTHORITY,
            "artifactstore_resolver_only",
        )
        self.assertEqual(
            COMPONENT_RUNTIME_STATUSES["gate1_bounded_graph"],
            "maintained",
        )
        self.assertEqual(COMPONENT_RUNTIME_STATUSES["workload_authority"], "maintained")
        self.assertEqual(WORKLOAD_AUTHORITY, "sqlite_cross_process_single_authority")
        self.assertEqual(WORKLOAD_ADMISSION, "capacity_queue_plus_worker_lease")
        self.assertIsNone(WORKLOAD_PRIMARY_WALL_TIMEOUT)

    def test_production_pipes_use_one_persisted_workload_factory_without_local_queues(self):
        pipe_paths = (
            OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe.py",
            OPENWEBUI_ACTIONS / "broker_reports_gate2_source_fact_pipe.py",
            OPENWEBUI_ACTIONS / "broker_reports_gate2_domain_source_fact_pipe.py",
        )
        violations = []
        for path in pipe_paths:
            source = path.read_text(encoding="utf-8")
            if "WorkloadAuthorityFactory(" not in source:
                violations.append(f"{path.name}:factory_missing")
            if "wait_for_admission(" not in source:
                violations.append(f"{path.name}:admission_missing")
            for forbidden in (
                "asyncio.Semaphore(",
                "ThreadPoolExecutor(",
                "ProcessPoolExecutor(",
                "workload_admission.py",
            ):
                if forbidden in source:
                    violations.append(f"{path.name}:{forbidden}")
            if "gate2_" in path.name and "_assert_gate1_workload_completed(" not in source:
                violations.append(f"{path.name}:gate1_completion_gate_missing")
        self.assertEqual(violations, [])

    def test_production_python_has_no_heavy_local_ocr_import(self):
        forbidden_roots = {"paddle", "paddleocr", "easyocr", "torch"}
        violations = []
        for root in (PACKAGE, OPENWEBUI_ACTIONS):
            for path in sorted(root.glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports = {alias.name.split(".", 1)[0] for alias in node.names}
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports = {node.module.split(".", 1)[0]}
                    else:
                        continue
                    for name in sorted(imports & forbidden_roots):
                        violations.append(f"{path.name}:{name}")
        self.assertEqual(violations, [])

    def test_visual_components_are_explicitly_classified(self):
        expected = {
            "visual_table_vlm": "maintained_qualified_default_on",
            "visual_neutral_tables": "maintained_qualified_default_on",
            "visual_review_boundary": "maintained_default_off",
            "visual_recovery_handoff": "maintained_qualified_default_on",
            "pdf_csv_experiment_provider": "proof_only",
            "pdf_grid_experiment_provider": "proof_only",
            "pdf_hybrid_provider": "proof_only",
            "pdf_dual_vlm_fact_providers": "maintained_qualified_default_on",
            "pdf_dual_vlm_canonical_table": "maintained_default_off",
            "pdf_dual_vlm_runtime": "maintained_qualified_default_on",
            "prove_visual_neutral_tables_actual_corpus": "offline_only",
        }
        self.assertEqual(
            {key: COMPONENT_RUNTIME_STATUSES.get(key) for key in expected},
            expected,
        )

    def test_gate2_imports_gate1_only_through_public_contract_surface(self):
        violations = []
        for module_name in sorted(GATE2_MODULES):
            for imported in _local_imports(module_name):
                if imported in GATE1_PRIVATE_IMPLEMENTATIONS:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_gate2_does_not_import_or_call_store_implementation_reads(self):
        violations = []
        forbidden_calls = (
            ".get_record_unchecked(",
            ".list_by_run(",
            ".read_payload(",
        )
        for module_name in sorted(GATE2_MODULES):
            source = _source(module_name)
            for imported in _local_imports(module_name):
                if imported in PLATFORM_IMPLEMENTATIONS:
                    violations.append(f"{module_name}->{imported}")
            for marker in forbidden_calls:
                if marker in source:
                    violations.append(f"{module_name}:{marker}")
        self.assertEqual(violations, [])

    def test_gate1_has_no_reverse_dependency_on_gate2_business_runtime(self):
        allowed_compatibility_edge = ("table_projection", "gate2_table_packages")
        violations = []
        for path in sorted(PACKAGE.glob("*.py")):
            module_name = path.stem
            if module_name in GATE2_MODULES or module_name in {
                "__init__",
                "artifact_lifecycle",
                "artifact_models",
                "artifact_resolver",
                "artifact_retention",
                "artifact_store",
            }:
                continue
            for imported in _local_imports(module_name):
                edge = (module_name, imported)
                if (
                    imported in GATE2_BUSINESS_RUNTIME_MODULES
                    and edge != allowed_compatibility_edge
                ):
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_provider_transport_does_not_import_gate2_business_runtime(self):
        violations = []
        for module_name in sorted(PROVIDER_TRANSPORT_MODULES):
            for imported in _local_imports(module_name):
                if imported in GATE2_BUSINESS_RUNTIME_MODULES:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_qualification_and_evidence_reuse_canonical_request_builder(self):
        qualification = "gate2_financial_semantic_v6_qualification_run"
        evidence = "gate2_financial_semantic_v6_evidence"

        self.assertNotIn("gate2_model_requests", _local_imports(qualification))
        self.assertEqual(
            _call_owners(evidence, "Gate2OpenWebUIRequestBuilder"),
            {"financial_semantic_v6_canonical_request"},
        )
        self.assertEqual(
            _call_owners(
                qualification,
                "financial_semantic_v6_canonical_request",
            ),
            {"qualify_financial_semantic_v6"},
        )

    def test_qualification_does_not_parse_provider_specific_fields(self):
        module_name = "gate2_financial_semantic_v6_qualification_run"
        forbidden_payload_fields = {
            "choices",
            "prompt_tokens",
            "completion_tokens",
            "input_tokens_details",
            "output_tokens_details",
        }

        self.assertNotIn(
            "gate2_provider_adapters",
            _local_imports(module_name),
        )
        self.assertEqual(
            _string_constants(_tree(module_name)) & forbidden_payload_fields,
            set(),
        )

    def test_compatibility_request_entrypoint_delegates_only(self):
        wrapper = _function_node(
            _tree("gate2_financial_semantic_v6_evidence"),
            "financial_semantic_v6_canonical_request",
        )

        self.assertTrue(COMPATIBILITY_WRAPPER_DELEGATES_ONLY)
        self.assertEqual(
            _call_names(wrapper) & {"Gate2OpenWebUIRequestBuilder"},
            {"Gate2OpenWebUIRequestBuilder"},
        )
        self.assertFalse(
            any(isinstance(node, ast.Dict) for node in ast.walk(wrapper))
        )

    def test_candidate_compiler_has_no_financial_type_ids_or_regex(self):
        module_name = "gate2_financial_semantic_v6_candidate_compiler"
        tree = _tree(module_name)
        registry = Gate2FinancialEvidenceRegistryFactory().create()
        known_type_ids = set(registry.provider_type_enum())
        imported_roots = {
            name
            for node in ast.walk(tree)
            for name in _import_roots(node)
        }

        self.assertEqual(_string_constants(tree) & known_type_ids, set())
        self.assertNotIn("re", imported_roots)
        self.assertEqual(
            {
                name
                for name in _call_names(tree)
                if name in {"compile", "match", "search", "fullmatch"}
            },
            set(),
        )

    def test_model_choice_schema_contains_only_minimal_choice_fields(self):
        schema = _choice_schema(("opaque_typed_option",))
        variants = schema["anyOf"]
        observed_fields = {
            field
            for variant in variants
            for field in variant["properties"]
        }

        self.assertEqual(
            observed_fields,
            set(SEMANTIC_CHOICE_OUTPUT_FIELDS),
        )
        self.assertTrue(
            all(variant["additionalProperties"] is False for variant in variants)
        )
        self.assertTrue(
            observed_fields.isdisjoint(
                {
                    "source_ref",
                    "source_value_ref",
                    "role_bindings",
                    "value_bindings",
                    "provenance",
                    "retention",
                }
            )
        )

    def test_generated_bundle_modules_match_maintained_source(self):
        mismatches = []
        for bundle_path in GENERATED_BUNDLES:
            modules = _bundled_modules(bundle_path)
            for module_name, bundled_source in modules.items():
                if module_name == "__init__":
                    continue
                if bundled_source != _source(module_name):
                    mismatches.append(f"{bundle_path.name}:{module_name}")
        self.assertEqual(mismatches, [])

    def test_model_client_uses_one_budget_admission_authority(self):
        factory_callers = {
            module_name
            for path in PACKAGE.glob("*.py")
            for module_name in (path.stem,)
            if _call_owners(
                module_name,
                "Gate2EconomyBudgetSessionFactory",
            )
        }
        extract = _method_node(
            _tree("gate2_model_clients"),
            "Gate2OpenWebUIStructuredModelClient",
            "extract",
        )
        admission_lines = _call_lines(extract, "prepare_call")
        transport_lines = (
            _call_lines(extract, "invoke_native_once")
            + _call_lines(extract, "_invoke_completion_once")
        )

        self.assertEqual(
            factory_callers,
            {
                "gate2_financial_semantic_v5_qualification",
                "gate2_financial_semantic_v6_qualification",
                "gate2_model_clients",
            },
        )
        self.assertTrue(
            all(
                "gate2_economy_budget" in _local_imports(module_name)
                for module_name in factory_callers
            )
        )
        self.assertEqual(
            _call_owners(
                "gate2_model_clients",
                "Gate2EconomyBudgetSessionFactory",
            ),
            {"Gate2StructuredModelClientFactory.create"},
        )
        self.assertEqual(len(admission_lines), 1)
        self.assertTrue(transport_lines)
        self.assertLess(admission_lines[0], min(transport_lines))

    def test_unclassified_retention_is_code_owned(self):
        tree = _tree("gate2_financial_semantic_v6_expansion")
        expand = _method_node(
            tree,
            "Gate2FinancialSemanticV6DecisionExpansionFactory",
            "_expand",
        )
        unclassified = _function_node(
            tree,
            "_unclassified_canonical_choice",
        )

        self.assertIn(
            "evidence_bundle.retention_set",
            _attribute_paths(expand),
        )
        self.assertNotIn(
            "model_output",
            {arg.arg for arg in unclassified.args.kwonlyargs},
        )
        self.assertEqual(
            set(SEMANTIC_CHOICE_OUTPUT_FIELDS)
            & {"retention", "source_refs", "value_bindings"},
            set(),
        )

    def test_validated_decision_uses_canonical_materialization_totality(self):
        tree = _tree("gate2_financial_semantic_v6_totality")
        materialize = _method_node(
            tree,
            "Gate2FinancialSemanticV6TotalMaterializerFactory",
            "_materialize",
        )

        self.assertIn(
            "gate2_financial_evidence_materialization",
            _local_imports("gate2_financial_semantic_v6_totality"),
        )
        self.assertIn(
            "Gate2FinancialEvidenceMaterializerFactory",
            _call_names(materialize),
        )
        self.assertIn("materialize", _call_names(materialize))
        self.assertIn(
            "financial_semantic_v6_validated_but_unmaterializable",
            _string_constants(materialize),
        )

    def test_artifact_store_and_gate2_runs_are_append_only_by_construction(self):
        store_source = _source("artifact_store")
        runtime_sources = "\n".join(
            _source(module_name)
            for module_name in ("gate2_source_fact_runtime", "gate2_domain_runtime")
        )

        self.assertNotIn("INSERT OR REPLACE", store_source.upper())
        self.assertIn("artifact_immutable", store_source)
        self.assertNotIn("_replace_run_record", runtime_sources)
        self.assertIn("_persist_terminal_run_record", runtime_sources)

    def test_gate3_business_runtime_uses_declared_context_boundary(self):
        gate3_business_modules = {
            path.stem
            for path in PACKAGE.glob("gate3_*.py")
            if path.stem != "gate3_context_manifest"
        }
        violations = []
        for module_name in sorted(gate3_business_modules):
            imports = _local_imports(module_name)
            if module_name == GATE3_FINANCIAL_DOMAIN_SUCCESSOR:
                if "gate2_financial_domain_query" not in imports:
                    violations.append(
                        f"{module_name}:financial_domain_boundary_missing"
                    )
                if "gate3_context_manifest" in imports:
                    violations.append(
                        f"{module_name}:legacy_manifest_boundary_present"
                    )
                forbidden_successor_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "gate1_public_contracts",
                    "gate2_financial_domain_catalog",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_successor_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif "gate3_context_manifest" not in imports:
                violations.append(f"{module_name}:manifest_boundary_missing")
            if imports & GATE1_PRIVATE_IMPLEMENTATIONS:
                violations.append(f"{module_name}:gate1_private_import")
        self.assertEqual(violations, [])


def _source(module_name: str) -> str:
    return (PACKAGE / f"{module_name}.py").read_text(encoding="utf-8")


def _tree(module_name: str) -> ast.Module:
    return ast.parse(_source(module_name))


def _local_imports(module_name: str) -> set[str]:
    tree = _tree(module_name)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        if node.module:
            imports.add(node.module.split(".", 1)[0])
        else:
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
    return imports


def _import_roots(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".", 1)[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.module:
        return {node.module.split(".", 1)[0]}
    return set()


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_names(node: ast.AST) -> set[str]:
    return {
        name
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        for name in (_call_name(item.func),)
        if name is not None
    }


def _call_lines(node: ast.AST, target: str) -> list[int]:
    return sorted(
        item.lineno
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and _call_name(item.func) == target
    )


def _call_owners(module_name: str, target: str) -> set[str]:
    owners = set()
    for node in _tree(module_name).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if target in _call_names(node):
                owners.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if not isinstance(
                    method,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue
                if target in _call_names(method):
                    owners.add(f"{node.name}.{method.name}")
    return owners


def _function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function_missing:{name}")


def _method_node(
    tree: ast.Module,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for method in node.body:
            if isinstance(
                method,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and method.name == method_name:
                return method
    raise AssertionError(f"method_missing:{class_name}.{method_name}")


def _string_constants(node: ast.AST) -> set[str]:
    return {
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant)
        and isinstance(item.value, str)
    }


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if not isinstance(node, ast.Attribute):
        return None
    parent = _attribute_path(node.value)
    return f"{parent}.{node.attr}" if parent else node.attr


def _attribute_paths(node: ast.AST) -> set[str]:
    return {
        path
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        for path in (_attribute_path(item),)
        if path is not None
    }


def _bundled_modules(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name)
            and target.id == "_BUNDLED_MODULES"
            for target in node.targets
        ):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, dict) or any(
            not isinstance(key, str) or not isinstance(source, str)
            for key, source in value.items()
        ):
            raise AssertionError(f"bundled_modules_invalid:{path.name}")
        return value
    raise AssertionError(f"bundled_modules_missing:{path.name}")


if __name__ == "__main__":
    unittest.main()
