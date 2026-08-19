#!/usr/bin/env python3
"""Inventory the exact G5.80 PDF table heuristic delta on a private corpus."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.full_source import FullSourceArtifactFactory  # noqa: E402
from broker_reports_gate1.table_projection import (  # noqa: E402
    NormalizedTableProjectionFactory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-private-corpus", action="store_true")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute_private_corpus:
        raise SystemExit("explicit_private_corpus_execution_required")
    sources = _parse_sources(args.source)
    private_output = args.private_output.resolve()
    safe_output = args.safe_output.resolve()
    if _is_within(private_output, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    if not _is_within(safe_output, REPO_ROOT.resolve()):
        raise SystemExit("safe_output_must_be_inside_repository")
    if private_output.exists() or safe_output.exists():
        raise SystemExit("output_must_be_new")

    documents = [_inventory(alias=alias, source=source) for alias, source in sources]
    private = {
        "schema_version": "broker_reports_g581_table_heuristic_private_v1",
        "goal": "G5.81",
        "heuristic": _heuristic(),
        "documents": documents,
    }
    safe_documents = [_safe_document(item) for item in documents]
    changed = [
        {"source_alias": item["source_alias"], "page": page["page"]}
        for item in safe_documents
        for page in item["pages"]
        if page["promoted_only_by_new_rule"]
    ]
    safe = {
        "schema_version": "broker_reports_g581_table_heuristic_receipt_v2",
        "goal": "G5.81",
        "heuristic": _heuristic(),
        "source_documents": len(documents),
        "pages_total": sum(item["pages_total"] for item in safe_documents),
        "candidates_total": sum(item["candidates_total"] for item in safe_documents),
        "current_ready_total": sum(
            item["current_ready_total"] for item in safe_documents
        ),
        "current_blocked_total": sum(
            item["current_blocked_total"] for item in safe_documents
        ),
        "promoted_only_by_new_rule_candidates_total": sum(
            item["promoted_only_by_new_rule_total"] for item in safe_documents
        ),
        "promoted_only_by_new_rule_pages_total": len(changed),
        "promoted_only_by_new_rule_pages": changed,
        "documents": safe_documents,
        "visual_truth_injected_into_machine_decision": False,
        "broker_page_coordinate_rules": 0,
        "provider_calls": 0,
        "production_visual_dependency": False,
        "private_output_sha256": _sha256(_json_bytes(private)),
    }
    _atomic_write(private_output, _json_bytes(private))
    _atomic_write(safe_output, _json_bytes(safe))
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0


def _parse_sources(values: list[str]) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    aliases: set[str] = set()
    for value in values:
        alias, separator, raw_path = value.partition("=")
        path = Path(raw_path).resolve()
        if (
            not separator
            or not alias
            or not alias.replace("_", "").replace("-", "").isalnum()
            or alias in aliases
            or not path.is_file()
            or path.suffix.lower() != ".pdf"
        ):
            raise SystemExit("private_source_argument_invalid")
        aliases.add(alias)
        parsed.append((alias, path))
    if len(parsed) < 3:
        raise SystemExit("private_corpus_requires_at_least_three_sources")
    return parsed


def _inventory(*, alias: str, source: Path) -> dict[str, Any]:
    content = source.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    built = FullSourceArtifactFactory().create().build(
        normalization_run_id=f"g581-heuristic-{alias}",
        document_id=f"g581-{alias}",
        profile_id="g581-private-regression-corpus",
        container_format="pdf",
        content_bytes=content,
        source_checksum_sha256=checksum,
    )
    result = NormalizedTableProjectionFactory().create().build_for_document(
        source_format="pdf",
        payloads=built.payloads,
        source_units=built.units,
    )
    payloads = {
        str(item.get("source_payload_ref") or ""): item
        for item in built.payloads
        if isinstance(item, dict) and item.get("source_payload_ref")
    }
    projections = {
        str(item.get("source_unit_ref") or ""): item
        for item in result.projections
    }
    candidates = []
    for unit in built.units:
        if not isinstance(unit, dict) or unit.get("pdf_unit_type") != (
            "pdf_table_candidate_unit"
        ):
            continue
        parent = payloads.get(str(unit.get("parent_payload_ref") or ""), {})
        projection = parent.get("pdf_text_layer_projection") or {}
        inventory = projection.get("table_candidate_inventory") or []
        candidate = next(
            (
                item
                for item in inventory
                if isinstance(item, dict)
                and item.get("table_candidate_ref") == unit.get("table_candidate_ref")
            ),
            None,
        )
        if candidate is None:
            raise SystemExit("table_candidate_inventory_missing")
        cells = [
            item
            for item in candidate.get("cell_inventory") or []
            if isinstance(item, dict)
        ]
        rows = [
            item
            for item in candidate.get("row_inventory") or []
            if isinstance(item, dict)
        ]
        counts = Counter(int(item.get("row_ordinal") or 0) for item in cells)
        old_column_structure = bool(counts) and min(counts.values()) >= 2
        new_column_structure = bool(counts) and max(counts.values()) >= 2
        actual = projections[str(unit.get("unit_ref") or "")]
        current_ready = actual.get("projection_status") == "ready"
        candidates.append(
            {
                "unit_ref": unit.get("unit_ref"),
                "candidate_ref": unit.get("table_candidate_ref"),
                "page": int((unit.get("location") or {}).get("page") or 0),
                "line_start": int((unit.get("location") or {}).get("line_start") or 0),
                "line_end": int((unit.get("location") or {}).get("line_end") or 0),
                "strategy": unit.get("table_strategy_ref"),
                "geometry_confidence": unit.get("geometry_confidence"),
                "rows": len(rows),
                "cells": len(cells),
                "row_cell_counts": [counts[key] for key in sorted(counts)],
                "old_column_structure": old_column_structure,
                "new_column_structure": new_column_structure,
                "current_ready": current_ready,
                "promoted_only_by_new_rule": (
                    current_ready
                    and not old_column_structure
                    and new_column_structure
                ),
                "current_status": actual.get("table_candidate_status"),
                "current_reason_codes": actual.get("reconstruction_reason_codes"),
                "current_row_count": actual.get("row_count"),
                "current_cell_count": actual.get("cell_count"),
            }
        )
    pages_total = max(
        (
            int((unit.get("location") or {}).get("page_end") or 0)
            for unit in built.units
            if isinstance(unit, dict)
        ),
        default=0,
    )
    return {
        "source_alias": alias,
        "source_path": str(source),
        "source_sha256": checksum,
        "pages_total": pages_total,
        "candidates": candidates,
    }


def _safe_document(document: dict[str, Any]) -> dict[str, Any]:
    candidates = document["candidates"]
    page_numbers = range(1, int(document["pages_total"]) + 1)
    pages = []
    for page in page_numbers:
        selected = [item for item in candidates if item["page"] == page]
        pages.append(
            {
                "page": page,
                "candidate_count": len(selected),
                "current_ready": sum(item["current_ready"] for item in selected),
                "current_blocked": sum(
                    not item["current_ready"] for item in selected
                ),
                "old_and_new_ready": sum(
                    item["current_ready"] and item["old_column_structure"]
                    for item in selected
                ),
                "promoted_only_by_new_rule": sum(
                    item["promoted_only_by_new_rule"] for item in selected
                ),
            }
        )
    return {
        "source_alias": document["source_alias"],
        "source_sha256": document["source_sha256"],
        "pages_total": document["pages_total"],
        "candidates_total": len(candidates),
        "current_ready_total": sum(item["current_ready"] for item in candidates),
        "current_blocked_total": sum(
            not item["current_ready"] for item in candidates
        ),
        "old_and_new_ready_total": sum(
            item["current_ready"] and item["old_column_structure"]
            for item in candidates
        ),
        "promoted_only_by_new_rule_total": sum(
            item["promoted_only_by_new_rule"] for item in candidates
        ),
        "pages": pages,
    }


def _heuristic() -> dict[str, Any]:
    return {
        "owner": "NormalizedTableProjectionFactory.create / _pdf_geometry_reasons",
        "structural_input": "candidate cell_inventory row_ordinal counts",
        "old_rule": "reject when any represented row has fewer than two cells",
        "old_predicate": "min(row_cell_counts.values()) < 2",
        "new_rule": "require at least one represented multi-column row",
        "new_predicate": "max(row_cell_counts.values()) < 2",
        "other_acceptance_checks_changed": False,
        "financial_semantics_used": False,
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
