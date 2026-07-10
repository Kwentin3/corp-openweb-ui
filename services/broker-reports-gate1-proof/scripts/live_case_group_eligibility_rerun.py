#!/usr/bin/env python3
"""
Customer-approved case_group_002 Gate 1 eligibility rerun.

The script updates the live Pipe Function with the current bundled build, then
prefers retained process=false source refs from the previous customer-approved
run. If retained refs are unavailable, it falls back to a new controlled
process=false upload using sanitized aliases. Stdout contains only safe
aggregate proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from live_case_group_process_false_gate1_run import (
    DEFAULT_CASE_GROUPS,
    DEFAULT_CASE_GROUP_ID,
    DEFAULT_PRIVATE_REGISTRY,
    DEFAULT_SAFE_SOURCE_REGISTRY,
    _chat_shape,
    _counter_delta,
    _file_content_endpoint_has_payload,
    _file_process_status,
    _load_json,
    _repo_path,
    _resolve_case_group_sources,
    _run_chat,
    _safety_flags_false,
    _source_policy_hints,
    _truthy_yes,
    _upload_process_false,
    _vector_delta_zero,
)
from live_no_rag_source_intake_smoke import (
    ROOT,
    _base_url,
    _capabilities,
    _default_ssh_target,
    _get_model,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
    _signin,
    _url,
)


SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
FUNCTION_ID = "broker_reports_gate1_pipe"
REQUIRED_ARTIFACT_TYPES = {
    "normalization_run_v0",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    "document_source_eligibility_v0",
    "validation_result_v0",
    "gate2_handoff_v0",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--settle-seconds", type=int, default=6)
    parser.add_argument("--force-new-process-false-upload", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    model_id = args.model_id or env.get("OPENWEBUI_WORKSPACE_MODEL_ID") or env.get("OPENWEBUI_MODEL_ID") or "test"
    case_group = _safe_case_group_summary(
        case_group_id=args.case_group_id,
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    source_policy_hints = _source_policy_hints(
        case_group_id=args.case_group_id,
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    case_id = f"customer_{args.case_group_id}_eligibility_gate1_{time.strftime('%Y%m%d%H%M%S')}"

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    function_update = _update_live_function(session, base_url)
    model = _get_model(session, base_url, model_id)

    uploaded: list[dict[str, Any]] = []
    intake_mode = "retained_process_false_refs"
    retained_case_id: str | None = None
    new_upload_performed = False
    gate1_completed = False

    try:
        before = _runtime_snapshot(ssh_target)
        after_intake = before
        if not args.force_new_process_false_upload:
            retained = _retained_process_false_refs(
                ssh_target=ssh_target,
                case_group_id=args.case_group_id,
                expected_count=case_group["files_total"],
            )
            retained_case_id = retained.get("case_id") if retained.get("status") == "found" else None
            uploaded = _openwebui_upload_refs_from_source_refs(
                session=session,
                base_url=base_url,
                source_refs=retained.get("source_refs", []),
                timeout=args.timeout,
            )

        if len(uploaded) != case_group["files_total"]:
            sources = _resolve_case_group_sources(
                case_group_id=args.case_group_id,
                private_registry_path=_repo_path(args.private_registry),
                safe_source_registry_path=_repo_path(args.safe_source_registry),
                case_groups_path=_repo_path(args.case_groups),
            )
            uploaded = [
                _upload_process_false(session, base_url, source, index + 1, args.timeout)
                for index, source in enumerate(sources["files"])
            ]
            new_upload_performed = True
            intake_mode = "new_process_false_upload"
            time.sleep(args.settle_seconds)
            after_intake = _runtime_snapshot(ssh_target)

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
            source_policy_hints=source_policy_hints,
            timeout=args.timeout,
        )
        gate1_completed = True
        time.sleep(args.settle_seconds)
        after_chat = _runtime_snapshot(ssh_target)

        artifacts = _artifact_summary(ssh_target, case_id)
        chat_shape = _chat_shape(chat_report, uploaded)
        intake_delta = _counter_delta(before, after_intake)
        chat_delta = _counter_delta(before, after_chat)
        checks = {
            "live_function_hash_parity": function_update["hash_parity"],
            "live_bundle_contains_eligibility_module": function_update["live_source_contains"]["eligibility_module"],
            "live_bundle_contains_source_policy_status": function_update["live_source_contains"][
                "source_role_policy_review_required"
            ],
            "process_false_or_retained_process_false_refs": intake_mode
            in {"retained_process_false_refs", "new_process_false_upload"},
            "source_ref_count_matches_package": len(uploaded) == case_group["files_total"],
            "process_status_completed_absent": all(value != "completed" for value in process_status_values),
            "uploaded_file_content_endpoint_empty": extracted_content_endpoint_count == 0,
            "document_rows_zero_delta": chat_delta["document_rows"] == 0,
            "knowledge_rows_zero_delta": chat_delta["knowledge_rows"] == 0,
            "vector_delta_zero_after_intake": _vector_delta_zero(intake_delta),
            "vector_delta_zero_after_chat": _vector_delta_zero(chat_delta),
            "compact_russian_report": chat_shape["compact_russian_report"],
            "compact_report_has_eligibility_counts": _chat_has_eligibility_counts(chat_report),
            "private_refs_not_in_chat": chat_shape["private_refs_not_in_chat"],
            "artifactstore_required_types_persisted": REQUIRED_ARTIFACT_TYPES <= set(artifacts["type_counts"]),
            "artifactstore_no_knowledge_backend": artifacts["openwebui_knowledge_records"] == 0,
            "customer_retention_applied": artifacts["retention_policy_modes"]
            == {"customer_approved_test": artifacts["case_record_count"]},
            "customer_retention_explicit": artifacts["retention_policy_explicit_false_count"] == 0,
            "document_source_eligibility_persisted": artifacts["type_counts"].get("document_source_eligibility_v0", 0) == 1,
            "gate2_handoff_reduced_ready": artifacts["handoff"]["handoff_mode"] == "reduced_subset_ready_for_gate2",
            "included_document_refs_present": artifacts["handoff"]["included_document_refs_count"] > 0,
            "excluded_source_policy_duplicate_refs_present": (
                artifacts["handoff"]["excluded_document_refs_count"] > 0
                and artifacts["handoff"]["pending_review_refs_count"] > 0
                and artifacts["handoff"]["source_policy_review_refs_count"] > 0
                and artifacts["handoff"]["duplicate_review_refs_count"] > 0
            ),
            "pdf_html_not_misrouted_to_ocr": artifacts["eligibility"]["requires_ocr_before_gate2"] == 0,
            "ocr_refs_match_eligibility": artifacts["handoff"]["ocr_required_refs_count"]
            == artifacts["eligibility"]["requires_ocr_before_gate2"],
            "private_slice_refs_only_for_included_documents": artifacts["handoff"][
                "private_slice_refs_only_for_included_documents"
            ],
            "terminal_blockers_not_in_included_refs": artifacts["handoff"][
                "terminal_blockers_not_in_included_refs"
            ],
            "safety_flags_false": _safety_flags_false(artifacts["safe_report"]),
        }
        passed = all(checks.values())
        summary = {
            "status": "passed" if passed else "partial",
            "statuses": _statuses(passed),
            "case_group": case_group,
            "case_id": case_id,
            "live_function": function_update,
            "model": {
                "model_id": model_id,
                "base_model_id": model.get("base_model_id"),
                "capabilities": _capabilities(model),
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
                "safe_registry_role_hints_count": len(source_policy_hints),
            },
            "intake": {
                "mode": intake_mode,
                "retained_refs_reused": intake_mode == "retained_process_false_refs",
                "retained_refs_case_id": retained_case_id,
                "new_process_false_upload_performed": new_upload_performed,
                "path": "POST /api/v1/files/?process=false" if new_upload_performed else "retained process=false source refs",
                "source_ref_count": len(uploaded),
                "sanitized_aliases_used_for_new_upload": new_upload_performed,
                "process_status_values": process_status_values,
                "content_endpoint_payload_count": extracted_content_endpoint_count,
            },
            "runtime_counters": {
                "before": _safe_counter_view(before),
                "after_intake": _safe_counter_view(after_intake),
                "after_chat": _safe_counter_view(after_chat),
                "delta_after_intake": intake_delta,
                "delta_after_chat": chat_delta,
            },
            "chat_visible_report_shape": chat_shape,
            "gate1_safe_report": artifacts["safe_report_summary"],
            "eligibility": artifacts["eligibility"],
            "handoff": artifacts["handoff"],
            "artifactstore": {
                key: value
                for key, value in artifacts.items()
                if key not in {"safe_report", "safe_report_summary", "eligibility", "handoff"}
            },
            "checks": checks,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if passed else 2
    except Exception:
        if uploaded and not gate1_completed and new_upload_performed:
            try:
                _delete_upload_refs(session, base_url, uploaded)
            except Exception:
                pass
        raise


def _safe_case_group_summary(
    *,
    case_group_id: str,
    safe_source_registry_path: Path,
    case_groups_path: Path,
) -> dict[str, Any]:
    case_groups = _load_json(case_groups_path)
    safe_source = _load_json(safe_source_registry_path)
    group = next(
        (item for item in case_groups.get("case_groups", []) if item.get("case_group_id") == case_group_id),
        None,
    )
    if not isinstance(group, dict):
        raise RuntimeError("case_group_missing")
    document_ids = list(group.get("document_ids") or [])
    safe_by_id = {item.get("document_id"): item for item in safe_source.get("documents", [])}
    formats: dict[str, int] = {}
    roles: dict[str, int] = {}
    source_candidates = 0
    methodology_candidates = 0
    for document_id in document_ids:
        safe_doc = safe_by_id.get(document_id)
        if not isinstance(safe_doc, dict):
            raise RuntimeError("case_group_safe_document_missing")
        container = str(safe_doc.get("container_format") or "unknown")
        role = str(safe_doc.get("document_role_candidate") or "unknown")
        formats[container] = formats.get(container, 0) + 1
        roles[role] = roles.get(role, 0) + 1
        if _truthy_yes(safe_doc.get("source_evidence_candidate")):
            source_candidates += 1
        if _truthy_yes(safe_doc.get("methodology_or_output_candidate")):
            methodology_candidates += 1
    return {
        "case_group_id": case_group_id,
        "broker_provider_candidate": group.get("broker_provider_candidate"),
        "confidence": group.get("confidence"),
        "readiness": group.get("readiness"),
        "manual_review_required": group.get("manual_review_required"),
        "files_total": len(document_ids),
        "formats_from_registry": dict(sorted(formats.items())),
        "document_role_candidates_from_registry": dict(sorted(roles.items())),
        "source_evidence_candidates_from_registry": source_candidates,
        "methodology_or_output_candidates_from_registry": methodology_candidates,
    }


def _update_live_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_hash = hashlib.sha256(bundle_source.encode("utf-8")).hexdigest()
    before = _get_function(session, base_url)
    previous_hash = hashlib.sha256(str(before.get("content") or "").encode("utf-8")).hexdigest()
    payload = {
        "id": FUNCTION_ID,
        "name": before.get("name") or "Broker Reports Gate 1",
        "meta": before.get("meta") if isinstance(before.get("meta"), dict) else {},
        "content": bundle_source,
    }
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    after = _get_function(session, base_url)
    live_source = str(after.get("content") or "")
    live_hash = hashlib.sha256(live_source.encode("utf-8")).hexdigest()
    return {
        "function_id": FUNCTION_ID,
        "previous_bundle_sha256": previous_hash,
        "bundle_sha256": bundle_hash,
        "live_bundle_sha256": live_hash,
        "hash_parity": live_hash == bundle_hash,
        "live_source_contains": {
            "eligibility_module": '"eligibility"' in live_source,
            "document_source_eligibility_v0": "document_source_eligibility_v0" in live_source,
            "reduced_subset_ready_for_gate2": "reduced_subset_ready_for_gate2" in live_source,
            "source_role_policy_review_required": "source_role_policy_review_required" in live_source,
        },
    }


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(_url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("function_response_invalid")
    return data


def _retained_process_false_refs(
    *,
    ssh_target: str,
    case_group_id: str,
    expected_count: int,
) -> dict[str, Any]:
    code = f"""
