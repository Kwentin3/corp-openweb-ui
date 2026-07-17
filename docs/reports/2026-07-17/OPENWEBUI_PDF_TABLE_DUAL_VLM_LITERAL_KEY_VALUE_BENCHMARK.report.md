TABLE_DETECTION_AND_PADDED_CROPPING:
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

Authority: `HISTORICAL_RESEARCH_NON_NORMATIVE`. Этот benchmark сохраняет
development evidence раннего padding/dual-VLM подхода и не определяет текущий
production runtime. Поддерживаемый PDF Table Intake описан в
[architecture entry](../../stage2/blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md)
и [versioned contract](../../stage2/contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md).

This is a controlled development-corpus diagnostic. It does not migrate production, change Gate 1 or Gate 2 authority, patch OpenWebUI core, construct tables with the parser, classify financial meaning, or establish production readiness.

## Plain conclusion

No fixed padding was selected. Under the corrected coordinate contract, the page detector itself reached recall `1.000000` and precision `1.000000` with `0` invalid bboxes, `0` missed tables, and `0` false candidates. Cropping still failed: even the largest predeclared `3.0%` padding left 3 incomplete crops (`drivewealth_p07:r1`, `moomoo_annual_p14:r1`, `ibkr_midyear_p03:r1`).

The diagnostic dual-provider run is nevertheless useful: both responses passed the literal schema on `5/9` crops. Among `22` unique alignments, `5` were exact raw key-header-value agreements, `11/16` comparable numeric pairs agreed, and `4` canonical agreements had compatible source regions. This is not an acceptance result: `4` alignments were ambiguous, Gemini had `2` terminal contract failures, OpenAI had `2`, and only `2` unique agreements were independently parser-verified in both arms.

The systematic coordinate-order error from prompt contract v1 is repaired in v2; the old sealed runs remain preserved as pre-v2 history. The remaining problems are crop completeness, literal reading/header binding disagreements, and incomplete independent evidence. The second VLM is useful as a disagreement and contract-failure detector in research, but material runtime benefit is not established without a valid crop set, a sealed literal reference, independent source verification, and provider scoring.

## Direct answers

- Selected fixed padding: **none**. `3.0%` per page side was used only for an explicitly invalid-upstream diagnostic; it is not the selected benchmark padding.
- Truncated crops eliminated: **no**. At `3.0%`, 3/9 matched reference tables remained cut: `drivewealth_p07:r1`, `moomoo_annual_p14:r1`, `ibkr_midyear_p03:r1`.
- Adjacent reference tables captured by padding: `0` for every declared variant. This does not rescue the gate because crop completeness failed.
- Literal entries returned: Gemini `89`, OpenAI `95` across all parsed responses, including contract-invalid responses and partial crops. Contract-valid table responses were Gemini `7/9`, OpenAI `7/9`, both `5/9`.
- Exact raw key-header-value agreements: `5` unique alignments. Safe-canonical agreements: `5`. Agreements with compatible source regions: `4`.
- Numeric values differing: `5` among `16` uniquely aligned numeric pairs. This is diagnostic-only and does not cover invalid, missing, or ambiguous entries.
- Row-label differences: `8`. Header-path differences: `10`. Another `4` alignments remained ambiguous and cannot be counted as correct.
- Wrong row/column binding: not scoreable without the sealed literal reference. Diagnostics found `4` material source-bbox mismatches and `4` ambiguous alignments.
- Provider-to-provider missing entries: Gemini `4`, OpenAI `6`. Misses and inventions against human truth remain unavailable.
- Gemini-correct/OpenAI-wrong, OpenAI-correct/Gemini-wrong, both-wrong, and both-correct-format-different cases: **not scoreable** because the new literal reference is not yet human-reviewed and sealed. The benchmark does not substitute the old semantic reference.
- Independently verified agreements: Gemini parser-verified `3`, OpenAI parser-verified `2`, both arms parser-verified `2` of `22` unique alignments. OCR was not available and was not improvised.
- Dominant disagreement classes: header-path (`10`), row-label (`8`), and visible-value (`7`) mismatches, followed by missing entries and numeric differences.
- Smallest justified next architecture: keep this as research only; create a new frozen benchmark version with a predeclared wider **global** padding range sufficient to test the observed maximum border gap, without per-table tuning, then rerun Gate A. Only after Gate A passes should the tested chain be scored: one detector -> global deterministic padding -> immutable crop -> independent Gemini/OpenAI literal extraction -> deterministic field diff -> parser evidence for text-layer tables -> bounded independent OCR only where separately justified -> human review -> observed key-header-value map. Financial semantic classification remains a separate Gate 3.

## Gate A — detection and crop padding

| Metric | Result | Gate |
|---|---:|---:|
| reference tables | 9 | — |
| matched tables | 9 | 9 |
| recall | `1.000000` | `1.000000` |
| precision | `1.000000` | `>=0.900000` |
| invalid bboxes | 0 | `0` |

| Padding per side | Cut | Merged | Split | Adjacent | Missed | False | Invalid | Repro failures | Selectable |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0% | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False |
| 0.5% | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False |
| 1% | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False |
| 2% | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False |
| 3% | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | False |

