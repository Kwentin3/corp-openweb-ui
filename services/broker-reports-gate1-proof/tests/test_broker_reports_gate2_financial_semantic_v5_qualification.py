from __future__ import annotations

import asyncio
import json
from pathlib import Path

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_qualification import (
    EXACT_MODEL_ID,
    PROVIDER_PROFILE_ID,
    SEMANTIC_CASES_TOTAL,
    Gate2FinancialSemanticV5QualificationFixtureFactory,
    Gate2FinancialSemanticV5QualificationPreflightFactory,
    qualify_financial_semantic_v5,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_KEY = b"v5-qualification-test-snapshot-key-32"
CONTINUATION_KEY = b"v5-qualification-test-continuation-key"


def _fixture():
    manifest = json.loads(
        (
            ROOT
            / "benchmarks"
            / "gate2_financial_semantic_v5"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    base = json.loads(
        (
            ROOT
            / "benchmarks"
            / "gate2_financial_successor_v2"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    return Gate2FinancialSemanticV5QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(manifest=manifest, base_manifest=base)


def _preflight(fixture):
    return Gate2FinancialSemanticV5QualificationPreflightFactory().create(
        fixture=fixture,
        repository_revision="a" * 40,
        stage_action={
            "content_sha256": "b" * 64,
            "qualification_policy_hash": "c" * 64,
            "production_admissions_empty": True,
            "checks": {"content_hash_exact": True, "active": True},
        },
        published_model_ids={EXACT_MODEL_ID},
    )


class _ExactFakeClient:
    def __init__(self, fixture) -> None:
        self.outputs = {
            item.packet.packet_hash: item.expected_model_output
            for item in fixture.semantic_cases
            if item.packet is not None
        }
        self.calls = 0

    async def extract(
        self,
        *,
        prompt,
        package,
        model_id,
        response_format,
    ):
        del prompt
        self.calls += 1
        return Gate2StructuredModelResult(
            content=self.outputs[sha256_json(package)],
            fallback_used=False,
            repair_attempt_count=0,
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="openai",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision="test",
                adapter_id="openwebui_openai_response_format",
                adapter_version="test",
                requested_model_id=model_id,
                resolved_model_id=model_id,
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                canonical_request_schema_hash=sha256_json(
                    response_format
                ),
                adapted_request_schema_hash=sha256_json(response_format),
                duration_ms=5,
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
            economy_budget_receipt={
                "status": "passed",
                "input_tokens": 100,
                "output_tokens": 20,
                "actual_cost_usd": "0.000045",
            },
        )


def test_preflight_pins_exact_v5_identity_with_zero_calls() -> None:
    fixture = _fixture()
    receipt = _preflight(fixture)

    assert receipt["status"] == "passed"
    assert receipt["acceptance"] == {
        "v5_harness": "READY",
        "exact_identity": "PINNED",
        "local_preflight": "PASSED",
        "provider_calls": "ZERO",
        "production_admission": "EMPTY",
    }
    assert receipt["routes"] == {
        "cases_total": 12,
        "semantic_cases_total": 10,
        "technical_cases_total": 2,
        "technical_case_provider_calls_total": 0,
    }
    assert receipt["budget"]["estimated_input_tokens_max"] <= 3072
    assert receipt["execution_accounting"]["provider_calls_total"] == 0
    assert receipt["exact_identity"]["exact_model_id"] == EXACT_MODEL_ID
    assert receipt["exact_identity"]["model_input_schema"].endswith(
        "_decision_packet_v5"
    )


def test_one_attempt_runs_only_semantic_cases_and_passes_hard_gates() -> None:
    fixture = _fixture()
    preflight = _preflight(fixture)
    client = _ExactFakeClient(fixture)
    private: dict[str, dict] = {}
    checkpoints: list[dict] = []

    result = asyncio.run(
        qualify_financial_semantic_v5(
            fixture=fixture,
            model_client=client,
            exact_identity=preflight["exact_identity"],
            private_case_checkpoint=lambda case_id, payload: private.__setitem__(
                case_id, payload
            ),
            safe_checkpoint=checkpoints.append,
        )
    )

    assert client.calls == SEMANTIC_CASES_TOTAL
    assert len(private) == SEMANTIC_CASES_TOTAL
    assert result["execution_state"] == "terminal"
    assert result["status"] == "passed"
    assert result["product_gate"] == "MODEL_SAFE_FOR_SHADOW"
    assert all(value == 0 for value in result["hard_gates"].values())
    assert result["attempt_accounting"] == {
        "provider_attempts_total": 1,
        "provider_calls_total": 10,
        "semantic_cases_total": 10,
        "technical_cases_total": 2,
        "technical_case_provider_calls_total": 0,
        "hidden_retry_total": 0,
        "fallback_total": 0,
        "repair_total": 0,
    }
    assert result["exact_decisions_preserved"] is True
    assert result["raw_private_data_in_receipt"] is False
    assert checkpoints[-1] == result


def test_preflight_fails_closed_for_stage_or_publication_drift() -> None:
    fixture = _fixture()
    try:
        Gate2FinancialSemanticV5QualificationPreflightFactory().create(
            fixture=fixture,
            repository_revision="a" * 40,
            stage_action={
                "content_sha256": "b" * 64,
                "production_admissions_empty": True,
                "checks": {"content_hash_exact": False},
            },
            published_model_ids={EXACT_MODEL_ID},
        )
    except ValueError as exc:
        assert str(exc) == "financial_semantic_v5_stage_action_parity_failed"
    else:  # pragma: no cover
        raise AssertionError("stage drift must fail closed")

    try:
        Gate2FinancialSemanticV5QualificationPreflightFactory().create(
            fixture=fixture,
            repository_revision="a" * 40,
            stage_action={
                "content_sha256": "b" * 64,
                "production_admissions_empty": True,
                "checks": {"content_hash_exact": True},
            },
            published_model_ids=set(),
        )
    except ValueError as exc:
        assert str(exc) == "financial_semantic_v5_exact_model_not_published"
    else:  # pragma: no cover
        raise AssertionError("missing exact model must fail closed")
