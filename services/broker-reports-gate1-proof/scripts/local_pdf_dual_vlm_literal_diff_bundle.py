#!/usr/bin/env python3
"""Build machine diffs and an operator HTML bundle from a sealed literal terminal."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    DIFFS_SCHEMA_VERSION,
    bbox_iou,
    canonical_json_bytes,
    canonicalize_entry,
)


class LiteralDiffBundleError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    terminal_path = Path(args.terminal).resolve()
    seal_path = Path(args.seal).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    diffs_path = output_root / "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_DIFFS.v1.json"
    review_dir = output_root / "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_DIFF_REVIEW"
    if diffs_path.exists() or (review_dir.exists() and any(review_dir.iterdir())):
        raise LiteralDiffBundleError("literal_diff_fresh_output_required")
    review_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = review_dir / "assets"
    assets_dir.mkdir()
    terminal = _json(terminal_path)
    seal = _json(seal_path)
    _verify_terminal(terminal_path, terminal, seal)
    agreements: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    total_gemini_entries = 0
    total_openai_entries = 0
    total_aligned = 0
    gemini_contract_valid_tables = 0
    openai_contract_valid_tables = 0
    dual_contract_valid_tables = 0
    agreement_metrics = {
        "unique_aligned_entries": 0,
        "exact_raw_key_header_value_agreements": 0,
        "canonical_key_header_value_agreements": 0,
        "numeric_agreements": 0,
        "numeric_comparable_entries": 0,
        "canonical_agreements_with_compatible_source_regions": 0,
        "entry_alignment_ambiguous": 0,
    }
    extracted_tables = 0
    table_records = 0

    for crop in terminal.get("crops") or []:
        table_records += 1
        case_id = str(crop.get("case_id"))
        candidate_id = str(crop.get("candidate_id"))
        crop_asset = None
        if crop.get("crop_png_base64"):
            crop_bytes = base64.b64decode(crop["crop_png_base64"])
            if hashlib.sha256(crop_bytes).hexdigest() != crop.get("crop_sha256"):
                raise LiteralDiffBundleError("literal_diff_crop_sha_mismatch")
            crop_asset = f"assets/{case_id}--{candidate_id}.png"
            (review_dir / crop_asset).write_bytes(crop_bytes)
            extracted_tables += 1
        gemini = crop.get("gemini") if isinstance(crop.get("gemini"), dict) else {}
        openai = crop.get("openai") if isinstance(crop.get("openai"), dict) else {}
        total_gemini_entries += len((gemini.get("json_output") or {}).get("entries") or [])
        total_openai_entries += len((openai.get("json_output") or {}).get("entries") or [])
        if gemini.get("terminal_status") == "completed":
            gemini_contract_valid_tables += 1
        if openai.get("terminal_status") == "completed":
            openai_contract_valid_tables += 1
        if (
            gemini.get("terminal_status") == "completed"
            and openai.get("terminal_status") == "completed"
        ):
            dual_contract_valid_tables += 1
        provider_diffs = crop.get("provider_diffs_reference_free")
        if isinstance(provider_diffs, dict):
            total_aligned += len((provider_diffs.get("alignment") or {}).get("matches") or [])
            _add_agreement_metrics(
                agreement_metrics,
                provider_diffs,
                (gemini.get("json_output") or {}).get("entries") or [],
                (openai.get("json_output") or {}).get("entries") or [],
            )
            for agreement in provider_diffs.get("compact_agreements") or []:
                agreements.append(
                    {
                        "case_id": case_id,
                        "page_number": crop.get("page_number"),
                        "candidate_id": candidate_id,
                        "crop_sha256": crop.get("crop_sha256"),
                        **copy.deepcopy(agreement),
                    }
                )
            for item in provider_diffs.get("disagreements") or []:
                disagreements.append(
                    _enrich_diff(
                        crop=crop,
                        item=item,
                        crop_asset=crop_asset,
                        ordinal=len(disagreements) + 1,
                    )
                )
        else:
            for provider_name, operation in (("gemini", gemini), ("openai", openai)):
                if operation and operation.get("terminal_status") != "completed":
                    disagreements.append(
                        _contract_failure_diff(
                            crop=crop,
                            provider_name=provider_name,
                            operation=operation,
                            crop_asset=crop_asset,
                            ordinal=len(disagreements) + 1,
                        )
                    )
            if not gemini and not openai:
                disagreements.append(
                    _contract_failure_diff(
                        crop=crop,
                        provider_name="upstream_detection",
                        operation={
                            "terminal_status": crop.get("terminal_status"),
                            "failure_code": crop.get("terminal_status"),
                            "contract_errors": [],
                            "raw_provider_text": None,
                        },
                        crop_asset=crop_asset,
                        ordinal=len(disagreements) + 1,
                    )
                )
    class_counts: dict[str, int] = {}
    for item in disagreements:
        class_counts[item["class"]] = class_counts.get(item["class"], 0) + 1
    summary = {
        "total_table_records": table_records,
        "tables_sent_to_both_providers": extracted_tables,
        "total_gemini_entries": total_gemini_entries,
        "total_openai_entries": total_openai_entries,
        "gemini_contract_valid_tables": gemini_contract_valid_tables,
        "openai_contract_valid_tables": openai_contract_valid_tables,
        "dual_contract_valid_tables": dual_contract_valid_tables,
        "total_aligned_entries": total_aligned,
        "exact_agreements": sum(item["status"] == "exact_raw_agreement" for item in agreements),
        "canonical_agreements_with_raw_format_difference": sum(
            item["status"] == "canonical_match_with_raw_format_difference"
            for item in agreements
        ),
        "disagreements": len(disagreements),
        "disagreements_by_class": dict(sorted(class_counts.items())),
        "missing_entries_in_gemini": class_counts.get("entry_missing_in_gemini", 0),
        "missing_entries_in_openai": class_counts.get("entry_missing_in_openai", 0),
        "tables_requiring_review": len(
            {(item["case_id"], item["candidate_id"]) for item in disagreements}
        ),
        "agreement_metrics": agreement_metrics,
    }
    output = {
        "schema_version": DIFFS_SCHEMA_VERSION,
        "benchmark_id": terminal.get("benchmark_id"),
        "terminal_sha256": seal["terminal_sha256"],
        "diagnostic_invalid_upstream_crop_set": terminal.get(
            "diagnostic_invalid_upstream_crop_set"
        ),
        "human_reference_added_during_scoring": False,
        "human_reference_status": "unsealed_review_required",
        "final_benchmark_disposition": "diagnostic_unscored",
        "summary": summary,
        "compact_agreements": agreements,
        "disagreements": disagreements,
    }
    diffs_path.write_bytes(canonical_json_bytes(output))
    decisions = {
        "schema_version": "broker_reports_pdf_dual_vlm_literal_diff_review_decisions_v1",
        "diffs_sha256": hashlib.sha256(diffs_path.read_bytes()).hexdigest(),
        "reviewer": {"type": "human", "id": "REPLACE_WITH_HUMAN_REVIEWER_ID"},
        "reviewed_at": "REPLACE_WITH_TIMEZONE_AWARE_ISO8601",
        "decisions": [
            {
                "diff_id": item["diff_id"],
                "decision": "REPLACE_WITH_gemini_correct_openai_correct_both_equivalent_both_wrong_reference_ambiguous_crop_problem_or_binding_problem",
                "note": "",
            }
            for item in disagreements
        ],
    }
    (review_dir / "review.decisions.template.json").write_bytes(
        canonical_json_bytes(decisions)
    )
    (review_dir / "index.html").write_text(
        _render_html(
            output,
            review_dir,
            hashlib.sha256(diffs_path.read_bytes()).hexdigest(),
        ),
        encoding="utf-8-sig",
    )
    print(json.dumps({"diffs": str(diffs_path), "diffs_sha256": hashlib.sha256(diffs_path.read_bytes()).hexdigest(), "review_bundle": str(review_dir), "disagreements": len(disagreements)}, ensure_ascii=False, sort_keys=True))
    return 0


def _enrich_diff(
    *,
    crop: dict[str, Any],
    item: dict[str, Any],
    crop_asset: str | None,
    ordinal: int,
) -> dict[str, Any]:
    gemini_entry_id = item.get("gemini_entry_id")
    openai_entry_id = item.get("openai_entry_id")
    evidence = crop.get("parser_evidence") or {}
    return {
        "diff_id": f"diff_{ordinal:04d}",
        "class": item["class"],
        "source_pdf_sha256": crop.get("document_sha256"),
        "page_number": crop.get("page_number"),
        "case_id": crop.get("case_id"),
        "candidate_id": crop.get("candidate_id"),
        "evidence_medium": crop.get("evidence_medium"),
        "detector_bbox": crop.get("detected_bbox"),
        "padded_crop_bbox": crop.get("padded_crop_bbox"),
        "crop_sha256": crop.get("crop_sha256"),
        "crop_asset": crop_asset,
        "gemini_highlighted_regions": _entry_regions(item.get("gemini")),
        "openai_highlighted_regions": _entry_regions(item.get("openai")),
        "exact_gemini_output": copy.deepcopy(item.get("gemini")),
        "exact_openai_output": copy.deepcopy(item.get("openai")),
        "canonicalized_forms": copy.deepcopy(item.get("canonical")),
        "minimal_field_difference": copy.deepcopy(item.get("minimal_difference")),
        "alignment": copy.deepcopy(item.get("alignment")),
        "parser_or_ocr_evidence": {
            "gemini": _evidence_for_entry(evidence.get("gemini"), gemini_entry_id),
            "openai": _evidence_for_entry(evidence.get("openai"), openai_entry_id),
            "ocr_performed": False,
        },
        "human_reference_answer": None,
        "final_benchmark_disposition": "diagnostic_unscored_reference_unsealed",
    }


def _add_agreement_metrics(
    metrics: dict[str, int],
    provider_diffs: dict[str, Any],
    gemini_entries: list[dict[str, Any]],
    openai_entries: list[dict[str, Any]],
) -> None:
    gemini = {str(item["entry_id"]): item for item in gemini_entries}
    openai = {str(item["entry_id"]): item for item in openai_entries}
    for match in (provider_diffs.get("alignment") or {}).get("matches") or []:
        if not match.get("match_unique"):
            metrics["entry_alignment_ambiguous"] += 1
            continue
        left_raw = gemini[str(match["gemini_entry_id"])]
        right_raw = openai[str(match["openai_entry_id"])]
        left = canonicalize_entry(left_raw)
        right = canonicalize_entry(right_raw)
        metrics["unique_aligned_entries"] += 1
        raw_equal = (
            left_raw["row_label_text"] == right_raw["row_label_text"]
            and left_raw["column_header_path"] == right_raw["column_header_path"]
            and left_raw["visible_value_text"] == right_raw["visible_value_text"]
        )
        canonical_equal = (
            left["row_label_text_canonical"] == right["row_label_text_canonical"]
            and left["column_header_path_canonical"]
            == right["column_header_path_canonical"]
            and left["visible_value_text_canonical"]
            == right["visible_value_text_canonical"]
        )
        if raw_equal:
            metrics["exact_raw_key_header_value_agreements"] += 1
        if canonical_equal:
            metrics["canonical_key_header_value_agreements"] += 1
        if (
            left["parsed_numeric_value"] is not None
            and right["parsed_numeric_value"] is not None
        ):
            metrics["numeric_comparable_entries"] += 1
            if left["parsed_numeric_value"] == right["parsed_numeric_value"]:
                metrics["numeric_agreements"] += 1
        if canonical_equal and _source_regions_compatible(left, right):
            metrics["canonical_agreements_with_compatible_source_regions"] += 1


def _source_regions_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    value_compatible = bbox_iou(left["value_bbox"], right["value_bbox"]) >= 0.1
    row_compatible = bbox_iou(left["row_label_bbox"], right["row_label_bbox"]) >= 0.1
    if not left["header_bboxes"] and not right["header_bboxes"]:
        header_compatible = True
    elif not left["header_bboxes"] or not right["header_bboxes"]:
        header_compatible = False
    else:
        header_compatible = any(
            bbox_iou(a, b) >= 0.1
            for a in left["header_bboxes"]
            for b in right["header_bboxes"]
        )
    return value_compatible and row_compatible and header_compatible


def _contract_failure_diff(
    *,
    crop: dict[str, Any],
    provider_name: str,
    operation: dict[str, Any],
    crop_asset: str | None,
    ordinal: int,
) -> dict[str, Any]:
    return {
        "diff_id": f"diff_{ordinal:04d}",
        "class": "schema_or_contract_failure",
        "source_pdf_sha256": crop.get("document_sha256"),
        "page_number": crop.get("page_number"),
        "case_id": crop.get("case_id"),
        "candidate_id": crop.get("candidate_id"),
        "evidence_medium": crop.get("evidence_medium"),
        "detector_bbox": crop.get("detected_bbox"),
        "padded_crop_bbox": crop.get("padded_crop_bbox"),
        "crop_sha256": crop.get("crop_sha256"),
        "crop_asset": crop_asset,
        "failed_provider": provider_name,
        "gemini_highlighted_regions": [],
        "openai_highlighted_regions": [],
        "exact_gemini_output": (
            operation.get("raw_provider_text") if provider_name == "gemini" else None
        ),
        "exact_openai_output": (
            operation.get("raw_provider_text") if provider_name == "openai" else None
        ),
        "canonicalized_forms": None,
        "minimal_field_difference": {
            "terminal_status": operation.get("terminal_status"),
            "failure_code": operation.get("failure_code"),
            "contract_errors": operation.get("contract_errors") or [],
        },
        "alignment": None,
        "parser_or_ocr_evidence": None,
        "human_reference_answer": None,
        "final_benchmark_disposition": "terminal_contract_failure_unscored",
    }


def _entry_regions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    result = []
    if isinstance(value.get("row_label_bbox"), list):
        result.append({"role": "row_label", "bbox": value["row_label_bbox"]})
    for bbox in value.get("header_bboxes") or []:
        if isinstance(bbox, list):
            result.append({"role": "header", "bbox": bbox})
    if isinstance(value.get("value_bbox"), list):
        result.append({"role": "value", "bbox": value["value_bbox"]})
    return result


def _evidence_for_entry(values: Any, entry_id: Any) -> dict[str, Any] | None:
    if not isinstance(values, list):
        return None
    return next(
        (
            copy.deepcopy(item)
            for item in values
            if isinstance(item, dict) and item.get("entry_id") == entry_id
        ),
        None,
    )


def _render_html(
    output: dict[str, Any], review_dir: Path, diffs_sha256: str
) -> str:
    summary = output["summary"]
    class_options = "".join(
        f"<option value='{html.escape(name)}'>{html.escape(name)} ({count})</option>"
        for name, count in summary["disagreements_by_class"].items()
    )
    medium_options = "".join(
        f"<option value='{html.escape(name)}'>{html.escape(name)}</option>"
        for name in sorted(
            {
                str(item.get("evidence_medium"))
                for item in output["disagreements"]
                if item.get("evidence_medium")
            }
        )
    )
    cards = "".join(_render_card(item, review_dir) for item in output["disagreements"])
    if not cards:
        cards = (
            "<p class='empty'>No disagreements require review. "
            "The compact machine agreement records remain in the JSON artifact.</p>"
        )
    metrics = "".join(
        f"<div class='metric'><b>{html.escape(label)}</b><span>{value}</span></div>"
        for label, value in (
            ("Tables", summary["total_table_records"]),
            ("Aligned entries", summary["total_aligned_entries"]),
            ("Exact agreements", summary["exact_agreements"]),
            (
                "Canonical/raw-format agreements",
                summary["canonical_agreements_with_raw_format_difference"],
            ),
            ("Disagreements", summary["disagreements"]),
            ("Missing in Gemini", summary["missing_entries_in_gemini"]),
            ("Missing in OpenAI", summary["missing_entries_in_openai"]),
            ("Tables requiring review", summary["tables_requiring_review"]),
        )
    )
    return """<!doctype html><html><head><meta charset='utf-8'><title>Dual-VLM literal diff review</title>
