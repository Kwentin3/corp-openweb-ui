from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .managed_document_contracts import (
    SCHEMA_ID as V1_SCHEMA_ID,
    SCHEMA_VERSION as V1_SCHEMA_VERSION,
    ManagedDocumentContractError,
    ManagedDocumentContractValidator,
    canonical_document_json_bytes,
    compute_document_integrity_sha256,
)


SCHEMA_VERSION = "broker_reports_managed_document_v2"
SCHEMA_ID = (
    "https://kwentin3.github.io/corp-openweb-ui/schemas/"
    "broker_reports_managed_document_v2.schema.json"
)

SOURCE_DERIVED_SPAN_ORIGINS = frozenset(
    {"SOURCE_EXPLICIT", "DETERMINISTIC_DERIVED"}
)


class CellState(StrEnum):
    PRESENT = "PRESENT"
    EMPTY = "EMPTY"
    UNREADABLE = "UNREADABLE"
    UNKNOWN = "UNKNOWN"
    COVERED_BY_SPAN = "COVERED_BY_SPAN"


class ManagedDocumentContractV2Error(ValueError):
    """Raised when a candidate violates the inactive v2 contract."""


@dataclass(frozen=True)
class ManagedDocumentV2:
    """Validated inactive v2 value with deterministic JSON methods."""

    payload: dict[str, Any]

    def canonical_json_bytes(self) -> bytes:
        return canonical_document_json_bytes(self.payload)

    @property
    def integrity_sha256(self) -> str:
        return str(self.payload["integrity_sha256"])


class ManagedDocumentContractV2Validator:
    """The sole inactive validator for Managed Document contract v2."""

    def __init__(
        self,
        schema: Mapping[str, Any],
        v1_schema: Mapping[str, Any] | None = None,
    ) -> None:
        self._schema = copy.deepcopy(dict(schema))
        if self._schema.get("$id") != SCHEMA_ID:
            _fail("managed_document_v2_schema_id_invalid")
        try:
            Draft202012Validator.check_schema(self._schema)
        except SchemaError as exc:
            raise ManagedDocumentContractV2Error(
                "managed_document_v2_schema_invalid"
            ) from exc
        self._validator = Draft202012Validator(
            self._schema,
            format_checker=FormatChecker(),
        )
        compatible_v1_schema = (
            copy.deepcopy(dict(v1_schema))
            if v1_schema is not None
            else _project_contract_schema_v2_to_v1(self._schema)
        )
        try:
            self._v1_validator = ManagedDocumentContractValidator(
                compatible_v1_schema
            )
        except ManagedDocumentContractError as exc:
            raise ManagedDocumentContractV2Error(
                f"managed_document_v2_v1_schema_invalid:{exc}"
            ) from exc

    def parse_json(self, raw: str | bytes) -> ManagedDocumentV2:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManagedDocumentContractV2Error(
                "managed_document_v2_json_invalid"
            ) from exc
        if not isinstance(payload, dict):
            _fail("managed_document_v2_root_invalid")
        return self.validate(payload)

    def validate(self, payload: Mapping[str, Any]) -> ManagedDocumentV2:
        candidate = copy.deepcopy(dict(payload))
        try:
            self._validator.validate(candidate)
        except ValidationError as exc:
            path = "/".join(str(part) for part in exc.absolute_path)
            suffix = f":{path}" if path else ""
            raise ManagedDocumentContractV2Error(
                f"managed_document_v2_schema_validation_failed{suffix}"
            ) from exc
        if candidate["schema_version"] != SCHEMA_VERSION:
            _fail("managed_document_v2_schema_version_invalid")

        projected = project_managed_document_v2_to_v1(candidate)
        try:
            self._v1_validator.validate(projected)
        except ManagedDocumentContractError as exc:
            raise ManagedDocumentContractV2Error(
                f"managed_document_v2_v1_compatibility_failed:{exc}"
            ) from exc

        _validate_span_invariants(candidate)
        claimed_integrity = candidate["integrity_sha256"]
        if claimed_integrity != compute_document_integrity_sha256(candidate):
            _fail("managed_document_v2_integrity_invalid")
        return ManagedDocumentV2(payload=candidate)

    def seal(self, payload: Mapping[str, Any]) -> ManagedDocumentV2:
        candidate = copy.deepcopy(dict(payload))
        candidate.pop("integrity_sha256", None)
        candidate["integrity_sha256"] = compute_document_integrity_sha256(
            candidate
        )
        return self.validate(candidate)


