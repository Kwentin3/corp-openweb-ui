from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    SERVICE_ROOT / "scripts" / "live_gate3_financial_annotations_persistence.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "live_gate3_financial_annotations_persistence", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_g35_plan_uses_existing_persistence_and_no_provider() -> None:
    module = _load_module()
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert module.EXPECTED_BATCH_SHA256 == (
        "c5be4f6a2e1728d04be10155787b02a1ef2fe0a3054e3530d4e72aba91555595"
    )
    assert module.PROVIDER_PROFILE_ID == "google_gemini"
    assert module.EXPECTED_MODEL_ID == "models/gemini-3.5-flash"
    assert "Gate3FinancialAnnotationsPersistenceFactory" in module.FACTORY_REQUIRED
    assert "ArtifactStore" in module.FACTORY_REQUIRED
    assert "requests" not in source
    assert "label_gate3_once" not in source
    assert "Gate3ChunkBatchLabelingFactory" not in source
    assert "import sqlite3" not in source


def test_execute_flag_and_private_input_are_mandatory() -> None:
    module = _load_module()
    source = inspect.getsource(module.main)

    assert "explicit_execute_flag_required" in source
    assert "private_batch_result_hash_mismatch" in source
    assert "broker_reports_gate3_strict_alias_private_result_v1" in source
    assert "GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION" in source
    assert "private_batch_result_must_be_outside_repository" in source
    assert "private_evidence_directory_must_be_new_or_empty" in source
    assert "safe_receipt_path_must_be_new" in source
