# Broker Reports G5.43 — аудит Evidence ↔ Tax Methodology Contract

Дата проверки: `2026-08-14`

Статус: `PARTIAL TERMINAL ACCEPTED`

```text
EVIDENCE_REQUIREMENTS_CONTRACT_PROVEN
FACT_TO_METHODOLOGY_BRIDGE_PROVEN
DECLARATION_INPUT_CORE_PROVEN
LEGAL_METHODOLOGY_GAPS = [
  ambiguous_security_disposal_source_classification,
  partial_acquisition_commission_allocation,
  non_rub_intermediate_precision_and_rounding,
  treaty_specific_foreign_tax_credit_limit
]
```

`TAX_METHODOLOGY_CONTRACT_PROVEN` и
`DECLARATION_INPUT_CONTRACT_AUDIT_CLOSED` не заявлены: четыре внешних
юридико-методологических вопроса оставлены fail-closed.

## Итог

Обе стороны детерминированного ядра теперь имеют явный контракт. Реальные
документы преобразуются в независимые source-bound facts; официальный текст —
в SHA-pinned, versioned methodology; runtime исполняет только типизированные
операции и не интерпретирует документы или НК РФ.

Аудит исправил четыре подтверждённых дефекта:

1. В текущей settlement-методике для базы по ценным бумагам была ошибочно
   выбрана пятиступенчатая шкала. Опубликована новая append-only версия
   `2026.4-audited`: 13% до 2,4 млн руб., затем 312 000 руб. + 15% превышения.
   Старая `2026.3-experimental` сохранена только для исторического replay.
2. Явно подписанный ИНН из шапки одного документа терялся. Добавлен нейтральный
   source fact `REPORTED_ENTITY_TAX_IDENTIFIER`; роль налогоплательщика ему не
   приписывается.
3. Сохранённые dividend/coupon observations и отсутствие source-jurisdiction
   ошибочно диагностировались как недостаток source evidence. Теперь они
   завершаются как `METHODOLOGY_UNRESOLVED` там, где отсутствует правило или
   fact contract.
4. Девять активных declaration demands не имели единого исполнимого входного
   контракта. Опубликована и подключена методика
   `ru-3ndfl-2025-declaration-input-contract@2026.0-audited`; runtime проверяет
   её hash и точное покрытие всех активных demands.

## Объём доказательства

Frozen real corpus: 4 документа, 2 906 canonical targets, 186 Gate 3 financial
annotations, 186 Gate 4 financial source facts и 15 metadata source facts.
Потерянных нужных source-present facts — 0; выдуманных facts — 0; выдуманных
relations — 0; provenance полный. Для G5.43 не выполнялись provider calls или
reruns.

Финансовые наблюдения: 28 покупок, 20 продаж, 27 дивидендов, 11 купонов,
6 компонентов НКД, 18 detail-комиссий, 7 итогов комиссий, 29 transaction
charges, 37 удержаний налога и 3 итога удержаний. Detail и aggregate assertions
сохранены раздельно; reconciliation и разнесение итогов не выполнялись.

## 1. Evidence Map

