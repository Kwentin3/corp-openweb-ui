"""Gate 3 LLM-friendly projection over the public canonical reader."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .canonical_artifact import validate_canonical_artifact
from .canonical_store import CanonicalReadEnvelope, CanonicalReaderFactory


GATE3_PROJECTION_SCHEMA_VERSION = "broker_reports_gate3_projection_v1"
FACTORY_REQUIRED = (
    "Gate3ProjectionFactory.create is the only Gate3ProjectionV1 construction "
    "entrypoint and must consume CanonicalReaderFactory.create output"
)
FORBIDDEN = (
    "Projection must not read source files, parser payloads, private evidence, "
    "ArtifactStore internals, provider output or financial semantics"
)

_TEXT_NODE_TYPES = {"HEADING", "TEXT", "NOTE"}
_BREAK_NODE_TYPES = {"PAGE_BREAK", "SHEET_BREAK"}
_ISSUE_NODE_TYPES = {"CONFLICT", "AMBIGUITY"}


class Gate3ProjectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _RenderedTablePlan:
    heading_lines: tuple[str, ...]
    grid_header_lines: tuple[str, ...]
    row_lines: tuple[str, ...]
    note_lines: tuple[str, ...]
    header_present: bool


@dataclass(frozen=True)
class _RenderedStructuralUnit:
    unit_kind: str
    container_id: str | None
    ancestor_headings: tuple[str, ...]
    node_id: str | None
    node_type: str | None
    content: str
    table: _RenderedTablePlan | None = None


@dataclass(frozen=True)
class _ProjectionRenderPlan:
    projection: dict[str, Any]
    units: tuple[_RenderedStructuralUnit, ...]


class Gate3ProjectionFactory:
    """Build one deterministic, non-persisted projection of an active version.

    Gate 3 adds a separate semantic annotation layer; it never mutates the
    CanonicalArtifactV1 read here.
    """

    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if not document_id:
            raise Gate3ProjectionError("gate3_projection_document_id_required")
        envelope = CanonicalReaderFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create().read_active_envelope(document_id, context)
        return _render_projection(document_id=document_id, envelope=envelope)

    def _create_structural_plan(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> _ProjectionRenderPlan:
        """Package-internal exact render plan for the structural chunk owner."""

        if not document_id:
            raise Gate3ProjectionError("gate3_projection_document_id_required")
        envelope = CanonicalReaderFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create().read_active_envelope(document_id, context)
        return _render_projection_plan(document_id=document_id, envelope=envelope)


class _AliasIssuer:
    def __init__(self) -> None:
        self._next = 1
        self.mappings: list[dict[str, Any]] = []

    def issue(self, target: dict[str, Any]) -> str:
        alias = f"t{self._next:03d}"
        self._next += 1
        self.mappings.append(
            {"target_alias": alias, "canonical_target": dict(target)}
        )
        return alias


def _render_projection(
    *,
    document_id: str,
    envelope: CanonicalReadEnvelope,
) -> dict[str, Any]:
    return _render_projection_plan(
        document_id=document_id,
        envelope=envelope,
    ).projection


def _render_projection_plan(
    *,
    document_id: str,
    envelope: CanonicalReadEnvelope,
) -> _ProjectionRenderPlan:
    artifact = envelope.artifact
    validation = validate_canonical_artifact(artifact)
    if not validation["passed"]:
        raise Gate3ProjectionError("gate3_projection_canonical_invalid")
    if envelope.version_status != "ACTIVE":
        raise Gate3ProjectionError("gate3_projection_canonical_not_active")
    if str(artifact.get("artifact_id") or "") != envelope.canonical_version_id:
        raise Gate3ProjectionError("gate3_projection_canonical_binding_mismatch")

    containers = list(artifact.get("containers") or [])
    nodes = list(artifact.get("nodes") or [])
    root_ref = str(artifact.get("root_container_ref") or "")
    containers_by_id = {
        str(container.get("container_id") or ""): container
        for container in containers
    }
    root = containers_by_id.get(root_ref)
    if root is None:
        raise Gate3ProjectionError("gate3_projection_root_required")

    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for container in containers:
        children[container.get("parent_container_ref")].append(container)
    nodes_by_container: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        nodes_by_container[str(node.get("container_ref") or "")].append(node)

    aliases = _AliasIssuer()
    lines: list[str] = []
    units: list[_RenderedStructuralUnit] = []
    visited_containers: set[str] = set()
    visited_nodes: set[str] = set()
    represented_issue_refs: set[str] = set()

    def append_container(
        container: dict[str, Any],
        depth: int,
        ancestor_headings: tuple[str, ...],
    ) -> None:
        container_id = str(container.get("container_id") or "")
        if container_id in visited_containers:
            raise Gate3ProjectionError("gate3_projection_container_cycle")
        visited_containers.add(container_id)
        container_heading = _container_heading(container, depth)
        current_headings = (*ancestor_headings, container_heading)
        _append_block(lines, [container_heading])

        for node in sorted(
            nodes_by_container.get(container_id, []),
            key=lambda item: (int(item.get("order") or 0), str(item.get("node_id") or "")),
        ):
            visited_nodes.add(str(node.get("node_id") or ""))
            represented_issue_refs.update(
                str(value) for value in node.get("issue_refs") or []
            )
            unit_start = len(lines)
            table_plan = _append_node(
                lines,
                node=node,
                depth=depth,
                aliases=aliases,
            )
            units.append(
                _RenderedStructuralUnit(
                    unit_kind="table" if table_plan is not None else "node",
                    container_id=container_id,
                    ancestor_headings=current_headings,
                    node_id=str(node.get("node_id") or ""),
                    node_type=str(node.get("node_type") or ""),
                    content=_unit_content(lines[unit_start:]),
                    table=table_plan,
                )
            )

        for child in sorted(
            children.get(container_id, []),
            key=lambda item: (
                int(item.get("order") or 0),
                str(item.get("container_id") or ""),
            ),
        ):
            append_container(child, depth + 1, current_headings)

    append_container(root, 0, ())
    if visited_containers != set(containers_by_id):
        raise Gate3ProjectionError("gate3_projection_container_tree_incomplete")
    node_ids = {str(node.get("node_id") or "") for node in nodes}
    if visited_nodes != node_ids:
        raise Gate3ProjectionError("gate3_projection_node_traversal_incomplete")

    remaining_issues = [
        issue
        for issue in artifact.get("issues") or []
        if str(issue.get("issue_id") or "") not in represented_issue_refs
    ]
    if remaining_issues:
        unit_start = len(lines)
        _append_block(lines, ["## Canonical notices"])
        for issue in remaining_issues:
            lines.append(
                "> {0} ({1}): {2}".format(
                    _markdown_text(issue.get("issue_type")),
                    _markdown_text(issue.get("severity")),
                    _markdown_text(issue.get("summary")),
                )
            )
        units.append(
            _RenderedStructuralUnit(
                unit_kind="canonical_notices",
                container_id=root_ref,
                ancestor_headings=(_container_heading(root, 0),),
                node_id=None,
                node_type=None,
                content=_unit_content(lines[unit_start:]),
            )
        )

    content = "\n".join(lines).rstrip() + "\n"
    projection = {
        "schema_version": GATE3_PROJECTION_SCHEMA_VERSION,
        "canonical_binding": {
            "document_id": document_id,
            "canonical_version_id": envelope.canonical_version_id,
        },
        "model_view": {"media_type": "text/markdown", "content": content},
        "target_mappings": aliases.mappings,
    }
    _validate_mappings(projection, artifact)
    return _ProjectionRenderPlan(projection=projection, units=tuple(units))


def _append_node(
    lines: list[str],
    *,
    node: dict[str, Any],
    depth: int,
    aliases: _AliasIssuer,
) -> _RenderedTablePlan | None:
    node_type = str(node.get("node_type") or "")
    node_id = str(node.get("node_id") or "")
    content = node.get("content") or {}

    if node_type in _TEXT_NODE_TYPES:
        alias = aliases.issue({"kind": "node", "node_id": node_id})
        text = _markdown_text(content.get("text"))
        if node_type == "HEADING":
            source_level = max(1, min(6, int(content.get("level") or 1)))
            level = min(6, depth + source_level + 1)
            _append_block(lines, [f"{'#' * level} [{alias}] {text}"])
        elif node_type == "NOTE":
            _append_block(lines, [f"> [{alias}] Note: {text}"])
        else:
            _append_block(lines, [f"[{alias}] {text}"])
        _append_links(lines, content.get("links") or [])
        return None

    if node_type == "LIST":
        rendered: list[str] = []
        for item_index, item in enumerate(content.get("items") or []):
            alias = aliases.issue(
                {"kind": "list_item", "node_id": node_id, "item_index": item_index}
            )
            prefix = "1." if item.get("ordered") else "-"
            level = max(0, int(item.get("level") or 0))
            rendered.append(
                f"{'  ' * level}{prefix} [{alias}] {_markdown_text(item.get('text'))}"
            )
        if rendered:
            _append_block(lines, rendered)
        return None

    if node_type == "TABLE":
        return _append_table(lines, node=node, depth=depth, aliases=aliases)

    if node_type in _BREAK_NODE_TYPES:
        label = "Page break" if node_type == "PAGE_BREAK" else "Sheet break"
        _append_block(lines, [f"--- {label} ---"])
        return None

    if node_type in _ISSUE_NODE_TYPES:
        label = "Conflict" if node_type == "CONFLICT" else "Ambiguity"
        _append_block(
            lines,
            [f"> {label}: {_markdown_text(content.get('summary'))}"],
        )
        return None

    raise Gate3ProjectionError("gate3_projection_node_type_unsupported")


def _append_table(
    lines: list[str],
    *,
    node: dict[str, Any],
    depth: int,
    aliases: _AliasIssuer,
) -> _RenderedTablePlan:
    node_id = str(node.get("node_id") or "")
    content = node.get("content") or {}
    title = content.get("title")
    notes = list(content.get("notes") or [])
    node_alias = None
    if title is not None or notes:
        node_alias = aliases.issue({"kind": "node", "node_id": node_id})

    heading_level = min(6, depth + 2)
    heading = f"{'#' * heading_level} "
    if title is not None:
        heading += f"[{node_alias}] {_markdown_text(title)}"
    else:
        heading += "Table"
    _append_block(lines, [heading])

    cells_by_coordinate: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in content.get("cells") or []:
        coordinate = (int(cell.get("row") or 0), int(cell.get("column") or 0))
        if coordinate[0] < 1 or coordinate[1] < 1:
            raise Gate3ProjectionError("gate3_projection_cell_coordinate_invalid")
        if coordinate in cells_by_coordinate:
            raise Gate3ProjectionError("gate3_projection_cell_coordinate_duplicate")
        cells_by_coordinate[coordinate] = cell
    rows_with_cells = {row for row, _column in cells_by_coordinate}

    declared_rows = []
    header = list(content.get("header") or [])
    if header:
        declared_rows.append(header)
    declared_rows.extend(list(row) for row in content.get("rows") or [])
    row_count = max(
        len(declared_rows),
        max((coordinate[0] for coordinate in cells_by_coordinate), default=0),
    )
    column_count = max(
        max((len(row) for row in declared_rows), default=0),
        max((coordinate[1] for coordinate in cells_by_coordinate), default=0),
    )

    grid_header_lines: list[str] = []
    row_lines: list[str] = []
    if row_count and column_count:
        grid_header_lines = [
            "| row | "
            + " | ".join(f"column {column}" for column in range(1, column_count + 1))
            + " |",
            "| --- | " + " | ".join("---" for _ in range(column_count)) + " |",
        ]
        for row in range(1, row_count + 1):
            if row in rows_with_cells:
                row_alias = aliases.issue(
                    {"kind": "table_row", "node_id": node_id, "row": row}
                )
                row_label = f"[{row_alias}] "
            else:
                row_label = ""
            row_label += "header" if header and row == 1 else str(row)
            rendered_cells: list[str] = []
            for column in range(1, column_count + 1):
                cell = cells_by_coordinate.get((row, column))
                if cell is None:
                    fallback = (
                        declared_rows[row - 1][column - 1]
                        if row <= len(declared_rows)
                        and column <= len(declared_rows[row - 1])
                        else ""
                    )
                    rendered_cells.append(_markdown_text(fallback))
                    continue
                cell_alias = aliases.issue(
                    {
                        "kind": "table_cell",
                        "node_id": node_id,
                        "row": row,
                        "column": column,
                    }
                )
                rendered_cells.append(
                    f"[{cell_alias}] {_markdown_text(_cell_display_value(cell))}"
                )
            row_lines.append(
                "| " + row_label + " | " + " | ".join(rendered_cells) + " |"
            )
        _append_block(lines, [*grid_header_lines, *row_lines])

    rendered_notes: list[str] = []
    if notes:
        for index, note in enumerate(notes):
            prefix = f"[{node_alias}] " if title is None and index == 0 else ""
            rendered_notes.append(f"> {prefix}Table note: {_markdown_text(note)}")
        _append_block(lines, rendered_notes)
    return _RenderedTablePlan(
        heading_lines=(heading,),
        grid_header_lines=tuple(grid_header_lines),
        row_lines=tuple(row_lines),
        note_lines=tuple(rendered_notes),
        header_present=bool(header),
    )


def _append_links(lines: list[str], links: list[dict[str, Any]]) -> None:
    if not links:
        return
    rendered = [
        f"  - Link: {_markdown_text(link.get('text'))} -> "
        f"{_markdown_text(link.get('target'))}"
        for link in links
    ]
    _append_block(lines, rendered)


def _container_heading(container: dict[str, Any], depth: int) -> str:
    container_type = str(container.get("container_type") or "")
    metadata = container.get("metadata") or {}
    label = container_type.title()
    if container_type == "PAGE":
        label = f"Page {int(metadata.get('page_number') or 0)}"
    elif container_type == "SECTION":
        label = f"Section {int(metadata.get('section_index') or 0)}"
    elif container_type == "SHEET":
        sheet_name = metadata.get("sheet_name")
        label = (
            f"Sheet: {_markdown_text(sheet_name)}"
            if sheet_name is not None
            else f"Sheet {int(metadata.get('sheet_index') or 0)}"
        )
    level = min(6, depth + 1)
    return f"{'#' * level} {label}"


def _cell_display_value(cell: dict[str, Any]) -> Any:
    for field in ("displayed_value", "cached_value", "value", "raw_value"):
        value = cell.get(field)
        if value is not None:
            return value
    return ""


def _markdown_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (
        text.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("|", "\\|")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def _append_block(lines: list[str], block: list[str]) -> None:
    if not block:
        return
    if lines and lines[-1] != "":
        lines.append("")
    lines.extend(block)


def _unit_content(lines: list[str]) -> str:
    start = 0
    end = len(lines)
    while start < end and lines[start] == "":
        start += 1
    while end > start and lines[end - 1] == "":
        end -= 1
    return "\n".join(lines[start:end]).rstrip() + "\n" if start < end else ""


def _validate_mappings(projection: dict[str, Any], artifact: dict[str, Any]) -> None:
    nodes = {
        str(node.get("node_id") or ""): node for node in artifact.get("nodes") or []
    }
    aliases: set[str] = set()
    targets: set[tuple[Any, ...]] = set()
    content = str((projection.get("model_view") or {}).get("content") or "")
    visible_alias_counts = Counter(
        re.findall(r"(?<!\\)\[(t[0-9]{3,})\]", content)
    )
    table_coordinates: dict[str, set[tuple[int, int]]] = {}
    table_rows: dict[str, set[int]] = {}
    for node_id, node in nodes.items():
        if str(node.get("node_type") or "") != "TABLE":
            continue
        coordinates = {
            (int(cell.get("row") or 0), int(cell.get("column") or 0))
            for cell in (node.get("content") or {}).get("cells") or []
        }
        table_coordinates[node_id] = coordinates
        table_rows[node_id] = {row for row, _column in coordinates}
    for mapping in projection.get("target_mappings") or []:
        alias = str(mapping.get("target_alias") or "")
        if alias in aliases or visible_alias_counts[alias] != 1:
            raise Gate3ProjectionError("gate3_projection_alias_not_unique")
        aliases.add(alias)
        target = mapping.get("canonical_target") or {}
        node = nodes.get(str(target.get("node_id") or ""))
        if node is None:
            raise Gate3ProjectionError("gate3_projection_target_node_missing")
        node_type = str(node.get("node_type") or "")
        kind = str(target.get("kind") or "")
        key: tuple[Any, ...]
        if kind == "node":
            if node_type in _BREAK_NODE_TYPES | _ISSUE_NODE_TYPES:
                raise Gate3ProjectionError("gate3_projection_target_node_forbidden")
            key = (kind, target["node_id"])
        elif kind == "list_item":
            item_index = int(target.get("item_index", -1))
            if node_type != "LIST" or not 0 <= item_index < len(
                (node.get("content") or {}).get("items") or []
            ):
                raise Gate3ProjectionError("gate3_projection_list_item_unresolved")
            key = (kind, target["node_id"], item_index)
        elif kind == "table_row":
            row = int(target.get("row") or 0)
            if node_type != "TABLE" or row not in table_rows.get(
                str(target.get("node_id") or ""), set()
            ):
                raise Gate3ProjectionError("gate3_projection_table_row_unresolved")
            key = (kind, target["node_id"], row)
        elif kind == "table_cell":
            coordinate = (
                int(target.get("row") or 0),
                int(target.get("column") or 0),
            )
            if node_type != "TABLE" or coordinate not in table_coordinates.get(
                str(target.get("node_id") or ""), set()
            ):
                raise Gate3ProjectionError("gate3_projection_table_cell_unresolved")
            key = (kind, target["node_id"], *coordinate)
        else:
            raise Gate3ProjectionError("gate3_projection_target_kind_unsupported")
        if key in targets:
            raise Gate3ProjectionError("gate3_projection_target_duplicate")
        targets.add(key)
    if set(visible_alias_counts) != aliases:
        raise Gate3ProjectionError("gate3_projection_alias_not_unique")


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_PROJECTION_SCHEMA_VERSION",
    "Gate3ProjectionError",
    "Gate3ProjectionFactory",
]
