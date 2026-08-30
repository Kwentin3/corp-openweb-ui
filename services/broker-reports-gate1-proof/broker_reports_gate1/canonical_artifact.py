"""Gate 2 non-financial CanonicalArtifactV1 construction authority."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .table_projection import NormalizedTableProjectionFactory


CANONICAL_ARTIFACT_SCHEMA_VERSION = "canonical_artifact_v1"
CANONICAL_NORMALIZER_POLICY_VERSION = "canonical_normalizer_v1"
FACTORY_REQUIRED = "CanonicalNormalizerFactory.create is the only CanonicalArtifactV1 construction entrypoint"
FORBIDDEN_FIELDS = {
    "financial_fact",
    "financial_role",
    "ontology",
    "tax_treatment",
    "declaration_field",
    "gate3_context",
}
SUPPORTED_FORMATS = {"pdf", "html_text", "csv", "xlsx"}
CANONICAL_SOURCE_FORMATS = {"pdf", "html", "csv", "xlsx"}
CANONICAL_CONTAINER_TYPES = {
    "DOCUMENT",
    "PAGE",
    "SECTION",
    "WORKBOOK",
    "SHEET",
    "DATASET",
}
CANONICAL_NODE_TYPES = {
    "HEADING",
    "TEXT",
    "LIST",
    "TABLE",
    "NOTE",
    "PAGE_BREAK",
    "SHEET_BREAK",
    "CONFLICT",
    "AMBIGUITY",
}
CANONICAL_ROOT_TYPE_BY_FORMAT = {
    "pdf": "DOCUMENT",
    "html": "DOCUMENT",
    "csv": "DATASET",
    "xlsx": "WORKBOOK",
}


class CanonicalArtifactError(RuntimeError):
    def __init__(self, code: str, subject: str = "") -> None:
        super().__init__(f"{code}: {subject}" if subject else code)
        self.code = code
        self.subject = subject


@dataclass(frozen=True)
class CanonicalNormalizerConfig:
    normalizer_version: str


class CanonicalNormalizerFactory:
    """Sole constructor for the public Gate 2 normalizer.

    Keeping creation here prevents format adapters from becoming independent
    schema owners. A new format must extend ``CanonicalNormalizer`` and still
    emit the same versioned logical contract.
    """

    def __init__(self, config: CanonicalNormalizerConfig) -> None:
        self.config = config

    def create(self) -> "CanonicalNormalizer":
        """Create the configured authority; an unversioned builder is invalid."""

        if not self.config.normalizer_version:
            raise CanonicalArtifactError("canonical_normalizer_version_required")
        return CanonicalNormalizer(self.config)


class CanonicalNormalizer:
    """Adapt supported source structures into one ordered non-financial model."""

    def __init__(self, config: CanonicalNormalizerConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        tenant_id: str,
        artifact_version: int,
        document: dict[str, Any],
        source_artifact_ref: str,
        source_payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
        table_projections: list[dict[str, Any]],
        created_at: str | None = None,
        previous_version_ref: str | None = None,
    ) -> dict[str, Any]:
        """Build and validate one ``CanonicalArtifactV1``.

        Format branching ends inside this method. Downstream code must observe
        only the common container/node/table/provenance contract.
        """

        source_format = str(document.get("container_format") or "")
        if source_format not in SUPPORTED_FORMATS:
            raise CanonicalArtifactError(
                "canonical_format_not_supported", source_format
            )
        if not tenant_id or not source_artifact_ref:
            raise CanonicalArtifactError("canonical_authenticated_scope_required")
        source_sha256 = str(document.get("sha256") or "")
        if len(source_sha256) != 64:
            raise CanonicalArtifactError("canonical_source_sha256_invalid")
        if artifact_version < 1:
            raise CanonicalArtifactError("canonical_artifact_version_invalid")

        builder = _LogicalBuilder(
            source_sha256=source_sha256,
            source_artifact_ref=source_artifact_ref,
        )
        if source_format == "pdf":
            self._adapt_pdf(
                builder,
                source_payloads,
                source_units,
                table_projections,
            )
        elif source_format == "html_text":
            self._adapt_html(builder, source_payloads)
        elif source_format == "csv":
            self._adapt_csv(builder, source_payloads, source_units)
        else:
            self._adapt_xlsx(builder, source_payloads)

        logical = builder.finish()
        if source_format == "pdf":
            accounting = pdf_source_atom_accounting(
                logical,
                source_payloads=source_payloads,
                source_units=source_units,
                table_projections=table_projections,
            )
            if accounting["accounting_status"] != "passed":
                raise CanonicalArtifactError(
                    "canonical_pdf_source_atom_accounting_incomplete",
                    ",".join(accounting["reason_codes"]),
                )
            root_container = next(
                item
                for item in logical["containers"]
                if item["container_id"] == logical["root_container_ref"]
            )
            root_container.setdefault("metadata", {})["pdf_completeness"] = (
                copy.deepcopy(accounting["completeness_receipt"])
            )
        canonical_source_format = (
            "html" if source_format == "html_text" else source_format
        )
        hash_material = _root_hash_material(
            normalizer_version=self.config.normalizer_version,
            source_format=canonical_source_format,
            source_sha256=source_sha256,
            containers=logical["containers"],
            nodes=logical["nodes"],
            provenance=logical["provenance"],
            issues=logical["issues"],
        )
        root_hash = _sha256(hash_material)
        artifact = {
            "artifact_id": f"canonical_{root_hash[:32]}_v{artifact_version}",
            "tenant_id": tenant_id,
            "schema_version": CANONICAL_ARTIFACT_SCHEMA_VERSION,
            "artifact_version": artifact_version,
            "normalizer_version": self.config.normalizer_version,
            "previous_version_ref": previous_version_ref,
            "status": "validated",
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "source": {
                "source_artifact_ref": source_artifact_ref,
                "source_format": canonical_source_format,
                "mime_type": str(
                    document.get("declared_mime_type") or "application/octet-stream"
                ),
                "source_sha256": source_sha256,
            },
            "root_container_ref": logical["root_container_ref"],
            "canonical_root_hash": root_hash,
            "containers": logical["containers"],
            "nodes": logical["nodes"],
            "provenance": logical["provenance"],
            "issues": logical["issues"],
            "chunks": [],
        }
        validation = validate_canonical_artifact(artifact)
        if not validation["passed"]:
            raise CanonicalArtifactError(
                "canonical_artifact_validation_failed",
                ",".join(validation["error_codes"]),
            )
        return artifact

    def build_xlsx_streaming(
        self,
        *,
        source_path,
        staging_root,
        tenant_id: str,
        document_id: str,
        source_artifact_ref: str,
        source_sha256: str,
        mime_type: str,
        config=None,
    ):
        """Build a resumable XLSX plan without materializing the workbook.

        The factory-created normalizer remains the sole logical construction
        authority.  The implementation import is intentionally local to avoid
        making the generic artifact contract depend on the XLSX ZIP adapter.
        """

        from .xlsx_streaming import (  # noqa: PLC0415
            XlsxStreamingCanonicalAdapter,
            XlsxStreamingConfig,
        )

        return XlsxStreamingCanonicalAdapter(
            config=config or XlsxStreamingConfig(),
            normalizer_version=self.config.normalizer_version,
        ).build(
            source_path=source_path,
            staging_root=staging_root,
            tenant_id=tenant_id,
            document_id=document_id,
            source_artifact_ref=source_artifact_ref,
            source_sha256=source_sha256,
            mime_type=mime_type,
        )

    @staticmethod
    def _adapt_pdf(
        builder: "_LogicalBuilder",
        source_payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
        table_projections: list[dict[str, Any]],
    ) -> None:
        """Assemble PDF evidence without letting visual proposals become truth.

        Every parser atom and table proposal is represented or terminally
        accounted before the shared completeness validator can admit output.
        """

        _validate_bound_projection_inputs(
            source_payloads, source_units, table_projections
        )
        root = builder.add_container("DOCUMENT", None, {})
        projections_by_unit: dict[str, dict[str, Any]] = {}
        standalone_projections: list[dict[str, Any]] = []
        for projection in table_projections:
            ref = str(projection.get("source_unit_ref") or "")
            if ref:
                projections_by_unit[ref] = projection
        ordered = sorted(
            source_units,
            key=lambda item: (
                int(
                    _location(item).get("page")
                    or _location(item).get("page_start")
                    or 1
                ),
                int(_location(item).get("line_start") or 0),
                str(item.get("unit_ref") or ""),
            ),
        )
        source_unit_refs = {
            str(unit.get("unit_ref") or "") for unit in ordered if unit.get("unit_ref")
        }
        standalone_projections = sorted(
            [
                projection
                for projection in table_projections
                if str(projection.get("source_unit_ref") or "")
                not in source_unit_refs
            ],
            key=lambda item: (
                _projection_page(item),
                str(item.get("table_projection_id") or ""),
            ),
        )
        page_locations: dict[int, dict[str, Any]] = {}
        for unit in ordered:
            location = _location(unit)
            page = int(location.get("page") or location.get("page_start") or 1)
            page_locations.setdefault(page, location)
        for projection in standalone_projections:
            page = _projection_page(projection)
            page_locations.setdefault(page, _projection_location(projection))
        page_containers: dict[int, str] = {}
        for page in sorted(page_locations):
            page_containers[page] = builder.add_container(
                "PAGE", root, {"page_number": page}
            )
            if len(page_containers) > 1:
                builder.add_node(
                    page_containers[page],
                    "PAGE_BREAK",
                    {"boundary_ref": f"page:{page}"},
                    page_locations[page],
                )
        seen_tables: set[str] = set()
        for unit in ordered:
            location = _location(unit)
            page = int(location.get("page") or location.get("page_start") or 1)
            container = page_containers[page]
            unit_ref = str(unit.get("unit_ref") or "")
            location = {
                **location,
                "source_unit_ref": unit_ref,
                "parent_payload_ref": str(unit.get("parent_payload_ref") or ""),
            }
            issue_refs: list[str] = []
            atom_status = str(unit.get("atom_status") or "")
            if atom_status == "CONFLICT_EVIDENCE":
                issue_ref = builder.add_issue(
                    "CONFLICT",
                    "warning",
                    "source_conflict_retained",
                    location,
                )
                builder.add_node(
                    container,
                    "CONFLICT",
                    {
                        "summary": "source_conflict_retained",
                        "alternative_refs": [unit_ref],
                    },
                    location,
                    issue_refs=[issue_ref],
                )
                continue
            elif atom_status == "AMBIGUOUS_EVIDENCE":
                issue_ref = builder.add_issue(
                    "AMBIGUITY",
                    "warning",
                    "source_ambiguity_retained",
                    location,
                )
                builder.add_node(
                    container,
                    "AMBIGUITY",
                    {
                        "summary": "source_ambiguity_retained",
                        "alternative_refs": [unit_ref],
                    },
                    location,
                    issue_refs=[issue_ref],
                )
                continue
            projection = projections_by_unit.get(unit_ref)
            table_id = str(
                (projection or {}).get("canonical_table_id")
                or (projection or {}).get("table_projection_id")
                or ""
            )
            projection_status = str((projection or {}).get("projection_status") or "")
            if (
                projection
                and projection_status == "ready"
                and table_id not in seen_tables
            ):
                seen_tables.add(table_id)
                rows, table_location, title, header_present = (
                    _projection_table_material(projection, location)
                )
                builder.add_table(
                    container,
                    rows,
                    table_location,
                    metadata={
                        "source_format": "pdf",
                        "source_unit_ref": unit_ref,
                        "table_projection_id": projection.get("table_projection_id"),
                        "canonical_table_id": projection.get("canonical_table_id"),
                        "table_candidate_status": projection.get(
                            "table_candidate_status"
                        ),
                        "parser_duplicate_text_suppressed": True,
                        **(
                            {
                                "logical_table_id": projection.get(
                                    "logical_table_id"
                                ),
                                "continuation": copy.deepcopy(
                                    projection.get("continuation")
                                ),
                            }
                            if projection.get("logical_table_id")
                            else {}
                        ),
                    },
                    canonical_cells=_projection_canonical_cells(
                        builder, projection, table_location
                    ),
                    canonical_cell_source_refs_resolved=True,
                    header_present=header_present,
                    title=title,
                    issue_refs=issue_refs,
                )
                continue
            if projection and projection_status != "ready":
                issue_refs.append(
                    builder.add_issue(
                        "PARTIAL",
                        "warning",
                        "pdf_table_projection_terminal_fallback_text",
                        location,
                    )
                )
            rows = unit.get("rows") or unit.get("cells")
            if isinstance(rows, list) and rows:
                builder.add_table(
                    container,
                    copy.deepcopy(rows),
                    location,
                    metadata={"source_format": "pdf"},
                    title=unit.get("table_title"),
                    notes=copy.deepcopy(unit.get("table_notes") or []),
                    issue_refs=issue_refs,
                )
                continue
            text = str(unit.get("text") or "")
            if text:
                node_type, content = _pdf_text_node(unit, text)
                builder.add_node(
                    container,
                    node_type,
                    content,
                    location,
                    issue_refs=issue_refs,
                )
                continue
            if unit.get("pdf_unit_type") == "pdf_visual_page_unit":
                builder.add_issue(
                    "UNSUPPORTED",
                    "info",
                    "pdf_visual_atom_evidence_only",
                    location,
                )
                continue
            builder.add_issue(
                "PARTIAL",
                "blocking",
                "pdf_source_unit_unresolved",
                location,
            )
        for projection in standalone_projections:
            if str(projection.get("projection_status") or "") != "ready":
                continue
            table_id = str(
                projection.get("canonical_table_id")
                or projection.get("table_projection_id")
                or ""
            )
            if not table_id or table_id in seen_tables:
                continue
            seen_tables.add(table_id)
            page = _projection_page(projection)
            rows, table_location, title, header_present = (
                _projection_table_material(
                    projection, _projection_location(projection)
                )
            )
            builder.add_table(
                page_containers[page],
                rows,
                table_location,
                metadata={
                    "source_format": "pdf",
                    "source_unit_ref": projection.get("source_unit_ref"),
                    "table_projection_id": projection.get("table_projection_id"),
                    "canonical_table_id": projection.get("canonical_table_id"),
                    "table_candidate_status": projection.get(
                        "table_candidate_status"
                    ),
                    "standalone_source_bound_projection": True,
                    "parser_duplicate_text_suppressed": False,
                    **(
                        {
                            "logical_table_id": projection.get("logical_table_id"),
                            "continuation": copy.deepcopy(
                                projection.get("continuation")
                            ),
                        }
                        if projection.get("logical_table_id")
                        else {}
                    ),
                },
                canonical_cells=_projection_canonical_cells(
                    builder,
                    projection,
                    table_location,
                ),
                canonical_cell_source_refs_resolved=True,
                header_present=header_present,
                title=title,
            )
        if not ordered and not standalone_projections:
            if _proved_empty_pdf(source_payloads):
                builder.add_issue(
                    "PARTIAL",
                    "info",
                    "EMPTY_SOURCE_DOCUMENT",
                    {"source_state": "proved_empty_pdf"},
                )
            else:
                builder.add_issue(
                    "PARTIAL",
                    "blocking",
                    "pdf_source_units_unavailable",
                    {"source_state": "nonempty_or_unproved_pdf"},
                )
        container_order = {
            str(item["container_id"]): index
            for index, item in enumerate(builder.containers)
        }
        builder.nodes.sort(
            key=lambda item: (
                container_order.get(str(item.get("container_ref") or ""), 10**9),
                int(item.get("order") or 0),
            )
        )

    @staticmethod
    def _adapt_html(
        builder: "_LogicalBuilder", source_payloads: list[dict[str, Any]]
    ) -> None:
        root = builder.add_container("DOCUMENT", None, {})
        section = builder.add_container("SECTION", root, {"section_index": 1})
        semantic_blocks: list[dict[str, Any]] = []
        for payload in source_payloads:
            canonical = payload.get("canonical_projection")
            if isinstance(canonical, dict) and isinstance(
                canonical.get("blocks"), list
            ):
                semantic_blocks = copy.deepcopy(canonical["blocks"])
                break
        if semantic_blocks:
            for block in semantic_blocks:
                kind = str(block.get("kind") or "text")
                location = dict(block.get("source_location") or {})
                if kind == "table":
                    builder.add_table(
                        section,
                        copy.deepcopy(block.get("rows") or []),
                        location,
                        metadata={
                            "source_format": "html",
                            "caption": block.get("caption"),
                        },
                    )
                elif kind == "heading":
                    builder.add_node(
                        section,
                        "HEADING",
                        {
                            "text": str(block.get("text") or ""),
                            "level": int(block.get("level") or 1),
                            "links": copy.deepcopy(block.get("links") or []),
                        },
                        location,
                    )
                elif kind == "list":
                    builder.add_node(
                        section,
                        "LIST",
                        {"items": copy.deepcopy(block.get("items") or [])},
                        location,
                    )
                elif kind == "note":
                    builder.add_node(
                        section,
                        "NOTE",
                        {
                            "text": str(block.get("text") or ""),
                            "links": copy.deepcopy(block.get("links") or []),
                        },
                        location,
                    )
                else:
                    builder.add_node(
                        section,
                        "TEXT",
                        {
                            "text": str(block.get("text") or ""),
                            "links": copy.deepcopy(block.get("links") or []),
                        },
                        location,
                    )
            return
        for payload in source_payloads:
            projection = payload.get("normalized_projection") or {}
            location = dict(payload.get("source_location") or {})
            rows = projection.get("cells")
            if isinstance(rows, list):
                builder.add_table(
                    section,
                    copy.deepcopy(rows),
                    location,
                    metadata={"source_format": "html"},
                )
            elif "text" in projection:
                builder.add_node(
                    section,
                    "TEXT",
                    {"text": str(projection.get("text") or "")},
                    location,
                )

    @staticmethod
    def _adapt_csv(
        builder: "_LogicalBuilder",
        source_payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
    ) -> None:
        root = builder.add_container("DATASET", None, {})
        payload = source_payloads[0] if source_payloads else {}
        canonical = payload.get("canonical_projection") or {}
        rows = canonical.get("rows")
        if not isinstance(rows, list):
            unit = source_units[0] if source_units else {}
            rows = unit.get("rows") or unit.get("cells") or []
        metadata = {
            "source_format": "csv",
            "encoding": canonical.get("encoding") or _location(payload).get("encoding"),
            "delimiter": canonical.get("delimiter")
            or _location(payload).get("delimiter"),
            "quotechar": canonical.get("quotechar", '"'),
            "header_present": bool(canonical.get("header_present", True)),
            "duplicate_headers": bool(canonical.get("duplicate_headers", False)),
        }
        builder.add_table(
            root,
            copy.deepcopy(rows),
            _location(payload),
            metadata=metadata,
            header_present=metadata["header_present"],
        )

    @staticmethod
    def _adapt_xlsx(
        builder: "_LogicalBuilder", source_payloads: list[dict[str, Any]]
    ) -> None:
        root = builder.add_container("WORKBOOK", None, {})
        for payload in sorted(
            source_payloads,
            key=lambda item: int(_location(item).get("sheet_index") or 0),
        ):
            canonical = payload.get("canonical_projection") or {}
            location = _location(payload)
            sheet_index = int(
                location.get("sheet_index") or canonical.get("sheet_index") or 0
            )
            sheet = builder.add_container(
                "SHEET",
                root,
                {
                    "sheet_index": sheet_index,
                    "sheet_name": canonical.get("sheet_name"),
                    "sheet_visibility": canonical.get("sheet_visibility")
                    or location.get("sheet_visibility"),
                    "named_ranges": copy.deepcopy(canonical.get("named_ranges") or []),
                    "table_definitions": copy.deepcopy(
                        canonical.get("table_definitions") or []
                    ),
                },
            )
            if sheet_index > 1:
                builder.add_node(
                    sheet,
                    "SHEET_BREAK",
                    {"boundary_ref": f"sheet:{sheet_index}"},
                    location,
                )
            rows = canonical.get("rows")
            if not isinstance(rows, list):
                rows = (payload.get("normalized_projection") or {}).get("cells") or []
            builder.add_table(
                sheet,
                copy.deepcopy(rows),
                location,
                metadata={"source_format": "xlsx"},
                canonical_cells=copy.deepcopy(canonical.get("cells") or []),
                header_present=False,
            )
        if not source_payloads:
            builder.add_issue(
                "PARTIAL", "blocking", "xlsx_source_payloads_unavailable", {}
            )


class _LogicalBuilder:
    def __init__(self, *, source_sha256: str, source_artifact_ref: str) -> None:
        self.source_sha256 = source_sha256
        self.source_artifact_ref = source_artifact_ref
        self.containers: list[dict[str, Any]] = []
        self.nodes: list[dict[str, Any]] = []
        self.provenance: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = []
        self._container_orders: dict[str | None, int] = {}
        self._node_orders: dict[str, int] = {}

    def add_container(
        self, container_type: str, parent: str | None, metadata: dict[str, Any]
    ) -> str:
        order = self._container_orders.get(parent, 0)
        self._container_orders[parent] = order + 1
        container_id = f"container_{_sha256([self.source_sha256, container_type, parent, order])[:24]}"
        self.containers.append(
            {
                "container_id": container_id,
                "container_type": container_type,
                "parent_container_ref": parent,
                "order": order,
                "source_refs": [
                    self._provenance_ref(
                        {"container_type": container_type, "order": order}
                    )
                ],
                "metadata": metadata,
            }
        )
        return container_id

    def add_node(
        self,
        container_ref: str,
        node_type: str,
        content: dict[str, Any],
        source_locator: dict[str, Any],
        *,
        issue_refs: list[str] | None = None,
    ) -> str:
        order = self._node_orders.get(container_ref, 0)
        self._node_orders[container_ref] = order + 1
        provenance_ref = self._provenance_ref(source_locator)
        node_id = f"node_{_sha256([self.source_sha256, container_ref, order, node_type, content])[:24]}"
        self.nodes.append(
            {
                "node_id": node_id,
                "container_ref": container_ref,
                "order": order,
                "node_type": node_type,
                "source_refs": [provenance_ref],
                "evidence_refs": [],
                "issue_refs": list(issue_refs or []),
                "content": content,
            }
        )
        return node_id

    def add_table(
        self,
        container_ref: str,
        rows: list[Any],
        source_locator: dict[str, Any],
        *,
        metadata: dict[str, Any],
        canonical_cells: list[dict[str, Any]] | None = None,
        canonical_cell_source_refs_resolved: bool = False,
        header_present: bool = False,
        title: Any = None,
        notes: list[Any] | None = None,
        issue_refs: list[str] | None = None,
    ) -> str:
        normalized_rows = [
            list(row) if isinstance(row, list) else [row] for row in rows
        ]
        header = normalized_rows[0] if header_present and normalized_rows else []
        body = (
            normalized_rows[1:]
            if header_present and normalized_rows
            else normalized_rows
        )
        provenance_ref = self._provenance_ref(source_locator)
        cells = (
            _normalize_canonical_cells(
                canonical_cells,
                provenance_ref,
                preserve_source_refs=canonical_cell_source_refs_resolved,
            )
            if canonical_cells
            else _cells_from_rows(normalized_rows, provenance_ref)
        )
        return self.add_node(
            container_ref,
            "TABLE",
            {
                "title": title if title is not None else metadata.get("caption"),
                "header": header,
                "rows": body,
                "notes": list(notes or []),
                "cells": cells,
                "metadata": metadata,
            },
            source_locator,
            issue_refs=issue_refs,
        )

    def add_issue(
        self,
        issue_type: str,
        severity: str,
        summary: str,
        source_locator: dict[str, Any],
    ) -> str:
        source_ref = self._provenance_ref(source_locator)
        issue_id = f"issue_{_sha256([self.source_sha256, issue_type, severity, summary, source_locator])[:24]}"
        self.issues.append(
            {
                "issue_id": issue_id,
                "issue_type": issue_type,
                "severity": severity,
                "source_refs": [source_ref],
                "evidence_refs": [],
                "summary": summary,
            }
        )
        return issue_id

    def _provenance_ref(self, source_locator: dict[str, Any]) -> str:
        provenance_id = f"prov_{_sha256([self.source_sha256, source_locator])[:24]}"
        if not any(item["provenance_id"] == provenance_id for item in self.provenance):
            self.provenance.append(
                {
                    "provenance_id": provenance_id,
                    "source_ref": self.source_artifact_ref,
                    "source_locator": copy.deepcopy(source_locator),
                    "evidence_refs": [],
                }
            )
        return provenance_id

    def finish(self) -> dict[str, Any]:
        roots = [
            item["container_id"]
            for item in self.containers
            if item["parent_container_ref"] is None
        ]
        if len(roots) != 1:
            raise CanonicalArtifactError("canonical_root_container_cardinality_invalid")
        return {
            "root_container_ref": roots[0],
            "containers": self.containers,
            "nodes": self.nodes,
            "provenance": self.provenance,
            "issues": self.issues,
        }


PDF_SOURCE_ATOM_CATEGORIES = (
    "PRIMARY_TEXT_NODE",
    "PRIMARY_TABLE_NODE",
    "HEADING_OR_NOTE_NODE",
    "SUPPRESSED_PROVED_TABLE_DUPLICATE",
    "PAGE_FURNITURE",
    "EVIDENCE_ONLY",
    "CONFLICT",
    "AMBIGUITY",
    "UNRESOLVED",
)
PDF_COMPLETENESS_RECEIPT_SCHEMA_VERSION = "canonical_pdf_completeness_v1"


def _pdf_text_node(unit: dict[str, Any], text: str) -> tuple[str, dict[str, Any]]:
    declared = str(
        unit.get("canonical_node_type")
        or unit.get("semantic_role")
        or unit.get("content_role")
        or ""
    ).upper()
    if declared == "HEADING":
        return "HEADING", {
            "text": text,
            "level": max(1, min(6, int(unit.get("heading_level") or 1))),
        }
    if declared == "NOTE":
        return "NOTE", {"text": text}
    if declared == "LIST":
        items = unit.get("list_items")
        if isinstance(items, list) and items:
            return "LIST", {
                "items": [
                    {
                        "text": str(item.get("text") or ""),
                        "level": max(0, int(item.get("level") or 0)),
                        "ordered": bool(item.get("ordered")),
                    }
                    for item in items
                    if isinstance(item, dict) and str(item.get("text") or "")
                ]
            }
    return "TEXT", {"text": text}


def _proved_empty_pdf(source_payloads: list[dict[str, Any]]) -> bool:
    if len(source_payloads) != 1:
        return False
    payload = source_payloads[0]
    projection = payload.get("pdf_text_layer_projection") or {}
    reasons = {
        str(value) for value in payload.get("parser_completeness_reason_codes") or []
    }
    return (
        payload.get("parser_completeness_status") == "complete"
        and len(projection.get("page_inventory") or []) == 0
        and bool(
            reasons
            & {
                "EMPTY_SOURCE_DOCUMENT",
                "pdf_empty_source_document",
            }
        )
    )


def pdf_source_atom_accounting(
    logical: dict[str, Any],
    *,
    source_payloads: list[dict[str, Any]],
    source_units: list[dict[str, Any]],
    table_projections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify every PDF source atom before a candidate can be validated.

    The receipt intentionally contains counts only. Exact unit, parser and
    content refs remain in private provenance and never enter safe evidence.
    """

    nodes = list(logical.get("nodes") or [])
    containers = list(logical.get("containers") or [])
    provenance = list(logical.get("provenance") or [])
    issues = list(logical.get("issues") or [])
    projection_by_unit = {
        str(item.get("source_unit_ref") or ""): item
        for item in table_projections
        if isinstance(item, dict) and item.get("source_unit_ref")
    }
    table_projection_ids = {
        str(
            (node.get("content") or {}).get("metadata", {}).get("table_projection_id")
            or ""
        )
        for node in nodes
        if node.get("node_type") == "TABLE"
    }
    provenance_unit_refs = {
        str((item.get("source_locator") or {}).get("source_unit_ref") or "")
        for item in provenance
    }
    node_types_by_unit: dict[str, set[str]] = {}
    provenance_by_id = {
        str(item.get("provenance_id") or ""): item for item in provenance
    }
    for node in nodes:
        for source_ref in node.get("source_refs") or []:
            locator = (provenance_by_id.get(str(source_ref)) or {}).get(
                "source_locator"
            ) or {}
            unit_ref = str(locator.get("source_unit_ref") or "")
            if unit_ref:
                node_types_by_unit.setdefault(unit_ref, set()).add(
                    str(node.get("node_type") or "")
                )

    categories: dict[str, str] = {}
    unit_categories: dict[str, str] = {}
    reason_codes: set[str] = set()
    ready_projection_units: set[str] = set()
    terminal_projection_units: set[str] = set()
    ready_table_text_characters = 0
    ready_table_text_characters_emitted = 0

    for unit in source_units:
        unit_ref = str(unit.get("unit_ref") or "")
        projection = projection_by_unit.get(unit_ref)
        projection_status = str((projection or {}).get("projection_status") or "")
        atom_status = str(unit.get("atom_status") or "")
        text = str(unit.get("text") or "")
        rows = unit.get("rows") or unit.get("cells")
        declared = str(
            unit.get("canonical_node_type")
            or unit.get("semantic_role")
            or unit.get("content_role")
            or ""
        ).upper()
        if not unit_ref or unit_ref not in provenance_unit_refs:
            category = "UNRESOLVED"
            reason_codes.add("pdf_source_unit_provenance_unresolved")
        elif atom_status == "CONFLICT_EVIDENCE":
            category = "CONFLICT"
        elif atom_status == "AMBIGUOUS_EVIDENCE":
            category = "AMBIGUITY"
        elif projection_status == "ready":
            ready_projection_units.add(unit_ref)
            projection_id = str(projection.get("table_projection_id") or "")
            ready_table_text_characters += len(text)
            if projection_id and projection_id in table_projection_ids:
                category = "PRIMARY_TABLE_NODE"
                if "TEXT" in node_types_by_unit.get(unit_ref, set()):
                    ready_table_text_characters_emitted += len(text)
                    reason_codes.add("pdf_ready_table_text_duplicated")
            else:
                category = "UNRESOLVED"
                reason_codes.add("pdf_ready_table_projection_unrepresented")
        elif projection is not None:
            terminal_projection_units.add(unit_ref)
            if text:
                category = "PRIMARY_TEXT_NODE"
            else:
                category = "UNRESOLVED"
                reason_codes.add("pdf_terminal_table_projection_without_fallback")
        elif unit.get("pdf_unit_type") == "pdf_visual_page_unit":
            category = "EVIDENCE_ONLY"
        elif declared in {"HEADING", "NOTE", "LIST"} and text:
            category = "HEADING_OR_NOTE_NODE"
        elif isinstance(rows, list) and rows:
            category = "PRIMARY_TABLE_NODE"
        elif text:
            category = "PRIMARY_TEXT_NODE"
        elif str(unit.get("page_furniture_role") or ""):
            category = "PAGE_FURNITURE"
        else:
            category = "UNRESOLVED"
            reason_codes.add("pdf_source_unit_unresolved")
        unit_categories[unit_ref or f"missing:{len(unit_categories)}"] = category
        selected = [
            str(value)
            for value in (unit.get("coverage") or {}).get("selected_source_refs") or []
            if value
        ]
        atom_refs = selected or [f"unit:{unit_ref}"]
        for atom_ref in atom_refs:
            previous = categories.get(atom_ref)
            if previous is not None and previous != category:
                categories[atom_ref] = "UNRESOLVED"
                reason_codes.add("pdf_source_atom_conflicting_classification")
            else:
                categories[atom_ref] = category

    projection_unit_refs = {
        str(item.get("source_unit_ref") or "")
        for item in table_projections
        if isinstance(item, dict)
    }
    standalone_projection_refs = projection_unit_refs - set(unit_categories)
    for projection_ref in sorted(standalone_projection_refs):
        projection = projection_by_unit[projection_ref]
        projection_id = str(projection.get("table_projection_id") or "")
        atom_ref = f"projection:{projection_ref}"
        if (
            projection.get("projection_status") == "ready"
            and projection_id
            and projection_id in table_projection_ids
            and projection_ref in provenance_unit_refs
        ):
            categories[atom_ref] = "PRIMARY_TABLE_NODE"
            ready_projection_units.add(projection_ref)
        else:
            categories[atom_ref] = "UNRESOLVED"
            reason_codes.add("pdf_table_projection_source_unit_unresolved")

    counts = {category: 0 for category in PDF_SOURCE_ATOM_CATEGORIES}
    for category in categories.values():
        counts[category if category in counts else "UNRESOLVED"] += 1
    unresolved_total = counts["UNRESOLVED"]
    source_atoms_total = len(categories)
    accounted_total = source_atoms_total - unresolved_total
    projection = (
        source_payloads[0].get("pdf_text_layer_projection") or {}
        if len(source_payloads) == 1
        else {}
    )
    source_pages_total = len(projection.get("page_inventory") or [])
    parser_lines_total = len(projection.get("line_inventory") or [])
    page_containers_total = sum(
        item.get("container_type") == "PAGE" for item in containers
    )
    empty_source_document = _proved_empty_pdf(source_payloads)
    if source_pages_total > 0 and not nodes:
        reason_codes.add("pdf_nonempty_zero_nodes")
    if source_pages_total != page_containers_total and not empty_source_document:
        reason_codes.add("pdf_page_container_accounting_mismatch")
    if not source_units and not empty_source_document:
        reason_codes.add("pdf_source_units_unavailable")
    if any(
        item.get("issue_type") == "PARTIAL" and item.get("severity") == "blocking"
        for item in issues
    ):
        reason_codes.add("pdf_blocking_issue_present")

    all_node_refs_resolve = all(
        node.get("source_refs")
        and all(str(ref) in provenance_by_id for ref in node.get("source_refs") or [])
        for node in nodes
    )
    if not all_node_refs_resolve:
        reason_codes.add("pdf_primary_node_source_ref_unresolved")
    accounting_percent = (
        100.0
        if source_atoms_total == 0 and empty_source_document
        else round(accounted_total * 100.0 / source_atoms_total, 6)
        if source_atoms_total
        else 0.0
    )
    duplicate_reduction = (
        100.0
        if ready_table_text_characters == 0
        else round(
            100.0
            * (ready_table_text_characters - ready_table_text_characters_emitted)
            / ready_table_text_characters,
            6,
        )
    )
    passed = (
        not reason_codes
        and unresolved_total == 0
        and accounting_percent == 100.0
        and all_node_refs_resolve
    )
    receipt = {
        "schema_version": PDF_COMPLETENESS_RECEIPT_SCHEMA_VERSION,
        "source_pages_total": source_pages_total,
        "parser_lines_total": parser_lines_total,
        "source_units_total": len(source_units),
        "source_atoms_total": source_atoms_total,
        "source_atoms_accounted_total": accounted_total,
        "source_atom_accounting_percent": accounting_percent,
        "unresolved_source_atoms_total": unresolved_total,
        "logical_container_count": len(containers),
        "page_container_count": page_containers_total,
        "logical_node_count": len(nodes),
        "table_node_count": sum(node.get("node_type") == "TABLE" for node in nodes),
        "table_projections_total": len(table_projections),
        "ready_table_projections_total": len(ready_projection_units),
        "terminal_table_projections_total": len(terminal_projection_units),
        "represented_ready_table_projections_total": len(ready_projection_units),
        "duplicate_table_text_reduction_percent": duplicate_reduction,
        "empty_source_document": empty_source_document,
        "categories": counts,
    }
    return {
        "schema_version": "canonical_pdf_source_atom_accounting_v1",
        "accounting_status": "passed" if passed else "failed",
        "reason_codes": sorted(reason_codes),
        "completeness_receipt": receipt,
    }


