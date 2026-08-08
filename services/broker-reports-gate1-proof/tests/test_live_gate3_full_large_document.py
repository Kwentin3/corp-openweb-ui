from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_gate3_full_large_document.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "live_gate3_full_large_document", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_g37a_plan_is_exactly_six_one_attempt_chunks_and_existing_owners() -> None:
    module = _load_module()
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    module._assert_frozen_contract()
    assert module.EXPECTED_CHUNKS == 6
    assert module.MAX_AVAILABILITY_CHECKS == 3
    assert "Gate3ChunkBatchLabelingFactory.create" in module.FACTORY_REQUIRED
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in (
        module.FACTORY_REQUIRED
    )
    assert "semantic retry" in module.FORBIDDEN
    assert "Gate3ChunkBatchLabelingFactory(" in source
    assert "Gate3FinancialAnnotationsPersistenceFactory(" in source
    assert "Gate3BoundedLabelingFactory(" not in source
    assert "import sqlite3" not in source
    assert "alias normal" not in source.lower()


def test_g37a_safe_receipt_is_terminal_and_bounded() -> None:
    module = _load_module()
    receipt = module._base_receipt(
        args=SimpleNamespace(
            provider_profile_id=module.DEFAULT_PROVIDER_PROFILE_ID,
            model_id=module.DEFAULT_MODEL_ID,
        ),
        plan={"plan_sha256": "frozen-plan"},
        availability_checks=2,
        goal_status="BLOCKED_EXTERNAL",
        acceptance="FAIL",
    )

    assert receipt["goal"] == "G3.7A"
    assert receipt["goal_status"] == "BLOCKED_EXTERNAL"
    assert receipt["acceptance"] == "FAIL"
    assert receipt["availability_checks_used"] == 2
    assert receipt["max_availability_checks"] == 3
    assert receipt["max_provider_submissions_per_chunk"] == 1
    assert receipt["retry_count"] == 0
    assert receipt["repair_count"] == 0
    assert receipt["fallback_count"] == 0
    assert receipt["next_allowed_goal"] == "NONE"


def test_g37a_terminal_and_irreversible_boundaries_are_explicit() -> None:
    module = _load_module()
    source = inspect.getsource(module.main)

    assert "explicit_execute_flag_required" in source
    assert "safe_receipt_path_must_be_new" in source
    assert "private_evidence_directory_must_be_new_or_empty" in source
    assert "submission_counter" in source
    assert '"persistence": "NOT_RUN"' in source
    assert "if not labeling_pass" in source
    assert source.index("if not labeling_pass") < source.index("persistence.save(")
    assert '"read_back_exact"' in source
    assert '"gate2_unchanged"' in source
