from __future__ import annotations

import ast
import argparse
import base64
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
PIPE_SOURCE = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe.py"
BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
GATE2_PIPE_SOURCE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe.py"
)
GATE2_BUNDLE_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
GATE2_DOMAIN_PIPE_SOURCE = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe.py"
)
GATE2_DOMAIN_BUNDLE_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)

BUNDLE_ADAPTER_MARKER = "# Begin maintainable source adapter:"
GATE1_RESOURCE_NAMES = (
    "gate3_financial_label_dictionary.v1.json",
    "gate3_financial_label_dictionary.v2.json",
    "gate3_financial_label_dictionary.v2_0_1.json",
    "gate3_financial_label_dictionary.v2_1.json",
    "gate3_financial_role_pack.v1.json",
    "gate3_financial_role_pack.v2.json",
    "gate3_financial_role_pack.v3.json",
    "gate3_financial_role_pack.v3_1.json",
    "gate3_financial_role_pack.v4.json",
    "gate3_labeling_response.v1.schema.json",
    "gate3_predeclared_assertion_labeling_response.v1.schema.json",
    "gate3_role_labeling_response.v1.schema.json",
    "gate5_declaration_projection_evidence.ru_3ndfl_2025_appendix8.v0.json",
    "gate5_declaration_projection_evidence.ru_3ndfl_2025_section2.v1.json",
    "gate5_declaration_projection_spec.ru_3ndfl_2025_appendix8.v0.json",
    "gate5_declaration_projection_spec.ru_3ndfl_2025_section2.v1.json",
    "gate5_full_declaration_definition_authoring.primary.v1.payload.json",
    "gate5_full_declaration_definition_candidate.g528b.json",
    "gate5_full_declaration_definition_review.g528b.json",
    "gate5_full_declaration_obligations.ru_3ndfl_2025.v1.json",
    "gate5_consumer_first_xml_projection.ru_3ndfl_2025.v0.json",
    "gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json",
    "gate5_full_target_xml_schema.NO_NDFL3_1_033_00_05_20_01.xsd.b64",
    "gate5_openwebui_product_definition.v0.json",
    "gate5_tax_methodology.ru_3ndfl_2025_declaration_input_contract.v3.json",
    "gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v0.json",
    "gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v1.json",
    "gate5_tax_methodology.ru_ordinary_trade_declaration_product.v1.json",
    "gate5_tax_methodology.ru_ndfl_securities_income_group_tax_base_proof.v0.json",
    "gate5_tax_methodology.ru_ndfl_securities_operation_tax_model_proof.v0.json",
    "gate5_tax_methodology.ru_ndfl_securities_proof.v0.json",
    "gate5_tax_methodology.ru_ndfl_securities_real_source_fact_contract.v0.json",
    "gate5_tax_methodology.ru_ndfl_securities_real_source_fact_contract.v2.json",
    "gate5_tax_methodology.ru_ndfl_securities_source_fact_consumption_proof.v0.json",
    "gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json",
)

