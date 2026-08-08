# G3.3V — проверка финансового словаря на реальном брокерском корпусе

Дата: 2026-08-07

Статус: `PARTIALLY_COMPLETED`

Режим: research-only; runtime, Gate 2, G3.1/G3.2, provider route и product path
не изменялись.

## 1. Итог

Все 10 кандидатов G3.3R рассмотрены. Девять выдержали corpus validation и
вошли в отдельный `Financial Label Dictionary v1 — CANDIDATE`.
`BROKER_SERVICE_CHARGE` не вошёл: в доступной текстовой части корпуса не найден
ни один чистый пример списанной account-level платы именно за обслуживание
брокерского счёта. Похожие реальные строки оказались либо расходами конкретной
сделки, либо платой за счёт депо, либо просто текстом договора/подразделения.

Словарь устойчиво разделяет оставшиеся девять понятий при условии, что модель
получает не один literal, а минимальный контекст строки: раздел, направление
суммы, соседние колонки и вид операции.

Обнаружены пять фактов, которые могут понадобиться Gate 4 и не покрыты
кандидатом v1: РЕПО, обслуживание счёта депо, возврат капитала, распределение
акций и налоговый платёж/возврат. Они зафиксированы только как
`NEW_LABEL_CANDIDATE`; автоматически в словарь не добавлялись.

## 2. Корпус и граница доказательства

Использованы:

- safe-индекс 63 исходных файлов;
- локальный private registry только для разрешённого чтения оригиналов;
- safe acceptance: 104 source identities и 80 logical documents;
- семейства BCS, IBKR, Otkritie, Sber и VTB;
- 58 из 63 top-level источников, из которых удалось получить текст, таблицы
  или XML/HTML/CSV/XLSX-содержимое без provider LLM;
- пять визуальных PDF без text layer оставлены вне семантического утверждения:
  `brdoc_036_f1995ee6a6fa`, `brdoc_060_e69ef2fa1cb2`,
  `brdoc_061_aeaff2e070aa`, `brdoc_062_161065e246ac`,
  `brdoc_063_510b999b1914`.

Поэтому `CUSTOMER_CORPUS_REVIEW = PARTIAL`: проверена вся доступная
text-addressable часть top-level корпуса и архивные текстовые члены, но не
приписан финансовый смысл пяти visual-only источникам.

Старые широкие Gate 2 labels использовались только как навигация. Keyword scan
также был только discovery-механизмом: ни количество совпадений, ни regex сами
по себе не считались evidence. Решения ниже опираются на вручную проверенные
строки и их контекст в отдельном evidence-файле.

`POSITIVE_EVIDENCE_COUNT`, `COUNTEREXAMPLE_COUNT` и `AMBIGUOUS_COUNT` — число
отобранных privacy-safe evidence specimens, а не оценка общего числа событий в
корпусе.

## 3. Ценность ранее предоставленного домена

Ранее созданные managed Skill/Prompt/Semantic Pack не дают готового словаря для
G3.3V: их активный compact snapshot содержит только широкие Gate 2 понятия
`cash_balance_snapshot_v1` и `printed_financial_metric_v1`, а сами assets имеют
статусы `managed_target_not_live` / `target_normative_not_live`.

Полезна не их финансовая таксономия, а проверочная дисциплина:

- один явно назначенный semantic authority;
- решение по полному bounded context, а не по одному literal;
- counterexamples и ambiguity rules обязательны;
- неоднозначное значение остаётся unclassified, а не угадывается;
- regex, prompt и общие знания модели не становятся параллельной семантической
  властью.

Эта дисциплина применена в G3.3V. Переносить прежние типы, prompt wording или
Claude workflow в новый словарь не нужно: кандидат G3.3V точнее и короче для
задачи Gate 4. Старый blueprint также полезен только как напоминание, что
Claude-процесс был примером пользовательского workflow, а результат требует
ручной проверки; финансовых определений для v1 он не добавляет.

## 4. Label Decision Matrix

