from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "broker_reports_gate1"

GATE2_MODULES = {
    path.stem
    for path in PACKAGE.glob("gate2_*.py")
    if path.stem != "gate2_handoff"
} | {"gate3_context_manifest"}
GATE1_PRIVATE_IMPLEMENTATIONS = {
    "csv_profile",
    "document_memory",
    "full_source",
    "pdf_layout_units",
    "pdf_text_layer",
    "source_provenance",
    "table_projection",
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


class BrokerReportsGateArchitectureTest(unittest.TestCase):
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
                if imported in GATE2_BUSINESS_RUNTIME_MODULES and edge != allowed_compatibility_edge:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_provider_transport_does_not_import_gate2_business_runtime(self):
        violations = []
        for module_name in sorted(PROVIDER_TRANSPORT_MODULES):
            for imported in _local_imports(module_name):
                if imported in GATE2_BUSINESS_RUNTIME_MODULES:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

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

    def test_gate3_business_runtime_has_not_bypassed_manifest_boundary(self):
        gate3_business_modules = {
            path.stem
            for path in PACKAGE.glob("gate3_*.py")
            if path.stem != "gate3_context_manifest"
        }
        violations = []
        for module_name in sorted(gate3_business_modules):
            imports = _local_imports(module_name)
            if "gate3_context_manifest" not in imports:
                violations.append(f"{module_name}:manifest_boundary_missing")
            if imports & GATE1_PRIVATE_IMPLEMENTATIONS:
                violations.append(f"{module_name}:gate1_private_import")
        self.assertEqual(violations, [])


def _source(module_name: str) -> str:
    return (PACKAGE / f"{module_name}.py").read_text(encoding="utf-8")


def _local_imports(module_name: str) -> set[str]:
    tree = ast.parse(_source(module_name))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        if node.module:
            imports.add(node.module.split(".", 1)[0])
        else:
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
    return imports


if __name__ == "__main__":
    unittest.main()
