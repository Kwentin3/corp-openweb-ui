#!/usr/bin/env python3
"""Render the evidence-bounded literal key-value benchmark report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"

sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_literal_contracts import sha256_json  # noqa: E402


class LiteralReportError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--detection-terminal", required=True)
    parser.add_argument("--detection-seal", required=True)
    parser.add_argument("--padding-experiment", required=True)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--terminal-seal", required=True)
    parser.add_argument("--diffs", required=True)
    parser.add_argument("--reference-draft", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    manifest = _json(Path(args.manifest).resolve())
    detection_terminal_path = Path(args.detection_terminal).resolve()
    detection_seal_path = Path(args.detection_seal).resolve()
    padding_path = Path(args.padding_experiment).resolve()
    terminal_path = Path(args.terminal).resolve()
    seal_path = Path(args.terminal_seal).resolve()
    diffs_path = Path(args.diffs).resolve()
    draft_path = Path(args.reference_draft).resolve()
    padding = _json(padding_path)
    detection_terminal = _json(detection_terminal_path)
    detection_seal = _json(detection_seal_path)
    terminal = _json(terminal_path)
    seal = _json(seal_path)
    diffs = _json(diffs_path)
    draft = _json(draft_path)
    _verify_inputs(
        manifest,
        padding,
        detection_terminal_path,
        detection_terminal,
        detection_seal,
        terminal_path,
        terminal,
        seal,
        diffs,
        draft,
    )
    output = Path(args.output).resolve()
    if output.name != "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_KEY_VALUE_BENCHMARK.report.md":
        raise LiteralReportError("literal_report_filename_invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _render(
            manifest=manifest,
            padding=padding,
            detection_terminal=detection_terminal,
            terminal=terminal,
            diffs=diffs,
            draft=draft,
            identities={
                "padding": hashlib.sha256(padding_path.read_bytes()).hexdigest(),
                "detection_terminal": detection_seal["terminal_sha256"],
                "terminal": seal["terminal_sha256"],
                "diffs": hashlib.sha256(diffs_path.read_bytes()).hexdigest(),
                "reference_draft": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
            },
        ),
        encoding="utf-8-sig",
    )
    print(json.dumps({"report": str(output), "report_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "conclusion": "DUAL_VLM_LITERAL_EXTRACTION_PROMISING_BUT_NOT_READY"}, ensure_ascii=False, sort_keys=True))
    return 0


def _render(
    *,
    manifest: dict[str, Any],
    padding: dict[str, Any],
    detection_terminal: dict[str, Any],
    terminal: dict[str, Any],
    diffs: dict[str, Any],
    draft: dict[str, Any],
    identities: dict[str, str],
) -> str:
    summary = diffs["summary"]
    agreement = summary["agreement_metrics"]
    detection = padding["detection_metrics"]
    variants = padding["variant_results"]
    reference_entries = sum(
        len(table.get("entries") or [])
        for case in draft.get("cases") or []
        for table in case.get("tables") or []
    )
    missing_locators = sum(
        entry.get("row_label_bbox") is None or entry.get("value_bbox") is None
        for case in draft.get("cases") or []
        for table in case.get("tables") or []
        for entry in table.get("entries") or []
    )
    evidence = _agreement_evidence(terminal)
    accounting = _operational_accounting(
        manifest, detection_terminal, terminal, padding, diffs
    )
    variant_rows = "\n".join(
        "| {padding:g}% | {cut} | {merged} | {split} | {adjacent} | {missed} | {false} | {invalid} | {repro} | {passed} |".format(
            padding=float(item["padding_percent_per_page_side"]),
            cut=item["cut_reference_tables"],
            merged=item["merged_reference_tables"],
            split=item["split_reference_tables"],
            adjacent=item["adjacent_table_inclusion"],
            missed=item["missed_reference_tables"],
            false=item["false_candidates"],
            invalid=item["invalid_bboxes"],
            repro=item["crop_reproducibility_failures"],
            passed=str(item["selection_conditions_passed"]),
        )
        for item in variants
    )
    class_rows = "\n".join(
        f"| `{name}` | {count} |"
        for name, count in summary["disagreements_by_class"].items()
    )
    failure_rows = "\n".join(_detection_failure_rows(padding))
    operation_rows = "\n".join(
        f"| {item['stage']} | {item['operations']} | {item['preflight']} | {item['generate']} | {item['input_bytes']} | {item['input_tokens']} | {item['output_tokens']} | {item['latency_ms']} | {item['estimated_micro_usd']} | {item['terminal_failures']} |"
        for item in accounting
    )
    removed_keywords = len(
        terminal["schema_equivalence"].get("removed_keywords") or []
    )
    largest_variant = max(
        variants, key=lambda item: float(item["padding_fraction_per_page_side"])
    )
    largest_cut_ids = [
        f"{item['case_id']}:{item['reference_region_id']}"
        for item in largest_variant.get("crops") or []
        if not item.get("complete_reference_table_contained")
    ]
    largest_cut_text = ", ".join(f"`{item}`" for item in largest_cut_ids)
    numeric_differences = max(
        0,
        int(agreement["numeric_comparable_entries"])
        - int(agreement["numeric_agreements"]),
    )
    provider_table_total = int(summary["tables_sent_to_both_providers"])
    gemini_terminal_failures = (
        provider_table_total - int(summary["gemini_contract_valid_tables"])
    )
    openai_terminal_failures = (
        provider_table_total - int(summary["openai_contract_valid_tables"])
    )
    padding_crop_count = sum(
        len(candidate.get("padding_variants") or [])
        for case in detection_terminal.get("cases") or []
        for candidate in case.get("candidates") or []
    )
    return f"""TABLE_DETECTION_AND_PADDED_CROPPING:
