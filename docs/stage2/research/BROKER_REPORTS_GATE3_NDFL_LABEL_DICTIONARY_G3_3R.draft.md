# Минимальные финансовые бирки

Размечай только явно указанные финансовые факты. Если условия не выполнены или
контекста недостаточно, не ставь бирку.

## SECURITY_PURCHASE

Покупка или иное явное приобретение ценной бумаги для счёта.

Ставить, если:
- источник прямо обозначает исполненную покупку конкретной ценной бумаги.

Не ставить, если:
- перевод или зачисление бумаги без покупки;
- остаток позиции, заявка, покупка валюты или РЕПО.

Примеры: Покупка; Buy; Purchase; Trades (Purchase).

Не путать с: Position Transfer In; Open Position; FX Purchase.

## SECURITY_DISPOSAL

Продажа, погашение или иное явное возмездное выбытие ценной бумаги.

Ставить, если:
- источник обозначает исполненную продажу, redemption или maturity с proceeds.

Не ставить, если:
- transfer out, отмена, открытие short или уменьшение позиции без причины;
- corporate action без доказанного возмездного выбытия.

Примеры: Продажа; Sell; Sale; Trades (Sales); Redemption; Maturity.

Не путать с: Position Transfer Out; Withdrawal; Cancelled; Delisting.

## DIVIDEND_INCOME

Выплаченный или зачисленный дивиденд по долевому инструменту.

Ставить, если:
- источник прямо называет выплаченный или зачисленный dividend.

Не ставить, если:
- projected/accrued dividend;
- payment in lieu, short-dividend debit, return of capital или section total.

Примеры: Ordinary Dividend; Cash Dividend; Dividend received; Выплата дивидендов.

Не путать с: Dividend Accrual; Payment in Lieu; Return of capital; Stock Dividend.

## COUPON_INCOME

Выплаченный или зачисленный купон по облигации.

Ставить, если:
- источник прямо обозначает paid/received bond coupon.

Не ставить, если:
- НКД в цене сделки;
- общий interest, дивиденд или погашение principal.

Примеры: Bond Coupon Payment; Coupon; Купон; Выплата купона.

Не путать с: Accrued Interest; НКД; Interest; Redemption.

## INTEREST_INCOME

Зачисленный процентный доход, не являющийся купоном или доходом от займа
ценных бумаг.

Ставить, если:
- описание и направление суммы подтверждают credited interest.

Не ставить, если:
- debit interest/charge, bond coupon, НКД или unpaid accrual;
- SYEP/stock-loan income или только заголовок секции.

Примеры: Interest received; Interest credit; Muni exempt interest; Проценты зачислены.

Не путать с: Debit Interest; Interest Accrued; Bond Coupon Payment; SYEP Interest Received.

## SECURITIES_LENDING_INCOME

Доход или процент, зачисленный за предоставление ценных бумаг в заём.

Ставить, если:
- source связывает доход с securities lending, stock loan или yield enhancement.

Не ставить, если:
- обычный interest по cash, купон, payment in lieu или margin charge.

Примеры: IBKR Managed Securities (SYEP) Interest Received; Securities Lending Income; Stock Loan Income.

Не путать с: Interest; Bond Coupon; Payment in Lieu; Margin Interest.

## ACCRUED_COUPON_COMPONENT

Накопленный, но ещё не выплаченный купонный процент как компонент
облигационной сделки.

Ставить, если:
- НКД/accrued interest явно входит в расчёт покупки или продажи облигации.

Не ставить, если:
- выплаченный купон, общий interest accrual баланса или прогноз дохода.

Примеры: НКД; Накопленный купонный доход; Accrued Interest.

Не путать с: Bond Coupon Payment; Interest Accrued; Projected Income.

## TRANSACTION_CHARGE

Комиссия, сбор или transaction tax, явно привязанные к конкретной покупке или
продаже ценной бумаги.

Ставить, если:
- связь с исполненной сделкой видна из той же строки или секции.

Не ставить, если:
- tax withheld from income;
- обслуживание счёта, custody fee, margin interest или неопределённый service charge.

Примеры: Комиссия брокера; Комиссия биржи; Broker Commission; Commission; Tax/Fee; Stamp Duty.

Не путать с: Withholding Tax; Account Maintenance Fee; Depositary Fee; Interest Charge.

## BROKER_SERVICE_CHARGE

Списанная плата брокеру за обслуживание брокерского счёта или брокерскую
услугу, не привязанная к одной сделке.

Ставить, если:
- source явно называет broker/account maintenance, reporting, plan или иную account-level service fee.

Не ставить, если:
- комиссия конкретной сделки, custody/depositary fee, налог или debit interest;
- `Service Charge` без broker-account контекста.

Примеры: Комиссия за обслуживание счета; Account Maintenance Fee; Reporting Fee; Monthly Activity Fee.

Не путать с: Commission; Depositary Fee; Withholding Tax; Debit Interest.

## TAX_WITHHELD

Налог, фактически удержанный из конкретного дохода.

Ставить, если:
- источник подтверждает withholding/deduction и связь с income event.

Не ставить, если:
- transaction tax/stamp duty;
- налог только рассчитан или подлежит уплате;
- комиссия или общая налоговая справка без фактического удержания.

Примеры: Withholding Tax; Tax Withheld; Foreign Tax Paid; Удержанный налог; Удержание налога.

Не путать с: Tax/Fee в trade row; Stamp Duty; Tax Calculated; Tax Payable.
