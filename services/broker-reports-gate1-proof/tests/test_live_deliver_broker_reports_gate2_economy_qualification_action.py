from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from live_deliver_broker_reports_gate2_economy_qualification_action import (  # noqa: E402
    ACTION_ID,
    ACTION_PATH,
    ALLOWED_EXACT_MODEL_IDS,
    MAINTAINED_FUNCTION_IDS,
    _assert_production_admissions_empty,
    _assert_target_models_published,
    _candidate_payload,
    _function_state,
    _sha256_text,
)
from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationPolicyFactory,
)


def test_candidate_payload_binds_exact_repository_policy_and_revision() -> None:
    policy = Gate2EconomyQualificationPolicyFactory().create().snapshot()
    source = ACTION_PATH.read_text(encoding="utf-8")
    payload = _candidate_payload(
        source=source,
        source_revision="a" * 40,
        policy_snapshot=policy,
    )

    assert payload["id"] == ACTION_ID
    assert payload["content"] == source
    assert payload["meta"] == {
        "description": (
            "Read-only policy boundary for bounded Gate 2 economy model qualification."
        ),
        "qualification_scope": "qualification_only",
        "qualification_policy_hash": policy["qualification_policy_hash"],
        "model_policy_hash": policy["model_policy"]["policy_hash"],
        "workload_policy_hash": policy["workload_policy"]["policy_hash"],
        "source_revision": "a" * 40,
    }


def test_delivery_scope_excludes_all_maintained_production_functions() -> None:
    assert ACTION_ID not in MAINTAINED_FUNCTION_IDS
    assert MAINTAINED_FUNCTION_IDS == (
        "broker_reports_gate1_pipe",
        "broker_reports_gate2_source_fact_pipe",
        "broker_reports_gate2_domain_source_fact_pipe",
    )


def test_safe_function_state_hashes_content_meta_and_valves() -> None:
    state = _function_state(
        {
            "id": "test",
            "name": "Test",
            "type": "action",
            "is_active": True,
            "is_global": False,
            "content": "private-content",
            "meta": {
                "qualification_scope": "qualification_only",
                "private": "not-projected",
            },
            "valves": {"private": "not-projected"},
        }
    )

    assert state["content_sha256"] == _sha256_text("private-content")
    assert state["safe_meta"] == {"qualification_scope": "qualification_only"}
    assert "private-content" not in str(state)
    assert "not-projected" not in str(state)


def test_delivery_preconditions_are_exact_and_fail_closed() -> None:
    policy = Gate2EconomyQualificationPolicyFactory().create().snapshot()

    _assert_target_models_published(set(ALLOWED_EXACT_MODEL_IDS))
    _assert_production_admissions_empty(policy)
