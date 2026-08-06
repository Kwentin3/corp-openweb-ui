# DOC23 — Deduplicated Gate 1 LLM View and Parser Rescue Validation

Date: 2026-08-05  
Project: `Kwentin3/corp-openweb-ui`  
Scope: research-only; no Gate 3, financial extractor, parser/cropper change, VLM regeneration, or product activation.

## Terminal result

```text
DOC23_EXPERIMENT = COMPLETED
PARSER_TABLE_OVERLAP = DUPLICATE_HEAVY
PARSER_RESCUE = PARTIAL
DEDUPLICATED_VIEW_MATERIAL_SUFFICIENCY = CONFIRMED
CONTEXT_COMPRESSION = MINIMUM_MET
AUTOMATED_AUDIT = BLOCKED
GATE1_LLM_VIEW_DECISION = NEEDS_MORE_RESEARCH
CROP_RESEARCH_POLICY = PAUSE
```

`COMPLETED` means the research package, all 48 direct reviews, exact preflight, and all 48 frozen automated slots reached terminal accounting. It does not mean the automated acceptance target passed. The automated audit is blocked by 30 provider quota failures, one invalid structured output, only 17 completed observations, and observed exact agreement below 90%.

## 1. Corpus and evidence boundary

DOC23 reused the frozen DOC15/DOC21/DOC22 corpus without exclusions:

- 24 target tables;
- two existing Gate 1 table JSON arms per target (`google_flash_lite`, `anthropic_opus`);
- 48 cases total;
- crop classes unchanged: 12 clean, 7 clipped, 5 contaminated;
- six source documents, 663 pages, and 34,541 unique parser lines;
- all existing PDF, overlay, parser, VLM JSON, DOC21 verdict, and DOC22 verdict artifacts retained byte-for-byte.

The research output has three physically separate layers:

1. `FULL_EVIDENCE`: unchanged source PDFs, parser inventories, coordinates, overlays, table JSON, and receipts.
2. `DEDUPLICATED_DOCUMENT_VIEW`: ordered pages and parser text with one unchanged target table block, explicit rescue/conflict/ambiguity blocks, and proved duplicate parser lines omitted from the primary view.
3. `LLM_TEST_PROJECTION`: compact serialization used by the fixed verifier.

No provider name, direct verdict, DOC22 verdict, crop class, expected answer, or other arm was included in automated verifier input.

## 2. Deduplication method

Every target-page parser line was classified as `DUPLICATE`, `PARSER_RESCUE`, `EXTERNAL_CONTEXT`, `CONFLICT`, `AMBIGUOUS`, or `UNRELATED`. Suppression required all of the following:

- the line was fully inside the target geometry;
- same-segment lexical coverage against one VLM title/header/row/note segment was at least 0.90;
- all line numbers, dates, signs, currency markers, and unit markers were represented by that same segment;
- the line did not partially overlap the target;
- a clipped crop did not put the line in the target edge band;
- DOC22 had not recorded a conflict for the case.

Anything uncertain remained visible. The pre-freeze sealed review caught one important unsafe candidate: Google `ACORNS_T02` was lexically duplicate but its split parser row was part of an existing row-relation conflict. The generic DOC22-conflict guard was therefore added before freeze, and all five conflicting parser lines remained in the primary view.

The serializer preserves document/page order and uses compact blocks:

```text
[PAGE n]
ordinary parser text
[TABLE table_id]
title/header/row/note lines from unchanged VLM JSON
[PROVENANCE ...]
[PARSER_RESCUE ...]
[CONFLICT ...]
[AMBIGUOUS ...]
```

Parser fragments are never merged into or used to correct the VLM table JSON.

## 3. Parser/VLM overlap

Across 48 target-page projections, 2,154 line classifications were recorded. Of 984 table-overlapping lines, 752 were proved duplicates: 76.4228%.

| Classification | Lines |
|---|---:|
| Duplicate | 752 |
| Parser rescue | 111 |
| External context | 1,170 |
| Conflict | 42 |
| Ambiguous | 79 |
| Unrelated | 0 |

The parser is therefore duplicate-heavy inside the selected table regions, but not safely disposable. It also retains markers, OCR variants, clipped-edge content, and conflicting row/value representations that must remain visible.

Duplicate content before/after the primary projection:

| Measure | Before | After | Reduction |
|---|---:|---:|---:|
| Lexical tokens | 4,593 | 199 | 95.6673% |
| Numeric tokens | 1,748 | 78 | 95.5378% |
| Date tokens | 348 | 10 | 97.1264% |
| Currency/unit markers | 561 | 41 | 92.6916% |
| Table segments represented twice | 685 | 34 | 95.0365% |

