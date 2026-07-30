from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    estimate_gate2_request_input_tokens,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
    Gate2FinancialSemanticV6ChoiceError,
    normalize_financial_semantic_v6_type_first_response,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (  # noqa: E402,E501
    TYPE_FIRST_LOGICAL_REQUEST_MAX_UTF8_BYTES,
    Gate2FinancialSemanticV6ContextLintError,
    Gate2FinancialSemanticV6ContextLinterFactory,
    validate_financial_semantic_v6_type_first_logical_request_budget,
    validate_financial_semantic_v6_type_first_sealed_request,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    TYPE_FIRST_BLOCKS,
    TYPE_FIRST_TASK,
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    validate_financial_semantic_v6_type_first_material,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (  # noqa: E402,E501
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-type-first-inactive-test-snapshot-key"
CONTINUATION_KEY = b"v6-type-first-inactive-test-continuation-key"


@pytest.fixture(scope="module")
def v6_fixture():
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(
            V6_BASE_MANIFEST_PATH.read_text(encoding="utf-8")
        ),
    )


def _model_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _case_args(case) -> dict:
    return {
        "packet": case.packet,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }


def _materials(case, v6_fixture):
    candidate, mapping_receipt = Gate2FinancialSemanticV6PacketFactory(
        registry=v6_fixture.registry
    ).create_type_first_candidate(**_case_args(case))
    response_profile = (
        Gate2FinancialSemanticV6ChoiceContractFactory(
            registry=v6_fixture.registry
        ).create_type_first_response_profile(
            **_case_args(case),
            type_first_candidate=candidate,
            mapping_receipt=mapping_receipt,
        )
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": response_profile.canonical_schema(),
        },
    }
    sealed_request = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    ).create_type_first(
        **_case_args(case),
        choice_contract=case.choice_contract,
        type_first_candidate=candidate,
        response_profile=response_profile,
        system_message=V6_SEMANTIC_SYSTEM_PROMPT,
        serialized_context=_model_bytes(candidate.payload).decode("utf-8"),
        response_format=response_format,
        mapping_receipt=mapping_receipt,
    )
    return candidate, mapping_receipt, response_profile, sealed_request


def _reseal_mapping_receipt(receipt, **changes):
    draft = replace(receipt, **changes, integrity_sha256="")
    return replace(
        draft,
        integrity_sha256=sha256_json(draft.integrity_payload()),
    )


def test_type_first_candidate_reuses_exact_context_v2_1_semantics(
    v6_fixture,
) -> None:
    for case in v6_fixture.semantic_cases:
        active_packet_before = copy.deepcopy(case.packet)
        candidate, receipt, _, _ = _materials(case, v6_fixture)

        assert tuple(candidate.payload) == TYPE_FIRST_BLOCKS
        assert candidate.payload["task"] == TYPE_FIRST_TASK
        assert (
            candidate.payload["source"]
            == case.packet.context_v2_candidate.payload["source"]
        )
        assert (
            candidate.payload["type_cards"]
            == case.packet.context_v2_candidate.payload["type_cards"]
        )
        assert candidate.active is False
        assert candidate.transport_eligible is False
        assert candidate.provider_calls_total == 0
        assert receipt.visible_type_card_order == tuple(
            item["type_key"]
            for item in candidate.payload["type_cards"]
        )
        assert receipt.local_to_canonical_type_ids == {
            item["type_key"]: item["input_type_id"]
            for item in case.packet.context_v2_mapping_receipt.type_mappings
        }
        assert receipt.integrity_sha256 == sha256_json(
            receipt.integrity_payload()
        )
        assert case.packet == active_packet_before


