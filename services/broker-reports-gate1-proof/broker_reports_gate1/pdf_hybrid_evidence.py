from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import (
    PDF_HYBRID_EVIDENCE_PACKAGE_SCHEMA,
    canonical_json_bytes,
    hybrid_binding_output_schema,
    sha256_json,
)


PDF_HYBRID_EVIDENCE_POLICY_VERSION = "pdf_hybrid_evidence_policy_v1"
FACTORY_REQUIRED = (
    "PdfHybridEvidenceFactory.create is the only hybrid evidence-package entrypoint"
)
FORBIDDEN = (
    "Callers must not use OCR authority, full-PDF text, unrelated pages, business instructions, "
    "or silent truncation"
)


class PdfHybridEvidenceError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        component_accounting: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.component_accounting = component_accounting or {}
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridEvidenceConfig:
    policy_version: str = PDF_HYBRID_EVIDENCE_POLICY_VERSION
    maximum_candidates: int = 512
    maximum_candidate_json_bytes: int = 128 * 1024
    target_input_tokens: int = 24_000
    maximum_input_tokens: int = 32_000
    maximum_rows: int = 64
    maximum_columns: int = 24
    maximum_grid_positions: int = 1_536
    maximum_header_depth: int = 8
    target_output_tokens: int = 12_000
    maximum_output_tokens: int = 16_384


class PdfHybridEvidenceFactory:
    def __init__(self, config: PdfHybridEvidenceConfig | None = None) -> None:
        self.config = config or PdfHybridEvidenceConfig()

    def create(self) -> "PdfHybridEvidenceBuilder":
        if self.config.policy_version != PDF_HYBRID_EVIDENCE_POLICY_VERSION:
            raise PdfHybridEvidenceError("pdf_hybrid_evidence_policy_invalid")
        return PdfHybridEvidenceBuilder(self.config)