| LABEL_ID | DECISION | POSITIVE | COUNTER | AMBIGUOUS | BROKER_FAMILIES_COVERED | CURRENT_DEFINITION_PROBLEM | PROPOSED_MINIMAL_DEFINITION | GATE4_JUSTIFICATION | CONFIDENCE |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `SECURITY_PURCHASE` | `KEEP` | 3 | 2 | 1 | Otkritie, VTB, IBKR | Проблемы определения не найдено; literal без event context недостаточен. | Исполненная покупка конкретной ценной бумаги для счёта; не transfer, position, FX или РЕПО. | Даёт acquisition event для последующей привязки стоимости приобретения. | `HIGH` |
| `SECURITY_DISPOSAL` | `KEEP` | 4 | 2 | 1 | Otkritie, Sber, VTB | Sale и redemption различимы по source text, но отдельные Gate 3 labels не нужны. | Исполненная продажа, погашение или иное возмездное выбытие с proceeds; не transfer, отмена или неясное corporate action. | Gate 4 нужен общий disposal event; точный subtype остаётся в canonical context. | `HIGH` |
| `DIVIDEND_INCOME` | `KEEP` | 3 | 2 | 1 | IBKR, Otkritie, VTB | `Dividend` встречается также в accrual, stock distribution и return of capital. | Выплаченный или зачисленный денежный дивиденд; не accrual, stock dividend или return of capital. | Отдельный вид дохода и возможная связь с удержанным налогом. | `HIGH` |
| `COUPON_INCOME` | `KEEP` | 3 | 2 | 1 | Otkritie, Sber, VTB | Один `Купон` без payment/credit context может быть заголовком или НКД. | Выплаченный или зачисленный купон по облигации; не НКД, principal redemption или общий interest. | Отдельный доход; нельзя смешивать с ценовым компонентом НКД. | `HIGH` |
| `INTEREST_INCOME` | `KEEP` | 2 | 2 | 2 | BCS; IBKR как counterexample | Направление и объект займа обязательны; слово `процент` не классифицирует факт. | Фактически начисленный/зачисленный процентный доход по денежным средствам; не debit interest, coupon, НКД или securities lending. | Нужен отдельный income fact, но только при доказанном credit/income context. | `MEDIUM` |
| `SECURITIES_LENDING_INCOME` | `KEEP` | 1 | 2 | 2 | BCS | Положительный event найден только в одном broker family; generic loan wording смешивает деньги и ЦБ. | Фактически начисленный/зачисленный доход за передачу именно ценных бумаг в заём; не cash interest, margin charge или общее описание договора. | Экономический источник отличается от cash interest; Gate 4 должен видеть это различие. | `MEDIUM` |
| `ACCRUED_COUPON_COMPONENT` | `KEEP` | 2 | 2 | 1 | Sber, VTB | `НКД` в position snapshot не равен НКД сделки. | НКД/accrued coupon, явно включённый в расчёт покупки или продажи облигации; не выплаченный coupon и не informational position value. | Нужен как компонент transaction cost/proceeds, а не как самостоятельный доход. | `HIGH` |
| `TRANSACTION_CHARGE` | `KEEP` | 4 | 2 | 1 | BCS, IBKR, Sber, VTB | Название комиссии недостаточно; обязательна связь с конкретной исполненной сделкой. | Комиссия, сбор или transaction tax, прямо связанные с покупкой/продажей; не account/custody service, withholding или interest charge. | Gate 4 нужен общий класс прямых transaction costs; subtype остаётся в source text, поэтому split не доказан. | `HIGH` |
| `BROKER_SERVICE_CHARGE` | `DROP` | 0 | 3 | 2 | BCS, VTB | Нет clean positive; термин пересекается с transaction service и custody/depo fee. | Не предлагается. Реальную custody/depo строку рассматривать отдельно, не расширять старый label. | Отдельная downstream-потребность именно в broker account service на этом корпусе не доказана. | `MEDIUM` |
| `TAX_WITHHELD` | `KEEP` | 3 | 2 | 2 | IBKR, Otkritie, Sber | Нельзя принимать tax calculation, payable или объединённый payment/refund за withholding. | Фактически удержанный налог, связанный с доходом или однозначным income section; не transaction tax, calculation, payable, payment/refund. | Нужен для сверки удержанного налога без решения о зачёте. | `HIGH` |

### 4.1 Почему `SECURITY_DISPOSAL` не разделён

Корпус явно различает `Продажа`, `Погашение ЦБ` и `частичное погашение`. Для
Gate 4 это разные source descriptions, но общий обязательный вопрос один:
произошло ли возмездное выбытие, для которого нужны proceeds и cost basis.
Canonical context не удаляется, поэтому downstream может прочитать subtype.
Отдельные `SALE` и `REDEMPTION` labels на Gate 3 дали бы дублирование без
доказанного выигрыша.

### 4.2 Почему `TRANSACTION_CHARGE` не разделён

