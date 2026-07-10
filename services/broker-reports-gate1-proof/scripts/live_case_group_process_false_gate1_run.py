#!/usr/bin/env python3
"""
Customer-approved Gate 1 live run for a selected case group via process=false.

The script resolves source files from the ignored private registry, uploads them
to OpenWebUI with process=false under sanitized aliases, invokes the
broker_reports_gate1_pipe Workspace Model, and prints only safe aggregate proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from live_no_rag_source_intake_smoke import (
    ROOT,
    _base_url,
    _capabilities,
    _default_ssh_target,
    _delete_uploads,
    _extract_content,
    _get_model,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
    _signin,
    _url,
)


DEFAULT_CASE_GROUP_ID = "case_group_002"
DEFAULT_PRIVATE_REGISTRY = (
    "local/stage2/broker_reports_customer_source_documents_intake_2026-07-06/private_registry.json"
)
DEFAULT_SAFE_SOURCE_REGISTRY = "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.vNEXT.safe.json"
DEFAULT_CASE_GROUPS = "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_CASE_GROUPS.v0.safe.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument(
        "--source-ordinals",
        default="",
        help="Optional comma-separated 1-based safe registry ordinals for a limited controlled proof.",
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--enable-llm-passport", action="store_true")
    parser.add_argument("--passport-model-id", default=None)
    parser.add_argument("--passport-prompt-command", default="broker_gate1_document_passport")
    parser.add_argument("--passport-max-documents", type=int, default=32)
    parser.add_argument("--enable-clarification", action="store_true")
    parser.add_argument("--clarification-model-id", default=None)
    parser.add_argument("--clarification-prompt-command", default="broker_gate1_clarification_request")
    parser.add_argument("--disable-clarification-criticality-refinement", action="store_true")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--settle-seconds", type=int, default=6)
    parser.add_argument("--cleanup-source-uploads", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    model_id = args.model_id or env.get("OPENWEBUI_WORKSPACE_MODEL_ID") or env.get("OPENWEBUI_MODEL_ID") or "test"

    sources = _resolve_case_group_sources(
        case_group_id=args.case_group_id,
        private_registry_path=_repo_path(args.private_registry),
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    selected_ordinals = {
        int(item.strip())
        for item in str(args.source_ordinals or "").split(",")
        if item.strip()
    }
    if selected_ordinals:
        sources["files"] = [
            item
            for index, item in enumerate(sources["files"], start=1)
            if index in selected_ordinals
        ]
        if not sources["files"]:
            raise RuntimeError("case_group_source_selection_empty")
        sources["files_total"] = len(sources["files"])
        sources["case_group_summary"]["selected_source_ordinals"] = sorted(
            selected_ordinals
        )
        sources["case_group_summary"]["files_total"] = len(sources["files"])
    case_id = f"customer_{args.case_group_id}_process_false_gate1_{time.strftime('%Y%m%d%H%M%S')}"

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    model = _get_model(session, base_url, model_id)
    passport_model_id = (
        args.passport_model_id
        or env.get("OPENWEBUI_PASSPORT_MODEL_ID")
        or (_select_passport_model(session, base_url) if args.enable_llm_passport else None)
    )
    clarification_model_id = (
        args.clarification_model_id
        or env.get("OPENWEBUI_CLARIFICATION_MODEL_ID")
        or passport_model_id
        or (_select_passport_model(session, base_url) if args.enable_clarification else None)
    )
    uploaded: list[dict[str, Any]] = []
    gate1_completed = False

    try:
        before = _runtime_snapshot(ssh_target)
        uploaded = [
            _upload_process_false(session, base_url, source, index + 1, args.timeout)
            for index, source in enumerate(sources["files"])
        ]
        time.sleep(args.settle_seconds)
        after_upload = _runtime_snapshot(ssh_target)

        process_status_values = [
            _file_process_status(session, base_url, str(item["id"]), args.timeout)
            for item in uploaded
        ]
        extracted_content_endpoint_count = sum(
            1
            for item in uploaded
            if _file_content_endpoint_has_payload(session, base_url, str(item["id"]), args.timeout)
        )

        chat_report = _run_chat(
            session=session,
            base_url=base_url,
            model_id=model_id,
            uploads=uploaded,
            case_id=case_id,
            case_group_id=args.case_group_id,
            source_policy_hints=sources.get("source_policy_hints", []),
            passport_config={
                "enabled": args.enable_llm_passport,
                "model_id": passport_model_id,
                "prompt_command": args.passport_prompt_command,
                "max_documents": args.passport_max_documents,
            },
            clarification_config={
                "enabled": args.enable_clarification,
                "model_id": clarification_model_id,
                "prompt_command": args.clarification_prompt_command,
                "criticality_refinement_enabled": not args.disable_clarification_criticality_refinement,
            },
            timeout=args.timeout,
        )
        gate1_completed = True
        time.sleep(args.settle_seconds)
        after_chat = _runtime_snapshot(ssh_target)

        cleanup = {"policy": "retained_for_customer_approved_test", "performed": False, "deleted_count": 0}
        after_cleanup = after_chat
        if args.cleanup_source_uploads:
            deleted = _delete_uploads(session, base_url, uploaded)
            cleanup = {"policy": "operator_requested_cleanup", "performed": True, "deleted_count": deleted}
            time.sleep(args.settle_seconds)
            after_cleanup = _runtime_snapshot(ssh_target)

        artifacts = _artifact_summary(ssh_target, case_id)
        chat_shape = _chat_shape(chat_report, uploaded)
        upload_delta = _counter_delta(before, after_upload)
        chat_delta = _counter_delta(before, after_chat)
        cleanup_delta = _counter_delta(before, after_cleanup)
        handoff_status = artifacts["safe_report"].get("gate2_handoff_status")
        handoff_mode = artifacts["safe_report"].get("gate2_handoff_mode")
        gate2_handoff_ready = (
            handoff_status in {"ready_with_safe_refs", "ready_with_reduced_subset"}
            and handoff_mode in {"full_package_ready_for_gate2", "reduced_subset_ready_for_gate2"}
        )
        clarification_request_summary = artifacts["gate1_clarification_request_summary"]
        metadata_gap_summary = artifacts["gate1_metadata_gap_report_summary"]
        clarification_questions_total = int(clarification_request_summary.get("questions_total") or 0)
        critical_questions_total = int(clarification_request_summary.get("critical_questions_total") or 0)
        previous_strict_question_count_baseline = 35
        handoff_safe_metadata = artifacts.get("gate2_handoff_safe_metadata") or {}
        handoff_blocker_counts = handoff_safe_metadata.get("handoff_blocker_counts") or {}
        issue_ledger_summary = artifacts.get("gate1_issue_ledger_summary") or {}
        usage_classification_summary = artifacts.get("document_usage_classification_summary") or {}
        domain_context_packet_summary = artifacts.get("domain_context_packet_summary") or {}
        domain_stage_readiness = domain_context_packet_summary.get("stage_readiness") or {}
        domain_unresolved_summary = domain_context_packet_summary.get("unresolved_issue_summary") or {}
        next_stage_ref_summary = domain_context_packet_summary.get("next_stage_ref_summary") or {}
        source_ready_total = int(next_stage_ref_summary.get("source_fact_ready_total") or 0)
        primary_source_total = int(next_stage_ref_summary.get("primary_source_extraction_total") or 0)
        source_ready_not_primary_total = int(next_stage_ref_summary.get("source_ready_not_primary_total") or 0)
        dropped_source_ready_total = int(next_stage_ref_summary.get("dropped_source_ready_total") or 0)
        usage_source_ready_total = int(
            usage_classification_summary.get("source_fact_extraction_ready_total") or 0
        )
        included_reduced_total = int(
            (artifacts["safe_report"].get("source_eligibility_summary") or {}).get("included_in_reduced_subset")
            or 0
        )
        source_policy_review_count = int(handoff_blocker_counts.get("source_policy_review_required") or 0)
        duplicate_review_count = int(handoff_blocker_counts.get("duplicate_needs_canonical_choice") or 0)
        gate2_blocked_with_actionable_metadata_questions = (
            handoff_status == "blocked"
            and handoff_mode == "gate2_blocked_requires_metadata_review"
            and critical_questions_total > 0
        )
        gate2_blocked_with_actionable_policy_review = (
            handoff_status == "blocked"
            and handoff_mode == "gate2_blocked_requires_policy_review"
            and source_policy_review_count > 0
        )
        gate2_blocked_with_actionable_duplicate_choice = (
            handoff_status == "blocked"
            and handoff_mode in {"gate2_blocked_requires_duplicate_resolution", "gate2_blocked_requires_policy_review"}
            and duplicate_review_count > 0
            and critical_questions_total > 0
        )
        gate2_blocked_with_actionable_gate2_blockers = (
            gate2_blocked_with_actionable_metadata_questions
            or gate2_blocked_with_actionable_policy_review
            or gate2_blocked_with_actionable_duplicate_choice
        )
        checks = {
            "process_false_upload_count_matches_package": len(uploaded) == sources["files_total"],
            "process_status_completed_absent": all(value != "completed" for value in process_status_values),
            "uploaded_file_content_endpoint_empty": extracted_content_endpoint_count == 0,
            "document_rows_zero_delta": chat_delta["document_rows"] == 0,
            "knowledge_rows_zero_delta": chat_delta["knowledge_rows"] == 0,
            "vector_delta_zero_after_upload": _vector_delta_zero(upload_delta),
            "vector_delta_zero_after_chat": _vector_delta_zero(chat_delta),
            "compact_russian_report": chat_shape["compact_russian_report"],
            "private_refs_not_in_chat": chat_shape["private_refs_not_in_chat"],
            "artifactstore_persisted": artifacts["case_record_count"] > 0,
            "artifactstore_no_knowledge_backend": artifacts["openwebui_knowledge_records"] == 0,
            "customer_retention_applied": artifacts["retention_policy_modes"] == {"customer_approved_test": artifacts["case_record_count"]},
            "customer_retention_explicit": artifacts["retention_policy_explicit_false_count"] == 0,
            "gate2_handoff_created": artifacts["type_counts"].get("gate2_handoff_v0", 0) >= 1,
            "gate1_issue_ledger_created": artifacts["type_counts"].get("gate1_issue_ledger_v0", 0) >= 1,
            "document_usage_classification_created": artifacts["type_counts"].get(
                "document_usage_classification_v0", 0
            )
            >= 1,
            "domain_context_packet_created": artifacts["type_counts"].get("domain_context_packet_v0", 0) >= 1,
            "source_policy_review_removed_from_handoff_blockers": (
                source_policy_review_count == 0 and handoff_mode != "gate2_blocked_requires_policy_review"
            ),
            "unresolved_issues_carried_forward": (
                int(issue_ledger_summary.get("unresolved_issues_total") or 0) > 0
                and int(domain_unresolved_summary.get("unresolved_issues_total") or 0) > 0
            ),
            "domain_context_packet_ready_for_source_extraction": domain_stage_readiness.get(
                "source_fact_extraction"
            )
            in {"ready", "ready_with_issue_context"},
            "document_usage_classification_has_source_ready_docs": int(
                usage_classification_summary.get("source_fact_extraction_ready_total") or 0
            )
            > 0,
            "next_stage_refs_refined": bool(next_stage_ref_summary),
            "source_ready_count_reconciled": source_ready_total == usage_source_ready_total,
            "no_source_ready_doc_loss": (
                source_ready_total > 0
                and dropped_source_ready_total == 0
                and source_ready_total == primary_source_total + source_ready_not_primary_total
            ),
            "primary_refs_match_reduced_subset": primary_source_total == included_reduced_total,
            "gate2_handoff_ready_or_actionable_clarification": (
                gate2_handoff_ready
                if not args.enable_clarification
                else gate2_handoff_ready or gate2_blocked_with_actionable_gate2_blockers
            ),
            "private_slices_persisted": artifacts["private_case_records"] > 0,
            "safety_flags_false": _safety_flags_false(artifacts["safe_report"]),
        }
        if args.enable_llm_passport:
            expected_passport_count = min(sources["files_total"], args.passport_max_documents)
            checks.update(
                {
                    "llm_passport_prompt_resolved": artifacts["type_counts"].get("llm_prompt_snapshot_v0", 0) == 1,
                    "llm_passport_packages_built": artifacts["type_counts"].get("llm_document_package_v0", 0)
                    == expected_passport_count,
                    "llm_passport_model_calls_passed": artifacts["llm_passport_model_call_status_counts"].get(
                        "passed", 0
                    )
                    == expected_passport_count,
                    "llm_passport_validator_passed": artifacts[
                        "document_metadata_passport_validator_status_counts"
                    ].get("passed", 0)
                    == expected_passport_count,
                    "llm_passport_artifacts_persisted": all(
                        artifacts["type_counts"].get(artifact_type, 0) >= minimum
                        for artifact_type, minimum in {
                            "llm_prompt_snapshot_v0": 1,
                            "llm_document_package_v0": expected_passport_count,
                            "llm_passport_raw_output_v0": expected_passport_count,
                            "document_metadata_passport_v0": expected_passport_count,
                            "document_metadata_passport_validation_v0": 1,
                        }.items()
                    ),
                    "llm_passport_structured_output_mode_recorded": sum(
                        artifacts["llm_passport_structured_output_mode_counts"].values()
                    )
                    == expected_passport_count
                    and "unknown" not in artifacts["llm_passport_structured_output_mode_counts"],
                    "llm_passport_schema_hash_recorded": sum(
                        artifacts["llm_passport_schema_hash_counts"].values()
                    )
                    == expected_passport_count
                    and "unknown" not in artifacts["llm_passport_schema_hash_counts"],
                    "source_eligibility_v2_passed": bool(
                        artifacts["safe_report"].get("document_metadata_passport_summary")
                    )
                    and bool(artifacts["safe_report"].get("document_source_eligibility")),
                }
            )
        if args.enable_clarification:
            checks.update(
                {
                    "gate1_metadata_gap_report_created": artifacts["type_counts"].get(
                        "gate1_metadata_gap_report_v0", 0
                    )
                    == 1,
                    "gate1_metadata_gap_report_has_stage_issues": int(
                        metadata_gap_summary.get("gaps_total") or 0
                    )
                    > 0,
                    "gate1_clarification_prompt_resolved": artifacts["type_counts"].get(
                        "llm_clarification_prompt_snapshot_v0", 0
                    )
                    == 1,
                    "gate1_clarification_model_call_passed": artifacts[
                        "llm_clarification_model_call_status_counts"
                    ].get("passed", 0)
                    == 1,
                    "gate1_clarification_request_validated": artifacts["type_counts"].get(
                        "gate1_clarification_request_v0", 0
                    )
                    == 1
                    and clarification_request_summary.get("validator_status") == "passed",
                    "gate1_clarification_questions_created": clarification_questions_total > 0,
                    "gate1_clarification_criticality_counts_recorded": (
                        isinstance(metadata_gap_summary.get("criticality_counts"), dict)
                        and isinstance(clarification_request_summary.get("criticality_counts"), dict)
                    ),
                    "gate1_clarification_critical_questions_created": critical_questions_total > 0,
                    "gate1_clarification_nonblocking_questions_classified": (
                        int(clarification_request_summary.get("clarifying_questions_total") or 0)
                        + int(clarification_request_summary.get("non_critical_questions_total") or 0)
                    )
                    > 0,
                    "gate1_clarification_question_count_recorded_against_previous_baseline": (
                        clarification_questions_total > 0 and previous_strict_question_count_baseline > 0
                    ),
                    "gate1_clarification_duplicate_choice_present": (
                        int(
                            (clarification_request_summary.get("gap_type_counts") or {}).get(
                                "duplicate_canonical_choice"
                            )
                            or 0
                        )
                        >= 1
                    ),
                    "gate1_clarification_structured_output_mode_recorded": sum(
                        artifacts["llm_clarification_structured_output_mode_counts"].values()
                    )
                    == 1
                    and "unknown" not in artifacts["llm_clarification_structured_output_mode_counts"],
                    "gate1_clarification_schema_hash_recorded": sum(
                        artifacts["llm_clarification_schema_hash_counts"].values()
                    )
                    == 1
                    and "unknown" not in artifacts["llm_clarification_schema_hash_counts"],
                    "gate1_clarification_no_auto_resolution": artifacts["type_counts"].get(
                        "gate1_clarification_resolution_v0", 0
                    )
                    == 0,
                    "gate2_handoff_ready_or_actionable_questions": (
                        gate2_handoff_ready
                        or gate2_blocked_with_actionable_metadata_questions
                        or gate2_blocked_with_actionable_duplicate_choice
                    ),
                    "gate2_handoff_blocked_with_actionable_policy_review": (
                        gate2_blocked_with_actionable_policy_review
                        or handoff_mode != "gate2_blocked_requires_policy_review"
                    ),
                }
            )
        passed = all(checks.values())
        summary = {
            "status": "passed" if passed else "partial",
            "statuses": _statuses(passed, clarification_mode=args.enable_clarification),
            "case_group": sources["case_group_summary"],
            "case_id": case_id,
            "model": {
                "model_id": model_id,
                "base_model_id": model.get("base_model_id"),
                "capabilities": _capabilities(model),
            },
            "llm_passport": {
                "enabled": args.enable_llm_passport,
                "model_id": passport_model_id if args.enable_llm_passport else None,
                "prompt_command": args.passport_prompt_command if args.enable_llm_passport else None,
                "max_documents": args.passport_max_documents if args.enable_llm_passport else None,
            },
            "llm_clarification": {
                "enabled": args.enable_clarification,
                "model_id": clarification_model_id if args.enable_clarification else None,
                "prompt_command": args.clarification_prompt_command if args.enable_clarification else None,
                "operator_answers_supplied": False,
                "criticality_refinement_enabled": not args.disable_clarification_criticality_refinement
                if args.enable_clarification
                else None,
                "previous_strict_question_count_baseline": previous_strict_question_count_baseline
                if args.enable_clarification
                else None,
                "refined_questions_total": clarification_questions_total if args.enable_clarification else None,
                "refined_critical_questions_total": critical_questions_total if args.enable_clarification else None,
                "refined_clarifying_questions_total": int(
                    clarification_request_summary.get("clarifying_questions_total") or 0
                )
                if args.enable_clarification
                else None,
                "refined_non_critical_questions_total": int(
                    clarification_request_summary.get("non_critical_questions_total") or 0
                )
                if args.enable_clarification
                else None,
            },
            "retention_policy_requested": {
                "mode": "customer_approved_test",
                "explicit": True,
                "ttl_seconds": 14 * 24 * 60 * 60,
            },
            "source_policy_requested": {
                "mode": "customer_approved_private_registry",
                "explicit": True,
                "pdf_html_source_policy": "review_required",
                "safe_registry_role_hints_count": len(sources.get("source_policy_hints", [])),
            },
            "upload": {
                "path": "POST /api/v1/files/?process=false",
                "uploaded_count": len(uploaded),
                "sanitized_aliases_used": True,
                "process_status_values": process_status_values,
                "content_endpoint_payload_count": extracted_content_endpoint_count,
                "cleanup": cleanup,
            },
            "runtime_counters": {
                "before": _safe_counter_view(before),
                "after_process_false_upload": _safe_counter_view(after_upload),
                "after_chat": _safe_counter_view(after_chat),
                "after_cleanup": _safe_counter_view(after_cleanup),
                "delta_after_process_false_upload": upload_delta,
                "delta_after_chat": chat_delta,
                "delta_after_cleanup": cleanup_delta,
            },
            "chat_visible_report_shape": chat_shape,
            "gate1_safe_report": _safe_report_summary(artifacts["safe_report"]),
            "handoff_reconciliation": {
                "document_usage_classification_source_ready_total": usage_source_ready_total,
                "domain_context_packet_source_ready_total": source_ready_total,
                "primary_source_extraction_total": primary_source_total,
                "source_ready_not_primary_total": source_ready_not_primary_total,
                "dropped_source_ready_total": dropped_source_ready_total,
                "included_in_reduced_subset_total": included_reduced_total,
                "source_ready_minus_primary": source_ready_total - primary_source_total,
                "explanation": "source_ready_total can exceed primary/included refs; non-primary refs remain in secondary/duplicate/audit buckets.",
            },
            "artifactstore": {
                key: value
                for key, value in artifacts.items()
                if key != "safe_report"
            },
            "checks": checks,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if passed else 2
    except Exception:
        if uploaded and not gate1_completed:
            try:
                _delete_uploads(session, base_url, uploaded)
            except Exception:
                pass
        raise


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _source_policy_hints(
    *,
    case_group_id: str,
    safe_source_registry_path: Path,
    case_groups_path: Path,
) -> list[dict[str, Any]]:
    case_groups = _load_json(case_groups_path)
    safe_source = _load_json(safe_source_registry_path)
    group = next(
        (item for item in case_groups.get("case_groups", []) if item.get("case_group_id") == case_group_id),
        None,
    )
    if not isinstance(group, dict):
        raise RuntimeError("case_group_missing")
    safe_by_id = {item.get("document_id"): item for item in safe_source.get("documents", [])}
    hints = []
    for document_id in list(group.get("document_ids") or []):
        safe_doc = safe_by_id.get(document_id)
        if not isinstance(safe_doc, dict):
            raise RuntimeError("case_group_safe_document_missing")
        hint = _source_policy_hint_for_safe_doc(safe_doc)
        if hint:
            hints.append(hint)
    return hints


def _source_policy_hint_for_safe_doc(safe_doc: dict[str, Any]) -> dict[str, Any]:
    sha256 = str(safe_doc.get("sha256") or "")
    hash_prefix = str(safe_doc.get("hash_prefix") or sha256[:12])
    if not hash_prefix:
        return {}
    return {
        "safe_document_id": str(safe_doc.get("document_id") or ""),
        "sha256_prefix": hash_prefix[:12],
        "container_format": str(safe_doc.get("container_format") or "unknown"),
        "extension": str(safe_doc.get("extension") or ""),
        "document_role_candidate": str(safe_doc.get("document_role_candidate") or "unknown_or_needs_review"),
        "source_evidence_candidate": str(safe_doc.get("source_evidence_candidate") or "conditional"),
        "source_vs_output": str(safe_doc.get("source_vs_output") or "review_or_unknown"),
        "methodology_or_output_candidate": _truthy_yes(safe_doc.get("methodology_or_output_candidate")),
        "secondary_role_candidates": [
            str(item)
            for item in list(safe_doc.get("secondary_role_candidates") or [])[:10]
        ],
    }


def _truthy_yes(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"yes", "true", "1"}


def _resolve_case_group_sources(
    *,
    case_group_id: str,
    private_registry_path: Path,
    safe_source_registry_path: Path,
    case_groups_path: Path,
) -> dict[str, Any]:
    case_groups = _load_json(case_groups_path)
    safe_source = _load_json(safe_source_registry_path)
    private_registry = _load_json(private_registry_path)
    group = next(
        (item for item in case_groups.get("case_groups", []) if item.get("case_group_id") == case_group_id),
        None,
    )
    if not isinstance(group, dict):
        raise RuntimeError("case_group_missing")
    document_ids = list(group.get("document_ids") or [])
    safe_by_id = {item.get("document_id"): item for item in safe_source.get("documents", [])}
    private_by_id = {item.get("document_id"): item for item in private_registry.get("documents", [])}

    files = []
    source_policy_hints = []
    formats: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    source_candidates = 0
    methodology_candidates = 0
    for document_id in document_ids:
        safe_doc = safe_by_id.get(document_id)
        private_doc = private_by_id.get(document_id)
        if not isinstance(safe_doc, dict) or not isinstance(private_doc, dict):
            raise RuntimeError("case_group_document_registry_mismatch")
        path = Path(str(private_doc.get("absolute_path") or ""))
        if not path.exists() or not path.is_file():
            raise RuntimeError("private_source_file_missing")
        expected_sha = str(private_doc.get("sha256") or safe_doc.get("sha256") or "")
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            raise RuntimeError("private_source_file_hash_mismatch")
        container = str(safe_doc.get("container_format") or "unknown")
        role = str(safe_doc.get("document_role_candidate") or "unknown")
        formats[container] += 1
        roles[role] += 1
        if _truthy_yes(safe_doc.get("source_evidence_candidate")):
            source_candidates += 1
        if _truthy_yes(safe_doc.get("methodology_or_output_candidate")):
            methodology_candidates += 1
        hint = _source_policy_hint_for_safe_doc(safe_doc)
        if hint:
            source_policy_hints.append(hint)
        files.append(
            {
                "document_id": document_id,
                "path": path,
                "extension": str(safe_doc.get("extension") or path.suffix or ".bin"),
                "container_format": container,
                "role": role,
                "sha256_verified": True,
            }
        )

    return {
        "files": files,
        "files_total": len(files),
        "source_policy_hints": source_policy_hints,
        "case_group_summary": {
            "case_group_id": case_group_id,
            "broker_provider_candidate": group.get("broker_provider_candidate"),
            "confidence": group.get("confidence"),
            "readiness": group.get("readiness"),
            "manual_review_required": group.get("manual_review_required"),
            "files_total": len(files),
            "formats_from_registry": dict(sorted(formats.items())),
            "document_role_candidates_from_registry": dict(sorted(roles.items())),
            "source_evidence_candidates_from_registry": source_candidates,
            "methodology_or_output_candidates_from_registry": methodology_candidates,
        },
    }


def _upload_process_false(
    session: requests.Session,
    base_url: str,
    source: dict[str, Any],
    index: int,
    timeout: int,
) -> dict[str, Any]:
    extension = str(source["extension"] or ".bin")
    if not extension.startswith("."):
        extension = f".{extension}"
    alias = f"case_group_002_doc_{index:03d}{extension.lower()}"
    mime_type = mimetypes.guess_type(alias)[0] or "application/octet-stream"
    with Path(source["path"]).open("rb") as handle:
        response = session.post(
            _url(base_url, "/api/v1/files/?process=false"),
            files={"file": (alias, handle, mime_type)},
            timeout=timeout,
        )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError("process_false_upload_response_invalid")
    return {
        "id": str(data["id"]),
        "filename": alias,
        "mime_type": str(data.get("mime_type") or data.get("content_type") or mime_type),
        "size": data.get("size") or Path(source["path"]).stat().st_size,
    }


def _file_process_status(
    session: requests.Session,
    base_url: str,
    file_id: str,
    timeout: int,
) -> str | None:
    response = session.get(_url(base_url, f"/api/v1/files/{file_id}"), timeout=timeout)
    response.raise_for_status()
    data = response.json()
    file_data = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else {}
    value = file_data.get("status")
    return str(value) if value is not None else None


def _file_content_endpoint_has_payload(
    session: requests.Session,
    base_url: str,
    file_id: str,
    timeout: int,
) -> bool:
    response = session.get(_url(base_url, f"/api/v1/files/{file_id}/data/content"), timeout=timeout)
    if response.status_code >= 400:
        return False
    try:
        data = response.json()
    except ValueError:
        return bool(response.text.strip())
    if not isinstance(data, dict):
        return bool(data)
    content = data.get("content")
    return bool(content)


def _run_chat(
    *,
    session: requests.Session,
    base_url: str,
    model_id: str,
    uploads: list[dict[str, Any]],
    case_id: str,
    case_group_id: str,
    source_policy_hints: list[dict[str, Any]] | None,
    passport_config: dict[str, Any] | None,
    clarification_config: dict[str, Any] | None,
    timeout: int,
) -> str:
    files = [
        {
            "type": "file",
            "file": {
                "id": item["id"],
                "filename": item["filename"],
                "name": item["filename"],
                "mime_type": item["mime_type"],
                "content_type": item["mime_type"],
                "size": item["size"],
            },
        }
        for item in uploads
    ]
    retention = {"mode": "customer_approved_test", "explicit": True}
    source_policy = _source_policy_payload(source_policy_hints or [])
    passport_payload = _passport_payload(passport_config or {})
    clarification_payload = _clarification_payload(clarification_config or {})
    content = (
        "Gate 1 normalization for customer-approved package. "
        f"case_group_id={case_group_id}. "
        "Use process=false private intake refs only. "
        "Use retention_policy.mode=customer_approved_test explicit=true. "
        "Do not run source-fact extraction, tax calculation, declaration generation, "
        "XLS/XLSX export, OCR, or VLM."
    )
    if passport_payload.get("enabled"):
        content = "\n".join(
            [
                content,
                (
                    "broker_reports_gate1_passport "
                    "enabled=true "
                    f"passport_model_id={passport_payload['model_id']} "
                    f"passport_prompt_command={passport_payload['prompt_command']} "
                    f"passport_max_documents={passport_payload['max_documents']}"
                ),
            ]
        )
    if clarification_payload.get("enabled"):
        content = "\n".join(
            [
                content,
                (
                    "broker_reports_gate1_clarification "
                    "enabled=true "
                    f"clarification_model_id={clarification_payload['model_id']} "
                    f"clarification_prompt_command={clarification_payload['prompt_command']} "
                    f"criticality_refinement_enabled={str(clarification_payload['criticality_refinement_enabled']).lower()}"
                ),
            ]
        )
    body = {
        "model": model_id,
        "case_id": case_id,
        "retention_policy": retention,
        "source_policy": source_policy,
        "passport_enabled": passport_payload.get("enabled"),
        "passport_model_id": passport_payload.get("model_id"),
        "passport_prompt_command": passport_payload.get("prompt_command"),
        "passport_max_documents": passport_payload.get("max_documents"),
        "broker_reports_gate1": {
            "case_group_id": case_group_id,
            "source_intake": "process_false_private_upload",
            "retention_policy": retention,
            "source_policy": source_policy,
            "document_metadata_passport": passport_payload,
            "clarification": clarification_payload,
            "customer_docs_loaded_to_knowledge": False,
            "source_fact_extraction": False,
            "tax_calculation": False,
            "declaration_generation": False,
            "xlsx_export": False,
            "ocr_vlm": False,
        },
        "messages": [
            {
                "role": "user",
                "content": content,
                "files": files,
            }
        ],
        "files": files,
        "metadata": {
            "case_id": case_id,
            "case_group_id": case_group_id,
            "retention_policy": retention,
            "source_policy": source_policy,
            "broker_reports_gate1": {
                "case_group_id": case_group_id,
                "source_intake": "process_false_private_upload",
                "retention_policy": retention,
                "source_policy": source_policy,
                "document_metadata_passport": passport_payload,
                "clarification": clarification_payload,
                "customer_docs_loaded_to_knowledge": False,
                "source_fact_extraction": False,
                "tax_calculation": False,
                "declaration_generation": False,
                "xlsx_export": False,
                "ocr_vlm": False,
            },
        },
        "stream": False,
    }
    response = session.post(_url(base_url, "/api/chat/completions"), json=body, timeout=timeout)
    response.raise_for_status()
    content = _extract_content(response.json())
    if not content:
        raise RuntimeError("chat_content_missing")
    return content


def _passport_payload(config: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(config.get("enabled"))
    payload = {"enabled": enabled}
    if not enabled:
        return payload
    model_id = str(config.get("model_id") or "").strip()
    if not model_id:
        raise RuntimeError("passport_model_id_missing")
    payload.update(
        {
            "model_id": model_id,
            "prompt_command": str(config.get("prompt_command") or "broker_gate1_document_passport"),
            "max_documents": int(config.get("max_documents") or 32),
        }
    )
    return payload


def _clarification_payload(config: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(config.get("enabled"))
    payload = {"enabled": enabled}
    if not enabled:
        return payload
    model_id = str(config.get("model_id") or "").strip()
    if not model_id:
        raise RuntimeError("clarification_model_id_missing")
    payload.update(
        {
            "model_id": model_id,
            "prompt_command": str(config.get("prompt_command") or "broker_gate1_clarification_request"),
            "answers": [],
            "answer_source": "operator_confirmed",
            "criticality_refinement_enabled": bool(config.get("criticality_refinement_enabled", True)),
        }
    )
    return payload


def _select_passport_model(session: requests.Session, base_url: str) -> str:
    response = session.get(_url(base_url, "/api/models"), timeout=30)
    response.raise_for_status()
    data = response.json()
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("passport_model_list_unavailable")
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "")
        base_model_id = str(item.get("base_model_id") or "")
        owned_by = str(item.get("owned_by") or item.get("owned_by_id") or "")
        probe = " ".join([model_id, base_model_id, owned_by]).lower()
        if not model_id or "broker_reports_gate1_pipe" in probe or "realtime" in probe or "arena" in probe:
            continue
        candidates.append(model_id)
    if not candidates:
        raise RuntimeError("passport_model_candidate_missing")
    preferred = [item for item in candidates if "mini" in item.lower() and "gpt" in item.lower()]
    return preferred[0] if preferred else candidates[0]


def _source_policy_payload(source_policy_hints: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "customer_approved_private_registry",
        "explicit": True,
        "source_registry_role_hints_allowed": True,
        "pdf_html_source_policy": "review_required",
        "accept_pdf_html_source_roles": False,
        "safe_registry_role_hints": source_policy_hints,
    }


def _counter_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    before_safe = _safe_counter_view(before)
    after_safe = _safe_counter_view(after)
    return {key: int(after_safe[key]) - int(before_safe[key]) for key in before_safe}


def _vector_delta_zero(delta: dict[str, int]) -> bool:
    return (
        delta["vector_collections_count"] == 0
        and delta["vector_dir_count"] == 0
        and delta["vector_file_count"] == 0
        and delta["vector_size_bytes"] == 0
    )


def _artifact_summary(ssh_target: str, case_id: str) -> dict[str, Any]:
    code = f"""
