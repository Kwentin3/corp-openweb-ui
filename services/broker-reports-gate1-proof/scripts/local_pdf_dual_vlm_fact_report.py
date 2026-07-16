#!/usr/bin/env python3
"""Render the contractual Markdown report from a completed sealed score."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


SCORE_SCHEMA = "broker_reports_pdf_dual_vlm_fact_score_v1"
CONCLUSIONS = {
    "DUAL_VLM_FACT_ARCHITECTURE_RECOMMENDED",
    "DUAL_VLM_FACT_ARCHITECTURE_PROMISING_BUT_NOT_READY",
    "DUAL_VLM_FACT_ARCHITECTURE_NOT_JUSTIFIED",
}
GATE_KEYS = (
    "TABLE_DETECTION_AND_CROPPING",
    "DUAL_VLM_FINANCIAL_FACT_EXTRACTION",
    "FACT_EVIDENCE_VERIFICATION",
)


class ReportError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = render_report(
        score_path=Path(args.score).resolve(),
        output_path=Path(args.output).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def render_report(*, score_path: Path, output_path: Path) -> dict[str, Any]:
    score = _json_object(score_path)
    unsigned = dict(score)
    stored_checksum = unsigned.pop("score_checksum", None)
    if (
        score.get("schema_version") != SCORE_SCHEMA
        or score.get("scoring_status") != "completed"
        or stored_checksum != _sha256_json(unsigned)
    ):
        raise ReportError("dual_vlm_report_completed_score_required")
    gates = score.get("gates")
    if (
        not isinstance(gates, dict)
        or set(gates) != set(GATE_KEYS)
        or any(gates[key] not in {"PASSED", "FAILED"} for key in GATE_KEYS)
    ):
        raise ReportError("dual_vlm_report_gate_contract_invalid")
    conclusion = score.get("architectural_conclusion")
    if conclusion not in CONCLUSIONS:
        raise ReportError("dual_vlm_report_conclusion_invalid")
    rendered = _markdown(score).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_new(output_path, rendered)
    return {
        "status": "report_written",
        "output": str(output_path),
        "sha256": hashlib.sha256(rendered).hexdigest(),
        "conclusion": conclusion,
    }


def _markdown(score: dict[str, Any]) -> str:
    gates = score["gates"]
    detection = _object(score.get("detection"))
    facts = _object(score.get("facts"))
    gemini = _object(facts.get("gemini_alone"))
    openai = _object(facts.get("openai_alone"))
    consensus = _object(facts.get("canonical_consensus"))
    accepted = _object(facts.get("consensus_plus_evidence"))
    raster = _object(facts.get("raster_separate"))
    agreement = _object(facts.get("raw_model_agreement"))
    operational = _object(score.get("operational"))
    best = facts.get("best_single_provider") or "not established"
    consensus_recall_loss = _difference(
        max(_rate(gemini.get("recall")), _rate(openai.get("recall"))),
        _rate(consensus.get("recall")),
    )
    lines = [
        "TABLE_DETECTION_AND_CROPPING:",
        str(gates["TABLE_DETECTION_AND_CROPPING"]),
        "",
        "DUAL_VLM_FINANCIAL_FACT_EXTRACTION:",
        str(gates["DUAL_VLM_FINANCIAL_FACT_EXTRACTION"]),
        "",
        "FACT_EVIDENCE_VERIFICATION:",
        str(gates["FACT_EVIDENCE_VERIFICATION"]),
        "",
        str(score["architectural_conclusion"]),
        "",
        "# PDF table dual-VLM fact and evidence benchmark",
        "",
        "This is a controlled development-corpus result. It does not establish production readiness, change Gate 1 or Gate 2 authority, patch OpenWebUI core, or use RAG/vector retrieval.",
        "",
        "## Direct answers",
        "",
        f"- One-VLM detection/cropping: recall `{_fmt(detection.get('recall'))}`, precision `{_fmt(detection.get('precision'))}`, cut `{detection.get('cut_reference_tables')}`, merged `{detection.get('merged_reference_tables')}`, split `{detection.get('split_reference_tables')}`, reproducibility failures `{detection.get('crop_reproducibility_failures')}`.",
        f"- Raw Gemini/OpenAI agreement statuses: `{json.dumps(agreement, ensure_ascii=False, sort_keys=True)}`.",
        f"- Gemini alone: precision `{_fmt(gemini.get('precision'))}`, recall `{_fmt(gemini.get('recall'))}`. OpenAI alone: precision `{_fmt(openai.get('precision'))}`, recall `{_fmt(openai.get('recall'))}`. Best single provider: `{best}`.",
        f"- Canonical consensus: precision `{_fmt(consensus.get('precision'))}`, recall `{_fmt(consensus.get('recall'))}`; recall loss versus the better single-provider recall `{_fmt(consensus_recall_loss)}`.",
        f"- Consensus plus source evidence: precision `{_fmt(accepted.get('precision'))}`, recall `{_fmt(accepted.get('recall'))}`, parser/OCR accepted facts `{accepted.get('accepted_facts')}`, false accepted facts `{accepted.get('false_accepted_facts')}`.",
        f"- Human-review-required rate: `{_fmt(accepted.get('human_review_rate'))}`; provenance coverage: `{_fmt(accepted.get('provenance_coverage'))}`.",
        f"- Raster-only path: reference facts `{raster.get('reference_facts')}`, vision-only agreements `{raster.get('models_agree_vision_only')}`, automatically accepted `{raster.get('automatic_acceptance_eligible')}`. Without independent OCR, vision agreement is not source verification.",
        "- Parser-based table construction is not justified by this slice: the parser is retained only for exact text, coordinate, and relation evidence.",
        "- Smallest justified next architecture: page detector -> immutable crop -> independent Gemini/OpenAI fact extraction -> deterministic consensus -> parser evidence for text-layer facts -> bounded independent OCR only where separately justified -> human review for every unresolved or vision-only result.",
        "",
        "## Prior omissions corrected",
        "",
        "| Prior omission | Correction in this benchmark |",
        "|---|---|",
        "| One extraction VLM | Frozen Gemini and OpenAI provider/model pairs independently analyze identical crop bytes. |",
        "| Strategy C replayed Strategy B | No replay arm exists; each provider has its own preflight and one generate call. |",
        "| `human_reviewed=false` | Scoring requires a checksummed human reference and refuses missing/non-human references. |",
        "| Physical grid dominated | Financial facts and source trace are primary; layout is secondary diagnostics. |",
        "| Financial accuracy was not primary | Provider, consensus, and evidence precision/recall plus qualifier correctness are reported. |",
        "| Parser proved text existence only | Evidence requires unique row/value/header/qualifier spatial relations with parser refs. |",
        "| Raster evidence was conflated | Raster/mixed metrics are separate; no OCR means `models_agree_vision_only` and no auto-accept. |",
        "| No complete operator pack | Source-only human-reference pack and sealed-run comparison/evidence cards are generated for operator decisions. |",
        "",
        "## Safety and proof boundary",
        "",
        f"- False accepted facts: `{accepted.get('false_accepted_facts')}`.",
        f"- Invented accepted values: `{accepted.get('invented_accepted_values')}`.",
        f"- Mutated accepted values: `{accepted.get('mutated_accepted_values')}`.",
        f"- Reference human-reviewed: `{score.get('reference_human_reviewed')}`.",
        f"- Terminal verified before reference access: `{score.get('terminal_contract_verified_before_reference_access')}`.",
        f"- Terminal/reference unchanged during scoring: `{score.get('terminal_unchanged_during_scoring')}` / `{score.get('reference_unchanged_during_scoring')}`.",
        "",
        "## Operational accounting",
        "",
        "| Stage | Operations | Preflight | Generate | Input tokens | Output tokens | Latency ms | Estimated microUSD | Execution contract |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in ("detection", "gemini_extraction", "openai_extraction", "ocr"):
        item = _object(operational.get(key))
        lines.append(
            f"| {key} | {item.get('operations', 0)} | {item.get('count_or_preflight_calls', 0)} | {item.get('generate_calls', 0)} | {item.get('input_tokens', 0)} | {item.get('output_tokens', 0)} | {item.get('latency_ms', 0)} | {item.get('estimated_cost_microusd', 0)} | {item.get('execution_contract_passed', item.get('performed') is False)} |"
        )
    lines.extend(
        [
            "",
            "## Reproducibility identities",
            "",
            f"- Terminal SHA-256: `{score.get('terminal_sha256')}`.",
            f"- Manifest SHA-256: `{score.get('manifest_sha256')}`.",
            f"- Human reference SHA-256: `{score.get('reference_sha256')}`.",
            f"- Score checksum: `{score.get('score_checksum')}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReportError("dual_vlm_report_score_invalid") from exc
    if not isinstance(value, dict):
        raise ReportError("dual_vlm_report_score_invalid")
    return value


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rate(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _difference(left: float, right: float) -> float:
    return round(max(0.0, left - right), 6)


def _fmt(value: Any) -> str:
    return "not available" if value is None else str(value)


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


def _write_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


if __name__ == "__main__":
    raise SystemExit(main())
