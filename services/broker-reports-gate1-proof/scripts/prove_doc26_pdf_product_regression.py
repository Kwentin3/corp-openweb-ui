from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from broker_reports_gate1 import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    validate_canonical_artifact,
)


RUN_ID = "broker_reports_doc26_pdf_product_regression_2026-08-05_v1"
EXPECTED_DOCUMENTS = 6
EXPECTED_ARMS = 2
EXPECTED_PAGES = 663
EXPECTED_PARSER_LINES = 34_541
EXPECTED_TABLES = 24


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _integrity_valid(value: dict[str, Any]) -> bool:
    material = copy.deepcopy(value)
    expected = str(material.pop("integrity_sha256", ""))
    return bool(expected) and _sha256(material) == expected


def _source_units(candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[int, list[str]]]:
    units: list[dict[str, Any]] = []
    expected_order: dict[int, list[str]] = defaultdict(list)
    for page in candidate.get("pages") or []:
        page_number = int(page["page_number"])
        for ordinal, block in enumerate(page.get("blocks") or [], 1):
            block_type = str(block.get("block_type") or "TEXT")
            expected_order[page_number].append(block_type)
            refs = sorted(
                {
                    str(ref)
                    for field in (
                        "source_refs",
                        "suppressed_parser_evidence_refs",
                        "evidence_refs",
                        "source_block_refs",
                    )
                    for ref in block.get(field) or []
                    if ref
                }
            )
            location = {
                "page": page_number,
                "line_start": ordinal,
                "research_block_ref": str(block.get("block_id") or ""),
                "frozen_source_refs": refs,
            }
            unit: dict[str, Any] = {
                "unit_ref": f"doc26-unit-{page_number}-{ordinal}",
                "source_location": location,
                "atom_status": str(block.get("atom_status") or ""),
            }
            if block_type == "TABLE":
                content = block.get("content") or {}
                header = content.get("header") or []
                rows = copy.deepcopy(content.get("rows") or [])
                if header:
                    rows.insert(0, copy.deepcopy(header))
                unit.update(
                    {
                        "rows": rows,
                        "table_title": content.get("title"),
                        "table_notes": copy.deepcopy(content.get("notes") or []),
                        "research_table_ref": str(block.get("table_id") or ""),
                    }
                )
            else:
                unit["text"] = str(block.get("text") or "")
            units.append(unit)
    return units, dict(expected_order)


def _product_page_order(artifact: dict[str, Any]) -> dict[int, list[str]]:
    page_by_container = {
        str(item["container_id"]): int((item.get("metadata") or {}).get("page_number") or 0)
        for item in artifact.get("containers") or []
        if item.get("container_type") == "PAGE"
    }
    result: dict[int, list[str]] = defaultdict(list)
    for node in artifact.get("nodes") or []:
        if node.get("node_type") == "PAGE_BREAK":
            continue
        page = page_by_container.get(str(node.get("container_ref") or ""), 0)
        result[page].append(str(node.get("node_type") or ""))
    return dict(result)


