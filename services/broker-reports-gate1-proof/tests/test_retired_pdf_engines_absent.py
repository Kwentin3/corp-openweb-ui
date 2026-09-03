from __future__ import annotations

import ast
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
SCANNED_ROOTS = (
    PACKAGE_ROOT,
    SERVICE_ROOT / "openwebui_actions",
    SERVICE_ROOT / "scripts",
    SERVICE_ROOT / "tests",
)
FORBIDDEN_ENGINE_TOKENS = (
    "pdfplumber",
    "pdfminer",
    "pymupdf",
    "import fitz",
    "camelot",
    "docling",
    "visualpdfplumber",
)
RETIRED_MODULE_PREFIXES = (
    "broker_pdf_neutral_tables",
    "logical_row_table_recovery",
    "managed_pdf_document",
    "pdf_compact_",
    "pdf_continuation_",
    "pdf_csv_",
    "pdf_dual_",
    "pdf_grid_",
    "pdf_hybrid_",
    "pdf_layout",
    "pdf_native_navigation_",
    "pdf_normalization_",
    "pdf_parser_geometry",
    "pdf_semantic_header_",
    "pdf_structural_",
    "pdf_table_classification",
    "pdf_table_intake_",
    "pdf_table_locator",
    "pdf_table_raster",
    "pdf_table_validation",
    "pdf_text_layer",
    "pdf_topology_",
    "pdf_view_semantic_",
    "pdf_visual_",
    "pdf_vlm_",
    "semantic_visual_",
    "visual_pdfplumber_",
    "visual_table_review_",
)


def _maintained_files() -> list[Path]:
    paths: list[Path] = [SERVICE_ROOT / "requirements-ci.txt"]
    for root in SCANNED_ROOTS:
        paths.extend(root.rglob("*.py"))
    return sorted(
        path
        for path in paths
        if path.resolve() != Path(__file__).resolve()
        and "__pycache__" not in path.parts
    )


def test_retired_engine_dependencies_and_vocabulary_are_absent() -> None:
    violations: list[str] = []
    for path in _maintained_files():
        lowered = path.read_text(encoding="utf-8").casefold()
        for token in FORBIDDEN_ENGINE_TOKENS:
            if token.casefold() in lowered:
                violations.append(f"{path.relative_to(SERVICE_ROOT)}:{token}")
    assert violations == []


def test_retired_module_families_are_absent_from_package_and_imports() -> None:
    retired_files = sorted(
        path.name
        for path in PACKAGE_ROOT.glob("*.py")
        if any(path.stem.startswith(prefix) for prefix in RETIRED_MODULE_PREFIXES)
    )
    assert retired_files == []

    retired_imports: list[str] = []
    for path in _maintained_files():
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                short_name = module.rsplit(".", 1)[-1]
                if any(short_name.startswith(prefix) for prefix in RETIRED_MODULE_PREFIXES):
                    retired_imports.append(
                        f"{path.relative_to(SERVICE_ROOT)}:{node.lineno}:{module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    short_name = alias.name.rsplit(".", 1)[-1]
                    if any(
                        short_name.startswith(prefix)
                        for prefix in RETIRED_MODULE_PREFIXES
                    ):
                        retired_imports.append(
                            f"{path.relative_to(SERVICE_ROOT)}:{node.lineno}:{alias.name}"
                        )
    assert retired_imports == []


def test_generated_bundles_do_not_embed_retired_modules() -> None:
    bundles = sorted((SERVICE_ROOT / "openwebui_actions").glob("*_bundled.py"))
    assert len(bundles) == 3
    violations: list[str] = []
    for path in bundles:
        text = path.read_text(encoding="utf-8").casefold()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "_BUNDLED_MODULES"
                for target in node.targets
            ):
                modules = ast.literal_eval(node.value)
                module_names = set(modules)
                break
        assert module_names
        for module_name in module_names:
            if any(
                module_name.startswith(prefix)
                for prefix in RETIRED_MODULE_PREFIXES
            ):
                violations.append(f"{path.name}:{module_name}")
        for token in FORBIDDEN_ENGINE_TOKENS:
            if token.casefold() in text:
                violations.append(f"{path.name}:{token}")
    assert violations == []
