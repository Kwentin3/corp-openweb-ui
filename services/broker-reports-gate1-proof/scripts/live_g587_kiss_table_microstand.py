#!/usr/bin/env python3
"""Freeze and run the inactive G5.87 exhaustive table JSON microstand."""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import sys
import time
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
from g587_kiss_table_contract import (  # noqa: E402
    INSTRUCTION,
    INSTRUCTION_ID,
    INSTRUCTION_VERSION,
    compose_request,
    stable_sha256,
    table_rows,
    validate_and_map,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _is_within,
    _json_bytes,
    _private_manifest,
    _store_tree_snapshot,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


DOCUMENT_ID = "brdoc_001_7cfd297786cc"
NORMALIZATION_RUN_ID = "normrun_1f4f2d9e30c1a076"
DEV_ORDINALS = (10, 12, 14, 16, 20, 22, 52)
TAX_ORDINALS = (10, 12, 14, 16, 20, 22)
HOLDOUT_ORDINALS = (128,)
DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "workspace_model_id": "g540e-private-model",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("freeze", "development", "holdout"), required=True
    )
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--baseline-batch", type=Path, required=True)
    parser.add_argument("--semantic-stop", type=Path, required=True)
    parser.add_argument("--private-evidence-dir", type=Path, required=True)
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    root = args.private_evidence_dir.resolve()
    store_root = args.store_root.resolve()
    if _is_within(root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")
    if args.phase == "freeze":
        return _freeze(args, root, store_root)
    return _execute(args, root, store_root)


def _freeze(args: argparse.Namespace, root: Path, store_root: Path) -> int:
    if root.exists() and any(root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    root.mkdir(parents=True, exist_ok=True)
    store, context, chunk_set, canonical_artifact = _load_source(store_root)
    del store, canonical_artifact
    baseline = _read_json(args.baseline_batch)
    semantic_stop = _read_json(args.semantic_stop)
    baseline_chunks = {
        int(item["ordinal"]): item for item in baseline["chunk_set"]["chunks"]
    }
    selected = [*DEV_ORDINALS, *HOLDOUT_ORDINALS]
    chunks = {
        int(item["ordinal"]): item
        for item in chunk_set["chunks"]
        if int(item["ordinal"]) in selected
    }
    if set(chunks) != set(selected):
        raise SystemExit("frozen_chunk_missing")
    for ordinal, chunk in chunks.items():
        if chunk != baseline_chunks[ordinal]:
            raise SystemExit("chunk_drift_from_g583_baseline")

    requests_by_ordinal = {
        ordinal: compose_request(chunks[ordinal]) for ordinal in selected
    }
    controls = _build_controls(
        baseline=baseline,
        semantic_stop=semantic_stop,
        chunks=chunks,
    )
    if len(controls["affected_tax_exact"]) != 105:
        raise SystemExit("affected_tax_control_count_mismatch")
    if len(controls["true_dividend_exact"]) != 25:
        raise SystemExit("true_dividend_control_count_mismatch")
    if len(controls["existing_tax_exact"]) != 114:
        raise SystemExit("existing_tax_control_count_mismatch")
    frozen = {
        "schema_version": "broker_reports_g588_frozen_plan_v1",
        "goal": "G5.88",
        "document_id": DOCUMENT_ID,
        "canonical_binding": chunk_set["canonical_binding"],
        "development_ordinals": list(DEV_ORDINALS),
        "holdout_ordinals": list(HOLDOUT_ORDINALS),
        "holdout_layout": "other_fees_table_family_same_document",
        "other_document_table_unit_available_from_current_chunk_owner": False,
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "instruction_id": INSTRUCTION_ID,
        "instruction_version": INSTRUCTION_VERSION,
        "instruction_sha256": stable_sha256(INSTRUCTION),
        "semantic_attempts_max_development": len(DEV_ORDINALS),
        "semantic_attempts_max_holdout": len(HOLDOUT_ORDINALS),
        "execution_policy": "one_single_shot_semantic_response_per_table_sequential",
        "operational_retry_policy": "gate3_operational_no_response_v1",
        "semantic_retry": False,
        "best_of_n": False,
        "prompt_variants": 0,
        "vlm_calls": 0,
        "production_activation": False,
        "controls": controls,
        "request_sha256_by_ordinal": {
            str(key): stable_sha256(value) for key, value in requests_by_ordinal.items()
        },
        "chunk_sha256_by_ordinal": {
            str(key): stable_sha256(value) for key, value in chunks.items()
        },
        "baseline_batch_sha256": _file_sha256(args.baseline_batch),
        "semantic_stop_sha256": _file_sha256(args.semantic_stop),
        "store_tree_before_sha256": stable_sha256(_store_tree_snapshot(store_root)),
        "context": copy.deepcopy(CONTEXT),
        "normalization_run_id": context.normalization_run_id,
    }
    _atomic_write(root / "frozen-plan.private.json", _json_bytes(frozen))
    _atomic_write(root / "instruction.private.txt", INSTRUCTION.encode("utf-8"))
    _atomic_write(root / "chunks.private.json", _json_bytes(chunks))
    _atomic_write(root / "requests.private.json", _json_bytes(requests_by_ordinal))
    _atomic_write(root / "controls.private.json", _json_bytes(controls))
    _atomic_write(
        root / "store-tree.before.private.json",
        _json_bytes(_store_tree_snapshot(store_root)),
    )
    _atomic_write(root / "private-manifest.json", _json_bytes(_private_manifest(root)))
    print(
        json.dumps(
            {
                "phase": "freeze",
                "status": "FROZEN",
                "private_evidence_dir": str(root),
                "controls": {key: len(value) for key, value in controls.items()},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _execute(args: argparse.Namespace, root: Path, store_root: Path) -> int:
    if not (root / "frozen-plan.private.json").is_file():
        raise SystemExit("frozen_plan_required")
    plan = _read_json(root / "frozen-plan.private.json")
    chunks_raw = _read_json(root / "chunks.private.json")
    requests_raw = _read_json(root / "requests.private.json")
    chunks = {int(key): value for key, value in chunks_raw.items()}
    requests_by_ordinal = {int(key): value for key, value in requests_raw.items()}
    _verify_frozen(plan, chunks, requests_by_ordinal, args)
    if args.phase == "development":
        ordinals = DEV_ORDINALS
        output_path = root / "development.private.json"
    else:
        development = (
            _read_json(root / "development.private.json")
            if (root / "development.private.json").is_file()
            else None
        )
        if not _development_complete_for_holdout(development):
            raise SystemExit("complete_development_required_before_holdout")
        ordinals = HOLDOUT_ORDINALS
        output_path = root / "holdout.private.json"
    if output_path.exists():
        raise SystemExit("phase_output_already_exists")

    profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved")
    store, context, chunk_set, canonical_artifact = _load_source(store_root)
    del store, chunk_set
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
    boundary = _completion_boundary(
        session=session, base_url=base_url, timeout=args.timeout_seconds
    )

    def counted_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return boundary(form_data=form_data, **kwargs)

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
    outcomes = []
    semantic_responses_received = 0
    for ordinal in ordinals:
        request = requests_by_ordinal[ordinal]
        schema = request["response_format"]["json_schema"]["schema"]
        submissions_before = submissions["count"]
        started = time.perf_counter()
        try:
            result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=request,
                    canonical_schema=schema,
                    model_id=args.model_id,
                )
            )
        except Gate2SourceFactRuntimeError as exc:
            outcome = {
                "ordinal": ordinal,
                "status": "provider_failed",
                "error_code": exc.code,
                "operational_retry_receipt": copy.deepcopy(
                    getattr(exc, "operational_retry_receipt", None)
                ),
                "elapsed_seconds": time.perf_counter() - started,
                "transport_submissions": submissions["count"] - submissions_before,
            }
        else:
            semantic_responses_received += 1
            raw_evidence = {
                "schema_version": "broker_reports_g588_raw_table_response_v1",
                "goal": "G5.88",
                "ordinal": ordinal,
                "raw_model_output": copy.deepcopy(result.adapter_extracted_output),
                "raw_provider_response": copy.deepcopy(result.raw_provider_response),
                "prepared_request": _jsonable(result.prepared_request.form_data),
                "execution_metadata": _jsonable(result.execution_metadata),
                "operational_retry_receipt": copy.deepcopy(
                    result.operational_retry_receipt
                ),
                "elapsed_seconds": time.perf_counter() - started,
                "transport_submissions": submissions["count"] - submissions_before,
            }
            raw_path = root / f"{args.phase}-chunk-{ordinal:03d}-raw.private.json"
            _atomic_write(raw_path, _json_bytes(raw_evidence))
            try:
                validated = validate_and_map(
                    raw_model_output=result.adapter_extracted_output,
                    chunk=chunks[ordinal],
                    canonical_artifact=canonical_artifact,
                    model_id=args.model_id,
                )
            except Exception as exc:  # raw evidence is already durable
                outcome = {
                    "ordinal": ordinal,
                    "status": "validator_failed",
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", type(exc).__name__),
                    "raw_evidence_file": raw_path.name,
                    "operational_retry_receipt": copy.deepcopy(
                        result.operational_retry_receipt
                    ),
                }
            else:
                outcome = {
                    "ordinal": ordinal,
                    "status": "validated",
                    "error_code": None,
                    "raw_evidence_file": raw_path.name,
                    "operational_retry_receipt": copy.deepcopy(
                        result.operational_retry_receipt
                    ),
                    "validated": validated,
                }
        outcomes.append(outcome)
        _atomic_write(
            root / f"{args.phase}-chunk-{ordinal:03d}.private.json",
            _json_bytes(outcome),
        )

    qualification = _qualify(args.phase, outcomes, plan["controls"])
    result_payload = {
        "schema_version": "broker_reports_g588_phase_result_v1",
        "goal": "G5.88",
        "phase": args.phase,
        "qualified": qualification["qualified"],
        "terminal": qualification["terminal"],
        "semantic_attempts": len(ordinals),
        "transport_submissions": submissions["count"],
        "semantic_responses_received": semantic_responses_received,
        "semantic_retries": 0,
        "vlm_calls": 0,
        "production_activation": False,
        "qualification": qualification,
        "outcomes": outcomes,
        "store_tree_unchanged": _store_tree_snapshot(store_root)
        == _read_json(root / "store-tree.before.private.json"),
    }
    _atomic_write(output_path, _json_bytes(result_payload))
    _atomic_write(root / "private-manifest.json", _json_bytes(_private_manifest(root)))
    print(
        json.dumps(
            {
                key: result_payload[key]
                for key in (
                    "phase",
                    "qualified",
                    "terminal",
                    "semantic_attempts",
                    "transport_submissions",
                    "store_tree_unchanged",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _load_source(store_root: Path):
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
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=DOCUMENT_ID, context=context
    )
    envelope = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(DOCUMENT_ID, context)
    )
    if (
        envelope.canonical_version_id
        != chunk_set["canonical_binding"]["canonical_version_id"]
    ):
        raise SystemExit("canonical_binding_stale")
    return store, context, chunk_set, envelope.artifact


def _build_controls(
    *,
    baseline: dict[str, Any],
    semantic_stop: dict[str, Any],
    chunks: dict[int, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    row_id_by_identity: dict[tuple[str, int], tuple[int, str]] = {}
    for ordinal, chunk in chunks.items():
        for row in table_rows(chunk):
            target = row["row_target"]
            row_id_by_identity[(target["node_id"], target["row"])] = (
                ordinal,
                row["row_id"],
            )
    labels_by_row = _baseline_labels_by_row(baseline, chunks)
    affected: list[dict[str, Any]] = []
    for fact in semantic_stop["systematic_conflict"]["private_affected_facts"]:
        target = fact["target"]
        ordinal, row_id = row_id_by_identity[(target["node_id"], target["row"])]
        affected.append(
            {"ordinal": ordinal, "row_id": row_id, "expected_labels": ["TAX_WITHHELD"]}
        )
    affected_ids = {(item["ordinal"], item["row_id"]) for item in affected}
    true_dividends = [
        {"ordinal": ordinal, "row_id": row_id, "expected_labels": ["DIVIDEND_INCOME"]}
        for (ordinal, row_id), labels in sorted(labels_by_row.items())
        if ordinal in TAX_ORDINALS
        and "DIVIDEND_INCOME" in labels
        and (ordinal, row_id) not in affected_ids
    ]
    existing_tax = [
        {
            "ordinal": ordinal,
            "row_id": row_id,
            "expected_labels": ["TAX_WITHHELD"],
        }
        for (ordinal, row_id), labels in sorted(labels_by_row.items())
        if ordinal in TAX_ORDINALS and "TAX_WITHHELD" in labels
    ]
    structural = []
    for ordinal in TAX_ORDINALS:
        for row in table_rows(chunks[ordinal])[:2]:
            structural.append(
                {"ordinal": ordinal, "row_id": row["row_id"], "expected_status": "NONE"}
            )
    cross_by_row: dict[tuple[int, str], dict[str, Any]] = {}
    for label in (
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "COMMISSION",
        "TRANSACTION_CHARGE",
    ):
        candidates = [
            (row_id, labels)
            for (ordinal, row_id), labels in labels_by_row.items()
            if ordinal == 52 and label in labels
        ]
        for row_id, labels in candidates[:2]:
            cross_by_row[(52, row_id)] = {
                "ordinal": 52,
                "row_id": row_id,
                "expected_labels": sorted(labels),
            }
    holdout = [
        {"ordinal": ordinal, "row_id": row_id, "expected_labels": sorted(labels)}
        for (ordinal, row_id), labels in sorted(labels_by_row.items())
        if ordinal in HOLDOUT_ORDINALS
    ]
    return {
        "affected_tax_exact": affected,
        "true_dividend_exact": true_dividends,
        "existing_tax_exact": existing_tax,
        "structural_none": structural,
        "cross_type": list(cross_by_row.values()),
        "holdout": holdout,
    }


def _baseline_labels_by_row(
    baseline: dict[str, Any], chunks: dict[int, dict[str, Any]]
) -> dict[tuple[int, str], set[str]]:
    result: dict[tuple[int, str], set[str]] = {}
    for outcome in baseline["outcomes"]:
        ordinal = int(outcome["chunk"]["ordinal"])
        if ordinal not in chunks:
            continue
        mapping_by_alias = {
            item["target_alias"]: item["canonical_target"]
            for item in chunks[ordinal]["target_mappings"]
        }
        row_by_identity = {
            (row["row_target"]["node_id"], row["row_target"]["row"]): row["row_id"]
            for row in table_rows(chunks[ordinal])
        }
        raw = (outcome.get("pass1_attempt") or {}).get("raw_model_output")
        if isinstance(raw, str):
            raw = json.loads(raw)
        for annotation in (raw or {}).get("annotations", []):
            target = mapping_by_alias[annotation["target_alias"]]
            identity = (target.get("node_id"), target.get("row"))
            if identity in row_by_identity:
                result.setdefault((ordinal, row_by_identity[identity]), set()).add(
                    annotation["financial_label"]
                )
    return result


def _qualify(
    phase: str,
    outcomes: list[dict[str, Any]],
    controls: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    labels_by_key: dict[tuple[int, str], set[str]] = {}
    statuses_by_key: dict[tuple[int, str], str] = {}
    for outcome in outcomes:
        if outcome["status"] != "validated":
            continue
        validated = outcome["validated"]
        ordinal = int(outcome["ordinal"])
        statuses_by_key.update(
            {
                (ordinal, row_id): status
                for row_id, status in validated["row_statuses"].items()
            }
        )
        annotations = validated["mapped_financial_annotations_v2"]["annotations"]
        for row_id, annotation in zip(
            validated["annotation_row_ids"], annotations, strict=True
        ):
            labels_by_key.setdefault((ordinal, row_id), set()).add(
                annotation["financial_label"]
            )
    selected_groups = (
        [
            "affected_tax_exact",
            "true_dividend_exact",
            "existing_tax_exact",
            "structural_none",
            "cross_type",
        ]
        if phase == "development"
        else ["holdout"]
    )
    scores = {}
    for group in selected_groups:
        passed = 0
        failures = []
        for item in controls[group]:
            key = (item["ordinal"], item["row_id"])
            if "expected_labels" in item:
                ok = labels_by_key.get(key, set()) == set(item["expected_labels"])
            else:
                ok = statuses_by_key.get(key) == item["expected_status"]
            if ok:
                passed += 1
            else:
                failures.append(
                    {
                        "ordinal": key[0],
                        "row_id": key[1],
                        "actual_labels": sorted(labels_by_key.get(key, set())),
                        "actual_status": statuses_by_key.get(key),
                    }
                )
        scores[group] = {
            "passed": passed,
            "total": len(controls[group]),
            "failures": failures[:20],
        }
    qualified = all(outcome["status"] == "validated" for outcome in outcomes) and all(
        item["passed"] == item["total"] for item in scores.values()
    )
    terminal = (
        "KISS_TABLE_CONTRACT_DEVELOPMENT_QUALIFIED"
        if phase == "development" and qualified
        else "KISS_TABLE_CONTRACT_HOLDOUT_GENERALIZATION_QUALIFIED"
        if qualified
        else "KISS_TABLE_CONTRACT_SEMANTIC_RELIABILITY_INSUFFICIENT"
        if phase == "development"
        else "KISS_TABLE_CONTRACT_HOLDOUT_GENERALIZATION_FAILED"
    )
    return {
        "qualified": qualified,
        "terminal": terminal,
        "scores": scores,
        "outcomes_validated": sum(item["status"] == "validated" for item in outcomes),
        "outcomes_total": len(outcomes),
    }


def _verify_frozen(
    plan: dict[str, Any],
    chunks: dict[int, dict[str, Any]],
    requests_by_ordinal: dict[int, dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    if (
        plan.get("instruction_sha256") != stable_sha256(INSTRUCTION)
        or plan.get("provider_profile_id") != args.provider_profile_id
        or plan.get("model_id") != args.model_id
    ):
        raise SystemExit("frozen_contract_drift")
    for ordinal, chunk in chunks.items():
        if plan["chunk_sha256_by_ordinal"][str(ordinal)] != stable_sha256(
            chunk
        ) or plan["request_sha256_by_ordinal"][str(ordinal)] != stable_sha256(
            requests_by_ordinal[ordinal]
        ):
            raise SystemExit("frozen_input_drift")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("json_object_required")
    return value


def _development_complete_for_holdout(value: Any) -> bool:
    """Permit one frozen holdout after terminal development, including a failure."""

    return (
        isinstance(value, dict)
        and value.get("goal") == "G5.88"
        and value.get("phase") == "development"
        and value.get("semantic_attempts") == len(DEV_ORDINALS)
        and value.get("semantic_responses_received") == len(DEV_ORDINALS)
        and value.get("semantic_retries") == 0
        and isinstance(value.get("terminal"), str)
        and bool(value["terminal"])
        and isinstance(value.get("outcomes"), list)
        and len(value["outcomes"]) == len(DEV_ORDINALS)
        and all(item.get("status") == "validated" for item in value["outcomes"])
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
