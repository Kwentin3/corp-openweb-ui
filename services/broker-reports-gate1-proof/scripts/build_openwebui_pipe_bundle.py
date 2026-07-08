from __future__ import annotations

import ast
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
PIPE_SOURCE = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe.py"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"

MODULE_ORDER = [
    "contracts",
    "blockers",
    "inputs",
    "detectors",
    "profilers_csv_txt",
    "profilers_docx",
    "profilers_image",
    "profilers_pdf",
    "profilers_xlsx",
    "profilers_zip",
    "taxonomy",
    "validators",
    "artifact_models",
    "artifact_lifecycle",
    "artifact_retention",
    "artifact_store",
    "artifact_resolver",
    "gate2_handoff",
    "compact_report",
    "safe_report",
    "normalizer",
    "__init__",
]


def main() -> None:
    modules = {
        name: (PACKAGE_ROOT / f"{name}.py").read_text(encoding="utf-8")
        for name in MODULE_ORDER
    }
    pipe_source = _strip_openwebui_metadata(PIPE_SOURCE.read_text(encoding="utf-8"))
    bundle = _render_bundle(modules=modules, pipe_source=pipe_source)
    BUNDLE_PATH.write_text(bundle, encoding="utf-8", newline="\n")
    print(str(BUNDLE_PATH))


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


def _render_bundle(*, modules: dict[str, str], pipe_source: str) -> str:
    modules_literal = json.dumps(modules, ensure_ascii=False, indent=2, sort_keys=True)
    order_literal = json.dumps(MODULE_ORDER, ensure_ascii=True)
    return f'''"""
title: Broker Reports Gate 1 Pipe Backend Normalizer
author: Alpha Soft
version: 0.4.0-backend-normalizer-bundled
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import sys
import types


_BUNDLED_PACKAGE_NAME = "broker_reports_gate1"
_BUNDLED_PACKAGE_VERSION = "gate1_backend_profiling_completion_v1"
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


# Begin maintainable source adapter: openwebui_actions/broker_reports_gate1_pipe.py
{pipe_source.rstrip()}
'''


if __name__ == "__main__":
    main()
