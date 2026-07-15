from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json


PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA = (
    "broker_reports_pdf_parser_geometry_observation_v2"
)
PDF_PARSER_GEOMETRY_POLICY_VERSION = "pdf_parser_geometry_policy_v2"
_LEGACY_OBSERVATION_SCHEMA = "broker_reports_pdf_parser_geometry_observation_v1"
_LEGACY_POLICY_VERSION = "pdf_parser_geometry_policy_v1"

FACTORY_REQUIRED = (
    "PdfParserGeometryFactory.create is the only raw PDF vector geometry "
    "observation entrypoint"
)
FORBIDDEN = (
    "The geometry observer must not read legacy table cells, row or column "
    "counts, header depth, source values, or reference answers"
)

_FACTORY_TOKEN = object()
_OBSERVATION_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "observation_id",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "table_ref",
    "coordinate_space",
    "horizontal_signals",
    "vertical_signals",
    "unsupported_vector_kinds",
    "source_accounting",
    "legacy_grid_consumed",
    "observation_checksum",
}
_SIGNAL_KEYS = {
    "signal_id",
    "source_object_ref",
    "kind",
    "orientation",
    "position_normalized",
    "extent_normalized",
    "linewidth_points",
}


class PdfParserGeometryError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfParserGeometryConfig:
    policy_version: str = PDF_PARSER_GEOMETRY_POLICY_VERSION
    axis_alignment_tolerance_points: float = 0.75
    table_intersection_tolerance_points: float = 1.5
    minimum_signal_extent_points: float = 0.5
    maximum_signals: int = 20_000


class PdfParserGeometryFactory:
    def __init__(self, config: PdfParserGeometryConfig | None = None) -> None:
        self.config = config or PdfParserGeometryConfig()

    def create(self) -> "PdfParserGeometryRuntime":
        if self.config.policy_version != PDF_PARSER_GEOMETRY_POLICY_VERSION:
            raise PdfParserGeometryError("pdf_parser_geometry_policy_invalid")
        if (
            self.config.axis_alignment_tolerance_points < 0
            or self.config.table_intersection_tolerance_points < 0
            or self.config.minimum_signal_extent_points <= 0
            or self.config.maximum_signals < 1
        ):
            raise PdfParserGeometryError("pdf_parser_geometry_config_invalid")
        return PdfParserGeometryRuntime(self.config, _factory_token=_FACTORY_TOKEN)


