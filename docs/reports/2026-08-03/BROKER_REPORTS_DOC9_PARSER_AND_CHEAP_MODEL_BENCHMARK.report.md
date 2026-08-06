# Broker Reports DOC9 — Parser lexical audit and cheap vision-model benchmark

Date: 2026-08-03  
Task type: bounded diagnostic and comparative experiment  
Product integration: none

## Bottom line

```text
DOC9_EXPERIMENT = COMPLETED
PARSER_LEXICAL_PROJECTION = SUFFICIENT
BEST_CHEAP_MODEL = NONE
BEST_PRICE_QUALITY_MODEL = anthropic_sonnet_5 (best measured, rejected)
CHEAPEST_PRIMARY_CANDIDATE = NONE
BEST_FALLBACK_CANDIDATE = NONE
CHEAP_MODEL_STRATEGY = NOT_CONFIRMED
```

The parser did not truly lose the 486 DOC8 lexical tokens. The dominant defect was word merging caused by `pdfplumber` `x_tolerance=3.0`. A structure-neutral lexical-only projection at `x_tolerance=0.5` covered every corrected visible table token and all 319 numeric values. The cheap-model strategy nevertheless failed: no model returned valid, lossless structure for all 12 tables.

## Parser gap audit

### All 486 DOC8 missing cases

| Proven cause | Count |
|---|---:|
| Parser merged multiple visible tokens | 468 |
| Crop boundary error | 8 |
| Visual-gold mapping error | 10 |

### All 119 DOC8 extra cases

| Proven cause | Count |
|---|---:|
| Parser merged multiple visible tokens | 107 |
| Visible decorative/non-table note fragments | 8 |
| Visual-gold mapping error | 4 |

No case remained `unknown`, generic `parser error`, or generic `OCR problem`.

### Corrected coverage

| Metric | Covered / visible |
|---|---:|
| Normalized characters | 5,875 / 5,875 |
| Lexical tokens | 1,072 / 1,072 |
| Numeric values | 319 / 319 |
| Currency markers | 43 / 43 |
| Dates | 16 / 16 |
| Critical numeric value coverage | 100% |

The only lexical mechanism change was `word_x_tolerance: 3.0 → 0.5`. Raw text and a private NFKC form were retained. No rows, columns, grid, roles, reading order, cells, DOC6 output, or LLM-read values were added.

## Canonical input packages

Every provider received the same bytes for the original crop, ID map, shuffled UTF-8 inventory, prompt, output contract, and output-token limit. The inventory exposed only `id` and raw `text`; the gold corrections were evaluator-only.

- `unseen_pdf_03_t01`: `d7d329e1afa2a6f67a674ba84befb79410aff9a89d72f8726cf920fcab2b2deb`
- `unseen_pdf_02_t05`: `cb1bf34208b2feb55fdb440e89c943451c2bd7991e056932ef3544f42284eaec`
- `unseen_pdf_01_t04`: `aae21a1c2884bb8bd4cd7998904ee1a5643ca531004fd0370ff9f493ec2892be`
- `unseen_pdf_06_t25`: `afff1a7182364abd2b1292a17e268ff770ed217081c562c865debaa76876c23b`
- `unseen_pdf_06_t03`: `6b838e07cefae7c53ab45615e49b9d51664e82b05f142593dcc2b78600b1a8ab`
- `unseen_pdf_06_t35`: `59f4b7d37f19c2fb976c38eb66c2f7f5f8f9f08f183906e43a0551dc0516c8a1`
- `unseen_pdf_06_t27`: `36eff61580e34ecd4c01a940decd887be16fcc853a0bec1c3881a59e078fb5d3`
- `unseen_pdf_06_t09`: `d30ad16028e4dc743d8157df4cd413eac6a8df0fed86e161c0c8404c81ea377d`
- `unseen_pdf_06_t05`: `f038a3dc5f0f7342ce890ec53d12897e8b9a2610e17f0cbc7cc6c3f228d793a0`
- `unseen_pdf_01_t01`: `19e8e136c15a1d87ac1194a056257a3e6f8129bdf915ad9276271f6f0e63383e`
- `unseen_pdf_06_t07`: `edc6b56bebd086b2ad921eeb0a0386b344da387c51028c729f5e6bb997bed6e1`
- `unseen_pdf_01_t05`: `d68b5d0802dda9958ec52d5857f7ac63a2e6af0b251318ccd37d7cd9f0866586`

## Frozen models

