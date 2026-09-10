#!/usr/bin/env python3
"""Run one isolated native Mistral table-continuation annotation experiment.

This script is an R&D coordinator only.  It does not import a Pipe, create a
chat, write an ArtifactStore object, or build a Canonical.  The existing PDF
Document AI factory remains the sole owner of live provider configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_document_ai import (  # noqa: E402
    PdfDocumentExtractionError,
    PdfDocumentExtractorFactory,
    PdfSourceContext,
)
from broker_reports_gate1.profilers_pdf import profile_pdf  # noqa: E402


SAFE_RECEIPT_SCHEMA_VERSION = "goal391_native_table_annotation_lab_receipt_v1"
PRIVATE_EVIDENCE_SCHEMA_VERSION = "goal391_native_table_annotation_evidence_v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class NativeTableAnnotationLabError(RuntimeError):
    """A value-free terminal for invalid lab setup."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _require_new_external_path(path: Path, *, repo_root: Path = REPO_ROOT) -> Path:
    resolved = path.resolve()
    if _is_within(resolved, repo_root):
        raise NativeTableAnnotationLabError("goal391_annotation_output_inside_repository")
    if resolved.exists() or not resolved.parent.is_dir():
        raise NativeTableAnnotationLabError("goal391_annotation_output_must_be_new")
    return resolved


def _parse_zero_based_pages(value: str, *, source_page_count: int) -> tuple[int, ...]:
    if type(source_page_count) is not int or source_page_count < 1:
        raise NativeTableAnnotationLabError("goal391_annotation_source_page_count_invalid")
    try:
        pages = tuple(int(part) for part in value.split(","))
    except (AttributeError, ValueError):
        raise NativeTableAnnotationLabError("goal391_annotation_selected_pages_invalid") from None
    if (
        not pages
        or len(pages) > 8
        or pages != tuple(sorted(set(pages)))
        or any(page < 0 or page >= source_page_count for page in pages)
    ):
        raise NativeTableAnnotationLabError("goal391_annotation_selected_pages_invalid")
    return pages


def _read_source(*, source_pdf: Path, expected_sha256: str, source_page_count: int) -> bytes:
    if not _SHA256.fullmatch(expected_sha256):
        raise NativeTableAnnotationLabError("goal391_annotation_expected_source_sha256_invalid")
    if not source_pdf.is_file():
        raise NativeTableAnnotationLabError("goal391_annotation_source_pdf_missing")
    try:
        source_bytes = source_pdf.read_bytes()
    except OSError:
        raise NativeTableAnnotationLabError("goal391_annotation_source_pdf_unreadable") from None
    if _sha256_bytes(source_bytes) != expected_sha256:
        raise NativeTableAnnotationLabError("goal391_annotation_source_sha256_mismatch")
    profile, _items, blockers = profile_pdf(
        run_id="goal391_annotation_lab",
        document_id="goal391_annotation_source",
        content_bytes=source_bytes,
    )
    if blockers or profile.get("profile_status") != "preflight_passed":
        raise NativeTableAnnotationLabError("goal391_annotation_source_pdf_invalid")
    if profile.get("pages_count") != source_page_count:
        raise NativeTableAnnotationLabError("goal391_annotation_source_page_count_mismatch")
    return source_bytes


def _read_prompt(prompt_file: Path) -> str:
    if not prompt_file.is_file():
        raise NativeTableAnnotationLabError("goal391_annotation_prompt_missing")
    try:
        prompt = prompt_file.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        raise NativeTableAnnotationLabError("goal391_annotation_prompt_invalid") from None
    if not prompt.strip():
        raise NativeTableAnnotationLabError("goal391_annotation_prompt_invalid")
    return prompt


