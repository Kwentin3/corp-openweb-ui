#!/usr/bin/env python3
"""Freeze the G5.92 development and untouched-holdout request plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_PREDECLARED_ASSERTION_INSTRUCTION,
    GATE3_PREDECLARED_ASSERTION_INSTRUCTION_VERSION,
    GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256,
    Gate3BoundedLabelingFactory,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_V2_1_VERSION,
)


DEVELOPMENT_ORDINALS = (10, 12, 14, 16, 20, 22, 52)
HOLDOUT_ORDINALS = (128,)
DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g588-evidence-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    args = parser.parse_args()

    source_root = args.g588_evidence_dir.resolve()
    output_root = args.private_output_dir.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit("private_output_must_be_new_or_empty")
    output_root.mkdir(parents=True, exist_ok=True)

    source_plan = _read_json(source_root / "frozen-plan.private.json")
    chunks = _read_json(source_root / "chunks.private.json")
    if source_plan.get("goal") != "G5.88":
        raise SystemExit("g588_frozen_plan_required")
    all_ordinals = (*DEVELOPMENT_ORDINALS, *HOLDOUT_ORDINALS)
    selected = {str(ordinal): chunks[str(ordinal)] for ordinal in all_ordinals}
    expected_hashes = source_plan.get("chunk_sha256_by_ordinal") or {}
    if any(
        _stable_sha256(selected[str(ordinal)]) != expected_hashes.get(str(ordinal))
        for ordinal in all_ordinals
    ):
        raise SystemExit("g588_frozen_chunk_hash_mismatch")

    owner = Gate3BoundedLabelingFactory(
        store=None,
        read_enabled=False,
        model_client=None,
        model_id=args.model_id,
        dictionary_version=GATE3_DICTIONARY_V2_1_VERSION,
    )
    batches: dict[str, Any] = {}
    request_hashes: dict[str, str] = {}
    assertion_counts: dict[str, int] = {}
    dictionary_binding: dict[str, Any] | None = None
    for ordinal in all_ordinals:
        prepared = owner.prepare_predeclared_assertion_batch(
            chunk=selected[str(ordinal)]
        )
        if dictionary_binding is None:
            dictionary_binding = prepared["dictionary_managed_binding"]
        elif prepared["dictionary_managed_binding"] != dictionary_binding:
            raise SystemExit("dictionary_binding_drift")
        batch = {
            "assertion_envelope": prepared["assertion_envelope"],
            "model_visible_request": prepared["model_visible_request"],
        }
        batches[str(ordinal)] = batch
        request_hashes[str(ordinal)] = _stable_sha256(
            prepared["model_visible_request"]
        )
        assertion_counts[str(ordinal)] = len(
            prepared["assertion_envelope"]["assertions"]
        )

    plan = {
        "schema_version": "broker_reports_g592_predeclared_assertion_plan_v1",
        "goal": "G5.92",
        "source_corpus_goal": "G5.88",
        "development_ordinals": list(DEVELOPMENT_ORDINALS),
        "untouched_holdout_ordinals": list(HOLDOUT_ORDINALS),
        "holdout_policy": "execute_once_after_development_proof_without_refinement",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "dictionary_binding": dictionary_binding,
        "instruction_version": GATE3_PREDECLARED_ASSERTION_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_PREDECLARED_ASSERTION_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "response_schema_sha256": (
            GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256
        ),
        "request_sha256_by_ordinal": request_hashes,
        "assertion_count_by_ordinal": assertion_counts,
        "execution_policy": "one_batch_attempt_per_frozen_structural_chunk",
        "semantic_attempts_max_development": len(DEVELOPMENT_ORDINALS),
        "semantic_attempts_max_holdout": len(HOLDOUT_ORDINALS),
        "semantic_retry": False,
        "best_of_n": False,
        "prompt_variants": 1,
        "model_variants": 1,
        "broker_specific_rules": 0,
        "literal_specific_rules": 0,
        "role_binding": False,
        "tax_calculation": False,
        "production_activation": False,
        "g588_controls_sha256": _file_sha256(source_root / "controls.private.json"),
        "g588_source_truth_sha256": _file_sha256(
            source_root / "development-source-truth-qualification.private.json"
        ),
    }
    _atomic_write(output_root / "frozen-plan.private.json", _json_bytes(plan))
    _atomic_write(output_root / "chunks.private.json", _json_bytes(selected))
    _atomic_write(output_root / "batches.private.json", _json_bytes(batches))
    print(
        json.dumps(
            {
                "status": "FROZEN",
                "development_batches": len(DEVELOPMENT_ORDINALS),
                "holdout_batches": len(HOLDOUT_ORDINALS),
                "development_assertions": sum(
                    assertion_counts[str(item)] for item in DEVELOPMENT_ORDINALS
                ),
                "holdout_assertions": sum(
                    assertion_counts[str(item)] for item in HOLDOUT_ORDINALS
                ),
                "provider_calls": 0,
                "private_plan_sha256": _file_sha256(
                    output_root / "frozen-plan.private.json"
                ),
            },
            sort_keys=True,
        )
    )
    return 0


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
