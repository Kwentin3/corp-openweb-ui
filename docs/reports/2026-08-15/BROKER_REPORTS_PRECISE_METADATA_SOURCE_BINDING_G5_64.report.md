# G5.64 — Precise Metadata Source Binding & Duplicate Evidence Proof

Дата: 2026-08-15
Статус: `CLOSED_WITH_LOCALIZED_SEMANTIC_RESIDUALS`

## Terminal

```text
METADATA_STRUCTURAL_SOURCE_BINDING_PROVEN
FROZEN_ORACLE_VISIBILITY_24_OF_24_PRESERVED
REPEATED_ASSERTION_EVIDENCE_MODEL_PROVEN
SAME_FACT_DUPLICATE_PUBLICATION_ZERO
MULTI_VALUE_METADATA_PRESERVED
WHOLE_TABLE_LITERAL_AMBIGUITY_REMOVED
SAME_LLM_ADAPTER_CLEAN_REPLAY_COMPLETED
FINANCIAL_GENERALIZATION_PRESERVED
LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED
```

G5.64 закрыл structural contract, но не объявил LLM семантически точной. После
точной адресности остались три локализованных semantic/extraction residuals.
Prompt, instruction, contract meaning и output не ремонтировались.

## Freeze

- corpus: `pdf_002`, `pdf_024`, `holdout_a`, `holdout_b`;
- G5.62 source truth: `24` assertions, Canonical loss `0`;
- metadata contract `1.0.0`, 11 fact types;
- instruction `1.0.0` и proposal schema
  `broker_reports_llm_metadata_proposal_v1` exact относительно G5.63 replay;
- provider/model: `google_gemini` / `models/gemini-3.5-flash`;
- Gate 2 model client/request/provider adapter и live replay harness: exact
  full-file hashes относительно G5.63 baseline;
- financial pipeline, Gate 4 и Gate 5 не менялись.

Единственная новая frozen copy отличается от G5.63 corpus manifest только
`context_policy_version=v3`; все source identities, Canonical roots, contexts,
oracle hashes, provider и model exact.

## Phase 1 — provider calls 0

### Failure attribution G5.63

- `WHOLE_TABLE_TARGET_REPEATED_LITERAL_AMBIGUITY`: один alias содержал все rows,
  поэтому одинаковый owner literal соответствовал нескольким Canonical cells;
- `PARTIAL_ACCOUNT_LITERAL_AMBIGUITY`: короткий account literal встречался
  внутри нескольких cells одного whole-table target;
- repeated document headers были физически валидны, но прежний validator
  отклонял второй semantic key вместо сохранения дополнительного evidence.

### Minimal structural change

Small table теперь публикуется как `row + source header`. Все rows сохранены,
row/character/target cutoff не добавлен. `TEXT` остаётся Canonical text block:
валидируемая address unit — ровно один реальный `content.text.lines[n]`
fragment, поэтому искусственное оконное дробление и придуманные headings не
нужны.

Qualification после полной packaging, до обращения к oracle:

| Case | Visible | Ambiguous | Targets | Row+header targets | Context chars |
|---|---:|---:|---:|---:|---:|
| `pdf_002` | 9 | 0 | 18 | 0 | 79,361 |
| `pdf_024` | 6 | 0 | 6 | 0 | 28,993 |
| `holdout_a` | 3 | 0 | 59 | 46 | 9,273 |
| `holdout_b` | 6 | 0 | 14 | 10 | 1,686 |
| **Total** | **24** | **0** | **97** | **56** | **119,313** |

Whole-table targets: `0`. Semantic hints: `0`. Broker-specific rules: `0`.
Oracle selector input: `false`.

## Duplicate-evidence contract

Validator сначала независимо доказывает каждый physical binding. Затем
publication group использует только fact type, normalized value и structural
source context. Первый source-order binding остаётся primary, полный список
сохраняется в `source_binding.evidence_locations`.

Deterministic behavior tests доказали:

- одинаковое text assertion в трёх source places: `3 raw → 1 published`,
  evidence locations `3`;