В корпусе есть broker commission, exchange commission, transaction costs и
внешние расходы. Их объединяет доказуемая связь с конкретной сделкой. Gate 4
в любом случае должен проверить допустимость конкретного source-stated
расхода; название и subtype остаются в canonical строке. Отдельные labels для
broker/exchange/clearing/stamp duty не нужны до evidence, что Gate 4 теряет
решение при общей бирке.

### 4.3 Почему `BROKER_SERVICE_CHARGE` удалён

Три похожих класса оказались разными:

1. `Комиссия за брокерские услуги по проведению расчетов по заключенным
   сделкам` — transaction charge.
2. `Вознаграждение за обслуживание счета депо` — custody/depository fact,
   который исходное определение прямо исключало.
3. `брокерское обслуживание` / `Департамент брокерского обслуживания` — текст
   соглашения или подписи без финансового списания.

Расширять label до любой услуги опасно: он станет ловить договорный текст и
смешает account-level custody с direct transaction cost. Поэтому минимальный
v1 обходится без него.

## 5. Missing Coverage — только `NEW_LABEL_CANDIDATE`

| Candidate | SOURCE_EVIDENCE | WHY_GATE4_NEEDS_IT | WHY_EXISTING_LABELS_FAIL | RECOMMENDATION |
| --- | --- | --- | --- | --- |
| `REPO_EVENT` | Otkritie `brdoc_007...`: `Репо с неттингом`; VTB-family `brdoc_044...`: `Внебирж. Спец. РЕПО-1ч` / `РЕПО-2ч` и пояснение о разнице частей. | РЕПО встречается массово и может влиять на доход/расход и связь двух частей. | Purchase/disposal сознательно исключают РЕПО; transaction charge покрывает только комиссию, не саму операцию. | Отдельный research: минимально отличить самостоятельное РЕПО от технического переноса; не добавлять сейчас. |
| `SECURITIES_CUSTODY_CHARGE` | BCS `brdoc_039...`, p.3: `Вознаграждение за обслуживание счета депо` с ненулевой source value. | Может быть отдельным source-stated расходом, который Gate 4 должен проверить на допустимость. | Transaction charge требует конкретную сделку; удалённый broker-service label прямо исключал custody. | Проверить downstream-методику и второй broker family; затем review отдельного label. |
| `RETURN_OF_CAPITAL` | IBKR `brdoc_001...` / `brdoc_003...`: cash distribution с literal `Возврат капитала`. | Не является обычным дивидендом и может менять cost basis/характер выплаты. | `DIVIDEND_INCOME` прямо исключает return of capital; disposal тоже не доказан. | Отдельный методический review; не маскировать как dividend. |
| `STOCK_DISTRIBUTION_EVENT` | IBKR `brdoc_001...`: `Дивиденд в форме акций`; BCS: `Дивидендный сплит`. | Может менять количество и basis без денежного dividend income. | Dividend label требует денежную выплату; purchase не должен ловить бесплатное распределение. | Исследовать минимальную границу stock dividend/split; не создавать широкий `CORPORATE_ACTION`. |
| `TAX_SETTLEMENT_OR_REFUND` | VTB-family `brdoc_044...`: `Уплата/возврат налога за предыдущий год`. | Gate 4 может потребоваться сверка реально уплаченного/возвращённого налога между периодами. | `TAX_WITHHELD` не должен принимать объединённый payment/refund без направления. | Проверить, достаточно ли direction-aware settlement fact; не расширять `TAX_WITHHELD`. |

Ни один кандидат не добавлен в Candidate v1: для каждого ещё отсутствует хотя
бы один из элементов — устойчивая boundary, подтверждённая Gate 4 методика или
достаточная cross-broker coverage.

## 6. Excluded Facts

| Реальный факт | Решение для v1 | Почему |
| --- | --- | --- |
| FX/валютная операция | `EXCLUDED` | Само наличие FX не является одним из девяти нужных source facts; методика налогообложения валютных сделок не входит в доказанную границу. |
| Cash deposit/withdrawal/transfer | `EXCLUDED` | Движение денег само по себе не доказывает доход, расход, purchase или disposal. |
| Position/balance snapshot | `EXCLUDED` | Состояние позиции не является исполненной операцией; использование как event даст ложные покупки/выбытия. |
| Debit/margin interest | `EXCLUDED` | Это charge, а не `INTEREST_INCOME`; отдельная Gate 4 потребность не доказана. |
| Tax calculated/base/payable | `EXCLUDED` | Это расчёт/итог источника, а не факт фактического удержания; Gate 4 не должен принимать его за `TAX_WITHHELD`. |
| Generic printed totals | `EXCLUDED` | Итог раздела не доказывает individual event и может смешивать coupon/dividend или разные комиссии. |
| Договорные и справочные формулировки | `EXCLUDED` | Описание тарифа, договора займа или брокерского обслуживания без event/value не является финансовым фактом клиента. |
| Visual-only unknown PDFs | `UNREVIEWED` | Текстового semantic evidence нет; им не приписывался выдуманный смысл. |

