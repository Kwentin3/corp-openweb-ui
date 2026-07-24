# Broker Reports — Gate 2: начальный каталог кандидатов Registry

Дата: 2026-07-23  
Статус: `GOAL_5_INITIAL_REGISTRY_CANDIDATES: COMPLETED_WITH_GAPS`

## Решение

Начальный каталог содержит 12 experimental candidates, подтверждённых фактическим корпусом. Ни один кандидат этим отчётом не переводится в production `active`: это blueprint и safe draft.

Список намеренно не включает универсальный набор сделок, доходов и налогов. Для широких legacy transaction IDs в исследованном корпусе недостаточно evidence.

## Каталог

`Evidence` — число crop units; для lease liability дополнительно указаны два независимых schedule contexts.

| Candidate ID | Evidence | Source family | Категория | Required roles | Projection target | Gate 3 relevance | Readiness |
|---|---:|---|---|---|---|---|---|
| `cash_balance_snapshot_v1` | 3 | statement balance | state | amount, unit/currency, as-of date, scope | `balance_snapshot_view_v1` | cash evidence | `ready` |
| `regulated_asset_balance_snapshot_v1` | 2 | regulated/segregated statement balance | state | amount, unit/currency, as-of date, regulatory scope | `balance_snapshot_view_v1` | restricted liquidity context | `needs_definition` |
| `receivable_balance_snapshot_v1` | 3 | statement balance | state | amount, unit/currency, as-of date, receivable class | `statement_line_item_view_v1` | possible income/cost inputs only after methodology | `needs_definition` |
| `payable_balance_snapshot_v1` | 3 | statement balance | state | amount, unit/currency, as-of date, liability class | `statement_line_item_view_v1` | liability evidence | `needs_definition` |
| `equity_balance_snapshot_v1` | 3 | statement balance | state | amount, unit/currency, as-of date, equity component | `statement_line_item_view_v1` | reconciliation context | `needs_definition` |
| `security_inventory_balance_snapshot_v1` | 1 | dealer inventory/financing statement | state | amount and/or quantity, unit, as-of date, inventory scope | none until valuation basis exists | instrument context | `defer` |
| `lease_right_of_use_asset_snapshot_v1` | 2 | lease schedule | state | amount, unit/currency, as-of date, lease class | `balance_snapshot_view_v1` | usually contextual, not direct tax fact | `needs_definition` |
| `lease_liability_snapshot_v1` | 4 / 2 contexts | lease schedule | state | amount, unit/currency, as-of date, maturity/class | `balance_snapshot_view_v1` | liability context | `needs_definition` |
| `credit_loss_allowance_snapshot_v1` | 1 | credit-loss schedule | state | amount, unit/currency, as-of date, exposure class | `balance_snapshot_view_v1` | methodology required for deductions | `needs_methodology` |
| `credit_loss_allowance_movement_v1` | 1 | credit-loss movement schedule | event | amount, period/date, component kind, unit/currency | `movement_schedule_view_v1` | methodology required | `needs_methodology` |
| `lease_payment_schedule_item_v1` | 2 | lease cash-flow schedule | aggregate/event schedule | amount, period bucket, unit/currency, payment role | `movement_schedule_view_v1` | contextual cash-flow input | `needs_definition` |
| `printed_financial_metric_v1` | 3 | statement/schedule printed total | aggregate | amount, unit/currency, period/scope, label evidence ref | `printed_metric_view_v1` | evidence/reconciliation only | `ready` |

## Safe examples и counterexamples

| Candidate | Допустимый synthetic example | Reject/counterexample |
|---|---|---|
| cash balance | source line states a cash-class balance on reporting date | restricted asset without cash classification |
| regulated asset balance | source explicitly places balance in regulated/segregated scope | ordinary cash line |
| receivable balance | receivable-class carrying balance on date | cash receipt event |
| payable balance | payable/liability balance on date | payment transaction |
| equity balance | named equity component on date | period income total |
| security inventory balance | dealer inventory balance with valuation basis evidence | client security position inferred only from similar label |
| lease ROU asset | lease asset carrying balance | lease payment schedule row |
| lease liability | lease obligation balance with maturity/scope | generic payable without lease evidence |
| loss allowance snapshot | allowance balance on date | gross receivable |
| loss allowance movement | explicitly labelled movement component for a period | closing balance repeated as a total |
| lease schedule item | non-overlapping payment bucket with period | liability snapshot |
| printed metric | explicit source-printed total | total calculated by Gate 2 from child rows |

