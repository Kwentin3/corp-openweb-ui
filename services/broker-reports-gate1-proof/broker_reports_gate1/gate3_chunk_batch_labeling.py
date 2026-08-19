"""Sequential Gate 3 type/role chunk labeling and deterministic merge."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext
from .gate2_model_contracts import Gate2SourceFactRuntimeError
from .gate3_bounded_labeling import (
    Gate3BoundedLabelingAttempt,
    Gate3BoundedLabelingFactory,
)
from .gate3_financial_role_pack import (
    GATE3_ROLE_PACK_CURRENT_VERSION,
    Gate3FinancialRolePackFactory,
)
from .gate3_role_labeling import (
    Gate3RoleLabelingAttempt,
    Gate3RoleLabelingFactory,
)
from .gate3_structural_chunking import Gate3StructuralChunkFactory


GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate3_chunk_batch_labeling_result_v4"
)
GATE3_SEMANTIC_PUBLICATION_MODE_FULL = "FULL"
GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED = "DEMAND_SCOPED"
_VALIDATED_ROLE_EXECUTION_STATUSES = frozenset(
    {"validated", "validated_with_local_rejections", "skipped_empty"}
)
_VALIDATED_CHUNK_STATUSES = frozenset(
    {"validated", "validated_with_local_rejections"}
)
FACTORY_REQUIRED = (
    "Gate3ChunkBatchLabelingFactory.create is the only sequential Gate 3 "
    "batch and merge entrypoint; it must call Gate3StructuralChunkFactory, "
    "Gate3BoundedLabelingFactory and Gate3RoleLabelingFactory"
)
FORBIDDEN = (
    "Gate 3 batch must not change chunking, label or role meaning, retry a semantic response, "
    "repair, fall back, execute chunks concurrently, call once per fact, "
    "semantically deduplicate, persist annotations or activate a route"
)


class Gate3ChunkBatchLabelingError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate3ChunkLabelingOutcome:
    chunk: dict[str, Any] = field(repr=False)
    attempt: Gate3BoundedLabelingAttempt | None = field(repr=False)
    role_attempt: Gate3RoleLabelingAttempt | None = field(repr=False)
    provider_error: Gate2SourceFactRuntimeError | None = field(repr=False)
    terminal_status: str
    error_code: str | None
    failed_phase: str | None


@dataclass(frozen=True)
class Gate3ChunkBatchLabelingResult:
    chunk_set: dict[str, Any] = field(repr=False)
    outcomes: tuple[Gate3ChunkLabelingOutcome, ...] = field(repr=False)
    merged_output: dict[str, Any] | None = field(repr=False)
    semantic_scope: dict[str, Any]
    selected_chunk_ordinals: tuple[int, ...]
    selection_mode: str
    document_status: str
    metrics: dict[str, Any]


class Gate3ChunkBatchLabelingFactory:
    """Label selected chunks sequentially and merge without financial logic."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._model_id = model_id

    async def create(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        chunk_ordinals: Iterable[int] | None = None,
        requested_financial_labels: tuple[str, ...] | None = None,
    ) -> Gate3ChunkBatchLabelingResult:
        chunk_set = Gate3StructuralChunkFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create(document_id=document_id, context=context)
        chunks = list(chunk_set["chunks"])
        selected_ordinals, selection_mode = _select_ordinals(
            chunks=chunks,
            chunk_ordinals=chunk_ordinals,
        )
        chunk_by_ordinal = {int(chunk["ordinal"]): chunk for chunk in chunks}
        selected = [chunk_by_ordinal[ordinal] for ordinal in selected_ordinals]
        binding = chunk_set["canonical_binding"]
        if binding.get("document_id") != document_id or any(
            chunk["canonical_binding"] != binding for chunk in selected
        ):
            raise Gate3ChunkBatchLabelingError("gate3_chunk_batch_document_mixing")

        labeling = Gate3BoundedLabelingFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            model_client=self._model_client,
            model_id=self._model_id,
        )
        role_labeling = Gate3RoleLabelingFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            model_client=self._model_client,
            model_id=self._model_id,
        )
        outcomes: list[Gate3ChunkLabelingOutcome] = []
        for chunk in selected:
            try:
                attempt = await labeling.create_from_chunk(
                    chunk=chunk,
                    requested_financial_labels=requested_financial_labels,
                )
            except Gate2SourceFactRuntimeError as exc:
                outcomes.append(
                    Gate3ChunkLabelingOutcome(
                        chunk=copy.deepcopy(chunk),
                        attempt=None,
                        role_attempt=None,
                        provider_error=exc,
                        terminal_status="provider_failed",
                        error_code=exc.code,
                        failed_phase="financial_labeling",
                    )
                )
                continue
            if attempt.validation_status != "validated":
                outcomes.append(
                    Gate3ChunkLabelingOutcome(
                        chunk=copy.deepcopy(chunk),
                        attempt=attempt,
                        role_attempt=None,
                        provider_error=None,
                        terminal_status="rejected",
                        error_code=attempt.validation_error_code,
                        failed_phase="financial_labeling",
                    )
                )
                continue
            try:
                role_attempt = await role_labeling.create_from_chunk(
                    chunk=chunk,
                    context=context,
                    pass1_attempt=attempt,
                )
            except Gate2SourceFactRuntimeError as exc:
                outcomes.append(
                    Gate3ChunkLabelingOutcome(
                        chunk=copy.deepcopy(chunk),
                        attempt=attempt,
                        role_attempt=None,
                        provider_error=exc,
                        terminal_status="provider_failed",
                        error_code=exc.code,
                        failed_phase="role_labeling",
                    )
                )
                continue
            outcomes.append(
                Gate3ChunkLabelingOutcome(
                    chunk=copy.deepcopy(chunk),
                    attempt=attempt,
                    role_attempt=role_attempt,
                    provider_error=None,
                    terminal_status=(
                        "validated_with_local_rejections"
                        if role_attempt.execution_status
                        == "validated_with_local_rejections"
                        else "validated"
                        if role_attempt.execution_status
                        in _VALIDATED_ROLE_EXECUTION_STATUSES
                        else "rejected"
                    ),
                    error_code=role_attempt.validation_error_code,
                    failed_phase=(
                        None
                        if role_attempt.execution_status
                        in _VALIDATED_ROLE_EXECUTION_STATUSES
                        else "role_labeling"
                    ),
                )
            )

        merged_output = _merge_validated_attempts(
            binding=binding,
            outcomes=outcomes,
        )
        rejected = sum(outcome.terminal_status == "rejected" for outcome in outcomes)
        provider_failed = sum(
            outcome.terminal_status == "provider_failed" for outcome in outcomes
        )
        if rejected or provider_failed:
            document_status = "incomplete"
        elif selection_mode == "full_document":
            document_status = "complete"
        else:
            document_status = "representative_subset_validated"
        metrics = _batch_metrics(
            chunks=selected,
            outcomes=outcomes,
            merged_output=merged_output,
        )
        semantic_scope = {
            "publication_mode": (
                GATE3_SEMANTIC_PUBLICATION_MODE_FULL
                if requested_financial_labels is None
                else GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED
            ),
            "document_id": document_id,
            "requested_financial_labels": (
                []
                if requested_financial_labels is None
                else list(requested_financial_labels)
            ),
            "requested_roles": _requested_roles(requested_financial_labels),
            "selected_chunk_ordinals": list(selected_ordinals),
        }
        return Gate3ChunkBatchLabelingResult(
            chunk_set=copy.deepcopy(chunk_set),
            outcomes=tuple(outcomes),
            merged_output=merged_output,
            semantic_scope=semantic_scope,
            selected_chunk_ordinals=selected_ordinals,
            selection_mode=selection_mode,
            document_status=document_status,
            metrics=metrics,
        )


