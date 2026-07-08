from __future__ import annotations

import copy
import json
from typing import Iterable

from .blockers import privacy_violation
from .contracts import BLOCKER_CODES


SAFE_REPORT_ALLOWED_KEYS = {
    "schema_version",
    "report_id",
    "normalization_run_id",
    "run_status",
    "trigger_type",
    "entrypoint",
    "normalizer_version",
    "files_total",
    "container_counts",
    "document_class_counts",
    "duplicate_count",
    "blockers_total",
    "summary_counts",
    "file_ref_visibility",
    "input_context",
    "normalization_run",
    "document_inventory",
    "documents",
    "technical_readability_profiles",
    "taxonomy_candidates",
    "normalization_blockers",
    "blockers",
    "validation_result",
    "case_groups",
    "safe_artifact_refs",
    "private_artifact_summary",
    "supported_contracts",
    "recommended_next_step",
    "next_step",
    "gate2_handoff_status",
    "safety_flags",
    "safety_statement",
}

FORBIDDEN_FIELD_NAMES = {
    "file_id",
    "filename",
    "original_filename",
    "original_filename_private",
    "private_ref",
    "private_path",
    "path",
    "raw_text",
    "raw_rows",
    "rows",
    "text",
    "content",
    "normalized_table_slice",
    "normalized_text_slice",
}

FALSE_SAFETY_FLAGS = {
    "tax_correctness_claimed",
    "source_fact_extraction_performed",
    "declaration_generated",
    "xlsx_generated",
    "fns_filing_claimed",
    "ocr_performed",
    "customer_docs_loaded_to_knowledge",
}


def validate_artifacts(package: dict) -> dict:
    errors: list[dict] = []
    documents = package.get("document_inventory", {}).get("documents", [])
    profiles = package.get("technical_readability_profiles", [])
    slices = package.get("private_normalized_slices", [])
    taxonomy_candidates = package.get("taxonomy_candidates", [])
    blockers = package.get("normalization_blockers", [])
    run_id = package.get("normalization_run", {}).get("run_id")

    blocker_ids = {item.get("blocker_id") for item in blockers}
    profile_by_doc = {item.get("document_id"): item for item in profiles}
    document_ids = {item.get("document_id") for item in documents}
    taxonomy_doc_ids = {item.get("document_id") for item in taxonomy_candidates}

    for blocker in blockers:
        if blocker.get("code") not in BLOCKER_CODES:
            errors.append(_error("unsupported_blocker_code", blocker.get("blocker_id")))
        if blocker.get("run_id") != run_id:
            errors.append(_error("blocker_run_ref_mismatch", blocker.get("blocker_id")))

    for document in documents:
        document_id = document.get("document_id")
        refs = document.get("blocker_refs")
        if not isinstance(refs, list):
            errors.append(_error("document_missing_blocker_refs", document_id))
            refs = []
        for ref in refs:
            if ref not in blocker_ids:
                errors.append(_error("document_unknown_blocker_ref", document_id))

        if document.get("bytes_status") == "available" and document.get("container_format") in {
            "csv",
            "txt",
            "html_text",
            "xlsx",
            "pdf",
            "zip",
            "docx",
            "image",
        }:
            if document_id not in profile_by_doc and not refs:
                errors.append(_error("supported_readable_file_has_no_profile_or_blocker", document_id))

        if document_id not in taxonomy_doc_ids:
            errors.append(_error("document_missing_taxonomy_candidate", document_id))

    for private_slice in slices:
        if not private_slice.get("document_id"):
            errors.append(_error("slice_missing_document_id", private_slice.get("slice_id")))
        if not private_slice.get("profile_id"):
            errors.append(_error("slice_missing_profile_id", private_slice.get("slice_id")))
        if not private_slice.get("source_location"):
            errors.append(_error("slice_missing_source_location", private_slice.get("slice_id")))

    for taxonomy_candidate in taxonomy_candidates:
        if taxonomy_candidate.get("document_id") not in document_ids:
            errors.append(_error("taxonomy_unknown_document_ref", taxonomy_candidate.get("taxonomy_candidate_id")))

    for profile in profiles:
        if profile.get("container_format") == "zip":
            has_inventory = bool(profile.get("member_inventory")) or bool(profile.get("member_count"))
            doc_refs = {
                blocker.get("code")
                for blocker in blockers
                if blocker.get("document_id") == profile.get("document_id")
            }
            if not has_inventory and not ({"parser_failed", "unsupported_format", "corrupt_file"} & doc_refs):
                errors.append(_error("zip_missing_inventory_or_blocker", profile.get("document_id")))
        if profile.get("container_format") == "pdf" and profile.get("raster_or_scan_likelihood") in {"medium", "high"}:
            doc_refs = {
                blocker.get("code")
                for blocker in blockers
                if blocker.get("document_id") == profile.get("document_id")
            }
            if "raster_requires_ocr_or_review" not in doc_refs:
                errors.append(_error("raster_pdf_missing_gate2_blocker", profile.get("document_id")))

    gate2_status = package.get("normalization_run", {}).get("gate2_handoff_status")
    if any(blocker.get("blocks_gate2") for blocker in blockers) and gate2_status != "blocked":
        errors.append(_error("gate2_handoff_not_blocked_for_terminal_blockers", gate2_status))

    return _validation_result(errors=errors, privacy_blocker=None)


def validate_safe_report(
    *,
    safe_report: dict,
    private_markers: Iterable[str],
    run_id: str,
) -> dict:
    errors: list[dict] = []
    unknown_keys = sorted(set(safe_report) - SAFE_REPORT_ALLOWED_KEYS)
    if unknown_keys:
        errors.append(_error("safe_report_unknown_keys", ",".join(unknown_keys)))

    forbidden_paths = _find_forbidden_fields(safe_report)
    for path in forbidden_paths:
        errors.append(_error("safe_report_forbidden_field", path))

    flags = safe_report.get("safety_flags") if isinstance(safe_report.get("safety_flags"), dict) else {}
    for flag in FALSE_SAFETY_FLAGS:
        if flags.get(flag) is not False:
            errors.append(_error("safety_flag_not_false", flag))

    rendered = json.dumps(safe_report, ensure_ascii=False, sort_keys=True)
    leaked = [
        marker
        for marker in private_markers
        if isinstance(marker, str) and len(marker) >= 3 and marker in rendered
    ]
    privacy_blocker = privacy_violation(run_id, "private_marker_detected") if leaked else None
    return _validation_result(errors=errors, privacy_blocker=privacy_blocker)


def merge_validation_results(*results: dict) -> dict:
    errors: list[dict] = []
    privacy_blocker = None
    for result in results:
        errors.extend(copy.deepcopy(result.get("errors") or []))
        if result.get("privacy_blocker"):
            privacy_blocker = result["privacy_blocker"]
    return _validation_result(errors=errors, privacy_blocker=privacy_blocker)


def _validation_result(*, errors: list[dict], privacy_blocker: dict | None) -> dict:
    if privacy_blocker:
        status = "privacy_failed"
    elif errors:
        status = "failed"
    else:
        status = "passed"
    return {
        "schema_version": "validation_result_v0",
        "status": status,
        "passed": status == "passed",
        "errors_count": len(errors),
        "errors": errors,
        "privacy_blocker": privacy_blocker,
    }


def _find_forbidden_fields(value: object, *, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_FIELD_NAMES:
                findings.append(child_path)
            findings.extend(_find_forbidden_fields(child, prefix=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_fields(child, prefix=f"{prefix}[{index}]"))
    return findings


def _error(code: str, subject: object) -> dict:
    return {"code": code, "subject": str(subject or "")}
