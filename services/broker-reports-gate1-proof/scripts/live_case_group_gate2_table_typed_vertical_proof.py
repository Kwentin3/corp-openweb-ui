#!/usr/bin/env python3
"""Run bounded live typed Gate 2 extraction from normalized table projections."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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

from live_case_group_gate2_domain_vertical_proof import (  # noqa: E402
    _audit_new_run,
    _domain_run_refs,
)
from live_case_group_gate2_extraction_proof import _case_manifest  # noqa: E402
from live_case_group_process_false_gate1_run import (  # noqa: E402
    _counter_delta,
    _select_passport_model,
    _vector_delta_zero,
)
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


DEFAULT_CASE_ID = ""
TYPED_DOMAINS = {
    "trade_operation",
    "income",
    "withholding_tax",
    "fee_commission",
    "cash_movement",
    "currency_fx",
    "position_snapshot",
    "document_summary_evidence",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--provider-profile-id", default="openai_gpt")
    parser.add_argument("--target-kind", choices=("native", "pdf", "all"), default="all")
    parser.add_argument("--target-domain", choices=sorted(TYPED_DOMAINS), default=None)
    parser.add_argument("--candidate-binding", action="store_true")
    parser.add_argument("--max-repair-attempts", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    if not args.case_id:
        raise RuntimeError("case_id_required_for_table_typed_vertical")

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
    if manifest.get("blocker"):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker": manifest.get("blocker"),
                    "case_id": args.case_id,
                    "active_records_total": manifest.get("active_records_total"),
                    "domain_context_packets_total": manifest.get(
                        "domain_context_packets_total"
                    ),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if manifest.get("owner_matches_authenticated_user") is not True:
        raise RuntimeError("case_owner_does_not_match_authenticated_user")
    targets = _select_table_targets(
        ssh_target=ssh_target,
        dcp_ref=str(manifest["domain_context_packet_ref"]),
        user_id=str(current_user["id"]),
    )
    selected = _filter_targets(
        targets=targets,
        target_kind=args.target_kind,
        target_domain=args.target_domain,
    )
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "passed" if selected else "blocked",
                    "case_id": args.case_id,
                    "candidate_binding_enabled": args.candidate_binding,
                    "provider_profile_id": args.provider_profile_id,
                    "selected_targets": [_safe_target(item) for item in selected],
                    "candidate_summary": _compact_candidate_summary(
                        targets["candidate_summary"]
                    ),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if selected else 2
    if not selected:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker": "no_typed_table_projection_target",
                    "case_id": args.case_id,
                    "candidate_binding_enabled": args.candidate_binding,
                    "provider_profile_id": args.provider_profile_id,
                    "candidate_summary": _compact_candidate_summary(
                        targets["candidate_summary"]
                    ),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    model_id = (
        args.model_id
        or env.get("OPENWEBUI_GATE2_MODEL_ID")
        or env.get("OPENWEBUI_PASSPORT_MODEL_ID")
        or _select_passport_model(session, base_url)
    )
    runs = []
    for target in selected:
        previous_run_refs = _domain_run_refs(ssh_target=ssh_target, case_id=args.case_id)
        before = _runtime_snapshot(ssh_target)
        chat_content = _run_chat(
            session=session,
            base_url=base_url,
            dcp_ref=str(manifest["domain_context_packet_ref"]),
            model_id=model_id,
            target=target,
            candidate_binding_enabled=args.candidate_binding,
            provider_profile_id=args.provider_profile_id,
            max_repair_attempts=args.max_repair_attempts,
            timeout=args.timeout,
        )
        after = _runtime_snapshot(ssh_target)
        delta = _counter_delta(before, after)
        audit = _audit_new_run(
            ssh_target=ssh_target,
            case_id=args.case_id,
            previous_run_refs=previous_run_refs,
        )
        runs.append(
            _summarize_run(
                target=target,
                model_id=model_id,
                audit=audit,
                delta=delta,
                before=before,
                after=after,
                chat_content=chat_content,
            )
        )
    checks = {
        "all_requested_targets_passed": all(item["status"] == "passed" for item in runs),
        "at_least_one_typed_fact": any(
            int((item.get("summary") or {}).get("typed_facts_total") or 0) > 0
            for item in runs
        ),
        "native_typed_passed": any(
            item["target"]["target_kind"] == "native" and item["status"] == "passed"
            for item in runs
        )
        if args.target_kind in {"native", "all"}
        else True,
        "pdf_typed_passed_or_not_requested": any(
            item["target"]["target_kind"] == "pdf" and item["status"] == "passed"
            for item in runs
        )
        if args.target_kind in {"pdf", "all"}
        else True,
    }
    status = "passed" if all(checks.values()) else "failed"
    output = {
        "status": status,
        "case_id": args.case_id,
        "model_id": model_id,
        "runtime_path": "broker_reports_gate2_domain_source_fact_pipe -> Gate2DomainSourceFactRuntimeFactory.create",
        "prefer_table_projections": True,
        "candidate_binding_enabled": args.candidate_binding,
        "provider_profile_id": args.provider_profile_id,
        "selected_targets": [_safe_target(item) for item in selected],
        "runs": runs,
        "checks": checks,
        "candidate_summary": _compact_candidate_summary(targets["candidate_summary"]),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _compact_candidate_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "safe_candidate_matrix"}


def _safe_target(target: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in target.items() if key != "headers"}


def _filter_targets(
    *,
    targets: dict[str, Any],
    target_kind: str,
    target_domain: str | None,
) -> list[dict[str, Any]]:
    source = (
        targets.get("eligible_targets") if target_domain else targets.get("selected_targets")
    ) or []
    values = [
        item
        for item in source
        if (target_kind == "all" or item["target_kind"] == target_kind)
        and (target_domain is None or item["domain"] == target_domain)
    ]
    if target_domain is None:
        return values
    selected: list[dict[str, Any]] = []
    for kind in ("native", "pdf"):
        if target_kind not in {"all", kind}:
            continue
        matches = [item for item in values if item["target_kind"] == kind]
        if matches:
            selected.append(matches[0])
    return selected


def _select_table_targets(*, ssh_target: str, dcp_ref: str, user_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import json
from collections import Counter
from pathlib import Path

namespace = {{"__name__": "gate2_table_typed_vertical_preflight_bundle"}}
exec(compile({bundle_source!r}, "<gate2_table_typed_vertical_preflight_bundle>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    Gate2InputReadinessConfig, Gate2InputReadinessFactory,
    Gate2SourceUnitRouterFactory, Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory,
)

typed_domains = {sorted(TYPED_DOMAINS)!r}
store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
record = store.get_record_unchecked({dcp_ref!r})
if record is None:
    raise RuntimeError("gate2_table_typed_dcp_missing")
context = ArtifactAccessContext(
    user_id={user_id!r}, normalization_run_id=record.normalization_run_id,
    case_id=record.case_id, chat_id=record.chat_id,
    workspace_model_id=record.workspace_model_id,
    allow_private=True, require_source_available=True,
)
readiness = Gate2InputReadinessFactory(
    store=store,
    config=Gate2InputReadinessConfig(prefer_table_projections=True),
).create().audit_and_build(domain_context_packet_ref={dcp_ref!r}, context=context)
primary = [
    item for item in readiness.packages
    if "primary_source_extraction_refs" in set(item.get("source_bucket_roles") or [])
]
document_refs = sorted({{str(item.get("document_ref") or "") for item in primary}})
candidates = []
for document_index, document_ref in enumerate(document_refs):
    units = [item for item in primary if str(item.get("document_ref") or "") == document_ref]
    for unit_index, package in enumerate(units):
        unit = package.get("source_unit") or {{}}
        if unit.get("source_input_mode") != "normalized_table_projection":
            continue
        route = Gate2SourceUnitRouterFactory().create().route(package)
        segmentation = Gate2SourceUnitSegmenterFactory(
            Gate2SourceUnitSegmenterConfig(table_max_selected_refs=1)
        ).create().segment(base_package=package, parent_route=route)
        for segment_index, derived in enumerate(segmentation.derived_packages):
            derived_route = Gate2SourceUnitRouterFactory().create().route(derived)
            entries = [
                item for item in derived_route.get("route_entries") or []
                if item.get("route_kind") == "model_candidate"
            ]
            domains = sorted({{domain for item in entries for domain in item.get("candidate_domains") or []}})
            typed = [domain for domain in domains if domain in typed_domains]
            confidence = Counter(str(item.get("confidence") or "low") for item in entries)
            source_format = str(unit.get("source_format") or "unknown")
            single_typed = len(typed) == 1 and len(domains) == 1
            eligible = bool(entries) and single_typed and unit.get("semantic_table_truth_claimed") is False
            target_kind = "pdf" if source_format == "pdf" else "native"
            rows = [
                row for row in ((derived.get("source_unit") or {{}}).get("model_source_projection") or {{}}).get("rows") or []
                if row.get("row_ref") in set(derived_route.get("selected_source_refs") or [])
            ]
            cell_refs = {{
                str(cell.get("cell_ref") or "")
                for row in rows
                for cell in row.get("cells") or []
                if cell.get("cell_ref")
            }}
            value_refs = set()
            for row in rows:
                for cell in row.get("cells") or []:
                    refs = cell.get("source_value_refs") if isinstance(cell.get("source_value_refs"), list) else []
                    for ref in refs:
                        if ref:
                            value_refs.add(str(ref))
                    if cell.get("source_value_ref"):
                        value_refs.add(str(cell.get("source_value_ref")))
            headers = []
            for row in ((derived.get("source_unit") or {{}}).get("model_source_projection") or {{}}).get("rows") or []:
                for cell in row.get("cells") or []:
                    label = str(cell.get("header_label") or "")
                    if label and label not in headers:
                        headers.append(label)
            candidates.append({{
                "eligible": eligible,
                "target_kind": target_kind,
                "domain": typed[0] if typed else "",
                "domains": domains,
                "document_batch_start": document_index,
                "document_batch_limit": 1,
                "source_unit_start": unit_index,
                "source_unit_limit": 1,
                "source_segment_start": segment_index,
                "source_segment_limit": 1,
                "source_format": source_format,
                "projection_quality": (unit.get("table_quality") or {{}}).get("reconstruction_quality"),
                "semantic_table_truth_claimed": unit.get("semantic_table_truth_claimed"),
                "selected_refs_total": len(derived_route.get("selected_source_refs") or []),
                "model_candidates_total": len(entries),
                "high_confidence_candidates": confidence.get("high", 0),
                "medium_confidence_candidates": confidence.get("medium", 0),
                "low_confidence_candidates": confidence.get("low", 0),
                "selected_rows_total": len(rows),
                "selected_cell_refs_total": len(cell_refs),
                "selected_source_value_refs_total": len(value_refs),
                "headers": headers[:12],
                "derived_package_size_bytes": len(json.dumps(derived, ensure_ascii=False, sort_keys=True).encode("utf-8")),
            }})

def rank(item):
    return (
        0 if item["eligible"] else 1,
        0 if item["domain"] == "cash_movement" else 1,
        -item["high_confidence_candidates"],
        item["medium_confidence_candidates"],
        item["low_confidence_candidates"],
        item["derived_package_size_bytes"],
        item["document_batch_start"],
        item["source_unit_start"],
        item["source_segment_start"],
    )

selected = []
for target_kind in ("native", "pdf"):
    values = [item for item in candidates if item["target_kind"] == target_kind and item["eligible"]]
    if values:
        selected.append(sorted(values, key=rank)[0])
print(json.dumps({{
    "selected_targets": selected,
    "eligible_targets": sorted(
        [item for item in candidates if item["eligible"]],
        key=rank,
    ),
    "candidate_summary": {{
        "readiness_status": readiness.validation.get("validator_status"),
        "packages_total": len(readiness.packages),
        "table_candidates_total": len(candidates),
        "eligible_table_targets_total": sum(1 for item in candidates if item["eligible"]),
        "eligible_by_kind": {{
            "native": sum(1 for item in candidates if item["eligible"] and item["target_kind"] == "native"),
            "pdf": sum(1 for item in candidates if item["eligible"] and item["target_kind"] == "pdf"),
        }},
        "safe_candidate_matrix": sorted([
            {{
                "target_kind": item["target_kind"],
                "eligible": item["eligible"],
                "domain": item["domain"],
                "domains": item["domains"],
                "source_format": item["source_format"],
                "projection_quality": item["projection_quality"],
                "document_batch_start": item["document_batch_start"],
                "source_unit_start": item["source_unit_start"],
                "source_segment_start": item["source_segment_start"],
                "selected_refs_total": item["selected_refs_total"],
                "model_candidates_total": item["model_candidates_total"],
                "high": item["high_confidence_candidates"],
                "medium": item["medium_confidence_candidates"],
                "low": item["low_confidence_candidates"],
                "selected_cell_refs_total": item["selected_cell_refs_total"],
                "selected_source_value_refs_total": item["selected_source_value_refs_total"],
                "headers": item["headers"],
                "derived_package_size_bytes": item["derived_package_size_bytes"],
            }}
            for item in candidates
        ], key=lambda item: (
            item["target_kind"], not item["eligible"], item["document_batch_start"],
            item["source_unit_start"], item["source_segment_start"],
        ))[:80],
    }},
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=240)


def _run_chat(
    *,
    session,
    base_url,
    dcp_ref,
    model_id,
    target,
    candidate_binding_enabled,
    provider_profile_id,
    max_repair_attempts,
    timeout,
) -> str:
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": FUNCTION_ID,
            "messages": [
                {
                    "role": "user",
                    "content": "Run one bounded live typed Gate 2 table-domain extraction.",
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
                "prefer_table_projections": True,
                "source_segment_start": target["source_segment_start"],
                "source_segment_limit": 1,
                "table_segment_max_refs": 1,
                "domain_allowlist": [target["domain"]],
                "candidate_binding_enabled": candidate_binding_enabled,
                "provider_profile_id": provider_profile_id,
                "max_repair_attempts": max_repair_attempts,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def _summarize_run(
    *,
    target: dict[str, Any],
    model_id: str,
    audit: dict[str, Any],
    delta: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    chat_content: str,
) -> dict[str, Any]:
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    packages = summary.get("domain_packages") if isinstance(summary.get("domain_packages"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    facts_by_type = summary.get("facts_by_type") if isinstance(summary.get("facts_by_type"), dict) else {}
    domain = target["domain"]
    typed_fact_accepted = (
        int(facts_by_type.get(domain) or 0) > 0
        and int(summary.get("typed_facts_total") or 0) > 0
    )
    all_selected_domain_packages_accepted = (
        packages.get("accepted") == packages.get("total")
        and packages.get("rejected") == 0
    )
    complete_conflict_free_selected_unit = (
        coverage.get("uncovered_total") == 0
        and coverage.get("conflict_total") == 0
        and audit.get("complete_stitch_total") == 1
    )
    forbidden_errors = {
        "source_fact_provenance_missing",
        "source_fact_completeness_overstated",
        "source_fact_coverage_gap",
        "source_fact_issue_not_carried",
        "source_fact_unknown_value_ref",
        "source_fact_normalized_value_unreproducible",
    }
    error_codes = set((audit.get("validation_error_code_counts") or {}).keys())
    checks = {
        "target_is_normalized_table_projection": target.get("eligible") is True,
        "target_single_typed_domain": domain in TYPED_DOMAINS and target.get("domains") == [domain],
        "domain_runtime_terminal": summary.get("terminal_status") == "completed",
        "typed_fact_accepted": typed_fact_accepted,
        "no_unknown_only_result": int(summary.get("typed_facts_total") or 0) > 0,
        "all_selected_domain_packages_accepted": all_selected_domain_packages_accepted,
        "complete_conflict_free_selected_unit": complete_conflict_free_selected_unit,
        "no_blocking_validation_errors_after_repair": not (forbidden_errors & error_codes)
        or (
            typed_fact_accepted
            and all_selected_domain_packages_accepted
            and complete_conflict_free_selected_unit
        ),
        "strict_json_schema_no_fallback": audit.get("strict_raw_outputs_total") == audit.get("raw_outputs_total")
        and audit.get("fallback_raw_outputs_total") == 0,
        "raw_outputs_private": audit.get("private_raw_outputs_total") == audit.get("raw_outputs_total"),
        "facts_private_and_validated": audit.get("private_source_facts_total")
        == audit.get("source_facts_total")
        == audit.get("validated_source_facts_total"),
        "artifactstore_no_knowledge": audit.get("knowledge_backend_records") == 0,
        "document_rows_zero_delta": delta.get("document_rows") == 0,
        "file_rows_zero_delta": delta.get("file_rows") == 0,
        "knowledge_rows_zero_delta": delta.get("knowledge_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(delta),
        "no_tax_declaration_xlsx": summary.get("no_tax_declaration_xlsx_work") is True,
        "chat_safe": "Gate 2" in chat_content
        and "raw_output" not in chat_content
        and "source_value_index" not in chat_content
        and "private_slice_artifact_ref" not in chat_content,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "target": _safe_target(target),
        "model_id": model_id,
        "checks": checks,
        "summary": summary,
        "artifact_audit": audit,
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": delta,
    }


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
        raise RuntimeError("gate2_table_typed_remote_result_invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