import json
import sqlite3
from pathlib import Path

case_prefix = "customer_" + {case_group_id!r} + "_process_false_gate1_"
expected_count = {expected_count}
db_path = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
result = {{"status": "not_found", "case_id": None, "source_refs": []}}
if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    case_rows = conn.execute(
        "select case_id, max(created_at) as latest_created_at "
        "from artifact_records "
        "where artifact_type = 'source_file_ref_v0' and case_id like ? "
        "and purge_status = 'active' and lifecycle_status != 'purged' "
        "group by case_id order by latest_created_at desc",
        (case_prefix + "%",),
    ).fetchall()
    for case_row in case_rows:
        case_id = case_row["case_id"]
        rows = conn.execute(
            "select source_file_ref_json, retention_policy_json "
            "from artifact_records "
            "where case_id = ? and artifact_type = 'source_file_ref_v0' "
            "and purge_status = 'active' and lifecycle_status != 'purged' "
            "order by created_at asc, artifact_id asc",
            (case_id,),
        ).fetchall()
        if len(rows) != expected_count:
            continue
        refs = []
        valid = True
        for row in rows:
            policy = json.loads(row["retention_policy_json"])
            source_ref = json.loads(row["source_file_ref_json"] or "{{}}")
            if policy.get("mode") != "customer_approved_test" or policy.get("explicit") is not True:
                valid = False
                break
            if source_ref.get("source_deleted") is True or not source_ref.get("openwebui_file_id"):
                valid = False
                break
            refs.append(source_ref)
        if valid:
            result = {{"status": "found", "case_id": case_id, "source_refs": refs}}
            break
    conn.close()
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