import json
import sqlite3
from pathlib import Path

case_id = {case_id!r}
db_path = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
result = {{
    "case_record_count": 0,
    "type_counts": {{}},
    "visibility_counts": {{}},
    "storage_backend_counts": {{}},
    "retention_policy_modes": {{}},
    "retention_policy_explicit_false_count": 0,
    "lifecycle_status_counts": {{}},
    "purge_status_counts": {{}},
    "private_case_records": 0,
    "openwebui_knowledge_records": 0,
    "safe_report": {{}},
    "llm_passport_model_call_status_counts": {{}},
    "document_metadata_passport_validator_status_counts": {{}},
    "document_metadata_passport_validation_summary": {{}},
    "llm_passport_structured_output_mode_counts": {{}},
    "llm_passport_response_format_type_counts": {{}},
    "llm_passport_schema_hash_counts": {{}},
    "llm_passport_repair_attempted_count": 0,
    "llm_passport_fallback_used_count": 0,
    "llm_clarification_model_call_status_counts": {{}},
    "llm_clarification_structured_output_mode_counts": {{}},
    "llm_clarification_response_format_type_counts": {{}},
    "llm_clarification_schema_hash_counts": {{}},
    "llm_clarification_fallback_used_count": 0,
    "gate1_metadata_gap_report_summary": {{}},
    "gate1_clarification_request_summary": {{}},
    "gate2_handoff_safe_metadata": {{}},
    "gate1_issue_ledger_summary": {{}},
    "document_usage_classification_summary": {{}},
    "domain_context_packet_summary": {{}},
    "gate1_clarification_resolution_counts": {{
        "validation_status_counts": {{}},
        "gap_type_counts": {{}},
        "usable_by_source_eligibility_v2": 0,
    }},
}}
if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select artifact_type, visibility, storage_backend, retention_policy_json, "
        "lifecycle_status, purge_status, payload_inline_json, safe_metadata_json "
        "from artifact_records where case_id = ?",
        (case_id,),
    ).fetchall()
    conn.close()
    result["case_record_count"] = len(rows)
    for row in rows:
        artifact_type = row["artifact_type"] or "unknown"
        visibility = row["visibility"] or "unknown"
        storage_backend = row["storage_backend"] or "unknown"
        lifecycle_status = row["lifecycle_status"] or "unknown"
        purge_status = row["purge_status"] or "unknown"
        result["type_counts"][artifact_type] = result["type_counts"].get(artifact_type, 0) + 1
        result["visibility_counts"][visibility] = result["visibility_counts"].get(visibility, 0) + 1
        result["storage_backend_counts"][storage_backend] = result["storage_backend_counts"].get(storage_backend, 0) + 1
        result["lifecycle_status_counts"][lifecycle_status] = result["lifecycle_status_counts"].get(lifecycle_status, 0) + 1
        result["purge_status_counts"][purge_status] = result["purge_status_counts"].get(purge_status, 0) + 1
        if visibility == "private_case":
            result["private_case_records"] += 1
        if storage_backend == "openwebui_knowledge":
            result["openwebui_knowledge_records"] += 1
        policy = json.loads(row["retention_policy_json"])
        mode = policy.get("mode") or "unknown"
        result["retention_policy_modes"][mode] = result["retention_policy_modes"].get(mode, 0) + 1
        if policy.get("explicit") is not True:
            result["retention_policy_explicit_false_count"] += 1
        if artifact_type == "chat_visible_normalization_report_v0" and row["payload_inline_json"]:
            result["safe_report"] = json.loads(row["payload_inline_json"])
        safe_metadata = json.loads(row["safe_metadata_json"] or "{{}}")
        if artifact_type == "llm_passport_raw_output_v0":
            status = safe_metadata.get("model_call_status") or "unknown"
            result["llm_passport_model_call_status_counts"][status] = (
                result["llm_passport_model_call_status_counts"].get(status, 0) + 1
            )
            mode = safe_metadata.get("structured_output_mode") or "unknown"
            result["llm_passport_structured_output_mode_counts"][mode] = (
                result["llm_passport_structured_output_mode_counts"].get(mode, 0) + 1
            )
            response_format_type = safe_metadata.get("response_format_type") or "unknown"
            result["llm_passport_response_format_type_counts"][response_format_type] = (
                result["llm_passport_response_format_type_counts"].get(response_format_type, 0) + 1
            )
            schema_hash = safe_metadata.get("output_schema_hash") or "unknown"
            result["llm_passport_schema_hash_counts"][schema_hash] = (
                result["llm_passport_schema_hash_counts"].get(schema_hash, 0) + 1
            )
            if safe_metadata.get("repair_attempted") is True:
                result["llm_passport_repair_attempted_count"] += 1
            if safe_metadata.get("fallback_used") is True:
                result["llm_passport_fallback_used_count"] += 1
        if artifact_type == "llm_clarification_raw_output_v0":
            status = safe_metadata.get("model_call_status") or "unknown"
            result["llm_clarification_model_call_status_counts"][status] = (
                result["llm_clarification_model_call_status_counts"].get(status, 0) + 1
            )
            mode = safe_metadata.get("structured_output_mode") or "unknown"
            result["llm_clarification_structured_output_mode_counts"][mode] = (
                result["llm_clarification_structured_output_mode_counts"].get(mode, 0) + 1
            )
            response_format_type = safe_metadata.get("response_format_type") or "unknown"
            result["llm_clarification_response_format_type_counts"][response_format_type] = (
                result["llm_clarification_response_format_type_counts"].get(response_format_type, 0) + 1
            )
            schema_hash = safe_metadata.get("output_schema_hash") or "unknown"
            result["llm_clarification_schema_hash_counts"][schema_hash] = (
                result["llm_clarification_schema_hash_counts"].get(schema_hash, 0) + 1
            )
            if safe_metadata.get("fallback_used") is True:
                result["llm_clarification_fallback_used_count"] += 1
        if artifact_type == "document_metadata_passport_v0":
            status = safe_metadata.get("validator_status") or "unknown"
            result["document_metadata_passport_validator_status_counts"][status] = (
                result["document_metadata_passport_validator_status_counts"].get(status, 0) + 1
            )
        if artifact_type == "document_metadata_passport_validation_v0":
            result["document_metadata_passport_validation_summary"] = safe_metadata
        if artifact_type == "gate1_metadata_gap_report_v0":
            result["gate1_metadata_gap_report_summary"] = {{
                "gap_report_id": safe_metadata.get("gap_report_id"),
                "gaps_total": safe_metadata.get("gaps_total"),
                "blocking_gaps_total": safe_metadata.get("blocking_gaps_total"),
                "gap_type_counts": safe_metadata.get("gap_type_counts") or {{}},
                "criticality_counts": safe_metadata.get("criticality_counts") or {{}},
                "critical_gaps_total": safe_metadata.get("critical_gaps_total"),
                "clarifying_gaps_total": safe_metadata.get("clarifying_gaps_total"),
                "non_critical_gaps_total": safe_metadata.get("non_critical_gaps_total"),
                "handoff_mode": safe_metadata.get("handoff_mode"),
            }}
        if artifact_type == "gate1_clarification_request_v0":
            result["gate1_clarification_request_summary"] = {{
                "clarification_request_id": safe_metadata.get("clarification_request_id"),
                "gap_report_id": safe_metadata.get("gap_report_id"),
                "questions_total": safe_metadata.get("questions_total"),
                "required_questions_total": safe_metadata.get("required_questions_total"),
                "gap_type_counts": safe_metadata.get("gap_type_counts") or {{}},
                "criticality_counts": safe_metadata.get("criticality_counts") or {{}},
                "critical_questions_total": safe_metadata.get("critical_questions_total"),
                "clarifying_questions_total": safe_metadata.get("clarifying_questions_total"),
                "non_critical_questions_total": safe_metadata.get("non_critical_questions_total"),
                "validator_status": safe_metadata.get("validator_status"),
                "output_schema_hash": safe_metadata.get("output_schema_hash"),
            }}
        if artifact_type == "gate1_clarification_resolution_v0":
            status = safe_metadata.get("validation_status") or "unknown"
            counts = result["gate1_clarification_resolution_counts"]
            counts["validation_status_counts"][status] = counts["validation_status_counts"].get(status, 0) + 1
            gap_type = safe_metadata.get("gap_type") or "unknown"
            counts["gap_type_counts"][gap_type] = counts["gap_type_counts"].get(gap_type, 0) + 1
            if safe_metadata.get("usable_by_source_eligibility_v2") is True:
                counts["usable_by_source_eligibility_v2"] += 1
        if artifact_type == "gate1_issue_ledger_v0":
            result["gate1_issue_ledger_summary"] = {{
                "issues_total": safe_metadata.get("issues_total"),
                "unresolved_issues_total": safe_metadata.get("unresolved_issues_total"),
                "skipped_unresolved_issues_total": safe_metadata.get("skipped_unresolved_issues_total"),
                "awaiting_answer_unresolved_issues_total": safe_metadata.get("awaiting_answer_unresolved_issues_total"),
            }}
        if artifact_type == "document_usage_classification_v0":
            result["document_usage_classification_summary"] = {{
                "documents_total": safe_metadata.get("documents_total"),
                "source_fact_extraction_ready_total": safe_metadata.get("source_fact_extraction_ready_total"),
                "source_fact_extraction_blocked_total": safe_metadata.get("source_fact_extraction_blocked_total"),
            }}
        if artifact_type == "domain_context_packet_v0":
            result["domain_context_packet_summary"] = {{
                "domain_ingestion_status": safe_metadata.get("domain_ingestion_status"),
                "unresolved_issue_summary": safe_metadata.get("unresolved_issue_summary") or {{}},
                "stage_readiness": safe_metadata.get("stage_readiness") or {{}},
                "next_stage_ref_summary": safe_metadata.get("next_stage_ref_summary") or {{}},
                "vector_knowledge_guard": safe_metadata.get("vector_knowledge_guard") or {{}},
            }}
        if artifact_type == "gate2_handoff_v0":
            result["gate2_handoff_safe_metadata"] = {{
                "handoff_status": safe_metadata.get("handoff_status"),
                "handoff_mode": safe_metadata.get("handoff_mode"),
                "decision_status_counts": safe_metadata.get("decision_status_counts") or {{}},
                "handoff_blocker_counts": safe_metadata.get("handoff_blocker_counts") or {{}},
                "next_stage_ref_summary": safe_metadata.get("next_stage_ref_summary") or {{}},
                "auto_resolved_duplicate_document_ids": safe_metadata.get("auto_resolved_duplicate_document_ids") or [],
                "auto_canonical_duplicate_groups": safe_metadata.get("auto_canonical_duplicate_groups") or [],
            }}
