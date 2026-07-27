from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialSemanticV6DecisionEvidenceError,
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    financial_semantic_v6_canonical_request,
    financial_semantic_v6_private_evidence_hash,
    replay_financial_semantic_v6_decision,
)
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    V6_EXACT_MODEL_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
    V6_PROVIDER_PROFILE_ID,
    Gate2FinancialSemanticV6CapturedExecution,
    Gate2FinancialSemanticV6ExecutionIdentityFactory,
    financial_semantic_v6_response_format,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_evidence.py"


def _cases():
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _authorities(case_id):
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(registry=registry)
        .create(gate1_packages=(fixture.payload,))
        .scopes[0]
    )
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(fixture.payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )
    packet = Gate2FinancialSemanticV6PacketFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    choice = Gate2FinancialSemanticV6ChoiceContractFactory(registry=registry).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    return {
        "fixture": fixture,
        "registry": registry,
        "scope": scope,
        "bundle": bundle,
        "compilation": compilation,
        "packet": packet,
        "choice": choice,
    }


def _execution_identity(authorities):
    profile = gate2_provider_profile(V6_PROVIDER_PROFILE_ID)
    response_format = financial_semantic_v6_response_format(authorities["choice"])
    metadata = Gate2ProviderExecutionMetadata(
        provider_id=profile.provider_id,
        provider_profile_id=profile.profile_id,
        provider_profile_revision=gate2_provider_profile_revision(profile),
        adapter_id=profile.adapter_id,
        adapter_version=profile.adapter_version,
        requested_model_id=V6_EXACT_MODEL_ID,
        resolved_model_id=V6_EXACT_MODEL_ID,
        provider_response_id="resp_synthetic_goal9_exact",
        structured_output_mode=profile.structured_output_mode,
        response_format_type=profile.response_format_type,
        response_format_schema_mode=profile.response_format_schema_mode,
        transport_type=profile.transport_type,
        canonical_request_schema_hash=authorities["choice"].choice_schema_hash,
        adapted_request_schema_hash=authorities["choice"].choice_schema_hash,
        schema_transform_count=0,
        duration_ms=123,
        input_tokens=250,
        output_tokens=18,
        total_tokens=268,
        cached_input_tokens=0,
        reasoning_tokens=0,
        finish_reason="stop",
    )
    capture = Gate2FinancialSemanticV6CapturedExecution(
        request_profile=V6_QUALIFICATION_REQUEST_PROFILE,
        response_format_hash=sha256_json(response_format),
        execution_metadata=metadata,
        actual_cost_usd="0.000052",
    )
    identity = Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
        capture=capture,
        choice_contract=authorities["choice"],
    )
    return capture, identity


def _evidence(
    case_id="syn_successor_signed_literal",
    *,
    unclassified=False,
):
    authorities = _authorities(case_id)
    capture, identity = _execution_identity(authorities)
    if not unclassified and authorities["compilation"].typed_options:
        model_output = {
            "disposition": "typed_input",
            "typed_option_id": (
                authorities["compilation"].typed_options[0].typed_option_id
            ),
        }
    else:
        model_output = {
            "disposition": "unclassified_financial_input",
            "reason_code": "ambiguous_registry_type",
        }
    request = financial_semantic_v6_canonical_request(
        packet=authorities["packet"],
        choice_contract=authorities["choice"],
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=authorities["registry"]
    ).create(
        case_id=case_id,
        canonical_request=request,
        model_output=json.dumps(model_output, ensure_ascii=False),
        execution_capture=capture,
        execution_identity=identity,
        choice_contract=authorities["choice"],
        packet=authorities["packet"],
        evidence_bundle=authorities["bundle"],
        source_package=authorities["scope"].source_package,
        compilation=authorities["compilation"],
    )
    return {
        **authorities,
        "capture": capture,
        "identity": identity,
        "model_output": model_output,
        "request": request,
        "evidence": evidence,
    }


def _replay(bundle, private=None, safe=None):
    return replay_financial_semantic_v6_decision(
        private_evidence=(
            bundle["evidence"].private_evidence if private is None else private
        ),
        safe_receipt=bundle["evidence"].safe_receipt if safe is None else safe,
        choice_contract=bundle["choice"],
        packet=bundle["packet"],
        evidence_bundle=bundle["bundle"],
        source_package=bundle["scope"].source_package,
        compilation=bundle["compilation"],
        registry=bundle["registry"],
    )


def _rehash(private):
    material = copy.deepcopy(private)
    material.pop("private_evidence_hash")
    private["private_evidence_hash"] = financial_semantic_v6_private_evidence_hash(
        material
    )


@pytest.mark.parametrize("unclassified", [False, True])
def test_private_evidence_preserves_exact_choice_chain_and_provider_identity(
    unclassified,
) -> None:
    bundle = _evidence(
        "syn_successor_signed_literal"
        if not unclassified
        else "syn_successor_adjacent_equal",
        unclassified=unclassified,
    )
    private = bundle["evidence"].private_evidence

    assert private["exact_canonical_request_object"] == bundle["request"]
    assert private["canonical_request_hash"] == sha256_json(bundle["request"])
    assert private["provider_schema_hash"] == bundle["choice"].choice_schema_hash
    assert private["normalized_semantic_choice"] == bundle["model_output"]
    assert private["semantic_choice_hash"] == sha256_json(bundle["model_output"])
    assert (
        private["expanded_canonical_decision"]["model_choice_hash"]
        == (private["semantic_choice_hash"])
    )
    assert private["validation_result"]["status"] == "passed"
    assert private["materialized_artifact_hash"] == sha256_json(
        bundle["evidence"].materialized_artifact
    )
    assert private["provider_execution_identity"] == (
        bundle["identity"].to_private_dict()
    )
    assert private["exact_choice_preserved"] is True
    assert private["raw_provider_transport_preserved"] is False
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not contain canonical requests" in FORBIDDEN


