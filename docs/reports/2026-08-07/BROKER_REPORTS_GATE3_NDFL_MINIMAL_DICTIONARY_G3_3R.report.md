# Broker Reports GOAL G3.3R — минимальный финансовый словарь для НДФЛ

Status: `RESEARCH_ONLY`

Runtime activation: `false`

Production dictionary: `not created`

Date: 2026-08-07

## 1. Terminal status

```text
GOAL_G3_3R = PARTIALLY_COMPLETED

DOWNSTREAM_NEEDS = DEFINED

REAL_CORPUS_COVERAGE = PARTIAL

LABEL_SET = READY_FOR_REVIEW

LABEL_DEFINITIONS = DISTINGUISHABLE

LLM_FRIENDLY_DRAFT = READY

EXTERNAL_INPUT_GAPS = DOCUMENTED

NEXT_STEP_RECOMMENDATION = REVIEW_ONLY
```

Причина `PARTIALLY_COMPLETED`: downstream needs и минимальный review-кандидат
определены, но десять новых определений ещё не проверены бирка-за-биркой на
ранее предоставленном авторизованном customer corpus. Этот корпус не потерян:
safe index учитывает `63` исходных файла, а позднейший Gate 1/2 proof — `104`
source identities и `80` logical documents. Однако его старые широкие Gate 2
типы и package-validation не являются evidence точности новых Gate 3 labels.
Семь публичных PDF, непосредственно просмотренных в этом research, являются
отчётностью о финансовом состоянии broker-dealer организаций, а не
клиентскими transaction statements. Поэтому `REAL_CORPUS_COVERAGE` честно
остаётся `PARTIAL` до отдельного privacy-safe label review старого корпуса.

Ничего не реализовано: нет schema, registry, manifest, publisher, Skill,
Prompt, Tool, API, loader, БД, provider call или product activation.

## 2. Scope и метод

Словарь построен только как пересечение:

```text
исходный факт нужен будущему Gate 4 для НДФЛ
AND
факт реально представлен в брокерских документах
```

