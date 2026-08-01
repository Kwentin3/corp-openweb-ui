from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError


SCHEMA_VERSION = "broker_reports_managed_document_v1"
SCHEMA_ID = (
    "https://kwentin3.github.io/corp-openweb-ui/schemas/"
    "broker_reports_managed_document_v1.schema.json"
)


class SourceFormat(StrEnum):
    PDF = "PDF"
    HTML = "HTML"
    CSV = "CSV"
    XLSX = "XLSX"
    XLS = "XLS"
    UNKNOWN = "UNKNOWN"


class BlockType(StrEnum):
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    LIST = "LIST"
    TABLE = "TABLE"
    NOTE = "NOTE"
    VISUAL = "VISUAL"
    BOUNDARY = "BOUNDARY"
    UNKNOWN = "UNKNOWN"


class RelationType(StrEnum):
    BELONGS_TO_SECTION = "BELONGS_TO_SECTION"
    CAPTION_FOR = "CAPTION_FOR"
    NOTE_FOR = "NOTE_FOR"
    FOOTNOTE_FOR = "FOOTNOTE_FOR"
    CONTINUATION_OF = "CONTINUATION_OF"
    SAME_LOGICAL_OBJECT = "SAME_LOGICAL_OBJECT"
    EXPLAINS = "EXPLAINS"
    UNKNOWN_RELATION = "UNKNOWN_RELATION"


class ValueStatus(StrEnum):
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONFLICTING = "CONFLICTING"


class Origin(StrEnum):
    SOURCE_EXPLICIT = "SOURCE_EXPLICIT"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"
    MODEL_PROPOSED = "MODEL_PROPOSED"
    OPERATOR_SUPPLIED = "OPERATOR_SUPPLIED"
    UNKNOWN_ORIGIN = "UNKNOWN_ORIGIN"


class DocumentQualityStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class CellState(StrEnum):
    PRESENT = "PRESENT"
    EMPTY = "EMPTY"
    UNREADABLE = "UNREADABLE"
    UNKNOWN = "UNKNOWN"


class ManagedDocumentContractError(ValueError):
    """Raised when a managed-document candidate violates the v1 contract."""


@dataclass(frozen=True)
class ManagedDocument:
    """Validated inactive contract value with deterministic JSON methods."""

    payload: dict[str, Any]

    def canonical_json_bytes(self) -> bytes:
        return canonical_document_json_bytes(self.payload)

    @property
    def integrity_sha256(self) -> str:
        return str(self.payload["integrity_sha256"])


class ManagedDocumentContractValidator:
    """The sole inactive validator for managed-document contract v1."""

    def __init__(self, schema: Mapping[str, Any]) -> None:
        self._schema = copy.deepcopy(dict(schema))
        if self._schema.get("$id") != SCHEMA_ID:
            _fail("managed_document_schema_id_invalid")
        try:
            Draft202012Validator.check_schema(self._schema)
        except SchemaError as exc:
            raise ManagedDocumentContractError(
                "managed_document_schema_invalid"
            ) from exc
        self._validator = Draft202012Validator(
            self._schema,
            format_checker=FormatChecker(),
        )

    def parse_json(self, raw: str | bytes) -> ManagedDocument:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManagedDocumentContractError(
                "managed_document_json_invalid"
            ) from exc
        if not isinstance(payload, dict):
            _fail("managed_document_root_invalid")
        return self.validate(payload)

    def validate(self, payload: Mapping[str, Any]) -> ManagedDocument:
        candidate = copy.deepcopy(dict(payload))
        try:
            self._validator.validate(candidate)
        except ValidationError as exc:
            path = "/".join(str(part) for part in exc.absolute_path)
            suffix = f":{path}" if path else ""
            raise ManagedDocumentContractError(
                f"managed_document_schema_validation_failed{suffix}"
            ) from exc
        _validate_semantic_invariants(candidate)
        return ManagedDocument(payload=candidate)

    def seal(self, payload: Mapping[str, Any]) -> ManagedDocument:
        candidate = copy.deepcopy(dict(payload))
        candidate.pop("integrity_sha256", None)
        candidate["integrity_sha256"] = compute_document_integrity_sha256(
            candidate
        )
        return self.validate(candidate)