FAILED

GEMINI_LITERAL_TABLE_READING:
FAILED

OPENAI_LITERAL_TABLE_READING:
FAILED

DUAL_VLM_LITERAL_AGREEMENT:
FAILED

LITERAL_SOURCE_EVIDENCE:
FAILED

DUAL_VLM_LITERAL_EXTRACTION_PROMISING_BUT_NOT_READY

# PDF table detection padding and dual-VLM literal key-value benchmark

This is a controlled development-corpus diagnostic. It does not migrate production, change Gate 1 or Gate 2 authority, patch OpenWebUI core, construct tables with the parser, classify financial meaning, or establish production readiness.

## Plain conclusion

No fixed padding was selected. Under the corrected coordinate contract, the page detector itself reached recall `{_rate(detection['recall'])}` and precision `{_rate(detection['precision'])}` with `{detection['invalid_bboxes']}` invalid bboxes, `{largest_variant['missed_reference_tables']}` missed tables, and `{largest_variant['false_candidates']}` false candidates. Cropping still failed: even the largest predeclared `3.0%` padding left {largest_variant['cut_reference_tables']} incomplete crops ({largest_cut_text}).

The diagnostic dual-provider run is nevertheless useful: both responses passed the literal schema on `{summary['dual_contract_valid_tables']}/{provider_table_total}` crops. Among `{agreement['unique_aligned_entries']}` unique alignments, `{agreement['exact_raw_key_header_value_agreements']}` were exact raw key-header-value agreements, `{agreement['numeric_agreements']}/{agreement['numeric_comparable_entries']}` comparable numeric pairs agreed, and `{agreement['canonical_agreements_with_compatible_source_regions']}` canonical agreements had compatible source regions. This is not an acceptance result: `{agreement['entry_alignment_ambiguous']}` alignments were ambiguous, Gemini had `{gemini_terminal_failures}` terminal contract failures, OpenAI had `{openai_terminal_failures}`, and only `{evidence['both_parser_verified']}` unique agreements were independently parser-verified in both arms.