Налоговый baseline — действующие для декларации за 2025 год
[форма и порядок 3-НДФЛ](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/),
утверждённые
[приказом ФНС № ЕД-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/).
Локальная официальная копия порядка заполнения проверена по SHA-256
`7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

Терминология проверена по официальным материалам T‑Bank, IBKR, Fidelity,
Saxo и Trading 212. Сырые privacy-safe сопоставления находятся в
[evidence ledger](./BROKER_REPORTS_GATE3_NDFL_LABEL_EVIDENCE_G3_3R.report.md).
Чистый model-facing кандидат находится в
[LLM-friendly draft](../../stage2/research/BROKER_REPORTS_GATE3_NDFL_LABEL_DICTIONARY_G3_3R.draft.md).

## 3. Downstream needs map

Gate 3 помечает только source-stated финансовую реальность. В таблице ниже
«зачем» объясняет допуск бирки, но не переносит налоговый вывод в Gate 3.

| Нужный Gate 4 исходный факт | Зачем он нужен downstream | Что остаётся решением Gate 4 |
| --- | --- | --- |
| Покупка ценной бумаги | Дата, валюта и сумма приобретения нужны для cost basis, валютного пересчёта и последующего matching. | Допустимость расхода, FIFO/иной matching, категория операции. |
| Продажа, погашение или иное возмездное выбытие ценной бумаги | Доход от реализации/погашения и его дата входят в финансовый результат. | Налоговая база, льготы, сальдирование, код операции. |
| Дивиденд | Приложение 2 требует отдельный вид иностранного дохода, дату, источник, валюту и сумму. | Код дохода, ставка, страна источника, зачет налога. |
| Купон | Купон должен быть отделён от дивиденда, общего процента и НКД в сделке. | Налоговая категория и итоговый расчёт. |
| Процентный доход | Иностранные проценты являются отдельным видом дохода; дата и валюта нужны для пересчёта. | Налоговый код/режим и база. |
| Доход от займа ценных бумаг | Порядок 3-НДФЛ выделяет операции займа ценными бумагами; у брокера такой доход может находиться внутри `Interest`. | Расчёт по правилам займа и сальдирование. |
| НКД / accrued interest как компонент сделки | При облигационной покупке/продаже компонент отличается от выплаченного купона и влияет на исходные суммы расходов/доходов. | Его налоговый учет и связь с лотом. |
| Прямая комиссия/сбор конкретной сделки | ФНС требует сумму расходов, связанных с приобретением, реализацией, хранением и погашением. | Признание конкретного расхода и его рублёвый эквивалент. |
| Нетранзакционная комиссия брокера | Broker tax reports отдельно показывают account/margin service charges, которые Gate 4 должен оценить, не теряя исходный факт. | Связь с доходом и допустимость уменьшения базы. |
| Налог, удержанный из дохода | Для иностранного дохода нужны сумма и дата уплаты/удержания налога; это вход в проверку возможного зачёта. | Юрисдикция, подтверждающие документы, применимость договора и сумма зачёта. |

Действующий порядок 3-НДФЛ отдельно требует для иностранного дохода источник,
код валюты, вид дохода, дату и сумму, а для иностранного налога — дату и сумму
уплаты. Эти поля не становятся отдельными финансовыми бирками: это атрибуты
помеченного события либо external inputs.

## 4. Candidate Financial Label Dictionary

### 4.1 `SECURITY_PURCHASE`

**Смысл:** явно указанная покупка/приобретение ценной бумаги для счёта.

**Ставить, если:** источник прямо обозначает исполненную покупку конкретной
ценной бумаги.

**Не ставить, если:** это перевод/зачисление бумаги, остаток позиции, покупка
валюты, РЕПО или только заявка без исполненной сделки.

**Реальные формулировки:** `Покупка`; `Buy`; `Purchase`;
`Trades (Purchase)`.

**Ближайшие контрпримеры:** `Position Transfer In`; `Зачисление` без причины;
`Open Position`; `FX Purchase`.

**Зачем нужен Gate 4:** стоимость и дата приобретения нужны для cost basis и
раздельного валютного пересчёта.

**Статус:** `PROPOSED`.

### 4.2 `SECURITY_DISPOSAL`

**Смысл:** явно указанная продажа, погашение или иное возмездное выбытие ценной
бумаги.

**Ставить, если:** источник прямо обозначает исполненную продажу, redemption
или maturity с proceeds.

**Не ставить, если:** это transfer out, уменьшение позиции без причины,
открытие short, отменённая заявка или corporate action без доказанного
возмездного выбытия.

**Реальные формулировки:** `Продажа`; `Sell`; `Sale`; `Trades (Sales)`;
`Redemption`; `Maturity`.

**Ближайшие контрпримеры:** `Position Transfer Out`; `Withdrawal`;
`Cancelled`; `Delisting`.

**Зачем нужен Gate 4:** proceeds и дата реализации/погашения входят в
финансовый результат.

**Статус:** `PROPOSED`.

### 4.3 `DIVIDEND_INCOME`

**Смысл:** явно указанная выплата или зачисление дивиденда по долевому
инструменту.

**Ставить, если:** источник прямо называет выплаченный/зачисленный dividend.

**Не ставить, если:** это projected/accrued dividend, payment in lieu, списание
дивиденда по short, return of capital или общий section total без отдельного
события.

**Реальные формулировки:** `Ordinary Dividend`; `Cash Dividend`;
`Dividend received`; `Выплата дивидендов`.

**Ближайшие контрпримеры:** `Dividend Accrual`; `Payment in Lieu`;
`Return of capital`; `Stock Dividend`.

**Зачем нужен Gate 4:** дивиденды требуют отдельного income treatment,
источника выплаты и проверки удержанного налога.

**Статус:** `PROPOSED`.

### 4.4 `COUPON_INCOME`

**Смысл:** явно указанная выплата/зачисление купона по облигации.

**Ставить, если:** source прямо обозначает paid/received bond coupon.

**Не ставить, если:** это НКД в цене сделки, общий interest по cash balance,
дивиденд или погашение principal.

**Реальные формулировки:** `Bond Coupon Payment`; `Coupon`; `Купон`;
`Выплата купона`.

**Ближайшие контрпримеры:** `Accrued Interest`; `НКД`; `Interest`;
`Redemption`.

**Зачем нужен Gate 4:** купон отделяется от дивиденда, общего процента и
облигационного выбытия.

**Статус:** `PROPOSED`.

### 4.5 `INTEREST_INCOME`

**Смысл:** явно зачисленный процентный доход, не являющийся купоном или
доходом от займа ценных бумаг.

**Ставить, если:** описание и направление суммы подтверждают именно credited
interest.

**Не ставить, если:** это debit interest/charge, bond coupon, НКД, unpaid
accrual, SYEP/stock-loan income или section header без строки события.

**Реальные формулировки:** `Interest received`; `Interest credit`;
`Muni exempt interest`; `Проценты зачислены`.

**Ближайшие контрпримеры:** `Debit Interest`; `Interest Accrued`;
`Bond Coupon Payment`; `SYEP Interest Received`.

**Зачем нужен Gate 4:** проценты — отдельный вид дохода с собственной датой,
валютой и источником.

**Статус:** `PROPOSED`.

### 4.6 `SECURITIES_LENDING_INCOME`

**Смысл:** явно зачисленный доход/процент за предоставление ценных бумаг в
заём.

**Ставить, если:** source связывает доход с securities lending, stock loan или
программой yield enhancement.

**Не ставить, если:** это обычный interest по cash, купон, payment in lieu of
dividend или плата брокеру за margin loan.

**Реальные формулировки:** `IBKR Managed Securities (SYEP) Interest Received`;
`Securities Lending Income`; `Stock Loan Income`.

**Ближайшие контрпримеры:** `Interest`; `Bond Coupon`; `Payment in Lieu`;
`Margin Interest`.

**Зачем нужен Gate 4:** порядок 3-НДФЛ выделяет операции займа ценными
бумагами отдельно от обычного процентного дохода.

**Статус:** `PROPOSED`.

### 4.7 `ACCRUED_COUPON_COMPONENT`

**Смысл:** явно указанный накопленный, но ещё не выплаченный купонный процент
как компонент облигационной сделки.

**Ставить, если:** НКД/accrued interest явно входит в расчёт покупки или
продажи облигации.

**Не ставить, если:** это выплаченный купон, общий interest accrual баланса,
broker interest или прогноз дохода.

**Реальные формулировки:** `НКД`; `Накопленный купонный доход`;
`Accrued Interest`.

**Ближайшие контрпримеры:** `Bond Coupon Payment`; `Interest Accrued`;
`Projected Income`.

**Зачем нужен Gate 4:** компонент нельзя смешивать с coupon payment или
principal при разборе исходных сумм покупки/продажи.

**Статус:** `PROPOSED`.

### 4.8 `TRANSACTION_CHARGE`

**Смысл:** комиссия, сбор или transaction tax, явно привязанные к конкретной
покупке/продаже ценной бумаги.

**Ставить, если:** связь с исполненной сделкой видна из той же строки/секции и
источник называет commission/fee/tax.

**Не ставить, если:** это tax withheld from income, обслуживание счёта,
custody fee, margin interest, внутренние расходы фонда или неопределённый
service charge.

**Реальные формулировки:** `Комиссия брокера`; `Комиссия биржи`;
`Broker Commission`; `Commission`; `Tax/Fee`; `Stamp Duty`.

**Ближайшие контрпримеры:** `Withholding Tax`; `Account Maintenance Fee`;
`Depositary Fee`; `Interest Charge`.

**Зачем нужен Gate 4:** прямые расходы конкретной сделки должны быть доступны
для последующей проверки их учета.

**Статус:** `PROPOSED`.

### 4.9 `BROKER_SERVICE_CHARGE`

**Смысл:** явно списанная плата брокеру за обслуживание брокерского счёта или
брокерскую услугу, не привязанная к одной сделке.

**Ставить, если:** source явно называет broker/account maintenance, reporting,
plan или иной account-level service fee.

**Не ставить, если:** это комиссия конкретной сделки, custody/depositary fee,
налог, debit interest или неопределённый `Service Charge` без broker-account
контекста.

**Реальные формулировки:** `Комиссия за обслуживание счета`;
`Account Maintenance Fee`; `Reporting Fee`; `Monthly Activity Fee`.

**Ближайшие контрпримеры:** `Commission`; `Depositary Fee`;
`Withholding Tax`; `Debit Interest`.

**Зачем нужен Gate 4:** такие source-stated расходы встречаются отдельно от
trade fees и требуют отдельной downstream-проверки допустимости.

**Статус:** `PROPOSED`.

### 4.10 `TAX_WITHHELD`

**Смысл:** явно указанный налог, фактически удержанный из конкретного дохода.

**Ставить, если:** источник подтверждает withholding/deduction, сумму и связь
с income event либо однозначным income section.

**Не ставить, если:** это transaction tax/stamp duty, рассчитанный, но не
удержанный налог, tax payable, комиссия или общая налоговая справка без
фактического удержания.

**Реальные формулировки:** `Withholding Tax`; `Tax Withheld`;
`Foreign Tax Paid`; `Удержанный налог`; `Удержание налога`.

**Ближайшие контрпримеры:** `Tax/Fee` в trade row; `Stamp Duty`;
`Tax Calculated`; `Tax Payable`.

**Зачем нужен Gate 4:** это исходный факт для проверки иностранного/агентского
налога, но не решение о его зачёте.

**Статус:** `PROPOSED`.

### 4.11 Кандидаты без достаточного evidence

| Candidate | Статус | Почему не включён в LLM draft |
| --- | --- | --- |
| `SECURITIES_CUSTODY_CHARGE` | `INSUFFICIENT_EVIDENCE` | Потребность следует из категории расходов на хранение, но в исследованном transaction evidence нет достаточного multi-broker набора реальных строк custody/depositary charge. |
| `DERIVATIVE_SETTLEMENT` | `INSUFFICIENT_EVIDENCE` | В T‑Bank видны variation margin/options, а в 3-НДФЛ несколько разных PFI-категорий; одна широкая бирка будет слишком грубой, дробление пока не доказано. |
| `REPO_EVENT` | `INSUFFICIENT_EVIDENCE` | Одно и то же `РЕПО` может быть самостоятельной операцией или техническим переносом расчётов; устойчивых условий различения нет. |
| `PAYMENT_IN_LIEU` | `INSUFFICIENT_EVIDENCE` | Брокеры могут включать substitute payments в dividend/interest sections, но российский downstream treatment и достаточные реальные строки не подтверждены. |
| `RETURN_OF_CAPITAL` | `INSUFFICIENT_EVIDENCE` | Реальная формулировка есть в Fidelity sample, но достаточная российская downstream-методика и multi-broker coverage отсутствуют. |
| `CORPORATE_ACTION_PROCEEDS` | `REJECTED` | Слишком широкая бирка: merger, spin-off, tender, redemption и другие события требуют разных downstream-правил. |

## 5. Coverage matrix

| Нужный факт | Встречается | Доказанные формулировки/источники | Label | Evidence |
| --- | --- | --- | --- | --- |
| Покупка ценной бумаги | Да, official broker docs/sample | T‑Bank `Покупка`; IBKR `Trades (Purchase)` | `SECURITY_PURCHASE` | Достаточно для review |
| Продажа/погашение | Да | T‑Bank `Продажа`; IBKR `Trades (Sales)`, `Redemption`; ФНС `реализация (погашение)` | `SECURITY_DISPOSAL` | Достаточно для review |
| Дивиденд | Да | IBKR `Ordinary Dividend`; Fidelity `Dividend received`; T‑Bank `выплата дивидендов` | `DIVIDEND_INCOME` | Достаточно для review |
| Купон | Да | IBKR `Bond Coupon Payment`; T‑Bank `купоны` | `COUPON_INCOME` | Достаточно для review |
| Процентный доход | Да | IBKR `Interest`; Fidelity `Muni exempt interest` | `INTEREST_INCOME` | Достаточно при наличии event context |
| Доход от займа бумаг | Да, узко | IBKR `SYEP Interest Received`; ФНС `операции займа ценными бумагами` | `SECURITIES_LENDING_INCOME` | Достаточно для узкого review |
| НКД в облигационной сделке | Да | T‑Bank `НКД`; IBKR `Accrued Interest` | `ACCRUED_COUPON_COMPONENT` | Достаточно для review |
| Trade fee/tax | Да | T‑Bank `Комиссия брокера/биржи`; IBKR `Commission`, `Tax/Fee`; Saxo `commission` | `TRANSACTION_CHARGE` | Достаточно для review |
| Нетранзакционная broker fee | Да | T‑Bank `комиссия за обслуживание`; IBKR maintenance/reporting fees | `BROKER_SERVICE_CHARGE` | Достаточно, deductibility не заявлена |
| Удержанный налог | Да | IBKR `Withholding Tax`; T‑Bank `удержание налога`; ФНС строки 110/130 Приложения 2 | `TAX_WITHHELD` | Достаточно для review |
| Custody/depositary fee | Потребность есть; строки не доказаны | `Depositary fee`, `Custody fee` только как терминологические сигналы | Нет draft-label | Недостаточно |
| PFI/РЕПО/payment-in-lieu/corporate action | Частично | Несколько опасно широких broker categories | Нет draft-label | Недостаточно |

## 6. Excluded concepts

| Концепт | Почему сознательно не включён |
| --- | --- |
| `TRADE` | Слишком широк: Gate 4 обязан различать acquisition и disposal. |
| `INCOME` | Слишком широк: dividend, coupon, ordinary interest и securities-lending income имеют разные downstream rules. |
| `FEE` | Слишком широк: trade charge, broker service, custody и tax withholding нельзя смешивать. |
| `CASH_MOVEMENT` | Пополнение, вывод и внутренний перевод сами по себе не являются доходом/расходом НДФЛ; используются только для reconciliation. |
| `POSITION` / `HOLDING` | Остаток — состояние счёта, не достаточный налоговый event. |
| `FX_CONVERSION` | Для пересчёта дохода/расхода нужны валюта, дата и официальный курс; broker FX trade не заменяет этот расчёт. Самостоятельное налогообложение FX — отдельный scope. |
| `REALIZED_PNL` / `TAXABLE_PROFIT` | Это broker-calculated или налоговый вывод, а не первичный факт Gate 3. |
| `TAX_DEDUCTIBLE_EXPENSE` | Решение о допустимости расхода принадлежит Gate 4. |
| Балансы, performance, NAV, unrealized P/L | Не нужны текущему declaration-source baseline. |
| Deposits, withdrawals, position transfers | Нужны для сверки, но не для минимального tax-event словаря. |

## 7. Missing external inputs

Эти данные нужны Gate 4, но не должны выдумываться Gate 3 из брокерского
отчёта:

1. налоговый статус/резидентство пользователя и применимый налоговый период;
2. официальные курсы Банка России на даты доходов и расходов;
3. нормативная классификация операции и инструмента, включая обращаемость,
   PFI, ИИС и специальные режимы;
4. правила FIFO/matching, перенос убытков, льготы и пользовательские выборы;
5. acquisition history и подтверждающие документы от другого брокера при
   переводе активов;
6. страна и надлежащий документ об иностранном налоге, а также актуальная
   применимость соглашения об избежании двойного налогообложения;
7. corporate-action notices, issuer data, tax forms и иные документы, если
   activity statement не содержит достаточного контекста;
8. specialist-approved methodology для derivatives, РЕПО, short, securities
   lending, return of capital и payment in lieu.

Механизм получения этих данных в G3.3R не проектируется.

## 8. Conflict report

| Конфликт | Риск | Research-решение |
| --- | --- | --- |
| IBKR `Interest` включает broker/bond interest, debit interest, accruals и SYEP | Одна строка может быть ошибочно помечена как обычный interest | Section header недостаточен; нужны event description и направление суммы. Coupon и SYEP имеют отдельные бирки. При нехватке контекста — omission. |
| T‑Bank `Иные операции` может содержать short-dividend debit | Похожий текст на dividend, но противоположный экономический факт | Не ставить `DIVIDEND_INCOME` без явного зачисления и event context. Отдельная бирка пока не допущена. |
| `Commission`, `Tax/Fee`, `Stamp Duty`, `Withholding Tax` | Transaction tax можно спутать с налогом, удержанным из дохода | `TRANSACTION_CHARGE` требует связь с trade; `TAX_WITHHELD` требует связь с income withholding. |
| Fidelity section `Dividends, Interest & Other Income` содержит `Return of capital` | Section heading создаёт ложный dividend/income label | Label ставится по строке события, не по заголовку секции. `Return of capital` пока omission. |
| Purchase/sale totals и отдельные trade rows | Дублирование одного смысла | Для baseline label ставится на event row; aggregate без самостоятельного event не размечается. |
| Broker `Realized P/L` и `Cost Basis` | Provider может принять broker calculation за налоговую истину | Эти понятия исключены из словаря; Gate 4 пересчитывает по source events и external rules. |
| `Depositary fee` / `Custody fee` / generic `Service Charge` | Сходная лексика, разная связь с допустимыми расходами | Не объединять с `BROKER_SERVICE_CHARGE`; custody label ждёт evidence. Generic service charge без контекста не размечается. |

После этих ограничений один явно выраженный факт не удовлетворяет двум
`PROPOSED` определениям. Неоднозначный или недостаточно контекстный факт не
получает бирку; omission не является отрицательным утверждением.

## 9. Corpus accounting

### 9.1 Corpus, непосредственно использованный для label evidence

- файлов: `7` PDF;
- семейства: Betterment, DriveWealth, IBKR, Moomoo, Wealthfront;
- каждый документ по title/text является `Statement of Financial Condition`
  или эквивалентной broker-dealer financial statement;
- client transaction statements: `0`;
- пригодность для label evidence: только отрицательное доказательство
  несоответствия корпуса задаче.

### 9.2 External official broker evidence

- [T‑Bank: как читать брокерский отчёт](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/);
- [T‑Bank: как читать налоговый отчёт](https://www.tbank.ru/invest/help/educate/broker-report/about/tax-report/);
- [IBKR: sample Activity Statement](https://www.ibkrguides.com/reportingreference/reportguide/daily_concatenated_sample.html);
- [IBKR: Trades fields](https://www.ibkrguides.com/reportingreference/reportguide/et_trades.htm);
- [IBKR: Dividends](https://www.ibkrguides.com/reportingreference/reportguide/et_dividends.htm);
- [IBKR: Withholding Tax](https://www.ibkrguides.com/reportingreference/reportguide/witholdingtax_default.htm);
- [IBKR: Fixed Income Trades](https://www.ibkrguides.com/reportingreference/reportguide/fixedincome_tradeconfirm.htm);
- [Fidelity: sample brokerage statement](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/sample-new-fidelity-acnt-stmt.pdf);
- [Saxo: Cash Movements](https://www.help.saxo/hc/en-us/articles/360041087992-How-do-I-read-the-Cash-Movements-Summary);
- [Trading 212: account activity statement](https://helpcentre.trading212.com/hc/en-us/articles/15757156925469-What-is-an-account-activity-statement).

Это official public samples/documentation, не customer-private evidence.

### 9.3 Ранее предоставленный customer domain: сохранённая ценность и границы

Ранее предоставленный корпус существует отдельно от семи PDF из п. 9.1 и не
должен быть потерян. Его
[privacy-safe intake index](../2026-07-06/OPENWEBUI_BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INTAKE_INDEX.report.md)
и [safe registry](../../stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json)
учитывают `63` файла: `7` source broker reports, `8` operations tables, `7`
dividends reports, `2` fees reports, а также calculation/review материалы.
Представлены как минимум BCS, IBKR, Otkritie, Sber и VTB. Позднейший
[actual-corpus reproof](../2026-07-21/BROKER_REPORTS_GOAL5_INTEGRATED_ACTUAL_CORPUS_REPROOF.report.md)
учитывает `104` source identities, `80` logical documents и `681/681`
валидных Gate 2 packages.

Эта информация ценна для G3.3R как:

1. авторизованный multi-broker validation corpus для проверки найденных
   формулировок, конфликтов и omissions;
2. очередь приоритетных slices: operations, dividends, fees, withholding/FX;
3. доказательство, что проверку нельзя ограничивать публичными sample
   statements;
4. источник regression/counterexample cases после privacy-safe разметки
   человеком.

Но это пока не per-label evidence текущего словаря: safe index намеренно не
публикует строки и значения, а старый Gate 2 использовал более широкие типы
`trade_operation`, `income`, `fee_commission`, `withholding_tax`,
`cash_movement`, `currency_fx`, `position_snapshot`. Они смешивают смыслы,
которые будущий Gate 4 должен различать. Поэтому ими нельзя автоматически
подтвердить ни coverage, ни точность десяти новых labels.

Старые проектные
[NDFL Knowledge Pack](../../stage2/domain/BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.md),
[Skill](../../stage2/skills/BROKER_REPORTS_NDFL_EXTRACTION_SKILL.md) и
[Prompt Pack](../../stage2/prompts/BROKER_REPORTS_JSON_EXTRACTION_PROMPT_PACK.md)
сохраняют полезную методическую часть: source evidence first, отдельные
missing/uncertain/conflict states, запрет превращать source fact в налоговый
вывод и необходимость различать purchase/sale, dividend/coupon, fees и
withholding. Старый managed Financial Domain
[Skill](../../../services/broker-reports-gate1-proof/managed_assets/skills/broker_reports_financial_domain_skill.v1.md)
добавляет полезное правило читать полный bounded context и принимать тип
только при однозначной поддержке.

Критическое ограничение: эти материалы — draft/project assets, а не
нормативный источник labels. Сам Knowledge Pack прямо указывает, что текущие
customer CloudCowork/Claude prompts ещё требовалось получить. Read-only live
inventory на `2026-08-07` также показал `Knowledge = 0`, `Skills = 0` и только
`12` project-managed Broker Reports prompts. Поэтому наличие или авторство
исходных customer Claude Skill/Prompt в доступном контуре не подтверждено и в
отчёте не заявляется.

**Review outcome:** текущие десять labels точнее и компактнее исторических
широких типов. Label set и LLM-friendly draft оставлены без изменений; старые
материалы сохраняются как provenance, validation corpus и методические
guardrails, но не как второй владелец словаря.

## 10. KISS check

```text
JSON schema = NOT_CREATED
registry = NOT_CREATED
manifest = NOT_CREATED
publisher = NOT_CREATED
Skill = NOT_CREATED
Prompt = NOT_CREATED
Tool = NOT_CREATED
Knowledge_Base_or_RAG = NOT_CREATED
API_or_runtime_loader = NOT_CREATED
database = NOT_CREATED
versioning_system = NOT_CREATED
Financial_Domain = NOT_CREATED
provider_calls = 0
runtime_or_contract_changes = 0
```

В model draft входят только `10` PROPOSED labels. Широкие `TRADE`, `INCOME`,
`FEE` и `CASH_MOVEMENT` отклонены; неподтверждённые семьи не замаскированы
общим catch-all label.

## 11. Observations

```text
OBSERVATION = Ранее предоставленный авторизованный customer corpus сохранён, но в G3.3R не выполнен label-by-label review его privacy-safe fragments.
IMPACT_ON_CURRENT_GOAL = Corpus пригоден для следующей проверки, но его старые широкие Gate 2 facts не подтверждают точность новых Gate 3 labels автоматически.
BLOCKING = YES (для статуса SUFFICIENT_FOR_V1), NO (для review текущего baseline)
```

```text
OBSERVATION = Официальные broker samples подтверждают десять коротких взаимно различимых event/charge labels.
IMPACT_ON_CURRENT_GOAL = Candidate dictionary и чистый LLM-friendly draft готовы к review.
BLOCKING = NO
```

```text
OBSERVATION = PFI, РЕПО, payment-in-lieu, return of capital и corporate actions требуют отдельной методики и более сильного evidence.
IMPACT_ON_CURRENT_GOAL = Они исключены из draft вместо расширения словаря догадками.
BLOCKING = YES (для универсального НДФЛ coverage), NO (для review текущего baseline)
```

## 12. Stop

G3.3R завершён на research boundary. Следующий шаг не назначается агентом.
Разрешённая рекомендация: `REVIEW_ONLY`.