The remaining duplicate representations are deliberate clipped-edge or conflict guards, not missed suppression.

## 4. What DOC22 rescue actually used

DOC22 reported 100 rescued category elements across the two arms. DOC23 attributed their source as follows:

| Source class | Elements | Share |
|---|---:|---:|
| True external context | 96 | 96.0% |
| Mixed external context and parser table copy | 4 | 4.0% |
| Pure parser copy of table | 0 | 0.0% |
| Parser-only missing table fragment | 0 | 0.0% |
| Unresolved | 0 | 0.0% |

The four mixed elements were:

- Google `ACORNS_T01`: `CURRENCY`;
- Google `JEFFERIES_T05`: `MISSING_VALUE`;
- Google `JEFFERIES_T05`: `GROUP_OR_TOTAL_RELATION`;
- Google `STONEX_T01`: `MISSING_VALUE`.

All other DOC22 rescues were attributed to headings, immediately preceding/following context, period/scale headers, or previous-page continuation evidence rather than to a second copy of the target table body.

Rescued categories were: table scope 29, period 28, column relation 20, unit/scale 14, continuation identity 5, missing value 2, currency 1, and group/total relation 1. No parser rescue fragment was lost from the deduplicated view.

## 5. Conflicts and ambiguity

All five DOC22 conflict cases remain explicit:

- Google `ACORNS_T02`: `CONTEXT_CONFLICT`; direct verdict remains `AMBIGUOUS`.
- Google `LPL_T01`: `PERIOD_AMBIGUITY`; direct verdict remains `AMBIGUOUS`.
- Opus `LPL_T01`: `PERIOD_AMBIGUITY`; direct verdict remains `AMBIGUOUS`.
- Opus `LPL_T02`: `CONTEXT_CONFLICT`; no safe upgrade was made.
- Opus `TRADEWEB_T03`: `CONTEXT_CONFLICT`; no safe upgrade was made.

The deterministic line audit also retained 42 parser/VLM atom or relation conflicts across nine cases:

- Opus `TRADEWEB_T02` (5), `TRADEWEB_T03` (10), `TRADEWEB_T05` (2);
- Google `ACORNS_T02` (5), `JEFFERIES_T05` (3), `LPL_T01` (3), `TRADEWEB_T02` (5), `TRADEWEB_T03` (7), `TRADEWEB_T05` (2).

There were 79 kept ambiguous lines across 36 cases, mainly target-edge lines, parser OCR token splits, short symbol-only lines, and content without sufficient same-segment identity. The complete case/count ledger is in `BROKER_REPORTS_DOC23_CONFLICTS.safe.json`. At the material direct-verdict level, ambiguity remains exactly the three DOC22 cases above; no DOC22 ambiguity was converted into a safe verdict.

## 6. Direct agent review

The agent reviewed all six source-page contact sheets (24 target pages), all 48 case diffs, all retained risk lines, every suppressed-line proof, all five DOC22 conflict families, and all three DOC22 material ambiguities.

| Provider arm | Document sufficient | Rescued | Critical | Ambiguous | Material |
|---|---:|---:|---:|---:|---:|
| Google Flash Lite | 1 | 21 | 0 | 2 | 22/24 |
| Anthropic Opus | 4 | 19 | 0 | 1 | 23/24 |

The DOC22 material results were preserved exactly. Direct automation eligibility therefore passed for both arms. Lost parser rescue fragments: 0. Hidden conflicts: 0. DOC22 ambiguous cases upgraded: 0.

## 7. Compression

The local `o200k_base` estimate over all 48 full-document case projections was:

```text
FULL_SHADOW_TOKENS = 8,448,750
DEDUPLICATED_VIEW_TOKENS = 5,893,591
TOKEN_REDUCTION_ABSOLUTE = 2,555,159
TOKEN_REDUCTION_PERCENT = 30.2430%
```

Per document:

| Document | Full shadow | Deduplicated | Reduction |
|---|---:|---:|---:|
| Acorns 2025 | 48,531 | 30,829 | 36.4757% |
| Jefferies 2024 | 2,528,771 | 1,731,035 | 31.5464% |
| LPL 2025 | 1,350,908 | 976,438 | 27.7199% |
| Oppenheimer 2025 | 25,234 | 15,189 | 39.8074% |
| StoneX 2025 | 2,321,193 | 1,575,748 | 32.1147% |
| Tradeweb 2025 | 2,174,113 | 1,564,352 | 28.0464% |

Attribution of the 2,555,159-token reduction:

- engineering metadata removed: 2,537,886;
- duplicate target-table text removed: 8,641;
- repeated schemas removed: 6,112;
- long identifiers removed: 2,520.