| Что присутствует в source | Normalized fact | Consumer | Результат |
| --- | --- | --- | --- |
| имя стороны/клиента | `PARTY_NAME` | human gap closure | сохранено без taxpayer-role inference |
| явно подписанный ИНН сущности | `REPORTED_ENTITY_TAX_IDENTIFIER` | human gap closure | сохранено; роль требует подтверждения |
| юридическое имя брокера | `BROKER_LEGAL_NAME` | evidence intake | сохранено |
| номер счёта/договора | `ACCOUNT_IDENTIFIER`, `ACCOUNT_CONTRACT_IDENTIFIER` | evidence intake | 4 факта |
| период отчёта | `STATEMENT_PERIOD` | evidence intake | 8 фактов |
| покупка бумаги | `SECURITY_PURCHASE` | deterministic securities consumer | 28 фактов |
| продажа бумаги | `SECURITY_DISPOSAL` | deterministic securities consumer | 20 фактов |
| прямая transaction charge | `TRANSACTION_CHARGE` | deterministic securities consumer | 29 фактов |
| detail-комиссия | `COMMISSION` | deterministic consumer, evidence review | 18 фактов |
| итог комиссии | `COMMISSION_TOTAL` | deterministic consumer, evidence review | 7 независимых фактов |
| detail удержанного налога | `TAX_WITHHELD` | deterministic consumer, evidence review | 37 фактов |
| итог удержанного налога | `TAX_WITHHELD_TOTAL` | deterministic consumer, evidence review | 3 независимых факта |
| дивиденд | `DIVIDEND_INCOME` | evidence review, case assembly | 27 фактов |
| купон | `COUPON_INCOME` | evidence review, case assembly | 11 фактов |
| компонент НКД | `ACCRUED_COUPON_COMPONENT` | evidence intake | 6 фактов |

Существующие owners переиспользованы: metadata производит
`Gate3MetadataSourceFactRuntimeFactory.create`, финансовые observations —
`Gate4FinancialCaseRuntimeFactory.create`, а Gate 5 получает их через
публичные evidence/fact queries. Ни один source adapter не назначает
residency, income source, allowability или tax-agent meaning.

## 2. Methodology Map

| Declaration demand | Правило и входы | Official authority | Owner / output | Статус |
| --- | --- | --- | --- | --- |
| filing instance | filing id, correction, period, destination authority | приказ ФНС ЕД-7-11/913@ | Filing & Party Identity / filing component | `USER/CASE` отсутствует |
| taxpayer identity and period status | authenticated identity, presence days, Art. 207 exceptions | приказ ФНС; НК РФ ст. 207(2) | Filing & Party Identity / taxpayer-period status | `USER/CASE` отсутствует |
| signer and representation | signer, capacity, authority evidence | приказ ФНС | Filing & Party Identity / signer component | `USER/CASE` отсутствует |
| budget disposition | complete settlement, authenticated intent, budget destination | приказ ФНС | Declaration Budget Outcome / disposition component | `USER/CASE` отсутствует |
| Russian-source income | income kind, payer jurisdiction or realization location, tax-agent facts | НК РФ ст. 208(1), (3), (4) | Declaration Income Sources / Russian source entry | bridge/source inputs отсутствуют |
| foreign-source income and tax | jurisdiction, tax document, translation, treaty | НК РФ ст. 208, 214(2), 232(1)–(3) | Declaration Income Sources / foreign source and credit candidate | legal и input gaps |
| securities/derivatives result | purchase/disposal atoms, direct expense, market/IIS/residence/FX | НК РФ ст. 214.1(1), (3), (4), (7), (10), (12), (13) | Financial Investment Results / category model | bounded source/legal gaps |
| income-group base | complete category models, other income/reductions, residence, RUB amounts | НК РФ ст. 210, 214, 214.1; приказ ФНС | Income Group Tax Base / group base | upstream blocked |
| income-group settlement | complete group base, withheld/credit facts | НК РФ ст. 210(6), 224(1.1); приказ ФНС | Declaration Tax Settlement / group result | audited; upstream blocked |

Каждое правило содержит applicability, typed inputs, operation, authority,
version, output и fail-closed behavior. Все девять строк связаны с одним
immutable input contract через
`Gate5TrustedMethodologyAuthorityFactory.create`.

## 3. Bridge Matrix

