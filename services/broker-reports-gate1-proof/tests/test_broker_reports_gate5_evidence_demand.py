from __future__ import annotations

import inspect

import pytest

from broker_reports_gate1.gate3_evidence_demand_port import (
    Gate3EvidenceDemandPortFactory,
)
from broker_reports_gate1.gate5_evidence_demand import (
    EVIDENCE_DEMAND_IS_REQUEST_NOT_READER,
    Gate5EvidenceDemandRuntimeFactory,
)
from broker_reports_gate1.gate5_evidence_demand_contract import (
    Gate5EvidenceDemandContractAuthorityFactory,
)


def _methodology(*requirements: str, owners: tuple[str, ...] = ("consumer_a",)) -> dict:
    return {
        "rules": [
            {
                "rule_id": "rule_a",
                "required_inputs": list(requirements),
                "output": "result_a",
            }
        ],
        "demand_bindings": [
            {"demand": "demand_a", "owner": owner, "rule_ids": ["rule_a"]}
            for owner in owners
        ],
    }


def _evaluate(*, requirements: tuple[str, ...], facts: list[dict]) -> dict:
    return Gate5EvidenceDemandRuntimeFactory.create().evaluate(
        active_demands=["demand_a"],
        active_rule_ids=["rule_a"],
        methodology=_methodology(*requirements),
        evidence_contract=(
            Gate5EvidenceDemandContractAuthorityFactory.create().resolve()
        ),
        normalized_facts=facts,
    )


def _fact(fact_type: str, *roles: str) -> dict:
    return {
        "fact_id": f"fact_{fact_type.casefold()}_{len(roles)}",
        "financial_type": fact_type,
        "roles": [
            {"role": role, "status": "value", "value": f"value_{index}"}
            for index, role in enumerate(roles)
        ],
    }


def test_existing_fact_is_reused_without_source_request() -> None:
    result = _evaluate(
        requirements=("dividend_amount",),
        facts=[_fact("DIVIDEND_INCOME", "amount")],
    )

    assert result["evidence_demands"][0]["classification"] == "FACT_AVAILABLE"
    assert result["source_owner_requests"] == []
    assert result["metrics"]["provider_calls"] == 0


def test_missing_fact_emits_request_and_never_accepts_canonical_input() -> None:
    result = _evaluate(requirements=("dividend_amount",), facts=[])

    assert result["evidence_demands"][0]["classification"] == "SOURCE_OWNER_REQUESTED"
    assert result["source_owner_requests"][0]["fact_type"] == "DIVIDEND_INCOME"
    assert result["source_owner_requests"][0]["required_roles"] == ["amount"]
    assert EVIDENCE_DEMAND_IS_REQUEST_NOT_READER in result["terminals"]
    assert (
        "canonical_documents"
        not in inspect.signature(
            Gate5EvidenceDemandRuntimeFactory.create().evaluate
        ).parameters
    )
    assert result["source_or_canonical_read"] is False


def test_one_meaning_shared_by_multiple_consumers_emits_one_request() -> None:
    runtime = Gate5EvidenceDemandRuntimeFactory.create()
    result = runtime.evaluate(
        active_demands=["demand_a"],
        active_rule_ids=["rule_a"],
        methodology=_methodology(
            "dividend_amount", owners=("consumer_a", "consumer_b")
        ),
        evidence_contract=(
            Gate5EvidenceDemandContractAuthorityFactory.create().resolve()
        ),
        normalized_facts=[],
    )

    assert len(result["source_owner_requests"]) == 1
    assert result["source_owner_requests"][0]["consumers"] == [
        "consumer_a",
        "consumer_b",
    ]


def test_financial_request_binds_to_current_gate3_dictionary_and_role_pack() -> None:
    request = _evaluate(requirements=("dividend_amount",), facts=[])[
        "source_owner_requests"
    ]

    binding = Gate3EvidenceDemandPortFactory.create().bind(request)

    assert binding["counts"] == {
        "BOUND_TO_EXISTING_GATE3_OWNER": 1,
        "UPSTREAM_FACT_CONTRACT_GAP": 0,
        "UPSTREAM_ROLE_CONTRACT_MISMATCH": 0,
    }
    assert binding["bindings"][0]["owner_factory"] == (
        "Gate3ChunkBatchLabelingFactory.create"
    )
    assert binding["bindings"][0]["owner_arguments"] == {
        "requested_financial_labels": ["DIVIDEND_INCOME"]
    }
    assert binding["source_or_canonical_read"] is False
    assert binding["provider_calls"] == 0


def test_new_nonfinancial_meaning_fails_closed_at_existing_owner_boundary() -> None:
    request = _evaluate(requirements=("payer_organization_jurisdiction",), facts=[])[
        "source_owner_requests"
    ]

    binding = Gate3EvidenceDemandPortFactory.create().bind(request)

    assert binding["bindings"][0]["outcome"] == "UPSTREAM_FACT_CONTRACT_GAP"
    assert binding["bindings"][0]["owner_factory"] is None


def test_ambiguous_role_request_does_not_fall_back_to_generic_extraction() -> None:
    request = _evaluate(requirements=("dividend_amount",), facts=[])[
        "source_owner_requests"
    ][0]
    request["required_roles"] = ["payer_country"]

    binding = Gate3EvidenceDemandPortFactory.create().bind([request])

    assert binding["bindings"][0]["outcome"] == ("UPSTREAM_ROLE_CONTRACT_MISMATCH")
    assert binding["bindings"][0]["owner_factory"] is None


def test_per_observation_cardinality_requests_owner_when_one_sibling_is_incomplete() -> (
    None
):
    result = _evaluate(
        requirements=("dividend_amount",),
        facts=[
            _fact("DIVIDEND_INCOME", "amount"),
            _fact("DIVIDEND_INCOME", "date"),
        ],
    )

    assert result["evidence_demands"][0]["classification"] == ("SOURCE_OWNER_REQUESTED")


def test_factory_rejects_removed_semantic_adapter_api() -> None:
    with pytest.raises(TypeError):
        Gate5EvidenceDemandRuntimeFactory.create(semantic_adapter=object())
