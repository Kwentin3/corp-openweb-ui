from __future__ import annotations

import copy
import json
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

import pytest

import broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_provider_proof as provider_proof_module
import broker_reports_gate1.gate2_provider_adapters as provider_adapter_module
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (
    CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_provider_proof import (
    CONTEXT_V2_1_LOCAL_PROJECTION_MODEL_IDS,
    CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION,
    CONTEXT_V2_1_PROVIDER_PROOF_SCHEMA_VERSION,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialSemanticV6ContextV21ProviderProofError,
    Gate2FinancialSemanticV6ContextV21ProviderProofFactory,
    validate_financial_semantic_v6_context_v2_1_provider_case_proof,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit import (
    NEW_REASON_CODE,
    validate_financial_semantic_v6_outcome_audit,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    Gate2FinancialSemanticV6DecisionEvidenceError,
    replay_financial_semantic_v6_context_v2_1_decision,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_smoke_report import (
    CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION,
    CONTEXT_V2_1_PROVIDER_PROOF_CASES,
    CONTEXT_V2_1_PROVIDER_PROOF_PROFILES,
    CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION,
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
    Gate2FinancialSemanticV6TransparentSmokeReportError,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
HISTORICAL_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6"
    / "manifest.json"
)
BASE_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
CATALOG_V2_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
PROOF_MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v6_context_v2_1_provider_proof.py"
)
SNAPSHOT_AUTHORITY_KEY = b"context-v2-1-provider-proof-snapshot-key-32"
CONTINUATION_KEY = b"context-v2-1-provider-proof-continuation-key-32"
CASE_IDS = tuple(CONTEXT_V2_1_PROVIDER_PROOF_CASES)
PROVIDER_PROFILE_IDS = CONTEXT_V2_1_PROVIDER_PROOF_PROFILES
PROVIDER_CASE_PARAMS = tuple(product(PROVIDER_PROFILE_IDS, CASE_IDS))
ZERO_ACCOUNTING = {
    "provider_calls_total": 0,
    "semantic_repair_total": 0,
    "fallback_total": 0,
    "retry_total": 0,
}
ACTIVE_CHOICE_SCHEMA_HASHES = {
    "syn_successor_v2_unique_cash": (
        "883381d22afd40c398e1c07040e4de456a4f14d8d4a0f3528e2f78b85664a45b"
    ),
    "syn_successor_v2_no_registry_type": (
        "10a54d609f1658982b18b12ed3a4ac1a8c0b39a3e35dcbfdf02af79abe728d7f"
    ),
    "syn_successor_v2_multiple_compatible": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
}
EXPECTED_PROFILES = {
    "openai_gpt": {
        "provider_id": "openai",
        "adapter_id": "openai_response_format",
        "adapter_version": "1.1.0",
        "structured_output_mode": "openwebui_response_format_json_schema",
        "local_model_id": "local-proof-openai-profile-v1",
    },
    "anthropic_claude": {
        "provider_id": "anthropic",
        "adapter_id": "anthropic_native_messages",
        "adapter_version": "1.2.0",
        "structured_output_mode": (
            "openwebui_anthropic_output_config_json_schema"
        ),
        "local_model_id": "local-proof-anthropic-profile-v1",
    },
    "google_gemini": {
        "provider_id": "google",
        "adapter_id": "gemini_response_format",
        "adapter_version": "1.7.0",
        "structured_output_mode": "openwebui_response_format_json_schema",
        "local_model_id": "local-proof-google-profile-v1",
    },
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _audit_inputs() -> dict[str, dict[str, Any]]:
    return {
        "manifest": _read(AUDIT_PATH),
        "historical_manifest": _read(HISTORICAL_PATH),
        "base_manifest": _read(BASE_PATH),
        "semantic_pack": _read(PACK_PATH),
        "reason_catalog_v2": _read(CATALOG_V2_PATH),
    }


def _expected_answer(case: Any, audit_case: dict[str, Any]) -> dict[str, str]:
    assert audit_case["expected_route"] == "semantic_model"
    if audit_case["expected_disposition"] == "typed_input":
        matches = tuple(
            option
            for option in case.compilation.typed_options
            if option.input_type_id == audit_case["expected_input_type_id"]
        )
        assert len(matches) == 1
        return {
            "disposition": "typed_input",
            "typed_option_id": matches[0].typed_option_id,
        }
    assert audit_case["expected_disposition"] == (
        "unclassified_financial_input"
    )
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": audit_case["expected_reason_code"],
    }


def _local_answer(case: Any, expected: dict[str, str]) -> dict[str, str]:
    if expected["disposition"] == "unclassified_financial_input":
        return {
            "choice": "unclassified",
            "reason": expected["reason_code"],
        }
    restoration = tuple(
        item
        for item in case.packet.context_v2_mapping_receipt.choice_restoration
        if item["typed_option_id"] == expected["typed_option_id"]
    )
    assert len(restoration) == 1
    return {"choice": restoration[0]["choice_key"]}


def _simulated_provider_response(
    provider_profile_id: str,
    model_output: dict[str, Any] | str,
) -> dict[str, Any]:
    if isinstance(model_output, dict):
        visible_output: Any = copy.deepcopy(model_output)
        if provider_profile_id == "openai_gpt":
            visible_output = {
                "broker_reports_gate2_choice": visible_output,
            }
        content = json.dumps(
            visible_output,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    else:
        content = model_output
    if provider_profile_id == "anthropic_claude":
        return {
            "content": [{"type": "text", "text": content}],
            "stop_reason": "end_turn",
        }
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content},
            }
        ]
    }


def _decoded_adapter_output(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    assert isinstance(value, dict)
    return value


def _semantic_enums(value: Any) -> dict[str, tuple[tuple[Any, ...], ...]]:
    found: dict[str, list[tuple[Any, ...]]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                for name, schema in properties.items():
                    if (
                        name in {"choice", "reason"}
                        and isinstance(schema, dict)
                        and isinstance(schema.get("enum"), list)
                    ):
                        found.setdefault(name, []).append(
                            tuple(copy.deepcopy(schema["enum"]))
                        )
                    visit(schema)
            for name, child in node.items():
                if name != "properties":
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return {
        name: tuple(
            sorted(
                enums,
                key=lambda item: json.dumps(
                    item,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
            )
        )
        for name, enums in sorted(found.items())
    }


def _expected_provider_schema(
    *,
    provider_profile_id: str,
    canonical_schema: dict[str, Any],
) -> dict[str, Any]:
    if provider_profile_id != "openai_gpt":
        return copy.deepcopy(canonical_schema)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "broker_reports_gate2_choice": copy.deepcopy(canonical_schema),
        },
        "required": ["broker_reports_gate2_choice"],
    }


def _expected_final_provider_request(
    *,
    provider_profile_id: str,
    proof: Any,
) -> dict[str, Any]:
    contract = EXPECTED_PROFILES[provider_profile_id]
    model_visible = proof.sealed_request["model_visible_request"]
    messages = model_visible["messages"]
    if provider_profile_id == "anthropic_claude":
        return {
            "model": contract["local_model_id"],
            "max_tokens": 32768,
            "messages": [copy.deepcopy(messages[1])],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": copy.deepcopy(
                        proof.provider_visible_response_schema
                    ),
                }
            },
            "system": messages[0]["content"],
        }
    expected = copy.deepcopy(model_visible)
    expected["response_format"]["json_schema"]["schema"] = copy.deepcopy(
        proof.provider_visible_response_schema
    )
    if provider_profile_id == "openai_gpt":
        expected["response_format"]["json_schema"]["name"] = (
            "broker_reports_gate2_choice"
        )
    expected["model"] = contract["local_model_id"]
    expected["metadata"] = {
        "broker_reports_gate2": {
            "provider_profile_id": provider_profile_id,
            "provider_adapter_id": contract["adapter_id"],
            "provider_adapter_version": contract["adapter_version"],
            "structured_output_mode": contract["structured_output_mode"],
        }
    }
    return expected