def canonical_node_has_machine_content(node: dict[str, Any]) -> bool:
    """Return whether a logical node carries content beyond a format boundary."""

    node_type = str(node.get("node_type") or "")
    content = node.get("content") or {}
    if node_type in {"HEADING", "TEXT", "NOTE"}:
        return bool(str(content.get("text") or "").strip())
    if node_type == "LIST":
        return any(
            str(item.get("text") or "").strip()
            for item in content.get("items") or []
            if isinstance(item, dict)
        )
    if node_type == "TABLE":
        return bool(
            content.get("header")
            or content.get("rows")
            or content.get("cells")
            or str(content.get("title") or "").strip()
            or any(str(value).strip() for value in content.get("notes") or [])
        )
    if node_type in {"CONFLICT", "AMBIGUITY"}:
        return bool(str(content.get("summary") or "").strip())
    return False


def assess_canonical_completeness(artifact: dict[str, Any]) -> dict[str, Any]:
    """Compute the format-neutral, counts-only Gate 2 completeness decision.

    This check intentionally runs both before persistence and after reader
    reconstruction: storage success alone must never make empty or unlinked
    logical content active.
    """

    containers = list(artifact.get("containers") or [])
    nodes = list(artifact.get("nodes") or [])
    issues = list(artifact.get("issues") or [])
    provenance_ids = {
        str(item.get("provenance_id") or "")
        for item in artifact.get("provenance") or []
    }
    source_artifact_ref = str(
        (artifact.get("source") or {}).get("source_artifact_ref") or ""
    )
    provenance_source_links_complete = bool(provenance_ids) and all(
        str(item.get("source_ref") or "") == source_artifact_ref
        for item in artifact.get("provenance") or []
    )
    machine_content_nodes = sum(
        canonical_node_has_machine_content(node) for node in nodes
    )
    explicit_empty = any(
        issue.get("issue_type") == "PARTIAL"
        and issue.get("summary") == "EMPTY_SOURCE_DOCUMENT"
        and issue.get("severity") == "info"
        for issue in issues
    )
    blocking_issues = sum(
        issue.get("severity") in {"blocking", "critical"} for issue in issues
    )
    referenced_items = [*containers, *nodes, *issues]
    source_refs_complete = bool(provenance_ids) and all(
        item.get("source_refs")
        and all(str(ref) in provenance_ids for ref in item.get("source_refs") or [])
        for item in referenced_items
    )
    table_cell_refs_complete = all(
        cell.get("source_refs")
        and all(str(ref) in provenance_ids for ref in cell.get("source_refs") or [])
        for node in nodes
        if node.get("node_type") == "TABLE"
        for cell in (node.get("content") or {}).get("cells") or []
    )
    reason_codes: list[str] = []
    if (
        not source_refs_complete
        or not table_cell_refs_complete
        or not provenance_source_links_complete
    ):
        reason_codes.append("canonical_source_ref_accounting_incomplete")
    if blocking_issues:
        reason_codes.append("canonical_blocking_issue_present")
    if machine_content_nodes == 0 and not explicit_empty:
        reason_codes.append("canonical_machine_content_empty")
    if explicit_empty and (
        machine_content_nodes
        or any(node.get("node_type") in {"PAGE_BREAK", "SHEET_BREAK"} for node in nodes)
    ):
        reason_codes.append("canonical_empty_source_contract_invalid")
    return {
        "schema_version": "canonical_completeness_assessment_v1",
        "source_format": str((artifact.get("source") or {}).get("source_format") or ""),
        "logical_container_count": len(containers),
        "logical_node_count": len(nodes),
        "machine_content_node_count": machine_content_nodes,
        "issues_total": len(issues),
        "blocking_issues_total": blocking_issues,
        "explicit_empty_source": explicit_empty,
        "source_refs_complete": source_refs_complete,
        "table_cell_refs_complete": table_cell_refs_complete,
        "provenance_source_links_complete": provenance_source_links_complete,
        "status": "passed" if not reason_codes else "failed",
        "reason_codes": sorted(set(reason_codes)),
    }


