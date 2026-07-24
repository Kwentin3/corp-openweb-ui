# Broker Reports — Gate 2: инвентаризация понятий фактического корпуса

Дата: 2026-07-23  
Статус: `GOAL_1_CORPUS_CONCEPT_INVENTORY: COMPLETED`

## Граница и приватность

Исследован только авторизованный private corpus. В Git не перенесены имена файлов, названия организаций, исходные labels, суммы, валютные значения и provider output.

Безопасная база исследования:

- 6 документов;
- 9 bounded table crops;
- 36 provider executions в visual-table quality run;
- receipt hash: `f8862b9a2104a8b4f08b24b6ebe06fc784ce78bb27524e2dd67e8cce92eff1f5`;
- layout mix: 5 borderless, 4 simple-grid/complex, 8 sparse, 6 с итогами; признаки могут пересекаться;
- автоматическая публикация таблиц не была разрешена: все результаты оставались review-required.

`Evidence count` ниже означает число отдельных crop/table units, в которых концепт виден. Это не число строк, не число денежных значений и не статистическая частота по генеральной совокупности.

## Главный вывод по составу корпуса

Корпус не является набором клиентских trade feeds. Основной материал — брокерско-дилерская финансовая отчётность и вспомогательные schedules: состояния активов, обязательств и капитала, напечатанные итоги, lease schedules и credit-loss allowance.

Поэтому текущая семёрка широких transaction-oriented типов не покрывает реальные понятия корпуса. Расширять её source labels нельзя: сначала нужен слой канонических state/aggregate facts.

## Инвентарь концептов

| Канонический кандидат | Evidence count | Категория | Минимальные значения | Суммирование/пересчёт | Неоднозначность |
|---|---:|---|---|---|---|
| statement line-item balance snapshot | 3 | state | amount, unit/currency, as-of date/period, line-item concept | нельзя суммировать без statement scope и elimination rules; пересчитывать нельзя | одна строка может быть активом, обязательством, капиталом или subtotal |
| cash balance snapshot | 3 | state | amount, currency/unit, as-of date, entity/account scope | суммирование только в общей валюте и одном scope | cash, equivalents и restricted cash могут быть объединены |
| regulated/segregated asset snapshot | 2 | state | amount, currency/unit, as-of date, regulatory scope | только в одном regulatory basis | нельзя считать обычным свободным cash |
| security inventory/financing balance snapshot | 1 | state | amount и/или quantity, unit, as-of date, instrument/category | aggregation зависит от valuation basis | не равно клиентской позиции; может быть financing balance |
| receivable balance snapshot | 3 | state | amount, unit/currency, as-of date, counterparty/category scope | допустимо в однородной основе и до netting | gross/net и allowance могут менять смысл |
| payable/liability balance snapshot | 3 | state | amount, unit/currency, as-of date, liability category | допустимо только при совместимой классификации | payable, accrued expense и borrowing не взаимозаменяемы |
| members’ equity/capital snapshot | 3 | state | amount, unit/currency, as-of date, equity component | нельзя слепо складывать с liabilities или P/L | capital, retained result и total equity различаются |
| printed total metric | 3 | aggregate | amount, unit/currency, period/scope, source evidence ref | хранится как напечатанный итог; calculated total — отдельная сущность | один итог может дублировать сумму строк или иметь скрытые adjustments |
| credit-loss allowance snapshot | 1 | state | amount, unit/currency, as-of date, exposure class | нельзя складывать с gross receivable как одинаковый ресурс | contra-asset/sign semantics требуют определения |
| credit-loss allowance movement | 1 | event/aggregate schedule | opening, movement components, closing, period, unit | reconciliation допускается только кодом после определения ролей | movement row может быть event, adjustment или printed subtotal |
| lease right-of-use asset snapshot | 2 | state | amount, unit/currency, as-of date, lease class | только однородные lease classes | gross carrying amount и net balance различаются |
| lease liability snapshot | 4 crops / 2 contexts | state | amount, unit/currency, as-of date, maturity/class | current/non-current могут складываться только в одном reporting basis | один context может повторяться в нескольких crops |
| lease cash-flow schedule item | 2 | event/aggregate schedule | amount, period bucket/date, unit/currency, payment role | допустимо по непересекающимся buckets | contractual payment, interest и principal нельзя смешивать |
| regulatory standards qualitative row | 1 | attribute/no-fact | label/evidence ref, applicability state | не суммируется | может не содержать финансового факта вообще |

