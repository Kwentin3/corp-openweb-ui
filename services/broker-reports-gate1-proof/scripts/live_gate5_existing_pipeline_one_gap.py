#!/usr/bin/env python3
"""Run one G5.48 demand through the existing bounded Gate 3 owner."""

from __future__ import annotations

import argparse
import asyncio
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
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialRolePackFactory,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-one-gap", action="store_true")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--private-evidence-dir", required=True)
    parser.add_argument("--safe-receipt-path", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--workspace-model-id", required=True)
    parser.add_argument("--normalization-run-id", required=True)
    parser.add_argument("--chunk-ordinal", type=int, required=True)
    parser.add_argument("--demanded-fact-type", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--provider-profile-id", default="google_gemini")
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_one_gap:
        raise SystemExit("explicit_execute_flag_required")

    store_root = Path(args.store_root).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    safe_path = Path(args.safe_receipt_path).resolve()
    if _within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not _within(safe_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("artifact_store_unavailable")
    profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in profile.approved_model_ids:
        raise SystemExit("model_not_approved_for_profile")

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id=args.user_id,
        case_id=args.case_id,
        chat_id=None,
        workspace_model_id=args.workspace_model_id,
        normalization_run_id=args.normalization_run_id,
        allow_private=True,
    )
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=args.document_id, context=context
    )
    chunk = next(
        (
            item
            for item in chunk_set["chunks"]
            if int(item["ordinal"]) == args.chunk_ordinal
        ),
        None,
    )
    if chunk is None:
        raise SystemExit("requested_chunk_unavailable")
    before = _store_snapshot(store_root)

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if args.model_id not in _published_model_ids(session, base_url):
        raise SystemExit("model_not_published")
    user = _current_user(session, base_url)
    live_user_id = str(user.get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def counted_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
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
    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=args.model_id,
        ).create(
            document_id=args.document_id,
            context=context,
            chunk_ordinals=(args.chunk_ordinal,),
            requested_financial_labels=(args.demanded_fact_type,),
        )
    )
    after = _store_snapshot(store_root)
    if before != after:
        raise SystemExit("artifact_store_mutated")
    if submissions["count"] > 2:
        raise SystemExit("one_gap_submission_budget_exceeded")

    private_root.mkdir(parents=True, exist_ok=True)
    private_result = {
        "schema_version": "broker_reports_g548_one_gap_private_v1",
        "result": _jsonable(result),
    }
    private_bytes = _json_bytes(private_result)
    (private_root / "result.private.json").write_bytes(private_bytes)
    annotations = (
        result.merged_output.get("annotations", [])
        if result.merged_output is not None
        else []
    )
    demanded = [
        item
        for item in annotations
        if item.get("financial_label") == args.demanded_fact_type
    ]
    profile = next(
        item
        for item in Gate3FinancialRolePackFactory.create().load_published()["profiles"]
        if item["financial_label"] == args.demanded_fact_type
    )
    required_roles = set(profile["required_roles"])
    complete = _role_pack_complete_annotations(demanded, required_roles)
    safe = {
        "schema_version": "broker_reports_g548_one_gap_receipt_v1",
        "goal": "G5.48",
        "status": (
            "RECOVERED_VIA_EXISTING_BOUNDED_PIPELINE"
            if complete
            else "EXISTING_PIPELINE_EXECUTED_WITHOUT_DEMANDED_COMPLETE_FACT"
        ),
        "document_alias": "document_4",
        "chunk_ordinal": args.chunk_ordinal,
        "chunk_chars": chunk["metrics"]["model_view_chars"],
        "chunk_targets": len(chunk["target_mappings"]),
        "demanded_fact_type": args.demanded_fact_type,
        "demanded_annotations": len(demanded),
        "demanded_complete_annotations": len(complete),
        "provider_submissions": submissions["count"],
        "input_tokens_total": result.metrics["input_tokens_total"],
        "output_tokens_total": result.metrics["output_tokens_total"],
        "document_status": result.document_status,
        "selection_mode": result.selection_mode,
        "owner_factory": "Gate3ChunkBatchLabelingFactory.create",
        "retry_count": 0,
        "repair_count": 0,
        "persistence": "none",
        "store_unchanged": True,
        "private_result_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "source_literals_committed": False,
    }
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_bytes(_json_bytes(safe))
    print(json.dumps({"status": safe["status"]}, sort_keys=True))
    return 0


def _role_pack_complete_annotations(
    annotations: list[dict[str, Any]], required_roles: set[str]
) -> list[dict[str, Any]]:
    return [
        item
        for item in annotations
        if required_roles.issubset(
            {
                role.get("role")
                for role in item.get("roles", [])
                if role.get("status") == "bound"
            }
        )
    ]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: _jsonable(getattr(value, key)) for key in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Exception):
        return {"type": type(value).__name__, "code": getattr(value, "code", None)}
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _store_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
