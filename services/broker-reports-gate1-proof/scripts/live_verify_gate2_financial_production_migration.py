#!/usr/bin/env python3
"""Verify the released Registry-driven Gate 2 write path on one safe scope."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from live_broker_reports_private_intake_smoke import (  # noqa: E402
    _authenticated_session,
)
from live_gate2_synthetic_extraction_smoke import (  # noqa: E402
    _extract_content,
    _remote_json,
    _url,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
)


FUNCTION_ID = "broker_reports_gate2_domain_source_fact_pipe"
SOURCE_FUNCTION_ID = "broker_reports_gate2_source_fact_pipe"
GATE1_FUNCTION_ID = "broker_reports_gate1_pipe"
FINANCIAL_TYPES = frozenset(
    {
        "broker_reports_financial_evidence_inputs_v1",
        "broker_reports_gate2_financial_context_v1",
        "broker_reports_gate2_financial_evidence_production_receipt_v1",
        "broker_reports_gate2_financial_evidence_production_run_v1",
    }
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--dcp-ref", required=True)
    parser.add_argument("--source-unit-start", required=True, type=int)
    parser.add_argument("--source-segment-start", required=True, type=int)
    parser.add_argument("--model-id", default="gpt-5.6-sol")
    parser.add_argument("--provider-profile-id", default="openai_gpt")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = (
        args.base_url.rstrip("/")
        if args.base_url
        else _base_url(env)
    )
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    session = _authenticated_session(base_url, env)
    before_runtime = _runtime_snapshot(ssh_target)
    before_scope = _scope_snapshot(
        ssh_target=ssh_target,
        dcp_ref=args.dcp_ref,
    )
    before_functions = _function_snapshot(session, base_url)
    domain_valves = _function_valves(
        session, base_url, FUNCTION_ID
    )

    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json=_migration_chat_body(
            dcp_ref=args.dcp_ref,
            model_id=args.model_id,
            provider_profile_id=args.provider_profile_id,
            source_unit_start=args.source_unit_start,
            source_segment_start=args.source_segment_start,
        ),
        timeout=args.timeout,
    )
    response.raise_for_status()
    chat_content = _extract_content(response.json())
    if not chat_content.strip():
        raise RuntimeError("financial_migration_chat_content_missing")

    after_runtime = _runtime_snapshot(ssh_target)
    after_scope = _scope_snapshot(
        ssh_target=ssh_target,
        dcp_ref=args.dcp_ref,
    )
    after_functions = _function_snapshot(session, base_url)
    evaluation = evaluate(
        before_scope=before_scope,
        after_scope=after_scope,
        before_runtime=_safe_counter_view(before_runtime),
        after_runtime=_safe_counter_view(after_runtime),
        before_functions=before_functions,
        after_functions=after_functions,
        domain_valves=domain_valves,
        chat_content=chat_content,
    )
    print(
        json.dumps(
            evaluation,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if evaluation["status"] == "passed" else 2


def _migration_chat_body(
    *,
    dcp_ref: str,
    model_id: str,
    provider_profile_id: str,
    source_unit_start: int,
    source_segment_start: int,
) -> dict[str, Any]:
    if source_unit_start < 0 or source_segment_start < 0:
        raise ValueError("financial_migration_target_invalid")
    return {
        "model": FUNCTION_ID,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Run the controlled Gate 2 financial evidence "
                    "production migration verification."
                ),
            }
        ],
        "stream": False,
        "broker_reports_gate2_domain": {
            "domain_context_packet_ref": dcp_ref,
            "model_id": model_id,
            "provider_profile_id": provider_profile_id,
            "wave": "primary",
            "run_mode": "customer",
            "document_batch_limit": 1,
            "source_unit_start": source_unit_start,
            "source_unit_limit": 1,
            "source_segment_start": source_segment_start,
            "source_segment_limit": 1,
            "segmentation_enabled": True,
            "candidate_binding_enabled": False,
            "gate3_context_manifest_enabled": False,
            "answer_context_selection_enabled": False,
            "max_repair_attempts": 1,
        },
    }


def evaluate(
    *,
    before_scope: dict[str, Any],
    after_scope: dict[str, Any],
    before_runtime: dict[str, int],
    after_runtime: dict[str, int],
    before_functions: dict[str, str],
    after_functions: dict[str, str],
    domain_valves: dict[str, Any],
    chat_content: str,
) -> dict[str, Any]:
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    before_records = before_scope["record_hashes"]
    after_records = after_scope["record_hashes"]
    existing_unchanged = all(
        after_records.get(ref) == digest
        for ref, digest in before_records.items()
    )
    new_financial = after_scope["new_financial"]
    counts = {
        artifact_type: int(
            new_financial["type_counts"].get(artifact_type, 0)
        )
        - int(
            before_scope["new_financial"]["type_counts"].get(
                artifact_type, 0
            )
        )
        for artifact_type in sorted(FINANCIAL_TYPES)
    }
    receipt = new_financial.get("receipt") or {}
    run = new_financial.get("run") or {}
    context = new_financial.get("context") or {}
    inputs_total = counts.get(
        "broker_reports_financial_evidence_inputs_v1", 0
    )
    context_total = counts.get(
        "broker_reports_gate2_financial_context_v1", 0
    )
    receipt_total = counts.get(
        "broker_reports_gate2_financial_evidence_production_receipt_v1",
        0,
    )
    run_total = counts.get(
        "broker_reports_gate2_financial_evidence_production_run_v1",
        0,
    )
    knowledge_vector_keys = (
        "knowledge_rows",
        "vector_file_count",
        "vector_dir_count",
        "vector_collections_count",
        "vector_size_bytes",
    )
    checks = {
        "production_valve_enabled": (
            domain_valves.get("financial_evidence_enabled") is True
        ),
        "registry_valve_exact": (
            domain_valves.get(
                "financial_evidence_registry_version"
            )
            == registry.registry_version
        ),
        "preexisting_artifacts_unchanged": existing_unchanged,
        "new_financial_run_present": run_total == 1,
        "new_financial_receipt_present": receipt_total == 1,
        "new_financial_context_present": context_total == 1,
        "new_financial_inputs_present": inputs_total > 0,
        "single_write_new_schema": (
            run.get("write_policy") == "new_schema_only"
        ),
        "legacy_dual_read": (
            run.get("legacy_read_policy") == "dual_read"
        ),
        "registry_identity_exact": (
            run.get("registry_version")
            == registry.registry_version
            and run.get("registry_hash") == registry.registry_hash
        ),
        "receipt_passed": receipt.get("status") == "passed",
        "terminal_scope_complete": (
            receipt.get("uncovered_source_refs_total") == 0
        ),
        "unclassified_value_loss_zero": (
            receipt.get("unclassified_value_loss_total") == 0
        ),
        "duplicate_interpretations_zero": (
            receipt.get("duplicate_interpretations_total") == 0
        ),
        "fallback_repair_failures_zero": all(
            receipt.get(key) == 0
            for key in (
                "fallback_total",
                "repair_attempts_total",
                "provider_failures_total",
                "schema_failures_total",
            )
        ),
        "context_scope_count_matches_inputs": (
            context.get("source_scopes_total") == inputs_total
        ),
        "gate3_fields_zero": run.get("gate3_fields_total") == 0,
        "gate1_source_function_identity_unchanged": all(
            before_functions.get(function_id)
            == after_functions.get(function_id)
            for function_id in (
                GATE1_FUNCTION_ID,
                SOURCE_FUNCTION_ID,
            )
        ),
        "knowledge_rag_vector_delta_zero": all(
            before_runtime.get(key) == after_runtime.get(key)
            for key in knowledge_vector_keys
        ),
        "chat_reports_financial_completion": (
            "structured financial evidence context: completed"
            in chat_content
        ),
    }
    return {
        "schema_version": (
            "broker_reports_gate2_financial_production_migration_proof_v1"
        ),
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "new_financial_artifact_type_counts": counts,
        "receipt": receipt,
        "run": run,
        "context": context,
        "runtime_before": before_runtime,
        "runtime_after": after_runtime,
        "function_hashes_before": before_functions,
        "function_hashes_after": after_functions,
    }


def _scope_snapshot(*, ssh_target: str, dcp_ref: str) -> dict[str, Any]:
    return _remote_json(
        ssh_target,
        f'''
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

dcp_ref = {dcp_ref!r}
db_path = "/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
payload_root = Path("/app/backend/data/broker_reports_gate1/payloads")

def payload_bytes(row):
    if row["payload_inline_json"]:
        return row["payload_inline_json"].encode("utf-8")
    if row["payload_ref"]:
        return (payload_root / row["payload_ref"]).read_bytes()
    return b""

def payload(row):
    raw = payload_bytes(row)
    return json.loads(raw.decode("utf-8")) if raw else {{}}

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    dcp = conn.execute(
        "select * from artifact_records where artifact_id=?",
        (dcp_ref,),
    ).fetchone()
    if dcp is None:
        raise RuntimeError("financial_migration_dcp_missing")
    rows = conn.execute(
        """
        select * from artifact_records
        where user_id=? and normalization_run_id=?
          and coalesce(case_id,'')=coalesce(?, '')
          and coalesce(chat_id,'')=coalesce(?, '')
          and purge_status='active'
        """,
        (
            dcp["user_id"],
            dcp["normalization_run_id"],
            dcp["case_id"],
            dcp["chat_id"],
        ),
    ).fetchall()

record_hashes = {{}}
financial = []
for row in rows:
    material = {{
        key: row[key]
        for key in row.keys()
        if key not in {{"created_at", "updated_at"}}
    }}
    material["payload_sha256"] = hashlib.sha256(
        payload_bytes(row)
    ).hexdigest()
    record_hashes[str(row["artifact_id"])] = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    if str(row["artifact_type"]) in {sorted(FINANCIAL_TYPES)!r}:
        financial.append((row, payload(row)))

type_counts = Counter(
    str(row["artifact_type"]) for row, _ in financial
)
latest = {{}}
for row, value in financial:
    artifact_type = str(row["artifact_type"])
    previous = latest.get(artifact_type)
    if previous is None or str(row["created_at"]) > previous[0]:
        latest[artifact_type] = (str(row["created_at"]), value)

receipt = (
    latest.get(
        "broker_reports_gate2_financial_evidence_production_receipt_v1"
    )
    or (None, {{}})
)[1]
run = (
    latest.get(
        "broker_reports_gate2_financial_evidence_production_run_v1"
    )
    or (None, {{}})
)[1]
context = (
    latest.get("broker_reports_gate2_financial_context_v1")
    or (None, {{}})
)[1]
safe_receipt = {{
    key: receipt.get(key)
    for key in (
        "schema_version",
        "status",
        "registry_version",
        "registry_hash",
        "source_refs_total",
        "source_scopes_total",
        "uncovered_source_refs_total",
        "duplicate_interpretations_total",
        "unclassified_value_loss_total",
        "fallback_total",
        "repair_attempts_total",
        "provider_failures_total",
        "schema_failures_total",
        "integrity_hash",
    )
}}
safe_run = {{
    "schema_version": run.get("schema_version"),
    "status": run.get("status"),
    "registry_version": (run.get("registry") or {{}}).get(
        "registry_version"
    ),
    "registry_hash": (run.get("registry") or {{}}).get("registry_hash"),
    "financial_inputs_total": len(run.get("financial_input_refs") or []),
    "legacy_read_policy": run.get("legacy_read_policy"),
    "write_policy": run.get("write_policy"),
    "gate3_fields_total": run.get("gate3_fields_total"),
    "integrity_hash": run.get("integrity_hash"),
}}
safe_context = {{
    "schema_version": context.get("schema_version"),
    "registry_version": (context.get("registry") or {{}}).get(
        "registry_version"
    ),
    "registry_hash": (context.get("registry") or {{}}).get(
        "registry_hash"
    ),
    "source_scopes_total": (context.get("scope_coverage") or {{}}).get(
        "source_scopes_total"
    ),
    "integrity_hash": context.get("integrity_hash"),
}}
print(json.dumps({{
    "record_hashes": record_hashes,
    "records_total": len(rows),
    "new_financial": {{
        "type_counts": dict(type_counts),
        "receipt": safe_receipt,
        "run": safe_run,
        "context": safe_context,
    }},
}}, sort_keys=True))
''',
        timeout=120,
    )


def _function_snapshot(session, base_url: str) -> dict[str, str]:
    result = {}
    for function_id in (
        GATE1_FUNCTION_ID,
        SOURCE_FUNCTION_ID,
        FUNCTION_ID,
    ):
        response = session.get(
            _url(base_url, f"/api/v1/functions/id/{function_id}"),
            timeout=30,
        )
        response.raise_for_status()
        content = str((response.json() or {}).get("content") or "")
        result[function_id] = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
    return result


def _function_valves(session, base_url: str, function_id: str):
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{function_id}/valves"),
        timeout=30,
    )
    response.raise_for_status()
    value = response.json()
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