def _select_ordinals(
    *,
    chunks: list[dict[str, Any]],
    chunk_ordinals: Iterable[int] | None,
) -> tuple[tuple[int, ...], str]:
    available = tuple(int(chunk["ordinal"]) for chunk in chunks)
    if not available:
        raise Gate3ChunkBatchLabelingError("gate3_chunk_batch_empty")
    if chunk_ordinals is None:
        return available, "full_document"
    selected = tuple(chunk_ordinals)
    if (
        not selected
        or any(
            isinstance(ordinal, bool) or not isinstance(ordinal, int)
            for ordinal in selected
        )
        or selected != tuple(sorted(set(selected)))
        or any(ordinal not in available for ordinal in selected)
    ):
        raise Gate3ChunkBatchLabelingError("gate3_chunk_batch_selection_invalid")
    return (
        selected,
        "full_document" if selected == available else "representative_subset",
    )


def _requested_roles(
    requested_financial_labels: tuple[str, ...] | None,
) -> list[str]:
    if requested_financial_labels is None:
        return []
    role_pack = Gate3FinancialRolePackFactory.create().load_published(
        GATE3_ROLE_PACK_CURRENT_VERSION
    )
    requested = set(requested_financial_labels)
    return sorted(
        {
            role
            for profile in role_pack["profiles"]
            if profile["financial_label"] in requested
            for role in [*profile["required_roles"], *profile["optional_roles"]]
        }
    )