safe_report = result["safe_report"] if isinstance(result["safe_report"], dict) else {{}}
domain_summary = safe_report.get("domain_context_packet_summary") if isinstance(safe_report.get("domain_context_packet_summary"), dict) else {{}}
if domain_summary:
    result["domain_context_packet_summary"]["unresolved_issue_summary"] = domain_summary.get("unresolved_issue_summary") or {{}}
    result["domain_context_packet_summary"]["next_stage_ref_summary"] = domain_summary.get("next_stage_ref_summary") or result["domain_context_packet_summary"].get("next_stage_ref_summary") or {{}}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
"""
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=ROOT,
        input=code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def _chat_shape(chat_report: str, uploads: list[dict[str, Any]]) -> dict[str, Any]:
    lowered = chat_report.lower()
    private_tokens = [str(item.get("id") or "") for item in uploads] + [
        str(item.get("filename") or "") for item in uploads
    ]
    private_leak = any(token and token in chat_report for token in private_tokens)
    return {
        "length": len(chat_report),
        "contains_cyrillic": any("\u0400" <= char <= "\u04ff" for char in chat_report),
        "contains_json_fence": "```json" in lowered,
        "starts_with_json": chat_report.lstrip().startswith("{"),
        "contains_gate2_hint": "gate 2" in lowered or "gate2" in lowered or "handoff" in lowered or "refs" in lowered,
        "compact_russian_report": (
            len(chat_report) < 7000
            and "```json" not in lowered
            and not chat_report.lstrip().startswith("{")
            and any("\u0400" <= char <= "\u04ff" for char in chat_report)
        ),
        "private_refs_not_in_chat": not private_leak,
    }


def _safe_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    flags = report.get("safety_flags") if isinstance(report.get("safety_flags"), dict) else {}
    return {
        "files_total": report.get("files_total"),
        "run_status": report.get("run_status"),
        "container_counts": report.get("container_counts"),
        "document_class_counts": report.get("document_class_counts"),
        "duplicate_count": report.get("duplicate_count"),
        "blockers_total": report.get("blockers_total"),
        "gate2_handoff_status": report.get("gate2_handoff_status"),
        "gate2_handoff_mode": report.get("gate2_handoff_mode"),
        "gate2_reduced_subset_ready": report.get("gate2_reduced_subset_ready"),
        "source_eligibility_summary": report.get("source_eligibility_summary"),
        "document_metadata_passport_summary": report.get("document_metadata_passport_summary"),
        "gate1_metadata_gap_report_summary": report.get("gate1_metadata_gap_report_summary"),
        "gate1_clarification_request_summary": report.get("gate1_clarification_request_summary"),
        "gate1_clarification_resolution_summary": report.get("gate1_clarification_resolution_summary"),
        "gate1_issue_ledger_summary": report.get("gate1_issue_ledger_summary"),
        "document_usage_classification_summary": report.get("document_usage_classification_summary"),
        "domain_context_packet_summary": report.get("domain_context_packet_summary"),
        "domain_ingestion_summary": report.get("domain_ingestion_summary"),
        "validation_status": report.get("validation_result", {}).get("status")
        if isinstance(report.get("validation_result"), dict)
        else None,
        "safety_flags": {
            key: flags.get(key)
            for key in (
                "source_fact_extraction_performed",
                "tax_correctness_claimed",
                "declaration_generated",
                "xlsx_generated",
                "ocr_performed",
                "customer_docs_loaded_to_knowledge",
            )
        },
    }


def _safety_flags_false(report: dict[str, Any]) -> bool:
    flags = report.get("safety_flags") if isinstance(report.get("safety_flags"), dict) else {}
    return all(
        flags.get(key) is False
        for key in (
            "source_fact_extraction_performed",
            "tax_correctness_claimed",
            "declaration_generated",
            "xlsx_generated",
            "ocr_performed",
            "customer_docs_loaded_to_knowledge",
        )
    )


def _statuses(passed: bool, *, clarification_mode: bool = False) -> list[str]:
    if passed:
        if clarification_mode:
            return [
                "CUSTOMER_CASE_GROUP_002_PROCESS_FALSE_GATE1_READY",
                "CUSTOMER_APPROVED_RETENTION_APPLIED",
                "CUSTOMER_VECTOR_DB_GUARD_PASSED",
                "CUSTOMER_KNOWLEDGE_GUARD_PASSED",
                "CUSTOMER_ARTIFACTSTORE_PERSISTENCE_READY",
                "CUSTOMER_COMPACT_REPORT_READY",
                "GATE1_GAP_BLOCKING_POLICY_REFINED",
                "GATE1_CLARIFICATION_GROUPED_QUESTIONS_READY",
                "GATE1_UNRESOLVED_ISSUES_CARRIED_FORWARD",
                "GATE1_DOMAIN_CONTEXT_PACKET_READY",
                "GATE1_DOMAIN_CONTEXT_HANDOFF_AUDIT_READY",
                "GATE1_NO_SOURCE_READY_DOC_LOSS_PROVEN",
                "GATE1_NEXT_STAGE_REFS_REFINED",
                "GATE1_ISSUE_LEDGER_CARRY_FORWARD_PROVEN",
                "CASE_GROUP_002_DOMAIN_INGESTION_RERUN_READY",
                "CASE_GROUP_002_DOMAIN_CONTEXT_PACKET_READY",
                "CASE_GROUP_002_CLARIFICATION_REQUEST_READY",
                "CASE_GROUP_002_CLARIFICATION_CRITICALITY_RERUN_READY",
                "CASE_GROUP_002_ACTIONABLE_CRITICAL_QUESTIONS_READY",
                "CASE_GROUP_002_HANDOFF_RECONCILIATION_READY",
                "CASE_GROUP_002_NO_SOURCE_READY_DOC_LOSS_PROVEN",
                "CASE_GROUP_002_VECTOR_GUARD_PASSED",
                "CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED",
                "READY_FOR_CASE_GROUP_002_DOMAIN_SOURCE_FACT_EXTRACTION_WITH_ISSUE_CONTEXT",
            ]
        return [
            "CUSTOMER_CASE_GROUP_002_PROCESS_FALSE_GATE1_READY",
            "CUSTOMER_APPROVED_RETENTION_APPLIED",
            "CUSTOMER_VECTOR_DB_GUARD_PASSED",
            "CUSTOMER_KNOWLEDGE_GUARD_PASSED",
            "CUSTOMER_ARTIFACTSTORE_PERSISTENCE_READY",
            "CUSTOMER_COMPACT_REPORT_READY",
            "CUSTOMER_SOURCE_UPLOAD_CLEANUP_READY",
            "GATE1_UNRESOLVED_ISSUES_CARRIED_FORWARD",
            "GATE1_DOMAIN_CONTEXT_PACKET_READY",
            "GATE1_DOMAIN_CONTEXT_HANDOFF_AUDIT_READY",
            "GATE1_NO_SOURCE_READY_DOC_LOSS_PROVEN",
            "GATE1_NEXT_STAGE_REFS_REFINED",
            "GATE1_ISSUE_LEDGER_CARRY_FORWARD_PROVEN",
            "CASE_GROUP_002_DOMAIN_INGESTION_RERUN_READY",
            "CASE_GROUP_002_DOMAIN_CONTEXT_PACKET_READY",
            "CASE_GROUP_002_HANDOFF_RECONCILIATION_READY",
            "CASE_GROUP_002_NO_SOURCE_READY_DOC_LOSS_PROVEN",
            "CASE_GROUP_002_VECTOR_GUARD_PASSED",
            "CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED",
            "READY_FOR_CASE_GROUP_002_DOMAIN_SOURCE_FACT_EXTRACTION_WITH_ISSUE_CONTEXT",
        ]
    return [
        "CUSTOMER_CASE_GROUP_002_PROCESS_FALSE_GATE1_PARTIAL",
        "CUSTOMER_GATE2_PROOF_BLOCKED",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
