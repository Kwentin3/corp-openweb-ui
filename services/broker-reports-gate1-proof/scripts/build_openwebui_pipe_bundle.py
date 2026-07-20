from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
PIPE_SOURCE = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe.py"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
GATE2_PIPE_SOURCE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe.py"
)
GATE2_BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
GATE2_DOMAIN_PIPE_SOURCE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe.py"
)
GATE2_DOMAIN_BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)

BUNDLE_ADAPTER_MARKER = "# Begin maintainable source adapter:"

MODULE_ORDER = [
    "contracts",
    "source_provenance",
    "broker_pdf_neutral_tables",
    "table_projection",
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
    "pdf_layout",
    "pdf_layout_units",
    "pdf_text_layer",
    "pdf_visual_memory",
    "full_source",
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
    "artifact_models",
    "artifact_lifecycle",
    "artifact_retention",
    "artifact_store",
    "artifact_resolver",
    "gate1_public_contracts",
    "gate2_source_fact_contracts",
    "gate2_fns_2ndfl_contracts",
    "gate2_fns_2ndfl_adapter",
    "gate2_table_packages",
    "gate2_input_readiness",
    "gate2_model_contracts",
    "gate2_model_requests",
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
    "gate2_source_fact_validation",
    "gate2_source_fact_runtime",
    "gate2_source_fact_stitching",
    "gate3_context_manifest",
    "gate2_domain_runtime",
    "gate2_handoff",
    "compact_report",
    "safe_report",
    "document_passport",
    "normalizer",
    "__init__",
]

GATE1_HYBRID_MODULES = [
    "pdf_hybrid_contracts",
    "pdf_table_intake_contracts",
    "pdf_table_classification",
    "pdf_table_raster",
    "pdf_hybrid_evidence",
    "pdf_hybrid_budget",
    "pdf_hybrid_compaction",
    "pdf_hybrid_windows",
    "pdf_hybrid_provider",
    "pdf_hybrid_structure",
    "pdf_dual_oracle_contracts",
    "pdf_dual_oracle_consensus",
    "pdf_hybrid_materialization",
    "pdf_table_validation",
    "pdf_hybrid_reliability",
    "pdf_parser_geometry",
    "pdf_structural_row_windows",
    "pdf_visual_topology",
    "pdf_topology_assembly",
    "pdf_vlm_product_routing",
    "pdf_vlm_region_binding",
    "pdf_grid_experiment_provider",
    "pdf_table_intake_runtime",
    "pdf_continuation_discovery",
    "pdf_structural_repair_runtime",
    "pdf_semantic_header_contracts",
    "pdf_semantic_header_projection",
    "pdf_structural_repair_shadow",
    "pdf_hybrid_shadow",
    "pdf_hybrid_reliability_shadow",
]

