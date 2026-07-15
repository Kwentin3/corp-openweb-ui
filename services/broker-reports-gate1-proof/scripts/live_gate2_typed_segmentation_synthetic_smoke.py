#!/usr/bin/env python3
"""Prove one live typed derived Gate 2 unit from a complete full-source parent."""

from __future__ import annotations

import argparse
import json
import sys
import time
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

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_process_false_gate1_run import (
    _counter_delta,
    _vector_delta_zero,
)
from live_gate2_domain_synthetic_smoke import (
    _audit_case,
    _audit_safe_validation_metadata,
    _remote_json,
)
from live_gate2_synthetic_extraction_smoke import (
    _current_user,
    _purge_case,
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
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--retain", action="store_true")
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
    model_id = _select_gate2_smoke_model(
        explicit_model_id=args.model_id,
        env=env,
    )
    case_id = f"synthetic_gate2_typed_segmentation_{time.strftime('%Y%m%d%H%M%S')}"
    before = _runtime_snapshot(ssh_target)
    seeded = _seed_truncated_case(
        ssh_target=ssh_target,
        case_id=case_id,
        user_id=str(current_user["id"]),
    )
    target = _select_typed_target(
        ssh_target=ssh_target,
        dcp_ref=str(seeded["domain_context_packet_ref"]),
        user_id=str(current_user["id"]),
    )
    if target.get("eligible") is not True:
        raise RuntimeError("synthetic_typed_segment_target_missing")
    chat_content = _run_chat(
        session=session,
        base_url=base_url,
        dcp_ref=str(seeded["domain_context_packet_ref"]),
        model_id=model_id,
        target=target,
        timeout=args.timeout,
    )
    after = _runtime_snapshot(ssh_target)
    delta = _counter_delta(before, after)
    audit = _audit_case(ssh_target=ssh_target, case_id=case_id)
    validation_audit = _audit_safe_validation_metadata(
        ssh_target=ssh_target, case_id=case_id
    )
    segmentation = _audit_segmentation(ssh_target=ssh_target, case_id=case_id)
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    checks = {
        "compact_projection_truncated_full_source_complete": (
            seeded.get("compact_slice_truncated") is True
            and int(seeded.get("parent_selected_total") or 0) >= 5
            and target.get("parent_source_slice_truncated") is False
            and target.get("source_slice_truncated") is False
        ),
        "typed_high_confidence_target": target.get("domain") == "position_snapshot"
        and target.get("confidence") == "high",
        "one_plan_one_private_derived_unit": segmentation.get("plan_total") == 1
        and segmentation.get("derived_total") == 1
        and segmentation.get("private_derived_total") == 1,
        "derived_complete_parent_complete": (
            segmentation.get("derived_truncated_total") == 0
            and segmentation.get("parent_truncated_total") == 0
            and segmentation.get("parent_remainder_status")
            == "not_applicable_parent_complete"
        ),
        "parent_refs_partitioned": segmentation.get("all_parent_selected_refs_partitioned") is True
        and segmentation.get("unaccounted_total") == 0
        and segmentation.get("duplicate_total") == 0,
        "domain_package_accepted": packages.get("total") == 1
        and packages.get("accepted") == 1
        and packages.get("rejected") == 0,
        "typed_fact_persisted": int((summary.get("facts_by_type") or {}).get("position_snapshot", 0)) > 0
        and int(summary.get("typed_facts_total") or 0) > 0,
        "complete_stitch_coverage": coverage.get("uncovered_total") == 0
        and coverage.get("conflict_total") == 0
        and audit.get("complete_stitch_total") == 1,
        "strict_private_outputs": audit.get("strict_raw_outputs_total") == audit.get("raw_outputs_total") == 1
        and audit.get("fallback_raw_outputs_total") == 0
        and audit.get("raw_output_private_total") == 1
        and audit.get("source_facts_private_total") == audit.get("source_facts_total") == 1
        and audit.get("source_facts_validated_total") == 1,
        "expansion_ready_for_complete_parent": (
            summary.get("ready_for_primary_expansion") is True
        ),
        "safe_chat_summary": "Gate 2" in chat_content
        and not any(
            marker in chat_content
            for marker in (
                "SYNTH-",
                "source_value_index",
                "private_slice_artifact_ref",
                "raw_output",
            )
        ),
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
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
        "target": target,
        "checks": checks,
        "summary": summary,
        "segmentation_audit": segmentation,
        "artifact_audit": audit,
        "validation_audit": validation_audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
        "cleanup": cleanup,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def _seed_truncated_case(*, ssh_target: str, case_id: str, user_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from pathlib import Path
namespace = {{"__name__": "gate2_typed_segmentation_synthetic_seed"}}
exec(compile({bundle_source!r}, "<gate2_typed_segmentation_synthetic_seed>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    FileInput, Gate1Normalizer, build_retention_policy, persist_gate1_result,
)
content = (
    b"Date,Operation,Amount,Currency,Identifier\\n"
    b"2025-01-01,position_snapshot,10.00,USD,SYNTH-POS-A\\n"
    b"2025-01-02,position_snapshot,11.00,USD,SYNTH-POS-B\\n"
    b"2025-01-03,unclassified_source_row,1.00,USD,SYNTH-UNKNOWN\\n"
    b"2025-01-04,broker_commission,0.50,USD,SYNTH-FEE\\n"
    b"2025-01-05,cash_deposit,2.00,USD,SYNTH-CASH\\n"
    b"2025-01-06,dividend,3.00,USD,SYNTH-INCOME\\n"
)
result = Gate1Normalizer().normalize([
    FileInput.from_bytes(
        private_ref="synthetic-gate2-typed-segmentation",
        filename="synthetic_gate2_typed_segmentation.csv",
        content=content,
        mime_type="text/csv",
    )
], input_context={{"clarification_criticality_refinement_enabled": True}})
package = result.package
document_ref = package["domain_context_packet"]["next_stage_refs"]["source_fact_ready_refs"][0]
private_slice = next(
    item for item in package["private_normalized_slices"]
    if item["document_id"] == document_ref
)
context = ArtifactAccessContext(
    user_id={user_id!r},
    normalization_run_id=package["normalization_run"]["run_id"],
    case_id={case_id!r},
    chat_id=f"chat_{{{case_id!r}}}",
    workspace_model_id="broker_reports_gate2_domain_source_fact_pipe",
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
    source_file_refs=[{{"provider": "synthetic", "source_deleted": False}}],
)
print(json.dumps({{
    "domain_context_packet_ref": manifest.artifact_refs_by_type["domain_context_packet_v0"][0],
    "compact_slice_truncated": bool(private_slice.get("truncated")),
    "parent_selected_total": int((private_slice.get("coverage") or {{}}).get("selected_total") or 0),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _select_typed_target(*, ssh_target: str, dcp_ref: str, user_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from pathlib import Path
namespace = {{"__name__": "gate2_typed_segmentation_synthetic_preflight"}}
exec(compile({bundle_source!r}, "<gate2_typed_segmentation_synthetic_preflight>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    Gate2InputReadinessFactory, Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterConfig, Gate2SourceUnitSegmenterFactory,
)
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
record = store.get_record_unchecked({dcp_ref!r})
context = ArtifactAccessContext(
    user_id={user_id!r}, normalization_run_id=record.normalization_run_id,
    case_id=record.case_id, chat_id=record.chat_id,
    workspace_model_id=record.workspace_model_id,
    allow_private=True, require_source_available=True,
)
readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
    domain_context_packet_ref=record.artifact_id, context=context,
)
base = readiness.packages[0]
parent_route = Gate2SourceUnitRouterFactory().create().route(base)
segmentation = Gate2SourceUnitSegmenterFactory(
    Gate2SourceUnitSegmenterConfig(table_max_selected_refs=1)
).create().segment(
    base_package=base, parent_route=parent_route,
)
candidates = []
for index, package in enumerate(segmentation.derived_packages):
    route = Gate2SourceUnitRouterFactory().create().route(package)
    entries = [item for item in route["route_entries"] if item["route_kind"] == "model_candidate"]
    domains = sorted({{domain for item in entries for domain in item["candidate_domains"]}})
    if entries and domains == ["position_snapshot"] and all(item["confidence"] == "high" for item in entries):
        candidates.append({{
            "eligible": True,
            "document_batch_start": 0,
            "source_unit_start": 0,
            "source_segment_start": index,
            "domain": "position_snapshot",
            "domains": domains,
            "confidence": "high",
            "selected_refs_total": len(route["selected_source_refs"]),
            "issue_refs_total": len(route.get("issue_refs") or []),
            "parent_source_slice_truncated": bool((package.get("source_unit") or {{}}).get("parent_source_slice_truncated")),
            "source_slice_truncated": bool((package.get("source_unit") or {{}}).get("source_slice_truncated")),
            "parent_remainder_status": (package.get("source_unit") or {{}}).get("parent_remainder_status"),
        }})
target = sorted(candidates, key=lambda item: (item["selected_refs_total"], item["source_segment_start"]))[0] if candidates else {{"eligible": False}}
target["derived_units_total"] = len(segmentation.derived_packages)
target["candidate_typed_units_total"] = len(candidates)
print(json.dumps(target, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _run_chat(*, session, base_url, dcp_ref, model_id, target, timeout) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Выполни минимальную типизированную вертикаль Gate 2.",
                }
            ],
            "stream": False,
            "broker_reports_gate2_domain": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "wave": "primary",
                "run_mode": "synthetic",
                "document_batch_start": target["document_batch_start"],
                "document_batch_limit": 1,
                "source_unit_start": target["source_unit_start"],
                "source_unit_limit": 1,
                "segmentation_enabled": True,
                "source_segment_start": target["source_segment_start"],
                "source_segment_limit": 1,
                "table_segment_max_refs": 1,
                "domain_allowlist": target["domains"],
                "max_repair_attempts": 1,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _audit_segmentation(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    code = f'''
import json, sqlite3
from pathlib import Path
root = Path("/app/backend/data/broker_reports_gate1/payloads")
conn = sqlite3.connect("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute("select * from artifact_records where case_id=? and purge_status='active'", ({case_id!r},)).fetchall()
finally:
    conn.close()
def payload(row):
    return json.loads(row["payload_inline_json"]) if row["payload_inline_json"] else json.loads((root / row["payload_ref"]).read_text(encoding="utf-8"))
plans = [row for row in rows if row["artifact_type"] == "broker_reports_source_unit_segmentation_plan_v0"]
derived = [row for row in rows if row["artifact_type"] == "broker_reports_derived_source_unit_v0"]
plan = payload(plans[0]) if len(plans) == 1 else {{}}
unit_payloads = [payload(row) for row in derived]
coverage = plan.get("coverage") or {{}}
print(json.dumps({{
    "plan_total": len(plans),
    "derived_total": len(derived),
    "private_derived_total": sum(1 for row in derived if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "derived_truncated_total": sum(1 for item in unit_payloads if (item.get("source_unit") or {{}}).get("source_slice_truncated") is True),
    "parent_truncated_total": sum(1 for item in unit_payloads if (item.get("source_unit") or {{}}).get("parent_source_slice_truncated") is True),
    "parent_remainder_status": coverage.get("parent_remainder_status"),
    "all_parent_selected_refs_partitioned": coverage.get("all_parent_selected_refs_partitioned"),
    "unaccounted_total": len(coverage.get("unaccounted_source_refs") or []),
    "duplicate_total": len(coverage.get("duplicate_source_refs") or []),
    "selected_for_extraction_total": coverage.get("selected_for_extraction_total"),
    "deferred_derived_units_total": coverage.get("deferred_derived_units_total"),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=60)


if __name__ == "__main__":
    raise SystemExit(main())
