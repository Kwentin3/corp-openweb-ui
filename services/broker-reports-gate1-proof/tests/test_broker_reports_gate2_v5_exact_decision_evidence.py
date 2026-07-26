from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402,E501
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402,E501
    FinancialEvidenceExecutionMetadata,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402,E501
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402,E501
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_ambiguity import (  # noqa: E402,E501
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_contract import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ModelContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_evidence import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialSemanticV5DecisionEvidenceError,
    Gate2FinancialSemanticV5DecisionEvidenceFactory,
    Gate2FinancialSemanticV5ProviderCallReceipt,
    financial_semantic_v5_private_evidence_hash,
    replay_financial_semantic_v5_decision,
)
from broker_reports_gate1.gate2_financial_semantic_v5_execution import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV5DecisionPacketFactory,
    structural_binding_candidates_from_source_context,
)
from broker_reports_gate1.gate2_financial_semantic_v5_preclose import (  # noqa: E402,E501
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402,E501
    _fixture_package,
    _model_output,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODEL_ID = "synthetic-nano-v5"


def _cases():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in manifest["cases"]}


def _bundle(case_id: str):
    case = copy.deepcopy(_cases()[case_id])
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(case)
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    candidates = structural_binding_candidates_from_source_context(
        source_context=context
    )
    projection = Gate2FinancialSemanticV5ProjectionFactory().create()
    ambiguity = Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
        projection=projection,
        candidates=candidates,
    )
    preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
        evidence=Gate2TechnicalPrecloseEvidence(
            source_support="supported",
            authoritative_layout_only=False,
            source_value_candidates_total=len(candidates),
            scope_valid=True,
        )
    )
    packet = Gate2FinancialSemanticV5DecisionPacketFactory().create(
        source_context=context,
        projection=projection,
        ambiguity=ambiguity,
        candidates=candidates,
        preclose=preclose,
    )
    execution = (
        Gate2FinancialSemanticV5ExecutionContractFactory().create()
    )
    model_contract = (
        Gate2FinancialSemanticV5ModelContractFactory().create(
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=scope.decision_contract,
        )
    )
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    ).build(
        prompt=execution.prompt,
        package=packet.payload,
        model_id=MODEL_ID,
        response_format=model_contract.response_format,
    )
    model_output = _model_output(
        case=case,
        scope=scope,
        selected_value_refs=fixture.selected_value_refs,
    )
    metadata = FinancialEvidenceExecutionMetadata(
        execution_ref=f"execution:v5-evidence:{case_id}",
        decision_validation_ref=f"validation:v5-evidence:{case_id}",
    )
    evidence = (
        Gate2FinancialSemanticV5DecisionEvidenceFactory().create(
            case_id=case_id,
            model_id=MODEL_ID,
            canonical_request=request,
            model_output=json.dumps(model_output),
            provider_receipt=(
                Gate2FinancialSemanticV5ProviderCallReceipt(
                    input_tokens=321,
                    output_tokens=47,
                    cost_usd="0.000123",
                    latency_ms=456,
                )
            ),
            model_contract=model_contract,
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=scope.decision_contract,
            registry=registry,
            source_package=scope.source_package,
            execution_metadata=metadata,
        )
    )
    return {
        "case": case,
        "fixture": fixture,
        "registry": registry,
        "scope": scope,
        "projection": projection,
        "ambiguity": ambiguity,
        "packet": packet,
        "execution": execution,
        "model_contract": model_contract,
        "request": request,
        "model_output": model_output,
        "metadata": metadata,
        "evidence": evidence,
    }


def _replay(bundle, private_evidence=None):
    return replay_financial_semantic_v5_decision(
        private_evidence=(
            bundle["evidence"].private_evidence
            if private_evidence is None
            else private_evidence
        ),
        model_id=MODEL_ID,
        model_contract=bundle["model_contract"],
        execution=bundle["execution"],
        projection=bundle["projection"],
        ambiguity=bundle["ambiguity"],
        packet=bundle["packet"],
        canonical_contract=bundle["scope"].decision_contract,
        registry=bundle["registry"],
        source_package=bundle["scope"].source_package,
        execution_metadata=bundle["metadata"],
    )


def _rehash(private_evidence):
    material = copy.deepcopy(private_evidence)
    material.pop("private_evidence_hash")
    private_evidence["private_evidence_hash"] = (
        financial_semantic_v5_private_evidence_hash(material)
    )


@pytest.mark.parametrize(
    "case_id",
    (
        "syn_successor_v2_unique_cash",
        "syn_successor_v2_multiple_compatible",
    ),
)
def test_private_evidence_preserves_exact_request_decision_and_receipt(
    case_id,
):
    bundle = _bundle(case_id)
    private = bundle["evidence"].private_evidence

    assert private["exact_canonical_request_object"] == (
        bundle["request"]
    )
    assert private["canonical_request_hash"] == sha256_json(
        bundle["request"]
    )
    assert private["response_schema_hash"] == (
        bundle["model_contract"].response_format_hash
    )
    assert private["normalized_canonical_model_decision"] == (
        bundle["model_output"]
    )
    assert private["decision_hash"] == sha256_json(
        bundle["model_output"]
    )
    assert private["validator_result"]["status"] == "passed"
    assert private["provider_receipt"] == {
        "input_tokens": 321,
        "output_tokens": 47,
        "cost_usd": "0.000123",
        "latency_ms": 456,
    }
    assert private["raw_provider_transport_preserved"] is False
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not contain canonical requests" in FORBIDDEN


