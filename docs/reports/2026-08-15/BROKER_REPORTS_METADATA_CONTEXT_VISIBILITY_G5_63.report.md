# G5.63 — Metadata Context Visibility Generalization Proof

Дата: 2026-08-15
Статус: `PARTIAL`

## Terminal

```text
METADATA_CONTEXT_POSITION_INDEPENDENCE_PROVEN
FROZEN_ORACLE_CONTEXT_VISIBILITY_24_OF_24
MAGIC_TEXT_HEAD_CUTOFF_REMOVED
SAME_LLM_ADAPTER_REPLAY_COMPLETED
CONTEXT_VISIBILITY_FAILURES_ZERO
FINANCIAL_GENERALIZATION_PRESERVED

METADATA_CONTEXT_GENERALIZATION_PARTIAL
EXACT_CONTEXT_BINDING_GAP_LOCALIZED
LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED
LLM_SEMANTIC_TUNING_NOT_AUTHORIZED
```

Position-based visibility исправлена полностью, но весь adapter ещё нельзя
признать надёжным: два из четырёх replay outputs отклонены неизменённым
validator. Повторный model call, output repair и semantic tuning не выполнялись.

## Изменение owner

Изменён только существующий `build_metadata_context_package`:

- `TEXT_HEAD first 24` заменён полным Canonical `TEXT` node;
- small table переносится целиком;
- все structural candidates включаются без position/target/char truncation;
- large Canonical tables по-прежнему исключаются pre-existing structural
  threshold `64` nonempty cells;
- context policy identity повышена с `v1` до `v2`.

Новые selector framework, semantic classifier, broker wording, regex vocabulary,
page rules и oracle-fed selection не добавлены.

## Phase 1 — без provider

До replay получено:

| Case | Oracle facts | Visible | Invisible | Targets | Context chars | Large tables excluded |
|---|---:|---:|---:|---:|---:|---:|
| `pdf_002` | 9 | 9 | 0 | 18 | 79,361 | 0 |
| `pdf_024` | 6 | 6 | 0 | 6 | 28,993 | 0 |
| `holdout_a` | 3 | 3 | 0 | 22 | 5,480 | 3 |
| `holdout_b` | 6 | 6 | 0 | 6 | 1,070 | 47 |
| **Total** | **24** | **24** | **0** | **52** | **114,904** | **50** |

Selector строился до чтения oracle и не имеет oracle parameter. G5.62 oracle
был воспроизведён отдельно с exact equality `true`.

Опубликованный input limit неизменённой `gemini-3.5-flash` — `1,048,576`
tokens; максимальный фактический input frozen case составил `63,101` tokens.
Спецификация проверена 2026-08-15 по официальной странице Google:
https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash

## Phase 2 — единственный clean replay

Execution accounting:

- provider calls: `4`, ровно `1` на документ;
- retry / best-of-N / manual repair: `0 / false / false`;
- rendered context: `114,904 chars`;
- final model input: `138,628 chars`, `85,698 input tokens`;
- output: `2,459 tokens`;
- provider-reported total: `99,983 tokens`;
- duration: `60,406 ms`;
- source stores changed: `false`.

По сравнению с G5.61 input tokens выросли с `23,080` до `85,698`; calls остались
`4`. Цена за полную visibility измерена, но не оптимизировалась.

| Case | Raw / unique | Correct | Missed | Extras | Duplicates | Ambiguous | Validator |
|---|---:|---:|---:|---:|---:|---:|---|
| `pdf_002` | 24 / 10 | 9 | 0 | 1 | 14 | 0 | rejected: duplicate |
| `pdf_024` | 6 / 6 | 5 | 1 | 1 | 0 | 0 | validated |
| `holdout_a` | 4 / 4 | 3 | 0 | 1 | 0 | 0 | validated |
| `holdout_b` | 6 / 6 | 5 | 1 | 1 | 0 | 2 | rejected: ambiguous literal |
| **Total** | **40 / 26** | **22** | **2** | **4** | **14** | **2** | **2 / 4 accepted** |

Invented literals, physically invalid provenance и unsupported fields: `0`.

## Визуальная квалификация residuals

- `pdf_002`: repeated document header на pages 1/9/15 породил 14 duplicate
  assertions; формулировка вида документа гражданина ошибочно повышена до
  citizenship три раза. Все девять реальных oracle facts при этом найдены.
- `pdf_024`: полный agreement виден, но модель скопировала только неполную часть
  contract identifier; один правильный contract fact пропущен.
- `holdout_a`: прежний client code снова ошибочно повышен до account identifier.
- `holdout_b`: document title загрязнён соседним issuer text; whole-table target
  сделал повторённое имя владельца и частичный account literal неоднозначными
  для неизменённого validator.

Это не visibility misses: правильные 24 assertions присутствовали в context.
Последний пункт является локализованным context packaging/binding gap, поэтому
G5.63 закрывается `PARTIAL`, а не semantic-only success.

## Financial regression

Factory-routed replay на private копиях stores:

- `holdout_a`: `39`, exact frozen JSON equality `true`;
- `holdout_b`: `129`, exact frozen JSON equality `true`;
- оба case status complete;
- provider calls: `0`.

## Freeze и verification

- instruction, proposal schema, validator, request composition и adapter factory:
  protected AST hashes exact;
- G5.60 extractor, Gate 2 model client/request/provider adapter и исходный G5.61
  live harness: full-file hashes exact;
- G5.62 private oracle recheck: exact `true`;
- focused G5.63 tests: `22 passed`;
- финальная Canonical/metadata/Gate 4/architecture/KT1 suite: `155 passed`,
  `0 failed`;
- private values, PDFs, screenshots, raw outputs and hashes committed: `false`.

## KISS и STOP

Сохранён один context owner и штатный factory-routed replay. Не появились
MetadataContextEngine, semantic router, hints, synonyms, retries или voting.

Второй replay запрещён текущим clean-experiment contract. Следующий шаг может
быть только отдельно авторизованным узким refinement structural row binding;
semantic tuning и G5.64 автоматически не запущены.

## Источник

- Google AI for Developers, Gemini 3.5 Flash model specification, проверено
  2026-08-15: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
