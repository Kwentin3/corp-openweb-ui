from __future__ import annotations

import hashlib
from typing import Iterable


SAFE_REPORT_SCHEMA = "broker_reports_chat_visible_normalization_report_v0"
NORMALIZER_VERSION = "gate1_backend_profiling_completion_v1"
SAFETY_STATEMENT = (
    "Gate 1 did not calculate tax, extract source facts through LLM, generate "
    "declaration, generate XLS/XLSX or file with FNS."
)

SAFETY_FLAGS = {
    "tax_correctness_claimed": False,
    "source_fact_extraction_performed": False,
    "declaration_generated": False,
    "xlsx_generated": False,
    "fns_filing_claimed": False,
    "ocr_performed": False,
    "customer_docs_loaded_to_knowledge": False,
}

SUPPORTED_CONTRACTS = [
    "normalization_run_v0",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "private_normalized_slices_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    SAFE_REPORT_SCHEMA,
    "validation_result_v0",
]

BLOCKER_CODES = {
    "no_files",
    "bytes_unavailable",
    "unsupported_format",
    "encrypted_file",
    "corrupt_file",
    "parser_failed",
    "raster_requires_ocr_or_review",
    "zip_requires_review",
    "unknown_role",
    "privacy_violation",
    "duplicate_review",
}


def stable_digest(parts: Iterable[object], *, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]


def normalization_run_id(input_summaries: list[dict]) -> str:
    material = [
        f"{item.get('private_ref_hash')}:{item.get('extension')}:{item.get('mime_type')}"
        for item in input_summaries
    ]
    return f"normrun_{stable_digest(material)}"


def safe_artifact_refs(run_id: str) -> dict[str, str]:
    suffix = run_id.removeprefix("normrun_")
    return {
        "normalization_run_ref": run_id,
        "document_inventory_ref": f"docinv_{suffix}",
        "technical_readability_profile_ref": f"techprofiles_{suffix}",
        "private_normalized_slices_ref": f"privslices_{suffix}",
        "taxonomy_candidates_ref": f"taxcands_{suffix}",
        "normalization_blockers_ref": f"blockers_{suffix}",
        "chat_visible_report_ref": f"normreport_{suffix}",
        "validation_result_ref": f"validation_{suffix}",
    }


def document_id(
    *,
    index: int,
    content_sha256: str | None,
    private_ref_hash: str,
    extension: str,
    mime_type: str,
) -> str:
    digest = content_sha256[:12] if content_sha256 else stable_digest(
        [private_ref_hash, extension, mime_type],
        length=12,
    )
    return f"brdoc_{index:03d}_{digest}"


def profile_id(document_id_value: str) -> str:
    return f"techprof_{document_id_value.removeprefix('brdoc_')}"


def taxonomy_candidate_id(document_id_value: str) -> str:
    return f"taxcand_{document_id_value.removeprefix('brdoc_')}"


def slice_id(document_id_value: str, suffix: str) -> str:
    return f"slice_{document_id_value.removeprefix('brdoc_')}_{suffix}"


def make_blocker(
    *,
    run_id: str,
    document_id: str | None,
    code: str,
    created_by_step: str,
    safe_message: str,
    review_action: str,
    severity: str = "blocking",
    blocks_next_gate: bool = True,
    reason: str | None = None,
) -> dict:
    if code not in BLOCKER_CODES:
        raise ValueError(f"unsupported blocker code: {code}")
    material = [run_id, document_id or "run", code, created_by_step, reason or ""]
    return {
        "blocker_id": f"blocker_{stable_digest(material, length=12)}",
        "run_id": run_id,
        "document_id": document_id,
        "code": code,
        "severity": severity,
        "blocks_gate2": blocks_next_gate,
        "blocks_next_gate": blocks_next_gate,
        "safe_message": safe_message,
        "review_action": review_action,
        "created_by_step": created_by_step,
        "reason_code": reason,
    }


def safety_flags() -> dict[str, bool]:
    return dict(SAFETY_FLAGS)