Thus table-body deduplication is real and numerically strong, but most whole-document savings came from removing engineering envelopes rather than from deleting one target table copy per case.

The exact live preflight comparison corroborated the estimate: DOC22 full-shadow qualification used 235,290 input tokens; DOC23 deduplicated qualification used 161,296, a 31.4480% reduction.

The 30% minimum was met. The 50% target was not met. `CONTEXT_COMPRESSION = MINIMUM_MET`.

## 8. Exact preflight and rate plan

The fixed verifier was exact `gpt-5.6-sol` through the existing research route:

```text
NativePdfTransport.invoke_image_structured
→ NativePdfTransport._post_plain
→ OpenAI Responses API
```

Preflight used the real deduplicated projection, target overlay image, strict structured output, omitted temperature, `reasoning.effort=low`, and `max_output_tokens=2048`. It returned HTTP 200, valid structured output, the exact requested model, and token accounting.

Before freeze, the rate plan was fixed to sequential execution, concurrency 1, and a 20-second delay between starts. Retry, fallback, repair, and failed-case exclusion were forbidden.

## 9. Automated audit

All slots were terminally accounted:

```text
EXPECTED = 48
STARTED = 48
ATTEMPTED = 48
COMPLETED = 17
FAILED = 31
HTTP_200 = 18
HTTP_429 = 30
PROVIDER_INSUFFICIENT_QUOTA = 30
STRUCTURED_OUTPUT_INVALID = 1
RETRY = 0
FALLBACK = 0
REPAIR = 0
UNACCOUNTED = 0
```

The single HTTP 200 failure reached the 2,048-output-token limit and ended with non-JSON text (`JSONDecodeError`). It was not repaired or retried. The 30 HTTP 429 responses carried `credit_balance_exhausted`/insufficient-quota semantics; fixed pacing could not remedy that external account state.

Observed agreement on the 17 structured-valid calls only:

| Metric | Result |
|---|---:|
| Exact verdict agreement | 13/17 = 76.4706% |
| Sufficiency agreement | 15/17 = 88.2353% |
| Exact rescue-category agreement | 3/17 = 17.6471% |
| Ambiguity agreement | 15/17 = 88.2353% |
| Conflict-presence agreement | 17/17 = 100.0% |
| False safe | 0 |
| False block | 2 |

These are observed-subset diagnostics, not corpus metrics. Completed automated cases were not 48/48, exact agreement was below 90%, and rescue-category agreement was weak. Therefore `AUTOMATED_AUDIT = BLOCKED`, not validated.

## 10. Data that cannot be safely deduplicated

The following must remain visible unless stronger evidence is added:

- any partial target overlap;
- clipped-crop edge lines;
- parser-only currency, unit, scale, date, sign, heading, note, or continuation markers;
- split parser rows where VLM row binding differs;
- parser OCR numeric splits that do not match one VLM segment exactly;
- all DOC22 conflict-case parser evidence;
- any numeric or marker mismatch with a competing VLM atom;
- short symbol-only or low-identity lines;
- any line classified `AMBIGUOUS`.

The LPL target tables and Tradeweb percentage rows were the clearest examples: their parser tokenization did not support safe suppression despite geometry overlap.

## 11. Decision and next boundary

DOC23 confirms that a conservative research-only deduplicated view can preserve DOC22 direct sufficiency and remove more than 95% of proved duplicate numeric content. It does not yet justify a minimum product document-view contract because:

1. only 17/48 automated cases completed;
2. observed exact agreement was 76.4706%, below 90%;
3. observed rescue-category agreement was 17.6471%;
4. the 50% context-compression target was not met.

The next action is not product activation and not Gate 3. A new, explicit research decision is required to fund a complete fixed-verifier run and to address structured-output length before `DEFINE_MINIMUM_DOCUMENT_VIEW_CONTRACT` can start. Crop research remains paused as the primary route because direct evidence continues to show document context, not crop class, as the dominant sufficiency mechanism.

## 12. Scope confirmation

```text
DOC23_RESEARCH_ONLY = TRUE
FULL_EVIDENCE_PRESERVED = TRUE
GATE1_PRODUCT_CHANGED_BY_DOC23 = FALSE
PARSER_CHANGED_BY_DOC23 = FALSE
CROPPER_CHANGED_BY_DOC23 = FALSE
VLM_TABLES_REGENERATED = FALSE
GATE2_CHANGED_BY_DOC23 = FALSE
GATE3_CREATED = FALSE
PRODUCT_PIPELINE_ACTIVATED = FALSE
```

The checkout already contained unrelated uncommitted DOC7–DOC22 and runtime changes before DOC23. DOC23 did not modify or clean those files.