- одинаковый owner под одним table header в двух rows: один party fact с двумя
  evidence locations;
- `ACCOUNT-A` и `ACCOUNT-B`: два независимых facts;
- разные periods: независимые facts;
- `Client: X` и `Signed by: X`: два assertions, automatic collapse `0`;
- один и тот же proposal/alias дважды: fail closed, а не fake evidence.

Live replay в этот раз сам вернул raw repeated assertions `0`, поэтому live
collapse count также `0`; обязательная collapse ветка доказана реальным
validator в deterministic tests, не post-hoc обработкой replay output.

## Phase 2 — один clean replay

Исходный Python process выполнил ровно один submission на документ. Retry,
best-of-N, manual repair и второй replay отсутствуют.

| Case | Raw / published | Correct | Missed | Extras | Ambiguous | Validator |
|---|---:|---:|---:|---:|---:|---|
| `pdf_002` | 9 / 9 | 9 | 0 | 0 | 0 | accepted |
| `pdf_024` | 6 / 6 | 5 | 1 | 1 | 0 | accepted |
| `holdout_a` | 4 / 4 | 3 | 0 | 1 | 0 | accepted |
| `holdout_b` | 6 / 6 | 5 | 1 | 1 | 0 | accepted |
| **Total** | **25 / 25** | **22** | **2** | **3** | **0** | **4/4 accepted** |

Invented literals, invalid provenance/value и unsupported fields: `0/0/0`.
Published duplicate assertions: `0`. Восемь facts в multi-value groups
сохранены независимо: два account identifiers и три periods в `pdf_002`, три
account identifiers в `holdout_b`.

Execution accounting:

- provider calls: `4`, per document `1`;
- retry / best-of-N / manual repair: `0 / false / false`;
- rendered context: `119,313 chars`;
- final model input: `147,398 chars`, `88,958 input tokens`;
- output: `2,031 tokens`;
- provider-reported total: `103,022 tokens`;
- total duration: `72,515 ms`;
- source stores unchanged: `true`.

## Visual semantic residuals

1. `INCOMPLETE_CONTRACT_IDENTIFIER`: source и Canonical содержат полный
   identifier с датой, LLM скопировала только префикс. Это extraction residual,
   не binding ambiguity.
2. `CLIENT_CODE_NOT_ACCOUNT_IDENTIFIER`: точная row `Код клиента` была неверно
   опубликована как account identifier. Контрольная semantic ошибка не скрыта.
3. `DOCUMENT_TYPE_CONTAMINATED_BY_ADJACENT_ISSUER`: точный Canonical line
   содержит document heading и соседний issuer marker; LLM включила marker в
   document type. Correct substring доступен, физический binding однозначен;
   semantic/extraction repair не разрешён.

Passport→citizenship error в этом replay не повторилась, но никаких правил
против неё не добавлено.

## Financial regression

На private копиях stores выполнен
`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`:

- `holdout_a`: `39`, status `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- `holdout_b`: `129`, status `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- exact canonical JSON equality до/после rebuild: `true` для обоих.

## Verification and architecture

- focused G5.64 behavior suite: `25 passed`;
- broad metadata/Canonical/Gate 4/architecture/KT1 suite: `141 passed`;
- failures: `0`; warnings: шесть существующих SWIG/escape deprecations;
- factory path preserved: Canonical reader → `Gate3LlmMetadataAdapterFactory`
  → configured Gate 2 model client → one provider submission;
- `FACTORY_REQUIRED` / `FORBIDDEN` anchors и architecture guards green;
- unit under test не mocked; provider — единственная mocked/external boundary в
  offline tests; replay terminal подтверждён persisted private result;
- private PDF bytes, values, paths, screenshots, raw outputs и oracle не
  committed.

## KISS and scope stop

Один existing packager и один validator получили две узкие операции: row+header
addressability и evidence aggregation. Не появились graph, registry, generic
dedup framework, synonym vocabulary, reconciliation, retry или новый owner.

LLM adapter остаётся proof-only. Product activation, commit, push, PR и
следующий semantic GOAL не выполнялись.