def _sealed_request_for_case(
    proof_context: dict[str, Any],
    case_id: str,
) -> Any:
    case = proof_context["cases"][case_id]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": (
                case.choice_contract.context_v2_1_response_profile
                .canonical_schema()
            ),
        },
    }
    return Gate2FinancialSemanticV6ContextLinterFactory(
        registry=proof_context["registry"]
    ).create_context_v2_1(
        packet=case.packet,
        choice_contract=case.choice_contract,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
        system_message=V6_SEMANTIC_SYSTEM_PROMPT,
        serialized_context=json.dumps(
            case.packet.context_v2_candidate.payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ),
        response_format=response_format,
        mapping_receipt=case.packet.context_v2_mapping_receipt,
    )


def _prepared_request_for_case(
    proof_context: dict[str, Any],
    provider_profile_id: str,
    case_id: str,
) -> provider_adapter_module.Gate2PreparedProviderRequest:
    sealed_request = _sealed_request_for_case(proof_context, case_id)
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
        )
    ).build_from_sealed_context_v2_1(
        model_visible_request=sealed_request.model_visible_request,
        model_id=proof.local_projection_model_id,
    )
    return provider_adapter_module.Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(provider_profile_id),
    ).create().prepare_form_data(
        form_data=form_data,
        response_format=sealed_request.response_format,
    )


def _assert_direct_prepared_forgery_rejected(
    *,
    proof_context: dict[str, Any],
    provider_profile_id: str,
    case_id: str,
    forged_request: (
        provider_adapter_module.Gate2PreparedProviderRequest
    ),
) -> None:
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    case = proof_context["cases"][case_id]
    sealed_request = _sealed_request_for_case(
        proof_context,
        case_id,
    )
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    canonical_schema = (
        case.choice_contract.context_v2_1_response_profile.canonical_schema()
    )
    binding_kwargs = {
        "canonical_schema": canonical_schema,
        "provider_profile": gate2_provider_profile(
            provider_profile_id
        ),
        "model_visible_request": sealed_request.model_visible_request,
        "local_projection_model_id": proof.local_projection_model_id,
    }
    assert prepared_request.context_v2_1_contract_is_bound(
        **binding_kwargs
    )
    assert not forged_request.context_v2_1_contract_is_bound(
        **binding_kwargs
    )

    evidence_factory = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=proof_context["registry"]
    )
    evidence_kwargs = {
        "case_id": case_id,
        "provider_profile_id": proof.provider_profile_id,
        "provider_adapter_id": proof.provider_adapter_id,
        "provider_adapter_version": proof.provider_adapter_version,
        "local_projection_model_id": proof.local_projection_model_id,
        "sealed_request": sealed_request,
        "adapter_extracted_output": proof.adapter_extracted_output,
        "choice_contract": case.choice_contract,
        "packet": case.packet,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as create_failure:
        evidence_factory.create_context_v2_1_candidate(
            **evidence_kwargs,
            prepared_request=forged_request,
        )
    assert create_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "private_evidence_canonical_schema_mismatch"
    )

    genuine = evidence_factory.create_context_v2_1_candidate(
        **evidence_kwargs,
        prepared_request=prepared_request,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as replay_failure:
        replay_financial_semantic_v6_context_v2_1_decision(
            private_evidence=genuine.private_evidence,
            expected_provider_profile_id=proof.provider_profile_id,
            expected_provider_adapter_id=proof.provider_adapter_id,
            expected_provider_adapter_version=(
                proof.provider_adapter_version
            ),
            expected_local_projection_model_id=(
                proof.local_projection_model_id
            ),
            expected_sealed_request=sealed_request,
            expected_prepared_request=forged_request,
            choice_contract=case.choice_contract,
            packet=case.packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=proof_context["registry"],
        )
    assert replay_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "offline_replay_projection_mismatch"
    )


@pytest.mark.parametrize(
    ("existing_name", "expected_name"),
    (
        (None, "broker_reports_gate2_choice"),
        (
            "broker_reports_gate2_financial_semantic_choice_v6",
            "broker_reports_gate2_financial_semantic_choice_v6",
        ),
    ),
)
def test_openai_root_envelope_projection_has_one_stable_provider_name(
    existing_name: str | None,
    expected_name: str,
) -> None:
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "choice": {
                                "type": "string",
                                "enum": ["choice_1"],
                            },
                        },
                        "required": ["choice"],
                    },
                ],
            },
        },
    }
    if existing_name is not None:
        response_format["json_schema"]["name"] = existing_name
    neutral_contract = copy.deepcopy(response_format)

    prepared = provider_adapter_module.Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile("openai_gpt"),
    ).create().prepare_form_data(
        form_data={"model": "local-proof", "messages": []},
        response_format=response_format,
    )

    assert response_format == neutral_contract
    if existing_name is None:
        assert set(response_format["json_schema"]) == {"strict", "schema"}
    provider_json_schema = prepared.form_data["response_format"][
        "json_schema"
    ]
    assert set(provider_json_schema) == {"name", "strict", "schema"}
    assert provider_json_schema["name"] == expected_name
    assert prepared.schema_transform_count == 1