The systematic coordinate-order error from prompt contract v1 is repaired in v2; the old sealed runs remain preserved as pre-v2 history. The remaining problems are crop completeness, literal reading/header binding disagreements, and incomplete independent evidence. The second VLM is useful as a disagreement and contract-failure detector in research, but material runtime benefit is not established without a valid crop set, a sealed literal reference, independent source verification, and provider scoring.

## Direct answers

- Selected fixed padding: **none**. `3.0%` per page side was used only for an explicitly invalid-upstream diagnostic; it is not the selected benchmark padding.
- Truncated crops eliminated: **no**. At `3.0%`, {largest_variant['cut_reference_tables']}/{detection['reference_tables']} matched reference tables remained cut: {largest_cut_text}.
- Adjacent reference tables captured by padding: `0` for every declared variant. This does not rescue the gate because crop completeness failed.
- Literal entries returned: Gemini `{summary['total_gemini_entries']}`, OpenAI `{summary['total_openai_entries']}` across all parsed responses, including contract-invalid responses and partial crops. Contract-valid table responses were Gemini `{summary['gemini_contract_valid_tables']}/{provider_table_total}`, OpenAI `{summary['openai_contract_valid_tables']}/{provider_table_total}`, both `{summary['dual_contract_valid_tables']}/{provider_table_total}`.
- Exact raw key-header-value agreements: `{agreement['exact_raw_key_header_value_agreements']}` unique alignments. Safe-canonical agreements: `{agreement['canonical_key_header_value_agreements']}`. Agreements with compatible source regions: `{agreement['canonical_agreements_with_compatible_source_regions']}`.
- Numeric values differing: `{numeric_differences}` among `{agreement['numeric_comparable_entries']}` uniquely aligned numeric pairs. This is diagnostic-only and does not cover invalid, missing, or ambiguous entries.
- Row-label differences: `{summary['disagreements_by_class'].get('row_label_text_mismatch', 0)}`. Header-path differences: `{summary['disagreements_by_class'].get('column_header_path_mismatch', 0)}`. Another `{agreement['entry_alignment_ambiguous']}` alignments remained ambiguous and cannot be counted as correct.
- Wrong row/column binding: not scoreable without the sealed literal reference. Diagnostics found `{summary['disagreements_by_class'].get('source_bbox_material_mismatch', 0)}` material source-bbox mismatches and `{agreement['entry_alignment_ambiguous']}` ambiguous alignments.
- Provider-to-provider missing entries: Gemini `{summary['missing_entries_in_gemini']}`, OpenAI `{summary['missing_entries_in_openai']}`. Misses and inventions against human truth remain unavailable.
- Gemini-correct/OpenAI-wrong, OpenAI-correct/Gemini-wrong, both-wrong, and both-correct-format-different cases: **not scoreable** because the new literal reference is not yet human-reviewed and sealed. The benchmark does not substitute the old semantic reference.
- Independently verified agreements: Gemini parser-verified `{evidence['gemini_parser_verified']}`, OpenAI parser-verified `{evidence['openai_parser_verified']}`, both arms parser-verified `{evidence['both_parser_verified']}` of `{evidence['unique_aligned']}` unique alignments. OCR was not available and was not improvised.
- Dominant disagreement classes: header-path (`{summary['disagreements_by_class'].get('column_header_path_mismatch', 0)}`), row-label (`{summary['disagreements_by_class'].get('row_label_text_mismatch', 0)}`), and visible-value (`{summary['disagreements_by_class'].get('visible_value_text_mismatch', 0)}`) mismatches, followed by missing entries and numeric differences.
- Smallest justified next architecture: keep this as research only; create a new frozen benchmark version with a predeclared wider **global** padding range sufficient to test the observed maximum border gap, without per-table tuning, then rerun Gate A. Only after Gate A passes should the tested chain be scored: one detector -> global deterministic padding -> immutable crop -> independent Gemini/OpenAI literal extraction -> deterministic field diff -> parser evidence for text-layer tables -> bounded independent OCR only where separately justified -> human review -> observed key-header-value map. Financial semantic classification remains a separate Gate 3.