def _merge_validated_attempts(
    *,
    binding: dict[str, str],
    outcomes: list[Gate3ChunkLabelingOutcome],
) -> dict[str, Any] | None:
    validated = [
        outcome.role_attempt.validated_output
        for outcome in outcomes
        if outcome.role_attempt is not None
        and outcome.role_attempt.validated_output is not None
        and outcome.terminal_status in _VALIDATED_CHUNK_STATUSES
    ]
    if not validated:
        return None
    first = validated[0]
    identity_fields = (
        "canonical_binding",
        "dictionary_identity",
        "role_pack_identity",
        "instruction_identity",
        "role_instruction_identity",
        "model_identity",
    )
    if first["canonical_binding"] != binding or any(
        any(output[field] != first[field] for field in identity_fields)
        for output in validated
    ):
        raise Gate3ChunkBatchLabelingError("gate3_chunk_batch_merge_identity_mismatch")

    annotations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for outcome in outcomes:
        if (
            outcome.role_attempt is None
            or outcome.role_attempt.validated_output is None
            or outcome.terminal_status not in _VALIDATED_CHUNK_STATUSES
        ):
            continue
        chunk_target_order = {
            _stable_json(mapping["canonical_target"]): index
            for index, mapping in enumerate(outcome.chunk["target_mappings"])
        }
        chunk_annotations = list(outcome.role_attempt.validated_output["annotations"])
        try:
            ordered = sorted(
                enumerate(chunk_annotations),
                key=lambda item: (
                    chunk_target_order[_stable_json(item[1]["target"])],
                    item[0],
                ),
            )
        except KeyError as exc:
            raise Gate3ChunkBatchLabelingError(
                "gate3_chunk_batch_merge_target_unknown"
            ) from exc
        for _, annotation in ordered:
            identity = _stable_json(annotation)
            if identity in seen:
                raise Gate3ChunkBatchLabelingError("gate3_chunk_batch_merge_duplicate")
            seen.add(identity)
            annotations.append(copy.deepcopy(annotation))
    return {
        "schema_version": first["schema_version"],
        "canonical_binding": copy.deepcopy(binding),
        "dictionary_identity": copy.deepcopy(first["dictionary_identity"]),
        "role_pack_identity": copy.deepcopy(first["role_pack_identity"]),
        "instruction_identity": copy.deepcopy(first["instruction_identity"]),
        "role_instruction_identity": copy.deepcopy(first["role_instruction_identity"]),
        "model_identity": copy.deepcopy(first["model_identity"]),
        "annotations": annotations,
        "validation_status": "validated",
    }


