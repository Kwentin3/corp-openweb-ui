from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .managed_document_contracts import (
    canonical_document_json_bytes,
    compute_document_integrity_sha256,
)


SCHEMA_VERSION = "broker_reports_managed_document_v2"
SCHEMA_ID = (
    "https://kwentin3.github.io/corp-openweb-ui/schemas/"
    "broker_reports_managed_document_v2.schema.json"
)
SCHEMA_CANONICAL_SHA256 = (
    "c626ea6c63d5d9dc0e410736abef6d38c209196139dd5e3a3be02ec0205f4bd3"
)
_STANDARD_METADATA_NAMES = {
    "document_type",
    "title",
    "issuer",
    "document_date",
    "reporting_period",
    "owner_or_account",
    "language",
    "primary_currency",
}


class LogicalRowRole(StrEnum):
    TABLE_TITLE = "TABLE_TITLE"
    COLUMN_HEADER = "COLUMN_HEADER"
    GROUP_HEADER = "GROUP_HEADER"
    DATA = "DATA"
    SUBTOTAL = "SUBTOTAL"
    TOTAL = "TOTAL"
    NOTE = "NOTE"
    CONTINUATION_HEADER = "CONTINUATION_HEADER"
    UNKNOWN = "UNKNOWN"


class RowEntryKind(StrEnum):
    LABEL = "LABEL"
    VALUE = "VALUE"
    UNIT = "UNIT"
    MARKER = "MARKER"
    NOTE = "NOTE"
    UNKNOWN = "UNKNOWN"


class ColumnBindingStatus(StrEnum):
    BOUND = "BOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ManagedDocumentContractV2Error(ValueError):
    """Raised when a candidate violates the inactive v2 contract."""


@dataclass(frozen=True)
class ManagedDocumentV2:
    """Validated inactive row-oriented document with canonical JSON methods."""

    payload: dict[str, Any]

    def canonical_json_bytes(self) -> bytes:
        return canonical_document_json_bytes(self.payload)

    @property
    def integrity_sha256(self) -> str:
        return str(self.payload["integrity_sha256"])


class ManagedDocumentContractV2Validator:
    """Sole validator for the additive row-oriented document contract."""

    def __init__(self, schema: Mapping[str, Any]) -> None:
        self._schema = copy.deepcopy(dict(schema))
        if self._schema.get("$id") != SCHEMA_ID:
            _fail("managed_document_v2_schema_id_invalid")
        if _canonical_schema_sha256(self._schema) != SCHEMA_CANONICAL_SHA256:
            _fail("managed_document_v2_schema_hash_invalid")
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

    @property
    def schema_canonical_sha256(self) -> str:
        return SCHEMA_CANONICAL_SHA256

    def parse_json(self, raw: str | bytes) -> ManagedDocumentV2:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            payload = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_non_finite_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManagedDocumentContractV2Error(
                "managed_document_v2_json_invalid"
            ) from exc
        if not isinstance(payload, dict):
            _fail("managed_document_v2_root_invalid")
        return self.validate(payload)

    def validate(self, payload: Mapping[str, Any]) -> ManagedDocumentV2:
        candidate = copy.deepcopy(dict(payload))
        _reject_non_finite_numbers(candidate)
        try:
            self._validator.validate(candidate)
        except ValidationError as exc:
            path = "/".join(str(part) for part in exc.absolute_path)
            suffix = f":{path}" if path else ""
            raise ManagedDocumentContractV2Error(
                f"managed_document_v2_schema_validation_failed{suffix}"
            ) from exc
        _validate_semantic_invariants(candidate)
        return ManagedDocumentV2(payload=candidate)

    def seal(self, payload: Mapping[str, Any]) -> ManagedDocumentV2:
        candidate = copy.deepcopy(dict(payload))
        candidate.pop("integrity_sha256", None)
        _reject_non_finite_numbers(candidate)
        candidate["integrity_sha256"] = compute_document_integrity_sha256(
            candidate
        )
        return self.validate(candidate)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("managed_document_v2_duplicate_json_key")
        value[key] = item
    return value


def _reject_non_finite_json_constant(_: str) -> None:
    _fail("managed_document_v2_non_finite_number_forbidden")


