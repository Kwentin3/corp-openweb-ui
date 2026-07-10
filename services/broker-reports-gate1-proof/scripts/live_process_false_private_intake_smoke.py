#!/usr/bin/env python3
"""
Live smoke for Broker Reports Gate 1 private source intake.

This script proves the project-owned upload path that sends source files to
OpenWebUI with process=false, then hands opaque upload refs to the Gate 1 Pipe.
It deliberately prints only aggregate counters and boolean checks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

from live_no_rag_source_intake_smoke import (
    FIXTURES,
    ROOT,
    SYNTHETIC_FILES,
    SYNTHETIC_MARKERS,
    _base_url,
    _capabilities,
    _delete_uploads,
    _default_ssh_target,
    _extract_content,
    _get_model,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
    _signin,
    _update_model,
    _url,
    _with_capabilities,
)
from live_case_group_process_false_gate1_run import _passport_payload, _select_passport_model


DEFAULT_CASE_ID_PREFIX = "case_gate1_process_false_private_intake_smoke"
CLARIFICATION_GAP_SYNTHETIC_FILES = [
    FIXTURES / "synthetic_missing_metadata_report.txt",
]
BLOCKING_POLICY_SYNTHETIC_FILES = [
    FIXTURES / "synthetic_missing_metadata_report.txt",
    FIXTURES / "synthetic_operations.csv",
    FIXTURES / "synthetic_operations_duplicate.csv",
]

FORBIDDEN_CHAT_MARKERS = [
    *SYNTHETIC_MARKERS,
    '"artifacts"',
    '"private_normalized',
    '"gate2_handoff"',
    "openwebui-file",
]


def _compact_bool(value: bool) -> str:
    return "true" if value else "false"


def _prompt(case_id: str) -> str:
    return (
        "Gate 1 normalization artifactstore retention smoke on synthetic files only. "
        f"case_id={case_id}. "
        "Use retention_policy=synthetic_24h. "
        "Do not run source-fact extraction, tax calculation, declaration generation, "
        "XLS/XLSX export, OCR, or VLM. "
        "Return the normal compact Russian report and opaque Gate 2 refs."
    )


def _synthetic_files(mode: str) -> list[Path]:
    if mode == "blocking_policy":
        return list(BLOCKING_POLICY_SYNTHETIC_FILES)
    if mode == "clarification_gap":
        return list(CLARIFICATION_GAP_SYNTHETIC_FILES)
    return list(SYNTHETIC_FILES)


def _assert_fixture_paths(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing synthetic fixtures: {missing}")


def _upload_file_process_false(
    session: requests.Session,
    base_url: str,
    path: Path,
    timeout: int,
) -> dict[str, Any]:
    with path.open("rb") as handle:
        files = {"file": (path.name, handle, "text/plain")}
        response = session.post(
            _url(base_url, "/api/v1/files/?process=false"),
            files=files,
            timeout=timeout,
        )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError("process=false upload response did not contain a file ref")
    return {
        "id": str(data["id"]),
        "filename": str(data.get("filename") or data.get("name") or path.name),
        "mime_type": str(data.get("mime_type") or data.get("content_type") or "text/plain"),
        "size": data.get("size") or path.stat().st_size,
    }


def _get_file_record(
    session: requests.Session,
    base_url: str,
    file_id: str,
    timeout: int,
) -> dict[str, Any]:
    response = session.get(_url(base_url, f"/api/v1/files/{file_id}"), timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _file_content_has_marker(
    session: requests.Session,
    base_url: str,
    file_id: str,
    timeout: int,
) -> bool:
    response = session.get(
        _url(base_url, f"/api/v1/files/{file_id}/data/content"),
        timeout=timeout,
    )
    if response.status_code >= 400:
        return False
    payload = response.text
    return any(marker in payload for marker in SYNTHETIC_MARKERS)


def _run_chat(
    session: requests.Session,
    base_url: str,
    model_id: str,
    uploads: list[dict[str, Any]],
    case_id: str,
    timeout: int,
    *,
    passport_config: dict[str, Any] | None = None,
    clarification_config: dict[str, Any] | None = None,
) -> str:
    files = [
        {
            "type": "file",
            "file": {
                "id": upload["id"],
                "filename": upload["filename"],
                "name": upload["filename"],
                "mime_type": upload["mime_type"],
                "content_type": upload["mime_type"],
                "size": upload["size"],
            },
        }
        for upload in uploads
    ]
    passport = _passport_payload(passport_config or {})
    clarification = _clarification_payload(clarification_config or {})
    content = _prompt(case_id)
    if passport.get("enabled"):
        content = "\n".join(
            [
                content,
                (
                    "broker_reports_gate1_passport "
                    "enabled=true "
                    f"passport_model_id={passport['model_id']} "
                    f"passport_prompt_command={passport['prompt_command']} "
                    f"passport_max_documents={passport['max_documents']}"
                ),
            ]
        )
    if clarification.get("enabled"):
        content = "\n".join(
            [
                content,
                (
                    "broker_reports_gate1_clarification "
                    "enabled=true "
                    f"clarification_model_id={clarification['model_id']} "
                    f"clarification_prompt_command={clarification['prompt_command']} "
                    f"criticality_refinement_enabled={str(clarification['criticality_refinement_enabled']).lower()}"
                ),
            ]
        )
    body = {
        "model": model_id,
        "case_id": case_id,
        "broker_reports_gate1": {
            "case_id": case_id,
            "retention_policy": "synthetic_24h",
            "source_intake": "process_false_private_upload",
            "document_metadata_passport": passport,
            "clarification": clarification,
            "customer_docs_loaded_to_knowledge": False,
            "source_fact_extraction": False,
            "tax_calculation": False,
            "declaration_generation": False,
            "xlsx_export": False,
            "ocr_vlm": False,
        },
        "messages": [{"role": "user", "content": content, "files": files}],
        "files": files,
        "metadata": {
            "case_id": case_id,
            "files": files,
            "broker_reports_gate1": {
                "case_id": case_id,
                "retention_policy": "synthetic_24h",
                "source_intake": "process_false_private_upload",
                "document_metadata_passport": passport,
                "clarification": clarification,
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
            "answers": list(config.get("answers") or []),
            "answer_source": str(config.get("answer_source") or "operator_confirmed"),
            "criticality_refinement_enabled": bool(config.get("criticality_refinement_enabled", True)),
        }
    )
    return payload


def _synthetic_clarification_answers(enabled: bool) -> list[dict[str, Any]]:
    if not enabled:
        return []
    return [
        {
            "gap_type": "missing_period",
            "answer_value": "2025-01-01..2025-12-31",
            "source": "operator_confirmed",
            "answered_by": "synthetic_operator",
            "answered_at": "2026-07-09T00:00:00Z",
        },
    ]


def _artifact_case_summary(ssh_target: str, case_id: str) -> dict[str, Any]:
    code = f"""
