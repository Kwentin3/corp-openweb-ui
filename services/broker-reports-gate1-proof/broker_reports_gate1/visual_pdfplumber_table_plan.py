from __future__ import annotations

import copy
import hashlib
import importlib.metadata
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pdfplumber

from .canonical_artifact import (
    CANONICAL_NORMALIZER_POLICY_VERSION,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    validate_canonical_artifact,
)
from .contracts import stable_digest
from .full_source import FullSourceArtifactConfig, FullSourceArtifactFactory
from .pdf_layout import PDF_LAYOUT_POLICY_VERSION, PDFPLUMBER_PINNED_VERSION
from .pdf_layout_units import PdfLayoutUnitBuilder
from .pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
    pdf_layout_page_checksum_ref,
    pdf_payload_checksum_ref,
    validate_pdf_text_layer_payload,
)
from .table_projection import NormalizedTableProjectionFactory


FACTORY_REQUIRED = (
    "VisualPdfPlumberTableAdapterFactory.create is the only G5.100 research "
    "adapter entrypoint"
)
FORBIDDEN = (
    "The G5.100 adapter must not consume VLM cell values, expose tolerance "
    "settings, call a breadcrumb resolver, mint a second Canonical schema, "
    "or enter product routing"
)

ADAPTER_VERSION = "visual_pdfplumber_table_adapter_g5100_v1"
PLAN_SCHEMA_VERSION = "broker_reports_pdfplumber_table_plan_g5100_v1"
TERMINAL_EXTRACTED = "NATIVE_TABLE_EXTRACTED"
TERMINAL_NO_TABLE = "NO_TABLE_PLAN"
TERMINAL_NOT_FOUND = "NATIVE_TABLE_NOT_FOUND"
TERMINAL_AMBIGUOUS = "NATIVE_TABLE_AMBIGUOUS"
TERMINAL_SOURCE_BINDING_FAILED = "SOURCE_BINDING_FAILED"

_PAGE_KEYS = frozenset({"tables"})
_TABLE_KEYS = frozenset(
    {
        "bbox",
        "vertical_strategy",
        "explicit_vertical_lines",
        "horizontal_strategy",
    }
)
_HORIZONTAL_STRATEGIES = frozenset({"lines", "text"})
_FORBIDDEN_PLAN_KEYS = frozenset(
    {
        "body",
        "body_rows",
        "body_values",
        "cell_values",
        "cells",
        "rows",
        "values",
        "amount",
        "date",
        "security",
        "financial_semantics",
        "snap_tolerance",
        "snap_x_tolerance",
        "snap_y_tolerance",
        "join_tolerance",
        "join_x_tolerance",
        "join_y_tolerance",
        "intersection_tolerance",
        "intersection_x_tolerance",
        "intersection_y_tolerance",
        "text_tolerance",
        "text_x_tolerance",
        "text_y_tolerance",
        "min_words_vertical",
        "min_words_horizontal",
        "explicit_horizontal_lines",
    }
)


class VisualPdfPlumberTablePlanError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VisualPdfPlumberTableAdapterConfig:
    expected_pdfplumber_version: str = PDFPLUMBER_PINNED_VERSION
    maximum_tables_per_page: int = 12
    maximum_vertical_lines_per_table: int = 40


class VisualPdfPlumberTableAdapterFactory:
    def __init__(
        self, config: VisualPdfPlumberTableAdapterConfig | None = None
    ) -> None:
        self.config = config or VisualPdfPlumberTableAdapterConfig()

    def create(self) -> "VisualPdfPlumberTableAdapter":
        if self.config.maximum_tables_per_page <= 0:
            raise VisualPdfPlumberTablePlanError("g5100_table_budget_invalid")
        if self.config.maximum_vertical_lines_per_table < 2:
            raise VisualPdfPlumberTablePlanError("g5100_vertical_line_budget_invalid")
        return VisualPdfPlumberTableAdapter(self.config)


