#!/usr/bin/env python3
"""Preflight and run exactly one smallest real typed segmented Gate 2 vertical."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)
FUNCTION_ID = "broker_reports_gate2_domain_source_fact_pipe"
DEFAULT_CASE_ID = "customer_case_group_002_process_false_gate1_20260709175007"
PREFERRED_DOMAINS = (
    "position_snapshot",
    "cash_movement",
    "fee_commission",
    "income",
    "withholding_tax",
    "trade_operation",
    "currency_fx",
    "document_summary_evidence",
)

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_gate2_extraction_proof import _case_manifest
from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _select_passport_model,
    _vector_delta_zero,
)
from live_gate2_synthetic_extraction_smoke import _current_user
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
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--audit-latest",
        action="store_true",
        help="Audit the latest persisted typed run without another model call.",
    )
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    current_user = _current_user(session, base_url)
    manifest = _case_manifest(
        ssh_target=ssh_target,
        case_id=args.case_id,
        authenticated_user_id=str(current_user["id"]),
    )
    if manifest.get("owner_matches_authenticated_user") is not True:
        raise RuntimeError("case_owner_does_not_match_authenticated_user")
    preflight = _select_typed_segment_target(
        ssh_target=ssh_target,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        user_id=str(current_user["id"]),
    )
    if args.preflight_only:
        print(
            json.dumps(
                {"status": "passed" if preflight.get("eligible") else "blocked", "preflight": preflight},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if preflight.get("eligible") else 2
    if preflight.get("eligible") is not True:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker": "no_high_confidence_typed_derived_unit",
                    "preflight": preflight,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    if args.audit_latest:
        run_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
        if not run_refs:
            raise RuntimeError("gate2_typed_vertical_existing_run_missing")
        previous_run_refs = run_refs[:-1]
        model_id = "existing_run_not_reinvoked"
        before = _runtime_snapshot(ssh_target)
        after = _runtime_snapshot(ssh_target)
        chat_content = "Gate 2 existing typed run audit."
    else:
        model_id = (
            args.model_id
            or env.get("OPENWEBUI_GATE2_MODEL_ID")
            or env.get("OPENWEBUI_PASSPORT_MODEL_ID")
            or _select_passport_model(session, base_url)
        )
        previous_run_refs = _domain_run_refs(
            ssh_target=ssh_target, case_id=args.case_id
        )
        before = _runtime_snapshot(ssh_target)
        chat_content = _run_chat(
            session=session,
            base_url=base_url,
            dcp_ref=str(manifest["domain_context_packet_ref"]),
            model_id=model_id,
            target=preflight["selected_target"],
            timeout=args.timeout,
        )
        after = _runtime_snapshot(ssh_target)
    delta = _counter_delta(before, after)
    audit = _audit_new_typed_run(
        ssh_target=ssh_target,
        case_id=args.case_id,
        previous_run_refs=previous_run_refs,
    )
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    target = preflight["selected_target"]
    selected_domain = str(target["domain"])
    forbidden_errors = {
        "source_fact_provenance_missing",
        "source_fact_completeness_overstated",
        "source_fact_coverage_gap",
        "source_fact_issue_not_carried",
    }
    error_codes = set((audit.get("validation_error_code_counts") or {}).keys())
    checks = {
        "one_primary_document_parent_and_segment": target.get("document_batch_limit") == 1
        and target.get("source_unit_limit") == 1
        and target.get("source_segment_limit") == 1,
        "typed_high_confidence_target": target.get("confidence") == "high"
        and selected_domain != "unknown_source_row"
        and 1 <= len(target.get("domains") or []) <= 2,
        "derived_unit_complete_parent_resolved": target.get("source_slice_truncated") is False
        and target.get("parent_source_slice_truncated") is False
        and target.get("parent_remainder_status")
        == "not_applicable_parent_complete",
        "domain_runtime_terminal": summary.get("terminal_status") == "completed",
        "one_segmentation_plan_and_private_derived_unit": audit.get("segmentation_plan_total") == 1
        and audit.get("derived_source_unit_total") == 1
        and audit.get("private_derived_source_unit_total") == 1,
        "one_domain_package_accepted": packages.get("total") == 1
        and packages.get("accepted") == 1
        and packages.get("rejected") == 0,
        "validator_passed_typed_fact": int((summary.get("facts_by_type") or {}).get(selected_domain, 0)) > 0
        and int(summary.get("typed_facts_total") or 0) > 0
        and int((summary.get("facts_by_type") or {}).get("unknown_source_row", 0)) == 0,
        "complete_conflict_free_coverage": coverage.get("selected_total") == target.get("selected_refs_total")
        and coverage.get("uncovered_total") == 0
        and coverage.get("conflict_total") == 0
        and audit.get("complete_stitch_total") == 1,
        "no_core_validation_errors": not (forbidden_errors & error_codes),
        "strict_private_outputs": audit.get("strict_raw_outputs_total") == audit.get("raw_outputs_total") == 1
        and audit.get("fallback_raw_outputs_total") == 0
        and audit.get("private_raw_outputs_total") == 1
        and audit.get("private_source_facts_total") == audit.get("source_facts_total") == 1
        and audit.get("validated_source_facts_total") == 1,
        "issue_refs_carried": int(target.get("issue_refs_total") or 0) == 0
        or int(audit.get("issue_fact_links_total") or 0) > 0,
        "parent_coverage_partitioned": audit.get("all_parent_selected_refs_partitioned") is True
        and audit.get("segmentation_unaccounted_total") == 0
        and audit.get("segmentation_duplicate_total") == 0,
        "limited_primary_expansion_ready_not_executed": summary.get(
            "ready_for_primary_expansion"
        )
        is True
        and preflight.get("primary_expansion_run") is False,
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(delta),
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
        "chat_safe": "Gate 2" in chat_content
        and not any(
            marker in chat_content
            for marker in (
                "raw_output",
                "private_slice_artifact_ref",
                "source_value_index",
                "openwebui_file_id",
            )
        ),
    }
    status = "passed" if checks and all(checks.values()) else "failed"
    output = {
        "status": status,
        "case_id": args.case_id,
        "model_id": model_id,
        "preflight": preflight,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "limited_primary_expansion_ready": summary.get(
            "ready_for_primary_expansion"
        )
        is True,
        "primary_expansion_executed": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _select_typed_segment_target(
    *, ssh_target: str, dcp_ref: str, user_id: str
) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from collections import Counter
from pathlib import Path
namespace = {{"__name__": "case_group_gate2_typed_segmentation_preflight"}}
exec(compile({bundle_source!r}, "<case_group_gate2_typed_segmentation_preflight>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    Gate2InputReadinessFactory, Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
)
preferred = {PREFERRED_DOMAINS!r}
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
record = store.get_record_unchecked({dcp_ref!r})
if record is None:
    raise RuntimeError("gate2_typed_vertical_dcp_missing")
context = ArtifactAccessContext(
    user_id={user_id!r}, normalization_run_id=record.normalization_run_id,
    case_id=record.case_id, chat_id=record.chat_id,
    workspace_model_id=record.workspace_model_id,
    allow_private=True, require_source_available=True,
)
readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
    domain_context_packet_ref=record.artifact_id, context=context,
)
primary = [
    item for item in readiness.packages
    if "primary_source_extraction_refs" in set(item.get("source_bucket_roles") or [])
]
document_refs = sorted({{str(item.get("document_ref") or "") for item in primary}})
parent_units_total = 0
parent_truncated_total = 0
derived_units_total = 0
derived_truncated_total = 0
typed_candidate_units_total = 0
high_confidence_typed_units_total = 0
candidates = []
domain_counts = Counter()
for document_index, document_ref in enumerate(document_refs):
    units = [item for item in primary if str(item.get("document_ref") or "") == document_ref]
    for unit_index, base in enumerate(units):
        parent_units_total += 1
        parent_truncated = bool((base.get("source_unit") or {{}}).get("source_slice_truncated"))
        parent_truncated_total += int(parent_truncated)
        parent_route = Gate2SourceUnitRouterFactory().create().route(base)
        segmentation = Gate2SourceUnitSegmenterFactory().create().segment(
            base_package=base, parent_route=parent_route,
        )
        derived_units_total += len(segmentation.derived_packages)
        for segment_index, package in enumerate(segmentation.derived_packages):
            unit = package.get("source_unit") or {{}}
            derived_truncated_total += int(unit.get("source_slice_truncated") is True)
            route = Gate2SourceUnitRouterFactory().create().route(package)
            entries = [item for item in route["route_entries"] if item["route_kind"] == "model_candidate"]
            domains = sorted({{domain for item in entries for domain in item["candidate_domains"]}})
            typed = bool(entries) and 1 <= len(domains) <= 2 and "unknown_source_row" not in domains
            high = typed and all(item.get("confidence") == "high" for item in entries)
            typed_candidate_units_total += int(typed)
            high_confidence_typed_units_total += int(high)
            if not high:
                continue
            primary_domains = sorted({{str(item.get("primary_suggested_domain") or "") for item in entries}})
            if len(primary_domains) != 1:
                continue
            domain = primary_domains[0]
            domain_counts[domain] += 1
            plan_coverage = segmentation.plan.get("coverage") or {{}}
            candidates.append({{
                "eligible": True,
                "selection_kind": "typed_high_confidence_derived_unit",
                "document_batch_start": document_index,
                "document_batch_limit": 1,
                "source_unit_start": unit_index,
                "source_unit_limit": 1,
                "source_segment_start": segment_index,
                "source_segment_limit": 1,
                "domain": domain,
                "domains": domains,
                "confidence": "high",
                "selected_refs_total": len(route.get("selected_source_refs") or []),
                "model_candidates_total": len(entries),
                "issue_refs_total": len(route.get("issue_refs") or []),
                "source_slice_truncated": bool(unit.get("source_slice_truncated")),
                "parent_source_slice_truncated": bool(unit.get("parent_source_slice_truncated")),
                "parent_remainder_status": unit.get("parent_remainder_status"),
                "parent_selected_total": int(plan_coverage.get("parent_selected_total") or 0),
                "parent_accounted_total": int(plan_coverage.get("derived_accounted_total") or 0),
                "parent_refs_partitioned": plan_coverage.get("all_parent_selected_refs_partitioned") is True,
                "safe_reason_codes": [
                    "contiguous_uniform_domain_cluster",
                    "all_candidates_high_confidence",
                    "derived_unit_complete_within_parent_projection",
                    (
                        "parent_remainder_not_applicable_complete"
                        if unit.get("parent_remainder_status")
                        == "not_applicable_parent_complete"
                        else "parent_remainder_explicitly_pending"
                    ),
                ],
            }})
ranked = sorted(
    candidates,
    key=lambda item: (
        preferred.index(item["domain"]) if item["domain"] in preferred else len(preferred),
        item["selected_refs_total"],
        item["document_batch_start"],
        item["source_unit_start"],
        item["source_segment_start"],
    ),
)
selected = ranked[0] if ranked else None
print(json.dumps({{
    "eligible": selected is not None,
    "primary_documents_total": len(document_refs),
    "source_units_total": parent_units_total,
    "truncated_source_units_before": parent_truncated_total,
    "derived_source_units_total": derived_units_total,
    "truncated_source_units_after": derived_truncated_total,
    "candidate_typed_units_total": typed_candidate_units_total,
    "high_confidence_typed_units_total": high_confidence_typed_units_total,
    "high_confidence_units_by_domain": dict(sorted(domain_counts.items())),
    "selected_target": selected,
    "non_primary_extraction_run": False,
    "primary_expansion_run": False,
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=240)


def _run_chat(*, session, base_url, dcp_ref, model_id, target, timeout) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Выполни одну минимальную типизированную вертикаль Gate 2.",
                }
            ],
            "stream": False,
            "broker_reports_gate2_domain": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "wave": "primary",
                "run_mode": "customer",
                "document_batch_start": target["document_batch_start"],
                "document_batch_limit": 1,
                "source_unit_start": target["source_unit_start"],
                "source_unit_limit": 1,
                "segmentation_enabled": True,
                "source_segment_start": target["source_segment_start"],
                "source_segment_limit": 1,
                "domain_allowlist": target["domains"],
                "max_repair_attempts": 1,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _domain_run_refs(*, ssh_target: str, case_id: str) -> list[str]:
    code = f'''
import json, sqlite3
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
try:
    rows = conn.execute(
        "select artifact_id from artifact_records where case_id=? and artifact_type='broker_reports_domain_source_fact_extraction_run_v0' and purge_status='active' order by rowid",
        ({case_id!r},),
    ).fetchall()
finally:
    conn.close()
print(json.dumps({{"refs": [str(row[0]) for row in rows]}}))
'''
    return [
        str(item)
        for item in _remote_json(ssh_target, code, timeout=60)["refs"]
    ]


def _audit_new_typed_run(
    *, ssh_target: str, case_id: str, previous_run_refs: list[str]
) -> dict[str, Any]:
    code = f'''
import json, sqlite3
from collections import Counter
from pathlib import Path
root = Path("/app/backend/data/broker_reports_gate1/payloads")
previous = set({previous_run_refs!r})
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute("select * from artifact_records where case_id=? and purge_status='active'", ({case_id!r},)).fetchall()
finally:
    conn.close()
by_ref = {{str(row["artifact_id"]): row for row in rows}}
def payload(row):
    return json.loads(row["payload_inline_json"]) if row["payload_inline_json"] else json.loads((root / row["payload_ref"]).read_text(encoding="utf-8"))
runs = [row for row in rows if row["artifact_type"] == "broker_reports_domain_source_fact_extraction_run_v0" and row["artifact_id"] not in previous]
if len(runs) != 1:
    raise RuntimeError("gate2_typed_vertical_new_run_count_invalid")
run = payload(runs[0])
summary = payload(by_ref[str(run["summary_ref"])])
raw_rows = [by_ref[ref] for ref in run.get("raw_output_refs") or []]
fact_rows = [by_ref[ref] for ref in run.get("source_facts_refs") or []]
validation_rows = [by_ref[ref] for ref in run.get("validation_refs") or []]
stitch_rows = [by_ref[ref] for ref in run.get("stitch_result_refs") or []]
route_rows = [by_ref[ref] for ref in run.get("route_refs") or []]
plan_rows = [by_ref[ref] for ref in run.get("segmentation_plan_refs") or []]
derived_rows = [by_ref[ref] for ref in run.get("derived_source_unit_refs") or []]
raw_payloads = [payload(row) for row in raw_rows]
stitches = [payload(row) for row in stitch_rows]
validations = [payload(row) for row in validation_rows]
plans = [payload(row) for row in plan_rows]
derived = [payload(row) for row in derived_rows]
error_counts = Counter(str(error.get("code") or "unknown") for item in validations for error in item.get("errors") or [])
plan_coverage = plans[0].get("coverage") if len(plans) == 1 else {{}}
print(json.dumps({{
    "summary": summary,
    "segmentation_plan_total": len(plan_rows),
    "derived_source_unit_total": len(derived_rows),
    "private_derived_source_unit_total": sum(1 for row in derived_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "derived_truncated_total": sum(1 for item in derived if (item.get("source_unit") or {{}}).get("source_slice_truncated") is True),
    "parent_truncated_total": sum(1 for item in derived if (item.get("source_unit") or {{}}).get("parent_source_slice_truncated") is True),
    "parent_remainder_status": plan_coverage.get("parent_remainder_status"),
    "all_parent_selected_refs_partitioned": plan_coverage.get("all_parent_selected_refs_partitioned"),
    "segmentation_unaccounted_total": len(plan_coverage.get("unaccounted_source_refs") or []),
    "segmentation_duplicate_total": len(plan_coverage.get("duplicate_source_refs") or []),
    "route_total": len(route_rows),
    "route_issue_refs_total": sum(len(payload(row).get("issue_refs") or []) for row in route_rows),
    "stitch_total": len(stitch_rows),
    "complete_stitch_total": sum(1 for item in stitches if (item.get("coverage") or {{}}).get("coverage_status") == "complete"),
    "issue_fact_links_total": sum(len(item.get("issue_fact_linkage") or []) for item in stitches),
    "raw_outputs_total": len(raw_rows),
    "private_raw_outputs_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "strict_raw_outputs_total": sum(1 for item in raw_payloads if item.get("structured_output_mode") == "openwebui_response_format_json_schema" and item.get("response_format_type") == "json_schema"),
    "fallback_raw_outputs_total": sum(1 for item in raw_payloads if item.get("fallback_used") is True),
    "source_facts_total": len(fact_rows),
    "private_source_facts_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "validated_source_facts_total": sum(1 for row in fact_rows if row["validation_status"] == "validated"),
    "validation_error_code_counts": dict(sorted(error_counts.items())),
    "knowledge_backend_records": sum(1 for row in [*runs, *raw_rows, *fact_rows, *validation_rows, *stitch_rows, *route_rows, *plan_rows, *derived_rows] if row["storage_backend"] == "openwebui_knowledge"),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=180)


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
        raise RuntimeError("gate2_typed_vertical_remote_result_invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
