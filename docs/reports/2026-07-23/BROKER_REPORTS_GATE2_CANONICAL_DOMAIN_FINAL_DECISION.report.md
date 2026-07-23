# Broker Reports — Gate 2 Canonical Financial Domain: итоговое решение

Дата: 2026-07-23  
Research program: `COMPLETED_WITH_EXPLICIT_GAPS`

## Однозначный ответ

Gate 2 нужен не новый VLM-проект и не универсальная бухгалтерская онтология. Нужен минимальный управляемый канонический домен из пяти частей:

1. versioned Fact Registry с immutable `fact_type_id`, определениями, ролями, sign/aggregation/deduplication policies и lifecycle;
2. короткий model-facing contract с четырьмя раздельными outcomes: `typed_fact`, `unclassified_fact`, `no_fact`, `unsupported`;
3. deterministic materializer/validator, который сам строит canonical fact, provenance, IDs, restrictions и audit;
4. bounded registry-driven projection layer для statement/balance/movement/printed-metric views;
5. отдельные Gate 3 relevance metadata без налоговых расчётов и declaration semantics.

Модель только выбирает допустимый финансовый смысл и связывает его с source values. Код создаёт проверяемые факты и проекции. Свободного дрейфа типов нет.

## Главная причина проблемы

Текущие девять строковых ID не являются однородным справочником. В одном наборе смешаны:

- финансовые события;
- состояния;
- source evidence;
- router domains;
- extractor identifiers;
- fallback/unknown status.

`unknown_source_row` одновременно означает «fallback», «тип факта» и «не удалось классифицировать». Модель использует его как «значение есть, тип неизвестен», а validator — как «bindings запрещены». Поэтому 41/41 strict schema outputs не предотвратили 20 rejected packages.

Проблема не в JSON как формате. Проблема в неверном доменном контракте.

## Рекомендуемая архитектура

```text
Gate 1 evidence
      ↓
registry-bound model decision
      ↓
deterministic materializer + canonical validator
      ↓
canonical source-local facts
      ↓
bounded projection profiles
      ↓
Gate 3 consumers with separate methodology
```

Registry является единственным источником:

- provider enum/schema;
- model descriptions;
- required/optional/forbidden roles;
- validation/materialization profiles;
- projection mapping;
- compatibility metadata.

OpenAI получает nested `anyOf` под корневым object. Gemini получает bounded provider projection с сохранёнными disposition/fact enums и теми же branches; снятые provider constraints повторно проверяет canonical validator.

## Что делать с current stage

`CURRENT_STAGE_RISK: CRITICAL_UNTIL_CONTAINED`.

Рекомендован отдельный атомарный rollback semantic-selection release к доказанным предыдущим Gate 2 Function identities. После rollback semantic selection должен оставаться выключенным до shadow qualification нового registry-driven contract.

Причина:

- до release: 35/41 accepted, 7 uncovered refs;
- после release: 21/41 accepted, 42 uncovered refs;
- 20 packages отвергнуты после schema-valid model output;
- prompt-only mitigation не устраняет доменный конфликт.

Research branch stage не меняет. Перед операторским rollback обязательна read-only проверка, что live release identity не изменился.

## Начальный registry

Safe draft содержит 12 experimental corpus-driven candidates:

- cash и regulated asset balances;
- receivable, payable и equity balances;
- security inventory balance;
- lease asset/liability states;
- credit-loss allowance state/movement;
- lease schedule item;
- printed financial metric.

`ready` для первого implementation slice:

- `cash_balance_snapshot_v1`;
- `printed_financial_metric_v1`.

Остальные требуют definition/methodology или отложены. Ни один кандидат этим исследованием не активирован.

Legacy `trade_operation`, `income`, `withholding_tax`, `fee_commission`, `cash_movement`, `currency_fx`, `position_snapshot` сохраняются для чтения старых artifacts, но не получают автоматический alias. Для transaction registry нужен отдельный actual corpus.

## Register decision

Текущий Gate 2 не имеет финансового регистра. Рекомендуется bounded projection layer, а не полноценный ledger:

- `statement_line_item_view_v1`;
- `balance_snapshot_view_v1`;
- `movement_schedule_view_v1`;
- `printed_metric_view_v1`.

