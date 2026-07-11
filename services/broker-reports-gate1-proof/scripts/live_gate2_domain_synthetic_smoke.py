#!/usr/bin/env python3
"""Live synthetic proof for domain-routed Gate 2 extraction and no-RAG guards."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
FUNCTION_ID = "broker_reports_gate2_domain_source_fact_pipe"
EXPECTED_DOMAINS = {
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

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import PROVIDER_STATUS_APPROVED, gate2_provider_profile

from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _select_passport_model,
    _vector_delta_zero,
)
from live_gate2_synthetic_extraction_smoke import (
    _current_user,
    _purge_case,
    _seed_synthetic_gate1,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--provider-profile-id", default="openai_gpt")
    parser.add_argument("--domain", choices=sorted(EXPECTED_DOMAINS), default=None)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--candidate-binding", action="store_true")
    parser.add_argument("--capability-probe", action="store_true")
    parser.add_argument("--retain", action="store_true")
    parser.add_argument("--audit-case", default=None)
    parser.add_argument("--cleanup-case", default=None)
    args = parser.parse_args()
    expected_domains = {args.domain} if args.domain else EXPECTED_DOMAINS

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    if args.cleanup_case:
        cleanup = _purge_case(ssh_target=ssh_target, case_id=args.cleanup_case)
        print(
            json.dumps(
                {"status": "passed", "case_id": args.cleanup_case, "cleanup": cleanup},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.audit_case:
        audit_case = (
            _latest_active_domain_case(ssh_target)
            if args.audit_case == "latest"
            else args.audit_case
        )
        audit = _audit_safe_validation_metadata(
            ssh_target=ssh_target, case_id=audit_case
        )
        audit["candidate_binding_enabled"] = args.candidate_binding
        audit["provider_profile_id"] = args.provider_profile_id
        print(
            json.dumps(
                audit,
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
    case_id = f"synthetic_gate2_domain_{time.strftime('%Y%m%d%H%M%S')}"
    before = _runtime_snapshot(ssh_target)
    seeded = _seed_synthetic_gate1(
        ssh_target=ssh_target,
        case_id=case_id,
        user_id=str(current_user["id"]),
        domain=args.domain,
    )
    cleanup = {"performed": False, "purged_records_total": 0}
    try:
        chat_content = _run_domain_chat(
            session=session,
            base_url=base_url,
            dcp_ref=str(seeded["domain_context_packet_ref"]),
            model_id=model_id,
            candidate_binding_enabled=args.candidate_binding,
            provider_capability_probe=args.capability_probe,
            provider_profile_id=args.provider_profile_id,
            domain=args.domain,
            timeout=args.timeout,
        )
        after = _runtime_snapshot(ssh_target)
        delta = _counter_delta(before, after)
        audit = _audit_case(ssh_target=ssh_target, case_id=case_id)
        safe_attempt_audit = _audit_safe_validation_metadata(
            ssh_target=ssh_target,
            case_id=case_id,
        )
        audit["provider_execution"] = safe_attempt_audit.get(
            "provider_execution",
            {},
        )
        audit["validator_status_counts"] = safe_attempt_audit.get(
            "validator_status_counts",
            {},
        )
        audit["validation_error_code_counts"] = safe_attempt_audit.get(
            "error_code_counts",
            {},
        )
    finally:
        if not args.retain:
            cleanup = _purge_case(ssh_target=ssh_target, case_id=case_id)
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    safe_terminal = (
        "Gate 2" in chat_content
        and "Подтверждённые доменные исходные факты не созданы." in chat_content
        and "Расчёт налогов, декларация и XLS/XLSX не выполнялись." in chat_content
    )
    chat_has_no_private_markers = not any(
        marker in chat_content
        for marker in (
            "2025-01-",
            "SYNTH-",
            "source_value_index",
            "private_slice_artifact_ref",
        )
    )
    profile = gate2_provider_profile(args.provider_profile_id)
    blocker = None
    if int(audit.get("summary_total") or 0) == 0:
        blocker = (
            "gate2_no_strict_structured_provider_available"
            if profile.gate2_status != PROVIDER_STATUS_APPROVED
            else "gate2_domain_runtime_summary_missing"
        )
        checks = {
            "capability_rejected_before_runtime": profile.gate2_status
            != PROVIDER_STATUS_APPROVED
            and audit.get("domain_runtime_factory_path") is False,
            "safe_terminal_without_facts": safe_terminal,
            "no_domain_packages_created": int(audit.get("domain_package_total") or 0)
            == 0,
            "no_raw_outputs_created": int(audit.get("raw_outputs_total") or 0) == 0,
            "no_source_facts_created": int(audit.get("source_facts_total") or 0)
            == 0,
            "chat_has_no_private_markers": chat_has_no_private_markers,
            "document_rows_zero_delta": delta.get("document_rows") == 0,
            "file_rows_zero_delta": delta.get("file_rows") == 0,
            "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
            "vector_delta_zero": _vector_delta_zero(delta),
            "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        }
        status = "blocked" if all(checks.values()) else "failed"
    else:
        provider_execution = (
            audit.get("provider_execution")
            if isinstance(audit.get("provider_execution"), dict)
            else {}
        )
        checks = {
            "domain_runtime_factory_path_used": audit.get("domain_runtime_factory_path")
            is True,
            "all_requested_domain_prompts_used": set(audit.get("prompt_domains") or [])
            == expected_domains,
            "strict_json_schema_only": audit.get("strict_raw_outputs_total")
            == audit.get("raw_outputs_total")
            and int(audit.get("raw_outputs_total") or 0) > 0,
            "fallback_not_used": audit.get("fallback_raw_outputs_total") == 0,
            "provider_schema_audit_present": (
                provider_execution.get("canonical_schema_hash_present_attempts")
                == provider_execution.get("metadata_total")
                and provider_execution.get("adapted_schema_hash_present_attempts")
                == provider_execution.get("metadata_total")
            ),
            "provider_schema_adapter_expected": (
                int(provider_execution.get("schema_transform_total") or 0) > 0
                if args.provider_profile_id == "google_gemini"
                else int(provider_execution.get("schema_transform_total") or 0) == 0
            ),
            "routes_persisted": audit.get("route_total")
            == (1 if args.domain else 3),
            "narrow_packages_persisted": int(packages.get("total") or 0)
            == len(expected_domains)
            and packages.get("accepted") == len(expected_domains)
            and packages.get("rejected") == 0,
            "all_requested_domains_accepted": set(
                (packages.get("accepted_by_domain") or {}).keys()
            )
            == expected_domains,
            "all_requested_fact_types_present": set(
                (summary.get("facts_by_type") or {}).keys()
            )
            == expected_domains,
            "stitch_complete": coverage.get("uncovered_total") == 0
            and coverage.get("conflict_total") == 0
            and audit.get("complete_stitch_total") == (1 if args.domain else 3),
            "issue_links_present": int(audit.get("issue_fact_links_total") or 0)
            > 0,
            "raw_outputs_private": audit.get("raw_output_private_total")
            == audit.get("raw_outputs_total"),
            "source_facts_private": audit.get("source_facts_private_total")
            == audit.get("source_facts_total"),
            "only_validator_passed_persisted": audit.get(
                "source_facts_validated_total"
            )
            == audit.get("source_facts_total"),
            "safe_russian_summary": "Gate 2" in chat_content
            and "Расчёт налогов, декларация и XLS/XLSX не выполнялись."
            in chat_content,
            "chat_has_no_private_markers": chat_has_no_private_markers,
            "document_rows_zero_delta": delta.get("document_rows") == 0,
            "file_rows_zero_delta": delta.get("file_rows") == 0,
            "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
            "vector_delta_zero": _vector_delta_zero(delta),
            "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
            "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work")
            is True,
        }
        status = "passed" if checks and all(checks.values()) else "failed"
    output = {
        "status": status,
        "blocker": blocker,
        "case_id": case_id,
        "model_id": model_id,
        "candidate_binding_enabled": args.candidate_binding,
        "provider_capability_probe": args.capability_probe,
        "provider_profile_id": args.provider_profile_id,
        "requested_domain": args.domain,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "cleanup": cleanup,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] in {"passed", "blocked"} else 1


def _run_domain_chat(
    *,
    session,
    base_url,
    dcp_ref,
    model_id,
    candidate_binding_enabled,
    provider_capability_probe,
    provider_profile_id,
    domain,
    timeout,
) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Выполни контролируемую доменную экстракцию Gate 2.",
                }
            ],
            "stream": False,
            "broker_reports_gate2_domain": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "wave": "primary",
                "run_mode": (
                    "provider_qualification"
                    if provider_capability_probe
                    else "synthetic"
                ),
                "document_batch_limit": 3,
                "source_unit_limit": 3,
                "segmentation_enabled": False,
                "candidate_binding_enabled": candidate_binding_enabled,
                "provider_profile_id": provider_profile_id,
                "provider_capability_probe": provider_capability_probe,
                "domain_allowlist": [domain] if domain else [],
                "max_repair_attempts": 1,
            },
        },
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
root = Path("/app/backend/data/broker_reports_gate1/payloads")
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select * from artifact_records where case_id=? order by created_at asc",
        (case_id,),
    ).fetchall()
    by_type = Counter(str(row["artifact_type"]) for row in rows)
    def payload(row):
        if row["payload_inline_json"]:
            return json.loads(row["payload_inline_json"])
        return json.loads((root / row["payload_ref"]).read_text(encoding="utf-8"))
    summary_rows = [row for row in rows if row["artifact_type"] == "broker_reports_domain_source_fact_extraction_summary_v0"]
    summary = payload(summary_rows[0]) if len(summary_rows) == 1 else {{}}
    raw_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_fact_raw_output_v0"]
    fact_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_facts_v0"]
    stitch_rows = [row for row in rows if row["artifact_type"] == "broker_reports_source_fact_stitch_result_v0"]
    raw_payloads = [payload(row) for row in raw_rows]
    stitch_payloads = [payload(row) for row in stitch_rows]
    prompt_domains = sorted({{str(item.get("extractor_domain")) for item in raw_payloads if item.get("extractor_domain")}})
    output = {{
        "case_records_total": len(rows),
        "summary_total": len(summary_rows),
        "type_counts": dict(sorted(by_type.items())),
        "summary": summary,
        "domain_runtime_factory_path": by_type.get("broker_reports_domain_source_fact_extraction_run_v0", 0) == 1,
        "route_total": by_type.get("broker_reports_source_unit_domain_route_v0", 0),
        "domain_package_total": by_type.get("broker_reports_domain_extraction_package_v0", 0),
        "domain_wrapper_total": by_type.get("broker_reports_domain_source_facts_v0", 0),
        "stitch_total": len(stitch_rows),
        "complete_stitch_total": sum(1 for item in stitch_payloads if (item.get("coverage") or {{}}).get("coverage_status") == "complete"),
        "issue_fact_links_total": sum(len(item.get("issue_fact_linkage") or []) for item in stitch_payloads),
        "prompt_domains": prompt_domains,
        "raw_outputs_total": len(raw_rows),
        "raw_output_private_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
        "strict_raw_outputs_total": sum(1 for item in raw_payloads if item.get("structured_output_mode") == "openwebui_response_format_json_schema" and item.get("response_format_type") == "json_schema"),
        "fallback_raw_outputs_total": sum(1 for item in raw_payloads if item.get("fallback_used") is True),
        "source_facts_total": len(fact_rows),
        "source_facts_private_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
        "source_facts_validated_total": sum(1 for row in fact_rows if row["validation_status"] == "validated"),
        "knowledge_backend_records": sum(1 for row in rows if row["storage_backend"] == "openwebui_knowledge"),
    }}
finally:
    conn.close()
print(json.dumps(output, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=90)


def _audit_safe_validation_metadata(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    code = f'''
import json
import sqlite3
from collections import Counter
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select artifact_type, safe_metadata_json, purge_status from artifact_records where case_id=?",
        ({case_id!r},),
    ).fetchall()
finally:
    conn.close()
validations = [
    json.loads(row["safe_metadata_json"])
    for row in rows
    if row["artifact_type"] == "broker_reports_source_fact_validation_v0"
]
raw_attempts = [
    json.loads(row["safe_metadata_json"])
    for row in rows
    if row["artifact_type"] == "broker_reports_source_fact_raw_output_v0"
]
provider_executions = [
    item.get("provider_execution")
    for item in raw_attempts
    if isinstance(item.get("provider_execution"), dict)
]
errors = Counter()
by_domain = {{}}
for item in validations:
    counts = item.get("error_code_counts") or {{}}
    errors.update(counts)
    domain = str(item.get("extractor_domain") or "unknown")
    by_domain.setdefault(domain, Counter()).update(counts)
print(json.dumps({{
    "case_id": {case_id!r},
    "records_total": len(rows),
    "purge_status_counts": dict(Counter(str(row["purge_status"]) for row in rows)),
    "validations_total": len(validations),
    "validator_status_counts": dict(Counter(str(item.get("validator_status") or "unknown") for item in validations)),
    "error_code_counts": dict(sorted(errors.items())),
    "error_code_counts_by_domain": {{
        key: dict(sorted(value.items())) for key, value in sorted(by_domain.items())
    }},
    "provider_execution": {{
        "attempts_total": len(raw_attempts),
        "metadata_total": len(provider_executions),
        "failure_class_counts": dict(sorted(Counter(
            str(item.get("failure_class"))
            for item in raw_attempts
            if item.get("failure_class")
        ).items())),
        "provider_profile_counts": dict(sorted(Counter(
            str(item.get("provider_profile_id"))
            for item in provider_executions
            if item.get("provider_profile_id")
        ).items())),
        "adapter_counts": dict(sorted(Counter(
            str(item.get("adapter_id"))
            for item in provider_executions
            if item.get("adapter_id")
        ).items())),
        "requested_model_counts": dict(sorted(Counter(
            str(item.get("requested_model_id"))
            for item in provider_executions
            if item.get("requested_model_id")
        ).items())),
        "resolved_model_counts": dict(sorted(Counter(
            str(item.get("resolved_model_id"))
            for item in provider_executions
            if item.get("resolved_model_id")
        ).items())),
        "response_id_present_attempts": sum(
            1 for item in provider_executions
            if item.get("provider_response_id_present") is True
        ),
        "response_id_hash_present_attempts": sum(
            1 for item in provider_executions
            if item.get("provider_response_id_sha256")
        ),
        "canonical_schema_hash_present_attempts": sum(
            1 for item in provider_executions
            if item.get("canonical_request_schema_hash")
        ),
        "adapted_schema_hash_present_attempts": sum(
            1 for item in provider_executions
            if item.get("adapted_request_schema_hash")
        ),
        "canonical_schema_hash_counts": dict(sorted(Counter(
            str(item.get("canonical_request_schema_hash"))
            for item in provider_executions
            if item.get("canonical_request_schema_hash")
        ).items())),
        "adapted_schema_hash_counts": dict(sorted(Counter(
            str(item.get("adapted_request_schema_hash"))
            for item in provider_executions
            if item.get("adapted_request_schema_hash")
        ).items())),
        "schema_transform_total": sum(
            item.get("schema_transform_count") or 0 for item in provider_executions
            if isinstance(item.get("schema_transform_count"), int)
        ),
        "usage_reported_attempts": sum(
            1 for item in provider_executions
            if any(isinstance(item.get(field), int) for field in (
                "input_tokens", "output_tokens", "total_tokens"
            ))
        ),
        "input_tokens_total": sum(
            item.get("input_tokens") or 0 for item in provider_executions
            if isinstance(item.get("input_tokens"), int)
        ),
        "output_tokens_total": sum(
            item.get("output_tokens") or 0 for item in provider_executions
            if isinstance(item.get("output_tokens"), int)
        ),
        "total_tokens_total": sum(
            item.get("total_tokens") or 0 for item in provider_executions
            if isinstance(item.get("total_tokens"), int)
        ),
        "duration_observed_attempts": sum(
            1 for item in provider_executions
            if isinstance(item.get("duration_ms"), int)
        ),
        "duration_total_ms": sum(
            item.get("duration_ms") or 0 for item in provider_executions
            if isinstance(item.get("duration_ms"), int)
        ),
    }},
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=60)


def _latest_active_domain_case(ssh_target: str) -> str:
    code = '''
import json
import sqlite3

conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
try:
    row = conn.execute(
        """
        select case_id, max(created_at) as latest_at
        from artifact_records
        where case_id like 'synthetic_gate2_domain_%'
          and purge_status = 'active'
        group by case_id
        order by latest_at desc
        limit 1
        """
    ).fetchone()
finally:
    conn.close()
if row is None:
    raise RuntimeError("active_synthetic_gate2_domain_case_not_found")
print(json.dumps({"case_id": row[0]}))
'''
    return str(_remote_json(ssh_target, code, timeout=30)["case_id"])


def _remote_json(ssh_target: str, code: str, *, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no", ssh_target,
            "docker", "exec", "-i", "openwebui", "python", "-",
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
        raise RuntimeError("gate2_domain_remote_result_invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
