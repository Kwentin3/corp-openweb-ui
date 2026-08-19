#!/usr/bin/env python3
"""Run exactly one G5.67 metadata submission from a frozen private manifest."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
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
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_LLM_METADATA_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    Gate3LlmMetadataAdapterFactory,
    metadata_proposal_response_schema,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _base_url,
    _is_within,
    _read_env,
    _signin,
    _url,
)
from live_g561_llm_metadata_generalization import (  # noqa: E402
    _jsonable,
    _store_snapshot,
    _write_json,
)


FACTORY_REQUIRED = (
    "Gate3LlmMetadataAdapterFactory.create and "
    "Gate2StructuredModelClientFactory.create are the only replay route"
)
FORBIDDEN = (
    "direct provider calls, retry, best-of-N, manual repair, oracle injection, "
    "per-holdout prompt, semantic fallback or source-store mutation"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    manifest = _read_json(args.frozen_manifest.resolve())
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("g567_private_output_inside_repository")
    if output_root.exists():
        raise SystemExit("g567_output_root_must_be_new")
    _validate_manifest(manifest)

    source_store = Path(manifest["source_store_root"]).resolve()
    source_before = _store_snapshot(source_store)
    working_store = output_root / "working-store"
    output_root.mkdir(parents=True)
    shutil.copytree(source_store, working_store)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=working_store / "artifacts.sqlite3",
            payload_root=working_store / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **manifest["context"],
        allow_private=True,
        require_source_available=True,
    )

    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    provider_profile = manifest["provider_profile"]
    model_id = manifest["model_id"]
    gate2_provider_profile(provider_profile)
    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE,
            provider_profile_id=provider_profile,
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
    attempt = None
    error = None
    try:
        attempt = asyncio.run(
            Gate3LlmMetadataAdapterFactory(
                store=store,
                read_enabled=True,
                model_client=client,
                model_id=model_id,
            ).create(document_id=manifest["document_id"], context=context)
        )
    except Exception as exc:  # provider boundary evidence must remain inspectable
        error = _error_receipt(exc)
    if submissions["count"] != 1:
        raise SystemExit("exactly_one_g567_holdout_submission_required")
    source_unchanged = source_before == _store_snapshot(source_store)

    private_result = {
        "schema_version": "broker_reports_g567_holdout_result_private_v1",
        "goal": "G5.67",
        "alias": manifest["alias"],
        "freeze_sha256": _sha256_json(manifest),
        "provider_profile": provider_profile,
        "model_id": model_id,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "proposal_schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
        "provider_submissions": submissions["count"],
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "source_store_unchanged": source_unchanged,
        "validation_status": (
            attempt.validation_status if attempt is not None else "not_reached"
        ),
        "validation_error_code": (
            attempt.validation_error_code if attempt is not None else None
        ),
        "raw_model_output": (
            _jsonable(attempt.raw_model_output) if attempt is not None else None
        ),
        "validated_output": (
            _jsonable(attempt.validated_output) if attempt is not None else None
        ),
        "context_package": (
            _jsonable(attempt.context_package) if attempt is not None else None
        ),
        "binding_registry": (
            _jsonable(attempt.binding_registry) if attempt is not None else None
        ),
        "execution_metadata": (
            _jsonable(attempt.execution_metadata) if attempt is not None else None
        ),
        "metrics": _jsonable(attempt.metrics) if attempt is not None else None,
        "error": error,
    }
    safe_result = {
        "schema_version": "broker_reports_g567_holdout_result_safe_v1",
        "goal": "G5.67",
        "alias": manifest["alias"],
        "freeze_sha256": _sha256_json(manifest),
        "provider_profile": provider_profile,
        "model_id": model_id,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "proposal_schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
        "provider_submissions": submissions["count"],
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "source_store_unchanged": source_unchanged,
        "validation_status": (
            attempt.validation_status if attempt is not None else "not_reached"
        ),
        "validation_error_code": (
            attempt.validation_error_code if attempt is not None else None
        ),
        "published_facts": (
            len(attempt.validated_output["metadata_facts"])
            if attempt is not None and attempt.validated_output is not None
            else 0
        ),
        "metrics": _jsonable(attempt.metrics) if attempt is not None else None,
        "failure_class": (error or {}).get("failure_class"),
    }
    _write_json(output_root / "result.private.json", private_result)
    _write_json(output_root / "result.safe.json", safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0 if attempt is not None else 1


def _error_receipt(exc: Exception) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "code": getattr(exc, "code", None),
        "failure_class": getattr(exc, "failure_class", None),
        "message": str(exc),
        "execution_metadata": _jsonable(getattr(exc, "execution_metadata", None)),
        "raw_output": _jsonable(getattr(exc, "raw_output", None)),
    }


def _validate_manifest(value: dict[str, Any]) -> None:
    schema_hash = _sha256_json(metadata_proposal_response_schema())
    if (
        value.get("schema_version") != "broker_reports_g567_holdout_freeze_private_v1"
        or value.get("goal") != "G5.67"
        or value.get("frozen_before_provider") is not True
        or value.get("oracle_qualified_before_provider") is not True
        or value.get("output_used_as_truth_hint") is not False
        or value.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or value.get("instruction_version") != GATE3_LLM_METADATA_INSTRUCTION_VERSION
        or value.get("instruction_sha256")
        != hashlib.sha256(GATE3_LLM_METADATA_INSTRUCTION.encode("utf-8")).hexdigest()
        or value.get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        or value.get("proposal_schema_version")
        != GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION
        or value.get("proposal_schema_sha256") != schema_hash
        or value.get("provider_profile") != "google_gemini"
        or value.get("model_id") != "models/gemini-3.5-flash"
        or not Path(value.get("source_store_root") or "").is_absolute()
        or not isinstance(value.get("context"), dict)
        or not isinstance(value.get("document_id"), str)
    ):
        raise SystemExit("g567_holdout_freeze_invalid")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("g567_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
