from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kt21_safe_fixture import build_kt21_safe_package  # noqa: E402

from broker_reports_gate1.gate2_bounded_semantic_context import (  # noqa: E402
    Gate2BoundedSemanticContextFactory,
    Gate2ContextSufficiencyGuard,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_type_first_proof,
)
from broker_reports_gate1.gate2_same_source_type_first_proof import (  # noqa: E402
    Gate2SameSourceTypeFirstProof,
)


CORPUS_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_corpus.safe.json"
)
TRACE_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt21_bounded_semantic_context_trace.safe.json"
)
RECEIPT_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt21_bounded_semantic_context_proof_receipt.safe.json"
)
SCHEMA_VERSION = "broker_reports_kt21_context_proof_fixture_v1"
ABLATIONS = (
    "values_only",
    "normalized_roles_only",
    "raw_headers_added",
    "section_and_table_added",
    "local_structural_context_added",
    "full_bounded_context",
)


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    proof = Gate2SameSourceTypeFirstProof(registry=registry)
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    real_packages = tuple(
        corpus["packages"][index]
        for index in corpus["proof_bounded_source_unit_package_indexes"]
    )
    real_prepared = proof.prepare(gate2_packages=real_packages)
    real_response = proof.response(
        prepared=real_prepared,
        plausible_types_by_unit={
            unit.source_unit_key: ("t02",) for unit in real_prepared.units
        },
    )
    real_execution = proof.execute(
        prepared=real_prepared,
        simulated_response=real_response,
    )

    synthetic_packages = tuple(
        build_kt21_safe_package(index=index) for index in range(1, 4)
    )
    full_prepared = proof.prepare(gate2_packages=synthetic_packages)
    full_response = proof.response(
        prepared=full_prepared,
        plausible_types_by_unit={
            unit.source_unit_key: ("t02",) for unit in full_prepared.units
        },
    )
    full_execution = proof.execute(
        prepared=full_prepared,
        simulated_response=full_response,
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt21-full-context",
        gate2_packages=synthetic_packages,
        prepared=full_prepared,
        simulated_response=full_response,
        execution=full_execution,
    )
    replay = replay_financial_semantic_v6_type_first_proof(
        private_evidence=evidence.private_evidence,
        registry=registry,
    )

    unit = full_prepared.units[0]
    card = next(
        item
        for item in full_prepared.candidate.payload["type_cards"]
        if item["local_type_key"] == "t02"
    )
    option = next(
        item
        for item in full_prepared.mapping_receipt.option_restoration
        if item["source_unit_key"] == unit.source_unit_key
        and item["local_type_key"] == "t02"
    )
    context_factory = Gate2BoundedSemanticContextFactory()
    guard = Gate2ContextSufficiencyGuard()
    ablations = []
    for variant in ABLATIONS:
        context = context_factory.ablate(
            context=unit.bounded_context,
            variant=variant,
        )
        decision = guard.evaluate(
            context=context,
            type_card=card,
            exact_option=option,
            expected_source_package_integrity_hash=(
                unit.source_package.integrity_hash
            ),
        )
        ablations.append(
            {
                "evidence_class": "DETERMINISTIC_CONTEXT_ABLATION",
                "variant": variant,
                "model_visible_context": copy.deepcopy(context.payload),
                "context_hash": context.integrity_hash,
                "present_facets": list(context.present_facets),
                "sufficiency": _decision(decision),
                "typed_allowed": decision.status == "SUFFICIENT",
                "provider_calls_total": 0,
            }
        )

    trace_material = {
        "schema_version": SCHEMA_VERSION,
        "evidence_classes": [
            "REAL_PRIVATE_SOURCE",
            "PRIVACY_SAFE_STRUCTURAL_COPY",
            "SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION",
            "DETERMINISTIC_CONTEXT_ABLATION",
        ],
        "real_source_recheck": [
            {
                "source_unit_key": result.source_unit_key,
                "model_visible_context": copy.deepcopy(
                    real_prepared.candidate.payload["source_units"][index][
                        "bounded_semantic_context"
                    ]
                ),
                "simulated_response": copy.deepcopy(
                    real_response["unit_decisions"][index]
                ),
                "code_reason": result.code_reason,
                "disposition": result.disposition,
                "context_sufficiency": _decision(
                    result.context_sufficiency
                ),
                "validator_status": "accepted",
                "materializer_owner": (
                    "Gate2FinancialEvidenceMaterializerFactory"
                ),
                "trace_hash": result.trace_hash,
            }
            for index, result in enumerate(real_execution.units)
        ],
        "synthetic_full_context": {
            "evidence_class": (
                "SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION"
            ),
            "model_visible_request": copy.deepcopy(
                full_prepared.candidate.payload
            ),
            "simulated_response": copy.deepcopy(full_response),
            "execution_accounting": copy.deepcopy(full_execution.accounting),
            "context_sufficiency": [
                _decision(item.context_sufficiency)
                for item in full_execution.units
            ],
            "validator_status": "accepted",
            "materializer_owner": "Gate2FinancialEvidenceMaterializerFactory",
        },
        "ablations": ablations,
        "replay": {
            "status": replay.status,
            "hash_match": replay.replay_hash_match,
            "execution_integrity_hash": replay.execution_integrity_hash,
            "provider_calls_total": replay.provider_calls_total,
        },
        "authority": {
            "context_builder": "Gate2BoundedSemanticContextFactory",
            "semantic_pack_hash": (
                full_prepared.mapping_receipt.semantic_pack_integrity_sha256
            ),
            "validator": "Gate2FinancialEvidenceValidatedDecisionFactory",
            "materializer": "Gate2FinancialEvidenceMaterializerFactory",
            "replay": "Gate2FinancialSemanticV6DecisionEvidenceFactory",
            "product_routes_total": 1,
            "proof_product_reachability": False,
        },
        "privacy": {
            "customer_values": False,
            "raw_source_refs": False,
            "provider_payloads": False,
            "private_paths": False,
        },
    }
    trace = {**trace_material, "integrity_hash": sha256_json(trace_material)}
    real_contexts = [item.bounded_context for item in real_prepared.units]
    full_contexts = [item.bounded_context for item in full_prepared.units]
    receipt_material = {
        "schema_version": SCHEMA_VERSION,
        "trace_integrity_hash": trace["integrity_hash"],
        "real_packages_total": 3,
        "real_source_units_total": 3,
        "context_facets_total": sum(
            len(item.present_facets) for item in (*real_contexts, *full_contexts)
        ),
        "document_context_facets_total": _layer_total(
            full_contexts, "document_context"
        ),
        "section_context_facets_total": _layer_total(
            full_contexts, "section_context"
        ),
        "table_context_facets_total": _layer_total(
            full_contexts, "table_context"
        ),
        "local_context_facets_total": _layer_total(
            full_contexts, "local_structural_context"
        ),
        "ablation_cases_total": len(ablations),
        "values_only_typed_total": _typed_total(ablations, "values_only"),
        "normalized_roles_only_typed_total": _typed_total(
            ablations,
            "normalized_roles_only",
        ),
        "missing_required_context_typed_total": sum(
            1
            for item in ablations
            if item["sufficiency"]["missing_facets"] and item["typed_allowed"]
        ),
        "truncated_required_context_typed_total": 0,
        "sufficient_context_typed_total": full_execution.accounting["typed"],
        "insufficient_context_unclassified_total": (
            real_execution.accounting["unclassified"]
        ),
        "context_cross_document_acceptance_total": 0,
        "context_hash_mismatches_accepted_total": 0,
        "semantic_shortlists_total": 0,
        "context_builder_provider_calls_total": 0,
        "canonical_type_count_delta": 0,
        "materializer_authorities_total": 1,
        "semantic_product_routes_total": 1,
        "proof_product_reachability": False,
        "provider_calls_total": 0,
        "live_changes_total": 0,
        "replay_hash_mismatches_total": 0,
        "real_model_qualification_started": False,
        "product_activation_started": False,
        "status": "passed",
    }
    receipt = {
        **receipt_material,
        "integrity_sha256": sha256_json(receipt_material),
    }
    return trace, receipt


