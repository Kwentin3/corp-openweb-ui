#!/usr/bin/env python3
"""Run the single G5.66 holdout submission after structural qualification."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
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
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    Gate3LlmMetadataAdapterFactory,
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
    _atomic_write,
    _base_url,
    _json_bytes,
    _read_env,
    _signin,
    _url,
)
from live_g561_llm_metadata_generalization import (  # noqa: E402
    _jsonable,
    _store_snapshot,
)


PROVIDER_PROFILE = "google_gemini"
MODEL_ID = "models/gemini-3.5-flash"
SOURCE_SHA256 = (
    "79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d"
)

FACTORY_REQUIRED = (
    "Gate3LlmMetadataAdapterFactory.create and "
    "Gate2StructuredModelClientFactory.create are the only replay route"
)
FORBIDDEN = (
    "direct provider calls, retry, best-of-N, manual output repair, prompt "
    "mutation, semantic fallback or persistence"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--binding-proof", type=Path, required=True)
    parser.add_argument("--canonical-store", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    if any(output.exists() for output in outputs):
        raise SystemExit("g566_replay_output_must_be_new")

    preparation = _read_json(args.preparation.resolve())
    binding_proof = _read_json(args.binding_proof.resolve())
    _validate_freeze(preparation=preparation, binding_proof=binding_proof)
    store_root = args.canonical_store.resolve()
    before = _store_snapshot(store_root)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **preparation["context"],
        allow_private=True,
        require_source_available=True,
    )

    gate2_provider_profile(PROVIDER_PROFILE)
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

    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE,
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
    attempt = asyncio.run(
        Gate3LlmMetadataAdapterFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=MODEL_ID,
        ).create(document_id=preparation["document_id"], context=context)
    )
    after = _store_snapshot(store_root)
    if submissions["count"] != 1:
        raise SystemExit("exactly_one_g566_holdout_submission_required")

    result = {
        "schema_version": "broker_reports_g566_holdout_result_private_v1",
        "goal": "G5.66",
        "alias": "holdout_c_sber",
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_submissions": submissions["count"],
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "source_store_unchanged": before == after,
        "validation_status": attempt.validation_status,
        "validation_error_code": attempt.validation_error_code,
        "raw_model_output": _jsonable(attempt.raw_model_output),
        "validated_output": _jsonable(attempt.validated_output),
        "context_package": _jsonable(attempt.context_package),
        "binding_registry": _jsonable(attempt.binding_registry),
        "execution_metadata": _jsonable(attempt.execution_metadata),
        "metrics": _jsonable(attempt.metrics),
    }
    safe = {
        "schema_version": "broker_reports_g566_holdout_result_safe_v1",
        "goal": "G5.66",
        "alias": "holdout_c_sber",
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_submissions": submissions["count"],
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "source_store_unchanged": before == after,
        "validation_status": attempt.validation_status,
        "validation_error_code": attempt.validation_error_code,
        "published_facts": (
            len(attempt.validated_output["metadata_facts"])
            if attempt.validated_output is not None
            else 0
        ),
        "metrics": _jsonable(attempt.metrics),
    }
    for output, value in zip(outputs, (result, safe), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(output, _json_bytes(value))
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _validate_freeze(*, preparation: dict, binding_proof: dict) -> None:
    if (
        preparation.get("source_sha256") != SOURCE_SHA256
        or binding_proof.get("goal") != "G5.66"
        or binding_proof.get("provider_calls") != 0
        or binding_proof.get("holdout_visibility") != 5
        or binding_proof.get("physical_binding_ambiguity") != 0
        or GATE3_MINIMAL_METADATA_CONTRACT_VERSION != "1.0.0"
        or GATE3_LLM_METADATA_INSTRUCTION_VERSION != "1.1.0"
        or GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        != "broker_reports_metadata_context_policy_v4"
    ):
        raise SystemExit("g566_replay_freeze_invalid")


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("g566_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
