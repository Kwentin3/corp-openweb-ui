from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from .managed_document_coverage import (
    PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION,
    require_private_contract,
    seal_private_contract,
    validate_parity_checklist,
)
from .managed_pdf_document import PdfSourceObservationAdapter, _identifier


PARITY_DIMENSIONS = (
    "SOURCE_IDENTITY",
    "PAGE_BOUNDARIES",
    "BLOCK_ORDER",
    "TEXT_CONTENT",
    "TEXT_SEQUENCE",
    "TABLE_REGIONS",
    "TABLE_POSITION",
    "TABLE_DETAILS",
    "VALIDATED_TABLES",
    "VALUE_SAMPLES",
    "VISUALS",
    "METADATA_DISCIPLINE",
    "PROVENANCE",
    "UNKNOWN_AND_LOSS_ACCOUNTING",
)


def build_pdf_only_checklist(content_bytes: bytes) -> dict[str, Any]:
    source_sha256 = hashlib.sha256(content_bytes).hexdigest()
    document_id = _identifier("document_pdf", source_sha256)
    observation = PdfSourceObservationAdapter().observe(
        content_bytes,
        document_id=document_id,
        source_checksum_sha256=source_sha256,
        private_source_ref=_identifier("private_pdf", source_sha256),
    )
    if observation["status"] == "BLOCKED":
        checklist = seal_private_contract(
            {
                "schema_version": PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION,
                "pass": "PDF_ONLY",
                "review_isolation": "PDF bytes and parser outputs only; no Managed Document artifact read",
                "document_id": document_id,
                "source_checksum_sha256": source_sha256,
                "terminal_status": "BLOCKED",
                "reason_codes": observation["reason_codes"],
                "summary": {
                    "page_boundaries_total": 0,
                    "block_order_tokens": [],
                    "structure_items": [],
                    "source_content_token_multiset_sha256": _token_hash([]),
                    "source_content_sequence_sha256": _token_sequence_hash([]),
                    "tables": [],
                    "value_sample_policy": "NOT_APPLICABLE",
                    "value_samples": [],
                    "table_regions_total": 0,
                    "validated_tables_total": 0,
                    "visuals_total": 0,
                    "metadata_expected_unknown": True,
                    "known_losses_expected_total": 0,
                },
            }
        )
        require_private_contract(validate_parity_checklist(checklist))
        return checklist

    order_tokens: list[str] = []
    structure_items: list[dict[str, Any]] = []
    content_items: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    table_regions_total = 0
    validated_tables_total = 0
    visuals_total = 0
    known_losses_expected_total = 0
    for page in observation["pages"]:
        page_number = page["page_number"]
        _add_structure_item(
            order_tokens,
            structure_items,
            f"{page_number}:PAGE",
            {"page": page_number, "source_page_ref": page["page_ref"]},
        )
        candidate_by_word: dict[str, dict[str, Any]] = {}
        table_item_by_ref: dict[str, dict[str, Any]] = {}
        word_by_ref = {item["word_ref"]: item for item in page["words"]}
        for candidate in page["table_candidates"]:
            table_regions_total += 1
            validated = _pdf_candidate_is_logically_valid(candidate)
            if validated:
                validated_tables_total += 1
            else:
                known_losses_expected_total += 1
            for word_ref in candidate["contributing_word_refs"]:
                candidate_by_word[word_ref] = candidate
            rows = candidate.get("row_inventory") or []
            cells = candidate.get("cell_inventory") or []
            columns_total = max(
                (int(item.get("column_ordinal") or 0) for item in cells),
                default=0,
            )
            table_item = {
                "table_sequence_ordinal": len(tables),
                "position_ordinal": None,
                "page": page_number,
                "representation": "TABLE" if validated else "UNKNOWN",
                "rows_total": len(rows) if validated else None,
                "columns_total": columns_total if validated else None,
                "empty_cells_total": (
                    sum(not (item.get("word_refs") or []) for item in cells)
                    if validated
                    else None
                ),
                "unreadable_cells_total": 0 if validated else None,
                "title_status": "UNKNOWN",
                "header_hierarchy_status": "UNKNOWN",
                "row_groups_status": "UNKNOWN",
                "totals_status": "NOT_CLASSIFIED",
                "units_status": "UNKNOWN",
                "footnotes_status": "UNKNOWN",
                "continuation_status": "UNKNOWN",
                "content_sequence_sha256": _token_sequence_hash(
                    [
                        str(item["text"])
                        for item in _pdf_candidate_ordered_words(
                            candidate,
                            validated=validated,
                            word_by_ref=word_by_ref,
                        )
                    ]
                ),
                "source_pointer": {
                    "page": page_number,
                    "table_region_ref": candidate["table_candidate_ref"],
                    "visible_source_word_refs": candidate["contributing_word_refs"],
                },
            }
            tables.append(table_item)
            table_item_by_ref[candidate["table_candidate_ref"]] = table_item
        emitted: set[str] = set()
        line_by_ref = {item["line_ref"]: item for item in page["text_lines"]}
        for block in page["text_blocks"]:
            pending_text = False
            for line_ref in block["line_refs"]:
                line = line_by_ref[line_ref]
                for word_ref in line["word_refs"]:
                    candidate = candidate_by_word.get(word_ref)
                    if candidate is None:
                        pending_text = True
                        word = word_by_ref[word_ref]
                        content_items.append(
                            {
                                "value": str(word["text"]),
                                "source_pointer": {
                                    "page": page_number,
                                    "visible_source_word_ref": word_ref,
                                    "table_region_ref": None,
                                },
                            }
                        )
                        continue
                    if pending_text:
                        _add_structure_item(
                            order_tokens,
                            structure_items,
                            f"{page_number}:TEXT",
                            {"page": page_number, "source_line_ref": line_ref},
                        )
                        pending_text = False
                    candidate_ref = candidate["table_candidate_ref"]
                    if candidate_ref not in emitted:
                        _add_structure_item(
                            order_tokens,
                            structure_items,
                            f"{page_number}:TABLE_REGION",
                            {
                                "page": page_number,
                                "table_region_ref": candidate_ref,
                            },
                        )
                        table_item_by_ref[candidate_ref]["position_ordinal"] = (
                            len(order_tokens) - 1
                        )
                        for table_word in _pdf_candidate_ordered_words(
                            candidate,
                            validated=_pdf_candidate_is_logically_valid(candidate),
                            word_by_ref=word_by_ref,
                        ):
                            content_items.append(
                                {
                                    "value": str(table_word["text"]),
                                    "source_pointer": {
                                        "page": page_number,
                                        "visible_source_word_ref": table_word[
                                            "word_ref"
                                        ],
                                        "table_region_ref": candidate_ref,
                                    },
                                }
                            )
                        emitted.add(candidate_ref)
            if pending_text:
                _add_structure_item(
                    order_tokens,
                    structure_items,
                    f"{page_number}:TEXT",
                    {"page": page_number, "source_block_ref": block["source_block_ref"]},
                )
        for candidate in page["table_candidates"]:
            if candidate["table_candidate_ref"] not in emitted:
                _add_structure_item(
                    order_tokens,
                    structure_items,
                    f"{page_number}:TABLE_REGION",
                    {
                        "page": page_number,
                        "table_region_ref": candidate["table_candidate_ref"],
                    },
                )
                table_item_by_ref[candidate["table_candidate_ref"]][
                    "position_ordinal"
                ] = len(order_tokens) - 1
                for table_word in _pdf_candidate_ordered_words(
                    candidate,
                    validated=_pdf_candidate_is_logically_valid(candidate),
                    word_by_ref=word_by_ref,
                ):
                    content_items.append(
                        {
                            "value": str(table_word["text"]),
                            "source_pointer": {
                                "page": page_number,
                                "visible_source_word_ref": table_word["word_ref"],
                                "table_region_ref": candidate[
                                    "table_candidate_ref"
                                ],
                            },
                        }
                    )
        if page["image_objects_total"]:
            visuals_total += 1
            known_losses_expected_total += 2
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page_number}:VISUAL",
                {"page": page_number, "source_page_ref": page["page_ref"]},
            )
    content_tokens = [item["value"] for item in content_items]
    all_values = len(observation["pages"]) == 1
    checklist = seal_private_contract(
        {
            "schema_version": PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION,
            "pass": "PDF_ONLY",
            "review_isolation": "PDF bytes and parser outputs only; no Managed Document artifact read",
            "document_id": document_id,
            "source_checksum_sha256": source_sha256,
            "terminal_status": "READY",
            "reason_codes": observation.get("reason_codes", []),
            "summary": {
                "page_boundaries_total": len(observation["pages"]),
                "block_order_tokens": order_tokens,
                "structure_items": structure_items,
                "source_content_token_multiset_sha256": _token_hash(content_tokens),
                "source_content_sequence_sha256": _token_sequence_hash(content_tokens),
                "tables": tables,
                "value_sample_policy": (
                    "ALL_VALUES" if all_values else "DETERMINISTIC_20"
                ),
                "value_samples": _bounded_value_samples(
                    content_items, all_values=all_values
                ),
                "table_regions_total": table_regions_total,
                "validated_tables_total": validated_tables_total,
                "visuals_total": visuals_total,
                "metadata_expected_unknown": True,
                "known_losses_expected_total": known_losses_expected_total,
            },
        }
    )
    require_private_contract(validate_parity_checklist(checklist))
    return checklist


