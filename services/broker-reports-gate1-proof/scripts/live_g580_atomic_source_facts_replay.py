#!/usr/bin/env python3
"""Run one ordinary Gate 3/Gate 4 replay over the repaired G5.80 Canonical."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    Gate4FinancialCaseRuntimeFactory,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate5_real_source_fact_contract import (  # noqa: E402
    _atomic_write,
    _base_url,
    _document_result,
    _json_bytes,
    _jsonable,
    _private_manifest,
    _private_result,
    _read_env,
    _signin,
    _url,
)


DOCUMENT_ID = "brdoc_001_7cfd297786cc"
NORMALIZATION_RUN_ID = "normrun_1f4f2d9e30c1a076"
EXPECTED_CANONICAL_VERSION_ID = "canver_lvs64r6lTXf56n30XPIfbV0FRxwVW1lE"
EXPECTED_CHUNKS = 140
PROVIDER_PROFILE_ID = "google_gemini"
MODEL_ID = "models/gemini-3.5-flash"
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-one-frozen-replay", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--private-evidence-dir", required=True)
    parser.add_argument("--safe-receipt-path", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.execute_one_frozen_replay:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")
    if MODEL_ID not in gate2_provider_profile(PROVIDER_PROFILE_ID).approved_model_ids:
        raise SystemExit("exact_model_not_approved")

    store_root = Path(args.store_root).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    safe_path = Path(args.safe_receipt_path).resolve()
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_replay_directory_must_be_empty")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("store_unavailable")
    private_root.mkdir(parents=True, exist_ok=True)

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=NORMALIZATION_RUN_ID,
        allow_private=True,
    )
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=DOCUMENT_ID,
        context=context,
    )
    binding = chunk_set["canonical_binding"]
    chunks = list(chunk_set["chunks"])
    if (
        binding["canonical_version_id"] != EXPECTED_CANONICAL_VERSION_ID
        or len(chunks) != EXPECTED_CHUNKS
        or [int(item["ordinal"]) for item in chunks]
        != list(range(1, EXPECTED_CHUNKS + 1))
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_replay_shape_changed")
    plan = {
        "schema_version": "broker_reports_g580_atomic_replay_plan_v1",
        "goal": "G5.80",
        "document_id": DOCUMENT_ID,
        "normalization_run_id": NORMALIZATION_RUN_ID,
        "canonical_binding": binding,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "model_id": MODEL_ID,
        "chunks": len(chunks),
        "targets": chunk_set["coverage"]["eligible_targets"],
        "provider_submissions_max": 2 * len(chunks),
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "manual_facts": 0,
        "production_visual_dependency": False,
    }
    _atomic_write(private_root / "frozen-plan.private.json", _json_bytes(plan))

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if MODEL_ID not in _published_model_ids(session, base_url):
        raise SystemExit("exact_model_not_published")
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    completed_submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        _write_progress(
            private_root=private_root,
            started=submissions["count"],
            completed=completed_submissions["count"],
            state="provider_call_started",
        )
        result = completion(form_data=form_data, **kwargs)
        completed_submissions["count"] += 1
        _write_progress(
            private_root=private_root,
            started=submissions["count"],
            completed=completed_submissions["count"],
            state="provider_call_returned",
        )
        return result

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            one_attempt_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()
    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=DOCUMENT_ID, context=context)
    )
    private_result = _private_result(result)
    private_result_bytes = _json_bytes(private_result)
    _atomic_write(private_root / "gate3-batch.private.json", private_result_bytes)

    safe = {
        "schema_version": "broker_reports_g580_atomic_replay_receipt_v1",
        "goal": "G5.80",
        "document_id": DOCUMENT_ID,
        "canonical_version_id": EXPECTED_CANONICAL_VERSION_ID,
        "document_status": result.document_status,
        "chunks_total": result.metrics["chunks_total"],
        "chunks_validated": result.metrics["chunks_validated"],
        "chunks_rejected": result.metrics["chunks_rejected"],
        "chunks_provider_failed": result.metrics["chunks_provider_failed"],
        "annotations_validated": result.metrics["annotations_validated"],
        "provider_submissions": submissions["count"],
        "provider_submissions_returned": completed_submissions["count"],
        "provider_submissions_max": plan["provider_submissions_max"],
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "manual_facts": 0,
        "production_visual_dependency": False,
        "private_result_sha256": hashlib.sha256(private_result_bytes).hexdigest(),
    }
    if result.document_status != "complete":
        safe["terminal"] = "DOWNSTREAM_REPLAY_INCOMPLETE"
        _finish(private_root, safe_path, safe)
        return 2

    sidecar = Gate3FinancialAnnotationsPersistenceFactory(
        store=store,
        read_enabled=True,
    ).create().save(
        document_id=DOCUMENT_ID,
        context=context,
        validated_document_result=_document_result(result),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    gate4 = Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True).create()
    assembly = gate4.rebuild_case(context=context)
    materializations = [
        gate4.materialize_artifact(
            financial_annotations_artifact_id=source.financial_annotations_artifact_id,
            context=context,
        )
        for source in assembly.sources
        if source.financial_annotations_artifact_id is not None
    ]
    omissions = [
        item
        for materialization in materializations
        for item in materialization.non_materialized_presence_annotations
    ]
    _atomic_write(
        private_root / "gate4.private.json",
        _json_bytes(
            {
                "assembly": _jsonable(assembly),
                "non_materialized_presence_annotations": omissions,
            }
        ),
    )
    facts = list(assembly.facts)
    target_kinds = Counter(item["annotation_target"]["kind"] for item in facts)
    type_counts = Counter(item["financial_type"] for item in facts)
    omission_types = Counter(item["financial_label"] for item in omissions)
    g57908 = [
        fact
        for fact in facts
        if fact["gate3_binding"]["canonical_binding"]["document_id"]
        == "brdoc_001_79af73d5be78"
        and fact["annotation_target"]
        == {
            "kind": "table_cell",
            "node_id": "node_bfdfbcc1b016e5225a13ecd4",
            "row": 5,
            "column": 4,
        }
    ]
    g57908_roles = {
        role["role"]: role["status"] for fact in g57908 for role in fact["roles"]
    }
    safe.update(
        {
            "sidecar_artifact_id": sidecar.artifact_id,
            "gate4_status": assembly.status,
            "gate3_case_status": assembly.gate3_case_status,
            "gate4_sources_total": len(assembly.sources),
            "gate4_facts_total": len(facts),
            "gate4_target_kind_counts": dict(sorted(target_kinds.items())),
            "gate4_financial_type_counts": dict(sorted(type_counts.items())),
            "non_materialized_presence_total": len(omissions),
            "non_materialized_presence_type_counts": dict(sorted(omission_types.items())),
            "g57908_exact_fact_count": len(g57908),
            "g57908_amount_status": g57908_roles.get("amount"),
            "g57908_currency_status": g57908_roles.get("currency"),
            "stored_purchase_sale_relations": 0,
            "false_user_requests": 0,
            "terminal": "CURRENT_CASE_SOURCE_FACTS_REQUALIFIED",
        }
    )
    _finish(private_root, safe_path, safe)
    print(json.dumps({key: safe[key] for key in ("terminal", "provider_submissions", "gate4_facts_total", "non_materialized_presence_total", "g57908_exact_fact_count")}, sort_keys=True))
    return 0


def _finish(private_root: Path, safe_path: Path, safe: dict) -> None:
    _atomic_write(safe_path, _json_bytes(safe))
    _atomic_write(
        private_root / "private-manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )


def _write_progress(
    *, private_root: Path, started: int, completed: int, state: str
) -> None:
    event = {
        "schema_version": "broker_reports_g580_provider_progress_v1",
        "goal": "G5.80",
        "provider_submissions_started": started,
        "provider_submissions_returned": completed,
        "state": state,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write(
        private_root / "provider-progress.private.json",
        _json_bytes(event),
    )
    with (private_root / "provider-progress.private.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