def test_type_first_mapping_receipt_fails_closed_by_drift_class(
    v6_fixture,
) -> None:
    case = v6_fixture.semantic_cases[0]
    candidate, receipt, _, _ = _materials(case, v6_fixture)
    validator_args = {
        **_case_args(case),
        "registry": v6_fixture.registry,
    }

    changed_payload = copy.deepcopy(candidate.payload)
    changed_payload["source"] = {"document": {"children": []}}
    with pytest.raises(Gate2FinancialSemanticV6PacketError) as source_exc:
        validate_financial_semantic_v6_type_first_material(
            **validator_args,
            candidate=replace(candidate, payload=changed_payload),
            receipt=receipt,
        )
    assert source_exc.value.code == "source_hash_drift"

    changed_pack = copy.deepcopy(receipt.semantic_pack_identity)
    changed_pack["integrity_sha256"] = "0" * 64
    with pytest.raises(Gate2FinancialSemanticV6PacketError) as pack_exc:
        validate_financial_semantic_v6_type_first_material(
            **validator_args,
            candidate=candidate,
            receipt=_reseal_mapping_receipt(
                receipt,
                semantic_pack_identity=changed_pack,
            ),
        )
    assert pack_exc.value.code == "pack_projection_drift"

    changed_evidence = copy.deepcopy(receipt.evidence_bundle_scope)
    changed_evidence["evidence_bundle_id"] = "wrong-bundle"
    with pytest.raises(Gate2FinancialSemanticV6PacketError) as evidence_exc:
        validate_financial_semantic_v6_type_first_material(
            **validator_args,
            candidate=candidate,
            receipt=_reseal_mapping_receipt(
                receipt,
                evidence_bundle_scope=changed_evidence,
            ),
        )
    assert evidence_exc.value.code == "evidence_bundle_scope_mismatch"

    changed_compilation = copy.deepcopy(
        receipt.candidate_compilation_scope
    )
    changed_compilation["candidate_compilation_integrity_sha256"] = (
        "0" * 64
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError
    ) as compilation_exc:
        validate_financial_semantic_v6_type_first_material(
            **validator_args,
            candidate=candidate,
            receipt=_reseal_mapping_receipt(
                receipt,
                candidate_compilation_scope=changed_compilation,
            ),
        )
    assert (
        compilation_exc.value.code
        == "candidate_compilation_scope_mismatch"
    )

    changed_mapping = copy.deepcopy(
        receipt.local_to_canonical_type_ids
    )
    changed_mapping["type_1"] = "wrong-type-id"
    with pytest.raises(Gate2FinancialSemanticV6PacketError) as mapping_exc:
        validate_financial_semantic_v6_type_first_material(
            **validator_args,
            candidate=candidate,
            receipt=_reseal_mapping_receipt(
                receipt,
                local_to_canonical_type_ids=changed_mapping,
            ),
        )
    assert mapping_exc.value.code == "mapping_receipt_mismatch"


def test_type_first_schema_and_parser_are_exact_and_fail_closed(
    v6_fixture,
) -> None:
    case = v6_fixture.semantic_cases[0]
    candidate, receipt, profile, _ = _materials(case, v6_fixture)
    assert profile.canonical_schema() == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "plausible_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["type_1", "type_2"],
                },
                "minItems": 0,
                "maxItems": 2,
                "uniqueItems": True,
            }
        },
        "required": ["plausible_types"],
    }
    parser_args = {
        "response_profile": profile,
        "type_first_candidate": candidate,
        "mapping_receipt": receipt,
        "choice_contract": case.choice_contract,
        "packet": case.packet,
    }
    assert normalize_financial_semantic_v6_type_first_response(
        model_output='{"plausible_types":["type_1","type_2"]}',
        **parser_args,
    ) == {
        "plausible_type_keys": ("type_1", "type_2"),
    }
    backend_id = receipt.local_to_canonical_type_ids["type_1"]
    invalid_outputs = (
        ("{", "malformed_json"),
        (
            '{"plausible_types":[],"plausible_types":[]}',
            "duplicate_response_field",
        ),
        ("[]", "response_root_not_object"),
        ("{}", "missing_plausible_types"),
        (
            '{"plausible_types":[],"extra":true}',
            "extra_response_field",
        ),
        ('{"plausible_types":null}', "plausible_types_null"),
        ('{"plausible_types":"type_1"}', "plausible_types_not_array"),
        (
            json.dumps({"plausible_types": [backend_id]}),
            "backend_type_id_forbidden",
        ),
        ('{"plausible_types":["type_3"]}', "unknown_type_key"),
        (
            '{"plausible_types":["type_1","type_1"]}',
            "duplicate_type_key",
        ),
        (
            '{"plausible_types":["type_2","type_1"]}',
            "out_of_order_type_keys",
        ),
    )
    for model_output, expected_code in invalid_outputs:
        with pytest.raises(Gate2FinancialSemanticV6ChoiceError) as exc_info:
            normalize_financial_semantic_v6_type_first_response(
                model_output=model_output,
                **parser_args,
            )
        assert exc_info.value.code == expected_code


