"""Inactive G3.4C sequential chunk labeling and deterministic merge proof."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext
from .gate2_model_contracts import Gate2SourceFactRuntimeError
from .gate3_bounded_labeling import (
    FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
    Gate3BoundedLabelingAttempt,
    Gate3BoundedLabelingFactory,
)
from .gate3_structural_chunking import Gate3StructuralChunkFactory


GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate3_chunk_batch_labeling_result_v1"
)
FACTORY_REQUIRED = (
    "Gate3ChunkBatchLabelingFactory.create is the only G3.4C sequential batch "
    "and merge entrypoint; it must call Gate3StructuralChunkFactory.create "
    "and Gate3BoundedLabelingFactory.create_from_chunk"
)
FORBIDDEN = (
    "G3.4C must not change chunking, dictionary or instruction, retry, repair, "
    "fall back, execute chunks concurrently, classify financial meaning in "
    "code, semantically deduplicate, persist annotations or activate a route"
)


class Gate3ChunkBatchLabelingError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate3ChunkLabelingOutcome:
    chunk: dict[str, Any] = field(repr=False)
    attempt: Gate3BoundedLabelingAttempt | None = field(repr=False)
    provider_error: Gate2SourceFactRuntimeError | None = field(repr=False)
    terminal_status: str
    error_code: str | None


@dataclass(frozen=True)
class Gate3ChunkBatchLabelingResult:
    chunk_set: dict[str, Any] = field(repr=False)
    outcomes: tuple[Gate3ChunkLabelingOutcome, ...] = field(repr=False)
    merged_output: dict[str, Any] | None = field(repr=False)
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
        if (
            binding.get("document_id") != document_id
            or any(chunk["canonical_binding"] != binding for chunk in selected)
        ):
            raise Gate3ChunkBatchLabelingError(
                "gate3_chunk_batch_document_mixing"
            )

        labeling = Gate3BoundedLabelingFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            model_client=self._model_client,
            model_id=self._model_id,
        )
        outcomes: list[Gate3ChunkLabelingOutcome] = []
        for chunk in selected:
            try:
                attempt = await labeling.create_from_chunk(chunk=chunk)
            except Gate2SourceFactRuntimeError as exc:
                outcomes.append(
                    Gate3ChunkLabelingOutcome(
                        chunk=copy.deepcopy(chunk),
                        attempt=None,
                        provider_error=exc,
                        terminal_status="provider_failed",
                        error_code=exc.code,
                    )
                )
                continue
            outcomes.append(
                Gate3ChunkLabelingOutcome(
                    chunk=copy.deepcopy(chunk),
                    attempt=attempt,
                    provider_error=None,
                    terminal_status=attempt.validation_status,
                    error_code=attempt.validation_error_code,
                )
            )

        merged_output = _merge_validated_attempts(
            binding=binding,
            outcomes=outcomes,
        )
        rejected = sum(
            outcome.terminal_status == "rejected" for outcome in outcomes
        )
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
        return Gate3ChunkBatchLabelingResult(
            chunk_set=copy.deepcopy(chunk_set),
            outcomes=tuple(outcomes),
            merged_output=merged_output,
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
        raise Gate3ChunkBatchLabelingError(
            "gate3_chunk_batch_selection_invalid"
        )
    return (
        selected,
        "full_document" if selected == available else "representative_subset",
    )


def _merge_validated_attempts(
    *,
    binding: dict[str, str],
    outcomes: list[Gate3ChunkLabelingOutcome],
) -> dict[str, Any] | None:
    validated = [
        outcome.attempt.validated_output
        for outcome in outcomes
        if outcome.attempt is not None
        and outcome.attempt.validated_output is not None
        and outcome.terminal_status == "validated"
    ]
    if not validated:
        return None
    first = validated[0]
    identity_fields = (
        "canonical_binding",
        "dictionary_identity",
        "instruction_identity",
        "model_identity",
    )
    if first["canonical_binding"] != binding or any(
        any(output[field] != first[field] for field in identity_fields)
        for output in validated
    ):
        raise Gate3ChunkBatchLabelingError(
            "gate3_chunk_batch_merge_identity_mismatch"
        )

    annotations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for outcome in outcomes:
        if (
            outcome.attempt is None
            or outcome.attempt.validated_output is None
            or outcome.terminal_status != "validated"
        ):
            continue
        chunk_target_order = {
            _stable_json(mapping["canonical_target"]): index
            for index, mapping in enumerate(outcome.chunk["target_mappings"])
        }
        chunk_annotations = list(
            outcome.attempt.validated_output["annotations"]
        )
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
                raise Gate3ChunkBatchLabelingError(
                    "gate3_chunk_batch_merge_duplicate"
                )
            seen.add(identity)
            annotations.append(copy.deepcopy(annotation))
    return {
        "schema_version": FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(binding),
        "dictionary_identity": copy.deepcopy(first["dictionary_identity"]),
        "instruction_identity": copy.deepcopy(first["instruction_identity"]),
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
    for outcome in outcomes:
        value = (
            outcome.attempt.execution_metadata
            if outcome.attempt is not None
            else getattr(outcome.provider_error, "execution_metadata", None)
        )
        if value is not None:
            metadata.append(value)
    input_tokens = [
        value.input_tokens
        for value in metadata
        if isinstance(value.input_tokens, int)
    ]
    output_tokens = [
        value.output_tokens
        for value in metadata
        if isinstance(value.output_tokens, int)
    ]
    durations = [
        value.duration_ms
        for value in metadata
        if isinstance(value.duration_ms, int)
    ]
    return {
        "chunks_total": len(chunks),
        "chunks_validated": sum(
            outcome.terminal_status == "validated" for outcome in outcomes
        ),
        "chunks_rejected": sum(
            outcome.terminal_status == "rejected" for outcome in outcomes
        ),
        "chunks_provider_failed": sum(
            outcome.terminal_status == "provider_failed" for outcome in outcomes
        ),
        "annotations_validated": (
            len(merged_output["annotations"])
            if merged_output is not None
            else 0
        ),
        "chunk_chars_total": sum(
            int(chunk["metrics"]["model_view_chars"]) for chunk in chunks
        ),
        "chunk_chars_max": max(
            int(chunk["metrics"]["model_view_chars"]) for chunk in chunks
        ),
        "aliases_total": sum(
            int(chunk["metrics"]["target_count"]) for chunk in chunks
        ),
        "input_tokens_total": sum(input_tokens) if input_tokens else None,
        "input_tokens_max": max(input_tokens) if input_tokens else None,
        "output_tokens_total": sum(output_tokens) if output_tokens else None,
        "duration_ms_total": sum(durations) if durations else None,
    }


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
    "Gate3ChunkBatchLabelingError",
    "Gate3ChunkBatchLabelingFactory",
    "Gate3ChunkBatchLabelingResult",
    "Gate3ChunkLabelingOutcome",
]
