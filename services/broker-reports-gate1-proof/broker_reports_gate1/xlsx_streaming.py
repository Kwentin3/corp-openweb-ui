"""Bounded XLSX CanonicalArtifactV1 normalization.

This module is the XLSX implementation owned by ``CanonicalNormalizer``.  It
streams existing OOXML worksheet parts, writes deterministic row-node staging
chunks, and never constructs a workbook DOM or full logical artifact in RAM.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from .canonical_artifact import (
    CANONICAL_ARTIFACT_SCHEMA_VERSION,
    FORBIDDEN_FIELDS,
    CanonicalArtifactError,
    canonical_node_has_machine_content,
)


XLSX_CANONICAL_PROFILE_VERSION = "xlsx_canonical_profile_v1"
XLSX_STREAMING_POLICY_VERSION = "xlsx_ooxml_streaming_v1"
FACTORY_REQUIRED = (
    "XLSX normalization is reachable only through "
    "CanonicalNormalizerFactory.create().build_xlsx_streaming"
)
FORBIDDEN = (
    "Workbook DOMs, pandas DataFrames, expanded empty ranges, duplicate style "
    "objects, and whole-artifact JSON serialization are forbidden"
)


@dataclass(frozen=True)
class XlsxStreamingConfig:
    chunk_rows: int = 256
    maximum_input_bytes: int = 16 * 1024 * 1024
    maximum_zip_parts: int = 4_096
    maximum_uncompressed_bytes: int = 256 * 1024 * 1024
    maximum_member_bytes: int = 128 * 1024 * 1024
    maximum_compression_ratio: float = 1_000.0

    def validate(self) -> None:
        if self.chunk_rows < 1 or self.chunk_rows > 4_096:
            raise CanonicalArtifactError("xlsx_chunk_rows_invalid")
        if (
            min(
                self.maximum_input_bytes,
                self.maximum_zip_parts,
                self.maximum_uncompressed_bytes,
                self.maximum_member_bytes,
            )
            < 1
        ):
            raise CanonicalArtifactError("xlsx_streaming_limit_invalid")


@dataclass(frozen=True)
class XlsxStreamingPlan:
    stage_root: Path
    tenant_id: str
    document_id: str
    source_artifact_ref: str
    source_sha256: str
    mime_type: str
    normalizer_version: str
    canonical_root_hash: str
    root_container_ref: str
    containers: tuple[dict[str, Any], ...]
    provenance: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, Any], ...]
    node_entries: tuple[dict[str, Any], ...]
    safe_metrics: dict[str, Any]

    def iter_nodes(self) -> Iterator[dict[str, Any]]:
        for entry in self.node_entries:
            inline = entry.get("inline_node")
            if isinstance(inline, dict):
                yield json.loads(json.dumps(inline))
                continue
            relative = str(entry.get("relative_path") or "")
            if (
                not relative
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
            ):
                raise CanonicalArtifactError("xlsx_staging_path_invalid")
            path = self.stage_root / relative
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise CanonicalArtifactError("xlsx_staging_chunk_hash_mismatch")
            payload = json.loads(data.decode("utf-8"))
            node = payload.get("node")
            if not isinstance(node, dict):
                raise CanonicalArtifactError("xlsx_staging_chunk_invalid")
            yield node

    def logical_envelope(self, *, created_at: str) -> dict[str, Any]:
        return {
            "artifact_id": f"canonical_{self.canonical_root_hash[:32]}_v1",
            "tenant_id": self.tenant_id,
            "schema_version": CANONICAL_ARTIFACT_SCHEMA_VERSION,
            "artifact_version": 1,
            "normalizer_version": self.normalizer_version,
            "previous_version_ref": None,
            "status": "validated",
            "created_at": created_at,
            "source": {
                "source_artifact_ref": self.source_artifact_ref,
                "source_format": "xlsx",
                "mime_type": self.mime_type,
                "source_sha256": self.source_sha256,
            },
            "root_container_ref": self.root_container_ref,
            "canonical_root_hash": self.canonical_root_hash,
            "containers": [],
            "nodes": [],
            "provenance": [],
            "issues": [],
            "chunks": [],
        }


class XlsxStreamingCanonicalAdapter:
    def __init__(self, *, config: XlsxStreamingConfig, normalizer_version: str) -> None:
        config.validate()
        if not normalizer_version:
            raise CanonicalArtifactError("canonical_normalizer_version_required")
        self.config = config
        self.normalizer_version = normalizer_version

    def build(
        self,
        *,
        source_path: Path,
        staging_root: Path,
        tenant_id: str,
        document_id: str,
        source_artifact_ref: str,
        source_sha256: str,
        mime_type: str,
    ) -> XlsxStreamingPlan:
        source_path = Path(source_path)
        staging_root = Path(staging_root)
        if not tenant_id or not document_id or not source_artifact_ref:
            raise CanonicalArtifactError("canonical_authenticated_scope_required")
        if (
            not source_path.is_file()
            or source_path.stat().st_size > self.config.maximum_input_bytes
        ):
            raise CanonicalArtifactError("xlsx_input_limit_exceeded")
        if _file_sha256(source_path) != source_sha256:
            raise CanonicalArtifactError("canonical_source_sha256_invalid")
        staging_root.mkdir(parents=True, exist_ok=True)
        state_path = staging_root / "streaming-plan.private.json"
        existing = _read_state(state_path)
        authority = {
            "source_sha256": source_sha256,
            "normalizer_version": self.normalizer_version,
            "profile_version": XLSX_CANONICAL_PROFILE_VERSION,
            "policy_version": XLSX_STREAMING_POLICY_VERSION,
            "chunk_rows": self.config.chunk_rows,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "source_artifact_ref": source_artifact_ref,
            "mime_type": mime_type,
        }
        if existing is not None:
            if existing.get("authority") != authority:
                raise CanonicalArtifactError("xlsx_streaming_resume_authority_drift")
            _verify_tracked_chunks(staging_root, existing.get("node_entries") or [])
            if existing.get("status") == "COMPLETE":
                return _plan_from_state(staging_root, existing)
        try:
            with ZipFile(source_path) as archive:
                inventory = _inventory(archive, self.config)
                if existing is None:
                    state = self._initialize_state(
                        archive=archive,
                        authority=authority,
                        inventory=inventory,
                        source_sha256=source_sha256,
                        source_artifact_ref=source_artifact_ref,
                    )
                    _write_state(state_path, state)
                else:
                    state = existing
                    if state.get("inventory_safe") != inventory["safe"]:
                        raise CanonicalArtifactError("xlsx_streaming_inventory_drift")
                self._stream_pending_sheets(archive, staging_root, state_path, state)
        except BadZipFile as exc:
            raise CanonicalArtifactError("bad_xlsx_zip") from exc
        state = _read_state(state_path)
        if state is None or state.get("status") != "COMPLETE":
            raise CanonicalArtifactError("xlsx_streaming_plan_incomplete")
        return _plan_from_state(staging_root, state)

    def _initialize_state(
        self,
        *,
        archive: ZipFile,
        authority: dict[str, Any],
        inventory: dict[str, Any],
        source_sha256: str,
        source_artifact_ref: str,
    ) -> dict[str, Any]:
        workbook = _workbook_inventory(archive)
        shared_strings = _shared_strings(archive)
        styles = _styles(archive)
        root_locator = {"kind": "xlsx_workbook"}
        root_provenance = _provenance(source_sha256, source_artifact_ref, root_locator)
        root_id = _container_id(source_sha256, "WORKBOOK", None, 0)
        containers: list[dict[str, Any]] = [
            {
                "container_id": root_id,
                "container_type": "WORKBOOK",
                "parent_container_ref": None,
                "order": 0,
                "source_refs": [root_provenance["provenance_id"]],
                "metadata": {
                    "xlsx_profile_version": XLSX_CANONICAL_PROFILE_VERSION,
                    "streaming_policy_version": XLSX_STREAMING_POLICY_VERSION,
                    "chunk_rows": self.config.chunk_rows,
                    "shared_strings": shared_strings,
                    "styles": styles,
                    "named_ranges": workbook["named_ranges"],
                    "calculation_properties": workbook["calculation_properties"],
                },
            }
        ]
        provenance = [root_provenance]
        sheets: list[dict[str, Any]] = []
        for sheet in workbook["sheets"]:
            locator = {"kind": "xlsx_sheet", "sheet_index": sheet["sheet_index"]}
            prov = _provenance(source_sha256, source_artifact_ref, locator)
            provenance.append(prov)
            container_id = _container_id(
                source_sha256, "SHEET", root_id, sheet["sheet_index"] - 1
            )
            metadata = _worksheet_metadata(archive, sheet)
            containers.append(
                {
                    "container_id": container_id,
                    "container_type": "SHEET",
                    "parent_container_ref": root_id,
                    "order": sheet["sheet_index"] - 1,
                    "source_refs": [prov["provenance_id"]],
                    "metadata": {
                        "sheet_index": sheet["sheet_index"],
                        "sheet_name": sheet["sheet_name"],
                        "sheet_visibility": sheet["sheet_visibility"],
                        "declared_dimension": metadata["declared_dimension"],
                        "merged_ranges": metadata["merged_ranges"],
                        "table_definitions": metadata["table_definitions"],
                        "links": metadata["links"],
                        "hidden_columns": metadata["hidden_columns"],
                        "shared_formulas": {},
                    },
                }
            )
            sheets.append({**sheet, **metadata, "container_id": container_id})
        issues = _feature_issues(
            archive,
            source_sha256=source_sha256,
            source_artifact_ref=source_artifact_ref,
            source_ref=root_provenance["provenance_id"],
        )
        return {
            "schema_version": "broker_reports_xlsx_streaming_state_v1",
            "status": "STREAMING",
            "authority": authority,
            "inventory_safe": inventory["safe"],
            "sheets": sheets,
            "completed_sheets": [],
            "containers": containers,
            "provenance": provenance,
            "issues": issues,
            "node_entries": [],
            "safe_metrics": {
                **inventory["safe"],
                "row_chunks": 0,
                "material_cells": 0,
                "blank_styled_cells": 0,
                "formulas": 0,
                "missing_cached_values": 0,
            },
        }

    def _stream_pending_sheets(
        self,
        archive: ZipFile,
        staging_root: Path,
        state_path: Path,
        state: dict[str, Any],
    ) -> None:
        completed = {int(value) for value in state.get("completed_sheets") or []}
        workbook_metadata = state["containers"][0]["metadata"]
        container_by_index = {
            int(item["metadata"]["sheet_index"]): item
            for item in state["containers"]
            if item.get("container_type") == "SHEET"
        }
        for sheet in state["sheets"]:
            sheet_index = int(sheet["sheet_index"])
            if sheet_index in completed:
                continue
            for path in staging_root.glob(f"sheet-{sheet_index:03d}-*.json*"):
                path.unlink()
            container = container_by_index[sheet_index]
            local_entries: list[dict[str, Any]] = []
            local_provenance: list[dict[str, Any]] = []
            node_order = 0
            if sheet_index > 1:
                locator = {"kind": "xlsx_sheet_boundary", "sheet_index": sheet_index}
                prov = _provenance(
                    state["authority"]["source_sha256"],
                    state["authority"]["source_artifact_ref"],
                    locator,
                )
                local_provenance.append(prov)
                content = {"boundary_ref": f"sheet:{sheet_index}"}
                node = _node(
                    source_sha256=state["authority"]["source_sha256"],
                    container_ref=sheet["container_id"],
                    order=node_order,
                    node_type="SHEET_BREAK",
                    content=content,
                    provenance_ref=prov["provenance_id"],
                )
                local_entries.append(_inline_entry(node))
                node_order += 1
            sheet_entries, sheet_provenance, stats, shared_formulas = (
                self._stream_sheet(
                    archive=archive,
                    staging_root=staging_root,
                    sheet=sheet,
                    start_order=node_order,
                    source_sha256=state["authority"]["source_sha256"],
                    source_artifact_ref=state["authority"]["source_artifact_ref"],
                    shared_strings=list(workbook_metadata.get("shared_strings") or []),
                    styles=list(workbook_metadata.get("styles") or []),
                )
            )
            local_entries.extend(sheet_entries)
            local_provenance.extend(sheet_provenance)
            container["metadata"]["actual_max_row"] = stats["maximum_row"]
            container["metadata"]["actual_max_column"] = stats["maximum_column"]
            container["metadata"]["shared_formulas"] = shared_formulas
            if _dimension_mismatch(
                str(container["metadata"].get("declared_dimension") or ""),
                stats["maximum_row"],
                stats["maximum_column"],
            ):
                state["issues"].append(
                    _issue(
                        source_sha256=state["authority"]["source_sha256"],
                        issue_type="PARTIAL",
                        severity="warning",
                        summary="DIMENSION_METADATA_INCONSISTENT",
                        source_ref=container["source_refs"][0],
                        subject=[sheet_index],
                    )
                )
            if stats["formulas"]:
                state["issues"].append(
                    _issue(
                        source_sha256=state["authority"]["source_sha256"],
                        issue_type="PARTIAL",
                        severity="warning",
                        summary="STALE_CALCULATION_POSSIBLE",
                        source_ref=container["source_refs"][0],
                        subject=[sheet_index],
                    )
                )
            if stats["missing_cached_values"]:
                state["issues"].append(
                    _issue(
                        source_sha256=state["authority"]["source_sha256"],
                        issue_type="PARTIAL",
                        severity="warning",
                        summary="MISSING_CACHED_VALUE",
                        source_ref=container["source_refs"][0],
                        subject=[sheet_index, stats["missing_cached_values"]],
                    )
                )
            if stats["unsupported_formulas"]:
                state["issues"].append(
                    _issue(
                        source_sha256=state["authority"]["source_sha256"],
                        issue_type="UNSUPPORTED",
                        severity="warning",
                        summary="UNSUPPORTED_XLSX_FEATURE",
                        source_ref=container["source_refs"][0],
                        subject=["array_or_dynamic_formula", sheet_index],
                    )
                )
            state["node_entries"].extend(local_entries)
            state["provenance"].extend(local_provenance)
            state["completed_sheets"].append(sheet_index)
            for key in (
                "row_chunks",
                "material_cells",
                "blank_styled_cells",
                "formulas",
                "missing_cached_values",
            ):
                state["safe_metrics"][key] += stats[key]
            _write_state(state_path, state)
        state["issues"] = _deduplicate_issues(state["issues"])
        root_hash = canonical_root_hash_from_streaming_parts(
            normalizer_version=self.normalizer_version,
            source_sha256=state["authority"]["source_sha256"],
            containers=state["containers"],
            nodes=_nodes_from_entries(staging_root, state["node_entries"]),
            provenance=state["provenance"],
            issues=state["issues"],
        )
        state["canonical_root_hash"] = root_hash
        state["root_container_ref"] = state["containers"][0]["container_id"]
        state["status"] = "COMPLETE"
        _write_state(state_path, state)

    def _stream_sheet(
        self,
        *,
        archive: ZipFile,
        staging_root: Path,
        sheet: dict[str, Any],
        start_order: int,
        source_sha256: str,
        source_artifact_ref: str,
        shared_strings: list[dict[str, Any]],
        styles: list[dict[str, Any]],
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], dict[str, int], dict[str, str]
    ]:
        entries: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        stats = {
            "row_chunks": 0,
            "material_cells": 0,
            "blank_styled_cells": 0,
            "formulas": 0,
            "missing_cached_values": 0,
            "unsupported_formulas": 0,
            "maximum_row": 0,
            "maximum_column": 0,
        }
        shared_formulas: dict[str, str] = {}
        batch: list[dict[str, Any]] = []
        batch_start: int | None = None
        batch_end: int | None = None
        node_order = start_order
        merge_ranges = [_a1_bounds(value) for value in sheet.get("merged_ranges") or []]
        links = {
            str(item["ref"]): str(item["link_ref"]) for item in sheet.get("links") or []
        }

        def flush() -> None:
            nonlocal batch, batch_start, batch_end, node_order
            if not batch:
                return
            locator = {
                "kind": "xlsx_row_chunk",
                "sheet_index": sheet["sheet_index"],
                "row_start": batch_start,
                "row_end": batch_end,
            }
            prov = _provenance(source_sha256, source_artifact_ref, locator)
            provenance.append(prov)
            cells = [cell for row in batch for cell in row["cells"]]
            blank_runs = [run for row in batch for run in row["blank_style_runs"]]
            for cell in cells:
                cell["source_refs"] = [prov["provenance_id"]]
            content = {
                "title": None,
                "header": [],
                "rows": [],
                "notes": [],
                "cells": cells,
                "metadata": {
                    "source_format": "xlsx",
                    "xlsx_profile_version": XLSX_CANONICAL_PROFILE_VERSION,
                    "row_start": batch_start,
                    "row_end": batch_end,
                    "blank_style_runs": blank_runs,
                },
            }
            node = _node(
                source_sha256=source_sha256,
                container_ref=sheet["container_id"],
                order=node_order,
                node_type="TABLE",
                content=content,
                provenance_ref=prov["provenance_id"],
            )
            relative = (
                f"sheet-{int(sheet['sheet_index']):03d}-node-{node_order:05d}.json"
            )
            data = _json_bytes({"node": node})
            _write_bytes_atomic(staging_root / relative, data)
            entries.append(
                {
                    "relative_path": relative,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "node_id": node["node_id"],
                    "container_ref": sheet["container_id"],
                    "order": node_order,
                    "node_type": "TABLE",
                }
            )
            stats["row_chunks"] += 1
            node_order += 1
            batch = []
            batch_start = None
            batch_end = None

        root: ET.Element | None = None
        path = str(sheet["path"])
        with archive.open(path) as stream:
            for event, element in ET.iterparse(stream, events=("start", "end")):
                if root is None and event == "start":
                    root = element
                if event != "end" or _local_name(element.tag) != "row":
                    continue
                row_number = _int_or(element.attrib.get("r"), stats["maximum_row"] + 1)
                row_hidden = _truthy(element.attrib.get("hidden"))
                material_cells: list[dict[str, Any]] = []
                blank_styled: list[dict[str, Any]] = []
                for cell_element in (
                    child for child in element if _local_name(child.tag) == "c"
                ):
                    parsed = _cell(
                        cell_element,
                        row_number=row_number,
                        row_hidden=row_hidden,
                        hidden_columns=sheet.get("hidden_columns") or [],
                        merge_ranges=merge_ranges,
                        shared_strings=shared_strings,
                        styles=styles,
                        links=links,
                        shared_formulas=shared_formulas,
                    )
                    stats["maximum_column"] = max(
                        stats["maximum_column"], parsed["column"]
                    )
                    if parsed["kind"] == "material":
                        material_cells.append(parsed["cell"])
                        stats["material_cells"] += 1
                        if parsed["cell"]["cell_type"] == "formula":
                            stats["formulas"] += 1
                            if parsed["cell"].get("cached_value") is None:
                                stats["missing_cached_values"] += 1
                            if parsed.get("unsupported_formula"):
                                stats["unsupported_formulas"] += 1
                    elif parsed["kind"] == "blank_styled":
                        blank_styled.append(parsed["cell"])
                        stats["blank_styled_cells"] += 1
                stats["maximum_row"] = max(stats["maximum_row"], row_number)
                if material_cells or blank_styled:
                    if batch_start is None:
                        batch_start = row_number
                    batch_end = row_number
                    batch.append(
                        {
                            "row": row_number,
                            "cells": material_cells,
                            "blank_style_runs": _blank_style_runs(blank_styled),
                        }
                    )
                if (
                    batch_start is not None
                    and row_number - batch_start + 1 >= self.config.chunk_rows
                ):
                    flush()
                element.clear()
                if root is not None:
                    root.clear()
        flush()
        if not entries:
            batch = [{"row": 0, "cells": [], "blank_style_runs": []}]
            batch_start = 0
            batch_end = 0
            flush()
        return entries, provenance, stats, shared_formulas


def canonical_root_hash_from_streaming_parts(
    *,
    normalizer_version: str,
    source_sha256: str,
    containers: list[dict[str, Any]],
    nodes: Iterator[dict[str, Any]],
    provenance: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> str:
    """Hash the existing CanonicalArtifactV1 root material incrementally."""

    digest = hashlib.sha256()
    digest.update(b'{"containers":')
    _hash_array(digest, iter(containers))
    digest.update(b',"issues":')
    _hash_array(digest, iter(issues))
    digest.update(b',"nodes":')
    _hash_array(digest, nodes)
    digest.update(b',"normalizer_version":')
    digest.update(_json_bytes(normalizer_version))
    digest.update(b',"provenance":')
    _hash_array(
        digest,
        (
            {
                "provenance_id": item.get("provenance_id"),
                "source_locator": item.get("source_locator") or {},
            }
            for item in provenance
        ),
    )
    digest.update(b',"schema_version":')
    digest.update(_json_bytes(CANONICAL_ARTIFACT_SCHEMA_VERSION))
    digest.update(b',"source_format":"xlsx","source_sha256":')
    digest.update(_json_bytes(source_sha256))
    digest.update(b"}")
    return digest.hexdigest()


def validate_xlsx_streaming_plan(plan: XlsxStreamingPlan) -> dict[str, Any]:
    errors: list[str] = []
    containers = list(plan.containers)
    container_ids = [str(item.get("container_id") or "") for item in containers]
    if len(container_ids) != len(set(container_ids)) or "" in container_ids:
        errors.append("canonical_container_ids_invalid")
    if plan.root_container_ref not in container_ids:
        errors.append("canonical_root_container_unresolved")
    root = next(
        (
            item
            for item in containers
            if item.get("container_id") == plan.root_container_ref
        ),
        {},
    )
    if (
        root.get("container_type") != "WORKBOOK"
        or root.get("parent_container_ref") is not None
    ):
        errors.append("canonical_root_container_type_invalid")
    provenance_ids = {str(item.get("provenance_id") or "") for item in plan.provenance}
    issue_ids = {str(item.get("issue_id") or "") for item in plan.issues}
    for container in containers:
        refs = container.get("source_refs") or []
        if not refs or any(str(ref) not in provenance_ids for ref in refs):
            errors.append("canonical_container_source_ref_unresolved")
    for issue in plan.issues:
        refs = issue.get("source_refs") or []
        if not refs or any(str(ref) not in provenance_ids for ref in refs):
            errors.append("canonical_issue_source_ref_unresolved")
        if issue.get("severity") in {"blocking", "critical"}:
            errors.append("canonical_blocking_issue_present")
    node_ids: set[str] = set()
    orders: dict[str, list[int]] = {}
    machine_content_nodes = 0
    try:
        for node in plan.iter_nodes():
            node_id = str(node.get("node_id") or "")
            if not node_id or node_id in node_ids:
                errors.append("canonical_node_ids_invalid")
            node_ids.add(node_id)
            container_ref = str(node.get("container_ref") or "")
            if container_ref not in container_ids:
                errors.append("canonical_node_container_unresolved")
            orders.setdefault(container_ref, []).append(int(node.get("order") or 0))
            if not node.get("source_refs") or any(
                str(ref) not in provenance_ids for ref in node.get("source_refs") or []
            ):
                errors.append("canonical_node_source_ref_unresolved")
            if any(str(ref) not in issue_ids for ref in node.get("issue_refs") or []):
                errors.append("canonical_node_issue_ref_unresolved")
            if _lowered_keys(node) & FORBIDDEN_FIELDS:
                errors.append("canonical_financial_semantics_forbidden")
            machine_content_nodes += int(canonical_node_has_machine_content(node))
    except (OSError, ValueError, CanonicalArtifactError):
        errors.append("canonical_chunk_hash_mismatch")
    if machine_content_nodes == 0:
        errors.append("canonical_machine_content_empty")
    for container_ref, values in orders.items():
        if sorted(values) != list(range(len(values))):
            errors.append("canonical_node_order_non_contiguous")
    expected = canonical_root_hash_from_streaming_parts(
        normalizer_version=plan.normalizer_version,
        source_sha256=plan.source_sha256,
        containers=containers,
        nodes=plan.iter_nodes(),
        provenance=list(plan.provenance),
        issues=list(plan.issues),
    )
    if expected != plan.canonical_root_hash:
        errors.append("canonical_root_hash_mismatch")
    return {
        "schema_version": "canonical_xlsx_streaming_validation_v1",
        "passed": not errors,
        "error_codes": sorted(set(errors)),
    }


def _inventory(archive: ZipFile, config: XlsxStreamingConfig) -> dict[str, Any]:
    infos = archive.infolist()
    if len(infos) > config.maximum_zip_parts:
        raise CanonicalArtifactError("xlsx_zip_part_limit_exceeded")
    if any(info.flag_bits & 0x1 for info in infos):
        raise CanonicalArtifactError("xlsx_encrypted")
    uncompressed = sum(info.file_size for info in infos)
    compressed = sum(info.compress_size for info in infos)
    if uncompressed > config.maximum_uncompressed_bytes:
        raise CanonicalArtifactError("xlsx_uncompressed_limit_exceeded")
    if any(info.file_size > config.maximum_member_bytes for info in infos):
        raise CanonicalArtifactError("xlsx_member_limit_exceeded")
    ratio = uncompressed / max(compressed, 1)
    if ratio > config.maximum_compression_ratio:
        raise CanonicalArtifactError("xlsx_compression_ratio_exceeded")
    names = {info.filename for info in infos}
    worksheet_infos = [
        info
        for info in infos
        if re.fullmatch(r"xl/worksheets/[^/]+\.xml", info.filename)
    ]
    return {
        "safe": {
            "zip_parts": len(infos),
            "uncompressed_bytes": uncompressed,
            "compressed_bytes": compressed,
            "compression_ratio": round(ratio, 6),
            "worksheet_parts": len(worksheet_infos),
            "largest_worksheet_xml_bytes": max(
                (info.file_size for info in worksheet_infos), default=0
            ),
            "external_link_parts": sum(
                1
                for name in names
                if name.startswith("xl/externalLinks/") and name.endswith(".xml")
            ),
            "chart_parts": sum(
                1
                for name in names
                if name.startswith("xl/charts/") and name.endswith(".xml")
            ),
            "pivot_parts": sum(
                1
                for name in names
                if name.startswith("xl/pivot") and name.endswith(".xml")
            ),
            "drawing_parts": sum(
                1
                for name in names
                if name.startswith("xl/drawings/") and name.endswith(".xml")
            ),
            "table_definition_parts": sum(
                1
                for name in names
                if name.startswith("xl/tables/") and name.endswith(".xml")
            ),
        }
    }


def _workbook_inventory(archive: ZipFile) -> dict[str, Any]:
    relationships = _relationships(archive, "xl/_rels/workbook.xml.rels")
    sheets: list[dict[str, Any]] = []
    named_ranges: list[dict[str, Any]] = []
    calculation_properties: dict[str, Any] = {}
    with archive.open("xl/workbook.xml") as stream:
        for event, element in ET.iterparse(stream, events=("end",)):
            name = _local_name(element.tag)
            if name == "sheet":
                relationship_id = next(
                    (
                        value
                        for key, value in element.attrib.items()
                        if _local_name(key) == "id"
                    ),
                    "",
                )
                target = _part_path("xl", relationships.get(relationship_id, ""))
                sheets.append(
                    {
                        "sheet_index": len(sheets) + 1,
                        "sheet_name": str(element.attrib.get("name") or ""),
                        "sheet_visibility": str(
                            element.attrib.get("state") or "visible"
                        ),
                        "path": target,
                    }
                )
            elif name == "definedName":
                named_ranges.append(
                    {
                        "name": str(element.attrib.get("name") or ""),
                        "formula": str(element.text or ""),
                        "local_sheet_id": element.attrib.get("localSheetId"),
                    }
                )
            elif name == "calcPr":
                calculation_properties = dict(element.attrib)
            element.clear()
    if not sheets:
        raise CanonicalArtifactError("xlsx_workbook_has_no_sheets")
    names = set(archive.namelist())
    if any(not sheet["path"] or sheet["path"] not in names for sheet in sheets):
        raise CanonicalArtifactError("xlsx_sheet_missing")
    return {
        "sheets": sheets,
        "named_ranges": named_ranges,
        "calculation_properties": calculation_properties,
    }


def _worksheet_metadata(archive: ZipFile, sheet: dict[str, Any]) -> dict[str, Any]:
    path = str(sheet["path"])
    relationships_path = str(
        PurePosixPath(path).parent / "_rels" / (PurePosixPath(path).name + ".rels")
    )
    relationships = _relationships(archive, relationships_path)
    declared_dimension: str | None = None
    merged_ranges: list[str] = []
    hidden_columns: list[dict[str, int]] = []
    table_relationships: list[str] = []
    hyperlinks: list[dict[str, Any]] = []
    with archive.open(path) as stream:
        for event, element in ET.iterparse(stream, events=("end",)):
            name = _local_name(element.tag)
            if name == "dimension":
                declared_dimension = element.attrib.get("ref")
            elif name == "mergeCell" and element.attrib.get("ref"):
                merged_ranges.append(str(element.attrib["ref"]))
            elif name == "col" and _truthy(element.attrib.get("hidden")):
                hidden_columns.append(
                    {
                        "start": _int_or(element.attrib.get("min"), 0),
                        "end": _int_or(
                            element.attrib.get("max"),
                            _int_or(element.attrib.get("min"), 0),
                        ),
                    }
                )
            elif name == "tablePart":
                relationship_id = next(
                    (
                        value
                        for key, value in element.attrib.items()
                        if _local_name(key) == "id"
                    ),
                    "",
                )
                if relationship_id:
                    table_relationships.append(relationship_id)
            elif name == "hyperlink" and element.attrib.get("ref"):
                relationship_id = next(
                    (
                        value
                        for key, value in element.attrib.items()
                        if _local_name(key) == "id"
                    ),
                    "",
                )
                target = relationships.get(relationship_id, "") or element.attrib.get(
                    "location", ""
                )
                hyperlinks.append(
                    {
                        "ref": str(element.attrib["ref"]),
                        "link_ref": f"link:{hashlib.sha256(str(target).encode('utf-8')).hexdigest()[:24]}",
                        "target": str(target),
                    }
                )
            element.clear()
    table_definitions: list[dict[str, Any]] = []
    for relationship_id in table_relationships:
        target = _part_path(
            str(PurePosixPath(path).parent), relationships.get(relationship_id, "")
        )
        if target not in archive.namelist():
            continue
        root = ET.fromstring(archive.read(target))
        table_definitions.append(
            {
                "name": root.attrib.get("name"),
                "display_name": root.attrib.get("displayName"),
                "ref": root.attrib.get("ref"),
                "totals_row_count": root.attrib.get("totalsRowCount"),
            }
        )
    return {
        "declared_dimension": declared_dimension,
        "merged_ranges": merged_ranges,
        "hidden_columns": hidden_columns,
        "table_definitions": table_definitions,
        "links": hyperlinks,
    }


def _shared_strings(archive: ZipFile) -> list[dict[str, Any]]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    values: list[dict[str, Any]] = []
    with archive.open("xl/sharedStrings.xml") as stream:
        for event, element in ET.iterparse(stream, events=("end",)):
            if _local_name(element.tag) == "si":
                values.append(
                    {
                        "shared_string_ref": f"sst:{len(values)}",
                        "value": "".join(
                            node.text or ""
                            for node in element.iter()
                            if _local_name(node.tag) == "t"
                        ),
                    }
                )
                element.clear()
    return values


def _styles(archive: ZipFile) -> list[dict[str, Any]]:
    if "xl/styles.xml" not in archive.namelist():
        return []
    custom_formats: dict[str, str] = {}
    styles: list[dict[str, Any]] = []
    in_cell_xfs = False
    with archive.open("xl/styles.xml") as stream:
        for event, element in ET.iterparse(stream, events=("start", "end")):
            name = _local_name(element.tag)
            if event == "start" and name == "cellXfs":
                in_cell_xfs = True
            elif event == "end" and name == "numFmt":
                custom_formats[str(element.attrib.get("numFmtId") or "")] = str(
                    element.attrib.get("formatCode") or ""
                )
                element.clear()
            elif event == "end" and name == "xf" and in_cell_xfs:
                number_format_id = str(element.attrib.get("numFmtId") or "0")
                styles.append(
                    {
                        "style_ref": f"style:{len(styles)}",
                        "number_format_ref": f"numfmt:{number_format_id}",
                        "number_format_code": custom_formats.get(number_format_id),
                        "font_ref": f"font:{element.attrib.get('fontId', '0')}",
                        "fill_ref": f"fill:{element.attrib.get('fillId', '0')}",
                        "border_ref": f"border:{element.attrib.get('borderId', '0')}",
                        "alignment": dict(
                            next(
                                (
                                    child.attrib
                                    for child in element
                                    if _local_name(child.tag) == "alignment"
                                ),
                                {},
                            )
                        ),
                    }
                )
                element.clear()
            elif event == "end" and name == "cellXfs":
                in_cell_xfs = False
                element.clear()
    return styles


def _cell(
    element: ET.Element,
    *,
    row_number: int,
    row_hidden: bool,
    hidden_columns: list[dict[str, int]],
    merge_ranges: list[tuple[int, int, int, int, str]],
    shared_strings: list[dict[str, Any]],
    styles: list[dict[str, Any]],
    links: dict[str, str],
    shared_formulas: dict[str, str],
) -> dict[str, Any]:
    coordinate = str(element.attrib.get("r") or "")
    column = _column_ordinal(coordinate)
    style_index = _int_or(element.attrib.get("s"), -1)
    style_ref = f"style:{style_index}" if style_index >= 0 else None
    number_format_ref = (
        str(styles[style_index].get("number_format_ref"))
        if 0 <= style_index < len(styles)
        else None
    )
    formula_node = next(
        (child for child in element if _local_name(child.tag) == "f"), None
    )
    value_node = next(
        (child for child in element if _local_name(child.tag) == "v"), None
    )
    inline_value = (
        "".join(
            child.text or ""
            for child in element.iter()
            if _local_name(child.tag) == "t"
        )
        or None
    )
    raw_value = value_node.text if value_node is not None else inline_value
    if formula_node is None and raw_value in {None, ""}:
        if style_ref:
            return {
                "kind": "blank_styled",
                "column": column,
                "cell": {"row": row_number, "column": column, "style_ref": style_ref},
            }
        return {"kind": "blank", "column": column}
    type_code = str(element.attrib.get("t") or "")
    shared_string_ref = None
    displayed_value = None
    value: Any = raw_value
    if type_code == "s" and raw_value not in {None, ""}:
        index = _int_or(raw_value, -1)
        if 0 <= index < len(shared_strings):
            shared_string_ref = str(shared_strings[index]["shared_string_ref"])
            value = shared_strings[index]["value"]
            displayed_value = str(value)
        else:
            value = None
    elif type_code in {"str", "inlineStr"}:
        value = inline_value if inline_value is not None else raw_value
        displayed_value = None if value is None else str(value)
    elif type_code == "b":
        value = str(raw_value) == "1"
        displayed_value = "TRUE" if value else "FALSE"
    elif type_code == "e":
        value = raw_value
        displayed_value = None if value is None else str(value)
    elif raw_value not in {None, ""}:
        value = _number_or_text(str(raw_value))
    formula = formula_node.text if formula_node is not None else None
    formula_attributes = dict(formula_node.attrib) if formula_node is not None else {}
    formula_ref = None
    unsupported_formula = False
    if formula_node is not None:
        formula_type = str(formula_attributes.get("t") or "normal")
        shared_index = str(formula_attributes.get("si") or "")
        if formula_type == "shared" and shared_index:
            formula_ref = f"shared_formula:{shared_index}"
            if formula:
                shared_formulas[formula_ref] = formula
            elif formula_ref in shared_formulas:
                formula = shared_formulas[formula_ref]
        if formula_type in {"array", "dataTable"} or "aca" in formula_attributes:
            unsupported_formula = True
    cached_value = (
        value if formula_node is not None and raw_value not in {None, ""} else None
    )
    merged_range = next(
        (
            original
            for start_row, start_column, end_row, end_column, original in merge_ranges
            if start_row <= row_number <= end_row
            and start_column <= column <= end_column
        ),
        None,
    )
    hidden = row_hidden or any(
        int(item["start"]) <= column <= int(item["end"]) for item in hidden_columns
    )
    if formula_node is not None:
        cell_type = "formula"
    elif type_code == "b":
        cell_type = "boolean"
    elif type_code == "e":
        cell_type = "error"
    elif type_code in {"s", "str", "inlineStr"}:
        cell_type = "string"
    elif _style_is_date(style_index, styles):
        cell_type = "date"
    else:
        cell_type = "number" if isinstance(value, (int, float)) else "string"
    return {
        "kind": "material",
        "column": column,
        "unsupported_formula": unsupported_formula,
        "cell": {
            "row": row_number,
            "column": column,
            "value": value,
            "raw_value": raw_value,
            "displayed_value": displayed_value,
            "cached_value": cached_value,
            "cell_type": cell_type,
            "formula": formula,
            "formula_ref": formula_ref,
            "formula_attributes": formula_attributes,
            "merged_range": merged_range,
            "source_coordinate": coordinate or f"R{row_number}C{column}",
            "hidden": hidden,
            "style_ref": style_ref,
            "number_format_ref": number_format_ref,
            "shared_string_ref": shared_string_ref,
            "link_ref": links.get(coordinate),
            "source_refs": [],
        },
    }


def _feature_issues(
    archive: ZipFile,
    *,
    source_sha256: str,
    source_artifact_ref: str,
    source_ref: str,
) -> list[dict[str, Any]]:
    del source_artifact_ref
    names = set(archive.namelist())
    features = {
        "EXTERNAL_REFERENCE": any(
            name.startswith("xl/externalLinks/") for name in names
        ),
        "charts": any(name.startswith("xl/charts/") for name in names),
        "pivots": any(name.startswith("xl/pivot") for name in names),
        "drawings": any(name.startswith("xl/drawings/") for name in names),
        "macros": any(name.endswith("vbaProject.bin") for name in names),
        "data_connections": "xl/connections.xml" in names,
    }
    issues: list[dict[str, Any]] = []
    if features.pop("EXTERNAL_REFERENCE"):
        issues.append(
            _issue(
                source_sha256=source_sha256,
                issue_type="UNSUPPORTED",
                severity="warning",
                summary="EXTERNAL_REFERENCE",
                source_ref=source_ref,
                subject=["external_links"],
            )
        )
    for feature, present in features.items():
        if present:
            issues.append(
                _issue(
                    source_sha256=source_sha256,
                    issue_type="UNSUPPORTED",
                    severity="warning",
                    summary="UNSUPPORTED_XLSX_FEATURE",
                    source_ref=source_ref,
                    subject=[feature],
                )
            )
    return issues


def _relationships(archive: ZipFile, path: str) -> dict[str, str]:
    if path not in archive.namelist():
        return {}
    values: dict[str, str] = {}
    with archive.open(path) as stream:
        for event, element in ET.iterparse(stream, events=("end",)):
            if _local_name(element.tag) == "Relationship":
                relationship_id = element.attrib.get("Id")
                target = element.attrib.get("Target")
                if relationship_id and target:
                    values[str(relationship_id)] = str(target)
            element.clear()
    return values


def _part_path(base: str, target: str) -> str:
    if not target:
        return ""
    if target.startswith("/"):
        return str(PurePosixPath(target.lstrip("/")))
    parts: list[str] = []
    for part in PurePosixPath(base, target).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part not in {"", "."}:
            parts.append(part)
    return str(PurePosixPath(*parts))


def _plan_from_state(stage_root: Path, state: dict[str, Any]) -> XlsxStreamingPlan:
    authority = state["authority"]
    plan = XlsxStreamingPlan(
        stage_root=stage_root,
        tenant_id=str(authority["tenant_id"]),
        document_id=str(authority["document_id"]),
        source_artifact_ref=str(authority["source_artifact_ref"]),
        source_sha256=str(authority["source_sha256"]),
        mime_type=str(authority["mime_type"]),
        normalizer_version=str(authority["normalizer_version"]),
        canonical_root_hash=str(state["canonical_root_hash"]),
        root_container_ref=str(state["root_container_ref"]),
        containers=tuple(state["containers"]),
        provenance=tuple(state["provenance"]),
        issues=tuple(state["issues"]),
        node_entries=tuple(state["node_entries"]),
        safe_metrics=dict(state["safe_metrics"]),
    )
    validation = validate_xlsx_streaming_plan(plan)
    if not validation["passed"]:
        raise CanonicalArtifactError(
            "xlsx_streaming_validation_failed", ",".join(validation["error_codes"])
        )
    return plan


def _nodes_from_entries(
    stage_root: Path, entries: list[dict[str, Any]]
) -> Iterator[dict[str, Any]]:
    plan = XlsxStreamingPlan(
        stage_root=stage_root,
        tenant_id="x",
        document_id="x",
        source_artifact_ref="x",
        source_sha256="0" * 64,
        mime_type="application/octet-stream",
        normalizer_version="x",
        canonical_root_hash="0" * 64,
        root_container_ref="x",
        containers=(),
        provenance=(),
        issues=(),
        node_entries=tuple(entries),
        safe_metrics={},
    )
    yield from plan.iter_nodes()


def _inline_entry(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "inline_node": node,
        "node_id": node["node_id"],
        "container_ref": node["container_ref"],
        "order": node["order"],
        "node_type": node["node_type"],
    }


def _provenance(
    source_sha256: str, source_artifact_ref: str, locator: dict[str, Any]
) -> dict[str, Any]:
    provenance_id = f"prov_{_stable_hash([source_sha256, locator])[:24]}"
    return {
        "provenance_id": provenance_id,
        "source_ref": source_artifact_ref,
        "source_locator": locator,
        "evidence_refs": [],
    }


def _container_id(
    source_sha256: str, container_type: str, parent: str | None, order: int
) -> str:
    return (
        f"container_{_stable_hash([source_sha256, container_type, parent, order])[:24]}"
    )


def _node(
    *,
    source_sha256: str,
    container_ref: str,
    order: int,
    node_type: str,
    content: dict[str, Any],
    provenance_ref: str,
) -> dict[str, Any]:
    node_id = f"node_{_stable_hash([source_sha256, container_ref, order, node_type, content])[:24]}"
    return {
        "node_id": node_id,
        "container_ref": container_ref,
        "order": order,
        "node_type": node_type,
        "source_refs": [provenance_ref],
        "evidence_refs": [],
        "issue_refs": [],
        "content": content,
    }


def _issue(
    *,
    source_sha256: str,
    issue_type: str,
    severity: str,
    summary: str,
    source_ref: str,
    subject: list[Any],
) -> dict[str, Any]:
    return {
        "issue_id": f"issue_{_stable_hash([source_sha256, issue_type, severity, summary, subject])[:24]}",
        "issue_type": issue_type,
        "severity": severity,
        "source_refs": [source_ref],
        "evidence_refs": [],
        "summary": summary,
    }


def _deduplicate_issues(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        issue_id = str(value.get("issue_id") or "")
        if issue_id not in seen:
            seen.add(issue_id)
            result.append(value)
    return result


def _blank_style_runs(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for cell in sorted(cells, key=lambda item: int(item["column"])):
        if (
            runs
            and runs[-1]["end_column"] + 1 == int(cell["column"])
            and runs[-1]["style_ref"] == cell["style_ref"]
        ):
            runs[-1]["end_column"] = int(cell["column"])
        else:
            runs.append(
                {
                    "row": int(cell["row"]),
                    "start_column": int(cell["column"]),
                    "end_column": int(cell["column"]),
                    "style_ref": str(cell["style_ref"]),
                }
            )
    return runs


def _a1_bounds(value: str) -> tuple[int, int, int, int, str]:
    first, _, last = value.partition(":")
    last = last or first
    return (
        _row_ordinal(first),
        _column_ordinal(first),
        _row_ordinal(last),
        _column_ordinal(last),
        value,
    )


def _dimension_mismatch(value: str, maximum_row: int, maximum_column: int) -> bool:
    if maximum_row == 0 and maximum_column == 0 and value in {"", "A1"}:
        return False
    if not value:
        return maximum_row > 0 or maximum_column > 0
    _, _, end_row, end_column, _ = _a1_bounds(value)
    return end_row != maximum_row or end_column != maximum_column


def _column_ordinal(value: str) -> int:
    match = re.match(r"([A-Za-z]+)", value or "")
    if match is None:
        return 0
    ordinal = 0
    for character in match.group(1).upper():
        ordinal = ordinal * 26 + ord(character) - ord("A") + 1
    return ordinal


def _row_ordinal(value: str) -> int:
    match = re.search(r"(\d+)$", value or "")
    return int(match.group(1)) if match else 0


def _style_is_date(style_index: int, styles: list[dict[str, Any]]) -> bool:
    if not 0 <= style_index < len(styles):
        return False
    number_format = str(styles[style_index].get("number_format_ref") or "")
    number_format_id = _int_or(number_format.partition(":")[2], -1)
    if number_format_id in {14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47}:
        return True
    code = str(styles[style_index].get("number_format_code") or "").lower()
    return bool(code and re.search(r"[ymdhis]", re.sub(r'"[^"]*"', "", code)))


def _number_or_text(value: str) -> Any:
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() and "e" not in value.lower() else number


def _truthy(value: Any) -> bool:
    return str(value or "0") in {"1", "true", "True"}


def _int_or(value: Any, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _hash_array(digest, values: Iterator[Any]) -> None:
    digest.update(b"[")
    first = True
    for value in values:
        if not first:
            digest.update(b",")
        first = False
        digest.update(_json_bytes(value))
    digest.update(b"]")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_state(path: Path, state: dict[str, Any]) -> None:
    payload = json.loads(json.dumps(state))
    payload.pop("integrity_sha256", None)
    payload["integrity_sha256"] = _stable_hash(payload)
    _write_bytes_atomic(
        path, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )


def _read_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(payload.pop("integrity_sha256", ""))
    if supplied != _stable_hash(payload):
        raise CanonicalArtifactError("xlsx_streaming_state_integrity_invalid")
    payload["integrity_sha256"] = supplied
    return payload


def _verify_tracked_chunks(stage_root: Path, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        relative = entry.get("relative_path")
        if not relative:
            continue
        path = stage_root / str(relative)
        if not path.is_file() or hashlib.sha256(
            path.read_bytes()
        ).hexdigest() != entry.get("sha256"):
            raise CanonicalArtifactError("xlsx_streaming_resume_chunk_invalid")


def _lowered_keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(str(key).lower())
            result.update(_lowered_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_lowered_keys(child))
    return result


def cleanup_xlsx_staging(plan: XlsxStreamingPlan) -> None:
    """Remove only the plan-owned staging directory after durable finalization."""

    if plan.stage_root.is_dir():
        shutil.rmtree(plan.stage_root)
