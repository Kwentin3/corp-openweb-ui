#!/usr/bin/env python3
"""Prepare and seal the source-only literal table reference."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"
DEFAULT_CORPUS_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    REFERENCE_SCHEMA_VERSION,
    REFERENCE_SEAL_SCHEMA_VERSION,
    canonical_json_bytes,
    sha256_json,
    validate_reference,
)


class LiteralReferencePackError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    prepare.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    prepare.add_argument("--output-dir", required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--draft", required=True)
    finalize.add_argument("--decisions", required=True)
    finalize.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return prepare_reference(args) if args.command == "prepare" else finalize_reference(args)


def prepare_reference(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    _fresh_directory(output_dir)
    manifest_path = Path(args.manifest).resolve()
    manifest = _json(manifest_path)
    if manifest.get("schema_version") != "broker_reports_pdf_dual_vlm_literal_manifest_v1":
        raise LiteralReferencePackError("literal_reference_manifest_invalid")
    context = manifest.get("historical_context") or {}
    source_manifest_contract = manifest.get("source_case_manifest") or {}
    source_manifest_path = _repo_path(source_manifest_contract.get("path"))
    structural_path = _repo_path(context.get("structural_reference"))
    human_fact_path = _repo_path(context.get("human_reviewed_fact_reference"))
    _require_file_sha(source_manifest_path, source_manifest_contract.get("file_sha256"))
    _require_file_sha(structural_path, context.get("structural_reference_file_sha256"))
    _require_file_sha(human_fact_path, context.get("human_reviewed_fact_reference_sha256"))

    source_manifest = _json(source_manifest_path)
    structural = _json(structural_path)
    prior_human = _json(human_fact_path)
    if prior_human.get("human_reviewed") is not True:
        raise LiteralReferencePackError("literal_reference_prior_human_truth_invalid")
    source_cases = {str(case["case_id"]): case for case in source_manifest["cases"]}
    prior_cases = {str(case["case_id"]): case for case in prior_human["cases"]}
    corpus_root = Path(args.corpus_root).resolve()
    renderer = PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0)).create()
    assets_dir = output_dir / "assets"
    assets_dir.mkdir()
    cases: list[dict[str, Any]] = []
    prior_entry_count = 0
    new_scope_entry_count = 0

    for structural_case in structural["cases"]:
        case_id = str(structural_case["case_id"])
        source_case = source_cases[case_id]
        prior_case = prior_cases.get(case_id) or {"regions": []}
        source_path = _source_path(corpus_root, str(source_case["relative_pdf"]))
        pdf_bytes = source_path.read_bytes()
        if hashlib.sha256(pdf_bytes).hexdigest() != source_case["pdf_sha256"]:
            raise LiteralReferencePackError("literal_reference_source_sha256_mismatch")
        tables: list[dict[str, Any]] = []
        for region in structural_case.get("regions") or []:
            region_id = str(region["region_id"])
            prior_region = next(
                (
                    item
                    for item in prior_case.get("regions") or []
                    if item.get("region_id") == region_id
                ),
                None,
            )
            rendered = renderer.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=str(source_case["pdf_sha256"]),
                document_ref=case_id,
                page_number=int(source_case["page_number"]),
                table_ref=f"literal_reference_{case_id}_{region_id}",
                table_bbox=[float(item) for item in region["bbox_points"]],
                dpi=int(source_case["render_dpi"]),
            )
            png_bytes = base64.b64decode(rendered["private_png_base64"])
            asset_name = f"{case_id}--{region_id}.png"
            (assets_dir / asset_name).write_bytes(png_bytes)
            crop_sha256 = hashlib.sha256(png_bytes).hexdigest()
            prior_facts = _prior_fact_index(prior_region)
            entries: list[dict[str, Any]] = []
            header_indices = {
                int(item) - 1
                for item in region.get("header_rows") or []
                if isinstance(item, int) and item > 0
            }
            rows = region.get("cells") or []
            for row_index, row in enumerate(rows):
                if row_index in header_indices or not isinstance(row, list) or not row:
                    continue
                row_label = str(row[0]).strip()
                if not row_label:
                    continue
                for column_index, raw_value in enumerate(row[1:], start=1):
                    visible_value = str(raw_value).strip()
                    if not visible_value:
                        continue
                    entry_id = f"{case_id}:{region_id}:r{row_index + 1}:c{column_index + 1}"
                    prior = prior_facts.get(_literal_key(row_label, visible_value))
                    if prior is not None:
                        prior_entry_count += 1
                    else:
                        new_scope_entry_count += 1
                    locators = ((prior or {}).get("fact") or {}).get("source_regions") or {}
                    prior_fact = (prior or {}).get("fact") or {}
                    header_path = _header_path(rows, header_indices, column_index)
                    if not header_path and isinstance(prior_fact.get("header_path"), list):
                        header_path = [str(item) for item in prior_fact["header_path"]]
                    entries.append(
                        {
                            "reference_entry_id": entry_id,
                            "row_label_text": row_label,
                            "column_header_path": header_path,
                            "visible_value_text": visible_value,
                            "row_label_bbox": _locator_bbox(locators.get("row_label")),
                            "header_bboxes": [
                                bbox
                                for bbox in (
                                    _locator_bbox(item) for item in locators.get("header") or []
                                )
                                if bbox is not None
                            ],
                            "value_bbox": _locator_bbox(locators.get("value")),
                            "cell_state": (
                                "empty" if visible_value in {"-", "–", "—", "−", "--", "N/A", "n/a"} else "value"
                            ),
                            "visibly_empty": visible_value
                            in {"-", "–", "—", "−", "--", "N/A", "n/a"},
                            "spans_multiple_visual_rows": _row_spans(region, row_index + 1),
                            "spans_multiple_visual_columns": _column_spans(
                                region, row_index + 1, column_index + 1
                            ),
                            "literal_source_notes": "",
                            "review_status": "pending",
                            "review_provenance": {
                                "new_literal_review_required": True,
                                "prior_human_fact_review_available": prior is not None,
                                "prior_review_decision": (prior or {}).get("review_decision"),
                                "prior_reference_sha256": context.get(
                                    "human_reviewed_fact_reference_sha256"
                                ),
                                "new_literal_fields_not_in_prior_contract": [
                                    "cell_state",
                                    "visibly_empty",
                                    "span_flags",
                                    "literal_only_scope",
                                ],
                            },
                        }
                    )
            tables.append(
                {
                    "table_identifier": f"{case_id}:{region_id}",
                    "complete_table_bbox": [float(item) for item in region["bbox_normalized"]],
                    "crop_sha256": crop_sha256,
                    "crop_asset": f"assets/{asset_name}",
                    "evidence_medium": _evidence_medium(source_case, prior_region),
                    "another_table_near_crop_boundary": _near_other_table(
                        region, structural_case.get("regions") or []
                    ),
                    "entries": entries,
                }
            )
        cases.append(
            {
                "case_id": case_id,
                "document_sha256": str(source_case["pdf_sha256"]),
                "page_number": int(source_case["page_number"]),
                "tables": tables,
            }
        )

    draft = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "benchmark_id": manifest["benchmark_id"],
        "human_reviewed": False,
        "manifest_sha256": sha256_json(manifest),
        "reference_scope": "all_visible_value_bearing_table_entries",
        "semantic_financial_types_present": False,
        "prior_human_review_carry_forward_is_final_review": False,
        "preparation_accounting": {
            "entries_with_prior_human_fact_review": prior_entry_count,
            "entries_new_to_literal_scope": new_scope_entry_count,
        },
        "cases": cases,
    }
    draft_path = output_dir / "reference.literal.draft.json"
    draft_path.write_bytes(canonical_json_bytes(draft))
    template = _decision_template(draft, draft_path)
    (output_dir / "review.decisions.template.json").write_bytes(
        canonical_json_bytes(template)
    )
    (output_dir / "review.html").write_text(
        _review_html(draft, assets_dir), encoding="utf-8-sig"
    )
    print(
        json.dumps(
            {
                "draft": str(draft_path),
                "draft_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
                "entries_with_prior_human_review": prior_entry_count,
                "entries_requiring_new_literal_scope_review": new_scope_entry_count,
                "all_entries_require_literal_contract_review": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def finalize_reference(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    _fresh_directory(output_dir)
    draft_path = Path(args.draft).resolve()
    decisions_path = Path(args.decisions).resolve()
    draft = _json(draft_path)
    decisions = _json(decisions_path)
    if draft.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise LiteralReferencePackError("literal_reference_draft_schema_invalid")
    if decisions.get("draft_file_sha256") != hashlib.sha256(draft_path.read_bytes()).hexdigest():
        raise LiteralReferencePackError("literal_reference_decision_draft_sha_mismatch")
    reviewer = decisions.get("reviewer") or {}
    if reviewer.get("type") != "human" or _ai_identity(str(reviewer.get("id") or "")):
        raise LiteralReferencePackError("literal_reference_human_reviewer_required")
    reviewed_at = str(decisions.get("reviewed_at") or "")
    try:
        parsed_time = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise LiteralReferencePackError("literal_reference_review_time_invalid") from exc
    if parsed_time.tzinfo is None:
        raise LiteralReferencePackError("literal_reference_review_time_timezone_required")
    decision_values = decisions.get("decisions")
    if not isinstance(decision_values, list):
        raise LiteralReferencePackError("literal_reference_decisions_invalid")
    by_id = {str(item.get("reference_entry_id")): item for item in decision_values if isinstance(item, dict)}
    expected_ids = {
        str(entry["reference_entry_id"])
        for case in draft["cases"]
        for table in case["tables"]
        for entry in table["entries"]
    }
    if set(by_id) != expected_ids:
        raise LiteralReferencePackError("literal_reference_decision_coverage_invalid")

    final = copy.deepcopy(draft)
    final["human_reviewed"] = True
    final["reviewed_at"] = reviewed_at
    final["reviewer"] = {"type": "human", "id": str(reviewer["id"])}
    for case in final["cases"]:
        for table in case["tables"]:
            for entry in table["entries"]:
                decision = by_id[str(entry["reference_entry_id"])]
                action = decision.get("decision")
                if action not in {"confirmed", "corrected", "ambiguous", "excluded"}:
                    raise LiteralReferencePackError("literal_reference_decision_invalid")
                corrections = decision.get("corrections") or {}
                if action == "corrected":
                    if not isinstance(corrections, dict) or not corrections:
                        raise LiteralReferencePackError(
                            "literal_reference_correction_payload_required"
                        )
                    for key in (
                        "row_label_text",
                        "column_header_path",
                        "visible_value_text",
                        "row_label_bbox",
                        "header_bboxes",
                        "value_bbox",
                        "cell_state",
                        "visibly_empty",
                        "spans_multiple_visual_rows",
                        "spans_multiple_visual_columns",
                        "literal_source_notes",
                    ):
                        if key in corrections:
                            entry[key] = copy.deepcopy(corrections[key])
                entry["review_status"] = action
                entry["review_provenance"] = {
                    **entry["review_provenance"],
                    "literal_contract_reviewed_by_human": True,
                    "reviewed_at": reviewed_at,
                    "reviewer_id": str(reviewer["id"]),
                    "review_note": str(decision.get("note") or ""),
                }

    errors = validate_reference(final, require_human_reviewed=True)
    if errors:
        raise LiteralReferencePackError(errors[0])
    reference_path = output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json"
    reference_bytes = canonical_json_bytes(final)
    reference_path.write_bytes(reference_bytes)
    seal = {
        "schema_version": REFERENCE_SEAL_SCHEMA_VERSION,
        "reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "reference_size_bytes": len(reference_bytes),
        "human_reviewed": True,
        "reviewed_at": reviewed_at,
        "decision_file_sha256": hashlib.sha256(decisions_path.read_bytes()).hexdigest(),
    }
    seal_path = output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.sha256.json"
    seal_path.write_bytes(canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "reference": str(reference_path),
                "seal": str(seal_path),
                "reference_sha256": seal["reference_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _decision_template(draft: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_pdf_table_literal_review_decisions_v1",
        "draft_file_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
        "reviewer": {"type": "human", "id": "REPLACE_WITH_HUMAN_REVIEWER_ID"},
        "reviewed_at": "REPLACE_WITH_TIMEZONE_AWARE_ISO8601",
        "decisions": [
            {
                "reference_entry_id": entry["reference_entry_id"],
                "decision": "REPLACE_WITH_confirmed_corrected_ambiguous_or_excluded",
                "corrections": {},
                "note": "",
            }
            for case in draft["cases"]
            for table in case["tables"]
            for entry in table["entries"]
        ],
    }


def _review_html(draft: dict[str, Any], assets_dir: Path) -> str:
    cards: list[str] = []
    for case in draft["cases"]:
        for table in case["tables"]:
            image_path = assets_dir.parent / table["crop_asset"]
            image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            rows: list[str] = []
            for entry in table["entries"]:
                missing = not entry["row_label_bbox"] or not entry["value_bbox"]
                rows.append(
                    "<tr data-entry-id='"
                    + html.escape(entry["reference_entry_id"])
                    + "' data-missing='"
                    + ("true" if missing else "false")
                    + "'><td><code>"
                    + html.escape(entry["reference_entry_id"])
                    + "</code></td><td>"
                    + html.escape(entry["row_label_text"])
                    + "</td><td>"
                    + html.escape(" / ".join(entry["column_header_path"]))
                    + "</td><td>"
                    + html.escape(entry["visible_value_text"])
                    + "</td><td>"
                    + ("missing bbox" if missing else "locator present")
                    + "</td><td><select class='decision'><option value=''>choose</option><option>confirmed</option><option>corrected</option>"
                    + "<option>ambiguous</option><option>excluded</option></select></td>"
                    + "<td><textarea class='corrections' placeholder='corrections JSON; required for corrected'></textarea></td>"
                    + "<td><input class='note' placeholder='review note'></td></tr>"
                )
            cards.append(
                "<section><h2>"
                + html.escape(table["table_identifier"])
                + "</h2><img src='data:image/png;base64,"
                + image_data
                + "' alt='table crop'><table><thead><tr><th>ID</th><th>Row</th>"
                + "<th>Header path</th><th>Value</th><th>Locator</th><th>Decision</th><th>Corrections JSON</th><th>Note</th>"
                + "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></section>"
            )
    return """<!doctype html><html><head><meta charset="utf-8"><title>Literal reference review</title>