async def _ordinary_user_and_request(*, ordinary_user_id: str) -> tuple[Any, Any]:
    if not isinstance(ordinary_user_id, str) or not ordinary_user_id.strip():
        raise NativeTableAnnotationLabError("goal391_annotation_ordinary_user_id_invalid")
    from open_webui.models.users import Users

    result = await Users.get_users()
    users = result.get("users", []) if isinstance(result, Mapping) else []
    user = next(
        (
            candidate
            for candidate in users
            if getattr(candidate, "id", None) == ordinary_user_id
            and getattr(candidate, "role", None) == "user"
        ),
        None,
    )
    if user is None:
        raise NativeTableAnnotationLabError("goal391_annotation_ordinary_user_unavailable")

    from open_webui.main import app
    from starlette.requests import Request

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/chat/completions",
            "raw_path": b"/api/chat/completions",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 80),
            "app": app,
        }
    )
    return user, request


def _safe_receipt(
    *,
    status: str,
    terminal: str,
    source_sha256: str | None,
    source_bytes_total: int,
    source_page_count: int | None,
    selected_pages: tuple[int, ...] | None,
    prompt: str | None,
    annotation_attempts_started_total: int,
    annotation_responses_validated_total: int,
    extractor: Any | None = None,
    evidence_written: bool = False,
    raw_response: bytes | None = None,
) -> dict[str, object]:
    """Return a receipt containing only terminal state, hashes, and counts."""
    receipt: dict[str, object] = {
        "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
        "status": status,
        "terminal": terminal,
        "annotation_attempts_started_total": annotation_attempts_started_total,
        "annotation_responses_validated_total": annotation_responses_validated_total,
        "source_bytes_total": source_bytes_total,
        "private_evidence_written": evidence_written,
    }
    if source_sha256 is not None:
        receipt["source_sha256"] = source_sha256
    if source_page_count is not None:
        receipt["source_pages_total"] = source_page_count
    if selected_pages is not None:
        receipt["selected_pages_total"] = len(selected_pages)
        receipt["selected_pages_sha256"] = _canonical_sha256(list(selected_pages))
    if prompt is not None:
        receipt["annotation_prompt_sha256"] = _sha256_bytes(prompt.encode("utf-8"))
        receipt["annotation_prompt_bytes_total"] = len(prompt.encode("utf-8"))
    if extractor is not None:
        receipt["adapter_id"] = str(getattr(extractor, "adapter_id", ""))
    if raw_response is not None:
        receipt["raw_response_sha256"] = _sha256_bytes(raw_response)
        receipt["raw_response_bytes_total"] = len(raw_response)
    return receipt


def _private_evidence(*, result: Any, prompt: str) -> dict[str, object]:
    """Keep the provider-derived material private for a later human visual audit."""
    extraction = result.extraction
    assessment = result.assessment
    return {
        "schema_version": PRIVATE_EVIDENCE_SCHEMA_VERSION,
        "source_pdf_sha256": extraction.source_pdf_sha256,
        "document_annotation_prompt": prompt,
        "selected_zero_based_pages": list(assessment.source_page_numbers),
        "response_binding": {
            "raw_annotation_sha256": assessment.raw_annotation_sha256,
            "table_refs_sha256": assessment.table_refs_sha256,
            "request_parameters_sha256": assessment.request_parameters_sha256,
            "selected_page_bindings_sha256": (
                assessment.selected_page_bindings_sha256
            ),
        },
        "page_markdown": [
            {
                "local_page_number": page_number,
                "markdown": markdown.decode("utf-8", errors="strict"),
            }
            for page_number, markdown in zip(
                extraction.page_numbers,
                extraction.page_markdown_bytes,
                strict=True,
            )
        ],
        "tables": [
            {
                "local_ref": table.local_ref,
                "local_page_number": table.page_number,
                "native_table_id": table.markdown_target,
                "html": table.html_bytes.decode("utf-8", errors="strict"),
            }
            for table in extraction.table_refs
        ],
        "continuation_links": [
            {
                "parent_table_ref": link.parent_table_ref,
                "child_table_ref": link.child_table_ref,
            }
            for link in assessment.links
        ],
    }