def _openwebui_upload_refs_from_source_refs(
    *,
    session: requests.Session,
    base_url: str,
    source_refs: list[dict[str, Any]],
    timeout: int,
) -> list[dict[str, Any]]:
    uploads = []
    for source_ref in source_refs:
        file_id = str(source_ref.get("openwebui_file_id") or "")
        if not file_id:
            return []
        response = session.get(_url(base_url, f"/api/v1/files/{file_id}"), timeout=timeout)
        if response.status_code >= 400:
            return []
        record = response.json() if response.text else {}
        data = record.get("data") if isinstance(record, dict) and isinstance(record.get("data"), dict) else {}
        filename = (
            data.get("filename")
            or data.get("name")
            or record.get("filename")
            or record.get("name")
            or ""
        )
        mime_type = (
            data.get("mime_type")
            or data.get("content_type")
            or record.get("mime_type")
            or record.get("content_type")
            or source_ref.get("content_type")
            or ""
        )
        size = data.get("size") or record.get("size") or source_ref.get("size_bytes")
        if not filename:
            return []
        uploads.append(
            {
                "id": file_id,
                "filename": str(filename),
                "mime_type": str(mime_type),
                "size": size,
            }
        )
    return uploads


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
    "safe_report_summary": {{}},
    "eligibility": {{"status_counts": {{}}, "entries_count": 0}},
    "handoff": {{}},
}}
if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select artifact_id, artifact_type, document_id, visibility, storage_backend, "
        "retention_policy_json, lifecycle_status, purge_status, payload_inline_json "
        "from artifact_records where case_id = ?",
        (case_id,),
    ).fetchall()
    records_by_id = {{row["artifact_id"]: row for row in rows}}
    result["case_record_count"] = len(rows)
    handoff_payload = {{}}
    eligibility_payload = {{}}
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
        if row["payload_inline_json"]:
            payload = json.loads(row["payload_inline_json"])
            if artifact_type == "chat_visible_normalization_report_v0":
                result["safe_report"] = payload
            elif artifact_type == "gate2_handoff_v0":
                handoff_payload = payload
            elif artifact_type == "document_source_eligibility_v0":
                eligibility_payload = payload
    safe_report = result["safe_report"] if isinstance(result["safe_report"], dict) else {{}}
    flags = safe_report.get("safety_flags") if isinstance(safe_report.get("safety_flags"), dict) else {{}}
    result["safe_report_summary"] = {{
        "files_total": safe_report.get("files_total"),
        "run_status": safe_report.get("run_status"),
        "container_counts": safe_report.get("container_counts"),
        "document_class_counts": safe_report.get("document_class_counts"),
        "duplicate_count": safe_report.get("duplicate_count"),
        "blockers_total": safe_report.get("blockers_total"),
        "gate2_handoff_status": safe_report.get("gate2_handoff_status"),
        "gate2_handoff_mode": safe_report.get("gate2_handoff_mode"),
        "gate2_reduced_subset_ready": safe_report.get("gate2_reduced_subset_ready"),
        "source_eligibility_summary": safe_report.get("source_eligibility_summary"),
        "validation_status": (safe_report.get("validation_result") or {{}}).get("status")
            if isinstance(safe_report.get("validation_result"), dict) else None,
        "safety_flags": {{
            key: flags.get(key)
            for key in (
                "source_fact_extraction_performed",
                "tax_correctness_claimed",
                "declaration_generated",
                "xlsx_generated",
                "ocr_performed",
                "customer_docs_loaded_to_knowledge",
            )
        }},
    }}
    entries = eligibility_payload.get("entries") if isinstance(eligibility_payload, dict) else []
    status_counts = {{}}
    included_doc_ids_from_eligibility = set()
    terminal_included = False
    for entry in entries or []:
        status = entry.get("source_eligibility") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        if entry.get("included_in_reduced_subset"):
            included_doc_ids_from_eligibility.add(entry.get("document_id"))
            if entry.get("exclusion_is_terminal") or entry.get("can_enter_gate2") is not True:
                terminal_included = True
    included_refs = list(handoff_payload.get("included_document_refs") or [])
    excluded_refs = list(handoff_payload.get("excluded_document_refs") or [])
    pending_refs = list(handoff_payload.get("pending_review_refs") or [])
    source_policy_refs = list(handoff_payload.get("source_policy_review_refs") or [])
    ocr_refs = list(handoff_payload.get("ocr_required_refs") or [])
    duplicate_refs = list(handoff_payload.get("duplicate_review_refs") or [])
    private_refs = list(handoff_payload.get("private_slice_refs") or [])
    included_doc_ids = {{
        records_by_id[ref]["document_id"]
        for ref in included_refs
        if ref in records_by_id and records_by_id[ref]["document_id"]
    }}
    private_doc_ids = {{
        records_by_id[ref]["document_id"]
        for ref in private_refs
        if ref in records_by_id and records_by_id[ref]["document_id"]
    }}
    private_refs_only_included = bool(private_refs) and private_doc_ids <= included_doc_ids
    result["eligibility"] = {{
        "entries_count": len(entries or []),
        "status_counts": dict(sorted(status_counts.items())),
        "accepted_for_gate2": status_counts.get("accepted_for_gate2", 0),
        "excluded_from_gate2": status_counts.get("excluded_from_gate2", 0),
        "requires_manual_review": status_counts.get("requires_manual_review", 0),
        "requires_ocr_before_gate2": status_counts.get("requires_ocr_before_gate2", 0),
        "source_role_policy_review_required": status_counts.get("source_role_policy_review_required", 0),
        "duplicate_needs_canonical_choice": status_counts.get("duplicate_needs_canonical_choice", 0),
        "methodology_or_output_artifact": status_counts.get("methodology_or_output_artifact", 0),
        "unknown_role_requires_review": status_counts.get("unknown_role_requires_review", 0),
    }}
    result["handoff"] = {{
        "handoff_status": handoff_payload.get("handoff_status"),
        "handoff_mode": handoff_payload.get("handoff_mode"),
        "reduced_subset_validated": handoff_payload.get("reduced_subset_validated") is True,
        "included_document_refs_count": len(included_refs),
        "excluded_document_refs_count": len(excluded_refs),
        "pending_review_refs_count": len(pending_refs),
        "source_policy_review_refs_count": len(source_policy_refs),
        "ocr_required_refs_count": len(ocr_refs),
        "duplicate_review_refs_count": len(duplicate_refs),
        "private_slice_refs_count": len(private_refs),
        "private_slice_refs_only_for_included_documents": private_refs_only_included,
        "terminal_blockers_not_in_included_refs": (
            not terminal_included and included_doc_ids <= included_doc_ids_from_eligibility
        ),
    }}
    conn.close()
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