def build_artifact_only_checklist(managed_document: dict[str, Any]) -> dict[str, Any]:
    document_id = str(managed_document.get("document_id") or "")
    source = managed_document.get("source") or {}
    source_sha256 = str(source.get("checksum_sha256") or "")
    anchors = {
        str(item.get("anchor_id") or ""): item
        for item in managed_document.get("anchors") or []
        if isinstance(item, dict)
    }
    order_tokens = []
    structure_items: list[dict[str, Any]] = []
    content_items: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    table_regions_total = 0
    validated_tables_total = 0
    visuals_total = 0
    provenance_valid = True
    for block in managed_document.get("blocks") or []:
        anchor = anchors.get(next(iter(block.get("source_anchor_ids") or []), ""), {})
        locator = (
            anchor.get("locator") if isinstance(anchor.get("locator"), dict) else {}
        )
        page = int(locator.get("page") or locator.get("source_part_index") or 0)
        if anchor.get("checksum_sha256") != source_sha256 or page <= 0:
            provenance_valid = False
        block_type = block.get("block_type")
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        base_pointer = {
            "page": page,
            "block_id": block.get("block_id"),
            "anchor_ids": list(block.get("source_anchor_ids") or []),
        }
        if block_type == "BOUNDARY":
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:PAGE",
                base_pointer,
            )
        elif block_type == "PARAGRAPH":
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:TEXT",
                base_pointer,
            )
            _append_content_items(
                content_items,
                str(content.get("raw_text") or ""),
                base_pointer,
            )
        elif block_type == "TABLE":
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:TABLE_REGION",
                {**base_pointer, "table_id": content.get("table_id")},
            )
            table_regions_total += 1
            validated_tables_total += 1
            rows = content.get("rows") or []
            table_values = []
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    if value is not None:
                        table_values.append(str(value))
                        _append_content_items(
                            content_items,
                            str(value),
                            {
                                **base_pointer,
                                "table_id": content.get("table_id"),
                                "row_index": row_index,
                                "column_index": column_index,
                            },
                        )
            tables.append(
                {
                    "table_sequence_ordinal": len(tables),
                    "position_ordinal": len(order_tokens) - 1,
                    "page": page,
                    "representation": "TABLE",
                    "rows_total": len(rows),
                    "columns_total": max((len(row) for row in rows), default=0),
                    "empty_cells_total": sum(
                        value is None for row in rows for value in row
                    ),
                    "unreadable_cells_total": 0,
                    "title_status": str(
                        (content.get("title") or {}).get("status") or "UNKNOWN"
                    ),
                    "header_hierarchy_status": str(
                        (content.get("header_hierarchy") or {}).get("status")
                        or "UNKNOWN"
                    ),
                    "row_groups_status": str(
                        (content.get("row_groups") or {}).get("status") or "UNKNOWN"
                    ),
                    "totals_status": "NOT_CLASSIFIED",
                    "units_status": "UNKNOWN" if not content.get("units") else "PRESENT",
                    "footnotes_status": "UNKNOWN",
                    "continuation_status": (
                        "UNKNOWN"
                        if not content.get("continuation_relation_ids")
                        else "PRESENT"
                    ),
                    "content_sequence_sha256": _token_sequence_hash(table_values),
                    "source_pointer": {
                        **base_pointer,
                        "table_id": content.get("table_id"),
                        "row_index_bounds": [0, max(len(rows) - 1, 0)],
                        "column_index_bounds": [
                            0,
                            max((len(row) for row in rows), default=1) - 1,
                        ],
                    },
                }
            )
        elif (
            block_type == "UNKNOWN"
            and "table region" in str(content.get("reason") or "").lower()
        ):
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:TABLE_REGION",
                base_pointer,
            )
            table_regions_total += 1
            raw_text = str(content.get("raw_text") or "")
            _append_content_items(content_items, raw_text, base_pointer)
            tables.append(
                {
                    "table_sequence_ordinal": len(tables),
                    "position_ordinal": len(order_tokens) - 1,
                    "page": page,
                    "representation": "UNKNOWN",
                    "rows_total": None,
                    "columns_total": None,
                    "empty_cells_total": None,
                    "unreadable_cells_total": None,
                    "title_status": "UNKNOWN",
                    "header_hierarchy_status": "UNKNOWN",
                    "row_groups_status": "UNKNOWN",
                    "totals_status": "NOT_CLASSIFIED",
                    "units_status": "UNKNOWN",
                    "footnotes_status": "UNKNOWN",
                    "continuation_status": "UNKNOWN",
                    "content_sequence_sha256": _token_sequence_hash([raw_text]),
                    "source_pointer": {**base_pointer, "table_id": None},
                }
            )
        elif block_type == "VISUAL":
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:VISUAL",
                base_pointer,
            )
            visuals_total += 1
        else:
            _add_structure_item(
                order_tokens,
                structure_items,
                f"{page}:{block_type or 'UNKNOWN'}",
                base_pointer,
            )
            if content.get("raw_text"):
                _append_content_items(
                    content_items,
                    str(content["raw_text"]),
                    base_pointer,
                )
    content_tokens = [item["value"] for item in content_items]
    metadata = managed_document.get("metadata") or {}
    metadata_all_unknown = (
        all(
            isinstance(value, dict) and value.get("status") == "UNKNOWN"
            for key, value in metadata.items()
            if key != "additional"
        )
        and metadata.get("additional") == []
    )
    quality = managed_document.get("quality") or {}
    checklist = seal_private_contract(
        {
            "schema_version": PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION,
            "pass": "ARTIFACT_ONLY",
            "review_isolation": (
                "Managed Document JSON only; no PDF bytes or PDF-only checklist read"
            ),
            "document_id": document_id,
            "source_checksum_sha256": source_sha256,
            "terminal_status": quality.get("status"),
            "reason_codes": [],
            "summary": {
                "page_boundaries_total": sum(
                    item.get("block_type") == "BOUNDARY"
                    for item in managed_document.get("blocks") or []
                ),
                "block_order_tokens": order_tokens,
                "structure_items": structure_items,
                "source_content_token_multiset_sha256": _token_hash(content_tokens),
                "source_content_sequence_sha256": _token_sequence_hash(content_tokens),
                "tables": tables,
                "value_sample_policy": (
                    "ALL_VALUES"
                    if sum(
                        item.get("block_type") == "BOUNDARY"
                        for item in managed_document.get("blocks") or []
                    )
                    == 1
                    else "DETERMINISTIC_20"
                ),
                "value_samples": _bounded_value_samples(
                    content_items,
                    all_values=(
                        sum(
                            item.get("block_type") == "BOUNDARY"
                            for item in managed_document.get("blocks") or []
                        )
                        == 1
                    ),
                ),
                "table_regions_total": table_regions_total,
                "validated_tables_total": validated_tables_total,
                "visuals_total": visuals_total,
                "metadata_expected_unknown": metadata_all_unknown,
                "known_losses_expected_total": int(
                    quality.get("known_losses_total") or 0
                ),
                "provenance_valid": provenance_valid,
                "unaccounted_context_loss_total": int(
                    quality.get("unaccounted_context_loss_total") or 0
                ),
            },
        }
    )
    require_private_contract(validate_parity_checklist(checklist))
    return checklist