@pytest.fixture(scope="module")
def proof_context() -> dict[str, Any]:
    audit_inputs = _audit_inputs()
    audit_snapshot = validate_financial_semantic_v6_outcome_audit(
        **audit_inputs
    )
    audit_cases = {
        item["case_id"]: item for item in audit_inputs["manifest"]["cases"]
    }
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    qualification_fixture = (
        Gate2FinancialSemanticV6QualificationFixtureFactory(
            registry=registry,
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create(
            manifest=audit_inputs["historical_manifest"],
            base_manifest=audit_inputs["base_manifest"],
        )
    )
    cases = {
        case.case_id: case for case in qualification_fixture.semantic_cases
    }
    assert set(CASE_IDS) <= set(cases)
    assert set(CASE_IDS) <= set(audit_cases)

    expected_answers = {
        case_id: _expected_answer(cases[case_id], audit_cases[case_id])
        for case_id in CASE_IDS
    }
    local_answers = {
        case_id: _local_answer(cases[case_id], expected_answers[case_id])
        for case_id in CASE_IDS
    }
    responses = {
        (provider_profile_id, case_id): _simulated_provider_response(
            provider_profile_id,
            local_answers[case_id],
        )
        for provider_profile_id, case_id in PROVIDER_CASE_PARAMS
    }
    active_before = {
        case_id: (
            copy.deepcopy(cases[case_id].choice_contract.choice_schema),
            cases[case_id].choice_contract.choice_schema_hash,
        )
        for case_id in CASE_IDS
    }
    factory = Gate2FinancialSemanticV6ContextV21ProviderProofFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    )
    proofs = {
        (provider_profile_id, case_id): factory.create_case(
            case=cases[case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=expected_answers[case_id],
            simulated_provider_response=responses[
                (provider_profile_id, case_id)
            ],
        )
        for provider_profile_id, case_id in PROVIDER_CASE_PARAMS
    }
    return {
        "audit_snapshot": audit_snapshot,
        "audit_cases": audit_cases,
        "historical_manifest": audit_inputs["historical_manifest"],
        "registry": registry,
        "cases": cases,
        "expected_answers": expected_answers,
        "local_answers": local_answers,
        "responses": responses,
        "active_before": active_before,
        "factory": factory,
        "proofs": proofs,
    }


def test_corrected_four_fixture_authority_is_validated_outcome_audit(
    proof_context,
) -> None:
    snapshot = proof_context["audit_snapshot"]
    audit_cases = proof_context["audit_cases"]
    historical_cases = {
        item["case_id"]: item
        for item in proof_context["historical_manifest"]["cases"]
    }
    detail_case_id = "syn_successor_v2_detail_vs_subtotal"

    assert snapshot.cases_total == 12
    assert snapshot.corrected_expected_answers_total == 3
    assert {
        case_id: audit_cases[case_id]["taxonomy_state"]
        for case_id in CASE_IDS
    } == CONTEXT_V2_1_PROVIDER_PROOF_CASES
    assert historical_cases[detail_case_id]["expected_reason_code"] == (
        "ambiguous_registry_type"
    )
    assert audit_cases[detail_case_id]["expected_reason_code"] == (
        NEW_REASON_CODE
    )
    assert proof_context["expected_answers"][detail_case_id] == {
        "disposition": "unclassified_financial_input",
        "reason_code": NEW_REASON_CODE,
    }


@pytest.mark.parametrize(
    ("provider_profile_id", "case_id"),
    PROVIDER_CASE_PARAMS,
    ids=[
        f"{provider_profile_id}-{case_id}"
        for provider_profile_id, case_id in PROVIDER_CASE_PARAMS
    ],
)
def test_all_twelve_provider_case_paths_are_exact_terminal_proofs(
    proof_context,
    provider_profile_id,
    case_id,
) -> None:
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    case = proof_context["cases"][case_id]
    expected_answer = proof_context["expected_answers"][case_id]
    local_answer = proof_context["local_answers"][case_id]
    simulated_response = proof_context["responses"][
        (provider_profile_id, case_id)
    ]
    profile_contract = EXPECTED_PROFILES[provider_profile_id]

    validate_financial_semantic_v6_context_v2_1_provider_case_proof(
        proof=proof,
        factory=proof_context["factory"],
        case=case,
        expected_answer=expected_answer,
        simulated_provider_response=simulated_response,
    )

    assert proof.schema_version == CONTEXT_V2_1_PROVIDER_PROOF_SCHEMA_VERSION
    assert proof.policy_version == CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION
    assert proof.active is False
    assert proof.transport_eligible is False
    assert proof.case_id == case_id
    assert proof.taxonomy_state == CONTEXT_V2_1_PROVIDER_PROOF_CASES[case_id]
    assert proof.provider_profile_id == provider_profile_id
    assert proof.provider_adapter_id == profile_contract["adapter_id"]
    assert proof.provider_adapter_version == (
        profile_contract["adapter_version"]
    )
    assert proof.local_projection_model_id == (
        profile_contract["local_model_id"]
    )
    assert proof.schema_projection_policy_version == (
        provider_adapter_module
        .CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
    )
    assert len(proof.adapter_adapted_schema_hash) == 64
    assert len(proof.adapter_canonical_schema_hash) == 64
    assert CONTEXT_V2_1_LOCAL_PROJECTION_MODEL_IDS[provider_profile_id] == (
        profile_contract["local_model_id"]
    )
    assert proof.integrity_hash == sha256_json(proof.integrity_payload())
    assert proof.execution_accounting == ZERO_ACCOUNTING
    assert proof.simulated_provider_response == simulated_response

    sealed = proof.sealed_request
    assert sealed["active"] is False
    assert sealed["transport_eligible"] is False
    assert sealed["sealed_request_receipt"]["provider_calls_total"] == 0
    assert sealed["model_visible_request"]["messages"] == [
        {"role": "system", "content": V6_SEMANTIC_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": sealed["serialized_context"],
        },
    ]
    assert json.loads(sealed["serialized_context"]) == (
        case.packet.context_v2_candidate.payload
    )
    neutral_json_schema = sealed["model_visible_request"][
        "response_format"
    ]["json_schema"]
    assert set(neutral_json_schema) == {"strict", "schema"}
    assert "name" not in neutral_json_schema

    canonical_schema = (
        case.choice_contract.context_v2_1_response_profile.response_schema
    )
    expected_provider_schema = _expected_provider_schema(
        provider_profile_id=provider_profile_id,
        canonical_schema=canonical_schema,
    )
    assert proof.provider_visible_response_schema == expected_provider_schema
    assert _semantic_enums(proof.provider_visible_response_schema) == (
        _semantic_enums(canonical_schema)
    )
    assert set(_semantic_enums(canonical_schema)) == {"choice", "reason"}
    assert any(
        enum == CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES
        for enum in _semantic_enums(canonical_schema)["reason"]
    )
    assert proof.exact_final_provider_request == (
        _expected_final_provider_request(
            provider_profile_id=provider_profile_id,
            proof=proof,
        )
    )
    if provider_profile_id == "openai_gpt":
        openai_json_schema = proof.exact_final_provider_request[
            "response_format"
        ]["json_schema"]
        assert set(openai_json_schema) == {"name", "strict", "schema"}
        assert openai_json_schema["name"] == "broker_reports_gate2_choice"
    assert _decoded_adapter_output(proof.adapter_extracted_output) == (
        local_answer
    )
    assert proof.normalized_canonical_answer == expected_answer
    assert proof.expected_answer == expected_answer

    totality = proof.total_materialization
    artifact = totality["canonical_artifact"]
    assert totality["validated_but_unmaterializable"] is False
    assert totality["materializer_totality_status"] == (
        "proven_for_expansion"
    )
    assert totality["terminal_disposition"] == expected_answer["disposition"]
    assert totality["canonical_artifact_hash"] == sha256_json(artifact)
    assert len(proof.serialized_private_evidence_hash) == 64
    assert len(proof.restored_private_evidence_hash) == 64
    assert proof.replay_materialized_artifact_hash == (
        totality["canonical_artifact_hash"]
    )
    assert proof.restore_exact is True
    assert proof.replay_exact is True
    assert artifact["terminal_disposition"] == expected_answer["disposition"]
    if expected_answer["disposition"] == "typed_input":
        assert len(artifact["typed_inputs"]) == 1
        assert artifact["unclassified_inputs"] == []
        assert artifact["typed_inputs"][0]["input_type_id"] == (
            proof_context["audit_cases"][case_id][
                "expected_input_type_id"
            ]
        )
    else:
        assert artifact["typed_inputs"] == []
        assert len(artifact["unclassified_inputs"]) == 1
        assert artifact["unclassified_inputs"][0]["gap_reason_code"] == (
            expected_answer["reason_code"]
        )

    persisted = json.loads(proof.serialized_snapshot)
    persisted_payload = persisted["snapshot_payload"]
    assert persisted["snapshot_payload_sha256"] == sha256_json(
        persisted_payload
    )
    assert proof.restored_snapshot_integrity_hash == (
        persisted_payload["integrity_sha256"]
    )
    assert proof.replay_snapshot_integrity_hash == (
        proof.restored_snapshot_integrity_hash
    )

    report = proof.transparent_report_projection
    assert report["schema_version"] == (
        CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION
    )
    assert report["provider"] == {
        "provider_id": profile_contract["provider_id"],
        "provider_profile_id": provider_profile_id,
        "adapter_id": profile_contract["adapter_id"],
        "adapter_version": profile_contract["adapter_version"],
        "schema_projection_policy_version": (
            provider_adapter_module
            .CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
        ),
        "adapted_schema_hash": proof.adapter_adapted_schema_hash,
        "canonical_schema_hash": proof.adapter_canonical_schema_hash,
    }
    assert report["exact_final_model_visible_request"] == (
        proof.exact_final_provider_request
    )
    assert report["exact_system_message"] == V6_SEMANTIC_SYSTEM_PROMPT
    assert report["exact_user_content"] == sealed["serialized_context"]
    assert report["exact_provider_visible_response_schema"] == (
        proof.provider_visible_response_schema
    )
    assert report["exact_adapter_extracted_output"] == (
        proof.adapter_extracted_output
    )
    assert report["normalized_canonical_answer"] == expected_answer
    assert report["expected_answer"] == expected_answer
    assert report["field_level_diff"]["all_fields_match"] is True
    assert report["pipeline"] == {
        "materialized_artifact_hash": totality[
            "canonical_artifact_hash"
        ],
        "serialized_private_evidence_hash": (
            proof.serialized_private_evidence_hash
        ),
        "restored_private_evidence_hash": (
            proof.restored_private_evidence_hash
        ),
        "replay_materialized_artifact_hash": (
            proof.replay_materialized_artifact_hash
        ),
        "persisted_snapshot_hash": sha256_json(persisted),
        "replay_snapshot_integrity_hash": (
            proof.replay_snapshot_integrity_hash
        ),
        "restore_exact": True,
        "replay_exact": True,
    }
    assert report["actual_metrics"] == {
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
        "latency_ms": None,
        "status": "NOT_APPLICABLE_NO_PROVIDER_CALL",
    }
    assert report["execution_accounting"] == ZERO_ACCOUNTING
    assert proof.safe_summary()["execution_accounting"] == ZERO_ACCOUNTING


def test_active_v6_choice_schema_and_hash_remain_exact(
    proof_context,
) -> None:
    for case_id in CASE_IDS:
        case = proof_context["cases"][case_id]
        schema_before, hash_before = proof_context["active_before"][case_id]
        assert case.choice_contract.choice_schema == schema_before
        assert case.choice_contract.choice_schema_hash == hash_before
        assert case.choice_contract.choice_schema_hash == (
            ACTIVE_CHOICE_SCHEMA_HASHES[case_id]
        )
        assert sha256_json(case.choice_contract.choice_schema) == hash_before
        assert NEW_REASON_CODE not in json.dumps(
            case.choice_contract.choice_schema,
            ensure_ascii=False,
        )
        assert NEW_REASON_CODE in json.dumps(
            case.choice_contract.context_v2_1_response_profile.response_schema,
            ensure_ascii=False,
        )


def test_transparent_projector_requires_the_exact_twelve_case_matrix(
    proof_context,
) -> None:
    case_evidence = [
        proof_context["proofs"][
            pair
        ].transparent_report_case_evidence
        for pair in PROVIDER_CASE_PARAMS
    ]
    report = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_provider_report(case_evidence=case_evidence)
    )

    assert report["schema_version"] == (
        CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION
    )
    assert report["status"] == "passed"
    assert report["active"] is False
    assert report["provider_profiles_total"] == 3
    assert report["semantic_fixtures_total"] == 4
    assert report["provider_case_paths_total"] == 12
    assert len(report["cases"]) == 12
    assert {
        (
            item["provider"]["provider_profile_id"],
            item["case_id"],
        )
        for item in report["cases"]
    } == set(PROVIDER_CASE_PARAMS)
    assert all(
        item["field_level_diff"]["all_fields_match"] is True
        and item["pipeline"]["restore_exact"] is True
        and item["pipeline"]["replay_exact"] is True
        for item in report["cases"]
    )
    assert report["execution_accounting"] == ZERO_ACCOUNTING