class VisualPdfPlumberTableAdapter:
    """Research-only native table-plan adapter inside the Gate 2 boundary.

    The VLM supplies only a crop and native pdfplumber table settings.  The
    maintained parser owns source words, the maintained layout-unit builder
    owns source refs, and the maintained table/canonical factories own the
    final Gate 2 representation.
    """

    def __init__(self, config: VisualPdfPlumberTableAdapterConfig) -> None:
        self.config = config

    def execute_single_page(
        self,
        *,
        pdf_bytes: bytes,
        image_width_pixels: int,
        image_height_pixels: int,
        plan: dict[str, Any],
        document_id: str,
    ) -> dict[str, Any]:
        self._validate_runtime()
        validate_pdfplumber_table_plan(
            plan,
            image_width_pixels=image_width_pixels,
            image_height_pixels=image_height_pixels,
            maximum_tables=self.config.maximum_tables_per_page,
            maximum_vertical_lines=self.config.maximum_vertical_lines_per_table,
        )
        if not pdf_bytes.startswith(b"%PDF-"):
            raise VisualPdfPlumberTablePlanError("g5100_pdf_header_missing")

        source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        base = FullSourceArtifactFactory(
            FullSourceArtifactConfig(enable_pdf_layout_slice2=False)
        ).create().build(
            normalization_run_id="g5100_native_plan",
            document_id=document_id,
            profile_id="g5100_research_only",
            container_format="pdf",
            content_bytes=pdf_bytes,
            source_checksum_sha256=source_sha256,
        )
        if len(base.payloads) != 1:
            raise VisualPdfPlumberTablePlanError("g5100_base_payload_invalid")

        parser = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="table_candidates")
        )
        parsed = parser.parse(pdf_bytes)
        if parsed.layout_projection_status != "complete" or len(parsed.pages) != 1:
            return {
                "adapter_version": ADAPTER_VERSION,
                "plan_schema_version": PLAN_SCHEMA_VERSION,
                "terminal": TERMINAL_SOURCE_BINDING_FAILED,
                "reason": "g5100_layout_projection_incomplete",
                "tables": [],
                "canonical": None,
                "canonical_metrics": _empty_canonical_metrics(),
                "parser": _parser_evidence(parsed),
            }

        page = parsed.pages[0]
        native_tables, terminals = self._execute_native_tables(
            pdf_bytes=pdf_bytes,
            image_width_pixels=image_width_pixels,
            image_height_pixels=image_height_pixels,
            plan=plan,
            parser_page=page,
        )
        if any(item["terminal"] != TERMINAL_EXTRACTED for item in terminals):
            return {
                "adapter_version": ADAPTER_VERSION,
                "plan_schema_version": PLAN_SCHEMA_VERSION,
                "terminal": next(
                    item["terminal"]
                    for item in terminals
                    if item["terminal"] != TERMINAL_EXTRACTED
                ),
                "reason": next(
                    item.get("reason")
                    for item in terminals
                    if item["terminal"] != TERMINAL_EXTRACTED
                ),
                "tables": terminals,
                "canonical": None,
                "canonical_metrics": _empty_canonical_metrics(),
                "parser": _parser_evidence(parsed),
            }

        canonical_bundle = self._build_canonical(
            base_payload=base.payloads[0],
            parsed=parsed,
            native_tables=native_tables,
            source_sha256=source_sha256,
            document_id=document_id,
        )
        table_terminal = TERMINAL_NO_TABLE if not terminals else TERMINAL_EXTRACTED
        return {
            "adapter_version": ADAPTER_VERSION,
            "plan_schema_version": PLAN_SCHEMA_VERSION,
            "terminal": table_terminal,
            "reason": None,
            "tables": terminals,
            "native_tables": native_tables,
            "canonical": canonical_bundle["canonical"],
            "table_projections": canonical_bundle["table_projections"],
            "canonical_metrics": canonical_bundle["metrics"],
            "parser": _parser_evidence(parsed),
            "vlm_body_values_used": 0,
            "invented_source_literals": 0,
        }

    def _validate_runtime(self) -> None:
        actual = importlib.metadata.version("pdfplumber")
        if actual != self.config.expected_pdfplumber_version:
            raise VisualPdfPlumberTablePlanError(
                "g5100_pdfplumber_version_mismatch"
            )

    def _execute_native_tables(
        self,
        *,
        pdf_bytes: bytes,
        image_width_pixels: int,
        image_height_pixels: int,
        plan: dict[str, Any],
        parser_page: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        native_tables: list[dict[str, Any]] = []
        terminals: list[dict[str, Any]] = []
        owned_words: set[int] = set()
        with pdfplumber.open(
            BytesIO(pdf_bytes),
            laparams={
                "line_overlap": 0.5,
                "char_margin": 2.0,
                "line_margin": 0.5,
                "word_margin": 0.1,
                "boxes_flow": None,
                "detect_vertical": True,
                "all_texts": True,
            },
            unicode_norm="NFC",
            strict_metadata=False,
        ) as pdf:
            if len(pdf.pages) != 1:
                raise VisualPdfPlumberTablePlanError(
                    "g5100_single_page_slice_required"
                )
            source_page = pdf.pages[0]
            if float(source_page.width) <= 0 or float(source_page.height) <= 0:
                raise VisualPdfPlumberTablePlanError("g5100_pdf_page_dimensions_invalid")
            for ordinal, item in enumerate(plan["tables"], 1):
                crop_bbox = _image_bbox_to_pdf(
                    item["bbox"],
                    image_width_pixels=image_width_pixels,
                    image_height_pixels=image_height_pixels,
                    pdf_width=float(source_page.width),
                    pdf_height=float(source_page.height),
                )
                explicit_vertical_lines = [
                    _image_x_to_pdf(
                        value,
                        image_width_pixels=image_width_pixels,
                        pdf_width=float(source_page.width),
                    )
                    for value in item["explicit_vertical_lines"]
                ]
                settings = {
                    "vertical_strategy": item["vertical_strategy"],
                    "explicit_vertical_lines": explicit_vertical_lines,
                    "horizontal_strategy": item["horizontal_strategy"],
                }
                found = source_page.crop(crop_bbox, strict=True).find_tables(
                    table_settings=settings
                )
                if not found:
                    terminals.append(
                        {
                            "plan_ordinal": ordinal,
                            "terminal": TERMINAL_NOT_FOUND,
                            "reason": "pdfplumber_find_tables_returned_zero",
                            "native_settings": settings,
                            "crop_bbox": list(crop_bbox),
                        }
                    )
                    continue
                if len(found) != 1:
                    terminals.append(
                        {
                            "plan_ordinal": ordinal,
                            "terminal": TERMINAL_AMBIGUOUS,
                            "reason": "pdfplumber_find_tables_returned_multiple",
                            "native_table_count": len(found),
                            "native_settings": settings,
                            "crop_bbox": list(crop_bbox),
                        }
                    )
                    continue
                candidate = _native_candidate(
                    table=found[0],
                    parser_page=parser_page,
                    horizontal_strategy=item["horizontal_strategy"],
                )
                contributing = set(candidate["contributing_word_parser_ordinals"])
                if contributing & owned_words:
                    terminals.append(
                        {
                            "plan_ordinal": ordinal,
                            "terminal": TERMINAL_SOURCE_BINDING_FAILED,
                            "reason": "g5100_duplicate_word_ownership",
                            "native_settings": settings,
                            "crop_bbox": list(crop_bbox),
                        }
                    )
                    continue
                owned_words.update(contributing)
                candidate["parser_ordinal"] = ordinal
                candidate["native_configuration"] = settings
                candidate["plan_crop_bbox"] = list(crop_bbox)
                native_tables.append(candidate)
                terminals.append(
                    {
                        "plan_ordinal": ordinal,
                        "terminal": TERMINAL_EXTRACTED,
                        "reason": None,
                        "native_settings": settings,
                        "crop_bbox": list(crop_bbox),
                        "table_bbox": copy.deepcopy(candidate["bbox"]),
                        "rows_total": candidate["rows_total"],
                        "columns_total": candidate["columns_total"],
                        "cells_total": candidate["cells_total"],
                        "source_words_total": len(contributing),
                    }
                )
        return native_tables, terminals

    def _build_canonical(
        self,
        *,
        base_payload: dict[str, Any],
        parsed: Any,
        native_tables: list[dict[str, Any]],
        source_sha256: str,
        document_id: str,
    ) -> dict[str, Any]:
        payload = copy.deepcopy(base_payload)
        projection = copy.deepcopy(payload["pdf_text_layer_projection"])
        layout_pages = copy.deepcopy(parsed.pages)
        layout_pages[0]["table_candidate_inventory"] = copy.deepcopy(native_tables)
        layout_pages[0]["table_candidate_status"] = (
            "candidate" if native_tables else "not_claimed"
        )
        layout_pages[0]["semantic_reconstruction_status"] = (
            "candidate" if native_tables else "not_claimed"
        )
        layout_pages[0]["table_reason_codes"] = [
            "g5100_minimal_native_pdfplumber_plan"
        ] if native_tables else []

        page_inventory = copy.deepcopy(projection.get("page_inventory") or [])
        if len(page_inventory) != 1:
            raise VisualPdfPlumberTablePlanError("g5100_page_inventory_invalid")
        layout_label = (
            "pdfplumber_layout_"
            + self.config.expected_pdfplumber_version.replace(".", "_")
        )
        layout_ref = "parser_" + stable_digest(
            [layout_label, "g5100_research_only", parsed.parser_config_ref],
            length=20,
        )
        layout_build = PdfLayoutUnitBuilder().build(
            normalization_run_id="g5100_native_plan",
            document_id=document_id,
            profile_id="g5100_research_only",
            source_checksum_sha256=source_sha256,
            source_checksum_ref=str(payload.get("source_checksum_ref") or ""),
            payload_ref=str(payload.get("source_payload_ref") or ""),
            layout_parser_ref=layout_ref,
            layout_parser_label=layout_label,
            layout_parser_config_ref=parsed.parser_config_ref,
            layout_pages=layout_pages,
            page_inventory=page_inventory,
        )
        if layout_build.layout_projection_status != "complete":
            raise VisualPdfPlumberTablePlanError(
                "g5100_whole_page_layout_assembly_incomplete"
            )

        for page in layout_build.pages:
            page["page_layout_checksum_ref"] = pdf_layout_page_checksum_ref(
                page, layout_ref
            )
        projection.update(
            {
                "page_inventory": layout_build.pages,
                "char_inventory": layout_build.char_inventory,
                "word_inventory": layout_build.word_inventory,
                "line_inventory": layout_build.line_inventory,
                "block_inventory": layout_build.block_inventory,
                "bbox_inventory": layout_build.bbox_inventory,
                "vector_line_inventory": layout_build.vector_line_inventory,
                "rect_inventory": layout_build.rect_inventory,
                "table_candidate_inventory": layout_build.table_candidate_inventory,
                "provided_capabilities": [
                    "page_text",
                    "layout_words",
                    "layout_lines",
                    "table_candidates",
                ],
                "layout_requested_capability": "table_candidates",
                "layout_parser_ref": layout_ref,
                "layout_projection_policy_ref": PDF_LAYOUT_POLICY_VERSION,
                "layout_parser_engine": parsed.parser_engine,
                "layout_parser_engine_version": parsed.parser_engine_version,
                "layout_underlying_engine": parsed.underlying_engine,
                "layout_underlying_engine_version": parsed.underlying_engine_version,
                "layout_parser_config_ref": parsed.parser_config_ref,
                "layout_unit_config_ref": PdfLayoutUnitBuilder().config.config_ref,
                "layout_projection_status": "complete",
                "layout_reason_codes": layout_build.layout_reason_codes,
                "table_candidate_status": layout_build.table_candidate_status,
                "layout_page_checksum_refs": [
                    str(page.get("page_layout_checksum_ref") or "")
                    for page in layout_build.pages
                ],
                "layout_coverage": layout_build.coverage,
                "semantic_reconstruction_status": (
                    layout_build.semantic_reconstruction_status
                ),
                "layout_parser_diagnostics": copy.deepcopy(parsed.diagnostics),
                "layout_unit_diagnostics": layout_build.diagnostics,
                "page_rendering_used_for_extraction": False,
            }
        )
        projection.setdefault("completeness", {}).update(
            {
                "layout_projection_status": "complete",
                "table_candidate_status": layout_build.table_candidate_status,
                "layout_reason_codes": layout_build.layout_reason_codes,
                "semantic_reconstruction_status": (
                    layout_build.semantic_reconstruction_status
                ),
            }
        )
        payload.update(
            {
                "pdf_text_layer_projection": projection,
                "layout_projection_status": "complete",
                "table_candidate_status": layout_build.table_candidate_status,
                "semantic_reconstruction_status": (
                    layout_build.semantic_reconstruction_status
                ),
                "page_rendering_used_for_extraction": False,
                "source_value_refs": [
                    *list(payload.get("source_value_refs") or []),
                    *layout_build.source_value_refs,
                ],
                "source_value_index": [
                    *list(payload.get("source_value_index") or []),
                    *layout_build.source_value_index,
                ],
                "extraction_unit_refs": [
                    str(unit.get("unit_ref") or "") for unit in layout_build.units
                ],
            }
        )
        payload.setdefault("coverage_index", {}).update(
            {
                "full_source_coverage_available": True,
                "table_candidate_refs": [
                    str(item.get("table_candidate_ref") or "")
                    for item in layout_build.table_candidate_inventory
                ],
            }
        )
        payload["payload_checksum_ref"] = pdf_payload_checksum_ref(payload)
        unit_refs = [str(unit.get("unit_ref") or "") for unit in layout_build.units]
        for index, unit in enumerate(layout_build.units):
            unit["payload_checksum_ref"] = payload["payload_checksum_ref"]
            unit["source_unit_checksum_ref"] = _checksum_ref(
                "srcunitchk",
                {
                    "unit_ref": unit.get("unit_ref"),
                    "payload_checksum_ref": unit.get("payload_checksum_ref"),
                    "slice_payload_checksum_ref": unit.get(
                        "slice_payload_checksum_ref"
                    ),
                    "coverage_ref": (unit.get("coverage") or {}).get(
                        "coverage_ref"
                    ),
                    "pdf_layout_unit_checksum_ref": unit.get(
                        "pdf_layout_unit_checksum_ref"
                    ),
                },
            )
            unit["remaining_unit_refs"] = unit_refs[index + 1 :]
            unit["next_unit_refs"] = unit_refs[index + 1 : index + 2]

        payload_validation = validate_pdf_text_layer_payload(payload)
        if payload_validation.get("validator_status") != "passed":
            raise VisualPdfPlumberTablePlanError(
                "g5100_augmented_payload_validation_failed"
            )
        projections = NormalizedTableProjectionFactory().create().build_for_document(
            source_format="pdf",
            payloads=[payload],
            source_units=layout_build.units,
        )
        canonical = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(
                normalizer_version=CANONICAL_NORMALIZER_POLICY_VERSION
            )
        ).create().build(
            tenant_id="g5100_research",
            artifact_version=1,
            document={
                "container_format": "pdf",
                "declared_mime_type": "application/pdf",
                "sha256": source_sha256,
            },
            source_artifact_ref="artifact_" + source_sha256[:24],
            source_payloads=[payload],
            source_units=layout_build.units,
            table_projections=projections.projections,
            created_at="2000-01-01T00:00:00+00:00",
        )
        validation = validate_canonical_artifact(canonical)
        if not validation.get("passed"):
            raise VisualPdfPlumberTablePlanError(
                "g5100_canonical_validation_failed"
            )
        receipt = (
            next(
                item
                for item in canonical["containers"]
                if item["container_id"] == canonical["root_container_ref"]
            ).get("metadata", {}).get("pdf_completeness", {})
        )
        metrics = {
            "canonical_valid": True,
            "canonical_tables": sum(
                node.get("node_type") == "TABLE" for node in canonical["nodes"]
            ),
            "canonical_text_nodes": sum(
                node.get("node_type") in {"TEXT", "HEADING", "NOTE", "LIST"}
                for node in canonical["nodes"]
            ),
            "source_atom_accounting_percent": receipt.get(
                "source_atom_accounting_percent"
            ),
            "unresolved_source_atoms_total": receipt.get(
                "unresolved_source_atoms_total"
            ),
            "table_text_duplicate_reduction_percent": receipt.get(
                "duplicate_table_text_reduction_percent"
            ),
            "layout_selected_refs": layout_build.coverage.get("selected_total"),
            "layout_accounted_refs": layout_build.coverage.get("accounted_total"),
            "layout_duplicate_refs": len(
                layout_build.coverage.get("duplicate_accounted_refs") or []
            ),
            "layout_unaccounted_refs": len(
                layout_build.coverage.get("unaccounted_refs") or []
            ),
            "ready_table_projections": sum(
                item.get("projection_status") == "ready"
                for item in projections.projections
            ),
            "blocked_table_projections": sum(
                item.get("projection_status") != "ready"
                for item in projections.projections
            ),
        }
        return {
            "canonical": canonical,
            "table_projections": projections.projections,
            "metrics": metrics,
        }