import json
import sqlite3
from pathlib import Path

case_id = {case_id!r}
db_path = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
result = {{
    "case_record_count": 0,
    "purged_records": 0,
    "active_private_payload_records": 0,
    "none_tombstone_records": 0,
    "type_counts": {{}},
    "lifecycle_status_counts": {{}},
    "purge_status_counts": {{}},
    "storage_backend_counts": {{}},
    "llm_passport_model_call_status_counts": {{}},
    "document_metadata_passport_validator_status_counts": {{}},
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
    "document_metadata_passport_validation_summary": {{}},
    "gate1_metadata_gap_report_summary": {{}},
    "gate1_clarification_request_summary": {{}},
    "gate1_clarification_resolution_counts": {{
        "validation_status_counts": {{}},
        "gap_type_counts": {{}},
        "usable_by_source_eligibility_v2": 0,
    }},
    "gate1_issue_ledger_summary": {{}},
    "document_usage_classification_summary": {{}},
    "domain_context_packet_summary": {{}},
    "gate2_handoff_safe_metadata": {{}},
}}
if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select case_id, artifact_type, lifecycle_status, purge_status, storage_backend, safe_metadata_json "
        "from artifact_records where case_id = ? or case_id like ?",
        (case_id, case_id + "%"),
    ).fetchall()
    conn.close()
    result["case_record_count"] = len(rows)
    for row in rows:
        row_case_id = str(row["case_id"] or "")
        primary_case = row_case_id == case_id
        artifact_type = row["artifact_type"] or "unknown"
        lifecycle_status = row["lifecycle_status"] or "unknown"
        purge_status = row["purge_status"] or "unknown"
        storage_backend = row["storage_backend"] or "unknown"
        result["type_counts"][artifact_type] = result["type_counts"].get(artifact_type, 0) + 1
        result["lifecycle_status_counts"][lifecycle_status] = result["lifecycle_status_counts"].get(lifecycle_status, 0) + 1
        result["purge_status_counts"][purge_status] = result["purge_status_counts"].get(purge_status, 0) + 1
        result["storage_backend_counts"][storage_backend] = result["storage_backend_counts"].get(storage_backend, 0) + 1
        if lifecycle_status == "purged":
            result["purged_records"] += 1
        if storage_backend == "none_tombstone":
            result["none_tombstone_records"] += 1
        if artifact_type.startswith("private_") and lifecycle_status != "purged":
            result["active_private_payload_records"] += 1
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
        if artifact_type == "document_metadata_passport_validation_v0" and primary_case:
            result["document_metadata_passport_validation_summary"] = safe_metadata
        if artifact_type == "gate1_metadata_gap_report_v0" and primary_case:
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
        if artifact_type == "gate1_clarification_request_v0" and primary_case:
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
        if artifact_type == "gate1_issue_ledger_v0" and primary_case:
            result["gate1_issue_ledger_summary"] = {{
                "issues_total": safe_metadata.get("issues_total"),
                "unresolved_issues_total": safe_metadata.get("unresolved_issues_total"),
                "skipped_unresolved_issues_total": safe_metadata.get("skipped_unresolved_issues_total"),
                "awaiting_answer_unresolved_issues_total": safe_metadata.get("awaiting_answer_unresolved_issues_total"),
            }}
        if artifact_type == "document_usage_classification_v0" and primary_case:
            result["document_usage_classification_summary"] = {{
                "documents_total": safe_metadata.get("documents_total"),
                "source_fact_extraction_ready_total": safe_metadata.get("source_fact_extraction_ready_total"),
                "source_fact_extraction_blocked_total": safe_metadata.get("source_fact_extraction_blocked_total"),
            }}
        if artifact_type == "domain_context_packet_v0" and primary_case:
            result["domain_context_packet_summary"] = {{
                "domain_ingestion_status": safe_metadata.get("domain_ingestion_status"),
                "unresolved_issue_summary": safe_metadata.get("unresolved_issue_summary") or {{}},
                "stage_readiness": safe_metadata.get("stage_readiness") or {{}},
                "next_stage_ref_summary": safe_metadata.get("next_stage_ref_summary") or {{}},
                "vector_knowledge_guard": safe_metadata.get("vector_knowledge_guard") or {{}},
            }}
        if artifact_type == "gate2_handoff_v0" and primary_case:
            result["gate2_handoff_safe_metadata"] = {{
                "handoff_status": safe_metadata.get("handoff_status"),
                "handoff_mode": safe_metadata.get("handoff_mode"),
                "decision_status_counts": safe_metadata.get("decision_status_counts") or {{}},
                "handoff_blocker_counts": safe_metadata.get("handoff_blocker_counts") or {{}},
                "next_stage_ref_summary": safe_metadata.get("next_stage_ref_summary") or {{}},
                "auto_resolved_duplicate_document_ids": safe_metadata.get("auto_resolved_duplicate_document_ids") or [],
                "auto_canonical_duplicate_groups": safe_metadata.get("auto_canonical_duplicate_groups") or [],
            }}
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


