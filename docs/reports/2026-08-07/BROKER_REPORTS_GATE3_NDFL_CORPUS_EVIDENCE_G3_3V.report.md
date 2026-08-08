# G3.3V — privacy-safe corpus evidence

Дата: 2026-08-07

Назначение: дать постановщикам проверяемые реальные примеры для Label Decision
Matrix без публикации customer bytes.

## 1. Правила evidence

- `source` — стабильный `brdoc_*` из safe-индекса, не private filename.
- `p.N / line N` — locator в извлечённом text layer; для CSV/HTML указан
  logical/physical line в локальном чтении.
- `[value]` заменяет дату, количество, цену, сумму, account marker или иной
  customer value.
- `[security]` заменяет название/тикер инструмента.
- Фрагменты не synthetic: сохранены реальные broker wording и порядок
  существенных полей; удалены только чувствительные значения.
- `non-zero value suppressed` означает, что в той же source row проверено
  наличие ненулевого числового значения, но само значение не экспортировано.
- Старые Gate 2 labels и keyword hits не являются решением.

Decision vocabulary:

- `MATCH` — достаточный положительный случай;
- `COUNTEREXAMPLE` — похожий реальный факт, который label получать не должен;
- `AMBIGUOUS` — без дополнительного контекста label ставить нельзя;
- `NOT_COVERED` — реальный факт вне итогового набора.

## 2. Corpus accounting

| Проверка | Результат |
| --- | --- |
| Top-level sources | 63 |
| Text-addressable after bounded local parsing | 58 |
| Visual-only without text layer | 5 |
| Safe acceptance accounting | 104 source identities / 80 logical documents |
| Provider calls for G3.3V | 0 |
| Customer amounts/account IDs exported | 0 |

Visual-only sources без semantic claim:
`brdoc_036_f1995ee6a6fa`, `brdoc_060_e69ef2fa1cb2`,
`brdoc_061_aeaff2e070aa`, `brdoc_062_161065e246ac`,
`brdoc_063_510b999b1914`.

## 3. `SECURITY_PURCHASE`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| PUR-01 | `brdoc_044_74e5de8408a8` / VTB-family / operations, p.6 lines 10–14 | `Московская биржа … Покупка … Расчеты по заключенным сделкам` + transaction row values suppressed. | `MATCH` |
| PUR-02 | `brdoc_045_0c44a95cc671` / VTB / securities transactions, p.2 | Table direction contains separate `Продажа` and `Покупка` columns/rows; executed transaction section supplies date/price/value context. | `MATCH` |
| PUR-03 | `brdoc_007_bdc1038fdd93` / Otkritie / transaction table, p.7 line 29 | `Покупка` within securities operation rows, not a position summary. | `MATCH` |
| PUR-04 | `brdoc_037_8c0fea99b1db` / BCS / operation types, p.2 lines 319–321 | `Проценты по займам "овернайт ЦБ" … Переводы между площадками`. A transfer can increase holdings but is not a purchase. | `COUNTEREXAMPLE` |
| PUR-05 | `brdoc_001_b874d956e33a` / IBKR / corporate actions, CSV line 365 | `Корпоративные действия … Дивиденд в форме акций [value] за [value]`. Shares arrive without an executed purchase. | `COUNTEREXAMPLE` |
| PUR-06 | `brdoc_007_bdc1038fdd93` / Otkritie / explanatory REPO block, p.15 | Standalone `Покупка.` appears inside a `Репо с неттингом` explanation. Without REPO context it would be a false purchase. | `AMBIGUOUS` |

Conclusion: the label needs executed-security-operation context; literal
`Покупка` alone is insufficient.

