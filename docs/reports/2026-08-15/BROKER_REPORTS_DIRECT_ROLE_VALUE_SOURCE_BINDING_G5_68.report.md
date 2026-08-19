# G5.68 — Direct Role-Value Source Binding Proof

Дата: 2026-08-15
Статус: `CLOSED_STRUCTURE_PROVEN_WITH_UNREPAIRED_LLM_RESIDUALS`

## Terminal

```text
DIRECT_ROLE_VALUE_SOURCE_BINDING_PROVEN
COMPOSITE_ROLE_EVIDENCE_OVERREACH_REMOVED
PHYSICAL_AND_ROLE_EVIDENCE_BINDING_VALID
CLIENT_CODE_ACCOUNT_SEMANTIC_ERROR_PERSISTS
PURE_LLM_SEMANTIC_FAILURE_PROVEN
NON_DIRECT_MODEL_EVIDENCE_REJECTED
NO_HEURISTIC_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

`DEVELOPMENT_METADATA_CORPUS_SOURCE_ALIGNED` и `CURRENT_UNSEEN_HOLDOUT_SOURCE_ALIGNED` не объявлены: replay сохранил model residuals.

## Visual qualification and first wrong owner

G5.67 failing source проверен по render первой страницы. Значение находится в cell, непосредственно подписанной локальной label «код клиента». Account-related text находится в другой row той же headerless key/value table.

Canonical уже различает обе cells, их row/column и содержит пустой `content.header`. Новый layout engine не нужен. Первый wrong owner был `_small_table_row_candidates`: он всегда принимал минимальную row за header и создавал compound `header + row` evidence target.

## Minimal refinement

- rich model context сохранён;
- каждый evidence alias теперь указывает на одну точную line/cell;
- header lineage разрешена только при непустом реальном Canonical `content.header`;
- validator допускает только same atomic address, same row или same-column real header lineage;
- same table/page alone отклоняются;
- instruction `1.2.0`, proposal schema v2 и semantic context policy v4 не менялись.

Human-language semantics, regex/synonyms, blacklist, broker branches, RAG/graph/judge/retry: `0`.

## Offline proof before provider

Provider calls: `0`.

| Corpus | Visibility | Ambiguity |
|---|---:|---:|
| G5.62 development | 24/24 | 0 |
| G5.66 current unseen | 5/5 | 0 |

Known wide role→value binding больше не direct. Точная local label→value relation квалифицирована как `SAME_TABLE_ROW`. Обязательные LABEL|VALUE, HEADER↓VALUE, SAME LINE, SAME TABLE ONLY, SAME PAGE ONLY и same literal/different labels покрыты behavior tests.

## One clean replay

Gemini ответил на все пять frozen submissions; transport/balance `400` не возник.

- documents/submissions: `5/5`, по одному call;
- retry / best-of-N / manual repair: `0 / false / false`;
- source stores unchanged: `true`;
- provider input/output/total tokens: `369917 / 2835 / 388404`;
- provider duration total: `99313 ms`;
- повторный replay после residuals не выполнялся.

Квалификация raw output без мутации:

| Metric | Total |
|---|---:|
| raw facts | 30 |
| structurally accepted assertions | 26 |
| correct facts | 21 |
| missed facts | 8 |
| semantic extras | 5 |
| wrong roles | 1 |
| role/value structural failures | 4 |
| invented literals | 0 |
| invalid provenance | 0 |
| duplicates | 0 |

Четыре non-direct evidence choices были fail-closed отклонены. Известный G5.67 case теперь ссылается на точную local label cell и соседнюю value cell (`SAME_TABLE_ROW`), но модель всё равно публикует `ACCOUNT_IDENTIFIER`. Это чистый semantic LLM failure; он не исправлялся.

## Financial and architecture regression

`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`:

- `holdout_a`: `39`, before/after SHA-256 identical;
- `holdout_b`: `129`, before/after SHA-256 identical;
- оба: `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- source stores unchanged: `true`.

Verification:

- focused metadata/qualification: `56 passed`;
- architecture/cross-gate/canonical/bundle: `55 passed`;
- failures: `0`;
- только прежние SWIG deprecation warnings;
- generated OpenWebUI bundles пересобраны и parity tests green.

## KISS and scope stop

Изменён один существующий owner адресации и его deterministic validator. Не созданы layout engine, semantic validator, vocabulary, graph или parallel metadata subsystem.

Private PDF, visual, oracle, raw provider output и private qualification остаются вне Git. Product activation, commit, push, PR, instruction `1.3.0` и следующий Goal не выполнялись.
