# Broker Reports — Gate 2: аудит register/accounting model

Дата: 2026-07-23  
Статус: `GOAL_6_REGISTER_MODEL_AUDIT: COMPLETED`

## Однозначный вывод

В текущем Gate 2 полноценного финансового регистра нет. Есть source-local facts, transport packages, coverage/ownership artifacts, answer projections и Gate 3 manifest. Называть их «регистром» нельзя.

Целевое решение для Gate 2 — вариант B: небольшой registry-driven projection layer поверх canonical facts. Он не является double-entry ledger и не рассчитывает налоговые показатели. Вариант C допустим только после отдельного принятого требования Gate 3.

## Классификация существующих output

| Output | Фактический класс | Почему не register |
|---|---|---|
| `broker_reports_source_facts_v0` | canonical source-local facts | нет posting model, dimensions contract и correction semantics |
| domain source-fact wrapper | transport package | группирует facts по extractor/domain |
| source-fact validation | validation artifact | содержит verdict/errors/counts |
| source-fact stitching | ownership/coverage artifact | выбирает owner и фиксирует unknown/uncovered refs |
| domain run | orchestration artifact | описывает execution и package outcomes |
| answer context | compact projection | сокращает поля для ответа, не ведёт учёт |
| Gate 3 context manifest | artifact graph/manifest | считает типы и ссылки, не проводки |
| `gate3_ledger_candidate` | downstream hint | boolean metadata без ledger contract |
| FNS 2-NDFL typed facts | specialized deterministic facts | отдельные source families, нет общего register model |
| printed summary fact | source evidence/aggregate | не calculated register total |

## Проверка register-признаков

| Признак | Текущее состояние | Gap |
|---|---|---|
| ключи измерений | частичные source/account/instrument refs | нет единого dimension contract |
| ресурсы | amount, currency, quantity встречаются в facts | нет resource semantics по projection |
| периодичность | date/period source-local | нет register period close/reopen |
| валюта | значение и currency могут храниться | нет conversion/functional currency policy |
| account dimensions | optional refs | нет canonical account dimension |
| instrument dimensions | optional identifier/ref | нет instrument identity/valuation basis |
| movement contract | subtype hints | нет debit/credit или другого posting contract |
| correction/reversal | отсутствует | нельзя корректно исправлять проводки |
| idempotency | deterministic fact IDs | есть для facts, не для register posting |
| deduplication | source-fact identity material | нет междокументной reconciliation policy |
| aggregation | hints и downstream flags | нет нормативных group-by/compatibility rules |
| lineage | сильная source provenance | это готовая основа |
| replay | artifact revisions и deterministic validation | нет replay register projection по rule version |

Сильные стороны текущего контура — lineage, immutable artifacts, deterministic IDs и fail-closed validation. Их достаточно для построения проекций, но недостаточно, чтобы объявить ledger существующим.

## Варианты

### A. Только fact model

Подходит для хранения accepted source-local assertions. Не хватает явного ответа, как одинаковые facts показывать в balance, movement, schedule и printed metric views.

Решение: не выбирать как конечную модель. Она остаётся основой.

### B. Registry-driven projection layer

Рекомендуется.

Минимальные profiles:

- `statement_line_item_view_v1`;
- `balance_snapshot_view_v1`;
- `movement_schedule_view_v1`;
- `printed_metric_view_v1`.

Projection entry содержит:

- `projection_entry_id`;
- `projection_profile_id/version`;
- `fact_id`;
- разрешённые dimension refs;
- resource/value refs;
- period/as-of basis;
- source lineage;
- projection rule hash.

Она не копирует customer values без необходимости и не меняет `fact_type_id`. Один accepted fact может иметь несколько проекций только по явным mappings.

### C. Полноценный accounting ledger

Не рекомендуется в Gate 2 сейчас.

Для него отсутствуют:

- chart/account semantics;
- debit/credit or alternative movement model;
- balancing rules;
- correction/reversal policy;
- posting periods;
- multi-currency method;
- valuation/cost basis;
- Gate 3 tax and declaration requirements.

Проектирование этих частей сейчас было бы speculative abstraction.

## Printed и calculated

Projection layer обязан различать:

- source-printed balance/total;
- calculated projection aggregate;
- reconciliation comparison.

Calculated artifact содержит ordered input fact IDs и rule version. Printed metric содержит source evidence. Их совпадение — проверка, но не identity merge.

## Correction, deduplication и replay

До ledger:

- canonical source fact immutable;
- ошибочная классификация исправляется новым run/fact и supersession metadata, не перезаписью;
- duplicate evidence объединяется только в separate reconciliation layer;
- projection replay использует pinned registry/projection versions;
- cross-document economic deduplication остаётся будущей задачей, а source-level duplicate identity не выдаётся за неё.

## Gate boundary

Gate 2 может:

- сохранить source-local fact;
- показать его в bounded accounting-like view;
- построить простой deterministic aggregate, разрешённый registry;
- передать lineage и methodology blockers.

Gate 2 не может:

- квалифицировать налоговый режим;
- рассчитывать cost basis, P/L, tax base или declaration fields;
- создавать double-entry postings без принятой методологии;
- сводить независимые документы в окончательный ledger.

## Риски

| Риск | Уровень | Контроль |
|---|---|---|
| projection начинают считать ledger | high | явные названия `*_view`, запрет posting vocabulary без ADR |
| один fact проецируется несовместимо | medium | registry mapping и deterministic tests |
| printed total смешивается с calculated | high | разные artifact/type identities |
| Gate 3 semantics просачивается в Gate 2 | critical | forbidden fields и separate mapping |
| проекции становятся вторым source of truth | high | обязательный `fact_id` и rule hash |

## Acceptance

`CURRENT_REGISTER_REALITY: NO_FINANCIAL_REGISTER_PRESENT`  
`FACT_VS_REGISTER: SEPARATED`  
`ACCOUNTING_GAPS: EXPLICIT`  
`TARGET_OPTION: B_BOUNDED_REGISTRY_DRIVEN_PROJECTION`  
`NO_UNJUSTIFIED_LEDGER_DESIGN: PASSED`

