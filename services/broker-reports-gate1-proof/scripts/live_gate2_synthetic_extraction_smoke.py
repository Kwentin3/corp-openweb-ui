#!/usr/bin/env python3
"""Synthetic full-union Gate 2 proof through the installed OpenWebUI Pipe."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
BUNDLE = (
    ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
FUNCTION_ID = "broker_reports_gate2_source_fact_pipe"

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _select_passport_model,
    _vector_delta_zero,
)
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


EXPECTED_FACT_TYPES = {
    "trade_operation",
    "income",
    "withholding_tax",
    "fee_commission",
    "cash_movement",
    "currency_fx",
    "position_snapshot",
    "document_summary_evidence",
    "unknown_source_row",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--retain", action="store_true")
    parser.add_argument("--audit-case", default=None)
    parser.add_argument("--cleanup-active-synthetic", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    if args.cleanup_active_synthetic:
        cases = _active_synthetic_cases(ssh_target)
        cleanup = [
            {"case_id": case_id, **_purge_case(ssh_target=ssh_target, case_id=case_id)}
            for case_id in cases
        ]
        print(json.dumps({"status": "passed", "cases": cleanup}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.audit_case:
        case_id = (
            _latest_active_synthetic_case(ssh_target)
            if args.audit_case == "latest"
            else args.audit_case
        )
        print(
            json.dumps(
                {"case_id": case_id, "artifact_audit": _audit_case(ssh_target=ssh_target, case_id=case_id)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
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
    case_id = f"synthetic_gate2_full_union_{time.strftime('%Y%m%d%H%M%S')}"

    before = _runtime_snapshot(ssh_target)
    seeded = _seed_synthetic_gate1(
        ssh_target=ssh_target,
        case_id=case_id,
        user_id=str(current_user["id"]),
    )
    chat_content = _run_gate2_chat(
        session=session,
        base_url=base_url,
        dcp_ref=str(seeded["domain_context_packet_ref"]),
        model_id=model_id,
        timeout=args.timeout,
    )
    after = _runtime_snapshot(ssh_target)
    delta = _counter_delta(before, after)
    audit = _audit_case(ssh_target=ssh_target, case_id=case_id)
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("packages") if isinstance(summary.get("packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    facts_by_type = summary.get("facts_by_type") if isinstance(summary.get("facts_by_type"), dict) else {}
    forbidden_chat_markers = [
        "2025-01-01",
        "100.00",
        "SYNTH-INSTRUMENT",
        "raw_output",
        "source_value_index",
        "private_slice_artifact_ref",
    ]
    checks = {
        "function_path_used": audit.get("runtime_factory_path") is True,
        "managed_prompt_used": audit.get("managed_prompt_used") is True,
        "strict_json_schema_used": audit.get("strict_json_schema_raw_outputs_total")
        == audit.get("raw_outputs_total")
        and int(audit.get("raw_outputs_total") or 0) > 0,
        "fallback_not_used": audit.get("fallback_raw_outputs_total") == 0,
        "all_packages_accepted": int(packages.get("total") or 0) > 0
        and packages.get("accepted") == packages.get("total")
        and packages.get("rejected") == 0
        and packages.get("blocked") == 0,
        "all_fact_types_present": set(facts_by_type) == EXPECTED_FACT_TYPES,
        "raw_output_private": audit.get("raw_output_private_total")
        == audit.get("raw_outputs_total"),
        "facts_private": audit.get("source_facts_private_total")
        == audit.get("source_facts_total"),
        "only_validator_passed_facts_persisted": audit.get("source_facts_validated_total")
        == audit.get("source_facts_total"),
        "issue_linked_facts_present": int(summary.get("issue_linked_facts_total") or 0) > 0,
        "coverage_complete": int(coverage.get("selected") or 0)
        == int(coverage.get("fact_covered") or 0) + int(coverage.get("no_fact") or 0)
        and int(coverage.get("pending") or 0) == 0
        and int(coverage.get("rejected") or 0) == 0,
        "safe_russian_summary": "Gate 2" in chat_content
        and "Расчёт налогов, декларация и XLS/XLSX не выполнялись." in chat_content,
        "chat_has_no_private_markers": not any(marker in chat_content for marker in forbidden_chat_markers),
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(delta),
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
    }
    cleanup = {"performed": False, "purged_records_total": 0}
    if not args.retain:
        cleanup = _purge_case(ssh_target=ssh_target, case_id=case_id)
    output = {
        "status": "passed" if checks and all(checks.values()) else "failed",
        "case_id": case_id,
        "model_id": model_id,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "cleanup": cleanup,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def _current_user(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(_url(base_url, "/api/v1/auths/"), timeout=30)
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not value.get("id"):
        raise RuntimeError("gate2_authenticated_user_missing")
    return value


def _seed_synthetic_gate1(
    *,
    ssh_target: str,
    case_id: str,
    user_id: str,
) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from pathlib import Path

bundle_source = {bundle_source!r}
namespace = {{"__name__": "broker_reports_gate2_synthetic_seed_bundle"}}
exec(compile(bundle_source, "<broker_reports_gate2_synthetic_seed_bundle>", "exec"), namespace)

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)

documents = [
    (
        "synthetic_gate2_types_a.csv",
        b"Date,Operation,Amount,Currency,Identifier\\n"
        b"2025-01-01,sell,100.00,USD,SYNTH-INSTRUMENT-A\\n"
        b"2025-01-02,dividend,5.00,USD,SYNTH-INSTRUMENT-B\\n"
        b"2025-01-03,withholding,1.00,USD,SYNTH-INSTRUMENT-B\\n"
        b"2025-01-04,broker_commission,0.50,USD,SYNTH-INSTRUMENT-A\\n",
    ),
    (
        "synthetic_gate2_types_b.csv",
        b"Date,Operation,Amount,Currency,Identifier\\n"
        b"2025-01-05,cash_deposit,25.00,USD,SYNTH-CASH\\n"
        b"2025-01-06,explicit_fx_rate,1.25,USD,SYNTH-FX\\n"
        b"2025-01-07,position_snapshot,10.00,USD,SYNTH-INSTRUMENT-C\\n"
        b"2025-01-08,source_summary,141.75,USD,SYNTH-SUMMARY\\n",
    ),
    (
        "synthetic_gate2_types_c.csv",
        b"Date,Operation,Amount,Currency,Identifier\\n"
        b"2025-01-09,unclassified_source_row,3.00,USD,SYNTH-UNKNOWN\\n",
    ),
]
result = Gate1Normalizer().normalize(
    [
        FileInput.from_bytes(
            private_ref=f"synthetic-gate2-{{index}}",
            filename=name,
            content=content,
            mime_type="text/csv",
        )
        for index, (name, content) in enumerate(documents, start=1)
    ],
    input_context={{"clarification_criticality_refinement_enabled": True}},
)
package = result.package
source_ready = package["domain_context_packet"]["next_stage_refs"]["source_fact_ready_refs"]
if len(source_ready) != 3:
    raise RuntimeError("synthetic_gate2_source_ready_count_invalid")
document_ref = source_ready[0]
slice_ref = next(
    item["slice_id"]
    for item in package["private_normalized_slices"]
    if item["document_id"] == document_ref
)
issue_ref = "issue_synthetic_gate2_confirmation_limit"
package["gate1_issue_ledger"]["entries"].append({{
    "issue_id": issue_ref,
    "normalization_run_id": package["normalization_run"]["run_id"],
    "issue_type": "metadata_gap",
    "target_document_refs": [document_ref],
    "criticality": "clarifying",
    "affected_stage": "source_fact_extraction",
    "blocked_stages": [],
    "stages_that_may_continue": ["source_fact_extraction"],
    "status": "unresolved",
    "unresolved_reason": "synthetic_proof_issue",
    "user_was_asked": False,
    "answer_supplied": False,
    "ask_policy": "do_not_ask",
    "resolution_refs": [],
    "evidence_refs": [slice_ref],
    "blocker_refs": [],
    "reason_codes": ["synthetic_confirmation_limit"],
    "provenance": {{"source_artifact_type": "synthetic_fixture", "source_ref": slice_ref}},
    "created_at": "2026-07-10T00:00:00Z",
    "updated_at": "2026-07-10T00:00:00Z",
    "safe_explanation": "Synthetic unresolved confirmation limit.",
}})
usage_entry = next(
    item for item in package["document_usage_classification"]["entries"]
    if item["document_ref"] == document_ref
)
usage_entry["issue_refs"] = sorted(set(usage_entry["issue_refs"] + [issue_ref]))
usage_entry["warning_issue_refs"] = sorted(set(usage_entry["warning_issue_refs"] + [issue_ref]))
usage_entry["issue_refs_by_stage"].setdefault("source_fact_extraction", []).append(issue_ref)
usage_entry["readiness_by_stage"]["source_fact_extraction"] = "ready_with_issues"
dcp = package["domain_context_packet"]
dcp["unresolved_issue_refs"] = sorted(set(dcp["unresolved_issue_refs"] + [issue_ref]))
dcp["document_issue_refs"].setdefault(document_ref, []).append(issue_ref)
dcp["stage_readiness"]["source_fact_extraction"] = "ready_with_issue_context"
package["gate2_handoff"].setdefault("document_issue_refs", {{}}).setdefault(document_ref, []).append(issue_ref)

context = ArtifactAccessContext(
    user_id={user_id!r},
    normalization_run_id=package["normalization_run"]["run_id"],
    case_id={case_id!r},
    chat_id=f"chat_{{{case_id!r}}}",
    workspace_model_id="broker_reports_gate2_source_fact_pipe",
    allow_private=True,
    require_source_available=True,
)
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
manifest = persist_gate1_result(
    store=store,
    result=result,
    context=context,
    retention_policy=build_retention_policy(mode="api_smoke"),
    source_file_refs=[
        {{"provider": "synthetic", "source_deleted": False}}
        for _ in documents
    ],
)
print(json.dumps({{
    "case_id": {case_id!r},
    "normalization_run_id": context.normalization_run_id,
    "domain_context_packet_ref": manifest.artifact_refs_by_type["domain_context_packet_v0"][0],
    "source_ready_total": len(source_ready),
    "private_slices_total": len(manifest.private_slice_refs),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=90)


def _run_gate2_chat(
    *,
    session: requests.Session,
    base_url: str,
    dcp_ref: str,
    model_id: str,
    timeout: int,
) -> str:
    body = {
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
            "wave": "primary",
            "run_mode": "synthetic",
        },
    }
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _audit_case(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    code = f'''
import json
import sqlite3
from collections import Counter
from pathlib import Path

case_id = {case_id!r}
db_path = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select * from artifact_records where case_id = ? order by created_at asc",
        (case_id,),
    ).fetchall()
    type_counts = Counter(str(row["artifact_type"]) for row in rows)
    summary_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_fact_extraction_summary_v0"]
    if len(summary_rows) != 1:
        raise RuntimeError("synthetic_gate2_summary_count_invalid")
    summary = json.loads(summary_rows[0]["payload_inline_json"])
    raw_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_fact_raw_output_v0"]
    fact_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_facts_v0"]
    validation_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_fact_validation_v0"]
    raw_meta = [json.loads(row["safe_metadata_json"]) for row in raw_rows]
    raw_payloads = [
        json.loads(
            row["payload_inline_json"]
            or (
                Path("/app/backend/data/broker_reports_gate1/payloads")
                / row["payload_ref"]
            ).read_text(encoding="utf-8")
        )
        for row in raw_rows
    ]
    fact_meta = [json.loads(row["safe_metadata_json"]) for row in fact_rows]
    validation_meta = [json.loads(row["safe_metadata_json"]) for row in validation_rows]
    validation_payloads = [json.loads(row["payload_inline_json"]) for row in validation_rows]
    validation_error_code_counts = Counter()
    validation_error_subjects_by_code = {{}}
    for item in validation_meta:
        validation_error_code_counts.update(item.get("error_code_counts") or {{}})
    for item in validation_payloads:
        for error in item.get("errors") or []:
            validation_error_subjects_by_code.setdefault(str(error.get("code")), set()).add(
                str(error.get("subject") or "")
            )
    output = {{
        "case_records_total": len(rows),
        "type_counts": dict(sorted(type_counts.items())),
        "summary": summary,
        "runtime_factory_path": type_counts.get("broker_reports_source_fact_extraction_run_v0", 0) == 1,
        "managed_prompt_used": bool(raw_meta) and all(item.get("prompt_ref") == "broker_reports_gate2_source_fact_prompt_v0" for item in raw_meta),
        "raw_outputs_total": len(raw_rows),
        "raw_output_private_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
        "strict_json_schema_raw_outputs_total": sum(1 for item in raw_meta if item.get("structured_output_mode") == "openwebui_response_format_json_schema" and item.get("response_format_type") == "json_schema"),
        "fallback_raw_outputs_total": sum(1 for item in raw_meta if item.get("fallback_used") is True),
        "synthetic_provider_error_objects": [
            item.get("raw_output")
            for item in raw_payloads
            if item.get("model_call_status") == "failed"
        ],
        "source_facts_total": len(fact_rows),
        "source_facts_private_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
        "source_facts_validated_total": sum(1 for row in fact_rows if row["validation_status"] == "validated" and json.loads(row["safe_metadata_json"]).get("validator_status") == "passed"),
        "validation_total": len(validation_rows),
        "validation_passed_total": sum(1 for row in validation_rows if json.loads(row["safe_metadata_json"]).get("validator_status") == "passed"),
        "validation_error_code_counts": dict(sorted(validation_error_code_counts.items())),
        "validation_error_subjects_by_code": {{
            key: sorted(value)
            for key, value in sorted(validation_error_subjects_by_code.items())
        }},
        "knowledge_backend_records": sum(1 for row in rows if row["storage_backend"] == "openwebui_knowledge"),
        "fact_type_counts_from_records": dict(sorted(Counter({{key: sum(int(meta.get("fact_type_counts", {{}}).get(key, 0)) for meta in fact_meta) for key in set().union(*(set(meta.get("fact_type_counts", {{}})) for meta in fact_meta))}}).items())),
    }}
finally:
    conn.close()
print(json.dumps(output, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=60)


def _latest_active_synthetic_case(ssh_target: str) -> str:
    code = '''
import json
import sqlite3

conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
try:
    row = conn.execute(
        """
        select case_id, max(created_at) as latest_at
        from artifact_records
        where case_id like 'synthetic_gate2_full_union_%'
          and purge_status = 'active'
        group by case_id
        order by latest_at desc
        limit 1
        """
    ).fetchone()
finally:
    conn.close()
if row is None:
    raise RuntimeError("active_synthetic_gate2_case_not_found")
print(json.dumps({"case_id": row[0]}))
'''
    return str(_remote_json(ssh_target, code, timeout=30)["case_id"])


def _active_synthetic_cases(ssh_target: str) -> list[str]:
    code = '''
import json
import sqlite3

conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
try:
    rows = conn.execute(
        """
        select distinct case_id
        from artifact_records
        where case_id like 'synthetic_gate2_full_union_%'
          and purge_status = 'active'
        order by case_id
        """
    ).fetchall()
finally:
    conn.close()
print(json.dumps({"case_ids": [row[0] for row in rows]}))
'''
    return [
        str(item)
        for item in _remote_json(ssh_target, code, timeout=30)["case_ids"]
    ]


def _purge_case(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from pathlib import Path
bundle_source = {bundle_source!r}
namespace = {{"__name__": "broker_reports_gate2_synthetic_purge_bundle"}}
exec(compile(bundle_source, "<broker_reports_gate2_synthetic_purge_bundle>", "exec"), namespace)
from broker_reports_gate1 import ArtifactStoreConfig, ArtifactStoreFactory
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
purged = store.purge_case(case_id={case_id!r})
print(json.dumps({{"performed": True, "purged_records_total": len(purged)}}, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=90)


def _remote_json(ssh_target: str, code: str, *, timeout: int) -> dict[str, Any]:
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
        timeout=timeout,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("gate2_remote_result_invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