def test_transparent_projector_case_evidence_is_immutable(
    proof_context,
) -> None:
    target_pair = ("openai_gpt", "syn_successor_v2_unique_cash")
    target = proof_context["proofs"][
        target_pair
    ].transparent_report_case_evidence
    forged_projection = target.to_dict()
    forged_projection["pipeline"]["materialized_artifact_hash"] = "0" * 64
    forged_projection["pipeline"][
        "replay_materialized_artifact_hash"
    ] = "0" * 64
    forged_draft = copy.deepcopy(forged_projection)
    forged_draft.pop("integrity_hash")
    forged_projection["integrity_hash"] = sha256_json(forged_draft)
    forged_serialized = json.dumps(
        forged_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    with pytest.raises(AttributeError, match="is immutable"):
        target._serialized_projection = forged_serialized
    with pytest.raises(AttributeError, match="is immutable"):
        setattr(
            target,
            (
                "_Gate2FinancialSemanticV6ContextV21ReportCaseEvidence"
                "__serialized_projection"
            ),
            forged_serialized,
        )

    report = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_provider_report(
            case_evidence=[
                proof_context["proofs"][
                    pair
                ].transparent_report_case_evidence
                for pair in PROVIDER_CASE_PARAMS
            ]
        )
    )
    published_target = next(
        item
        for item in report["cases"]
        if (
            item["provider"]["provider_profile_id"],
            item["case_id"],
        )
        == target_pair
    )
    assert (
        published_target["pipeline"]["materialized_artifact_hash"]
        != "0" * 64
    )
    assert (
        published_target["pipeline"]["replay_materialized_artifact_hash"]
        != "0" * 64
    )