| Methodology input | Normalized fact | Deterministic selection | Status |
| --- | --- | --- | --- |
| acquisition order/cost | `SECURITY_PURCHASE(date, asset, quantity, amount, currency)` | `FILTER` asset/date, `ORDER` by date, `FIFO` consume | `PARTIAL_SOURCE` |
| disposal proceeds/quantity | `SECURITY_DISPOSAL(date, asset, quantity, amount, currency)` | `FILTER` complete, process stable fact-id order | `PARTIAL_SOURCE` |
| direct disposal expense | `TRANSACTION_CHARGE(amount, currency)` | exact canonical table-row binding only | `PROVEN` |
| commission assertions | `COMMISSION`, `COMMISSION_TOTAL` | select independently; never reconcile/split total | `METHODOLOGY` |
| coupon income | complete `COUPON_INCOME` | filter; classify by Article 214.1 after market/FX inputs | `CONTRACT` |
| dividend group | complete `DIVIDEND_INCOME` plus payer/source | filter, classify payer jurisdiction, group separately | `CONTRACT` |
| domestic/foreign source | observation plus payer jurisdiction or realization location | apply exact Article 208 input; otherwise fail closed | `CONTRACT` |
| taxpayer residence | presence days plus exception evidence | compare with 183 only after exception review | `USER/CASE` |
| organized-market status | security/date plus admission and quotation reference facts | apply Article 214.1 criteria on disposal date | `CONTRACT` |
| IIS/exemption/loss | authenticated account regime and exact claim facts | exact scoped selection; no default | `USER/CASE` |
| RUB conversion | amount/currency/date plus exact CBR rate and nominal | exact lookup and Decimal multiply/divide | `METHODOLOGY` |
| foreign tax credit | income/tax documents, dates, authority, translation, treaty | verify evidence and treaty, apply reviewed rule | `METHODOLOGY` |
| withheld tax | `TAX_WITHHELD`, `TAX_WITHHELD_TOTAL` | require explicit group/tax-agent binding; no proximity/equality | `CONTRACT` |
| filing/signer/budget facts | typed authenticated user/case facts | exact key/scope selection and enum/authority validation | `USER/CASE` |
| 2025 securities group rate | complete resident non-IIS securities/derivatives RUB base | compare with 2.4m; apply 13% / 312k + 15% excess | `PROVEN` |

Операции deterministic core ограничены обычными `SELECT`, `FILTER`, `ORDER`,
`GROUP`, `FIFO`, `SUM`, `COMPARE`, `APPLY RULE` и `FAIL CLOSED`. После
normalization нет LLM tax reasoning и silent fallback.

## 4. Gap Register

| Класс | Gap | Конкретное следующее действие |
| --- | --- | --- |
| `SOURCE` | `acquisition_quantity_insufficient` (4) | получить выписки с недостающими предыдущими покупками точных инструментов |
| `SOURCE` | `required_financial_roles_missing` (13) | получить официальный export с отсутствующим date/asset/quantity/amount/currency |
| `SOURCE` | `invalid_source_date_or_decimal` (2) | получить исправленный source; не чинить значение после normalization |
| `SOURCE` | `payer_jurisdiction_and_foreign_tax_documents_absent` | получить payer/issuer jurisdiction, realization location и foreign-tax documents |
| `INTAKE` | `explicit_entity_inn_was_not_normalized` | закрыто в G5.43; хранить нейтральный ИНН, роль подтверждает пользователь |
| `CONTRACT` | `issuer_payer_and_realization_location_fact_contracts_missing` | добавить узкие source-fact types только для явно утверждённых данных и доказать на untouched corpus |
| `CONTRACT` | `organized_market_iis_and_cbr_reference_fact_contracts_missing` | опубликовать typed external/user facts для market, account regime и CBR lookup |
| `CONTRACT` | `withholding_to_income_group_binding_missing` | требовать явный source assertion или reviewed methodology key; не связывать по proximity/value/document |
| `METHODOLOGY` | `partial_acquisition_commission_allocation` | получить authority review; до этого не выдавать allocated expense |
| `METHODOLOGY` | `non_rub_intermediate_precision_and_rounding` | проверить precision/rounding и опубликовать additive methodology version |
| `METHODOLOGY` | `treaty_specific_foreign_tax_credit_limit` | проверить конкретный treaty/jurisdiction до eligibility/cap behavior |
| `METHODOLOGY` | `ambiguous_security_disposal_source_classification` | получить authoritative ruling/review для неоднозначного Article 208(4) case |
| `USER/CASE` | `filing_identity_signer_and_budget_intent` | собрать typed authenticated filing, signer/authority и intent facts |
| `USER/CASE` | `taxpayer_confirmation_and_residence_inputs` | подтвердить identity и собрать presence-day/exception facts, не вывод residence |

