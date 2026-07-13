from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import PDF_TABLE_CLASSIFICATION_SCHEMA, sha256_json


PDF_TABLE_CLASSIFIER_POLICY_VERSION = "pdf_table_classifier_policy_v1"
FACTORY_REQUIRED = (
    "PdfTableClassifierFactory.create is the only hybrid table classifier entrypoint"
)
FORBIDDEN = "Callers must not classify business domains or bypass measured structural signals"


@dataclass(frozen=True)
class PdfTableClassifierConfig:
    policy_version: str = PDF_TABLE_CLASSIFIER_POLICY_VERSION
    wide_column_threshold: int = 12
    high_empty_cell_density: float = 0.45
    high_multiline_cell_density: float = 0.30
    shadow_allowlist: tuple[str, ...] = ()


class PdfTableClassifierFactory:
    def __init__(self, config: PdfTableClassifierConfig | None = None) -> None:
        self.config = config or PdfTableClassifierConfig()

    def create(self) -> "PdfTableClassifier":
        if self.config.policy_version != PDF_TABLE_CLASSIFIER_POLICY_VERSION:
            raise ValueError("pdf_table_classifier_policy_invalid")
        return PdfTableClassifier(self.config)


class PdfTableClassifier:
    def __init__(self, config: PdfTableClassifierConfig) -> None:
        self.config = config

    def classify(
        self,
        *,
        document_ref: str,
        document_checksum: str,
        page_ref: str,
        page_number: int,
        table_candidate: dict[str, Any],
        deterministic_projection: dict[str, Any],
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        table_ref = str(table_candidate.get("table_candidate_ref") or "")
        bbox_ref = str(table_candidate.get("bbox_ref") or "")
        if not all((document_ref, document_checksum, page_ref, table_ref, bbox_ref)):
            raise ValueError("pdf_table_classifier_identity_missing")
        measured = self._signals(table_candidate, deterministic_projection, signals or {})
        blockers = sorted(
            set(
                str(item)
                for item in deterministic_projection.get("reconstruction_reason_codes") or []
                if item
            )
        )
        reasons: list[str] = []
        if not measured["ordered_source_words_complete"] or measured["source_word_count"] == 0:
            selected = "unsupported_image_or_text_layer"
            reasons.append("pdf_hybrid_source_words_unavailable")
        elif table_ref in self.config.shadow_allowlist:
            selected = "hybrid_complex"
            reasons.append("pdf_hybrid_explicit_shadow_allowlist")
        elif "pdf_table_geometry_column_structure_insufficient" in blockers:
            selected = "hybrid_after_deterministic_block"
            reasons.append("pdf_hybrid_current_column_structure_blocker")
        else:
            complex_reasons = [
                (measured["wide_table"], "pdf_hybrid_wide_table"),
                (measured["multi_row_or_merged_header"], "pdf_hybrid_complex_header"),
                (measured["continuation_signal"], "pdf_hybrid_continuation"),
                (measured["conflicting_grid_hypotheses"], "pdf_hybrid_grid_conflict"),
                (measured["high_empty_cell_density"], "pdf_hybrid_high_empty_density"),
                (measured["high_multiline_cell_density"], "pdf_hybrid_high_multiline_density"),
                (
                    not measured["deterministic_header_hierarchy_accepted"],
                    "pdf_hybrid_header_hierarchy_unaccepted",
                ),
            ]
            reasons.extend(reason for enabled, reason in complex_reasons if enabled)
            if reasons:
                selected = "hybrid_complex"
            elif (
                deterministic_projection.get("projection_status") == "ready"
                and deterministic_projection.get("validator_status") == "passed"
            ):
                selected = "deterministic_simple"
                reasons.append("pdf_deterministic_projection_validated_simple")
            else:
                selected = "human_review_required"
                reasons.append("pdf_table_path_not_safely_resolved")
        config_snapshot = asdict(self.config)
        result = {
            "schema_version": PDF_TABLE_CLASSIFICATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(config_snapshot),
            "classification_id": "pdfclass_" + stable_digest(
                [document_checksum, table_ref, self.config.policy_version, sha256_json(measured)],
                length=24,
            ),
            "document_ref": document_ref,
            "document_checksum": document_checksum,
            "page_ref": page_ref,
            "page_number": int(page_number),
            "table_ref": table_ref,
            "table_bbox_ref": bbox_ref,
            "detector_result": {
                "strategy_ref": table_candidate.get("table_strategy_ref"),
                "geometry_confidence": table_candidate.get("geometry_confidence"),
                "rows_total": int(table_candidate.get("rows_total") or 0),
                "columns_total": _column_count(table_candidate),
            },
            "deterministic_result": {
                "projection_status": deterministic_projection.get("projection_status"),
                "validator_status": deterministic_projection.get("validator_status"),
                "reconstruction_quality": deterministic_projection.get(
                    "reconstruction_quality"
                ),
                "blocker_codes": blockers,
            },
            "measured_signals": measured,
            "selected_path": selected,
            "reason_codes": sorted(set(reasons)),
            "evidence_identity": sha256_json(
                [document_checksum, page_ref, table_ref, bbox_ref, measured]
            ),
            "business_domain_classification_performed": False,
            "authoritative_decision": False,
        }
        result["classification_hash"] = sha256_json(result)
        return result

    def _signals(
        self,
        candidate: dict[str, Any],
        projection: dict[str, Any],
        supplied: dict[str, Any],
    ) -> dict[str, Any]:
        cells = [item for item in candidate.get("cell_inventory") or [] if isinstance(item, dict)]
        rows = max(
            int(candidate.get("rows_total") or 0),
            max((int(item.get("row_ordinal") or 0) for item in cells), default=0),
        )
        columns = max((int(item.get("column_ordinal") or 0) for item in cells), default=0)
        empty = sum(not (item.get("word_refs") or []) for item in cells)
        multiline = int(supplied.get("multiline_cells_total") or 0)
        header = projection.get("header_model") if isinstance(projection.get("header_model"), dict) else {}
        header_depth = int(supplied.get("header_depth") or header.get("header_depth") or 0)
        source_words = list(candidate.get("contributing_word_refs") or [])
        empty_density = round(empty / len(cells), 6) if cells else 0.0
        multiline_density = round(multiline / len(cells), 6) if cells else 0.0
        return {
            "source_word_count": len(source_words),
            "ordered_source_words_complete": supplied.get(
                "ordered_source_words_complete", bool(source_words)
            )
            is True,
            "row_count_hint": rows,
            "column_count_hint": columns,
            "row_confidence": supplied.get("row_confidence", candidate.get("geometry_confidence")),
            "column_confidence": supplied.get(
                "column_confidence", projection.get("reconstruction_quality")
            ),
            "header_depth": header_depth,
            "multi_row_or_merged_header": bool(
                supplied.get("multi_row_or_merged_header", header_depth > 1)
            ),
            "continuation_signal": bool(supplied.get("continuation_signal", False)),
            "conflicting_grid_hypotheses": bool(
                supplied.get("conflicting_grid_hypotheses", False)
            ),
            "empty_cell_density": empty_density,
            "high_empty_cell_density": empty_density >= self.config.high_empty_cell_density,
            "multiline_cell_density": multiline_density,
            "high_multiline_cell_density": (
                multiline_density >= self.config.high_multiline_cell_density
            ),
            "wide_table": columns >= self.config.wide_column_threshold,
            "deterministic_header_hierarchy_accepted": supplied.get(
                "deterministic_header_hierarchy_accepted",
                projection.get("projection_status") == "ready",
            )
            is True,
            "crop_readability_status": str(
                supplied.get("crop_readability_status") or "not_rendered"
            ),
        }


def _column_count(candidate: dict[str, Any]) -> int:
    return max(
        (
            int(item.get("column_ordinal") or 0)
            for item in candidate.get("cell_inventory") or []
            if isinstance(item, dict)
        ),
        default=0,
    )