def test_offline_replay_reproduces_exact_materialized_artifact_hash():
    bundle = _bundle("syn_successor_v2_unique_cash")
    replay = _replay(bundle)

    assert replay.status == "exact"
    assert replay.materialized_artifact == (
        bundle["evidence"].materialized_artifact
    )
    assert replay.materialized_artifact_hash == (
        bundle["evidence"].private_evidence[
            "materialized_artifact_hash"
        ]
    )
    assert replay.decision_hash == bundle["evidence"].private_evidence[
        "decision_hash"
    ]
    assert replay.safe_receipt == bundle["evidence"].safe_receipt


def test_offline_replay_accepts_canonical_json_key_reordering():
    bundle = _bundle("syn_successor_v2_unique_cash")
    private = dict(
        reversed(
            tuple(bundle["evidence"].private_evidence.items())
        )
    )

    assert _replay(bundle, private).status == "exact"


def test_repository_safe_receipt_links_hashes_without_private_values():
    bundle = _bundle("syn_successor_v2_unique_cash")
    safe = bundle["evidence"].safe_receipt
    private = bundle["evidence"].private_evidence
    safe_json = json.dumps(safe, ensure_ascii=False, sort_keys=True)

    assert safe["hashes"]["private_evidence_hash"] == private[
        "private_evidence_hash"
    ]
    assert safe["hashes"]["decision_hash"] == private[
        "decision_hash"
    ]
    assert safe["hashes"]["materialized_artifact_hash"] == private[
        "materialized_artifact_hash"
    ]
    assert safe["counts"]["provider_calls_total"] == 1
    assert safe["decision_classification"]["disposition"] == (
        "typed_input"
    )
    assert safe["exact_canonical_decision_preserved"] is True
    assert safe["offline_replay"] == "exact"
    assert safe["private_safe_hash_link_verified"] is True
    assert safe["raw_private_data_in_receipt"] is False
    private_values = {
        *bundle["fixture"].selected_literals.values(),
        *bundle["fixture"].selected_literals.keys(),
    }
    assert all(str(value) not in safe_json for value in private_values)
    assert all(
        forbidden not in safe_json
        for forbidden in (
            "exact_canonical_request_object",
            "normalized_canonical_model_decision",
            "source_value_ref",
            "literal_value",
            "value_bindings",
            "raw_provider_output",
        )
    )


@pytest.mark.parametrize(
    "field",
    (
        "canonical_request",
        "decision",
        "validator",
        "artifact",
        "execution_metadata",
    ),
)
def test_offline_replay_rejects_rehashed_private_tampering(field):
    bundle = _bundle("syn_successor_v2_unique_cash")
    private = copy.deepcopy(bundle["evidence"].private_evidence)
    if field == "canonical_request":
        private["exact_canonical_request_object"]["model"] = "other"
        private["canonical_request_hash"] = sha256_json(
            private["exact_canonical_request_object"]
        )
    elif field == "decision":
        private["normalized_canonical_model_decision"]["decision"][
            "reason_code"
        ] = "no_registry_type"
        private["decision_hash"] = sha256_json(
            private["normalized_canonical_model_decision"]
        )
    elif field == "validator":
        private["validator_result"]["status"] = "failed"
    elif field == "artifact":
        private["materialized_artifact_hash"] = "0" * 64
    else:
        private["replay_authorities"]["execution_metadata"][
            "execution_ref"
        ] = "execution:v5-evidence:tampered"
    _rehash(private)

    with pytest.raises(
        Gate2FinancialSemanticV5DecisionEvidenceError
    ):
        _replay(bundle, private)


@pytest.mark.parametrize(
    "receipt",
    (
        Gate2FinancialSemanticV5ProviderCallReceipt(
            input_tokens=-1,
            output_tokens=1,
            cost_usd="0.1",
            latency_ms=1,
        ),
        Gate2FinancialSemanticV5ProviderCallReceipt(
            input_tokens=1,
            output_tokens=1,
            cost_usd="NaN",
            latency_ms=1,
        ),
        Gate2FinancialSemanticV5ProviderCallReceipt(
            input_tokens=1,
            output_tokens=1,
            cost_usd="0.1",
            latency_ms=-1,
        ),
    ),
)
def test_provider_receipt_is_bounded_and_numeric(receipt):
    bundle = _bundle("syn_successor_v2_unique_cash")

    with pytest.raises(
        Gate2FinancialSemanticV5DecisionEvidenceError
    ) as exc:
        Gate2FinancialSemanticV5DecisionEvidenceFactory().create(
            case_id=bundle["case"]["case_id"],
            model_id=MODEL_ID,
            canonical_request=bundle["request"],
            model_output=bundle["model_output"],
            provider_receipt=receipt,
            model_contract=bundle["model_contract"],
            execution=bundle["execution"],
            projection=bundle["projection"],
            ambiguity=bundle["ambiguity"],
            packet=bundle["packet"],
            canonical_contract=bundle["scope"].decision_contract,
            registry=bundle["registry"],
            source_package=bundle["scope"].source_package,
            execution_metadata=bundle["metadata"],
        )
    assert exc.value.code == (
        "financial_semantic_v5_provider_receipt_invalid"
    )