## 4. `SECURITY_DISPOSAL`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| DSP-01 | `brdoc_044_74e5de8408a8` / VTB-family / operations, p.5 lines 14–18 | `Московская биржа … Продажа … Расчеты по заключенным сделкам`. | `MATCH` |
| DSP-02 | same source / VTB-family / operations, p.5 lines 21–25 | `Внебиржевой рынок … Погашение ЦБ … Погашение ценных бумаг`. | `MATCH` |
| DSP-03 | `brdoc_045_0c44a95cc671` / VTB / legend, p.3 | `* — Сделка погашения ЦБ`; `о — Сделка частичного погашения ЦБ`, bound to the transaction table. | `MATCH` |
| DSP-04 | `brdoc_055_21c85fa3ff06` / Sber-family / cash operations, HTML line 153 | `Основной рынок Зачисление д/с (погашение [security]) [value]`. Cash credit confirms proceeds from redemption. | `MATCH` |
| DSP-05 | `brdoc_037_8c0fea99b1db` / BCS / operation types, p.2 | `Переводы между площадками` is movement, not a disposal. | `COUNTEREXAMPLE` |
| DSP-06 | `brdoc_001_b874d956e33a` / IBKR / corporate actions, CSV line 365 | `Дивиденд в форме акций` changes holdings but does not prove consideration/proceeds. | `COUNTEREXAMPLE` |
| DSP-07 | `brdoc_007_bdc1038fdd93` / Otkritie / REPO explanation, p.15 | `Репо с неттингом` with embedded purchase/sale wording cannot be reduced to ordinary disposal without both-leg context. | `AMBIGUOUS` |

Conclusion: sale and redemption may share the label; transfer and REPO may
not. Subtype remains visible in source text.

## 5. `DIVIDEND_INCOME`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| DIV-01 | `brdoc_003_be6168a763cd` / IBKR / dividends, CSV lines 383–384 | `Дивиденды,Header,Валюта,Дата,Описание,Сумма` followed by `Наличный дивиденд … (Обыкновенный дивиденд),[value]`. | `MATCH` |
| DIV-02 | `brdoc_001_b874d956e33a` / IBKR / dividends, CSV data row | `Наличный дивиденд [value] на акцию (Обыкновенный дивиденд),[value]`. | `MATCH` |
| DIV-03 | `brdoc_045_0c44a95cc671` / VTB / income payment table, p.7 lines 153–165 | `Дата выплаты / Счет для зачисления … дивиденды [value]`; payment date/account section establishes paid income. | `MATCH` |
| DIV-04 | `brdoc_003_be6168a763cd` / IBKR / dividends, CSV line 458 | `Наличный дивиденд … (Возврат капитала),[value]`. Dividend section placement does not make return of capital a dividend income fact. | `COUNTEREXAMPLE` |
| DIV-05 | same source / IBKR / corporate actions, CSV line 340 | `Дивиденд в форме акций` is a stock distribution, not cash dividend income. | `COUNTEREXAMPLE` |
| DIV-06 | same source / IBKR / NAV/change sections, CSV lines 19, 30 | `Начисления дивидендов` / `Изменения в начислениях дивидендов` lack a paid/credited event. | `AMBIGUOUS` |

## 6. `COUPON_INCOME`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| CPN-01 | `brdoc_055_21c85fa3ff06` / Sber-family / cash operations, HTML line 207 | `Зачисление д/с (купон [value] по [security]). Налог удержан. [value]`. | `MATCH` |
| CPN-02 | `brdoc_056_1fb1c0744eb0` / Sber-family / cash operations, HTML line 208 | `Зачисление д/с (купон [value] по [security]). Налог удержан. [value]`. | `MATCH` |
| CPN-03 | `brdoc_059_b9bca7e6e44d` / Sber / tax calculation detail, p.3 | Row description `Погашение купона` appears under `Купон, Код Дохода` with source values suppressed. | `MATCH` |
| CPN-04 | same source / Sber / securities table, p.3 lines 23–24 | `НКД продажи` / `НКД покупки` are transaction components, not coupon payment. | `COUNTEREXAMPLE` |
| CPN-05 | `brdoc_044_74e5de8408a8` / VTB-family / redemption row, p.5 | `Погашение ЦБ` is principal disposal unless coupon payment is separately stated. | `COUNTEREXAMPLE` |
| CPN-06 | `brdoc_007_bdc1038fdd93` / Otkritie / income table, p.3 | `Доходы и расходы по ценным бумагам (дивиденды и купоны)` is a mixed section title; row-level `Вид дохода` is required. | `AMBIGUOUS` |