def canonical_document_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_document_integrity_sha256(payload: Mapping[str, Any]) -> str:
    unsigned = copy.deepcopy(dict(payload))
    unsigned.pop("integrity_sha256", None)
    return hashlib.sha256(canonical_document_json_bytes(unsigned)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("managed_document_duplicate_json_key")
        value[key] = item
    return value


def _validate_semantic_invariants(payload: dict[str, Any]) -> None:
    if payload["schema_version"] != SCHEMA_VERSION:
        _fail("managed_document_schema_version_invalid")

    anchors = payload["anchors"]
    anchor_ids = _unique_ids(anchors, "anchor_id", "source_anchor")
    source_format = payload["source"]["format"]
    source_part_count = payload["source"]["source_part_count"]
    if payload["source"]["source_details"]["kind"] != source_format:
        _fail("managed_document_source_details_format_mismatch")
    for anchor in anchors:
        if anchor["source_format"] != source_format:
            _fail("managed_document_anchor_source_format_mismatch")
        if anchor["locator"]["kind"] != source_format:
            _fail("managed_document_anchor_locator_format_mismatch")
        _validate_anchor_part_range(anchor, source_part_count)

    blocks = payload["blocks"]
    block_ids = _unique_ids(blocks, "block_id", "block")
    ordinals = [block["ordinal"] for block in blocks]
    if ordinals != list(range(len(blocks))):
        _fail("managed_document_block_ordinal_invalid")

    quality = payload["quality"]
    issues = quality["issue_ledger"]
    issue_ids = _unique_ids(issues, "issue_id", "issue")
    losses = quality["loss_ledger"]
    loss_ids = _unique_ids(losses, "loss_id", "loss")

    additional_metadata = payload["metadata"]["additional"]
    additional_names = [item["name"] for item in additional_metadata]
    if len(additional_names) != len(set(additional_names)):
        _fail("managed_document_duplicate_additional_metadata_name")
    metadata_fields: list[dict[str, Any]] = []
    for field in payload["metadata"].values():
        if isinstance(field, list):
            for item in field:
                _validate_metadata_field(item, anchor_ids)
                metadata_fields.append(item)
        else:
            _validate_metadata_field(field, anchor_ids)
            metadata_fields.append(field)

    table_ids: set[str] = set()
    for block in blocks:
        _require_refs(block["source_anchor_ids"], anchor_ids, "block_anchor")
        _require_refs(block["issue_ids"], issue_ids, "block_issue")
        content = block["content"]
        block_type = block["block_type"]
        if block_type == BlockType.TABLE:
            table_id = content["table_id"]
            if table_id in table_ids:
                _fail("managed_document_duplicate_table_id")
            table_ids.add(table_id)
            _validate_table_content(content, anchor_ids, issue_ids, loss_ids)
        elif block_type == BlockType.LIST:
            item_ordinals = [item["ordinal"] for item in content["items"]]
            if item_ordinals != list(range(len(item_ordinals))):
                _fail("managed_document_list_ordinal_invalid")
            item_ids = [item["item_id"] for item in content["items"]]
            if len(item_ids) != len(set(item_ids)):
                _fail("managed_document_duplicate_list_item_id")
        elif block_type == BlockType.BOUNDARY:
            if not 1 <= content["source_part_index"] <= source_part_count:
                _fail("managed_document_boundary_source_part_invalid")
        elif block_type == BlockType.UNKNOWN:
            private_ref = content["private_artifact"]["ref"]
            if content["raw_text"] is None and private_ref is None:
                _fail("managed_document_unknown_block_evidence_missing")

    relations = payload["relations"]
    relation_ids = _unique_ids(relations, "relation_id", "relation")
    for relation in relations:
        _validate_relation_endpoint(relation["source"], blocks, block_ids)
        _validate_relation_endpoint(relation["target"], blocks, block_ids)
        _require_refs(
            relation["evidence_anchor_ids"], anchor_ids, "relation_anchor"
        )
        _require_refs(relation["issue_ids"], issue_ids, "relation_issue")
        if relation["origin"] == Origin.SOURCE_EXPLICIT and not relation[
            "evidence_anchor_ids"
        ]:
            _fail("managed_document_source_explicit_relation_evidence_missing")

    for block in blocks:
        if block["block_type"] == BlockType.TABLE:
            content = block["content"]
            _require_refs(
                content["related_relation_ids"],
                relation_ids,
                "table_relation",
            )
            _require_refs(
                content["continuation_relation_ids"],
                relation_ids,
                "table_continuation_relation",
            )
            continuation_ids = set(content["continuation_relation_ids"])
            for relation in relations:
                if relation["relation_id"] in continuation_ids and relation[
                    "relation_type"
                ] not in {
                    RelationType.CONTINUATION_OF,
                    RelationType.SAME_LOGICAL_OBJECT,
                }:
                    _fail("managed_document_table_continuation_type_invalid")

    for issue in issues:
        _require_refs(issue["anchor_ids"], anchor_ids, "issue_anchor")
        _require_refs(issue["block_ids"], block_ids, "issue_block")
        _require_refs(issue["relation_ids"], relation_ids, "issue_relation")
    for loss in losses:
        if loss["accounted"] is not True:
            _fail("managed_document_loss_unaccounted")
        _require_refs(loss["anchor_ids"], anchor_ids, "loss_anchor")
        _require_refs(loss["block_ids"], block_ids, "loss_block")

    if quality["preserved_blocks_total"] != len(blocks):
        _fail("managed_document_preserved_block_count_invalid")
    unknown_total = sum(
        block["block_type"] == BlockType.UNKNOWN for block in blocks
    )
    if quality["unknown_blocks_total"] != unknown_total:
        _fail("managed_document_unknown_block_count_invalid")
    if quality["known_losses_total"] != len(losses):
        _fail("managed_document_known_loss_count_invalid")
    conflicts_total = sum(
        field["status"] == ValueStatus.CONFLICTING for field in metadata_fields
    ) + sum(relation["status"] == "CONFLICTING" for relation in relations)
    if quality["conflicts_total"] != conflicts_total:
        _fail("managed_document_conflict_count_invalid")
    blocking_total = sum(loss["blocks_semantic_analysis"] for loss in losses)
    if quality["blocking_losses_total"] != blocking_total:
        _fail("managed_document_blocking_loss_count_invalid")
    if quality["unaccounted_context_loss_total"] != 0:
        _fail("managed_document_unaccounted_context_loss_forbidden")
    if quality["source_elements_total"] < len(blocks):
        _fail("managed_document_source_element_count_invalid")

    status = quality["status"]
    if status == DocumentQualityStatus.COMPLETE:
        if blocking_total != 0:
            _fail("managed_document_complete_with_blocking_loss")
        if (
            unknown_total != 0
            or quality["unsupported_elements_total"] != 0
            or losses
            or conflicts_total != 0
            or any(
                block["restoration"]["status"] != "RESTORED"
                for block in blocks
            )
        ):
            _fail("managed_document_complete_with_incomplete_context")
    if status == DocumentQualityStatus.BLOCKED and blocking_total == 0:
        _fail("managed_document_blocked_without_blocking_loss")
    if status == DocumentQualityStatus.PARTIAL and blocking_total != 0:
        _fail("managed_document_partial_with_blocking_loss")
    if status == DocumentQualityStatus.PARTIAL and not (
        unknown_total
        or quality["unsupported_elements_total"]
        or losses
        or conflicts_total
        or any(
            block["restoration"]["status"] != "RESTORED" for block in blocks
        )
    ):
        _fail("managed_document_partial_without_incomplete_context")

    claimed_integrity = payload["integrity_sha256"]
    if claimed_integrity != compute_document_integrity_sha256(payload):
        _fail("managed_document_integrity_invalid")


def _validate_anchor_part_range(anchor: dict[str, Any], part_count: int) -> None:
    locator = anchor["locator"]
    part_index = locator.get("source_part_index")
    if part_index is not None and not 1 <= part_index <= part_count:
        _fail("managed_document_anchor_source_part_invalid")
    if locator["kind"] == SourceFormat.PDF and locator["page"] > part_count:
        _fail("managed_document_anchor_pdf_page_invalid")
    if locator["kind"] == SourceFormat.CSV and (
        locator["row_start"] > locator["row_end"]
        or locator["column_start"] > locator["column_end"]
    ):
        _fail("managed_document_anchor_csv_range_invalid")


def _validate_metadata_field(field: dict[str, Any], anchor_ids: set[str]) -> None:
    _require_refs(
        field["evidence_anchor_ids"], anchor_ids, "metadata_anchor"
    )
    status = field["status"]
    value = field["value"]
    candidates = field["candidates"]
    if status == ValueStatus.PRESENT and (value is None or candidates):
        _fail("managed_document_metadata_present_value_invalid")
    if status in {ValueStatus.UNKNOWN, ValueStatus.NOT_APPLICABLE} and (
        value is not None or candidates
    ):
        _fail("managed_document_metadata_unknown_value_invalid")
    if status == ValueStatus.CONFLICTING and (
        value is not None or len(candidates) < 2
    ):
        _fail("managed_document_metadata_conflict_invalid")
    if field["origin"] == Origin.SOURCE_EXPLICIT and not field[
        "evidence_anchor_ids"
    ]:
        _fail("managed_document_source_explicit_evidence_missing")


def _validate_table_content(
    content: dict[str, Any],
    anchor_ids: set[str],
    issue_ids: set[str],
    loss_ids: set[str],
) -> None:
    rows = content["rows"]
    _validate_metadata_field(content["title"], anchor_ids)
    _require_refs(content["known_gap_ids"], loss_ids, "table_loss")
    annotation_coordinates = [
        (item["row_index"], item["column_index"])
        for item in content["cell_annotations"]
    ]
    if len(annotation_coordinates) != len(set(annotation_coordinates)):
        _fail("managed_document_duplicate_table_annotation")
    for annotation in content["cell_annotations"]:
        row_index = annotation["row_index"]
        column_index = annotation["column_index"]
        if row_index >= len(rows) or column_index >= len(rows[row_index]):
            _fail("managed_document_table_annotation_out_of_range")
        value = rows[row_index][column_index]
        if annotation["state"] == CellState.PRESENT and value is None:
            _fail("managed_document_present_cell_is_null")
        if annotation["state"] in {CellState.EMPTY, CellState.UNREADABLE} and (
            value is not None
        ):
            _fail("managed_document_absent_cell_has_value")
        _require_refs(
            annotation["evidence_anchor_ids"], anchor_ids, "cell_anchor"
        )
        _require_refs(annotation["issue_ids"], issue_ids, "cell_issue")
    for header in content["header_hierarchy"]["entries"]:
        if (
            header["row_index"] >= len(rows)
            or header["column_start"] > header["column_end"]
            or header["column_end"] >= len(rows[header["row_index"]])
        ):
            _fail("managed_document_table_header_coordinate_invalid")
    for group in content["row_groups"]["groups"]:
        if (
            group["row_start"] > group["row_end"]
            or group["row_end"] >= len(rows)
        ):
            _fail("managed_document_table_row_group_invalid")
    for marker in content["row_markers"]:
        if marker["row_index"] >= len(rows):
            _fail("managed_document_table_row_marker_invalid")
    for unit in content["units"]:
        if any(
            column_index >= max(len(row) for row in rows)
            for column_index in unit["column_indexes"]
        ):
            _fail("managed_document_table_unit_column_invalid")


def _validate_relation_endpoint(
    endpoint: dict[str, Any],
    blocks: list[dict[str, Any]],
    block_ids: set[str],
) -> None:
    block_id = endpoint["block_id"]
    if block_id not in block_ids:
        _fail("managed_document_relation_endpoint_missing")
    row_index = endpoint["row_index"]
    column_index = endpoint["column_index"]
    if column_index is not None and row_index is None:
        _fail("managed_document_relation_cell_without_row")
    if row_index is None:
        return
    block = next(item for item in blocks if item["block_id"] == block_id)
    if block["block_type"] != BlockType.TABLE:
        _fail("managed_document_relation_row_target_not_table")
    rows = block["content"]["rows"]
    if row_index >= len(rows):
        _fail("managed_document_relation_row_out_of_range")
    if column_index is not None and column_index >= len(rows[row_index]):
        _fail("managed_document_relation_column_out_of_range")


def _unique_ids(
    items: list[dict[str, Any]], key: str, label: str
) -> set[str]:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        _fail(f"managed_document_duplicate_{label}_id")
    return set(values)


def _require_refs(values: list[str], allowed: set[str], label: str) -> None:
    if len(values) != len(set(values)) or not set(values) <= allowed:
        _fail(f"managed_document_{label}_ref_invalid")


def _fail(code: str) -> None:
    raise ManagedDocumentContractError(code)