def _chat_has_eligibility_counts(chat_report: str) -> bool:
    required_fragments = [
        "Получено документов",
        "Итог Gate 1",
        "Принято к Gate 2",
        "Исключено как не source",
        "Требуют OCR",
        "Требуют проверки роли/source-policy",
        "Дубликаты / canonical choice",
        "Handoff mode",
    ]
    return all(fragment in chat_report for fragment in required_fragments)


def _delete_upload_refs(session: requests.Session, base_url: str, uploads: list[dict[str, Any]]) -> int:
    deleted = 0
    for upload in uploads:
        file_id = upload.get("id")
        if not file_id:
            continue
        response = session.delete(_url(base_url, f"/api/v1/files/{file_id}"), timeout=30)
        if response.status_code in {200, 204}:
            deleted += 1
    return deleted


def _statuses(passed: bool) -> list[str]:
    if passed:
        return [
            "GATE1_PDF_TEXT_LAYER_POLICY_READY",
            "GATE1_HTML_TABLE_EVIDENCE_READY",
            "GATE1_SOURCE_ROLE_POLICY_READY",
            "CASE_GROUP_002_PDF_HTML_RERUN_V2_READY",
            "CASE_GROUP_002_SUMMARY_COUNTS_READY",
            "CASE_GROUP_002_VECTOR_GUARD_PASSED",
            "CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED",
            "READY_FOR_SPECIALIST_DECISION_ON_PDF_HTML_SOURCE_POLICY",
            "CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF_LIMITED_TO_CURRENT_ACCEPTED_SUBSET",
        ]
    return [
        "CASE_GROUP_002_PDF_HTML_RERUN_V2_PARTIAL",
        "CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF_BLOCKED",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