def validate_pdfplumber_table_plan(
    value: Any,
    *,
    image_width_pixels: int,
    image_height_pixels: int,
    maximum_tables: int = 12,
    maximum_vertical_lines: int = 40,
) -> None:
    if image_width_pixels <= 0 or image_height_pixels <= 0:
        raise VisualPdfPlumberTablePlanError("g5100_image_dimensions_invalid")
    if not isinstance(value, dict) or set(value) != _PAGE_KEYS:
        raise VisualPdfPlumberTablePlanError("g5100_plan_shape_invalid")
    _reject_forbidden_keys(value)
    tables = value.get("tables")
    if not isinstance(tables, list) or len(tables) > maximum_tables:
        raise VisualPdfPlumberTablePlanError("g5100_tables_invalid")
    previous_bottom = -1.0
    for item in tables:
        if not isinstance(item, dict) or set(item) != _TABLE_KEYS:
            raise VisualPdfPlumberTablePlanError("g5100_table_plan_shape_invalid")
        bbox = _numbers(item.get("bbox"), expected=4)
        if (
            bbox[0] < 0
            or bbox[1] < 0
            or bbox[2] > image_width_pixels
            or bbox[3] > image_height_pixels
            or bbox[2] <= bbox[0]
            or bbox[3] <= bbox[1]
        ):
            raise VisualPdfPlumberTablePlanError("g5100_bbox_invalid")
        if bbox[1] < previous_bottom:
            raise VisualPdfPlumberTablePlanError("g5100_table_plans_overlap_or_reorder")
        previous_bottom = bbox[3]
        if item.get("vertical_strategy") != "explicit":
            raise VisualPdfPlumberTablePlanError(
                "g5100_vertical_strategy_not_whitelisted"
            )
        if item.get("horizontal_strategy") not in _HORIZONTAL_STRATEGIES:
            raise VisualPdfPlumberTablePlanError(
                "g5100_horizontal_strategy_not_whitelisted"
            )
        lines = _numbers(item.get("explicit_vertical_lines"))
        if not 2 <= len(lines) <= maximum_vertical_lines:
            raise VisualPdfPlumberTablePlanError("g5100_vertical_lines_invalid")
        if lines != sorted(set(lines)):
            raise VisualPdfPlumberTablePlanError(
                "g5100_vertical_lines_not_strictly_ordered"
            )
        if lines[0] < bbox[0] or lines[-1] > bbox[2]:
            raise VisualPdfPlumberTablePlanError(
                "g5100_vertical_lines_outside_crop"
            )


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in _FORBIDDEN_PLAN_KEYS:
                raise VisualPdfPlumberTablePlanError("g5100_plan_domain_leakage")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested)


