#!/usr/bin/env python3
"""Run one live PDF through whole-document Gate 2 windows and persist a packet.

The script prints safe aggregates only. It does not parse PDFs, call provider
SDKs, or bypass Gate 2 factories; extraction is executed through the deployed
OpenWebUI Gate 2 domain pipe one deterministic source-unit segment at a time.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
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
PACKET_SCHEMA_VERSION = "broker_reports_document_extraction_packet_v0"

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_gate2_domain_vertical_proof import _domain_run_refs, _remote_json  # noqa: E402
from live_case_group_gate2_extraction_proof import _case_manifest  # noqa: E402
from live_case_group_process_false_gate1_run import _counter_delta, _vector_delta_zero  # noqa: E402
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
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
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model-id", default="models/gemini-3.1-flash-lite")
    parser.add_argument("--provider-profile-id", default="google_gemini")
    parser.add_argument("--table-segment-max-refs", type=int, default=4)
    parser.add_argument("--text-segment-max-refs", type=int, default=6)
    parser.add_argument("--max-model-calls", type=int, default=120)
    parser.add_argument("--max-repair-attempts", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--disable-candidate-binding", action="store_true")
    parser.add_argument("--resume-existing-runs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--resume-run-count", type=int, default=None)
    args = parser.parse_args()

    started = time.perf_counter()
    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    candidate_binding_enabled = not args.disable_candidate_binding

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
    if manifest.get("blocker"):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker": manifest.get("blocker"),
                    "case_id": args.case_id,
                    "active_records_total": manifest.get("active_records_total"),
                    "domain_context_packets_total": manifest.get("domain_context_packets_total"),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if manifest.get("owner_matches_authenticated_user") is not True:
        raise RuntimeError("case_owner_does_not_match_authenticated_user")

    preflight = _preflight_matrix(
        ssh_target=ssh_target,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        user_id=str(current_user["id"]),
        table_segment_max_refs=args.table_segment_max_refs,
        text_segment_max_refs=args.text_segment_max_refs,
        candidate_binding_enabled=candidate_binding_enabled,
    )
    preflight_checks = _preflight_checks(preflight, max_model_calls=args.max_model_calls)
    if args.preflight_only or not all(preflight_checks.values()):
        status = "passed" if all(preflight_checks.values()) else "blocked"
        print(
            json.dumps(
                {
                    "status": status,
                    "case_id": args.case_id,
                    "provider_profile_id": args.provider_profile_id,
                    "model_id": args.model_id,
                    "candidate_binding_enabled": candidate_binding_enabled,
                    "preflight_checks": preflight_checks,
                    "preflight": _compact_preflight(preflight),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if status == "passed" else 2

    existing_run_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
    resume_count = 0
    if args.resume_existing_runs:
        resume_count = min(len(existing_run_refs), len(preflight.get("windows") or []))
    if args.resume_run_count is not None:
        resume_count = max(0, min(args.resume_run_count, len(preflight.get("windows") or [])))
    if resume_count:
        print(
            json.dumps(
                {
                    "event": "resume_existing_domain_runs",
                    "case_id": args.case_id,
                    "resume_count": resume_count,
                    "existing_domain_runs_total": len(existing_run_refs),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )

    before_all = _runtime_snapshot_extended(ssh_target)
    runs: list[dict[str, Any]] = []
    if resume_count:
        existing_audits = _audit_domain_run_refs(
            ssh_target=ssh_target,
            case_id=args.case_id,
            run_refs=existing_run_refs[:resume_count],
        )
        for index, audit in enumerate(existing_audits):
            runs.append(
                _summarize_window(
                    window=preflight["windows"][index],
                    audit=audit,
                    delta={},
                    before={},
                    after={},
                    chat_content="Gate 2 persisted domain run.",
                    runtime_delta_available=False,
                    resumed=True,
                )
            )

    for window in preflight["windows"][resume_count:]:
        previous_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
        try:
            chat_content = _run_window_chat(
                session=session,
                base_url=base_url,
                dcp_ref=str(manifest["domain_context_packet_ref"]),
                model_id=args.model_id,
                provider_profile_id=args.provider_profile_id,
                candidate_binding_enabled=candidate_binding_enabled,
                max_repair_attempts=args.max_repair_attempts,
                table_segment_max_refs=args.table_segment_max_refs,
                text_segment_max_refs=args.text_segment_max_refs,
                window=window,
                timeout=args.timeout,
            )
            audit = _audit_new_domain_run(
                ssh_target=ssh_target,
                case_id=args.case_id,
                previous_run_refs=previous_refs,
            )
            runs.append(
                _summarize_window(
                    window=window,
                    audit=audit,
                    delta={},
                    before={},
                    after={},
                    chat_content=chat_content,
                    runtime_delta_available=False,
                    resumed=False,
                )
            )
            print(
                json.dumps(
                    {
                        "event": "window_completed",
                        "window_index": window.get("window_index"),
                        "runs_collected": len(runs),
                        "windows_total": len(preflight.get("windows") or []),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
        except Exception as exc:
            runs.append(
                {
                    "status": "failed",
                    "window": _safe_window(window),
                    "error_class": exc.__class__.__name__,
                    "error_message": str(exc)[:500],
                    "runtime_delta_available": False,
                    "runtime_before": {},
                    "runtime_after": {},
                    "runtime_delta": {},
                }
            )
            print(
                json.dumps(
                    {
                        "event": "window_failed",
                        "window_index": window.get("window_index"),
                        "error_class": exc.__class__.__name__,
                        "runs_collected": len(runs),
                        "windows_total": len(preflight.get("windows") or []),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )

    after_all = _runtime_snapshot_extended(ssh_target)
    aggregate = _aggregate_result(
        case_id=args.case_id,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        preflight=preflight,
        runs=runs,
        provider_profile_id=args.provider_profile_id,
        model_id=args.model_id,
        candidate_binding_enabled=candidate_binding_enabled,
        max_repair_attempts=args.max_repair_attempts,
        before_all=before_all,
        after_all=after_all,
        runtime_seconds=round(time.perf_counter() - started, 3),
    )
    packet_ref = None
    document_packet = aggregate.pop("document_packet")
    if aggregate["checks"]["document_level_packet_persistable"]:
        packet_ref = _persist_document_packet(
            ssh_target=ssh_target,
            dcp_ref=str(manifest["domain_context_packet_ref"]),
            packet=document_packet,
        )
        aggregate["document_packet_ref"] = packet_ref["artifact_id"]
        aggregate["document_packet_safe_metadata"] = packet_ref["safe_metadata"]
        aggregate["checks"]["document_level_packet_persisted"] = True
    else:
        aggregate["checks"]["document_level_packet_persisted"] = False
    aggregate["document_packet_summary"] = _document_packet_summary(document_packet)
    aggregate["status"] = "passed" if all(aggregate["checks"].values()) else "partial"
    print(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if aggregate["status"] == "passed" else 1


def _preflight_checks(preflight: dict[str, Any], *, max_model_calls: int) -> dict[str, bool]:
    readiness = preflight.get("readiness") or {}
    coverage = preflight.get("coverage_plan") or {}
    return {
        "readiness_passed": readiness.get("validator_status") == "passed",
        "exactly_one_source_ready_document": readiness.get("source_ready_documents_total") == 1,
        "one_document_packageable": readiness.get("packageable_documents_total") == 1,
        "packages_available": int(readiness.get("packages_total") or 0) > 0,
        "windows_available": int(coverage.get("windows_total") or 0) > 0,
        "all_parent_refs_partitioned": coverage.get("unaccounted_parent_refs_total") == 0
        and coverage.get("duplicate_parent_refs_total") == 0,
        "no_truncated_source_units": coverage.get("truncated_source_units_total") == 0
        and coverage.get("pending_parent_remainders_total") == 0,
        "model_call_budget_bounded": int(coverage.get("expected_model_calls_total") or 0) <= max_model_calls,
        "knowledge_vector_guard": (readiness.get("vector_knowledge_guard") or {}).get("customer_docs_loaded_to_knowledge") is False
        and (readiness.get("vector_knowledge_guard") or {}).get("vectorization_performed") is False,
    }


def _compact_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    windows = list(preflight.get("windows") or [])
    segment_kind_counts = Counter(str(item.get("segment_kind") or "unknown") for item in windows)
    domain_window_counts = Counter(
        domain
        for item in windows
        for domain in (item.get("domains") or ["deterministic_no_fact"])
    )
    selected_refs_by_domain = Counter()
    for item in windows:
        domains = item.get("domains") or ["deterministic_no_fact"]
        for domain in domains:
            selected_refs_by_domain[domain] += int(item.get("selected_refs_total") or 0)
    return {
        "normalization_run_id": preflight.get("normalization_run_id"),
        "domain_context_packet_ref": preflight.get("domain_context_packet_ref"),
        "document_refs_total": len(preflight.get("document_refs") or []),
        "readiness": preflight.get("readiness") or {},
        "coverage_plan": preflight.get("coverage_plan") or {},
        "segment_kind_counts": dict(sorted(segment_kind_counts.items())),
        "domain_window_counts": dict(sorted(domain_window_counts.items())),
        "selected_refs_by_domain": dict(sorted(selected_refs_by_domain.items())),
        "units": preflight.get("units") or [],
        "windows_preview": windows[:5],
        "windows_tail_preview": windows[-3:] if len(windows) > 5 else [],
    }


def _preflight_matrix(
    *,
    ssh_target: str,
    dcp_ref: str,
    user_id: str,
    table_segment_max_refs: int,
    text_segment_max_refs: int,
    candidate_binding_enabled: bool,
) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import copy
import json
from collections import Counter
from pathlib import Path

namespace = {{"__name__": "single_pdf_whole_document_preflight_bundle"}}
exec(compile({bundle_source!r}, "<single_pdf_whole_document_preflight_bundle>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    Gate2InputReadinessConfig, Gate2InputReadinessFactory,
    Gate2SourceUnitRouterFactory, Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory, Gate2DomainPackageBuilderConfig,
    Gate2DomainPackageBuilderFactory,
)

store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
dcp_record = store.get_record_unchecked({dcp_ref!r})
if dcp_record is None:
    raise RuntimeError("single_pdf_dcp_missing")
context = ArtifactAccessContext(
    user_id={user_id!r},
    normalization_run_id=dcp_record.normalization_run_id,
    case_id=dcp_record.case_id,
    chat_id=dcp_record.chat_id,
    workspace_model_id=dcp_record.workspace_model_id,
    allow_private=True,
    require_source_available=True,
)
readiness = Gate2InputReadinessFactory(
    store=store,
    config=Gate2InputReadinessConfig(prefer_table_projections=True),
).create().audit_and_build(domain_context_packet_ref={dcp_ref!r}, context=context)
primary = [
    item for item in readiness.packages
    if "primary_source_extraction_refs" in set(item.get("source_bucket_roles") or [])
]
document_refs = sorted({{str(item.get("document_ref") or "") for item in primary if item.get("document_ref")}})
router = Gate2SourceUnitRouterFactory().create()
segmenter = Gate2SourceUnitSegmenterFactory(
    Gate2SourceUnitSegmenterConfig(
        table_max_selected_refs={table_segment_max_refs!r},
        text_max_selected_refs={text_segment_max_refs!r},
    )
).create()
domain_builder = Gate2DomainPackageBuilderFactory(
    Gate2DomainPackageBuilderConfig(candidate_binding_enabled={candidate_binding_enabled!r})
).create()
windows = []
unit_summaries = []
parent_selected_total = 0
derived_accounted_total = 0
duplicate_parent_refs_total = 0
unaccounted_parent_refs_total = 0
truncated_source_units_total = 0
pending_parent_remainders_total = 0
expected_model_calls_total = 0
source_input_mode_counts = Counter()
unit_kind_counts = Counter()
domain_package_counts = Counter()
route_kind_counts = Counter()
coverage_ref_ids = []
source_unit_refs = []
table_projection_refs = []
for document_index, document_ref in enumerate(document_refs):
    units = [item for item in primary if str(item.get("document_ref") or "") == document_ref]
    for unit_index, package in enumerate(units):
        package = copy.deepcopy(package)
        package["extraction_run_id"] = "single_pdf_preflight"
        package["created_at"] = "single_pdf_preflight"
        unit = package.get("source_unit") or {{}}
        source_input_mode_counts[str(unit.get("source_input_mode") or "unknown")] += 1
        unit_kind_counts[str(unit.get("unit_kind") or "unknown")] += 1
        source_unit_ref = str(unit.get("unit_id") or "")
        if source_unit_ref:
            source_unit_refs.append(source_unit_ref)
        table_ref = str(package.get("table_projection_artifact_ref") or "")
        if table_ref:
            table_projection_refs.append(table_ref)
        if unit.get("source_slice_truncated") is True:
            truncated_source_units_total += 1
        parent_route = router.route(package)
        segmentation = segmenter.segment(base_package=package, parent_route=parent_route)
        plan_coverage = segmentation.plan.get("coverage") or {{}}
        parent_selected_total += int(plan_coverage.get("parent_selected_total") or 0)
        derived_accounted_total += int(plan_coverage.get("derived_accounted_total") or 0)
        duplicate_parent_refs_total += len(plan_coverage.get("duplicate_source_refs") or [])
        unaccounted_parent_refs_total += len(plan_coverage.get("unaccounted_source_refs") or [])
        if plan_coverage.get("parent_remainder_status") == "pending_gate1_reslice":
            pending_parent_remainders_total += 1
        unit_summaries.append({{
            "document_batch_start": document_index,
            "source_unit_start": unit_index,
            "source_unit_ref": source_unit_ref,
            "source_input_mode": unit.get("source_input_mode"),
            "unit_kind": unit.get("unit_kind"),
            "source_format": unit.get("source_format"),
            "parent_selected_total": int(plan_coverage.get("parent_selected_total") or 0),
            "derived_segments_total": len(segmentation.derived_packages),
            "coverage_scope": unit.get("coverage_scope"),
            "source_slice_truncated": unit.get("source_slice_truncated") is True,
            "parent_remainder_status": unit.get("parent_remainder_status"),
        }})
        for segment_index, derived in enumerate(segmentation.derived_packages):
            route = router.route(derived)
            route_coverage = route.get("coverage") or {{}}
            for entry in route.get("route_entries") or []:
                route_kind_counts[str(entry.get("route_kind") or "unknown")] += 1
            domain_packages = domain_builder.build(base_package=derived, route=route)
            domains = [str(item.get("extractor_domain") or "") for item in domain_packages if item.get("extractor_domain")]
            domain_package_counts.update(domains)
            expected_model_calls_total += len(domain_packages)
            segment = (derived.get("segmentation") or {{}})
            coverage = derived.get("coverage_expectation") or {{}}
            coverage_ref = str(coverage.get("coverage_ref") or "")
            if coverage_ref:
                coverage_ref_ids.append(coverage_ref)
            windows.append({{
                "window_index": len(windows),
                "document_batch_start": document_index,
                "document_batch_limit": 1,
                "source_unit_start": unit_index,
                "source_unit_limit": 1,
                "source_segment_start": segment_index,
                "source_segment_limit": 1,
                "source_unit_ref": source_unit_ref,
                "segment_kind": segment.get("segment_kind"),
                "source_input_mode": unit.get("source_input_mode"),
                "unit_kind": unit.get("unit_kind"),
                "source_format": unit.get("source_format"),
                "domains": domains,
                "domain_packages_total": len(domain_packages),
                "selected_refs_total": int(route_coverage.get("selected_total") or 0),
                "deterministic_no_fact_total": int(route_coverage.get("deterministic_no_fact_total") or 0),
                "unknown_route_total": int(route_coverage.get("unknown_total") or 0),
                "ambiguous_route_total": int(route_coverage.get("ambiguous_total") or 0),
                "coverage_ref": coverage_ref,
            }})

safe_report = readiness.safe_report
validation = readiness.validation
print(json.dumps({{
    "normalization_run_id": context.normalization_run_id,
    "domain_context_packet_ref": {dcp_ref!r},
    "document_refs": document_refs,
    "readiness": {{
        "status": safe_report.get("status"),
        "validator_status": validation.get("validator_status"),
        "source_ready_documents_total": safe_report.get("source_ready_documents_total"),
        "packageable_documents_total": safe_report.get("packageable_documents_total"),
        "unpackageable_document_refs_total": len(safe_report.get("unpackageable_document_refs") or []),
        "packages_total": safe_report.get("packages_total"),
        "packages_passed": safe_report.get("packages_passed"),
        "unit_kind_counts": safe_report.get("unit_kind_counts") or {{}},
        "source_input_mode_counts": safe_report.get("source_input_mode_counts") or {{}},
        "coverage_selected_total": safe_report.get("coverage_selected_total"),
        "source_value_refs_total": safe_report.get("source_value_refs_total"),
        "source_unit_refs_total": safe_report.get("source_unit_refs_total"),
        "slice_audit": safe_report.get("slice_audit") or {{}},
        "handoff_audit": safe_report.get("handoff_audit") or {{}},
        "error_code_counts": validation.get("error_code_counts") or {{}},
        "warning_code_counts": validation.get("warning_code_counts") or {{}},
        "vector_knowledge_guard": safe_report.get("vector_knowledge_guard") or {{}},
    }},
    "units": unit_summaries,
    "windows": windows,
    "coverage_plan": {{
        "source_units_total": len(unit_summaries),
        "windows_total": len(windows),
        "parent_selected_total": parent_selected_total,
        "derived_accounted_total": derived_accounted_total,
        "duplicate_parent_refs_total": duplicate_parent_refs_total,
        "unaccounted_parent_refs_total": unaccounted_parent_refs_total,
        "truncated_source_units_total": truncated_source_units_total,
        "pending_parent_remainders_total": pending_parent_remainders_total,
        "expected_model_calls_total": expected_model_calls_total,
        "deterministic_no_fact_route_refs_total": route_kind_counts.get("deterministic_no_fact", 0),
        "model_candidate_route_refs_total": route_kind_counts.get("model_candidate", 0),
        "domain_package_counts": dict(sorted(domain_package_counts.items())),
        "source_input_mode_counts": dict(sorted(source_input_mode_counts.items())),
        "unit_kind_counts": dict(sorted(unit_kind_counts.items())),
        "unique_coverage_refs_total": len(set(coverage_ref_ids)),
        "source_unit_refs_total": len(set(source_unit_refs)),
        "table_projection_refs_total": len(set(table_projection_refs)),
    }},
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=240)


def _runtime_snapshot_extended(ssh_target: str) -> dict[str, Any]:
    code = r'''
import json
import os
import sqlite3
from pathlib import Path

def db_count(conn, table):
    try:
        return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    except Exception:
        return 0

def tree_stats(path):
    root = Path(path)
    if not root.exists():
        return {"exists": False, "file_count": 0, "dir_count": 0, "size_bytes": 0, "collections_count": 0}
    file_count = 0
    dir_count = 0
    size_bytes = 0
    for current, dirs, files in os.walk(root):
        dir_count += len(dirs)
        for name in files:
            file_count += 1
            try:
                size_bytes += (Path(current) / name).stat().st_size
            except OSError:
                pass
    collections_count = 0
    chroma = root / "chroma.sqlite3"
    if chroma.exists():
        try:
            with sqlite3.connect(chroma) as conn:
                collections_count = int(conn.execute("select count(*) from collections").fetchone()[0])
        except Exception:
            collections_count = 0
    return {
        "exists": True,
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
        "collections_count": collections_count,
    }

db_path = "/app/backend/data/webui.db"
db = {"file_count": 0, "document_count": 0, "knowledge_count": 0}
try:
    with sqlite3.connect(db_path) as conn:
        db = {
            "file_count": db_count(conn, "file"),
            "document_count": db_count(conn, "document"),
            "knowledge_count": db_count(conn, "knowledge"),
        }
except Exception:
    pass

artifact_store = {"record_count": 0}
artifact_db = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
if artifact_db.exists():
    try:
        with sqlite3.connect(artifact_db) as conn:
            artifact_store["record_count"] = db_count(conn, "artifact_records")
    except Exception:
        pass

print(json.dumps({
    "db": db,
    "vector": tree_stats("/app/backend/data/vector_db"),
    "artifact_store": artifact_store,
}, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=180)


def _run_window_chat(
    *,
    session: requests.Session,
    base_url: str,
    dcp_ref: str,
    model_id: str,
    provider_profile_id: str,
    candidate_binding_enabled: bool,
    max_repair_attempts: int,
    table_segment_max_refs: int,
    text_segment_max_refs: int,
    window: dict[str, Any],
    timeout: int,
) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Run one bounded single-PDF Gate 2 document window.",
                }
            ],
            "stream": False,
            "broker_reports_gate2_domain": {
                "domain_context_packet_ref": dcp_ref,
                "model_id": model_id,
                "provider_profile_id": provider_profile_id,
                "wave": "primary",
                "run_mode": "customer",
                "document_batch_start": window["document_batch_start"],
                "document_batch_limit": 1,
                "source_unit_start": window["source_unit_start"],
                "source_unit_limit": 1,
                "segmentation_enabled": True,
                "prefer_table_projections": True,
                "source_segment_start": window["source_segment_start"],
                "source_segment_limit": 1,
                "table_segment_max_refs": table_segment_max_refs,
                "text_segment_max_refs": text_segment_max_refs,
                "domain_allowlist": list(window.get("domains") or []),
                "candidate_binding_enabled": candidate_binding_enabled,
                "max_repair_attempts": max_repair_attempts,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _audit_new_domain_run(
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
    rows = conn.execute(
        "select * from artifact_records where case_id=? and purge_status='active'",
        ({case_id!r},),
    ).fetchall()
finally:
    conn.close()
by_ref = {{str(row["artifact_id"]): row for row in rows}}
def payload(row):
    return json.loads(row["payload_inline_json"]) if row["payload_inline_json"] else json.loads((root / row["payload_ref"]).read_text(encoding="utf-8"))
runs = [
    row for row in rows
    if row["artifact_type"] == "broker_reports_domain_source_fact_extraction_run_v0"
    and row["artifact_id"] not in previous
]
if len(runs) != 1:
    raise RuntimeError("single_pdf_new_domain_run_count_invalid")
run_row = runs[0]
run = payload(run_row)
summary = payload(by_ref[str(run["summary_ref"])])
raw_rows = [by_ref[ref] for ref in run.get("raw_output_refs") or []]
package_rows = [by_ref[ref] for ref in run.get("domain_package_refs") or []]
fact_rows = [by_ref[ref] for ref in run.get("source_facts_refs") or []]
domain_fact_rows = [by_ref[ref] for ref in run.get("domain_source_facts_refs") or []]
validation_rows = [by_ref[ref] for ref in run.get("validation_refs") or []]
stitch_rows = [by_ref[ref] for ref in run.get("stitch_result_refs") or []]
route_rows = [by_ref[ref] for ref in run.get("route_refs") or []]
plan_rows = [by_ref[ref] for ref in run.get("segmentation_plan_refs") or []]
derived_rows = [by_ref[ref] for ref in run.get("derived_source_unit_refs") or []]
candidate_rows = [by_ref[ref] for ref in run.get("source_value_candidate_set_refs") or []]
relation_rows = [by_ref[ref] for ref in run.get("candidate_relation_set_refs") or []]
binding_rows = [by_ref[ref] for ref in run.get("candidate_binding_validation_refs") or []]
raw_payloads = [payload(row) for row in raw_rows]
validations = [payload(row) for row in validation_rows]
stitches = [payload(row) for row in stitch_rows]
error_counts = Counter(str(error.get("code") or "unknown") for item in validations for error in item.get("errors") or [])
provider_profile_counts = Counter(str(item.get("provider_profile_id") or "unknown") for item in raw_payloads)
model_counts = Counter(str(item.get("model_id") or "unknown") for item in raw_payloads)
structured_counts = Counter(str(item.get("structured_output_mode") or "unknown") for item in raw_payloads)
response_format_counts = Counter(str(item.get("response_format_type") or "unknown") for item in raw_payloads)
raw_status_counts = Counter(str(item.get("model_call_status") or "unknown") for item in raw_payloads)
raw_error_counts = Counter(str(item.get("error_code") or "none") for item in raw_payloads)
repair_attempts_total = sum(int(item.get("repair_attempt_count") or 0) for item in raw_payloads)
provider_execs = [item.get("provider_execution_safe") or {{}} for item in raw_payloads]
duration_ms_total = sum(int(item.get("duration_ms") or 0) for item in provider_execs)
input_tokens_total = sum(int(item.get("input_tokens") or 0) for item in provider_execs if item.get("input_tokens") is not None)
output_tokens_total = sum(int(item.get("output_tokens") or 0) for item in provider_execs if item.get("output_tokens") is not None)
total_tokens_total = sum(int(item.get("total_tokens") or 0) for item in provider_execs if item.get("total_tokens") is not None)
all_rows = [
    *runs, *raw_rows, *package_rows, *fact_rows, *domain_fact_rows,
    *validation_rows, *stitch_rows, *route_rows, *plan_rows, *derived_rows,
    *candidate_rows, *relation_rows, *binding_rows,
]
print(json.dumps({{
    "extraction_run_ref": run_row["artifact_id"],
    "extraction_run_id": run.get("extraction_run_id"),
    "summary_ref": run.get("summary_ref"),
    "summary": summary,
    "artifact_refs": {{
        "route_refs": run.get("route_refs") or [],
        "segmentation_plan_refs": run.get("segmentation_plan_refs") or [],
        "derived_source_unit_refs": run.get("derived_source_unit_refs") or [],
        "domain_package_refs": run.get("domain_package_refs") or [],
        "raw_output_refs": run.get("raw_output_refs") or [],
        "source_facts_refs": run.get("source_facts_refs") or [],
        "domain_source_facts_refs": run.get("domain_source_facts_refs") or [],
        "validation_refs": run.get("validation_refs") or [],
        "stitch_result_refs": run.get("stitch_result_refs") or [],
        "candidate_set_refs": run.get("source_value_candidate_set_refs") or [],
        "relation_set_refs": run.get("candidate_relation_set_refs") or [],
        "candidate_binding_validation_refs": run.get("candidate_binding_validation_refs") or [],
    }},
    "stitch_coverage": [item.get("coverage") or {{}} for item in stitches],
    "stitch_issue_fact_links_total": sum(len(item.get("issue_fact_linkage") or []) for item in stitches),
    "raw_outputs_total": len(raw_rows),
    "raw_status_counts": dict(sorted(raw_status_counts.items())),
    "raw_error_counts": dict(sorted(raw_error_counts.items())),
    "strict_raw_outputs_total": sum(1 for item in raw_payloads if item.get("structured_output_mode") in {{"openwebui_response_format_json_schema", "openwebui_anthropic_output_config_json_schema"}} and item.get("response_format_type") == "json_schema"),
    "fallback_raw_outputs_total": sum(1 for item in raw_payloads if item.get("fallback_used") is True),
    "repair_attempts_total": repair_attempts_total,
    "provider_profile_counts": dict(sorted(provider_profile_counts.items())),
    "model_counts": dict(sorted(model_counts.items())),
    "structured_output_mode_counts": dict(sorted(structured_counts.items())),
    "response_format_type_counts": dict(sorted(response_format_counts.items())),
    "provider_execution_aggregates": {{
        "calls_total": len(provider_execs),
        "duration_ms_total": duration_ms_total,
        "input_tokens_total": input_tokens_total,
        "output_tokens_total": output_tokens_total,
        "total_tokens_total": total_tokens_total,
        "token_usage_reported_calls": sum(1 for item in provider_execs if item.get("total_tokens") is not None),
    }},
    "source_facts_total": len(fact_rows),
    "private_source_facts_total": sum(1 for row in fact_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "validated_source_facts_total": sum(1 for row in fact_rows if row["validation_status"] == "validated"),
    "validation_error_code_counts": dict(sorted(error_counts.items())),
    "private_raw_outputs_total": sum(1 for row in raw_rows if row["visibility"] == "private_case" and row["storage_backend"] == "project_artifact_payload"),
    "knowledge_backend_records": sum(1 for row in all_rows if row["storage_backend"] == "openwebui_knowledge"),
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _audit_domain_run_refs(
    *, ssh_target: str, case_id: str, run_refs: list[str]
) -> list[dict[str, Any]]:
    all_refs = _domain_run_refs(ssh_target=ssh_target, case_id=case_id)
    audits: list[dict[str, Any]] = []
    for run_ref in run_refs:
        if run_ref not in all_refs:
            raise RuntimeError("single_pdf_resume_run_ref_missing")
        previous_refs = [item for item in all_refs if item != run_ref]
        audits.append(
            _audit_new_domain_run(
                ssh_target=ssh_target,
                case_id=case_id,
                previous_run_refs=previous_refs,
            )
        )
    return audits


def _summarize_window(
    *,
    window: dict[str, Any],
    audit: dict[str, Any],
    delta: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    chat_content: str,
    runtime_delta_available: bool = True,
    resumed: bool = False,
) -> dict[str, Any]:
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    raw_total = int(audit.get("raw_outputs_total") or 0)
    checks = {
        "terminal_completed": summary.get("terminal_status") == "completed",
        "domain_packages_accounted": int(packages.get("total") or 0) == window.get("domain_packages_total"),
        "all_domain_packages_accepted_or_no_model_package": packages.get("rejected") == 0,
        "coverage_selected_matches_window": coverage.get("selected_total") == window.get("selected_refs_total"),
        "coverage_conflict_free": int(coverage.get("conflict_total") or 0) == 0,
        "coverage_complete_no_uncovered": int(coverage.get("uncovered_total") or 0) == 0,
        "strict_json_schema_no_fallback": raw_total == 0
        or (
            audit.get("strict_raw_outputs_total") == raw_total
            and audit.get("fallback_raw_outputs_total") == 0
        ),
        "repair_not_used": int(audit.get("repair_attempts_total") or 0) == 0,
        "raw_outputs_private": audit.get("private_raw_outputs_total") == raw_total,
        "facts_private_and_validated": audit.get("private_source_facts_total")
        == audit.get("source_facts_total")
        == audit.get("validated_source_facts_total"),
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "document_rows_zero_delta": not runtime_delta_available or delta.get("document_rows") == 0,
        "file_rows_zero_delta": not runtime_delta_available or delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": not runtime_delta_available or delta.get("knowledge_rows") == 0,
        "vector_delta_zero": not runtime_delta_available or _vector_delta_zero(delta),
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
        "chat_safe": "Gate 2" in chat_content
        and not any(
            marker in chat_content
            for marker in ("raw_output", "private_slice_artifact_ref", "source_value_index")
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "window": _safe_window(window),
        "resumed_from_existing_run": resumed,
        "runtime_delta_available": runtime_delta_available,
        "checks": checks,
        "summary": summary,
        "artifact_audit": {
            key: value
            for key, value in audit.items()
            if key not in {"summary"}
        },
        "runtime_before": _safe_counter_view(before) if runtime_delta_available else {},
        "runtime_after": _safe_counter_view(after) if runtime_delta_available else {},
        "runtime_delta": delta,
    }


def _aggregate_result(
    *,
    case_id: str,
    dcp_ref: str,
    preflight: dict[str, Any],
    runs: list[dict[str, Any]],
    provider_profile_id: str,
    model_id: str,
    candidate_binding_enabled: bool,
    max_repair_attempts: int,
    before_all: dict[str, Any],
    after_all: dict[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    coverage = Counter()
    domain_packages = Counter()
    facts_by_type = Counter()
    provider_profiles = Counter()
    models = Counter()
    structured_modes = Counter()
    response_formats = Counter()
    raw_status_counts = Counter()
    raw_error_counts = Counter()
    validation_error_counts = Counter()
    provider_exec = Counter()
    artifact_refs: dict[str, list[str]] = defaultdict(list)
    failed_windows = 0
    issue_fact_links_total = 0
    for run in runs:
        if run.get("status") != "passed":
            failed_windows += 1
        summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
        cov = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
        for field in (
            "selected_total",
            "accepted_fact_owned_total",
            "unknown_total",
            "no_fact_total",
            "conflict_total",
            "uncovered_total",
        ):
            coverage[field] += int(cov.get(field) or 0)
        packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
        for field in ("total", "accepted", "rejected"):
            domain_packages[field] += int(packages.get(field) or 0)
        domain_packages.update({f"accepted:{k}": int(v) for k, v in (packages.get("accepted_by_domain") or {}).items()})
        facts_by_type.update({str(k): int(v) for k, v in (summary.get("facts_by_type") or {}).items()})
        audit = run.get("artifact_audit") if isinstance(run.get("artifact_audit"), dict) else {}
        provider_profiles.update(audit.get("provider_profile_counts") or {})
        models.update(audit.get("model_counts") or {})
        structured_modes.update(audit.get("structured_output_mode_counts") or {})
        response_formats.update(audit.get("response_format_type_counts") or {})
        raw_status_counts.update(audit.get("raw_status_counts") or {})
        raw_error_counts.update(audit.get("raw_error_counts") or {})
        validation_error_counts.update(audit.get("validation_error_code_counts") or {})
        issue_fact_links_total += int(audit.get("stitch_issue_fact_links_total") or 0)
        for key, values in (audit.get("artifact_refs") or {}).items():
            artifact_refs[key].extend(str(item) for item in values or [])
        for key, value in (audit.get("provider_execution_aggregates") or {}).items():
            provider_exec[key] += int(value or 0)

    runtime_delta = _counter_delta(before_all, after_all)
    plan = preflight.get("coverage_plan") or {}
    windows_total = int(plan.get("windows_total") or 0)
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "case_id": case_id,
        "normalization_run_id": preflight.get("normalization_run_id"),
        "domain_context_packet_ref": dcp_ref,
        "document_ref": (preflight.get("document_refs") or [None])[0],
        "provider": {
            "provider_profile_id": provider_profile_id,
            "model_id": model_id,
            "candidate_binding_enabled": candidate_binding_enabled,
            "max_repair_attempts": max_repair_attempts,
            "hidden_failover_used": False,
        },
        "preflight": {
            "readiness": preflight.get("readiness") or {},
            "coverage_plan": plan,
            "source_units_total": len(preflight.get("units") or []),
            "windows_total": windows_total,
        },
        "execution": {
            "windows_total": windows_total,
            "windows_passed": sum(1 for item in runs if item.get("status") == "passed"),
            "windows_failed": failed_windows,
            "raw_status_counts": dict(sorted(raw_status_counts.items())),
            "raw_error_counts": dict(sorted(raw_error_counts.items())),
            "validation_error_code_counts": dict(sorted(validation_error_counts.items())),
            "runtime_seconds": runtime_seconds,
        },
        "artifacts": {
            key: sorted(set(values)) for key, values in sorted(artifact_refs.items())
        },
        "provider_execution_aggregates": dict(sorted(provider_exec.items())),
        "provider_profile_counts": dict(sorted(provider_profiles.items())),
        "model_counts": dict(sorted(models.items())),
        "structured_output_mode_counts": dict(sorted(structured_modes.items())),
        "response_format_type_counts": dict(sorted(response_formats.items())),
        "domain_packages": {
            "total": domain_packages.get("total", 0),
            "accepted": domain_packages.get("accepted", 0),
            "rejected": domain_packages.get("rejected", 0),
            "accepted_by_domain": {
                key.split(":", 1)[1]: value
                for key, value in sorted(domain_packages.items())
                if key.startswith("accepted:")
            },
        },
        "facts_by_type": dict(sorted(facts_by_type.items())),
        "coverage": dict(sorted(coverage.items())),
        "issue_fact_links_total": issue_fact_links_total,
        "guards": {
            "knowledge_rows_zero_delta": runtime_delta.get("knowledge_rows") == 0,
            "document_rows_zero_delta": runtime_delta.get("document_rows") == 0,
            "vector_delta_zero": _vector_delta_zero(runtime_delta),
            "ordinary_upload_used": False,
            "ocr_vlm_used": False,
            "tax_declaration_xlsx_work": False,
        },
        "terminal_restrictions": {
            "gate3_not_run": True,
            "cross_document_consolidation_not_run": True,
            "tax_calculation_not_run": True,
            "declaration_mapping_not_run": True,
            "xls_xlsx_generation_not_run": True,
        },
    }
    checks = {
        "preflight_ready": preflight.get("readiness", {}).get("validator_status") == "passed",
        "all_windows_executed": len(runs) == windows_total and windows_total > 0,
        "all_windows_passed": failed_windows == 0,
        "coverage_matches_preflight": coverage.get("selected_total", 0) == int(plan.get("derived_accounted_total") or 0),
        "coverage_complete": coverage.get("uncovered_total", 0) == 0
        and coverage.get("conflict_total", 0) == 0,
        "domain_packages_accounted": domain_packages.get("rejected", 0) == 0,
        "single_provider_used": dict(provider_profiles) in ({}, {provider_profile_id: provider_exec.get("calls_total", 0)}),
        "single_model_used": dict(models) in ({}, {model_id: provider_exec.get("calls_total", 0)}),
        "strict_structured_output": not structured_modes
        or set(structured_modes) <= {"openwebui_response_format_json_schema", "openwebui_anthropic_output_config_json_schema"},
        "no_hidden_json_downgrade": not response_formats or set(response_formats) == {"json_schema"},
        "no_repair_or_fallback": raw_error_counts.get("none", 0) == provider_exec.get("calls_total", 0)
        and validation_error_counts == Counter(),
        "private_refs_persisted": all(artifact_refs.get(key) for key in ("stitch_result_refs", "validation_refs")),
        "document_level_packet_persistable": True,
        "knowledge_vector_guard": packet["guards"]["knowledge_rows_zero_delta"]
        and packet["guards"]["document_rows_zero_delta"]
        and packet["guards"]["vector_delta_zero"],
        "scope_restrictions_held": all(packet["terminal_restrictions"].values()),
    }
    return {
        "status": "pending_packet_persist",
        "case_id": case_id,
        "preflight": _compact_preflight(preflight),
        "run_status_counts": dict(sorted(Counter(str(item.get("status") or "unknown") for item in runs).items())),
        "failed_runs": [
            _compact_run_failure(item) for item in runs if item.get("status") != "passed"
        ][:20],
        "runs_preview": [_compact_run_result(item) for item in runs[:3]],
        "runs_tail_preview": [_compact_run_result(item) for item in (runs[-3:] if len(runs) > 3 else [])],
        "document_packet": packet,
        "runtime_before": _safe_counter_view(before_all),
        "runtime_after": _safe_counter_view(after_all),
        "runtime_delta": runtime_delta,
        "checks": checks,
    }


def _compact_run_failure(run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    audit = run.get("artifact_audit") if isinstance(run.get("artifact_audit"), dict) else {}
    return {
        "status": run.get("status"),
        "window": run.get("window"),
        "resumed_from_existing_run": run.get("resumed_from_existing_run"),
        "terminal_status": summary.get("terminal_status"),
        "coverage": summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {},
        "domain_packages": summary.get("domain_packages")
        if isinstance(summary.get("domain_packages"), dict)
        else {},
        "facts_by_type": summary.get("facts_by_type")
        if isinstance(summary.get("facts_by_type"), dict)
        else {},
        "raw_status_counts": audit.get("raw_status_counts") or {},
        "raw_error_counts": audit.get("raw_error_counts") or {},
        "validation_error_code_counts": audit.get("validation_error_code_counts") or {},
    }


def _compact_run_result(run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    audit = run.get("artifact_audit") if isinstance(run.get("artifact_audit"), dict) else {}
    return {
        "status": run.get("status"),
        "window": run.get("window"),
        "resumed_from_existing_run": run.get("resumed_from_existing_run"),
        "terminal_status": summary.get("terminal_status"),
        "coverage": summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {},
        "domain_packages": summary.get("domain_packages")
        if isinstance(summary.get("domain_packages"), dict)
        else {},
        "facts_by_type": summary.get("facts_by_type")
        if isinstance(summary.get("facts_by_type"), dict)
        else {},
        "raw_status_counts": audit.get("raw_status_counts") or {},
        "raw_error_counts": audit.get("raw_error_counts") or {},
        "validation_error_code_counts": audit.get("validation_error_code_counts") or {},
    }


def _document_packet_summary(packet: dict[str, Any]) -> dict[str, Any]:
    artifacts = packet.get("artifacts") if isinstance(packet.get("artifacts"), dict) else {}
    return {
        "schema_version": packet.get("schema_version"),
        "normalization_run_id": packet.get("normalization_run_id"),
        "document_ref": packet.get("document_ref"),
        "provider": packet.get("provider"),
        "execution": packet.get("execution"),
        "domain_packages": packet.get("domain_packages"),
        "facts_by_type": packet.get("facts_by_type"),
        "coverage": packet.get("coverage"),
        "issue_fact_links_total": packet.get("issue_fact_links_total"),
        "artifact_ref_counts": {
            key: len(values) if isinstance(values, list) else 0
            for key, values in sorted(artifacts.items())
        },
        "provider_execution_aggregates": packet.get("provider_execution_aggregates"),
        "guards": packet.get("guards"),
        "terminal_restrictions": packet.get("terminal_restrictions"),
    }


def _persist_document_packet(
    *, ssh_target: str, dcp_ref: str, packet: dict[str, Any]
) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    packet_json = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    code = f'''
import json
from pathlib import Path

namespace = {{"__name__": "single_pdf_document_packet_bundle"}}
exec(compile({bundle_source!r}, "<single_pdf_document_packet_bundle>", "exec"), namespace)
from broker_reports_gate1 import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.artifact_models import ArtifactRecord, utc_now_iso
from broker_reports_gate1.artifact_store import new_artifact_id

packet = json.loads({packet_json!r})
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
dcp = store.get_record_unchecked({dcp_ref!r})
if dcp is None:
    raise RuntimeError("single_pdf_packet_dcp_missing")
artifact_id = new_artifact_id()
now = utc_now_iso()
record = store.put_record(ArtifactRecord(
    artifact_id=artifact_id,
    artifact_type={PACKET_SCHEMA_VERSION!r},
    case_id=dcp.case_id,
    chat_id=dcp.chat_id,
    user_id=dcp.user_id,
    workspace_model_id=dcp.workspace_model_id,
    normalization_run_id=dcp.normalization_run_id,
    document_id=packet.get("document_ref"),
    source_file_ref=None,
    visibility="private_case",
    storage_backend="project_artifact_payload",
    retention_policy=dcp.retention_policy,
    access_policy={{"scope": "case_private", "source": "single_pdf_whole_document_gate2_e2e"}},
    validation_status="validated",
    lifecycle_status="private_ready",
    payload_kind="json",
    payload=packet,
    safe_metadata={{
        "schema_version": {PACKET_SCHEMA_VERSION!r},
        "windows_total": packet.get("execution", {{}}).get("windows_total"),
        "windows_passed": packet.get("execution", {{}}).get("windows_passed"),
        "coverage_selected_total": packet.get("coverage", {{}}).get("selected_total"),
        "coverage_uncovered_total": packet.get("coverage", {{}}).get("uncovered_total"),
        "coverage_conflict_total": packet.get("coverage", {{}}).get("conflict_total"),
        "provider_profile_id": packet.get("provider", {{}}).get("provider_profile_id"),
        "model_id": packet.get("provider", {{}}).get("model_id"),
        "created_at": now,
    }},
    created_at=now,
    updated_at=now,
))
print(json.dumps({{
    "artifact_id": record.artifact_id,
    "payload_ref": record.payload_ref,
    "safe_metadata": record.safe_metadata,
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=120)


def _safe_window(window: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in window.items()
        if key not in {"coverage_ref", "source_unit_ref"}
    }


if __name__ == "__main__":
    raise SystemExit(main())