def _write_json_new(path: Path, value: Mapping[str, object]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _write_private_bytes_new(path: Path, value: bytes) -> None:
    """Write provider bytes once with owner-only permissions outside Git."""

    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise NativeTableAnnotationLabError(
            "goal391_annotation_private_response_write_failed"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)


async def _preflight(args: argparse.Namespace) -> tuple[bytes, str, tuple[int, ...], Any]:
    source_bytes = _read_source(
        source_pdf=args.source_pdf.resolve(),
        expected_sha256=args.expected_source_sha256,
        source_page_count=args.source_page_count,
    )
    prompt = _read_prompt(args.prompt_file.resolve())
    selected_pages = _parse_zero_based_pages(
        args.selected_zero_based_pages,
        source_page_count=args.source_page_count,
    )
    _user, request = await _ordinary_user_and_request(
        ordinary_user_id=args.ordinary_user_id,
    )
    extractor = PdfDocumentExtractorFactory.create(server_request=request)
    required_method = (
        "capture_unvalidated_table_annotation_response_once"
        if args.capture_one_unvalidated_response
        else "extract_with_table_continuation_assessment"
    )
    if not callable(getattr(extractor, required_method, None)):
        raise NativeTableAnnotationLabError("goal391_annotation_method_unavailable")
    return source_bytes, prompt, selected_pages, extractor


async def run(args: argparse.Namespace) -> dict[str, object]:
    source_bytes_total = 0
    source_sha256: str | None = None
    prompt: str | None = None
    selected_pages: tuple[int, ...] | None = None
    extractor: Any | None = None
    annotation_attempts_started_total = 0
    annotation_responses_validated_total = 0
    try:
        source_bytes, prompt, selected_pages, extractor = await _preflight(args)
        source_bytes_total = len(source_bytes)
        source_sha256 = _sha256_bytes(source_bytes)
        if args.preflight_only:
            return _safe_receipt(
                status="PREFLIGHT_PASSED",
                terminal="READY",
                source_sha256=source_sha256,
                source_bytes_total=source_bytes_total,
                source_page_count=args.source_page_count,
                selected_pages=selected_pages,
                prompt=prompt,
                annotation_attempts_started_total=0,
                annotation_responses_validated_total=0,
                extractor=extractor,
            )

        context = PdfSourceContext(
            document_ref="goal391_native_table_annotation_lab",
            expected_pdf_sha256=source_sha256,
            preflight_page_count=args.source_page_count,
        )
        annotation_attempts_started_total = 1
        if args.capture_one_unvalidated_response:
            raw_response = extractor.capture_unvalidated_table_annotation_response_once(
                source_bytes,
                context,
                source_page_numbers=selected_pages,
                document_annotation_prompt=prompt,
            )
            _write_private_bytes_new(args.private_raw_response, raw_response)
            return _safe_receipt(
                status="RAW_RESPONSE_CAPTURED_AWAITING_PRIVATE_AUDIT",
                terminal="ONE_CLEAN_CALL_RAW_RESPONSE_READY",
                source_sha256=source_sha256,
                source_bytes_total=source_bytes_total,
                source_page_count=args.source_page_count,
                selected_pages=selected_pages,
                prompt=prompt,
                annotation_attempts_started_total=annotation_attempts_started_total,
                annotation_responses_validated_total=0,
                extractor=extractor,
                evidence_written=True,
                raw_response=raw_response,
            )
        result = extractor.extract_with_table_continuation_assessment(
            source_bytes,
            context,
            source_page_numbers=selected_pages,
            document_annotation_prompt=prompt,
        )
        annotation_responses_validated_total = 1
        _write_json_new(args.private_evidence, _private_evidence(result=result, prompt=prompt))
        return _safe_receipt(
            status="COMPLETED_AWAITING_VISUAL_AUDIT",
            terminal="ONE_CLEAN_CALL_EVIDENCE_READY",
            source_sha256=source_sha256,
            source_bytes_total=source_bytes_total,
            source_page_count=args.source_page_count,
            selected_pages=selected_pages,
            prompt=prompt,
            annotation_attempts_started_total=annotation_attempts_started_total,
            annotation_responses_validated_total=annotation_responses_validated_total,
            extractor=extractor,
            evidence_written=True,
        )
    except PdfDocumentExtractionError as exc:
        return _safe_receipt(
            status="FAILED",
            terminal=exc.code,
            source_sha256=source_sha256,
            source_bytes_total=source_bytes_total,
            source_page_count=getattr(args, "source_page_count", None),
            selected_pages=selected_pages,
            prompt=prompt,
            annotation_attempts_started_total=annotation_attempts_started_total,
            annotation_responses_validated_total=annotation_responses_validated_total,
            extractor=extractor,
        )
    except NativeTableAnnotationLabError as exc:
        return _safe_receipt(
            status="FAILED",
            terminal=str(exc),
            source_sha256=source_sha256,
            source_bytes_total=source_bytes_total,
            source_page_count=getattr(args, "source_page_count", None),
            selected_pages=selected_pages,
            prompt=prompt,
            annotation_attempts_started_total=annotation_attempts_started_total,
            annotation_responses_validated_total=annotation_responses_validated_total,
            extractor=extractor,
        )
    except Exception as exc:
        return _safe_receipt(
            status="FAILED",
            terminal=type(exc).__name__,
            source_sha256=source_sha256,
            source_bytes_total=source_bytes_total,
            source_page_count=getattr(args, "source_page_count", None),
            selected_pages=selected_pages,
            prompt=prompt,
            annotation_attempts_started_total=annotation_attempts_started_total,
            annotation_responses_validated_total=annotation_responses_validated_total,
            extractor=extractor,
        )


def _public_summary(receipt: Mapping[str, object]) -> dict[str, object]:
    return {
        key: receipt[key]
        for key in (
            "status",
            "terminal",
            "annotation_attempts_started_total",
            "annotation_responses_validated_total",
            "source_pages_total",
            "selected_pages_total",
            "private_evidence_written",
        )
        if key in receipt
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight-only", action="store_true")
    modes.add_argument("--execute-one-clean-call", action="store_true")
    modes.add_argument("--capture-one-unvalidated-response", action="store_true")
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--source-page-count", type=int, required=True)
    parser.add_argument("--selected-zero-based-pages", required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--ordinary-user-id", required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    parser.add_argument("--private-evidence", type=Path)
    parser.add_argument("--private-raw-response", type=Path)
    args = parser.parse_args()
    try:
        args.safe_receipt = _require_new_external_path(args.safe_receipt)
        if args.capture_one_unvalidated_response:
            if args.private_evidence is not None or args.private_raw_response is None:
                raise NativeTableAnnotationLabError(
                    "goal391_annotation_private_output_mode_invalid"
                )
            args.private_raw_response = _require_new_external_path(
                args.private_raw_response
            )
        elif args.private_raw_response is not None or args.private_evidence is None:
            raise NativeTableAnnotationLabError(
                "goal391_annotation_private_output_mode_invalid"
            )
        else:
            args.private_evidence = _require_new_external_path(args.private_evidence)
    except NativeTableAnnotationLabError as exc:
        raise SystemExit(str(exc)) from None
    receipt = asyncio.run(run(args))
    _write_json_new(args.safe_receipt, receipt)
    print(json.dumps(_public_summary(receipt), ensure_ascii=False, sort_keys=True))
    return (
        0
        if receipt["status"]
        in {
            "PREFLIGHT_PASSED",
            "COMPLETED_AWAITING_VISUAL_AUDIT",
            "RAW_RESPONSE_CAPTURED_AWAITING_PRIVATE_AUDIT",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