MODULE_ORDER = [
    "contracts",
    "pdf_table_locator",
    "architecture_policy",
    "workload_authority",
    "source_provenance",
    "broker_pdf_neutral_tables",
    "blockers",
    "file_processing_outcomes",
    "inputs",
    "archive_intake",
    "detectors",
    "csv_profile",
    "profilers_csv_txt",
    "profilers_docx",
    "profilers_image",
    "profilers_pdf",
    "profilers_xlsx",
    "xml_source",
    "profilers_xml",
    "profilers_zip",
    "pdf_source_bound_grid",
    "pdf_layout",
    "pdf_layout_units",
    "pdf_text_layer",
    "pdf_source_bound_table_assembler",
    "table_projection",
    "pdf_visual_memory",
    "full_source",
    "canonical_artifact",
    "artifact_models",
    "artifact_lifecycle",
    "artifact_retention",
    "artifact_store",
    "bounded_graph",
    "pdf_compact_canonical",
    "pdf_compact_gate2_adapter",
    "pdf_normalization_acceptance",
    "taxonomy",
    "criticality",
    "eligibility",
    "document_memory",
    "domain_ingestion",
    "validators",
    "clarification",
    "artifact_resolver",
    "canonical_store",
    "gate1_public_contracts",
    "gate2_source_fact_contracts",
    "gate2_fns_2ndfl_contracts",
    "gate2_fns_2ndfl_adapter",
    "gate2_fns_2ndfl_parity",
    "gate2_table_packages",
    "gate2_input_readiness",
    "gate2_model_contracts",
    "gate2_model_requests",
    "gate2_economy_model_policy",
    "gate2_economy_workload_policy",
    "gate2_economy_provider_selection",
    "gate2_economy_budget",
    "gate2_provider_adapters",
    "gate2_model_clients",
    "gate2_domain_routing",
    "gate2_candidate_binding",
    "gate2_candidate_binding_runtime",
    "gate2_llm_context",
    "gate2_domain_packages",
    "gate2_source_unit_segmentation",
    "gate2_domain_contracts",
    "gate2_domain_finalization",
    "gate2_source_fact_selection",
    "gate2_source_fact_validation",
    "gate2_source_fact_runtime",
    "gate2_source_fact_stitching",
    "answer_context_selection",
    "gate3_context_manifest",
    "gate2_domain_runtime",
    "gate2_handoff",
    "compact_report",
    "safe_report",
    "document_passport",
    "normalizer",
    "__init__",
]

GATE1_PDF_TABLE_MODULES = [
    "private_intake_bytes",
    "pdf_table_raster",
    "pdf_table_locator_provider",
    "pdf_table_intake_runtime",
]