## 7. `INTEREST_INCOME`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| INT-01 | `brdoc_037_8c0fea99b1db` / BCS / cash operations, p.1 line 221 | Nine actual rows `Проценты по займам "овернайт"` with non-zero values suppressed; no `ЦБ` marker. | `MATCH` |
| INT-02 | `brdoc_038_d603a3988ee0` / BCS / cash operations, p.1 line 249 | Actual row `Проценты по займам "овернайт"` with source value context. | `MATCH` |
| INT-03 | `brdoc_003_be6168a763cd` / IBKR / interest, CSV lines 721–724 | `Процент,Header,Валюта,Дата,Описание,Сумма` followed by `Дебетовый процент …`. This is an expense/charge. | `COUNTEREXAMPLE` |
| INT-04 | `brdoc_055_21c85fa3ff06` / Sber-family / cash operations | `Зачисление д/с (купон …)` is coupon income despite being economically interest-like. | `COUNTEREXAMPLE` |
| INT-05 | `brdoc_003_be6168a763cd` / IBKR / NAV, CSV line 18 | `Начисления процентов` is an accrual/balance component without credited-income direction. | `AMBIGUOUS` |
| INT-06 | `brdoc_037_8c0fea99b1db` / BCS / footnote, p.18 lines 80–81 | `Проценты … за пользование Денежными средствами/Ценными Бумагами по договору займа`. Generic formula combines two possible labels and is not an event. | `AMBIGUOUS` |

## 8. `SECURITIES_LENDING_INCOME`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| SLI-01 | `brdoc_037_8c0fea99b1db` / BCS / operations, p.2 line 319 | Actual row `Проценты по займам "овернайт ЦБ"` with non-zero value suppressed. The `ЦБ` object distinguishes it from cash overnight interest. | `MATCH` |
| SLI-02 | same source / BCS / cash operations, p.1 line 221 | `Проценты по займам "овернайт"` without `ЦБ` belongs to cash interest. | `COUNTEREXAMPLE` |
| SLI-03 | `brdoc_003_be6168a763cd` / IBKR / interest | `Дебетовый процент` is a charge, not securities-lending income. | `COUNTEREXAMPLE` |
| SLI-04 | `brdoc_037_8c0fea99b1db` / BCS / footnote, p.18 lines 80–81 | Formula covering `Денежными средствами/Ценными Бумагами` is not specific enough. | `AMBIGUOUS` |
| SLI-05 | `brdoc_006_7cfd297786cc` / IBKR / legal information, p.64 lines 27–31 | Explanatory text about `выдачи акций в кредит` and a lending rate describes mechanics, not a customer income event. | `AMBIGUOUS` |

## 9. `ACCRUED_COUPON_COMPONENT`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| ACC-01 | `brdoc_059_b9bca7e6e44d` / Sber / securities transaction table, p.3 lines 21–25 | `Продано на сумму / Куплено на сумму / НКД продажи / НКД покупки / Комиссия по сделке`. | `MATCH` |
| ACC-02 | `brdoc_045_0c44a95cc671` / VTB / transaction-cost table, p.3 lines 120–124 | `Комиссионные затраты (транзактные) … Цена / НКД / Сумма`. | `MATCH` |
| ACC-03 | `brdoc_055_21c85fa3ff06` / Sber-family / positions footnote, HTML line 311 | `Информация о накопленном купонном доходе (НКД) носит информационный характер`. This is not a transaction component. | `COUNTEREXAMPLE` |
| ACC-04 | same source / Sber-family / positions, HTML line 68 | Position columns include `Рыночная стоимость, без НКД / НКД`; a snapshot is not purchase/sale NКД. | `COUNTEREXAMPLE` |
| ACC-05 | `brdoc_044_74e5de8408a8` / VTB-family / securities view, p.5 lines 61–67 | Standalone `НКД в валюте номинала (на конец …)` needs the table scope; without it, transaction vs position is unclear. | `AMBIGUOUS` |

