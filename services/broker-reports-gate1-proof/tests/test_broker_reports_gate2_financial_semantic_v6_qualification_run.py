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
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    replay_financial_semantic_v6_decision,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_PROMPT_VERSION,
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
    SEMANTIC_CASES_TOTAL,
    V6_QUALIFICATION_PUBLICATION_HASH,
    Gate2FinancialSemanticV6QualificationFixtureFactory,
    Gate2FinancialSemanticV6QualificationPreflightFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification_run import (
    LOCAL_PREFLIGHT_FAILED,
    MODEL_OUTPUT_SCHEMA_FAILED,
    MODEL_SEMANTIC_GATE_FAILED,
    MODEL_SAFE_FOR_SHADOW,
    PROVIDER_RESPONSE_INVALID,
    PROVIDER_TRANSPORT_FAILED,
    PROVIDER_USAGE_METADATA_INCOMPLETE,
    REQUEST_BUILD_FAILED,
    V6_QUALIFICATION_TERMINAL_CLASSES,
    qualify_financial_semantic_v6,
)
from broker_reports_gate1.gate2_financial_semantic_v6_stronger_candidate import (
    V6_GOAL12_EXACT_MODEL_ID,
    V6_GOAL12_PROVIDER_PROFILE_ID,
    Gate2FinancialSemanticV6StrongerCandidatePreflightFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelResult,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_KEY = b"v6-run-test-snapshot-authority-key"
CONTINUATION_KEY = b"v6-run-test-continuation-authority"


def _fixture():
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(
            (
                ROOT
                / "benchmarks"
                / "gate2_financial_semantic_v6"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        ),
        base_manifest=json.loads(
            (
                ROOT
                / "benchmarks"
                / "gate2_financial_successor_v2"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        ),
    )


def _preflight(
    fixture,
    *,
    exact_model_id: str = V6_EXACT_MODEL_ID,
    provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
):
    return Gate2FinancialSemanticV6QualificationPreflightFactory().create(
        fixture=fixture,
        repository_revision="a" * 40,
        stage_action={
            "content_sha256": "b" * 64,
            "v6_qualification_snapshot_hash": (
                V6_QUALIFICATION_PUBLICATION_HASH
            ),
            "production_admissions_empty": True,
            "checks": {
                "content_hash_exact": True,
                "active": True,
                "not_global": True,
            },
        },
        published_model_ids={exact_model_id},
        exact_model_id=exact_model_id,
        provider_profile_id=provider_profile_id,
    )


class _ExactFakeClient:
    def __init__(
        self,
        fixture,
        *,
        wrong_type: bool = False,
        provider_failure: bool = False,
        pretransport_failure: bool = False,
        usage_metadata_incomplete: bool = False,
        invalid_output: bool = False,
        invalid_response: bool = False,
        provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
    ) -> None:
        self.outputs = {
            item.packet.packet_hash: item.expected_model_choice
            for item in fixture.semantic_cases
            if item.packet is not None
        }
        if wrong_type:
            target = next(
                item
                for item in fixture.semantic_cases
                if item.expected_disposition == "typed_input"
                and item.compilation is not None
                and any(
                    option.input_type_id != item.expected_input_type_id
                    for option in item.compilation.typed_options
                )
            )
            wrong = next(
                option
                for option in target.compilation.typed_options
                if option.input_type_id != target.expected_input_type_id
            )
            self.outputs[target.packet.packet_hash] = {
                "disposition": "typed_input",
                "typed_option_id": wrong.typed_option_id,
            }
        self.calls = 0
        self.local_invocations = 0
        self.provider_responses = 0
        self.provider_failure = provider_failure
        self.pretransport_failure = pretransport_failure
        self.usage_metadata_incomplete = usage_metadata_incomplete
        self.invalid_output = invalid_output
        self.invalid_response = invalid_response
        self.provider_profile_id = provider_profile_id

    def qualification_lifecycle_snapshot(self) -> dict[str, int]:
        return {
            "local_invocations_total": self.local_invocations,
            "provider_submissions_total": self.calls,
            "provider_responses_total": self.provider_responses,
        }

    async def extract(
        self,
        *,
        prompt,
        package,
        model_id,
        response_format,
    ):
        self.local_invocations += 1
        if self.pretransport_failure and self.local_invocations == 1:
            raise Gate2SourceFactRuntimeError(
                "gate2_financial_semantic_v6_prompt_contract_mismatch",
                "test request build failure",
            )
        assert prompt.content == V6_SEMANTIC_SYSTEM_PROMPT
        assert prompt.version == V6_SEMANTIC_PROMPT_VERSION
        assert prompt.hash == sha256_json(V6_SEMANTIC_SYSTEM_PROMPT)
        profile = gate2_provider_profile(self.provider_profile_id)
        self.calls += 1
        choice_schema_hash = sha256_json(
            response_format["json_schema"]["schema"]
        )
        metadata = Gate2ProviderExecutionMetadata(
            provider_id=profile.provider_id,
            provider_profile_id=profile.profile_id,
            provider_profile_revision=gate2_provider_profile_revision(
                profile
            ),
            adapter_id=profile.adapter_id,
            adapter_version=profile.adapter_version,
            requested_model_id=model_id,
            resolved_model_id=model_id,
            provider_response_id=f"response-{self.calls}",
            structured_output_mode=profile.structured_output_mode,
            response_format_type=profile.response_format_type,
            response_format_schema_mode=profile.response_format_schema_mode,
            transport_type=profile.transport_type,
            canonical_request_schema_hash=choice_schema_hash,
            adapted_request_schema_hash=choice_schema_hash,
            schema_transform_count=0,
            duration_ms=5,
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cached_input_tokens=0,
            reasoning_tokens=0,
            finish_reason="stop",
        )
        if self.provider_failure and self.calls == 1:
            raise Gate2SourceFactRuntimeError(
                "financial_semantic_v6_test_provider_failure",
                "test provider failure",
                raw_output={"transport_error_type": "SyntheticFailure"},
                execution_metadata=metadata,
                failure_class="provider_transport",
            )
        self.provider_responses += 1
        content = self.outputs[sha256_json(package)]
        if self.invalid_response and self.calls == 1:
            content = None
        if self.invalid_output and self.calls == 1:
            content = {"disposition": "typed_input", "typed_option_id": "unknown"}
        return Gate2StructuredModelResult(
            content=content,
            fallback_used=False,
            repair_attempt_count=0,
            execution_metadata=metadata,
            economy_budget_receipt=(
                None
                if self.usage_metadata_incomplete and self.calls == 1
                else {
                    "status": "passed",
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "actual_cost_usd": "0.000045",
                }
            ),
        )


def _run(
    *,
    wrong_type: bool = False,
    provider_failure: bool = False,
    pretransport_failure: bool = False,
    usage_metadata_incomplete: bool = False,
    invalid_output: bool = False,
    invalid_response: bool = False,
    exact_model_id: str = V6_EXACT_MODEL_ID,
    provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
):
    fixture = _fixture()
    client = _ExactFakeClient(
        fixture,
        wrong_type=wrong_type,
        provider_failure=provider_failure,
        pretransport_failure=pretransport_failure,
        usage_metadata_incomplete=usage_metadata_incomplete,
        invalid_output=invalid_output,
        invalid_response=invalid_response,
        provider_profile_id=provider_profile_id,
    )
    private: dict[str, dict] = {}
    checkpoints: list[dict] = []
    result = asyncio.run(
        qualify_financial_semantic_v6(
            fixture=fixture,
            model_client=client,
            exact_identity=_preflight(
                fixture,
                exact_model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
            )["exact_identity"],
            private_case_checkpoint=lambda case_id, payload: private.__setitem__(
                case_id,
                payload,
            ),
            safe_checkpoint=checkpoints.append,
        )
    )
    return fixture, client, private, checkpoints, result


def test_one_attempt_runs_ten_semantic_calls_and_passes_exact_gate() -> None:
    fixture, client, private, checkpoints, result = _run()

    assert client.calls == SEMANTIC_CASES_TOTAL
    assert len(private) == SEMANTIC_CASES_TOTAL
    assert result["execution_state"] == "terminal"
    assert result["status"] == "passed"
    assert result["terminal_class"] == MODEL_SAFE_FOR_SHADOW
    assert result["product_gate"] == MODEL_SAFE_FOR_SHADOW
    assert all(value == 0 for value in result["hard_gates"].values())
    assert result["quality"]["typed_precision_basis_points"] == 10_000
    assert result["quality"]["typed_recall_basis_points"] == 10_000
    assert result["attempt_accounting"] == {
        "provider_attempts_total": 1,
        "model_attempts_consumed_total": 1,
        "local_invocations_total": 10,
        "provider_submissions_total": 10,
        "provider_responses_total": 10,
        "semantic_decisions_total": 10,
        "product_admitted_decisions_total": 10,
        "provider_calls_total": 10,
        "semantic_cases_total": 10,
        "technical_cases_total": 2,
        "technical_case_provider_calls_total": 0,
        "hidden_retry_total": 0,
        "fallback_total": 0,
        "repair_total": 0,
    }
    assert result["acceptance"] == {
        "provider_attempts": "EXACTLY_ONE",
        "hidden_retry": "ZERO",
        "exact_evidence": "PRESERVED",
        "product_gate": "MODEL_SAFE_FOR_SHADOW",
    }
    assert result["model_metrics_status"] == "PUBLISHED"
    assert result["cases_total"] == len(fixture.cases) == 12
    assert result["exact_evidence_preserved"] is True
    assert result["raw_private_data_in_receipt"] is False
    assert checkpoints[-1] == result


def test_valid_but_wrong_type_is_terminal_without_retry_and_fails_gate() -> None:
    _, client, private, _, result = _run(wrong_type=True)

    assert client.calls == SEMANTIC_CASES_TOTAL
    assert len(private) == SEMANTIC_CASES_TOTAL
    assert result["execution_state"] == "terminal"
    assert result["status"] == "failed"
    assert result["terminal_class"] == MODEL_SEMANTIC_GATE_FAILED
    assert result["product_gate"] == "MODEL_NOT_SAFE_FOR_SHADOW"
    assert result["hard_gates"]["wrong_type_total"] == 1
    assert result["hard_gates"]["invalid_options_total"] == 0
    assert result["attempt_accounting"]["hidden_retry_total"] == 0
    assert result["attempt_accounting"]["fallback_total"] == 0
    assert result["attempt_accounting"]["repair_total"] == 0
    assert result["exact_evidence_preserved"] is True


def test_safe_receipt_contains_no_exact_choice_or_source_values() -> None:
    _, _, _, _, result = _run()
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert "typed_option_id" not in serialized
    assert "source_value_ref" not in serialized
    assert "literal_value" not in serialized
    assert "provider_response_id\"" not in serialized
    assert "exact_canonical_request_object" not in serialized
    assert "normalized_semantic_choice" not in serialized


def test_provider_failure_preserves_available_evidence_and_does_not_retry() -> None:
    _, client, private, _, result = _run(provider_failure=True)

    assert client.calls == SEMANTIC_CASES_TOTAL
    assert len(private) == SEMANTIC_CASES_TOTAL
    failed = private["syn_successor_v2_unique_cash"]
    assert failed["exact_model_output"] == {
        "transport_error_type": "SyntheticFailure"
    }
    assert failed["failure_class"] == "provider_transport"
    assert failed["terminal_class"] == PROVIDER_TRANSPORT_FAILED
    assert result["execution_state"] == "terminal"
    assert result["terminal_class"] == PROVIDER_TRANSPORT_FAILED
    assert result["product_gate"] is None
    assert result["quality"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"
    assert result["hard_gates"]["canonical_failures_total"] == 1
    assert result["attempt_accounting"]["provider_submissions_total"] == 10
    assert result["attempt_accounting"]["provider_responses_total"] == 9
    assert result["attempt_accounting"]["semantic_decisions_total"] == 9
    assert result["attempt_accounting"]["hidden_retry_total"] == 0
    assert result["exact_evidence_preserved"] is True


def test_pretransport_case_has_zero_submission_and_no_model_metrics() -> None:
    _, client, _, _, result = _run(pretransport_failure=True)

    assert client.local_invocations == SEMANTIC_CASES_TOTAL
    assert client.calls == SEMANTIC_CASES_TOTAL - 1
    assert result["terminal_class"] == REQUEST_BUILD_FAILED
    assert result["product_gate"] is None
    assert result["quality"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"
    accounting = result["attempt_accounting"]
    assert accounting["local_invocations_total"] == SEMANTIC_CASES_TOTAL
    assert accounting["provider_submissions_total"] == (
        SEMANTIC_CASES_TOTAL - 1
    )
    assert accounting["provider_attempts_total"] == 1
    failed = next(
        item for item in result["case_receipts"] if item["status"] == "failed"
    )
    assert failed["provider_calls_total"] == 0
    assert failed["terminal_class"] == REQUEST_BUILD_FAILED


def test_all_pretransport_failures_consume_zero_model_attempts() -> None:
    fixture = _fixture()
    client = _ExactFakeClient(fixture, pretransport_failure=True)
    client.pretransport_failure = True

    async def always_pretransport(**_kwargs):
        client.local_invocations += 1
        raise Gate2SourceFactRuntimeError(
            "gate2_financial_semantic_v6_prompt_contract_mismatch",
            "test request build failure",
        )

    client.extract = always_pretransport
    result = asyncio.run(
        qualify_financial_semantic_v6(
            fixture=fixture,
            model_client=client,
            exact_identity=_preflight(fixture)["exact_identity"],
            private_case_checkpoint=lambda _case_id, _payload: None,
        )
    )

    accounting = result["attempt_accounting"]
    assert result["terminal_class"] == REQUEST_BUILD_FAILED
    assert accounting["local_invocations_total"] == SEMANTIC_CASES_TOTAL
    assert accounting["provider_submissions_total"] == 0
    assert accounting["provider_attempts_total"] == 0
    assert accounting["model_attempts_consumed_total"] == 0
    assert result["acceptance"]["provider_attempts"] == "ZERO"


def test_provider_usage_metadata_defect_has_separate_terminal() -> None:
    _, _, _, _, result = _run(usage_metadata_incomplete=True)

    assert result["terminal_class"] == PROVIDER_USAGE_METADATA_INCOMPLETE
    assert result["product_gate"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"
    assert result["attempt_accounting"]["provider_submissions_total"] == 10
    assert result["attempt_accounting"]["provider_responses_total"] == 10
    assert result["attempt_accounting"]["semantic_decisions_total"] == 9


def test_invalid_model_choice_has_schema_terminal_without_metrics() -> None:
    _, _, _, _, result = _run(invalid_output=True)

    assert result["terminal_class"] == MODEL_OUTPUT_SCHEMA_FAILED
    assert result["product_gate"] is None
    assert result["quality"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"
    assert result["attempt_accounting"]["semantic_decisions_total"] == 9


def test_invalid_provider_response_has_non_model_terminal() -> None:
    _, _, _, _, result = _run(invalid_response=True)

    assert result["terminal_class"] == PROVIDER_RESPONSE_INVALID
    assert result["product_gate"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"


def test_terminal_taxonomy_is_exact_and_explicit() -> None:
    assert V6_QUALIFICATION_TERMINAL_CLASSES == (
        "LOCAL_PREFLIGHT_FAILED",
        "REQUEST_BUILD_FAILED",
        "PROVIDER_TRANSPORT_FAILED",
        "PROVIDER_RESPONSE_INVALID",
        "PROVIDER_USAGE_METADATA_INCOMPLETE",
        "MODEL_OUTPUT_SCHEMA_FAILED",
        "MODEL_SEMANTIC_GATE_FAILED",
        "PRODUCT_VALIDATION_FAILED",
        "PRODUCT_MATERIALIZATION_FAILED",
        "MODEL_SAFE_FOR_SHADOW",
    )


def test_goal12_preflight_changes_only_one_exact_candidate() -> None:
    fixture = _fixture()
    nano = json.loads(
        (
            ROOT.parents[1]
            / "docs"
            / "reports"
            / "2026-07-27"
            / (
                "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_"
                "NANO_QUALIFICATION.receipt.safe.json"
            )
        ).read_text(encoding="utf-8")
    )
    receipt = (
        Gate2FinancialSemanticV6StrongerCandidatePreflightFactory().create(
            fixture=fixture,
            repository_revision="a" * 40,
            stage_action={
                "content_sha256": "b" * 64,
                "v6_qualification_snapshot_hash": (
                    V6_QUALIFICATION_PUBLICATION_HASH
                ),
                "production_admissions_empty": True,
                "checks": {
                    "content_hash_exact": True,
                    "active": True,
                },
            },
            published_model_ids={V6_GOAL12_EXACT_MODEL_ID},
            nano_terminal_receipt=nano,
        )
    )
    candidate = receipt["exact_identity"]
    nano_identity = nano["exact_identity"]

    assert receipt["acceptance"] == {
        "architecture": "FROZEN",
        "one_new_candidate": "EXACT",
        "model_comparison": "SAME_V6_WORKLOAD",
        "provider_calls": "ZERO",
    }
    assert candidate["model_provider"]["exact_model_id"] == (
        V6_GOAL12_EXACT_MODEL_ID
    )
    assert candidate["model_provider"]["provider_profile_id"] == (
        V6_GOAL12_PROVIDER_PROFILE_ID
    )
    for key in (
        "evidence_bundle_schema",
        "typed_option_schema",
        "semantic_packet_schema",
        "semantic_choice_schema",
        "compact_pack_projection",
        "prompt",
        "ambiguity_policy",
        "provider_schema",
        "benchmark",
        "execution_identity",
        "evidence_contract",
        "attempt_policy",
    ):
        assert candidate[key] == nano_identity[key]
    assert receipt["execution_accounting"]["provider_calls_total"] == 0
    assert receipt["production_admissions_total"] == 0


def test_goal12_candidate_uses_same_terminal_runner_without_prompt_drift() -> None:
    fixture, client, private, _, result = _run(
        exact_model_id=V6_GOAL12_EXACT_MODEL_ID,
        provider_profile_id=V6_GOAL12_PROVIDER_PROFILE_ID,
    )

    assert client.calls == SEMANTIC_CASES_TOTAL
    assert len(private) == SEMANTIC_CASES_TOTAL
    assert result["execution_state"] == "terminal"
    assert result["product_gate"] == "MODEL_SAFE_FOR_SHADOW"
    assert result["exact_identity"]["model_provider"]["exact_model_id"] == (
        V6_GOAL12_EXACT_MODEL_ID
    )
    assert result["attempt_accounting"]["hidden_retry_total"] == 0
    case = fixture.semantic_cases[0]
    safe = next(
        item["safe_decision_receipt"]
        for item in result["case_receipts"]
        if item["case_id"] == case.case_id
    )
    replay = replay_financial_semantic_v6_decision(
        private_evidence=private[case.case_id],
        safe_receipt=safe,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
        registry=fixture.registry,
    )
    assert replay.status == "EXACT"
    assert replay.provider_calls_total == 0


def test_terminal_runner_classifies_unowned_pair_as_local_preflight() -> None:
    fixture = _fixture()
    identity = _preflight(fixture)["exact_identity"]
    identity["model_provider"]["exact_model_id"] = "gpt-unowned-candidate"
    identity["identity_hash"] = sha256_json(
        {
            key: value
            for key, value in identity.items()
            if key != "identity_hash"
        }
    )
    client = _ExactFakeClient(fixture)

    result = asyncio.run(
        qualify_financial_semantic_v6(
            fixture=fixture,
            model_client=client,
            exact_identity=identity,
            private_case_checkpoint=lambda _case_id, _payload: None,
        )
    )

    assert client.calls == 0
    assert result["terminal_class"] == LOCAL_PREFLIGHT_FAILED
    assert result["failure_code"] == (
        "financial_semantic_v6_qualification_identity_invalid"
    )
    assert result["product_gate"] is None
    assert result["model_metrics_status"] == "NOT_PUBLISHED"
    assert result["attempt_accounting"]["provider_attempts_total"] == 0
