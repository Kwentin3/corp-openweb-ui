#!/usr/bin/env python3
"""Execute one frozen G5.92 predeclared-assertion phase through the real provider path."""

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
    Gate3BoundedLabelingFactory,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_V2_1_VERSION,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--phase", choices=("development", "holdout"), required=True)
    parser.add_argument("--private-plan-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 600:
        raise SystemExit("timeout_out_of_bounds")

    root = args.private_plan_dir.resolve()
    if _is_within(root, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    plan_path = root / "frozen-plan.private.json"
    plan_bytes_before = plan_path.read_bytes()
    plan = _read_json(plan_path)
    chunks = _read_json(root / "chunks.private.json")
    batches = _read_json(root / "batches.private.json")
    if plan.get("goal") != "G5.92":
        raise SystemExit("g592_frozen_plan_required")
    ordinals = tuple(plan[f"{args.phase}_ordinals"])
    if args.phase == "holdout":
        qualification = _read_json(root / "development-qualification.private.json")
        if qualification.get("development_proven_for_holdout") is not True:
            raise SystemExit("development_proof_required_before_holdout")
    replay_path = root / f"{args.phase}-replay.private.json"
    if replay_path.exists():
        raise SystemExit("phase_replay_already_exists")

    provider_profile_id = str(plan["provider_profile_id"])
    model_id = str(plan["model_id"])
    profile = gate2_provider_profile(provider_profile_id)
    if model_id not in profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved")
    env = _read_env(args.env_file)
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if model_id not in _published_model_ids(session, base_url):
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
            provider_profile_id=provider_profile_id,
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
        store=None,
        read_enabled=False,
        model_client=model_client,
        model_id=model_id,
        dictionary_version=GATE3_DICTIONARY_V2_1_VERSION,
    )

    outcomes: list[dict[str, Any]] = []
    for ordinal in ordinals:
        chunk = chunks[str(ordinal)]
        prepared = owner.prepare_predeclared_assertion_batch(chunk=chunk)
        if (
            _stable_sha256(prepared["model_visible_request"])
            != plan["request_sha256_by_ordinal"][str(ordinal)]
            or prepared["assertion_envelope"]
            != batches[str(ordinal)]["assertion_envelope"]
            or prepared["model_visible_request"]
            != batches[str(ordinal)]["model_visible_request"]
        ):
            raise SystemExit("frozen_request_drift")
        try:
            attempt = asyncio.run(
                owner.create_from_predeclared_assertions(chunk=chunk)
            )
            outcome = {
                "ordinal": ordinal,
                "terminal_status": attempt.validation_status,
                "validation_error_code": attempt.validation_error_code,
                "validated_output": copy.deepcopy(attempt.validated_output),
                "raw_provider_response": copy.deepcopy(attempt.raw_provider_response),
                "raw_model_output": copy.deepcopy(attempt.raw_model_output),
                "execution_metadata": _plain(attempt.execution_metadata),
                "operational_retry_receipt": copy.deepcopy(
                    attempt.operational_retry_receipt
                ),
                "metrics": copy.deepcopy(attempt.metrics),
            }
        except Gate2SourceFactRuntimeError as exc:
            outcome = {
                "ordinal": ordinal,
                "terminal_status": "provider_error",
                "validation_error_code": exc.code,
            }
        outcomes.append(outcome)
        _atomic_write(
            root / f"{args.phase}-replay.in-progress.private.json",
            _json_bytes({"goal": "G5.92", "phase": args.phase, "outcomes": outcomes}),
        )

    replay = {
        "schema_version": "broker_reports_g592_predeclared_assertion_replay_v1",
        "goal": "G5.92",
        "phase": args.phase,
        "plan_sha256": hashlib.sha256(plan_bytes_before).hexdigest(),
        "semantic_attempts": len(ordinals),
        "transport_submissions": submissions["count"],
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 1,
        "model_variants": 1,
        "outcomes": outcomes,
    }
    _atomic_write(replay_path, _json_bytes(replay))
    if plan_path.read_bytes() != plan_bytes_before:
        raise SystemExit("frozen_plan_mutated")
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "phase": args.phase,
                "semantic_attempts": len(ordinals),
                "transport_submissions": submissions["count"],
                "validated": sum(
                    item["terminal_status"] == "validated" for item in outcomes
                ),
                "replay_sha256": _file_sha256(replay_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"json_object_required:{path.name}")
    return value


def _stable_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