def test_public_report_projector_cannot_mint_fabricated_pipeline_evidence(
    proof_context,
) -> None:
    target_pair = ("openai_gpt", "syn_successor_v2_unique_cash")
    provider_profile_id, case_id = target_pair
    proof = proof_context["proofs"][target_pair]
    case = proof_context["cases"][case_id]
    sealed_request = _sealed_request_for_case(proof_context, case_id)
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )

    fabricated_projection = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_provider_case(
            case_id=case_id,
            provider_profile=gate2_provider_profile(
                provider_profile_id
            ),
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            canonical_schema=(
                case.choice_contract.context_v2_1_response_profile
                .canonical_schema()
            ),
            local_projection_model_id=proof.local_projection_model_id,
            adapter_extracted_output=proof.adapter_extracted_output,
            normalized_answer=proof.normalized_canonical_answer,
            expected_answer=proof.expected_answer,
            materialized_artifact_hash="1" * 64,
            serialized_private_evidence_hash="2" * 64,
            restored_private_evidence_hash="3" * 64,
            replay_materialized_artifact_hash="1" * 64,
            persisted_snapshot_hash="4" * 64,
            replay_snapshot_integrity_hash="5" * 64,
            restore_exact=True,
            replay_exact=True,
        )
    )
    assert fabricated_projection["pipeline"][
        "materialized_artifact_hash"
    ] == "1" * 64
    case_evidence = [
        (
            fabricated_projection
            if pair == target_pair
            else proof_context["proofs"][
                pair
            ].transparent_report_case_evidence
        )
        for pair in PROVIDER_CASE_PARAMS
    ]

    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        (
            Gate2FinancialSemanticV6TransparentSmokeReportFactory()
            .create_context_v2_1_provider_report(
                case_evidence=case_evidence
            )
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_cases_invalid"
    )


def test_report_case_rejects_non_frozen_user_content(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    original = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory
        .create_context_v2_1_provider_case
    )

    def create_with_private_content(self, **kwargs):
        forged_visible = copy.deepcopy(
            kwargs["sealed_request"].model_visible_request
        )
        forged_visible["messages"][1]["content"] = (
            "forbidden_actual_corpus_sentinel"
        )
        forged_sealed = replace(
            kwargs["sealed_request"],
            model_visible_request=forged_visible,
        )
        form_data = Gate2OpenWebUIRequestBuilder(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
            )
        ).build_from_sealed_context_v2_1(
            model_visible_request=forged_visible,
            model_id=kwargs["local_projection_model_id"],
        )
        forged_prepared = (
            provider_adapter_module.Gate2ProviderAdapterFactory(
                profile=kwargs["provider_profile"],
            ).create().prepare_form_data(
                form_data=form_data,
                response_format=forged_visible["response_format"],
            )
        )
        return original(
            self,
            **{
                **kwargs,
                "sealed_request": forged_sealed,
                "prepared_request": forged_prepared,
            },
        )

    monkeypatch.setattr(
        Gate2FinancialSemanticV6TransparentSmokeReportFactory,
        "create_context_v2_1_provider_case",
        create_with_private_content,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_authority_invalid"
    )


def test_report_case_rejects_vacuous_non_choice_answers(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    original = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory
        .create_context_v2_1_provider_case
    )

    def create_with_vacuous_answers(self, **kwargs):
        return original(
            self,
            **{
                **kwargs,
                "normalized_answer": {},
                "expected_answer": {},
            },
        )

    monkeypatch.setattr(
        Gate2FinancialSemanticV6TransparentSmokeReportFactory,
        "create_context_v2_1_provider_case",
        create_with_vacuous_answers,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_authority_invalid"
    )


def test_report_case_rejects_unbound_adapter_output(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    original = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory
        .create_context_v2_1_provider_case
    )

    def create_with_unbound_output(self, **kwargs):
        return original(
            self,
            **{
                **kwargs,
                "adapter_extracted_output": (
                    '{"choice":"choice_999",'
                    '"forbidden_private_field":'
                    '"forbidden_actual_corpus_sentinel"}'
                ),
            },
        )

    monkeypatch.setattr(
        Gate2FinancialSemanticV6TransparentSmokeReportFactory,
        "create_context_v2_1_provider_case",
        create_with_unbound_output,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_authority_invalid"
    )


def test_report_aggregate_rejects_resealed_stale_case_projection(
    proof_context,
) -> None:
    target_pair = ("google_gemini", "syn_successor_v2_unique_cash")
    target = proof_context["proofs"][target_pair]
    projection = copy.deepcopy(target.transparent_report_projection)
    projection["normalized_canonical_answer"] = {}
    projection["expected_answer"] = {}
    projection["field_level_diff"] = {
        "all_fields_match": True,
        "fields": [],
    }
    projection["exact_user_content"] = (
        "forbidden_actual_corpus_sentinel"
    )
    projection["provider"]["adapter_version"] = "9.9.9"
    projection.pop("integrity_hash")
    projection["integrity_hash"] = sha256_json(projection)
    draft = replace(
        target,
        provider_adapter_version="9.9.9",
        normalized_canonical_answer={},
        expected_answer={},
        transparent_report_projection=projection,
        integrity_hash="",
    )
    resealed = replace(
        draft,
        integrity_hash=sha256_json(draft.integrity_payload()),
    )
    proofs = [
        (
            resealed
            if pair == target_pair
            else proof_context["proofs"][pair]
        )
        for pair in PROVIDER_CASE_PARAMS
    ]

    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        (
            Gate2FinancialSemanticV6TransparentSmokeReportFactory()
            .create_context_v2_1_provider_report(
                case_evidence=proofs
            )
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_cases_invalid"
    )


def test_report_aggregate_rejects_resealed_extra_private_field(
    proof_context,
) -> None:
    target_pair = ("google_gemini", "syn_successor_v2_unique_cash")
    target = proof_context["proofs"][target_pair]
    projection = copy.deepcopy(target.transparent_report_projection)
    projection["forbidden_private_field"] = (
        "forbidden_actual_corpus_sentinel"
    )
    projection.pop("integrity_hash")
    projection["integrity_hash"] = sha256_json(projection)
    draft = replace(
        target,
        transparent_report_projection=projection,
        integrity_hash="",
    )
    resealed = replace(
        draft,
        integrity_hash=sha256_json(draft.integrity_payload()),
    )
    proofs = [
        (
            resealed
            if pair == target_pair
            else proof_context["proofs"][pair]
        )
        for pair in PROVIDER_CASE_PARAMS
    ]

    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        (
            Gate2FinancialSemanticV6TransparentSmokeReportFactory()
            .create_context_v2_1_provider_report(
                case_evidence=proofs
            )
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_cases_invalid"
    )


@pytest.mark.parametrize(
    ("provider_profile_id", "model_output", "error_code"),
    [
        (
            "openai_gpt",
            '{"choice":',
            "financial_semantic_v6_context_v2_1_choice_json_invalid",
        ),
        (
            "google_gemini",
            {"choice": "choice_999"},
            "financial_semantic_v6_context_v2_1_choice_key_unknown",
        ),
        (
            "anthropic_claude",
            {"choice": "unclassified", "reason": "free text"},
            "financial_semantic_v6_context_v2_1_choice_reason_invalid",
        ),
    ],
)
def test_adapter_extracted_invalid_outputs_fail_closed_without_repair(
    proof_context,
    provider_profile_id,
    model_output,
    error_code,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=_simulated_provider_response(
                provider_profile_id,
                model_output,
            ),
        )

    assert failure.value.code == error_code


