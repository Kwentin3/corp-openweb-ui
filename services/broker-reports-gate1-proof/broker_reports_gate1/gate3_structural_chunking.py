"""Inactive deterministic bounded structural chunks over the G3.2 renderer."""

from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate3_projection import Gate3ProjectionFactory


GATE3_STRUCTURAL_CHUNK_SET_SCHEMA_VERSION = (
    "broker_reports_gate3_structural_chunk_set_v1"
)
DEFAULT_MAX_CHUNK_CHARS = 60_000
FACTORY_REQUIRED = (
    "Gate3StructuralChunkFactory.create is the only structural chunking "
    "entrypoint and must reuse Gate3ProjectionFactory's exact render plan"
)
FORBIDDEN = (
    "Chunking must not use financial labels, dictionary meanings, keyword "
    "selection, LLMs, providers, embeddings, RAG, source files, persistence, "
    "overlapping data rows, a second renderer or a second alias authority"
)

_ALIAS_RE = re.compile(r"(?<!\\)\[(t[0-9]{3,})\]")


class Gate3StructuralChunkError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = copy.deepcopy(details or {})


class Gate3StructuralChunkFactory:
    """Build ordered non-persisted chunks for exactly one active document."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._max_chunk_chars = max_chunk_chars

    def create(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if (
            isinstance(self._max_chunk_chars, bool)
            or not isinstance(self._max_chunk_chars, int)
            or self._max_chunk_chars < 1
        ):
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_budget_invalid"
            )
        plan = Gate3ProjectionFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        )._create_structural_plan(document_id=document_id, context=context)
        projection = plan.projection
        source_content = str(projection["model_view"]["content"])
        mappings = list(projection["target_mappings"])
        mapping_by_alias = {
            str(item["target_alias"]): item for item in mappings
        }
        source_visible_aliases = _visible_aliases(source_content)
        if set(source_visible_aliases) != set(mapping_by_alias):
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_projection_mapping_invalid"
            )
        mapping_order = {
            alias: index for index, alias in enumerate(source_visible_aliases)
        }
        binding = copy.deepcopy(projection["canonical_binding"])

        if len(source_content) <= self._max_chunk_chars:
            chunks = [
                _make_chunk(
                    binding=binding,
                    ordinal=1,
                    structural_kind="whole_document",
                    structural_scope={
                        "container_refs": [],
                        "node_refs": [],
                        "row_start": None,
                        "row_end": None,
                    },
                    ancestor_headings=(),
                    context_content="",
                    target_content=source_content,
                    mapping_by_alias=mapping_by_alias,
                    mapping_order=mapping_order,
                    max_chunk_chars=self._max_chunk_chars,
                    repeated_table_header=False,
                    repeated_table_notes=False,
                )
            ]
        else:
            chunks = _chunk_rendered_units(
                units=plan.units,
                binding=binding,
                mapping_by_alias=mapping_by_alias,
                mapping_order=mapping_order,
                max_chunk_chars=self._max_chunk_chars,
            )

        result = {
            "schema_version": GATE3_STRUCTURAL_CHUNK_SET_SCHEMA_VERSION,
            "canonical_binding": binding,
            "budget": {
                "measure": "model_view_chars",
                "max_chunk_chars": self._max_chunk_chars,
            },
            "chunks": chunks,
            "coverage": _coverage(
                projection=projection,
                chunks=chunks,
            ),
        }
        _validate_chunk_set(result, projection=projection)
        return result


def _chunk_rendered_units(
    *,
    units,
    binding: dict[str, str],
    mapping_by_alias: dict[str, dict[str, Any]],
    mapping_order: dict[str, int],
    max_chunk_chars: int,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    pending_units: list[Any] = []
    pending_headings: tuple[str, ...] | None = None
    pending_prefix_context: list[str] = []
    carried_context: list[str] = []

    def flush_pending() -> None:
        nonlocal pending_headings
        if not pending_units:
            return
        target_content = _join_blocks([unit.content for unit in pending_units])
        context_content = _join_blocks(
            [
                *pending_prefix_context,
                _headings_context(pending_headings or ()),
            ]
        )
        chunk = _make_chunk(
            binding=binding,
            ordinal=len(chunks) + 1,
            structural_kind="structural_blocks",
            structural_scope={
                "container_refs": _ordered_unique(
                    unit.container_id for unit in pending_units if unit.container_id
                ),
                "node_refs": _ordered_unique(
                    unit.node_id for unit in pending_units if unit.node_id
                ),
                "row_start": None,
                "row_end": None,
            },
            ancestor_headings=pending_headings or (),
            context_content=context_content,
            target_content=target_content,
            mapping_by_alias=mapping_by_alias,
            mapping_order=mapping_order,
            max_chunk_chars=max_chunk_chars,
            repeated_table_header=False,
            repeated_table_notes=False,
        )
        chunks.append(chunk)
        pending_units.clear()
        pending_prefix_context.clear()
        pending_headings = None

    for unit in units:
        if not _visible_aliases(unit.content):
            flush_pending()
            carried_context.append(unit.content)
            continue

        if unit.table is not None:
            flush_pending()
            table_chunks = _chunk_table_unit(
                unit=unit,
                prefix_context=tuple(carried_context),
                binding=binding,
                first_ordinal=len(chunks) + 1,
                mapping_by_alias=mapping_by_alias,
                mapping_order=mapping_order,
                max_chunk_chars=max_chunk_chars,
            )
            chunks.extend(table_chunks)
            carried_context.clear()
            continue

        if pending_units and pending_headings != unit.ancestor_headings:
            flush_pending()
        if not pending_units:
            pending_headings = unit.ancestor_headings
            pending_prefix_context.extend(carried_context)
            carried_context.clear()
        candidate_units = [*pending_units, unit]
        candidate_target = _join_blocks(
            [candidate.content for candidate in candidate_units]
        )
        candidate_context = _join_blocks(
            [
                *pending_prefix_context,
                _headings_context(unit.ancestor_headings),
            ]
        )
        candidate_model = _compose_model_content(
            context_content=candidate_context,
            target_content=candidate_target,
        )
        if len(candidate_model) <= max_chunk_chars:
            pending_units.append(unit)
            continue
        flush_pending()
        pending_headings = unit.ancestor_headings
        single_model = _compose_model_content(
            context_content=_join_blocks(
                [
                    *pending_prefix_context,
                    _headings_context(unit.ancestor_headings),
                ]
            ),
            target_content=unit.content,
        )
        if len(single_model) > max_chunk_chars:
            _raise_indivisible(
                unit_kind="node",
                required_chars=len(single_model),
                max_chunk_chars=max_chunk_chars,
            )
        pending_units.append(unit)
    flush_pending()
    if carried_context:
        _append_context_only_chunks(
            chunks=chunks,
            context_blocks=carried_context,
            binding=binding,
            mapping_by_alias=mapping_by_alias,
            mapping_order=mapping_order,
            max_chunk_chars=max_chunk_chars,
        )
    if not chunks:
        _raise_indivisible(
            unit_kind="document_structure",
            required_chars=0,
            max_chunk_chars=max_chunk_chars,
        )
    return chunks


def _chunk_table_unit(
    *,
    unit,
    prefix_context: tuple[str, ...],
    binding: dict[str, str],
    first_ordinal: int,
    mapping_by_alias: dict[str, dict[str, Any]],
    mapping_order: dict[str, int],
    max_chunk_chars: int,
) -> list[dict[str, Any]]:
    whole_context = _join_blocks(
        [*prefix_context, _headings_context(unit.ancestor_headings)]
    )
    whole_model = _compose_model_content(
        context_content=whole_context,
        target_content=unit.content,
    )
    scope = {
        "container_refs": [unit.container_id] if unit.container_id else [],
        "node_refs": [unit.node_id] if unit.node_id else [],
        "row_start": None,
        "row_end": None,
    }
    if len(whole_model) <= max_chunk_chars:
        return [
            _make_chunk(
                binding=binding,
                ordinal=first_ordinal,
                structural_kind="whole_table",
                structural_scope=scope,
                ancestor_headings=unit.ancestor_headings,
                context_content=whole_context,
                target_content=unit.content,
                mapping_by_alias=mapping_by_alias,
                mapping_order=mapping_order,
                max_chunk_chars=max_chunk_chars,
                repeated_table_header=False,
                repeated_table_notes=False,
            )
        ]

    table = unit.table
    if not table.row_lines:
        _raise_indivisible(
            unit_kind="table_without_rows",
            required_chars=len(whole_model),
            max_chunk_chars=max_chunk_chars,
        )

    heading_has_target = bool(_visible_aliases("\n".join(table.heading_lines)))
    notes_have_target = bool(_visible_aliases("\n".join(table.note_lines)))
    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(table.row_lines):
        end = start
        chosen: tuple[str, str, bool, bool] | None = None
        while end < len(table.row_lines):
            candidate_end = end + 1
            (
                candidate_context,
                candidate_target,
                repeated_header,
                repeated_notes,
            ) = (
                _table_chunk_parts(
                    unit=unit,
                    row_start=start,
                    row_end=candidate_end,
                    prefix_context=prefix_context if start == 0 else (),
                    heading_has_target=heading_has_target,
                    notes_have_target=notes_have_target,
                )
            )
            candidate_model = _compose_model_content(
                context_content=candidate_context,
                target_content=candidate_target,
            )
            if len(candidate_model) > max_chunk_chars:
                break
            chosen = (
                candidate_context,
                candidate_target,
                repeated_header,
                repeated_notes,
            )
            end = candidate_end
        if chosen is None:
            required_context, required_target, _, _ = _table_chunk_parts(
                unit=unit,
                row_start=start,
                row_end=start + 1,
                prefix_context=prefix_context if start == 0 else (),
                heading_has_target=heading_has_target,
                notes_have_target=notes_have_target,
            )
            _raise_indivisible(
                unit_kind="table_row",
                required_chars=len(
                    _compose_model_content(
                        context_content=required_context,
                        target_content=required_target,
                    )
                ),
                max_chunk_chars=max_chunk_chars,
                row=start + 1,
            )
        context_content, target_content, repeated_header, repeated_notes = chosen
        chunks.append(
            _make_chunk(
                binding=binding,
                ordinal=first_ordinal + len(chunks),
                structural_kind="table_rows",
                structural_scope={
                    "container_refs": [unit.container_id]
                    if unit.container_id
                    else [],
                    "node_refs": [unit.node_id] if unit.node_id else [],
                    "row_start": start + 1,
                    "row_end": end,
                },
                ancestor_headings=unit.ancestor_headings,
                context_content=context_content,
                target_content=target_content,
                mapping_by_alias=mapping_by_alias,
                mapping_order=mapping_order,
                max_chunk_chars=max_chunk_chars,
                repeated_table_header=repeated_header,
                repeated_table_notes=repeated_notes,
            )
        )
        start = end
    return chunks


def _table_chunk_parts(
    *,
    unit,
    row_start: int,
    row_end: int,
    prefix_context: tuple[str, ...],
    heading_has_target: bool,
    notes_have_target: bool,
) -> tuple[str, str, bool, bool]:
    table = unit.table
    first = row_start == 0
    context_blocks = [*prefix_context, *unit.ancestor_headings]
    target_blocks: list[str] = []

    heading_text = "\n".join(table.heading_lines)
    if first and heading_has_target:
        target_blocks.append(heading_text)
    else:
        context_blocks.append(_strip_aliases(heading_text))

    notes_text = "\n".join(table.note_lines)
    if first and notes_have_target:
        target_blocks.append(notes_text)
    elif notes_text:
        context_blocks.append(_strip_aliases(notes_text))

    if table.grid_header_lines:
        context_blocks.append("\n".join(table.grid_header_lines))

    repeated_header = bool(table.header_present and row_start > 0)
    if repeated_header:
        context_blocks.append(_strip_aliases(table.row_lines[0]))

    target_blocks.append("\n".join(table.row_lines[row_start:row_end]))
    return (
        _join_blocks(context_blocks),
        _join_blocks(target_blocks),
        repeated_header,
        bool(notes_text and not (first and notes_have_target)),
    )


def _append_context_only_chunks(
    *,
    chunks: list[dict[str, Any]],
    context_blocks: list[str],
    binding: dict[str, str],
    mapping_by_alias: dict[str, dict[str, Any]],
    mapping_order: dict[str, int],
    max_chunk_chars: int,
) -> None:
    """Preserve terminal structure only when no later target can carry it."""

    pending: list[str] = []
    for block in context_blocks:
        candidate = _join_blocks([*pending, block])
        if len(_compose_model_content(context_content="", target_content=candidate)) <= max_chunk_chars:
            pending.append(block)
            continue
        if not pending:
            _raise_indivisible(
                unit_kind="terminal_document_structure",
                required_chars=len(block.rstrip()) + 1,
                max_chunk_chars=max_chunk_chars,
            )
        _append_context_only_chunk(
            chunks=chunks,
            content=_join_blocks(pending),
            binding=binding,
            mapping_by_alias=mapping_by_alias,
            mapping_order=mapping_order,
            max_chunk_chars=max_chunk_chars,
        )
        pending = [block]
    if pending:
        _append_context_only_chunk(
            chunks=chunks,
            content=_join_blocks(pending),
            binding=binding,
            mapping_by_alias=mapping_by_alias,
            mapping_order=mapping_order,
            max_chunk_chars=max_chunk_chars,
        )


def _append_context_only_chunk(
    *,
    chunks: list[dict[str, Any]],
    content: str,
    binding: dict[str, str],
    mapping_by_alias: dict[str, dict[str, Any]],
    mapping_order: dict[str, int],
    max_chunk_chars: int,
) -> None:
    chunks.append(
        _make_chunk(
            binding=binding,
            ordinal=len(chunks) + 1,
            structural_kind="structural_blocks",
            structural_scope={
                "container_refs": [],
                "node_refs": [],
                "row_start": None,
                "row_end": None,
            },
            ancestor_headings=(),
            context_content="",
            target_content=content,
            mapping_by_alias=mapping_by_alias,
            mapping_order=mapping_order,
            max_chunk_chars=max_chunk_chars,
            repeated_table_header=False,
            repeated_table_notes=False,
        )
    )


def _make_chunk(
    *,
    binding: dict[str, str],
    ordinal: int,
    structural_kind: str,
    structural_scope: dict[str, Any],
    ancestor_headings: tuple[str, ...],
    context_content: str,
    target_content: str,
    mapping_by_alias: dict[str, dict[str, Any]],
    mapping_order: dict[str, int],
    max_chunk_chars: int,
    repeated_table_header: bool,
    repeated_table_notes: bool,
) -> dict[str, Any]:
    context_content = _strip_aliases(context_content)
    if _visible_aliases(context_content):
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_context_target_leak"
        )
    model_content = _compose_model_content(
        context_content=context_content,
        target_content=target_content,
    )
    if len(model_content) > max_chunk_chars:
        _raise_indivisible(
            unit_kind=structural_kind,
            required_chars=len(model_content),
            max_chunk_chars=max_chunk_chars,
        )
    visible_aliases = _visible_aliases(model_content)
    if len(visible_aliases) != len(set(visible_aliases)):
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_working_target_duplicate"
        )
    unknown = [alias for alias in visible_aliases if alias not in mapping_by_alias]
    if unknown:
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_target_unknown"
        )
    ordered_aliases = sorted(visible_aliases, key=mapping_order.__getitem__)
    if ordered_aliases != visible_aliases:
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_target_order_changed"
        )
    target_mappings = [
        copy.deepcopy(mapping_by_alias[alias]) for alias in ordered_aliases
    ]
    identity_material = {
        "schema_version": GATE3_STRUCTURAL_CHUNK_SET_SCHEMA_VERSION,
        "canonical_binding": binding,
        "ordinal": ordinal,
        "structural_scope": structural_scope,
        "target_aliases": ordered_aliases,
        "model_view_sha256": hashlib.sha256(
            model_content.encode("utf-8")
        ).hexdigest(),
    }
    chunk_id = "g3chunk_" + hashlib.sha256(
        json.dumps(
            identity_material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    normalized_target = target_content.rstrip() + "\n" if target_content else ""
    return {
        "chunk_id": chunk_id,
        "ordinal": ordinal,
        "canonical_binding": copy.deepcopy(binding),
        "structural_kind": structural_kind,
        "structural_scope": copy.deepcopy(structural_scope),
        "context_policy": {
            "context_only_target_aliases": 0,
            "data_row_overlap": 0,
            "ancestor_headings": len(ancestor_headings),
            "repeated_table_header": repeated_table_header,
            "repeated_table_notes": repeated_table_notes,
        },
        "model_view": {
            "media_type": "text/markdown",
            "content": model_content,
        },
        "target_mappings": target_mappings,
        "metrics": {
            "model_view_chars": len(model_content),
            "target_count": len(target_mappings),
            "context_overhead_chars": len(model_content) - len(normalized_target),
        },
    }


def _coverage(
    *,
    projection: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    source_aliases = [
        alias
        for alias in _visible_aliases(projection["model_view"]["content"])
    ]
    chunk_aliases = [
        str(mapping["target_alias"])
        for chunk in chunks
        for mapping in chunk["target_mappings"]
    ]
    counts = Counter(chunk_aliases)
    lost = [alias for alias in source_aliases if counts[alias] == 0]
    duplicated = [alias for alias in source_aliases if counts[alias] > 1]
    return {
        "eligible_targets": len(source_aliases),
        "working_targets": len(chunk_aliases),
        "lost_targets": len(lost),
        "duplicated_working_targets": len(duplicated),
        "context_only_target_aliases": 0,
        "data_row_overlap": 0,
        "target_order_preserved": chunk_aliases == source_aliases,
    }


def _validate_chunk_set(
    chunk_set: dict[str, Any],
    *,
    projection: dict[str, Any],
) -> None:
    chunks = chunk_set["chunks"]
    if not chunks:
        raise Gate3StructuralChunkError("gate3_structural_chunk_empty")
    binding = projection["canonical_binding"]
    budget = chunk_set["budget"]["max_chunk_chars"]
    if [chunk["ordinal"] for chunk in chunks] != list(
        range(1, len(chunks) + 1)
    ):
        raise Gate3StructuralChunkError("gate3_structural_chunk_order_invalid")
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_identity_duplicate"
        )
    for chunk in chunks:
        if chunk["canonical_binding"] != binding:
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_document_mixing"
            )
        content = chunk["model_view"]["content"]
        if len(content) > budget or len(content) != chunk["metrics"][
            "model_view_chars"
        ]:
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_budget_exceeded"
            )
        aliases = _visible_aliases(content)
        mapped = [
            mapping["target_alias"] for mapping in chunk["target_mappings"]
        ]
        if aliases != mapped:
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_mapping_visibility_mismatch"
            )
    coverage = chunk_set["coverage"]
    if coverage != {
        "eligible_targets": len(projection["target_mappings"]),
        "working_targets": len(projection["target_mappings"]),
        "lost_targets": 0,
        "duplicated_working_targets": 0,
        "context_only_target_aliases": 0,
        "data_row_overlap": 0,
        "target_order_preserved": True,
    }:
        raise Gate3StructuralChunkError(
            "gate3_structural_chunk_coverage_invalid"
        )
    row_end_by_node: dict[str, int] = {}
    for chunk in chunks:
        if chunk["structural_kind"] != "table_rows":
            continue
        scope = chunk["structural_scope"]
        node_ref = str(scope["node_refs"][0])
        expected_start = row_end_by_node.get(node_ref, 0) + 1
        if scope["row_start"] != expected_start or scope["row_end"] < expected_start:
            raise Gate3StructuralChunkError(
                "gate3_structural_chunk_row_overlap_or_gap"
            )
        row_end_by_node[node_ref] = int(scope["row_end"])


def _compose_model_content(*, context_content: str, target_content: str) -> str:
    context = context_content.strip()
    target = target_content.strip()
    if context:
        return (
            "## Structural context (context only)\n\n"
            + context
            + "\n\n## Target content\n\n"
            + target
            + "\n"
        )
    return target + "\n" if target else ""


def _headings_context(headings: tuple[str, ...]) -> str:
    return _join_blocks(list(headings))


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block.strip() for block in blocks if block.strip())


def _strip_aliases(content: str) -> str:
    return _ALIAS_RE.sub("", content)


def _visible_aliases(content: str) -> list[str]:
    return _ALIAS_RE.findall(content)


def _ordered_unique(values) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _raise_indivisible(
    *,
    unit_kind: str,
    required_chars: int,
    max_chunk_chars: int,
    row: int | None = None,
) -> None:
    details: dict[str, Any] = {
        "unit_kind": unit_kind,
        "required_chars": required_chars,
        "max_chunk_chars": max_chunk_chars,
    }
    if row is not None:
        details["row"] = row
    raise Gate3StructuralChunkError(
        "gate3_structural_chunk_indivisible_unit_exceeds_budget",
        details=details,
    )


__all__ = [
    "DEFAULT_MAX_CHUNK_CHARS",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_STRUCTURAL_CHUNK_SET_SCHEMA_VERSION",
    "Gate3StructuralChunkError",
    "Gate3StructuralChunkFactory",
]
