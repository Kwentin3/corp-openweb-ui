# Broker Reports DOC7 — Blind generalization and Markdown/JSON experiment

Date: 2026-08-03  
Repository head frozen for the experiment: `aec47d83826add1b091c01b3847b5f2a9c16c67b`  
Outcome: experiment completed; DOC6 failed on the unseen corpus; Markdown advantage was not established.

## Terminal classifications

```text
DOC6_GENERALIZATION = FAILED
MARKDOWN_VS_JSON = INCONCLUSIVE
OUTPUT_SCHEMA_PRESSURE = INCONCLUSIVE
```

The JSON arm had materially higher visible-entry recall and fewer invented and dropped values. Logical-row recall was nearly equal, and Markdown had fewer wrong-column associations. Under the frozen classification rule, this mixed binding direction prevents an overall `JSON_BETTER` claim.

## Frozen unseen corpus

The corpus was selected and its manifest sealed before visual gold, DOC6, or provider calls. Every PDF has a text layer on every page. No scan challenge set was mixed into the metrics.

| Safe ID | Official document | Publisher | Year | Pages | Gold tables | Complexity |
|---|---|---:|---:|---:|---:|---|
| `unseen_pdf_01` | [Statement of Financial Condition](https://m1.com/m1_financial_condition_statement.pdf) | M1 Finance LLC | 2025 | 16 | 6 | statements, sparse rows, money columns, subtotals/totals, one continuation |
| `unseen_pdf_02` | [iShares MSCI ACWI UCITS ETF factsheet](https://www.blackrock.com/gls-download/literature/fact-sheet/isad-ishares-msci-acwi-ucits-etf-fund-fact-sheet-en-se.pdf) | BlackRock / iShares | 2026 | 4 | 5 | adjacent tables, group headers, wide and percentage tables |
| `unseen_pdf_03` | [JPMorgan Unconstrained Debt Fund factsheet](https://am.jpmorgan.com/content/dam/jpm-am-aem/americas/us/en/literature/fact-sheet/taxable-fixed-income/FS-UD-I.PDF) | JPMorgan Asset Management | 2025 | 2 | 8 | adjacent tables, multilevel headers, wide money tables |
| `unseen_pdf_04` | [Vanguard U.S. Growth Fund factsheet](https://institutional.vanguard.com/iippdf/pdfs/FS23.pdf) | Vanguard | 2026 | 4 | 5 | two-column layout, adjacent and wide percentage tables |
| `unseen_pdf_05` | [ClearBridge RARE Infrastructure Value Fund factsheet](https://etf.franklintempleton.com/FormBuilder/_Resource/_module/2ALS5wVdVkKEMhM3WIDmaQ/file/FACTSHEET_RIVAFU%20A_30-November-2025%20%28AU60TGP00341%29.pdf) | Franklin Templeton / ClearBridge | 2025 | 1 | 5 | adjacent tables, group headers, percentages and currency markers |
| `unseen_pdf_06` | [Vanguard Target Retirement holdings](https://personal1.vanguard.com/funds/reports/h308q1.pdf?2210212504=) | Vanguard | 2025 | 24 | 36 | schedules, group headers, totals, derivatives, wide money tables |

Totals: 6 documents, 5 publishers, 51 pages, 65 meaningful tables. The 24-page Vanguard document is dominant, so both micro totals and table-class results are retained in the safe evidence.

### Why the documents are unseen

Before freeze, every selected SHA-256 and official URL produced zero matches in:

- the previous real-PDF scopes;
- current Git and Git history;
- private DOC2–DOC6 workspaces;
- prior manifests, visual-gold files, and test corpora;
- the known source-SHA history.

Two candidates were rejected because their bytes matched known Robinhood and TradeStation PDFs. This confirms that the check detects known sources rather than merely recording an assertion. No failed document was removed after selection.

The public frozen manifest contains each official URL, source SHA-256, size, page count, text-layer status, complexity tags, and zero-match counters. It contains no private filesystem path or source value.

## Visual gold

An isolated agent created gold directly from the PDFs before any tested-system output existed. It could not see DOC6 output, Markdown/JSON output, or recovery diagnostics. Ambiguous fields had to use `UNKNOWN`/`null`; the completed gold required no unknown row roles.

| Item | Total |
|---|---:|
| Documents | 6 |
| Tables | 65 |
| Logical rows | 649 |
| Visible entries | 2,062 |
| Headers | 144 |
| Group rows | 104 |
| Data rows | 325 |
| Subtotals | 18 |
| Totals | 56 |
| Notes | 2 |
| Cross-page continuation tables | 1 |

Gold integrity SHA-256: `b2543e1d85a10ff885e53162d15fed937f92dca35ec210298dd8f06cacd49d90`.

Schema, canonical integrity, manifest binding, PDF SHA/page sizes, bbox, ordinal/parent invariants, and the table-count gate all passed before DOC6 and provider execution.

## Experiment A — frozen DOC6

The unchanged factory path was invoked for all six PDFs:

```text
ManagedPdfDocumentV2Factory.create
→ FullSourceArtifactFactory.create
→ LogicalRowTableFactory.create
→ ManagedDocumentContractV2Validator.seal
→ ManagedDocumentLlmViewV2Factory.create
```

No provider, VLM, visual gold input, filename rule, correction map, override, grid owner, or product route was used.

All six attempts ended before a Managed Document could be produced:

| Terminal failure type | Documents |
|---|---:|
| `ManagedPdfDocumentV2Error` | 4 |
| `LogicalRowTableRecoveryError` | 2 |

Every failure remains in the denominator. Therefore:

| Metric | Result |
|---|---:|
| Tables detected / expected | 0 / 65 |
| Logical rows matched / expected | 0 / 649 |
| Entries matched / expected | 0 / 2,062 |
| Dropped visible value occurrences | 1,472 |
| Missing continuations | 1 |
| Provider calls | 0 |

Row order, row role, parent, and binding accuracy are not measurable because no table or row reached the comparison surface. Zero reported mismatches in those categories is vacuous, not evidence of correctness. All 2,062 expected entries and all 1,472 value occurrences are accounted as missing.

`DOC6_GENERALIZATION = FAILED`.

## Experiment B — paired Markdown and JSON

Each gold table was rendered at 180 DPI. Both arms received byte-identical crop sets, the same semantic instruction, the same context limit, the same exact model snapshot, and one call. The only prompt difference was the response-serialization instruction.

| Control | Result |
|---|---|
| Model snapshot | `gpt-5.4-2026-03-05` returned by 130/130 calls |
| Calls | 65 Markdown + 65 JSON |
| HTTP outcomes | 130 × 200 |
| Attempts | 130; no retry and no best-of |
| Input parity failures | 0 |
| Tools / retrieval / web | 0 / 0 / 0 |
| Store | `false` |
| Truncations | 0 |
| Markdown prompt SHA-256 | `1956ee866440cb4ea979d14098e6cf9546e8b9530fc4c35845e23cb120cce0e3` |
| JSON prompt SHA-256 | `c2d4519ce44f943cea9325d714ee8aa6da37323b35b1280b352aa4d99d6009d4` |

### Aggregate results

| Metric | Markdown | JSON |
|---|---:|---:|
| Table recall | 65/65 (100.00%) | 65/65 (100.00%) |
| Logical-row recall | 630/649 (97.07%) | 631/649 (97.23%) |
| Header-row recall | 126/144 (87.50%) | 127/144 (88.19%) |
| Group-row recall | 104/104 (100.00%) | 104/104 (100.00%) |
| Data-row recall | 325/325 (100.00%) | 325/325 (100.00%) |
| Subtotal-row recall | 18/18 (100.00%) | 18/18 (100.00%) |
| Total-row recall | 56/56 (100.00%) | 56/56 (100.00%) |
| Note-row recall | 1/2 (50.00%) | 1/2 (50.00%) |
| Visible-entry recall | 1,819/2,062 (88.22%) | 1,960/2,062 (95.05%) |
| Row-order mismatches | 77 | 1 |
| Wrong row associations | 6 | 6 |
| Wrong column associations | 30 | 43 |
| Invented value occurrences | 258 | 44 |
| Dropped value occurrences | 280 | 47 |
| Duplicated value occurrences | 0 | 0 |
| Invalid JSON | n/a | 0 |
| Frozen malformed-Markdown diagnostic | 15 | n/a |
| Truncated responses | 0 | 0 |

The malformed-Markdown counter is conservative: the frozen evaluator flags heterogeneous pipe widths across a response, including legal multiple Markdown tables. It is disclosed but not used for the final classification.

### Pre-registered questions

Paired table bootstrap: 10,000 resamples, seed 1729, two-sided 95% interval.

| Question | Answer | Markdown advantage; 95% CI |
|---|---|---:|
| More logical rows | `INCONCLUSIVE` | -0.00156; [-0.01071, 0.00769] |
| More visible entries | `FALSE` | -0.07775; [-0.11652, -0.04487] |
| Fewer wrong row bindings | `INCONCLUSIVE` | 0.00000; [-0.10769, 0.12308] |
| Fewer wrong column bindings | `INCONCLUSIVE` | 0.20000; [-0.20000, 0.64615] |

Markdown therefore did not retain more logical rows, and the hypothesis that it retains more visible values was rejected on this corpus.

### Safe examples

Visible values are deliberately omitted from Git evidence.

- Markdown preserved a row that JSON lost in `unseen_pdf_01_t04` (sparse money/subtotal table) and `unseen_pdf_06_t24` (wide multilevel affiliated-transactions table).
- Markdown had wrong column bindings in `unseen_pdf_01_t04` (4), `unseen_pdf_03_t06` (24), and `unseen_pdf_04_t04` (1).
- Markdown had wrong row bindings in `unseen_pdf_01_t02` (2), `unseen_pdf_01_t03` (1), `unseen_pdf_01_t06` (2), and `unseen_pdf_03_t02` (1).
- JSON preserved a row that Markdown lost in `unseen_pdf_01_t02`, `unseen_pdf_06_t18`, and `unseen_pdf_06_t30`.

Class-level results are not materially contradictory: JSON's large entry-recall advantage is concentrated in schedule-of-investments, group-header, and sparse-row classes; the two arms are near parity in several smaller classes. Markdown has only small entry-recall point advantages in performance/percentage tables, insufficient for a table-class-dependent conclusion.

## Integrity and acceptance

```text
UNSEEN_CORPUS_FROZEN = TRUE
UNSEEN_DOCUMENTS_TOTAL = 6
UNSEEN_TABLES_TOTAL = 65
VISUAL_GOLD_CREATED_BEFORE_RUN = TRUE
DOC6_CODE_CHANGED_DURING_RUN = FALSE
DOC6_BLIND_RUN_COMPLETED = TRUE
DOC6_DOCUMENTS_WITH_MANAGED_OUTPUT_TOTAL = 0
DOC6_TERMINAL_FAILURES_TOTAL = 6
MARKDOWN_ARM_COMPLETED = TRUE
JSON_ARM_COMPLETED = TRUE
ALL_CORPUS_DOCUMENTS_REPORTED = TRUE
FAILED_DOCUMENTS_EXCLUDED_TOTAL = 0
ALL_MISMATCHES_ACCOUNTED = TRUE
```

`DOC6_BLIND_RUN_COMPLETED` means every frozen document received one terminal, accounted attempt; it does not mean DOC6 produced an output.

The evaluator and runner self-tests passed before freeze. Frozen-file verification passed after DOC6 and both provider arms. The final service-cwd regression run passed 306 tests, including 8 DOC7 public-evidence tests. Those tests verify canonical hashes, corpus gates, metrics, call parity, exact model snapshot, classifications, the privacy denylist, and unchanged DOC6 source hashes.

## Stop boundary

DOC6, Managed Document v2, View v2, prompts, evaluator, comparison rules, and visual gold were not modified during the blind run. No DOC6 fix, Markdown-to-Logical-Row implementation, product integration, activation, fallback, or universal-parser claim was made.