def _native_candidate(
    *, table: Any, parser_page: dict[str, Any], horizontal_strategy: str
) -> dict[str, Any]:
    bbox = _bbox(list(table.bbox))
    rows = list(table.rows or [])
    columns = list(table.columns or [])
    cells = [list(cell) for cell in table.cells or [] if cell is not None]
    if not rows or len(columns) < 2 or not cells:
        raise VisualPdfPlumberTablePlanError("g5100_native_grid_incompatible")
    words = list(parser_page.get("word_inventory") or [])
    cell_inventory = []
    contributing: set[int] = set()
    for ordinal, cell in enumerate(cells, 1):
        cell_bbox = _bbox(cell)
        word_ordinals = [
            int(word["parser_ordinal"])
            for word in words
            if _bbox_center_inside(word.get("bbox"), cell_bbox)
        ]
        contributing.update(word_ordinals)
        cell_inventory.append(
            {
                "cell_ordinal": ordinal,
                "bbox": cell_bbox,
                "word_parser_ordinals": word_ordinals,
            }
        )
    if not contributing:
        raise VisualPdfPlumberTablePlanError("g5100_source_words_missing")
    return {
        "parser_ordinal": 0,
        "table_strategy_ref": (
            "ruled_lines_v0"
            if horizontal_strategy == "lines"
            else "aligned_text_v0"
        ),
        "table_reconstruction_status": "candidate",
        "geometry_confidence": 1.0,
        "bbox": bbox,
        "rows_total": len(rows),
        "columns_total": len(columns),
        "cells_total": len(cell_inventory),
        "cell_inventory": cell_inventory,
        "contributing_word_parser_ordinals": sorted(contributing),
        "ruling_evidence_total": sum(
            1
            for item in [
                *list(parser_page.get("vector_line_inventory") or []),
                *list(parser_page.get("rect_inventory") or []),
            ]
            if _bbox_overlap(item.get("bbox"), bbox)
        ),
        "reconstruction_reason_codes": [
            "g5100_vlm_crop_native_pdfplumber_plan",
            "geometry_only_non_semantic_candidate",
        ],
    }


