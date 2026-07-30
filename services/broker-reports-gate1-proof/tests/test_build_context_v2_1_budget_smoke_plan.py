from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
BUILD_SCRIPT = (
    SERVICE_ROOT
    / "scripts"
    / "build_context_v2_1_budget_smoke_plan.py"
)
SAFE_PLAN_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.plan.safe.json"
)
TRANSPARENT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.transparent.json"
)


def _load_builder():
    name = "build_context_v2_1_budget_smoke_plan_under_test"
    spec = importlib.util.spec_from_file_location(name, BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load_builder()


@pytest.fixture(scope="module")
def built_artifacts():
    return BUILDER.build_artifacts()


def test_precall_artifacts_pin_all_exact_synthetic_requests(
    built_artifacts,
) -> None:
    safe_plan, transparent = built_artifacts
    safe_slots = {
        item["slot_id"]: item for item in safe_plan["slots"]
    }

    assert safe_plan["status"] == "frozen_preflight_not_executed"
    assert safe_plan["transport_executed"] is False
    assert safe_plan["execution_accounting"][
        "provider_submissions_total"
    ] == 0
    assert transparent["status"] == "preflight_not_executed"
    assert transparent["transport_executed"] is False
    assert transparent["contains_customer_data"] is False
    assert transparent["synthetic_evidence_only"] is True
    assert transparent["slots_total"] == 12
    assert transparent["execution_accounting"] == {
        "planned_slots_total": 12,
        "maximum_provider_submissions_total": 12,
        "provider_calls_total": 0,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert [
        item["slot_id"] for item in transparent["slots"]
    ] == [item["slot_id"] for item in safe_plan["slots"]]

    provider_counts: dict[str, int] = {}
    for item in transparent["slots"]:
        safe_slot = safe_slots[item["slot_id"]]
        provider_id = item["provider"]["provider_profile_id"]
        provider_counts[provider_id] = (
            provider_counts.get(provider_id, 0) + 1
        )
        model_visible = item["exact_model_visible_request"]
        prepared = item["exact_final_prepared_request"]
        provider_schema = item["exact_provider_visible_schema"]
        expected_answer = item["audited_expected_answer"]
        hashes = item["hashes"]

        assert set(model_visible) == {"messages", "response_format"}
        assert [message["role"] for message in model_visible["messages"]] == [
            "system",
            "user",
        ]
        assert all(
            isinstance(message["content"], str)
            and message["content"]
            for message in model_visible["messages"]
        )
        assert prepared["provider_visible_schema"] == provider_schema
        assert sha256_json(prepared) == hashes["prepared_request_hash"]
        assert sha256_json(provider_schema) == (
            hashes["provider_visible_schema_hash"]
        )
        assert sha256_json(expected_answer) == (
            hashes["expected_answer_hash"]
        )
        assert hashes["prepared_request_hash"] == (
            safe_slot["prepared_request_hash"]
        )
        assert hashes["model_visible_request_hash"] == (
            safe_slot["model_visible_request_hash"]
        )
        assert hashes["slot_integrity_hash"] == (
            safe_slot["integrity_hash"]
        )
        assert item["operation_identity"] == (
            f"{safe_plan['integrity_hash']}:{safe_slot['integrity_hash']}"
        )
        assert hashes["operation_identity_sha256"] == hashlib.sha256(
            item["operation_identity"].encode("utf-8")
        ).hexdigest()
        assert item["execution_accounting"] == {
            "provider_calls_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        }
        assert item["status"] == "preflight_not_executed"

    assert provider_counts == {
        "openai_gpt": 4,
        "anthropic_claude": 4,
        "google_gemini": 4,
    }
    google = [
        item
        for item in transparent["slots"]
        if item["provider"]["provider_profile_id"]
        == "google_gemini"
    ]
    assert all(
        item["model_identity"]
        == {
            "requested_model_selector": (
                "models/gemini-3.1-flash-lite"
            ),
            "identity_kind": "stable_selector_not_immutable",
            "immutable_model_id_proven": False,
            "caveat": (
                "provider_inventory_has_no_dated_immutable_google_model_id"
            ),
        }
        for item in google
    )
    assert all(
        item["model_identity"]["immutable_model_id_proven"] is True
        and item["model_identity"]["caveat"] is None
        for item in transparent["slots"]
        if item["provider"]["provider_profile_id"]
        in {"openai_gpt", "anthropic_claude"}
    )


def test_precall_artifacts_contain_no_private_material_or_transport(
    built_artifacts,
) -> None:
    _safe_plan, transparent = built_artifacts
    source = BUILD_SCRIPT.read_text(encoding="utf-8")
    forbidden_keys = {
        "api_key",
        "authorization",
        "choice_restoration",
        "credential",
        "credentials",
        "filesystem_path",
        "mapping_receipt",
        "password",
        "private_evidence",
        "private_mapping",
        "provider_output",
        "provider_response",
        "provider_response_id",
        "raw_provider_response",
        "repository_path",
        "secret",
        "source_path",
    }

    assert BUILDER._recursive_keys(transparent).isdisjoint(
        forbidden_keys
    )
    assert "production GOAL 12" in BUILDER.FACTORY_REQUIRED
    assert "must not call a provider" in BUILDER.FORBIDDEN
    for forbidden in (
        "extract_context_v2_1_once(",
        "execute_slot(",
        "urlopen(",
        "requests.",
        "httpx.",
        "Gate2OpenWebUIStructuredModelClient",
    ):
        assert forbidden not in source


def test_generated_files_and_check_mode_are_byte_exact(
    built_artifacts,
    tmp_path,
) -> None:
    safe_plan, transparent = built_artifacts

    assert SAFE_PLAN_PATH.read_bytes() == BUILDER._json_bytes(safe_plan)
    assert TRANSPARENT_PATH.read_bytes() == BUILDER._json_bytes(
        transparent
    )
    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "passed"
    assert summary["mode"] == "check"
    assert summary["provider_calls_total"] == 0

    isolated = tmp_path / "artifact.json"
    expected = b'{\n  "status": "preflight_not_executed"\n}\n'
    outputs = {isolated: expected}
    BUILDER.write_or_check_outputs(outputs=outputs, check=False)
    BUILDER.write_or_check_outputs(outputs=outputs, check=True)
    isolated.write_bytes(expected + b"\r\n")
    with pytest.raises(
        SystemExit,
        match="context_v2_1_budget_smoke_precall_drift:artifact.json",
    ):
        BUILDER.write_or_check_outputs(outputs=outputs, check=True)