Double-entry posting, correction periods, cost basis, P/L, tax base и declaration mapping не проектируются без принятой методологии Gate 3.

## Отвергнутые альтернативы

| Альтернатива | Почему отклонена |
|---|---|
| Markdown как runtime contract | удобен человеку, но требует parser и не даёт object contract |
| полный внутренний JSON от модели | возвращает атомарную сложность и хрупкость |
| только упростить prompt | не разделяет semantic levels |
| добавить ещё одно `if` в validator | ловит конфликт после ответа, но не устраняет taxonomy |
| свободные model-generated types | создают необратимый type drift |
| гигантская общая provider schema | ухудшает выбор и упирается в Gemini complexity |
| новый registry service | лишняя операционная граница для code-owned declarations |
| универсальный accounting ledger | не подтверждён корпусом и Gate 3 |
| silent migration старых facts | ломает replay и скрывает неоднозначность |

## Самый узкий безопасный следующий implementation slice

После отдельного operational containment:

1. создать pure `Gate2FactRegistryFactory`;
2. включить только два experimental declarations: cash snapshot и printed metric;
3. реализовать consistency validation и deterministic snapshot hash;
4. не подключать provider, runtime, ArtifactStore или stage;
5. зафиксировать synthetic examples/counterexamples и privacy tests.

Этот slice проверяет главный architectural assumption с минимальным blast radius. Следующий PR отдельно строит decision schema factory.

## Нерешённые методологические вопросы

| Gap | Что требуется | Future owner | До закрытия запрещено |
|---|---|---|---|
| transaction taxonomy | репрезентативный trade/income/fee/cash/FX corpus | Gate 2 domain | active transaction types |
| statement sign/netting | нормативные class и sign rules | Gate 2 domain | cross-class aggregation |
| security identity/valuation | instrument and valuation basis | Gate 2 + product methodology | client position/cost basis claims |
| allowance treatment | accounting/tax methodology | Gate 3 | expense/deduction claims |
| lease treatment | reporting and tax methodology | Gate 2/Gate 3 | cash/tax inference |
| cross-document deduplication | reconciliation identity rules | Gate 3 | consolidated ledger |
| ledger requirements | accepted posting/use cases | Gate 3/product | double-entry design |
| Gemini runtime shape | provider capability smoke under bounded schema | Gate 2 runtime | production enablement |

## Доставленные artifacts

1. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL0_ARCHAEOLOGY.report.md`
2. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL1_ACTUAL_CORPUS_CONCEPT_INVENTORY.report.md`
3. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL2_LAYER_MODEL.report.md`
4. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL3_FACT_REGISTRY_BLUEPRINT.report.md`
5. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL4_DECISION_CONTRACT_BLUEPRINT.report.md`
6. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL5_INITIAL_REGISTRY_CANDIDATES.report.md`
7. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL6_REGISTER_ACCOUNTING_AUDIT.report.md`
8. `BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL7_MIGRATION_ROADMAP.report.md`
9. `BROKER_REPORTS_GATE2_CANONICAL_FACT_REGISTRY_DRAFT.safe.json`
10. этот final decision report.

Все находятся в `docs/reports/2026-07-23/`. Production code, Gate 1, canonical validator, provider policy и stage не изменялись.

## Terminal statuses

`GOAL_0_CURRENT_DOMAIN_ARCHAEOLOGY: COMPLETED`  
`GOAL_1_CORPUS_CONCEPT_INVENTORY: COMPLETED`  
`GOAL_2_DOMAIN_LAYER_MODEL: COMPLETED`  
`GOAL_3_FACT_REGISTRY_BLUEPRINT: COMPLETED`  
`GOAL_4_DECISION_CONTRACT_BLUEPRINT: COMPLETED`  
`GOAL_5_INITIAL_REGISTRY_CANDIDATES: COMPLETED_WITH_GAPS`  
`GOAL_6_REGISTER_MODEL_AUDIT: COMPLETED`  
`GOAL_7_MIGRATION_PLAN: COMPLETED`  
`RESEARCH_PROGRAM_STATUS: COMPLETED_WITH_EXPLICIT_GAPS`

Gaps являются ограничениями на будущие выводы, а не скрытыми runtime TODO этого research PR.

