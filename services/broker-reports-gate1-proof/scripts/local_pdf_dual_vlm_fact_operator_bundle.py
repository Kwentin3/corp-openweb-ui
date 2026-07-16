#!/usr/bin/env python3
"""Create a sealed-run operator review bundle for every detected table crop."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any


TERMINAL_SCHEMA = "broker_reports_pdf_dual_vlm_fact_terminal_v1"
SEAL_SCHEMA = "broker_reports_pdf_dual_vlm_fact_terminal_seal_v1"
INDEX_SCHEMA = "broker_reports_pdf_dual_vlm_fact_operator_review_index_v1"
INTENT_SCHEMA = "broker_reports_pdf_dual_vlm_fact_operator_review_intent_v1"
CHECKLIST = (
    "crop_completeness",
    "row_label",
    "value",
    "sign",
    "period",
    "currency",
    "scale",
    "header_relationship",
    "source_address",
    "missing_or_invented_facts",
)


class OperatorBundleError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    result = build_operator_bundle(
        terminal_path=Path(args.terminal).resolve(),
        seal_path=Path(args.seal).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_operator_bundle(
    *, terminal_path: Path, seal_path: Path, output_dir: Path
) -> dict[str, Any]:
    terminal_bytes = terminal_path.read_bytes()
    terminal_sha = hashlib.sha256(terminal_bytes).hexdigest()
    terminal = _json_object(terminal_bytes, "operator_bundle_terminal_invalid")
    seal = _json_object(seal_path.read_bytes(), "operator_bundle_seal_invalid")
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA
        or seal.get("schema_version") != SEAL_SCHEMA
        or seal.get("terminal_sha256") != terminal_sha
        or seal.get("terminal_size_bytes") != len(terminal_bytes)
        or seal.get("reference_accessed") is not False
        or terminal.get("reference_accessed") is not False
    ):
        raise OperatorBundleError("operator_bundle_terminal_seal_mismatch")
    _require_fresh(output_dir)
    artifact_root = terminal_path.parent.resolve()
    cards: list[dict[str, Any]] = []
    image_data: dict[str, dict[str, str | None]] = {}
    for case in terminal.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or "unknown_case")
        case_input = case.get("input") if isinstance(case.get("input"), dict) else {}
        page_path = _artifact_path(artifact_root, case_input.get("page_artifact"))
        page_meta, page_uri = _image(page_path) if page_path else (None, None)
        crops = [item for item in case.get("crops") or [] if isinstance(item, dict)]
        if not crops:
            card_id = f"case:{case_id}:no_crop"
            card = {
                "card_id": card_id,
                "card_kind": "case_without_crop",
                "case_id": case_id,
                "page_number": case_input.get("page_number"),
                "pdf_sha256": case_input.get("pdf_sha256"),
                "detected_bbox": None,
                "page_artifact": page_meta,
                "crop_artifact": None,
                "detection": copy.deepcopy(case.get("detection")),
                "crop_contract": None,
                "gemini": None,
                "openai": None,
                "consensus": None,
                "evidence": None,
                "outcomes": [
                    {
                        "status": case.get("terminal_status"),
                        "reason": _case_reason(case),
                    }
                ],
                "checklist_fields": list(CHECKLIST),
            }
            cards.append(card)
            image_data[card_id] = {"page": page_uri, "crop": None}
            continue
        for crop_index, crop in enumerate(crops, start=1):
            card_id = f"crop:{case_id}:{crop_index}"
            candidate = crop.get("candidate")
            candidate = candidate if isinstance(candidate, dict) else {}
            crop_path = _artifact_path(artifact_root, crop.get("crop_artifact"))
            crop_meta, crop_uri = _image(crop_path) if crop_path else (None, None)
            card = {
                "card_id": card_id,
                "card_kind": "detected_crop",
                "case_id": case_id,
                "page_number": case_input.get("page_number"),
                "pdf_sha256": case_input.get("pdf_sha256"),
                "detected_bbox": copy.deepcopy(candidate.get("bbox")),
                "candidate_id": candidate.get("candidate_id"),
                "page_artifact": page_meta,
                "crop_artifact": crop_meta,
                "detection": copy.deepcopy(case.get("detection")),
                "crop_contract": copy.deepcopy(crop.get("crop_contract")),
                "same_crop_sha256_for_both_extractors": crop.get(
                    "same_crop_sha256_for_both_extractors"
                ),
                "evidence_medium": crop.get("evidence_medium"),
                "gemini": _provider_view(crop.get("gemini")),
                "openai": _provider_view(crop.get("openai")),
                "consensus": copy.deepcopy(crop.get("consensus")),
                "evidence": copy.deepcopy(crop.get("evidence")),
                "outcomes": _outcomes(crop),
                "checklist_fields": list(CHECKLIST),
            }
            cards.append(card)
            image_data[card_id] = {"page": page_uri, "crop": crop_uri}
    index: dict[str, Any] = {
        "schema_version": INDEX_SCHEMA,
        "terminal_sha256": terminal_sha,
        "manifest_sha256": terminal.get("manifest_sha256"),
        "reference_available": False,
        "human_reference_used": False,
        "cards": cards,
    }
    index["index_sha256"] = _sha256_json(index)
    index_path = output_dir / "operator-review.index.json"
    html_path = output_dir / "operator-review.html"
    _write_new(index_path, _canonical_json(index))
    rendered = _render(index, image_data).encode("utf-8")
    _write_new(html_path, rendered)
    return {
        "status": "operator_review_required",
        "cards": len(cards),
        "terminal_sha256": terminal_sha,
        "index": str(index_path),
        "index_sha256": index["index_sha256"],
        "html": str(html_path),
        "html_sha256": hashlib.sha256(rendered).hexdigest(),
    }


def _provider_view(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    operation = value.get("operation")
    operation = operation if isinstance(operation, dict) else {}
    attempt = operation.get("attempt")
    attempt = attempt if isinstance(attempt, dict) else {}
    return {
        "status": value.get("status"),
        "contract_errors": copy.deepcopy(value.get("contract_errors") or []),
        "output": copy.deepcopy(value.get("output")),
        "operation": {
            "kind": operation.get("kind"),
            "task_id": operation.get("task_id"),
            "image_bytes": operation.get("image_bytes"),
            "count_attempted": operation.get("count_attempted"),
            "generate_attempted": operation.get("generate_attempted"),
            "count_tokens": copy.deepcopy(operation.get("count_tokens")),
            "failure_code": operation.get("failure_code"),
            "attempt": copy.deepcopy(attempt),
        },
    }


def _outcomes(crop: dict[str, Any]) -> list[dict[str, Any]]:
    consensus = crop.get("consensus")
    consensus = consensus if isinstance(consensus, dict) else {}
    evidence = crop.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    evidence_by_fact = {
        str(item.get("fact_id")): item
        for item in evidence.get("source_maps") or []
        if isinstance(item, dict)
    }
    result = []
    for entry in consensus.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        fact_id = str(entry.get("consensus_id") or "")
        source_map = evidence_by_fact.get(fact_id)
        result.append(
            {
                "fact_id": fact_id,
                "consensus_status": entry.get("status"),
                "runtime_disposition": entry.get("runtime_disposition"),
                "material_differences": copy.deepcopy(
                    entry.get("material_differences") or []
                ),
                "evidence_status": (
                    source_map.get("evidence_status") if source_map else None
                ),
                "automatic_acceptance_eligible": (
                    source_map.get("automatic_acceptance_eligible")
                    if source_map
                    else False
                ),
                "reason_codes": copy.deepcopy(
                    source_map.get("reason_codes") if source_map else []
                ),
                "source_address": copy.deepcopy(
                    source_map.get("relation_candidates") if source_map else []
                ),
            }
        )
    if not result:
        result.append(
            {
                "fact_id": None,
                "consensus_status": crop.get("terminal_status"),
                "runtime_disposition": "human_review_required",
                "material_differences": [],
                "evidence_status": None,
                "automatic_acceptance_eligible": False,
                "reason_codes": [_crop_reason(crop)],
                "source_address": [],
            }
        )
    return result


def _render(index: dict[str, Any], image_data: dict[str, dict[str, str | None]]) -> str:
    cards = "".join(
        _render_card(card, image_data[card["card_id"]]) for card in index["cards"]
    )
    embedded = json.dumps(index, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dual-VLM PDF financial fact operator review</title>
<style>
:root {{ font-family: system-ui,sans-serif; color-scheme:light dark }}
body {{ margin:0 }} main {{ max-width:96rem; margin:auto; padding:1rem }}
article {{ border:1px solid currentColor; border-radius:.5rem; margin:1rem 0; padding:1rem }}
.images {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(22rem,1fr)); gap:1rem }}
.image-wrap {{ position:relative; display:inline-block; max-width:100% }}
img {{ display:block; max-width:100%; max-height:52rem; border:1px solid #777 }}
.box {{ position:absolute; box-sizing:border-box; pointer-events:none; border:.22rem solid #d4351c }}
.row {{ border-color:#1d70b8 }} .value {{ border-color:#00703c }} .header {{ border-color:#f47738 }}
fieldset {{ margin:1rem 0 }} label {{ display:block; margin:.35rem 0 }}
textarea,select {{ width:min(100%,64rem); box-sizing:border-box }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:32rem; overflow:auto }}
button {{ padding:.7rem 1rem; font-weight:700 }}
:focus-visible {{ outline:.25rem solid #ffbf47; outline-offset:.2rem }}
.state {{ border-left:.35rem solid #1d70b8; padding:.75rem }}
</style></head><body><main id="app" aria-busy="false">
<h1>Dual-VLM PDF financial fact operator review</h1>
<p>This sealed-run pack shows source images, both provider outputs, deterministic consensus,
evidence, and exact rejection/review reasons. It exports operator intent only.</p>
<section class="state" id="status" role="status" aria-live="polite">
Loaded {len(index["cards"])} review cards. Human reference was not used.</section>
<form id="form"><section>{cards}</section>
<button type="button" id="export">Export operator review intent JSON</button>
<p id="feedback" role="status" aria-live="polite">No export attempted.</p></form>
</main><script id="index" type="application/json">{embedded}</script>
<script>(()=>{{'use strict';const index=JSON.parse(document.getElementById('index').textContent);
const safe=s=>s.replace(/[^A-Za-z0-9_-]/g,'_');
const selected=name=>{{const x=document.querySelector(`input[name="${{CSS.escape(name)}}"]:checked`);return x?x.value:'pending'}};
document.getElementById('export').addEventListener('click',()=>{{
 const entries=index.cards.map(card=>{{const id=safe(card.card_id);return{{card_id:card.card_id,
 decision:selected(`${{id}}-decision`),note:document.getElementById(`${{id}}-note`).value,
 corrected_json:document.getElementById(`${{id}}-corrected`).value.trim()||null,
 checklist:Object.fromEntries(card.checklist_fields.map(field=>[field,document.getElementById(`${{id}}-${{field}}`).value])),
 fact_decisions:card.outcomes.filter(x=>x.fact_id).map(x=>{{const f=safe(`${{id}}-${{x.fact_id}}`);return{{fact_id:x.fact_id,decision:selected(`${{f}}-decision`),note:document.getElementById(`${{f}}-note`).value}}}})}}}});
 const intent={{schema_version:{json.dumps(INTENT_SCHEMA)},terminal_sha256:index.terminal_sha256,index_sha256:index.index_sha256,entries}};
 const url=URL.createObjectURL(new Blob([JSON.stringify(intent,null,2)],{{type:'application/json'}}));
 const a=document.createElement('a');a.href=url;a.download='operator-review.intent.json';a.click();URL.revokeObjectURL(url);
 document.getElementById('feedback').textContent='Operator intent exported; no benchmark truth or acceptance was changed.';
}});}})();</script></body></html>"""


