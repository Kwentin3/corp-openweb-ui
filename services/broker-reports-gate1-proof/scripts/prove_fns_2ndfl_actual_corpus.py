#!/usr/bin/env python3
"""Read-only private proof for the deterministic FNS 2-NDFL adapter.

The console and optional committed JSON contain counts and opaque digests only.
Customer values, source refs, paths and raw typed payloads never leave memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactResolver,
    Gate2Fns2NdflAdapterFactory,
    Gate2Fns2NdflParityFactory,
    render_fns_2ndfl_safe_report,
    render_fns_2ndfl_parity_safe_report,
)
from profile_gate2_package_preparation import (  # noqa: E402
    DEFAULT_ACTUAL_CONFIG,
    prepare_actual_latest,
)


SCHEMA_VERSION = "broker_reports_fns_2ndfl_actual_corpus_proof_safe_v1"
OPAQUE_NAMESPACE = "broker-reports-fns-2ndfl-actual-proof-v1"
FACTORY_REQUIRED = (
    "prepare_actual_latest -> ArtifactStoreFactory.create -> ArtifactResolver; "
    "Gate2Fns2NdflAdapterFactory.create is the typed authority; "
    "Gate2Fns2NdflParityFactory.create is the paired-representation authority"
)
FORBIDDEN = (
    "The proof must not read source bytes directly, persist typed payloads, "
    "call a provider, emit private values or mutate ArtifactStore"
)


def _opaque(value: Any, *, length: int = 24) -> str:
    material = f"{OPAQUE_NAMESPACE}|{value}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:length]


def _snapshot(records: list[Any]) -> list[tuple[Any, ...]]:
    return [
        (
            record.artifact_id,
            record.payload_ref,
            record.validation_status,
            record.lifecycle_status,
            record.purge_status,
            record.updated_at,
        )
        for record in records
    ]


def _structural_signature(rows: list[Any]) -> str:
    material = [
        [str(row[2]), str(row[3]), str(row[4]), str(row[5])]
        for row in rows[1:]
        if isinstance(row, list) and len(row) >= 6
    ]
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unit_document_ref(unit: dict[str, Any]) -> str:
    return str(unit.get("document_ref") or unit.get("document_id") or "")


def _single_payload(
    *,
    resolver: ArtifactResolver,
    records: list[Any],
    context: Any,
    artifact_type: str,
) -> dict[str, Any]:
    matches = [record for record in records if record.artifact_type == artifact_type]
    if len(matches) != 1:
        raise RuntimeError(f"actual_{artifact_type}_count_invalid")
    return _object(resolver.resolve(matches[0].artifact_id, context)["payload"])


def _paired_withholding_documents(
    *,
    document_memory: dict[str, Any],
    usage_classification: dict[str, Any],
) -> list[dict[str, str]]:
    usage_by_document = {
        str(entry.get("document_ref")): entry
        for entry in usage_classification.get("entries") or []
        if isinstance(entry, dict) and entry.get("document_ref")
    }
    grouped: dict[str, dict[str, str]] = {}
    for memory in document_memory.get("documents") or []:
        if not isinstance(memory, dict):
            continue
        document_ref = str(memory.get("source_file_ref") or "")
        parent_ref = str(
            _object(memory.get("source_lineage")).get("archive_parent_source_ref")
            or ""
        )
        container_format = str(memory.get("container_format") or "")
        inferred_role = str(
            _object(usage_by_document.get(document_ref)).get("inferred_role") or ""
        )
        if (
            document_ref
            and parent_ref
            and container_format in {"pdf", "xml"}
            and inferred_role == "withholding_report"
        ):
            grouped.setdefault(parent_ref, {})[container_format] = document_ref
    return [
        {
            "pdf_document_ref": members["pdf"],
            "xml_document_ref": members["xml"],
        }
        for _, members in sorted(grouped.items())
        if set(members) == {"pdf", "xml"}
    ]


def _assert_safe(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = {
        "artifact_ref": r"\bart_[A-Za-z0-9_-]+",
        "document_ref": r"\bbrdoc_[A-Za-z0-9_-]+",
        "source_ref": r"\b(?:srcunit|srcpayload|srcval|srcsum)_[A-Za-z0-9_-]+",
        "windows_path": r"[A-Za-z]:\\",
        "private_value_key": r'"(?:value|fields|facts|cells|rows|filename)"\s*:',
    }
    violations = [
        name for name, pattern in forbidden.items() if re.search(pattern, rendered)
    ]
    if violations:
        raise RuntimeError("unsafe_fns_2ndfl_proof_output:" + ",".join(violations))


def build_proof(config_path: Path) -> dict[str, Any]:
    prepared = prepare_actual_latest(config_path)
    resolver = ArtifactResolver(prepared.store)
    records_before = resolver.catalog_run(prepared.context)
    snapshot_before = _snapshot(records_before)
    units = [
        resolver.resolve(record.artifact_id, prepared.context)["payload"]
        for record in records_before
        if record.artifact_type == "private_normalized_source_unit_v0"
        and record.validation_status == "validated"
    ]
    xml_units = [
        unit
        for unit in units
        if unit.get("parser") == "python_expat_neutral_events"
        and (unit.get("source_location") or {}).get("kind")
        == "xml_neutral_event_rows"
    ]
    document_memory = _single_payload(
        resolver=resolver,
        records=records_before,
        context=prepared.context,
        artifact_type="broker_reports_gate1_document_memory_manifest_v1",
    )
    usage_classification = _single_payload(
        resolver=resolver,
        records=records_before,
        context=prepared.context,
        artifact_type="document_usage_classification_v0",
    )
    paired_documents = _paired_withholding_documents(
        document_memory=document_memory,
        usage_classification=usage_classification,
    )
    pdf_candidates_by_document: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        if unit.get("pdf_unit_type") != "pdf_table_candidate_unit":
            continue
        document_ref = _unit_document_ref(unit)
        pdf_candidates_by_document.setdefault(document_ref, []).append(unit)
    adapter = Gate2Fns2NdflAdapterFactory().create()
    parity_service = Gate2Fns2NdflParityFactory().create()
    started = time.perf_counter()
    first_outputs = []
    outputs_by_document: dict[str, dict[str, Any]] = {}
    deterministic_replays = 0
    for unit in xml_units:
        package_ref = f"sfpkg_actual_{_opaque(unit.get('unit_ref'), length=20)}"
        first = adapter.adapt(source_package_ref=package_ref, source_unit=unit)
        second = adapter.adapt(source_package_ref=package_ref, source_unit=unit)
        if first != second:
            raise RuntimeError("fns_2ndfl_actual_deterministic_replay_mismatch")
        deterministic_replays += 1
        first_outputs.append(first)
        outputs_by_document[_unit_document_ref(unit)] = first
    parity_outputs = []
    parity_deterministic_replays = 0
    for pair in paired_documents:
        typed_output = outputs_by_document.get(pair["xml_document_ref"])
        pdf_candidates = pdf_candidates_by_document.get(
            pair["pdf_document_ref"], []
        )
        if typed_output is None or not pdf_candidates:
            raise RuntimeError("fns_2ndfl_actual_parity_input_incomplete")
        first = parity_service.reconcile(
            typed_xml_output=typed_output,
            paired_pdf_document_ref=pair["pdf_document_ref"],
            pdf_source_units=pdf_candidates,
        )
        second = parity_service.reconcile(
            typed_xml_output=typed_output,
            paired_pdf_document_ref=pair["pdf_document_ref"],
            pdf_source_units=pdf_candidates,
        )
        if first != second:
            raise RuntimeError("fns_2ndfl_actual_parity_replay_mismatch")
        parity_deterministic_replays += 1
        parity_outputs.append(first)
    elapsed = time.perf_counter() - started
    records_after = resolver.catalog_run(prepared.context)
    artifactstore_unchanged = snapshot_before == _snapshot(records_after)

    structural_variants = {
        _structural_signature(unit.get("cells") or []) for unit in xml_units
    }
    family_counts = Counter(
        str(fact.get("fact_family") or "unknown")
        for output in first_outputs
        for fact in output.get("facts") or []
        if isinstance(fact, dict)
    )
    schema_counts = Counter(
        str(output.get("schema_version_id") or "unknown")
        for output in first_outputs
    )
    period_counts = Counter(
        str(output.get("report_period") or "unknown") for output in first_outputs
    )
    safe_reports = [render_fns_2ndfl_safe_report(item) for item in first_outputs]
    parity_safe_reports = [
        render_fns_2ndfl_parity_safe_report(item) for item in parity_outputs
    ]
    parity_terminal_counts = Counter(
        {
            terminal_class: sum(
                int((output.get("terminal_class_counts") or {}).get(terminal_class) or 0)
                for output in parity_outputs
            )
            for terminal_class in {
                str(terminal_class)
                for output in parity_outputs
                for terminal_class in (output.get("terminal_class_counts") or {})
            }
        }
    )
    candidate_role_counts = Counter(
        {
            role: sum(
                int((output.get("candidate_role_counts") or {}).get(role) or 0)
                for output in parity_outputs
            )
            for role in {
                str(role)
                for output in parity_outputs
                for role in (output.get("candidate_role_counts") or {})
            }
        }
    )
    pdf_candidates_preserved = sum(
        len(output.get("pdf_candidate_refs") or []) for output in parity_outputs
    )
    unmatched_material_errors = sum(
        int(output.get("unmatched_material_errors") or 0)
        for output in parity_outputs
    )
    provider_calls = sum(
        int((output.get("provider_accounting") or {}).get("calls") or 0)
        for output in first_outputs
    )
    provider_tokens = sum(
        int((output.get("provider_accounting") or {}).get("tokens") or 0)
        for output in first_outputs
    )
    provider_cost = sum(
        int((output.get("provider_accounting") or {}).get("cost") or 0)
        for output in first_outputs
    )
    provider_calls += sum(
        int((output.get("provider_accounting") or {}).get("calls") or 0)
        for output in parity_outputs
    )
    provider_tokens += sum(
        int((output.get("provider_accounting") or {}).get("tokens") or 0)
        for output in parity_outputs
    )
    provider_cost += sum(
        int((output.get("provider_accounting") or {}).get("cost") or 0)
        for output in parity_outputs
    )

    proof = {
        "schema_version": SCHEMA_VERSION,
        "workload": {
            "kind": "actual_customer_corpus_gate1_memory",
            "opaque_run_id": _opaque(prepared.context.normalization_run_id),
            "workload_fingerprint": prepared.identity.get("workload_fingerprint"),
            "customer_values_exposed": False,
        },
        "adapter": {
            "adapter_id": "broker_reports_fns_2ndfl_source_facts_v1",
            "factory_route": FACTORY_REQUIRED,
            "forbidden_route": FORBIDDEN,
        },
        "input_accounting": {
            "neutral_xml_units": len(xml_units),
            "observed_structural_variants": len(structural_variants),
            "report_period_counts": dict(sorted(period_counts.items())),
        },
        "terminal_accounting": {
            "typed_outputs_validated": len(first_outputs),
            "deterministic_replays_passed": deterministic_replays,
            "typed_facts_total": sum(
                len(output.get("facts") or []) for output in first_outputs
            ),
            "fact_family_counts": dict(sorted(family_counts.items())),
            "non_fact_source_nodes_total": sum(
                len(output.get("non_fact_source_nodes") or [])
                for output in first_outputs
            ),
            "schema_version_counts": dict(sorted(schema_counts.items())),
            "safe_reports_validated": sum(
                report.get("validator_status") == "passed"
                for report in safe_reports
            ),
        },
        "paired_representation_accounting": {
            "paired_groups": len(paired_documents),
            "terminal_outputs_validated": len(parity_outputs),
            "deterministic_replays_passed": parity_deterministic_replays,
            "pdf_candidates_preserved": pdf_candidates_preserved,
            "pdf_candidates_canonicalized": 0,
            "candidate_role_counts": dict(sorted(candidate_role_counts.items())),
            "terminal_class_counts": dict(sorted(parity_terminal_counts.items())),
            "unmatched_material_errors": unmatched_material_errors,
            "safe_reports_validated": sum(
                report.get("validator_status") == "passed"
                for report in parity_safe_reports
            ),
            "recovery_disposition": (
                "recovery_deferred_validated_paired_xml_coverage"
            ),
        },
        "provider_accounting": {
            "calls": provider_calls,
            "tokens": provider_tokens,
            "cost": provider_cost,
            "llm_fallback_performed": False,
        },
        "performance": {
            "two_pass_adapter_wall_seconds": round(elapsed, 6),
            "outputs_per_second": round(
                (len(first_outputs) * 2) / elapsed, 3
            )
            if elapsed
            else None,
        },
        "guards": {
            "artifactstore_unchanged": artifactstore_unchanged,
            "source_bytes_read_directly": False,
            "typed_payloads_persisted": False,
            "customer_values_in_safe_output": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "acceptance": {
            "xml_packages_24_of_24": len(xml_units) == len(first_outputs) == 24,
            "structural_variants_17_observed": len(structural_variants) == 17,
            "terminal_validation_24_of_24": len(first_outputs) == 24,
            "deterministic_replay_24_of_24": deterministic_replays == 24,
            "paired_representation_groups_24_of_24": (
                len(paired_documents) == len(parity_outputs) == 24
            ),
            "paired_representation_replay_24_of_24": (
                parity_deterministic_replays == 24
            ),
            "pdf_candidates_180_preserved_recovery_deferred": (
                pdf_candidates_preserved == 180
            ),
            "bidirectional_material_parity_passed": (
                len(parity_outputs) == 24
                and all(
                    output.get("terminal_status") == "validated"
                    for output in parity_outputs
                )
            ),
            "unmatched_material_errors_zero": unmatched_material_errors == 0,
            "provider_calls_zero": provider_calls == 0,
            "provider_tokens_zero": provider_tokens == 0,
            "provider_cost_zero": provider_cost == 0,
            "artifactstore_immutability_passed": artifactstore_unchanged,
            "privacy_passed": True,
        },
    }
    if not all(proof["acceptance"].values()):
        raise RuntimeError("fns_2ndfl_actual_acceptance_failed")
    proof["safe_output_digest"] = hashlib.sha256(
        json.dumps(
            proof,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _assert_safe(proof)
    return proof


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual-config", type=Path, default=DEFAULT_ACTUAL_CONFIG)
    parser.add_argument("--safe-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    proof = build_proof(args.actual_config.resolve())
    if args.safe_output:
        output = args.safe_output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "schema_version": proof["schema_version"],
                "acceptance": proof["acceptance"],
                "safe_output_digest": proof["safe_output_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
