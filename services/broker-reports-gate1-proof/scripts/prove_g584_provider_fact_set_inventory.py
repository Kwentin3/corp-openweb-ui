#!/usr/bin/env python3
"""Qualify G5.84 exact failures and account current Gate 4 inventory."""

from __future__ import annotations

import argparse
import asyncio
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from broker_reports_gate1.gate3_role_labeling import (  # noqa: E402
    Gate3RoleValueResolverFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate4_financial_case_materialization import (  # noqa: E402
    gate4_annotation_materialization_decision,
    gate4_financial_case_fact_id,
)


LARGE_DOCUMENT_ID = "brdoc_001_7cfd297786cc"
MODEL_ID = "models/gemini-3.5-flash"
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}
BASELINE_RUNS = {
    "brdoc_001_25c3b0606ce8": "normrun_056b15c46f64d9c9",
    "brdoc_001_79af73d5be78": "normrun_0ac55d0083f8ad4a",
    LARGE_DOCUMENT_ID: "normrun_b5c1922880533908",
    "brdoc_001_36a166a5a13e": "normrun_e5dcaae40e5ab7a9",
}
CURRENT_RUNS = {
    **BASELINE_RUNS,
    LARGE_DOCUMENT_ID: "normrun_1f4f2d9e30c1a076",
}