## Event, state, aggregate и attribute

- `state`: cash, receivable, payable, equity, inventory, lease asset/liability и allowance balance на дату.
- `event`: отдельное изменение allowance либо schedule payment, только если source semantics действительно указывает движение.
- `aggregate`: напечатанный total и периодические schedule totals. Они не должны притворяться первичными событиями.
- `attribute`: qualitative regulatory applicability и описательные характеристики.

Классификация важна для знака, дедупликации и aggregation rules. Одно числовое значение не доказывает, что перед нами событие.

## Source labels и canonical concepts

Source label остаётся evidence:

```text
source label + value refs + table context
                    ↓
registry candidate matching
                    ↓
immutable canonical fact type
```

Разные labels могут выражать один `cash_balance_snapshot_v1`. Один label может потребовать несколько фактов: например, строка с gross balance, allowance и net balance. Ни label, ни название таблицы не становятся `fact_type_id`.

## Контрпримеры, запрещающие поспешное объединение

- security statement balance не обязательно является `position_snapshot` клиента;
- printed total не является вычисленным aggregate, даже если значения совпали;
- restricted/segregated cash не тождественен доступному cash;
- allowance не является расходом периода без movement context;
- lease liability balance не является cash movement;
- qualitative regulatory row не становится фактом только из-за наличия числа или года;
- одна и та же сумма в summary и detail не означает два независимых экономических факта.

## Что показал текущий Gate 2

Безопасная инспекция последнего persisted run:

- 39 packages accepted, 0 rejected;
- 63 canonical facts;
- 57 `unknown_source_row`;
- 6 `document_summary_evidence`;
- accepted router domains: summary 10, fee 7, income 2, position 13, unknown 7;
- segmentation: 15 parent units и 197 derived units.

То есть routing hypotheses не превратились в типизированные финансовые факты. Формальная accepted-статистика скрывает доменный gap: 90,5% фактов остались `unknown_source_row`, а остальные относятся к summary evidence.

Отдельный semantic-selection контроль дал 21 accepted и 20 rejected packages, 42 uncovered refs. Это не новый corpus count, а подтверждение конфликта decision semantics.

## Потребности downstream

Gate 3 сможет безопасно потреблять только:

- immutable fact type и version;
- source lineage;
- date/period и unit/currency basis;
- sign semantics;
- identity/deduplication material;
- явное различие state/event/aggregate;
- projection metadata, не подменяющее налоговую методологию.

Налоговые квалификации, declaration mapping, cost basis, P/L и calculated tax не выводятся из этого корпуса и остаются запрещёнными до отдельной методологии Gate 3.

## Сохранение нераспознанного смысла

Если финансовое содержание видно, но registry type не доказан, правильный результат — `unclassified_fact` с evidence bindings. Он:

- сохраняет source refs и values;
- не публикует canonical fact;
- создаёт измеримый registry-gap;
- не смешивается с `no_fact` или `unsupported`.

Это прямо устраняет потерю значений, наблюдавшуюся при нынешнем `unknown_source_row`.

## Ограничения исследования

| Gap | Чего не хватает | Владелец | До закрытия запрещено |
|---|---|---|---|
| transaction concepts | авторизованный репрезентативный trade/income/fee corpus | Gate 2 domain research | продвигать широкие legacy transaction IDs в active registry |
| sign conventions | отчётная методология по каждому statement family | Gate 2 registry owner | автоматическая netting/aggregation |
| Gate 3 tax relevance | принятая налоговая методология | Gate 3 | declaration/tax classification |
| register requirements | подтверждённые потребители и posting rules | Gate 3/product methodology | проектировать universal ledger |
| corpus representativeness | больше broker/report families | Gate 2 qualification | объявлять каталог универсальным |

## Acceptance

`CORPUS_CONCEPTS: INVENTORIED`  
`SOURCE_LABELS_VS_CANONICAL_CONCEPTS: SEPARATED`  
`EVENT_STATE_AGGREGATE_ATTRIBUTE: CLASSIFIED`  
`AMBIGUOUS_CONCEPTS: EXPLICIT`  
`UNCLASSIFIED_FINANCIAL_MEANING: PRESERVED`