def run(repo_root: Path) -> dict[str, Any]:
    private_root = (
        repo_root
        / "local"
        / "stage2"
        / "broker_reports_doc24_gate2_canonical_document_2026-08-05"
        / "private"
    )
    candidate_root = private_root / "doc24_canonical_documents"
    candidate_files = sorted(candidate_root.glob("*.private.json"))
    material = _read_json(
        repo_root
        / "docs"
        / "stage2"
        / "BROKER_REPORTS_DOC24_MATERIAL_SUFFICIENCY.safe.json"
    )
    if len(candidate_files) != EXPECTED_DOCUMENTS * EXPECTED_ARMS:
        return {
            "schema_version": "broker_reports_doc26_pdf_product_regression_safe_v1",
            "run_id": RUN_ID,
            "status": "BLOCKED",
            "blocker_codes": ["frozen_doc24_candidate_cardinality_mismatch"],
            "provider_calls": 0,
            "parser_reruns": 0,
            "cropper_reruns": 0,
            "vlm_tables_regenerated": False,
        }
    arms: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "documents": set(),
            "pages": set(),
            "parser_refs": set(),
            "tables": set(),
            "candidate_files": 0,
            "ordering_errors": 0,
            "continuation_order_errors": 0,
            "multiple_table_page_order_errors": 0,
            "unresolved_refs": 0,
            "hidden_conflicts": 0,
            "conflicts": 0,
            "ambiguities": 0,
            "product_hashes": [],
            "integrity_failures": 0,
        }
    )
    factory = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="canonical-doc26-pdf-v1")
    )
    for candidate_file in candidate_files:
        candidate = _read_json(candidate_file)
        arm_id = str(candidate.get("table_arm_id") or "")
        metrics = arms[arm_id]
        metrics["candidate_files"] += 1
        if not _integrity_valid(candidate):
            metrics["integrity_failures"] += 1
            continue
        document_id = str(candidate.get("document_id") or "")
        metrics["documents"].add(document_id)
        units, expected_order = _source_units(candidate)
        artifact = factory.create().build(
            tenant_id="doc26-private-regression",
            artifact_version=1,
            document={
                "container_format": "pdf",
                "sha256": str(
                    (candidate.get("input_sources") or {}).get(
                        "doc22_shadow_sha256"
                    )
                ),
                "declared_mime_type": "application/pdf",
            },
            source_artifact_ref=f"frozen-doc24-{_sha256([arm_id, document_id])[:24]}",
            source_payloads=[],
            source_units=units,
            table_projections=[],
            created_at="2026-08-05T00:00:00+00:00",
        )
        validation = validate_canonical_artifact(artifact)
        metrics["unresolved_refs"] += len(validation["error_codes"])
        metrics["product_hashes"].append(artifact["canonical_root_hash"])
        product_order = _product_page_order(artifact)
        if product_order != expected_order:
            metrics["ordering_errors"] += 1
        for page in candidate.get("pages") or []:
            page_number = int(page["page_number"])
            metrics["pages"].add((document_id, page_number))
            research_types = [
                str(item.get("block_type") or "TEXT")
                for item in page.get("blocks") or []
            ]
            if product_order.get(page_number, []) != research_types:
                if page.get("continuation"):
                    metrics["continuation_order_errors"] += 1
                if research_types.count("TABLE") > 1:
                    metrics["multiple_table_page_order_errors"] += 1
        for unit in units:
            for ref in (unit.get("source_location") or {}).get(
                "frozen_source_refs"
            ) or []:
                if str(ref).startswith("parser:"):
                    metrics["parser_refs"].add(str(ref))
            table_ref = str(unit.get("research_table_ref") or "")
            if table_ref:
                metrics["tables"].add(table_ref)
        expected_conflicts = sum(
            1 for unit in units if unit.get("atom_status") == "CONFLICT_EVIDENCE"
        )
        expected_ambiguities = sum(
            1 for unit in units if unit.get("atom_status") == "AMBIGUOUS_EVIDENCE"
        )
        actual_conflicts = sum(
            1 for item in artifact["issues"] if item["issue_type"] == "CONFLICT"
        )
        actual_ambiguities = sum(
            1 for item in artifact["issues"] if item["issue_type"] == "AMBIGUITY"
        )
        metrics["conflicts"] += actual_conflicts
        metrics["ambiguities"] += actual_ambiguities
        metrics["hidden_conflicts"] += abs(expected_conflicts - actual_conflicts)
        metrics["hidden_conflicts"] += abs(expected_ambiguities - actual_ambiguities)

    provider_metrics = material.get("provider_metrics") or {}
    safe_arms: list[dict[str, Any]] = []
    overall_pass = True
    for arm_id, metrics in sorted(arms.items()):
        provider_key = (
            "anthropic_opus" if "anthropic" in arm_id else "google_flash_lite"
        )
        provider = provider_metrics.get(provider_key) or {}
        arm_pass = all(
            (
                len(metrics["documents"]) == EXPECTED_DOCUMENTS,
                len(metrics["pages"]) == EXPECTED_PAGES,
                len(metrics["parser_refs"]) == EXPECTED_PARSER_LINES,
                len(metrics["tables"]) == EXPECTED_TABLES,
                metrics["ordering_errors"] == 0,
                metrics["continuation_order_errors"] == 0,
                metrics["multiple_table_page_order_errors"] == 0,
                metrics["unresolved_refs"] == 0,
                metrics["hidden_conflicts"] == 0,
                metrics["integrity_failures"] == 0,
            )
        )
        overall_pass = overall_pass and arm_pass
        safe_arms.append(
            {
                "arm_id": arm_id,
                "status": "PASSED" if arm_pass else "FAILED",
                "documents": len(metrics["documents"]),
                "pages_accounted": len(metrics["pages"]),
                "parser_lines_accounted": len(metrics["parser_refs"]),
                "target_tables_inserted": len(metrics["tables"]),
                "ordering_errors": metrics["ordering_errors"],
                "continuation_order_errors": metrics[
                    "continuation_order_errors"
                ],
                "multiple_table_page_order_errors": metrics[
                    "multiple_table_page_order_errors"
                ],
                "unresolved_refs": metrics["unresolved_refs"],
                "hidden_conflicts": metrics["hidden_conflicts"],
                "explicit_conflicts": metrics["conflicts"],
                "explicit_ambiguities": metrics["ambiguities"],
                "product_root_hashes_total": len(metrics["product_hashes"]),
                "product_root_hashes_unique": len(set(metrics["product_hashes"])),
                "material_sufficient_or_rescued": int(
                    provider.get("sufficient_total") or 0
                ),
                "material_critical": int(
                    provider.get("critical_information_loss_total") or 0
                ),
                "material_ambiguous": int(
                    (provider.get("counts") or {}).get("AMBIGUOUS") or 0
                ),
            }
        )
    result = {
        "schema_version": "broker_reports_doc26_pdf_product_regression_safe_v1",
        "run_id": RUN_ID,
        "date": "2026-08-05",
        "status": "PASSED" if overall_pass else "FAILED",
        "frozen_input": {
            "documents": EXPECTED_DOCUMENTS,
            "arms": EXPECTED_ARMS,
            "pages": EXPECTED_PAGES,
            "parser_lines": EXPECTED_PARSER_LINES,
            "target_tables_per_arm": EXPECTED_TABLES,
            "candidate_integrity_checked": True,
        },
        "product_boundary": "CanonicalNormalizerFactory.create",
        "arms": safe_arms,
        "research_product_differences": [
            {
                "classification": "EXPECTED_SCHEMA_DIFFERENCE",
                "difference": "CanonicalArtifactV1 adds typed containers, nodes, cells and root-hash envelope while retaining DOC24 block order and refs",
                "unexplained": False,
            },
            {
                "classification": "CANONICAL_IMPROVEMENT",
                "difference": "DOC24 conflict and ambiguity atom states become explicit issue_refs",
                "unexplained": False,
            },
        ],
        "research_product_unexplained_differences": 0 if overall_pass else 1,
        "provider_calls": 0,
        "parser_reruns": 0,
        "cropper_reruns": 0,
        "vlm_tables_regenerated": False,
        "private_content_in_report": False,
        "legacy_product_reads_changed": False,
        "canonical_product_reads_enabled": False,
    }
    result["integrity_sha256"] = _sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.repo_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
