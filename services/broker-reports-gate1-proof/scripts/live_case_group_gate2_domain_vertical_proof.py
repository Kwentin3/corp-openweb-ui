#!/usr/bin/env python3
"""Prove a supported CSV partition through Gate 2 and the Gate 3 context root."""

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
DEFAULT_CASE_ID = "customer_case_group_002_process_false_gate1_20260717204732"

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_gate2_extraction_proof import _case_manifest
from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _vector_delta_zero,
)
from live_gate2_synthetic_extraction_smoke import (
    _current_user,
    _select_gate2_smoke_model,
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
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--audit-latest", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
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
    if args.audit_latest:
        run_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
        if not run_refs:
            raise RuntimeError("gate2_domain_vertical_run_missing")
        previous_run_refs = run_refs[:-1]
        audit = _audit_new_run(
            ssh_target=ssh_target,
            case_id=args.case_id,
            previous_run_refs=previous_run_refs,
        )
        manifest_audit = _audit_manifest_contract(
            ssh_target=ssh_target,
            case_id=args.case_id,
            previous_run_refs=previous_run_refs,
        )
        checks = _latest_audit_checks(audit, manifest_audit)
        status = "passed" if checks and all(checks.values()) else "failed"
        print(json.dumps({
            "status": status,
            "case_id": args.case_id,
            "checks": checks,
            "summary": audit.get("summary") or {},
            "artifact_audit": audit,
            "gate3_manifest_audit": manifest_audit,
            "private_values_emitted": False,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if status == "passed" else 1
    target = _select_vertical_target(
        ssh_target=ssh_target,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        user_id=str(current_user["id"]),
    )
    if args.preflight_only:
        print(json.dumps({"status": "passed", "target": target}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if target.get("eligible") is not True:
        print(json.dumps({"status": "blocked", "blocker": "no_supported_csv_typed_segment", "target": target}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2

    model_id = _select_gate2_smoke_model(
        explicit_model_id=args.model_id,
        env=env,
        provider_profile_id="openai_gpt",
    )
    previous_run_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
    before = _runtime_snapshot(ssh_target)
    chat_content = _run_chat(
        session=session,
        base_url=base_url,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        model_id=model_id,
        target=target,
        timeout=args.timeout,
    )
    after = _runtime_snapshot(ssh_target)
    delta = _counter_delta(before, after)
    audit = _audit_new_run(
        ssh_target=ssh_target,
        case_id=args.case_id,
        previous_run_refs=previous_run_refs,
    )
    manifest_audit = _audit_manifest_contract(
        ssh_target=ssh_target,
        case_id=args.case_id,
        previous_run_refs=previous_run_refs,
    )
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    forbidden_errors = {
        "source_fact_provenance_missing",
        "source_fact_completeness_overstated",
        "source_fact_coverage_gap",
        "source_fact_issue_not_carried",
    }
    error_codes = set((audit.get("validation_error_code_counts") or {}).keys())
    checks = {
        "target_one_csv_document_unit_segment": target.get("document_batch_limit") == 1 and target.get("source_unit_limit") == 1 and target.get("source_segment_limit") == 1,
        "target_supported_csv_profile_v1": target.get("csv_profile_id") == "broker_reports_csv_supported_profile_v1",
        "target_one_typed_high_confidence_domain": len(target.get("domains") or []) == 1 and int(target.get("high_confidence_candidates") or 0) > 0,
        "target_parent_complete_without_remainder": target.get("parent_source_slice_truncated") is False and target.get("parent_remainder_status") == "not_applicable_parent_complete",
        "domain_runtime_terminal": summary.get("terminal_status") == "completed",
        "one_stitch_result": audit.get("stitch_total") == 1,
        "at_least_one_accepted_fact_set": int(packages.get("accepted") or 0) > 0 and int(summary.get("facts_total") or 0) > 0,
        "all_selected_domain_packages_accepted": packages.get("accepted") == packages.get("total") and packages.get("rejected") == 0,
        "complete_conflict_free_selected_unit": coverage.get("uncovered_total") == 0 and coverage.get("conflict_total") == 0 and audit.get("complete_stitch_total") == 1,
        "no_core_broad_failure_codes": not (forbidden_errors & error_codes),
        "strict_json_schema_no_fallback": audit.get("strict_raw_outputs_total") == audit.get("raw_outputs_total") and audit.get("fallback_raw_outputs_total") == 0,
        "raw_rejected_outputs_private": audit.get("private_raw_outputs_total") == audit.get("raw_outputs_total"),
        "facts_private_and_validated": audit.get("private_source_facts_total") == audit.get("source_facts_total") == audit.get("validated_source_facts_total"),
        "issue_refs_carried": audit.get("route_issue_refs_total") == 0 or int(audit.get("issue_fact_links_total") or 0) > 0,
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(delta),
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
        "manifest_ready_and_safe": manifest_audit.get("gate3_input_status") == "ready" and manifest_audit.get("private_copy_fields_present") is False,
        "same_context_manifest_and_private_fact_resolve": manifest_audit.get("same_context_manifest_resolved") is True and manifest_audit.get("same_context_private_fact_resolved") is True,
        "wrong_context_denied": all(code == "artifact_access_denied" for code in (manifest_audit.get("wrong_context_codes") or {}).values()),
        "active_retention_coherent": manifest_audit.get("active_retention") is True and manifest_audit.get("retention_horizon_coherent") is True,
        "controlled_expiry_and_purge_fail_closed": manifest_audit.get("controlled_graph_active_resolved") is True and manifest_audit.get("controlled_graph_expiry_code") == "artifact_expired" and manifest_audit.get("controlled_graph_purge_code") == "artifact_purged",
        "chat_safe": "Gate 2" in chat_content and "Расчёт налогов, декларация и XLS/XLSX не выполнялись." in chat_content and not any(marker in chat_content for marker in ("raw_output", "private_slice_artifact_ref", "source_value_index")),
    }
    status = "passed" if checks and all(checks.values()) else "failed"
    output = {
        "status": status,
        "case_id": args.case_id,
        "model_id": model_id,
        "target": target,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "gate3_manifest_audit": manifest_audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "primary_expansion_allowed": status == "passed" and summary.get("ready_for_primary_expansion") is True,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _select_vertical_target(*, ssh_target: str, dcp_ref: str, user_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from collections import Counter
from pathlib import Path

namespace = {{"__name__": "gate2_domain_vertical_preflight_bundle"}}
exec(compile({bundle_source!r}, "<gate2_domain_vertical_preflight_bundle>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactResolver, ArtifactStoreConfig, ArtifactStoreFactory,
    Gate2InputReadinessFactory, Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
)

store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
dcp_ref = {dcp_ref!r}
record = store.get_record_unchecked(dcp_ref)
if record is None:
    raise RuntimeError("gate2_domain_vertical_dcp_missing")
context = ArtifactAccessContext(
    user_id={user_id!r}, normalization_run_id=record.normalization_run_id,
    case_id=record.case_id, chat_id=record.chat_id,
    workspace_model_id=record.workspace_model_id,
    allow_private=True, require_source_available=True,
)
readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
    domain_context_packet_ref=dcp_ref, context=context,
)
profile_by_document = {{}}
resolver = ArtifactResolver(store)
for profile_record in store.list_by_type(
    context.normalization_run_id, "technical_readability_profile_v0"
):
    resolved_profiles = resolver.resolve(profile_record.artifact_id, context)["payload"] or []
    for profile in resolved_profiles:
        if not isinstance(profile, dict):
            continue
        if (
            profile.get("container_format") == "csv"
            and profile.get("supported_csv_profile_status") == "accepted"
        ):
            profile_by_document[str(profile.get("document_id") or "")] = str(
                profile.get("supported_csv_profile_id") or ""
            )
primary = [
    item for item in readiness.packages
    if "primary_source_extraction_refs" in set(item.get("source_bucket_roles") or [])
]
document_refs = sorted({{str(item.get("document_ref") or "") for item in primary}})
candidates = []
for document_index, document_ref in enumerate(document_refs):
    units = [item for item in primary if str(item.get("document_ref") or "") == document_ref]
    for unit_index, package in enumerate(units):
        parent_unit = package.get("source_unit") or {{}}
        csv_profile_id = profile_by_document.get(document_ref, "")
        parent_route = Gate2SourceUnitRouterFactory().create().route(package)
        segmented = Gate2SourceUnitSegmenterFactory().create().segment(
            base_package=package, parent_route=parent_route,
        )
        for segment_index, derived in enumerate(segmented.derived_packages):
            route = Gate2SourceUnitRouterFactory().create().route(derived)
            entries = [item for item in route["route_entries"] if item["route_kind"] == "model_candidate"]
            domains = sorted({{domain for item in entries for domain in item["candidate_domains"]}})
            confidence = Counter(str(item.get("confidence") or "low") for item in entries)
            derived_unit = derived.get("source_unit") or {{}}
            typed_eligible = bool(entries) and len(domains) == 1 and "unknown_source_row" not in domains
            supported_csv = csv_profile_id == "broker_reports_csv_supported_profile_v1"
            parent_complete = (
                parent_unit.get("source_slice_truncated") is False
                and parent_unit.get("parent_remainder_status") == "not_applicable_parent_complete"
            )
            eligible = supported_csv and parent_complete and typed_eligible and confidence.get("high", 0) > 0
            candidates.append({{
                "eligible": eligible,
                "selection_kind": "typed_high_confidence_csv_segment" if eligible else "ineligible",
                "csv_profile_id": csv_profile_id,
                "document_batch_start": document_index,
                "document_batch_limit": 1,
                "source_unit_start": unit_index,
                "source_unit_limit": 1,
                "source_segment_start": segment_index,
                "source_segment_limit": 1,
                "domains": domains,
                "selected_refs_total": len(route["selected_source_refs"]),
                "model_candidates_total": len(entries),
                "deterministic_no_fact_total": route["coverage"]["deterministic_no_fact_total"],
                "ambiguous_total": route["coverage"]["ambiguous_total"],
                "unknown_total": route["coverage"]["unknown_total"],
                "high_confidence_candidates": confidence.get("high", 0),
                "medium_confidence_candidates": confidence.get("medium", 0),
                "low_confidence_candidates": confidence.get("low", 0),
                "issue_refs_total": len(route.get("issue_refs") or []),
                "parent_source_slice_truncated": parent_unit.get("source_slice_truncated") is True,
                "parent_remainder_status": parent_unit.get("parent_remainder_status"),
                "derived_source_slice_truncated": derived_unit.get("source_slice_truncated") is True,
                "parent_segments_total": len(segmented.derived_packages),
            }})
eligible = [item for item in candidates if item["eligible"]]
ranked = sorted(
    eligible,
    key=lambda item: (
        item["model_candidates_total"],
        item["low_confidence_candidates"],
        -item["high_confidence_candidates"],
        item["selected_refs_total"],
        item["document_batch_start"],
        item["source_unit_start"],
        item["source_segment_start"],
    ),
)
target = ranked[0] if ranked else {{
    "eligible": False,
    "candidates_total": len(candidates),
    "eligible_candidates_total": 0,
}}
target["candidates_total"] = len(candidates)
target["eligible_candidates_total"] = len(eligible)
target["safe_candidate_matrix"] = sorted(
    [
        {{
            "document_batch_start": item["document_batch_start"],
            "source_unit_start": item["source_unit_start"],
            "source_segment_start": item["source_segment_start"],
            "eligible": item["eligible"],
            "selection_kind": item["selection_kind"],
            "domains": item["domains"],
            "selected_refs_total": item["selected_refs_total"],
            "model_candidates_total": item["model_candidates_total"],
            "ambiguous_total": item["ambiguous_total"],
            "unknown_total": item["unknown_total"],
            "high": item["high_confidence_candidates"],
            "medium": item["medium_confidence_candidates"],
            "low": item["low_confidence_candidates"],
            "csv_profile_id": item["csv_profile_id"],
            "parent_truncated": item["parent_source_slice_truncated"],
            "parent_remainder_status": item["parent_remainder_status"],
        }}
        for item in candidates
    ],
    key=lambda item: (
        item["model_candidates_total"], item["low"], -item["high"],
        item["document_batch_start"], item["source_unit_start"], item["source_segment_start"],
    ),
)[:25]
print(json.dumps(target, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=180)


def _run_chat(*, session, base_url, dcp_ref, model_id, target, timeout) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [{"role": "user", "content": "Выполни минимальную доменную вертикаль Gate 2."}],
            "stream": False,
            "broker_reports_gate2_domain": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "provider_profile_id": _provider_profile_id(model_id),
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
                "candidate_binding_enabled": True,
                "max_repair_attempts": 0,
                "gate3_context_manifest_enabled": True,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _provider_profile_id(model_id: str) -> str:
    normalized = str(model_id or "").lower()
    if "gemini" in normalized:
        return "google_gemini"
    if "claude" in normalized:
        return "anthropic_claude"
    if "deepseek" in normalized:
        return "deepseek"
    if "glm" in normalized:
        return "zai_glm"
    if "qwen" in normalized:
        return "alibaba_qwen"
    return "openai_gpt"


def _latest_audit_checks(
    audit: dict[str, Any], manifest_audit: dict[str, Any]
) -> dict[str, bool]:
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    return {
        "domain_runtime_terminal": summary.get("terminal_status") == "completed",
        "typed_facts_accepted": int(summary.get("facts_total") or 0) > 0 and int(packages.get("accepted") or 0) > 0,
        "no_rejected_packages": packages.get("accepted") == packages.get("total") and packages.get("rejected") == 0,
        "zero_uncovered_conflict": coverage.get("uncovered_total") == 0 and coverage.get("conflict_total") == 0,
        "strict_schema_no_fallback": audit.get("strict_raw_outputs_total") == audit.get("raw_outputs_total") and audit.get("fallback_raw_outputs_total") == 0,
        "facts_private_validated": audit.get("private_source_facts_total") == audit.get("source_facts_total") == audit.get("validated_source_facts_total"),
        "no_knowledge_backend": audit.get("knowledge_backend_records") == 0 and manifest_audit.get("knowledge_backend_records") == 0,
        "manifest_ready_safe": manifest_audit.get("gate3_input_status") == "ready" and manifest_audit.get("private_copy_fields_present") is False,
        "same_context_resolves": manifest_audit.get("same_context_manifest_resolved") is True and manifest_audit.get("same_context_private_fact_resolved") is True,
        "wrong_context_denied": all(code == "artifact_access_denied" for code in (manifest_audit.get("wrong_context_codes") or {}).values()),
        "active_retention_coherent": manifest_audit.get("active_retention") is True and manifest_audit.get("retention_horizon_coherent") is True,
        "no_repair_failover_provider_failure": manifest_audit.get("repair_attempts_total") == 0 and manifest_audit.get("fallback_attempts_total") == 0 and manifest_audit.get("provider_failures_total") == 0,
        "controlled_expiry_purge_fail_closed": manifest_audit.get("controlled_graph_active_resolved") is True and manifest_audit.get("controlled_graph_expiry_code") == "artifact_expired" and manifest_audit.get("controlled_graph_purge_code") == "artifact_purged",
    }


def _domain_run_refs(*, ssh_target: str, case_id: str) -> list[str]:
    code = f'''
import json, sqlite3
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
try:
    rows = conn.execute(
        "select artifact_id from artifact_records where case_id=? and artifact_type='broker_reports_domain_source_fact_extraction_run_v0' and purge_status='active' order by created_at asc, artifact_id asc",
        ({case_id!r},),
    ).fetchall()
finally:
    conn.close()
print(json.dumps({{"refs": [str(row[0]) for row in rows]}}))
'''
    return [str(item) for item in _remote_json(ssh_target, code, timeout=60)["refs"]]


def _audit_new_run(*, ssh_target: str, case_id: str, previous_run_refs: list[str]) -> dict[str, Any]:
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
    raise RuntimeError("gate2_domain_vertical_new_run_count_invalid")
run = payload(runs[0])
summary = payload(by_ref[str(run["summary_ref"])])
manifest_ref = str(run.get("gate3_context_manifest_ref") or "")
manifest_payload = payload(by_ref[manifest_ref]) if manifest_ref else {{}}
raw_rows = [by_ref[ref] for ref in run.get("raw_output_refs") or []]
package_rows = [by_ref[ref] for ref in run.get("domain_package_refs") or []]
candidate_rows = [by_ref[ref] for ref in run.get("source_value_candidate_set_refs") or []]
relation_rows = [by_ref[ref] for ref in run.get("candidate_relation_set_refs") or []]
binding_rows = [by_ref[ref] for ref in run.get("candidate_binding_validation_refs") or []]
fact_rows = [by_ref[ref] for ref in run.get("source_facts_refs") or []]
validation_rows = [by_ref[ref] for ref in run.get("validation_refs") or []]
stitch_rows = [by_ref[ref] for ref in run.get("stitch_result_refs") or []]
route_rows = [by_ref[ref] for ref in run.get("route_refs") or []]
raw_payloads = [payload(row) for row in raw_rows]
def structured_output(item):
    value = item.get("raw_output")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {{}}
    return value if isinstance(value, dict) else {{}}
candidate_metadata = [json.loads(row["safe_metadata_json"] or "{{}}") for row in candidate_rows]
relation_metadata = [json.loads(row["safe_metadata_json"] or "{{}}") for row in relation_rows]
binding_payloads = [payload(row) for row in binding_rows]
stitches = [payload(row) for row in stitch_rows]
validations = [payload(row) for row in validation_rows]
error_counts = Counter(str(error.get("code") or "unknown") for item in validations for error in item.get("errors") or [])
print(json.dumps({{
    "summary": summary,
    "gate3_manifest_safe": {{
        "manifest_ref": manifest_ref or None,
        "schema_version": manifest_payload.get("schema_version"),
        "gate3_input_status": manifest_payload.get("gate3_input_status"),
        "reason_codes": manifest_payload.get("reason_codes") or [],
        "decision_metrics": manifest_payload.get("decision_metrics") or {{}},
        "zero_loss_reconciliation": manifest_payload.get("zero_loss_reconciliation") or {{}},
    }},
    "route_total": len(route_rows),
    "route_issue_refs_total": sum(len(payload(row).get("issue_refs") or []) for row in route_rows),
    "stitch_total": len(stitch_rows),
    "complete_stitch_total": sum(1 for item in stitches if (item.get("coverage") or {{}}).get("coverage_status") == "complete"),
    "issue_fact_links_total": sum(len(item.get("issue_fact_linkage") or []) for item in stitches),
    "raw_outputs_total": len(raw_rows),
    "private_raw_outputs_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "strict_raw_outputs_total": sum(1 for item in raw_payloads if item.get("structured_output_mode") in {"openwebui_response_format_json_schema", "openwebui_anthropic_output_config_json_schema"} and item.get("response_format_type") == "json_schema"),
    "fallback_raw_outputs_total": sum(1 for item in raw_payloads if item.get("fallback_used") is True),
    "provider_execution": [item.get("provider_execution_safe") or {{}} for item in raw_payloads],
    "provider_failures": [{{
        "error_code": item.get("error_code"),
        "failure_class": item.get("failure_class"),
        "model_call_status": item.get("model_call_status"),
    }} for item in raw_payloads if item.get("model_call_status") == "failed"],
    "domain_package_safe_statuses": [{{
        "validation_status": row["validation_status"],
        "warning_codes": json.loads(row["warning_codes_json"] or "[]"),
        "budget_status": (json.loads(row["safe_metadata_json"] or "{{}}") or {{}}).get("budget_status"),
    }} for row in package_rows],
    "candidate_sets": [{{
        "candidates_total": item.get("candidates_total"),
        "candidate_kind_counts": item.get("candidate_kind_counts") or {{}},
        "validation_status": item.get("validation_status"),
    }} for item in candidate_metadata],
    "relation_sets": [{{
        "relations_total": item.get("relations_total"),
        "relation_kind_counts": item.get("relation_kind_counts") or {{}},
        "validation_status": item.get("validation_status"),
    }} for item in relation_metadata],
    "binding_validations": [{{
        "validator_status": item.get("validator_status"),
        "errors_count": item.get("errors_count"),
        "selected_refs_total": item.get("selected_refs_total"),
        "accounted_refs_total": item.get("accounted_refs_total"),
        "repair_attempt_count": item.get("repair_attempt_count"),
    }} for item in binding_payloads],
    "binding_fact_type_counts": dict(sorted(Counter(
        str(result.get("fact_type") or "unknown")
        for item in raw_payloads
        for result in (structured_output(item).get("binding_results") or [])
        if isinstance(result, dict)
    ).items())),
    "binding_no_fact_reason_counts": dict(sorted(Counter(
        str(result.get("reason_code") or "unknown")
        for item in raw_payloads
        for result in (structured_output(item).get("no_fact_results") or [])
        if isinstance(result, dict)
    ).items())),
    "source_facts_total": len(fact_rows),
    "private_source_facts_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "validated_source_facts_total": sum(1 for row in fact_rows if row["validation_status"] == "validated"),
    "validation_error_code_counts": dict(sorted(error_counts.items())),
    "knowledge_backend_records": sum(1 for row in [*runs, *raw_rows, *fact_rows, *validation_rows, *stitch_rows, *route_rows] if row["storage_backend"] == "openwebui_knowledge"),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _audit_manifest_contract(
    *, ssh_target: str, case_id: str, previous_run_refs: list[str]
) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import copy
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

namespace = {{"__name__": "gate3_context_stage_audit_bundle"}}
exec(compile({bundle_source!r}, "<gate3_context_stage_audit_bundle>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactResolver,
    ArtifactStoreConfig, ArtifactStoreError, ArtifactStoreFactory,
    Gate3ContextManifestFactory,
)
from broker_reports_gate1.artifact_models import ArtifactRecord, RetentionPolicy
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.gate3_context_manifest import (
    _contains_private_copy_field, _manifest_descendant_refs,
    _manifest_integrity_hash, _safe_access_context,
)

store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
previous = set({previous_run_refs!r})
runs = [
    item for item in store.list_by_case({case_id!r})
    if item.artifact_type == "broker_reports_domain_source_fact_extraction_run_v0"
    and item.artifact_id not in previous and item.purge_status == "active"
]
if len(runs) != 1:
    raise RuntimeError("gate3_context_stage_new_run_count_invalid")
run_record = runs[0]
run = store.read_payload(run_record)
context = ArtifactAccessContext(
    user_id=run_record.user_id,
    normalization_run_id=run_record.normalization_run_id,
    case_id=run_record.case_id,
    chat_id=run_record.chat_id,
    workspace_model_id=run_record.workspace_model_id,
    allow_private=True,
    require_source_available=True,
)
manifest_ref = str(run.get("gate3_context_manifest_ref") or "")
service = Gate3ContextManifestFactory(store=store).create()
manifest = service.resolve_for_gate3(manifest_ref=manifest_ref, context=context)
resolver = ArtifactResolver(store)
fact_refs = list(
    (manifest.get("artifact_roots") or {{}}).get("validated_source_fact_refs") or []
)
if not fact_refs:
    raise RuntimeError("gate3_context_stage_private_fact_ref_missing")
resolver.resolve(str(fact_refs[0]), context)

def denied_code(test_context):
    try:
        service.resolve_for_gate3(manifest_ref=manifest_ref, context=test_context)
    except ArtifactStoreError as exc:
        return exc.code
    return "unexpected_access_allowed"

wrong_context_codes = {{
    "user": denied_code(ArtifactAccessContext(
        user_id="wrong-user", normalization_run_id=context.normalization_run_id,
        case_id=context.case_id, chat_id=context.chat_id,
        workspace_model_id=context.workspace_model_id, allow_private=True,
        require_source_available=True,
    )),
    "case": denied_code(ArtifactAccessContext(
        user_id=context.user_id, normalization_run_id=context.normalization_run_id,
        case_id="wrong-case", chat_id=context.chat_id,
        workspace_model_id=context.workspace_model_id, allow_private=True,
        require_source_available=True,
    )),
    "workspace": denied_code(ArtifactAccessContext(
        user_id=context.user_id, normalization_run_id=context.normalization_run_id,
        case_id=context.case_id, chat_id=context.chat_id,
        workspace_model_id="wrong-workspace", allow_private=True,
        require_source_available=True,
    )),
}}

graph_refs = [manifest_ref, *_manifest_descendant_refs(manifest)]
graph_records = [store.get_record_unchecked(ref) for ref in graph_refs]
if any(item is None for item in graph_records):
    raise RuntimeError("gate3_context_stage_graph_record_missing")
retention_modes = {{item.retention_policy.mode for item in graph_records}}
expires_at_values = {{item.expires_at for item in graph_records}}
active_retention = all(
    item.purge_status == "active" and item.lifecycle_status not in {{"expired", "purged"}}
    for item in graph_records
)

probe_token = uuid.uuid4().hex[:16]
probe_run = "gate3_probe_run_" + probe_token
probe_case = "gate3_probe_case_" + probe_token
probe_workspace = "gate3_probe_workspace_" + probe_token
probe_context = ArtifactAccessContext(
    user_id=context.user_id, normalization_run_id=probe_run,
    case_id=probe_case, workspace_model_id=probe_workspace,
    allow_private=True, require_source_available=True,
)
probe_expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
probe_retention = RetentionPolicy(
    mode="expires_after_ttl", ttl_seconds=600, expires_at=probe_expires,
    source_delete_cascades=True, chat_delete_cascades=True,
    keep_redacted_tombstone=True, requires_manual_purge=False, explicit=True,
)
probe_root = Path("/app/backend/data/broker_reports_gate1/lifecycle_probes") / probe_token
probe_store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite", sqlite_path=probe_root / "artifacts.sqlite3",
    payload_root=probe_root / "payloads",
)).create()
descendant_refs = _manifest_descendant_refs(manifest)
ref_map = {{ref: "gate3_probe_art_" + probe_token + "_" + str(index) for index, ref in enumerate(descendant_refs)}}

def remap(value):
    if isinstance(value, dict):
        return {{key: remap(child) for key, child in value.items()}}
    if isinstance(value, list):
        return [remap(child) for child in value]
    if isinstance(value, str):
        return ref_map.get(value, value)
    return value

for original_ref in descendant_refs:
    original = store.get_record_unchecked(original_ref)
    if original is None:
        raise RuntimeError("gate3_context_stage_probe_source_record_missing")
    probe_store.put_record(ArtifactRecord(
        artifact_id=ref_map[original_ref], artifact_type=original.artifact_type,
        case_id=probe_case, chat_id=None, user_id=context.user_id,
        workspace_model_id=probe_workspace, normalization_run_id=probe_run,
        document_id=None, source_file_ref=None, visibility="private_case",
        storage_backend="project_artifact_payload", retention_policy=probe_retention,
        access_policy={{"controlled_lifecycle_probe": True}},
        validation_status="validated", lifecycle_status="private_ready",
        payload_kind="inline_json", payload={{"controlled_lifecycle_probe": True}},
        safe_metadata={{"controlled_lifecycle_probe": True}},
    ))

probe_manifest = remap(copy.deepcopy(manifest))
probe_manifest_ref = "gate3_probe_manifest_" + probe_token
probe_manifest["manifest_id"] = probe_manifest_ref
probe_manifest["normalization_run_id"] = probe_run
probe_manifest["access_context"] = _safe_access_context(probe_context)
probe_manifest["created_at"] = datetime.now(timezone.utc).isoformat()
probe_manifest["integrity_hash"] = _manifest_integrity_hash(probe_manifest)
probe_store.put_record(ArtifactRecord(
    artifact_id=probe_manifest_ref,
    artifact_type="broker_reports_gate3_context_manifest_v0",
    case_id=probe_case, chat_id=None, user_id=context.user_id,
    workspace_model_id=probe_workspace, normalization_run_id=probe_run,
    document_id=None, source_file_ref=None, visibility="safe_internal",
    storage_backend="project_artifact_store", retention_policy=probe_retention,
    access_policy={{"controlled_lifecycle_probe": True}},
    validation_status="validated", lifecycle_status="validated",
    payload_kind="inline_json", payload=probe_manifest,
    safe_metadata={{"controlled_lifecycle_probe": True}},
))
probe_service = Gate3ContextManifestFactory(store=probe_store).create()
probe_service.resolve_for_gate3(manifest_ref=probe_manifest_ref, context=probe_context)

probe_store.expire_run(
    probe_context,
    datetime.now(timezone.utc) + timedelta(minutes=20),
)
try:
    probe_service.resolve_for_gate3(manifest_ref=probe_manifest_ref, context=probe_context)
except ArtifactStoreError as exc:
    expiry_code = exc.code
else:
    expiry_code = "unexpected_access_allowed"
probe_store.purge_run(probe_context)
try:
    probe_service.resolve_for_gate3(manifest_ref=probe_manifest_ref, context=probe_context)
except ArtifactStoreError as exc:
    purge_code = exc.code
else:
    purge_code = "unexpected_access_allowed"

metrics = manifest.get("decision_metrics") or {{}}
print(json.dumps({{
    "manifest_ref": manifest_ref,
    "schema_version": manifest.get("schema_version"),
    "gate3_input_status": manifest.get("gate3_input_status"),
    "reason_codes": manifest.get("reason_codes") or [],
    "declared_scope_kind": (manifest.get("declared_scope") or {{}}).get("scope_kind"),
    "documents_total": len((manifest.get("declared_scope") or {{}}).get("document_refs") or []),
    "selected_source_refs_total": metrics.get("selected_source_refs_total"),
    "typed_facts_total": metrics.get("typed_facts_total"),
    "rejected_packages_total": metrics.get("rejected_packages_total"),
    "uncovered_total": metrics.get("uncovered_total"),
    "conflict_total": metrics.get("conflict_total"),
    "repair_attempts_total": metrics.get("repair_attempts_total"),
    "fallback_attempts_total": metrics.get("fallback_attempts_total"),
    "provider_failures_total": metrics.get("provider_failures_total"),
    "provider_schema_identities": (manifest.get("terminal_gate2") or {{}}).get("provider_identities") or [],
    "private_copy_fields_present": _contains_private_copy_field(manifest),
    "same_context_manifest_resolved": True,
    "same_context_private_fact_resolved": True,
    "wrong_context_codes": wrong_context_codes,
    "active_retention": active_retention,
    "retention_horizon_coherent": len(retention_modes) == 1 and len(expires_at_values) == 1,
    "knowledge_backend_records": sum(1 for item in graph_records if item.storage_backend == "openwebui_knowledge"),
    "controlled_graph_active_resolved": True,
    "controlled_graph_expiry_code": expiry_code,
    "controlled_graph_purge_code": purge_code,
    "controlled_graph_records_total": len(descendant_refs) + 1,
    "private_values_emitted": False,
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=180)


def _remote_json(ssh_target: str, code: str, *, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no", ssh_target, "docker", "exec", "-i", "openwebui", "python", "-"],
        cwd=ROOT,
        input=code,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    if completed.returncode != 0:
        lines = [line.strip() for line in (completed.stderr or "").splitlines() if line.strip()]
        failure_class = (lines[-1].split(":", 1)[0] if lines else "remote_execution_failed")[:120]
        failure_code = (
            lines[-1].rsplit(":", 1)[-1].strip() if lines and ":" in lines[-1] else "unknown"
        )[:120]
        raise RuntimeError(
            f"gate2_domain_vertical_remote_failed: {failure_class}:{failure_code}"
        )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("gate2_domain_vertical_remote_result_invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