def _render_card(card: dict[str, Any], images: dict[str, str | None]) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", card["card_id"])
    page_overlay = _overlay(card.get("detected_bbox"), "box", "Detected bbox")
    crop_overlays = _evidence_overlays(card.get("evidence"))
    page = _figure(images.get("page"), "Source page", page_overlay)
    crop = _figure(
        images.get("crop"), "Immutable crop with evidence regions", crop_overlays
    )
    provider_sections = "".join(
        _json_details(label, card.get(key))
        for label, key in (("Gemini result", "gemini"), ("OpenAI result", "openai"))
    )
    consensus = _json_details("Canonical consensus", card.get("consensus"))
    evidence = _json_details(
        "Parser/OCR evidence and source addresses", card.get("evidence")
    )
    outcomes = "".join(_render_outcome(safe, item) for item in card["outcomes"])
    checklist = "".join(
        f'<label for="{safe}-{field}">{html.escape(field.replace("_", " ").title())}</label>'
        f'<select id="{safe}-{field}"><option value="pending">Choose…</option>'
        '<option value="pass">Pass</option><option value="issue">Issue</option>'
        '<option value="uncertain">Uncertain</option></select>'
        for field in card["checklist_fields"]
    )
    return f"""<article aria-labelledby="{safe}-title"><h2 id="{safe}-title">
{html.escape(card["case_id"])} · {html.escape(str(card.get("candidate_id") or card["card_kind"]))}</h2>
<p>Page {html.escape(str(card.get("page_number")))} · PDF {html.escape(str(card.get("pdf_sha256")))}<br>
Evidence medium: {html.escape(str(card.get("evidence_medium") or "not applicable"))}</p>
<div class="images">{page}{crop}</div>{provider_sections}{consensus}{evidence}
<section aria-label="Fact outcomes"><h3>Fact outcomes</h3>{outcomes}</section>
<fieldset><legend>Table decision</legend>{_radios(safe, "decision")}
<label for="{safe}-note">Decision note</label><textarea id="{safe}-note" rows="3"></textarea>
<label for="{safe}-corrected">Corrected JSON when needed</label><textarea id="{safe}-corrected" rows="5"></textarea></fieldset>
<fieldset><legend>Checklist</legend>{checklist}</fieldset></article>"""