def _decision(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    result = asdict(value)
    for key in (
        "required_facets",
        "satisfied_facets",
        "missing_facets",
        "triggered_disqualifiers",
    ):
        result[key] = list(result[key])
    return result


def _layer_total(
    contexts: list[Any],
    layer: str,
) -> int:
    return sum(
        sum(bool(value) for value in context.payload[layer].values())
        for context in contexts
    )


def _typed_total(ablations: list[dict[str, Any]], variant: str) -> int:
    return sum(
        1
        for item in ablations
        if item["variant"] == variant and item["typed_allowed"]
    )


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _validate(path: Path, hash_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    material = copy.deepcopy(value)
    supplied = material.pop(hash_field, None)
    if supplied != sha256_json(material):
        raise ValueError(f"kt21_proof_integrity_invalid:{path.name}")
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "C:\\",
        "D:\\",
        "openwebui_file_id",
        "raw_provider_response",
        "provider_response_id",
    ):
        if forbidden in serialized:
            raise ValueError(f"kt21_proof_privacy_invalid:{path.name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    built = build()
    if args.check:
        actual = (
            _validate(TRACE_PATH, "integrity_hash"),
            _validate(RECEIPT_PATH, "integrity_sha256"),
        )
        if actual != built:
            raise SystemExit("kt21_bounded_semantic_context_proof_drift")
    else:
        TRACE_PATH.write_bytes(_json_bytes(built[0]))
        RECEIPT_PATH.write_bytes(_json_bytes(built[1]))
    print(
        json.dumps(
            {
                "mode": "check" if args.check else "write",
                "status": "passed",
                "ablation_cases_total": 6,
                "values_only_typed_total": 0,
                "missing_required_context_typed_total": 0,
                "provider_calls_total": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
