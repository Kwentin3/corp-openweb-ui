from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    V6_EXACT_MODEL_ID,
    V6_EXECUTION_IDENTITY_POLICY_VERSION,
    V6_PROVIDER_PROFILE_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V6_QUALIFICATION_PUBLICATION_HASH,
    Gate2FinancialSemanticV6QualificationError,
    Gate2FinancialSemanticV6QualificationFixtureFactory,
    Gate2FinancialSemanticV6QualificationPreflightFactory,
    financial_semantic_v6_qualification_publication,
)


V6_MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
ACTION_PATH = (
    ROOT / "openwebui_actions" / "broker_reports_gate2_economy_qualification_action.py"
)
CLI_PATH = ROOT / "scripts" / "live_gate2_financial_semantic_v6_qualification.py"
SNAPSHOT_KEY = b"v6-qualification-test-snapshot-key-32"
CONTINUATION_KEY = b"v6-qualification-test-continuation-key"


def _fixture():
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8")),
    )


def _stage():
    return {
        "action_id": "broker_reports_gate2_economy_qualification_action",
        "content_sha256": "b" * 64,
        "qualification_policy_hash": "c" * 64,
        "v6_qualification_snapshot_hash": V6_QUALIFICATION_PUBLICATION_HASH,
        "production_admissions_empty": True,
        "checks": {
            "content_hash_exact": True,
            "type_action": True,
            "active": True,
            "not_global": True,
            "scope_qualification_only": True,
            "policy_hash_exact": True,
            "v6_qualification_snapshot_exact": True,
        },
    }


def _preflight():
    return Gate2FinancialSemanticV6QualificationPreflightFactory().create(
        fixture=_fixture(),
        repository_revision="a" * 40,
        stage_action=_stage(),
        published_model_ids={V6_EXACT_MODEL_ID},
    )


def _load_action_module():
    spec = importlib.util.spec_from_file_location(
        "broker_reports_gate2_v6_qualification_action_under_test",
        ACTION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("qualification action import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v6_preflight_pins_every_exact_identity_with_zero_calls() -> None:
    receipt = _preflight()
    identity = receipt["exact_identity"]

    assert receipt["acceptance"] == {
        "v6_harness": "READY",
        "action_repository_live_parity": "EXACT",
        "local_preflight": "PASSED",
        "provider_calls": "ZERO",
    }
    assert identity["repository_revision"] == "a" * 40
    assert identity["evidence_bundle_schema"]
    assert identity["typed_option_schema"]
    assert identity["semantic_packet_schema"]
    assert identity["semantic_choice_schema"]
    assert identity["compact_pack_projection"]["source_authority_hashes_sha256"]
    assert identity["compact_pack_projection"]["compact_projection_hashes_sha256"]
    assert identity["prompt"]["version"]
    assert identity["prompt"]["hash"]
    assert identity["ambiguity_policy"]["hash"]
    assert identity["provider_schema"]["schema_hashes_sha256"]
    assert identity["benchmark"]["cases_total"] == 12
    assert identity["model_provider"] == {
        "exact_model_id": V6_EXACT_MODEL_ID,
        "provider_profile_id": V6_PROVIDER_PROFILE_ID,
        "provider_route_revision": receipt["authorization"]["receipt_identity"][
            "provider_route_revision"
        ],
        "request_profile": V6_QUALIFICATION_REQUEST_PROFILE,
        "workload_class": "gate2_financial_evidence",
    }
    assert identity["execution_identity"]["policy_version"] == (
        V6_EXECUTION_IDENTITY_POLICY_VERSION
    )
    assert identity["evidence_contract"]["private_schema_version"]
    assert identity["evidence_contract"]["safe_schema_version"]
    assert receipt["execution_accounting"] == {
        "provider_attempts_total": 0,
        "provider_calls_total": 0,
        "technical_case_provider_calls_total": 0,
        "synthetic_execution_captures_total": 10,
        "fallback_total": 0,
        "repair_total": 0,
        "hidden_retry_total": 0,
        "production_admissions_total": 0,
    }
    assert receipt["integrity_sha256"] == sha256_json(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"}
    )
    assert "only" in FACTORY_REQUIRED
    assert "must not call a provider" in FORBIDDEN


def test_preflight_builds_ten_exact_requests_and_preserves_evidence_contract() -> None:
    receipt = _preflight()

    assert receipt["routes"] == {
        "cases_total": 12,
        "semantic_cases_total": 10,
        "technical_cases_total": 2,
        "technical_case_provider_calls_total": 0,
    }
    assert len(receipt["case_preflights"]) == 10
    assert all(
        item["canonical_request_hash"]
        and item["budgeted_request_hash"]
        and item["evidence_bundle_hash"]
        and item["typed_options_hash"]
        and item["packet_hash"]
        and item["compact_pack_projection_hash"]
        and item["choice_schema_hash"]
        and item["response_format_hash"]
        and item["evidence_contract_validated"] is True
        and item["provider_calls_total"] == 0
        for item in receipt["case_preflights"]
    )
    assert receipt["evidence_contract"]["cases_validated_total"] == 10
    assert receipt["evidence_contract"]["exact_replay_ready"] is True
    assert receipt["budget"]["planned_provider_calls_total"] == 10
    assert receipt["budget"]["within_budget"] is True
    assert receipt["budget"]["estimated_input_tokens_max"] == 3004
    assert receipt["budget"]["estimated_input_tokens_max"] <= 3072


def test_action_publishes_exact_v6_workload_and_keeps_admissions_empty() -> None:
    module = _load_action_module()
    publication = financial_semantic_v6_qualification_publication()

    assert module.V6_QUALIFICATION_SNAPSHOT == publication
    assert module.V6_QUALIFICATION_SNAPSHOT_HASH == (V6_QUALIFICATION_PUBLICATION_HASH)
    assert publication["attempts_total"] == 1
    assert publication["semantic_provider_calls_total"] == 10
    assert publication["technical_provider_calls_total"] == 0
    assert publication["production_admissions"] == []
    assert all(
        route["production_admissions"] == []
        for route in module.POLICY_SNAPSHOT["workload_routes"].values()
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        (
            lambda stage, models: (
                {**stage, "v6_qualification_snapshot_hash": "0" * 64},
                models,
            ),
            "financial_semantic_v6_stage_action_parity_failed",
        ),
        (
            lambda stage, models: (stage, set()),
            "financial_semantic_v6_exact_model_not_published",
        ),
    ),
)
def test_preflight_fails_closed_for_action_or_publication_drift(
    mutation,
    expected_code,
) -> None:
    stage, models = mutation(_stage(), {V6_EXACT_MODEL_ID})
    with pytest.raises(
        Gate2FinancialSemanticV6QualificationError,
        match=expected_code,
    ):
        Gate2FinancialSemanticV6QualificationPreflightFactory().create(
            fixture=_fixture(),
            repository_revision="a" * 40,
            stage_action=stage,
            published_model_ids=models,
        )


def test_goal11a_cli_has_no_provider_execution_or_evidence_write_route() -> None:
    source = CLI_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "post" not in calls
    assert "put" not in calls
    assert "delete" not in calls
    assert "--execute" not in source
    assert "private-evidence" not in source
    assert "safe-receipt" not in source
    assert "qualify_financial_semantic_v6(" not in source
