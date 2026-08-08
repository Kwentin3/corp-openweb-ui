# Broker Reports G3.3R — privacy-safe label evidence ledger

Status: `RESEARCH_EVIDENCE_ONLY`

Private customer bytes: `not used`

Date: 2026-08-07

## 1. Evidence boundary

Этот ledger сохраняет проверяемые короткие source fragments и их связь с
кандидатами финансовых бирок. Он не является production dictionary, налоговой
методикой или разрешением на runtime.

Источники:

1. действующий официальный порядок 3-НДФЛ за 2025 год;
2. публичные official broker sample statements и reporting guides;
3. агрегатная проверка доступного локального публичного корпуса;
4. без private customer documents, account IDs, names, amounts или paths.

## 2. Downstream raw evidence

Локальный официальный файл:

```text
docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx
sha256 = 7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
source = https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/
```

| Paragraph | Короткий исходный фрагмент | Downstream need |
| --- | --- | --- |
| 7 / extracted paragraph 0026 | `доходы ... и расходы ... в иностранной валюте` → курс на дату получения/осуществления | Дата, валюта и исходная сумма нужны отдельно для income и expense events. |
| 23 / 0065 | `Приложение 8 ... операции с ценными бумагами` | Покупки/выбытия и связанные расходы нужны отдельной цепочке расчёта. |
| 62–63 / 0240–0255 | `отдельно по каждому источнику выплаты дохода и коду вида дохода` | Dividend, coupon/interest и иные income kinds нельзя свести к `INCOME`. |
| 63 / 0249–0255 | `дата получения дохода`, `код валюты`, `сумма дохода` | Для income event необходимы source-visible date/currency/amount. |
| 63 / 0259–0262 | `дата уплаты налога`, `сумма налога` | Удержанный/уплаченный налог — отдельный исходный факт, не tax-credit decision. |
| 101 / 0473–0476 | `код вида операции`, `общая сумма дохода`, `общая сумма расходов` | Gate 4 различает operation class и income/expense sides. |
| 101 / 0475 | `приобретением, реализацией, хранением и погашением` | Purchase, disposal и связанные charges должны сохраняться раздельно. |
| Appendix 8 code list / 0943–0995 | `операции ... ценных бумаг`, `ПФИ`, `РЕПО`, `займа ценными бумагами` | Securities lending/PFI/REPO нельзя автоматически объединять с обычным trade. |
| Appendix 8 code list / 1011 | `облигациями ... в виде процента (купона)` | Coupon требует отдельного смысла от general interest. |

Дополнительный официальный FNS cross-check:

- [ФНС о продаже акций](https://www.nalog.gov.ru/rn11/news/smi/15956801/):
  финансовый результат учитывает расходы, связанные с приобретением,
  реализацией, хранением и погашением;
- [ФНС: формы 3-НДФЛ](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/):
  для декларации за 2025 год действует приказ № ЕД-7-11/913@;
- [ФНС об инвестиционных вычетах](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/inv_vichet/):
  продажа и погашение рассматриваются вместе, а acquisition order важен для
  FIFO downstream.

## 3. Source fragment → proposed label

### 3.1 `SECURITY_PURCHASE`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Вид сделки — покупка` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Явная исполненная purchase event. |
| `Trades (Purchase)` | [IBKR sample Activity Statement](https://www.ibkrguides.com/reportingreference/reportguide/daily_concatenated_sample.html) | Явная purchase-side категория. |
| `Type — Buy or Sell` | [IBKR Fixed Income Trades](https://www.ibkrguides.com/reportingreference/reportguide/fixedincome_tradeconfirm.htm) | `Buy` подтверждает bond purchase. |

Downstream link: порядок ФНС отдельно требует расходы acquisition-side и их
валютный пересчёт на дату расхода.

### 3.2 `SECURITY_DISPOSAL`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Вид сделки — ... продажа` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Явная sale event. |
| `Trades (Sales)` | [IBKR sample Activity Statement](https://www.ibkrguides.com/reportingreference/reportguide/daily_concatenated_sample.html) | Явная sale-side категория. |
| `Redemption`; `Maturity` | [IBKR Corporate Actions](https://www.ibkrguides.com/reportingreference/reportguide/corporateactions_pa.htm) | Реальные варианты paid disposal, требующие proceeds context. |

Downstream link: ФНС использует связку `реализация (погашение)`; отдельные
labels `SALE` и `REDEMPTION` не дают дополнительного результата для baseline.

### 3.3 `DIVIDEND_INCOME`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Ordinary Dividend` | [IBKR Dividends](https://www.ibkrguides.com/reportingreference/reportguide/et_dividends.htm) | Explicit dividend income type. |
| `Cash Dividend` | [IBKR sample Activity Statement](https://www.ibkrguides.com/reportingreference/reportguide/daily_concatenated_sample.html) | Explicit paid dividend event. |
| `Dividend received` | [Fidelity sample statement](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/sample-new-fidelity-acnt-stmt.pdf) | Explicit credited dividend event. |
| `получение дивидендов` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Русская broker-report формулировка. |

Downstream link: Приложение 2 требует отдельный income kind, source, date,
currency and amount. Section heading alone не является событием.

### 3.4 `COUPON_INCOME`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Bond Coupon Payment` | [IBKR consolidated activities sample](https://ibkrguides.com/clientportal/performanceandstatements/activities-consolidated-report-sample.pdf) | Explicit paid bond coupon. |
| `получение ... купонов` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Русская broker-report формулировка. |
| `дивиденды или купоны` | [T‑Bank tax report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/tax-report/) | Broker tax report distinguishes both families. |

Downstream link: Appendix 8 отдельно называет bond interest `(купон)`; НКД в
trade row не является paid coupon.

### 3.5 `INTEREST_INCOME`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Interest` | [IBKR Interest section](https://www.ibkrguides.com/reportingreference/reportguide/interest_default.htm) | Допустимо только с credited event context. |
| `Muni exempt interest` | [Fidelity sample statement](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/sample-new-fidelity-acnt-stmt.pdf) | Explicit interest-income row. |
| `interest ... credited/debited` | [Saxo financial reports](https://www.help.saxo/hc/fr-fr/articles/360001268946-O%C3%B9-puis-je-trouver-mes-relev%C3%A9s-et-rapports-financiers) | Direction must be inspected; header alone is insufficient. |

Downstream link: иностранные проценты — отдельный income kind; coupon, debit
interest и securities-lending interest требуют иных смыслов.

### 3.6 `SECURITIES_LENDING_INCOME`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `IBKR Managed Securities (SYEP) Interest Received` | [IBKR consolidated activities sample](https://ibkrguides.com/clientportal/performanceandstatements/activities-consolidated-report-sample.pdf) | Explicit securities-lending program income. |
| `SYEP income` | [IBKR Interest Accruals](https://www.ibkrguides.com/reportingreference/reportguide/interestaccruals_default.htm) | Broker confirms that lending income can be hidden inside Interest. |
| `операции займа ценными бумагами` | Official FNS procedure, Appendix 8 | Downstream operation family distinct from general interest. |

Downstream link: this label prevents an Interest-section row from losing the
securities-loan meaning needed by Gate 4.

### 3.7 `ACCRUED_COUPON_COMPONENT`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `НКД` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Source explicitly separates amount without НКД and total trade amount. |
| `Accrued Interest` | [IBKR Fixed Income Trades](https://www.ibkrguides.com/reportingreference/reportguide/fixedincome_tradeconfirm.htm) | Explicit component of bond trade final money. |

Downstream link: purchase/sale amounts and dates must remain separable from a
later `Bond Coupon Payment`.

### 3.8 `TRANSACTION_CHARGE`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Комиссия брокера` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Per-trade broker commission. |
| `Комиссия биржи`; `Комиссия клир. центра` | Same T‑Bank guide | Direct trade charges with different collectors. |
| `Commission`; `Tax/Fee` | [IBKR Trades](https://www.ibkrguides.com/reportingreference/reportguide/et_trades.htm) | Per-transaction commission and tax/fee fields. |
| `commission, share amount` | [Saxo Cash Movements](https://www.help.saxo/hc/en-us/articles/360041087992-How-do-I-read-the-Cash-Movements-Summary) | Booking type plus instrument context identifies transaction charge. |

Downstream link: Gate 4 needs the source-stated direct charge, but decides
whether and how it reduces the Russian tax base.

### 3.9 `BROKER_SERVICE_CHARGE`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `комиссия за обслуживание по тарифному плану` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Account-level charge, not one trade commission. |
| `Нетранзакционные расходы` | [T‑Bank tax report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/tax-report/) | Broker explicitly separates service/margin charges from transaction expenses. |
| `Account Maintenance and Reporting Fees` | [IBKR Details of Fees and Charges](https://www.ibkrguides.com/reportingreference/reportguide/detailsfeescharges.htm) | Explicit account-level fee family. |

Downstream link: source fact is preserved for review; the label does not claim
tax deductibility.

### 3.10 `TAX_WITHHELD`

| Source fragment | Official source | Mapping |
| --- | --- | --- |
| `Withholding Tax` | [IBKR Withholding Tax](https://www.ibkrguides.com/reportingreference/reportguide/witholdingtax_default.htm) | Explicit tax withholding section. |
| `удержание налога по счету` | [T‑Bank broker report guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/) | Explicit withheld-tax cash movement. |
| `налог, удержанный эмитентом` | [T‑Bank reports guide](https://www.tbank.ru/invest/help/educate/broker-report/about/get-report/) | Foreign-income certificate field. |
| `дата уплаты налога`; `сумма налога` | Official FNS procedure, paragraphs 0259–0262 | Gate 4 requires date/amount and separate creditability review. |

Downstream link: `TAX_WITHHELD` records only source-stated withholding. It does
not assert foreign-tax credit, Russian tax due or treaty applicability.

## 4. Counterevidence and excluded raw fragments

| Fragment | Source | Why no proposed label is assigned |
| --- | --- | --- |
| `Return of capital` | Fidelity sample statement | Not a dividend; Russian downstream treatment and multi-broker evidence are incomplete. |
| `Payment in lieu` | IBKR/Fidelity reporting references | Can appear under dividend/interest reporting but is not proven equivalent to either. |
| `Иные операции` | T‑Bank broker report guide | Can represent a short-dividend debit; category alone is semantically insufficient. |
| `РЕПО` | T‑Bank broker report guide | Can be a technical cash-timing operation or a substantive repo; context rule not proven. |
| `Corporate Actions` | IBKR reporting guide | Contains heterogeneous acquisition, split, merger, redemption, tender and other events. |
| `Dividends, Interest & Other Income` | Fidelity sample statement | Section heading contains multiple incompatible row meanings. |
| `Service Charge` | Generic broker terminology | Insufficient without broker-account purpose and charge scope. |
| `Depositary fee` / `Custody fee` | Terminology signal | Gate 4 need is plausible, but real transaction rows and robust boundaries are not yet proven. |

## 5. Local corpus audit

The repository-safe manifest is:

```text
services/broker-reports-gate1-proof/benchmarks/semantic_visual_actual_corpus_v1/manifest.json
sha256 = b8e06d00c045ae02424c551fb127776a5c3f7cb5138de247eb7e99670c44d835
```

Read-only text/title inspection of this seven-PDF research manifest produced:

```text
pdf_files = 7
broker_families = 5
statement_of_financial_condition_documents = 7
client_transaction_statements_in_manifest = 0
private_customer_documents_used_for_label_fragments = 0
```

The documents mention words such as trade, dividend or fee in corporate
financial-statement meaning. Those occurrences were not used as evidence for
client financial labels.

## 6. Earlier authorized customer corpus: availability evidence

The earlier customer domain was not absent. Its repository-safe intake
artifacts record:

```text
source_files = 63
source_broker_reports = 7
operations_tables = 8
dividends_reports = 7
fees_reports = 2
represented_broker_or_role_families >= 5
```

Sources:

- [safe intake report](../2026-07-06/OPENWEBUI_BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INTAKE_INDEX.report.md);
- [safe registry](../../stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json);
- [later actual-corpus reproof](../2026-07-21/BROKER_REPORTS_GOAL5_INTEGRATED_ACTUAL_CORPUS_REPROOF.report.md).

The later proof accounts for `104` source identities, `80` logical documents
and `681/681` valid Gate 2 packages. This demonstrates retained corpus and
processing coverage, not correctness of the ten G3.3R labels. No private row,
value, identifier or filename was copied into this ledger, and the historical
broad Gate 2 types were not treated as substitute label evidence.

## 7. Privacy and reproducibility

```text
CUSTOMER_BYTES_IN_GIT = 0
CUSTOMER_VALUES_IN_REPORT = 0
CUSTOMER_IDENTIFIERS_IN_REPORT = 0
PRIVATE_PATHS_IN_REPORT = 0
PUBLIC_OFFICIAL_SOURCE_FRAGMENTS_ONLY = true
PROVIDER_CALLS = 0
```

Все fragments короткие, взяты из публичных official sources и связаны с URL
или локальным official hash. Выдуманные примеры не использовались как
evidence.