All six IDs were present in their official Models APIs before freeze. OpenAI documents image input and snapshots on the [GPT-5.4 nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano) and [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) pages. Google documents stable multimodal Flash-Lite models and prices on its [models](https://ai.google.dev/gemini-api/docs/models) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) pages. Anthropic documents image support, pinned IDs, and prices in its [models overview](https://platform.claude.com/docs/en/about-claude/models/overview).

- `openai_nano` — requested `gpt-5.4-nano-2026-03-17`; resolved `gpt-5.4-nano-2026-03-17` × 12; snapshot; $0.2/M input, $1.25/M output.
- `openai_mini` — requested `gpt-5.4-mini-2026-03-17`; resolved `gpt-5.4-mini-2026-03-17` × 12; snapshot; $0.75/M input, $4.5/M output.
- `google_25_flash_lite` — requested `models/gemini-2.5-flash-lite`; resolved `NOT_RETURNED_HTTP_404` × 12; stable_concrete_id; $0.1/M input, $0.4/M output.
- `google_35_flash_lite` — requested `models/gemini-3.5-flash-lite`; resolved `gemini-3.5-flash-lite` × 12; stable_concrete_id; $0.3/M input, $2.5/M output.
- `anthropic_haiku_45` — requested `claude-haiku-4-5-20251001`; resolved `claude-haiku-4-5-20251001` × 12; dated_snapshot; $1.0/M input, $5.0/M output.
- `anthropic_sonnet_5` — requested `claude-sonnet-5`; resolved `claude-sonnet-5` × 12; dateless_pinned_snapshot; $2.0/M input, $10.0/M output.

Sonnet 5 used the introductory $2/$10 rate valid through 2026-08-31. Provider default thinking behavior was recorded rather than treated as internally equivalent.

## Call accounting and invalid outputs

`12 tables × 6 models = 72` one-attempt calls. No retry, fallback, best-of, tools, retrieval, web, structured-output API, or manual repair was used.

- OpenAI nano: 10 strict JSON parses, 2 JSON parse errors; 0/12 valid after ID validation.
- OpenAI mini: 12 strict JSON parses; 1/12 valid after ID validation.
- Gemini 2.5 Flash-Lite: 12 HTTP 404 responses despite successful pre-freeze Models API discovery.
- Gemini 3.5 Flash-Lite: 12 fenced JSON responses; strict valid 0/12.
- Claude Haiku 4.5: 12 fenced JSON responses; strict valid 0/12.
- Claude Sonnet 5: 4 strict parses, 4 fenced JSON, 3 empty outputs, 1 other parse error; 3/12 valid.

Markdown fences were not stripped. Missing, duplicate, or invented IDs were not repaired.

## Quality table

| Model | Valid | ID conservation | Row recall | Cell recall | Token placement | Exact tables | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| `openai_nano` | 0/12 | 24.83% | 0.77% | 6.54% | 0.42% | 0/12 | `REJECTED_INVALID_OUTPUT` |
| `openai_mini` | 1/12 | 26.08% | 9.23% | 17.19% | 6.57% | 1/12 | `REJECTED_INVALID_OUTPUT` |
| `google_25_flash_lite` | 0/12 | 0.00% | 0.00% | 0.00% | 0.00% | 0/12 | `REJECTED_INVALID_OUTPUT` |
| `google_35_flash_lite` | 0/12 | 0.00% | 0.00% | 0.00% | 0.00% | 0/12 | `REJECTED_INVALID_OUTPUT` |
| `anthropic_haiku_45` | 0/12 | 0.00% | 0.00% | 0.00% | 0.00% | 0/12 | `REJECTED_INVALID_OUTPUT` |
| `anthropic_sonnet_5` | 3/12 | 7.51% | 10.77% | 9.69% | 8.27% | 2/12 | `REJECTED_INVALID_OUTPUT` |

## Cost table

| Model | Average/table | Average latency | Cost/exact table | Estimated/1,000 |
|---|---:|---:|---:|---:|
| `openai_nano` | $0.001604 | 6.754s | n/a | $1.604 |
| `openai_mini` | $0.005722 | 5.937s | $0.068663 | $5.722 |
| `google_25_flash_lite` | $0.000000 | 1.102s | n/a | $0.000 |
| `google_35_flash_lite` | $0.005680 | 5.726s | n/a | $5.680 |
| `anthropic_haiku_45` | $0.010526 | 11.933s | n/a | $10.527 |
| `anthropic_sonnet_5` | $0.051847 | 40.992s | $0.311084 | $51.847 |

Estimated total cost: **$0.904552**. This is a usage-based estimate, not a billing receipt. The HTTP-404 Gemini 2.5 calls reported no token usage and therefore have a zero usage estimate.

## Completely exact tables

- `openai_nano`: none
- `openai_mini`: `unseen_pdf_01_t05`
- `google_25_flash_lite`: none
- `google_35_flash_lite`: none
- `anthropic_haiku_45`: none
- `anthropic_sonnet_5`: `unseen_pdf_01_t04`, `unseen_pdf_02_t05`

The safe frontier artifact lists every invalid-output, row-error, and cell-grouping-error table. Sonnet 5 was the best measured quality/cost model but remains rejected because only 3/12 outputs were valid. The raw mathematical Pareto set includes zero-cost failures; the usable-candidate Pareto frontier is empty.

## Acceptance and stop boundary

```text
PARSER_LEXICAL_AUDIT_COMPLETED = TRUE
ALL_DOC8_FRAGMENT_GAPS_CLASSIFIED = TRUE
CANONICAL_INPUT_PACKAGES_TOTAL = 12
INPUT_PACKAGE_HASH_PARITY = PASSED
PROVIDERS_TOTAL = 3
MODELS_TOTAL = 6
EXPECTED_CALLS_TOTAL = 72
ALL_CALLS_ACCOUNTED = TRUE
FAILED_TABLES_EXCLUDED_TOTAL = 0
PROMPT_CHANGED_DURING_RUN = FALSE
INVENTORY_CHANGED_DURING_RUN = FALSE
DOC6_CHANGED = FALSE
```

No cascade, product route, provider adapter, runtime configuration, DOC6 recovery, or model activation was created.