def compare_parity_checklists(
    pdf_checklist: dict[str, Any], artifact_checklist: dict[str, Any]
) -> dict[str, Any]:
    require_private_contract(validate_parity_checklist(pdf_checklist))
    require_private_contract(validate_parity_checklist(artifact_checklist))
    if pdf_checklist.get("pass") != "PDF_ONLY":
        raise ValueError("managed_document_parity_pdf_pass_required")
    if artifact_checklist.get("pass") != "ARTIFACT_ONLY":
        raise ValueError("managed_document_parity_artifact_pass_required")
    pdf_summary = pdf_checklist["summary"]
    artifact_summary = artifact_checklist["summary"]
    dimensions = []

    def compare(
        name: str,
        left: Any,
        right: Any,
        *,
        mismatch_status: str = "WRONG_VALUE",
        critical: bool = True,
        critical_category: str | None = "SOURCE_VALUES_CHANGED",
    ) -> None:
        dimensions.append(
            {
                "dimension": name,
                "status": "MATCH" if left == right else mismatch_status,
                "critical_if_mismatch": critical,
                "critical_category": (
                    None if left == right or not critical else critical_category
                ),
                "pdf_value_sha256": _value_hash(left),
                "artifact_value_sha256": _value_hash(right),
            }
        )

    compare(
        "SOURCE_IDENTITY",
        [pdf_checklist["document_id"], pdf_checklist["source_checksum_sha256"]],
        [
            artifact_checklist["document_id"],
            artifact_checklist["source_checksum_sha256"],
        ],
        critical_category="WRONG_SOURCE_ANCHOR",
    )
    compare(
        "PAGE_BOUNDARIES",
        pdf_summary["page_boundaries_total"],
        artifact_summary["page_boundaries_total"],
        mismatch_status=(
            "MISSING_IN_ARTIFACT"
            if pdf_summary["page_boundaries_total"]
            > artifact_summary["page_boundaries_total"]
            else "EXTRA_IN_ARTIFACT"
        ),
        critical_category="MISSING_DOCUMENT_BLOCK",
    )
    compare(
        "BLOCK_ORDER",
        pdf_summary["block_order_tokens"],
        artifact_summary["block_order_tokens"],
        mismatch_status="WRONG_ORDER",
        critical_category="WRONG_BLOCK_ORDER",
    )
    compare(
        "TEXT_CONTENT",
        pdf_summary["source_content_token_multiset_sha256"],
        artifact_summary["source_content_token_multiset_sha256"],
        critical_category="SOURCE_VALUES_CHANGED",
    )
    compare(
        "TEXT_SEQUENCE",
        pdf_summary["source_content_sequence_sha256"],
        artifact_summary["source_content_sequence_sha256"],
        mismatch_status="WRONG_ORDER",
        critical_category="WRONG_BLOCK_ORDER",
    )
    compare(
        "TABLE_REGIONS",
        pdf_summary["table_regions_total"],
        artifact_summary["table_regions_total"],
        mismatch_status=(
            "MISSING_IN_ARTIFACT"
            if pdf_summary["table_regions_total"]
            > artifact_summary["table_regions_total"]
            else "EXTRA_IN_ARTIFACT"
        ),
        critical_category="MISSING_TABLE",
    )
    compare(
        "TABLE_POSITION",
        _table_positions(pdf_summary["tables"]),
        _table_positions(artifact_summary["tables"]),
        mismatch_status="WRONG_ORDER",
        critical_category="WRONG_TABLE_POSITION",
    )
    compare(
        "TABLE_DETAILS",
        _table_signatures(pdf_summary["tables"]),
        _table_signatures(artifact_summary["tables"]),
        critical_category="WRONG_TABLE_VALUE",
    )
    compare(
        "VALIDATED_TABLES",
        pdf_summary["validated_tables_total"],
        artifact_summary["validated_tables_total"],
        critical_category="MISSING_TABLE",
    )
    compare(
        "VALUE_SAMPLES",
        _sample_signatures(pdf_summary["value_samples"]),
        _sample_signatures(artifact_summary["value_samples"]),
        critical_category="SOURCE_VALUES_CHANGED",
    )
    compare(
        "VISUALS",
        pdf_summary["visuals_total"],
        artifact_summary["visuals_total"],
        critical_category="MISSING_DOCUMENT_BLOCK",
    )
    compare(
        "METADATA_DISCIPLINE",
        pdf_summary["metadata_expected_unknown"],
        artifact_summary["metadata_expected_unknown"],
        mismatch_status="PARTIAL_MATCH",
        critical=False,
        critical_category=None,
    )
    compare(
        "PROVENANCE",
        True,
        artifact_summary.get("provenance_valid"),
        mismatch_status="WRONG_RELATION",
        critical=True,
        critical_category="WRONG_SOURCE_ANCHOR",
    )
    compare(
        "UNKNOWN_AND_LOSS_ACCOUNTING",
        [pdf_summary["known_losses_expected_total"], 0],
        [
            artifact_summary["known_losses_expected_total"],
            artifact_summary.get("unaccounted_context_loss_total"),
        ],
        mismatch_status="WRONG_RELATION",
        critical_category="MISSING_BLOCKING_LOSS",
    )
    critical_total = sum(
        item["status"] != "MATCH" and item["critical_if_mismatch"]
        for item in dimensions
    )
    noncritical_total = sum(
        item["status"] != "MATCH" and not item["critical_if_mismatch"]
        for item in dimensions
    )
    comparison = seal_private_contract(
        {
            "schema_version": PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION,
            "pass": "COMPARISON",
            "review_isolation": (
                "Sealed PDF-only and artifact-only checklists only; no source payload read"
            ),
            "document_id": pdf_checklist["document_id"],
            "source_checksum_sha256": pdf_checklist["source_checksum_sha256"],
            "terminal_status": (
                "MATCH"
                if not critical_total and not noncritical_total
                else "MISMATCH"
            ),
            "dimensions": dimensions,
            "critical_mismatches_total": critical_total,
            "noncritical_mismatches_total": noncritical_total,
            "full_parity": not critical_total and not noncritical_total,
        }
    )
    require_private_contract(validate_parity_checklist(comparison))
    return comparison