<style>body{font-family:system-ui;margin:0;background:#f3f5f8;color:#172033}header{padding:24px;background:#172033;color:white}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;padding:18px}.metric{background:white;border-radius:10px;padding:12px;display:flex;flex-direction:column}.metric span{font-size:24px}.filters{margin:0 18px 18px;padding:12px;display:flex;gap:8px;flex-wrap:wrap}.card{background:white;margin:0 18px 18px;padding:18px;border-radius:12px}.crop{position:relative;display:inline-block;max-width:100%}.crop img{max-width:100%;display:block}.box{position:absolute;border:2px solid;box-sizing:border-box;pointer-events:none}.gemini{border-color:#1c9a6c}.openai{border-color:#d35c33}.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}.panel{background:#f7f8fa;padding:10px;overflow:auto}pre{white-space:pre-wrap;font-size:12px}.hidden{display:none}.warning{background:#ffe7b5;color:#5e3b00;padding:10px;border-radius:8px}.primary{background:#2358d4;color:white;border:0;border-radius:6px;padding:7px 12px}.primary:disabled{background:#9aa5ba;color:#eef1f6}.empty{margin:18px;padding:18px;background:white;border-radius:12px}:focus-visible{outline:3px solid #ffbf47;outline-offset:2px}</style></head><body>
<header><h1>Dual-VLM literal diff review</h1><p class='warning'>Diagnostic only: upstream crop gate failed and literal human reference is not sealed.</p><p id='status' role='status' aria-live='polite'>Static review bundle loaded. Complete every decision and reviewer ID to enable export.</p></header><div class='metrics'>""" + metrics + """</div><fieldset class='filters'><legend>Review filters and export</legend><label>Class <select id='classFilter'><option value=''>All</option>""" + class_options + """</select></label><label>Issue <select id='categoryFilter'><option value=''>All</option><option value='value_mismatch'>value mismatch</option><option value='missing_entry'>missing entry</option><option value='header_mismatch'>header mismatch</option><option value='coordinate_mismatch'>coordinate mismatch</option></select></label><label>Medium <select id='mediumFilter'><option value=''>All</option>""" + medium_options + """</select></label><label>Provider <select id='providerFilter'><option value=''>All</option><option>gemini</option><option>openai</option></select></label><label>Page, case, table or value <input id='search' placeholder='search review cards'></label><label>Human reviewer ID <input id='reviewer'></label><button class='primary' id='export' disabled>Export decisions</button></fieldset><main>""" + cards + """</main><script>
const exportButton=document.getElementById('export'),statusLine=document.getElementById('status');function setStatus(message,isError=false){statusLine.textContent=message;statusLine.style.color=isError?'#ffd6d6':'white'}function updateExportState(){const cards=[...document.querySelectorAll('.card')],complete=cards.every(card=>card.querySelector('.operator-decision').value);exportButton.disabled=!document.getElementById('reviewer').value.trim()||!complete}function apply(){const c=document.getElementById('classFilter').value,k=document.getElementById('categoryFilter').value,m=document.getElementById('mediumFilter').value,p=document.getElementById('providerFilter').value,q=document.getElementById('search').value.toLowerCase();document.querySelectorAll('.card').forEach(x=>{const ok=(!c||x.dataset.cls===c)&&(!k||x.dataset.category.includes(k))&&(!m||x.dataset.medium===m)&&(!p||x.dataset.provider.includes(p))&&(!q||x.innerText.toLowerCase().includes(q));x.classList.toggle('hidden',!ok)})}document.querySelectorAll('select,input').forEach(x=>x.addEventListener('input',()=>{apply();updateExportState()}));updateExportState();
exportButton.addEventListener('click',()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){setStatus('Human reviewer ID is required.',true);return}const decisions=[];for(const card of document.querySelectorAll('.card')){const decision=card.querySelector('.operator-decision').value;if(!decision){setStatus('Every diff needs a decision: '+card.dataset.diffId,true);return}decisions.push({diff_id:card.dataset.diffId,decision,note:card.querySelector('.operator-note').value})}const payload={schema_version:'broker_reports_pdf_dual_vlm_literal_diff_review_decisions_v1',diffs_sha256:'""" + diffs_sha256 + """',reviewer:{type:'human',id:reviewer},reviewed_at:new Date().toISOString(),decisions};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));a.download='diff.review.decisions.private.json';a.click();URL.revokeObjectURL(a.href);setStatus('Decision file exported successfully.')});
</script></body></html>"""


def _render_card(item: dict[str, Any], review_dir: Path) -> str:
    provider = str(item.get("failed_provider") or "gemini openai")
    categories = " ".join(_filter_categories(str(item.get("class") or "")))
    asset = item.get("crop_asset")
    image = ""
    if isinstance(asset, str):
        image = (
            "<div class='crop'><img src='"
            + html.escape(asset)
            + "'>"
            + _boxes(item.get("gemini_highlighted_regions") or [], "gemini")
            + _boxes(item.get("openai_highlighted_regions") or [], "openai")
            + "</div>"
        )
    decision_options = "".join(
        f"<option>{value}</option>"
        for value in (
            "Gemini correct",
            "OpenAI correct",
            "both equivalent",
            "both wrong",
            "reference ambiguous",
            "crop problem",
            "binding problem",
        )
    )
    return (
        f"<article class='card' data-diff-id='{html.escape(item['diff_id'])}' data-cls='{html.escape(item['class'])}' data-category='{html.escape(categories)}' data-medium='{html.escape(str(item.get('evidence_medium') or 'unknown'))}' data-provider='{html.escape(provider)}'>"
        f"<h2>{html.escape(item['diff_id'])} · {html.escape(item['class'])}</h2>"
        f"<p>{html.escape(str(item.get('case_id')))} · page {item.get('page_number')} · {html.escape(str(item.get('candidate_id')))}</p>"
        + image
        + "<div class='cols'><div class='panel'><h3>Gemini</h3><pre>"
        + html.escape(json.dumps(item.get("exact_gemini_output"), ensure_ascii=False, indent=2))
        + "</pre></div><div class='panel'><h3>OpenAI</h3><pre>"
        + html.escape(json.dumps(item.get("exact_openai_output"), ensure_ascii=False, indent=2))
        + "</pre></div></div><h3>Minimal diff</h3><pre>"
        + html.escape(json.dumps(item.get("minimal_field_difference"), ensure_ascii=False, indent=2))
        + "</pre><h3>Parser/OCR evidence</h3><pre>"
        + html.escape(json.dumps(item.get("parser_or_ocr_evidence"), ensure_ascii=False, indent=2))
        + "</pre><h3>Human reference</h3><p>Pending sealed literal reference.</p>"
        + f"<label>Operator decision <select class='operator-decision'><option value=''>choose</option>{decision_options}</select></label> <label>Note <input class='operator-note'></label></article>"
    )


def _filter_categories(disagreement_class: str) -> list[str]:
    categories: list[str] = []
    if disagreement_class in {
        "visible_value_text_mismatch",
        "parsed_numeric_value_mismatch",
        "sign_mismatch",
        "decimal_or_thousands_separator_mismatch",
        "empty_vs_value_mismatch",
        "unreadable_vs_value_mismatch",
        "raw_format_only_difference",
    }:
        categories.append("value_mismatch")
    if disagreement_class.startswith(("entry_missing_", "extra_entry_")):
        categories.append("missing_entry")
    if disagreement_class in {
        "column_header_text_mismatch",
        "column_header_path_mismatch",
        "column_binding_mismatch",
    }:
        categories.append("header_mismatch")
    if disagreement_class == "source_bbox_material_mismatch":
        categories.append("coordinate_mismatch")
    return categories


def _boxes(regions: list[dict[str, Any]], class_name: str) -> str:
    result = []
    for item in regions:
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        result.append(
            f"<span class='box {class_name}' title='{html.escape(str(item.get('role')))}' style='left:{bbox[0]*100}%;top:{bbox[1]*100}%;width:{(bbox[2]-bbox[0])*100}%;height:{(bbox[3]-bbox[1])*100}%'></span>"
        )
    return "".join(result)


def _verify_terminal(
    path: Path, terminal: dict[str, Any], seal: dict[str, Any]
) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        seal.get("terminal_sha256") != digest
        or seal.get("terminal_size_bytes") != path.stat().st_size
    ):
        raise LiteralDiffBundleError("literal_diff_terminal_seal_mismatch")
    if terminal.get("reference_accessed") is not False:
        raise LiteralDiffBundleError("literal_diff_reference_boundary_invalid")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralDiffBundleError("literal_diff_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralDiffBundleError("literal_diff_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