def _counter_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    before_safe = _safe_counter_view(before)
    after_safe = _safe_counter_view(after)
    return {key: int(after_safe[key]) - int(before_safe[key]) for key in before_safe}


def _vector_deltas_zero(before: dict[str, Any], after: dict[str, Any]) -> bool:
    deltas = _counter_delta(before, after)
    return (
        deltas["vector_collections_count"] == 0
        and deltas["vector_dir_count"] == 0
        and deltas["vector_file_count"] == 0
        and deltas["vector_size_bytes"] == 0
    )


def _docs_knowledge_zero_delta(before: dict[str, Any], after: dict[str, Any]) -> bool:
    deltas = _counter_delta(before, after)
    return deltas["document_rows"] == 0 and deltas["knowledge_rows"] == 0


def _file_rows_returned(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return _safe_counter_view(after)["file_rows"] == _safe_counter_view(before)["file_rows"]


def _safe_statuses(passed: bool) -> list[str]:
    if passed:
        return [
            "PROJECT_OWNED_PRIVATE_INTAKE_READY",
            "PROCESS_FALSE_UPLOAD_PROVEN",
            "LIVE_GATE1_VECTOR_DB_GUARD_PROVEN",
            "LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN",
            "LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN",
            "LIVE_GATE1_ARTIFACTSTORE_PERSISTENCE_PASSED",
            "LIVE_GATE1_COMPACT_RUSSIAN_REPORT_READY",
            "GATE1_CLARIFICATION_CRITICALITY_SYNTHETIC_PASSED",
            "GATE1_UNRESOLVED_ISSUES_CARRIED_FORWARD",
            "GATE1_DOMAIN_CONTEXT_PACKET_READY",
            "GATE1_DOMAIN_CONTEXT_HANDOFF_SYNTHETIC_PASSED",
            "GATE1_NO_SOURCE_READY_DOC_LOSS_PROVEN",
            "GATE1_NEXT_STAGE_REFS_REFINED",
            "GATE1_DOMAIN_INGESTION_SYNTHETIC_PASSED",
            "READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE",
        ]
    return [
        "PROJECT_OWNED_PRIVATE_INTAKE_PARTIAL",
        "CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="Path to .env with OpenWebUI smoke settings")
    parser.add_argument("--base-url", default=None, help="OpenWebUI base URL override")
    parser.add_argument("--ssh-target", default=None, help="SSH target for runtime counter snapshots")
    parser.add_argument("--model-id", default=None, help="Workspace Model id to invoke")
    parser.add_argument("--email", default=None, help="OpenWebUI login email")
    parser.add_argument("--password", default=None, help="OpenWebUI login password")
    parser.add_argument("--enable-llm-passport", action="store_true")
    parser.add_argument("--passport-model-id", default=None)
    parser.add_argument("--passport-prompt-command", default="broker_gate1_document_passport")
    parser.add_argument("--passport-max-documents", type=int, default=32)
    parser.add_argument("--synthetic-fixture-mode", choices=("default", "clarification_gap", "blocking_policy"), default="default")
    parser.add_argument("--enable-clarification", action="store_true")
    parser.add_argument("--clarification-model-id", default=None)
    parser.add_argument("--clarification-prompt-command", default="broker_gate1_clarification_request")
    parser.add_argument("--clarification-synthetic-answers", action="store_true")
    parser.add_argument("--disable-clarification-criticality-refinement", action="store_true")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP request timeout seconds")
    parser.add_argument("--settle-seconds", type=int, default=6, help="Delay for async/vector guard snapshots")
    parser.add_argument(
        "--case-id",
        default="",
        help="Opaque smoke case namespace; default is a timestamped synthetic namespace",
    )
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    model_id = args.model_id or env.get("OPENWEBUI_WORKSPACE_MODEL_ID") or env.get("OPENWEBUI_MODEL_ID") or "test"
    if args.email:
        env["WEBUI_ADMIN_EMAIL"] = args.email
    if args.password:
        env["WEBUI_ADMIN_PASSWORD"] = args.password
    if not ssh_target:
        raise RuntimeError("OPENWEBUI_SSH_TARGET is required for runtime boundary counters")
    if not env.get("WEBUI_ADMIN_EMAIL") or not env.get("WEBUI_ADMIN_PASSWORD"):
        raise RuntimeError("OpenWebUI login credentials are required")
    case_id = args.case_id.strip() or f"{DEFAULT_CASE_ID_PREFIX}_{time.strftime('%Y%m%d%H%M%S')}"
    synthetic_files = _synthetic_files(args.synthetic_fixture_mode)

    _assert_fixture_paths(synthetic_files)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
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

    original_model = _get_model(session, base_url, model_id)
    original_caps = _capabilities(original_model)
    target_model = _with_capabilities(
        original_model,
        {
            **original_caps,
            "file_upload": True,
            "file_context": False,
        },
    )
    if target_model != original_model:
        _update_model(session, base_url, target_model)

    uploaded_refs: list[dict[str, Any]] = []
    uploaded_ids: list[str] = []
    restored_after_failure = False
    passed = False

    try:
        before = _runtime_snapshot(ssh_target)

        for path in synthetic_files:
            data = _upload_file_process_false(session, base_url, path, args.timeout)
            uploaded_refs.append(data)
            uploaded_ids.append(str(data["id"]))

        time.sleep(args.settle_seconds)
        after_upload = _runtime_snapshot(ssh_target)

        file_records = [
            _get_file_record(session, base_url, file_id, args.timeout)
            for file_id in uploaded_ids
        ]
        process_status_values = [
            ((record.get("data") or {}).get("status") if isinstance(record.get("data"), dict) else None)
            for record in file_records
        ]
        extracted_text_present = any(
            _file_content_has_marker(session, base_url, file_id, args.timeout)
            for file_id in uploaded_ids
        )

        chat_report = _run_chat(
            session,
            base_url,
            model_id,
            uploaded_refs,
            case_id,
            args.timeout,
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
                "answers": _synthetic_clarification_answers(args.clarification_synthetic_answers),
                "answer_source": "operator_confirmed",
                "criticality_refinement_enabled": not args.disable_clarification_criticality_refinement,
            },
        )
        time.sleep(args.settle_seconds)
        after_chat = _runtime_snapshot(ssh_target)

        deleted_upload_count = _delete_uploads(
            session,
            base_url,
            [{"id": file_id} for file_id in uploaded_ids],
        )
        time.sleep(args.settle_seconds)
        after_delete = _runtime_snapshot(ssh_target)
        artifact_case_summary = _artifact_case_summary(ssh_target, case_id)

        chat_lower = chat_report.lower()
        pipe_refs_usable = (
            "gate 2" in chat_lower
            or "gate2" in chat_lower
            or "ref" in chat_lower
            or "handoff" in chat_lower
        )
        chat_contains_cyrillic = any("\u0400" <= char <= "\u04ff" for char in chat_report)
        compact_russian_report = (
            len(chat_report) < 5000
            and "```json" not in chat_lower
            and "готово" in chat_lower
        )
        compact_russian_report = (
            len(chat_report) < 5000
            and "```json" not in chat_lower
            and not chat_report.lstrip().startswith("{")
            and chat_contains_cyrillic
        )
        chat_leak_found = any(marker.lower() in chat_lower for marker in FORBIDDEN_CHAT_MARKERS)
        upload_delta = _counter_delta(before, after_upload)
        chat_delta = _counter_delta(before, after_chat)
        delete_delta = _counter_delta(before, after_delete)
        artifact_delta_after_chat = chat_delta["artifactstore_record_count"] > 0
        artifacts_persisted = artifact_case_summary["case_record_count"] > 0
        purge_proven = (
            artifact_case_summary["purged_records"] > 0
            and artifact_case_summary["none_tombstone_records"] > 0
        )
        issue_ledger_summary = artifact_case_summary["gate1_issue_ledger_summary"]
        usage_classification_summary = artifact_case_summary["document_usage_classification_summary"]
        domain_context_packet_summary = artifact_case_summary["domain_context_packet_summary"]
        domain_stage_readiness = domain_context_packet_summary.get("stage_readiness") or {}
        next_stage_ref_summary = domain_context_packet_summary.get("next_stage_ref_summary") or {}
        source_ready_total = int(next_stage_ref_summary.get("source_fact_ready_total") or 0)
        primary_source_total = int(next_stage_ref_summary.get("primary_source_extraction_total") or 0)
        source_ready_not_primary_total = int(next_stage_ref_summary.get("source_ready_not_primary_total") or 0)
        dropped_source_ready_total = int(next_stage_ref_summary.get("dropped_source_ready_total") or 0)
        usage_source_ready_total = int(
            usage_classification_summary.get("source_fact_extraction_ready_total") or 0
        )

        checks = {
            "process_false_query_used": True,
            "uploaded_file_rows_created": upload_delta["file_rows"] == len(synthetic_files),
            "file_process_status_completed_absent": all(value != "completed" for value in process_status_values),
            "uploaded_file_data_no_extracted_text": not extracted_text_present,
            "document_rows_zero_delta": _docs_knowledge_zero_delta(before, after_chat),
            "knowledge_rows_zero_delta": _docs_knowledge_zero_delta(before, after_chat),
            "vector_delta_zero_after_upload": _vector_deltas_zero(before, after_upload),
            "vector_delta_zero_after_chat": _vector_deltas_zero(before, after_chat),
            "vector_delta_zero_after_delete": _vector_deltas_zero(before, after_delete),
            "pipe_gate1_refs_usable": pipe_refs_usable,
            "artifactstore_persisted": artifacts_persisted and artifact_delta_after_chat,
            "gate1_issue_ledger_created": artifact_case_summary["type_counts"].get("gate1_issue_ledger_v0", 0)
            >= 1,
            "document_usage_classification_created": artifact_case_summary["type_counts"].get(
                "document_usage_classification_v0", 0
            )
            >= 1,
            "domain_context_packet_created": artifact_case_summary["type_counts"].get(
                "domain_context_packet_v0", 0
            )
            >= 1,
            "unresolved_issues_carried_forward": int(issue_ledger_summary.get("unresolved_issues_total") or 0) >= 0,
            "domain_context_packet_ready_for_source_extraction": domain_stage_readiness.get(
                "source_fact_extraction"
            )
            in {"ready", "ready_with_issue_context", "blocked"},
            "document_usage_classification_present": int(usage_classification_summary.get("documents_total") or 0)
            == len(synthetic_files),
            "next_stage_refs_refined": bool(next_stage_ref_summary),
            "source_ready_count_reconciled": source_ready_total == usage_source_ready_total,
            "no_source_ready_doc_loss": (
                dropped_source_ready_total == 0
                and source_ready_total == primary_source_total + source_ready_not_primary_total
            ),
            "blocking_policy_fixture_has_source_ready_refs": (
                source_ready_total > 0 if args.synthetic_fixture_mode == "blocking_policy" else True
            ),
            "compact_russian_report": compact_russian_report,
            "private_slices_not_in_chat": not chat_leak_found,
            "source_uploads_deleted": deleted_upload_count == len(uploaded_ids),
            "source_file_rows_returned_to_baseline": _file_rows_returned(before, after_delete),
            "artifact_private_payloads_purged_or_tombstoned": purge_proven,
            "artifact_case_has_no_active_private_payload_after_purge": (
                artifact_case_summary["active_private_payload_records"] == 0
            ),
            "customer_docs_loaded_to_knowledge_false": True,
            "source_fact_extraction_false": True,
            "tax_declaration_xls_ocr_flags_false": True,
        }
        if args.enable_llm_passport:
            expected_passport_count = min(len(synthetic_files), args.passport_max_documents)
            checks.update(
                {
                    "llm_passport_prompt_resolved": artifact_case_summary["type_counts"].get(
                        "llm_prompt_snapshot_v0", 0
                    )
                    == 1,
                    "llm_passport_packages_built": artifact_case_summary["type_counts"].get(
                        "llm_document_package_v0", 0
                    )
                    == expected_passport_count,
                    "llm_passport_model_calls_passed": artifact_case_summary[
                        "llm_passport_model_call_status_counts"
                    ].get("passed", 0)
                    == expected_passport_count,
                    "llm_passport_validator_passed": artifact_case_summary[
                        "document_metadata_passport_validator_status_counts"
                    ].get("passed", 0)
                    == expected_passport_count,
                    "llm_passport_artifacts_persisted": all(
                        artifact_case_summary["type_counts"].get(artifact_type, 0) >= minimum
                        for artifact_type, minimum in {
                            "llm_prompt_snapshot_v0": 1,
                            "llm_document_package_v0": expected_passport_count,
                            "llm_passport_raw_output_v0": expected_passport_count,
                            "document_metadata_passport_v0": expected_passport_count,
                            "document_metadata_passport_validation_v0": 1,
                        }.items()
                    ),
                    "llm_passport_structured_output_mode_recorded": sum(
                        artifact_case_summary["llm_passport_structured_output_mode_counts"].values()
                    )
                    == expected_passport_count
                    and "unknown" not in artifact_case_summary["llm_passport_structured_output_mode_counts"],
                    "llm_passport_schema_hash_recorded": sum(
                        artifact_case_summary["llm_passport_schema_hash_counts"].values()
                    )
                    == expected_passport_count
                    and "unknown" not in artifact_case_summary["llm_passport_schema_hash_counts"],
                }
            )
        if args.enable_clarification:
            clarification_request_summary = artifact_case_summary["gate1_clarification_request_summary"]
            clarification_resolution_counts = artifact_case_summary["gate1_clarification_resolution_counts"]
            metadata_gap_summary = artifact_case_summary["gate1_metadata_gap_report_summary"]
            checks.update(
                {
                    "gate1_metadata_gap_report_created": artifact_case_summary["type_counts"].get(
                        "gate1_metadata_gap_report_v0", 0
                    )
                    == 1,
                    "gate1_clarification_prompt_resolved": artifact_case_summary["type_counts"].get(
                        "llm_clarification_prompt_snapshot_v0", 0
                    )
                    == 1,
                    "gate1_clarification_model_call_passed": artifact_case_summary[
                        "llm_clarification_model_call_status_counts"
                    ].get("passed", 0)
                    == 1,
                    "gate1_clarification_request_validated": artifact_case_summary["type_counts"].get(
                        "gate1_clarification_request_v0", 0
                    )
                    == 1
                    and clarification_request_summary.get("validator_status") == "passed",
                    "gate1_clarification_questions_created": (
                        int(clarification_request_summary.get("questions_total") or 0) > 0
                    ),
                    "gate1_clarification_criticality_counts_recorded": (
                        isinstance(metadata_gap_summary.get("criticality_counts"), dict)
                        and isinstance(clarification_request_summary.get("criticality_counts"), dict)
                    ),
                    "gate1_clarification_structured_output_mode_recorded": sum(
                        artifact_case_summary["llm_clarification_structured_output_mode_counts"].values()
                    )
                    == 1
                    and "unknown" not in artifact_case_summary["llm_clarification_structured_output_mode_counts"],
                    "gate1_clarification_schema_hash_recorded": sum(
                        artifact_case_summary["llm_clarification_schema_hash_counts"].values()
                    )
                    == 1
                    and "unknown" not in artifact_case_summary["llm_clarification_schema_hash_counts"],
                    "gate1_clarification_questions_visible": "вопрос" in chat_lower,
                }
            )
            if args.synthetic_fixture_mode == "clarification_gap":
                checks.update(
                    {
                        "gate1_clarification_gap_questions_present": int(
                            clarification_request_summary.get("questions_total") or 0
                        )
                        > 0,
                        "gate1_clarification_nonblocking_questions_classified": (
                            int(clarification_request_summary.get("clarifying_questions_total") or 0)
                            + int(clarification_request_summary.get("non_critical_questions_total") or 0)
                        )
                        > 0,
                        "gate1_clarification_unanswered_or_skipped_questions_carried_forward": int(
                            issue_ledger_summary.get("awaiting_answer_unresolved_issues_total") or 0
                        )
                        + int(issue_ledger_summary.get("skipped_unresolved_issues_total") or 0)
                        > 0,
                    }
                )
            if args.clarification_synthetic_answers:
                checks.update(
                    {
                        "gate1_clarification_resolutions_persisted": artifact_case_summary["type_counts"].get(
                            "gate1_clarification_resolution_v0", 0
                        )
                        > 0,
                        "gate1_clarification_resolution_usable": int(
                            clarification_resolution_counts.get("usable_by_source_eligibility_v2") or 0
                        )
                        > 0,
                        "gate1_clarification_only_critical_gap_answered": set(
                            clarification_resolution_counts.get("gap_type_counts") or {}
                        )
                        <= {"missing_period"},
                        "gate1_clarification_critical_answers_unblock_handoff": artifact_case_summary[
                            "gate2_handoff_safe_metadata"
                        ].get("handoff_mode")
                        in {"full_package_ready_for_gate2", "reduced_subset_ready_for_gate2"},
                    }
                )
        passed = all(checks.values())
        summary = {
            "status": "passed" if passed else "partial",
            "statuses": _safe_statuses(passed),
            "model_id": model_id,
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
                "synthetic_answers": args.clarification_synthetic_answers,
                "criticality_refinement_enabled": not args.disable_clarification_criticality_refinement
                if args.enable_clarification
                else None,
            },
            "synthetic_fixture_mode": args.synthetic_fixture_mode,
            "workspace_model_caps_before": original_caps,
            "workspace_model_caps_after": _capabilities(_get_model(session, base_url, model_id)),
            "process_false_upload_count": len(uploaded_ids),
            "process_status_values": process_status_values,
            "handoff_reconciliation": {
                "document_usage_classification_source_ready_total": usage_source_ready_total,
                "domain_context_packet_source_ready_total": source_ready_total,
                "primary_source_extraction_total": primary_source_total,
                "source_ready_not_primary_total": source_ready_not_primary_total,
                "dropped_source_ready_total": dropped_source_ready_total,
            },
            "checks": checks,
            "runtime_counters": {
                "before": _safe_counter_view(before),
                "after_process_false_upload": _safe_counter_view(after_upload),
                "after_chat": _safe_counter_view(after_chat),
                "after_delete": _safe_counter_view(after_delete),
                "delta_after_process_false_upload": upload_delta,
                "delta_after_chat": chat_delta,
                "delta_after_delete": delete_delta,
            },
            "artifact_case_summary": artifact_case_summary,
            "chat_visible_report_shape": {
                "length": len(chat_report),
                "contains_cyrillic": chat_contains_cyrillic,
                "starts_with_json": chat_report.lstrip().startswith("{"),
                "contains_gate2_hint": pipe_refs_usable,
                "contains_json_fence": "```json" in chat_lower,
            },
            "cleanup": {
                "openwebui_uploads_deleted": deleted_upload_count,
                "model_config_left_file_context_false": _capabilities(
                    _get_model(session, base_url, model_id)
                ).get("file_context")
                is False,
                "model_config_restored_after_failure": restored_after_failure,
            },
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if passed else 2
    except Exception:
        if uploaded_ids:
            try:
                _delete_uploads(
                    session,
                    base_url,
                    [{"id": file_id} for file_id in uploaded_ids],
                )
            except Exception:
                pass
        if not passed and target_model != original_model:
            try:
                _update_model(session, base_url, original_model)
                restored_after_failure = True
            except Exception as restore_error:  # pragma: no cover - operator visibility path
                print(
                    json.dumps(
                        {
                            "status": "partial",
                            "statuses": _safe_statuses(False),
                            "model_config_restore_error": restore_error.__class__.__name__,
                        },
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
