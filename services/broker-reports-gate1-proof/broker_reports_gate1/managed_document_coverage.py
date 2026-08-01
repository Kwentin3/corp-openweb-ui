from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any


SOURCE_OBSERVATION_INVENTORY_SCHEMA_VERSION = (
    "broker_reports_pdf_source_observation_inventory_v1"
)
MANAGED_DOCUMENT_COVERAGE_SCHEMA_VERSION = (
    "broker_reports_managed_document_coverage_receipt_v1"
)
PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION = (
    "broker_reports_pdf_managed_document_parity_checklist_v1"
)

OBSERVATION_TYPES = {
    "PAGE_BOUNDARY",
    "TEXT_BLOCK",
    "TEXT_LINE",
    "TABLE_REGION",
    "VALIDATED_LOGICAL_TABLE",
    "VISUAL_REGION",
    "FULL_PAGE_VISUAL",
    "UNSUPPORTED_REGION",
    "PARSER_FAILURE",
    "UNKNOWN_OBSERVATION",
}

COVERAGE_STATUSES = {
    "REPRESENTED_BY_BLOCK",
    "REPRESENTED_BY_ANCHOR",
    "REPRESENTED_BY_TABLE",
    "DUPLICATE_SUPPRESSED",
    "KNOWN_LOSS",
    "BLOCKED_AT_SOURCE",
    "UNRESOLVED",
}

PARITY_STATUSES = {
    "MATCH",
    "PARTIAL_MATCH",
    "MISSING_IN_ARTIFACT",
    "EXTRA_IN_ARTIFACT",
    "WRONG_ORDER",
    "WRONG_RELATION",
    "WRONG_VALUE",
    "UNVERIFIABLE",
}