def _image_bbox_to_pdf(
    value: list[float],
    *,
    image_width_pixels: int,
    image_height_pixels: int,
    pdf_width: float,
    pdf_height: float,
) -> tuple[float, float, float, float]:
    bbox = _numbers(value, expected=4)
    return (
        bbox[0] * pdf_width / image_width_pixels,
        bbox[1] * pdf_height / image_height_pixels,
        bbox[2] * pdf_width / image_width_pixels,
        bbox[3] * pdf_height / image_height_pixels,
    )


def _image_x_to_pdf(
    value: float, *, image_width_pixels: int, pdf_width: float
) -> float:
    return float(value) * pdf_width / image_width_pixels


def _numbers(value: Any, *, expected: int | None = None) -> list[float]:
    if not isinstance(value, list) or (expected is not None and len(value) != expected):
        raise VisualPdfPlumberTablePlanError("g5100_numeric_array_invalid")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise VisualPdfPlumberTablePlanError("g5100_numeric_array_invalid")
    return [float(item) for item in value]


def _bbox(value: Any) -> list[float]:
    result = _numbers(value, expected=4)
    if result[2] <= result[0] or result[3] <= result[1]:
        raise VisualPdfPlumberTablePlanError("g5100_source_bbox_invalid")
    return [round(item, 6) for item in result]