def test_type_first_linter_enforces_exact_2500_byte_measurement(
    v6_fixture,
) -> None:
    for case in v6_fixture.semantic_cases:
        candidate, receipt, profile, sealed = _materials(
            case,
            v6_fixture,
        )
        logical_request = {
            "response_schema": profile.canonical_schema(),
            "user_context": copy.deepcopy(candidate.payload),
        }
        logical_bytes = _model_bytes(logical_request)
        assert (
            sealed.sealed_request_receipt.logical_request_utf8_bytes
            == len(logical_bytes)
        )
        assert (
            sealed.sealed_request_receipt.logical_request_sha256
            == hashlib.sha256(logical_bytes).hexdigest()
        )
        assert (
            len(logical_bytes)
            <= TYPE_FIRST_LOGICAL_REQUEST_MAX_UTF8_BYTES
        )
        assert validate_financial_semantic_v6_type_first_logical_request_budget(
            response_schema=profile.canonical_schema(),
            user_context=candidate.payload,
        ) == len(logical_bytes)
        assert sealed.active is False
        assert sealed.transport_eligible is False
        assert sealed.model_visible_request["messages"] == [
            {
                "role": "system",
                "content": V6_SEMANTIC_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": _model_bytes(candidate.payload).decode("utf-8"),
            },
        ]
        validate_financial_semantic_v6_type_first_sealed_request(
            sealed_request=sealed,
            **_case_args(case),
            choice_contract=case.choice_contract,
            type_first_candidate=candidate,
            response_profile=profile,
            registry=v6_fixture.registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=receipt,
        )

    with pytest.raises(Gate2FinancialSemanticV6ContextLintError) as exc_info:
        validate_financial_semantic_v6_type_first_logical_request_budget(
            response_schema={},
            user_context={"oversized": "x" * 2_500},
        )
    assert (
        exc_info.value.code
        == "type_first_logical_request_budget_exceeded"
    )