_GATE1_HYBRID_INSERT_AT = MODULE_ORDER.index("gate2_provider_adapters") + 1
GATE1_MODULE_ORDER = [
    *MODULE_ORDER[:_GATE1_HYBRID_INSERT_AT],
    *GATE1_HYBRID_MODULES,
    *MODULE_ORDER[_GATE1_HYBRID_INSERT_AT:],
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
        for name in sorted(set(MODULE_ORDER) | set(GATE1_HYBRID_MODULES))
    }
    if target in {"all", "gate1"}:
        pipe_source = _strip_openwebui_metadata(PIPE_SOURCE.read_text(encoding="utf-8"))
        bundle = _render_bundle(
            modules={name: modules[name] for name in GATE1_MODULE_ORDER},
            pipe_source=pipe_source,
            title="Broker Reports Gate 1 Pipe Backend Normalizer",
            version="0.19.0-broker-pdf-neutral-tables-v1-bundled",
            package_version="gate1_broker_pdf_neutral_tables_profile_v1",
            source_label="openwebui_actions/broker_reports_gate1_pipe.py",
            requirements="pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107,PyMuPDF==1.26.5",
        )
        BUNDLE_PATH.write_text(bundle, encoding="utf-8", newline="\n")
        print(str(BUNDLE_PATH))
    if target in {"all", "gate2"}:
        gate2_pipe_source = _strip_openwebui_metadata(
            GATE2_PIPE_SOURCE.read_text(encoding="utf-8")
        )
        gate2_modules = {name: modules[name] for name in MODULE_ORDER}
        gate2_modules["__init__"] = _project_package_init(
            gate2_modules["__init__"], included_modules=set(gate2_modules)
        )
        gate2_bundle = _render_bundle(
            modules=gate2_modules,
            pipe_source=gate2_pipe_source,
            title="Broker Reports Gate 2 Source Fact Extraction",
            version="0.6.0-broker-pdf-neutral-tables-v1-bundled",
            package_version="gate2_broker_pdf_neutral_tables_profile_v1",
            source_label="openwebui_actions/broker_reports_gate2_source_fact_pipe.py",
            requirements="pydantic",
        )
        GATE2_BUNDLE_PATH.write_text(gate2_bundle, encoding="utf-8", newline="\n")
        print(str(GATE2_BUNDLE_PATH))
    if target in {"all", "gate2-domain"}:
        gate2_domain_pipe_source = _strip_openwebui_metadata(
            GATE2_DOMAIN_PIPE_SOURCE.read_text(encoding="utf-8")
        )
        gate2_domain_modules = {name: modules[name] for name in MODULE_ORDER}
        gate2_domain_modules["__init__"] = _project_package_init(
            gate2_domain_modules["__init__"],
            included_modules=set(gate2_domain_modules),
        )
        gate2_domain_bundle = _render_bundle(
            modules=gate2_domain_modules,
            pipe_source=gate2_domain_pipe_source,
            title="Broker Reports Gate 2 Domain Source Fact Extraction",
            version="0.8.0-broker-pdf-neutral-tables-v1-bundled",
            package_version="gate2_domain_broker_pdf_neutral_tables_profile_v1",
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
            if item.end_lineno != item.lineno or len(constants_by_line[item.lineno]) != 1:
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
        "provider_adapters_module": '"gate2_provider_adapters"',
        "model_clients_module": '"gate2_model_clients"',
        "csv_profile_module": '"csv_profile"',
        "gate3_context_manifest_module": '"gate3_context_manifest"',
        "csv_profile_factory": "CsvSupportedProfileFactory(",
        "csv_profile_factory_anchor": (
            "CsvSupportedProfileFactory.create is the only production "
            "supported-CSV parser entrypoint"
        ),
        "gate3_context_manifest_factory": "Gate3ContextManifestFactory(",
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
        "runtime_factory": runtime_factory,
        "source_adapter": BUNDLE_ADAPTER_MARKER,
    }
    missing = sorted(
        label
        for label, marker in required_markers.items()
        if marker not in bundle_source
    )
    if missing:
        raise RuntimeError(
            "gate2_bundle_contract_missing:" + ",".join(missing)
        )

    source_adapter = bundle_source.split(BUNDLE_ADAPTER_MARKER, 1)[1]
    forbidden_markers = {
        "direct_openwebui_completion": "generate_chat_completion",
        "direct_anthropic_endpoint": "api.anthropic.com/v1/messages",
        "duplicate_completion_parser": "_completion_dict_content",
        "duplicate_provider_error_classifier": "_provider_error_code",
        "legacy_pipe_model_client": "class OpenWebUIGate2",
    }
    present = sorted(
        label
        for label, marker in forbidden_markers.items()
        if marker in source_adapter
    )
    if present:
        raise RuntimeError(
            "gate2_bundle_contract_forbidden:" + ",".join(present)
        )


def _render_bundle(
    *,
    modules: dict[str, str],
    pipe_source: str,
    title: str,
    version: str,
    package_version: str,
    source_label: str,
    requirements: str,
) -> str:
    modules_literal = json.dumps(modules, ensure_ascii=False, indent=2, sort_keys=True)
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


_BUNDLED_PACKAGE_NAME = "broker_reports_gate1"
_BUNDLED_PACKAGE_VERSION = "{package_version}"
_BUNDLED_MODULE_ORDER = {order_literal}
_BUNDLED_MODULES = {modules_literal}


def _install_bundled_package() -> None:
    for name in list(sys.modules):
        if name == _BUNDLED_PACKAGE_NAME or name.startswith(f"{{_BUNDLED_PACKAGE_NAME}}."):
            del sys.modules[name]

    package = types.ModuleType(_BUNDLED_PACKAGE_NAME)
    package.__file__ = "<broker_reports_gate1_openwebui_bundle>"
    package.__package__ = _BUNDLED_PACKAGE_NAME
    package.__path__ = []
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


if __name__ == "__main__":
    main()
