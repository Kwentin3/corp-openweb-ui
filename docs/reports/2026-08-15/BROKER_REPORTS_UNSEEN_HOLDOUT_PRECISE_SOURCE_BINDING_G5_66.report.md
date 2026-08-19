# G5.66 — Unseen Holdout Precise Source Binding Proof

Дата: 2026-08-15
Статус: `CLOSED_WITH_LOCALIZED_SEMANTIC_RESIDUALS`

## Terminal

```text
UNSEEN_HOLDOUT_SOURCE_BINDING_PROVEN
REPEATED_LITERAL_PHYSICAL_AMBIGUITY_ZERO
HOLDOUT_ORACLE_VISIBILITY_5_OF_5
FROZEN_METADATA_VISIBILITY_24_OF_24_PRESERVED
SAME_LLM_INSTRUCTION_1_1_REPLAY_COMPLETED
FINANCIAL_GENERALIZATION_PRESERVED
LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED
```

## Frozen boundary

- тот же unseen holdout и неизменённый G5.65 source-truth oracle: `5` facts;
- metadata contract `1.0.0`, instruction `1.1.0`, proposal schema unchanged;
- provider/model unchanged: `google_gemini` / `models/gemini-3.5-flash`;
- semantic fields added: `0`;
- financial code, Gate 4 и Gate 5 не менялись.

Изменён только structural context policy: `v3 → v4`.

## Visual qualification of the four G5.65 ambiguities

Первая страница PDF проверена визуально. Старый `m001/FULL_TEXT_NODE` объединял
девять естественных Canonical lines.

| Proposal meaning | Occurrences in old target | Physical source places | Canonical distinction |
|---|---:|---|---|
| document kind | 2 | page header, page footer | `lines[0]`, `lines[8]` |
| statement period | 2 | page header, page footer | `lines[1]`, `lines[8]` |
| report date | 2 | creation line, page footer | `lines[1]`, `lines[8]` |
| short identifier | 2 | contract line, trading-code line | `lines[3]`, `lines[7]` |

Первый неправильный owner — `build_metadata_context_package`, который создавал
один full-text target на весь `TEXT` node. Canonical и validator уже сохраняли
точные `content.text.lines[n]`; validator ничего не терял.

## Minimal structural refinement

Каждая непустая Canonical `TEXT` line теперь отдельный `TEXT_LINE` target с
одним fragment и точным `field_path`. Это общая structural операция без знания
person, broker, account или contract semantics. Fixed page/column/substring
rules, invented headings и semantic hints: `0`.

Table behavior не менялось: small table остаётся `row + header`; large tables
не добавлены в metadata context. G5.64 duplicate-evidence aggregation и
multi-account preservation подтверждены теми же behavior tests.

## Offline proof before provider

Provider calls: `0`.

| Corpus | Oracle visibility | Ambiguous | Targets | Context chars |
|---|---:|---:|---:|---:|
| unseen holdout | 5/5 | 0 | 101 | 16,836 |
| frozen `pdf_002` | 9/9 | 0 | 2,458 | 76,921 |
| frozen `pdf_024` | 6/6 | 0 | 723 | 28,276 |
| frozen `holdout_a` | 3/3 | 0 | 65 | 9,267 |
| frozen `holdout_b` | 6/6 | 0 | 17 | 1,683 |
| **frozen total** | **24/24** | **0** | **3,263** | **116,147** |

Packager signature не принимает oracle; packaging завершался до measurement.
Удаление oracle не меняет selection или binding.

## One clean holdout replay

Factory route:

```text
CanonicalReaderFactory.create
→ Gate3LlmMetadataAdapterFactory.create
→ Gate2StructuredModelClientFactory.create
→ one OpenWebUI provider submission
```

Execution accounting:

- provider submissions: `1`, calls per document: `1`;
- retry / best-of-N / manual repair: `0 / false / false`;
- source store unchanged: `true`;
- input/output/provider-total: `10,265 / 401 / 13,738` tokens;
- duration: `18,484 ms`;
- validator: `validated`, published facts: `7`;
- raw output remained unchanged; no second replay.

## Clean semantic residual

| Metric | Value |
|---|---:|
| source truth | 5 |
| raw / published | 7 / 7 |
| correct | 4 |
| missed | 1 |
| semantic extras | 3 |
| wrong role | 2 |
| incomplete/overinclusive value | 1 |
| ambiguous bindings | 0 |
| invented literals | 0 |
| invalid provenance | 0 |

Remaining classes are exactly:

1. `TRADING_CODE_MISCLASSIFIED_AS_ACCOUNT_IDENTIFIER`;
2. `BROKER_ROLE_INFERRED_NOT_EXPLICIT`;
3. `CONTRACT_IDENTIFIER_LABEL_OVERINCLUSION`.

Signer→party and tax-residency→citizenship negative cases remained clean.
Semantic instruction, validator and output were not changed after replay.

## Financial and architecture verification

Current factory replay through
`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`:

- `holdout_a`: `39`, `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- `holdout_b`: `129`, `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`.

Verification under Windows PowerShell with no special test ENV:

- focused metadata/binding suite: `37 passed`;
- architecture guard suite: `65 passed`;
- failures: `0`; only pre-existing SWIG/escape deprecation warnings;
- `FACTORY_REQUIRED` / `FORBIDDEN` anchors preserved;
- offline tests mock only external boundaries; unit under test is real;
- replay terminal is persisted, not inferred from transport success.

## KISS and scope stop

One existing owner changed from full `TEXT` node addressing to existing
Canonical line addressing. No locator engine, RAG, graph, resolver, generic
dedup subsystem, prompt tuning or broker-specific rule was added.

Private PDF bytes, paths, names, raw output and oracle remain outside Git.
Product activation, commit, push, PR and the next semantic Goal were not run.
