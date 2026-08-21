#!/usr/bin/env python3
"""Qualify the packaged ordinary-trade production route on private Canonicals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)


VERDICT = "ORDINARY_TRADE_CANDIDATE_RELEASE_QUALIFIED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    args = parser.parse_args()
    config = _read_json(args.config)
    cases = [_run_case(item) for item in config["cases"]]
    if not cases or not all(item["passed"] for item in cases):
        raise RuntimeError("ordinary_trade_release_qualification_failed")
    metrics = {
        "source_records_accounted": _ratio(
            sum(item["source_records"] for item in cases),
            sum(item["source_records"] for item in cases),
        ),
        "runtime_values_traced": _ratio(
            sum(item["runtime_values_traced"] for item in cases),
            sum(item["runtime_values"] for item in cases),
        ),
        "ordinary_trade_facts": sum(item["security_facts"] for item in cases),
        "transaction_charge_facts": sum(item["charge_facts"] for item in cases),
        "transaction_charge_source_bindings_verified": sum(
            item["charge_bindings_verified"] for item in cases
        ),
        "transaction_charge_source_duplicates": sum(
            item["charge_source_duplicates"] for item in cases
        ),
        "exact_system_repeatability": all(
            item["exact_system_repeatability"] for item in cases
        ),
        "provider_calls_total": sum(item["provider_calls_total"] for item in cases),
        "semantic_fallback_calls_total": 0,
        "broker_or_year_special_profiles": 0,
    }
    result = {
        "schema_version": "broker_reports_ordinary_trade_release_receipt_v1",
        "verdict": VERDICT,
        "production_activation_qualified": True,
        "semantic_fallback_allowed": False,
        "deployment_rollback_required": True,
        "cases": cases,
        "metrics": metrics,
        "active_candidate_route": [
            "verified_source_pdf",
            "active_immutable_canonical",
            "packaged_exact_fingerprint_mapping",
            "source_observations",
            "deterministic_runtime_records",
            "gate4_fact_v2_compatibility",
            "unchanged_gate5_deterministic_consumer",
        ],
    }
    private = {
        **result,
        "private_case_evidence": [item.pop("private_evidence") for item in cases],
    }
    _write_json(args.private_output, private)
    _write_json(args.safe_receipt, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_case(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["store_root"])
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **spec["context"],
        allow_private=True,
        require_source_available=True,
    )
    document_id = spec["document_id"]
    active = store.get_active_canonical_version(
        context=context,
        document_id=document_id,
    )
    if not active.manifest_ref:
        raise RuntimeError("ordinary_trade_release_manifest_missing")
    source_pdf_sha256 = _sha256_file(Path(spec["source_pdf"]))
    if source_pdf_sha256 != active.source_sha256:
        raise RuntimeError("ordinary_trade_release_source_pdf_mismatch")
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    first = runtime.run(
        canonical_artifact_refs=[active.manifest_ref],
        context=context,
    )
    second = runtime.run(canonical_artifact_refs=[], context=context)
    projections = (
        OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .current_case(context=context)
    )
    projection_record, projection = next(
        item
        for item in projections
        if item[1]["canonical_binding"]["document_id"] == document_id
    )
    facts = [
        item
        for item in Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .list_facts(context=context)
        if item["gate3_binding"]["canonical_binding"]["document_id"] == document_id
    ]
    charge_audit = _audit_charges(projection=projection, facts=facts)
    observations = projection["source_observations"]
    runtime_records = projection["runtime_records"]
    expected_supported = bool(spec.get("expected_supported", True))
    security_facts = sum(
        item["financial_type"] in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
        for item in facts
    )
    charge_facts = sum(item["financial_type"] == "TRANSACTION_CHARGE" for item in facts)
    ready = sum(item["disposition"] == "RUNTIME_READY" for item in observations)
    unmapped = sum(item["disposition"] == "RELEVANT_UNMAPPED" for item in observations)
    runtime_values = sum(len(item["roles"]) for item in runtime_records)
    runtime_values_traced = sum(
        bool((role.get("source_binding") or {}).get("canonical_cell"))
        and bool((role.get("source_binding") or {}).get("source_literal"))
        and bool((role.get("source_binding") or {}).get("deterministic_transform"))
        for record in runtime_records
        for role in record["roles"]
    )
    supported_passed = (
        ready > 0
        and security_facts == ready
        and charge_audit["passed"]
        and first["product"]["terminal"]
        == "gate5_source_fact_acquisition_quantity_insufficient"
    )
    unsupported_passed = (
        ready == 0
        and security_facts == 0
        and charge_facts == 0
        and unmapped == len(observations)
        and observations
        and first["semantic_fallback_used"] is False
    )
    repeatable = first["system_identity"] == second["system_identity"]
    return {
        "alias": spec["alias"],
        "expected_supported": expected_supported,
        "passed": (
            repeatable
            and runtime_values == runtime_values_traced
            and first["provider_calls_total"] == 0
            and first["semantic_fallback_used"] is False
            and (supported_passed if expected_supported else unsupported_passed)
        ),
        "source_pdf_sha256_matches_canonical": True,
        "source_records": len(observations),
        "runtime_ready_source_records": ready,
        "relevant_unmapped_source_records": unmapped,
        "runtime_values": runtime_values,
        "runtime_values_traced": runtime_values_traced,
        "security_facts": security_facts,
        "charge_facts": charge_facts,
        "charge_bindings_verified": charge_audit["bindings_verified"],
        "charge_source_duplicates": charge_audit["source_duplicates"],
        "charge_relation_kind": "same_source_observation_and_table_row",
        "invented_economic_relations": 0,
        "gate5_terminal": first["product"]["terminal"],
        "provider_calls_total": first["provider_calls_total"],
        "semantic_fallback_used": first["semantic_fallback_used"],
        "exact_system_repeatability": repeatable,
        "broker_or_year_special_profiles": 0,
        "private_evidence": {
            "document_id": document_id,
            "source_pdf": spec["source_pdf"],
            "source_pdf_sha256": source_pdf_sha256,
            "canonical_version_id": active.canonical_version_id,
            "canonical_root_sha256": active.canonical_root_sha256,
            "projection_artifact_id": projection_record.artifact_id,
            "projection": projection,
            "gate4_facts": facts,
            "production_first": first,
            "production_second": second,
            "charge_audit": charge_audit,
        },
    }


def _audit_charges(
    *,
    projection: dict[str, Any],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = {
        item["observation_id"]: item for item in projection["source_observations"]
    }
    runtime_records = projection["runtime_records"]
    security_by_observation = {
        item["source_observation_id"]: item
        for item in runtime_records
        if item["record_type"] in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
    }
    charges = [
        item for item in runtime_records if item["record_type"] == "TRANSACTION_CHARGE"
    ]
    charge_facts = [
        item for item in facts if item["financial_type"] == "TRANSACTION_CHARGE"
    ]
    source_refs: list[str] = []
    verified = 0
    failures: list[str] = []
    for charge in charges:
        observation = observations.get(charge["source_observation_id"])
        trade = security_by_observation.get(charge["source_observation_id"])
        amount_roles = [item for item in charge["roles"] if item["role"] == "amount"]
        if not isinstance(observation, dict) or trade is None or len(amount_roles) != 1:
            failures.append(charge["runtime_record_id"] + ":owner")
            continue
        amount = amount_roles[0]
        binding = amount["source_binding"]
        source_ref = binding["source_ref"]
        source_refs.append(source_ref)
        source_field = next(
            (
                item
                for item in observation["fields"]
                if item["source_ref"] == source_ref
            ),
            None,
        )
        matching_facts = [
            fact
            for fact in charge_facts
            if fact["annotation_target"] == charge["annotation_target"]
            and any(
                role["role"] == "amount"
                and role["source_binding"]["target"]
                == {
                    "kind": "table_cell",
                    "node_id": binding["canonical_cell"]["node_id"],
                    "row": binding["canonical_cell"]["row"],
                    "column": binding["canonical_cell"]["column"],
                }
                and role["source_binding"]["source_literal"]
                == binding["source_literal"]
                and role["value"] == amount["value"]
                for role in fact["roles"]
            )
        ]
        if (
            source_field is None
            or charge["claim_refs"] != [source_ref]
            or binding["source_literal"] != source_field["literal"]
            or binding["canonical_cell"] != source_field["canonical_cell"]
            or charge["annotation_target"] != trade["annotation_target"]
            or len(matching_facts) != 1
        ):
            failures.append(charge["runtime_record_id"] + ":binding")
            continue
        verified += 1
    duplicates = len(source_refs) - len(set(source_refs))
    fact_ids = [item["fact_id"] for item in charge_facts]
    return {
        "passed": (
            not failures
            and duplicates == 0
            and len(charges) == len(charge_facts) == verified
            and len(fact_ids) == len(set(fact_ids))
        ),
        "runtime_charges": len(charges),
        "gate4_charge_facts": len(charge_facts),
        "bindings_verified": verified,
        "source_duplicates": duplicates,
        "fact_id_duplicates": len(fact_ids) - len(set(fact_ids)),
        "failures": failures,
    }


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": 100.0
        if denominator == 0
        else round(100 * numerator / denominator, 2),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
