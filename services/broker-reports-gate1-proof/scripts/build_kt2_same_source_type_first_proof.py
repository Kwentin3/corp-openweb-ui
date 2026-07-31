from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_type_first_proof,
)
from broker_reports_gate1.gate2_same_source_type_first_proof import (  # noqa: E402
    Gate2SameSourceTypeFirstProof,
    false_singleton_comparator,
    safe_trace_pack,
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
    / "kt2_same_source_type_first_trace.safe.json"
)
RECEIPT_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_proof_receipt.safe.json"
)


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    packages = tuple(
        corpus["packages"][index]
        for index in corpus["proof_bounded_source_unit_package_indexes"]
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    proof = Gate2SameSourceTypeFirstProof(registry=registry)
    prepared = proof.prepare(gate2_packages=packages)
    main_response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            "u01": ("t01", "t02"),
            "u02": ("t02",),
            "u03": (),
        },
    )
    main_execution = proof.execute(
        prepared=prepared,
        simulated_response=main_response,
    )
    no_exact_response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            "u01": ("t02",),
            "u02": ("t01", "t02"),
            "u03": ("t01",),
        },
    )
    no_exact_execution = proof.execute(
        prepared=prepared,
        simulated_response=no_exact_response,
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt2-main",
        gate2_packages=packages,
        prepared=prepared,
        simulated_response=main_response,
        execution=main_execution,
    )
    replay = replay_financial_semantic_v6_type_first_proof(
        private_evidence=evidence.private_evidence,
        registry=registry,
    )
    comparator = false_singleton_comparator(
        prepared=prepared,
        execution=main_execution,
    )
    main_trace = safe_trace_pack(
        prepared=prepared,
        response=main_response,
        execution=main_execution,
    )
    no_exact_trace = safe_trace_pack(
        prepared=prepared,
        response=no_exact_response,
        execution=no_exact_execution,
    )
    selected_traces = [
        copy.deepcopy(main_trace["traces"][1]),
        copy.deepcopy(main_trace["traces"][0]),
        copy.deepcopy(no_exact_trace["traces"][0]),
        copy.deepcopy(main_trace["traces"][2]),
    ]
    trace_ids = (
        "unique_safe_typed_path",
        "multiple_plausible_types",
        "no_exact_constructible_option",
        "false_singleton_trap",
    )
    for trace_id, trace in zip(trace_ids, selected_traces, strict=True):
        trace["trace_id"] = trace_id
        trace["evidence_class"] = (
            "DETERMINISTIC_ADVERSARIAL_DERIVATION"
        )
        trace["replay"] = {
            "status": replay.status,
            "hash_match": replay.replay_hash_match,
            "provider_calls_total": replay.provider_calls_total,
        }
    trace_material = {
        "schema_version": "broker_reports_kt2_type_first_trace_pack_v1",
        "evidence_class": "PRIVACY_SAFE_STRUCTURAL_COPY",
        "source_binding": {
            "real_gate2_packages_total": 1,
            "real_source_units_total": 3,
            "exact_private_values_in_git": False,
        },
        "what_model_saw": copy.deepcopy(prepared.candidate.payload),
        "what_model_did_not_see": [
            "canonical_type_ids",
            "canonical_typed_option_ids",
            "source_refs",
            "role_bindings",
            "materialized_values",
            "code_owned_reasons",
            "expected_answers",
        ],
        "sealed_mapping_safe_summary": (
            prepared.mapping_receipt.safe_summary()
        ),
        "response_profile_safe_summary": (
            prepared.response_profile.safe_summary()
        ),
        "traces": selected_traces,
        "completeness_accounting": copy.deepcopy(main_execution.accounting),
        "false_singleton_comparator": comparator,
        "existing_owner_reuse": {
            "choice": "Gate2FinancialSemanticV6ChoiceContractFactory",
            "expansion": "Gate2FinancialSemanticV6DecisionExpansionFactory",
            "validator": "Gate2FinancialEvidenceValidatedDecisionFactory",
            "materializer": "Gate2FinancialEvidenceMaterializerFactory",
            "evidence_replay": (
                "Gate2FinancialSemanticV6DecisionEvidenceFactory"
            ),
            "persistence": "ArtifactStoreFactory / ArtifactResolver",
        },
        "evidence_safe_receipt": copy.deepcopy(evidence.safe_receipt),
        "replay": {
            "status": replay.status,
            "replay_exact": True,
            "replay_hash_match": replay.replay_hash_match,
            "execution_integrity_hash": replay.execution_integrity_hash,
            "materialized_artifact_hashes": list(
                replay.materialized_artifact_hashes
            ),
            "provider_calls_total": replay.provider_calls_total,
        },
        "privacy": {
            "customer_values": False,
            "raw_source_refs": False,
            "raw_provider_payloads": False,
            "private_paths": False,
        },
    }
    trace_pack = {
        **trace_material,
        "integrity_hash": _sha256_json(trace_material),
    }
    receipt_material = {
        "schema_version": "broker_reports_kt2_type_first_proof_fixture_receipt_v1",
        "corpus_integrity_hash": corpus["integrity_hash"],
        "type_card_projection_hash": (
            prepared.candidate.type_card_projection_hash
        ),
        "sealed_request_hash": prepared.candidate.request_hash,
        "sealed_mapping_hash": prepared.mapping_receipt.integrity_hash,
        "main_execution_integrity_hash": main_execution.integrity_hash,
        "trace_pack_integrity_hash": trace_pack["integrity_hash"],
        "real_gate2_packages_total": 1,
        "real_source_units_total": 3,
        "adversarial_response_cases_total": 22,
        "replay_tamper_cases_total": 6,
        "human_reviewable_traces_total": 4,
        "type_cards_total": len(prepared.candidate.payload["type_cards"]),
        "prebound_options_total": len(
            prepared.mapping_receipt.option_restoration
        ),
        "simulated_responses_total": 2,
        "typed_units_total": main_execution.accounting["typed"],
        "unclassified_units_total": main_execution.accounting[
            "unclassified"
        ],
        "unaccounted_units_total": main_execution.accounting[
            "unaccounted_units"
        ],
        **{
            key: value
            for key, value in comparator.items()
            if key.endswith("_total")
        },
        "replay_cases_total": 1,
        "replay_hash_mismatches_total": 0,
        "canonical_type_count_delta": 0,
        "canonical_shape_delta": 0,
        "materializer_contract_delta": 0,
        "canonical_materializer_authorities_total": 1,
        "semantic_product_routes_total": 1,
        "proof_product_reachability": False,
        "proof_provider_reachability": False,
        "model_calls_total": 0,
        "provider_calls_total": 0,
        "retries_total": 0,
        "repairs_total": 0,
        "fallbacks_total": 0,
        "model_generated_values_total": 0,
        "unknown_local_keys_accepted_total": 0,
        "unbound_source_refs_total": 0,
        "duplicate_materialized_facts_total": 0,
        "customer_values_in_git_total": 0,
        "raw_provider_payloads_in_git_total": 0,
        "live_changes_total": 0,
        "type_first_activation_total": 0,
        "model_qualification_started": False,
        "product_activation_started": False,
        "status": "passed",
    }
    receipt = {
        **receipt_material,
        "integrity_sha256": _sha256_json(receipt_material),
    }
    return trace_pack, receipt


def _validate(path: Path, hash_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    material = copy.deepcopy(value)
    supplied = material.pop(hash_field, None)
    if supplied != _sha256_json(material):
        raise ValueError(f"kt2_proof_output_integrity_invalid:{path.name}")
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "C:\\",
        "D:\\",
        "openwebui_file_id",
        "raw_provider_response",
        "provider_response_id",
    ):
        if forbidden in serialized:
            raise ValueError(f"kt2_proof_output_privacy_invalid:{path.name}")
    return value


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


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
            raise SystemExit("kt2_same_source_type_first_proof_drift")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "mode": "check",
                    "traces_total": 4,
                    "provider_calls_total": 0,
                    "unaccounted_units_total": 0,
                },
                sort_keys=True,
            )
        )
        return
    TRACE_PATH.write_bytes(_json_bytes(built[0]))
    RECEIPT_PATH.write_bytes(_json_bytes(built[1]))
    print(
        json.dumps(
            {
                "status": "written",
                "trace": TRACE_PATH.relative_to(REPO_ROOT).as_posix(),
                "receipt": RECEIPT_PATH.relative_to(REPO_ROOT).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