def test_removed_gemini_choice_or_reason_enum_fails_before_extraction(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    monkeypatch.setattr(
        provider_adapter_module,
        "_GEMINI_PRESERVED_ENUM_PROPERTIES",
        provider_adapter_module._GEMINI_PRESERVED_ENUM_PROPERTIES
        - {"choice", "reason"},
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "gate2_provider_schema_semantic_enum_removed"
    )


def test_openai_wrapped_duplicate_choice_key_fails_before_choice_parsing(
    proof_context,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    duplicate_response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": (
                        '{"broker_reports_gate2_choice":'
                        '{"choice":"choice_999","choice":"choice_1"}}'
                    )
                },
            }
        ]
    }

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="openai_gpt",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=duplicate_response,
        )

    assert failure.value.code == "gate2_model_invalid_response"


def test_openai_missing_required_root_envelope_fails_before_choice_parsing(
    proof_context,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    bare_response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": '{"choice":"choice_1"}',
                },
            }
        ]
    }

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="openai_gpt",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=bare_response,
        )

    assert failure.value.code == "gate2_model_invalid_response"


def test_openai_extraction_does_not_trust_forged_transform_count(
    proof_context,
) -> None:
    provider_profile_id = "openai_gpt"
    case_id = "syn_successor_v2_unique_cash"
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    prepared_request = replace(
        _prepared_request_for_case(
            proof_context,
            provider_profile_id,
            case_id,
        ),
        schema_transform_count=0,
    )
    adapter = provider_adapter_module.Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(provider_profile_id),
    ).create()
    bare_response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"choice":"choice_1"}'},
            }
        ]
    }

    assert prepared_request.schema_binding_is_valid()
    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        adapter.extract_prepared_content(
            bare_response,
            prepared_request=prepared_request,
        )

    assert failure.value.code == "gate2_model_invalid_response"


@pytest.mark.parametrize(
    ("provider_profile_id", "terminal_field", "nonterminal_value"),
    (
        ("openai_gpt", "finish_reason", "length"),
        ("google_gemini", "finish_reason", "length"),
        ("anthropic_claude", "stop_reason", "max_tokens"),
    ),
)
def test_candidate_provider_response_must_be_terminal(
    proof_context,
    provider_profile_id,
    terminal_field,
    nonterminal_value,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    response = copy.deepcopy(
        proof_context["responses"][(provider_profile_id, case_id)]
    )
    if provider_profile_id == "anthropic_claude":
        response[terminal_field] = nonterminal_value
    else:
        response["choices"][0][terminal_field] = nonterminal_value

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=response,
        )

    assert failure.value.code == "gate2_model_response_not_terminal"


@pytest.mark.parametrize(
    "provider_profile_id",
    ("openai_gpt", "google_gemini"),
)
def test_candidate_openwebui_response_requires_exactly_one_choice(
    proof_context,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    response = copy.deepcopy(
        proof_context["responses"][(provider_profile_id, case_id)]
    )
    response["choices"].append(copy.deepcopy(response["choices"][0]))

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=response,
        )

    assert failure.value.code == "gate2_model_response_not_terminal"


def test_candidate_anthropic_response_requires_one_text_block(
    proof_context,
) -> None:
    provider_profile_id = "anthropic_claude"
    case_id = "syn_successor_v2_unique_cash"
    response = copy.deepcopy(
        proof_context["responses"][(provider_profile_id, case_id)]
    )
    response["content"].append(copy.deepcopy(response["content"][0]))

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=response,
        )

    assert failure.value.code == "gate2_model_invalid_response"