def project_managed_document_v2_to_v1(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a sealed deep-copy suitable only for historical v1 consumers.

    ``COVERED_BY_SPAN`` maps to ``UNKNOWN`` because v1 has no span state and
    mapping it to ``EMPTY`` or ``UNREADABLE`` would invent a false meaning.
    This compatibility projection is not a semantic parity claim.
    """

    projected = copy.deepcopy(dict(payload))
    if projected.get("schema_version") != SCHEMA_VERSION:
        _fail("managed_document_v2_projection_source_version_invalid")
    projected["schema_version"] = V1_SCHEMA_VERSION
    for block in projected.get("blocks", []):
        if block.get("block_type") != "TABLE":
            continue
        content = block.get("content", {})
        content.pop("cell_spans", None)
        for annotation in content.get("cell_annotations", []):
            annotation.pop("span_id", None)
            if annotation.get("state") == CellState.COVERED_BY_SPAN:
                annotation["state"] = CellState.UNKNOWN.value
    projected["integrity_sha256"] = compute_document_integrity_sha256(
        projected
    )
    return projected


def _project_contract_schema_v2_to_v1(
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    projected = copy.deepcopy(dict(schema))
    projected["$id"] = V1_SCHEMA_ID
    projected["title"] = "Broker Reports Managed Document v1"
    projected["properties"]["schema_version"]["const"] = V1_SCHEMA_VERSION

    table = projected["$defs"]["tableContent"]
    table["required"].remove("cell_spans")
    table["properties"].pop("cell_spans")
    annotation = table["properties"]["cell_annotations"]["items"]
    annotation["required"].remove("span_id")
    annotation["properties"].pop("span_id")
    annotation["properties"]["state"]["enum"].remove(
        CellState.COVERED_BY_SPAN.value
    )
    projected["$defs"].pop("cellSpan")
    projected["$defs"].pop("spanId")
    return projected


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("managed_document_v2_duplicate_json_key")
        value[key] = item
    return value


def _validate_span_invariants(payload: dict[str, Any]) -> None:
    anchor_ids = {anchor["anchor_id"] for anchor in payload["anchors"]}
    issue_ids = {
        issue["issue_id"] for issue in payload["quality"]["issue_ledger"]
    }
    for block in payload["blocks"]:
        if block["block_type"] != "TABLE":
            continue
        _validate_table_spans(
            block["content"],
            anchor_ids=anchor_ids,
            issue_ids=issue_ids,
        )


def _validate_table_spans(
    content: dict[str, Any],
    *,
    anchor_ids: set[str],
    issue_ids: set[str],
) -> None:
    rows = content["rows"]
    spans = content["cell_spans"]
    annotations = content["cell_annotations"]

    span_ids = [span["span_id"] for span in spans]
    if len(span_ids) != len(set(span_ids)):
        _fail("managed_document_v2_duplicate_span_id")
    span_ids_set = set(span_ids)

    annotation_by_coordinate: dict[tuple[int, int], dict[str, Any]] = {}
    covered_annotations: dict[tuple[int, int], dict[str, Any]] = {}
    for annotation in annotations:
        coordinate = (
            annotation["row_index"],
            annotation["column_index"],
        )
        annotation_by_coordinate[coordinate] = annotation
        state = annotation["state"]
        span_id = annotation["span_id"]
        if state == CellState.COVERED_BY_SPAN:
            if span_id is None or span_id not in span_ids_set:
                _fail("managed_document_v2_covered_span_ref_invalid")
            covered_annotations[coordinate] = annotation
            row_index, column_index = coordinate
            if rows[row_index][column_index] is not None:
                _fail("managed_document_v2_covered_cell_value_not_null")
            if annotation["evidence_anchor_ids"]:
                _fail("managed_document_v2_span_source_word_double_ownership")
        elif span_id is not None:
            _fail("managed_document_v2_noncovered_cell_has_span_id")

    coordinate_owner: dict[tuple[int, int], str] = {}
    span_by_id = {span["span_id"]: span for span in spans}
    max_columns = max(len(row) for row in rows)
    for span in spans:
        span_id = span["span_id"]
        row_start = span["row_start"]
        row_end = span["row_end"]
        column_start = span["column_start"]
        column_end = span["column_end"]
        value_coordinate = (
            span["value_row_index"],
            span["value_column_index"],
        )

        if (
            row_start > row_end
            or column_start > column_end
            or row_end >= len(rows)
            or column_end >= max_columns
        ):
            _fail("managed_document_v2_span_out_of_bounds")
        if not (
            row_start <= value_coordinate[0] <= row_end
            and column_start <= value_coordinate[1] <= column_end
        ):
            _fail("managed_document_v2_span_value_coordinate_outside")
        area = (row_end - row_start + 1) * (
            column_end - column_start + 1
        )
        if area < 2:
            _fail("managed_document_v2_span_area_too_small")
        for row_index in range(row_start, row_end + 1):
            if column_end >= len(rows[row_index]):
                _fail("managed_document_v2_span_missing_logical_coordinate")

        value_annotation = annotation_by_coordinate.get(value_coordinate)
        if (
            value_annotation is not None
            and value_annotation["state"] == CellState.COVERED_BY_SPAN
        ):
            _fail("managed_document_v2_span_value_coordinate_covered")

        _require_refs(
            span["evidence_anchor_ids"],
            anchor_ids,
            "managed_document_v2_span_anchor_ref_invalid",
        )
        _require_refs(
            span["issue_ids"],
            issue_ids,
            "managed_document_v2_span_issue_ref_invalid",
        )
        if (
            span["origin"] in SOURCE_DERIVED_SPAN_ORIGINS
            and not span["evidence_anchor_ids"]
        ):
            _fail("managed_document_v2_source_derived_span_evidence_missing")

        for row_index in range(row_start, row_end + 1):
            for column_index in range(column_start, column_end + 1):
                coordinate = (row_index, column_index)
                if coordinate in coordinate_owner:
                    _fail("managed_document_v2_spans_overlap")
                coordinate_owner[coordinate] = span_id
                if coordinate == value_coordinate:
                    continue
                annotation = annotation_by_coordinate.get(coordinate)
                if (
                    annotation is None
                    or annotation["state"] != CellState.COVERED_BY_SPAN
                    or annotation["span_id"] != span_id
                ):
                    _fail("managed_document_v2_span_covered_annotation_missing")

    for coordinate, annotation in covered_annotations.items():
        owner = coordinate_owner.get(coordinate)
        if owner is None or owner != annotation["span_id"]:
            _fail("managed_document_v2_covered_coordinate_owner_invalid")
        if annotation["span_id"] not in span_by_id:
            _fail("managed_document_v2_covered_span_ref_invalid")

    _validate_header_span_compatibility(content, spans)


def _validate_header_span_compatibility(
    content: dict[str, Any],
    spans: list[dict[str, Any]],
) -> None:
    for header in content["header_hierarchy"]["entries"]:
        header_row = header["row_index"]
        header_start = header["column_start"]
        header_end = header["column_end"]
        for span in spans:
            if not span["row_start"] <= header_row <= span["row_end"]:
                continue
            overlap = not (
                span["column_end"] < header_start
                or span["column_start"] > header_end
            )
            if not overlap:
                continue
            compatible = (
                span["value_row_index"] == header_row
                and span["column_start"] == header_start
                and span["column_end"] == header_end
            )
            if not compatible:
                _fail("managed_document_v2_header_span_coverage_conflict")


def _require_refs(
    values: list[str], allowed: set[str], error_code: str
) -> None:
    if len(values) != len(set(values)) or not set(values) <= allowed:
        _fail(error_code)


def _fail(code: str) -> None:
    raise ManagedDocumentContractV2Error(code)
