from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live_gate5_existing_pipeline_one_gap.py"
SPEC = importlib.util.spec_from_file_location("live_gate5_existing_pipeline_one_gap", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_role_pack_completion_uses_current_bound_status() -> None:
    complete = MODULE._role_pack_complete_annotations(
        [
            {
                "roles": [
                    {"role": "date", "status": "bound"},
                    {"role": "amount", "status": "bound"},
                    {"role": "currency", "status": "bound"},
                ]
            },
            {
                "roles": [
                    {"role": "date", "status": "bound"},
                    {"role": "amount", "status": "bound"},
                    {"role": "currency", "status": "missing"},
                ]
            },
        ],
        {"date", "amount", "currency"},
    )

    assert len(complete) == 1