def _render_outcome(card_safe: str, value: dict[str, Any]) -> str:
    fact_id = value.get("fact_id")
    if not fact_id:
        return _json_details("No canonical fact outcome", value)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", f"{card_safe}-{fact_id}")
    rendered = html.escape(json.dumps(value, ensure_ascii=False, indent=2))
    return f"""<fieldset><legend>{html.escape(str(fact_id))}</legend>
<pre>{rendered}</pre>{_radios(safe, "decision")}
<label for="{safe}-note">Fact decision note</label><textarea id="{safe}-note" rows="2"></textarea></fieldset>"""


def _radios(prefix: str, field: str) -> str:
    return "".join(
        f'<label><input type="radio" name="{prefix}-{field}" value="{value}"> {label}</label>'
        for value, label in (
            ("confirm", "Confirm"),
            ("correct", "Correct"),
            ("ambiguous", "Ambiguous"),
            ("reject", "Reject"),
        )
    )


def _figure(uri: str | None, caption: str, overlays: str) -> str:
    if uri is None:
        return f"<figure><figcaption>{html.escape(caption)}</figcaption><p>Artifact unavailable.</p></figure>"
    return (
        f"<figure><figcaption>{html.escape(caption)}</figcaption>"
        f'<span class="image-wrap"><img src="{uri}" alt="{html.escape(caption)}">'
        f"{overlays}</span></figure>"
    )