def validate_canonical_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate schema, references, ordering and fail-closed completeness."""

    errors: list[str] = []
    if artifact.get("schema_version") != CANONICAL_ARTIFACT_SCHEMA_VERSION:
        errors.append("canonical_schema_version_mismatch")
    if not artifact.get("tenant_id"):
        errors.append("canonical_tenant_required")
    if not artifact.get("normalizer_version"):
        errors.append("canonical_normalizer_version_required")
    artifact_version = artifact.get("artifact_version")
    if not isinstance(artifact_version, int) or artifact_version < 1:
        errors.append("canonical_artifact_version_invalid")

    containers = artifact.get("containers") or []
    nodes = artifact.get("nodes") or []
    provenance = artifact.get("provenance") or []
    issues = artifact.get("issues") or []
    source = artifact.get("source") or {}
    source_format = str(source.get("source_format") or "")
    container_ids = [str(item.get("container_id") or "") for item in containers]
    node_ids = [str(item.get("node_id") or "") for item in nodes]
    provenance_ids = {str(item.get("provenance_id") or "") for item in provenance}
    provenance_by_id = {
        str(item.get("provenance_id") or ""): item for item in provenance
    }
    issue_ids = {str(item.get("issue_id") or "") for item in issues}
    root_ref = str(artifact.get("root_container_ref") or "")
    root = next(
        (item for item in containers if item.get("container_id") == root_ref),
        {},
    )

    if source_format not in CANONICAL_SOURCE_FORMATS:
        errors.append("canonical_source_format_invalid")
    if not source.get("source_artifact_ref") or not source.get("mime_type"):
        errors.append("canonical_source_identity_incomplete")
    if len(str(source.get("source_sha256") or "")) != 64:
        errors.append("canonical_source_sha256_invalid")
    if len(container_ids) != len(set(container_ids)) or "" in container_ids:
        errors.append("canonical_container_ids_invalid")
    if len(node_ids) != len(set(node_ids)) or "" in node_ids:
        errors.append("canonical_node_ids_invalid")
    if root_ref not in container_ids:
        errors.append("canonical_root_container_unresolved")
    if root and root.get("parent_container_ref") is not None:
        errors.append("canonical_root_container_parent_invalid")
    if root and root.get("container_type") != CANONICAL_ROOT_TYPE_BY_FORMAT.get(
        source_format
    ):
        errors.append("canonical_root_container_type_invalid")

    for container in containers:
        if container.get("container_type") not in CANONICAL_CONTAINER_TYPES:
            errors.append("canonical_container_type_invalid")
        parent = container.get("parent_container_ref")
        if parent is not None and parent not in container_ids:
            errors.append("canonical_container_parent_unresolved")
        refs = container.get("source_refs") or []
        if not refs or any(str(ref) not in provenance_ids for ref in refs):
            errors.append("canonical_container_source_ref_unresolved")
    for parent in {item.get("parent_container_ref") for item in containers}:
        orders = sorted(
            int(item.get("order") or 0)
            for item in containers
            if item.get("parent_container_ref") == parent
        )
        if orders != list(range(len(orders))):
            errors.append("canonical_container_order_non_contiguous")
    for container_id in container_ids:
        orders = sorted(
            int(item.get("order") or 0)
            for item in nodes
            if item.get("container_ref") == container_id
        )
        if orders != list(range(len(orders))):
            errors.append("canonical_node_order_non_contiguous")

    for issue in issues:
        if issue.get("issue_type") not in {
            "CONFLICT",
            "AMBIGUITY",
            "UNSUPPORTED",
            "PARTIAL",
        }:
            errors.append("canonical_issue_type_invalid")
        if issue.get("severity") not in {"info", "warning", "blocking"}:
            errors.append("canonical_issue_severity_invalid")
        refs = issue.get("source_refs") or []
        if not refs or any(str(ref) not in provenance_ids for ref in refs):
            errors.append("canonical_issue_source_ref_unresolved")
    for node in nodes:
        node_type = str(node.get("node_type") or "")
        content = node.get("content")
        if node_type not in CANONICAL_NODE_TYPES:
            errors.append("canonical_node_type_invalid")
        if not isinstance(content, dict):
            errors.append("canonical_node_content_invalid")
            content = {}
        if node.get("container_ref") not in container_ids:
            errors.append("canonical_node_container_unresolved")
        refs = node.get("source_refs") or []
        if not refs or any(str(ref) not in provenance_ids for ref in refs):
            errors.append("canonical_node_source_ref_unresolved")
        if any(str(ref) not in issue_ids for ref in node.get("issue_refs") or []):
            errors.append("canonical_node_issue_ref_unresolved")
        if node_type in {"HEADING", "TEXT", "NOTE"} and not isinstance(
            content.get("text"), str
        ):
            errors.append("canonical_text_node_content_invalid")
        elif node_type == "LIST" and not isinstance(content.get("items"), list):
            errors.append("canonical_list_node_content_invalid")
        elif node_type == "TABLE":
            if any(
                not isinstance(content.get(field), list)
                for field in ("header", "rows", "notes", "cells")
            ):
                errors.append("canonical_table_node_content_invalid")
            for cell in content.get("cells") or []:
                cell_refs = cell.get("source_refs") or []
                if not cell_refs or any(
                    str(ref) not in provenance_ids for ref in cell_refs
                ):
                    errors.append("canonical_table_cell_source_ref_unresolved")
            node_source_refs = [str(ref) for ref in node.get("source_refs") or []]
            node_source_locator = (
                (provenance_by_id.get(node_source_refs[0]) or {}).get(
                    "source_locator"
                )
                if len(node_source_refs) == 1
                else None
            )
            if isinstance(node_source_locator, dict) and (
                "table_title_binding" in node_source_locator
                or "table_header_binding" in node_source_locator
            ):
                errors.extend(
                    _canonical_table_source_binding_errors(
                        content=content,
                        source_locator=node_source_locator,
                        provenance_by_id=provenance_by_id,
                    )
                )
        elif node_type in {"PAGE_BREAK", "SHEET_BREAK"} and not str(
            content.get("boundary_ref") or ""
        ):
            errors.append("canonical_break_node_content_invalid")
        elif node_type in {"CONFLICT", "AMBIGUITY"} and not str(
            content.get("summary") or ""
        ):
            errors.append("canonical_issue_node_content_invalid")

    completeness = assess_canonical_completeness(artifact)
    errors.extend(completeness["reason_codes"])

    if source_format == "pdf":
        receipt = (root.get("metadata") or {}).get("pdf_completeness") or {}
        page_containers = sum(
            item.get("container_type") == "PAGE" for item in containers
        )
        empty_issue = any(
            item.get("issue_type") == "PARTIAL"
            and item.get("summary") == "EMPTY_SOURCE_DOCUMENT"
            for item in issues
        )
        empty_source = receipt.get("empty_source_document") is True
        if receipt.get("schema_version") != PDF_COMPLETENESS_RECEIPT_SCHEMA_VERSION:
            errors.append("canonical_pdf_completeness_receipt_missing")
        if int(receipt.get("logical_node_count") or 0) != len(nodes):
            errors.append("canonical_pdf_completeness_node_count_mismatch")
        if int(receipt.get("logical_container_count") or 0) != len(containers):
            errors.append("canonical_pdf_completeness_container_count_mismatch")
        if int(receipt.get("page_container_count") or 0) != page_containers:
            errors.append("canonical_pdf_completeness_page_count_mismatch")
        if float(receipt.get("source_atom_accounting_percent") or 0.0) != 100.0:
            errors.append("canonical_pdf_source_atom_accounting_incomplete")
        if int(receipt.get("unresolved_source_atoms_total") or 0) != 0:
            errors.append("canonical_pdf_source_atoms_unresolved")
        if not nodes and not (empty_source and empty_issue):
            errors.append("canonical_pdf_nonempty_zero_nodes")
        if empty_source and (nodes or page_containers or not empty_issue):
            errors.append("canonical_pdf_empty_source_contract_invalid")
        if any(
            item.get("issue_type") == "PARTIAL" and item.get("severity") == "blocking"
            for item in issues
        ):
            errors.append("canonical_pdf_blocking_issue_present")

    lowered_keys = {key.lower() for key in _walk_keys(artifact)}
    if lowered_keys & FORBIDDEN_FIELDS:
        errors.append("canonical_financial_semantics_forbidden")
    if (
        not isinstance(artifact.get("canonical_root_hash"), str)
        or len(artifact.get("canonical_root_hash") or "") != 64
    ):
        errors.append("canonical_root_hash_invalid")
    else:
        expected_hash = _sha256(
            _root_hash_material(
                normalizer_version=str(artifact.get("normalizer_version") or ""),
                source_format=source_format,
                source_sha256=str(source.get("source_sha256") or ""),
                containers=containers,
                nodes=nodes,
                provenance=provenance,
                issues=issues,
            )
        )
        if artifact.get("canonical_root_hash") != expected_hash:
            errors.append("canonical_root_hash_mismatch")
    return {
        "schema_version": "canonical_artifact_validation_v1",
        "passed": not errors,
        "validator_status": "passed" if not errors else "failed",
        "error_codes": sorted(set(errors)),
        "completeness": completeness,
    }


def canonical_compare_receipt(
    artifact: dict[str, Any], *, legacy_source_units: list[dict[str, Any]]
) -> dict[str, Any]:
    canonical_source_refs = {
        ref
        for node in artifact.get("nodes") or []
        for ref in node.get("source_refs") or []
    }
    source_unit_refs = {str(item.get("unit_ref") or "") for item in legacy_source_units}
    legacy_scalar_values_total = sum(
        len(row)
        for unit in legacy_source_units
        for row in (unit.get("rows") or unit.get("cells") or [])
        if isinstance(row, list)
    )
    canonical_scalar_values_total = sum(
        len(node.get("content", {}).get("cells") or [])
        for node in artifact.get("nodes") or []
        if node.get("node_type") == "TABLE"
    )
    legacy_text_characters_total = sum(
        len(str(unit.get("text") or "")) for unit in legacy_source_units
    )
    canonical_text_characters_total = sum(
        len(str((node.get("content") or {}).get("text") or ""))
        for node in artifact.get("nodes") or []
        if node.get("node_type") in {"HEADING", "TEXT", "NOTE"}
    ) + sum(
        len(str(item.get("text") or ""))
        for node in artifact.get("nodes") or []
        if node.get("node_type") == "LIST"
        for item in (node.get("content") or {}).get("items") or []
    )
    exact_content_accounting = bool(legacy_source_units) and (
        legacy_scalar_values_total == canonical_scalar_values_total
        and legacy_text_characters_total == canonical_text_characters_total
    )
    provenance_ids = {
        str(item.get("provenance_id") or "")
        for item in artifact.get("provenance") or []
    }
    provenance_complete = bool(canonical_source_refs) and (
        canonical_source_refs <= provenance_ids
    )
    return {
        "schema_version": "canonical_legacy_compare_receipt_v1",
        "canonical_artifact_id": artifact.get("artifact_id"),
        "canonical_root_hash": artifact.get("canonical_root_hash"),
        "legacy_source_units_total": len(source_unit_refs),
        "canonical_nodes_total": len(artifact.get("nodes") or []),
        "canonical_source_refs_total": len(canonical_source_refs),
        "legacy_scalar_values_total": legacy_scalar_values_total,
        "canonical_scalar_values_total": canonical_scalar_values_total,
        "legacy_text_characters_total": legacy_text_characters_total,
        "canonical_text_characters_total": canonical_text_characters_total,
        "presence_status": "matched" if exact_content_accounting else "inconclusive",
        "order_status": "validated_contiguous",
        "provenance_status": "resolved" if provenance_complete else "inconclusive",
        "critical_loss_status": "not_detected"
        if exact_content_accounting
        else "inconclusive",
        "comparison_status": "matched"
        if exact_content_accounting and provenance_complete
        else "inconclusive",
        "authoritative_representation": "legacy_gate2_handoff_v0",
        "cutover_authorized": False,
    }


def _cells_from_rows(rows: list[list[Any]], source_ref: str) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row, start=1):
            cell_type = (
                "blank"
                if value is None or value == ""
                else "boolean"
                if isinstance(value, bool)
                else "number"
                if isinstance(value, (int, float))
                else "string"
            )
            cells.append(
                {
                    "row": row_index,
                    "column": column_index,
                    "value": value,
                    "raw_value": value,
                    "displayed_value": None if value is None else str(value),
                    "cell_type": cell_type,
                    "formula": None,
                    "merged_range": None,
                    "source_coordinate": f"R{row_index}C{column_index}",
                    "hidden": False,
                    "number_format_ref": None,
                    "source_refs": [source_ref],
                }
            )
    return cells


def _normalize_canonical_cells(
    cells: list[dict[str, Any]],
    source_ref: str,
    *,
    preserve_source_refs: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for cell in cells:
        item = copy.deepcopy(cell)
        if not preserve_source_refs:
            item["source_refs"] = [source_ref]
        item.setdefault("number_format_ref", None)
        result.append(item)
    return result


def _projection_matrix(projection: dict[str, Any]) -> list[list[Any]]:
    values = {
        str(item.get("value_path_ref") or ""): item.get("normalized_value")
        for item in projection.get("private_values") or []
        if isinstance(item, dict)
    }
    row_count = int(projection.get("row_count") or 0)
    column_count = int(projection.get("column_count") or 0)
    matrix: list[list[Any]] = [
        [None for _ in range(column_count)] for _ in range(row_count)
    ]
    for cell in projection.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        row_value = cell.get("row_ordinal")
        column_value = cell.get("column_ordinal")
        if row_value is None and isinstance(cell.get("logical_row_index"), int):
            row_value = int(cell["logical_row_index"]) + 1
        if column_value is None and isinstance(
            cell.get("logical_column_index"), int
        ):
            column_value = int(cell["logical_column_index"]) + 1
        row = int(row_value or 0)
        column = int(column_value or 0)
        if 1 <= row <= row_count and 1 <= column <= column_count:
            matrix[row - 1][column - 1] = values.get(
                str(cell.get("normalized_private_value_path") or "")
            )
    return matrix


def _validate_bound_projection_inputs(
    source_payloads: list[dict[str, Any]],
    source_units: list[dict[str, Any]],
    table_projections: list[dict[str, Any]],
) -> None:
    """Rebuild B1 custody before promotion; persisted Canonical has no source ledger."""

    bound = [
        item
        for item in table_projections
        if "table_title_binding" in item or "bound_header_row_count" in item
    ]
    if not bound:
        return
    rebuilt = NormalizedTableProjectionFactory().create().build_for_document(
        source_format="pdf",
        payloads=source_payloads,
        source_units=source_units,
    )
    rebuilt_by_id = {
        str(item.get("table_projection_id") or ""): item
        for item in rebuilt.projections
    }
    if any(
        rebuilt_by_id.get(str(item.get("table_projection_id") or "")) != item
        or item.get("validator_status") != "passed"
        for item in bound
    ):
        raise CanonicalArtifactError("canonical_pdf_table_projection_custody_invalid")


def _projection_table_material(
    projection: dict[str, Any], source_location: dict[str, Any]
) -> tuple[list[list[Any]], dict[str, Any], Any, bool]:
    matrix = _projection_matrix(projection)
    location = {
        **source_location,
        "source_unit_ref": str(projection.get("source_unit_ref") or ""),
        "table_projection_id": str(projection.get("table_projection_id") or ""),
        "source_kind": "source_bound_table_projection",
    }
    if not {
        "table_title_binding",
        "bound_header_row_count",
    } <= set(projection):
        return (
            matrix,
            location,
            None,
            bool((projection.get("header_model") or {}).get("header_row_refs")),
        )
    if projection.get("validator_status") != "passed":
        raise CanonicalArtifactError("canonical_pdf_table_source_binding_not_validated")
    title_binding = copy.deepcopy(projection.get("table_title_binding"))
    if _title_binding_error(title_binding, (title_binding or {}).get("value")):
        raise CanonicalArtifactError("canonical_pdf_table_title_binding_invalid")
    try:
        header_count = int(projection.get("bound_header_row_count") or 0)
    except (TypeError, ValueError) as exc:
        raise CanonicalArtifactError("canonical_pdf_table_header_binding_invalid") from exc
    projection_rows = sorted(
        [item for item in projection.get("rows") or [] if isinstance(item, dict)],
        key=lambda item: int(item.get("row_ordinal") or 0),
    )
    if header_count < 0 or header_count > len(matrix):
        raise CanonicalArtifactError("canonical_pdf_table_header_binding_invalid")
    expected_header_row_refs = [
        str(item.get("row_ref") or "") for item in projection_rows[:header_count]
    ]
    header_model = projection.get("header_model") or {}
    header_row_ref_set = set(expected_header_row_refs)
    header_source_refs = [
        str(ref)
        for cell in projection.get("cells") or []
        if isinstance(cell, dict)
        and str(cell.get("row_ref") or "") in header_row_ref_set
        for ref in cell.get("source_value_refs") or []
    ]
    header_material = {"row_refs": expected_header_row_refs, "source_value_refs": header_source_refs}
    if (
        any(not ref for ref in expected_header_row_refs)
        or list(header_model.get("header_row_refs") or []) != expected_header_row_refs
        or list(header_model.get("source_value_refs") or []) != header_source_refs
        or header_model.get("source_checksum_ref") != _checksum_ref("pdfheaderchk", header_material)
    ):
        raise CanonicalArtifactError("canonical_pdf_table_header_binding_invalid")
    location.update({
        "table_title_binding": title_binding,
        "table_header_binding": {
            "bound_header_row_count": header_count,
            "header_row_refs": expected_header_row_refs,
            "source_value_refs": header_source_refs,
            "source_checksum_ref": header_model.get("source_checksum_ref"),
        },
        "table_projection_checksum_ref": projection.get(
            "table_projection_checksum_ref"
        ),
    })
    header, body = _spanned_table_view(
        _projection_span_entries(projection),
        row_count=int(projection.get("row_count") or 0),
        column_count=int(projection.get("column_count") or 0),
        header_row_count=header_count,
    )
    rows = [header, *body] if header_count else matrix
    return rows, location, (title_binding or {}).get("value"), bool(header_count)


def _projection_span_entries(projection: dict[str, Any]) -> list[dict[str, Any]]:
    values = {str(item.get("value_path_ref") or ""): item.get("normalized_value") for item in projection.get("private_values") or [] if isinstance(item, dict)}
    return [
        {
            "cell_ref": str(cell.get("cell_ref") or ""),
            "row": int(cell.get("row_ordinal") or 0),
            "column": int(cell.get("column_ordinal") or 0),
            "row_span": max(1, int(cell.get("row_span") or 1)),
            "column_span": max(1, int(cell.get("column_span") or 1)),
            "value": values.get(str(cell.get("normalized_private_value_path") or "")),
        }
        for cell in projection.get("cells") or []
        if isinstance(cell, dict)
    ]


def _projection_canonical_cells(
    builder: "_LogicalBuilder",
    projection: dict[str, Any],
    source_location: dict[str, Any],
) -> list[dict[str, Any]] | None:
    projection_cells = [
        cell for cell in projection.get("cells") or [] if isinstance(cell, dict)
    ]
    exact_ref_contract = any(
        "cell_ref" in cell or "source_value_refs" in cell
        for cell in projection_cells
    )
    rectangular_cell_count = int(projection.get("row_count") or 0) * int(
        projection.get("column_count") or 0
    )
    if not exact_ref_contract and len(projection_cells) >= rectangular_cell_count:
        return None
    if exact_ref_contract and any(
        not str(cell.get("cell_ref") or "")
        or not isinstance(cell.get("source_value_refs"), list)
        for cell in projection_cells
    ):
        raise CanonicalArtifactError(
            "canonical_pdf_table_projection_cell_refs_incomplete"
        )
    values = {
        str(item.get("value_path_ref") or ""): item.get("normalized_value")
        for item in projection.get("private_values") or []
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for cell in projection_cells:
        row_value = cell.get("row_ordinal")
        column_value = cell.get("column_ordinal")
        if row_value is None and isinstance(cell.get("logical_row_index"), int):
            row_value = int(cell["logical_row_index"]) + 1
        if column_value is None and isinstance(
            cell.get("logical_column_index"), int
        ):
            column_value = int(cell["logical_column_index"]) + 1
        row = int(row_value or 0)
        column = int(column_value or 0)
        if row < 1 or column < 1:
            continue
        value = values.get(str(cell.get("normalized_private_value_path") or ""))
        locator = {
            "kind": "pdf_table_projection_cell",
            "page": int(source_location.get("page") or 0),
            "source_unit_ref": str(projection.get("source_unit_ref") or ""),
            "table_projection_id": str(
                projection.get("table_projection_id") or ""
            ),
            "cell_ref": str(cell.get("cell_ref") or ""),
            "row_ref": str(cell.get("row_ref") or ""),
            "row": row,
            "column": column,
            "row_span": max(1, int(cell.get("row_span") or 1)),
            "column_span": max(1, int(cell.get("column_span") or 1)),
            "bbox_ref": cell.get("bbox_ref"),
            "source_value_refs": [
                str(item) for item in cell.get("source_value_refs") or []
            ],
        }
        cell_type = (
            "blank"
            if value is None or value == ""
            else "boolean"
            if isinstance(value, bool)
            else "number"
            if isinstance(value, (int, float))
            else "string"
        )
        row_span = max(1, int(cell.get("row_span") or 1))
        column_span = max(1, int(cell.get("column_span") or 1))
        result.append(
            {
                "row": row,
                "column": column,
                "value": value,
                "raw_value": value,
                "displayed_value": None if value is None else str(value),
                "cell_type": cell_type,
                "formula": None,
                "merged_range": (
                    f"R{row}C{column}:R{row + row_span - 1}C{column + column_span - 1}"
                    if row_span > 1 or column_span > 1
                    else None
                ),
                "source_coordinate": str(
                    cell.get("cell_ref") or f"R{row}C{column}"
                ),
                "hidden": False,
                "number_format_ref": None,
                "source_refs": [builder._provenance_ref(locator)],
            }
        )
    return result


def _canonical_table_source_binding_errors(
    *,
    content: dict[str, Any],
    source_locator: dict[str, Any],
    provenance_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if set(source_locator) >= {"table_title_binding", "table_header_binding"}:
        title_binding = source_locator.get("table_title_binding")
        if _title_binding_error(title_binding, content.get("title")):
            errors.append("canonical_table_title_binding_mismatch")

        header_binding = source_locator.get("table_header_binding")
        if not isinstance(header_binding, dict) or set(header_binding) != {
            "bound_header_row_count",
            "header_row_refs",
            "source_value_refs",
            "source_checksum_ref",
        }:
            errors.append("canonical_table_header_binding_invalid")
            return errors
        try:
            header_count = int(header_binding.get("bound_header_row_count") or 0)
        except (TypeError, ValueError):
            errors.append("canonical_table_header_binding_invalid")
            return errors
        header_row_refs = [str(ref) for ref in header_binding.get("header_row_refs") or []]
        header_source_refs = [
            str(ref) for ref in header_binding.get("source_value_refs") or []
        ]
        header_material = {
            "row_refs": header_row_refs,
            "source_value_refs": header_source_refs,
        }
        if (
            header_count < 0
            or len(header_row_refs) != header_count
            or len(header_row_refs) != len(set(header_row_refs))
            or len(header_source_refs) != len(set(header_source_refs))
            or header_binding.get("source_checksum_ref")
            != _checksum_ref("pdfheaderchk", header_material)
        ):
            errors.append("canonical_table_header_binding_invalid")

        resolved_cells: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for cell in content.get("cells") or []:
            refs = [str(ref) for ref in cell.get("source_refs") or []]
            locator = (
                (provenance_by_id.get(refs[0]) or {}).get("source_locator")
                if len(refs) == 1
                else None
            )
            if not isinstance(locator, dict) or locator.get("kind") != "pdf_table_projection_cell":
                errors.append("canonical_table_binding_cell_provenance_invalid")
                continue
            resolved_cells.append((cell, locator))
        resolved_cells.sort(key=lambda item: (int(item[1].get("row") or 0), int(item[1].get("column") or 0)))
        header_cells = [
            item
            for item in resolved_cells
            if 1 <= int(item[1].get("row") or 0) <= header_count
        ]
        derived_row_refs: list[str] = []
        for row in range(1, header_count + 1):
            row_refs = {
                str(locator.get("row_ref") or "")
                for _cell, locator in header_cells
                if int(locator.get("row") or 0) == row
            }
            if len(row_refs) != 1 or "" in row_refs:
                errors.append("canonical_table_header_row_refs_invalid")
                continue
            derived_row_refs.append(next(iter(row_refs)))
        derived_source_refs = [str(ref) for _cell, locator in header_cells for ref in locator.get("source_value_refs") or []]
        if derived_row_refs != header_row_refs or derived_source_refs != header_source_refs:
            errors.append("canonical_table_header_source_binding_mismatch")
        try:
            derived_header, derived_body = _canonical_bound_table_view(
                resolved_cells, header_count
            )
        except (CanonicalArtifactError, TypeError, ValueError):
            errors.append("canonical_table_binding_cell_geometry_invalid")
            return errors
        if content.get("header") != derived_header:
            errors.append("canonical_table_header_vector_mismatch")
        if content.get("rows") != derived_body:
            errors.append("canonical_table_body_rows_mismatch")
    else:
        errors.append("canonical_table_source_binding_pair_incomplete")
    return errors


def _canonical_bound_table_view(
    resolved_cells: list[tuple[dict[str, Any], dict[str, Any]]],
    header_row_count: int,
) -> tuple[list[Any], list[list[Any]]]:
    entries = [
        {
            "cell_ref": str(locator.get("cell_ref") or ""),
            "row": int(locator.get("row") or 0),
            "column": int(locator.get("column") or 0),
            "row_span": max(1, int(locator.get("row_span") or 1)),
            "column_span": max(1, int(locator.get("column_span") or 1)),
            "value": cell.get("value"),
        }
        for cell, locator in resolved_cells
    ]
    return _spanned_table_view(
        entries,
        row_count=max(
            (item["row"] + item["row_span"] - 1 for item in entries), default=0
        ),
        column_count=max(
            (
                item["column"] + item["column_span"] - 1
                for item in entries
            ),
            default=0,
        ),
        header_row_count=header_row_count,
    )


def _spanned_table_view(
    entries: list[dict[str, Any]],
    *,
    row_count: int,
    column_count: int,
    header_row_count: int,
) -> tuple[list[Any], list[list[Any]]]:
    matrix: list[list[Any]] = [
        [None for _ in range(column_count)] for _ in range(row_count)
    ]
    for item in entries:
        row, column = int(item["row"]), int(item["column"])
        if 1 <= row <= row_count and 1 <= column <= column_count:
            matrix[row - 1][column - 1] = item.get("value")
    if header_row_count == 0:
        return [], matrix
    header: list[Any] = []
    for column in range(1, column_count + 1):
        parts: list[str] = []
        seen: set[str] = set()
        for row in range(1, header_row_count + 1):
            covering = [
                item
                for item in entries
                if item["row"] <= row < item["row"] + item["row_span"]
                and item["column"]
                <= column
                < item["column"] + item["column_span"]
            ]
            if len(covering) > 1:
                raise CanonicalArtifactError(
                    "canonical_pdf_table_header_cell_overlap"
                )
            if not covering or covering[0]["cell_ref"] in seen:
                continue
            item = covering[0]
            seen.add(item["cell_ref"])
            if item.get("value") not in (None, ""):
                parts.append(str(item["value"]))
        header.append("\n".join(parts) if parts else None)
    return header, matrix[header_row_count:]


def _unique_nonempty_strings(value: Any) -> bool:
    refs = [str(item) for item in value or []] if isinstance(value, list) else []
    return bool(refs) and all(refs) and len(refs) == len(set(refs))


def _title_binding_error(binding: Any, title: Any) -> bool:
    if binding is None:
        return title is not None
    keys = {"value", "word_refs", "line_refs", "source_value_refs", "checksum_ref"}
    return (
        not isinstance(binding, dict)
        or set(binding) != keys
        or title != binding.get("value")
        or not isinstance(binding.get("value"), str)
        or any(not _unique_nonempty_strings(binding.get(field)) for field in ("word_refs", "line_refs", "source_value_refs"))
        or binding.get("checksum_ref") != _checksum_ref("pdftitlechk", {key: value for key, value in binding.items() if key != "checksum_ref"})
    )


def _checksum_ref(prefix: str, value: Any) -> str:
    return f"{prefix}_{_sha256(value)[:24]}"


def _projection_page(projection: dict[str, Any]) -> int:
    page_refs = projection.get("page_refs")
    if not isinstance(page_refs, list) or len(page_refs) != 1:
        raise CanonicalArtifactError("canonical_pdf_table_projection_page_invalid")
    page_ref = str(page_refs[0] or "")
    prefix = "page_"
    if not page_ref.startswith(prefix) or not page_ref[len(prefix) :].isdigit():
        raise CanonicalArtifactError("canonical_pdf_table_projection_page_invalid")
    page = int(page_ref[len(prefix) :])
    if page < 1:
        raise CanonicalArtifactError("canonical_pdf_table_projection_page_invalid")
    return page


def _projection_location(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": _projection_page(projection),
        "source_unit_ref": str(projection.get("source_unit_ref") or ""),
        "table_projection_id": str(projection.get("table_projection_id") or ""),
        "source_kind": "source_bound_table_projection",
    }


def _location(value: dict[str, Any]) -> dict[str, Any]:
    location = value.get("source_location") or value.get("location") or {}
    return dict(location) if isinstance(location, dict) else {}


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _root_hash_material(
    *,
    normalizer_version: str,
    source_format: str,
    source_sha256: str,
    containers: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_ARTIFACT_SCHEMA_VERSION,
        "normalizer_version": normalizer_version,
        "source_format": source_format,
        "source_sha256": source_sha256,
        "containers": containers,
        "nodes": nodes,
        "provenance": [
            {
                "provenance_id": item.get("provenance_id"),
                "source_locator": item.get("source_locator") or {},
            }
            for item in provenance
        ],
        "issues": issues,
    }


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