def _add_structure_item(
    order_tokens: list[str],
    structure_items: list[dict[str, Any]],
    token: str,
    source_pointer: dict[str, Any],
) -> None:
    order_tokens.append(token)
    structure_items.append(
        {
            "structure_ordinal": len(order_tokens) - 1,
            "token": token,
            "source_pointer": source_pointer,
        }
    )


def _append_content_items(
    target: list[dict[str, Any]], value: str, source_pointer: dict[str, Any]
) -> None:
    for token_ordinal, token in enumerate(_tokens(value)):
        target.append(
            {
                "value": token,
                "source_pointer": {
                    **source_pointer,
                    "token_ordinal": token_ordinal,
                },
            }
        )


def _bounded_value_samples(
    content_items: list[dict[str, Any]], *, all_values: bool
) -> list[dict[str, Any]]:
    expanded = [
        {"value": token, "source_pointer": item["source_pointer"]}
        for item in content_items
        for token in _tokens(str(item["value"]))
    ]
    if all_values or len(expanded) <= 20:
        indices = list(range(len(expanded)))
    else:
        indices = sorted({round(index * (len(expanded) - 1) / 19) for index in range(20)})
    return [
        {
            "sequence_index": index,
            "value_sha256": _value_hash(expanded[index]["value"]),
            "source_pointer": expanded[index]["source_pointer"],
        }
        for index in indices
    ]


