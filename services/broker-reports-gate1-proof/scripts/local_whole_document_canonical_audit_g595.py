#!/usr/bin/env python3
"""Project frozen G5.94 Markdown and score the private G5.95 visual audit.

The adapter is deliberately research-only.  It receives only a page ordinal and
the frozen primary Markdown.  PDF bytes, Variant A and financial context are not
arguments and cannot influence projection.  Raw literals and page-level review
remain in caller-selected local/private files; the safe result contains counts,
hashes and terminal verdicts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "whole_document_canonical_audit_g595"
    / "manifest.json"
)
MANIFEST_SCHEMA = "broker_reports_whole_document_canonical_audit_g595_manifest_v1"
PROJECTION_SCHEMA = "broker_reports_markdown_canonical_compatible_g595_private_v1"
REVIEW_SCHEMA = "broker_reports_whole_document_visual_review_g595_private_v1"
SAFE_SCHEMA = "broker_reports_whole_document_canonical_audit_g595_safe_v1"

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_DELIMITER_CELL_RE = re.compile(r"^:?-{3,}:?$")


class G595Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    project = subparsers.add_parser("project")
    project.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    project.add_argument("--g594-private-dir", required=True)
    project.add_argument("--private-output", required=True)
    score = subparsers.add_parser("score")
    score.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    score.add_argument("--projection", required=True)
    score.add_argument("--review", required=True)
    score.add_argument("--safe-output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "project":
            result = project_document(
                manifest_path=Path(args.manifest),
                g594_private_dir=Path(args.g594_private_dir),
                private_output=Path(args.private_output),
            )
        else:
            result = score_document(
                manifest_path=Path(args.manifest),
                projection_path=Path(args.projection),
                review_path=Path(args.review),
                safe_output=Path(args.safe_output),
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, G595Error) else type(exc).__name__
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def project_markdown_page(page_number: int, markdown: str | None) -> dict[str, Any]:
    """Mechanically move explicit Markdown blocks into a common audit shape."""
    if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
        raise G595Error("g595_page_number_invalid")
    if markdown is None:
        return {
            "page": page_number,
            "status": "unavailable",
            "nodes": [],
            "capabilities": _b_capabilities(),
        }
    if not isinstance(markdown, str) or not markdown.strip() or "\x00" in markdown:
        raise G595Error("g595_markdown_invalid")

    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nodes: list[dict[str, Any]] = []
    paragraph: list[str] = []
    index = 0

    def flush_text() -> None:
        if not paragraph:
            return
        nodes.append(
            {
                "type": "TEXT",
                "order": len(nodes),
                "literal": "\n".join(paragraph),
            }
        )
        paragraph.clear()

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            flush_text()
            index += 1
            continue
        heading = _HEADING_RE.fullmatch(line)
        if heading:
            flush_text()
            nodes.append(
                {
                    "type": "HEADING",
                    "order": len(nodes),
                    "level": len(heading.group(1)),
                    "literal": heading.group(2),
                }
            )
            index += 1
            continue
        table = _explicit_table_at(lines, index)
        if table is not None:
            flush_text()
            node, index = table
            node["order"] = len(nodes)
            nodes.append(node)
            continue
        paragraph.append(line)
        index += 1
    flush_text()
    return {
        "page": page_number,
        "status": "represented",
        "nodes": nodes,
        "capabilities": _b_capabilities(),
    }


def _explicit_table_at(
    lines: list[str], index: int
) -> tuple[dict[str, Any], int] | None:
    if index + 1 >= len(lines):
        return None
    header = _split_table_row(lines[index])
    delimiter = _split_table_row(lines[index + 1])
    if header is None or delimiter is None or len(header) != len(delimiter):
        return None
    if not delimiter or not all(_DELIMITER_CELL_RE.fullmatch(cell) for cell in delimiter):
        return None

    rows = [_row(0, "HEADER", header)]
    cursor = index + 2
    body_ordinal = 0
    while cursor < len(lines):
        cells = _split_table_row(lines[cursor])
        if cells is None or len(cells) != len(header):
            break
        rows.append(_row(body_ordinal, "BODY", cells))
        body_ordinal += 1
        cursor += 1
    return (
        {
            "type": "TABLE",
            "order": -1,
            "column_count": len(header),
            "rows": rows,
        },
        cursor,
    )


def _split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if "|" not in stripped:
        return None
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    current_text = "".join(current).strip()
    cells.append(current_text)
    return cells if len(cells) >= 2 else None


def _row(ordinal: int, role: str, cells: list[str]) -> dict[str, Any]:
    return {
        "type": "ROW",
        "order": ordinal,
        "role": role,
        "cells": [
            {"type": "CELL", "column": column, "literal": literal}
            for column, literal in enumerate(cells)
        ],
    }


def _b_capabilities() -> dict[str, bool]:
    return {
        "page_identity": True,
        "node_order": True,
        "markdown_line_identity": True,
        "source_coordinates": False,
        "pdf_cell_path": False,
        "glyph_or_word_refs": False,
    }


def project_document(
    *, manifest_path: Path, g594_private_dir: Path, private_output: Path
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    selection = manifest["selection"]
    document_id = selection["selected_document_id"]
    pages = int(selection["pages"])
    projected_pages = []
    source_hashes = []
    for page_number in range(1, pages + 1):
        source = (
            g594_private_dir
            / "variant_b_slots"
            / f"{document_id}_p{page_number:03d}_run1.result.private.json"
        )
        result = _read_object(source)
        slot = result.get("slot") or {}
        if (
            slot.get("document_id") != document_id
            or slot.get("page_number") != page_number
            or slot.get("run_ordinal") != 1
            or slot.get("response_selection_eligible") is not False
        ):
            raise G595Error("g595_primary_slot_binding_invalid")
        markdown = result.get("markdown")
        if markdown is not None and result.get("validation_error") is not None:
            raise G595Error("g595_primary_result_terminal_invalid")
        projected_pages.append(project_markdown_page(page_number, markdown))
        source_hashes.append(_sha256_bytes(source.read_bytes()))

    projection = {
        "schema_version": PROJECTION_SCHEMA,
        "goal": "G5.95",
        "manifest_sha256": _sha256_json(manifest),
        "document_id": document_id,
        "pages": projected_pages,
        "source_primary_result_sha256": source_hashes,
        "adapter_inputs": ["page_number", "primary_markdown_or_unavailable"],
        "pdf_or_variant_a_used": False,
    }
    _write_json(private_output, projection)
    counts = _projection_counts(projection)
    return {
        "status": "projected",
        "document_id": document_id,
        **counts,
        "projection_sha256": _sha256_json(projection),
    }


def score_document(
    *,
    manifest_path: Path,
    projection_path: Path,
    review_path: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    projection = _read_object(projection_path)
    review = _read_object(review_path)
    _validate_projection(projection, manifest)
    _validate_review(review, manifest, projection)
    aggregate = {
        arm: _aggregate_arm(review["pages"], arm) for arm in ("A", "B")
    }
    terminal = _terminal(aggregate, review["adapter_verdict"])
    safe = {
        "schema_version": SAFE_SCHEMA,
        "goal": "G5.95",
        "manifest_sha256": _sha256_json(manifest),
        "selection": manifest["selection"],
        "reviewed_pages": len(review["pages"]),
        "page_ordinals_complete": True,
        "projection": _projection_counts(projection),
        "provenance_capabilities": {
            "A_frozen": {
                "page_identity": True,
                "node_order": True,
                "source_coordinates": True,
                "pdf_cell_path": True,
                "glyph_or_word_refs": True,
            },
            "B_adapter": _b_capabilities(),
        },
        "coverage": aggregate,
        "adapter_verdict": review["adapter_verdict"],
        "architecture_verdict": review["architecture_verdict"],
        "terminals": terminal,
        "scope": {
            "variant_a_parser_changes": 0,
            "variant_b_retries": 0,
            "variant_b_prompt_or_model_changes": 0,
            "hybrid_designs": 0,
            "gate3_plus_changes": 0,
            "raw_customer_text_in_safe_output": False,
        },
        "private_projection_sha256": _sha256_json(projection),
        "private_review_sha256": _sha256_json(review),
    }
    _write_json(safe_output, safe)
    return {
        "status": "scored",
        "reviewed_pages": len(review["pages"]),
        "adapter_verdict": review["adapter_verdict"],
        "terminals": terminal,
        "safe_sha256": _sha256_json(safe),
    }


def _projection_counts(projection: dict[str, Any]) -> dict[str, int]:
    pages = projection["pages"]
    nodes = [node for page in pages for node in page["nodes"]]
    tables = [node for node in nodes if node["type"] == "TABLE"]
    return {
        "pages": len(pages),
        "represented_pages": sum(page["status"] == "represented" for page in pages),
        "unavailable_pages": sum(page["status"] == "unavailable" for page in pages),
        "heading_nodes": sum(node["type"] == "HEADING" for node in nodes),
        "text_nodes": sum(node["type"] == "TEXT" for node in nodes),
        "table_nodes": len(tables),
        "body_rows": sum(
            row["role"] == "BODY" for table in tables for row in table["rows"]
        ),
        "cells": sum(len(row["cells"]) for table in tables for row in table["rows"]),
    }


def _validate_projection(projection: dict[str, Any], manifest: dict[str, Any]) -> None:
    if projection.get("schema_version") != PROJECTION_SCHEMA:
        raise G595Error("g595_projection_schema_invalid")
    if projection.get("manifest_sha256") != _sha256_json(manifest):
        raise G595Error("g595_projection_manifest_mismatch")
    if projection.get("pdf_or_variant_a_used") is not False:
        raise G595Error("g595_adapter_independence_invalid")
    pages = projection.get("pages") or []
    expected = list(range(1, int(manifest["selection"]["pages"]) + 1))
    if [page.get("page") for page in pages] != expected:
        raise G595Error("g595_projection_page_set_invalid")
    for page in pages:
        if page.get("status") not in {"represented", "unavailable"}:
            raise G595Error("g595_projection_status_invalid")
        if page.get("status") == "unavailable" and page.get("nodes") != []:
            raise G595Error("g595_unavailable_page_nodes_invalid")
        if page.get("capabilities") != _b_capabilities():
            raise G595Error("g595_projection_capabilities_invalid")
        if [node.get("order") for node in page["nodes"]] != list(
            range(len(page["nodes"]))
        ):
            raise G595Error("g595_projection_order_invalid")


def _validate_review(
    review: dict[str, Any], manifest: dict[str, Any], projection: dict[str, Any]
) -> None:
    if review.get("schema_version") != REVIEW_SCHEMA:
        raise G595Error("g595_review_schema_invalid")
    if review.get("manifest_sha256") != _sha256_json(manifest):
        raise G595Error("g595_review_manifest_mismatch")
    if review.get("original_pdf_only_referee") is not True:
        raise G595Error("g595_review_referee_invalid")
    if review.get("adapter_verdict") not in {
        "MECHANICAL",
        "REQUIRES_NEW_HEURISTIC_PARSER",
    }:
        raise G595Error("g595_adapter_verdict_invalid")
    pages = review.get("pages") or []
    expected = list(range(1, int(manifest["selection"]["pages"]) + 1))
    if [page.get("page") for page in pages] != expected:
        raise G595Error("g595_review_page_set_invalid")
    projection_by_page = {page["page"]: page for page in projection["pages"]}
    for page in pages:
        if page.get("source_truth_reviewed") is not True:
            raise G595Error("g595_review_not_complete")
        visual = page.get("visual") or {}
        for field in ("tables", "body_rows", "headers"):
            if not _is_count(visual.get(field)):
                raise G595Error("g595_visual_count_invalid")
        for arm in ("A", "B"):
            metrics = page.get(arm) or {}
            for field in (
                "tables_represented",
                "body_rows_represented",
                "headers_preserved",
                "changed_literals",
                "lost_text_segments",
                "invented_text_segments",
                "wrong_row_structure",
                "wrong_column_relations",
                "broken_order",
            ):
                if not _is_count(metrics.get(field)):
                    raise G595Error("g595_arm_count_invalid")
            for represented, total in (
                ("tables_represented", "tables"),
                ("body_rows_represented", "body_rows"),
                ("headers_preserved", "headers"),
            ):
                if metrics[represented] > visual[total]:
                    raise G595Error("g595_coverage_exceeds_visual_truth")
            if not isinstance(metrics.get("page_represented"), bool):
                raise G595Error("g595_page_represented_invalid")
        b_available = projection_by_page[page["page"]]["status"] == "represented"
        if page["B"]["page_represented"] is not b_available:
            raise G595Error("g595_b_availability_review_mismatch")


def _aggregate_arm(pages: list[dict[str, Any]], arm: str) -> dict[str, int]:
    visual = {
        field: sum(page["visual"][field] for page in pages)
        for field in ("tables", "body_rows", "headers")
    }
    metrics = {
        field: sum(page[arm][field] for page in pages)
        for field in (
            "tables_represented",
            "body_rows_represented",
            "headers_preserved",
            "changed_literals",
            "lost_text_segments",
            "invented_text_segments",
            "wrong_row_structure",
            "wrong_column_relations",
            "broken_order",
        )
    }
    return {
        "pages_represented": sum(page[arm]["page_represented"] for page in pages),
        "pages_total": len(pages),
        "visual_tables": visual["tables"],
        "tables_represented": metrics["tables_represented"],
        "visual_body_rows": visual["body_rows"],
        "body_rows_represented": metrics["body_rows_represented"],
        "visual_headers": visual["headers"],
        "headers_preserved": metrics["headers_preserved"],
        "literal_changes": metrics["changed_literals"],
        "lost_text_segments": metrics["lost_text_segments"],
        "invented_text_segments": metrics["invented_text_segments"],
        "wrong_row_structure": metrics["wrong_row_structure"],
        "wrong_column_relations": metrics["wrong_column_relations"],
        "broken_order": metrics["broken_order"],
        "literal_errors_total": (
            metrics["changed_literals"]
            + metrics["lost_text_segments"]
            + metrics["invented_text_segments"]
        ),
        "structural_errors_total": (
            visual["tables"]
            - metrics["tables_represented"]
            + visual["body_rows"]
            - metrics["body_rows_represented"]
            + visual["headers"]
            - metrics["headers_preserved"]
            + metrics["wrong_row_structure"]
            + metrics["wrong_column_relations"]
            + metrics["broken_order"]
        ),
        "unavailable_pages": sum(not page[arm]["page_represented"] for page in pages),
    }


def _terminal(
    aggregate: dict[str, dict[str, int]], adapter_verdict: str
) -> list[str]:
    terminals = [
        "WHOLE_DOCUMENT_CANONICAL_AUDIT_PROVEN",
        "VARIANT_A_WHOLE_DOCUMENT_COVERAGE_MEASURED",
        "VARIANT_B_WHOLE_DOCUMENT_COVERAGE_MEASURED",
    ]
    if adapter_verdict == "MECHANICAL":
        terminals.append("MARKDOWN_TO_CANONICAL_THIN_ADAPTER_PROVEN")
    a = aggregate["A"]
    b = aggregate["B"]
    if b["structural_errors_total"] < a["structural_errors_total"]:
        terminals.append("VISUAL_STRUCTURE_ADVANTAGE_B_CONFIRMED")
    else:
        terminals.append("G594_SAMPLE_CONCLUSION_NOT_CONFIRMED_WHOLE_DOCUMENT")
    if b["wrong_column_relations"] < a["wrong_column_relations"]:
        terminals.append("COLUMN_RELATION_ADVANTAGE_B_CONFIRMED")
    if a["literal_errors_total"] < b["literal_errors_total"]:
        terminals.append("LITERAL_AUTHORITY_ADVANTAGE_A_CONFIRMED")
    return terminals


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_object(path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("frozen") is not True:
        raise G595Error("g595_manifest_invalid")
    if manifest.get("goal") != "G5.95":
        raise G595Error("g595_manifest_goal_invalid")
    selection = manifest.get("selection") or {}
    if (
        selection.get("criterion")
        != "maximum_declared_page_count_then_document_id_ascending"
        or selection.get("selected_document_id") != "document_04"
        or selection.get("pages") != 65
        or selection.get("fixed_before_g595_comparative_review") is not True
    ):
        raise G595Error("g595_selection_invalid")
    adapter = manifest.get("adapter") or {}
    if adapter.get("forbidden_inputs") != [
        "pdf",
        "variant_a",
        "financial_labels",
        "expected_taxonomy",
    ]:
        raise G595Error("g595_adapter_boundary_invalid")
    return manifest


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G595Error("g595_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


if __name__ == "__main__":
    raise SystemExit(main())
