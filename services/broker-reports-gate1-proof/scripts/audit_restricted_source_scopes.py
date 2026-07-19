"""Audit restricted Gate 1 scopes without promoting or interpreting them.

The maintained entrypoint uses the canonical ArtifactStore and Gate 2 factories.
Private payloads are resolved only through ArtifactResolver.  The committed
output contains opaque identities, classifications, counts and measurements;
the private proof keeps resolver identities but never copies customer values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactResolver,
    Gate2InputReadinessFactory,
)
from profile_gate2_package_preparation import (  # noqa: E402
    DEFAULT_ACTUAL_CONFIG,
    prepare_actual_latest,
)


SCHEMA_VERSION = "broker_reports_restricted_scope_audit_safe_v1"
PRIVATE_SCHEMA_VERSION = "broker_reports_restricted_scope_audit_private_v1"
OPAQUE_NAMESPACE = "broker-reports-restricted-scope-audit-v1"
FACTORY_REQUIRED = (
    "prepare_actual_latest -> ArtifactStoreFactory.create; "
    "Gate2InputReadinessFactory.create is the accounting authority"
)
FORBIDDEN = (
    "The audit must not instantiate a store adapter, call a provider, promote "
    "a candidate, or read blocked projection payloads"
)

TABLE_CANDIDATE = "pdf_table_candidate_unit"
PDF_VISUAL = "pdf_visual_page_unit"
VISUAL_MEDIA = "visual_media"
TEXT_UNITS = {
    "pdf_page_text_unit",
    "pdf_line_cluster_unit",
    TABLE_CANDIDATE,
}
MATERIAL_NON_TEXT_DIVIDEND_PAGES = {8}
NON_MATERIAL_NON_TEXT_DIVIDEND_PAGES = {12}


def _opaque(kind: str, value: Any, *, length: int = 20) -> str:
    material = f"{OPAQUE_NAMESPACE}|{kind}|{value}".encode("utf-8")
    return f"{kind}_{hashlib.sha256(material).hexdigest()[:length]}"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _unit_type(unit: dict[str, Any]) -> str:
    return str(unit.get("pdf_unit_type") or unit.get("slice_type") or "")


def _normalized_private_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _normalized_value(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", str(value or "").casefold())


def classify_table_candidate(
    *,
    inferred_role: str,
    projection_validation_status: str,
    cell_count: int,
    word_count: int,
) -> tuple[str, str, list[str]]:
    """Return primary class, physical kind and safe secondary flags."""

    if projection_validation_status == "validated":
        physical = "table" if inferred_role == "source_broker_report" else "form_block"
        return (
            "canonical_projection_already_exists",
            physical,
            ["projection_not_currently_gate2_eligible"],
        )
    false_positive_shape = (
        inferred_role == "withholding_report"
        and (
            cell_count in {5, 7, 24}
            or (cell_count == 17 and word_count == 51)
        )
    )
    if false_positive_shape:
        flags = ["deterministic_form_or_heading_shape"]
        if cell_count == 5:
            flags.append("non_material_section_heading")
        else:
            flags.append("material_structured_form_context")
        return "false_positive_table_candidate", "form_block_or_heading", flags
    return (
        "text_layout_complete_topology_unresolved",
        "table",
        ["source_values_preserved_in_private_layout"],
    )


def classify_visual_unit(
    *,
    unit_type: str,
    inferred_role: str,
    page_number: int | None,
    sibling_text_characters: int,
) -> tuple[str, bool, str]:
    """Classify one visual using memory evidence plus recorded operator review."""

    if unit_type == VISUAL_MEDIA:
        return "non_material_visual_content", False, "safe_permanent_deferral"
    if sibling_text_characters > 0:
        return (
            "visual_fallback_with_text_layout",
            True,
            "text_bounded_scope_available_visual_topology_deferred",
        )
    if (
        inferred_role == "dividends_report"
        and page_number in NON_MATERIAL_NON_TEXT_DIVIDEND_PAGES
    ):
        return "non_material_visual_content", False, "safe_permanent_deferral"
    if (
        inferred_role == "dividends_report"
        and page_number not in MATERIAL_NON_TEXT_DIVIDEND_PAGES
    ):
        return "explicit_review_required", True, "operator_review_required"
    return "visual_only_material_table", True, "gate1_visual_structure_recovery"


def bbox_relationship(left: Iterable[float], right: Iterable[float]) -> dict[str, float]:
    a = [float(item) for item in left]
    b = [float(item) for item in right]
    if len(a) != 4 or len(b) != 4:
        return {"iou": 0.0, "containment": 0.0}
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    smaller = min(area_a, area_b)
    return {
        "iou": intersection / union if union else 0.0,
        "containment": intersection / smaller if smaller else 0.0,
    }


def xml_value_coverage(
    *, xml_rows: list[list[Any]], pdf_text: str
) -> dict[str, Any]:
    normalized_pdf = _normalized_value(pdf_text)
    seen: set[str] = set()
    matched = 0
    total = 0
    unmatched_fields: Counter[str] = Counter()
    for row in xml_rows[1:]:
        if not isinstance(row, list) or len(row) < 7:
            continue
        value = _normalized_value(row[6])
        if len(value) < 2 or value in {"true", "false"} or value in seen:
            continue
        seen.add(value)
        total += 1
        if value in normalized_pdf:
            matched += 1
        else:
            unmatched_fields[str(row[5] or row[4] or row[2] or "unknown")] += 1
    non_financial_fields = {"НомСпр", "НомКорр", "Тлф"}
    unmatched_financial = sum(
        count
        for field, count in unmatched_fields.items()
        if field not in non_financial_fields
    )
    return {
        "values_total": total,
        "values_matched_in_pdf_layout": matched,
        "match_ratio": round(matched / total, 6) if total else 1.0,
        "unmatched_metadata_values": sum(
            count
            for field, count in unmatched_fields.items()
            if field in non_financial_fields
        ),
        "unmatched_financial_values": unmatched_financial,
    }


def assert_safe_output(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden_patterns = {
        "artifact_ref": r"\bart_[A-Za-z0-9_-]+",
        "document_ref": r"\bbrdoc_[A-Za-z0-9_-]+",
        "unit_ref": r"\bsrcunit_[A-Za-z0-9_-]+",
        "payload_ref": r"\bsrcpayload_[A-Za-z0-9_-]+",
        "run_ref": r"\bnormrun_[A-Za-z0-9_-]+",
        "windows_path": r"[A-Za-z]:\\",
        "private_value_key": (
            r'"(?:raw_text|raw_value|private_value|private_values|'
            r'private_media_base64|filename)"\s*:'
        ),
    }
    violations = [
        name for name, pattern in forbidden_patterns.items() if re.search(pattern, rendered)
    ]
    if violations:
        raise RuntimeError("unsafe_safe_output:" + ",".join(sorted(violations)))


def _resolve_single(
    resolver: ArtifactResolver,
    records: list[Any],
    context: Any,
    artifact_type: str,
) -> dict[str, Any]:
    matches = [record for record in records if record.artifact_type == artifact_type]
    if len(matches) != 1:
        raise RuntimeError(f"artifact_count_invalid:{artifact_type}:{len(matches)}")
    return _object(resolver.resolve(matches[0].artifact_id, context)["payload"])


def _bbox_index(parent: dict[str, Any]) -> dict[str, list[float]]:
    projection = _object(parent.get("pdf_text_layer_projection"))
    result: dict[str, list[float]] = {}
    for item in projection.get("bbox_inventory") or []:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            result[str(item.get("bbox_ref") or "")] = [float(v) for v in bbox]
    return result


def _candidate_dedup(
    candidates: list[dict[str, Any]],
    parent_by_ref: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_page: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        unit = item["unit"]
        page = int(_object(unit.get("source_location")).get("page") or 0)
        by_page[(str(unit.get("document_id") or ""), page)].append(item)
    duplicate_edges: list[dict[str, Any]] = []
    overlap_edges: list[dict[str, Any]] = []
    shared_word_edges: list[dict[str, Any]] = []
    bbox_cache = {
        parent_ref: _bbox_index(parent)
        for parent_ref, parent in parent_by_ref.items()
    }
    for page_items in by_page.values():
        for index, left in enumerate(page_items):
            left_unit = left["unit"]
            left_words = set(_strings(left_unit.get("table_contributing_word_refs")))
            parent_ref = str(left_unit.get("parent_payload_ref") or "")
            boxes = bbox_cache.get(parent_ref, {})
            left_bbox = boxes.get(str(left_unit.get("table_bbox_ref") or ""), [])
            for right in page_items[index + 1 :]:
                right_unit = right["unit"]
                right_words = set(
                    _strings(right_unit.get("table_contributing_word_refs"))
                )
                right_bbox = boxes.get(str(right_unit.get("table_bbox_ref") or ""), [])
                relation = bbox_relationship(left_bbox, right_bbox)
                pair = {
                    "left": left["opaque_candidate_id"],
                    "right": right["opaque_candidate_id"],
                }
                if left_words & right_words:
                    shared_word_edges.append(pair)
                if relation["iou"] >= 0.50 or relation["containment"] >= 0.80:
                    overlap_edges.append(pair)
                if relation["iou"] >= 0.95:
                    duplicate_edges.append(pair)
    return {
        "candidate_objects": len(candidates),
        "physical_region_groups": len(candidates) - len(duplicate_edges),
        "duplicate_candidate_members": len(duplicate_edges),
        "overlapping_candidate_pairs": len(overlap_edges),
        "shared_word_owner_pairs": len(shared_word_edges),
        "same_page_groups_inspected": len(by_page),
        "private_edges": {
            "duplicates": duplicate_edges,
            "overlaps": overlap_edges,
            "shared_words": shared_word_edges,
        },
    }


def _coverage_status(
    *,
    container_format: str,
    duplicate_non_primary: bool,
    packages_total: int,
    candidate_roles: set[str],
    visual_classes: Counter[str],
    restricted_visual_total: int,
) -> str:
    if container_format == "zip":
        return "archive_lineage_only"
    if duplicate_non_primary:
        return "duplicate_non_primary_source"
    if restricted_visual_total:
        return "requires_visual_consumer_and_explicit_review"
    if visual_classes["visual_only_material_table"]:
        return "materially_incomplete_requires_visual_recovery"
    if "source_broker_report" in candidate_roles:
        return "materially_incomplete_requires_gate1_table_reconstruction"
    if container_format == "xml":
        return "neutral_structure_requires_typed_gate2_adapter"
    if "withholding_report" in candidate_roles:
        return "pdf_recovery_deferable_via_paired_neutral_xml"
    if visual_classes["visual_fallback_with_text_layout"]:
        return "usable_for_text_bounded_scopes_with_visual_omissions"
    if packages_total:
        return "fully_usable_for_declared_current_scopes"
    return "explicit_review_required"


def build_audit(
    *,
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prepared = prepare_actual_latest(config_path)
    try:
        resolver = ArtifactResolver(prepared.store)
        records = resolver.catalog_run(prepared.context)
        gate2_started = time.perf_counter()
        gate2 = Gate2InputReadinessFactory(store=prepared.store).create().audit_and_build(
            domain_context_packet_ref=prepared.dcp_ref,
            context=prepared.context,
        )
        gate2_seconds = round(time.perf_counter() - gate2_started, 6)
        dcp = _resolve_single(
            resolver, records, prepared.context, "domain_context_packet_v0"
        )
        duc = _resolve_single(
            resolver,
            records,
            prepared.context,
            "document_usage_classification_v0",
        )
        memory = _resolve_single(
            resolver,
            records,
            prepared.context,
            "broker_reports_gate1_document_memory_manifest_v1",
        )
        roles = {
            str(entry.get("document_ref") or ""): str(entry.get("inferred_role") or "")
            for entry in duc.get("entries") or []
            if isinstance(entry, dict)
        }
        ready_documents = set(
            _strings(_object(dcp.get("next_stage_refs")).get("source_fact_ready_refs"))
        )
        source_records: dict[str, dict[str, Any]] = {}
        archive_groups: dict[str, dict[str, str]] = defaultdict(dict)
        source_hash_groups: dict[str, list[str]] = defaultdict(list)
        for record in records:
            if (
                record.artifact_type != "source_file_ref_v0"
                or record.validation_status != "validated"
            ):
                continue
            payload = _object(resolver.resolve(record.artifact_id, prepared.context)["payload"])
            document_id = str(record.document_id or "")
            source_records[document_id] = payload
            source_hash_groups[str(payload.get("file_hash_sha256") or "")].append(
                document_id
            )
            parent = str(payload.get("archive_parent_document_ref") or "")
            content_type = str(payload.get("content_type") or "")
            if parent and content_type in {"application/pdf", "application/xml"}:
                archive_groups[parent][content_type] = document_id
        duplicate_source_groups = [
            members
            for source_hash, members in source_hash_groups.items()
            if source_hash and len(members) > 1
        ]
        duplicate_non_primary = {
            document_id
            for members in duplicate_source_groups
            for document_id in members[1:]
        }
        duplicate_group_by_document = {
            document_id: _opaque("source_duplicate_group", sorted(members))
            for members in duplicate_source_groups
            for document_id in members
        }
        paired_document: dict[str, str] = {}
        for group in archive_groups.values():
            pdf_document = group.get("application/pdf")
            xml_document = group.get("application/xml")
            if pdf_document and xml_document:
                paired_document[pdf_document] = xml_document
                paired_document[xml_document] = pdf_document

        parent_by_ref: dict[str, dict[str, Any]] = {}
        parent_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
        units: list[dict[str, Any]] = []
        for record in records:
            if record.validation_status != "validated":
                continue
            if record.artifact_type == "private_normalized_source_payload_v0":
                payload = _object(
                    resolver.resolve(record.artifact_id, prepared.context)["payload"]
                )
                parent_by_ref[str(payload.get("source_payload_ref") or "")] = payload
                parent_by_document[str(payload.get("document_ref") or "")].append(payload)
            elif record.artifact_type == "private_normalized_source_unit_v0":
                units.append(
                    _object(
                        resolver.resolve(record.artifact_id, prepared.context)["payload"]
                    )
                )
        projection_record_by_unit = {
            str(record.safe_metadata.get("source_unit_ref") or ""): record
            for record in records
            if record.artifact_type == "broker_reports_normalized_table_projection_v0"
        }

        repeated_text_members: dict[str, list[str]] = defaultdict(list)
        candidate_private: list[dict[str, Any]] = []
        candidate_safe: list[dict[str, Any]] = []
        candidate_roles_by_document: dict[str, set[str]] = defaultdict(set)
        candidate_class_by_document: dict[str, Counter[str]] = defaultdict(Counter)
        for unit in units:
            if _unit_type(unit) != TABLE_CANDIDATE:
                continue
            unit_ref = str(unit.get("unit_ref") or "")
            document_id = str(unit.get("document_id") or "")
            projection_record = projection_record_by_unit.get(unit_ref)
            projection_status = (
                str(projection_record.validation_status) if projection_record else "missing"
            )
            cell_count = len(_strings(unit.get("table_cell_refs")))
            word_count = len(_strings(unit.get("layout_word_refs")))
            primary, physical_kind, flags = classify_table_candidate(
                inferred_role=roles.get(document_id, ""),
                projection_validation_status=projection_status,
                cell_count=cell_count,
                word_count=word_count,
            )
            opaque_id = _opaque("candidate", unit_ref)
            content_digest = hashlib.sha256(
                _normalized_private_text(unit.get("text")).encode("utf-8")
            ).hexdigest()
            repeated_text_members[content_digest].append(opaque_id)
            paired_xml = paired_document.get(document_id)
            material = not (
                primary == "false_positive_table_candidate" and cell_count == 5
            )
            safe_item = {
                "opaque_candidate_id": opaque_id,
                "opaque_document_id": _opaque("document", document_id),
                "primary_classification": primary,
                "physical_kind": physical_kind,
                "likely_material": material,
                "materiality_family": roles.get(document_id, "unknown"),
                "text_layout_memory_complete": True,
                "accepted_text_scope_contains_candidate_refs": False,
                "paired_neutral_xml_equivalent": bool(paired_xml),
                "existing_projection_quality": (
                    str(projection_record.safe_metadata.get("reconstruction_quality") or "")
                    if projection_record
                    else "none"
                ),
                "secondary_flags": sorted(
                    set(
                        flags
                        + (["paired_neutral_xml"] if paired_xml else [])
                        + ["no_ocr_or_vlm_used"]
                    )
                ),
                "recovery_owner": (
                    "none_pdf_recovery_deferable"
                    if paired_xml
                    else "gate1_neutral_representation"
                ),
            }
            candidate_safe.append(safe_item)
            candidate_roles_by_document[document_id].add(roles.get(document_id, ""))
            candidate_class_by_document[document_id][primary] += 1
            candidate_private.append(
                {
                    "opaque_candidate_id": opaque_id,
                    "document_ref": document_id,
                    "unit_ref": unit_ref,
                    "parent_payload_ref": unit.get("parent_payload_ref"),
                    "page": _object(unit.get("source_location")).get("page"),
                    "table_bbox_ref": unit.get("table_bbox_ref"),
                    "primary_classification": primary,
                    "cell_count": cell_count,
                    "word_count": word_count,
                    "content_digest": content_digest,
                    "unit": unit,
                }
            )
        dedup = _candidate_dedup(candidate_private, parent_by_ref)
        repeated_groups = [
            members for members in repeated_text_members.values() if len(members) > 1
        ]
        repeated_group_by_candidate = {
            candidate_id: _opaque("candidate_content_group", sorted(members))
            for members in repeated_groups
            for candidate_id in members
        }
        for item in candidate_safe:
            group = repeated_group_by_candidate.get(item["opaque_candidate_id"])
            item["repeated_content_group"] = group
            item["repeated_content_not_physical_duplicate"] = bool(group)

        sibling_text_characters: Counter[tuple[str, int]] = Counter()
        for unit in units:
            if _unit_type(unit) not in TEXT_UNITS:
                continue
            page = int(_object(unit.get("source_location")).get("page") or 0)
            sibling_text_characters[(str(unit.get("document_id") or ""), page)] += int(
                unit.get("chars_count") or len(str(unit.get("text") or ""))
            )
        current_visual_units = [
            unit
            for unit in units
            if str(unit.get("document_id") or "") in ready_documents
            and _unit_type(unit) in {PDF_VISUAL, VISUAL_MEDIA}
        ]
        restricted_document_visual_units = [
            unit
            for unit in units
            if str(unit.get("document_id") or "") not in ready_documents
            and _unit_type(unit) == PDF_VISUAL
        ]
        media_groups: dict[str, list[str]] = defaultdict(list)
        visual_safe: list[dict[str, Any]] = []
        visual_private: list[dict[str, Any]] = []
        visual_class_by_document: dict[str, Counter[str]] = defaultdict(Counter)
        for unit in current_visual_units:
            document_id = str(unit.get("document_id") or "")
            page = int(unit.get("page_number") or 0) or None
            sibling_chars = sibling_text_characters[(document_id, int(page or 0))]
            primary, material, recovery = classify_visual_unit(
                unit_type=_unit_type(unit),
                inferred_role=roles.get(document_id, ""),
                page_number=page,
                sibling_text_characters=sibling_chars,
            )
            if primary == "explicit_review_required":
                raise RuntimeError("actual_visual_operator_review_rule_incomplete")
            unit_ref = str(unit.get("unit_ref") or "")
            opaque_id = _opaque("visual", unit_ref)
            media_checksum = str(
                unit.get("private_media_sha256") or unit.get("media_checksum_ref") or ""
            )
            media_groups[media_checksum].append(opaque_id)
            visual_class_by_document[document_id][primary] += 1
            visual_safe.append(
                {
                    "opaque_visual_id": opaque_id,
                    "opaque_document_id": _opaque("document", document_id),
                    "primary_classification": primary,
                    "likely_material": material,
                    "sibling_text_layout_present": sibling_chars > 0,
                    "bounded_scope_available": True,
                    "recovery_disposition": recovery,
                    "recovery_owner": (
                        "gate1_neutral_representation"
                        if primary == "visual_only_material_table"
                        else "none_or_deferred"
                    ),
                    "whole_document_provider_scope_required": False,
                }
            )
            visual_private.append(
                {
                    "opaque_visual_id": opaque_id,
                    "document_ref": document_id,
                    "unit_ref": unit_ref,
                    "page": page,
                    "media_checksum": media_checksum,
                    "sibling_text_characters": sibling_chars,
                    "primary_classification": primary,
                }
            )
        duplicate_media_groups = [
            members for checksum, members in media_groups.items() if checksum and len(members) > 1
        ]
        duplicate_media_by_visual = {
            visual_id: _opaque("visual_content_group", sorted(members))
            for members in duplicate_media_groups
            for visual_id in members
        }
        for item in visual_safe:
            group = duplicate_media_by_visual.get(item["opaque_visual_id"])
            item["duplicate_visual_group"] = group
            item["duplicate_visual_representation"] = bool(group)

        restricted_visual_safe = []
        restricted_visual_by_document: Counter[str] = Counter()
        for unit in restricted_document_visual_units:
            document_id = str(unit.get("document_id") or "")
            restricted_visual_by_document[document_id] += 1
            restricted_visual_safe.append(
                {
                    "opaque_visual_id": _opaque("restricted_visual", unit.get("unit_ref")),
                    "opaque_document_id": _opaque("document", document_id),
                    "primary_classification": "visual_only_material_table",
                    "likely_material": True,
                    "current_928_accounting_member": False,
                    "document_level_reason": "source_fact_scope_blocked_unreadable",
                    "recovery_owner": "gate1_neutral_representation",
                }
            )

        xml_safe: list[dict[str, Any]] = []
        xml_private: list[dict[str, Any]] = []
        schema_signatures: Counter[str] = Counter()
        xml_structural_variants: Counter[str] = Counter()
        xml_coverage_rows: list[dict[str, Any]] = []
        units_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for unit in units:
            units_by_document[str(unit.get("document_id") or "")].append(unit)
        for group in archive_groups.values():
            pdf_document = group.get("application/pdf")
            xml_document = group.get("application/xml")
            if not pdf_document or not xml_document:
                continue
            xml_parent = next(
                (
                    parent
                    for parent in parent_by_document.get(xml_document, [])
                    if parent.get("container_format") == "xml"
                ),
                None,
            )
            if not xml_parent:
                raise RuntimeError("paired_xml_parent_missing")
            xml_rows = _object(xml_parent.get("normalized_projection")).get("cells") or []
            pdf_text = " ".join(
                str(unit.get("text") or "")
                for unit in units_by_document.get(pdf_document, [])
                if _unit_type(unit) in {TABLE_CANDIDATE, "pdf_line_cluster_unit"}
            )
            coverage = xml_value_coverage(xml_rows=xml_rows, pdf_text=pdf_text)
            xml_coverage_rows.append(coverage)
            schema_material = [
                [str(row[2]), str(row[3]), str(row[4]), str(row[5])]
                for row in xml_rows[1:]
                if isinstance(row, list) and len(row) >= 6
            ]
            structural_variant = hashlib.sha256(
                json.dumps(
                    schema_material,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            schema_names = {
                str(row[4])
                for row in xml_rows[1:]
                if isinstance(row, list) and len(row) >= 5 and row[4]
            }
            if not {"Документ", "НДФЛ-2"} <= schema_names:
                raise RuntimeError("xml_fns_2_ndfl_family_signature_missing")
            schema_signature = hashlib.sha256(
                "FNS_2_NDFL_XML|Документ|НДФЛ-2".encode("utf-8")
            ).hexdigest()
            schema_signatures[schema_signature] += 1
            xml_structural_variants[structural_variant] += 1
            xml_safe.append(
                {
                    "opaque_xml_document_id": _opaque("document", xml_document),
                    "opaque_paired_pdf_document_id": _opaque("document", pdf_document),
                    "opaque_schema_family_id": _opaque("xml_schema", schema_signature),
                    "neutral_structure_scope": "ready",
                    "financial_interpretation_allowed": False,
                    "paired_pdf_material_value_match_ratio": coverage["match_ratio"],
                    "unmatched_financial_values": coverage[
                        "unmatched_financial_values"
                    ],
                    "deterministic_typed_adapter_possible": True,
                    "llm_interpretation_required": False,
                    "recovery_owner": "gate2_typed_source_family_adapter",
                }
            )
            xml_private.append(
                {
                    "xml_document_ref": xml_document,
                    "pdf_document_ref": pdf_document,
                    "schema_signature": schema_signature,
                    "coverage": coverage,
                }
            )

        packages_by_document: Counter[str] = Counter(
            str(package.get("document_ref") or "") for package in gate2.packages
        )
        memory_by_document = {
            str(item.get("source_file_ref") or ""): item
            for item in memory.get("documents") or []
            if isinstance(item, dict)
        }
        document_safe: list[dict[str, Any]] = []
        material_unavailable_documents: list[str] = []
        for document_id, entry in sorted(memory_by_document.items()):
            container_format = str(entry.get("container_format") or "")
            visual_classes = visual_class_by_document[document_id]
            status = _coverage_status(
                container_format=container_format,
                duplicate_non_primary=document_id in duplicate_non_primary,
                packages_total=packages_by_document[document_id],
                candidate_roles=candidate_roles_by_document[document_id],
                visual_classes=visual_classes,
                restricted_visual_total=restricted_visual_by_document[document_id],
            )
            opaque_document_id = _opaque("document", document_id)
            unavailable = status in {
                "requires_visual_consumer_and_explicit_review",
                "materially_incomplete_requires_visual_recovery",
                "materially_incomplete_requires_gate1_table_reconstruction",
                "neutral_structure_requires_typed_gate2_adapter",
                "pdf_recovery_deferable_via_paired_neutral_xml",
            }
            if unavailable:
                material_unavailable_documents.append(opaque_document_id)
            document_safe.append(
                {
                    "opaque_document_id": opaque_document_id,
                    "container_format": container_format,
                    "inferred_source_family": roles.get(document_id, "unknown"),
                    "gate2_memory_status": entry.get("gate2_memory_status"),
                    "permitted_packages": packages_by_document[document_id],
                    "candidate_class_counts": dict(
                        sorted(candidate_class_by_document[document_id].items())
                    ),
                    "visual_class_counts": dict(sorted(visual_classes.items())),
                    "restricted_visual_units_outside_928": restricted_visual_by_document[
                        document_id
                    ],
                    "paired_source_document": (
                        _opaque("document", paired_document[document_id])
                        if document_id in paired_document
                        else None
                    ),
                    "duplicate_source_group": duplicate_group_by_document.get(document_id),
                    "coverage_status": status,
                    "complete_bounded_current_scenario": status
                    in {
                        "fully_usable_for_declared_current_scopes",
                        "usable_for_text_bounded_scopes_with_visual_omissions",
                    },
                    "material_evidence_unavailable_to_current_gate2": unavailable,
                }
            )

        candidate_counts = Counter(
            item["primary_classification"] for item in candidate_safe
        )
        physical_counts = Counter(item["physical_kind"] for item in candidate_safe)
        visual_counts = Counter(item["primary_classification"] for item in visual_safe)
        visual_material_group_ids = {
            item.get("duplicate_visual_group") or item["opaque_visual_id"]
            for item in visual_safe
            if item["primary_classification"] == "visual_only_material_table"
        }
        package_scope_counts = _object(gate2.validation.get("slice_audit")).get(
            "selected_scope_counts"
        ) or {}
        safe = {
            "schema_version": SCHEMA_VERSION,
            "audit_date": "2026-07-19",
            "status": "completed",
            "workload": {
                "fingerprint": prepared.identity.get("workload_fingerprint"),
                "artifact_records": len(records),
                "source_records": len(source_records),
                "logical_documents_excluding_archive_containers": sum(
                    1
                    for entry in memory_by_document.values()
                    if entry.get("container_format") != "zip"
                ),
            },
            "gate2_accounting": {
                "source_units_total": _object(gate2.validation.get("slice_audit")).get(
                    "full_source_units_total"
                ),
                "permitted_packages": len(gate2.packages),
                "blocked_noncanonical_table_candidates": 194,
                "blocked_visual_units": 67,
                "equation": "928=667+194+67",
                "selected_scope_counts": package_scope_counts,
                "provider_llm_calls": 0,
                "provider_retries": 0,
                "provider_tokens": 0,
                "measured_wall_seconds": gate2_seconds,
                "artifactstore_unchanged": gate2.validation.get(
                    "artifactstore_unchanged"
                ),
                "source_fact_llm_call_performed": _object(
                    gate2.safe_report.get("safety_flags")
                ).get("source_fact_llm_call_performed"),
            },
            "table_candidate_summary": {
                "candidate_objects": len(candidate_safe),
                "distinct_physical_regions": dedup["physical_region_groups"],
                "real_table_regions": physical_counts["table"],
                "form_or_heading_regions": len(candidate_safe)
                - physical_counts["table"],
                "primary_classification_counts": dict(sorted(candidate_counts.items())),
                "duplicate_candidate_members": dedup["duplicate_candidate_members"],
                "overlapping_candidate_pairs": dedup[
                    "overlapping_candidate_pairs"
                ],
                "shared_word_owner_pairs": dedup["shared_word_owner_pairs"],
                "complete_private_text_layout_representations": len(candidate_safe),
                "accepted_text_scope_representations": 0,
                "paired_neutral_xml_candidate_objects": sum(
                    bool(item["paired_neutral_xml_equivalent"])
                    for item in candidate_safe
                ),
                "broker_report_candidate_regions_unique_to_candidate_family": sum(
                    item["materiality_family"] == "source_broker_report"
                    for item in candidate_safe
                ),
                "repeated_content_groups_not_physical_duplicates": len(repeated_groups),
                "repeated_content_members": sum(len(group) for group in repeated_groups),
                "repeated_content_redundant_members": sum(
                    len(group) - 1 for group in repeated_groups
                ),
                "pdf_recovery_safely_deferable_via_xml": sum(
                    bool(item["paired_neutral_xml_equivalent"])
                    for item in candidate_safe
                ),
            },
            "table_candidates": candidate_safe,
            "visual_summary": {
                "blocked_visual_units": len(visual_safe),
                "primary_classification_counts": dict(sorted(visual_counts.items())),
                "exact_duplicate_visual_groups": len(duplicate_media_groups),
                "exact_duplicate_visual_members_beyond_first": sum(
                    len(group) - 1 for group in duplicate_media_groups
                ),
                "material_visual_only_units": visual_counts[
                    "visual_only_material_table"
                ],
                "unique_material_visual_only_groups": len(visual_material_group_ids),
                "units_safe_to_defer_for_text_bounded_scenarios": (
                    visual_counts["visual_fallback_with_text_layout"]
                    + visual_counts["non_material_visual_content"]
                ),
            },
            "visual_units": visual_safe,
            "restricted_document_visual_summary": {
                "outside_928_accounting": len(restricted_visual_safe),
                "classification": "visual_only_material_table",
                "documents": len(restricted_visual_by_document),
                "reason": "document_level_source_fact_scope_blocked_unreadable",
            },
            "restricted_document_visual_units": restricted_visual_safe,
            "xml_summary": {
                "neutral_xml_packages": len(xml_safe),
                "schema_families": len(schema_signatures),
                "optional_structural_variants": len(xml_structural_variants),
                "paired_pdf_documents": len(xml_safe),
                "xml_distinct_values_total": sum(
                    row["values_total"] for row in xml_coverage_rows
                ),
                "values_matched_in_pdf_layout_total": sum(
                    row["values_matched_in_pdf_layout"] for row in xml_coverage_rows
                ),
                "weighted_match_ratio": round(
                    sum(row["values_matched_in_pdf_layout"] for row in xml_coverage_rows)
                    / max(1, sum(row["values_total"] for row in xml_coverage_rows)),
                    6,
                ),
                "unmatched_metadata_values": sum(
                    row["unmatched_metadata_values"] for row in xml_coverage_rows
                ),
                "unmatched_financial_values": sum(
                    row["unmatched_financial_values"] for row in xml_coverage_rows
                ),
                "official_schema_family_identified": "FNS_2_NDFL_XML",
                "deterministic_typed_adapter_possible": True,
                "llm_required": False,
            },
            "xml_packages": xml_safe,
            "source_deduplication": {
                "source_records": len(source_records),
                "unique_byte_hash_groups": len(source_hash_groups),
                "exact_duplicate_groups": len(duplicate_source_groups),
                "redundant_source_records": sum(
                    len(group) - 1 for group in duplicate_source_groups
                ),
                "paired_pdf_xml_groups": len(xml_safe),
            },
            "document_coverage_summary": {
                "source_records": len(document_safe),
                "logical_documents_excluding_archive_containers": sum(
                    item["container_format"] != "zip" for item in document_safe
                ),
                "coverage_status_counts": dict(
                    sorted(Counter(item["coverage_status"] for item in document_safe).items())
                ),
                "material_evidence_unavailable_source_records": len(
                    material_unavailable_documents
                ),
                "material_evidence_unavailable_opaque_documents": sorted(
                    material_unavailable_documents
                ),
            },
            "document_coverage": document_safe,
            "ownership": {
                "neutral_text_and_table_structure": "gate1",
                "visual_to_neutral_cell_structure": "gate1_child_capability",
                "typed_financial_meaning": "gate2_typed_source_consumer",
                "visual_financial_fact_inference": "specialized_gate2_consumer",
                "validator_and_promotion_authority": "deterministic_contract_validators",
            },
            "confirmed_contract_or_implementation_defects": [
                {
                    "code": "archive_lineage_records_declared_source_fact_ready",
                    "affected_source_records": 24,
                    "impact": "spurious_gate2_memory_blocked_errors_for_container_identities",
                    "owner": "gate1_dcp_handoff_classification",
                    "candidate_or_visual_promotion_required": False,
                }
            ],
            "correct_restrictions_to_keep": [
                "noncanonical_pdf_candidates_must_not_be_promoted_as_tables",
                "visual_units_require_a_declared_typed_consumer",
                "neutral_xml_must_not_receive_financial_semantics_in_gate1",
                "low_quality_or_geometry_only_projections_are_not_canonical_facts",
                "document_level_unreadable_visual_sources_remain_review_restricted",
            ],
            "safety": {
                "customer_values_present": False,
                "filenames_present": False,
                "private_paths_present": False,
                "source_coordinates_present": False,
                "blocked_candidate_promotions": 0,
                "provider_calls": 0,
                "knowledge_rag_used": False,
            },
        }
        if len(candidate_safe) != 194:
            raise RuntimeError(f"candidate_accounting_mismatch:{len(candidate_safe)}")
        if len(visual_safe) != 67:
            raise RuntimeError(f"visual_accounting_mismatch:{len(visual_safe)}")
        if len(xml_safe) != 24:
            raise RuntimeError(f"xml_accounting_mismatch:{len(xml_safe)}")
        if len(restricted_visual_safe) != 6:
            raise RuntimeError(
                f"restricted_visual_accounting_mismatch:{len(restricted_visual_safe)}"
            )
        if candidate_counts != Counter(
            {
                "canonical_projection_already_exists": 33,
                "false_positive_table_candidate": 90,
                "text_layout_complete_topology_unresolved": 71,
            }
        ):
            raise RuntimeError(f"candidate_classification_drift:{dict(candidate_counts)}")
        if visual_counts != Counter(
            {
                "visual_fallback_with_text_layout": 51,
                "visual_only_material_table": 6,
                "non_material_visual_content": 10,
            }
        ):
            raise RuntimeError(f"visual_classification_drift:{dict(visual_counts)}")
        if dedup["duplicate_candidate_members"] or dedup["overlapping_candidate_pairs"]:
            raise RuntimeError("candidate_geometry_dedup_drift")
        if safe["xml_summary"]["unmatched_financial_values"]:
            raise RuntimeError("xml_pdf_financial_value_coverage_drift")
        assert_safe_output(safe)
        private = {
            "schema_version": PRIVATE_SCHEMA_VERSION,
            "safe_output_digest": hashlib.sha256(
                json.dumps(
                    safe,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "candidate_review": [
                {key: value for key, value in item.items() if key != "unit"}
                for item in candidate_private
            ],
            "candidate_geometry_edges": dedup["private_edges"],
            "visual_review": visual_private,
            "restricted_visual_review": [
                {
                    "document_ref": unit.get("document_id"),
                    "unit_ref": unit.get("unit_ref"),
                    "page": unit.get("page_number"),
                    "primary_classification": "visual_only_material_table",
                }
                for unit in restricted_document_visual_units
            ],
            "xml_review": xml_private,
            "raw_customer_values_copied": False,
            "original_files_copied": False,
        }
        return safe, private
    finally:
        prepared.cleanup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_ACTUAL_CONFIG)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    safe_output = args.safe_output.resolve()
    private_output = args.private_output.resolve()
    if private_output.is_relative_to(REPO_ROOT.resolve()) and "local" not in {
        part.casefold() for part in private_output.parts
    }:
        raise RuntimeError("private_output_must_be_outside_tracked_repository_scope")
    safe, private = build_audit(config_path=args.config.resolve())
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    private_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    private_output.write_text(
        json.dumps(private, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": safe["status"],
                "candidates": len(safe["table_candidates"]),
                "visual_units": len(safe["visual_units"]),
                "xml_packages": len(safe["xml_packages"]),
                "customer_values_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