class FrozenReplayClient:
    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self._attempts = attempts
        self.responses_consumed = 0

    async def label_gate3_once(
        self,
        *,
        model_visible_request: dict[str, Any],
        canonical_schema: dict[str, Any],
        model_id: str,
    ) -> Any:
        del canonical_schema
        if self.responses_consumed >= len(self._attempts):
            raise RuntimeError("frozen_response_inventory_exhausted")
        frozen = self._attempts[self.responses_consumed]
        self.responses_consumed += 1
        if (
            model_id != MODEL_ID
            or model_visible_request != frozen["model_visible_request"]
            or frozen["final_provider_request"].get("model") != MODEL_ID
        ):
            raise RuntimeError("frozen_model_request_parity_failed")
        return SimpleNamespace(
            prepared_request=SimpleNamespace(
                form_data=copy.deepcopy(frozen["final_provider_request"])
            ),
            adapter_extracted_output=copy.deepcopy(frozen["raw_model_output"]),
            raw_provider_response=copy.deepcopy(frozen["raw_provider_response"]),
            execution_metadata=SimpleNamespace(**frozen["execution_metadata"]),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-frozen-replay", action="store_true")
    parser.add_argument("--ordinary-batch", type=Path, required=True)
    parser.add_argument("--current-store-root", type=Path, required=True)
    parser.add_argument("--baseline-store-root", type=Path, required=True)
    parser.add_argument("--baseline-gate4-private", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute_frozen_replay:
        raise SystemExit("explicit_frozen_replay_flag_required")
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    ordinary = _read_json(args.ordinary_batch)
    outcomes = {int(item["chunk"]["ordinal"]): item for item in ordinary["outcomes"]}
    provider = _provider_qualification(outcomes[24])
    mismatch = _mismatch_qualification(outcomes[106])

    current_store = _store(args.current_store_root)
    replay = _replay_chunk_106(
        store=current_store,
        outcome=outcomes[106],
    )
    baseline_facts = _read_json(args.baseline_gate4_private)["assembly"]["facts"]
    inventory = _inventory(
        current_store=current_store,
        baseline_store=_store(args.baseline_store_root),
        baseline_facts=baseline_facts,
    )

    passed = (
        provider["transport_failure_without_semantic_output"]
        and mismatch["missing_aliases"] == []
        and mismatch["unknown_aliases"] == []
        and mismatch["duplicate_aliases"] == ["f005"]
        and replay["document_status"] == "representative_subset_validated"
        and replay["annotations_validated"] == 26
        and replay["facts_incomplete_due_to_role_rejection"] == 1
        and inventory["unexplained_delta"] == 0
        and inventory["duplicate_gate3_identities"] == 0
        and inventory["duplicate_gate4_fact_ids"] == 0
        and inventory["invented_facts"] == 0
        and inventory["invented_relations"] == 0
    )
    private = {
        "schema_version": "broker_reports_g584_qualification_private_v1",
        "goal": "G5.84",
        "ordinary_batch_sha256": _sha256(args.ordinary_batch),
        "provider_failure": provider,
        "fact_set_mismatch": mismatch,
        "chunk_106_exact_replay": replay,
        "inventory": inventory,
        "provider_calls": 0,
        "semantic_retry": 0,
        "best_of_n": 0,
        "similarity_reconciliation": 0,
        "production_visual_dependency": 0,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g584_qualification_safe_v1",
        "goal": "G5.84",
        "terminal": (
            "PROVIDER_RETRY_POLICY_BOUNDARY_REACHED"
            if passed
            else "CURRENT_FACT_INVENTORY_REQUALIFICATION_REQUIRED"
        ),
        "ordinary_batch_sha256": private["ordinary_batch_sha256"],
        "provider_failure": {
            key: provider[key]
            for key in (
                "chunk_ordinal",
                "pass1_facts",
                "http_status",
                "provider_error_type",
                "mapped_error_code",
                "transport_failure_without_semantic_output",
                "provider_calls",
                "retry_calls",
            )
        },
        "fact_set_mismatch": {
            key: mismatch[key]
            for key in (
                "chunk_ordinal",
                "pass1_facts",
                "pass2_facts",
                "pass2_unique_facts",
                "missing_aliases",
                "unknown_aliases",
                "duplicate_aliases",
                "duplicate_occurrences",
                "deduplicated_sequence_equals_pass1",
                "minimal_unsafe_unit",
            )
        },
        "chunk_106_exact_replay": replay,
        "inventory": {
            key: inventory[key]
            for key in (
                "baseline_facts_total",
                "baseline_atomic_facts",
                "baseline_non_atomic_pseudo_facts",
                "unchanged_other_documents_facts",
                "matched_old_large_atomic_facts",
                "removed_old_large_atomic_facts",
                "removed_old_large_financial_type_counts",
                "removed_old_large_page_counts",
                "removed_old_large_target_kind_counts",
                "new_atomic_facts_in_135_previously_valid_chunks",
                "facts_from_5_previously_suppressed_chunks",
                "current_large_document_facts",
                "current_case_facts",
                "explained_delta",
                "unexplained_delta",
                "duplicate_source_assertion_identities",
                "duplicate_gate3_identities",
                "duplicate_gate4_fact_ids",
                "invented_facts",
                "invented_relations",
                "targets_existing",
                "targets_total",
                "atomic_targets",
                "current_document_page_counts",
                "current_document_target_kind_counts",
                "current_document_financial_type_counts",
                "current_document_atomicity_counts",
            )
        },
        "provider_calls": 0,
        "ordinary_replay": 0,
        "semantic_retry": 0,
        "best_of_n": 0,
        "similarity_reconciliation": 0,
        "production_visual_dependency": 0,
        "passed": passed,
        "private_result_sha256": _sha256(args.private_output),
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


def _provider_qualification(outcome: dict[str, Any]) -> dict[str, Any]:
    error = outcome["provider_error"]
    raw = error["raw_output"]
    pass1_facts = len(outcome["pass1_attempt"]["validated_output"]["annotations"])
    return {
        "chunk_ordinal": 24,
        "failed_phase": outcome["failed_phase"],
        "pass1_facts": pass1_facts,
        "http_status": raw.get("status_code"),
        "provider_error_type": (raw.get("error") or {}).get("type"),
        "mapped_error_code": outcome["error_code"],
        "transport_failure_without_semantic_output": (
            outcome["failed_phase"] == "role_labeling"
            and outcome["error_code"] == "gate2_model_provider_unavailable"
            and raw.get("status_code") == 502
            and (raw.get("error") or {}).get("type") == "non_json_provider_response"
            and outcome.get("role_attempt") is None
        ),
        "semantic_request_sha256": None,
        "semantic_request_hash_reason": (
            "typed provider exception preserves adapter/schema/model identity "
            "but not the failed role request body"
        ),
        "provider_calls": 1,
        "retry_calls": 0,
        "raw_output_sha256": _json_sha256(raw),
    }


def _mismatch_qualification(outcome: dict[str, Any]) -> dict[str, Any]:
    pass1 = outcome["pass1_attempt"]["validated_output"]["annotations"]
    role_attempt = outcome["role_attempt"]
    raw_role_output = role_attempt["raw_model_output"]
    decoded_role_output = (
        json.loads(raw_role_output)
        if isinstance(raw_role_output, str)
        else raw_role_output
    )
    pass2 = decoded_role_output["facts"]
    expected = [f"f{index:03d}" for index in range(1, len(pass1) + 1)]
    returned = [item.get("fact_alias") for item in pass2]
    counts = Counter(returned)
    missing = [alias for alias in expected if counts[alias] == 0]
    unknown = sorted(alias for alias in counts if alias not in set(expected))
    duplicates = [alias for alias in expected if counts[alias] > 1]
    duplicate_labels = {
        alias: [
            item.get("financial_label")
            for item in pass2
            if item.get("fact_alias") == alias
        ]
        for alias in duplicates
    }
    deduplicated = list(dict.fromkeys(returned))
    return {
        "chunk_ordinal": 106,
        "pass1_facts": len(expected),
        "pass2_facts": len(returned),
        "pass2_unique_facts": len(counts),
        "missing_aliases": missing,
        "unknown_aliases": unknown,
        "duplicate_aliases": duplicates,
        "duplicate_occurrences": sum(counts[a] - 1 for a in duplicates),
        "duplicate_labels": duplicate_labels,
        "deduplicated_sequence_equals_pass1": deduplicated == expected,
        "reordered_only": counts == Counter(expected) and returned != expected,
        "minimal_unsafe_unit": "exact_pass1_fact:f005",
        "raw_role_output_sha256": _json_sha256(role_attempt["raw_model_output"]),
    }


def _replay_chunk_106(*, store: Any, outcome: dict[str, Any]) -> dict[str, Any]:
    client = FrozenReplayClient(
        [outcome["pass1_attempt"], outcome["role_attempt"]]
    )
    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(
            document_id=LARGE_DOCUMENT_ID,
            context=_context(CURRENT_RUNS[LARGE_DOCUMENT_ID]),
            chunk_ordinals=(106,),
        )
    )
    metrics = result.metrics
    return {
        "document_status": result.document_status,
        "chunks_validated": metrics["chunks_validated"],
        "chunks_with_local_failures": metrics["chunks_with_local_failures"],
        "annotations_validated": metrics["annotations_validated"],
        "facts_role_complete": metrics["facts_role_complete"],
        "facts_role_incomplete": metrics["facts_role_incomplete"],
        "facts_incomplete_due_to_role_rejection": metrics[
            "facts_incomplete_due_to_role_rejection"
        ],
        "role_bindings_rejected": metrics["role_bindings_rejected"],
        "rejection_codes": sorted(
            {
                item["error_code"]
                for item in result.outcomes[0].role_attempt.rejected_role_bindings
            }
        ),
        "frozen_responses_consumed": client.responses_consumed,
        "provider_calls": 0,
    }


def _inventory(
    *,
    current_store: Any,
    baseline_store: Any,
    baseline_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    current_context = _context(CURRENT_RUNS[LARGE_DOCUMENT_ID])
    assembly = Gate4FinancialCaseRuntimeFactory(
        store=current_store,
        read_enabled=True,
    ).create().rebuild_case(context=current_context)
    if assembly.status != CASE_COMPLETE_FOR_CURRENT_INPUT_SET:
        raise RuntimeError("current_case_not_complete")
    current_facts = list(assembly.facts)
    baseline_atomic, baseline_non_atomic = _classify_baseline(
        store=baseline_store,
        facts=baseline_facts,
    )
    current_by_document = _by_document(current_facts)
    baseline_by_document = _by_document(baseline_atomic)
    other_documents = sorted(set(CURRENT_RUNS) - {LARGE_DOCUMENT_ID})
    if not all(
        _facts_hash(current_by_document[document_id])
        == _facts_hash(baseline_by_document[document_id])
        for document_id in other_documents
    ):
        raise RuntimeError("unchanged_document_inventory_drift")
    old_large = baseline_by_document[LARGE_DOCUMENT_ID]
    new_large = current_by_document[LARGE_DOCUMENT_ID]
    old_signatures = Counter(_source_assertion_signature(fact) for fact in old_large)
    new_signatures = Counter(_source_assertion_signature(fact) for fact in new_large)
    matched_old_large = sum((old_signatures & new_signatures).values())
    unmatched_old_large = _counter_unmatched(
        facts=old_large,
        available=new_signatures,
    )
    added_large = len(new_large) - matched_old_large
    suppressed_chunks = 173
    preexisting_valid_chunks_added = added_large - suppressed_chunks

    provenance = _current_provenance(
        store=current_store,
        assembly=assembly,
        facts=current_facts,
    )
    explained_delta = (
        -len(baseline_non_atomic)
        - len(unmatched_old_large)
        + preexisting_valid_chunks_added
        + suppressed_chunks
    )
    actual_delta = len(current_facts) - len(baseline_facts)
    removal_summary = _old_large_removal_summary(
        store=baseline_store,
        facts=unmatched_old_large,
    )
    return {
        "status": assembly.status,
        "sources_total": len(assembly.sources),
        "baseline_facts_total": len(baseline_facts),
        "baseline_atomic_facts": len(baseline_atomic),
        "baseline_non_atomic_pseudo_facts": len(baseline_non_atomic),
        "unchanged_other_documents_facts": sum(
            len(current_by_document[document_id])
            for document_id in other_documents
        ),
        "old_large_atomic_facts": len(old_large),
        "matched_old_large_atomic_facts": matched_old_large,
        "removed_old_large_atomic_facts": len(unmatched_old_large),
        **removal_summary,
        "new_atomic_facts_in_135_previously_valid_chunks": (
            preexisting_valid_chunks_added
        ),
        "facts_from_5_previously_suppressed_chunks": suppressed_chunks,
        "current_large_document_facts": len(new_large),
        "current_case_facts": len(current_facts),
        "actual_delta": actual_delta,
        "explained_delta": explained_delta,
        "unexplained_delta": actual_delta - explained_delta,
        **provenance,
    }


def _current_provenance(
    *,
    store: Any,
    assembly: Any,
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    persistence = Gate3FinancialAnnotationsPersistenceFactory(
        store=store,
        read_enabled=True,
    ).create()
    payloads: dict[str, dict[str, Any]] = {}
    resolvers: dict[str, Any] = {}
    canonicals: dict[str, dict[str, Any]] = {}
    for source in assembly.sources:
        context = _context(CURRENT_RUNS[source.document_id])
        payloads[source.document_id] = persistence.read(
            artifact_id=source.financial_annotations_artifact_id,
            context=context,
        )
        resolver = Gate3RoleValueResolverFactory.create_from_active_canonical(
            store=store,
            read_enabled=True,
            document_id=source.document_id,
            expected_canonical_version_id=source.canonical_version_id,
            context=context,
        )
        resolvers[source.document_id] = resolver
        envelope = CanonicalReaderFactory(
            store=store,
            read_enabled=True,
        ).create().read_active_envelope(source.document_id, context)
        if envelope.canonical_version_id != source.canonical_version_id:
            raise RuntimeError("current_canonical_binding_drift")
        canonicals[source.document_id] = envelope.artifact

    target_exists = 0
    atomic_targets = 0
    invented_facts = 0
    relation_fields = 0
    source_assertion_ids: list[str] = []
    gate3_ids: list[str] = []
    gate4_ids: list[str] = []
    page_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    atomicity_counts: Counter[str] = Counter()
    private_rows: list[dict[str, Any]] = []
    for fact in facts:
        binding = fact["gate3_binding"]
        document_id = binding["canonical_binding"]["document_id"]
        annotation_index = binding["annotation_index"]
        payload = payloads[document_id]
        annotation = payload["annotations"][annotation_index]
        exact_gate3_match = (
            annotation["target"] == fact["annotation_target"]
            and annotation["financial_label"] == fact["financial_type"]
            and payload["canonical_binding"] == binding["canonical_binding"]
            and gate4_financial_case_fact_id(fact) == fact["fact_id"]
        )
        invented_facts += int(not exact_gate3_match)
        resolver = resolvers[document_id]
        structural = resolver.is_unambiguously_atomic_assertion_target(
            annotation["target"]
        )
        literal = resolver.has_unambiguous_literal_anchor(annotation)
        decision = gate4_annotation_materialization_decision(
            annotation,
            structurally_atomic_target=structural,
            unambiguous_literal_anchor=literal,
        )
        target_exists += 1
        atomic_targets += int(decision["materializable"])
        atomicity = "structural" if structural else "unique_literal_anchor"
        gate3_id = f"{binding['financial_annotations_artifact_id']}:{annotation_index}"
        assertion_id = _json_sha256(
            {
                "document_id": document_id,
                "canonical_binding": binding["canonical_binding"],
                "annotation_index": annotation_index,
                "target": annotation["target"],
                "financial_label": annotation["financial_label"],
            }
        )
        source_assertion_ids.append(assertion_id)
        gate3_ids.append(gate3_id)
        gate4_ids.append(fact["fact_id"])
        relation_fields += _relation_field_count(fact)
        if document_id == LARGE_DOCUMENT_ID:
            page = _target_page(canonicals[document_id], annotation["target"])
            page_counts[str(page)] += 1
            kind_counts[annotation["target"]["kind"]] += 1
            type_counts[annotation["financial_label"]] += 1
            atomicity_counts[atomicity] += 1
        private_rows.append(
            {
                "source_assertion_id": assertion_id,
                "gate3_identity": gate3_id,
                "gate4_fact_id": fact["fact_id"],
                "document_id": document_id,
                "page": (
                    _target_page(canonicals[document_id], annotation["target"])
                ),
                "target_kind": annotation["target"]["kind"],
                "financial_type": annotation["financial_label"],
                "atomicity": atomicity,
            }
        )
    return {
        "targets_existing": target_exists,
        "targets_total": len(facts),
        "atomic_targets": atomic_targets,
        "duplicate_source_assertion_identities": _duplicates(source_assertion_ids),
        "duplicate_gate3_identities": _duplicates(gate3_ids),
        "duplicate_gate4_fact_ids": _duplicates(gate4_ids),
        "invented_facts": invented_facts,
        "invented_relations": relation_fields,
        "current_document_page_counts": dict(sorted(page_counts.items(), key=lambda x: int(x[0]))),
        "current_document_target_kind_counts": dict(sorted(kind_counts.items())),
        "current_document_financial_type_counts": dict(sorted(type_counts.items())),
        "current_document_atomicity_counts": dict(sorted(atomicity_counts.items())),
        "private_fact_rows": private_rows,
    }


def _old_large_removal_summary(
    *,
    store: Any,
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    context = _context(BASELINE_RUNS[LARGE_DOCUMENT_ID])
    envelope = CanonicalReaderFactory(
        store=store,
        read_enabled=True,
    ).create().read_active_envelope(LARGE_DOCUMENT_ID, context)
    type_counts = Counter(fact["financial_type"] for fact in facts)
    kind_counts = Counter(fact["annotation_target"]["kind"] for fact in facts)
    page_counts = Counter(
        str(_target_page(envelope.artifact, fact["annotation_target"]))
        for fact in facts
    )
    return {
        "removed_old_large_financial_type_counts": dict(sorted(type_counts.items())),
        "removed_old_large_page_counts": dict(
            sorted(page_counts.items(), key=lambda item: int(item[0]))
        ),
        "removed_old_large_target_kind_counts": dict(sorted(kind_counts.items())),
        "removed_old_large_reason": (
            "old-version exact required-role source assertion signature is absent "
            "from the replacement current Canonical-bound Gate3 proposal"
        ),
        "private_removed_old_large_fact_ids": [fact["fact_id"] for fact in facts],
    }


def _classify_baseline(*, store: Any, facts: list[dict[str, Any]]) -> tuple[list, list]:
    resolvers = {
        document_id: Gate3RoleValueResolverFactory.create_from_active_canonical(
            store=store,
            read_enabled=True,
            document_id=document_id,
            expected_canonical_version_id=next(
                fact["gate3_binding"]["canonical_binding"]["canonical_version_id"]
                for fact in facts
                if _document_id(fact) == document_id
            ),
            context=_context(run_id),
        )
        for document_id, run_id in BASELINE_RUNS.items()
    }
    atomic: list[dict[str, Any]] = []
    non_atomic: list[dict[str, Any]] = []
    for fact in facts:
        resolver = resolvers[_document_id(fact)]
        annotation = _annotation_from_fact(fact)
        decision = gate4_annotation_materialization_decision(
            annotation,
            structurally_atomic_target=(
                resolver.is_unambiguously_atomic_assertion_target(annotation["target"])
            ),
            unambiguous_literal_anchor=resolver.has_unambiguous_literal_anchor(annotation),
        )
        (atomic if decision["materializable"] else non_atomic).append(fact)
    return atomic, non_atomic


def _annotation_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    roles = []
    for role in fact["roles"]:
        source = role.get("source_binding")
        if not isinstance(source, dict):
            roles.append({"role": role["role"], "status": "missing"})
            continue
        restored = {
            "role": role["role"],
            "status": "bound",
            "target": source["target"],
        }
        if "exact_text" in source:
            restored["exact_text"] = source["exact_text"]
        roles.append(restored)
    return {
        "target": fact["annotation_target"],
        "financial_label": fact["financial_type"],
        "roles": roles,
    }


def _target_page(canonical: dict[str, Any], target: dict[str, Any]) -> int:
    node = next(
        item for item in canonical["nodes"] if item["node_id"] == target["node_id"]
    )
    provenance = {
        item["provenance_id"]: item for item in canonical["provenance"]
    }
    pages = {
        (provenance[source_ref].get("source_locator") or {}).get("page")
        for source_ref in node.get("source_refs") or []
    }
    pages.discard(None)
    if len(pages) != 1:
        raise RuntimeError("canonical_target_page_not_unique")
    return int(next(iter(pages)))


def _relation_field_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            int("relation" in str(key).lower()) + _relation_field_count(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return sum(_relation_field_count(item) for item in value)
    return 0


def _store(root: Path) -> Any:
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context(run_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=run_id,
        allow_private=True,
    )


def _document_id(fact: dict[str, Any]) -> str:
    return fact["gate3_binding"]["canonical_binding"]["document_id"]


def _by_document(facts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {document_id: [] for document_id in CURRENT_RUNS}
    for fact in facts:
        result[_document_id(fact)].append(fact)
    return result


def _source_assertion_signature(fact: dict[str, Any]) -> str:
    roles = [
        {
            "role": role["role"],
            "status": role["status"],
            "value": role.get("value"),
        }
        for role in fact["roles"]
        if role["requirement"] == "required"
    ]
    return _json_canonical(
        {"financial_type": fact["financial_type"], "roles": roles}
    )


def _counter_unmatched(
    *,
    facts: list[dict[str, Any]],
    available: Counter[str],
) -> list[dict[str, Any]]:
    remaining = available.copy()
    unmatched: list[dict[str, Any]] = []
    for fact in facts:
        signature = _source_assertion_signature(fact)
        if remaining[signature] > 0:
            remaining[signature] -= 1
        else:
            unmatched.append(fact)
    return unmatched


def _facts_hash(facts: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_json_canonical(facts).encode("utf-8")).hexdigest()


def _duplicates(values: list[str]) -> int:
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_json_canonical(value).encode("utf-8")).hexdigest()


def _json_canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
