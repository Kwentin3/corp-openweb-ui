#!/usr/bin/env python3
"""Replay one visually qualified table through the ordinary Gate 3 role path."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
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
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialLabelDictionaryFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3RoleLabelingFactory,
    Gate3StructuralChunkFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
    GATE3_LABELING_INSTRUCTION,
    GATE3_LABELING_INSTRUCTION_ID,
    GATE3_LABELING_INSTRUCTION_VERSION,
    Gate3BoundedLabelingAttempt,
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
from broker_reports_gate1.gate5_trusted_methodology import (  # noqa: E402
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _base_url,
    _is_within,
    _json_bytes,
    _private_outcome,
    _read_env,
    _signin,
    _store_tree_snapshot,
    _url,
)


FACTORY_REQUIRED = (
    "Gate3StructuralChunkFactory.create, "
    "Gate3RoleLabelingFactory.create_from_chunk, "
    "Gate3ChunkBatchLabelingFactory.create, "
    "Gate3FinancialAnnotationsPersistenceFactory.create, "
    "Gate4FinancialCaseRuntimeFactory.create and "
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create are the "
    "only replay route"
)
FORBIDDEN = (
    "No retry, best-of-N, semantic repair, manual role replacement, value-based "
    "column choice, baseline type rediscovery, cross-authority merge, direct "
    "production-store mutation or Gate 4/Gate 5 role logic"
)
PROVIDER_PROFILE_ID = "google_gemini"
MODEL_ID = "models/gemini-3.5-flash"
EXPECTED_ROLE_COLUMNS = {
    "date": 4,
    "asset": 10,
    "quantity": 13,
    "amount": 16,
    "currency": 17,
    "unit_price": 11,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-one-clean-replay", action="store_true")
    parser.add_argument("--source-store-root", type=Path, required=True)
    parser.add_argument("--prior-downstream-result", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_one_clean_replay:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")

    source_store = args.source_store_root.resolve()
    output_root = args.private_output_root.resolve()
    working_store = output_root / "working-store"
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    if output_root.exists():
        raise SystemExit("private_output_root_must_be_new")
    if not (source_store / "artifacts.sqlite3").is_file():
        raise SystemExit("source_store_missing")
    gate2_provider_profile(PROVIDER_PROFILE_ID)

    source_before = _store_tree_snapshot(source_store)
    shutil.copytree(source_store, working_store)
    prior = _read_json(args.prior_downstream_result)
    old_sidecar_id = _required_text(prior, "old_sidecar_artifact_id")
    destructive_sidecar_id = _required_text(prior, "new_sidecar_artifact_id")
    with sqlite3.connect(working_store / "artifacts.sqlite3") as connection:
        cursor = connection.execute(
            """
            UPDATE artifact_records
               SET validation_status = 'blocked', lifecycle_status = 'blocked'
             WHERE artifact_id = ?
            """,
            (destructive_sidecar_id,),
        )
        if cursor.rowcount != 1:
            raise SystemExit("destructive_proof_sidecar_not_found")
        connection.commit()

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=working_store / "artifacts.sqlite3",
            payload_root=working_store / "payloads",
        )
    ).create()
    old_record = store.get_record_unchecked(old_sidecar_id)
    if old_record is None or not old_record.document_id:
        raise SystemExit("old_full_sidecar_not_found")
    if old_record.safe_metadata.get("provider_profile_id") != PROVIDER_PROFILE_ID:
        raise SystemExit("provider_profile_mismatch")
    context = ArtifactAccessContext(
        user_id=old_record.user_id,
        normalization_run_id=old_record.normalization_run_id,
        case_id=old_record.case_id,
        chat_id=old_record.chat_id,
        workspace_model_id=old_record.workspace_model_id,
        allow_private=True,
    )

    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return base_completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
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
        model_id=MODEL_ID,
    )
    persistence = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    old_payload = persistence.read(
        artifact_id=old_sidecar_id,
        context=context,
    )
    chunk_set = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
    ).create(
        document_id=old_record.document_id,
        context=context,
    )
    chunks = list(chunk_set.get("chunks") or [])
    if len(chunks) != 1:
        raise SystemExit("accepted_fact_role_replay_requires_one_chunk")
    chunk = chunks[0]
    accepted_attempt = _accepted_fact_attempt_from_sidecar(
        base_payload=old_payload,
        chunk=chunk,
        model_id=MODEL_ID,
    )
    full_role_attempt = asyncio.run(
        Gate3RoleLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=MODEL_ID,
        ).create_from_chunk(
            chunk=chunk,
            context=context,
            pass1_attempt=accepted_attempt,
        )
    )
    full_output = full_role_attempt.validated_output
    full_annotations = (
        full_output["annotations"] if isinstance(full_output, dict) else []
    )
    full_counts = Counter(item["financial_label"] for item in full_annotations)
    if (
        submissions["count"] != 1
        or full_role_attempt.execution_status != "validated"
        or full_role_attempt.validation_error_code is not None
        or len(full_annotations) != 21
        or full_counts["SECURITY_PURCHASE"] != 5
        or full_counts["TRANSACTION_CHARGE"] != 15
        or full_counts["COMMISSION"] != 1
        or not _same_accepted_fact_set(old_payload, full_output)
        or not _source_first_row_context_proven(
            SimpleNamespace(chunk=chunk, role_attempt=full_role_attempt)
        )
    ):
        _write_private_role_failure(
            output_root,
            chunk,
            full_role_attempt,
            submissions["count"],
        )
        raise SystemExit("accepted_fact_role_replay_not_validated")
    full_role_columns = [
        _role_columns(annotation)
        for annotation in full_annotations
        if annotation["financial_label"] == "SECURITY_PURCHASE"
    ]
    if any(columns != EXPECTED_ROLE_COLUMNS for columns in full_role_columns):
        _write_private_role_failure(
            output_root,
            chunk,
            full_role_attempt,
            submissions["count"],
        )
        raise SystemExit("full_source_truth_role_columns_not_proven")

    records_before_baseline = len(store.list_by_run(context.normalization_run_id))
    full_record = persistence.save(
        document_id=old_record.document_id,
        context=context,
        validated_document_result=_role_only_document_result(
            document_id=old_record.document_id,
            chunk_ordinal=int(chunk["ordinal"]),
            merged_output=full_output,
        ),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    records_after_baseline = len(store.list_by_run(context.normalization_run_id))
    full_payload = persistence.read(
        artifact_id=full_record.artifact_id,
        context=context,
    )

    result = asyncio.run(
        batch_factory.create(
            document_id=old_record.document_id,
            context=context,
            requested_financial_labels=("SECURITY_PURCHASE",),
        )
    )
    if (
        submissions["count"] != 3
        or result.document_status != "complete"
        or len(result.outcomes) != 1
        or result.outcomes[0].terminal_status != "validated"
        or result.merged_output is None
    ):
        raise SystemExit("ordinary_role_replay_not_validated")

    annotations = result.merged_output["annotations"]
    if len(annotations) != 5:
        raise SystemExit("purchase_count_invalid")
    role_columns = [_role_columns(annotation) for annotation in annotations]
    if any(columns != EXPECTED_ROLE_COLUMNS for columns in role_columns):
        _write_private_result(
            output_root,
            result,
            role_columns,
            chunk,
            full_role_attempt,
        )
        raise SystemExit("source_truth_role_columns_not_proven")
    private_bytes = _write_private_result(
        output_root,
        result,
        role_columns,
        chunk,
        full_role_attempt,
    )
    if not _source_first_row_context_proven(result.outcomes[0]):
        raise SystemExit("source_first_row_context_missing")

    base_payload = full_payload
    records_before_recovery = len(store.list_by_run(context.normalization_run_id))
    recovered = persistence.save_recovery(
        document_id=old_record.document_id,
        context=context,
        validated_document_result=_document_result(result),
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=full_record.artifact_id,
        demand_request_id="g557_source_truth_role_mapping",
    )
    records_after_recovery = len(store.list_by_run(context.normalization_run_id))
    payload = persistence.read(
        artifact_id=recovered.record.artifact_id, context=context
    )
    counts = Counter(item["financial_label"] for item in payload["annotations"])
    gate4 = (
        Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True)
        .create()
        .rebuild_case(context=context)
    )
    document_facts = [
        fact
        for fact in gate4.facts
        if fact["gate3_binding"]["canonical_binding"]["document_id"]
        == old_record.document_id
    ]
    gate4_purchases = [
        fact
        for fact in document_facts
        if fact.get("financial_type") == "SECURITY_PURCHASE"
    ]
    gate4_role_columns = [_gate4_role_columns(fact) for fact in gate4_purchases]
    gate5 = (
        Gate5DeterministicSourceFactConsumptionRuntimeFactory(
            store=store, read_enabled=True
        )
        .create()
        .assess(
            methodology_ref={
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
                ),
            },
            context=context,
        )
    )
    source_unchanged = _store_tree_snapshot(source_store) == source_before
    replay = {
        "annotations": len(payload["annotations"]),
        "purchases": counts["SECURITY_PURCHASE"],
        "unrelated": counts["COMMISSION"] + counts["TRANSACTION_CHARGE"],
        "gate4_document_facts": len(document_facts),
        "gate4_purchase_facts": len(gate4_purchases),
        "gate5_security_facts": gate5["security_fact_counts"]["total"],
    }
    if (
        replay
        != {
            "annotations": 21,
            "purchases": 5,
            "unrelated": 16,
            "gate4_document_facts": 21,
            "gate4_purchase_facts": 5,
            "gate5_security_facts": 48,
        }
        or not source_unchanged
        or recovered.receipt["added_total"] != 0
        or recovered.receipt["superseded_total"] != 5
        or recovered.receipt["preserved_unrelated_total"] != 16
        or recovered.receipt["deleted_total"] != 0
        or any(columns != EXPECTED_ROLE_COLUMNS for columns in gate4_role_columns)
        or any(
            (fact.get("semantic_binding") or {})
            .get("role_pack", {})
            .get("semantic_version")
            != "3.0.0"
            for fact in gate4_purchases
        )
        or store.get_record_unchecked(old_sidecar_id) is None
        or store.get_record_unchecked(destructive_sidecar_id) is None
        or records_after_baseline - records_before_baseline != 1
        or records_after_recovery - records_before_recovery != 1
        or len(base_payload["annotations"]) != 21
    ):
        raise SystemExit("non_destructive_source_truth_replay_failed")

    safe = {
        "schema_version": "broker_reports_g557_role_mapping_replay_receipt_v1",
        "provider_calls": submissions["count"],
        "provider_batches": 2,
        "accepted_fact_role_replay_calls": 1,
        "demand_scoped_batch_calls": 2,
        "baseline_type_rediscovery_calls": 0,
        "retry_calls": 0,
        "source_store_unchanged": source_unchanged,
        "private_result_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "source_first_row_context_present": True,
        "source_first_row_targets_selectable": False,
        "financial_values_used_for_column_choice": False,
        "purchase_rows": 5,
        "all_required_role_columns_proven": True,
        "role_columns": EXPECTED_ROLE_COLUMNS,
        "full_authority_baseline_annotations": len(full_payload["annotations"]),
        "full_authority_baseline_purchases": full_counts["SECURITY_PURCHASE"],
        "full_authority_baseline_unrelated": (
            full_counts["TRANSACTION_CHARGE"] + full_counts["COMMISSION"]
        ),
        "accepted_fact_set_unchanged": True,
        "full_authority_baseline_added": 1,
        "annotations_before": len(base_payload["annotations"]),
        "annotations_after": replay["annotations"],
        "purchases_after": replay["purchases"],
        "unrelated_after": replay["unrelated"],
        "added_total": recovered.receipt["added_total"],
        "superseded_total": recovered.receipt["superseded_total"],
        "preserved_unrelated_total": recovered.receipt["preserved_unrelated_total"],
        "deleted_total": recovered.receipt["deleted_total"],
        "gate4_document_facts": replay["gate4_document_facts"],
        "gate4_purchase_facts": replay["gate4_purchase_facts"],
        "gate4_purchase_role_columns_proven": True,
        "gate4_purchase_role_pack_version": "3.0.0",
        "gate4_status": gate4.status,
        "gate5_security_facts": replay["gate5_security_facts"],
        "gate5_terminals": gate5["terminals"],
        "stored_financial_event_relations": gate5["stored_financial_event_relations"],
    }
    _atomic_write(output_root / "receipt.safe.json", _json_bytes(safe))
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0


def _role_columns(annotation: dict[str, Any]) -> dict[str, int]:
    if annotation.get("financial_label") != "SECURITY_PURCHASE" or (
        annotation.get("target") or {}
    ).get("kind") not in {"table_row", "table_cell"}:
        return {}
    result = {}
    for binding in annotation.get("roles") or []:
        target = binding.get("target") or {}
        if binding.get("status") != "bound" or target.get("kind") != "table_cell":
            return {}
        result[str(binding.get("role") or "")] = int(target.get("column") or 0)
    return result


def _gate4_role_columns(fact: dict[str, Any]) -> dict[str, int]:
    result = {}
    roles = fact.get("roles")
    if not isinstance(roles, list):
        return result
    for binding in roles:
        source_binding = binding.get("source_binding") or {}
        target = source_binding.get("target") or {}
        if binding.get("status") != "value" or target.get("kind") != "table_cell":
            return {}
        result[str(binding.get("role") or "")] = int(target.get("column") or 0)
    return result


def _source_first_row_context_proven(outcome: Any) -> bool:
    role_attempt = outcome.role_attempt
    if role_attempt is None:
        return False
    chunk = outcome.chunk
    row_one_aliases = {
        mapping["target_alias"]
        for mapping in chunk["target_mappings"]
        if (mapping.get("canonical_target") or {}).get("kind")
        in {"table_row", "table_cell"}
        and (mapping.get("canonical_target") or {}).get("row") == 1
    }
    source_lines = [
        line
        for line in chunk["model_view"]["content"].splitlines()
        if any(f"[{alias}]" in line for alias in row_one_aliases)
    ]
    context = role_attempt.role_context
    context_aliases = {
        mapping["target_alias"] for mapping in context["target_mappings"]
    }
    return bool(
        source_lines
        and any(
            re.sub(r"(?<!\\)\[t[0-9]{3,}\]", "", line)
            in context["model_view"]["content"]
            for line in source_lines
        )
        and row_one_aliases.isdisjoint(context_aliases)
        and not any(
            f"[{alias}]" in context["model_view"]["content"]
            for alias in row_one_aliases
        )
    )


def _write_private_result(
    output_root: Path,
    result: Any,
    role_columns: Any,
    full_chunk: dict[str, Any],
    full_role_attempt: Any,
) -> bytes:
    value = {
        "schema_version": "broker_reports_g557_private_role_mapping_replay_v1",
        "full_authority_role_replay": _private_role_attempt(
            full_chunk,
            full_role_attempt,
        ),
        "result": {
            "chunk_set": result.chunk_set,
            "outcomes": [_private_outcome(item) for item in result.outcomes],
            "merged_output": result.merged_output,
            "semantic_scope": result.semantic_scope,
            "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
            "selection_mode": result.selection_mode,
            "document_status": result.document_status,
            "metrics": result.metrics,
        },
        "role_context": copy.deepcopy(result.outcomes[0].role_attempt.role_context),
        "role_columns": role_columns,
    }
    data = _json_bytes(value)
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(output_root / "result.private.json", data)
    return data


def _write_private_role_failure(
    output_root: Path,
    chunk: dict[str, Any],
    role_attempt: Any,
    provider_calls: int,
) -> None:
    value = {
        "schema_version": "broker_reports_g557_private_role_replay_failure_v1",
        "provider_calls": provider_calls,
        "role_replay": _private_role_attempt(chunk, role_attempt),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(output_root / "role-failure.private.json", _json_bytes(value))


def _private_role_attempt(
    chunk: dict[str, Any],
    attempt: Any,
) -> dict[str, Any]:
    return {
        "chunk": copy.deepcopy(chunk),
        "role_context": copy.deepcopy(attempt.role_context),
        "role_provenance": copy.deepcopy(attempt.role_provenance),
        "pass1_output": copy.deepcopy(attempt.pass1_output),
        "facts": copy.deepcopy(attempt.facts),
        "role_pack": copy.deepcopy(attempt.role_pack),
        "role_pack_markdown": attempt.role_pack_markdown,
        "instruction": attempt.instruction,
        "model_visible_request": copy.deepcopy(attempt.model_visible_request),
        "final_provider_request": copy.deepcopy(attempt.final_provider_request),
        "raw_provider_response": copy.deepcopy(attempt.raw_provider_response),
        "raw_model_output": copy.deepcopy(attempt.raw_model_output),
        "validated_output": copy.deepcopy(attempt.validated_output),
        "execution_status": attempt.execution_status,
        "validation_error_code": attempt.validation_error_code,
        "execution_metadata": copy.deepcopy(attempt.execution_metadata),
        "metrics": copy.deepcopy(attempt.metrics),
    }


def _document_result(result: Any) -> dict[str, Any]:
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": copy.deepcopy(result.semantic_scope),
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": copy.deepcopy(result.metrics),
        "merged_output": copy.deepcopy(result.merged_output),
    }


def _role_only_document_result(
    *,
    document_id: str,
    chunk_ordinal: int,
    merged_output: dict[str, Any],
) -> dict[str, Any]:
    annotations_total = len(merged_output["annotations"])
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": {
            "publication_mode": "FULL",
            "document_id": document_id,
            "requested_financial_labels": [],
            "requested_roles": [],
            "selected_chunk_ordinals": [chunk_ordinal],
        },
        "selected_chunk_ordinals": [chunk_ordinal],
        "selection_mode": "full_document",
        "document_status": "complete",
        "metrics": {
            "chunks_total": 1,
            "chunks_validated": 1,
            "chunks_rejected": 0,
            "chunks_provider_failed": 0,
            "annotations_validated": annotations_total,
            "financial_labeling_provider_calls": 0,
            "role_labeling_provider_calls": 1,
            "role_labeling_skipped_empty_chunks": 0,
        },
        "merged_output": copy.deepcopy(merged_output),
    }


def _accepted_fact_attempt_from_sidecar(
    *,
    base_payload: dict[str, Any],
    chunk: dict[str, Any],
    model_id: str,
) -> Gate3BoundedLabelingAttempt:
    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published()
    expected_dictionary_identity = {
        "dictionary_id": dictionary["dictionary_id"],
        "semantic_version": dictionary["semantic_version"],
    }
    if (
        base_payload.get("validation_status") != "validated"
        or base_payload.get("canonical_binding") != chunk.get("canonical_binding")
        or base_payload.get("dictionary_identity") != expected_dictionary_identity
        or base_payload.get("instruction_identity")
        != {
            "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
        }
        or base_payload.get("model_identity") != {"model_id": model_id}
        or base_payload.get("role_pack_identity")
        != {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": "2.0.0",
        }
    ):
        raise SystemExit("accepted_fact_base_authority_invalid")
    mappings = list(chunk.get("target_mappings") or [])
    known_targets = {
        _stable_json(mapping["canonical_target"])
        for mapping in mappings
        if isinstance(mapping, dict)
        and isinstance(mapping.get("canonical_target"), dict)
    }
    accepted: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for annotation in base_payload.get("annotations") or []:
        if (
            not isinstance(annotation, dict)
            or set(annotation) != {"target", "financial_label", "roles"}
            or not isinstance(annotation.get("target"), dict)
            or not isinstance(annotation.get("financial_label"), str)
        ):
            raise SystemExit("accepted_fact_base_contract_invalid")
        target_key = _stable_json(annotation["target"])
        pair = (target_key, annotation["financial_label"])
        if target_key not in known_targets or pair in seen:
            raise SystemExit("accepted_fact_base_target_invalid")
        seen.add(pair)
        accepted.append(
            {
                "target": copy.deepcopy(annotation["target"]),
                "financial_label": annotation["financial_label"],
            }
        )
    if not accepted:
        raise SystemExit("accepted_fact_base_empty")
    projection = {
        "schema_version": "broker_reports_gate3_projection_v1",
        "canonical_binding": copy.deepcopy(chunk["canonical_binding"]),
        "model_view": copy.deepcopy(chunk["model_view"]),
        "target_mappings": copy.deepcopy(mappings),
    }
    validated_output = {
        "schema_version": FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(chunk["canonical_binding"]),
        "dictionary_identity": expected_dictionary_identity,
        "instruction_identity": {
            "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
        },
        "model_identity": {"model_id": model_id},
        "annotations": accepted,
        "validation_status": "validated",
    }
    return Gate3BoundedLabelingAttempt(
        projection=projection,
        dictionary=copy.deepcopy(dictionary),
        dictionary_managed_binding=dictionary_owner.managed_binding(),
        dictionary_markdown=dictionary_owner.render_model_markdown(),
        instruction=GATE3_LABELING_INSTRUCTION,
        model_visible_request={},
        final_provider_request={},
        raw_provider_response={},
        raw_model_output=None,
        validated_output=validated_output,
        validation_status="validated",
        validation_error_code=None,
        execution_metadata=None,
        operational_retry_receipt=None,
        metrics={
            "accepted_facts_total": len(accepted),
            "provider_called": False,
            "source": "immutable_validated_sidecar",
        },
    )


def _same_accepted_fact_set(
    base_payload: dict[str, Any],
    replay_output: dict[str, Any] | None,
) -> bool:
    if not isinstance(replay_output, dict):
        return False
    before = [
        (_stable_json(item["target"]), item["financial_label"])
        for item in base_payload.get("annotations") or []
    ]
    after = [
        (_stable_json(item["target"]), item["financial_label"])
        for item in replay_output.get("annotations") or []
    ]
    return before == after


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("json_object_required")
    return value


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise SystemExit(f"{key}_required")
    return item


if __name__ == "__main__":
    raise SystemExit(main())
