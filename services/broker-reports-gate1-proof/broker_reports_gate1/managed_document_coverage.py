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
    "NONCRITICAL_MISMATCH",
    "CRITICAL_MISMATCH",
    "NOT_APPLICABLE",
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
        if item.get("coverage_status") not in COVERAGE_STATUSES:
            errors.append("managed_document_coverage_status_invalid")
        if item.get("coverage_status") == "DUPLICATE_SUPPRESSED":
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
        elif item.get("duplicate_of_observation_id") is not None:
            errors.append("managed_document_coverage_duplicate_proof_unexpected")
        if item.get("coverage_status") == "UNRESOLVED" and (
            item.get("block_ids") or item.get("anchor_ids") or item.get("loss_ids")
        ):
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
    if checklist.get("pass") not in {"PDF_ONLY", "ARTIFACT_ONLY", "COMPARISON"}:
        errors.append("managed_document_parity_pass_invalid")
    if not _identifier(checklist.get("document_id")):
        errors.append("managed_document_parity_document_id_invalid")
    if not _sha256(checklist.get("source_checksum_sha256")):
        errors.append("managed_document_parity_source_checksum_invalid")
    if checklist.get("pass") == "COMPARISON":
        dimensions = _dicts(checklist.get("dimensions"))
        if any(item.get("status") not in PARITY_STATUSES for item in dimensions):
            errors.append("managed_document_parity_status_invalid")
        critical = sum(item.get("status") == "CRITICAL_MISMATCH" for item in dimensions)
        if checklist.get("critical_mismatches_total") != critical:
            errors.append("managed_document_parity_critical_count_mismatch")
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


def _identifier(value: Any) -> bool:
    if not isinstance(value, str) or len(value) < 3 or len(value) > 160:
        return False
    return all(character.isalnum() or character in "_-" for character in value)


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
