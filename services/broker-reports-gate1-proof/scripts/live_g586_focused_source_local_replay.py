#!/usr/bin/env python3
"""Run one G5.86 pass-1 replay over the six frozen affected chunks."""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
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
    Gate3BoundedLabelingFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_LABELING_INSTRUCTION,
    GATE3_LABELING_INSTRUCTION_VERSION,
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
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _is_within,
    _json_bytes,
    _private_manifest,
    _store_tree_snapshot,
)


DOCUMENT_ID = "brdoc_001_7cfd297786cc"
NORMALIZATION_RUN_ID = "normrun_1f4f2d9e30c1a076"
FOCUSED_ORDINALS = (10, 12, 14, 16, 20, 22)
DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "workspace_model_id": "g540e-private-model",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-focused-replay", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--baseline-batch", type=Path, required=True)
    parser.add_argument("--private-evidence-dir", type=Path, required=True)
    parser.add_argument("--safe-receipt-path", type=Path, required=True)
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_focused_replay:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")

    private_root = args.private_evidence_dir.resolve()
    receipt_path = args.safe_receipt_path.resolve()
    store_root = args.store_root.resolve()
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(receipt_path, REPO_ROOT.resolve()) or receipt_path.exists():
        raise SystemExit("safe_receipt_path_invalid")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")
    profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved")

    baseline = _read_json(args.baseline_batch)
    baseline_chunks = {
        int(item["ordinal"]): item for item in baseline["chunk_set"]["chunks"]
    }
    private_root.mkdir(parents=True, exist_ok=True)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id=CONTEXT["user_id"],
        case_id=CONTEXT["case_id"],
        chat_id=None,
        workspace_model_id=CONTEXT["workspace_model_id"],
        normalization_run_id=NORMALIZATION_RUN_ID,
        allow_private=True,
    )
    store_before = _store_tree_snapshot(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=DOCUMENT_ID,
        context=context,
    )
    chunks_by_ordinal = {int(item["ordinal"]): item for item in chunk_set["chunks"]}
    focused_chunks = [chunks_by_ordinal[ordinal] for ordinal in FOCUSED_ORDINALS]
    for chunk in focused_chunks:
        baseline_chunk = baseline_chunks[int(chunk["ordinal"])]
        if chunk != baseline_chunk:
            raise SystemExit("focused_chunk_drift_from_g583_baseline")

    plan = {
        "schema_version": "broker_reports_g586_focused_replay_plan_v1",
        "goal": "G5.86",
        "document_id": DOCUMENT_ID,
        "canonical_binding": chunk_set["canonical_binding"],
        "chunk_ordinals": list(FOCUSED_ORDINALS),
        "chunk_ids": [item["chunk_id"] for item in focused_chunks],
        "execution_policy": "one_pass1_semantic_attempt_per_chunk_sequential",
        "operational_retry_policy": "gate3_operational_no_response_v1",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_LABELING_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "max_semantic_attempts": len(FOCUSED_ORDINALS),
        "max_transport_submissions": len(FOCUSED_ORDINALS) * 2,
        "semantic_retry": False,
        "best_of_n": False,
        "temperature_variants": 0,
    }
    _atomic_write(private_root / "frozen-plan.private.json", _json_bytes(plan))
    _atomic_write(
        private_root / "focused-chunks.private.json", _json_bytes(focused_chunks)
    )
    _atomic_write(
        private_root / "instruction.private.txt",
        GATE3_LABELING_INSTRUCTION.encode("utf-8"),
    )
    _atomic_write(
        private_root / "store-tree.before.private.json", _json_bytes(store_before)
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
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def counted_completion(*, form_data, **kwargs):
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
            counted_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()
    owner = Gate3BoundedLabelingFactory(
        store=store,
        read_enabled=True,
        model_client=model_client,
        model_id=args.model_id,
    )
    outcomes = []
    for chunk in focused_chunks:
        try:
            attempt = asyncio.run(owner.create_from_chunk(chunk=chunk))
            outcome = {
                "chunk": copy.deepcopy(chunk),
                "terminal_status": (
                    "validated"
                    if attempt.validation_status == "validated"
                    else "rejected"
                ),
                "error_code": attempt.validation_error_code,
                "attempt": _private_attempt(attempt),
                "provider_error": None,
            }
        except Gate2SourceFactRuntimeError as exc:
            outcome = {
                "chunk": copy.deepcopy(chunk),
                "terminal_status": "provider_failed",
                "error_code": exc.code,
                "attempt": None,
                "provider_error": {
                    "code": exc.code,
                    "failure_class": getattr(exc, "failure_class", None),
                    "operational_retry_receipt": copy.deepcopy(
                        getattr(exc, "operational_retry_receipt", None)
                    ),
                },
            }
        outcomes.append(outcome)
        _atomic_write(
            private_root / f"chunk-{chunk['ordinal']:03d}.private.json",
            _json_bytes(outcome),
        )

    store_after = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store-tree.after.private.json", _json_bytes(store_after)
    )
    store_unchanged = store_before == store_after
    receipts = [
        item["attempt"]["operational_retry_receipt"]
        for item in outcomes
        if item["attempt"] is not None
    ] + [
        item["provider_error"]["operational_retry_receipt"]
        for item in outcomes
        if item["provider_error"] is not None
    ]
    semantic_attempts = sum(
        int(item.get("semantic_attempts") or 0) for item in receipts
    )
    transport_submissions = sum(
        int(item.get("transport_submissions") or 0) for item in receipts
    )
    batch = {
        "schema_version": "broker_reports_g586_focused_replay_private_v1",
        "goal": "G5.86",
        "plan": plan,
        "outcomes": outcomes,
        "provider_submission_counter": submissions["count"],
        "semantic_attempts": semantic_attempts,
        "transport_submissions": transport_submissions,
        "artifact_store_unchanged": store_unchanged,
        "persistence": "NOT_RUN",
        "role_labeling": "NOT_RUN",
    }
    _atomic_write(private_root / "focused-replay.private.json", _json_bytes(batch))

    validated = sum(item["terminal_status"] == "validated" for item in outcomes)
    rejected = sum(item["terminal_status"] == "rejected" for item in outcomes)
    provider_failed = sum(
        item["terminal_status"] == "provider_failed" for item in outcomes
    )
    receipt = {
        "schema_version": "broker_reports_g586_focused_replay_safe_v1",
        "goal": "G5.86",
        "terminal": (
            "FOCUSED_PASS1_REPLAY_CONTRACT_VALID"
            if validated == len(FOCUSED_ORDINALS)
            and not rejected
            and not provider_failed
            and store_unchanged
            and semantic_attempts == len(FOCUSED_ORDINALS)
            and transport_submissions == submissions["count"]
            else "FOCUSED_PASS1_REPLAY_INCOMPLETE"
        ),
        "chunk_ordinals": list(FOCUSED_ORDINALS),
        "chunks_validated": validated,
        "chunks_rejected": rejected,
        "chunks_provider_failed": provider_failed,
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "model_id": args.model_id,
        "provider_profile_id": args.provider_profile_id,
        "semantic_attempts": semantic_attempts,
        "transport_submissions": transport_submissions,
        "physical_submission_counter": submissions["count"],
        "operational_retries": sum(
            int(item.get("operational_retries") or 0) for item in receipts
        ),
        "semantic_retries": 0,
        "best_of_n": False,
        "model_changed": False,
        "temperature_variants": 0,
        "artifact_store_unchanged": store_unchanged,
        "persistence_writes": 0,
        "role_provider_calls": 0,
        "private_result_sha256": _sha256(private_root / "focused-replay.private.json"),
    }
    _atomic_write(receipt_path, _json_bytes(receipt))
    _atomic_write(
        private_root / "private-manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["terminal"] == "FOCUSED_PASS1_REPLAY_CONTRACT_VALID" else 2


def _private_attempt(attempt: Any) -> dict[str, Any]:
    return {
        "projection": copy.deepcopy(attempt.projection),
        "dictionary": copy.deepcopy(attempt.dictionary),
        "dictionary_managed_binding": copy.deepcopy(attempt.dictionary_managed_binding),
        "dictionary_markdown": attempt.dictionary_markdown,
        "instruction": attempt.instruction,
        "model_visible_request": copy.deepcopy(attempt.model_visible_request),
        "final_provider_request": copy.deepcopy(attempt.final_provider_request),
        "raw_provider_response": copy.deepcopy(attempt.raw_provider_response),
        "raw_model_output": copy.deepcopy(attempt.raw_model_output),
        "validated_output": copy.deepcopy(attempt.validated_output),
        "validation_status": attempt.validation_status,
        "validation_error_code": attempt.validation_error_code,
        "execution_metadata": _jsonable(attempt.execution_metadata),
        "operational_retry_receipt": copy.deepcopy(attempt.operational_retry_receipt),
        "metrics": copy.deepcopy(attempt.metrics),
    }


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("input_not_object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