@pytest.mark.parametrize(
    ("case_id", "unclassified"),
    [
        ("syn_successor_signed_literal", False),
        ("syn_successor_adjacent_equal", True),
    ],
)
def test_offline_replay_reproduces_exact_artifact_without_provider_call(
    case_id,
    unclassified,
) -> None:
    bundle = _evidence(case_id, unclassified=unclassified)
    replay = _replay(bundle)

    assert replay.status == "EXACT"
    assert replay.materialized_artifact == bundle["evidence"].materialized_artifact
    assert (
        replay.materialized_artifact_hash
        == (bundle["evidence"].private_evidence["materialized_artifact_hash"])
    )
    assert (
        replay.semantic_choice_hash
        == (bundle["evidence"].private_evidence["semantic_choice_hash"])
    )
    assert replay.safe_receipt == bundle["evidence"].safe_receipt
    assert replay.provider_calls_total == 0


def test_repository_safe_receipt_links_hashes_without_literals_or_refs() -> None:
    bundle = _evidence()
    private = bundle["evidence"].private_evidence
    safe = bundle["evidence"].safe_receipt
    rendered = json.dumps(safe, ensure_ascii=False, sort_keys=True)

    assert safe["hashes"]["private_evidence_hash"] == (private["private_evidence_hash"])
    assert safe["hashes"]["semantic_choice_hash"] == (private["semantic_choice_hash"])
    assert (
        safe["hashes"]["materialized_artifact_hash"]
        == (private["materialized_artifact_hash"])
    )
    assert safe["exact_choice_preserved"] == "YES"
    assert safe["offline_replay"] == "EXACT"
    assert safe["private_safe_hash_link"] == "VERIFIED"
    assert safe["private_safe_hash_link_verified"] is True
    assert safe["raw_private_data_in_receipt"] is False
    assert safe["raw_private_data_in_git"] == "ZERO"
    private_values = {item.literal_value for item in bundle["bundle"].source_values} | {
        item.source_value_ref for item in bundle["bundle"].source_values
    }
    assert all(value not in rendered for value in private_values)
    assert all(
        forbidden not in rendered
        for forbidden in (
            "exact_canonical_request_object",
            "normalized_semantic_choice",
            "expanded_canonical_decision",
            "provider_response_id",
            "source_value_ref",
            "literal_value",
            "role_bindings",
        )
    )


def test_canonical_request_is_exact_private_and_strict() -> None:
    bundle = _evidence()
    request = bundle["request"]
    assert request["model"] == V6_EXACT_MODEL_ID
    assert request["stream"] is False
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert json.loads(request["messages"][1]["content"]) == (bundle["packet"].payload)
    assert request["metadata"]["broker_reports_gate2"]["request_profile"] == (
        V6_QUALIFICATION_REQUEST_PROFILE
    )


@pytest.mark.parametrize(
    "tamper",
    [
        "choice",
        "expansion",
        "validation",
        "artifact_hash",
        "provider_identity",
        "authority",
    ],
)
def test_offline_replay_rejects_rehashed_private_tampering(tamper) -> None:
    bundle = _evidence()
    private = copy.deepcopy(bundle["evidence"].private_evidence)
    if tamper == "choice":
        private["normalized_semantic_choice"]["typed_option_id"] = "opt_missing"
    elif tamper == "expansion":
        private["expanded_canonical_decision"]["integrity_hash"] = "0" * 64
    elif tamper == "validation":
        private["validation_result"]["status"] = "failed"
    elif tamper == "artifact_hash":
        private["materialized_artifact_hash"] = "0" * 64
    elif tamper == "provider_identity":
        private["provider_execution_identity"]["total_tokens"] = 999
        private["provider_execution_identity"]["integrity_hash"] = "0" * 64
    else:
        private["replay_authorities"]["registry_hash"] = "0" * 64
    _rehash(private)

    with pytest.raises(Gate2FinancialSemanticV6DecisionEvidenceError):
        _replay(bundle, private=private)


def test_safe_receipt_tampering_breaks_private_safe_hash_link() -> None:
    bundle = _evidence()
    safe = copy.deepcopy(bundle["evidence"].safe_receipt)
    safe["hashes"]["private_evidence_hash"] = "0" * 64
    material = {key: value for key, value in safe.items() if key != "receipt_hash"}
    safe["receipt_hash"] = sha256_json(material)

    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="financial_semantic_v6_safe_receipt_invalid",
    ):
        _replay(bundle, safe=safe)


def test_execution_capture_mismatch_is_rejected_before_evidence() -> None:
    bundle = _evidence()
    capture = replace(
        bundle["capture"],
        execution_metadata=replace(
            bundle["capture"].execution_metadata,
            total_tokens=269,
        ),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="financial_semantic_v6_evidence_execution_identity_invalid",
    ):
        Gate2FinancialSemanticV6DecisionEvidenceFactory(
            registry=bundle["registry"]
        ).create(
            case_id="mismatch",
            canonical_request=bundle["request"],
            model_output=bundle["model_output"],
            execution_capture=capture,
            execution_identity=bundle["identity"],
            choice_contract=bundle["choice"],
            packet=bundle["packet"],
            evidence_bundle=bundle["bundle"],
            source_package=bundle["scope"].source_package,
            compilation=bundle["compilation"],
        )


def test_module_has_no_repository_writer_provider_call_or_repair_route() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
    assert "open(" not in source
    assert "requests." not in source
    assert "httpx." not in source
    assert "aiohttp." not in source
    assert "fallback_used" not in source
    assert "repair_attempt" not in source