def _table_positions(tables: list[dict[str, Any]]) -> list[list[int]]:
    return [
        [int(item["page"]), int(item["position_ordinal"])] for item in tables
    ]


def _table_signatures(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in item.items() if key != "source_pointer"}
        for item in tables
    ]


def _sample_signatures(samples: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [item["sequence_index"], item["value_sha256"]] for item in samples
    ]


def _pdf_candidate_ordered_words(
    candidate: dict[str, Any],
    *,
    validated: bool,
    word_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if validated:
        refs = [
            ref
            for cell in sorted(
                candidate.get("cell_inventory") or [],
                key=lambda item: (
                    int(item.get("row_ordinal") or 0),
                    int(item.get("column_ordinal") or 0),
                ),
            )
            for ref in cell.get("word_refs") or []
        ]
    else:
        refs = list(candidate.get("contributing_word_refs") or [])
    return [word_by_ref[ref] for ref in refs]


def _pdf_candidate_is_logically_valid(candidate: dict[str, Any]) -> bool:
    rows = candidate.get("row_inventory") or []
    cells = candidate.get("cell_inventory") or []
    counts = Counter(int(item.get("row_ordinal") or 0) for item in cells)
    owned = [ref for cell in cells for ref in cell.get("word_refs") or []]
    contributing = list(candidate.get("contributing_word_refs") or [])
    expected_columns = max(counts.values(), default=0)
    aligned_rows = sum(value == expected_columns for value in counts.values())
    row_alignment = aligned_rows / len(counts) if counts else 0.0
    return bool(
        float(candidate.get("geometry_confidence") or 0.0) >= 0.90
        and candidate.get("table_strategy_ref")
        in {
            "ruled_lines_v0",
            "aligned_text_v0",
            "mixed_geometry_v0",
            "repeated_x_columns_v0",
        }
        and len(rows) >= 2
        and len(cells) >= 4
        and counts
        and min(counts.values()) >= 2
        and len(owned) == len(set(owned))
        and set(owned) == set(contributing)
        and all(cell.get("bbox_ref") for cell in cells)
        and row_alignment >= 0.75
    )


def _tokens(value: str) -> list[str]:
    return [item for item in value.split() if item]


def _token_hash(values: list[str]) -> str:
    tokens = [token for value in values for token in _tokens(str(value))]
    return _value_hash(sorted(tokens))


def _token_sequence_hash(values: list[str]) -> str:
    tokens = [token for value in values for token in _tokens(str(value))]
    return _value_hash(tokens)


def _value_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
