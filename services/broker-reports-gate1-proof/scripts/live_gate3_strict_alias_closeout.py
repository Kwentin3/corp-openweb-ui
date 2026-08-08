#!/usr/bin/env python3
"""Run the explicitly authorized G3.4D strict-alias live closeout proof."""

from __future__ import annotations

import argparse
import asyncio
import copy
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
    GATE3_LABELING_INSTRUCTION_VERSION,
    GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
    _load_response_schema,
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
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _base_url,
    _chunk_plan_descriptor,
    _file_sha256,
    _is_within,
    _json_bytes,
    _private_manifest,
    _private_outcome,
    _provider_schema,
    _read_env,
    _safe_outcome,
    _sha256_json,
    _signin,
    _store_tree_snapshot,
    _url,
)


FACTORY_REQUIRED = (
    "Gate3ChunkBatchLabelingFactory.create and the existing "
    "Gate2StructuredModelClientFactory.create are the only live execution "
    "paths; the exact Gate3BoundedLabeling validator remains authoritative"
)
FORBIDDEN = (
    "G3.4D must not normalize or repair aliases, enumerate current aliases in "
    "schema, retry, change dictionary/chunking/semantics/merge, persist "
    "annotations, activate a product route or start G3.5"
)

DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
FROZEN_G34B_MODULE_SHA256 = (
    "203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba"
)
DOCUMENTS = {
    "compact_html": "brdoc_013_21c85fa3ff06",
    "large_csv_chunk3": "brdoc_003_be6168a763cd",
}
SELECTIONS: dict[str, tuple[int, ...] | None] = {
    "compact_html": None,
    "large_csv_chunk3": (3,),
}
FROZEN_SAFE_SHAPES = {
    "compact_html": {
        "available_chunks": 1,
        "ordinal": 1,
        "structural_kind": "whole_document",
        "row_start": None,
        "row_end": None,
        "model_view_chars": 15042,
        "target_count": 612,
    },
    "large_csv_chunk3": {
        "available_chunks": 6,
        "ordinal": 3,
        "structural_kind": "table_rows",
        "row_start": 488,
        "row_end": 761,
        "model_view_chars": 59964,
        "target_count": 2106,
    },
}
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "normrun_046152421c699e38",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run G3.4D strict-alias live reproof without repair or retry."
    )
    parser.add_argument("--execute-strict-alias-live-reproof", action="store_true")
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
            / "broker-reports-g3.4d-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_STRICT_ALIAS_G3_4D.receipt.safe.json"
        ),
    )
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    if not args.execute_strict_alias_live_reproof:
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
    if GATE3_LABELING_INSTRUCTION_VERSION != "1.0.1":
        raise SystemExit("strict_alias_instruction_version_changed")

    response_schema = _load_response_schema()
    alias_schema = _alias_schema(response_schema)
    alias_description = alias_schema.get("description")
    if (
        alias_schema.get("type") != "string"
        or alias_schema.get("pattern") != "^t[0-9]{3,}$"
        or not isinstance(alias_description, str)
        or "[t123]" not in alias_description
        or "t123" not in alias_description
        or "enum" in alias_schema
    ):
        raise SystemExit("strict_alias_canonical_schema_invalid")

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
    store_before = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.before.private.json",
        _json_bytes(store_before),
    )

    chunk_sets: dict[str, dict[str, Any]] = {}
    selected_chunks: dict[str, list[dict[str, Any]]] = {}
    for label, document_id in DOCUMENTS.items():
        chunk_set = Gate3StructuralChunkFactory(
            store=store,
            read_enabled=True,
        ).create(document_id=document_id, context=context)
        selection = SELECTIONS[label]
        selected = (
            list(chunk_set["chunks"])
            if selection is None
            else [
                chunk
                for chunk in chunk_set["chunks"]
                if int(chunk["ordinal"]) in selection
            ]
        )
        _validate_frozen_shape(
            label=label,
            chunk_set=chunk_set,
            selected=selected,
        )
        chunk_sets[label] = chunk_set
        selected_chunks[label] = selected
        _atomic_write(
            private_root / label / "selected_chunks.private.json",
            _json_bytes(selected),
        )

    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published("1.0.0")
    dictionary_markdown = dictionary_owner.render_model_markdown("1.0.0")
    plan = {
        "schema_version": "broker_reports_gate3_strict_alias_live_plan_v1",
        "goal": "G3.4D",
        "execution_policy": "two_predeclared_calls_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "frozen_g34b": {
            "max_chunk_chars": DEFAULT_MAX_CHUNK_CHARS,
            "module_sha256": FROZEN_G34B_MODULE_SHA256,
        },
        "response_schema_sha256": GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
        "alias_pattern": alias_schema["pattern"],
        "alias_description": alias_description,
        "alias_enum_present": False,
        "dictionary_version": "1.0.0",
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_LABELING_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "documents": {
            label: {
                "document_id": DOCUMENTS[label],
                "chunks_available": len(chunk_sets[label]["chunks"]),
                "selected_ordinals": [
                    int(chunk["ordinal"]) for chunk in selected_chunks[label]
                ],
                "selected_chunks": [
                    _chunk_plan_descriptor(chunk)
                    for chunk in selected_chunks[label]
                ],
            }
            for label in DOCUMENTS
        },
        "expected_provider_submissions": 2,
        "positive_specimens": {
            "ACCRUED_COUPON_COMPONENT": "NOT_MEASURED_NOT_IN_ACTIVE_STORE",
            "SECURITIES_LENDING_INCOME": "NOT_MEASURED_NOT_IN_ACTIVE_STORE",
        },
    }
    plan["plan_sha256"] = _sha256_json(plan)
    _atomic_write(private_root / "frozen_plan.private.json", _json_bytes(plan))
    _atomic_write(private_root / "dictionary.private.json", _json_bytes(dictionary))
    _atomic_write(
        private_root / "dictionary.private.md",
        dictionary_markdown.encode("utf-8"),
    )
    _atomic_write(
        private_root / "instruction.private.txt",
        GATE3_LABELING_INSTRUCTION.encode("utf-8"),
    )
    _atomic_write(
        private_root / "response_schema.private.json",
        _json_bytes(response_schema),
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
                chunk_ordinals=SELECTIONS[label],
            )
        )
        safe_attempts = []
        for outcome in result.outcomes:
            private = _private_outcome(outcome)
            private_bytes = _json_bytes(private)
            _atomic_write(
                private_root
                / label
                / f"chunk-{outcome.chunk['ordinal']:03d}.private.json",
                private_bytes,
            )
            safe = _safe_outcome(
                label=label,
                outcome=outcome,
                private_sha256=hashlib.sha256(private_bytes).hexdigest(),
                dictionary_markdown=dictionary_markdown,
            )
            safe.update(
                _strict_alias_safe_metrics(
                    outcome=outcome,
                    canonical_alias_description=alias_description,
                )
            )
            safe_attempts.append(safe)
            all_safe_attempts.append(safe)
        result_private = {
            "schema_version": "broker_reports_gate3_strict_alias_private_result_v1",
            "document_label": label,
            "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
            "selection_mode": result.selection_mode,
            "document_status": result.document_status,
            "metrics": result.metrics,
            "merged_output": result.merged_output,
        }
        result_bytes = _json_bytes(result_private)
        _atomic_write(
            private_root / label / "batch_result.private.json",
            result_bytes,
        )
        safe_documents[label] = {
            "chunks_available": len(chunk_sets[label]["chunks"]),
            "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
            "selection_mode": result.selection_mode,
            "document_status": result.document_status,
            "provider_submissions": (
                submission_counter["count"] - submissions_before
            ),
            "chunks_validated": result.metrics["chunks_validated"],
            "chunks_rejected": result.metrics["chunks_rejected"],
            "chunks_provider_failed": result.metrics["chunks_provider_failed"],
            "annotations_validated": result.metrics["annotations_validated"],
            "private_batch_result_sha256": hashlib.sha256(
                result_bytes
            ).hexdigest(),
            "attempts": safe_attempts,
        }

    store_after = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.after.private.json",
        _json_bytes(store_after),
    )
    if store_before != store_after:
        raise SystemExit("artifact_store_changed_during_g34d")
    if submission_counter["count"] != 2:
        raise SystemExit("exact_provider_submission_count_not_two")

    compact_raw_count = safe_documents["compact_html"]["attempts"][0][
        "raw_annotation_count"
    ]
    compact_complete = (
        safe_documents["compact_html"]["document_status"] == "complete"
        and safe_documents["compact_html"]["chunks_validated"] == 1
        and isinstance(compact_raw_count, int)
        and compact_raw_count > 0
        and safe_documents["compact_html"]["attempts"][0][
            "raw_aliases_all_exact_chunk_members"
        ]
        is True
    )
    chunk_regression = (
        safe_documents["large_csv_chunk3"]["document_status"]
        == "representative_subset_validated"
        and safe_documents["large_csv_chunk3"]["chunks_validated"] == 1
    )
    strict_alias_contract = bool(
        all(
            item["validation_status"] == "validated"
            and item["provider_alias_description_exact"] is True
            and item["provider_alias_enum_absent"] is True
            and item["raw_aliases_all_exact_chunk_members"] is True
            and item["dictionary_injection_count"] == 1
            and item["provider_schema_version_singleton_enum"] is True
            and item["raw_schema_version_exact"] is True
            for item in all_safe_attempts
        )
        and compact_complete
        and chunk_regression
    )
    receipt = {
        "schema_version": "broker_reports_gate3_strict_alias_safe_receipt_v1",
        "goal": "G3.4D",
        "goal_status": (
            "COMPLETED" if strict_alias_contract else "PARTIALLY_COMPLETED"
        ),
        "strict_alias_contract": (
            "PROVEN" if strict_alias_contract else "NOT_PROVEN"
        ),
        "previously_failed_compact_case": (
            "VALIDATED" if compact_complete else "REJECTED"
        ),
        "live_chunk_regression": "PASS" if chunk_regression else "FAIL",
        "alias_repair_layer": "NONE",
        "alias_authority_count": 1,
        "complete_real_document": (
            "PROVEN" if compact_complete else "NOT_PROVEN"
        ),
        "accrued_coupon_positive": "NOT_MEASURED",
        "securities_lending_positive": "NOT_MEASURED",
        "execution_policy": "two_predeclared_calls_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "frozen_plan_sha256": plan["plan_sha256"],
        "frozen_g34b_module_sha256": FROZEN_G34B_MODULE_SHA256,
        "response_schema_sha256": GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "provider_submissions_total": submission_counter["count"],
        "documents": safe_documents,
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
        "dictionary_injection_counts": sorted(
            {item["dictionary_injection_count"] for item in all_safe_attempts}
        ),
        "provider_alias_description_exact": all(
            item["provider_alias_description_exact"] is True
            for item in all_safe_attempts
        ),
        "provider_alias_enum_absent": all(
            item["provider_alias_enum_absent"] is True
            for item in all_safe_attempts
        ),
        "provider_alias_pattern_visible": all(
            item["provider_alias_pattern_visible"] is True
            for item in all_safe_attempts
        ),
        "raw_aliases_all_exact_chunk_members": all(
            item["raw_aliases_all_exact_chunk_members"] is True
            for item in all_safe_attempts
        ),
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "persistence_writes": 0,
        "artifact_store_tree_byte_identical": True,
        "store_tree_sha256": store_before["tree_sha256"],
        "exact_model_evidence": "AVAILABLE",
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "g3_4_status": (
            "READY_TO_CLOSE" if strict_alias_contract else "NOT_READY"
        ),
        "next_allowed_goal": "G3.5_AFTER_HUMAN_REVIEW",
    }
    _atomic_write(safe_receipt_path, _json_bytes(receipt))
    manifest = _private_manifest(private_root)
    _atomic_write(private_root / "private_manifest.json", _json_bytes(manifest))
    print(
        json.dumps(
            {
                "goal": "G3.4D",
                "provider_submissions": submission_counter["count"],
                "chunks_validated": receipt["chunks_validated"],
                "chunks_rejected": receipt["chunks_rejected"],
                "strict_alias_contract": receipt["strict_alias_contract"],
                "compact": receipt["previously_failed_compact_case"],
                "chunk_regression": receipt["live_chunk_regression"],
                "store_unchanged": True,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _alias_schema(schema: dict[str, Any]) -> dict[str, Any]:
    try:
        alias = schema["$defs"]["annotation"]["properties"]["target_alias"]
    except (KeyError, TypeError) as exc:
        raise SystemExit("strict_alias_schema_path_missing") from exc
    if not isinstance(alias, dict):
        raise SystemExit("strict_alias_schema_path_invalid")
    return alias


def _validate_frozen_shape(
    *,
    label: str,
    chunk_set: dict[str, Any],
    selected: list[dict[str, Any]],
) -> None:
    expected = FROZEN_SAFE_SHAPES[label]
    if len(chunk_set["chunks"]) != expected["available_chunks"] or len(selected) != 1:
        raise SystemExit(f"{label}_frozen_shape_changed")
    chunk = selected[0]
    actual = {
        "ordinal": int(chunk["ordinal"]),
        "structural_kind": chunk["structural_kind"],
        "row_start": chunk["structural_scope"]["row_start"],
        "row_end": chunk["structural_scope"]["row_end"],
        "model_view_chars": chunk["metrics"]["model_view_chars"],
        "target_count": chunk["metrics"]["target_count"],
    }
    if actual != {key: expected[key] for key in actual}:
        raise SystemExit(f"{label}_frozen_shape_changed")


def _strict_alias_safe_metrics(
    *,
    outcome: Any,
    canonical_alias_description: str,
) -> dict[str, Any]:
    attempt = outcome.attempt
    final_request = attempt.final_provider_request if attempt is not None else None
    provider_schema = _provider_schema(final_request)
    provider_alias = (
        _alias_schema(provider_schema)
        if isinstance(provider_schema, dict)
        else {}
    )
    raw = _raw_response_object(
        attempt.raw_model_output if attempt is not None else None
    )
    annotations = raw.get("annotations") if isinstance(raw, dict) else None
    aliases = (
        [item.get("target_alias") for item in annotations]
        if isinstance(annotations, list)
        and all(isinstance(item, dict) for item in annotations)
        else None
    )
    known = {
        mapping["target_alias"] for mapping in outcome.chunk["target_mappings"]
    }
    exact = (
        aliases is not None
        and all(isinstance(alias, str) and alias in known for alias in aliases)
    )
    return {
        "provider_alias_description_exact": (
            provider_alias.get("description") == canonical_alias_description
        ),
        "provider_alias_enum_absent": "enum" not in provider_alias,
        "provider_alias_pattern_visible": "pattern" in provider_alias,
        "provider_alias_schema_keys": sorted(provider_alias),
        "raw_annotation_count": len(aliases) if aliases is not None else None,
        "raw_aliases_all_exact_chunk_members": exact,
        "raw_alias_nonmember_count": (
            sum(alias not in known for alias in aliases)
            if aliases is not None
            else None
        ),
    }


def _raw_response_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