В current runtime все эти source meanings либо оставались `unknown_source_row`, либо могли попасть в широкие router hypotheses. Поэтому «accepted example» здесь означает подтверждённое source evidence, а не уже принятый typed fact. Production promotion требует новых typed qualification results.

## Ambiguity и запреты

| Candidate | Основная неоднозначность | Что запрещено до закрытия |
|---|---|---|
| cash/regulated asset | availability и restriction basis | объединять в один liquidity balance |
| receivable/payable | gross/net, class, offset | netting между classes |
| equity | component taxonomy | считать P/L или cash |
| security inventory | dealer inventory vs client position | legacy `position_snapshot` auto-mapping |
| lease states | current/non-current, gross/net | суммировать без reporting basis |
| loss allowance | contra-asset и sign | трактовать как deductible expense |
| movement schedules | event vs adjustment vs subtotal | публиковать без component semantics |
| printed metric | duplicate/repeated total | подменять calculated aggregate |

## Remapping текущих ID

### Сохраняются только как legacy identities

- `trade_operation`;
- `income`;
- `withholding_tax`;
- `fee_commission`;
- `cash_movement`;
- `currency_fx`;
- `position_snapshot`.

Они остаются читаемыми в persisted artifacts. Для новых facts они не становятся aliases автоматически: широкое понятие может соответствовать нескольким будущим canonical IDs.

### Не являются financial fact types

- `document_summary_evidence` → `source_evidence_kind=document_summary`;
- `unknown_source_row` → legacy disposition, далее разделяется на `unclassified_fact`, `no_fact` или `unsupported`;
- все `NO_FACT_REASON_VALUES` → reason codes технического disposition;
- router domains и extractor IDs → отдельные технические namespaces.

### Требуют будущего разделения

| Legacy ID | Возможное направление, не утверждённый mapping |
|---|---|
| `trade_operation` | purchase, sale, redemption, transfer, corporate action |
| `income` | dividend, coupon, interest, sale proceeds |
| `fee_commission` | broker commission, exchange fee, custody fee |
| `cash_movement` | deposit, withdrawal, credit, debit |
| `currency_fx` | exchange event, stated rate, converted amount attribute |
| `position_snapshot` | client security position, dealer inventory, cash position |

Ни один вариант не создаётся без actual-corpus evidence и определения identity/sign/aggregation.

## FNS specialized families

FNS 2-NDFL families не добавлены в этот общий каталог. Их deterministic adapter и versioned schema сохраняются. Отдельное исследование должно разделить:

- identity/metadata evidence;
- income/deduction source rows;
- tax summary facts;
- Gate 3 methodology.

Silent alias между FNS family и новым canonical ID запрещён.

## Promotion gates

Кандидат становится `active` только после:

1. нормативного определения;
2. safe corpus evidence минимум из согласованного числа независимых source contexts;
3. positive и counterexample fixtures;
4. required/optional/forbidden role review;
5. sign, aggregation и deduplication decision;
6. provider-schema capability test;
7. deterministic materialization/validation tests;
8. compatibility impact;
9. shadow corpus qualification без потери coverage.

`ready` в таблице означает «достаточно определён для первого implementation slice», а не «готов к production release».

## Gaps

| Gap | Нужное evidence/methodology | Owner | Запрещённый вывод |
|---|---|---|---|
| transaction registry | actual trade/income/fee/cash/FX corpus | Gate 2 | active transaction IDs |
| statement classes | formal balance taxonomy and scope rules | Gate 2 domain owner | automatic class/netting |
| allowance/lease methodology | accounting interpretation review | Gate 2 + future Gate 3 | tax/P&L use |
| Gate 3 relevance | accepted downstream method | Gate 3 | declaration mapping |
| production readiness | typed shadow qualification | Gate 2 runtime | rollout |

## Acceptance

`INITIAL_REGISTRY_SIZE: 12_BOUNDED_EXPERIMENTAL_CANDIDATES`  
`EVERY_TYPE_HAS_EVIDENCE: YES`  
`MIXED_LEVEL_IDENTIFIERS: REMAPPED`  
`UNREADY_TYPES: NOT_PROMOTED`

