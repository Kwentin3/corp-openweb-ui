# Broker Reports DOC15 — real reports blind holdout

## Outcome

- `DOC15_EXPERIMENT = COMPLETED`
- `SOURCE_TEXT_EFFECT = INCONCLUSIVE`
- `PASSED_PROVIDERS = []`
- `BEST_CHEAP_PROVIDER = openai_mini`
- `BEST_REFERENCE_PROVIDER = anthropic_opus`
- `GATE1_EXIT = NOT_CONFIRMED`
- Pipeline activation: not performed. Gate 2: not started.

## Corpus

Six official public reports from 6 issuers supplied exactly 24 sealed table crops. Hash overlap with DOC7–DOC14 PDFs: 0.

| Issuer | Document date | Pages | Detector candidates | SHA-256 |
|---|---:|---:|---:|---|
| Acorns Securities, LLC | 2025-12-31 | 14 | 12 | `85a3ad19deaf54d834fca1f05dec4efdf81dc0fca80fb5077d69891b2bb539a0` |
| Jefferies Financial Group Inc. | 2024-11-30 | 130 | 137 | `bb3a6c531c0a7ebc51110ac70ec06c7b6fdc9551adc596214129d5f70605332d` |
| LPL Financial Holdings Inc. | 2025-12-31 | 138 | 86 | `8244061079bf195e365b829c38bdfc865b3633819633a0cee584fda801538993` |
| StoneX Group Inc. | 2025-09-30 | 188 | 222 | `79d3dc2cdc9380b53620d28950500dea16ecd27b5c4ef98129bc264c6ff61056` |
| Tradeweb Markets Inc. | 2025-12-31 | 181 | 195 | `881b59b022436a2938cc530bf4fa308b39db081622381c3d0e73a8b631012881` |
| Oppenheimer Holdings Inc. | 2025-12-31 | 12 | 10 | `c6a8570a829884f697cc1651d44b151e3951142e582b62fe946a9c4d75744cf8` |

The 24 sealed IDs are: `ACORNS_T01`, `ACORNS_T02`, `ACORNS_T03`, `JEFFERIES_T01`, `JEFFERIES_T02`, `JEFFERIES_T03`, `JEFFERIES_T04`, `JEFFERIES_T05`, `JEFFERIES_T06`, `LPL_T01`, `LPL_T02`, `LPL_T03`, `LPL_T04`, `STONEX_T01`, `STONEX_T02`, `STONEX_T03`, `STONEX_T04`, `STONEX_T05`, `TRADEWEB_T01`, `TRADEWEB_T02`, `TRADEWEB_T03`, `TRADEWEB_T04`, `TRADEWEB_T05`, `OPPENHEIMER_T01`.

## Reuse boundary

DOC15 reused `FullSourceArtifactFactory`, its builder-owned `PdfTextLayerParserFactory` and `PdfLayoutUnitBuilder`, the existing crop renderer, `NativePdfTransport.invoke_image_structured`, the durable journal pattern, the existing evaluator primitives, and the private-to-safe publisher boundary. DOC15 added only private corpus/gold data plus thin experiment orchestration and a safe-evidence contract test. No parser, renderer, provider client, product route, DOC6, or Gate 2 code was added.

## Provider results

| Model | Arm | Valid | Recall | Precision | Unsupported | Source gaps | Row assoc. | Column assoc. | Header | Exact | Cost/table USD | Latency/table s | PASS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `openai_mini` | `IMAGE_ONLY` | 100.00% | 99.53% | 98.26% | 26 | 67 | 50.04% | 53.39% | 46.51% | 8.33% | 0.003487 | 7.050 | False |
| `openai_mini` | `IMAGE_PLUS_SOURCE_TEXT` | 100.00% | 98.78% | 96.88% | 47 | 62 | 59.81% | 50.77% | 47.67% | 8.33% | 0.003866 | 5.255 | False |
| `google_flash_lite` | `IMAGE_ONLY` | 100.00% | 95.40% | 99.23% | 11 | 64 | 70.31% | 88.48% | 62.79% | 29.17% | 0.002360 | 6.931 | False |
| `google_flash_lite` | `IMAGE_PLUS_SOURCE_TEXT` | 100.00% | 93.17% | 98.01% | 28 | 54 | 69.95% | 85.92% | 73.26% | 16.67% | 0.002621 | 4.561 | False |
| `anthropic_haiku` | `IMAGE_ONLY` | 100.00% | 97.97% | 96.60% | 51 | 62 | 47.63% | 61.34% | 32.56% | 4.17% | 0.004061 | 8.280 | False |
| `anthropic_haiku` | `IMAGE_PLUS_SOURCE_TEXT` | 100.00% | 96.01% | 95.62% | 65 | 51 | 47.92% | 72.14% | 37.21% | 4.17% | 0.004778 | 6.544 | False |
| `anthropic_opus` | `IMAGE_ONLY` | 100.00% | 99.86% | 97.43% | 39 | 67 | 78.12% | 93.22% | 81.40% | 29.17% | 0.028627 | 13.180 | False |
| `anthropic_opus` | `IMAGE_PLUS_SOURCE_TEXT` | 91.67% | 93.84% | 97.81% | 31 | 62 | 63.46% | 86.94% | 80.23% | 29.17% | 0.030943 | 10.267 | False |

