from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import pytest

from broker_reports_gate1.gate2_model_clients import (
    Gate2OpenWebUIStructuredModelClient,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.managed_pdf_to_canonical import (
    ManagedPdfToCanonicalFactory,
    _ManagedPdfSemanticReviewProviderBuilder,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MANAGED_DOCUMENT_SEMANTIC_EVIDENCE_SCHEMA_VERSION,
    MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
    MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
    _managed_semantic_critic_model_request,
    _managed_semantic_proposal_model_request,
)
from tests.test_broker_reports_managed_document_semantic_evidence_v1 import (
    TITLE_INJECTION,
    USER_SCOPE_SHA256,
    _builder,
    _injection_continuation_pdf,
    _observations,
)
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
)


MODEL_ID = "gpt-5.6-sol"


class _SemanticCompletionBoundary:
    def __init__(
        self, *, fail_phase: str | None = None, invalid_proposal: bool = False
    ) -> None:
        self.fail_phase = fail_phase
        self.invalid_proposal = invalid_proposal
        self.calls: list[dict[str, Any]] = []

    def resolve(self, user_id: str):
        return self.complete, SimpleNamespace(id=user_id, role="user")

    def complete(self, *, request, form_data, user, **_kwargs):
        package = json.loads(form_data["messages"][1]["content"])
        phase = package["phase"]
        self.calls.append(copy.deepcopy(form_data))
        if self.fail_phase == phase:
            raise RuntimeError(f"{phase}_boundary_failure")
        if phase == "managed_semantic_proposal":
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "tables": [
                    {
                        "table_ref": table["table_ref"],
                        "options": [
                            {
                                "disposition": "SAFE_AUXILIARY",
                                "columns": [],
                                "amount_currency_bindings": [],
                                "side_values": [],
                            }
                        ],
                    }
                    for table in package["evidence"]["tables"]
                ],
            }
            if self.invalid_proposal:
                output["tables"] = []
        else:
            assert phase == "managed_semantic_critic"
            assert all(
                "mapping_candidate" not in option
                for table in package["host_options"]
                for option in table["options"]
            )
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "proposal_ref": package["proposal_ref"],
                "tables": [
                    {
                        "table_ref": table["table_ref"],
                        "decision": "SELECT_OPTION",
                        "option_ref": table["options"][0]["option_ref"],
                    }
                    for table in package["host_options"]
                ],
            }
        return {
            "id": f"semantic-{len(self.calls)}",
            "model": MODEL_ID,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "choices": [
                {"finish_reason": "stop", "message": {"content": output}}
            ],
        }


def _provider_builder(request: Any):
    base = _builder(request)
    return ManagedPdfToCanonicalFactory().create_semantic_review_for_openwebui(
        base.schema,
        request,
        SimpleNamespace(id="semantic-user", role="user"),
        normalizer_config=base.normalizer_config,
        provider_profile_id="openai_gpt",
    )


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    semantic_boundary: _SemanticCompletionBoundary,
    observations: dict[str, Any] | list[dict[str, Any]],
):
    pdf_bytes = _injection_continuation_pdf()
    request = _openwebui_request()
    generations = (
        observations if isinstance(observations, list) else [observations, observations]
    )
    with _GeminiBoundary(generations) as visual_boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=visual_boundary,
        )
        monkeypatch.setattr(
            Gate2OpenWebUIStructuredModelClient,
            "_resolve_openwebui_completion_dependencies",
            lambda _self, user_id: semantic_boundary.resolve(user_id),
        )
        result = await _provider_builder(request).build_with_semantic_provider_review(
            pdf_bytes,
            tenant_id="tenant",
            artifact_version=1,
            source_artifact_ref="private_pdf_semantic_provider_review",
            task_id="semantic_provider_review",
            user_scope_sha256=USER_SCOPE_SHA256,
            proposal_model_id=MODEL_ID,
            critic_model_id=MODEL_ID,
            created_at="2026-08-30T00:00:00Z",
        )
    return result


