#!/usr/bin/env python3
"""Run the frozen G5.40E real-source labeling and deterministic-consumer proof."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any

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
    CanonicalReaderFactory,
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
from broker_reports_gate1.gate3_chunk_batch_labeling import (  # noqa: E402
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate3_ndfl_case_readiness import (  # noqa: E402
    Gate3NdflCaseReadinessFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_deterministic_source_fact_consumption import (  # noqa: E402
    Gate5DeterministicSourceFactConsumptionError,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (  # noqa: E402
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


FACTORY_REQUIRED = (
    "CanonicalReaderFactory, Gate3StructuralChunkFactory, "
    "Gate3ChunkBatchLabelingFactory, Gate3FinancialAnnotationsPersistenceFactory, "
    "Gate4FinancialCaseRuntimeFactory and "
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory are the only proof path"
)
FORBIDDEN = (
    "retry, repair, best-of-N, semantic post-editing, source-format reads after "
    "CanonicalArtifactV1, direct SQL, broker defaults, currency guessing, "
    "reconciliation, graph construction or persisted purchase-to-sale relations"
)

DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
DOCUMENTS = (
    {
        "label": "DEV_PUBLIC_TBANK",
        "document_id": "brdoc_001_25c3b0606ce8",
        "source_sha256": (
            "25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67"
        ),
        "normalization_run_id": "normrun_056b15c46f64d9c9",
    },
    {
        "label": "HOLDOUT_REAL_001",
        "document_id": "brdoc_001_79af73d5be78",
        "source_sha256": (
            "79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d"
        ),
        "normalization_run_id": "normrun_0ac55d0083f8ad4a",
    },
    {
        "label": "LARGE_REAL_001",
        "document_id": "brdoc_001_7cfd297786cc",
        "source_sha256": (
            "7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015"
        ),
        "normalization_run_id": "normrun_b5c1922880533908",
    },
    {
        "label": "PUBLIC_FIDELITY_STATEMENT",
        "document_id": "brdoc_001_36a166a5a13e",
        "source_sha256": (
            "36a166a5a13e6d6d86b391233023f83f6f7b4d268a4a23fbae01cb81290e3b96"
        ),
        "normalization_run_id": "normrun_e5dcaae40e5ab7a9",
    },
)
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}
CODE_FILES = (
    "canonical_artifact.py",
    "full_source.py",
    "gate2_handoff.py",
    "gate3_structural_chunking.py",
    "gate3_bounded_labeling.py",
    "gate3_role_labeling.py",
    "gate3_chunk_batch_labeling.py",
    "gate4_financial_case_materialization.py",
    "gate5_deterministic_source_fact_consumption.py",
    "gate5_tax_methodology.ru_ndfl_securities_real_source_fact_contract.v0.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-one-frozen-replay", action="store_true")
    parser.add_argument("--resume-frozen-deterministic", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument(
        "--store-root",
        default=str(REPO_ROOT / "local" / "g540e_private_20260813" / "store"),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g5.40e-20260813-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_REAL_SOURCE_FACT_CONTRACT_G5_40E.receipt.safe.json"
        ),
    )
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    if sum(
        (
            args.plan_only,
            args.execute_one_frozen_replay,
            args.resume_frozen_deterministic,
        )
    ) != 1:
        raise SystemExit("choose_exactly_one_of_plan_only_or_execute")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise SystemExit("timeout_out_of_bounds")
    provider_profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in provider_profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved_for_provider_profile")

    store_root = Path(args.store_root).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    safe_receipt_path = Path(args.safe_receipt_path).resolve()
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    contexts = {
        item["label"]: _context(item["normalization_run_id"])
        for item in DOCUMENTS
    }
    chunk_sets: dict[str, dict[str, Any]] = {}
    source_contracts: dict[str, dict[str, Any]] = {}
    for item in DOCUMENTS:
        label = item["label"]
        context = contexts[label]
        versions = reader.history(item["document_id"], context)
        active = [version for version in versions if version.status == "ACTIVE"]
        if len(active) != 1 or active[0].source_sha256 != item["source_sha256"]:
            raise SystemExit(f"{label}:active_source_hash_mismatch")
        envelope = reader.read_active_envelope(item["document_id"], context)
        chunk_set = Gate3StructuralChunkFactory(
            store=store,
            read_enabled=True,
        ).create(document_id=item["document_id"], context=context)
        chunk_sets[label] = chunk_set
        source_contracts[label] = _source_contract(
            item=item,
            envelope=envelope,
            chunk_set=chunk_set,
        )

    code_hashes = {
        relative: _file_sha256(SERVICE_ROOT / "broker_reports_gate1" / relative)
        for relative in CODE_FILES
    }
    plan = {
        "schema_version": "broker_reports_gate5_real_source_fact_plan_v0",
        "goal": "G5.40E",
        "execution_policy": "one_frozen_sequential_replay_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "documents": source_contracts,
        "provider_submissions_max": 2
        * sum(item["chunks"] for item in source_contracts.values()),
        "code_sha256": code_hashes,
    }
    plan["plan_sha256"] = _sha256_json(plan)
    if args.plan_only:
        print(json.dumps(_safe_plan_view(plan), sort_keys=True))
        return 0
    if args.resume_frozen_deterministic:
        return _resume_frozen_deterministic(
            store=store,
            store_root=store_root,
            private_root=private_root,
            safe_receipt_path=safe_receipt_path,
            source_contracts=source_contracts,
            current_code_hashes=code_hashes,
        )

    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    private_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(private_root / "frozen_plan.private.json", _json_bytes(plan))
    store_before = _store_snapshot(store_root)
    _atomic_write(
        private_root / "store.before.private.json",
        _json_bytes(store_before),
    )

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if args.model_id not in _published_model_ids(session, base_url):
        raise SystemExit("exact_model_not_published")
    live_user = _current_user(session, base_url)
    live_user_id = str(live_user.get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return base_completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=args.provider_profile_id,
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
    batch_factory = Gate3ChunkBatchLabelingFactory(
        store=store,
        read_enabled=True,
        model_client=model_client,
        model_id=args.model_id,
    )

    results: dict[str, Any] = {}
    safe_documents: dict[str, Any] = {}
    for item in DOCUMENTS:
        label = item["label"]
        before = submissions["count"]
        result = asyncio.run(
            batch_factory.create(
                document_id=item["document_id"],
                context=contexts[label],
                chunk_ordinals=None,
            )
        )
        results[label] = result
        private_result = _private_result(result)
        private_bytes = _json_bytes(private_result)
        _atomic_write(
            private_root / label / "batch_result.private.json",
            private_bytes,
        )
        safe_documents[label] = _safe_result(
            result=result,
            provider_submissions=submissions["count"] - before,
            private_sha256=hashlib.sha256(private_bytes).hexdigest(),
        )

    if submissions["count"] > plan["provider_submissions_max"]:
        raise SystemExit("provider_submission_budget_exceeded")
    all_complete = all(
        result.document_status == "complete" for result in results.values()
    )
    sidecars: dict[str, Any] = {}
    gate4_safe: dict[str, Any] = {"status": "not_run_incomplete_gate3"}
    assessment_safe: dict[str, Any] = {"status": "not_run_incomplete_gate3"}
    consumer_safe: dict[str, Any] = {"status": "not_run_incomplete_gate3"}
    if all_complete:
        persistence = Gate3FinancialAnnotationsPersistenceFactory(
            store=store,
            read_enabled=True,
        ).create()
        for item in DOCUMENTS:
            label = item["label"]
            result = results[label]
            sidecars[label] = persistence.save(
                document_id=item["document_id"],
                context=contexts[label],
                validated_document_result=_document_result(result),
                provider_profile_id=args.provider_profile_id,
            )
        root_context = contexts[DOCUMENTS[0]["label"]]
        gate4 = Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        ).create()
        assembly = gate4.rebuild_case(context=root_context)
        facts = list(assembly.facts)
        gate4_private = {
            "assembly": _jsonable(assembly),
            "sidecar_artifact_ids": {
                label: record.artifact_id for label, record in sidecars.items()
            },
        }
        _atomic_write(
            private_root / "gate4.private.json",
            _json_bytes(gate4_private),
        )
        gate4_safe = _safe_gate4(assembly=assembly, facts=facts)
        consumer_runtime = Gate5DeterministicSourceFactConsumptionRuntimeFactory(
            store=store,
            read_enabled=True,
        ).create()
        assessment = consumer_runtime.assess(
            methodology_ref=_source_fact_methodology_ref(),
            context=root_context,
        )
        _atomic_write(
            private_root / "gate5_assessment.private.json",
            _json_bytes(assessment),
        )
        assessment_safe = _safe_assessment(assessment, facts=facts)
        try:
            consumed = consumer_runtime.run(
                methodology_ref=_source_fact_methodology_ref(),
                context=root_context,
            )
        except Gate5DeterministicSourceFactConsumptionError as exc:
            consumer_safe = {
                "status": "fail_closed",
                "error_code": exc.code,
                "field_present": bool(exc.field),
            }
        else:
            _atomic_write(
                private_root / "gate5_consumption.private.json",
                _json_bytes(consumed),
            )
            consumer_safe = _safe_consumer(consumed)

    store_after = _store_snapshot(store_root)
    _atomic_write(
        private_root / "store.after.private.json",
        _json_bytes(store_after),
    )
    receipt = {
        "schema_version": "broker_reports_gate5_real_source_fact_receipt_v0",
        "goal": "G5.40E",
        "execution_policy": plan["execution_policy"],
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "frozen_plan_sha256": plan["plan_sha256"],
        "provider_submissions_total": submissions["count"],
        "provider_submissions_max": plan["provider_submissions_max"],
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "provider_rerun_count": 0,
        "documents": safe_documents,
        "all_documents_complete": all_complete,
        "sidecars_persisted": len(sidecars),
        "gate4": gate4_safe,
        "gate5_assessment": assessment_safe,
        "gate5_consumer": consumer_safe,
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "store_before_sha256": store_before["tree_sha256"],
        "store_after_sha256": store_after["tree_sha256"],
    }
    _atomic_write(safe_receipt_path, _json_bytes(receipt))
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )
    print(
        json.dumps(
            {
                "goal": "G5.40E",
                "documents_complete": sum(
                    value["document_status"] == "complete"
                    for value in safe_documents.values()
                ),
                "provider_submissions": submissions["count"],
                "gate4_status": gate4_safe["status"],
                "gate5_status": consumer_safe["status"],
            },
            sort_keys=True,
        )
    )
    return 0


def _resume_frozen_deterministic(
    *,
    store: Any,
    store_root: Path,
    private_root: Path,
    safe_receipt_path: Path,
    source_contracts: dict[str, dict[str, Any]],
    current_code_hashes: dict[str, str],
) -> int:
    frozen_plan_path = private_root / "frozen_plan.private.json"
    store_before_path = private_root / "store.before.private.json"
    if not frozen_plan_path.is_file() or not store_before_path.is_file():
        raise SystemExit("frozen_private_evidence_missing")
    frozen_plan = json.loads(frozen_plan_path.read_text(encoding="utf-8"))
    if (
        frozen_plan.get("goal") != "G5.40E"
        or frozen_plan.get("execution_policy")
        != "one_frozen_sequential_replay_no_retry_no_repair"
        or frozen_plan.get("documents") != source_contracts
    ):
        raise SystemExit("frozen_plan_source_contract_mismatch")
    safe_documents: dict[str, Any] = {}
    provider_submissions = 0
    for item in DOCUMENTS:
        label = item["label"]
        result_path = private_root / label / "batch_result.private.json"
        if not result_path.is_file():
            raise SystemExit(f"{label}:frozen_batch_result_missing")
        raw = result_path.read_bytes()
        result = json.loads(raw.decode("utf-8"))
        safe = _safe_stored_private_result(
            result=result,
            private_sha256=hashlib.sha256(raw).hexdigest(),
        )
        safe_documents[label] = safe
        provider_submissions += safe["provider_submissions"]
    if not all(
        value["document_status"] == "complete"
        for value in safe_documents.values()
    ):
        raise SystemExit("frozen_gate3_not_complete")
    if provider_submissions > frozen_plan["provider_submissions_max"]:
        raise SystemExit("provider_submission_budget_exceeded")

    root_context = _context(DOCUMENTS[0]["normalization_run_id"])
    readiness = Gate3NdflCaseReadinessFactory(
        store=store,
        read_enabled=True,
    ).create(context=root_context)
    if (
        readiness.get("case_status") != "ready_for_gate4_handoff"
        or readiness.get("summary", {}).get("documents_total") != len(DOCUMENTS)
        or readiness.get("summary", {}).get("gate3_ready_documents")
        != len(DOCUMENTS)
    ):
        raise SystemExit("frozen_sidecars_not_current")
    gate4 = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    assembly = gate4.rebuild_case(context=root_context)
    facts = list(assembly.facts)
    _atomic_write(
        private_root / "gate4.private.json",
        _json_bytes({"assembly": _jsonable(assembly)}),
    )
    gate4_safe = _safe_gate4(assembly=assembly, facts=facts)
    consumer_runtime = Gate5DeterministicSourceFactConsumptionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    assessment = consumer_runtime.assess(
        methodology_ref=_source_fact_methodology_ref(),
        context=root_context,
    )
    _atomic_write(
        private_root / "gate5_assessment.private.json",
        _json_bytes(assessment),
    )
    assessment_safe = _safe_assessment(assessment, facts=facts)
    try:
        consumed = consumer_runtime.run(
            methodology_ref=_source_fact_methodology_ref(),
            context=root_context,
        )
    except Gate5DeterministicSourceFactConsumptionError as exc:
        consumer_safe = {
            "status": "fail_closed",
            "error_code": exc.code,
            "field_present": bool(exc.field),
        }
    else:
        _atomic_write(
            private_root / "gate5_consumption.private.json",
            _json_bytes(consumed),
        )
        consumer_safe = _safe_consumer(consumed)

    store_before = json.loads(store_before_path.read_text(encoding="utf-8"))
    store_after = _store_snapshot(store_root)
    _atomic_write(
        private_root / "store.after.private.json",
        _json_bytes(store_after),
    )
    receipt = {
        "schema_version": "broker_reports_gate5_real_source_fact_receipt_v0",
        "goal": "G5.40E",
        "execution_policy": frozen_plan["execution_policy"],
        "provider_profile_id": frozen_plan["provider_profile_id"],
        "model_id": frozen_plan["model_id"],
        "frozen_plan_sha256": frozen_plan["plan_sha256"],
        "frozen_inference_code_sha256": frozen_plan["code_sha256"],
        "deterministic_resume_code_sha256": current_code_hashes,
        "provider_submissions_total": provider_submissions,
        "provider_submissions_max": frozen_plan["provider_submissions_max"],
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "provider_rerun_count": 0,
        "documents": safe_documents,
        "all_documents_complete": True,
        "sidecars_persisted": len(DOCUMENTS),
        "gate4": gate4_safe,
        "gate5_assessment": assessment_safe,
        "gate5_consumer": consumer_safe,
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "store_before_sha256": store_before["tree_sha256"],
        "store_after_sha256": store_after["tree_sha256"],
    }
    _atomic_write(safe_receipt_path, _json_bytes(receipt))
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )
    print(
        json.dumps(
            {
                "goal": "G5.40E",
                "documents_complete": len(DOCUMENTS),
                "provider_submissions": provider_submissions,
                "provider_reruns": 0,
                "gate4_status": gate4_safe["status"],
                "gate5_status": consumer_safe["status"],
            },
            sort_keys=True,
        )
    )
    return 0


def _context(normalization_run_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=normalization_run_id,
        allow_private=True,
    )


def _source_contract(*, item: dict[str, str], envelope: Any, chunk_set: dict) -> dict:
    artifact = envelope.artifact
    tables = [
        node for node in artifact["nodes"] if node.get("node_type") == "TABLE"
    ]
    table_contents = [table.get("content") or {} for table in tables]
    return {
        "source_sha256": item["source_sha256"],
        "physical_layout": envelope.physical_layout,
        "canonical_nodes": len(artifact["nodes"]),
        "canonical_tables": len(tables),
        "canonical_table_header_rows": sum(
            bool(content.get("header")) for content in table_contents
        ),
        "canonical_table_data_rows": sum(
            len(content.get("rows") or []) for content in table_contents
        ),
        "canonical_table_logical_rows": sum(
            len(content.get("rows") or []) + bool(content.get("header"))
            for content in table_contents
        ),
        "canonical_table_cells": sum(
            len(content.get("cells") or []) for content in table_contents
        ),
        "chunks": len(chunk_set["chunks"]),
        "chunk_chars": [chunk["metrics"]["model_view_chars"] for chunk in chunk_set["chunks"]],
        "targets": chunk_set["coverage"]["eligible_targets"],
        "lost_targets": chunk_set["coverage"]["lost_targets"],
        "duplicated_targets": chunk_set["coverage"]["duplicated_working_targets"],
        "target_order_preserved": chunk_set["coverage"]["target_order_preserved"],
    }


def _private_result(result: Any) -> dict[str, Any]:
    outcomes = []
    for outcome in result.outcomes:
        error = outcome.provider_error
        outcomes.append(
            {
                "chunk": copy.deepcopy(outcome.chunk),
                "pass1_attempt": _jsonable(outcome.attempt),
                "role_attempt": _jsonable(outcome.role_attempt),
                "provider_error": (
                    None
                    if error is None
                    else {
                        "type": error.__class__.__name__,
                        "code": getattr(error, "code", None),
                        "args": _jsonable(error.args),
                        "raw_output": _jsonable(getattr(error, "raw_output", None)),
                        "raw_provider_response": _jsonable(
                            getattr(error, "raw_provider_response", None)
                        ),
                        "execution_metadata": _jsonable(
                            getattr(error, "execution_metadata", None)
                        ),
                    }
                ),
                "terminal_status": outcome.terminal_status,
                "error_code": outcome.error_code,
                "failed_phase": outcome.failed_phase,
            }
        )
    return {
        "schema_version": "broker_reports_gate5_real_source_fact_private_result_v0",
        "chunk_set": copy.deepcopy(result.chunk_set),
        "outcomes": outcomes,
        "merged_output": copy.deepcopy(result.merged_output),
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": copy.deepcopy(result.metrics),
    }


def _safe_result(*, result: Any, provider_submissions: int, private_sha256: str) -> dict:
    labels = Counter()
    role_statuses = Counter()
    for outcome in result.outcomes:
        output = (
            outcome.role_attempt.validated_output
            if outcome.role_attempt is not None
            else None
        )
        for annotation in (output or {}).get("annotations", []):
            labels[annotation["financial_label"]] += 1
            role_statuses.update(role["status"] for role in annotation.get("roles", []))
    return {
        "document_status": result.document_status,
        "selection_mode": result.selection_mode,
        "chunks_total": result.metrics["chunks_total"],
        "chunks_validated": result.metrics["chunks_validated"],
        "chunks_rejected": result.metrics["chunks_rejected"],
        "chunks_provider_failed": result.metrics["chunks_provider_failed"],
        "annotations_validated": result.metrics["annotations_validated"],
        "provider_submissions": provider_submissions,
        "financial_type_counts": dict(sorted(labels.items())),
        "role_binding_status_counts": dict(sorted(role_statuses.items())),
        "private_result_sha256": private_sha256,
    }


def _safe_stored_private_result(
    *, result: dict[str, Any], private_sha256: str
) -> dict[str, Any]:
    labels = Counter()
    role_statuses = Counter()
    provider_submissions = 0
    for outcome in result.get("outcomes") or []:
        pass1 = outcome.get("pass1_attempt")
        role = outcome.get("role_attempt")
        if pass1 is not None or outcome.get("provider_error") is not None:
            provider_submissions += 1
        if role is not None and role.get("execution_status") != "skipped_empty":
            provider_submissions += 1
        output = (role or {}).get("validated_output") or {}
        for annotation in output.get("annotations") or []:
            labels[annotation["financial_label"]] += 1
            role_statuses.update(
                item["status"] for item in annotation.get("roles") or []
            )
    metrics = result["metrics"]
    return {
        "document_status": result["document_status"],
        "selection_mode": result["selection_mode"],
        "chunks_total": metrics["chunks_total"],
        "chunks_validated": metrics["chunks_validated"],
        "chunks_rejected": metrics["chunks_rejected"],
        "chunks_provider_failed": metrics["chunks_provider_failed"],
        "annotations_validated": metrics["annotations_validated"],
        "provider_submissions": provider_submissions,
        "financial_type_counts": dict(sorted(labels.items())),
        "role_binding_status_counts": dict(sorted(role_statuses.items())),
        "private_result_sha256": private_sha256,
    }


def _document_result(result: Any) -> dict[str, Any]:
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": copy.deepcopy(result.semantic_scope),
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": copy.deepcopy(result.metrics),
        "merged_output": copy.deepcopy(result.merged_output),
    }


def _safe_gate4(*, assembly: Any, facts: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts = Counter(fact["financial_type"] for fact in facts)
    status_counts = Counter(fact["status"] for fact in facts)
    target_kinds = Counter(fact["annotation_target"]["kind"] for fact in facts)
    currency_counts = Counter()
    for fact in facts:
        for role in fact["roles"]:
            if role["role"] != "currency":
                continue
            if role["status"] != "value":
                currency_counts["missing"] += 1
            elif re.fullmatch(r"[A-Z]{3}", str(role["value"])):
                currency_counts["iso_literal"] += 1
            else:
                currency_counts["non_iso_literal"] += 1
    return {
        "status": assembly.status,
        "gate3_case_status": assembly.gate3_case_status,
        "sources_total": len(assembly.sources),
        "facts_total": len(facts),
        "financial_type_counts": dict(sorted(type_counts.items())),
        "fact_status_counts": dict(sorted(status_counts.items())),
        "annotation_target_kind_counts": dict(sorted(target_kinds.items())),
        "currency_source_literal_counts": dict(sorted(currency_counts.items())),
    }


def _safe_consumer(value: dict[str, Any]) -> dict[str, Any]:
    direct = Counter(
        item["direct_transaction_expense"]["status"]
        for item in value["securities"]
    )
    return {
        "status": value["status"],
        "terminals": list(value["terminals"]),
        "securities_total": len(value["securities"]),
        "direct_transaction_expense_status_counts": dict(sorted(direct.items())),
        "commission_mode": value["assertions"]["commissions"]["mode"],
        "withheld_tax_mode": value["assertions"]["withheld_tax"]["mode"],
        "capability_map": copy.deepcopy(value["capability_map"]),
        "stored_financial_event_relations": 0,
    }


def _safe_assessment(
    value: dict[str, Any], *, facts: list[dict[str, Any]]
) -> dict[str, Any]:
    reason_codes = Counter(
        item["reason_code"]
        for item in value["security_facts"]
        if item["reason_code"] is not None
    )

    def assertion_summary(assertion: dict[str, Any]) -> dict[str, Any]:
        details = assertion["detail"]
        aggregates = assertion["aggregate"]
        return {
            "mode": assertion["mode"],
            "detail_facts": len(details),
            "aggregate_facts": len(aggregates),
            "detail_status_counts": dict(
                sorted(Counter(item["status"] for item in details).items())
            ),
            "aggregate_status_counts": dict(
                sorted(Counter(item["status"] for item in aggregates).items())
            ),
            "reconciliation": assertion["reconciliation"],
        }

    document_labels = {
        item["document_id"]: item["label"] for item in DOCUMENTS
    }
    facts_by_id = {fact["fact_id"]: fact for fact in facts}
    by_document: dict[str, Counter] = {
        label: Counter() for label in document_labels.values()
    }
    for item in value["security_facts"]:
        fact = facts_by_id[item["fact_id"]]
        document_id = fact["gate3_binding"]["canonical_binding"]["document_id"]
        counter = by_document[document_labels[document_id]]
        counter["total"] += 1
        counter[item["status"]] += 1
        if item["reason_code"] is not None:
            counter[f"reason:{item['reason_code']}"] += 1

    document_consumption = {
        document_labels[item["document_id"]]: {
            "status": item["status"],
            "reason_code": item["reason_code"],
            "securities_consumed": item["securities_consumed"],
        }
        for item in value["document_consumption"]
    }

    return {
        "status": value["status"],
        "terminals": list(value["terminals"]),
        "facts_total": value["facts_total"],
        "security_tax_input_status": value["security_tax_input_status"],
        "security_fact_counts": copy.deepcopy(value["security_fact_counts"]),
        "security_insufficiency_reason_counts": dict(sorted(reason_codes.items())),
        "security_by_document": {
            label: dict(sorted(counter.items()))
            for label, counter in by_document.items()
        },
        "document_consumption": document_consumption,
        "commissions": assertion_summary(value["assertions"]["commissions"]),
        "withheld_tax": assertion_summary(value["assertions"]["withheld_tax"]),
        "reconciliation": value["reconciliation"],
        "stored_financial_event_relations": value[
            "stored_financial_event_relations"
        ],
    }


def _source_fact_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _safe_plan_view(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal": plan["goal"],
        "execution_policy": plan["execution_policy"],
        "model_id": plan["model_id"],
        "documents": plan["documents"],
        "provider_submissions_max": plan["provider_submissions_max"],
        "plan_sha256": plan["plan_sha256"],
    }


def _store_snapshot(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "tree_sha256": _sha256_json(files),
        "files": files,
    }


def _private_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "private_manifest.json":
            continue
        raw = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "schema_version": "broker_reports_gate5_real_source_fact_private_manifest_v0",
        "goal": "G5.40E",
        "privacy": "PRIVATE_OUTSIDE_GIT",
        "files": files,
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
