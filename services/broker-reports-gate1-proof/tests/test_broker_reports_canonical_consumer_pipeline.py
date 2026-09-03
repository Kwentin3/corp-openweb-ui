from __future__ import annotations

import ast
from pathlib import Path

from broker_reports_gate1.canonical_consumer_migration import (
    COMPATIBILITY_STATUSES,
    FROZEN_CONSUMER_SURFACES,
    WAVE0_MAPPINGS,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CONTRACT_ROOT = REPO_ROOT / "docs" / "stage2" / "contracts"
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _local_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(ast.parse(_read(path))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_current_contracts_bind_the_frozen_inventory_and_read_boundary() -> None:
    pipeline = _read(CONTRACT_ROOT / "BROKER_REPORTS_PIPELINE_GATES.v1.md")
    reader = _read(CONTRACT_ROOT / "BROKER_REPORTS_CANONICAL_READER.v1.md")
    strategy = _read(
        CONTRACT_ROOT / "BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md"
    )
    matrix = _read(
        CONTRACT_ROOT
        / "BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md"
    )
    authorities = _read(
        CONTRACT_ROOT / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
    )

    assert len(FROZEN_CONSUMER_SURFACES) == 13
    assert all(
        surface.migration_wave != "WAVE_1_INTERNAL_READ_ONLY"
        for surface in FROZEN_CONSUMER_SURFACES
    )
    assert "CANONICAL_GATE2_READ_ENABLED=false" in reader
    assert "global product canonical\nread valve remains disabled" in pipeline
    assert "there is no silent legacy fallback" in reader
    assert "There is no frozen `WAVE_1_INTERNAL_READ_ONLY` surface" in strategy
    assert "| Wave 1 | none | none | no eligible frozen consumer |" in matrix
    assert "switches no background or\nprimary product consumer" in authorities


def test_compatibility_contracts_are_explicit_and_consumer_scoped() -> None:
    assert len(WAVE0_MAPPINGS) == 1
    assert len({mapping.feature_flag for mapping in WAVE0_MAPPINGS}) == 1
    assert all(
        mapping.feature_flag.startswith("CANONICAL_READ_")
        for mapping in WAVE0_MAPPINGS
    )
    assert COMPATIBILITY_STATUSES == {
        "CANONICAL_OK",
        "CANONICAL_INCOMPLETE",
        "CANONICAL_CONFLICT",
        "CANONICAL_ACCESS_DENIED",
        "CANONICAL_VERSION_UNSUPPORTED",
        "CANONICAL_STORAGE_FAILURE",
    }

    migration = PACKAGE_ROOT / "canonical_consumer_migration.py"
    imports = _local_imports(migration)
    source = _read(migration)
    assert "sqlite3" not in imports
    assert not any("provider" in name for name in imports)
    assert "gate3" not in source.lower()
    assert "CanonicalReaderFactory" in source
    assert "silent legacy fallback" in source


def test_compatibility_adapters_are_not_wired_into_product_consumers() -> None:
    product_paths = (
        PACKAGE_ROOT / "gate2_input_readiness.py",
        PACKAGE_ROOT / "gate2_source_fact_runtime.py",
        SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe.py",
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate1_pipe_bundled.py",
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate2_source_fact_pipe_bundled.py",
    )
    for path in product_paths:
        assert "canonical_consumer_migration" not in _read(path)
