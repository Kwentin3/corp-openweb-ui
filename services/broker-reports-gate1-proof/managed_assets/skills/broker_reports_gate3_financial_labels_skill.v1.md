# Broker Reports Financial Labels

Asset ID: `broker-reports-financial-labels`

Dictionary: `broker-reports-financial-labels@2.0.1`

Dictionary file SHA-256: `30b395b13387cad5d3d51269bc3bae989bb3b524c9547053841dc5d146c569fe`

Model-view SHA-256: `7f41ecf9bbe5dee17331a94817d0b3b531421856f4a70492ce1cdb8d1d81b888`

Status: generated operator-facing projection of the published package resource.

This Skill is an inspection surface, not a second financial-meaning authority. Edit and publish the versioned package dictionary through its governed lifecycle, then rebuild and republish this asset. Knowledge/RAG is not used.

## Published dictionary model view

# Financial labels

## SECURITY_PURCHASE

Смысл: Исполненная покупка конкретной ценной бумаги, которую источник прямо утверждает в точном source target.

Ставить, если:
- Источник прямо показывает исполненную покупку ценной бумаги.

Не ставить, если:
- Это transfer, position, FX, заявка или РЕПО.

Примеры:
- `Покупка`
- `Buy`
- `Purchase`

Не путать с:
- Перевод ценных бумаг
- Stock distribution

## SECURITY_DISPOSAL

Смысл: Исполненная продажа, погашение или иное возмездное выбытие ценной бумаги, которое источник прямо утверждает в точном source target.

Ставить, если:
- Источник показывает sale, redemption или maturity и полученные proceeds.

Не ставить, если:
- Это transfer out, отмена, изменение позиции, РЕПО или corporate action без доказанного возмездного выбытия.

Примеры:
- `Продажа`
- `Погашение ЦБ`
- `Sell`
- `Redemption`

Не путать с:
- Перевод ценных бумаг
- Stock dividend

## DIVIDEND_INCOME

Смысл: Выплаченный или зачисленный денежный дивиденд, прямо сообщённый источником.

Ставить, если:
- Источник прямо показывает paid или credited cash dividend.

Не ставить, если:
- Это dividend accrual, stock dividend или return of capital.

Примеры:
- `Наличный дивиденд`
- `Обыкновенный дивиденд`
- `Cash Dividend`

Не путать с:
- Начисления дивидендов
- Возврат капитала

## COUPON_INCOME

Смысл: Выплаченный или зачисленный купон по облигации, прямо сообщённый источником.

Ставить, если:
- Источник прямо показывает payment или credit купона.

Не ставить, если:
- Это НКД сделки, погашение principal или общий interest.

Примеры:
- `Зачисление д/с (купон …)`
- `Погашение купона`
- `Coupon Payment`

Не путать с:
- НКД покупки
- НКД продажи
- Погашение ЦБ

## INTEREST_INCOME

Смысл: Фактически начисленный или зачисленный процентный доход по денежным средствам, прямо сообщённый источником.

Ставить, если:
- Источник и направление суммы прямо подтверждают cash-interest income.

Не ставить, если:
- Это debit interest, coupon, НКД, unpaid accrual или доход от займа ценных бумаг.

Примеры:
- `Проценты по займам "овернайт"`
- `Interest Credit`

Не путать с:
- Дебетовый процент
- Начисления процентов

## SECURITIES_LENDING_INCOME

Смысл: Фактически начисленный или зачисленный доход за передачу ценных бумаг в заём, прямо сообщённый источником.

Ставить, если:
- Income row прямо называет securities или stock loan и содержит source value.

Не ставить, если:
- Это cash interest, margin charge, payment in lieu или общее описание договора.

Примеры:
- `Проценты по займам "овернайт ЦБ"`
- `Securities Lending Income`

Не путать с:
- Проценты по займам "овернайт" без ЦБ

## ACCRUED_COUPON_COMPONENT

Смысл: НКД как явно названный источником компонент строки покупки или продажи облигации.

Ставить, если:
- НКД или accrued coupon прямо находится в source target transaction price, cost или proceeds.

Не ставить, если:
- Это выплаченный купон, общий accrual или informational position value.

Примеры:
- `НКД покупки`
- `НКД продажи`
- `Accrued Interest в trade row`

Не путать с:
- Погашение купона
- НКД на конец периода

## TRANSACTION_CHARGE

Смысл: Комиссия, сбор или transaction tax, которые источник прямо сообщает в контексте конкретной source transaction row или секции; этот контекст не является налоговой или самостоятельно восстановленной экономической связью.

Ставить, если:
- Комиссия или сбор и конкретная исполненная сделка находятся в одном явно заданном source target.

Не ставить, если:
- Не выводи связь по дате, активу, сумме, соседству или сходству; для комиссии без source transaction context используй COMMISSION.

Примеры:
- `Комиссия в строке сделки`
- `Exchange Fee in trade row`
- `Transaction tax in execution row`

Не путать с:
- Удерживаемый налог
- Комиссия за период

## COMMISSION

Смысл: Комиссия, сбор или вознаграждение, прямо сообщённые источником без связи с конкретной операцией; точный source target остаётся единственным контекстом.

Ставить, если:
- Источник прямо называет комиссию или сбор и сумму, но не утверждает relation с конкретной transaction row.

Не ставить, если:
- Не распределяй сумму по операциям, активам, лотам или продажам и не выводи скрытую relation.

Примеры:
- `Комиссия: 100`
- `Broker fee`
- `Вознаграждение брокера`
- `Сбор агента при выплате дохода`

Не путать с:
- Комиссия в строке сделки
- Итого комиссии

## COMMISSION_TOTAL

Смысл: Итоговая комиссия или сбор за явно названный источником период, раздел или statement scope.

Ставить, если:
- Источник прямо помечает сумму как итог комиссии для своего точного aggregate target.

Не ставить, если:
- Не суммируй детали, не сверяй их с итогом, не заменяй итог деталями и не раскладывай итог обратно.

Примеры:
- `Итого`
- `Total commission`
- `Комиссия за период`

Не путать с:
- Комиссия: 100
- Комиссия в строке сделки

## TAX_WITHHELD

Смысл: Налог, который источник прямо утверждает как удержанный в точном detail source target.

Ставить, если:
- Withholding прямо указан в строке дохода или иной детальной source row.

Не ставить, если:
- Это transaction tax, tax calculated, tax payable, refund или aggregate total.

Примеры:
- `Налог удержан в строке дохода`
- `Withholding Tax Detail`

Не путать с:
- Расчет налога
- Итого удержанный налог

## TAX_WITHHELD_TOTAL

Смысл: Итог удержанного налога за явно названный источником период, раздел или statement scope.

Ставить, если:
- Источник прямо помечает сумму как total withheld tax для exact aggregate target.

Не ставить, если:
- Не суммируй детали, не сверяй их с итогом, не связывай итог с отдельными доходами и не заменяй source value.

Примеры:
- `Итого удержано`
- `Total tax withheld`
- `Налог удержанный за период`

Не путать с:
- Налог удержан в строке дохода
- Tax payable
