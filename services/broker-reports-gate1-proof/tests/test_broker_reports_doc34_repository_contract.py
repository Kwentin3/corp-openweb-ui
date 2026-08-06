from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from broker_reports_gate1.canonical_artifact import (
    CANONICAL_ARTIFACT_SCHEMA_VERSION,
    CanonicalNormalizerFactory,
    assess_canonical_completeness,
)
from broker_reports_gate1.canonical_consumer_migration import (
    render_neutral_canonical_projection,
)
from broker_reports_gate1.canonical_store import (
    CanonicalArtifactStoreFactory,
    CanonicalReader,
    CanonicalReaderFactory,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
ENTRYPOINT = DOC_ROOT / "BROKER_REPORTS_GATE2.md"

AUTHORITATIVE_MODULES = (
    "artifact_store.py",
    "artifact_resolver.py",
    "full_source.py",
    "canonical_artifact.py",
    "canonical_store.py",
    "canonical_consumer_migration.py",
    "canonical_wave2_shadow.py",
    "xlsx_streaming.py",
)


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def _local_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_one_public_schema_and_reader_authority() -> None:
    assignments: list[Path] = []
    reader_classes: list[Path] = []
    for path in PACKAGE_ROOT.glob("*.py"):
        tree = _tree(path)
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(
                    isinstance(target, ast.Name)
                    and target.id == "CANONICAL_ARTIFACT_SCHEMA_VERSION"
                    for target in targets
                ):
                    assignments.append(path)
            if isinstance(node, ast.ClassDef) and node.name == "CanonicalReader":
                reader_classes.append(path)

    assert CANONICAL_ARTIFACT_SCHEMA_VERSION == "canonical_artifact_v1"
    assert assignments == [PACKAGE_ROOT / "canonical_artifact.py"]
    assert reader_classes == [PACKAGE_ROOT / "canonical_store.py"]
    assert CanonicalNormalizerFactory.__module__.endswith("canonical_artifact")
    assert CanonicalArtifactStoreFactory.__module__.endswith("canonical_store")
    assert CanonicalReaderFactory.__module__.endswith("canonical_store")
    assert CanonicalReader.__module__.endswith("canonical_store")


def test_canonical_runtime_has_no_research_or_gate3_imports() -> None:
    forbidden_parts = {"scripts", "research", "proof", "gate3"}
    for filename in AUTHORITATIVE_MODULES:
        path = PACKAGE_ROOT / filename
        imports = _local_imports(path)
        offenders = sorted(
            name
            for name in imports
            if forbidden_parts.intersection(name.lower().split("."))
        )
        assert offenders == [], (path, offenders)


def test_projection_is_reader_only_and_format_opaque() -> None:
    source = inspect.getsource(render_neutral_canonical_projection)
    for forbidden in (
        "source_format",
        "ArtifactStore",
        "ArtifactResolver",
        "private_evidence",
        "provider_payload",
        "financial_fact",
    ):
        assert forbidden not in source


def test_completeness_guard_is_public_and_reader_revalidates() -> None:
    empty = {
        "containers": [],
        "nodes": [],
        "issues": [],
        "provenance": [],
        "source": {"source_artifact_ref": "source"},
    }
    result = assess_canonical_completeness(empty)
    assert result["status"] == "failed"
    assert "canonical_machine_content_empty" in result["reason_codes"]

    reader_source = inspect.getsource(CanonicalReader._validated)
    assert "validate_canonical_artifact" in reader_source


def test_entrypoint_routes_only_to_current_authorities() -> None:
    entry = ENTRYPOINT.read_text(encoding="utf-8")
    required = (
        "CanonicalNormalizerFactory.create",
        "CanonicalArtifactStoreFactory.create",
        "CanonicalReaderFactory.create",
        "BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md",
        "BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md",
        "BROKER_REPORTS_GATE2_SAFE_CHANGE_GUIDE.v1.md",
        "BROKER_REPORTS_GATE3_HANDOFF.v1.md",
    )
    assert all(value in entry for value in required)
    assert "CURRENT_ENTRYPOINT" in entry
    assert "Gate 3 ещё не реализован" in entry
    assert "BROKER_REPORTS_CURRENT_STATE.v1.*" in entry
    assert "historical snapshots" in entry


def test_new_documentation_links_resolve() -> None:
    paths = (
        ENTRYPOINT,
        DOC_ROOT / "architecture" / "BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md",
        DOC_ROOT / "operations" / "BROKER_REPORTS_GATE2_SAFE_CHANGE_GUIDE.v1.md",
        DOC_ROOT / "operations" / "BROKER_REPORTS_BRANCH_LIFECYCLE.v1.md",
        DOC_ROOT / "contracts" / "BROKER_REPORTS_GATE3_HANDOFF.v1.md",
    )
    link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            if raw_target.startswith(("http://", "https://", "#")):
                continue
            target = raw_target.split("#", 1)[0]
            assert (path.parent / target).resolve().exists(), (path, raw_target)


def test_do_not_break_invariants_are_review_visible() -> None:
    implementation_map = (
        DOC_ROOT / "architecture" / "BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md"
    ).read_text(encoding="utf-8")
    required = (
        "ONE_PUBLIC_SCHEMA",
        "ONE_PUBLIC_READER",
        "ALL_FORMATS_CONFORM",
        "DOWNSTREAM_FORMAT_OPACITY",
        "EVIDENCE_BOUNDARY",
        "LLM_PROJECTION_BOUNDARY",
        "COMPLETENESS_FAIL_CLOSED",
        "PROVENANCE_RESOLVES",
        "IMMUTABLE_VERSIONING",
        "ATOMIC_ACTIVATION",
        "DURABLE_ROUNDTRIP",
        "NO_SILENT_FALLBACK",
    )
    assert all(value in implementation_map for value in required)