def _bbox_center_inside(value: Any, outer: list[float]) -> bool:
    try:
        inner = _bbox(value)
    except VisualPdfPlumberTablePlanError:
        return False
    center_x = (inner[0] + inner[2]) / 2.0
    center_y = (inner[1] + inner[3]) / 2.0
    return (
        outer[0] <= center_x < outer[2]
        and outer[1] <= center_y < outer[3]
    )


def _bbox_overlap(left: Any, right: Any) -> bool:
    try:
        a = _bbox(left)
        b = _bbox(right)
    except VisualPdfPlumberTablePlanError:
        return False
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(
        a[1], b[1]
    )


def _checksum_ref(prefix: str, value: Any) -> str:
    return prefix + "_" + stable_digest(value, length=24)


def _parser_evidence(parsed: Any) -> dict[str, Any]:
    page = parsed.pages[0] if len(parsed.pages) == 1 else {}
    return {
        "factory_entrypoint": "PdfTextLayerParserFactory.create",
        "engine": parsed.parser_engine,
        "engine_version": parsed.parser_engine_version,
        "layout_projection_status": parsed.layout_projection_status,
        "words_total": len(page.get("word_inventory") or []),
        "lines_total": len(page.get("line_inventory") or []),
    }


def _empty_canonical_metrics() -> dict[str, Any]:
    return {
        "canonical_valid": False,
        "canonical_tables": 0,
        "canonical_text_nodes": 0,
        "source_atom_accounting_percent": 0.0,
        "unresolved_source_atoms_total": 0,
        "table_text_duplicate_reduction_percent": 0.0,
        "layout_selected_refs": 0,
        "layout_accounted_refs": 0,
        "layout_duplicate_refs": 0,
        "layout_unaccounted_refs": 0,
        "ready_table_projections": 0,
        "blocked_table_projections": 0,
    }