class PdfParserGeometryRuntime:
    def __init__(
        self,
        config: PdfParserGeometryConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfParserGeometryError("pdf_parser_geometry_factory_required")
        self.config = config

    def build_observation(
        self,
        *,
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        table_ref: str,
        table_bbox: list[float],
        pdf_text_layer_projection: dict[str, Any],
    ) -> dict[str, Any]:
        scope = _bbox(table_bbox)
        if (
            scope is None
            or not document_ref
            or not pdf_sha256
            or not page_ref
            or page_number < 1
            or not table_ref
        ):
            raise PdfParserGeometryError("pdf_parser_geometry_scope_invalid")
        width = scope[2] - scope[0]
        height = scope[3] - scope[1]
        if width <= 0 or height <= 0:
            raise PdfParserGeometryError("pdf_parser_geometry_scope_invalid")

        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): _bbox(item.get("bbox"))
            for item in _dicts(pdf_text_layer_projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        horizontal: list[dict[str, Any]] = []
        vertical: list[dict[str, Any]] = []
        for inventory_name, kind, ref_keys in (
            (
                "vector_line_inventory",
                "vector_line",
                ("pdfvectorline_ref", "object_ref"),
            ),
            ("rect_inventory", "rect_edge", ("pdfrect_ref", "object_ref")),
        ):
            for item in _dicts(pdf_text_layer_projection.get(inventory_name)):
                if item.get("page_ref") != page_ref:
                    continue
                source_bbox = bbox_by_ref.get(str(item.get("bbox_ref") or ""))
                if source_bbox is None or not _intersects(
                    source_bbox,
                    scope,
                    tolerance=self.config.table_intersection_tolerance_points,
                ):
                    continue
                source_ref = next(
                    (
                        str(item.get(key) or "")
                        for key in ref_keys
                        if str(item.get(key) or "")
                    ),
                    "",
                )
                if not source_ref:
                    raise PdfParserGeometryError(
                        "pdf_parser_geometry_source_object_ref_missing"
                    )
                linewidth = _optional_number(item.get("linewidth"))
                if kind == "vector_line":
                    signals = self._line_signals(
                        source_bbox=source_bbox,
                        source_ref=source_ref,
                        scope=scope,
                        linewidth=linewidth,
                    )
                else:
                    signals = self._rect_signals(
                        source_bbox=source_bbox,
                        source_ref=source_ref,
                        scope=scope,
                        linewidth=linewidth,
                    )
                for signal in signals:
                    (horizontal if signal["orientation"] == "horizontal" else vertical).append(
                        signal
                    )

        horizontal = _deduplicate_signals(horizontal)
        vertical = _deduplicate_signals(vertical)
        if len(horizontal) + len(vertical) > self.config.maximum_signals:
            raise PdfParserGeometryError("pdf_parser_geometry_signal_budget_exceeded")
        all_signals = [*horizontal, *vertical]
        vector_refs = {
            str(item["source_object_ref"])
            for item in all_signals
            if item.get("kind") == "vector_line"
        }
        rect_refs = {
            str(item["source_object_ref"])
            for item in all_signals
            if item.get("kind") == "rect_edge"
        }

        result = {
            "schema_version": PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "observation_id": _observation_id(
                pdf_sha256=pdf_sha256,
                page_ref=page_ref,
                table_ref=table_ref,
                table_bbox=scope,
                horizontal_signals=horizontal,
                vertical_signals=vertical,
                policy_version=self.config.policy_version,
            ),
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "table_ref": table_ref,
            "coordinate_space": {
                "unit": "table_normalized",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "table_bbox": scope,
            },
            "horizontal_signals": horizontal,
            "vertical_signals": vertical,
            "unsupported_vector_kinds": ["curve"],
            "source_accounting": {
                "objects_observed": len(vector_refs | rect_refs),
                "vector_line_objects": len(vector_refs),
                "rect_objects": len(rect_refs),
                "horizontal_signals": len(horizontal),
                "vertical_signals": len(vertical),
                "semantic_grid_claimed": False,
                "source_values_consumed": False,
            },
            "legacy_grid_consumed": False,
        }
        result["observation_checksum"] = sha256_json(result)
        errors = self.validate_observation(result)
        if errors:
            raise PdfParserGeometryError(errors[0])
        return result

    def validate_observation(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _OBSERVATION_KEYS:
            errors.append("pdf_parser_geometry_observation_keys_invalid")
        if data.get("schema_version") != PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA:
            errors.append("pdf_parser_geometry_observation_schema_invalid")
        if data.get("policy_version") != self.config.policy_version:
            errors.append("pdf_parser_geometry_observation_policy_invalid")
        if data.get("policy_configuration_hash") != sha256_json(asdict(self.config)):
            errors.append("pdf_parser_geometry_observation_config_invalid")
        if data.get("legacy_grid_consumed") is not False:
            errors.append("pdf_parser_geometry_legacy_grid_forbidden")
        if not all(
            isinstance(data.get(key), str) and bool(data.get(key))
            for key in (
                "observation_id",
                "document_ref",
                "pdf_sha256",
                "page_ref",
                "table_ref",
            )
        ) or not isinstance(data.get("page_number"), int) or isinstance(
            data.get("page_number"), bool
        ) or int(data.get("page_number") or 0) < 1:
            errors.append("pdf_parser_geometry_identity_invalid")
        coordinate = _object(data.get("coordinate_space"))
        if set(coordinate) != {
            "unit",
            "origin",
            "x_axis",
            "y_axis",
            "table_bbox",
        } or coordinate != {
            "unit": "table_normalized",
            "origin": "top_left",
            "x_axis": "right",
            "y_axis": "down",
            "table_bbox": coordinate.get("table_bbox"),
        }:
            errors.append("pdf_parser_geometry_coordinate_space_invalid")
        if _bbox(coordinate.get("table_bbox")) is None:
            errors.append("pdf_parser_geometry_table_bbox_invalid")
        if data.get("unsupported_vector_kinds") != ["curve"]:
            errors.append("pdf_parser_geometry_unsupported_kind_contract_invalid")
        for key, orientation in (
            ("horizontal_signals", "horizontal"),
            ("vertical_signals", "vertical"),
        ):
            values = data.get(key)
            if not isinstance(values, list):
                errors.append("pdf_parser_geometry_signal_inventory_invalid")
                continue
            for signal in values:
                current = _object(signal)
                extent = current.get("extent_normalized")
                if (
                    set(current) != _SIGNAL_KEYS
                    or current.get("kind") not in {"vector_line", "rect_edge"}
                    or current.get("orientation") != orientation
                    or not current.get("signal_id")
                    or not current.get("source_object_ref")
                    or not _normalized_number(current.get("position_normalized"), edge=True)
                    or not isinstance(extent, list)
                    or len(extent) != 2
                    or not all(_normalized_number(item, edge=True) for item in extent)
                    or float(extent[0]) > float(extent[1])
                    or (
                        current.get("linewidth_points") is not None
                        and not _nonnegative_number(current.get("linewidth_points"))
                    )
                ):
                    errors.append("pdf_parser_geometry_signal_invalid")
                    break
        total = len(_dicts(data.get("horizontal_signals"))) + len(
            _dicts(data.get("vertical_signals"))
        )
        if total > self.config.maximum_signals:
            errors.append("pdf_parser_geometry_signal_budget_exceeded")
        all_signals = [
            *_dicts(data.get("horizontal_signals")),
            *_dicts(data.get("vertical_signals")),
        ]
        signal_ids = [str(item.get("signal_id") or "") for item in all_signals]
        if len(signal_ids) != len(set(signal_ids)):
            errors.append("pdf_parser_geometry_signal_identity_duplicate")
        vector_refs = {
            str(item.get("source_object_ref") or "")
            for item in all_signals
            if item.get("kind") == "vector_line"
        }
        rect_refs = {
            str(item.get("source_object_ref") or "")
            for item in all_signals
            if item.get("kind") == "rect_edge"
        }
        expected_accounting = {
            "objects_observed": len(vector_refs | rect_refs),
            "vector_line_objects": len(vector_refs),
            "rect_objects": len(rect_refs),
            "horizontal_signals": len(_dicts(data.get("horizontal_signals"))),
            "vertical_signals": len(_dicts(data.get("vertical_signals"))),
            "semantic_grid_claimed": False,
            "source_values_consumed": False,
        }
        if data.get("source_accounting") != expected_accounting:
            errors.append("pdf_parser_geometry_source_accounting_invalid")
        expected_observation_id = _observation_id(
            pdf_sha256=data.get("pdf_sha256"),
            page_ref=data.get("page_ref"),
            table_ref=data.get("table_ref"),
            table_bbox=coordinate.get("table_bbox"),
            horizontal_signals=data.get("horizontal_signals"),
            vertical_signals=data.get("vertical_signals"),
            policy_version=self.config.policy_version,
        )
        if data.get("observation_id") != expected_observation_id:
            errors.append("pdf_parser_geometry_observation_identity_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("observation_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_parser_geometry_observation_checksum_invalid")
        return sorted(set(errors))

    def upgrade_v1_observation(self, value: Any) -> dict[str, Any]:
        data = copy.deepcopy(_object(value))
        if (
            set(data) != _OBSERVATION_KEYS
            or data.get("schema_version") != _LEGACY_OBSERVATION_SCHEMA
            or data.get("policy_version") != _LEGACY_POLICY_VERSION
        ):
            raise PdfParserGeometryError(
                "pdf_parser_geometry_legacy_observation_contract_invalid"
            )
        unsigned = dict(data)
        stored_checksum = unsigned.pop("observation_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            raise PdfParserGeometryError(
                "pdf_parser_geometry_legacy_observation_checksum_invalid"
            )
        legacy_config = asdict(self.config)
        legacy_config["policy_version"] = _LEGACY_POLICY_VERSION
        if data.get("policy_configuration_hash") != sha256_json(legacy_config):
            raise PdfParserGeometryError(
                "pdf_parser_geometry_legacy_observation_config_invalid"
            )
        data["schema_version"] = PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA
        data["policy_version"] = self.config.policy_version
        data["policy_configuration_hash"] = sha256_json(asdict(self.config))
        coordinate = _object(data.get("coordinate_space"))
        data["observation_id"] = _observation_id(
            pdf_sha256=data.get("pdf_sha256"),
            page_ref=data.get("page_ref"),
            table_ref=data.get("table_ref"),
            table_bbox=coordinate.get("table_bbox"),
            horizontal_signals=data.get("horizontal_signals"),
            vertical_signals=data.get("vertical_signals"),
            policy_version=self.config.policy_version,
        )
        data.pop("observation_checksum", None)
        data["observation_checksum"] = sha256_json(data)
        errors = self.validate_observation(data)
        if errors:
            raise PdfParserGeometryError(errors[0])
        return data

    def _line_signals(
        self,
        *,
        source_bbox: list[float],
        source_ref: str,
        scope: list[float],
        linewidth: float | None,
    ) -> list[dict[str, Any]]:
        width = source_bbox[2] - source_bbox[0]
        height = source_bbox[3] - source_bbox[1]
        signals: list[dict[str, Any]] = []
        if (
            width <= self.config.axis_alignment_tolerance_points
            and height >= self.config.minimum_signal_extent_points
        ):
            signals.append(
                _signal(
                    kind="vector_line",
                    orientation="vertical",
                    source_ref=source_ref,
                    edge="center",
                    position=(source_bbox[0] + source_bbox[2]) / 2,
                    extent=[source_bbox[1], source_bbox[3]],
                    scope=scope,
                    linewidth=linewidth,
                )
            )
        if (
            height <= self.config.axis_alignment_tolerance_points
            and width >= self.config.minimum_signal_extent_points
        ):
            signals.append(
                _signal(
                    kind="vector_line",
                    orientation="horizontal",
                    source_ref=source_ref,
                    edge="center",
                    position=(source_bbox[1] + source_bbox[3]) / 2,
                    extent=[source_bbox[0], source_bbox[2]],
                    scope=scope,
                    linewidth=linewidth,
                )
            )
        return signals

    def _rect_signals(
        self,
        *,
        source_bbox: list[float],
        source_ref: str,
        scope: list[float],
        linewidth: float | None,
    ) -> list[dict[str, Any]]:
        if (
            source_bbox[2] - source_bbox[0]
            < self.config.minimum_signal_extent_points
            or source_bbox[3] - source_bbox[1]
            < self.config.minimum_signal_extent_points
        ):
            return []
        return [
            _signal(
                kind="rect_edge",
                orientation="vertical",
                source_ref=source_ref,
                edge=edge,
                position=position,
                extent=[source_bbox[1], source_bbox[3]],
                scope=scope,
                linewidth=linewidth,
            )
            for edge, position in (("left", source_bbox[0]), ("right", source_bbox[2]))
        ] + [
            _signal(
                kind="rect_edge",
                orientation="horizontal",
                source_ref=source_ref,
                edge=edge,
                position=position,
                extent=[source_bbox[0], source_bbox[2]],
                scope=scope,
                linewidth=linewidth,
            )
            for edge, position in (("top", source_bbox[1]), ("bottom", source_bbox[3]))
        ]


def _signal(
    *,
    kind: str,
    orientation: str,
    source_ref: str,
    edge: str,
    position: float,
    extent: list[float],
    scope: list[float],
    linewidth: float | None,
) -> dict[str, Any]:
    axis_start = scope[1] if orientation == "horizontal" else scope[0]
    axis_length = (
        scope[3] - scope[1] if orientation == "horizontal" else scope[2] - scope[0]
    )
    extent_start = scope[0] if orientation == "horizontal" else scope[1]
    extent_length = (
        scope[2] - scope[0] if orientation == "horizontal" else scope[3] - scope[1]
    )
    normalized_position = _clip((position - axis_start) / axis_length)
    normalized_extent = sorted(
        [
            _clip((extent[0] - extent_start) / extent_length),
            _clip((extent[1] - extent_start) / extent_length),
        ]
    )
    return {
        "signal_id": "pdfgeomsig_"
        + stable_digest(
            [kind, orientation, source_ref, edge, normalized_position, normalized_extent],
            length=24,
        ),
        "source_object_ref": source_ref,
        "kind": kind,
        "orientation": orientation,
        "position_normalized": round(normalized_position, 12),
        "extent_normalized": [round(item, 12) for item in normalized_extent],
        "linewidth_points": linewidth,
    }


def _observation_id(
    *,
    pdf_sha256: Any,
    page_ref: Any,
    table_ref: Any,
    table_bbox: Any,
    horizontal_signals: Any,
    vertical_signals: Any,
    policy_version: str,
) -> str:
    return "pdfparsergeom_" + sha256_json(
        {
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "table_ref": table_ref,
            "table_bbox": table_bbox,
            "horizontal_signals": horizontal_signals,
            "vertical_signals": vertical_signals,
            "policy_version": policy_version,
        }
    )[:24]


def _deduplicate_signals(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in values:
        result[str(item.get("signal_id") or "")] = copy.deepcopy(item)
    return sorted(
        result.values(),
        key=lambda item: (
            float(item["position_normalized"]),
            float(item["extent_normalized"][0]),
            float(item["extent_normalized"][1]),
            str(item["kind"]),
            str(item["signal_id"]),
        ),
    )


def _bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(_number(item) for item in value)
    ):
        return None
    result = [float(item) for item in value]
    if result[0] > result[2] or result[1] > result[3]:
        return None
    return result


def _intersects(left: list[float], right: list[float], *, tolerance: float) -> bool:
    return not (
        left[2] < right[0] - tolerance
        or left[0] > right[2] + tolerance
        or left[3] < right[1] - tolerance
        or left[1] > right[3] + tolerance
    )


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _optional_number(value: Any) -> float | None:
    return float(value) if _number(value) else None


def _normalized_number(value: Any, *, edge: bool) -> bool:
    if not _number(value):
        return False
    current = float(value)
    return 0.0 <= current <= 1.0 if edge else 0.0 < current < 1.0


def _nonnegative_number(value: Any) -> bool:
    return _number(value) and float(value) >= 0


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