## 7. Conflict Matrix

| Пара/группа | Минимальная граница | Устойчиво различимо? |
| --- | --- | --- |
| `SECURITY_PURCHASE` vs `SECURITY_DISPOSAL` | Явное направление исполненной операции; combined `Покупка/Продажа` без row direction остаётся unclassified. | `YES` |
| purchase/disposal vs РЕПО | Literal/section `РЕПО` запрещает обычные purchase/disposal labels без доказанного самостоятельного выбытия. | `YES`, но РЕПО остаётся missing candidate |
| purchase/disposal vs transfer/corporate action | Нужны consideration/proceeds и event type; position movement недостаточен. | `YES` |
| `DIVIDEND_INCOME` vs `COUPON_INCOME` | Тип инструмента/выплаты и явный paid/credited event. Общий заголовок `купоны и дивиденды` недостаточен. | `YES` |
| `DIVIDEND_INCOME` vs return of capital/stock dividend | Cash dividend literal плюс отсутствие `return of capital`/stock distribution marker. | `YES` |
| `COUPON_INCOME` vs `ACCRUED_COUPON_COMPONENT` | Payment/credit event против НКД в цене покупки/продажи. | `YES` |
| `INTEREST_INCOME` vs `COUPON_INCOME` | Cash-interest section/object против bond coupon payment. | `YES` |
| `INTEREST_INCOME` vs `SECURITIES_LENDING_INCOME` | Объект займа: деньги против явно названных ценных бумаг; generic formula недостаточна. | `YES`, confidence medium |
| `TRANSACTION_CHARGE` vs custody/account service | Связь с конкретной сделкой против account/depo-level service. | `YES` |
| `TRANSACTION_CHARGE` vs `TAX_WITHHELD` | Trade-linked tax/fee против deduction из income/однозначного income section. | `YES` |
| `TAX_WITHHELD` vs tax calculation/payment/refund | Факт withholding и направление против расчёта или объединённой settlement-строки. | `YES` |

Внутри девяти labels нерешённых пересечений не осталось. Generic или
недостаточно контекстные строки должны получать не соседнюю бирку, а отсутствие
бирки.

## 8. KISS и ограничения

- Candidate v1 содержит 9 labels, а не все встреченные финансовые понятия.
- Ни один новый label не добавлен автоматически.
- Sale/redemption и разновидности transaction charges не раздроблены, потому
  что canonical source wording сохраняет нужную детализацию.
- Единственный positive family для securities lending даёт `MEDIUM`, а не
  ложный `HIGH` confidence.
- Пять visual-only документов не превращены в synthetic evidence.
- Corpus validation не является налоговой консультацией и не утверждает
  production dictionary.

## 9. Артефакты

- Privacy-safe raw evidence:
  [BROKER_REPORTS_GATE3_NDFL_CORPUS_EVIDENCE_G3_3V.report.md](BROKER_REPORTS_GATE3_NDFL_CORPUS_EVIDENCE_G3_3V.report.md)
- Чистый словарь для human review:
  [BROKER_REPORTS_GATE3_NDFL_LABEL_DICTIONARY_G3_3V.candidate.md](../../stage2/research/BROKER_REPORTS_GATE3_NDFL_LABEL_DICTIONARY_G3_3V.candidate.md)
- Исходный research G3.3R не заменён и остаётся отдельным provenance artifact.

## 10. Финальный статус

```text
GOAL_G3_3V = PARTIALLY_COMPLETED
CUSTOMER_CORPUS_REVIEW = PARTIAL
ORIGINAL_LABELS_REVIEWED = 10/10
LABEL_DECISIONS = READY_FOR_HUMAN_REVIEW
CONFLICTS = RESOLVED
MISSING_GATE4_FACTS = FOUND_AND_DOCUMENTED
CANDIDATE_V1 = READY_FOR_HUMAN_REVIEW
RAW_EVIDENCE = AVAILABLE
NEXT_STEP_RECOMMENDATION = REVIEW_ONLY
```