class ManagedDocumentCoverageError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def canonical_sha256(value: dict[str, Any]) -> str:
    material = copy.deepcopy(value)
    material.pop("integrity_sha256", None)
    payload = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal_private_contract(value: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(value)
    sealed["integrity_sha256"] = canonical_sha256(sealed)
    return sealed


def validate_source_observation_inventory(
    inventory: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if inventory.get("schema_version") != SOURCE_OBSERVATION_INVENTORY_SCHEMA_VERSION:
        errors.append("source_observation_inventory_schema_invalid")
    if not _identifier(inventory.get("document_id")):
        errors.append("source_observation_inventory_document_id_invalid")
    if not _sha256(inventory.get("source_checksum_sha256")):
        errors.append("source_observation_inventory_source_checksum_invalid")
    observations = _dicts(inventory.get("observations"))
    ids = [str(item.get("observation_id") or "") for item in observations]
    if not ids or any(not _identifier(value) for value in ids):
        errors.append("source_observation_inventory_id_invalid")
    if len(ids) != len(set(ids)):
        errors.append("source_observation_inventory_id_duplicate")
    for item in observations:
        if item.get("observation_type") not in OBSERVATION_TYPES:
            errors.append("source_observation_inventory_type_invalid")
        page = item.get("page")
        if page is not None and (not isinstance(page, int) or page <= 0):
            errors.append("source_observation_inventory_page_invalid")
        if not _sha256(item.get("observation_checksum_sha256")):
            errors.append("source_observation_inventory_checksum_invalid")
        if item.get("available_text") is not None and not isinstance(
            item.get("available_text"), str
        ):
            errors.append("source_observation_inventory_available_text_invalid")
        for field in (
            "parent_observation_ids",
            "source_refs",
            "related_observation_ids",
            "overlap_observation_ids",
        ):
            if not _identifier_list(item.get(field)):
                errors.append(f"source_observation_inventory_{field}_invalid")
        if item.get("processing_status") not in {"OBSERVED", "VALIDATED", "BLOCKED"}:
            errors.append("source_observation_inventory_processing_status_invalid")
        for field in ("source_parser", "source_parser_version", "source_parser_config_ref"):
            if item.get(field) is not None and not _provenance_value(item.get(field)):
                errors.append(f"source_observation_inventory_{field}_invalid")
    if inventory.get("observations_total") != len(observations):
        errors.append("source_observation_inventory_count_mismatch")
    if inventory.get("integrity_sha256") != canonical_sha256(inventory):
        errors.append("source_observation_inventory_integrity_mismatch")
    return _validation("source_observation_inventory", errors)


def validate_managed_document_coverage(
    receipt: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("schema_version") != MANAGED_DOCUMENT_COVERAGE_SCHEMA_VERSION:
        errors.append("managed_document_coverage_schema_invalid")
    if receipt.get("document_id") != inventory.get("document_id"):
        errors.append("managed_document_coverage_document_mismatch")
    if receipt.get("source_checksum_sha256") != inventory.get("source_checksum_sha256"):
        errors.append("managed_document_coverage_source_checksum_mismatch")
    inventory_validation = validate_source_observation_inventory(inventory)
    if not inventory_validation["passed"]:
        errors.append("managed_document_coverage_inventory_invalid")

    observations = _dicts(inventory.get("observations"))
    observation_by_id = {
        str(item.get("observation_id") or ""): item for item in observations
    }
    observation_ids = [str(item.get("observation_id") or "") for item in observations]
    entries = _dicts(receipt.get("entries"))
    covered_ids = [str(item.get("observation_id") or "") for item in entries]
    if Counter(covered_ids) != Counter(observation_ids):
        errors.append("managed_document_coverage_not_bijective")
    for item in entries:
        status = item.get("coverage_status")
        if status not in COVERAGE_STATUSES:
            errors.append("managed_document_coverage_status_invalid")
        for field in ("block_ids", "anchor_ids", "table_ids", "loss_ids"):
            if not _identifier_list(item.get(field)):
                errors.append(f"managed_document_coverage_{field}_invalid")
        block_ids = item.get("block_ids") if isinstance(item.get("block_ids"), list) else []
        anchor_ids = item.get("anchor_ids") if isinstance(item.get("anchor_ids"), list) else []
        table_ids = item.get("table_ids") if isinstance(item.get("table_ids"), list) else []
        loss_ids = item.get("loss_ids") if isinstance(item.get("loss_ids"), list) else []
        mapping_method = item.get("mapping_method")
        if not _identifier(item.get("reason_code")):
            errors.append("managed_document_coverage_reason_code_invalid")
        if status == "REPRESENTED_BY_BLOCK" and not block_ids:
            errors.append("managed_document_coverage_block_owner_missing")
        if status in {"REPRESENTED_BY_ANCHOR", "REPRESENTED_BY_TABLE"} and (
            not block_ids or not anchor_ids
        ):
            errors.append("managed_document_coverage_source_owner_missing")
        if status == "REPRESENTED_BY_TABLE" and (
            not table_ids or not _identifier(mapping_method)
        ):
            errors.append("managed_document_coverage_table_mapping_missing")
        if status != "REPRESENTED_BY_TABLE" and (
            table_ids or mapping_method is not None
        ):
            errors.append("managed_document_coverage_table_mapping_unexpected")
        if status == "KNOWN_LOSS" and (
            not loss_ids or not (block_ids or anchor_ids)
        ):
            errors.append("managed_document_coverage_known_loss_owner_missing")
        if status == "DUPLICATE_SUPPRESSED":
            duplicate = observation_by_id.get(
                str(item.get("duplicate_of_observation_id") or "")
            )
            current = observation_by_id.get(str(item.get("observation_id") or ""))
            if (
                duplicate is None
                or current is None
                or duplicate is current
                or not _same_source_observation(current, duplicate)
            ):
                errors.append("managed_document_coverage_duplicate_not_proven")
            if not block_ids:
                errors.append("managed_document_coverage_duplicate_owner_missing")
        elif item.get("duplicate_of_observation_id") is not None:
            errors.append("managed_document_coverage_duplicate_proof_unexpected")
        if status == "UNRESOLVED" and (block_ids or anchor_ids or loss_ids):
            errors.append("managed_document_coverage_unresolved_has_owner")

    unresolved = sum(item.get("coverage_status") == "UNRESOLVED" for item in entries)
    known_loss = sum(item.get("coverage_status") == "KNOWN_LOSS" for item in entries)
    blocked = sum(
        item.get("coverage_status") == "BLOCKED_AT_SOURCE" for item in entries
    )
    counters = (
        receipt.get("counters") if isinstance(receipt.get("counters"), dict) else {}
    )
    expected_counters = {
        "source_observations_total": len(observations),
        "coverage_entries_total": len(entries),
        "unresolved_total": unresolved,
        "known_loss_total": known_loss,
        "blocked_at_source_total": blocked,
        "unaccounted_context_loss_total": 0,
        "invented_source_content_total": 0,
    }
    if counters != expected_counters:
        errors.append("managed_document_coverage_counters_mismatch")
    expected_accepted = not unresolved and not blocked
    if bool(receipt.get("accepted")) != expected_accepted:
        errors.append("managed_document_coverage_acceptance_mismatch")
    if receipt.get("integrity_sha256") != canonical_sha256(receipt):
        errors.append("managed_document_coverage_integrity_mismatch")
    return _validation("managed_document_coverage", errors)


def validate_parity_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if (
        checklist.get("schema_version")
        != PDF_MANAGED_DOCUMENT_PARITY_CHECKLIST_SCHEMA_VERSION
    ):
        errors.append("managed_document_parity_schema_invalid")
    pass_type = checklist.get("pass")
    if pass_type not in {"PDF_ONLY", "ARTIFACT_ONLY", "COMPARISON"}:
        errors.append("managed_document_parity_pass_invalid")
    if not _identifier(checklist.get("document_id")):
        errors.append("managed_document_parity_document_id_invalid")
    if not _sha256(checklist.get("source_checksum_sha256")):
        errors.append("managed_document_parity_source_checksum_invalid")
    if pass_type in {"PDF_ONLY", "ARTIFACT_ONLY"}:
        summary = checklist.get("summary")
        required_summary_fields = {
            "page_boundaries_total",
            "block_order_tokens",
            "structure_items",
            "source_content_token_multiset_sha256",
            "source_content_sequence_sha256",
            "tables",
            "value_sample_policy",
            "value_samples",
            "table_regions_total",
            "validated_tables_total",
            "visuals_total",
            "metadata_expected_unknown",
            "known_losses_expected_total",
        }
        if not isinstance(summary, dict) or not required_summary_fields <= set(summary):
            errors.append("managed_document_parity_summary_incomplete")
        elif (
            not _sha256(summary.get("source_content_token_multiset_sha256"))
            or not _sha256(summary.get("source_content_sequence_sha256"))
            or not _pointer_collection(summary.get("structure_items"))
            or not _pointer_collection(summary.get("tables"))
            or not _sample_collection(summary.get("value_samples"))
        ):
            errors.append("managed_document_parity_summary_invalid")
    if pass_type == "COMPARISON":
        dimensions = _dicts(checklist.get("dimensions"))
        if any(item.get("status") not in PARITY_STATUSES for item in dimensions):
            errors.append("managed_document_parity_status_invalid")
        dimension_ids = [str(item.get("dimension") or "") for item in dimensions]
        if (
            not dimensions
            or len(dimension_ids) != len(set(dimension_ids))
            or any(not _identifier(value) for value in dimension_ids)
        ):
            errors.append("managed_document_parity_dimensions_invalid")
        for item in dimensions:
            critical = item.get("critical_if_mismatch")
            category = item.get("critical_category")
            if not isinstance(critical, bool):
                errors.append("managed_document_parity_critical_flag_invalid")
            if item.get("status") == "MATCH" and category is not None:
                errors.append("managed_document_parity_match_category_unexpected")
            if item.get("status") != "MATCH" and critical is True and not _identifier(
                category
            ):
                errors.append("managed_document_parity_critical_category_missing")
            if not _sha256(item.get("pdf_value_sha256")) or not _sha256(
                item.get("artifact_value_sha256")
            ):
                errors.append("managed_document_parity_dimension_hash_invalid")
        critical = sum(
            item.get("status") != "MATCH" and item.get("critical_if_mismatch") is True
            for item in dimensions
        )
        noncritical = sum(
            item.get("status") != "MATCH" and item.get("critical_if_mismatch") is False
            for item in dimensions
        )
        if checklist.get("critical_mismatches_total") != critical:
            errors.append("managed_document_parity_critical_count_mismatch")
        if checklist.get("noncritical_mismatches_total") != noncritical:
            errors.append("managed_document_parity_noncritical_count_mismatch")
        if bool(checklist.get("full_parity")) != (not critical and not noncritical):
            errors.append("managed_document_parity_full_parity_mismatch")
    if checklist.get("integrity_sha256") != canonical_sha256(checklist):
        errors.append("managed_document_parity_integrity_mismatch")
    return _validation("managed_document_parity", errors)


def require_private_contract(validation: dict[str, Any]) -> None:
    if not validation.get("passed"):
        first = next(
            iter(validation.get("reason_codes") or []), "private_contract_invalid"
        )
        raise ManagedDocumentCoverageError(str(first))


def _validation(kind: str, errors: list[str]) -> dict[str, Any]:
    reason_codes = sorted(set(errors))
    return {
        "schema_version": f"broker_reports_{kind}_validation_v1",
        "passed": not reason_codes,
        "validator_status": "passed" if not reason_codes else "failed",
        "errors_total": len(reason_codes),
        "reason_codes": reason_codes,
    }


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _pointer_collection(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, dict) and isinstance(item.get("source_pointer"), dict)
        for item in value
    )


def _sample_collection(value: Any) -> bool:
    return _pointer_collection(value) and all(
        isinstance(item.get("sequence_index"), int)
        and item["sequence_index"] >= 0
        and _sha256(item.get("value_sha256"))
        for item in value
    )


def _identifier(value: Any) -> bool:
    if not isinstance(value, str) or len(value) < 3 or len(value) > 160:
        return False
    return all(character.isalnum() or character in "_-" for character in value)


def _identifier_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(set(value))
        and all(_identifier(item) for item in value)
    )


def _provenance_value(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 160
        and all(character.isprintable() and character not in "\r\n" for character in value)
    )


def _sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _same_source_observation(
    current: dict[str, Any], duplicate: dict[str, Any]
) -> bool:
    fields = (
        "observation_type",
        "page",
        "bbox",
        "parent_observation_ids",
        "source_refs",
        "observation_checksum_sha256",
    )
    return all(current.get(field) == duplicate.get(field) for field in fields)