def test_resealed_openai_response_format_name_drift_fails_exact_replay(
    proof_context,
) -> None:
    provider_profile_id = "openai_gpt"
    case_id = "syn_successor_v2_unique_cash"
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    drifted_request = copy.deepcopy(proof.exact_final_provider_request)
    drifted_request["response_format"]["json_schema"]["name"] = (
        "drifted_provider_name"
    )
    draft = replace(
        proof,
        exact_final_provider_request=drifted_request,
        integrity_hash="",
    )
    resealed = replace(
        draft,
        integrity_hash=sha256_json(draft.integrity_payload()),
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ContextV21ProviderProofError,
    ) as failure:
        validate_financial_semantic_v6_context_v2_1_provider_case_proof(
            proof=resealed,
            factory=proof_context["factory"],
            case=proof_context["cases"][case_id],
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                (provider_profile_id, case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_proof_integrity_invalid"
    )


def test_resealed_provider_schema_projection_drift_fails_exact_replay(
    proof_context,
) -> None:
    provider_profile_id = "google_gemini"
    case_id = "syn_successor_v2_unique_cash"
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    drifted_schema = copy.deepcopy(proof.provider_visible_response_schema)
    drifted_schema["x-provider-projection-drift"] = True
    drifted_request = copy.deepcopy(proof.exact_final_provider_request)
    drifted_request["response_format"]["json_schema"]["schema"] = (
        copy.deepcopy(drifted_schema)
    )
    draft = replace(
        proof,
        provider_visible_response_schema=drifted_schema,
        exact_final_provider_request=drifted_request,
        integrity_hash="",
    )
    resealed = replace(
        draft,
        integrity_hash=sha256_json(draft.integrity_payload()),
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ContextV21ProviderProofError,
    ) as failure:
        validate_financial_semantic_v6_context_v2_1_provider_case_proof(
            proof=resealed,
            factory=proof_context["factory"],
            case=proof_context["cases"][case_id],
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                (provider_profile_id, case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_proof_integrity_invalid"
    )


def test_resealed_private_projection_drift_fails_trusted_evidence_replay(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    real_replay = (
        provider_proof_module
        .replay_financial_semantic_v6_context_v2_1_decision
    )

    def replay_resealed_drift(**kwargs):
        private_evidence = copy.deepcopy(kwargs["private_evidence"])
        drifted_schema = copy.deepcopy(
            private_evidence["provider_visible_schema"]
        )
        drifted_schema["x-resealed-provider-drift"] = True
        private_evidence["provider_visible_schema"] = drifted_schema
        private_evidence["provider_visible_schema_hash"] = sha256_json(
            drifted_schema
        )
        private_evidence["exact_final_provider_request"][
            "response_format"
        ]["json_schema"]["schema"] = copy.deepcopy(drifted_schema)
        private_evidence["final_provider_request_hash"] = sha256_json(
            private_evidence["exact_final_provider_request"]
        )
        authorities = private_evidence["replay_authorities"]
        authorities["provider_visible_schema_hash"] = private_evidence[
            "provider_visible_schema_hash"
        ]
        authorities["final_provider_request_hash"] = private_evidence[
            "final_provider_request_hash"
        ]
        private_evidence["private_evidence_hash"] = sha256_json(
            {
                key: value
                for key, value in private_evidence.items()
                if key != "private_evidence_hash"
            }
        )
        return real_replay(
            **{
                **kwargs,
                "private_evidence": private_evidence,
            }
        )

    monkeypatch.setattr(
        provider_proof_module,
        "replay_financial_semantic_v6_context_v2_1_decision",
        replay_resealed_drift,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "offline_replay_projection_mismatch"
    )


@pytest.mark.parametrize(
    "provider_profile_id",
    PROVIDER_PROFILE_IDS,
)
def test_report_projector_rejects_exposed_to_embedded_schema_drift(
    proof_context,
    monkeypatch,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    original = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory
        .create_context_v2_1_provider_case
    )

    def create_with_drifted_exposed_schema(self, **kwargs):
        prepared_request = kwargs["prepared_request"]
        drifted_schema = copy.deepcopy(
            prepared_request.provider_visible_schema
        )
        drifted_schema["x-report-schema-drift"] = True
        return original(
            self,
            **{
                **kwargs,
                "prepared_request": replace(
                    prepared_request,
                    provider_visible_schema=drifted_schema,
                    adapted_schema_hash=(
                        provider_adapter_module._schema_hash(
                            drifted_schema
                        )
                    ),
                ),
            },
        )

    monkeypatch.setattr(
        Gate2FinancialSemanticV6TransparentSmokeReportFactory,
        "create_context_v2_1_provider_case",
        create_with_drifted_exposed_schema,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                (provider_profile_id, case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_authority_invalid"
    )


def test_report_projector_rejects_forged_projection_policy_identity(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    original = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory
        .create_context_v2_1_provider_case
    )

    def create_with_forged_policy(self, **kwargs):
        return original(
            self,
            **{
                **kwargs,
                "prepared_request": replace(
                    kwargs["prepared_request"],
                    projection_policy_version=(
                        "wrong_projection_policy_v999"
                    ),
                ),
            },
        )

    monkeypatch.setattr(
        Gate2FinancialSemanticV6TransparentSmokeReportFactory,
        "create_context_v2_1_provider_case",
        create_with_forged_policy,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "provider_report_authority_invalid"
    )


def test_candidate_boundary_rejects_prepared_canonical_schema_hash_drift(
    proof_context,
    monkeypatch,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    adapter_type = (
        provider_adapter_module._Gate2OpenWebUIProviderAdapter
    )
    original = adapter_type.prepare_form_data

    def prepare_with_canonical_hash_drift(self, **kwargs):
        return replace(
            original(self, **kwargs),
            canonical_schema_hash="0" * 64,
        )

    monkeypatch.setattr(
        adapter_type,
        "prepare_form_data",
        prepare_with_canonical_hash_drift,
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        proof_context["factory"].create_case(
            case=proof_context["cases"][case_id],
            provider_profile_id="google_gemini",
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                ("google_gemini", case_id)
            ],
        )

    assert failure.value.code == "gate2_model_request_invalid"


def test_evidence_and_replay_reject_forged_projection_policy_identity(
    proof_context,
) -> None:
    provider_profile_id = "google_gemini"
    case_id = "syn_successor_v2_unique_cash"
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    case = proof_context["cases"][case_id]
    sealed_request = _sealed_request_for_case(
        proof_context,
        case_id,
    )
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_request = replace(
        prepared_request,
        projection_policy_version="wrong_projection_policy_v999",
    )
    canonical_schema = (
        case.choice_contract.context_v2_1_response_profile.canonical_schema()
    )

    assert prepared_request.canonical_schema_is_bound(canonical_schema)
    assert not forged_request.canonical_schema_is_bound(canonical_schema)

    evidence_factory = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=proof_context["registry"]
    )
    evidence_kwargs = {
        "case_id": case_id,
        "provider_profile_id": proof.provider_profile_id,
        "provider_adapter_id": proof.provider_adapter_id,
        "provider_adapter_version": proof.provider_adapter_version,
        "local_projection_model_id": proof.local_projection_model_id,
        "sealed_request": sealed_request,
        "adapter_extracted_output": proof.adapter_extracted_output,
        "choice_contract": case.choice_contract,
        "packet": case.packet,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as create_failure:
        evidence_factory.create_context_v2_1_candidate(
            **evidence_kwargs,
            prepared_request=forged_request,
        )

    assert create_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "private_evidence_canonical_schema_mismatch"
    )

    genuine = evidence_factory.create_context_v2_1_candidate(
        **evidence_kwargs,
        prepared_request=prepared_request,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as replay_failure:
        replay_financial_semantic_v6_context_v2_1_decision(
            private_evidence=genuine.private_evidence,
            expected_provider_profile_id=proof.provider_profile_id,
            expected_provider_adapter_id=proof.provider_adapter_id,
            expected_provider_adapter_version=(
                proof.provider_adapter_version
            ),
            expected_local_projection_model_id=(
                proof.local_projection_model_id
            ),
            expected_sealed_request=sealed_request,
            expected_prepared_request=forged_request,
            choice_contract=case.choice_contract,
            packet=case.packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=proof_context["registry"],
        )

    assert replay_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "offline_replay_projection_mismatch"
    )


def test_evidence_and_replay_reject_forged_openai_schema_name(
    proof_context,
) -> None:
    provider_profile_id = "openai_gpt"
    case_id = "syn_successor_v2_unique_cash"
    proof = proof_context["proofs"][(provider_profile_id, case_id)]
    case = proof_context["cases"][case_id]
    sealed_request = _sealed_request_for_case(
        proof_context,
        case_id,
    )
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_form_data = copy.deepcopy(prepared_request.form_data)
    forged_form_data["response_format"]["json_schema"]["name"] = (
        "forged_broker_reports_choice"
    )
    forged_request = replace(
        prepared_request,
        form_data=forged_form_data,
    )
    canonical_schema = (
        case.choice_contract.context_v2_1_response_profile.canonical_schema()
    )

    binding_kwargs = {
        "canonical_schema": canonical_schema,
        "provider_profile": gate2_provider_profile(
            provider_profile_id
        ),
        "model_visible_request": sealed_request.model_visible_request,
        "local_projection_model_id": proof.local_projection_model_id,
    }
    assert prepared_request.context_v2_1_contract_is_bound(
        **binding_kwargs
    )
    assert forged_request.schema_binding_is_valid()
    assert forged_request.canonical_schema_is_bound(canonical_schema)
    assert not forged_request.context_v2_1_contract_is_bound(
        **binding_kwargs
    )

    evidence_factory = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=proof_context["registry"]
    )
    evidence_kwargs = {
        "case_id": case_id,
        "provider_profile_id": proof.provider_profile_id,
        "provider_adapter_id": proof.provider_adapter_id,
        "provider_adapter_version": proof.provider_adapter_version,
        "local_projection_model_id": proof.local_projection_model_id,
        "sealed_request": sealed_request,
        "adapter_extracted_output": proof.adapter_extracted_output,
        "choice_contract": case.choice_contract,
        "packet": case.packet,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as create_failure:
        evidence_factory.create_context_v2_1_candidate(
            **evidence_kwargs,
            prepared_request=forged_request,
        )

    assert create_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "private_evidence_canonical_schema_mismatch"
    )

    genuine = evidence_factory.create_context_v2_1_candidate(
        **evidence_kwargs,
        prepared_request=prepared_request,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as replay_failure:
        replay_financial_semantic_v6_context_v2_1_decision(
            private_evidence=genuine.private_evidence,
            expected_provider_profile_id=proof.provider_profile_id,
            expected_provider_adapter_id=proof.provider_adapter_id,
            expected_provider_adapter_version=(
                proof.provider_adapter_version
            ),
            expected_local_projection_model_id=(
                proof.local_projection_model_id
            ),
            expected_sealed_request=sealed_request,
            expected_prepared_request=forged_request,
            choice_contract=case.choice_contract,
            packet=case.packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=proof_context["registry"],
        )

    assert replay_failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "offline_replay_projection_mismatch"
    )


@pytest.mark.parametrize(
    "provider_profile_id",
    PROVIDER_PROFILE_IDS,
)
def test_direct_evidence_replay_rejects_full_request_drift(
    proof_context,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_form_data = copy.deepcopy(prepared_request.form_data)
    if provider_profile_id == "anthropic_claude":
        forged_form_data["messages"][0]["content"] = (
            '{"task":"forged"}'
        )
        forged_form_data["temperature"] = 1
    else:
        forged_form_data["messages"][1]["content"] = (
            '{"task":"forged"}'
        )
        forged_form_data["n"] = 2

    _assert_direct_prepared_forgery_rejected(
        proof_context=proof_context,
        provider_profile_id=provider_profile_id,
        case_id=case_id,
        forged_request=replace(
            prepared_request,
            form_data=forged_form_data,
        ),
    )


@pytest.mark.parametrize(
    "provider_profile_id",
    PROVIDER_PROFILE_IDS,
)
def test_direct_evidence_replay_rejects_wrapper_or_count_drift(
    proof_context,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_form_data = copy.deepcopy(prepared_request.form_data)
    if provider_profile_id == "anthropic_claude":
        forged_form_data["output_config"]["format"]["type"] = "text"
    elif provider_profile_id == "google_gemini":
        forged_form_data["response_format"]["type"] = "json_object"
    else:
        forged_form_data["response_format"]["json_schema"][
            "strict"
        ] = False

    _assert_direct_prepared_forgery_rejected(
        proof_context=proof_context,
        provider_profile_id=provider_profile_id,
        case_id=case_id,
        forged_request=replace(
            prepared_request,
            form_data=forged_form_data,
            schema_transform_count=(
                prepared_request.schema_transform_count + 1
            ),
        ),
    )


@pytest.mark.parametrize(
    "provider_profile_id",
    PROVIDER_PROFILE_IDS,
)
def test_direct_evidence_replay_rejects_resealed_full_schema_drift(
    proof_context,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_schema = copy.deepcopy(
        prepared_request.provider_visible_schema
    )
    forged_schema["x-forged-projection"] = True
    forged_form_data = copy.deepcopy(prepared_request.form_data)
    if provider_profile_id == "anthropic_claude":
        forged_form_data["output_config"]["format"]["schema"] = (
            copy.deepcopy(forged_schema)
        )
    else:
        forged_form_data["response_format"]["json_schema"]["schema"] = (
            copy.deepcopy(forged_schema)
        )
    forged_request = replace(
        prepared_request,
        form_data=forged_form_data,
        provider_visible_schema=forged_schema,
        adapted_schema_hash=provider_adapter_module._schema_hash(
            forged_schema
        ),
    )

    assert forged_request.schema_binding_is_valid()
    _assert_direct_prepared_forgery_rejected(
        proof_context=proof_context,
        provider_profile_id=provider_profile_id,
        case_id=case_id,
        forged_request=forged_request,
    )


@pytest.mark.parametrize(
    "provider_profile_id",
    ("openai_gpt", "google_gemini"),
)
def test_direct_evidence_replay_rejects_embedded_profile_drift(
    proof_context,
    provider_profile_id,
) -> None:
    case_id = "syn_successor_v2_unique_cash"
    prepared_request = _prepared_request_for_case(
        proof_context,
        provider_profile_id,
        case_id,
    )
    forged_form_data = copy.deepcopy(prepared_request.form_data)
    metadata = forged_form_data["metadata"]["broker_reports_gate2"]
    metadata["provider_profile_id"] = "forged_profile"
    metadata["provider_adapter_version"] = "9.9.9"

    _assert_direct_prepared_forgery_rejected(
        proof_context=proof_context,
        provider_profile_id=provider_profile_id,
        case_id=case_id,
        forged_request=replace(
            prepared_request,
            form_data=forged_form_data,
        ),
    )


def test_resealed_private_mapping_tamper_fails_before_provider_projection(
    proof_context,
) -> None:
    provider_profile_id = "openai_gpt"
    case_id = "syn_successor_v2_unique_cash"
    case = proof_context["cases"][case_id]
    receipt = case.packet.context_v2_mapping_receipt
    identities = copy.deepcopy(receipt.identities)
    identities["context_view_hash"] = "0" * 64
    draft_receipt = replace(
        receipt,
        identities=identities,
        integrity_hash="",
    )
    receipt_material = draft_receipt.to_private_dict()
    receipt_material.pop("integrity_hash")
    forged_receipt = replace(
        draft_receipt,
        integrity_hash=sha256_json(receipt_material),
    )
    tampered_case = replace(
        case,
        packet=replace(
            case.packet,
            context_v2_mapping_receipt=forged_receipt,
        ),
    )

    with pytest.raises(ValueError) as failure:
        proof_context["factory"].create_case(
            case=tampered_case,
            provider_profile_id=provider_profile_id,
            expected_answer=proof_context["expected_answers"][case_id],
            simulated_provider_response=proof_context["responses"][
                (provider_profile_id, case_id)
            ],
        )

    assert "financial_semantic" in str(failure.value)


def test_provider_proof_keeps_factory_anchors_and_has_no_transport_route() -> None:
    source = PROOF_MODULE_PATH.read_text(encoding="utf-8")

    assert "create_case" in FACTORY_REQUIRED
    assert "existing linter" in FACTORY_REQUIRED
    assert "must not call provider transport" in FORBIDDEN
    assert all(
        owner in source
        for owner in (
            "Gate2FinancialSemanticV6ContextLinterFactory",
            "Gate2OpenWebUIRequestBuilder",
            "Gate2ProviderAdapterFactory",
            "Gate2FinancialSemanticV6DecisionEvidenceFactory",
            "serialize_financial_semantic_v6_context_v2_1_private_evidence",
            "restore_financial_semantic_v6_context_v2_1_private_evidence",
            "replay_financial_semantic_v6_context_v2_1_decision",
            "Gate2FinancialDomainPersistenceFactory",
            "Gate2FinancialSemanticV6TransparentSmokeReportFactory",
        )
    )
    assert all(
        forbidden not in source
        for forbidden in (
            "Gate2StructuredModelClientFactory",
            "invoke_native_once(",
            "generate_chat_completion",
            "urlopen(",
            "requests.post(",
        )
    )


def test_context_v2_1_request_profile_cannot_bypass_the_sealed_entrypoint() -> None:
    builder = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
        )
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as failure:
        builder.build(
            prompt=object(),
            package={},
            model_id="local-proof-openai-profile-v1",
            response_format={},
        )

    assert failure.value.code == "gate2_model_request_sealed_context_required"
