# G5.65 — Minimal Metadata Semantic Contract Refinement + Holdout Proof

Дата: 2026-08-15
Статус: `CLOSED_NEGATIVE_HOLDOUT_TERMINAL`

## Outcome

После прямого разрешения пользователя transient provider failure был проверен
ещё одним clean replay в отдельном output root. Frozen corpus прошёл `24/24`,
но обязательный unseen metadata holdout не прошёл strict validation и показал
новые semantic residuals. Contract после holdout не менялся, retry и repair не
выполнялись.

```text
MINIMAL_SEMANTIC_REFINEMENT_PROVEN_ON_FROZEN_CORPUS
FROZEN_METADATA_CORPUS_SOURCE_ALIGNED
LLM_METADATA_SEMANTIC_GENERALIZATION_NOT_PROVEN
EXACT_SEMANTIC_FAILURE_CLASSES_LOCALIZED
NO_RUNTIME_HEURISTIC_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

## Semantic change

Pre-change visual audit classified incomplete contract and mixed document
heading as `CONTRACT_UNDERSPECIFIED`; client-code/account as
`MODEL_IGNORED_CLEAR_CONTRACT`. Из остальных восьми fields только прежний
passport-to-citizenship case имел ту же boundary ambiguity.

Instruction изменилась один раз: `1.0.0 → 1.1.0`. Metadata contract и набор 11
fields остались `1.0.0`. Уточнены только meaning boundaries account, complete
contract identifier, document kind и explicit citizenship.

Broker-specific examples, synonym vocabulary, human-language regex, special
prompt branches и Python semantic branches: `0`. Packaging, validator, schema
и factory code не менялись.

## Phase 1 r1 — preserved transient incident

Первый frozen replay выполнил четыре submissions и получил:

```text
HTTP 400
detail = Model not found
resolved_model_id = null
```

Это не было доказательством balance/quota failure: billing/quota detail в
ответе отсутствовал. Raw r1 evidence сохранён неизменным.

## Phase 1 r2 — explicit user-authorized replay

Пользователь подтвердил доступность той же модели в OpenWebUI и прямо разрешил
повтор. R2 сохранил frozen corpus, instruction, context v3, schema,
provider/model и factory route.

| Case | Raw / published | Correct | Missed | Extras | Ambiguous | Validator |
|---|---:|---:|---:|---:|---:|---|
| `pdf_002` | 9 / 9 | 9 | 0 | 0 | 0 | accepted |
| `pdf_024` | 6 / 6 | 6 | 0 | 0 | 0 | accepted |
| `holdout_a` | 3 / 3 | 3 | 0 | 0 | 0 | accepted |
| `holdout_b` | 6 / 6 | 6 | 0 | 0 | 0 | accepted |
| **Total** | **24 / 24** | **24** | **0** | **0** | **0** | **4/4 accepted** |

Три G5.64 residuals resolved. Passport wording не стало citizenship. Invented
literals, invalid provenance, duplicates и unsupported fields: `0`.

R2 accounting: `4` calls, `1/document`, input `89,538`, output `1,587`,
provider total `105,766` tokens, duration `74,360 ms`. Retry, best-of-N и
manual repair: `0 / false / false`.

## Phase 2 — frozen unseen metadata holdout

До LLM execution выбран один real six-page report другого broker/layout. Его
source SHA не участвовал в G5.60–G5.65 metadata tuning; прежнее использование
ограничивалось structural/Gate 5 задачами. Selection, instruction hash и source
truth frozen до model call.

Визуальный oracle содержит пять fields: `DOCUMENT_TYPE`, `STATEMENT_PERIOD`,
`DOCUMENT_DATE`, `PARTY_NAME`, `ACCOUNT_CONTRACT_IDENTIFIER`. До output также
зафиксировано: trading code не account, signer не report subject, tax residency
не citizenship, company mention без явной broker role не broker legal name.

Единственный holdout submission получил model output, но validator завершил его:

```text
gate3_llm_metadata_literal_binding_ambiguous
```

| Metric | Value |
|---|---:|
| source-present supported facts | 5 |
| raw proposal facts | 7 |
| correct raw semantics | 4 |
| missed | 1 |
| semantic extras | 3 |
| invented literals | 0 |
| unsupported fields | 0 |
| ambiguous literal bindings | 4 |
| published facts after strict rejection | 0 |

Exact failure classes:

1. `REPEATED_LITERAL_WITHIN_SINGLE_CONTEXT_TARGET`;
2. `TRADING_CODE_MISCLASSIFIED_AS_ACCOUNT_IDENTIFIER`;
3. `BROKER_ROLE_INFERRED_NOT_EXPLICIT`;
4. `CONTRACT_IDENTIFIER_LABEL_OVERINCLUSION`.

Signer и citizenship negative cases passed. Trading-code/account и contract
boundary failed. Никакого post-hoc удаления extras или выбора другого target не
выполнено.

Holdout accounting: `1` call, input `9,535`, output `578`, provider total
`12,091` tokens, duration `157,125 ms`; retry/best-of-N/repair:
`0 / false / false`.

## Total execution, verification and scope

- provider submissions in G5.65: `9` (`4` r1 errors + `4` r2 + `1` holdout);
- successful provider input/output/total: `99,073 / 2,165 / 117,857` tokens;
- r1 token fields and provider monetary cost: unavailable;
- focused suite: `29 passed`; broad architecture suite: `123 passed`;
- financial persisted Gate 4 counts: `39 / 129`;
- G5.60 deterministic extractor unchanged; product activation: `false`.

KISS preserved: one instruction version change, no runtime fallback or tuning
after holdout. No commit, push, PR or next GOAL.