class PdfHybridEvidenceBuilder:
    TASK_TEXT = (
        "Reconstruct only the visible table structure. Place supplied candidate ids into a "
        "complete rectangular grid in source order. Every grid position must be present. "
        "Each cell is an array of candidate ids; use [] as an explicit empty cell. Return ambiguity "
        "or unsupported when structure cannot be resolved. Do not calculate, normalize, copy "
        "values, infer business facts, or invent ids."
    )

    def __init__(self, config: PdfHybridEvidenceConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        table_candidate: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        crop_manifest: dict[str, Any],
        private_crop_artifact_ref: str,
        row_count_hint: int,
        column_count_hint: int,
        header_depth_hint: int = 0,
    ) -> dict[str, Any]:
        table_ref = str(table_candidate.get("table_candidate_ref") or "")
        if (
            crop_manifest.get("table_ref") != table_ref
            or crop_manifest.get("pdf_sha256") != pdf_sha256
            or crop_manifest.get("page_number") != page_number
        ):
            raise PdfHybridEvidenceError("pdf_hybrid_evidence_crop_identity_mismatch")
        candidates, private_dictionary = self._candidates(
            page_ref=page_ref,
            table_candidate=table_candidate,
            projection=pdf_text_layer_projection,
        )
        dictionary_hash = sha256_json(private_dictionary)
        model_view = {
            "task": self.TASK_TEXT,
            "identity": {
                "package_id": "pending",
                "crop_sha256": crop_manifest.get("png_sha256"),
                "candidate_dictionary_hash": dictionary_hash,
            },
            "shape_hints": {
                "rows": int(row_count_hint),
                "columns": int(column_count_hint),
                "header_depth": int(header_depth_hint),
            },
            "candidates": candidates,
        }
        package_id = "pdfhybridpkg_" + stable_digest(
            [
                pdf_sha256,
                page_ref,
                table_ref,
                crop_manifest.get("png_sha256"),
                dictionary_hash,
                self.config.policy_version,
            ],
            length=24,
        )
        model_view["identity"]["package_id"] = package_id
        schema = hybrid_binding_output_schema()
        accounting = self._accounting(
            candidates=candidates,
            model_view=model_view,
            schema=schema,
            crop_manifest=crop_manifest,
            row_count_hint=row_count_hint,
            column_count_hint=column_count_hint,
            header_depth_hint=header_depth_hint,
        )
        hard_failures = accounting["hard_budget_failure_codes"]
        if hard_failures:
            raise PdfHybridEvidenceError(
                hard_failures[0],
                component_accounting=accounting,
            )
        package = {
            "schema_version": PDF_HYBRID_EVIDENCE_PACKAGE_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "package_id": package_id,
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "table_ref": table_ref,
            "table_bbox_ref": table_candidate.get("bbox_ref"),
            "table_bbox": list(crop_manifest.get("declared_table_bbox") or []),
            "crop_identity": {
                "private_crop_artifact_ref": private_crop_artifact_ref,
                "crop_id": crop_manifest.get("crop_id"),
                "crop_sha256": crop_manifest.get("png_sha256"),
                "dpi": crop_manifest.get("dpi"),
                "width": crop_manifest.get("width"),
                "height": crop_manifest.get("height"),
                "renderer": crop_manifest.get("renderer"),
                "renderer_version": crop_manifest.get("renderer_version"),
                "rotation": crop_manifest.get("page_rotation"),
                "padding_points": crop_manifest.get("padding_points"),
                "source_to_pixel_transform": crop_manifest.get(
                    "source_to_pixel_transform"
                ),
            },
            "candidate_dictionary_hash": dictionary_hash,
            "model_facing": model_view,
            "private_candidate_dictionary": private_dictionary,
            "output_schema": schema,
            "component_accounting": accounting,
            "source_authority": "existing_production_pdf_words_only",
            "ocr_used": False,
            "business_domain_context_included": False,
            "silent_truncation_performed": False,
            "column_split_performed": False,
        }
        package["package_hash"] = sha256_json(package)
        return package

    def _candidates(
        self,
        *,
        page_ref: str,
        table_candidate: dict[str, Any],
        projection: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
            for item in _dicts(projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        table_bbox = bbox_by_ref.get(str(table_candidate.get("bbox_ref") or ""), [])
        if len(table_bbox) != 4:
            raise PdfHybridEvidenceError("pdf_hybrid_evidence_table_bbox_missing")
        owned_refs = set(str(item) for item in table_candidate.get("contributing_word_refs") or [])
        words = [
            item
            for item in _dicts(projection.get("word_inventory"))
            if item.get("page_ref") == page_ref
            and item.get("word_ref") in owned_refs
            and _bbox_inside(bbox_by_ref.get(str(item.get("bbox_ref") or ""), []), table_bbox)
        ]
        words.sort(
            key=lambda item: (
                int(item.get("geometry_reading_order") or 0),
                int(item.get("parser_ordinal") or 0),
                str(item.get("word_ref") or ""),
            )
        )
        if set(str(item.get("word_ref") or "") for item in words) != owned_refs:
            raise PdfHybridEvidenceError("pdf_hybrid_evidence_source_word_scope_incomplete")
        word_by_ref = {str(item.get("word_ref") or ""): item for item in words}
        word_order = {
            str(item.get("word_ref") or ""): index for index, item in enumerate(words)
        }
        grouped_refs: list[list[str]] = []
        claimed: set[str] = set()
        for cell in sorted(
            _dicts(table_candidate.get("cell_inventory")),
            key=lambda item: (
                int(item.get("row_ordinal") or 0),
                int(item.get("column_ordinal") or 0),
            ),
        ):
            refs = [
                str(ref)
                for ref in cell.get("word_refs") or []
                if str(ref) in word_by_ref and str(ref) not in claimed
            ]
            refs.sort(key=word_order.get)
            if refs:
                grouped_refs.append(refs)
                claimed.update(refs)
        grouped_refs.extend([[ref] for ref in word_by_ref if ref not in claimed])
        grouped_refs.sort(key=lambda refs: min(word_order[ref] for ref in refs))
        model_candidates: list[dict[str, Any]] = []
        dictionary: dict[str, Any] = {}
        for index, refs in enumerate(grouped_refs):
            candidate_id = f"c{index}"
            selected_words = [word_by_ref[ref] for ref in refs]
            selected_bboxes = [
                bbox_by_ref.get(str(word.get("bbox_ref") or ""), [])
                for word in selected_words
            ]
            bbox = _bbox_union(selected_bboxes)
            text = " ".join(str(word.get("text") or "") for word in selected_words)
            model_candidates.append(
                {
                    "id": candidate_id,
                    "text": text,
                    "class": _mechanical_class(text),
                    "bbox": _normalized_bbox(bbox, table_bbox),
                    "order": index,
                }
            )
            dictionary[candidate_id] = {
                "exact_source_span": text,
                "source_value_refs": [
                    word.get("source_value_ref") for word in selected_words
                ],
                "word_refs": [word.get("word_ref") for word in selected_words],
                "source_bbox": bbox,
                "source_bbox_refs": [word.get("bbox_ref") for word in selected_words],
                "source_text_checksum_refs": [
                    word.get("text_checksum_ref") for word in selected_words
                ],
                "private_exact_value_paths": [
                    {
                        "kind": "pdf_layout_word_text",
                        "word_ref": word.get("word_ref"),
                    }
                    for word in selected_words
                ],
                "source_order": index,
            }
        return model_candidates, dictionary

    def _accounting(
        self,
        *,
        candidates: list[dict[str, Any]],
        model_view: dict[str, Any],
        schema: dict[str, Any],
        crop_manifest: dict[str, Any],
        row_count_hint: int,
        column_count_hint: int,
        header_depth_hint: int,
    ) -> dict[str, Any]:
        candidate_bytes = len(canonical_json_bytes(candidates))
        task_bytes = len(self.TASK_TEXT.encode("utf-8"))
        header_context = canonical_json_bytes(model_view.get("shape_hints"))
        schema_bytes = len(canonical_json_bytes(schema))
        model_bytes = len(canonical_json_bytes(model_view))
        text_characters = sum(len(str(item.get("text") or "")) for item in candidates)
        unique_text = " ".join(dict.fromkeys(str(item.get("text") or "") for item in candidates))
        unique_visible_bytes = len(unique_text.encode("utf-8"))
        estimated_tokens = (model_bytes + schema_bytes + 3) // 4
        grid_positions = max(0, int(row_count_hint)) * max(0, int(column_count_hint))
        expected_output_tokens = min(
            self.config.maximum_output_tokens,
            256 + grid_positions * 8 + len(candidates) * 2,
        )
        failures = []
        checks = [
            (len(candidates) > self.config.maximum_candidates, "pdf_hybrid_candidate_count_budget_exceeded"),
            (candidate_bytes > self.config.maximum_candidate_json_bytes, "pdf_hybrid_candidate_json_budget_exceeded"),
            (estimated_tokens > self.config.maximum_input_tokens, "pdf_hybrid_input_token_budget_exceeded"),
            (row_count_hint > self.config.maximum_rows, "pdf_hybrid_row_budget_exceeded"),
            (column_count_hint > self.config.maximum_columns, "pdf_hybrid_column_budget_exceeded"),
            (grid_positions > self.config.maximum_grid_positions, "pdf_hybrid_grid_budget_exceeded"),
            (header_depth_hint > self.config.maximum_header_depth, "pdf_hybrid_header_depth_budget_exceeded"),
            (expected_output_tokens > self.config.maximum_output_tokens, "pdf_hybrid_output_token_budget_exceeded"),
        ]
        failures.extend(code for failed, code in checks if failed)
        return {
            "image_bytes": int(crop_manifest.get("png_bytes") or 0),
            "image_width": int(crop_manifest.get("width") or 0),
            "image_height": int(crop_manifest.get("height") or 0),
            "candidate_count": len(candidates),
            "candidate_json_bytes": candidate_bytes,
            "candidate_text_characters": text_characters,
            "header_context_bytes": len(header_context),
            "task_policy_bytes": task_bytes,
            "schema_bytes": schema_bytes,
            "model_facing_text_bytes": model_bytes,
            "estimated_input_tokens": estimated_tokens,
            "expected_grid_positions": grid_positions,
            "expected_maximum_output_tokens": expected_output_tokens,
            "requested_maximum_output_tokens": self.config.maximum_output_tokens,
            "unique_visible_table_text_bytes": unique_visible_bytes,
            "model_facing_text_amplification_ratio": round(
                model_bytes / max(1, unique_visible_bytes), 6
            ),
            "provider_token_amplification_ratio": None,
            "target_input_tokens_exceeded": estimated_tokens > self.config.target_input_tokens,
            "target_output_tokens_exceeded": expected_output_tokens > self.config.target_output_tokens,
            "hard_budget_failure_codes": sorted(failures),
            "pre_provider_budget_passed": not failures,
        }


def _mechanical_class(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", text):
        return "numeric-like"
    if re.fullmatch(r"\d{1,4}[./-]\d{1,2}(?:[./-]\d{1,4})?", text):
        return "date-like"
    if re.fullmatch(r"[A-ZА-Я]{3}", text):
        return "currency-code"
    if re.fullmatch(r"[^\w\s]+", text):
        return "symbol"
    if len(text) <= 16:
        return "short-text"
    return "long-text"


def _normalized_bbox(value: list[Any], scope: list[Any]) -> list[float]:
    if len(value) != 4 or len(scope) != 4:
        raise PdfHybridEvidenceError("pdf_hybrid_evidence_bbox_invalid")
    width = float(scope[2]) - float(scope[0])
    height = float(scope[3]) - float(scope[1])
    if width <= 0 or height <= 0:
        raise PdfHybridEvidenceError("pdf_hybrid_evidence_bbox_invalid")
    return [
        round((float(value[0]) - float(scope[0])) / width, 6),
        round((float(value[1]) - float(scope[1])) / height, 6),
        round((float(value[2]) - float(scope[0])) / width, 6),
        round((float(value[3]) - float(scope[1])) / height, 6),
    ]


def _bbox_inside(value: list[Any], scope: list[Any]) -> bool:
    if len(value) != 4 or len(scope) != 4:
        return False
    center_x = (float(value[0]) + float(value[2])) / 2
    center_y = (float(value[1]) + float(value[3])) / 2
    epsilon = 0.5
    return (
        float(scope[0]) - epsilon <= center_x <= float(scope[2]) + epsilon
        and float(scope[1]) - epsilon <= center_y <= float(scope[3]) + epsilon
    )


def _bbox_union(values: list[list[Any]]) -> list[float]:
    valid = [value for value in values if len(value) == 4]
    if not valid:
        raise PdfHybridEvidenceError("pdf_hybrid_evidence_bbox_invalid")
    return [
        min(float(value[0]) for value in valid),
        min(float(value[1]) for value in valid),
        max(float(value[2]) for value in valid),
        max(float(value[3]) for value in valid),
    ]


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []
