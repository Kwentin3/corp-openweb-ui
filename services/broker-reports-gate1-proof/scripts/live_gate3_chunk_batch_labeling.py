#!/usr/bin/env python3
"""Run the explicitly authorized G3.4C one-attempt bounded chunk proof."""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import statistics
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
    Gate3FinancialLabelDictionaryFactory,
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
from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_LABELING_INSTRUCTION,
)
from broker_reports_gate1.gate3_structural_chunking import (  # noqa: E402
    DEFAULT_MAX_CHUNK_CHARS,
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
    "Gate3ChunkBatchLabelingFactory.create and the existing "
    "Gate2StructuredModelClientFactory.create are the only live labeling and "
    "provider paths"
)
FORBIDDEN = (
    "This proof must not retry, repair, fall back, change G3.4B, select chunks "
    "semantically, persist annotations, mutate ArtifactStore, activate a "
    "product route or write private evidence inside Git"
)

DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
FROZEN_G34B_MODULE_SHA256 = (
    "203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba"
)
DOCUMENTS = {
    "compact_html": "brdoc_013_21c85fa3ff06",
    "large_csv": "brdoc_003_be6168a763cd",
    "repo_xlsx": "brdoc_007_4790d8487926",
}
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "normrun_046152421c699e38",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run G3.4C bounded chunk labeling without retry or persistence."
    )
    parser.add_argument("--execute-one-attempt-chunk-batch", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument(
        "--store-root",
        default=str(
            REPO_ROOT
            / "local"
            / "stage2"
            / "broker_reports_doc29_local_restore_2026-08-05"
        ),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g3.4c-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING_G3_4C.receipt.safe.json"
        ),
    )
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    if not args.execute_one_attempt_chunk_batch:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")
    if DEFAULT_MAX_CHUNK_CHARS != 60_000:
        raise SystemExit("frozen_g34b_budget_changed")
    structural_module = (
        SERVICE_ROOT / "broker_reports_gate1" / "gate3_structural_chunking.py"
    )
    if _file_sha256(structural_module) != FROZEN_G34B_MODULE_SHA256:
        raise SystemExit("frozen_g34b_module_changed")

    private_root = Path(args.private_evidence_dir).resolve()
    safe_receipt_path = Path(args.safe_receipt_path).resolve()
    store_root = Path(args.store_root).resolve()
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(safe_receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")

    provider_profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in provider_profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved_for_provider_profile")
    private_root.mkdir(parents=True, exist_ok=True)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id=DEFAULT_CONTEXT["user_id"],
        case_id=DEFAULT_CONTEXT["case_id"],
        chat_id=None,
        workspace_model_id=DEFAULT_CONTEXT["workspace_model_id"],
        normalization_run_id=DEFAULT_CONTEXT["normalization_run_id"],
        allow_private=True,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    store_before = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.before.private.json",
        _json_bytes(store_before),
    )

    chunk_sets: dict[str, dict[str, Any]] = {}
    envelopes: dict[str, Any] = {}
    selections: dict[str, tuple[int, ...]] = {}
    for label, document_id in DOCUMENTS.items():
        envelopes[label] = reader.read_active_envelope(document_id, context)
        chunk_set = Gate3StructuralChunkFactory(
            store=store,
            read_enabled=True,
        ).create(document_id=document_id, context=context)
        chunk_sets[label] = chunk_set
        selections[label] = (
            _representative_repo_ordinals(chunk_set)
            if label == "repo_xlsx"
            else tuple(int(chunk["ordinal"]) for chunk in chunk_set["chunks"])
        )

    expected_submissions = sum(len(value) for value in selections.values())
    plan = {
        "schema_version": "broker_reports_gate3_chunk_batch_live_plan_v1",
        "goal": "G3.4C",
        "execution_policy": "sequential_one_submission_max_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "frozen_g34b": {
            "max_chunk_chars": DEFAULT_MAX_CHUNK_CHARS,
            "module_sha256": FROZEN_G34B_MODULE_SHA256,
        },
        "dictionary_version": "1.0.0",
        "instruction_id": "broker-reports-bounded-semantic-labeling",
        "documents": {
            label: {
                "document_id": DOCUMENTS[label],
                "chunks_available": len(chunk_sets[label]["chunks"]),
                "selected_ordinals": list(selections[label]),
                "selection_mode": (
                    "representative_structural_subset"
                    if label == "repo_xlsx"
                    else "all_chunks"
                ),
                "selected_chunks": [
                    _chunk_plan_descriptor(chunk_sets[label]["chunks"][ordinal - 1])
                    for ordinal in selections[label]
                ],
            }
            for label in DOCUMENTS
        },
        "expected_provider_submissions_max": expected_submissions,
        "selection_reads_financial_content": False,
    }
    plan["plan_sha256"] = _sha256_json(plan)
    _atomic_write(private_root / "frozen_plan.private.json", _json_bytes(plan))
    for label in DOCUMENTS:
        _atomic_write(
            private_root / label / "canonical_envelope.private.json",
            _json_bytes(envelopes[label]),
        )
        _atomic_write(
            private_root / label / "chunk_set.private.json",
            _json_bytes(chunk_sets[label]),
        )

    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published("1.0.0")
    dictionary_markdown = dictionary_owner.render_model_markdown("1.0.0")
    _atomic_write(
        private_root / "dictionary.private.json",
        _json_bytes(dictionary),
    )
    _atomic_write(
        private_root / "dictionary.private.md",
        dictionary_markdown.encode("utf-8"),
    )
    _atomic_write(
        private_root / "instruction.private.txt",
        GATE3_LABELING_INSTRUCTION.encode("utf-8"),
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

    submission_counter = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submission_counter["count"] += 1
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

    safe_documents: dict[str, Any] = {}
    all_safe_attempts: list[dict[str, Any]] = []
    for label, document_id in DOCUMENTS.items():
        submissions_before = submission_counter["count"]
        result = asyncio.run(
            batch_factory.create(
                document_id=document_id,
                context=context,
                chunk_ordinals=(
                    None if label != "repo_xlsx" else selections[label]
                ),
            )
        )
        safe_attempts = []
        for outcome in result.outcomes:
            attempt_private = _private_outcome(outcome)
            attempt_path = (
                private_root
                / label
                / f"chunk-{outcome.chunk['ordinal']:03d}.private.json"
            )
            attempt_bytes = _json_bytes(attempt_private)
            _atomic_write(attempt_path, attempt_bytes)
            safe_attempt = _safe_outcome(
                label=label,
                outcome=outcome,
                private_sha256=hashlib.sha256(attempt_bytes).hexdigest(),
                dictionary_markdown=dictionary_markdown,
            )
            safe_attempts.append(safe_attempt)
            all_safe_attempts.append(safe_attempt)
        batch_private = {
            "schema_version": "broker_reports_gate3_chunk_batch_private_result_v1",
            "document_label": label,
            "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
            "selection_mode": result.selection_mode,
            "document_status": result.document_status,
            "metrics": result.metrics,
            "merged_output": result.merged_output,
            "provider_submissions": (
                submission_counter["count"] - submissions_before
            ),
        }
        batch_bytes = _json_bytes(batch_private)
        _atomic_write(
            private_root / label / "batch_result.private.json",
            batch_bytes,
        )
        safe_documents[label] = {
            "chunks_available": len(chunk_sets[label]["chunks"]),
            "chunks_selected": len(result.selected_chunk_ordinals),
            "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
            "selection_mode": result.selection_mode,
            "document_status": result.document_status,
            "provider_submissions": submission_counter["count"]
            - submissions_before,
            "chunks_validated": result.metrics["chunks_validated"],
            "chunks_rejected": result.metrics["chunks_rejected"],
            "chunks_provider_failed": result.metrics["chunks_provider_failed"],
            "annotations_validated": result.metrics["annotations_validated"],
            "chunk_chars_total": result.metrics["chunk_chars_total"],
            "chunk_chars_max": result.metrics["chunk_chars_max"],
            "aliases_total": result.metrics["aliases_total"],
            "input_tokens_total": result.metrics["input_tokens_total"],
            "input_tokens_max": result.metrics["input_tokens_max"],
            "input_tokens_median": _median_present(
                item["input_tokens"] for item in safe_attempts
            ),
            "output_tokens_total": result.metrics["output_tokens_total"],
            "duration_ms_total": result.metrics["duration_ms_total"],
            "private_batch_result_sha256": hashlib.sha256(batch_bytes).hexdigest(),
            "attempts": safe_attempts,
        }

    store_after = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.after.private.json",
        _json_bytes(store_after),
    )
    if store_before != store_after:
        raise SystemExit("artifact_store_changed_during_g34c")
    if submission_counter["count"] > expected_submissions:
        raise SystemExit("provider_submission_budget_exceeded")

    final_input_chars = sum(
        item["final_model_input_chars"] or 0 for item in all_safe_attempts
    )
    repeated_fixed_chars = expected_submissions * (
        len(dictionary_markdown) + len(GATE3_LABELING_INSTRUCTION)
    )
    receipt = {
        "schema_version": "broker_reports_gate3_chunk_batch_labeling_safe_receipt_v1",
        "goal": "G3.4C",
        "execution_policy": "sequential_one_submission_max_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "frozen_plan_sha256": plan["plan_sha256"],
        "frozen_g34b_module_sha256": FROZEN_G34B_MODULE_SHA256,
        "max_chunk_chars": DEFAULT_MAX_CHUNK_CHARS,
        "dictionary_version": "1.0.0",
        "dictionary_chars": len(dictionary_markdown),
        "instruction_chars": len(GATE3_LABELING_INSTRUCTION),
        "provider_submissions_total": submission_counter["count"],
        "provider_submissions_max": expected_submissions,
        "documents": safe_documents,
        "chunks_submitted": len(all_safe_attempts),
        "chunks_validated": sum(
            item["validation_status"] == "validated"
            for item in all_safe_attempts
        ),
        "chunks_rejected": sum(
            item["validation_status"] == "rejected"
            for item in all_safe_attempts
        ),
        "chunks_provider_failed": sum(
            item["terminal_status"] == "provider_failed"
            for item in all_safe_attempts
        ),
        "schema_adapter_fix_live_proven": any(
            item["provider_schema_version_singleton_enum"] is True
            and item["raw_schema_version_exact"] is True
            and item["validation_status"] == "validated"
            for item in all_safe_attempts
        ),
        "dictionary_injection_counts": sorted(
            {
                item["dictionary_injection_count"]
                for item in all_safe_attempts
                if item["dictionary_injection_count"] is not None
            }
        ),
        "fixed_instruction_dictionary_repetition": {
            "requests": expected_submissions,
            "chars": repeated_fixed_chars,
            "share_of_final_model_input_chars": (
                round(repeated_fixed_chars / final_input_chars, 8)
                if final_input_chars
                else None
            ),
            "token_share_claimed": False,
        },
        "artifact_store_tree_byte_identical": True,
        "store_tree_sha256": store_before["tree_sha256"],
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "persistence_writes": 0,
    }
    _atomic_write(safe_receipt_path, _json_bytes(receipt))
    manifest = _private_manifest(private_root)
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(manifest),
    )
    print(
        json.dumps(
            {
                "goal": "G3.4C",
                "provider_submissions": submission_counter["count"],
                "chunks_validated": receipt["chunks_validated"],
                "chunks_rejected": receipt["chunks_rejected"],
                "chunks_provider_failed": receipt["chunks_provider_failed"],
                "schema_fix_live_proven": receipt[
                    "schema_adapter_fix_live_proven"
                ],
                "store_unchanged": True,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _representative_repo_ordinals(chunk_set: dict[str, Any]) -> tuple[int, ...]:
    chunks = list(chunk_set["chunks"])
    whole = [
        chunk for chunk in chunks if chunk["structural_kind"] == "whole_table"
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        if chunk["structural_kind"] != "table_rows":
            continue
        refs = chunk["structural_scope"]["node_refs"]
        if len(refs) != 1:
            raise SystemExit("repo_row_chunk_node_scope_invalid")
        grouped.setdefault(str(refs[0]), []).append(chunk)
    if not whole or not grouped:
        raise SystemExit("repo_representative_chunk_shapes_missing")
    row_group = min(
        grouped.values(),
        key=lambda group: (-len(group), int(group[0]["ordinal"])),
    )
    middle_index = len(row_group) // 2
    chosen = {
        int(whole[0]["ordinal"]),
        int(row_group[0]["ordinal"]),
        int(row_group[middle_index]["ordinal"]),
        int(row_group[min(middle_index + 1, len(row_group) - 1)]["ordinal"]),
        int(row_group[-1]["ordinal"]),
    }
    if len(chosen) < 4:
        raise SystemExit("repo_representative_subset_too_small")
    return tuple(sorted(chosen))


def _chunk_plan_descriptor(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk["chunk_id"],
        "ordinal": chunk["ordinal"],
        "structural_kind": chunk["structural_kind"],
        "structural_scope": copy.deepcopy(chunk["structural_scope"]),
        "model_view_chars": chunk["metrics"]["model_view_chars"],
        "target_count": chunk["metrics"]["target_count"],
        "model_view_sha256": hashlib.sha256(
            chunk["model_view"]["content"].encode("utf-8")
        ).hexdigest(),
    }


def _private_outcome(outcome) -> dict[str, Any]:
    if outcome.attempt is not None:
        attempt = outcome.attempt
        return {
            "schema_version": "broker_reports_gate3_chunk_labeling_private_evidence_v1",
            "chunk": copy.deepcopy(outcome.chunk),
            "dictionary": copy.deepcopy(attempt.dictionary),
            "dictionary_markdown": attempt.dictionary_markdown,
            "instruction": attempt.instruction,
            "model_visible_request": attempt.model_visible_request,
            "final_provider_request": attempt.final_provider_request,
            "raw_provider_response": attempt.raw_provider_response,
            "raw_model_output": attempt.raw_model_output,
            "validated_output": attempt.validated_output,
            "validation_status": attempt.validation_status,
            "validation_error_code": attempt.validation_error_code,
            "execution_metadata": _jsonable(attempt.execution_metadata),
            "metrics": attempt.metrics,
            "terminal_status": outcome.terminal_status,
        }
    error = outcome.provider_error
    prepared = getattr(error, "prepared_request", None)
    return {
        "schema_version": "broker_reports_gate3_chunk_labeling_private_evidence_v1",
        "chunk": copy.deepcopy(outcome.chunk),
        "dictionary": None,
        "dictionary_markdown": None,
        "instruction": GATE3_LABELING_INSTRUCTION,
        "model_visible_request": _sealed_view(
            copy.deepcopy(prepared.form_data) if prepared is not None else None
        ),
        "final_provider_request": (
            copy.deepcopy(prepared.form_data) if prepared is not None else None
        ),
        "raw_provider_response": copy.deepcopy(
            getattr(error, "raw_provider_response", None)
        ),
        "raw_model_output": copy.deepcopy(getattr(error, "raw_output", None)),
        "validated_output": None,
        "validation_status": None,
        "validation_error_code": None,
        "execution_metadata": _jsonable(
            getattr(error, "execution_metadata", None)
        ),
        "metrics": {},
        "terminal_status": outcome.terminal_status,
        "terminal_error": {
            "error_type": error.__class__.__name__ if error else None,
            "error_code": outcome.error_code,
            "error_args": _jsonable(error.args if error else ()),
        },
    }


def _safe_outcome(
    *,
    label: str,
    outcome,
    private_sha256: str,
    dictionary_markdown: str,
) -> dict[str, Any]:
    attempt = outcome.attempt
    metrics = attempt.metrics if attempt is not None else {}
    execution = (
        attempt.execution_metadata
        if attempt is not None
        else getattr(outcome.provider_error, "execution_metadata", None)
    )
    final_request = (
        attempt.final_provider_request
        if attempt is not None
        else getattr(getattr(outcome.provider_error, "prepared_request", None), "form_data", None)
    )
    schema = _provider_schema(final_request)
    raw_output = attempt.raw_model_output if attempt is not None else None
    raw_schema = raw_output.get("schema_version") if isinstance(raw_output, dict) else None
    if isinstance(raw_output, str):
        try:
            decoded = json.loads(raw_output)
        except json.JSONDecodeError:
            decoded = None
        raw_schema = decoded.get("schema_version") if isinstance(decoded, dict) else None
    labels = []
    if attempt is not None and attempt.validated_output is not None:
        labels = sorted(
            {
                annotation["financial_label"]
                for annotation in attempt.validated_output["annotations"]
            }
        )
    return {
        "document_label": label,
        "chunk_ordinal": outcome.chunk["ordinal"],
        "structural_kind": outcome.chunk["structural_kind"],
        "row_start": outcome.chunk["structural_scope"]["row_start"],
        "row_end": outcome.chunk["structural_scope"]["row_end"],
        "chunk_chars": outcome.chunk["metrics"]["model_view_chars"],
        "aliases": outcome.chunk["metrics"]["target_count"],
        "terminal_status": outcome.terminal_status,
        "validation_status": (
            attempt.validation_status if attempt is not None else None
        ),
        "validation_error_code": outcome.error_code,
        "annotations_validated": (
            len(attempt.validated_output["annotations"])
            if attempt is not None and attempt.validated_output is not None
            else 0
        ),
        "labels_observed": labels,
        "input_tokens": getattr(execution, "input_tokens", None),
        "output_tokens": getattr(execution, "output_tokens", None),
        "total_tokens": getattr(execution, "total_tokens", None),
        "duration_ms": getattr(execution, "duration_ms", None),
        "final_model_input_chars": metrics.get("final_model_input_chars"),
        "dictionary_injection_count": (
            sum(
                part.count(dictionary_markdown)
                for part in _provider_visible_parts(final_request)
            )
            if isinstance(final_request, dict)
            else None
        ),
        "provider_schema_version_singleton_enum": (
            (schema.get("properties") or {}).get("schema_version")
            == {"enum": ["broker_reports_gate3_labeling_response_v1"]}
            if isinstance(schema, dict)
            else False
        ),
        "raw_schema_version_exact": (
            raw_schema == "broker_reports_gate3_labeling_response_v1"
        ),
        "private_evidence_sha256": private_sha256,
    }


def _provider_schema(final_request: Any) -> dict[str, Any] | None:
    if not isinstance(final_request, dict):
        return None
    response_format = final_request.get("response_format")
    if isinstance(response_format, dict):
        wrapper = response_format.get("json_schema")
        return wrapper.get("schema") if isinstance(wrapper, dict) else None
    output_config = final_request.get("output_config")
    if isinstance(output_config, dict):
        return output_config.get("response_schema")
    return None


def _provider_visible_parts(final_request: Any) -> list[str]:
    if not isinstance(final_request, dict):
        return []
    parts = []
    system = final_request.get("system")
    if isinstance(system, str):
        parts.append(system)
    messages = final_request.get("messages")
    if isinstance(messages, list):
        parts.extend(
            item["content"]
            for item in messages
            if isinstance(item, dict) and isinstance(item.get("content"), str)
        )
    return parts


def _sealed_view(final_provider_request: Any) -> dict[str, Any] | None:
    if not isinstance(final_provider_request, dict):
        return None
    if "system" in final_provider_request:
        messages = [
            {"role": "system", "content": final_provider_request["system"]},
            *copy.deepcopy(final_provider_request.get("messages") or []),
        ]
        response_format = copy.deepcopy(final_provider_request.get("output_config"))
    else:
        messages = copy.deepcopy(final_provider_request.get("messages"))
        response_format = copy.deepcopy(final_provider_request.get("response_format"))
    return {"messages": messages, "response_format": response_format}


def _store_tree_snapshot(root: Path) -> dict[str, Any]:
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
    material = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "tree_sha256": hashlib.sha256(material).hexdigest(),
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
        "schema_version": "broker_reports_gate3_chunk_batch_private_manifest_v1",
        "goal": "G3.4C",
        "privacy": "PRIVATE_OUTSIDE_GIT",
        "files": files,
    }


def _median_present(values) -> int | float | None:
    present = [value for value in values if isinstance(value, int)]
    return statistics.median(present) if present else None


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


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


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


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