@pytest.mark.asyncio
async def test_raw_pdf_success_has_exactly_two_semantic_submissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _injection_continuation_pdf()
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref="private_pdf_semantic_provider_review",
    ).payloads[0]
    boundary = _SemanticCompletionBoundary()
    result = await _run(
        monkeypatch,
        semantic_boundary=boundary,
        observations=_observations(payload),
    )
    assert result.status == "REVIEWED_CANDIDATE"
    assert result.semantic_review_contract is not None
    assert result.semantic_review_contract["record_candidates"] == []
    assert result.execution_receipt["provider_submissions"] == 2
    assert result.execution_receipt["provider_responses"] == 2
    assert result.execution_receipt["local_invocations"] == 2
    assert result.execution_receipt["retry_count"] == 0
    assert len(boundary.calls) == 2
    packages = [json.loads(call["messages"][1]["content"]) for call in boundary.calls]
    assert [item["phase"] for item in packages] == [
        "managed_semantic_proposal",
        "managed_semantic_critic",
    ]
    assert packages[0]["evidence"] == packages[1]["evidence"]
    assert packages[0]["evidence_scope_ref"] == packages[1]["evidence_scope_ref"]
    assert packages[1]["proposal_ref"].startswith("semantic_proposal_")
    assert packages[1]["host_options"][0]["options"][0][
        "option_ref"
    ].startswith("semantic_option_")
    assert boundary.calls[0]["messages"][0] != boundary.calls[1]["messages"][0]
    assert TITLE_INJECTION not in boundary.calls[0]["messages"][0]["content"]
    assert TITLE_INJECTION not in boundary.calls[1]["messages"][0]["content"]
    assert [call["response_format"]["json_schema"]["name"] for call in boundary.calls] == [
        "managed_document_semantic_proposal_v1",
        "managed_document_semantic_critic_v1",
    ]
    assert [
        call["metadata"]["broker_reports_managed_semantic_review"]["phase"]
        for call in boundary.calls
    ] == ["managed_semantic_proposal", "managed_semantic_critic"]
    assert all(
        item["fallback_used"] is False and item["repair_attempt_count"] == 0
        for item in result.execution_receipt["executions"]
    )
    evidence = result.evidence_result.semantic_evidence
    review = result.semantic_review_contract
    assert evidence is not None and review is not None
    proposal_prompt, _, _ = _managed_semantic_proposal_model_request(evidence)
    critic_prompt, _, _ = _managed_semantic_critic_model_request(
        evidence=evidence,
        options=review["table_options"],
        proposal_ref=review["proposal_ref"],
    )
    for prompt in (proposal_prompt, critic_prompt):
        assert (
            prompt.input_schema_version
            == MANAGED_DOCUMENT_SEMANTIC_EVIDENCE_SCHEMA_VERSION
        )
        assert prompt.safe_metadata == {
            "runtime_active": False,
            "broker_specific": False,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_phase", "expected_calls", "reason"),
    [
        ("managed_semantic_proposal", 1, "PROPOSAL_PROVIDER_FAILED"),
        ("managed_semantic_critic", 2, "CRITIC_PROVIDER_FAILED"),
    ],
)
async def test_provider_failure_stops_without_retry_or_candidates(
    monkeypatch: pytest.MonkeyPatch,
    failure_phase: str,
    expected_calls: int,
    reason: str,
) -> None:
    pdf_bytes = _injection_continuation_pdf()
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref="private_pdf_semantic_provider_review",
    ).payloads[0]
    boundary = _SemanticCompletionBoundary(fail_phase=failure_phase)
    result = await _run(
        monkeypatch,
        semantic_boundary=boundary,
        observations=_observations(payload),
    )
    assert result.status == "BLOCKED"
    assert result.reason_code == reason
    assert result.semantic_review_contract is None
    assert result.execution_receipt["provider_submissions"] == expected_calls
    assert result.execution_receipt["local_invocations"] == expected_calls
    assert result.execution_receipt["provider_responses"] == expected_calls - 1
    assert result.execution_receipt["retry_count"] == 0
    assert result.execution_receipt["record_candidates_created"] == 0
    assert len(boundary.calls) == expected_calls


@pytest.mark.asyncio
async def test_invalid_proposal_response_stops_before_critic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _injection_continuation_pdf()
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref="private_pdf_semantic_provider_review",
    ).payloads[0]
    boundary = _SemanticCompletionBoundary(invalid_proposal=True)
    result = await _run(
        monkeypatch,
        semantic_boundary=boundary,
        observations=_observations(payload),
    )
    assert result.status == "BLOCKED"
    assert result.reason_code == "PROPOSAL_RESPONSE_INVALID"
    assert result.semantic_review_contract is None
    assert result.execution_receipt["local_invocations"] == 1
    assert result.execution_receipt["provider_submissions"] == 1
    assert result.execution_receipt["provider_responses"] == 1
    assert len(boundary.calls) == 1


@pytest.mark.asyncio
async def test_evidence_failure_makes_zero_semantic_submissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _SemanticCompletionBoundary()
    pdf_bytes = _injection_continuation_pdf()
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref="private_pdf_semantic_provider_review",
    ).payloads[0]
    proposal = _observations(payload)
    critic = copy.deepcopy(proposal)
    critic["pages"][0]["tables"][0]["header_boxes_2d"] = copy.deepcopy(
        critic["pages"][0]["tables"][0]["title_boxes_2d"]
    )
    result = await _run(
        monkeypatch,
        semantic_boundary=boundary,
        observations=[proposal, critic],
    )
    assert result.status == "BLOCKED"
    assert result.reason_code == "SEMANTIC_EVIDENCE_NOT_READY"
    assert result.execution_receipt["provider_submissions"] == 0
    assert result.execution_receipt["provider_responses"] == 0
    assert result.execution_receipt["local_invocations"] == 0
    assert result.execution_receipt["executions"] == []
    assert boundary.calls == []


@pytest.mark.asyncio
async def test_success_result_with_incomplete_lifecycle_is_rejected() -> None:
    metadata = Gate2ProviderExecutionMetadata(
        provider_id="openai",
        provider_profile_id="openai_gpt",
        provider_profile_revision="test",
        adapter_id="openai_response_format",
        adapter_version="test",
        requested_model_id=MODEL_ID,
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
    )

    class IncompleteLifecycleClient:
        def __init__(self) -> None:
            self.completed = False

        async def extract(self, **_kwargs):
            self.completed = True
            return Gate2StructuredModelResult(
                content={"unexpected": True}, execution_metadata=metadata
            )

        def qualification_lifecycle_snapshot(self):
            return {
                "local_invocations_total": int(self.completed),
                "provider_submissions_total": int(self.completed),
                "provider_responses_total": 0,
            }

    accounting = {
        "local_invocations": 0,
        "provider_submissions": 0,
        "provider_responses": 0,
    }
    executions: list[dict[str, Any]] = []
    content, failure = await _ManagedPdfSemanticReviewProviderBuilder._call_once(
        client=IncompleteLifecycleClient(),
        phase="PROPOSAL",
        prompt=object(),
        package={},
        model_id=MODEL_ID,
        response_format={},
        accounting=accounting,
        executions=executions,
    )
    assert content is None
    assert failure == "PROPOSAL_PROVIDER_FAILED"
    assert accounting == {
        "local_invocations": 1,
        "provider_submissions": 1,
        "provider_responses": 0,
    }
    assert executions == []