The detector bbox was preserved separately from every padded crop bbox. Invalid bboxes were terminal and were never clamped or repaired. Crop reproducibility failures were zero for all rendered valid candidates. Extra-area, dimensions, checksums, and the exact transformations are recorded per crop in the padding artifact. Neighbouring prose is conservatively marked as possible wherever padding added non-reference area; downstream padding effect was not isolated because no variant passed.

### Coordinate-contract correction

The first literal prompt version named normalized coordinates but did not spell out array order. Visual overlay audit showed Gemini interpreting several arrays as `[top, left, bottom, right]`. Prompt/schema/model-view v2 now state `[x0, y0, x1, y1] = [left, top, right, bottom]`, identify horizontal and vertical axes, and explicitly forbid the transposed order. This was rerun as new sealed lineage; no pre-v2 terminal was mutated.

### Exact detection regressions/failures

| Case | Failure |
|---|---|
| `drivewealth_p07` | cut `r1` remains at `3.0%` |
| `moomoo_annual_p14` | cut `r1` remains at `3.0%` |
| `ibkr_midyear_p03` | cut `r1` remains at `3.0%` |

## Literal reference boundary

- New literal reference draft entries: `89`; prior human semantic-fact lineage exists for `83`, while `6` entries are new to literal scope.
- Entries still missing row/value locators in the draft: `6`.
- `human_reviewed=false`; all `89` entries require a new literal-contract operator decision.
- The accepted `OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json` was **not** fabricated. It will exist only after complete human decisions pass the finalizer and receive a separate checksum.
- The sealed-reference scorer is implemented but was not run: it rejects an unsealed/non-human reference, projects both reference and provider locators into the same page coordinate space, excludes `ambiguous`/`excluded` entries from denominators, scores each provider independently, and attaches human answers to a new scored diff artifact without mutating the sealed terminal.
- The reference was unavailable to detection, crop rendering, prompts, provider adapters, consensus, and reference-free diff generation.

## Provider schema and execution equivalence

- Canonical fixture round-trip equivalent: `True`.
- Required field/cardinality equivalent: `True`; enum meaning equivalent: `True`; nullability equivalent: `True`.
- Gemini projection removed or transformed `13` recorded schema keywords while preserving the tested logical requirements. OpenAI used the canonical strict schema.
- This compares `model + provider API + schema adapter`; it is not an isolated model comparison.
- Every attempted extraction arm used one preflight and one generate, attempt number `1`, empty attempt lineage, zero retry, zero failover, and identical crop/model-view/canonical-schema hashes.
- Malformed provider outputs remained terminal; no LLM or deterministic semantic repair changed them.

## Diagnostic disagreement distribution

| Class | Count |
|---|---:|
| `column_header_path_mismatch` | 10 |
| `decimal_or_thousands_separator_mismatch` | 2 |
| `entry_missing_in_gemini` | 4 |
| `entry_missing_in_openai` | 6 |
| `parsed_numeric_value_mismatch` | 6 |
| `raw_format_only_difference` | 3 |
| `repeated_value_alignment_ambiguous` | 4 |
| `row_label_text_mismatch` | 8 |
| `schema_or_contract_failure` | 4 |
| `sign_mismatch` | 3 |
| `source_bbox_material_mismatch` | 4 |
| `visible_value_text_mismatch` | 7 |

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
| detection | 8 | 8 | 8 | 1702721 | 11690 | 938 | 27773 | 25977.0 | 0 |
| padding_variants | 45 | 0 | 0 | 3287824 | 0 | 0 | 0 | 0 | 0 |
| gemini_extraction | 9 | 9 | 9 | 689558 | 14041 | 25717 | 106595 | 252514.5 | 2 |
| openai_extraction | 9 | 9 | 9 | 689558 | 12617 | 10317 | 75429 | 55889.25 | 2 |
| parser_verification | 6 | 0 | 0 | 5405125 | 0 | 0 | 16994 | 0 | 0 |
| ocr | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| diff_generation | 1 | 0 | 0 | 0 | 0 | 61 | 0 | 0 | 0 |

Padding accounting reports `45` variant crops and `90` deterministic render operations over 9 valid detector candidates. Cost uses the frozen pricing snapshot in the versioned manifest and is only an estimate.

## Reproducibility identities

- Detection terminal SHA-256: `301a328a70ac90e228e1bdc01d010381f226479c37f9fbe85c15537df24bd65a`.
- Padding experiment SHA-256: `d649586efff610ac47321565eb83a6b8e85b0bb82f0e47cacd58d35fce06def2`.
- Diagnostic terminal SHA-256: `6bc8ab01a2a91a11517f50cef55878bbd5ff567ffe5ebf0a2e2e7427b1732413`.
- Machine diff SHA-256: `0f1d8a3a6b1684d1d4d42e58125503fd0e96f93a7c4e3ca6bc6c81a3106bf3bc`.
- Literal reference draft SHA-256: `ff5d2067b1fd3252ef394e5a9b9d9d45bb5d5f5a67e120413a7899175c9bc9b1` (not an accepted reference seal).

## Proof boundary

The benchmark repaired the semantic-contract error: provider prompts and scoring contracts contain no financial fact type, accounting category, normalized business concept, semantic entity class, or inferred financial role. No type mapping was introduced. The current output remains diagnostic observed table mappings with source trace; it is not normalized financial facts and is not production authority.
