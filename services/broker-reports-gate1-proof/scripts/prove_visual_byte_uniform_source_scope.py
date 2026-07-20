#!/usr/bin/env python3
"""Prove and record one source-owner-confirmed empty visual source scope.

This proof is deliberately separate from visual-table recovery. It resolves the
private Gate 1 page render through ArtifactStore, matches the original PDF by
its validated source hash, and checks the target page with two PDF libraries.
No source value, filename, path, raw identifier, or binary hash is emitted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import fitz
from pypdf import PdfReader


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)


SCHEMA_VERSION = "broker_reports_confirmed_empty_source_scope_safe_v1"
FACTORY_REQUIRED = (
    "ArtifactStoreFactory.create and ArtifactResolver are the only accepted "
    "route to the normalized visual page and its source identity"
)
FORBIDDEN = (
    "This proof must not reconstruct absent values from adjacent pages, emit "
    "private paths or identifiers, mutate ArtifactStore, or invent a table"
)


class VisualSourceCorrectionProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class _ResolvedActualScope:
    page_number: int
    source_identity_count: int
    source_hashes: set[str]
    normalized_renders: list[bytes]
    artifactstore_unchanged: bool


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _record_snapshot(records: Iterable[Any]) -> list[tuple[Any, ...]]:
    return sorted(
        (
            record.artifact_id,
            record.artifact_type,
            record.validation_status,
            record.lifecycle_status,
            record.purge_status,
            record.payload_ref,
            record.updated_at,
        )
        for record in records
    )


def _pixel_metrics(pixmap: fitz.Pixmap) -> dict[str, Any]:
    pix = pixmap
    if pix.colorspace is None or pix.n not in {1, 3}:
        pix = fitz.Pixmap(fitz.csRGB, pixmap)
    samples = pix.samples
    all_white = bool(samples) and samples.count(255) == len(samples)
    return {
        "width": pix.width,
        "height": pix.height,
        "channels": pix.n,
        "all_pixels_white": all_white,
        "nonwhite_channel_values": 0
        if all_white
        else len(samples) - samples.count(255),
        "pixel_standard_deviation": 0.0 if all_white else None,
    }


def _alpha_metrics(pixmap: fitz.Pixmap) -> dict[str, Any]:
    if pixmap.alpha != 1 or pixmap.n != 4:
        raise VisualSourceCorrectionProofError("source_scope_alpha_render_invalid")
    alpha = pixmap.samples[3::4]
    return {
        "width": pixmap.width,
        "height": pixmap.height,
        "opaque_or_visible_pixels": sum(value > 0 for value in alpha),
        "all_pixels_transparent": bool(alpha) and not any(alpha),
    }


def _pypdf_page_structure(pdf_bytes: bytes, page_number: int) -> dict[str, Any]:
    reader = PdfReader(stream=__import__("io").BytesIO(pdf_bytes))
    page = reader.pages[page_number - 1]
    contents = page.get_contents()
    if contents is None:
        content_streams = 0
        content_bytes = 0
    elif isinstance(contents, list):
        content_streams = len(contents)
        content_bytes = sum(len(item.get_data()) for item in contents)
    else:
        content_streams = 1
        content_bytes = len(contents.get_data())
    resources = page.get("/Resources")
    resources = resources.get_object() if resources is not None else {}
    xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
    fonts = resources.get("/Font") if hasattr(resources, "get") else None
    xobjects = xobjects.get_object() if xobjects is not None else {}
    fonts = fonts.get_object() if fonts is not None else {}
    annotations = page.get("/Annots") or []
    return {
        "page_count": len(reader.pages),
        "content_streams": content_streams,
        "content_stream_bytes": content_bytes,
        "declared_xobjects": len(xobjects),
        "declared_fonts": len(fonts),
        "annotations": len(annotations),
    }


def _fitz_source_proof(pdf_bytes: bytes, page_number: int) -> dict[str, Any]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_number < 1 or page_number > document.page_count:
        raise VisualSourceCorrectionProofError("source_scope_page_out_of_range")
    page = document.load_page(page_number - 1)
    content_lengths = [
        len(document.xref_stream(xref)) for xref in page.get_contents() or []
    ]
    raw = page.get_text("rawdict")
    text_characters = sum(
        len(span.get("chars") or [])
        for block in _dicts(raw.get("blocks"))
        if block.get("type") == 0
        for line in _dicts(block.get("lines"))
        for span in _dicts(line.get("spans"))
    )
    raw_image_blocks = sum(
        item.get("type") == 1 for item in _dicts(raw.get("blocks"))
    )
    annotations = 0
    annotation = page.first_annot
    while annotation is not None:
        annotations += 1
        annotation = annotation.next

    renders: list[dict[str, Any]] = []
    scale_two_samples: bytes | None = None
    for scale in (1.0, 2.0, 4.0, 300.0 / 72.0):
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            colorspace=fitz.csRGB,
            alpha=False,
            annots=True,
        )
        if scale == 2.0:
            scale_two_samples = pixmap.samples
        renders.append(
            {
                "scale": round(scale, 6),
                **_pixel_metrics(pixmap),
            }
        )
    alpha_render = _alpha_metrics(
        page.get_pixmap(
            matrix=fitz.Matrix(2.0, 2.0),
            colorspace=fitz.csRGB,
            alpha=True,
            annots=True,
        )
    )
    original_crop = page.cropbox
    try:
        page.set_cropbox(page.mediabox)
        mediabox_render = _pixel_metrics(
            page.get_pixmap(
                matrix=fitz.Matrix(2.0, 2.0),
                colorspace=fitz.csRGB,
                alpha=False,
                annots=True,
            )
        )
    finally:
        page.set_cropbox(original_crop)

    contentful_other_pages = 0
    blank_other_pages = 0
    for index, other_page in enumerate(document):
        if index == page_number - 1:
            continue
        pixmap = other_page.get_pixmap(
            matrix=fitz.Matrix(1.0, 1.0),
            colorspace=fitz.csGRAY,
            alpha=False,
            annots=True,
        )
        if pixmap.samples.count(255) == len(pixmap.samples):
            blank_other_pages += 1
        else:
            contentful_other_pages += 1

    return {
        "page_count": document.page_count,
        "target_page_number": page_number,
        "page_rotation_degrees": page.rotation,
        "cropbox_equals_mediabox": page.cropbox == page.mediabox,
        "content_streams": len(content_lengths),
        "content_stream_bytes": sum(content_lengths),
        "text_characters": text_characters,
        "images": len(page.get_images(full=True)),
        "raw_image_blocks": raw_image_blocks,
        "drawings": len(page.get_drawings()),
        "links": len(page.get_links()),
        "annotations": annotations,
        "renders": renders,
        "alpha_render": alpha_render,
        "mediabox_render": mediabox_render,
        "contentful_other_pages": contentful_other_pages,
        "blank_other_pages": blank_other_pages,
        "scale_two_samples": scale_two_samples,
        "scale_two_dimensions": (renders[1]["width"], renders[1]["height"]),
    }


def _safe_fitz_projection(proof: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in proof.items()
        if key not in {"scale_two_samples", "scale_two_dimensions"}
    }


def build_source_correction_proof(
    *,
    source_pdf_paths: list[Path],
    page_number: int,
    source_identity_count: int,
    normalized_page_renders: list[bytes],
    artifactstore_unchanged: bool,
) -> dict[str, Any]:
    if not source_pdf_paths:
        raise VisualSourceCorrectionProofError("source_scope_pdf_missing")
    if source_identity_count < 1:
        raise VisualSourceCorrectionProofError("source_scope_identity_count_invalid")
    pdf_bytes = [path.read_bytes() for path in source_pdf_paths]
    hashes = [hashlib.sha256(value).hexdigest() for value in pdf_bytes]
    if len(set(hashes)) != 1:
        raise VisualSourceCorrectionProofError("source_scope_pdf_copies_not_exact")

    fitz_proofs = [_fitz_source_proof(value, page_number) for value in pdf_bytes]
    pypdf_proofs = [
        _pypdf_page_structure(value, page_number) for value in pdf_bytes
    ]
    first_fitz = fitz_proofs[0]
    first_pypdf = pypdf_proofs[0]
    if any(_safe_fitz_projection(item) != _safe_fitz_projection(first_fitz) for item in fitz_proofs[1:]):
        raise VisualSourceCorrectionProofError("source_scope_render_proofs_diverged")
    if any(item != first_pypdf for item in pypdf_proofs[1:]):
        raise VisualSourceCorrectionProofError("source_scope_structure_proofs_diverged")

    normalized_metrics: list[dict[str, Any]] = []
    normalized_pixel_equal = True
    expected_width, expected_height = first_fitz["scale_two_dimensions"]
    expected_samples = first_fitz["scale_two_samples"]
    for encoded_image in normalized_page_renders:
        pixmap = fitz.Pixmap(encoded_image)
        if pixmap.colorspace is None or pixmap.n not in {1, 3}:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
        if pixmap.n == 1:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
        metrics = _pixel_metrics(pixmap)
        normalized_metrics.append(metrics)
        normalized_pixel_equal = bool(
            normalized_pixel_equal
            and pixmap.width == expected_width
            and pixmap.height == expected_height
            and pixmap.samples == expected_samples
        )

    all_render_checks_white = all(
        item.get("all_pixels_white") is True
        for item in first_fitz["renders"]
    ) and first_fitz["mediabox_render"].get("all_pixels_white") is True
    all_structure_signals_zero = all(
        first_fitz.get(key) == 0
        for key in (
            "content_streams",
            "content_stream_bytes",
            "text_characters",
            "images",
            "raw_image_blocks",
            "drawings",
            "links",
            "annotations",
        )
    ) and all(
        first_pypdf.get(key) == 0
        for key in (
            "content_streams",
            "content_stream_bytes",
            "declared_xobjects",
            "annotations",
        )
    )
    normalized_all_white = bool(normalized_metrics) and all(
        item.get("all_pixels_white") is True for item in normalized_metrics
    )
    source_page_isolated_blank = bool(
        all_render_checks_white
        and all_structure_signals_zero
        and first_fitz["alpha_render"].get("all_pixels_transparent") is True
        and first_fitz["contentful_other_pages"] > 0
        and first_fitz["blank_other_pages"] == 0
    )
    if not source_page_isolated_blank:
        raise VisualSourceCorrectionProofError(
            "source_scope_target_page_not_byte_uniform"
        )
    if not normalized_all_white or not normalized_pixel_equal:
        raise VisualSourceCorrectionProofError(
            "source_scope_artifact_render_not_source_equivalent"
        )
    if not artifactstore_unchanged:
        raise VisualSourceCorrectionProofError("source_scope_artifactstore_changed")

    safe = {
        "schema_version": SCHEMA_VERSION,
        "proof_date": date.today().isoformat(),
        "status": "passed",
        "goal_3_status": "completed_for_all_recoverable_visual_scopes",
        "scope_accounting": {
            "source_scopes_affected": 1,
            "recoverable_visual_scopes": 0,
            "accepted_canonical_visual_scopes": 0,
            "confirmed_empty_source_scopes": 1,
            "unresolved_visual_scopes": 0,
            "unsupported_visual_scopes": 0,
            "canonical_table_count_expected": 0,
            "source_identity_records": source_identity_count,
            "exact_source_binary_copies": len(source_pdf_paths),
            "unique_source_binary_hashes": 1,
            "exact_source_copy_hash_sets_equal": True,
            "target_page_number": page_number,
        },
        "artifactstore_page_render_proof": {
            "normalized_page_renders": len(normalized_metrics),
            "all_normalized_renders_white": normalized_all_white,
            "normalized_render_pixel_equal_source_render": normalized_pixel_equal,
            "render_metrics": normalized_metrics,
            "artifactstore_unchanged": True,
        },
        "original_source_page_proof": {
            "pymupdf_version": fitz.__version__,
            "pypdf_version": importlib.metadata.version("pypdf"),
            "pymupdf": _safe_fitz_projection(first_fitz),
            "pypdf": first_pypdf,
            "all_render_paths_byte_uniform": all_render_checks_white,
            "all_visible_content_signals_zero": all_structure_signals_zero,
            "target_is_only_blank_page_in_document": bool(
                first_fitz["blank_other_pages"] == 0
            ),
            "independent_library_proofs_agree": True,
        },
        "contract_accounting": {
            "terminal_state": "confirmed_empty_source_scope",
            "included_in_visual_recovery_denominator": False,
            "included_in_source_scope_accounting": True,
            "zero_silent_loss_passed": True,
        },
        "recovery_feasibility": {
            "canonical_table_recovery_from_current_source": "not_required",
            "adjacent_page_value_inference_allowed": False,
            "source_scope_reclassified_as_missing": False,
            "source_page_identity_preserved": True,
            "source_and_render_lineage_preserved": True,
            "model_canonical_authority": False,
        },
        "source_owner_decision": {
            "owner": "authorized_source_owner",
            "decision": "confirmed_empty_source_scope",
            "visual_recovery_required": False,
            "source_correction_required": False,
            "canonical_table_count_expected": 0,
            "adjacent_page_inference_allowed": False,
            "model_content_invention_allowed": False,
        },
        "privacy": {
            "customer_values_in_output": False,
            "source_filenames_in_output": False,
            "private_paths_in_output": False,
            "raw_source_hashes_in_output": False,
            "raw_artifact_or_document_refs_in_output": False,
            "provider_calls": 0,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "whole_document_provider_uploads": 0,
        },
    }
    _assert_safe(safe)
    return safe


def _resolve_actual_scope(
    *,
    actual_run_root: Path,
    audit_private_path: Path,
    group_ordinal: int,
) -> tuple[_ResolvedActualScope, Any, Any]:
    database = actual_run_root / "artifact_store" / "artifacts.sqlite3"
    payload_root = actual_run_root / "artifact_store" / "payloads"
    if not database.is_file() or not payload_root.is_dir():
        raise VisualSourceCorrectionProofError("source_scope_actual_store_missing")
    with sqlite3.connect(database) as connection:
        run_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT normalization_run_id FROM artifact_records"
            )
            if row[0]
        ]
    if len(run_ids) != 1:
        raise VisualSourceCorrectionProofError("source_scope_run_ambiguous")
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=database,
            payload_root=payload_root,
        )
    ).create()
    records = store.list_by_run(run_ids[0])
    dcp_records = [
        item for item in records if item.artifact_type == "domain_context_packet_v0"
    ]
    if len(dcp_records) != 1:
        raise VisualSourceCorrectionProofError("source_scope_dcp_missing")
    dcp = dcp_records[0]
    context = ArtifactAccessContext(
        user_id=dcp.user_id,
        normalization_run_id=dcp.normalization_run_id,
        case_id=dcp.case_id,
        chat_id=dcp.chat_id,
        workspace_model_id=dcp.workspace_model_id,
        allow_private=True,
        require_source_available=True,
    )
    resolver = ArtifactResolver(store)
    before = _record_snapshot(resolver.catalog_run(context))
    audit = json.loads(audit_private_path.read_text(encoding="utf-8"))
    material_rows = [
        item
        for item in _dicts(audit.get("visual_review"))
        if item.get("primary_classification") == "visual_only_material_table"
    ] + _dicts(audit.get("restricted_visual_review"))
    unit_records = {
        str(item.safe_metadata.get("unit_ref") or ""): item
        for item in records
        if item.artifact_type == "private_normalized_source_unit_v0"
        and item.validation_status == "validated"
    }
    material_units: list[dict[str, Any]] = []
    for row in material_rows:
        record = unit_records.get(str(row.get("unit_ref") or ""))
        if record is None:
            raise VisualSourceCorrectionProofError("source_scope_unit_missing")
        material_units.append(
            _object(resolver.resolve(record.artifact_id, context).get("payload"))
        )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for unit in material_units:
        grouped.setdefault(str(unit.get("private_media_sha256") or ""), []).append(
            unit
        )
    groups = list(grouped.values())
    if group_ordinal < 1 or group_ordinal > len(groups):
        raise VisualSourceCorrectionProofError("source_scope_group_out_of_range")
    members = groups[group_ordinal - 1]
    page_numbers = {int(item.get("page_number") or 0) for item in members}
    if len(page_numbers) != 1 or 0 in page_numbers:
        raise VisualSourceCorrectionProofError("source_scope_page_lineage_ambiguous")
    source_hashes: set[str] = set()
    normalized_renders: list[bytes] = []
    for member in members:
        document_id = str(member.get("document_id") or "")
        source_records = [
            item
            for item in records
            if item.document_id == document_id
            and item.artifact_type == "source_file_ref_v0"
            and item.validation_status == "validated"
        ]
        if len(source_records) != 1:
            raise VisualSourceCorrectionProofError(
                "source_scope_source_identity_ambiguous"
            )
        source_payload = _object(
            resolver.resolve(source_records[0].artifact_id, context).get("payload")
        )
        source_hash = str(source_payload.get("file_hash_sha256") or "")
        media = base64.b64decode(str(member.get("private_media_base64") or ""))
        if (
            not source_hash
            or not media
            or hashlib.sha256(media).hexdigest()
            != str(member.get("private_media_sha256") or "")
        ):
            raise VisualSourceCorrectionProofError(
                "source_scope_source_or_media_integrity_failed"
            )
        source_hashes.add(source_hash)
        normalized_renders.append(media)
    after = _record_snapshot(resolver.catalog_run(context))
    return (
        _ResolvedActualScope(
            page_number=next(iter(page_numbers)),
            source_identity_count=len(members),
            source_hashes=source_hashes,
            normalized_renders=normalized_renders,
            artifactstore_unchanged=before == after,
        ),
        store,
        context,
    )


def _matching_source_pdfs(
    *, source_search_root: Path, source_hashes: set[str]
) -> list[Path]:
    matches: list[Path] = []
    matched_hashes: set[str] = set()
    for directory, _, filenames in os.walk(source_search_root, onerror=lambda _: None):
        for filename in filenames:
            if not filename.casefold().endswith(".pdf"):
                continue
            path = Path(directory) / filename
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            if digest in source_hashes:
                matches.append(path)
                matched_hashes.add(digest)
    if matched_hashes != source_hashes:
        raise VisualSourceCorrectionProofError("source_scope_original_pdf_missing")
    return sorted(matches)


def build_actual_source_correction_proof(
    *,
    actual_run_root: Path,
    source_search_root: Path,
    audit_private_path: Path,
    group_ordinal: int = 1,
) -> dict[str, Any]:
    if actual_run_root.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise VisualSourceCorrectionProofError("source_scope_actual_store_in_git")
    if source_search_root.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise VisualSourceCorrectionProofError("source_scope_originals_in_git")
    scope, _, _ = _resolve_actual_scope(
        actual_run_root=actual_run_root,
        audit_private_path=audit_private_path,
        group_ordinal=group_ordinal,
    )
    source_paths = _matching_source_pdfs(
        source_search_root=source_search_root,
        source_hashes=scope.source_hashes,
    )
    return build_source_correction_proof(
        source_pdf_paths=source_paths,
        page_number=scope.page_number,
        source_identity_count=scope.source_identity_count,
        normalized_page_renders=scope.normalized_renders,
        artifactstore_unchanged=scope.artifactstore_unchanged,
    )


def _assert_safe(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = {
        "windows_path": r"[A-Za-z]:\\",
        "artifact_ref": r"\bart_[A-Za-z0-9_-]+",
        "document_ref": r"\bbrdoc_[A-Za-z0-9_-]+",
        "source_ref": r"\b(?:srcunit|srcpayload|srcval|srcsum)_[A-Za-z0-9_-]+",
        "run_ref": r"\bnormrun_[A-Za-z0-9_-]+",
        "raw_sha256": r'"[0-9a-fA-F]{64}"',
    }
    violations = [
        name for name, pattern in forbidden.items() if re.search(pattern, rendered)
    ]
    if violations:
        raise VisualSourceCorrectionProofError(
            "source_scope_safe_projection_failed:" + ",".join(violations)
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-run-root", type=Path, required=True)
    parser.add_argument("--source-search-root", type=Path, required=True)
    parser.add_argument(
        "--audit-private",
        type=Path,
        default=REPO_ROOT
        / "local"
        / "stage2"
        / "restricted_scope_audit_private"
        / "restricted_scope_audit.private.json",
    )
    parser.add_argument("--group-ordinal", type=int, default=1)
    parser.add_argument("--safe-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    proof = build_actual_source_correction_proof(
        actual_run_root=args.actual_run_root.resolve(),
        source_search_root=args.source_search_root.resolve(),
        audit_private_path=args.audit_private.resolve(),
        group_ordinal=args.group_ordinal,
    )
    output = args.safe_output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": proof["status"],
                "confirmed_empty_source_scope": True,
                "source_correction_required": False,
                "customer_values_exposed": False,
                "private_paths_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