<style>body{font-family:system-ui;margin:24px;background:#f5f6f8;color:#172033}section{background:white;padding:18px;margin:18px 0;border-radius:10px}img{max-width:100%;border:1px solid #ccd}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dde;padding:6px;text-align:left}tr[data-missing=true]{background:#fff0dc}code{font-size:11px}.primary{background:#2358d4;color:white;border:0;border-radius:6px;padding:7px 12px}.primary:disabled{background:#9aa5ba;color:#eef1f6}:focus-visible{outline:3px solid #a34f00;outline-offset:2px}</style></head><body>
<h1>Literal table reference v1 — human review required</h1>
<p>All entries require a new literal-contract decision. Orange rows also require bbox correction. Exported JSON must still pass the fail-closed finalizer.</p>
<p>Every normalized bbox correction must use <code>[x0, y0, x1, y1] = [left, top, right, bottom]</code>; never use <code>[top, left, bottom, right]</code>.</p>
<p id="status" role="status" aria-live="polite">Static source review loaded. Complete every decision and reviewer ID to enable export.</p><p><label>Human reviewer ID <input id="reviewer"></label> <button class="primary" id="export" disabled>Export review decisions</button></p>""" + "".join(cards) + """<script>
const exportButton=document.getElementById('export'),statusLine=document.getElementById('status');function setStatus(message,isError=false){statusLine.textContent=message;statusLine.style.color=isError?'#9b1c1c':'#176b3a'}function updateExportState(){const rows=[...document.querySelectorAll('tr[data-entry-id]')],complete=rows.every(row=>row.querySelector('.decision').value);exportButton.disabled=!document.getElementById('reviewer').value.trim()||!complete}document.querySelectorAll('select,input,textarea').forEach(x=>x.addEventListener('input',updateExportState));updateExportState();exportButton.addEventListener('click',()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){setStatus('Human reviewer ID is required.',true);return}const decisions=[];for(const row of document.querySelectorAll('tr[data-entry-id]')){const decision=row.querySelector('.decision').value;if(!decision){setStatus('Every entry needs a decision: '+row.dataset.entryId,true);return}if(row.dataset.missing==='true'&&decision==='confirmed'){setStatus('Missing bbox requires corrected, ambiguous, or excluded: '+row.dataset.entryId,true);return}let corrections={};const raw=row.querySelector('.corrections').value.trim();if(raw){try{corrections=JSON.parse(raw)}catch(e){setStatus('Invalid corrections JSON: '+row.dataset.entryId,true);return}}if(decision==='corrected'&&!Object.keys(corrections).length){setStatus('Corrections are required: '+row.dataset.entryId,true);return}decisions.push({reference_entry_id:row.dataset.entryId,decision,corrections,note:row.querySelector('.note').value})}const payload={schema_version:'broker_reports_pdf_table_literal_review_decisions_v1',draft_file_sha256:'""" + hashlib.sha256(canonical_json_bytes(draft)).hexdigest() + """',reviewer:{type:'human',id:reviewer},reviewed_at:new Date().toISOString(),decisions};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));a.download='review.decisions.private.json';a.click();URL.revokeObjectURL(a.href);setStatus('Decision file exported successfully.')});
</script></body></html>"""


def _prior_fact_index(region: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(region, dict):
        return result
    for wrapper in region.get("facts") or []:
        if not isinstance(wrapper, dict) or wrapper.get("accepted_for_scoring") is not True:
            continue
        fact = wrapper.get("fact") or {}
        key = _literal_key(fact.get("row_label"), fact.get("visible_value"))
        if key in result:
            raise LiteralReferencePackError("literal_reference_prior_fact_ambiguous")
        result[key] = wrapper
    return result


def _literal_key(row: Any, value: Any) -> str:
    def normalize(item: Any) -> str:
        return " ".join(str(item or "").split()).casefold()

    return normalize(row) + "\x00" + normalize(value)


def _header_path(rows: list[Any], header_indices: set[int], column_index: int) -> list[str]:
    result: list[str] = []
    for index in sorted(header_indices):
        row = rows[index] if index < len(rows) and isinstance(rows[index], list) else []
        value = str(row[column_index]).strip() if column_index < len(row) else ""
        if value and value not in result:
            result.append(value)
    return result


def _locator_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, dict):
        return None
    bbox = value.get("bbox_normalized")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    return [float(item) for item in bbox]


def _row_spans(region: dict[str, Any], row_index: int) -> bool:
    return any(
        int(span.get("start_row", -1)) <= row_index <= int(span.get("end_row", -1))
        and int(span.get("start_row", -1)) != int(span.get("end_row", -1))
        for span in region.get("spans") or []
        if isinstance(span, dict)
    )


def _column_spans(region: dict[str, Any], row_index: int, column_index: int) -> bool:
    return any(
        int(span.get("start_row", -1)) <= row_index <= int(span.get("end_row", -1))
        and int(span.get("start_column", -1)) <= column_index <= int(span.get("end_column", -1))
        and int(span.get("start_column", -1)) != int(span.get("end_column", -1))
        for span in region.get("spans") or []
        if isinstance(span, dict)
    )


def _evidence_medium(source_case: dict[str, Any], prior_region: Any) -> str:
    if isinstance(prior_region, dict) and prior_region.get("evidence_medium") in {
        "text_layer",
        "raster",
        "mixed",
    }:
        return str(prior_region["evidence_medium"])
    tags = set(source_case.get("category_tags") or [])
    if "mixed_text_and_raster" in tags:
        return "mixed"
    if "raster_image" in tags or "without_text_layer" in tags:
        return "raster"
    return "text_layer"


def _near_other_table(region: dict[str, Any], regions: list[Any]) -> bool:
    bbox = region.get("bbox_normalized")
    if not isinstance(bbox, list):
        return False
    for other in regions:
        if other is region or not isinstance(other, dict):
            continue
        other_bbox = other.get("bbox_normalized")
        if not isinstance(other_bbox, list):
            continue
        horizontal_gap = max(0.0, max(bbox[0], other_bbox[0]) - min(bbox[2], other_bbox[2]))
        vertical_gap = max(0.0, max(bbox[1], other_bbox[1]) - min(bbox[3], other_bbox[3]))
        if horizontal_gap <= 0.03 and vertical_gap <= 0.03:
            return True
    return False


def _fresh_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise LiteralReferencePackError("literal_reference_fresh_output_required")
    path.mkdir(parents=True, exist_ok=True)


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralReferencePackError("literal_reference_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralReferencePackError("literal_reference_json_not_object")
    return value


def _repo_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise LiteralReferencePackError("literal_reference_lineage_path_invalid")
    path = (REPO_ROOT / value).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise LiteralReferencePackError("literal_reference_lineage_path_escape") from exc
    return path


def _source_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LiteralReferencePackError("literal_reference_source_path_escape") from exc
    if not path.is_file():
        raise LiteralReferencePackError("literal_reference_source_missing")
    return path


def _require_file_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise LiteralReferencePackError("literal_reference_lineage_sha256_mismatch")


def _ai_identity(value: str) -> bool:
    if not value.strip():
        return True
    return bool(re.search(r"codex|openai|chatgpt|gemini|claude|assistant|model", value, re.I))


if __name__ == "__main__":
    raise SystemExit(main())
