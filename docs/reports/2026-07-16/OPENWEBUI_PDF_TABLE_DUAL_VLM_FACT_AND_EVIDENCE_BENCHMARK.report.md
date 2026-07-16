TABLE_DETECTION_AND_CROPPING:
FAILED

DUAL_VLM_FINANCIAL_FACT_EXTRACTION:
FAILED

FACT_EVIDENCE_VERIFICATION:
FAILED

DUAL_VLM_FACT_ARCHITECTURE_NOT_JUSTIFIED

# PDF table dual-VLM fact and evidence benchmark

This is a controlled development-corpus result. It does not establish production readiness, change Gate 1 or Gate 2 authority, patch OpenWebUI core, or use RAG/vector retrieval.

## Direct answers

- One-VLM detection/cropping: recall `0.888889`, precision `0.888889`, cut `5`, merged `0`, split `0`, reproducibility failures `0`.
- Raw Gemini/OpenAI agreement statuses: `{"human_review_required": 6, "model_conflict": 3, "one_model_missing_fact": 6}`.
- Gemini alone: precision `0.0`, recall `0.0`. OpenAI alone: precision `0.0`, recall `0.0`. Current-arm rank: `{"gemini_rank": [0.0, 0.0, -29, 0.0], "openai_rank": [0.0, 0.0, -18, 0.0], "provider": "openai"}`; an accuracy winner is not established while the reference fact-type contract is incompatible.
- Canonical consensus: precision `not available`, recall `0.0`; recall loss versus the better single-provider recall `0.0`.
- Consensus plus source evidence: precision `not available`, recall `0.0`, parser/OCR accepted facts `0`, false accepted facts `0`.
- Human-review-required rate: `1.0`; provenance coverage: `not available`.
- Raster-only path: reference facts `20`, vision-only agreements `0`, automatically accepted `0`. Without independent OCR, vision agreement is not source verification.
- Parser-based table construction is not justified by this slice: the parser is retained only for exact text, coordinate, and relation evidence.
- Smallest justified next architecture: page detector -> immutable crop -> independent Gemini/OpenAI fact extraction -> deterministic consensus -> parser evidence for text-layer facts -> bounded independent OCR only where separately justified -> human review for every unresolved or vision-only result.
- Comparison with the frozen previous single-VLM benchmark: `not_established`. The current material-improvement flag uses `current_provider_arms_only` and is not evidence of improvement over the prior benchmark.

## Provider-side structured-output comparability

- Paired crop extractions: `9`; complete pair coverage: `True`; identical crop SHA-256: `True`; identical model-view hashes: `True`; identical canonical schema hashes: `True`; identical provider-adapted schema hashes: `False`; shared prompt contract: `dual_vlm_fact_extraction_v1`.
- Gemini extraction: provider-projected schema; per-operation recorded schema-keyword transformations `{"67": 9}`; canonical/adapted schema hashes equal in `0/9` operations.
- OpenAI extraction: canonical schema unchanged; per-operation recorded schema-keyword transformations `{"0": 9}`; canonical/adapted schema hashes equal in `9/9` operations.
- Interpretation: both extraction arms received the same visual evidence and business questions, but different provider-adapted response schemas. This benchmark therefore compares `model + provider API + schema adapter` bundles, not isolated model capability. It does not establish that schema projection caused any observed disagreement.
- Detection (Gemini-only; not a Gemini/OpenAI comparison arm): provider-projected schema; per-operation recorded schema-keyword transformations `{"9": 8}`; canonical/adapted schema hashes equal in `0/8` operations.

## Exact detection failures