## 10. `TRANSACTION_CHARGE`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| TRC-01 | `brdoc_045_0c44a95cc671` / VTB / transaction result, p.3 lines 19–23 | `Сумма продажи … Комиссионные затраты (транзактные) … Результат от операций с ЦБ`. | `MATCH` |
| TRC-02 | `brdoc_055_21c85fa3ff06` / Sber-family / operation table, HTML line 170 | `Дата операции … Цена … Комиссия Брокера … Комиссия Биржи … Другие затраты`. | `MATCH` |
| TRC-03 | `brdoc_003_be6168a763cd` / IBKR / trades, CSV line 261 | `Сделки,Header … Цена транзакции … Выручка … Комиссия/плата … Базис`. | `MATCH` |
| TRC-04 | `brdoc_044_74e5de8408a8` / VTB-family / fees, p.2 lines 47–53 | `Комиссия банка за заключение сделок …` and `Комиссия за брокерские услуги по проведению расчетов по заключенным сделкам`. Both are trade-linked. | `MATCH` |
| TRC-05 | `brdoc_039_ca35351f1c5f` / BCS / account services, p.3 | `Вознаграждение за обслуживание счета депо` with non-zero value is account-level, not tied to one trade. | `COUNTEREXAMPLE` |
| TRC-06 | `brdoc_001_b874d956e33a` / IBKR / withholding section, CSV line 572 | `Удерживаемый налог … Наличный дивиденд … Налог,[value]` is income withholding, not transaction fee. | `COUNTEREXAMPLE` |
| TRC-07 | `brdoc_037_8c0fea99b1db` / BCS / operations, p.7 line 590 | `Начисленная комиссия` lacks enough local purpose/binding when isolated. | `AMBIGUOUS` |

## 11. `BROKER_SERVICE_CHARGE`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| BSC-01 | `brdoc_044_74e5de8408a8` / VTB-family / fees, p.2 line 53 | `Комиссия за брокерские услуги по проведению расчетов по заключенным сделкам` is transaction-linked. | `COUNTEREXAMPLE` |
| BSC-02 | same source / VTB-family / document prose, p.1, p.17 | `соглашение на брокерское обслуживание` / `Департамент брокерского обслуживания` are prose/signature, not charged events. | `COUNTEREXAMPLE` |
| BSC-03 | `brdoc_037_8c0fea99b1db` / BCS / operations, p.1 | `Комиссия за перенос позиции` is position-financing/transaction context, not account maintenance. | `COUNTEREXAMPLE` |
| BSC-04 | same source / BCS / operations, p.7 | `Начисленная комиссия` without purpose is not safely classifiable. | `AMBIGUOUS` |
| BSC-05 | `brdoc_044_74e5de8408a8` / VTB-family / heading/prose | Literal `брокерского обслуживания` without debit/value is ambiguous. | `AMBIGUOUS` |
| BSC-06 | `brdoc_039_ca35351f1c5f` / BCS / account services, p.3 | `Вознаграждение за обслуживание счета депо` with non-zero value is real, but excluded by the original broker-service definition. Candidate: custody charge. | `NOT_COVERED` |

No `MATCH` exists for the original label. This is the direct basis for `DROP`.

## 12. `TAX_WITHHELD`