_GATE1_PDF_TABLE_INSERT_AT = MODULE_ORDER.index("gate2_provider_adapters") + 1
GATE1_MODULE_ORDER = [
    *MODULE_ORDER[:_GATE1_PDF_TABLE_INSERT_AT],
    *GATE1_PDF_TABLE_MODULES,
    *MODULE_ORDER[_GATE1_PDF_TABLE_INSERT_AT:],
]
GATE1_NDFL_GATE3_MODULES = [
    "gate3_financial_label_dictionary",
    "gate3_financial_role_pack",
    "gate3_evidence_demand_port",
    "gate3_projection",
    "gate3_structural_chunking",
    "gate3_bounded_labeling",
    "gate3_role_labeling",
    "gate3_chunk_batch_labeling",
    "gate3_financial_annotations_persistence",
    "gate3_ndfl_case_readiness",
    "gate3_metadata_source_facts",
    "gate4_financial_case_materialization",
    "gate4_financial_case_cache",
    "gate3_ndfl_workflow",
]
GATE1_GATE5_MODULES = [
    "gate5_evidence_demand",
    "gate5_methodology_selection",
    "gate5_supplemental_fact",
    "gate5_combined_requirement_check",
    "gate5_declaration_filing_context",
    "declaration_semantics",
    "gate5_declaration_projection",
    "gate5_supplemental_fact_discovery",
    "gate5_methodology_calculation",
    "gate5_trusted_methodology",
    "gate5_residency_evidence",
    "gate5_deterministic_source_fact_consumption",
    "gate5_securities_disposal_tax_model",
    "gate5_tax_period_category_aggregation",
    "gate5_income_group_tax_base",
    "gate5_declaration_tax_settlement",
    "gate5_declaration_budget_outcome",
    "gate5_declaration_financial_investment_results",
    "gate5_declaration_income_sources",
    "gate5_declaration_right_side_assembly",
    "gate5_full_declaration_definition",
    "gate5_real_tax_case_assembly",
    "gate5_declaration_scope_resolution",
    "gate5_resolved_declaration_package",
    "gate5_declaration_semantic_input",
    "gate5_full_target_xml_projection",
    "gate5_evidence_intake",
    "gate5_client_evidence_review",
    "gate5_human_gap_closure",
    "gate5_declaration_preparation",
]
_GATE1_NDFL_GATE3_INSERT_AT = GATE1_MODULE_ORDER.index("gate3_context_manifest") + 1
GATE1_MODULE_ORDER = [
    *GATE1_MODULE_ORDER[:_GATE1_NDFL_GATE3_INSERT_AT],
    *GATE1_NDFL_GATE3_MODULES,
    *GATE1_MODULE_ORDER[_GATE1_NDFL_GATE3_INSERT_AT:],
]
_GATE1_GATE5_INSERT_AT = GATE1_MODULE_ORDER.index("normalizer") + 1
GATE1_MODULE_ORDER = [
    *GATE1_MODULE_ORDER[:_GATE1_GATE5_INSERT_AT],
    *GATE1_GATE5_MODULES,
    *GATE1_MODULE_ORDER[_GATE1_GATE5_INSERT_AT:],
]
GATE1_ORDINARY_TRADE_MODULES = [
    "ordinary_trade_semantic_compiler",
    "ordinary_trade_qualified_mappings",
    "ordinary_trade_semantic_mapping",
    "ordinary_trade_mapping_case",
    "ordinary_trade_projection",
    "ordinary_trade_mapping_runtime",
    "gate4_ordinary_trade_candidate",
    "ordinary_trade_candidate_runtime",
    "authenticated_case_taxpayer_binding",
    "ordinary_trade_tax_model_bridge",
    "active_category_declaration_assembly",
    "ordinary_trade_declaration_chat_adapter",
    "ordinary_trade_declaration_case_inputs",
    "ordinary_trade_declaration_mvp",
    "ordinary_trade_production_runtime",
]
_GATE1_ORDINARY_TRADE_INSERT_AT = (
    GATE1_MODULE_ORDER.index("gate5_declaration_preparation") + 1
)
GATE1_MODULE_ORDER = [
    *GATE1_MODULE_ORDER[:_GATE1_ORDINARY_TRADE_INSERT_AT],
    *GATE1_ORDINARY_TRADE_MODULES,
    *GATE1_MODULE_ORDER[_GATE1_ORDINARY_TRADE_INSERT_AT:],
]
GATE2_ONLY_MODULES = ["gate2_chat_dcp_resolution"]
GATE2_MODULE_ORDER = [
    name for name in MODULE_ORDER if name != "gate2_handoff"
] + GATE2_ONLY_MODULES
GATE2_FINANCIAL_MODULES = [
    "gate2_financial_evidence_registry",
    "gate2_financial_evidence_catalog",
    "gate2_financial_semantic_model_assets",
    "gate2_financial_semantic_contract",
    "gate2_financial_evidence_decision",
    "gate2_financial_evidence_materialization_contracts",
    "gate2_financial_evidence_source_package",
    "gate2_financial_evidence_materialization_validation",
    "gate2_financial_evidence_materialization",
    "gate2_financial_context_contracts",
    "gate2_financial_context_validation",
    "gate2_financial_context",
    "gate2_financial_domain_contracts",
    "gate2_financial_domain_projection",
    "gate2_financial_domain_validation",
    "gate2_financial_domain_catalog",
    "gate2_financial_domain_query",
    "gate2_financial_evidence_legacy_validation",
    "gate2_financial_evidence_compatibility",
    "gate2_financial_evidence_production_runtime",
]
_GATE2_FINANCIAL_INSERT_AT = GATE2_MODULE_ORDER.index("gate2_model_clients") + 1
GATE2_DOMAIN_MODULE_ORDER = [
    *GATE2_MODULE_ORDER[:_GATE2_FINANCIAL_INSERT_AT],
    *GATE2_FINANCIAL_MODULES,
    *GATE2_MODULE_ORDER[_GATE2_FINANCIAL_INSERT_AT:],
]
GATE2_SUCCESSOR_MODULES = [
    "gate2_financial_evidence_source_context",
    "gate2_financial_evidence_typed_admission",
    "gate2_deterministic_financial_scopes",
    "gate2_financial_evidence_successor_projection",
    "gate2_financial_evidence_successor",
    "gate2_successor_artifacts",
    "gate2_successor_artifacts_v2",
    "gate2_successor_compatibility",
]
_GATE2_SUCCESSOR_INSERT_AT = (
    GATE2_DOMAIN_MODULE_ORDER.index("gate2_source_unit_segmentation") + 1
)
GATE2_DOMAIN_MODULE_ORDER = [
    *GATE2_DOMAIN_MODULE_ORDER[:_GATE2_SUCCESSOR_INSERT_AT],
    *GATE2_SUCCESSOR_MODULES,
    *GATE2_DOMAIN_MODULE_ORDER[_GATE2_SUCCESSOR_INSERT_AT:],
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=("all", "gate1", "gate2", "gate2-domain"),
        default="all",
    )
    target = parser.parse_args().target
    modules = {
        name: (PACKAGE_ROOT / f"{name}.py").read_text(encoding="utf-8")
        for name in sorted(
            set(MODULE_ORDER)
            | set(GATE1_PDF_TABLE_MODULES)
            | set(GATE1_NDFL_GATE3_MODULES)
            | set(GATE1_GATE5_MODULES)
            | set(GATE1_ORDINARY_TRADE_MODULES)
            | set(GATE2_ONLY_MODULES)
            | set(GATE2_FINANCIAL_MODULES)
            | set(GATE2_SUCCESSOR_MODULES)
        )
    }
    if target in {"all", "gate1"}:
        pipe_source = _strip_openwebui_metadata(PIPE_SOURCE.read_text(encoding="utf-8"))
        gate1_modules = {name: modules[name] for name in GATE1_MODULE_ORDER}
        gate1_modules["__init__"] = _project_package_init(
            gate1_modules["__init__"],
            included_modules=set(gate1_modules),
        )
        bundle = _render_bundle(
            modules=gate1_modules,
            resources={
                name: base64.b64encode(
                    _canonical_resource_bytes(PACKAGE_ROOT / name)
                ).decode("ascii")
                for name in GATE1_RESOURCE_NAMES
            },
            pipe_source=pipe_source,
            title="Broker Reports Gate 1 Pipe Backend Normalizer",
            version="0.39.0-ordinary-trade-production-bundled",
            package_version="gate1_ordinary_trade_production_v9",
            source_label="openwebui_actions/broker_reports_gate1_pipe.py",
            requirements="pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107,PyMuPDF==1.26.5,lxml==6.1.1",
        )
        BUNDLE_PATH.write_text(bundle, encoding="utf-8", newline="\n")
        print(str(BUNDLE_PATH))
    if target in {"all", "gate2"}:
        gate2_pipe_source = _strip_openwebui_metadata(
            GATE2_PIPE_SOURCE.read_text(encoding="utf-8")
        )
        gate2_modules = {name: modules[name] for name in GATE2_MODULE_ORDER}
        gate2_modules["__init__"] = _project_package_init(
            gate2_modules["__init__"], included_modules=set(gate2_modules)
        )
        gate2_bundle = _render_bundle(
            modules=gate2_modules,
            resources={},
            pipe_source=gate2_pipe_source,
            title="Broker Reports Gate 2 Source Fact Extraction",
            version="0.15.0-positional-coverage-v1-bundled",
            package_version="gate2_positional_coverage_v1",
            source_label="openwebui_actions/broker_reports_gate2_source_fact_pipe.py",
            requirements="pydantic",
        )
        GATE2_BUNDLE_PATH.write_text(gate2_bundle, encoding="utf-8", newline="\n")
        print(str(GATE2_BUNDLE_PATH))
    if target in {"all", "gate2-domain"}:
        gate2_domain_pipe_source = _strip_openwebui_metadata(
            GATE2_DOMAIN_PIPE_SOURCE.read_text(encoding="utf-8")
        )
        gate2_domain_modules = {
            name: modules[name] for name in GATE2_DOMAIN_MODULE_ORDER
        }
        gate2_domain_modules["__init__"] = _project_package_init(
            gate2_domain_modules["__init__"],
            included_modules=set(gate2_domain_modules),
        )
        gate2_domain_bundle = _render_bundle(
            modules=gate2_domain_modules,
            resources={},
            pipe_source=gate2_domain_pipe_source,
            title="Broker Reports Gate 2 Domain Source Fact Extraction",
            version="0.13.0-single-current-pipeline-bundled",
            package_version="gate2_domain_single_current_pipeline_v1",
            source_label="openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py",
            requirements="pydantic",
        )
        GATE2_DOMAIN_BUNDLE_PATH.write_text(
            gate2_domain_bundle, encoding="utf-8", newline="\n"
        )
        print(str(GATE2_DOMAIN_BUNDLE_PATH))