| Failure class | Case | Page | Region/candidate | Detail |
|---|---|---:|---|---|
| false table | `betterment_p02` | 2 | `table_0` | negative page classified as a table |
| missed table | `ibkr_midyear_p03` | 3 | `r1` | reference region not detected |
| cut reference table | `drivewealth_p07` | 7 | `r1` / `table_1` | IoU `0.917664` but crop does not contain the complete reference table |
| cut reference table | `moomoo_annual_p14` | 14 | `r2` / `table_1` | IoU `0.974269` but crop does not contain the complete reference table |
| cut reference table | `moomoo_annual_p14` | 14 | `r1` / `table_0` | IoU `0.832579` but crop does not contain the complete reference table |
| cut reference table | `moomoo_midyear_p10` | 10 | `r2` / `table_2` | IoU `0.970091` but crop does not contain the complete reference table |
| cut reference table | `moomoo_midyear_p10` | 10 | `r1` / `table_1` | IoU `0.961268` but crop does not contain the complete reference table |
| detection contract invalid | `ibkr_midyear_p03` | 3 | detection output | `dual_vlm_detection_candidate_0_bbox_invalid` |

## Reference/scoring contract limitation

- Human-reference fact types: `{"financial_numeric_fact": 83}`.
- Types outside the provider fact contract: `["financial_numeric_fact"]`.
- Fact-type contract compatible: `False`; provider precision/recall interpretation: `contract_limited`.
- The scorer requires exact fact-type equality for a true positive. In this run, the reviewed generic `financial_numeric_fact` type is outside the provider output enum, so zero provider precision/recall is contract-dominated and must not be presented as a clean measurement of visual reading accuracy.
- No post-review type mapping or semantic repair was applied. The reviewed reference remains immutable; a contract-compatible typed reference would require a separate human-reviewed benchmark revision.
- Null reference-field counts: `{"currency": 83, "entity": 83, "normalized_row_identity": 83, "period": 83, "scale": 83, "unit": 83}`.

## Prior omissions corrected

| Prior omission | Correction in this benchmark |
|---|---|
| One extraction VLM | Frozen Gemini and OpenAI provider/model pairs independently analyze identical crop bytes. |
| Strategy C replayed Strategy B | No replay arm exists; each provider has its own preflight and one generate call. |
| `human_reviewed=false` | Scoring requires a checksummed human reference and refuses missing/non-human references. |
| Physical grid dominated | Financial facts and source trace are primary; layout is secondary diagnostics. |
| Financial accuracy was not primary | Provider, consensus, and evidence precision/recall plus qualifier correctness are reported. |
| Parser proved text existence only | Evidence requires unique row/value/header/qualifier spatial relations with parser refs. |
| Raster evidence was conflated | Raster/mixed metrics are separate; no OCR means `models_agree_vision_only` and no auto-accept. |
| No complete operator pack | Source-only human-reference pack and sealed-run comparison/evidence cards are generated for operator decisions. |

## Safety and proof boundary

- False accepted facts: `0`.
- Invented accepted values: `0`.
- Mutated accepted values: `0`.
- Reference human-reviewed: `True`.
- Terminal verified before reference access: `True`.
- Terminal/reference unchanged during scoring: `True` / `True`.

## Operational accounting

| Stage | Operations | Preflight | Generate | Input tokens | Output tokens | Latency ms | Estimated microUSD | Execution contract |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| detection | 8 | 8 | 8 | 11486 | 1372 | 58993 | 29577.0 | False |
| gemini_extraction | 9 | 9 | 9 | 13417 | 29785 | 172589 | 288190.5 | False |
| openai_extraction | 9 | 9 | 9 | 19452 | 10122 | 85364 | 57546.0 | False |
| ocr | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | True |

## Reproducibility identities

- Terminal SHA-256: `9ad8dde45a8560f7a609c932d8896fb19af5b761029d1fd9c437a05ee35257e2`.
- Manifest SHA-256: `8186f9031ec55aa226bc68f5cdafcc4c6fb10b7672ec802d874afd3690beda9d`.
- Human reference SHA-256: `ed1a846c2af8a8ffb9af2908398944679bd24b91e25d9f7764ae5202128e3c52`.
- Score checksum: `8855ae6941f287bd0c1d8f1f63a7f2c794e9a458705c6ffe61e1fd67b39e7396`.