## Gate A — detection and crop padding

| Metric | Result | Gate |
|---|---:|---:|
| reference tables | {detection['reference_tables']} | — |
| matched tables | {detection['matched_tables']} | {detection['reference_tables']} |
| recall | `{_rate(detection['recall'])}` | `1.000000` |
| precision | `{_rate(detection['precision'])}` | `>=0.900000` |
| invalid bboxes | {detection['invalid_bboxes']} | `0` |

| Padding per side | Cut | Merged | Split | Adjacent | Missed | False | Invalid | Repro failures | Selectable |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{variant_rows}

The detector bbox was preserved separately from every padded crop bbox. Invalid bboxes were terminal and were never clamped or repaired. Crop reproducibility failures were zero for all rendered valid candidates. Extra-area, dimensions, checksums, and the exact transformations are recorded per crop in the padding artifact. Neighbouring prose is conservatively marked as possible wherever padding added non-reference area; downstream padding effect was not isolated because no variant passed.

### Coordinate-contract correction

The first literal prompt version named normalized coordinates but did not spell out array order. Visual overlay audit showed Gemini interpreting several arrays as `[top, left, bottom, right]`. Prompt/schema/model-view v2 now state `[x0, y0, x1, y1] = [left, top, right, bottom]`, identify horizontal and vertical axes, and explicitly forbid the transposed order. This was rerun as new sealed lineage; no pre-v2 terminal was mutated.

### Exact detection regressions/failures

| Case | Failure |
|---|---|
{failure_rows}

## Literal reference boundary

- New literal reference draft entries: `{reference_entries}`; prior human semantic-fact lineage exists for `83`, while `6` entries are new to literal scope.
- Entries still missing row/value locators in the draft: `{missing_locators}`.
- `human_reviewed=false`; all `{reference_entries}` entries require a new literal-contract operator decision.
- The accepted `OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json` was **not** fabricated. It will exist only after complete human decisions pass the finalizer and receive a separate checksum.
- The sealed-reference scorer is implemented but was not run: it rejects an unsealed/non-human reference, projects both reference and provider locators into the same page coordinate space, excludes `ambiguous`/`excluded` entries from denominators, scores each provider independently, and attaches human answers to a new scored diff artifact without mutating the sealed terminal.
- The reference was unavailable to detection, crop rendering, prompts, provider adapters, consensus, and reference-free diff generation.

## Provider schema and execution equivalence

- Canonical fixture round-trip equivalent: `{terminal['schema_equivalence']['canonical_fixture_roundtrip']['canonical_equivalence']}`.
- Required field/cardinality equivalent: `{terminal['schema_equivalence']['required_field_cardinality_equivalent']}`; enum meaning equivalent: `{terminal['schema_equivalence']['enum_meaning_equivalent']}`; nullability equivalent: `{terminal['schema_equivalence']['nullability_equivalent']}`.
- Gemini projection removed or transformed `{removed_keywords}` recorded schema keywords while preserving the tested logical requirements. OpenAI used the canonical strict schema.
- This compares `model + provider API + schema adapter`; it is not an isolated model comparison.
- Every attempted extraction arm used one preflight and one generate, attempt number `1`, empty attempt lineage, zero retry, zero failover, and identical crop/model-view/canonical-schema hashes.
- Malformed provider outputs remained terminal; no LLM or deterministic semantic repair changed them.

## Diagnostic disagreement distribution

| Class | Count |
|---|---:|
{class_rows}

Detailed cards exist only for disagreements and terminal failures. Agreements are compact machine records. The HTML bundle supports class/provider/text filtering and includes the immutable crop, both source-box overlays, exact readings, minimal diff, parser evidence, pending human-reference slot, and operator controls.

## Evidence and acceptance