def _reject_non_finite_numbers(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        _fail("managed_document_v2_non_finite_number_forbidden")
    if isinstance(value, dict):
        for item in value.values():
            _reject_non_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_non_finite_numbers(item)


def _canonical_schema_sha256(schema: Mapping[str, Any]) -> str:
    try:
        canonical = json.dumps(
            schema,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ManagedDocumentContractV2Error(
            "managed_document_v2_schema_invalid"
        ) from exc
    return hashlib.sha256(canonical).hexdigest()


def _validate_semantic_invariants(payload: dict[str, Any]) -> None:
    if payload["schema_version"] != SCHEMA_VERSION:
        _fail("managed_document_v2_schema_version_invalid")

    source = payload["source"]
    source_format = source["format"]
    source_part_count = source["source_part_count"]
    if source["source_details"]["kind"] != source_format:
        _fail("managed_document_v2_source_details_format_mismatch")

    anchors = payload["anchors"]
    anchor_ids = _unique_ids(anchors, "anchor_id", "source_anchor")
    anchor_by_id = {item["anchor_id"]: item for item in anchors}
    for anchor in anchors:
        if anchor["source_format"] != source_format:
            _fail("managed_document_v2_anchor_source_format_mismatch")
        if anchor["locator"]["kind"] != source_format:
            _fail("managed_document_v2_anchor_locator_format_mismatch")
        _validate_anchor_part_range(anchor, source_part_count)

    issues = payload["quality"]["issue_ledger"]
    issue_ids = _unique_ids(issues, "issue_id", "issue")
    losses = payload["quality"]["loss_ledger"]
    loss_ids = _unique_ids(losses, "loss_id", "loss")

    evidence = payload["geometry_evidence"]
    evidence_ids = _unique_ids(
        evidence,
        "geometry_evidence_id",
        "geometry_evidence",
    )
    evidence_by_id = {
        item["geometry_evidence_id"]: item for item in evidence
    }
    for item in evidence:
        _require_refs(
            item["source_anchor_ids"],
            anchor_ids,
            "geometry_evidence_anchor",
        )
        _require_refs(
            item["issue_ids"],
            issue_ids,
            "geometry_evidence_issue",
        )
        if item["origin"] == "MODEL_PROPOSED":
            _fail("managed_document_v2_model_geometry_evidence_forbidden")
        if item["private_artifact"]["status"] != "PRESENT":
            _fail("managed_document_v2_geometry_private_artifact_missing")

    metadata_fields: list[dict[str, Any]] = []
    additional_names = [
        item["name"] for item in payload["metadata"]["additional"]
    ]
    if (
        len(additional_names) != len(set(additional_names))
        or set(additional_names) & _STANDARD_METADATA_NAMES
    ):
        _fail("managed_document_v2_duplicate_additional_metadata_name")
    for field in payload["metadata"].values():
        if isinstance(field, list):
            for item in field:
                _validate_metadata_field(item, anchor_ids)
                metadata_fields.append(item)
        else:
            _validate_metadata_field(field, anchor_ids)
            metadata_fields.append(field)

    blocks = payload["blocks"]
    block_ids = _unique_ids(blocks, "block_id", "block")
    if [item["ordinal"] for item in blocks] != list(range(len(blocks))):
        _fail("managed_document_v2_block_ordinal_invalid")

    table_ids: set[str] = set()
    row_ids: set[str] = set()
    entry_ids: set[str] = set()
    column_ids: set[str] = set()
    source_part_ids: set[str] = set()
    rows_by_id: dict[str, tuple[str, str, dict[str, Any]]] = {}
    entries_by_id: dict[
        str,
        tuple[str, str, str, dict[str, Any]],
    ] = {}
    table_by_id: dict[str, tuple[str, dict[str, Any]]] = {}
    used_evidence_ids: set[str] = set()

    for block in blocks:
        _require_refs(
            block["source_anchor_ids"],
            anchor_ids,
            "block_anchor",
        )
        _require_refs(block["issue_ids"], issue_ids, "block_issue")
        _require_refs(
            block["restoration"]["issue_ids"],
            issue_ids,
            "block_restoration_issue",
        )
        content = block["content"]
        block_type = block["block_type"]
        if block_type == "TABLE":
            table_id = content["table_id"]
            _claim_id(table_id, table_ids, "table")
            table_by_id[table_id] = (block["block_id"], content)
            _validate_table_content(
                block_id=block["block_id"],
                content=content,
                anchor_ids=anchor_ids,
                anchor_by_id=anchor_by_id,
                evidence_ids=evidence_ids,
                evidence_by_id=evidence_by_id,
                issue_ids=issue_ids,
                loss_ids=loss_ids,
                relation_ids=None,
                document_row_ids=row_ids,
                document_entry_ids=entry_ids,
                document_column_ids=column_ids,
                document_source_part_ids=source_part_ids,
                rows_by_id=rows_by_id,
                entries_by_id=entries_by_id,
                used_evidence_ids=used_evidence_ids,
                source_part_count=source_part_count,
            )
        elif block_type == "LIST":
            item_ordinals = [item["ordinal"] for item in content["items"]]
            if item_ordinals != list(range(len(item_ordinals))):
                _fail("managed_document_v2_list_ordinal_invalid")
            _unique_ids(content["items"], "item_id", "list_item")
        elif block_type == "BOUNDARY":
            if not 1 <= content["source_part_index"] <= source_part_count:
                _fail("managed_document_v2_boundary_source_part_invalid")
        elif block_type == "UNKNOWN":
            private_ref = content["private_artifact"]["ref"]
            if content["raw_text"] is None and private_ref is None:
                _fail("managed_document_v2_unknown_block_evidence_missing")

    relations = payload["relations"]
    relation_ids = _unique_ids(relations, "relation_id", "relation")
    for relation in relations:
        _validate_relation_endpoint(
            relation["source"],
            blocks_by_id={item["block_id"]: item for item in blocks},
            rows_by_id=rows_by_id,
            entries_by_id=entries_by_id,
        )
        _validate_relation_endpoint(
            relation["target"],
            blocks_by_id={item["block_id"]: item for item in blocks},
            rows_by_id=rows_by_id,
            entries_by_id=entries_by_id,
        )
        _require_refs(
            relation["evidence_anchor_ids"],
            anchor_ids,
            "relation_anchor",
        )
        _require_refs(relation["issue_ids"], issue_ids, "relation_issue")
        if (
            relation["origin"] == "SOURCE_EXPLICIT"
            and not relation["evidence_anchor_ids"]
        ):
            _fail(
                "managed_document_v2_source_explicit_relation_evidence_missing"
            )

    for table_id, (block_id, content) in table_by_id.items():
        _require_refs(content["relations"], relation_ids, "table_relation")
        for relation_id in content["relations"]:
            relation = next(
                item
                for item in relations
                if item["relation_id"] == relation_id
            )
            if block_id not in {
                relation["source"]["block_id"],
                relation["target"]["block_id"],
            }:
                _fail("managed_document_v2_table_relation_not_local")
        _require_refs(content["issues"], issue_ids, "table_issue")
        _require_refs(content["known_gap_ids"], loss_ids, "table_loss")

    _validate_source_word_ownership(
        payload["source_word_ownership"],
        anchor_ids=anchor_ids,
        anchor_by_id=anchor_by_id,
        issue_ids=issue_ids,
        table_by_id=table_by_id,
        entries_by_id=entries_by_id,
    )

    for issue in issues:
        _require_refs(issue["anchor_ids"], anchor_ids, "issue_anchor")
        _require_refs(issue["block_ids"], block_ids, "issue_block")
        _require_refs(
            issue["relation_ids"],
            relation_ids,
            "issue_relation",
        )
    for loss in losses:
        if loss["accounted"] is not True:
            _fail("managed_document_v2_loss_unaccounted")
        _require_refs(loss["anchor_ids"], anchor_ids, "loss_anchor")
        _require_refs(loss["block_ids"], block_ids, "loss_block")

    if evidence_ids != used_evidence_ids:
        _fail("managed_document_v2_orphan_geometry_evidence")
    _validate_quality(
        payload,
        metadata_fields=metadata_fields,
        table_by_id=table_by_id,
    )

    if payload["integrity_sha256"] != compute_document_integrity_sha256(
        payload
    ):
        _fail("managed_document_v2_integrity_invalid")


def _validate_table_content(
    *,
    block_id: str,
    content: dict[str, Any],
    anchor_ids: set[str],
    anchor_by_id: dict[str, dict[str, Any]],
    evidence_ids: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
    issue_ids: set[str],
    loss_ids: set[str],
    relation_ids: set[str] | None,
    document_row_ids: set[str],
    document_entry_ids: set[str],
    document_column_ids: set[str],
    document_source_part_ids: set[str],
    rows_by_id: dict[str, tuple[str, str, dict[str, Any]]],
    entries_by_id: dict[
        str,
        tuple[str, str, str, dict[str, Any]],
    ],
    used_evidence_ids: set[str],
    source_part_count: int,
) -> None:
    table_id = content["table_id"]
    rows = content["ordered_rows"]
    columns = content["logical_columns"]
    parts = content["source_parts"]

    if [item["ordinal"] for item in rows] != list(range(len(rows))):
        _fail("managed_document_v2_row_ordinal_invalid")
    if [item["ordinal"] for item in columns] != list(range(len(columns))):
        _fail("managed_document_v2_column_ordinal_invalid")
    if [item["ordinal"] for item in parts] != list(range(len(parts))):
        _fail("managed_document_v2_source_part_ordinal_invalid")

    table_row_ids: set[str] = set()
    table_entry_ids: set[str] = set()
    table_column_ids: set[str] = set()
    entry_row_role: dict[str, str] = {}
    table_entry_by_id: dict[str, dict[str, Any]] = {}
    entry_row_ordinal: dict[str, int] = {}
    row_by_id = {item["row_id"]: item for item in rows}

    for row in rows:
        row_id = row["row_id"]
        _claim_id(row_id, document_row_ids, "row")
        table_row_ids.add(row_id)
        rows_by_id[row_id] = (block_id, table_id, row)
        _require_refs(row["source_anchor_ids"], anchor_ids, "row_anchor")
        _require_refs(
            row["geometry_evidence_ids"],
            evidence_ids,
            "row_geometry",
        )
        _require_geometry_support(
            row["geometry_evidence_ids"],
            row["source_anchor_ids"],
            evidence_by_id,
            allowed_kinds={
                "TABLE_REGION",
                "ROW_BAND",
                "BASELINE",
                "INDENTATION",
                "HORIZONTAL_RULE",
            },
            label="row",
            allow_empty=True,
        )
        used_evidence_ids.update(row["geometry_evidence_ids"])
        _require_refs(row["issue_ids"], issue_ids, "row_issue")
        if row["role"] == LogicalRowRole.UNKNOWN and not row["issue_ids"]:
            _fail("managed_document_v2_unknown_row_issue_missing")
        if row["role_origin"] == "MODEL_PROPOSED":
            _fail("managed_document_v2_model_proposed_row_role_forbidden")
        if row["nesting_level"] is None and not row["issue_ids"]:
            _fail("managed_document_v2_unknown_nesting_issue_missing")
        if [item["ordinal"] for item in row["entries"]] != list(
            range(len(row["entries"]))
        ):
            _fail("managed_document_v2_entry_ordinal_invalid")
        for entry in row["entries"]:
            entry_id = entry["entry_id"]
            _claim_id(entry_id, document_entry_ids, "entry")
            table_entry_ids.add(entry_id)
            entries_by_id[entry_id] = (
                block_id,
                table_id,
                row_id,
                entry,
            )
            table_entry_by_id[entry_id] = entry
            entry_row_ordinal[entry_id] = row["ordinal"]
            entry_row_role[entry_id] = row["role"]
            _require_refs(
                entry["source_anchor_ids"],
                anchor_ids,
                "entry_anchor",
            )
            _require_refs(
                entry["geometry_evidence_ids"],
                evidence_ids,
                "entry_geometry",
            )
            _require_geometry_support(
                entry["geometry_evidence_ids"],
                entry["source_anchor_ids"],
                evidence_by_id,
                allowed_kinds={
                    "TABLE_REGION",
                    "ENTRY_REGION",
                    "COLUMN_ALIGNMENT",
                    "VISUAL_COVERAGE",
                    "HORIZONTAL_RULE",
                    "VERTICAL_RULE",
                },
                label="entry",
                allow_empty=True,
            )
            used_evidence_ids.update(entry["geometry_evidence_ids"])
            _require_refs(entry["issue_ids"], issue_ids, "entry_issue")
            if entry["origin"] == "MODEL_PROPOSED":
                _fail("managed_document_v2_model_proposed_entry_forbidden")
            if entry["text"] is None and (
                entry["kind"] != RowEntryKind.UNKNOWN
                or not entry["issue_ids"]
            ):
                _fail("managed_document_v2_null_entry_not_explicit_unknown")

    for row in rows:
        parent_id = row["parent_row_id"]
        nesting = row["nesting_level"]
        if parent_id is None:
            if nesting not in {0, None} and not row["issue_ids"]:
                _fail("managed_document_v2_unresolved_parent_issue_missing")
            continue
        if parent_id not in table_row_ids:
            _fail("managed_document_v2_parent_row_missing")
        parent = row_by_id[parent_id]
        if parent["ordinal"] >= row["ordinal"]:
            _fail("managed_document_v2_parent_row_order_invalid")
        if parent["role"] != LogicalRowRole.GROUP_HEADER:
            _fail("managed_document_v2_parent_row_role_invalid")
        parent_level = parent["nesting_level"]
        if (
            nesting is None
            or parent_level is None
            or nesting != parent_level + 1
        ):
            _fail("managed_document_v2_parent_nesting_invalid")

    for column in columns:
        column_id = column["column_id"]
        _claim_id(column_id, document_column_ids, "column")
        table_column_ids.add(column_id)
        _require_refs(
            column["header_path"],
            table_entry_ids,
            "column_header_entry",
        )
        for entry_id in column["header_path"]:
            if entry_row_role[entry_id] not in {
                LogicalRowRole.COLUMN_HEADER,
                LogicalRowRole.CONTINUATION_HEADER,
            }:
                _fail("managed_document_v2_header_path_role_invalid")
            header_entry = table_entry_by_id[entry_id]
            if not (
                header_entry["column_binding_status"]
                == ColumnBindingStatus.BOUND
                and (
                    header_entry["logical_column_id"] == column_id
                    or column_id
                    in header_entry["covers_logical_column_ids"]
                )
            ):
                _fail("managed_document_v2_header_path_binding_invalid")
        if [entry_row_ordinal[item] for item in column["header_path"]] != sorted(
            entry_row_ordinal[item] for item in column["header_path"]
        ):
            _fail("managed_document_v2_header_path_order_invalid")
        if not column["header_path"] and not column["issue_ids"]:
            _fail("managed_document_v2_header_path_issue_missing")
        _require_refs(
            column["source_anchor_ids"],
            anchor_ids,
            "column_anchor",
        )
        _require_refs(
            column["geometry_evidence_ids"],
            evidence_ids,
            "column_geometry",
        )
        _require_geometry_support(
            column["geometry_evidence_ids"],
            column["source_anchor_ids"],
            evidence_by_id,
            allowed_kinds={
                "TABLE_REGION",
                "COLUMN_ALIGNMENT",
                "VERTICAL_RULE",
                "VISUAL_COVERAGE",
            },
            label="column",
        )
        used_evidence_ids.update(column["geometry_evidence_ids"])
        _require_refs(column["issue_ids"], issue_ids, "column_issue")

    column_order = {
        column["column_id"]: column["ordinal"] for column in columns
    }
    for row in rows:
        for entry in row["entries"]:
            logical_column_id = entry["logical_column_id"]
            binding = entry["column_binding_status"]
            covers = entry["covers_logical_column_ids"]
            has_direct_binding = logical_column_id is not None
            has_coverage_binding = bool(covers)

            _require_refs(covers, table_column_ids, "entry_covered_column")
            if covers != sorted(covers, key=column_order.__getitem__):
                _fail("managed_document_v2_covered_column_order_invalid")
            if covers and len(covers) < 2:
                _fail("managed_document_v2_column_coverage_evidence_invalid")

            if binding == ColumnBindingStatus.BOUND:
                if not (has_direct_binding or has_coverage_binding):
                    _fail("managed_document_v2_bound_column_binding_missing")
                if (
                    has_direct_binding
                    and logical_column_id not in table_column_ids
                ):
                    _fail("managed_document_v2_bound_column_missing")
            else:
                if has_direct_binding:
                    _fail("managed_document_v2_unbound_column_present")
                if has_coverage_binding:
                    _fail(
                        "managed_document_v2_unbound_column_coverage_present"
                    )
            if (
                binding == ColumnBindingStatus.UNKNOWN
                and not entry["issue_ids"]
            ):
                _fail("managed_document_v2_unknown_column_issue_missing")
            if (
                row["role"]
                in {LogicalRowRole.SUBTOTAL, LogicalRowRole.TOTAL}
                and has_coverage_binding
                and logical_column_id != covers[0]
            ):
                _fail("managed_document_v2_summary_coverage_binding_invalid")
            if (
                has_direct_binding
                and has_coverage_binding
                and logical_column_id != covers[0]
            ):
                _fail(
                    "managed_document_v2_direct_column_not_leftmost_cover"
                )

            entry_anchor_ids = set(entry["source_anchor_ids"])
            if covers and not any(
                evidence_by_id[evidence_id]["kind"]
                in {"ENTRY_REGION", "VISUAL_COVERAGE", "COLUMN_ALIGNMENT"}
                and entry_anchor_ids
                & set(evidence_by_id[evidence_id]["source_anchor_ids"])
                for evidence_id in entry["geometry_evidence_ids"]
            ):
                _fail("managed_document_v2_column_coverage_evidence_invalid")

    row_ordinal = {item["row_id"]: item["ordinal"] for item in rows}
    expected_first = 0
    previous_page = 0
    for part in parts:
        _claim_id(
            part["source_part_id"],
            document_source_part_ids,
            "table_source_part",
        )
        if part["page"] > source_part_count:
            _fail("managed_document_v2_table_source_part_page_invalid")
        if part["region_anchor_id"] not in anchor_ids:
            _fail("managed_document_v2_table_source_part_anchor_missing")
        region_anchor = anchor_by_id[part["region_anchor_id"]]
        if (
            region_anchor["source_format"] == "PDF"
            and region_anchor["locator"]["page"] != part["page"]
        ):
            _fail("managed_document_v2_table_source_part_anchor_page_mismatch")
        first = row_ordinal.get(part["first_row_id"])
        last = row_ordinal.get(part["last_row_id"])
        if first is None or last is None or first > last:
            _fail("managed_document_v2_table_source_part_row_range_invalid")
        if first != expected_first:
            _fail("managed_document_v2_table_source_part_row_gap")
        expected_first = last + 1
        if part["page"] <= previous_page:
            _fail("managed_document_v2_table_source_part_page_order_invalid")
        previous_page = part["page"]
        _require_refs(
            part["geometry_evidence_ids"],
            evidence_ids,
            "source_part_geometry",
        )
        if not part["geometry_evidence_ids"] or any(
            evidence_by_id[evidence_id]["kind"] != "TABLE_REGION"
            or part["region_anchor_id"]
            not in evidence_by_id[evidence_id]["source_anchor_ids"]
            for evidence_id in part["geometry_evidence_ids"]
        ):
            _fail("managed_document_v2_source_part_geometry_invalid")
        _require_refs(
            part["continuation_evidence_ids"],
            evidence_ids,
            "source_part_continuation_geometry",
        )
        if any(
            evidence_by_id[evidence_id]["kind"] != "CONTINUATION"
            or part["region_anchor_id"]
            not in evidence_by_id[evidence_id]["source_anchor_ids"]
            for evidence_id in part["continuation_evidence_ids"]
        ):
            _fail("managed_document_v2_continuation_geometry_invalid")
        for row in rows[first : last + 1]:
            _require_pdf_anchor_page(
                row["source_anchor_ids"],
                page=part["page"],
                anchor_by_id=anchor_by_id,
                label="row_source_part",
            )
            for entry in row["entries"]:
                _require_pdf_anchor_page(
                    entry["source_anchor_ids"],
                    page=part["page"],
                    anchor_by_id=anchor_by_id,
                    label="entry_source_part",
                )
        used_evidence_ids.update(part["geometry_evidence_ids"])
        used_evidence_ids.update(part["continuation_evidence_ids"])
        _require_refs(part["issue_ids"], issue_ids, "source_part_issue")
    if expected_first != len(rows):
        _fail("managed_document_v2_table_source_part_tail_missing")

    statuses = [item["continuation_status"] for item in parts]
    if len(parts) == 1:
        if statuses != ["SINGLE"] or parts[0]["continuation_evidence_ids"]:
            _fail("managed_document_v2_single_part_continuation_invalid")
    else:
        expected_statuses = [
            "START",
            *(["CONTINUATION"] * (len(parts) - 2)),
            "END",
        ]
        if statuses != expected_statuses:
            _fail("managed_document_v2_continuation_status_invalid")
        if any(not item["continuation_evidence_ids"] for item in parts):
            _fail("managed_document_v2_continuation_evidence_missing")

    _require_refs(content["issues"], issue_ids, "table_issue")
    _require_refs(content["known_gap_ids"], loss_ids, "table_loss")
    if relation_ids is not None:
        _require_refs(content["relations"], relation_ids, "table_relation")

    local_unknown = any(
        row["role"] == LogicalRowRole.UNKNOWN
        or row["nesting_level"] is None
        or (
            row["parent_row_id"] is None
            and row["nesting_level"] not in {0, None}
        )
        or any(
            entry["column_binding_status"] == ColumnBindingStatus.UNKNOWN
            for entry in row["entries"]
        )
        for row in rows
    )
    if content["completeness_status"] == "COMPLETE" and (
        local_unknown or content["known_gap_ids"]
    ):
        _fail("managed_document_v2_complete_table_has_unknown_structure")


def _validate_source_word_ownership(
    ownership: list[dict[str, Any]],
    *,
    anchor_ids: set[str],
    anchor_by_id: dict[str, dict[str, Any]],
    issue_ids: set[str],
    table_by_id: dict[str, tuple[str, dict[str, Any]]],
    entries_by_id: dict[
        str,
        tuple[str, str, str, dict[str, Any]],
    ],
) -> None:
    word_ids = _unique_ids(
        ownership,
        "source_word_id",
        "source_word_ownership",
    )
    by_word = {item["source_word_id"]: item for item in ownership}
    owned_entries: set[str] = set()
    unresolved_tables: set[str] = set()
    source_anchor_ids: set[str] = set()
    bound_source_anchor_ids: set[str] = set()
    entry_ids_by_anchor: dict[str, set[str]] = {}
    for entry_id, (_, _, _, entry) in entries_by_id.items():
        for anchor_id in entry["source_anchor_ids"]:
            entry_ids_by_anchor.setdefault(str(anchor_id), set()).add(entry_id)
    for item in ownership:
        table_id = item["table_id"]
        if table_id not in table_by_id:
            _fail("managed_document_v2_word_owner_table_missing")
        if item["source_anchor_id"] not in anchor_ids:
            _fail("managed_document_v2_word_owner_anchor_missing")
        if item["source_anchor_id"] in source_anchor_ids:
            _fail("managed_document_v2_duplicate_source_word_anchor")
        source_anchor_ids.add(item["source_anchor_id"])
        word_anchor = anchor_by_id[item["source_anchor_id"]]
        locator = word_anchor["locator"]
        source_block_ref = locator.get("source_block_ref")
        bbox = locator.get("bbox")
        if (
            word_anchor["source_format"] != "PDF"
            or locator.get("kind") != "PDF"
            or not isinstance(source_block_ref, str)
            or not source_block_ref
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or bbox[2] < bbox[0]
            or bbox[3] < bbox[1]
        ):
            _fail("managed_document_v2_word_owner_pdf_locator_invalid")
        if item["source_word_id"] != _source_word_id(source_block_ref):
            _fail("managed_document_v2_word_owner_identity_mismatch")
        _require_refs(item["issue_ids"], issue_ids, "word_owner_issue")
        status = item["owner_status"]
        entry_id = item["owner_entry_id"]
        if status == "UNRESOLVED":
            if entry_ids_by_anchor.get(item["source_anchor_id"]):
                _fail(
                    "managed_document_v2_unresolved_word_anchor_entry_bound"
                )
            unresolved_tables.add(table_id)
            if not item["issue_ids"]:
                _fail("managed_document_v2_unresolved_word_issue_missing")
            continue
        if entry_id not in entries_by_id:
            _fail("managed_document_v2_word_owner_entry_missing")
        _, entry_table_id, _, entry = entries_by_id[entry_id]
        if entry_table_id != table_id:
            _fail("managed_document_v2_word_owner_cross_table")
        if item["source_anchor_id"] not in entry["source_anchor_ids"]:
            _fail("managed_document_v2_word_owner_anchor_not_entry_bound")
        if entry_ids_by_anchor[item["source_anchor_id"]] != {entry_id}:
            _fail("managed_document_v2_word_owner_anchor_multiple_entries")
        bound_source_anchor_ids.add(item["source_anchor_id"])
        if status == "OWNED":
            owned_entries.add(str(entry_id))
            continue
        duplicate_id = item["duplicate_of_source_word_id"]
        if duplicate_id == item["source_word_id"] or duplicate_id not in word_ids:
            _fail("managed_document_v2_duplicate_word_target_invalid")
        target = by_word[duplicate_id]
        if (
            target["owner_status"] != "OWNED"
            or target["table_id"] != table_id
            or target["owner_entry_id"] != entry_id
        ):
            _fail("managed_document_v2_duplicate_word_target_not_canonical")

    missing_entry_owners = set(entries_by_id) - owned_entries
    if missing_entry_owners:
        _fail("managed_document_v2_entry_without_owned_source_word")
    region_anchor_ids = {
        str(part["region_anchor_id"])
        for _block_id, table in table_by_id.values()
        for part in table["source_parts"]
    }
    entry_word_anchor_ids = set(entry_ids_by_anchor) - region_anchor_ids
    if entry_word_anchor_ids != bound_source_anchor_ids:
        _fail("managed_document_v2_entry_word_ownership_partition_invalid")
    for table_id in unresolved_tables:
        if table_by_id[table_id][1]["completeness_status"] != "BLOCKED":
            _fail("managed_document_v2_unresolved_word_table_not_blocked")


def _source_word_id(source_block_ref: str) -> str:
    canonical = json.dumps(
        [source_block_ref],
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()[:24]
    return f"source_word_{digest}"


def _validate_relation_endpoint(
    endpoint: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    rows_by_id: dict[str, tuple[str, str, dict[str, Any]]],
    entries_by_id: dict[
        str,
        tuple[str, str, str, dict[str, Any]],
    ],
) -> None:
    block_id = endpoint["block_id"]
    row_id = endpoint["row_id"]
    entry_id = endpoint["entry_id"]
    block = blocks_by_id.get(block_id)
    if block is None:
        _fail("managed_document_v2_relation_endpoint_missing")
    if entry_id is not None and row_id is None:
        _fail("managed_document_v2_relation_entry_without_row")
    if row_id is None:
        return
    row_owner = rows_by_id.get(row_id)
    if row_owner is None or row_owner[0] != block_id:
        _fail("managed_document_v2_relation_row_owner_invalid")
    if block["block_type"] != "TABLE":
        _fail("managed_document_v2_relation_row_target_not_table")
    if entry_id is not None:
        entry_owner = entries_by_id.get(entry_id)
        if (
            entry_owner is None
            or entry_owner[0] != block_id
            or entry_owner[2] != row_id
        ):
            _fail("managed_document_v2_relation_entry_owner_invalid")


def _validate_quality(
    payload: dict[str, Any],
    *,
    metadata_fields: list[dict[str, Any]],
    table_by_id: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    blocks = payload["blocks"]
    quality = payload["quality"]
    losses = quality["loss_ledger"]
    if quality["preserved_blocks_total"] != len(blocks):
        _fail("managed_document_v2_preserved_block_count_invalid")
    unknown_total = sum(
        item["block_type"] == "UNKNOWN" for item in blocks
    )
    if quality["unknown_blocks_total"] != unknown_total:
        _fail("managed_document_v2_unknown_block_count_invalid")
    if quality["known_losses_total"] != len(losses):
        _fail("managed_document_v2_known_loss_count_invalid")
    conflicts_total = sum(
        field["status"] == "CONFLICTING" for field in metadata_fields
    ) + sum(
        relation["status"] == "CONFLICTING"
        for relation in payload["relations"]
    )
    if quality["conflicts_total"] != conflicts_total:
        _fail("managed_document_v2_conflict_count_invalid")
    blocking_total = sum(
        item["blocks_semantic_analysis"] for item in losses
    )
    if quality["blocking_losses_total"] != blocking_total:
        _fail("managed_document_v2_blocking_loss_count_invalid")
    if quality["unaccounted_context_loss_total"] != 0:
        _fail("managed_document_v2_unaccounted_context_loss_forbidden")
    if quality["source_elements_total"] < len(blocks):
        _fail("managed_document_v2_source_element_count_invalid")

    status = quality["status"]
    incomplete_table = any(
        content["completeness_status"] != "COMPLETE"
        for _, content in table_by_id.values()
    )
    restoration_incomplete = any(
        item["restoration"]["status"] != "RESTORED" for item in blocks
    )
    incomplete = (
        unknown_total != 0
        or quality["unsupported_elements_total"] != 0
        or bool(losses)
        or conflicts_total != 0
        or restoration_incomplete
        or incomplete_table
    )
    if status == "COMPLETE" and (blocking_total or incomplete):
        _fail("managed_document_v2_complete_with_incomplete_context")
    if status == "BLOCKED" and blocking_total == 0:
        _fail("managed_document_v2_blocked_without_blocking_loss")
    if status == "PARTIAL" and blocking_total:
        _fail("managed_document_v2_partial_with_blocking_loss")
    if status == "PARTIAL" and not incomplete:
        _fail("managed_document_v2_partial_without_incomplete_context")


def _validate_anchor_part_range(
    anchor: dict[str, Any],
    part_count: int,
) -> None:
    locator = anchor["locator"]
    part_index = locator.get("source_part_index")
    if part_index is not None and not 1 <= part_index <= part_count:
        _fail("managed_document_v2_anchor_source_part_invalid")
    if locator["kind"] == "PDF" and locator["page"] > part_count:
        _fail("managed_document_v2_anchor_pdf_page_invalid")
    if locator["kind"] == "CSV" and (
        locator["row_start"] > locator["row_end"]
        or locator["column_start"] > locator["column_end"]
    ):
        _fail("managed_document_v2_anchor_csv_range_invalid")


def _validate_metadata_field(
    field: dict[str, Any],
    anchor_ids: set[str],
) -> None:
    _require_refs(
        field["evidence_anchor_ids"],
        anchor_ids,
        "metadata_anchor",
    )
    status = field["status"]
    value = field["value"]
    candidates = field["candidates"]
    if status == "PRESENT":
        if value is None or candidates:
            _fail("managed_document_v2_present_metadata_invalid")
    elif status == "CONFLICTING":
        if value is not None or len(candidates) < 2:
            _fail("managed_document_v2_conflicting_metadata_invalid")
    elif value is not None or candidates:
        _fail("managed_document_v2_nonpresent_metadata_invalid")
    if (
        field["origin"] == "SOURCE_EXPLICIT"
        and not field["evidence_anchor_ids"]
    ):
        _fail(
            "managed_document_v2_source_explicit_metadata_evidence_missing"
        )


def _unique_ids(
    items: list[dict[str, Any]],
    key: str,
    label: str,
) -> set[str]:
    values = [str(item[key]) for item in items]
    if len(values) != len(set(values)):
        _fail(f"managed_document_v2_duplicate_{label}_id")
    return set(values)


def _claim_id(value: str, claimed: set[str], label: str) -> None:
    if value in claimed:
        _fail(f"managed_document_v2_duplicate_{label}_id")
    claimed.add(value)


def _require_refs(
    values: list[str],
    allowed: set[str],
    label: str,
) -> None:
    if not set(values) <= allowed:
        _fail(f"managed_document_v2_{label}_ref_invalid")


def _require_geometry_support(
    geometry_ids: list[str],
    object_anchor_ids: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    allowed_kinds: set[str],
    label: str,
    allow_empty: bool = False,
) -> None:
    if not geometry_ids and allow_empty:
        return
    if not geometry_ids or any(
        evidence_by_id[item]["kind"] not in allowed_kinds
        for item in geometry_ids
    ):
        _fail(f"managed_document_v2_{label}_geometry_kind_invalid")
    object_anchors = set(object_anchor_ids)
    if not any(
        object_anchors & set(evidence_by_id[item]["source_anchor_ids"])
        for item in geometry_ids
    ):
        _fail(f"managed_document_v2_{label}_geometry_scope_invalid")


def _require_pdf_anchor_page(
    anchor_ids: list[str],
    *,
    page: int,
    anchor_by_id: dict[str, dict[str, Any]],
    label: str,
) -> None:
    for anchor_id in anchor_ids:
        anchor = anchor_by_id[anchor_id]
        if (
            anchor["source_format"] == "PDF"
            and anchor["locator"]["page"] != page
        ):
            _fail(f"managed_document_v2_{label}_page_mismatch")


def _fail(code: str) -> None:
    raise ManagedDocumentContractV2Error(code)
