#!/usr/bin/env python3
"""G3.7A full large-document proof over the final strict Gate 3 contract."""

from __future__ import annotations

import argparse
import asyncio
import copy
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
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3FinancialLabelDictionaryFactory,
    Gate3NdflCaseReadinessFactory,
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
    _read_env,
    _safe_outcome,
    _sha256_json,
    _signin,
    _store_tree_snapshot,
    _url,
)
from live_gate3_strict_alias_closeout import (  # noqa: E402
    _alias_schema,
    _strict_alias_safe_metrics,
)


FACTORY_REQUIRED = (
    "Gate3ChunkBatchLabelingFactory.create and "
    "Gate3FinancialAnnotationsPersistenceFactory.create are the only G3.7A "
    "label/merge and persistence routes"
)
FORBIDDEN = (
    "G3.7A must not change chunking, dictionary, instruction, aliases, "
    "validator, provider routing, merge or persistence; semantic retry, "
    "repair and fallback are forbidden"
)
DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
DOCUMENT_ID = "brdoc_003_be6168a763cd"
EXPECTED_CHUNKS = 6
EXPECTED_ALIASES = 14118
MAX_AVAILABILITY_CHECKS = 3
FROZEN_G34B_MODULE_SHA256 = (
    "203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba"
)
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "normrun_046152421c699e38",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the explicitly authorized G3.7A six-chunk proof."
    )
    parser.add_argument("--execute-full-large-document-proof", action="store_true")
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
            / "broker-reports-g3.7a-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_FULL_LARGE_DOCUMENT_G3_7A.receipt.safe.json"
        ),
    )
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    if not args.execute_full_large_document_proof:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")
    _assert_frozen_contract()

    private_root = Path(args.private_evidence_dir).resolve()
    receipt_path = Path(args.safe_receipt_path).resolve()
    store_root = Path(args.store_root).resolve()
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if receipt_path.exists():
        raise SystemExit("safe_receipt_path_must_be_new")
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
    canonical_before = reader.read_active_envelope(DOCUMENT_ID, context)
    store_before = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.before.private.json",
        _json_bytes(store_before),
    )

    chunk_set = Gate3StructuralChunkFactory(
        store=store, read_enabled=True
    ).create(document_id=DOCUMENT_ID, context=context)
    chunks = list(chunk_set["chunks"])
    ordinals = [int(chunk["ordinal"]) for chunk in chunks]
    if (
        len(chunks) != EXPECTED_CHUNKS
        or ordinals != list(range(1, EXPECTED_CHUNKS + 1))
        or sum(int(chunk["metrics"]["target_count"]) for chunk in chunks)
        != EXPECTED_ALIASES
        or any(
            int(chunk["metrics"]["model_view_chars"])
            > DEFAULT_MAX_CHUNK_CHARS
            for chunk in chunks
        )
        or any(
            chunk["canonical_binding"] != chunk_set["canonical_binding"]
            for chunk in chunks
        )
    ):
        raise SystemExit("frozen_large_document_shape_changed")
    _atomic_write(
        private_root / "selected_chunks.private.json",
        _json_bytes(chunks),
    )

    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published("1.0.0")
    dictionary_markdown = dictionary_owner.render_model_markdown("1.0.0")
    response_schema = _load_response_schema()
    alias_schema = _alias_schema(response_schema)
    plan = {
        "schema_version": "broker_reports_gate3_full_large_document_plan_v1",
        "goal": "G3.7A",
        "execution_policy": "all_six_chunks_once_no_retry_no_repair",
        "document_id": DOCUMENT_ID,
        "canonical_binding": copy.deepcopy(chunk_set["canonical_binding"]),
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "max_availability_checks": MAX_AVAILABILITY_CHECKS,
        "max_provider_submissions_per_chunk": 1,
        "expected_provider_submissions": EXPECTED_CHUNKS,
        "chunk_ordinals": ordinals,
        "chunks": [_chunk_plan_descriptor(chunk) for chunk in chunks],
        "frozen_g34b_module_sha256": FROZEN_G34B_MODULE_SHA256,
        "max_chunk_chars": DEFAULT_MAX_CHUNK_CHARS,
        "dictionary_version": "1.0.0",
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_LABELING_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "response_schema_sha256": GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
        "alias_pattern": alias_schema["pattern"],
        "alias_description": alias_schema["description"],
    }
    plan["plan_sha256"] = _sha256_json(plan)
    _atomic_write(private_root / "frozen_plan.private.json", _json_bytes(plan))
    _atomic_write(private_root / "dictionary.private.json", _json_bytes(dictionary))
    _atomic_write(
        private_root / "dictionary.private.md", dictionary_markdown.encode("utf-8")
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
    availability_checks = 0
    model_available = False
    for check in range(1, MAX_AVAILABILITY_CHECKS + 1):
        availability_checks = check
        if args.model_id in _published_model_ids(session, base_url):
            model_available = True
            break
        if check < MAX_AVAILABILITY_CHECKS:
            time.sleep(2)
    if not model_available:
        receipt = _base_receipt(
            args=args,
            plan=plan,
            availability_checks=availability_checks,
            goal_status="BLOCKED_EXTERNAL",
            acceptance="FAIL",
        )
        receipt["terminal_error"] = "exact_model_not_published"
        _seal_evidence(private_root, receipt_path, receipt)
        return 2

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
    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=args.model_id,
        ).create(document_id=DOCUMENT_ID, context=context)
    )

    safe_attempts = []
    for outcome in result.outcomes:
        private = _private_outcome(outcome)
        private_bytes = _json_bytes(private)
        _atomic_write(
            private_root / f"chunk-{outcome.chunk['ordinal']:03d}.private.json",
            private_bytes,
        )
        safe = _safe_outcome(
            label="large_csv_full",
            outcome=outcome,
            private_sha256=hashlib.sha256(private_bytes).hexdigest(),
            dictionary_markdown=dictionary_markdown,
        )
        safe.update(
            _strict_alias_safe_metrics(
                outcome=outcome,
                canonical_alias_description=alias_schema["description"],
            )
        )
        safe_attempts.append(safe)

    batch_private = {
        "schema_version": "broker_reports_gate3_full_large_private_result_v1",
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": result.metrics,
        "merged_output": result.merged_output,
    }
    batch_bytes = _json_bytes(batch_private)
    _atomic_write(private_root / "batch_result.private.json", batch_bytes)
    labeling_pass = bool(
        submission_counter["count"] == EXPECTED_CHUNKS
        and len(result.outcomes) == EXPECTED_CHUNKS
        and result.selected_chunk_ordinals == tuple(ordinals)
        and result.selection_mode == "full_document"
        and result.document_status == "complete"
        and result.metrics["chunks_validated"] == EXPECTED_CHUNKS
        and result.metrics["chunks_rejected"] == 0
        and result.metrics["chunks_provider_failed"] == 0
        and result.merged_output is not None
        and all(
            item["validation_status"] == "validated"
            and item["dictionary_injection_count"] == 1
            and item["raw_aliases_all_exact_chunk_members"] is True
            and item["provider_alias_description_exact"] is True
            and item["provider_alias_enum_absent"] is True
            and item["raw_schema_version_exact"] is True
            for item in safe_attempts
        )
    )
    receipt = _base_receipt(
        args=args,
        plan=plan,
        availability_checks=availability_checks,
        goal_status="COMPLETED" if labeling_pass else "FAILED",
        acceptance="PASS" if labeling_pass else "FAIL",
    )
    receipt.update(
        {
            "provider_submissions": submission_counter["count"],
            "chunks_total": result.metrics["chunks_total"],
            "chunks_validated": result.metrics["chunks_validated"],
            "chunks_rejected": result.metrics["chunks_rejected"],
            "chunks_provider_failed": result.metrics["chunks_provider_failed"],
            "chunk_attempts": safe_attempts,
            "input_tokens_per_chunk": [
                item["input_tokens"] for item in safe_attempts
            ],
            "peak_input_tokens": result.metrics["input_tokens_max"],
            "total_input_tokens": result.metrics["input_tokens_total"],
            "output_tokens_per_chunk": [
                item["output_tokens"] for item in safe_attempts
            ],
            "output_tokens_total": result.metrics["output_tokens_total"],
            "duration_ms_per_chunk": [
                item["duration_ms"] for item in safe_attempts
            ],
            "duration_ms_total": result.metrics["duration_ms_total"],
            "annotations_total": result.metrics["annotations_validated"],
            "batch_result_sha256": hashlib.sha256(batch_bytes).hexdigest(),
            "dictionary_injection_once_per_request": all(
                item["dictionary_injection_count"] == 1
                for item in safe_attempts
            ),
            "bare_aliases_only": all(
                item["raw_aliases_all_exact_chunk_members"] is True
                for item in safe_attempts
            ),
            "zero_cross_document_content": all(
                outcome.chunk["canonical_binding"]
                == chunk_set["canonical_binding"]
                for outcome in result.outcomes
            ),
            "document_status": result.document_status,
            "persistence": "NOT_RUN",
            "read_back_exact": False,
        }
    )
    if not labeling_pass:
        store_after = _store_tree_snapshot(store_root)
        receipt["artifact_store_unchanged_without_complete_result"] = (
            store_before == store_after
        )
        _atomic_write(
            private_root / "store_tree.after.private.json",
            _json_bytes(store_after),
        )
        _seal_evidence(private_root, receipt_path, receipt)
        return 1

    document_result = {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": copy.deepcopy(result.metrics),
        "merged_output": copy.deepcopy(result.merged_output),
    }
    persistence = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    stored = persistence.save(
        document_id=DOCUMENT_ID,
        context=context,
        validated_document_result=document_result,
        provider_profile_id=args.provider_profile_id,
    )
    read_back = persistence.read(artifact_id=stored.artifact_id, context=context)
    canonical_after = reader.read_active_envelope(DOCUMENT_ID, context)
    read_back_exact = read_back == result.merged_output
    canonical_unchanged = bool(
        canonical_after.canonical_version_id
        == canonical_before.canonical_version_id
        and canonical_after.canonical_root_sha256
        == canonical_before.canonical_root_sha256
    )
    binding_exact = bool(
        read_back["canonical_binding"] == chunk_set["canonical_binding"]
    )
    dictionary_exact = read_back["dictionary_identity"] == {
        "dictionary_id": "broker-reports-financial-labels",
        "semantic_version": "1.0.0",
    }
    persistence_pass = bool(
        read_back_exact
        and canonical_unchanged
        and binding_exact
        and dictionary_exact
    )
    _atomic_write(
        private_root / "stored_sidecar.private.json",
        _json_bytes(
            {
                "artifact_id": stored.artifact_id,
                "record": {
                    "artifact_type": stored.artifact_type,
                    "document_id": stored.document_id,
                    "normalization_run_id": stored.normalization_run_id,
                    "retention_policy": stored.retention_policy.to_dict(),
                    "safe_metadata": stored.safe_metadata,
                },
                "payload": read_back,
            }
        ),
    )
    readiness = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)
    store_after = _store_tree_snapshot(store_root)
    _atomic_write(
        private_root / "store_tree.after.private.json",
        _json_bytes(store_after),
    )
    receipt.update(
        {
            "goal_status": "COMPLETED" if persistence_pass else "FAILED",
            "acceptance": "PASS" if persistence_pass else "FAIL",
            "deterministic_merge": "PASS_BY_EXISTING_OWNER_AND_REGRESSION",
            "persistence": "PASS" if persistence_pass else "FAIL",
            "read_back_exact": read_back_exact,
            "canonical_binding_exact": binding_exact,
            "dictionary_binding_exact": dictionary_exact,
            "gate2_unchanged": canonical_unchanged,
            "stored_payload_sha256": hashlib.sha256(
                _json_bytes(read_back)
            ).hexdigest(),
            "artifact_id_sha256": hashlib.sha256(
                stored.artifact_id.encode("utf-8")
            ).hexdigest(),
            "current_case_status": readiness["case_status"],
            "current_case_documents_total": readiness["summary"][
                "documents_total"
            ],
            "current_case_gate3_ready_documents": readiness["summary"][
                "gate3_ready_documents"
            ],
            "next_allowed_goal": "G3.7B" if persistence_pass else "NONE",
        }
    )
    _seal_evidence(private_root, receipt_path, receipt)
    print(
        json.dumps(
            {
                "goal": "G3.7A",
                "acceptance": receipt["acceptance"],
                "chunks_validated": receipt["chunks_validated"],
                "provider_submissions": receipt["provider_submissions"],
                "annotations_total": receipt["annotations_total"],
                "persistence": receipt["persistence"],
                "read_back_exact": receipt["read_back_exact"],
                "gate2_unchanged": receipt["gate2_unchanged"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0 if persistence_pass else 1


def _assert_frozen_contract() -> None:
    if DEFAULT_MAX_CHUNK_CHARS != 60_000:
        raise SystemExit("frozen_g34b_budget_changed")
    if _file_sha256(
        SERVICE_ROOT / "broker_reports_gate1" / "gate3_structural_chunking.py"
    ) != FROZEN_G34B_MODULE_SHA256:
        raise SystemExit("frozen_g34b_module_changed")
    if GATE3_LABELING_INSTRUCTION_VERSION != "1.0.1":
        raise SystemExit("strict_alias_instruction_version_changed")
    schema = _load_response_schema()
    alias = _alias_schema(schema)
    if (
        alias.get("type") != "string"
        or alias.get("pattern") != "^t[0-9]{3,}$"
        or "[t123]" not in str(alias.get("description") or "")
        or "enum" in alias
    ):
        raise SystemExit("strict_alias_contract_changed")


def _base_receipt(
    *,
    args: Any,
    plan: dict[str, Any],
    availability_checks: int,
    goal_status: str,
    acceptance: str,
) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_gate3_full_large_document_receipt_v1",
        "goal": "G3.7A",
        "goal_status": goal_status,
        "acceptance": acceptance,
        "execution_policy": "all_six_chunks_once_no_retry_no_repair",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "availability_checks_used": availability_checks,
        "max_availability_checks": MAX_AVAILABILITY_CHECKS,
        "max_provider_submissions_per_chunk": 1,
        "frozen_plan_sha256": plan["plan_sha256"],
        "frozen_g34b_module_sha256": FROZEN_G34B_MODULE_SHA256,
        "dictionary_version": "1.0.0",
        "instruction_version": GATE3_LABELING_INSTRUCTION_VERSION,
        "response_schema_sha256": GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "next_allowed_goal": "NONE",
    }


def _seal_evidence(
    private_root: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
) -> None:
    _atomic_write(receipt_path, _json_bytes(receipt))
    manifest = _private_manifest(private_root)
    manifest["schema_version"] = (
        "broker_reports_gate3_full_large_document_private_manifest_v1"
    )
    manifest["goal"] = "G3.7A"
    _atomic_write(private_root / "private_manifest.json", _json_bytes(manifest))


if __name__ == "__main__":
    raise SystemExit(main())