- Automatically accepted entries: `0`.
- False/invented/mutated automatically accepted entries: `0` by fail-closed behavior, not by successful recall.
- Accepted-entry source coverage: not applicable because nothing passed the acceptance conjunction.
- Parser constructed tables: `false`; parser chose a provider or rewrote text: `false`.
- Raster/mixed entries without independent OCR remained vision-only and review-only.

## Operational accounting

| Stage | Operations | Preflight | Generate | Input bytes | Input tokens | Output tokens | Latency ms | Estimated microUSD | Terminal failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{operation_rows}

Padding accounting reports `{padding_crop_count}` variant crops and `{padding_crop_count * 2}` deterministic render operations over {detection['present_candidates']} valid detector candidates. Cost uses the frozen pricing snapshot in the versioned manifest and is only an estimate.

## Reproducibility identities

- Detection terminal SHA-256: `{identities['detection_terminal']}`.
- Padding experiment SHA-256: `{identities['padding']}`.
- Diagnostic terminal SHA-256: `{identities['terminal']}`.
- Machine diff SHA-256: `{identities['diffs']}`.
- Literal reference draft SHA-256: `{identities['reference_draft']}` (not an accepted reference seal).

## Proof boundary

The benchmark repaired the semantic-contract error: provider prompts and scoring contracts contain no financial fact type, accounting category, normalized business concept, semantic entity class, or inferred financial role. No type mapping was introduced. The current output remains diagnostic observed table mappings with source trace; it is not normalized financial facts and is not production authority.
"""


def _detection_failure_rows(padding: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for case in padding.get("cases") or []:
        case_id = str(case["case_id"])
        for region_id in case.get("missed_reference_region_ids") or []:
            rows.append(f"| `{case_id}` | missed reference table `{region_id}` |")
        for candidate_id in case.get("false_candidate_ids") or []:
            rows.append(f"| `{case_id}` | false/unmatched candidate `{candidate_id}` |")
        if int(case.get("invalid_bbox_count") or 0):
            rows.append(
                f"| `{case_id}` | invalid bbox count `{case['invalid_bbox_count']}` |"
            )
    largest = max(
        padding.get("variant_results") or [],
        key=lambda item: float(item["padding_fraction_per_page_side"]),
    )
    for crop in largest.get("crops") or []:
        if not crop.get("complete_reference_table_contained"):
            rows.append(
                f"| `{crop['case_id']}` | cut `{crop['reference_region_id']}` remains at `3.0%` |"
            )
    return rows or ["| — | none |"]


def _agreement_evidence(terminal: dict[str, Any]) -> dict[str, int]:
    result = {
        "unique_aligned": 0,
        "gemini_parser_verified": 0,
        "openai_parser_verified": 0,
        "both_parser_verified": 0,
    }
    for crop in terminal.get("crops") or []:
        diffs = crop.get("provider_diffs_reference_free")
        if not isinstance(diffs, dict):
            continue
        evidence = crop.get("parser_evidence") or {}
        for match in (diffs.get("alignment") or {}).get("matches") or []:
            if not match.get("match_unique"):
                continue
            result["unique_aligned"] += 1
            gemini = _entry_evidence(
                evidence.get("gemini"), match.get("gemini_entry_id")
            )
            openai = _entry_evidence(
                evidence.get("openai"), match.get("openai_entry_id")
            )
            gemini_verified = (gemini or {}).get("status") == "parser_literal_verified"
            openai_verified = (openai or {}).get("status") == "parser_literal_verified"
            result["gemini_parser_verified"] += int(gemini_verified)
            result["openai_parser_verified"] += int(openai_verified)
            result["both_parser_verified"] += int(gemini_verified and openai_verified)
    return result


def _entry_evidence(values: Any, entry_id: Any) -> dict[str, Any] | None:
    if not isinstance(values, list):
        return None
    return next(
        (
            item
            for item in values
            if isinstance(item, dict) and item.get("entry_id") == entry_id
        ),
        None,
    )


def _operational_accounting(
    manifest: dict[str, Any],
    detection_terminal: dict[str, Any],
    terminal: dict[str, Any],
    padding: dict[str, Any],
    diffs: dict[str, Any],
) -> list[dict[str, Any]]:
    detection_operations = [
        case["detection"]
        for case in detection_terminal.get("cases") or []
        if isinstance(case.get("detection"), dict)
    ]
    extraction: dict[str, list[dict[str, Any]]] = {"gemini": [], "openai": []}
    for crop in terminal.get("crops") or []:
        for provider in extraction:
            operation = crop.get(provider)
            if isinstance(operation, dict) and operation.get("task_id"):
                extraction[provider].append(operation)
    result = [
        {
            "stage": "detection",
            "operations": len(detection_operations),
            "preflight": sum(
                int(item.get("count_or_preflight_calls_completed") or 0)
                for item in detection_operations
            ),
            "generate": sum(
                int(item.get("generate_calls_completed") or 0)
                for item in detection_operations
            ),
            "input_bytes": sum(
                int(item.get("image_bytes") or 0) for item in detection_operations
            ),
            "input_tokens": sum(
                int((item.get("attempt") or {}).get("usage", {}).get("input_tokens") or 0)
                for item in detection_operations
            ),
            "output_tokens": sum(
                int((item.get("attempt") or {}).get("usage", {}).get("output_tokens") or 0)
                for item in detection_operations
            ),
            "latency_ms": sum(
                int((item.get("attempt") or {}).get("duration_ms") or 0)
                for item in detection_operations
            ),
            "estimated_micro_usd": _provider_cost(
                manifest["provider_contracts"]["detection"], detection_operations
            ),
            "terminal_failures": sum(
                case.get("terminal_status") != "completed"
                for case in detection_terminal.get("cases") or []
            ),
        },
        {
            "stage": "padding_variants",
            "operations": sum(
                len(candidate.get("padding_variants") or [])
                for case in detection_terminal.get("cases") or []
                for candidate in case.get("candidates") or []
            ),
            "preflight": 0,
            "generate": 0,
            "input_bytes": sum(
                int(variant.get("crop_bytes") or 0)
                for case in detection_terminal.get("cases") or []
                for candidate in case.get("candidates") or []
                for variant in candidate.get("padding_variants") or []
            ),
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0,
            "estimated_micro_usd": 0,
            "terminal_failures": 0,
        },
    ]
    for provider, operations in extraction.items():
        contract = manifest["provider_contracts"][f"{provider}_extraction"]
        input_tokens = sum(
            int((item.get("attempt") or {}).get("usage", {}).get("input_tokens") or 0)
            for item in operations
        )
        cached_tokens = sum(
            int((item.get("attempt") or {}).get("usage", {}).get("cached_input_tokens") or 0)
            for item in operations
        )
        output_tokens = sum(
            int((item.get("attempt") or {}).get("usage", {}).get("output_tokens") or 0)
            for item in operations
        )
        input_cost = input_tokens * float(contract["input_usd_per_1m_tokens"])
        if provider == "openai":
            input_cost -= cached_tokens * float(contract["input_usd_per_1m_tokens"])
            input_cost += cached_tokens * float(contract["cached_input_usd_per_1m_tokens"])
        output_cost = output_tokens * float(contract["output_usd_per_1m_tokens"])
        result.append(
            {
                "stage": f"{provider}_extraction",
                "operations": len(operations),
                "preflight": sum(
                    int(item.get("count_or_preflight_calls_completed") or 0)
                    for item in operations
                ),
                "generate": sum(
                    int(item.get("generate_calls_completed") or 0)
                    for item in operations
                ),
                "input_bytes": sum(int(item.get("input_bytes") or 0) for item in operations),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": sum(
                    int((item.get("attempt") or {}).get("duration_ms") or 0)
                    for item in operations
                ),
                "estimated_micro_usd": round(input_cost + output_cost, 3),
                "terminal_failures": sum(
                    item.get("terminal_status") != "completed" for item in operations
                ),
            }
        )
    parser_operations = terminal.get("parser_accounting") or []
    result.extend(
        [
            {
                "stage": "parser_verification",
                "operations": len(parser_operations),
                "preflight": 0,
                "generate": 0,
                "input_bytes": sum(int(item.get("input_bytes") or 0) for item in parser_operations),
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": sum(int(item.get("duration_ms") or 0) for item in parser_operations),
                "estimated_micro_usd": 0,
                "terminal_failures": 0,
            },
            {
                "stage": "ocr",
                "operations": 0,
                "preflight": 0,
                "generate": 0,
                "input_bytes": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "estimated_micro_usd": 0,
                "terminal_failures": 0,
            },
            {
                "stage": "diff_generation",
                "operations": 1,
                "preflight": 0,
                "generate": 0,
                "input_bytes": 0,
                "input_tokens": 0,
                "output_tokens": len(diffs.get("disagreements") or []),
                "latency_ms": 0,
                "estimated_micro_usd": 0,
                "terminal_failures": 0,
            },
        ]
    )
    return result


def _provider_cost(
    contract: dict[str, Any], operations: list[dict[str, Any]]
) -> float:
    input_tokens = sum(
        int((item.get("attempt") or {}).get("usage", {}).get("input_tokens") or 0)
        for item in operations
    )
    output_tokens = sum(
        int((item.get("attempt") or {}).get("usage", {}).get("output_tokens") or 0)
        for item in operations
    )
    return round(
        input_tokens * float(contract["input_usd_per_1m_tokens"])
        + output_tokens * float(contract["output_usd_per_1m_tokens"]),
        3,
    )


def _verify_inputs(
    manifest: dict[str, Any],
    padding: dict[str, Any],
    detection_path: Path,
    detection_terminal: dict[str, Any],
    detection_seal: dict[str, Any],
    terminal_path: Path,
    terminal: dict[str, Any],
    terminal_seal: dict[str, Any],
    diffs: dict[str, Any],
    draft: dict[str, Any],
) -> None:
    detection_sha = hashlib.sha256(detection_path.read_bytes()).hexdigest()
    if (
        detection_seal.get("terminal_sha256") != detection_sha
        or detection_seal.get("terminal_size_bytes") != detection_path.stat().st_size
    ):
        raise LiteralReportError("literal_report_detection_seal_mismatch")
    terminal_sha = hashlib.sha256(terminal_path.read_bytes()).hexdigest()
    if (
        terminal_seal.get("terminal_sha256") != terminal_sha
        or terminal_seal.get("terminal_size_bytes") != terminal_path.stat().st_size
    ):
        raise LiteralReportError("literal_report_terminal_seal_mismatch")
    if detection_terminal.get("manifest_sha256") != sha256_json(manifest):
        raise LiteralReportError("literal_report_manifest_mismatch")
    if padding.get("detection_terminal_sha256") != detection_sha:
        raise LiteralReportError("literal_report_padding_lineage_mismatch")
    if terminal.get("detection_terminal_sha256") != detection_sha:
        raise LiteralReportError("literal_report_terminal_detection_lineage_mismatch")
    if diffs.get("terminal_sha256") != terminal_sha:
        raise LiteralReportError("literal_report_diff_lineage_mismatch")
    if terminal.get("reference_accessed") is not False:
        raise LiteralReportError("literal_report_reference_boundary_invalid")
    if draft.get("human_reviewed") is not False:
        raise LiteralReportError("literal_report_expected_unsealed_draft")
    if draft.get("semantic_financial_types_present") is not False:
        raise LiteralReportError("literal_report_semantic_reference_invalid")


def _rate(value: Any) -> str:
    return "not_available" if value is None else f"{float(value):.6f}"


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralReportError("literal_report_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralReportError("literal_report_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