## Replay и фактические терминалы

Полный путь frozen corpus прошёл:

```text
real documents
→ canonical evidence
→ Gate 3 annotations and metadata source facts
→ Gate 4 independent financial facts
+ versioned SHA-pinned methodologies
→ deterministic case assembly
→ declaration preparation
```

В preparation активны все 9 demands и все 9 имеют methodology binding.
Фактический результат: 4 `MISSING_EVIDENCE`, 4 `METHODOLOGY_UNRESOLVED`,
1 `SOURCE_EVIDENCE_INSUFFICIENT`. Два уже известных metadata facts повторно
использованы; лишних вопросов пользователю — 0; неизвестных причин отсутствия
input — 0. Декларация, XML и PDF не выпускались.

## Verification

- Все 37 `test_broker_reports_gate5_*` modules: `430 passed`.
- Все 15 `test_broker_reports_gate3_*` и `test_broker_reports_gate4_*`
  modules: `150 passed`.
- Финальный bundle/case/preparation/audit slice: `15 passed`; 5 предупреждений
  относятся только к deprecated SWIG types сторонней библиотеки.
- `python -m compileall` для package/scripts/tests: `PASS`.
- `git diff --check`: `PASS`; сообщения о будущем LF → CRLF отражают
  существующую настройку рабочей копии, не whitespace errors.
- Повторная сборка Gate 1 closed-world bundle: байты и SHA-256 идентичны.

## KISS и граница изменения

Новый graph, DB, generic rule engine и параллельные owners не добавлены.
Изменение состоит из двух append-only JSON methodologies, одного нейтрального
metadata fact type, корректной диагностической классификации и фабричной
hash-pinned binding. Existing factories и public queries сохранены.

Локальные private values и трассы не помещались в Git. Frozen store не
изменился. Product activation, advisory/post-filing flow, commit, push и PR не
выполнялись.

Следующая допустимая граница — отдельная авторизация на закрытие четырёх
`LEGAL_METHODOLOGY_GAPS` и на добавление ровно тех source/contract/user facts,
которые потребуются опубликованным правилам. Проекцию или filing включать до
этого нельзя.

## Проверенные официальные источники

- [ФНС: приказ об утверждении формы 3-НДФЛ за 2025 год](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
- [НК РФ, статья 207 — налогоплательщики и резидентство](https://nalog.garant.ru/fns/nk/e4228a58ee428efc683b7a6fe69786e4/)
- [НК РФ, статья 208 — источники доходов](https://nalog.garant.ru/fns/nk/baeafce66c063554f5efd9801f2a9c23/)
- [НК РФ, статья 210 — налоговая база](https://nalog.garant.ru/fns/nk/6a3eaa02cea3fe2db1e9b04e275d1439/)
- [НК РФ, статья 214 — дивиденды и иностранный налог](https://nalog.garant.ru/fns/nk/18504d0125d60b72a85018b2ceb24b1c/)
- [НК РФ, статья 214.1 — операции с ценными бумагами](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/)
- [НК РФ, статья 224 — налоговые ставки](https://nalog.garant.ru/fns/nk/3cc8460732effc45905a5a1a311b451e/)
- [НК РФ, статья 232 — устранение двойного налогообложения](https://nalog.garant.ru/fns/nk/5d22100e7a48445f5abd8c902bfc7cb7/)

Машиночитаемый полный результат: 
`BROKER_REPORTS_GATE5_DECLARATION_INPUT_CONTRACT_AUDIT_G5_43.audit.safe.json`.
