#!/usr/bin/env python3
"""Close Goal 5 with sealed actual-corpus and reviewed-visual evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sqlite3
import struct
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import psutil


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate2TablePackageFactory,
    PdfVisualTableReviewFactory,
    VisualReviewAuthorityContext,
    build_retention_policy,
    validate_gate2_table_package,
    validate_pdf_dual_vlm_decision,
    validate_reviewed_visual_projection,
    validate_visual_review_receipt,
    validate_visual_review_seal,
)
from broker_reports_gate1.artifact_models import ArtifactRecord  # noqa: E402
from broker_reports_gate1.artifact_store import new_artifact_id  # noqa: E402
from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    CANONICAL_TABLE_SCHEMA_VERSION,
    compare_tables,
    sha256_json,
    validate_table_output,
)
from broker_reports_gate1.pdf_visual_table_review import (  # noqa: E402
    VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION,
    VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
)


SCHEMA_VERSION = "broker_reports_goal5_integrated_actual_corpus_v1_safe"
PRIVATE_TERMINAL_SCHEMA_VERSION = (
    "broker_reports_goal5_integrated_visual_review_v1_private"
)
CONFIG_SCHEMA_VERSION = "broker_reports_goal5_visual_review_config_v1"
TERMINAL_CLASSES = {
    "usable",
    "review_required",
    "rejected",
    "unsupported",
    "confirmed_empty",
    "externally_blocked",
}
PROVIDERS = ("gemini", "openai")


class Goal5ProofError(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vlm-root", type=Path, required=True)
    parser.add_argument("--review-config", type=Path, required=True)
    parser.add_argument("--gate1-acceptance", type=Path, required=True)
    parser.add_argument("--gate1-profile", type=Path, required=True)
    parser.add_argument("--gate1-store", type=Path, required=True)
    parser.add_argument("--fns-proof", type=Path, required=True)
    parser.add_argument("--accepted-baseline", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    report = prove(
        vlm_root=args.vlm_root,
        review_config_path=args.review_config,
        gate1_acceptance_path=args.gate1_acceptance,
        gate1_profile_path=args.gate1_profile,
        gate1_store_path=args.gate1_store,
        fns_proof_path=args.fns_proof,
        accepted_baseline_path=args.accepted_baseline,
        private_output=args.private_output,
    )
    _write_json(args.safe_output, report)


def prove(
    *,
    vlm_root: Path,
    review_config_path: Path,
    gate1_acceptance_path: Path,
    gate1_profile_path: Path,
    gate1_store_path: Path,
    fns_proof_path: Path,
    accepted_baseline_path: Path,
    private_output: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    process = psutil.Process()
    config = _read_json(review_config_path)
    _require(config.get("schema_version") == CONFIG_SCHEMA_VERSION, "config_invalid")
    expected = _object(config.get("expected_counts"))

    gate1_acceptance = _read_json(gate1_acceptance_path)
    gate1_profile = _read_json(gate1_profile_path)
    fns_proof = _read_json(fns_proof_path)
    accepted_baseline = _read_json(accepted_baseline_path)
    store_accounting = _audit_gate1_store_accounting(gate1_store_path)
    upstream = _validate_upstream_acceptance(
        gate1_acceptance=gate1_acceptance,
        gate1_profile=gate1_profile,
        fns_proof=fns_proof,
        accepted_baseline=accepted_baseline,
        store_accounting=store_accounting,
    )

    source_store_before = _artifactstore_signature(gate1_store_path)
    sealed = _load_and_validate_sealed_vlm(vlm_root=vlm_root, expected=expected)
    review = _review_decisions(
        sealed=sealed,
        config=config,
    )
    package = Gate2TablePackageFactory().create().build(
        projection=review["accepted_projection"],
        case_id="customer-case-alpha-goal5-review",
    )
    package_validation = validate_gate2_table_package(
        package,
        review["accepted_projection"],
    )
    _require(package_validation["validator_status"] == "passed", "visual_gate2_failed")

    _require(not private_output.exists(), "private_output_already_exists")
    private_output.mkdir(parents=True)
    lifecycle = _persist_and_probe_lifecycle(
        root=private_output,
        review_results=review["results"],
    )
    private_terminal = {
        "schema_version": PRIVATE_TERMINAL_SCHEMA_VERSION,
        "sealed_vlm_lineage": sealed["lineage"],
        "review_results": [
            {
                "repeat_index": item["repeat_index"],
                "terminal_class": item["terminal_class"],
                "review_receipt": item["result"].review_receipt,
                "review_seal": item["result"].review_seal,
            }
            for item in review["results"]
        ],
        "accepted_projection": review["accepted_projection"],
        "gate2_package": package,
        "gate2_validation": package_validation,
    }
    private_terminal["terminal_hash"] = sha256_json(private_terminal)
    _write_json(private_output / "integrated-review.private.json", private_terminal)

    source_store_after = _artifactstore_signature(gate1_store_path)
    _require(source_store_before == source_store_after, "source_artifactstore_mutated")
    terminal_counts = Counter(
        item["terminal_class"] for item in review["results"]
    )
    _require(set(terminal_counts) <= TERMINAL_CLASSES, "terminal_class_invalid")
    _require(sum(terminal_counts.values()) == sealed["decisions_total"], "terminal_loss")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "acceptance": {
            "ACTUAL_CORPUS_ACCOUNTING": "COMPLETE",
            "ZERO_SILENT_LOSS": "PASSED",
            "UNEXPLAINED_TERMINAL_STATES": "ZERO",
            "KNOWLEDGE_RAG_VECTOR_USE": "ZERO",
            "PROVIDER_CALLS": "FULLY_ACCOUNTED",
            "REVIEWED_VISUAL_HANDOFF": "PASSED",
            "ARTIFACTSTORE_IMMUTABILITY": "PASSED",
            "GATE2_VALIDATION_ERRORS": "ZERO",
        },
        "actual_corpus": upstream["actual_corpus"],
        "format_and_lineage_accounting": upstream["format_and_lineage"],
        "fns_typed_facts": upstream["fns"],
        "deterministic_gate2": upstream["gate2"],
        "visual_review": {
            "sealed_prior_vlm_decisions": sealed["decisions_total"],
            "review_receipts_validated": len(review["results"]),
            "terminal_class_counts": dict(sorted(terminal_counts.items())),
            "canonical_promotions": 1,
            "accepted_with_correction": 1,
            "reviewed_visual_gate2_packages": 1,
            "reviewed_visual_gate2_validation_errors": 0,
            "all_decisions_terminal": True,
            "source_region_inventory_complete": True,
            "canonical_cells_accounted": review["canonical_cells_total"],
            "reviewer_type": "delegated_agent_reviewed",
            "customer_acceptance_claimed": False,
            "human_review_claimed": False,
            "provider_consensus_canonical_authority": False,
            "local_ocr_evidence_used": False,
        },
        "provider_accounting": {
            "accepted_sealed_prior_provider_executions": sealed[
                "provider_executions_total"
            ],
            "score_samples_reconciled": sealed["provider_samples_total"],
            "new_provider_calls": 0,
            "unaccounted_provider_calls": 0,
            "raw_provider_responses_retained": False,
            "provider_values_in_safe_output": False,
        },
        "private_intake": upstream["private_intake"],
        "artifact_lifecycle": lifecycle,
        "artifactstore": {
            "source_records_before": source_store_before["records_total"],
            "source_records_after": source_store_after["records_total"],
            "source_payloads_before": source_store_before["payload_files_total"],
            "source_payloads_after": source_store_after["payload_files_total"],
            "source_store_signature_before": source_store_before["signature"],
            "source_store_signature_after": source_store_after["signature"],
            "unchanged": True,
        },
        "performance": {
            "gate1_proof_wall_seconds": upstream["performance"][
                "proof_wall_seconds"
            ],
            "gate1_normalization_wall_seconds": upstream["performance"][
                "normalization_wall_seconds"
            ],
            "gate1_peak_rss_bytes": upstream["performance"]["peak_rss_bytes"],
            "integrated_review_wall_seconds": round(time.perf_counter() - started, 6),
            "integrated_review_rss_snapshot_bytes": int(process.memory_info().rss),
        },
        "privacy": {
            "customer_values_included": False,
            "source_filenames_included": False,
            "private_paths_included": False,
            "artifact_ids_included": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "evidence": {
            "vlm_run_terminal_sha256": sealed["lineage"]["run_terminal_sha256"],
            "delegated_reference_sha256": sealed["lineage"]["reference_sha256"],
            "score_sha256": sealed["lineage"]["score_sha256"],
            "private_review_terminal_sha256": hashlib.sha256(
                (private_output / "integrated-review.private.json").read_bytes()
            ).hexdigest(),
        },
    }
    _assert_safe_report(report=report, sealed=sealed)
    report["safe_output_digest"] = sha256_json(report)
    return report


def _validate_upstream_acceptance(
    *,
    gate1_acceptance: dict[str, Any],
    gate1_profile: dict[str, Any],
    fns_proof: dict[str, Any],
    accepted_baseline: dict[str, Any],
    store_accounting: dict[str, Any],
) -> dict[str, Any]:
    checks = _object(gate1_acceptance.get("automated_checks"))
    handoff = _object(gate1_acceptance.get("gate2_public_handoff"))
    full_gate2 = _object(handoff.get("full_gate2_package_builder"))
    actual = _object(gate1_acceptance.get("actual_execution"))
    reconciliation = _object(gate1_acceptance.get("corpus_reconciliation"))
    privacy = _object(gate1_acceptance.get("privacy"))
    profile_checks = _object(gate1_profile.get("checks"))
    candidate = _object(gate1_profile.get("candidate"))
    fns_acceptance = _object(fns_proof.get("acceptance"))
    fns_terminal = _object(fns_proof.get("terminal_accounting"))
    fns_pairs = _object(fns_proof.get("paired_representation_accounting"))

    _require(gate1_acceptance.get("proof_status") == "passed", "gate1_not_passed")
    _require(checks and all(value is True for value in checks.values()), "gate1_checks_failed")
    _require(handoff.get("validator_status") == "passed", "gate1_handoff_failed")
    _require(full_gate2.get("status") == "completed", "full_gate2_not_completed")
    _require(full_gate2.get("validator_status") == "passed", "full_gate2_failed")
    _require(not handoff.get("error_refs"), "full_gate2_errors_present")
    _require(gate1_profile.get("status") == "passed", "gate1_profile_not_passed")
    _require(profile_checks and all(value is True for value in profile_checks.values()), "profile_checks_failed")
    _require(fns_acceptance and all(value is True for value in fns_acceptance.values()), "fns_checks_failed")
    _require(
        privacy.get("knowledge_rag_used") is False
        and privacy.get("vectorization_performed") is False,
        "knowledge_or_vector_use_detected",
    )
    _require(
        accepted_baseline.get("status") == "terminal_delivery_candidate"
        and accepted_baseline.get("private_customer_values_in_receipt") == 0,
        "accepted_baseline_invalid",
    )
    intake = next(
        (
            item
            for item in accepted_baseline.get("capability_ownership") or []
            if isinstance(item, dict)
            and item.get("capability") == "server_authoritative_private_intake"
        ),
        None,
    )
    _require(isinstance(intake, dict) and intake.get("owner_revisions"), "private_intake_not_owned")

    _require(actual.get("top_level_inputs_total") == 56, "top_level_count_invalid")
    _require(actual.get("document_sources_total") == 104, "source_count_invalid")
    _require(actual.get("logical_documents_total") == 80, "logical_count_invalid")
    _require(actual.get("archive_containers_total") == 24, "archive_count_invalid")
    _require(actual.get("archive_promoted_members_total") == 48, "archive_member_count_invalid")
    _require(
        reconciliation.get("registry_hashes_matched_total") == 63
        and reconciliation.get("registry_records_total") == 63
        and reconciliation.get("required_top_level_sources_total") == 56,
        "registry_reconciliation_invalid",
    )

    return {
        "actual_corpus": {
            "top_level_inputs": 56,
            "source_identities": 104,
            "logical_documents": 80,
            "all_material_sources_terminal": True,
            "zero_silent_loss": True,
        },
        "format_and_lineage": {
            "csv_sources": store_accounting["format_counts"]["csv"],
            "pdf_sources": store_accounting["format_counts"]["pdf"],
            "zip_containers": store_accounting["format_counts"]["zip"],
            "html_text_sources": store_accounting["format_counts"]["html_text"],
            "xml_sources": store_accounting["format_counts"]["xml"],
            "archive_promoted_members": 48,
            "archive_containers_lineage_only": store_accounting[
                "archive_lineage_refs"
            ],
            "visual_review_refs": store_accounting["visual_review_refs"],
            "source_fact_ready_refs": store_accounting["source_fact_ready_refs"],
            "unexplained_terminal_states": 0,
        },
        "fns": {
            "xml_packages": int(fns_pairs.get("paired_groups") or 0),
            "typed_outputs_validated": int(fns_terminal.get("typed_outputs_validated") or 0),
            "typed_facts": int(fns_terminal.get("typed_facts_total") or 0),
            "structural_variants": int(
                _object(fns_proof.get("input_accounting")).get(
                    "observed_structural_variants"
                )
                or 0
            ),
            "paired_pdf_candidates_preserved": int(
                fns_pairs.get("pdf_candidates_preserved") or 0
            ),
            "unmatched_material_errors": int(
                fns_pairs.get("unmatched_material_errors") or 0
            ),
        },
        "gate2": {
            "packages_validated": int(full_gate2.get("packages_total") or 0),
            "validation_errors": 0,
            "warnings": int(full_gate2.get("warnings_total") or 0),
            "artifactstore_unchanged": True,
        },
        "private_intake": {
            "authority": "server_authoritative_private_intake",
            "accepted_baseline_evidence_validated": True,
            "knowledge_rag_vector_prohibited": True,
            "customer_values_in_evidence": False,
        },
        "performance": {
            "proof_wall_seconds": float(candidate.get("proof_wall_seconds") or 0),
            "normalization_wall_seconds": float(
                candidate.get("normalization_wall_seconds") or 0
            ),
            "peak_rss_bytes": int(candidate.get("process_peak_rss_bytes") or 0),
        },
    }


def _load_and_validate_sealed_vlm(
    *, vlm_root: Path, expected: dict[str, Any]
) -> dict[str, Any]:
    terminal_path = vlm_root / "run-v1" / "terminal.private.json"
    terminal_seal_path = vlm_root / "run-v1" / "terminal.private.sha256.json"
    identity_path = vlm_root / "run-v1" / "run.identity.safe.json"
    reference_path = (
        vlm_root / "reference-v1" / "reference.delegated-agent.private.json"
    )
    reference_seal_path = (
        vlm_root / "reference-v1" / "reference.delegated-agent.private.sha256.json"
    )
    score_path = vlm_root / "score-v3" / "score.private.json"
    score_receipt_path = vlm_root / "score-v3" / "receipt.safe.json"
    pack_path = vlm_root / "source-review-v1" / "review-pack.private.json"

    terminal, terminal_bytes = _read_json_bytes(terminal_path)
    terminal_seal = _read_json(terminal_seal_path)
    identity = _read_json(identity_path)
    reference, reference_bytes = _read_json_bytes(reference_path)
    reference_seal = _read_json(reference_seal_path)
    score, score_bytes = _read_json_bytes(score_path)
    score_receipt = _read_json(score_receipt_path)
    pack = _read_json(pack_path)

    terminal_sha = str(terminal_seal.get("terminal_sha256") or "")
    reference_sha = str(reference_seal.get("reference_sha256") or "")
    score_sha = hashlib.sha256(score_bytes).hexdigest()
    _validate_file_seal(
        seal=terminal_seal,
        content_path=terminal_path,
        content_bytes=terminal_bytes,
        digest_key="terminal_sha256",
        size_key="terminal_size_bytes",
        filename_key="terminal_filename",
    )
    _validate_file_seal(
        seal=reference_seal,
        content_path=reference_path,
        content_bytes=reference_bytes,
        digest_key="reference_sha256",
        size_key="reference_size_bytes",
        filename_key="reference_filename",
    )
    _validate_embedded_hash(identity, "identity_hash", "run_identity_hash_invalid")
    _validate_embedded_hash(score, "score_hash", "score_hash_invalid")
    _validate_embedded_hash(score_receipt, "receipt_hash", "score_receipt_hash_invalid")
    _require(identity.get("terminal_sha256") == terminal_sha, "identity_terminal_mismatch")
    _require(score.get("run_terminal_sha256") == terminal_sha, "score_terminal_mismatch")
    _require(score.get("reference_sha256") == reference_sha, "score_reference_mismatch")
    _require(
        _object(reference.get("lineage")).get("run_terminal_sha256") == terminal_sha,
        "reference_terminal_mismatch",
    )
    _require(
        reference.get("delegated_agent_reviewed") is True
        and reference.get("human_reviewed") is False
        and reference.get("customer_accepted") is False,
        "reference_authority_invalid",
    )
    _require(
        _object(score.get("reference_authority")).get("provider_outputs_used")
        is False
        and _object(score.get("reference_authority")).get(
            "provider_consensus_used"
        )
        is False,
        "provider_output_used_as_truth",
    )
    _require(
        pack.get("provider_outputs_included") is False
        and pack.get("provider_consensus_included") is False,
        "source_review_pack_contaminated",
    )

    crops: dict[str, dict[str, Any]] = {}
    for item in _dicts(pack.get("crops")):
        asset = _safe_join(vlm_root / "source-review-v1", str(item.get("asset") or ""))
        raw = asset.read_bytes()
        width, height = _png_dimensions(raw)
        crop_sha = hashlib.sha256(raw).hexdigest()
        _require(
            crop_sha == item.get("crop_sha256")
            and width == item.get("width")
            and height == item.get("height"),
            "source_review_crop_identity_invalid",
        )
        candidate_ref = str(item.get("candidate_ref") or "")
        _require(candidate_ref and candidate_ref not in crops, "source_review_crop_duplicate")
        crops[candidate_ref] = {**item, "asset_path": asset}

    table_reviews = {
        str(item.get("runtime_candidate_ref") or ""): item
        for item in _dicts(reference.get("table_reviews"))
    }
    literal_tables = {
        str(item.get("runtime_candidate_ref") or ""): item
        for item in _dicts(_object(reference.get("literal_reference")).get("tables"))
    }
    _require(set(crops) == set(table_reviews) == set(literal_tables), "reference_crop_coverage_invalid")
    for candidate_ref, crop in crops.items():
        _require(
            table_reviews[candidate_ref].get("evaluated_crop_sha256")
            == crop.get("crop_sha256")
            == literal_tables[candidate_ref].get("evaluated_crop_sha256"),
            "reference_crop_hash_mismatch",
        )

    decisions: dict[tuple[str, int], dict[str, Any]] = {}
    executions: dict[tuple[str, int, str], dict[str, Any]] = {}
    for record in _dicts(terminal.get("decision_records")):
        decision = _object(record.get("decision"))
        errors = validate_pdf_dual_vlm_decision(decision)
        _require(not errors, errors[0] if errors else "decision_invalid")
        lineage = _object(decision.get("source_lineage"))
        candidate_ref = str(lineage.get("candidate_ref") or "")
        repeat_index = int(record.get("repeat_index") or 0)
        key = (candidate_ref, repeat_index)
        _require(candidate_ref in crops and key not in decisions, "decision_coverage_invalid")
        _require(lineage.get("crop_sha256") == crops[candidate_ref]["crop_sha256"], "decision_crop_mismatch")
        decisions[key] = decision
        decision_executions = _dicts(decision.get("executions"))
        _require(
            [item.get("provider") for item in decision_executions] == list(PROVIDERS),
            "decision_provider_order_invalid",
        )
        for execution in decision_executions:
            _validate_embedded_hash(execution, "execution_hash", "execution_hash_invalid")
            provider = str(execution.get("provider") or "")
            execution_key = (candidate_ref, repeat_index, provider)
            _require(execution_key not in executions, "provider_execution_duplicate")
            _require(
                execution.get("input_hash") == lineage.get("crop_sha256")
                and execution.get("hidden_retry") is False
                and execution.get("provider_failover") is False,
                "provider_execution_lineage_invalid",
            )
            executions[execution_key] = execution

    score_samples = {}
    for sample in _dicts(score.get("provider_sample_scores")):
        candidate_hash = str(sample.get("candidate_ref_hash") or "")
        repeat_index = int(sample.get("repeat_index") or 0)
        provider = str(sample.get("provider") or "")
        candidate_ref = next(
            (
                ref
                for ref in crops
                if hashlib.sha256(ref.encode("utf-8")).hexdigest()
                == candidate_hash
            ),
            None,
        )
        _require(candidate_ref is not None, "score_candidate_unknown")
        key = (candidate_ref, repeat_index, provider)
        execution = executions.get(key)
        decision = decisions.get((candidate_ref, repeat_index))
        _require(execution is not None and decision is not None, "score_execution_missing")
        proposal = _object(decision.get("proposals")).get(provider)
        expected_proposal_hash = sha256_json(proposal) if proposal is not None else None
        _require(
            sample.get("provider_terminal_status")
            == execution.get("terminal_provider_status")
            and sample.get("input_hash") == execution.get("input_hash")
            and sample.get("prompt_hash") == execution.get("prompt_hash")
            and sample.get("requested_model_id")
            == execution.get("requested_model_id")
            and sample.get("resolved_model_id") == execution.get("resolved_model_id")
            and sample.get("proposal_hash") == expected_proposal_hash,
            "score_provider_execution_mismatch",
        )
        _require(key not in score_samples, "score_sample_duplicate")
        score_samples[key] = sample

    expected_decisions = int(expected.get("decision_records") or 0)
    expected_executions = int(expected.get("provider_executions") or 0)
    expected_samples = int(expected.get("provider_samples") or 0)
    expected_crops = int(expected.get("reviewed_crops") or 0)
    _require(
        len(decisions) == expected_decisions
        and len(executions) == expected_executions
        and len(score_samples) == expected_samples
        and len(crops) == expected_crops,
        "sealed_vlm_expected_counts_invalid",
    )
    _require(set(executions) == set(score_samples), "provider_call_accounting_incomplete")
    _require(score.get("provider_samples") == len(score_samples), "score_sample_count_invalid")

    return {
        "decisions": decisions,
        "executions": executions,
        "score_samples": score_samples,
        "crops": crops,
        "table_reviews": table_reviews,
        "literal_tables": literal_tables,
        "decisions_total": len(decisions),
        "provider_executions_total": len(executions),
        "provider_samples_total": len(score_samples),
        "lineage": {
            "run_terminal_sha256": terminal_sha,
            "reference_sha256": reference_sha,
            "score_sha256": score_sha,
        },
        "sensitive_strings": _sensitive_strings(
            decisions=decisions,
            literal_tables=literal_tables,
            crops=crops,
        ),
    }


def _review_decisions(
    *, sealed: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    selected = _object(config.get("selected_review"))
    crop_asset = str(selected.get("crop_asset") or "")
    repeat_index = int(selected.get("repeat_index") or 0)
    provider = str(selected.get("provider") or "")
    sparse_currency = selected.get("sparse_currency_columns") is True
    reviewed_at = str(selected.get("reviewed_at") or "")
    candidate_ref = next(
        (
            ref
            for ref, item in sealed["crops"].items()
            if str(item["asset_path"].name) == Path(crop_asset).name
            and str(item.get("asset") or "").replace("\\", "/")
            == crop_asset.replace("\\", "/")
        ),
        None,
    )
    _require(candidate_ref is not None, "selected_crop_not_found")
    selected_key = (candidate_ref, repeat_index)
    decision = sealed["decisions"].get(selected_key)
    _require(decision is not None and provider in PROVIDERS, "selected_decision_invalid")
    score_sample = sealed["score_samples"].get((*selected_key, provider))
    _require(
        score_sample is not None
        and score_sample.get("structurally_useful_for_assisted_review") is True,
        "selected_provider_proposal_not_useful",
    )
    _require(
        sealed["table_reviews"][candidate_ref].get("disposition")
        == "assisted_review_candidate",
        "selected_crop_not_review_eligible",
    )

    candidate = build_candidate_from_literal_reference(
        table=sealed["literal_tables"][candidate_ref],
        table_id=candidate_ref,
        sparse_currency_columns=sparse_currency,
    )
    proposal = _object(decision.get("proposals")).get(provider)
    _require(isinstance(proposal, dict), "selected_provider_proposal_missing")
    comparison = compare_tables(proposal, candidate)
    differences = _dicts(comparison.get("differences"))
    _require(differences and comparison.get("FULL_TABLE_CONSENSUS") is False, "correction_diff_missing")
    acknowledgements = [
        {
            "difference_sha256": sha256_json(item),
            "reviewer_reason_code": "source_crop_verified_correction",
        }
        for item in differences
    ]
    corrected_cells = {
        tuple(item["cell"])
        for item in differences
        if isinstance(item.get("cell"), list) and len(item["cell"]) == 2
    }
    geometry = _build_region_accounting_submission(
        decision=decision,
        candidate=candidate,
        geometry=_object(config.get("reviewed_geometry")),
        corrected_cells=corrected_cells,
    )
    accepted_submission = {
        "schema_version": VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
        "reviewed_at": reviewed_at,
        "review_decision": "accepted_with_correction",
        "decision_reason_codes": ["source_crop_review_completed"],
        "selected_proposal_provider": provider,
        "canonical_candidate": candidate,
        "correction_acknowledgements": acknowledgements,
        "region_cell_accounting": geometry,
        "attestations": _attestations(accepted=True),
    }
    service = PdfVisualTableReviewFactory().create(
        authority=VisualReviewAuthorityContext(
            authenticated_user_id="goal5-user-delegator",
            reviewer_id="codex-technical-reviewer",
            reviewer_type="delegated_agent_reviewed",
            authority_ref="user_delegation_goal5_2026_07_21",
        )
    )

    results = []
    accepted_projection = None
    for key, current_decision in sorted(sealed["decisions"].items(), key=lambda item: (item[0][0], item[0][1])):
        current_ref, current_repeat = key
        if key == selected_key:
            terminal_class = "usable"
            submission = accepted_submission
        else:
            disposition = sealed["table_reviews"][current_ref].get("disposition")
            if disposition == "unsupported_layout":
                review_decision = "unsupported"
                terminal_class = "unsupported"
            elif current_decision.get("status") == "malformed_provider_output":
                review_decision = "rejected"
                terminal_class = "rejected"
            else:
                review_decision = "unresolved"
                terminal_class = "review_required"
            submission = _nonaccepted_submission(
                reviewed_at=reviewed_at,
                review_decision=review_decision,
            )
        result = service.review(decision=current_decision, submission=submission)
        _require(not validate_visual_review_receipt(result.review_receipt), "review_receipt_invalid")
        _require(
            not validate_visual_review_seal(
                result.review_seal,
                receipt=result.review_receipt,
                projection=result.canonical_projection,
            ),
            "review_seal_invalid",
        )
        if key == selected_key:
            _require(result.canonical_projection is not None, "accepted_projection_missing")
            _require(
                validate_reviewed_visual_projection(result.canonical_projection)[
                    "validator_status"
                ]
                == "passed",
                "accepted_projection_invalid",
            )
            accepted_projection = result.canonical_projection
        else:
            _require(result.canonical_projection is None, "nonaccepted_projection_present")
        results.append(
            {
                "candidate_ref": current_ref,
                "repeat_index": current_repeat,
                "terminal_class": terminal_class,
                "result": result,
            }
        )
    _require(accepted_projection is not None, "accepted_projection_missing")
    return {
        "results": results,
        "accepted_projection": accepted_projection,
        "canonical_cells_total": int(accepted_projection.get("cell_count") or 0),
    }


def build_candidate_from_literal_reference(
    *,
    table: dict[str, Any],
    table_id: str,
    sparse_currency_columns: bool,
) -> dict[str, Any]:
    entries = _dicts(table.get("entries"))
    _require(entries, "literal_reference_entries_missing")
    row_labels = list(dict.fromkeys(str(item.get("row_label_text") or "") for item in entries))
    header_paths = [
        tuple(str(part) for part in item.get("column_header_path") or [] if str(part))
        for item in entries
    ]
    leaf_headers = list(dict.fromkeys(path[-1] for path in header_paths if path))
    parent_headers = list(
        dict.fromkeys(part for path in header_paths for part in path[:-1])
    )
    _require(len(leaf_headers) == 2 and len(parent_headers) == 1, "literal_reference_header_shape_unsupported")
    by_key = {
        (str(item.get("row_label_text") or ""), str((item.get("column_header_path") or [""])[-1])): item
        for item in entries
    }
    _require(len(by_key) == len(row_labels) * len(leaf_headers), "literal_reference_grid_incomplete")

    value_columns_per_header = 2 if sparse_currency_columns else 1
    column_count = 1 + len(leaf_headers) * value_columns_per_header
    row_count = 2 + len(row_labels)
    cells: list[dict[str, Any]] = []

    def add(row: int, column: int, text: str, *, row_span: int = 1, column_span: int = 1, state: str | None = None) -> None:
        content_state = state or ("present" if text else "empty")
        cells.append(
            {
                "row_index": row,
                "column_index": column,
                "row_span": row_span,
                "column_span": column_span,
                "content_state": content_state,
                "source_text": text if content_state == "present" else "",
            }
        )

    add(0, 0, "", row_span=2)
    add(0, 1, parent_headers[0], column_span=column_count - 1)
    for ordinal, header in enumerate(leaf_headers):
        add(
            1,
            1 + ordinal * value_columns_per_header,
            header,
            column_span=value_columns_per_header,
        )
    for row_offset, row_label in enumerate(row_labels, start=2):
        add(row_offset, 0, row_label)
        for header_ordinal, header in enumerate(leaf_headers):
            entry = by_key[(row_label, header)]
            text = str(entry.get("visible_value_text") or "")
            state = str(entry.get("cell_state") or "")
            if state == "unreadable":
                symbol, value, value_state = "", "", "unreadable"
            else:
                match = re.fullmatch(r"\$\s*(.*)", text)
                symbol = "$" if match else ""
                value = match.group(1) if match else text
                value_state = "present" if value else "empty"
            column = 1 + header_ordinal * value_columns_per_header
            if sparse_currency_columns:
                add(row_offset, column, symbol)
                add(row_offset, column + 1, value, state=value_state)
            else:
                add(row_offset, column, text, state=value_state)
    output = {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": row_count,
        "column_count": column_count,
        "cells": cells,
    }
    errors = validate_table_output(output, table_id=table_id)
    _require(not errors, errors[0] if errors else "literal_candidate_invalid")
    return output


def _build_region_accounting_submission(
    *,
    decision: dict[str, Any],
    candidate: dict[str, Any],
    geometry: dict[str, Any],
    corrected_cells: set[tuple[int, int]],
) -> dict[str, Any]:
    row_edges = _float_list(geometry.get("row_edges"))
    column_edges = _float_list(geometry.get("column_edges"))
    _validate_edges(row_edges, int(candidate["row_count"]), "row")
    _validate_edges(column_edges, int(candidate["column_count"]), "column")
    bindings = []
    for cell in _dicts(candidate.get("cells")):
        row = int(cell["row_index"])
        column = int(cell["column_index"])
        row_end = row + int(cell["row_span"])
        column_end = column + int(cell["column_span"])
        text = str(cell.get("source_text") or "")
        key = (row, column)
        bindings.append(
            {
                "row_index": row,
                "column_index": column,
                "bbox_normalized": [
                    column_edges[column],
                    row_edges[row],
                    column_edges[column_end],
                    row_edges[row_end],
                ],
                "observed_content_state": cell["content_state"],
                "observed_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "review_action": "corrected" if key in corrected_cells else "confirmed",
            }
        )
    x0, x1 = column_edges[0], column_edges[-1]
    y0, y1 = row_edges[0], row_edges[-1]
    non_table_regions = [
        {"bbox_normalized": [0.0, 0.0, 1.0, y0], "reason_code": "outside_table_above"},
        {"bbox_normalized": [0.0, y0, x0, y1], "reason_code": "outside_table_left"},
        {"bbox_normalized": [x1, y0, 1.0, y1], "reason_code": "outside_table_right"},
        {"bbox_normalized": [0.0, y1, 1.0, 1.0], "reason_code": "outside_table_below"},
    ]
    lineage = _object(decision.get("source_lineage"))
    return {
        "schema_version": VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION,
        "crop_sha256": lineage["crop_sha256"],
        "coordinate_space": "normalized_0_1_top_left",
        "image_width": lineage["image_width"],
        "image_height": lineage["image_height"],
        "cell_bindings": bindings,
        "non_table_regions": non_table_regions,
        "all_canonical_cells_accounted": True,
        "source_region_inventory_complete": True,
    }


def _persist_and_probe_lifecycle(
    *, root: Path, review_results: list[dict[str, Any]]
) -> dict[str, Any]:
    run_id = "goal5visualrun_" + sha256_json(
        [item["result"].review_receipt["receipt_hash"] for item in review_results]
    )[:24]
    context = ArtifactAccessContext(
        user_id="goal5-user-delegator",
        case_id="customer-case-alpha-goal5-review",
        chat_id="customer-case-alpha-goal5-review",
        workspace_model_id="broker_reports_goal5_proof",
        normalization_run_id=run_id,
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(mode="customer_approved_test", explicit=True)

    def put_all(store: Any, *, selected_only: bool) -> int:
        count = 0
        for item in review_results:
            if selected_only and item["terminal_class"] != "usable":
                continue
            result = item["result"]
            payloads = [
                ("broker_reports_visual_table_review_receipt_v1", result.review_receipt),
                ("broker_reports_visual_table_review_seal_v1", result.review_seal),
            ]
            if result.canonical_projection is not None:
                payloads.append(
                    ("broker_reports_normalized_table_projection_v0", result.canonical_projection)
                )
            for artifact_type, payload in payloads:
                stored = store.put_record(
                    ArtifactRecord(
                        artifact_id=new_artifact_id(),
                        artifact_type=artifact_type,
                        case_id=context.case_id,
                        chat_id=context.chat_id,
                        user_id=context.user_id,
                        workspace_model_id=context.workspace_model_id,
                        normalization_run_id=context.normalization_run_id,
                        document_id=None,
                        source_file_ref=None,
                        visibility="private_case",
                        storage_backend="project_artifact_payload",
                        retention_policy=retention,
                        access_policy={"scope": "case_private", "requires_user_id": True},
                        validation_status="validated",
                        lifecycle_status="private_ready",
                        payload=payload,
                        safe_metadata={
                            "terminal_class": item["terminal_class"],
                            "reviewer_type": "delegated_agent_reviewed",
                        },
                    )
                )
                _require(store.read_payload(stored) == payload, "review_store_readback_failed")
                count += 1
        return count

    persistent = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "review-store" / "artifacts.sqlite3",
            payload_root=root / "review-store" / "payloads",
        )
    ).create()
    persisted = put_all(persistent, selected_only=False)
    persistent_records = persistent.list_by_run(run_id)
    _require(
        len(persistent_records) == persisted
        and all(item.lifecycle_status == "private_ready" for item in persistent_records),
        "review_store_lifecycle_invalid",
    )

    probe = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "cleanup-probe" / "artifacts.sqlite3",
            payload_root=root / "cleanup-probe" / "payloads",
        )
    ).create()
    probe_total = put_all(probe, selected_only=True)
    purge = probe.purge_run(context)
    probe_records = probe.list_by_run(run_id)
    _require(
        len(probe_records) == probe_total
        and all(item.lifecycle_status == "purged" for item in probe_records)
        and all(item.storage_backend == "none_tombstone" for item in probe_records)
        and not list((root / "cleanup-probe" / "payloads").glob("*.json")),
        "review_cleanup_probe_failed",
    )
    return {
        "private_records_persisted": persisted,
        "private_ready_records": persisted,
        "retention_mode": retention.mode,
        "cleanup_probe_records": probe_total,
        "cleanup_probe_purged": len(purge.artifact_ids),
        "cleanup_probe_payloads_remaining": 0,
        "cleanup_replay_safe": True,
    }


def _nonaccepted_submission(*, reviewed_at: str, review_decision: str) -> dict[str, Any]:
    return {
        "schema_version": VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
        "reviewed_at": reviewed_at,
        "review_decision": review_decision,
        "decision_reason_codes": [f"review_{review_decision}"],
        "selected_proposal_provider": None,
        "canonical_candidate": None,
        "correction_acknowledgements": [],
        "region_cell_accounting": None,
        "attestations": _attestations(accepted=False),
    }


def _attestations(*, accepted: bool) -> dict[str, bool]:
    return {
        "exact_bounded_crop_reviewed": True,
        "every_canonical_cell_reviewed": accepted,
        "source_regions_accounted": accepted,
        "provider_output_not_reference_truth": True,
        "provider_consensus_not_acceptance_authority": True,
        "local_ocr_evidence_used": False,
    }


def _audit_gate1_store_accounting(database: Path) -> dict[str, Any]:
    _require(database.is_file(), "gate1_store_missing")
    required_types = {
        "document_inventory_v0",
        "document_usage_classification_v0",
        "broker_reports_gate1_document_memory_manifest_v1",
        "domain_context_packet_v0",
    }
    payloads: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT artifact_type, payload_inline_json, payload_ref "
            "FROM artifact_records WHERE artifact_type IN (?,?,?,?)",
            tuple(sorted(required_types)),
        ).fetchall()
    _require(len(rows) == len(required_types), "gate1_store_accounting_artifacts_invalid")
    payload_root = database.parent / "payloads"
    for row in rows:
        artifact_type = str(row["artifact_type"])
        if row["payload_inline_json"] is not None:
            payload = json.loads(str(row["payload_inline_json"]))
        else:
            payload_path = _safe_join(payload_root, str(row["payload_ref"] or ""))
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        _require(isinstance(payload, dict), "gate1_store_accounting_payload_invalid")
        payloads[artifact_type] = payload

    inventory = payloads["document_inventory_v0"]
    memory = payloads["broker_reports_gate1_document_memory_manifest_v1"]
    usage = payloads["document_usage_classification_v0"]
    dcp = payloads["domain_context_packet_v0"]
    formats = Counter(
        str(item.get("container_format") or "unknown")
        for item in _dicts(inventory.get("documents"))
    )
    expected_formats = {"csv": 2, "pdf": 50, "zip": 24, "html_text": 4, "xml": 24}
    _require(dict(formats) == expected_formats, "actual_format_accounting_invalid")
    next_refs = _object(dcp.get("next_stage_refs"))
    archive_refs = set(str(item) for item in next_refs.get("archive_lineage_refs") or [])
    visual_refs = set(str(item) for item in next_refs.get("visual_review_refs") or [])
    source_ready_refs = set(str(item) for item in next_refs.get("source_fact_ready_refs") or [])
    memory_archive_refs = {
        str(item.get("source_file_ref") or "")
        for item in _dicts(memory.get("documents"))
        if item.get("gate2_memory_status") == "lineage_only"
    }
    memory_visual_refs = {
        str(item.get("source_file_ref") or "")
        for item in _dicts(memory.get("documents"))
        if _visual_review_only_memory(item)
    }
    usage_ready_refs = {
        str(item.get("document_ref") or "")
        for item in _dicts(usage.get("entries"))
        if _object(item.get("readiness_by_stage")).get("source_fact_extraction")
        in {"ready", "ready_with_issues"}
    }
    _require(
        archive_refs == memory_archive_refs
        and visual_refs == memory_visual_refs
        and source_ready_refs == usage_ready_refs
        and not source_ready_refs & (archive_refs | visual_refs)
        and len(archive_refs) == 24
        and len(visual_refs) == 5,
        "dcp_terminal_route_accounting_invalid",
    )
    _require(
        _object(memory.get("summary")).get("logical_documents_total") == 80,
        "document_memory_logical_count_invalid",
    )
    return {
        "format_counts": expected_formats,
        "archive_lineage_refs": len(archive_refs),
        "visual_review_refs": len(visual_refs),
        "source_fact_ready_refs": len(source_ready_refs),
    }


def _visual_review_only_memory(value: dict[str, Any]) -> bool:
    readiness = _object(_object(value.get("source_scope")).get("scope_readiness"))
    return readiness.get("visual_scope") == "ready" and not any(
        (
            readiness.get("text_scope") == "ready",
            readiness.get("neutral_structure_scope") == "ready",
            readiness.get("canonical_table_scope")
            == "ready_validated_projection_only",
        )
    )


def _artifactstore_signature(database: Path) -> dict[str, Any]:
    _require(database.is_file(), "gate1_store_missing")
    with sqlite3.connect(database) as connection:
        records_total = int(
            connection.execute("SELECT COUNT(*) FROM artifact_records").fetchone()[0]
        )
    payload_root = database.parent / "payloads"
    payload_files = sorted(path for path in payload_root.rglob("*") if path.is_file())
    material = [hashlib.sha256(database.read_bytes()).hexdigest()]
    payload_bytes_total = 0
    for path in payload_files:
        raw = path.read_bytes()
        payload_bytes_total += len(raw)
        material.extend(
            [
                path.relative_to(payload_root).as_posix(),
                str(len(raw)),
                hashlib.sha256(raw).hexdigest(),
            ]
        )
    return {
        "records_total": records_total,
        "payload_files_total": len(payload_files),
        "payload_bytes_total": payload_bytes_total,
        "signature": hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest(),
    }


def _validate_file_seal(
    *,
    seal: dict[str, Any],
    content_path: Path,
    content_bytes: bytes,
    digest_key: str,
    size_key: str,
    filename_key: str,
) -> None:
    unhashed = copy.deepcopy(seal)
    seal_hash = unhashed.pop("seal_sha256", None)
    _require(seal_hash == sha256_json(unhashed), "file_seal_hash_invalid")
    sealed_bytes = (
        content_bytes[:-1]
        if content_bytes.endswith(b"\n")
        and seal.get(size_key) == len(content_bytes) - 1
        else content_bytes
    )
    status_valid = "status" not in seal or seal.get("status") == "completed"
    _require(
        seal.get(digest_key) == hashlib.sha256(sealed_bytes).hexdigest()
        and seal.get(size_key) == len(sealed_bytes)
        and seal.get(filename_key) == content_path.name
        and status_valid,
        "file_seal_identity_invalid",
    )


def _validate_embedded_hash(value: dict[str, Any], key: str, code: str) -> None:
    unhashed = copy.deepcopy(value)
    actual = unhashed.pop(key, None)
    _require(actual == sha256_json(unhashed), code)


def _validate_edges(values: list[float], dimensions: int, axis: str) -> None:
    _require(len(values) == dimensions + 1, f"visual_geometry_{axis}_count_invalid")
    _require(
        all(0.0 <= value <= 1.0 for value in values)
        and all(left < right for left, right in zip(values, values[1:])),
        f"visual_geometry_{axis}_bounds_invalid",
    )


def _float_list(value: Any) -> list[float]:
    _require(isinstance(value, list), "visual_geometry_edges_invalid")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise Goal5ProofError("visual_geometry_edges_invalid") from exc


def _png_dimensions(raw: bytes) -> tuple[int, int]:
    _require(raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24, "crop_png_invalid")
    return struct.unpack(">II", raw[16:24])


def _safe_join(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    _require(path != root and root in path.parents and path.is_file(), "private_asset_path_invalid")
    return path


def _sensitive_strings(
    *,
    decisions: dict[tuple[str, int], dict[str, Any]],
    literal_tables: dict[str, dict[str, Any]],
    crops: dict[str, dict[str, Any]],
) -> set[str]:
    strings = set(crops)
    for item in crops.values():
        strings.add(str(item.get("asset") or ""))
    for decision in decisions.values():
        lineage = _object(decision.get("source_lineage"))
        strings.update(
            {
                str(lineage.get("source_ref") or ""),
                str(lineage.get("crop_id") or ""),
            }
        )
    for table in literal_tables.values():
        for entry in _dicts(table.get("entries")):
            strings.add(str(entry.get("row_label_text") or ""))
            strings.add(str(entry.get("visible_value_text") or ""))
            strings.update(str(item) for item in entry.get("column_header_path") or [])
    return {item for item in strings if len(item) >= 4}


def _assert_safe_report(*, report: dict[str, Any], sealed: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    _require(not re.search(r"[A-Za-z]:[\\/]", serialized), "safe_report_path_leak")
    _require(".png" not in serialized.lower(), "safe_report_filename_leak")
    for value in sealed["sensitive_strings"]:
        _require(value not in serialized, "safe_report_customer_value_leak")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "json_object_required")
    return value


def _read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    _require(isinstance(value, dict), "json_object_required")
    return value, raw


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Goal5ProofError(code)


if __name__ == "__main__":
    main()
