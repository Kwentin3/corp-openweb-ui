# Broker Reports DOC8 — Multi-model image + parser-context structure test

Date: 2026-08-03  
Task type: bounded research experiment  
Product integration: none

## Bottom line

```text
DOC8_EXPERIMENT = COMPLETED
PARSER_TEXT_IMPROVES_STRUCTURE = MODEL_DEPENDENT
BEST_ROW_MODEL = claude-opus-5
BEST_CELL_GROUPING_MODEL = claude-opus-5
BEST_TOKEN_CONSERVATION_MODEL = claude-opus-5
HYBRID_STRUCTURE_RECONCILIATION = NOT_CONFIRMED
```

Exact parser text strongly improved OpenAI and Claude structure recovery, but did not improve Gemini on this run. Claude hybrid was the best arm: it conserved every parser ID, achieved 91.41% exact-row recall and 97.92% exact-cell-group recall, and placed all scoreable IDs in the correct row/cell. It still missed the research threshold because exact-row recall was below 98% and only 4/12 tables were completely exact, below the required 75%.

## Frozen table selection

The 12 tables were selected from the sealed DOC7 corpus before provider calls. A fixed stratum order was used. Within each stratum, the unused candidate with the minimum SHA-256 rank was selected. DOC7 Markdown and JSON outputs were not consulted.

| Required stratum | Selected table | Classes |
|---|---|---|
| Simple two-column | `unseen_pdf_03_t01` | adjacent, key-value, money |
| Adjacent table | `unseen_pdf_02_t05` | trading information, wide |
| Sparse financial statement | `unseen_pdf_01_t04` | sparse, money, totals |
| Group rows | `unseen_pdf_06_t25` | group headers, schedule, sparse |
| Multilevel header | `unseen_pdf_06_t03` | affiliated transactions, 9-column wide table |
| Wide table | `unseen_pdf_06_t35` | derivatives, multilevel header |
| Currency markers | `unseen_pdf_06_t27` | money columns, wide table |
| Subtotals/totals | `unseen_pdf_06_t09` | affiliated transactions, totals |
| Long text values | `unseen_pdf_06_t05` | derivatives, long labels |
| Repeated identical numbers | `unseen_pdf_01_t01` | financial statement, group headers |
| Schedule of investments | `unseen_pdf_06_t07` | schedule, sparse, totals |
| Multi-page fragment | `unseen_pdf_01_t05` | cross-page continuation |

Selection integrity SHA-256: `0484866fc1a5c0263cbe9b04f406cc7fc3f33cef6e59941780a62da3425dfeab`.

No failed table was excluded.

## Structure-neutral parser inventory

The parser path was:

```text
FullSourceArtifactFactory.create
→ FullSourceArtifactBuilder.build
→ PdfTextLayerParserFactory.create
→ PdfLayoutUnitBuilder.build
→ word_inventory
```

Only `{opaque ID, exact source text}` was put in the hybrid text inventory. Its order was deterministically shuffled and differed from physical order for all 12 tables. The model received no parser row, column, grid, coordinate, reading-order, role, DOC6, or gold fields.

Safe inventory example:

```json
{"id": "f_12ab34cd", "text": "<exact source text redacted>"}
```

Safe ID-map example:

```text
[f_12ab34cd] <visible source text redacted>
```

Coordinates were used only to paint the ID beside its source word on the private ID-map image.

### Parser lexical coverage

| Metric | Total |
|---|---:|
| Gold lexical fragments | 1,086 |
| Parser lexical fragments matched | 600 |
| Parser lexical fragments missing | 486 |
| Parser extra lexical fragments | 119 |
| Opaque parser word IDs supplied to models | 627 |
| IDs unambiguously mapped to a gold cell | 556 |
| Gold mapping unresolved IDs | 61 |
| Parser-extra IDs | 10 |

Parser lexical coverage uses NFKC case-folded token multisets. It is reported separately and is not charged to the models. Structure metrics use only the 556 IDs with unambiguous gold-cell mappings. All 627 IDs nevertheless remain mandatory in the validator: each must occur once in `rows` or `unresolved`.

## Frozen models and prompt

All three official Models APIs returned HTTP 200 before freeze:

