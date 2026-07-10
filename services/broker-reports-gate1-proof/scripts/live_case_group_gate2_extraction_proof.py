#!/usr/bin/env python3
"""Controlled Gate 2 extraction proof over the existing process=false case."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
FUNCTION_ID = "broker_reports_gate2_source_fact_pipe"
DEFAULT_CASE_ID = "customer_case_group_002_process_false_gate1_20260709175007"

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _select_passport_model,
    _vector_delta_zero,
)
from live_gate2_synthetic_extraction_smoke import _current_user, _remote_json
from live_no_rag_source_intake_smoke import (
    _base_url,
    _default_ssh_target,
    _extract_content,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
    _signin,
    _url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--wave", choices=("primary", "non_primary"), default="primary")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--batch-start", type=int, default=0)
    parser.add_argument("--batch-limit", type=int, default=None)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    if args.status_only:
        print(
            json.dumps(
                {"case_id": args.case_id, "run_statuses": _case_run_statuses(ssh_target=ssh_target, case_id=args.case_id)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.audit_only:
        audit = _audit_new_run(
            ssh_target=ssh_target,
            case_id=args.case_id,
            previous_run_refs=[],
        )
        print(json.dumps({"case_id": args.case_id, "artifact_audit": audit}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    current_user = _current_user(session, base_url)
    model_id = (
        args.model_id
        or env.get("OPENWEBUI_GATE2_MODEL_ID")
        or env.get("OPENWEBUI_PASSPORT_MODEL_ID")
        or _select_passport_model(session, base_url)
    )
    manifest = _case_manifest(
        ssh_target=ssh_target,
        case_id=args.case_id,
        authenticated_user_id=str(current_user["id"]),
    )
    if manifest.get("owner_matches_authenticated_user") is not True:
        raise RuntimeError("case_owner_does_not_match_authenticated_user")

    before = _runtime_snapshot(ssh_target)
    chat_content = _run_gate2_chat(
        session=session,
        base_url=base_url,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        model_id=model_id,
        wave=args.wave,
        batch_start=args.batch_start,
        batch_limit=args.batch_limit,
        timeout=args.timeout,
    )
    after = _runtime_snapshot(ssh_target)
    delta = _counter_delta(before, after)
    audit = _audit_new_run(
        ssh_target=ssh_target,
        case_id=args.case_id,
        previous_run_refs=list(manifest.get("existing_gate2_run_refs") or []),
    )
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("packages") if isinstance(summary.get("packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    decisions = audit.get("source_decisions") if isinstance(audit.get("source_decisions"), dict) else {}
    checks = {
        "owner_scope_match": manifest.get("owner_matches_authenticated_user") is True,
        "dcp_is_runtime_input": audit.get("dcp_is_runtime_input") is True,
        "all_source_ready_refs_decided": decisions.get("total") == 15
        and decisions.get("unknown_decision_total") == 0,
        "wave_selected_refs_present": int(decisions.get("selected_total") or 0) > 0,
        "terminal_completed": summary.get("terminal_status") == "completed",
        "all_packages_accepted": int(packages.get("total") or 0) > 0
        and packages.get("accepted") == packages.get("total")
        and packages.get("rejected") == 0
        and packages.get("blocked") == 0,
        "strict_json_schema_all_calls": audit.get("strict_json_schema_raw_outputs_total")
        == audit.get("raw_outputs_total")
        and int(audit.get("raw_outputs_total") or 0) > 0,
        "fallback_not_used": audit.get("fallback_raw_outputs_total") == 0,
        "raw_outputs_private": audit.get("private_raw_outputs_total")
        == audit.get("raw_outputs_total"),
        "facts_private_and_validated": audit.get("private_source_facts_total")
        == audit.get("source_facts_total")
        == audit.get("validated_source_facts_total"),
        "accepted_packages_have_passed_validation": audit.get("passed_validations_total")
        == packages.get("accepted"),
        "coverage_accounted": int(coverage.get("selected") or 0)
        == int(coverage.get("fact_covered") or 0) + int(coverage.get("no_fact") or 0)
        and int(coverage.get("pending") or 0) == 0
        and int(coverage.get("rejected") or 0) == 0,
        "issue_refs_reachable": int(audit.get("decision_issue_refs_total") or 0) > 0,
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(delta),
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
        "chat_safe": "Gate 2" in chat_content
        and "Расчёт налогов, декларация и XLS/XLSX не выполнялись." in chat_content
        and not any(
            marker in chat_content
            for marker in ("raw_output", "private_slice_artifact_ref", "source_value_index")
        ),
        "full_source_slices": int(summary.get("truncated_source_units_total") or 0) == 0,
        "gate3_handoff_ready": summary.get("gate3_handoff_ready") is True,
    }
    execution_check_names = set(checks) - {"full_source_slices", "gate3_handoff_ready"}
    execution_passed = all(checks[name] for name in execution_check_names)
    status = "passed" if execution_passed and checks["full_source_slices"] and checks["gate3_handoff_ready"] else (
        "partial_truncated_source_slices" if execution_passed else "failed"
    )
    output = {
        "status": status,
        "case_id": args.case_id,
        "wave": args.wave,
        "batch_start": args.batch_start,
        "batch_limit": args.batch_limit,
        "model_id": model_id,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "non_primary_allowed": status == "passed" and args.wave == "primary",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status in {"passed", "partial_truncated_source_slices"} else 1


def _run_gate2_chat(
    *,
    session: requests.Session,
    base_url: str,
    dcp_ref: str,
    model_id: str,
    wave: str,
    batch_start: int,
    batch_limit: int | None,
    timeout: int,
) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Выполни контролируемое извлечение исходных фактов Gate 2.",
                }
            ],
            "stream": False,
            "broker_reports_gate2": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "wave": wave,
                "run_mode": "customer",
                "document_batch_start": batch_start,
                "document_batch_limit": batch_limit,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _case_manifest(
    *,
    ssh_target: str,
    case_id: str,
    authenticated_user_id: str,
) -> dict[str, Any]:
    code = f'''
import json
import sqlite3

case_id = {case_id!r}
authenticated_user_id = {authenticated_user_id!r}
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select * from artifact_records where case_id = ? and purge_status = 'active'",
        (case_id,),
    ).fetchall()
finally:
    conn.close()
dcp_rows = [row for row in rows if row["artifact_type"] == "domain_context_packet_v0"]
if len(dcp_rows) != 1:
    raise RuntimeError("case_group_gate2_dcp_count_invalid")
dcp = dcp_rows[0]
print(json.dumps({{
    "domain_context_packet_ref": dcp["artifact_id"],
    "owner_matches_authenticated_user": dcp["user_id"] == authenticated_user_id,
    "existing_gate2_run_refs": [
        row["artifact_id"]
        for row in rows
        if row["artifact_type"] == "broker_reports_source_fact_extraction_run_v0"
    ],
}}, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=60)


def _audit_new_run(
    *,
    ssh_target: str,
    case_id: str,
    previous_run_refs: list[str],
) -> dict[str, Any]:
    code = f'''
import json
import sqlite3
from collections import Counter
from pathlib import Path

case_id = {case_id!r}
previous_run_refs = set({previous_run_refs!r})
payload_root = Path("/app/backend/data/broker_reports_gate1/payloads")
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select * from artifact_records where case_id = ? and purge_status = 'active'",
        (case_id,),
    ).fetchall()
finally:
    conn.close()
by_ref = {{str(row["artifact_id"]): row for row in rows}}

def payload(row):
    if row["payload_inline_json"]:
        return json.loads(row["payload_inline_json"])
    return json.loads((payload_root / row["payload_ref"]).read_text(encoding="utf-8"))

new_runs = [
    row for row in rows
    if row["artifact_type"] == "broker_reports_source_fact_extraction_run_v0"
    and row["artifact_id"] not in previous_run_refs
]
if len(new_runs) != 1:
    raise RuntimeError("case_group_gate2_new_run_count_invalid")
run = payload(new_runs[0])
summary = payload(by_ref[str(run["summary_ref"])])
raw_rows = [by_ref[ref] for ref in run.get("raw_output_refs") or []]
fact_rows = [by_ref[ref] for ref in run.get("source_facts_refs") or []]
validation_rows = [by_ref[ref] for ref in run.get("validation_refs") or []]
package_rows = [by_ref[ref] for ref in run.get("package_refs") or []]
raw_meta = [json.loads(row["safe_metadata_json"]) for row in raw_rows]
fact_meta = [json.loads(row["safe_metadata_json"]) for row in fact_rows]
validation_meta = [json.loads(row["safe_metadata_json"]) for row in validation_rows]
decisions = run.get("source_ready_ref_decisions") or []
decision_counts = Counter(str(item.get("decision") or "unknown") for item in decisions)
selected_total = sum(1 for key, value in decision_counts.items() if key.startswith("selected_") for _ in range(value))
known_decisions = {{"selected_primary", "selected_secondary", "selected_duplicate_or_non_primary", "deferred_context_only", "blocked_with_reason"}}
fact_type_counts = Counter()
for meta in fact_meta:
    fact_type_counts.update(meta.get("fact_type_counts") or {{}})
validation_error_counts = Counter()
for meta in validation_meta:
    validation_error_counts.update(meta.get("error_code_counts") or {{}})
all_run_rows = [*raw_rows, *fact_rows, *validation_rows, *package_rows, new_runs[0], by_ref[str(run["summary_ref"])]]
print(json.dumps({{
    "extraction_run_id": run.get("extraction_run_id"),
    "summary": summary,
    "dcp_is_runtime_input": bool((run.get("input_refs") or {{}}).get("domain_context_packet_ref")),
    "source_decisions": {{
        "total": len(decisions),
        "selected_total": selected_total,
        "deferred_total": decision_counts.get("deferred_context_only", 0),
        "blocked_total": decision_counts.get("blocked_with_reason", 0),
        "unknown_decision_total": sum(value for key, value in decision_counts.items() if key not in known_decisions),
        "counts": dict(sorted(decision_counts.items())),
    }},
    "decision_issue_refs_total": sum(len(item.get("issue_refs") or []) for item in decisions),
    "raw_outputs_total": len(raw_rows),
    "private_raw_outputs_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "strict_json_schema_raw_outputs_total": sum(1 for meta in raw_meta if meta.get("structured_output_mode") == "openwebui_response_format_json_schema" and meta.get("response_format_type") == "json_schema"),
    "fallback_raw_outputs_total": sum(1 for meta in raw_meta if meta.get("fallback_used") is True),
    "repair_raw_outputs_total": sum(1 for meta in raw_meta if int(meta.get("repair_attempt_count") or 0) == 1),
    "source_facts_total": len(fact_rows),
    "private_source_facts_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "validated_source_facts_total": sum(1 for row in fact_rows if row["validation_status"] == "validated" and json.loads(row["safe_metadata_json"]).get("validator_status") == "passed"),
    "passed_validations_total": sum(1 for meta in validation_meta if meta.get("validator_status") == "passed"),
    "validation_error_code_counts": dict(sorted(validation_error_counts.items())),
    "fact_type_counts": dict(sorted(fact_type_counts.items())),
    "knowledge_backend_records": sum(1 for row in all_run_rows if row["storage_backend"] == "openwebui_knowledge"),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _case_run_statuses(*, ssh_target: str, case_id: str) -> list[dict[str, Any]]:
    code = f'''
import json
import sqlite3

case_id = {case_id!r}
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        """
        select payload_inline_json, created_at, updated_at
        from artifact_records
        where case_id = ?
          and artifact_type = 'broker_reports_source_fact_extraction_run_v0'
          and purge_status = 'active'
        order by created_at asc
        """,
        (case_id,),
    ).fetchall()
finally:
    conn.close()
output = []
for row in rows:
    payload = json.loads(row["payload_inline_json"])
    output.append({{
        "run_status": payload.get("run_status"),
        "wave": (payload.get("selection_policy") or {{}}).get("wave"),
        "package_refs_total": len(payload.get("package_refs") or []),
        "raw_output_refs_total": len(payload.get("raw_output_refs") or []),
        "source_facts_refs_total": len(payload.get("source_facts_refs") or []),
        "validation_refs_total": len(payload.get("validation_refs") or []),
        "has_summary": bool(payload.get("summary_ref")),
        "has_finished_at": bool(payload.get("finished_at")),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }})
print(json.dumps({{"run_statuses": output}}, ensure_ascii=False))
'''
    return list(_remote_json(ssh_target, code, timeout=60)["run_statuses"])


if __name__ == "__main__":
    raise SystemExit(main())