| ID | source / family / location | Реальный privacy-safe fragment и минимальный контекст | Decision |
| --- | --- | --- | --- |
| TAX-01 | `brdoc_001_b874d956e33a` / IBKR / withholding, CSV lines 571–572 | `Удерживаемый налог,Header,Валюта,Дата,Описание,Сумма` followed by `Наличный дивиденд … Налог,[value]`. | `MATCH` |
| TAX-02 | `brdoc_055_21c85fa3ff06` / Sber-family / cash operations, HTML line 207 | `Зачисление д/с (купон …). Налог удержан. [value]`. | `MATCH` |
| TAX-03 | `brdoc_007_bdc1038fdd93` / Otkritie / income table, p.3 lines 1–10 | `Доходы … (дивиденды и купоны)` with row columns `Вид дохода / Налог у источника / Налог у брокера / Сумма`; row values provide income-section binding. | `MATCH` |
| TAX-04 | `brdoc_059_b9bca7e6e44d` / Sber / tax calculation, p.1 | `Расчет налога … Налоговая база итого` is calculation, not proof of withholding. | `COUNTEREXAMPLE` |
| TAX-05 | `brdoc_044_74e5de8408a8` / VTB-family / cash operations, p.2 line 6 | `Уплата/возврат налога за предыдущий год` combines two directions and does not prove withholding from income. | `COUNTEREXAMPLE` |
| TAX-06 | `brdoc_045_0c44a95cc671` / VTB / table column, p.4 | Isolated literal `удержанная` needs its tax header, amount and event binding. | `AMBIGUOUS` |
| TAX-07 | `brdoc_007_bdc1038fdd93` / Otkritie / summary, p.2 | `Корректировка доходов … старых календарных периодов` near tax columns requires row-level direction; section adjacency alone is insufficient. | `AMBIGUOUS` |

## 13. Missing-coverage evidence

| ID | source / family / location | Реальный privacy-safe fragment | Decision / candidate |
| --- | --- | --- | --- |
| NEW-01 | `brdoc_044_74e5de8408a8` / VTB-family / p.16–17 | `Внебирж. Спец. РЕПО-1ч`; `Внебирж. Спец. РЕПО-2ч`; пояснение: разница частей отражается после исполнения второй части. | `NOT_COVERED` / `REPO_EVENT` |
| NEW-02 | `brdoc_007_bdc1038fdd93` / Otkritie / p.15 | `Репо с неттингом`. | `NOT_COVERED` / `REPO_EVENT` |
| NEW-03 | `brdoc_039_ca35351f1c5f` / BCS / p.3 | `Вознаграждение за обслуживание счета депо`, non-zero value suppressed. | `NOT_COVERED` / `SECURITIES_CUSTODY_CHARGE` |
| NEW-04 | `brdoc_001_b874d956e33a` / IBKR / CSV line 412 | `Наличный дивиденд … (Возврат капитала),[value]`. | `NOT_COVERED` / `RETURN_OF_CAPITAL` |
| NEW-05 | same source / IBKR / CSV line 365 | `Корпоративные действия … Дивиденд в форме акций [value] за [value]`. | `NOT_COVERED` / `STOCK_DISTRIBUTION_EVENT` |
| NEW-06 | `brdoc_039_ca35351f1c5f` / BCS / p.15 | `Дивидендный сплит.` | `NOT_COVERED` / `STOCK_DISTRIBUTION_EVENT` |
| NEW-07 | `brdoc_044_74e5de8408a8` / VTB-family / p.2 line 6 | `Уплата/возврат налога за предыдущий год [value]`. | `NOT_COVERED` / `TAX_SETTLEMENT_OR_REFUND` |

## 14. Evidence count reconciliation

| LABEL_ID | MATCH | COUNTEREXAMPLE | AMBIGUOUS | NOT_COVERED |
| --- | ---: | ---: | ---: | ---: |
| `SECURITY_PURCHASE` | 3 | 2 | 1 | 0 |
| `SECURITY_DISPOSAL` | 4 | 2 | 1 | 0 |
| `DIVIDEND_INCOME` | 3 | 2 | 1 | 0 |
| `COUPON_INCOME` | 3 | 2 | 1 | 0 |
| `INTEREST_INCOME` | 2 | 2 | 2 | 0 |
| `SECURITIES_LENDING_INCOME` | 1 | 2 | 2 | 0 |
| `ACCRUED_COUPON_COMPONENT` | 2 | 2 | 1 | 0 |
| `TRANSACTION_CHARGE` | 4 | 2 | 1 | 0 |
| `BROKER_SERVICE_CHARGE` | 0 | 3 | 2 | 1 |
| `TAX_WITHHELD` | 3 | 2 | 2 | 0 |