def test_type_first_request_builder_requires_exact_integrity_bound_seal(
    v6_fixture,
) -> None:
    case = v6_fixture.semantic_cases[0]
    _, _, _, sealed = _materials(case, v6_fixture)
    builder = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        )
    )
    before = copy.deepcopy(sealed)
    projected = builder.build_from_sealed_type_first(
        sealed_request=sealed,
        model_id="type-first-test-model",
    )
    assert tuple(projected) == ("messages", "response_format", "model")
    assert projected["messages"] == sealed.model_visible_request["messages"]
    assert (
        projected["response_format"]
        == sealed.model_visible_request["response_format"]
    )
    assert projected["model"] == "type-first-test-model"
    assert "stream" not in projected
    assert sealed == before

    with pytest.raises(Gate2SourceFactRuntimeError) as raw_exc:
        builder.build_from_sealed_type_first(
            sealed_request=sealed.model_visible_request,  # type: ignore[arg-type]
            model_id="type-first-test-model",
        )
    assert (
        raw_exc.value.code
        == "gate2_model_request_sealed_context_required"
    )

    changed_request = copy.deepcopy(sealed.model_visible_request)
    changed_request["messages"][0]["content"] = "resealed-drift"
    with pytest.raises(Gate2SourceFactRuntimeError) as request_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                model_visible_request=changed_request,
            ),
            model_id="type-first-test-model",
        )
    assert request_exc.value.code == "gate2_model_request_invalid"

    tampered_receipt = replace(
        sealed.sealed_request_receipt,
        integrity_sha256="0" * 64,
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as receipt_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                sealed_request_receipt=tampered_receipt,
            ),
            model_id="type-first-test-model",
        )
    assert receipt_exc.value.code == "gate2_model_request_invalid"

    wrong_context_profile_draft = replace(
        sealed.sealed_request_receipt,
        context_profile="wrong-context-profile",
        integrity_sha256="",
    )
    wrong_context_profile_receipt = replace(
        wrong_context_profile_draft,
        integrity_sha256=sha256_json(
            wrong_context_profile_draft.integrity_payload()
        ),
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as context_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                sealed_request_receipt=(
                    wrong_context_profile_receipt
                ),
            ),
            model_id="type-first-test-model",
        )
    assert context_exc.value.code == "gate2_model_request_invalid"

    wrong_profile_draft = replace(
        sealed.sealed_request_receipt,
        request_profile="wrong-profile",
        integrity_sha256="",
    )
    wrong_profile_receipt = replace(
        wrong_profile_draft,
        integrity_sha256=sha256_json(
            wrong_profile_draft.integrity_payload()
        ),
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as profile_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                sealed_request_receipt=wrong_profile_receipt,
            ),
            model_id="type-first-test-model",
    )
    assert profile_exc.value.code == "gate2_model_request_invalid"

    changed_payload = json.loads(sealed.serialized_context)
    changed_payload["task"] = "self-resealed-task-drift"
    changed_serialized_context = _model_bytes(changed_payload).decode(
        "utf-8"
    )
    changed_model_visible_request = copy.deepcopy(
        sealed.model_visible_request
    )
    changed_model_visible_request["messages"][1]["content"] = (
        changed_serialized_context
    )
    changed_logical_request = {
        "response_schema": (
            changed_model_visible_request["response_format"][
                "json_schema"
            ]["schema"]
        ),
        "user_context": changed_payload,
    }
    changed_payload_bytes = _model_bytes(changed_payload)
    changed_logical_request_bytes = _model_bytes(
        changed_logical_request
    )
    changed_model_visible_request_bytes = _model_bytes(
        changed_model_visible_request
    )
    changed_task_draft = replace(
        sealed.sealed_request_receipt,
        context_view_sha256=hashlib.sha256(
            changed_payload_bytes
        ).hexdigest(),
        logical_request_sha256=hashlib.sha256(
            changed_logical_request_bytes
        ).hexdigest(),
        logical_request_utf8_bytes=len(changed_logical_request_bytes),
        model_visible_request_sha256=hashlib.sha256(
            changed_model_visible_request_bytes
        ).hexdigest(),
        model_visible_request_utf8_bytes=len(
            changed_model_visible_request_bytes
        ),
        estimated_input_tokens=estimate_gate2_request_input_tokens(
            changed_model_visible_request
        ),
        integrity_sha256="",
    )
    changed_task_receipt = replace(
        changed_task_draft,
        integrity_sha256=sha256_json(
            changed_task_draft.integrity_payload()
        ),
    )
    with pytest.raises(AttributeError):
        setattr(
            sealed._request_builder_seal,
            "_receipt_integrity_sha256",
            changed_task_receipt.integrity_sha256,
        )
    with pytest.raises(AttributeError):
        object.__setattr__(
            sealed._request_builder_seal,
            "_receipt_integrity_sha256",
            changed_task_receipt.integrity_sha256,
        )
    with pytest.raises(Gate2SourceFactRuntimeError) as task_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                serialized_context=changed_serialized_context,
                model_visible_request=changed_model_visible_request,
                sealed_request_receipt=changed_task_receipt,
            ),
            model_id="type-first-test-model",
        )
    assert task_exc.value.code == "gate2_model_request_invalid"

    with pytest.raises(Gate2SourceFactRuntimeError) as wrapper_exc:
        builder.build_from_sealed_type_first(
            sealed_request=replace(
                sealed,
                serialized_context="{}",
            ),
            model_id="type-first-test-model",
        )
    assert wrapper_exc.value.code == "gate2_model_request_invalid"

    wrong_builder = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as builder_exc:
        wrong_builder.build_from_sealed_type_first(
            sealed_request=sealed,
            model_id="type-first-test-model",
        )
    assert builder_exc.value.code == "gate2_model_request_profile_mismatch"


def test_type_first_sealed_request_replay_rejects_tampering(
    v6_fixture,
) -> None:
    case = v6_fixture.semantic_cases[0]
    candidate, receipt, profile, sealed = _materials(case, v6_fixture)
    changed_request = copy.deepcopy(sealed.model_visible_request)
    changed_request["unexpected"] = True
    tampered = replace(sealed, model_visible_request=changed_request)

    with pytest.raises(Gate2FinancialSemanticV6ContextLintError) as exc_info:
        validate_financial_semantic_v6_type_first_sealed_request(
            sealed_request=tampered,
            **_case_args(case),
            choice_contract=case.choice_contract,
            type_first_candidate=candidate,
            response_profile=profile,
            registry=v6_fixture.registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=receipt,
        )
    assert exc_info.value.code == "type_first_sealed_replay_mismatch"
