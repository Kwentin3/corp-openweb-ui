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
from .gate2_financial_domain_local_proof import _assert_exact_results, _rejects
from .gate2_financial_domain_persistence import (
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v5_preclose import (
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterializerFactory,
    validate_financial_semantic_v6_total_materialization,
)


FACTORY_REQUIRED = (
    "run_financial_semantic_v6_negative_checks is the only V6 local-proof "
    "negative-check entrypoint"
)
FORBIDDEN = (
    "Negative checks must prove exact terminal rejection and must not repair "
    "a choice, call providers, invent options or relax canonical factories"
)


def run_financial_semantic_v6_negative_checks(
    *,
    registry: Any,
    snapshot_authority_key: bytes,
    access_context: FinancialDomainAccessContext,
    created_at: str,
    semantic_bundles: dict[str, dict[str, Any]],
    artifacts: list[dict[str, Any]],
    source_packages: list[Any],
    snapshot: Any,
    serialized: str,
) -> dict[str, bool]:
    unique = semantic_bundles["syn_successor_v2_unique_cash"]
    adjacent = semantic_bundles["syn_successor_v2_adjacent_equal"]
    unclassified = semantic_bundles["syn_successor_v2_no_registry_type"]

    invalid_preclose_rejected = _rejects(
        lambda: Gate2FinancialSemanticV5PrecloseFactory().create(
            evidence=Gate2TechnicalPrecloseEvidence(
                source_support="supported",
                authoritative_layout_only=True,
                source_value_candidates_total=1,
                scope_valid=True,
            )
        ),
        expected_code=("financial_semantic_v5_preclose_layout_value_conflict"),
    )
    packet_tamper = replace(unique["packet"], packet_hash="0" * 64)
    packet_tamper_rejected = _rejects(
        lambda: _expand(
            unique,
            unique["model_choice"],
            packet=packet_tamper,
        ),
        expected_code=("financial_semantic_v6_expansion_choice_contract_invalid"),
    )
    ambiguous_typed_rejected = _rejects(
        lambda: _expand(
            adjacent,
            {
                "disposition": "typed_input",
                "typed_option_id": "financial-typed-option:unknown",
            },
        ),
        expected_code="financial_semantic_v6_expansion_option_unknown",
    )
    nonminimal_choice = {
        **unique["model_choice"],
        "reason_code": "ambiguous_registry_type",
    }
    nonminimal_choice_rejected = _rejects(
        lambda: _expand(unique, nonminimal_choice),
        expected_code="financial_semantic_v6_expansion_typed_shape_invalid",
    )
    technical_model_branch_rejected = _rejects(
        lambda: _expand(
            unique,
            {
                "disposition": "no_financial_input",
                "reason_code": "header_or_layout",
            },
        ),
        expected_code="financial_semantic_v6_expansion_disposition_invalid",
    )
    expansion_tamper = replace(
        unique["expansion"],
        integrity_hash="0" * 64,
    )
    expansion_tamper_rejected = _rejects(
        lambda: Gate2FinancialSemanticV6TotalMaterializerFactory(
            registry=registry
        ).create(
            expansion=expansion_tamper,
            model_output=unique["model_choice"],
            choice_contract=unique["choice_contract"],
            packet=unique["packet"],
            evidence_bundle=unique["evidence_bundle"],
            source_package=unique["scope"].source_package,
            compilation=unique["compilation"],
        ),
        expected_code="financial_semantic_v6_totality_expansion_invalid",
    )
    retention_tamper = replace(
        unclassified["total"],
        terminal_source_value_refs=(
            unclassified["total"].terminal_source_value_refs[:-1]
        ),
    )
    retention_tamper_rejected = _rejects(
        lambda: validate_financial_semantic_v6_total_materialization(
            result=retention_tamper,
            expansion=unclassified["expansion"],
            model_output=unclassified["model_choice"],
            choice_contract=unclassified["choice_contract"],
            packet=unclassified["packet"],
            evidence_bundle=unclassified["evidence_bundle"],
            source_package=unclassified["scope"].source_package,
            compilation=unclassified["compilation"],
            registry=registry,
        ),
        expected_code=("financial_semantic_v6_total_materialization_integrity_invalid"),
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
        expected_code=("financial_evidence_coverage_candidate_count_invalid"),
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
            code="financial_semantic_v6_query_gap",
        ),
        expected_code="financial_semantic_v6_query_gap",
    )
    return {
        "invalid_preclose_rejected": invalid_preclose_rejected,
        "packet_identity_tamper_rejected": packet_tamper_rejected,
        "adjacent_equal_typed_rejected": ambiguous_typed_rejected,
        "nonminimal_choice_rejected": nonminimal_choice_rejected,
        "technical_model_branch_rejected": (technical_model_branch_rejected),
        "expansion_tamper_rejected": expansion_tamper_rejected,
        "unclassified_retention_tamper_rejected": (retention_tamper_rejected),
        "materialized_artifact_tamper_rejected": (artifact_tamper_rejected),
        "persistence_tamper_rejected": persistence_tamper_rejected,
        "query_gap_rejected": query_gap_rejected,
    }


def _expand(
    bundle: dict[str, Any],
    model_choice: dict[str, Any],
    *,
    packet=None,
):
    return Gate2FinancialSemanticV6DecisionExpansionFactory(
        registry=bundle["registry"]
    ).create(
        model_output=model_choice,
        choice_contract=bundle["choice_contract"],
        packet=bundle["packet"] if packet is None else packet,
        evidence_bundle=bundle["evidence_bundle"],
        source_package=bundle["scope"].source_package,
        compilation=bundle["compilation"],
    )
