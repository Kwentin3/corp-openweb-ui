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
    "TABLE_REGIONS",
    "VALIDATED_TABLES",
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
                    "source_content_token_multiset_sha256": _token_hash([]),
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
    content_tokens: list[str] = []
    table_regions_total = 0
    validated_tables_total = 0
    visuals_total = 0
    known_losses_expected_total = 0
    for page in observation["pages"]:
        page_number = page["page_number"]
        order_tokens.append(f"{page_number}:PAGE")
        content_tokens.extend(str(item["text"]) for item in page["words"])
        candidate_by_word: dict[str, dict[str, Any]] = {}
        for candidate in page["table_candidates"]:
            table_regions_total += 1
            if _pdf_candidate_is_logically_valid(candidate):
                validated_tables_total += 1
            else:
                known_losses_expected_total += 1
            for word_ref in candidate["contributing_word_refs"]:
                candidate_by_word[word_ref] = candidate
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
                        continue
                    if pending_text:
                        order_tokens.append(f"{page_number}:TEXT")
                        pending_text = False
                    candidate_ref = candidate["table_candidate_ref"]
                    if candidate_ref not in emitted:
                        order_tokens.append(f"{page_number}:TABLE_REGION")
                        emitted.add(candidate_ref)
            if pending_text:
                order_tokens.append(f"{page_number}:TEXT")
        for candidate in page["table_candidates"]:
            if candidate["table_candidate_ref"] not in emitted:
                order_tokens.append(f"{page_number}:TABLE_REGION")
        if page["image_objects_total"]:
            visuals_total += 1
            known_losses_expected_total += 2
            order_tokens.append(f"{page_number}:VISUAL")
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
                "source_content_token_multiset_sha256": _token_hash(content_tokens),
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
    content_tokens = []
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
        if block_type == "BOUNDARY":
            order_tokens.append(f"{page}:PAGE")
        elif block_type == "PARAGRAPH":
            order_tokens.append(f"{page}:TEXT")
            content_tokens.extend(_tokens(str(content.get("raw_text") or "")))
        elif block_type == "TABLE":
            order_tokens.append(f"{page}:TABLE_REGION")
            table_regions_total += 1
            validated_tables_total += 1
            for row in content.get("rows") or []:
                for value in row:
                    if value is not None:
                        content_tokens.extend(_tokens(str(value)))
        elif (
            block_type == "UNKNOWN"
            and "table region" in str(content.get("reason") or "").lower()
        ):
            order_tokens.append(f"{page}:TABLE_REGION")
            table_regions_total += 1
            content_tokens.extend(_tokens(str(content.get("raw_text") or "")))
        elif block_type == "VISUAL":
            order_tokens.append(f"{page}:VISUAL")
            visuals_total += 1
        else:
            order_tokens.append(f"{page}:{block_type or 'UNKNOWN'}")
            if content.get("raw_text"):
                content_tokens.extend(_tokens(str(content["raw_text"])))
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
                "source_content_token_multiset_sha256": _token_hash(content_tokens),
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

    def compare(name: str, left: Any, right: Any, *, critical: bool = True) -> None:
        dimensions.append(
            {
                "dimension": name,
                "status": (
                    "MATCH"
                    if left == right
                    else ("CRITICAL_MISMATCH" if critical else "NONCRITICAL_MISMATCH")
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
    )
    compare(
        "PAGE_BOUNDARIES",
        pdf_summary["page_boundaries_total"],
        artifact_summary["page_boundaries_total"],
    )
    compare(
        "BLOCK_ORDER",
        pdf_summary["block_order_tokens"],
        artifact_summary["block_order_tokens"],
    )
    compare(
        "TEXT_CONTENT",
        pdf_summary["source_content_token_multiset_sha256"],
        artifact_summary["source_content_token_multiset_sha256"],
    )
    compare(
        "TABLE_REGIONS",
        pdf_summary["table_regions_total"],
        artifact_summary["table_regions_total"],
    )
    compare(
        "VALIDATED_TABLES",
        pdf_summary["validated_tables_total"],
        artifact_summary["validated_tables_total"],
    )
    compare(
        "VISUALS",
        pdf_summary["visuals_total"],
        artifact_summary["visuals_total"],
    )
    compare(
        "METADATA_DISCIPLINE",
        pdf_summary["metadata_expected_unknown"],
        artifact_summary["metadata_expected_unknown"],
        critical=False,
    )
    compare("PROVENANCE", True, artifact_summary.get("provenance_valid"), critical=True)
    compare(
        "UNKNOWN_AND_LOSS_ACCOUNTING",
        [pdf_summary["known_losses_expected_total"], 0],
        [
            artifact_summary["known_losses_expected_total"],
            artifact_summary.get("unaccounted_context_loss_total"),
        ],
    )
    critical_total = sum(item["status"] == "CRITICAL_MISMATCH" for item in dimensions)
    noncritical_total = sum(
        item["status"] == "NONCRITICAL_MISMATCH" for item in dimensions
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
            "terminal_status": "MATCH" if not critical_total else "CRITICAL_MISMATCH",
            "dimensions": dimensions,
            "critical_mismatches_total": critical_total,
            "noncritical_mismatches_total": noncritical_total,
            "full_parity": not critical_total and not noncritical_total,
        }
    )
    require_private_contract(validate_parity_checklist(comparison))
    return comparison


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


def _value_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