## Source-text effect

Paired bootstrap used 10,000 deterministic paired resamples of the same 24 tables for every model. No hidden weighted score was used.

- `openai_mini`: `INCONCLUSIVE`; deltas `{"column_association_accuracy": -0.026258205689277947, "complete_table_exact_rate": 0.0, "cost_usd_total": 0.009111750000000002, "critical_value_recall": -0.007442489851150258, "header_accuracy": 0.011627906976744207, "latency_seconds_total": -43.09100000000001, "row_association_accuracy": 0.09773887673231219, "unsupported_values_total": 21}`.
- `google_flash_lite`: `INCONCLUSIVE`; deltas `{"column_association_accuracy": -0.025528811086797942, "complete_table_exact_rate": -0.12500000000000003, "cost_usd_total": 0.006273100000000004, "critical_value_recall": -0.022327469553450663, "header_accuracy": 0.10465116279069764, "latency_seconds_total": -56.900999999999996, "row_association_accuracy": -0.00364697301239969, "unsupported_values_total": 17}`.
- `anthropic_haiku`: `INCONCLUSIVE`; deltas `{"column_association_accuracy": 0.10795040116703136, "complete_table_exact_rate": 0.0, "cost_usd_total": 0.017203999999999997, "critical_value_recall": -0.01962110960757779, "header_accuracy": 0.046511627906976716, "latency_seconds_total": -41.667, "row_association_accuracy": 0.002917578409919741, "unsupported_values_total": 14}`.
- `anthropic_opus`: `INCONCLUSIVE`; deltas `{}`.

## Call accounting

All 192 slots are terminal and accounted: 190 completed, 2 failed or interrupted. Attempts: 192; retries: 0; fallbacks: 0; repairs: 0.

## Error classes and table classes

Aggregate error counts are reported separately for unsupported values, source-text gaps, missing and duplicated values, wrong rows and columns, header errors, split/merged/missing/extra rows, and missing/extra notes. Class-level metrics cover simple, wide, dense, sparse, multilevel-header, group-row, total, note, long-text, repeated-value, empty-cell, and continuation cases in the safe provider artifact.

## Optimization diagnostic

- **Reduce source-text context** — `NOT_RECOMMENDED_WITH_CURRENT_EVIDENCE`. Benefit: lower input tokens and cost. Risk: may remove values classified as source-text gaps or useful lexical evidence. Effort: medium.
- **Shorten prompt** — `NOT_RECOMMENDED_WITHOUT_NEW_CONTROLLED_ARM`. Benefit: small input-token reduction. Risk: could alter structure fidelity. Effort: low.
- **Reduce maximum output tokens** — `RECOMMENDED_FOR_SEPARATE_NEXT_GOAL`. Benefit: smaller worst-case budget. Risk: truncation on dense tables. Effort: low.
- **Review crop margins** — `RECOMMENDED_FOR_SEPARATE_NEXT_GOAL`. Benefit: avoid clipped labels at detector boundaries. Risk: wider crops may add neighboring content. Effort: medium.
- **Provider routing** — `NOT_RECOMMENDED_WITH_CURRENT_EVIDENCE`. Benefit: use a cheap passing primary where proven. Risk: routing can hide model-specific failures without deterministic validation. Effort: medium.
- **Deterministic validation before fallback** — `RECOMMENDED_FOR_DESIGN_RESEARCH_ONLY`. Benefit: bounded fallback decisions. Risk: content validation cannot be fully proven without gold. Effort: high.

These are recommendations only. `OPTIMIZATIONS_APPLIED_DURING_RUN = 0`.

## Decision

`GATE1_EXIT = NOT_CONFIRMED` under the pre-frozen thresholds. This closes DOC15 only; it does not activate the pipeline or authorize Gate 2.