def _batch_metrics(
    *,
    chunks: list[dict[str, Any]],
    outcomes: list[Gate3ChunkLabelingOutcome],
    merged_output: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = []
    operational_receipts: list[dict[str, Any]] = []
    for outcome in outcomes:
        if outcome.attempt is not None and outcome.attempt.execution_metadata:
            metadata.append(outcome.attempt.execution_metadata)
        if (
            outcome.role_attempt is not None
            and outcome.role_attempt.execution_metadata is not None
        ):
            metadata.append(outcome.role_attempt.execution_metadata)
        if outcome.provider_error is not None:
            value = getattr(outcome.provider_error, "execution_metadata", None)
            if value is not None:
                metadata.append(value)
        for owner in (outcome.attempt, outcome.role_attempt, outcome.provider_error):
            receipt = getattr(owner, "operational_retry_receipt", None)
            if isinstance(receipt, dict):
                operational_receipts.append(receipt)
    input_tokens = [
        value.input_tokens for value in metadata if isinstance(value.input_tokens, int)
    ]
    output_tokens = [
        value.output_tokens
        for value in metadata
        if isinstance(value.output_tokens, int)
    ]
    durations = [
        value.duration_ms for value in metadata if isinstance(value.duration_ms, int)
    ]
    chunks_rejected = sum(
        outcome.terminal_status == "rejected" for outcome in outcomes
    )
    chunks_provider_failed = sum(
        outcome.terminal_status == "provider_failed" for outcome in outcomes
    )
    facts_role_complete = sum(
        int(outcome.role_attempt.metrics.get("facts_role_complete") or 0)
        for outcome in outcomes
        if outcome.role_attempt is not None
        and outcome.terminal_status in _VALIDATED_CHUNK_STATUSES
    )
    facts_role_incomplete = sum(
        int(outcome.role_attempt.metrics.get("facts_role_incomplete") or 0)
        for outcome in outcomes
        if outcome.role_attempt is not None
        and outcome.terminal_status in _VALIDATED_CHUNK_STATUSES
    )
    facts_rejected = sum(
        len(outcome.role_attempt.facts)
        for outcome in outcomes
        if outcome.role_attempt is not None
        and outcome.terminal_status == "rejected"
    )
    semantic_rejections = sum(
        outcome.attempt is not None
        and outcome.attempt.validation_status == "rejected"
        for outcome in outcomes
    ) + sum(
        outcome.role_attempt is not None
        and outcome.role_attempt.execution_status == "rejected"
        for outcome in outcomes
    )
    result = {
        "chunks_total": len(chunks),
        "chunks_validated": sum(
            outcome.terminal_status in _VALIDATED_CHUNK_STATUSES
            for outcome in outcomes
        ),
        "chunks_rejected": chunks_rejected,
        "chunks_provider_failed": chunks_provider_failed,
        "chunks_with_local_failures": sum(
            outcome.terminal_status == "validated_with_local_rejections"
            for outcome in outcomes
        ),
        "fully_unusable_chunks": chunks_rejected + chunks_provider_failed,
        "annotations_validated": (
            len(merged_output["annotations"]) if merged_output is not None else 0
        ),
        "facts_role_complete": facts_role_complete,
        "facts_role_incomplete": facts_role_incomplete,
        "facts_incomplete_due_to_role_rejection": sum(
            int(
                outcome.role_attempt.metrics.get(
                    "facts_incomplete_due_to_role_rejection"
                )
                or 0
            )
            for outcome in outcomes
            if outcome.role_attempt is not None
            and outcome.terminal_status in _VALIDATED_CHUNK_STATUSES
        ),
        "facts_rejected": facts_rejected,
        "role_bindings_rejected": sum(
            len(outcome.role_attempt.rejected_role_bindings)
            for outcome in outcomes
            if outcome.role_attempt is not None
        ),
        "chunk_chars_total": sum(
            int(chunk["metrics"]["model_view_chars"]) for chunk in chunks
        ),
        "chunk_chars_max": max(
            int(chunk["metrics"]["model_view_chars"]) for chunk in chunks
        ),
        "aliases_total": sum(int(chunk["metrics"]["target_count"]) for chunk in chunks),
        "financial_labeling_provider_calls": sum(
            outcome.attempt is not None or outcome.failed_phase == "financial_labeling"
            for outcome in outcomes
        ),
        "role_labeling_provider_calls": sum(
            (
                outcome.role_attempt is not None
                and bool(outcome.role_attempt.metrics.get("provider_called"))
            )
            or outcome.failed_phase == "role_labeling"
            for outcome in outcomes
        ),
        "role_labeling_skipped_empty_chunks": sum(
            outcome.role_attempt is not None
            and outcome.role_attempt.execution_status == "skipped_empty"
            for outcome in outcomes
        ),
        "semantic_attempts": sum(
            int(receipt.get("semantic_attempts") or 0)
            for receipt in operational_receipts
        ),
        "transport_submissions": sum(
            int(receipt.get("transport_submissions") or 0)
            for receipt in operational_receipts
        ),
        "transport_failures_before_semantic_response": sum(
            int(receipt.get("transport_failures_before_semantic_response") or 0)
            for receipt in operational_receipts
        ),
        "operational_retries": sum(
            int(receipt.get("operational_retries") or 0)
            for receipt in operational_receipts
        ),
        "semantic_responses_received": sum(
            int(receipt.get("semantic_responses_received") or 0)
            for receipt in operational_receipts
        ),
        "semantic_rejections": semantic_rejections,
        "input_tokens_total": sum(input_tokens) if input_tokens else None,
        "input_tokens_max": max(input_tokens) if input_tokens else None,
        "output_tokens_total": sum(output_tokens) if output_tokens else None,
        "duration_ms_total": sum(durations) if durations else None,
    }
    result["source_fact_completeness_status"] = (
        "complete"
        if not facts_role_incomplete
        and not facts_rejected
        and not chunks_provider_failed
        else "incomplete"
    )
    return result


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION",
    "GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED",
    "GATE3_SEMANTIC_PUBLICATION_MODE_FULL",
    "Gate3ChunkBatchLabelingError",
    "Gate3ChunkBatchLabelingFactory",
    "Gate3ChunkBatchLabelingResult",
    "Gate3ChunkLabelingOutcome",
]
