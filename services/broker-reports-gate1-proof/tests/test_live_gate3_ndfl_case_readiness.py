from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_gate3_ndfl_case_readiness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "live_gate3_ndfl_case_readiness", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_g36_plan_is_read_only_and_uses_existing_owner() -> None:
    module = _load_module()
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Gate3NdflCaseReadinessFactory.create" in module.FACTORY_REQUIRED
    assert "must not write workflow state" in module.FORBIDDEN
    assert "Gate3NdflCaseReadinessFactory" in source
    assert "put_record(" not in source
    assert ".save(" not in source
    assert "requests" not in source
    assert "model_client" not in source
    assert "provider_adapter" not in source
    assert "import sqlite3" not in source


def test_execute_flag_and_evidence_boundaries_are_mandatory() -> None:
    module = _load_module()
    source = inspect.getsource(module.main)

    assert "explicit_execute_flag_required" in source
    assert "private_evidence_must_be_outside_repository" in source
    assert "private_evidence_directory_must_be_new_or_empty" in source
    assert "safe_receipt_path_must_be_new" in source
    assert "artifact_store_changed_during_readiness_proof" in source
    assert "readiness_foreign_scope_disclosed" in source
