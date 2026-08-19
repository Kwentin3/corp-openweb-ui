#!/usr/bin/env python3
"""Run one current Gate 3 pass-1 replay for the frozen G5.88 tax chunks."""

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
    GATE3_LABELING_INSTRUCTION,
    GATE3_LABELING_INSTRUCTION_VERSION,
    Gate3BoundedLabelingFactory,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_CURRENT_VERSION,
    Gate3FinancialLabelDictionaryFactory,
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


ORDINALS = (10, 12, 14, 16, 20, 22)
DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-replay", action="store_true")
    parser.add_argument("--g588-evidence-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--requested-financial-label",
        action="append",
        default=[],
    )
    args = parser.parse_args()
    if not args.execute_replay:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 600:
        raise SystemExit("timeout_out_of_bounds")

    source_root = args.g588_evidence_dir.resolve()
    output_root = args.private_output_dir.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit("private_output_must_be_new_or_empty")
    output_root.mkdir(parents=True, exist_ok=True)

    g588_plan = _read_json(source_root / "frozen-plan.private.json")
    chunks = _read_json(source_root / "chunks.private.json")
    if g588_plan.get("goal") != "G5.88":
        raise SystemExit("g588_frozen_plan_required")
    selected = {str(ordinal): chunks[str(ordinal)] for ordinal in ORDINALS}
    expected_hashes = g588_plan.get("chunk_sha256_by_ordinal") or {}
    if any(
        _stable_sha256(selected[str(ordinal)]) != expected_hashes.get(str(ordinal))
        for ordinal in ORDINALS
    ):
        raise SystemExit("g588_frozen_chunk_hash_mismatch")

    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary_binding = dictionary_owner.managed_binding(
        GATE3_DICTIONARY_CURRENT_VERSION
    )
    requested_labels = tuple(args.requested_financial_label)
    if any(label != "TAX_ADJUSTMENT" for label in requested_labels):
        raise SystemExit("g591_requested_label_not_allowed")
    plan = {
        "schema_version": "broker_reports_g591_tax_adjustment_replay_plan_v1",
        "goal": "G5.91",
        "source_corpus_goal": "G5.88",
        "chunk_ordinals": list(ORDINALS),
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "dictionary_binding": dictionary_binding,
        "requested_financial_labels": list(requested_labels),
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_LABELING_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "execution_policy": "one_current_gate3_pass1_attempt_per_frozen_chunk",
        "semantic_attempts_max": len(ORDINALS),
        "transport_submissions_max": len(ORDINALS),
        "semantic_retry": False,
        "best_of_n": False,
        "prompt_variants": 0,
        "kiss_contract_used": False,
        "vlm_calls": 0,
        "production_activation": False,
        "g588_controls_sha256": _file_sha256(source_root / "controls.private.json"),
    }
    _atomic_write(output_root / "frozen-plan.private.json", _json_bytes(plan))
    _atomic_write(output_root / "chunks.private.json", _json_bytes(selected))

    profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved")
    env = _read_env(args.env_file)
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
        store=None,
        read_enabled=False,
        model_client=model_client,
        model_id=args.model_id,
    )

    outcomes: list[dict[str, Any]] = []
    for ordinal in ORDINALS:
        chunk = selected[str(ordinal)]
        try:
            attempt = asyncio.run(
                owner.create_from_chunk(
                    chunk=chunk,
                    requested_financial_labels=requested_labels,
                )
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
            output_root / "replay.in-progress.private.json",
            _json_bytes({"goal": "G5.91", "outcomes": outcomes}),
        )

    replay = {
        "schema_version": "broker_reports_g591_tax_adjustment_replay_private_v1",
        "goal": "G5.91",
        "plan_sha256": _file_sha256(output_root / "frozen-plan.private.json"),
        "semantic_attempts": len(ORDINALS),
        "transport_submissions": submissions["count"],
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 0,
        "outcomes": outcomes,
    }
    _atomic_write(output_root / "replay.private.json", _json_bytes(replay))
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "semantic_attempts": len(ORDINALS),
                "transport_submissions": submissions["count"],
                "validated": sum(
                    item["terminal_status"] == "validated" for item in outcomes
                ),
                "private_output": str(output_root / "replay.private.json"),
            },
            ensure_ascii=False,
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
