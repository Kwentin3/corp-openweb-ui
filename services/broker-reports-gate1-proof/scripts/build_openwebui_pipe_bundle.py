from __future__ import annotations

import ast
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
    "table_projection",
    "blockers",
    "inputs",
    "detectors",
    "profilers_csv_txt",
    "profilers_docx",
    "profilers_image",
    "profilers_pdf",
    "profilers_xlsx",
    "profilers_zip",
    "pdf_layout",
    "pdf_layout_units",
    "pdf_text_layer",
    "full_source",
    "taxonomy",
    "criticality",
    "eligibility",
    "domain_ingestion",
    "validators",
    "clarification",
    "artifact_models",
    "artifact_lifecycle",
    "artifact_retention",
    "artifact_store",
    "artifact_resolver",
    "gate2_input_readiness",
    "gate2_source_fact_contracts",
    "gate2_model_contracts",
    "gate2_model_requests",
    "gate2_model_clients",
    "gate2_domain_routing",
    "gate2_candidate_binding",
    "gate2_candidate_binding_runtime",
    "gate2_domain_packages",
    "gate2_source_unit_segmentation",
    "gate2_domain_contracts",
    "gate2_domain_finalization",
    "gate2_source_fact_validation",
    "gate2_source_fact_runtime",
    "gate2_source_fact_stitching",
    "gate2_domain_runtime",
    "gate2_handoff",
    "compact_report",
    "safe_report",
    "document_passport",
    "normalizer",
    "__init__",
]


def main() -> None:
    modules = {
        name: (PACKAGE_ROOT / f"{name}.py").read_text(encoding="utf-8")
        for name in MODULE_ORDER
    }
    pipe_source = _strip_openwebui_metadata(PIPE_SOURCE.read_text(encoding="utf-8"))
    bundle = _render_bundle(
        modules=modules,
        pipe_source=pipe_source,
        title="Broker Reports Gate 1 Pipe Backend Normalizer",
        version="0.6.0-pdf-layout-rich-slice2-bundled",
        package_version="gate1_pdf_layout_rich_slice2_v0",
        source_label="openwebui_actions/broker_reports_gate1_pipe.py",
        requirements="pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107",
    )
    BUNDLE_PATH.write_text(bundle, encoding="utf-8", newline="\n")
    print(str(BUNDLE_PATH))
    gate2_pipe_source = _strip_openwebui_metadata(
        GATE2_PIPE_SOURCE.read_text(encoding="utf-8")
    )
    gate2_bundle = _render_bundle(
        modules=modules,
        pipe_source=gate2_pipe_source,
        title="Broker Reports Gate 2 Source Fact Extraction",
        version="0.2.0-provider-factory-runtime-bundled",
        package_version="gate2_provider_factory_runtime_v0",
        source_label="openwebui_actions/broker_reports_gate2_source_fact_pipe.py",
        requirements="pydantic",
    )
    GATE2_BUNDLE_PATH.write_text(gate2_bundle, encoding="utf-8", newline="\n")
    print(str(GATE2_BUNDLE_PATH))
    gate2_domain_pipe_source = _strip_openwebui_metadata(
        GATE2_DOMAIN_PIPE_SOURCE.read_text(encoding="utf-8")
    )
    gate2_domain_bundle = _render_bundle(
        modules=modules,
        pipe_source=gate2_domain_pipe_source,
        title="Broker Reports Gate 2 Domain Source Fact Extraction",
        version="0.4.0-domain-provider-factory-runtime-bundled",
        package_version="gate2_domain_provider_factory_runtime_v0",
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


def assert_gate2_bundle_contract(
    bundle_source: str,
    *,
    runtime_factory: str,
) -> None:
    required_markers = {
        "bundled_modules": "_BUNDLED_MODULES",
        "model_contracts_module": '"gate2_model_contracts"',
        "model_requests_module": '"gate2_model_requests"',
        "model_clients_module": '"gate2_model_clients"',
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
    order_literal = json.dumps(MODULE_ORDER, ensure_ascii=True)
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