- OpenAI: `gpt-5.4-2026-03-05`, the exact DOC7 snapshot. OpenAI documents this snapshot and its standard $2.50/M input and $15/M output pricing on the [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4).
- Google: `models/gemini-3.1-pro-preview`, selected as the strongest available general Pro model with a concrete non-`latest` ID. The live Models API reported `generateContent`; Google documents text/image/video/audio/PDF input on the [Gemini 3.1 Pro model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) and $2/M input, $12/M output below 200k prompt tokens on the [pricing page](https://ai.google.dev/gemini-api/docs/pricing).
- Anthropic: `claude-opus-5`, the newest available Opus with `image_input=true` in the live Models API. Anthropic's [Models API](https://platform.claude.com/docs/en/api/models/list) exposes image capability flags, and its [Opus 5 migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide) documents vision support and $5/M input, $25/M output pricing.

Shared prompt SHA-256: `09e74e4abef48aacb4348af07c68e22b30f7506c730feb5286719836c08a853f`.

Both arms received the same original crop, ID map, instruction, model, output limit, and one attempt. The hybrid arm's only addition was the shuffled exact-text inventory. No provider-specific structured-output schema, tools, retrieval, web, retry, repair, or best-of was used.

## Call accounting

```text
12 tables × 3 models × 2 arms = 72 calls
```

| Provider | Calls | HTTP 200 | Text outputs | Terminal empty outputs | Resolved model |
|---|---:|---:|---:|---:|---|
| OpenAI | 24 | 24 | 24 | 0 | `gpt-5.4-2026-03-05` |
| Google | 24 | 24 | 24 | 0 | `gemini-3.1-pro-preview` |
| Anthropic | 24 | 24 | 21 | 3 | `claude-opus-5` |

The three Anthropic image-only calls for `unseen_pdf_06_t03`, `unseen_pdf_06_t09`, and `unseen_pdf_06_t27` returned HTTP 200 without a text block. They remain terminal failed calls and were not retried.

## Results

The scoreable gold projection contains 128 rows, 384 cells, and 556 mapped IDs across 12 tables.

| Model / arm | Valid outputs | Row recall | Cell-group recall | Token placement | Exact tables | Invented / missing / duplicate / unresolved IDs |
|---|---:|---:|---:|---:|---:|---:|
| OpenAI image-only | 0/12 | 16.41% | 46.61% | 46.76% | 0/12 | 286 / 321 / 4 / 0 |
| OpenAI hybrid | 9/12 | 85.16% | 95.31% | 93.88% | 4/12 | 0 / 1 / 4 / 2 |
| Gemini image-only | 1/12 | 32.03% | 38.54% | 46.04% | 0/12 | 37 / 337 / 0 / 18 |
| Gemini hybrid | 6/12 | 28.91% | 22.14% | 25.00% | 1/12 | 0 / 469 / 0 / 0 |
| Claude image-only | 0/12 | 40.63% | 35.94% | 43.35% | 0/12 | 82 / 356 / 0 / 0 |
| Claude hybrid | 12/12 | 91.41% | 97.92% | 100.00% | 4/12 | 0 / 0 / 0 / 0 |

An output is valid only if its JSON shape is exact and every supplied ID occurs once in `rows` or `unresolved`. Structural metrics are still reported for known IDs in invalid outputs, but invalid outputs can never count as complete-table matches.

### Effect of parser text

| Model | Row recovery | Cell grouping | Missing IDs | Unresolved IDs |
|---|---|---|---|---|
| OpenAI | `TRUE` | `TRUE` | `TRUE` | `INCONCLUSIVE` |
| Gemini | `INCONCLUSIVE` | `INCONCLUSIVE` | `INCONCLUSIVE` | `INCONCLUSIVE` |
| Claude | `TRUE` | `TRUE` | `TRUE` | `INCONCLUSIVE` |

Each answer uses a paired 10,000-resample table bootstrap with seed 1808 and a two-sided 95% interval. The detailed intervals are retained in safe evidence.

`PARSER_TEXT_IMPROVES_STRUCTURE = MODEL_DEPENDENT`: the improvement is strong for OpenAI and Claude but absent for Gemini.

### Completely exact tables

- OpenAI hybrid: `unseen_pdf_01_t04`, `unseen_pdf_01_t05`, `unseen_pdf_06_t07`, `unseen_pdf_06_t09`.
- Gemini hybrid: `unseen_pdf_01_t05`.
- Claude hybrid: `unseen_pdf_01_t05`, `unseen_pdf_06_t03`, `unseen_pdf_06_t09`, `unseen_pdf_06_t27`.
- Every image-only arm: none.

The safe comparison artifact lists every table with row or cell-grouping errors. Source values and raw model output remain private.

## Token usage and estimated cost

| Provider / arm | Input tokens | Output tokens | Thinking tokens | Estimated USD |
|---|---:|---:|---:|---:|
| OpenAI image-only | 23,394 | 5,685 | 0 | 0.143760 |
| OpenAI hybrid | 31,324 | 5,774 | 0 | 0.164920 |
| Gemini image-only | 28,414 | 8,385 | 0 | 0.157448 |
| Gemini hybrid | 39,027 | 7,231 | 23,591 | 0.447918 |
| Claude image-only | 27,004 | 36,786 | 0 | 1.054670 |
| Claude hybrid | 37,719 | 11,840 | 0 | 0.484595 |

Estimated total: **$2.453311** at standard public token prices. This is a usage-based estimate, not a billing receipt. Gemini thinking tokens are included in its billable-output estimate.

## Research threshold

No model simultaneously achieved:

```text
100% parser-ID conservation
0 invented IDs
0 duplicated IDs
exact row recall >= 98%
exact cell-group recall >= 95%
complete-table exact match >= 75%
```

Claude hybrid passed ID conservation, invention, duplication, cell grouping, and token placement, but failed row recall (91.41%) and complete-table rate (33.33%). Therefore:

```text
HYBRID_STRUCTURE_RECONCILIATION = NOT_CONFIRMED
```

## Acceptance and integrity

```text
TABLES_FROZEN_TOTAL = 12
MODELS_FROZEN_TOTAL = 3
ARMS_TOTAL = 2
EXPECTED_PROVIDER_CALLS_TOTAL = 72
PARSER_INVENTORY_FROZEN = TRUE
FRAGMENT_GOLD_FROZEN_BEFORE_CALLS = TRUE
PROMPT_FROZEN_BEFORE_CALLS = TRUE
MODEL_IDS_FROZEN_BEFORE_CALLS = TRUE
ALL_72_CALLS_ACCOUNTED = TRUE
FAILED_TABLES_EXCLUDED_TOTAL = 0
ALL_OUTPUTS_VALIDATED = TRUE
ALL_METRICS_REPORTED = TRUE
```

Protocol integrity SHA-256: `fb474334c1d36f7767d7b6a37074cee9f4e790ab3e76433d867cb7196782ec39`.

DOC6, deterministic recovery, Managed Document v2, View v2, provider adapters, runtime configuration, and product routes were not changed. No new pipeline or activation was created.
