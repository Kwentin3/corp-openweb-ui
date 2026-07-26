from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

from .gate2_financial_domain_catalog import (
    Gate2FinancialDomainCatalogFactory,
)
from .gate2_financial_domain_contracts import (
    FinancialDomainAccessContext,
    canonical_json,
)
from .gate2_financial_domain_local_proof import (
    _assert_exact_results,
    _rejects,
)
from .gate2_financial_domain_persistence import (
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from .gate2_financial_semantic_v5_execution import (
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from .gate2_financial_semantic_v5_preclose import (
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)


FACTORY_REQUIRED = (
    "run_financial_semantic_v5_negative_checks is the only V5 local-proof "
    "negative-check entrypoint"
)
FORBIDDEN = (
    "Negative checks must prove exact terminal rejection and must not repair "
    "decisions, call providers or relax a canonical validator"
)


def run_financial_semantic_v5_negative_checks(
    *,
    registry: Any,
    snapshot_authority_key: bytes,
    access_context: FinancialDomainAccessContext,
    created_at: str,
    model_bundles: dict[str, dict[str, Any]],
    artifacts: list[dict[str, Any]],
    source_packages: list[Any],
    snapshot: Any,
    serialized: str,
) -> dict[str, bool]:
    unique = model_bundles["syn_successor_v2_unique_cash"]
    adjacent = model_bundles["syn_successor_v2_adjacent_equal"]
    unclassified = model_bundles[
        "syn_successor_v2_no_registry_type"
    ]

    invalid_preclose = _rejects(
        lambda: Gate2FinancialSemanticV5PrecloseFactory().create(
            evidence=Gate2TechnicalPrecloseEvidence(
                source_support="supported",
                authoritative_layout_only=True,
                source_value_candidates_total=1,
                scope_valid=True,
            )
        ),
        expected_code=(
            "financial_semantic_v5_preclose_layout_value_conflict"
        ),
    )
    packet_tamper = replace(
        unique["packet"],
        packet_hash="0" * 64,
    )
    packet_tamper_rejected = _rejects(
        lambda: unique["model_contract"].validate_and_adapt(
            model_output=unique["model_output"],
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=unique["projection"],
            ambiguity=unique["ambiguity"],
            packet=packet_tamper,
            canonical_contract=unique["scope"].decision_contract,
        ),
        expected_code=(
            "financial_semantic_v5_model_contract_identity_invalid"
        ),
    )
    ambiguous_typed = _typed_output_from_canonical_schema(
        adjacent["scope"].decision_contract.openai_response_format()
    )
    ambiguous_typed_rejected = _rejects(
        lambda: adjacent["model_contract"].validate_and_adapt(
            model_output=ambiguous_typed,
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=adjacent["projection"],
            ambiguity=adjacent["ambiguity"],
            packet=adjacent["packet"],
            canonical_contract=adjacent["scope"].decision_contract,
        ),
        expected_code="financial_semantic_v5_typed_branch_prohibited",
    )
    invalid_ref = copy.deepcopy(unique["model_output"])
    invalid_ref["decision"]["value_bindings"]["amount"] = (
        "source:value:invented"
    )
    invalid_ref_rejected = _rejects(
        lambda: unique["model_contract"].validate_and_adapt(
            model_output=invalid_ref,
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=unique["projection"],
            ambiguity=unique["ambiguity"],
            packet=unique["packet"],
            canonical_contract=unique["scope"].decision_contract,
        ),
        expected_code="financial_evidence_decision_binding_outside_package",
    )
    wrong_role = copy.deepcopy(unique["model_output"])
    wrong_role["decision"]["value_bindings"]["amount"] = next(
        item.source_value_ref
        for item in unique["scope"].decision_contract.package.candidates
        if "as_of_date" in item.allowed_roles
    )
    wrong_role_rejected = _rejects(
        lambda: unique["model_contract"].validate_and_adapt(
            model_output=wrong_role,
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=unique["projection"],
            ambiguity=unique["ambiguity"],
            packet=unique["packet"],
            canonical_contract=unique["scope"].decision_contract,
        ),
        expected_code="financial_evidence_decision_binding_incompatible",
    )
    duplicate = copy.deepcopy(unclassified["model_output"])
    duplicate["decision"]["value_bindings"][1] = copy.deepcopy(
        duplicate["decision"]["value_bindings"][0]
    )
    duplicate_rejected = _rejects(
        lambda: unclassified["model_contract"].validate_and_adapt(
            model_output=duplicate,
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=unclassified["projection"],
            ambiguity=unclassified["ambiguity"],
            packet=unclassified["packet"],
            canonical_contract=unclassified["scope"].decision_contract,
        ),
        expected_code="financial_evidence_decision_binding_duplicate",
    )
    technical_branch_rejected = _rejects(
        lambda: unique["model_contract"].validate_and_adapt(
            model_output={
                "decision": {
                    "disposition": "no_financial_input",
                    "reason_code": "header_or_layout",
                }
            },
            execution=(
                Gate2FinancialSemanticV5ExecutionContractFactory().create()
            ),
            projection=unique["projection"],
            ambiguity=unique["ambiguity"],
            packet=unique["packet"],
            canonical_contract=unique["scope"].decision_contract,
        ),
        expected_code="financial_semantic_v5_technical_branch_prohibited",
    )

    tampered_artifacts = copy.deepcopy(artifacts)
    tampered_artifacts[0]["coverage"]["candidate_refs_total"] = -1
    unsigned = dict(tampered_artifacts[0])
    unsigned.pop("integrity_hash")
    tampered_artifacts[0]["integrity_hash"] = sha256_json(unsigned)
    artifact_tamper_rejected = _rejects(
        lambda: Gate2FinancialDomainCatalogFactory(
            registry=registry,
            snapshot_authority_key=snapshot_authority_key,
        ).create(
            materialized_artifacts=tampered_artifacts,
            source_packages=source_packages,
            access_context=access_context,
            created_at=created_at,
            expires_at=None,
        ),
        expected_code=(
            "financial_evidence_coverage_candidate_count_invalid"
        ),
    )
    envelope = json.loads(serialized)
    envelope["snapshot_payload"]["integrity_sha256"] = "0" * 64
    persistence_tamper_rejected = _rejects(
        lambda: Gate2FinancialDomainPersistenceFactory(
            snapshot_authority_key=snapshot_authority_key
        ).restore(serialized=canonical_json(envelope)),
        expected_code="financial_domain_persistence_payload_invalid",
    )
    query_gap_rejected = _rejects(
        lambda: _assert_exact_results(
            expected=snapshot.coverage_records(),
            observed=snapshot.coverage_records()[:-1],
            code="financial_semantic_v5_query_gap",
        ),
        expected_code="financial_semantic_v5_query_gap",
    )
    return {
        "invalid_preclose_rejected": invalid_preclose,
        "packet_identity_tamper_rejected": packet_tamper_rejected,
        "ambiguous_typed_rejected": ambiguous_typed_rejected,
        "invalid_ref_rejected": invalid_ref_rejected,
        "wrong_role_rejected": wrong_role_rejected,
        "duplicate_binding_rejected": duplicate_rejected,
        "technical_model_branch_rejected": technical_branch_rejected,
        "materialized_artifact_tamper_rejected": (
            artifact_tamper_rejected
        ),
        "persistence_tamper_rejected": persistence_tamper_rejected,
        "query_gap_rejected": query_gap_rejected,
    }


def _typed_output_from_canonical_schema(
    response_format: dict[str, Any],
) -> dict[str, Any]:
    variants = response_format["json_schema"]["schema"]["properties"][
        "decision"
    ]["anyOf"]
    variant = next(
        item
        for item in variants
        if item["properties"]["disposition"]["enum"] == ["typed_input"]
    )
    decision = {
        key: (
            value["enum"][0]
            if isinstance(value, dict)
            and isinstance(value.get("enum"), list)
            and len(value["enum"]) == 1
            else None
        )
        for key, value in variant["properties"].items()
    }
    decision["value_bindings"] = {}
    for role_id, schema in variant["properties"]["value_bindings"][
        "properties"
    ].items():
        values = schema.get("enum")
        decision["value_bindings"][role_id] = (
            values[0] if values else None
        )
    return {"decision": decision}