def _strip_openwebui_metadata(source: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    first_line = 0
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        first_line = tree.body[0].end_lineno or 0

    kept: list[str] = []
    for line in lines[first_line:]:
        if line.strip() == "from __future__ import annotations":
            continue
        kept.append(line)
    return "\n".join(kept).lstrip() + "\n"


def _project_package_init(
    source: str,
    *,
    included_modules: set[str],
) -> str:
    """Keep a closed-world package facade for the selected bundle."""

    tree = ast.parse(source)
    removed_exports: set[str] = set()
    dropped_lines: set[int] = set()

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        module_name = str(node.module or "").split(".", 1)[0]
        if not module_name or module_name in included_modules:
            continue
        removed_exports.update(alias.asname or alias.name for alias in node.names)
        dropped_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

    if not removed_exports:
        return source

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            raise RuntimeError("bundle_package_init_all_must_be_static")
        constants_by_line: dict[int, list[str]] = {}
        for item in node.value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                constants_by_line.setdefault(item.lineno, []).append(item.value)
        for item in node.value.elts:
            if not (
                isinstance(item, ast.Constant)
                and isinstance(item.value, str)
                and item.value in removed_exports
            ):
                continue
            if (
                item.end_lineno != item.lineno
                or len(constants_by_line[item.lineno]) != 1
            ):
                raise RuntimeError("bundle_package_init_all_entry_must_own_line")
            dropped_lines.add(item.lineno)

    projected = "".join(
        line
        for line_number, line in enumerate(source.splitlines(keepends=True), start=1)
        if line_number not in dropped_lines
    )
    ast.parse(projected)
    return projected


def assert_gate2_bundle_contract(
    bundle_source: str,
    *,
    runtime_factory: str,
) -> None:
    required_markers = {
        "bundled_modules": "_BUNDLED_MODULES",
        "model_contracts_module": '"gate2_model_contracts"',
        "model_requests_module": '"gate2_model_requests"',
        "economy_provider_selection_module": ('"gate2_economy_provider_selection"'),
        "economy_workload_policy_module": ('"gate2_economy_workload_policy"'),
        "provider_adapters_module": '"gate2_provider_adapters"',
        "model_clients_module": '"gate2_model_clients"',
        "csv_profile_module": '"csv_profile"',
        "gate3_context_manifest_module": '"gate3_context_manifest"',
        "answer_context_selection_module": '"answer_context_selection"',
        "csv_profile_factory": "CsvSupportedProfileFactory(",
        "csv_profile_factory_anchor": (
            "CsvSupportedProfileFactory.create is the only production "
            "supported-CSV parser entrypoint"
        ),
        "gate3_context_manifest_factory": "Gate3ContextManifestFactory(",
        "answer_context_selection_factory": "AnswerContextSelectionFactory(",
        "answer_context_selection_factory_anchor": (
            "AnswerContextSelectionFactory.create is the only production "
            "answer-context selection entrypoint"
        ),
        "gate3_context_manifest_factory_anchor": (
            "Gate3ContextManifestFactory.create is the only production Gate 3 "
            "context-manifest build and resolution entrypoint"
        ),
        "provider_adapter_factory": "Gate2ProviderAdapterFactory(",
        "anthropic_native_adapter": "Gate2AnthropicNativeMessagesAdapter",
        "native_transport_config": "Gate2NativeProviderTransportConfig(",
        "provider_adapter_factory_anchor": (
            "Gate2ProviderAdapterFactory.create is the only production Gate 2 "
            "provider adapter entrypoint"
        ),
        "model_client_factory": "Gate2StructuredModelClientFactory(",
        "model_client_config": "Gate2StructuredModelClientConfig(",
        "model_client_factory_anchor": (
            "Gate2StructuredModelClientFactory.create is the only production "
            "Gate 2 model client entrypoint"
        ),
        "economy_provider_selection_factory": ("Gate2EconomyProviderSelectionFactory("),
        "economy_provider_selection_factory_anchor": (
            "Gate2EconomyProviderSelectionFactory.create is the only production"
        ),
        "economy_workload_policy_factory": ("Gate2EconomyWorkloadPolicyFactory("),
        "economy_workload_policy_factory_anchor": (
            "Gate2EconomyWorkloadPolicyFactory.create is the only code-owned"
        ),
        "economy_budget_enforcement": "economy_budget_enforcement=True",
        "runtime_factory": runtime_factory,
        "source_adapter": BUNDLE_ADAPTER_MARKER,
    }
    if runtime_factory == "Gate2DomainSourceFactRuntimeFactory":
        required_markers.update(
            {
                "deterministic_financial_scopes_module": (
                    '"gate2_deterministic_financial_scopes"'
                ),
                "financial_successor_module": ('"gate2_financial_evidence_successor"'),
                "financial_semantic_model_assets_module": (
                    '"gate2_financial_semantic_model_assets"'
                ),
                "financial_semantic_model_assets_factory_anchor": (
                    "load_gate2_financial_semantic_model_assets is the only"
                ),
                "financial_semantic_contract_module": (
                    '"gate2_financial_semantic_contract"'
                ),
                "financial_semantic_contract_factory_anchor": (
                    "Gate2FinancialSemanticContractFactory.create is the only"
                ),
                "financial_domain_catalog_module": ('"gate2_financial_domain_catalog"'),
                "financial_domain_projection_module": (
                    '"gate2_financial_domain_projection"'
                ),
                "financial_domain_validation_module": (
                    '"gate2_financial_domain_validation"'
                ),
                "financial_domain_catalog_factory_anchor": (
                    "Gate2FinancialDomainCatalogFactory.create is the only"
                ),
                "financial_domain_query_module": ('"gate2_financial_domain_query"'),
                "financial_domain_query_factory_anchor": (
                    "Gate2FinancialDomainQueryFactory.create is the only"
                ),
                "financial_successor_factory_anchor": (
                    "Gate2FinancialEvidenceSuccessorRunnerFactory.create is the only"
                ),
            }
        )
    missing = sorted(
        label
        for label, marker in required_markers.items()
        if marker not in bundle_source
    )
    if missing:
        raise RuntimeError("gate2_bundle_contract_missing:" + ",".join(missing))

    source_adapter = bundle_source.split(BUNDLE_ADAPTER_MARKER, 1)[1]
    forbidden_markers = {
        "direct_openwebui_completion": "generate_chat_completion",
        "direct_anthropic_endpoint": "api.anthropic.com/v1/messages",
        "duplicate_completion_parser": "_completion_dict_content",
        "duplicate_provider_error_classifier": "_provider_error_code",
        "legacy_pipe_model_client": "class OpenWebUIGate2",
    }
    present = sorted(
        label for label, marker in forbidden_markers.items() if marker in source_adapter
    )
    if present:
        raise RuntimeError("gate2_bundle_contract_forbidden:" + ",".join(present))


def _render_bundle(
    *,
    modules: dict[str, str],
    resources: dict[str, str],
    pipe_source: str,
    title: str,
    version: str,
    package_version: str,
    source_label: str,
    requirements: str,
) -> str:
    modules_literal = json.dumps(modules, ensure_ascii=False, indent=2, sort_keys=True)
    resources_literal = json.dumps(
        resources, ensure_ascii=True, indent=2, sort_keys=True
    )
    order_literal = json.dumps(list(modules), ensure_ascii=True)
    return f'''"""
title: {title}
author: Alpha Soft
version: {version}
required_open_webui_version: 0.9.6
requirements: {requirements}
"""

from __future__ import annotations

import sys
import types
import base64
import importlib.abc
import importlib.machinery
import io


_BUNDLED_PACKAGE_NAME = "broker_reports_gate1"
_BUNDLED_PACKAGE_VERSION = "{package_version}"
_BUNDLED_MODULE_ORDER = {order_literal}
_BUNDLED_MODULES = {modules_literal}
_BUNDLED_RESOURCES = {resources_literal}


class _BundleResourceReader(importlib.abc.ResourceReader):
    def open_resource(self, resource):
        try:
            encoded = _BUNDLED_RESOURCES[resource]
        except KeyError as exc:
            raise FileNotFoundError(resource) from exc
        return io.BytesIO(base64.b64decode(encoded))

    def resource_path(self, resource):
        raise FileNotFoundError(resource)

    def is_resource(self, name):
        return name in _BUNDLED_RESOURCES

    def contents(self):
        return iter(_BUNDLED_RESOURCES)


class _BundleLoader(importlib.abc.Loader):
    def get_resource_reader(self, fullname):
        if fullname == _BUNDLED_PACKAGE_NAME:
            return _BundleResourceReader()
        return None


def _install_bundled_package() -> None:
    for name in list(sys.modules):
        if name == _BUNDLED_PACKAGE_NAME or name.startswith(f"{{_BUNDLED_PACKAGE_NAME}}."):
            del sys.modules[name]

    loader = _BundleLoader()
    package = types.ModuleType(_BUNDLED_PACKAGE_NAME)
    package.__file__ = "<broker_reports_gate1_openwebui_bundle>"
    package.__package__ = _BUNDLED_PACKAGE_NAME
    package.__path__ = []
    package.__spec__ = importlib.machinery.ModuleSpec(
        _BUNDLED_PACKAGE_NAME,
        loader,
        is_package=True,
    )
    package.__bundle_version__ = _BUNDLED_PACKAGE_VERSION
    sys.modules[_BUNDLED_PACKAGE_NAME] = package

    for short_name in _BUNDLED_MODULE_ORDER:
        source = _BUNDLED_MODULES[short_name]
        if short_name == "__init__":
            module_name = _BUNDLED_PACKAGE_NAME
            module = package
        else:
            module_name = f"{{_BUNDLED_PACKAGE_NAME}}.{{short_name}}"
            module = types.ModuleType(module_name)
            module.__package__ = _BUNDLED_PACKAGE_NAME
            module.__file__ = f"<broker_reports_gate1_openwebui_bundle:{{short_name}}>"
            sys.modules[module_name] = module
            setattr(package, short_name, module)
        exec(compile(source, module.__file__, "exec"), module.__dict__)


_install_bundled_package()


# Begin maintainable source adapter: {source_label}
{pipe_source.rstrip()}
'''


def _canonical_resource_bytes(path: Path) -> bytes:
    """Keep bundled text resources identical on Windows and Linux."""

    return path.read_text(encoding="utf-8").encode("utf-8")


if __name__ == "__main__":
    main()