def _evidence_overlays(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    rendered = []
    for source_map in value.get("source_maps") or []:
        requests = (
            source_map.get("evidence_requests")
            if isinstance(source_map, dict)
            else None
        )
        if not isinstance(requests, dict):
            continue
        for role, item in (
            ("row", requests.get("row_label")),
            ("value", requests.get("value")),
        ):
            if isinstance(item, dict):
                rendered.append(
                    _overlay(item.get("crop_normalized_bbox"), f"box {role}", role)
                )
        for item in requests.get("headers") or []:
            if isinstance(item, dict):
                rendered.append(
                    _overlay(item.get("crop_normalized_bbox"), "box header", "header")
                )
    return "".join(rendered)


def _overlay(bbox: Any, css_class: str, label: str) -> str:
    if not _bbox(bbox):
        return ""
    x0, y0, x1, y1 = (float(item) for item in bbox)
    return (
        f'<span class="{css_class}" aria-label="{html.escape(label)}" '
        f'style="left:{x0 * 100:.6f}%;top:{y0 * 100:.6f}%;'
        f'width:{(x1 - x0) * 100:.6f}%;height:{(y1 - y0) * 100:.6f}%"></span>'
    )


def _json_details(label: str, value: Any) -> str:
    rendered = html.escape(json.dumps(value, ensure_ascii=False, indent=2))
    return f"<details><summary>{html.escape(label)}</summary><pre>{rendered}</pre></details>"


def _artifact_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise OperatorBundleError("operator_bundle_artifact_path_escape") from exc
    if not path.is_file():
        raise OperatorBundleError("operator_bundle_artifact_missing")
    return path


def _image(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if path.suffix.casefold() != ".png":
        raise OperatorBundleError("operator_bundle_image_type_invalid")
    return (
        {"filename": path.name, "sha256": sha, "bytes": len(payload)},
        "data:image/png;base64," + base64.b64encode(payload).decode("ascii"),
    )


def _case_reason(case: dict[str, Any]) -> str:
    detection = case.get("detection")
    detection = detection if isinstance(detection, dict) else {}
    errors = detection.get("contract_errors") or []
    return str(errors[0]) if errors else str(case.get("terminal_status") or "no_crop")


def _crop_reason(crop: dict[str, Any]) -> str:
    for arm in ("gemini", "openai"):
        value = crop.get(arm)
        if isinstance(value, dict) and value.get("contract_errors"):
            return str(value["contract_errors"][0])
    return str(crop.get("reason") or crop.get("terminal_status") or "no_consensus")


def _bbox(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and 0 <= float(value[0]) < float(value[2]) <= 1
        and 0 <= float(value[1]) < float(value[3]) <= 1
    )


def _json_object(payload: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise OperatorBundleError(code) from exc
    if not isinstance(value, dict):
        raise OperatorBundleError(code)
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require_fresh(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise OperatorBundleError("operator_bundle_fresh_output_required")
    path.mkdir(parents=True, exist_ok=True)


def _write_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


if __name__ == "__main__":
    raise SystemExit(main())
