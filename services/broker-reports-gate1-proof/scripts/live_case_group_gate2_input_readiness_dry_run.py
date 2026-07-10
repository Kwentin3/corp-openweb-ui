#!/usr/bin/env python3
"""Read-only Gate 2 input-readiness dry run over existing process=false artifacts.

The script does not upload files, invoke chat, call an LLM, or persist Gate 2
packages. It executes the canonical self-contained bundle inside the OpenWebUI
container and prints only safe aggregate proof.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from live_case_group_process_false_gate1_run import _counter_delta, _vector_delta_zero
from live_no_rag_source_intake_smoke import (
    ROOT,
    _default_ssh_target,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
)


DEFAULT_CASE_ID = "customer_case_group_002_process_false_gate1_20260709175007"
BUNDLE = ROOT / "services" / "broker-reports-gate1-proof" / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    before = _runtime_snapshot(ssh_target)
    dry_run = _remote_dry_run(ssh_target=ssh_target, case_id=args.case_id)
    after = _runtime_snapshot(ssh_target)
    runtime_delta = _counter_delta(before, after)
    safe_report = dry_run.get("safe_report") if isinstance(dry_run.get("safe_report"), dict) else {}
    validation = dry_run.get("validation") if isinstance(dry_run.get("validation"), dict) else {}
    bucket_counts = safe_report.get("bucket_counts") if isinstance(safe_report.get("bucket_counts"), dict) else {}
    safety_flags = safe_report.get("safety_flags") if isinstance(safe_report.get("safety_flags"), dict) else {}
    checks = {
        "canonical_bundle_used": dry_run.get("canonical_bundle_used") is True,
        "factory_path_used": dry_run.get("factory_path_used") is True,
        "validator_passed": validation.get("validator_status") == "passed",
        "source_ready_total_is_15": safe_report.get("source_ready_documents_total") == 15,
        "all_source_ready_documents_packageable": (
            safe_report.get("source_ready_documents_total")
            == safe_report.get("packageable_documents_total")
            and safe_report.get("no_source_ready_document_loss") is True
        ),
        "primary_packages_available": int(bucket_counts.get("primary_source_extraction_refs") or 0) > 0,
        "secondary_packages_available": int(bucket_counts.get("secondary_source_extraction_refs") or 0) > 0,
        "duplicate_non_primary_packages_available": int(
            bucket_counts.get("duplicate_or_non_primary_refs") or 0
        )
        > 0,
        "source_value_refs_available": int(safe_report.get("source_value_refs_total") or 0) > 0,
        "row_segment_coverage_ready": safe_report.get("row_segment_coverage_ready") is True,
        "artifactstore_unchanged": (
            (safe_report.get("vector_knowledge_guard") or {}).get("artifactstore_unchanged") is True
        ),
        "no_source_fact_llm_call": safety_flags.get("source_fact_llm_call_performed") is False,
        "no_tax_or_declaration_work": (
            safety_flags.get("tax_calculation_performed") is False
            and safety_flags.get("declaration_generated") is False
            and safety_flags.get("xlsx_generated") is False
        ),
        "document_rows_zero_delta": runtime_delta.get("document_rows") == 0,
        "knowledge_rows_zero_delta": runtime_delta.get("knowledge_rows") == 0,
        "vector_delta_zero": _vector_delta_zero(runtime_delta),
    }
    output = {
        "status": "passed" if checks and all(checks.values()) else "failed",
        "case_id": args.case_id,
        "checks": checks,
        "safe_report": safe_report,
        "validation": validation,
        "package_inventory": dry_run.get("package_inventory") or {},
        "runtime_before": _safe_counter_view(before),
        "runtime_after": _safe_counter_view(after),
        "runtime_delta": runtime_delta,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def _remote_dry_run(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f"""
import json
from pathlib import Path

bundle_source = {bundle_source!r}
namespace = {{"__name__": "broker_reports_gate2_input_readiness_live_bundle"}}
exec(compile(bundle_source, "<broker_reports_gate2_input_readiness_live_bundle>", "exec"), namespace)

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate2InputReadinessFactory,
)

case_id = {case_id!r}
store = ArtifactStoreFactory(
    ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
        payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
    )
).create()
records = store.list_by_case(case_id)
dcp_records = [record for record in records if record.artifact_type == "domain_context_packet_v0"]
if len(dcp_records) != 1:
    raise RuntimeError("gate2_case_domain_context_packet_count_invalid")
dcp_record = dcp_records[0]
context = ArtifactAccessContext(
    user_id=dcp_record.user_id,
    normalization_run_id=dcp_record.normalization_run_id,
    case_id=dcp_record.case_id,
    chat_id=dcp_record.chat_id,
    workspace_model_id=dcp_record.workspace_model_id,
    allow_private=True,
    require_source_available=True,
)
result = Gate2InputReadinessFactory(store=store).create().audit_and_build(
    domain_context_packet_ref=dcp_record.artifact_id,
    context=context,
)
validation = result.validation
primary_packages = [
    package for package in result.packages
    if "primary_source_extraction_refs" in (package.get("source_bucket_roles") or [])
]
non_primary_packages = [
    package for package in result.packages
    if set(package.get("source_bucket_roles") or [])
    & {{"secondary_source_extraction_refs", "duplicate_or_non_primary_refs"}}
]
truncated_packages = [
    package for package in result.packages
    if (package.get("source_unit") or {{}}).get("source_slice_truncated") is True
]
print(json.dumps({{
    "canonical_bundle_used": True,
    "factory_path_used": True,
    "safe_report": result.safe_report,
    "validation": {{
        "validator_status": validation.get("validator_status"),
        "errors_count": validation.get("errors_count"),
        "error_code_counts": validation.get("error_code_counts") or {{}},
        "warnings_count": validation.get("warnings_count"),
        "warning_code_counts": validation.get("warning_code_counts") or {{}},
        "source_ready_refs_total": validation.get("source_ready_refs_total"),
        "packageable_documents_total": len(validation.get("packageable_document_refs") or []),
        "unpackageable_document_refs": validation.get("unpackageable_document_refs") or [],
        "packages_total": validation.get("packages_total"),
        "packages_passed": validation.get("packages_passed"),
        "artifactstore_unchanged": validation.get("artifactstore_unchanged"),
        "knowledge_records": validation.get("knowledge_records"),
    }},
    "package_inventory": {{
        "primary_packages_total": len(primary_packages),
        "non_primary_packages_total": len(non_primary_packages),
        "truncated_packages_total": len(truncated_packages),
        "exact_fact_type_hint_rows_total": sum(
            1
            for package in result.packages
            for row in ((package.get("source_unit") or {{}}).get("model_source_projection") or {{}}).get("rows") or []
            if row.get("fact_type_hint")
        ),
    }},
}}, ensure_ascii=False, sort_keys=True))
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


if __name__ == "__main__":
    raise SystemExit(main())
