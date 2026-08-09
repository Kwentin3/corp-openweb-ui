# Broker Reports Gate 5 — Tax Methodology Boundary Research / Audit G5.1

**GOAL_STATUS:** `ACHIEVED — RESEARCH BOUNDARY CLOSED; IMPLEMENTATION NOT AUTHORIZED`

**Дата проверки источников:** 2026-08-09

**Объект:** российский НДФЛ / подготовка данных для 3-НДФЛ по брокерским отчетам

**Режим:** research-only; без изменения Gate 1–4, runtime, схем, БД и product route

> Это архитектурно-методический аудит, а не персональная налоговая консультация.
> Для расчета конкретного налогоплательщика нужны его налоговый период,
> статус, документы и применимая на этот период редакция законодательства.

## 1. Решение

Простая граница

```text
Financial Case -> Tax Methodology -> Tax Model
```

**недостаточна**. Gate 4 дает проверенные финансовые факты и provenance, но не
владеет налоговым периодом и статусом налогоплательщика, идентичностью и
налоговой категорией инструмента, историей лотов, убытками прошлых лет,
доказательствами иностранного налога, справочными курсами и версией нормы.

Минимальная доказанная граница:

```text
Gate4 Financial Case
+ Tax Context
+ Supplemental Tax Inputs
+ Reference Snapshot
        |
        v
Versioned Tax Methodology
        |
        v
ordinary deterministic calculator
        |
        v
Tax Model + scoped issues + end-to-end provenance
```

Ключевые выводы:

1. Единственный разрешенный upstream-вход Gate 5 остается
   `Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()`.
2. Gate 5 не должен читать broker source, `CanonicalArtifactV1`, Gate 3 targets
   или физические SQL-таблицы Gate 4.
3. `CASE_COMPLETE_FOR_CURRENT_INPUT_SET` и `role_complete` — технические
   утверждения, не налоговая полнота и не доказательство возможности расчета.
4. Версионируемый артефакт Tax Methodology нужен. Он должен владеть только
   применимостью и смыслом норм; арифметика остается обычным кодом.
5. Универсальный Tax Engine, rules DSL, relation engine, graph DB, новый
   Repository/DB, RAG, runtime LLM и DTO декларации на этой границе не нужны.
6. Есть блокирующие upstream-пробелы. Самый узкий и сильный —
   `ACCRUED_COUPON_COMPONENT`: сейчас у него есть только `amount` и `currency`,
   чего недостаточно для связи НКД с приобретением, купоном или выбытием.

## 2. Scope и доказательная база

### 2.1. В scope

- все девять текущих `financial_type`;
- пять уже зафиксированных missing candidates;
- текущая публичная read boundary Gate 4;
- минимальные внешние налоговые inputs и reference data;
- граница между Tax Methodology, deterministic code и Tax Model;
- Tax Dependency Matrix, Upstream Gap Register, KISS review;
- один следующий разрешенный исследовательский шаг.

### 2.2. Вне scope

- production-код и контракт Gate 5;
- изменение Gate 1–4, dictionary, Role Pack, runtime или SQL;
- FIFO/cost-basis implementation;
- расчет конкретного физического лица;
- формирование или отправка 3-НДФЛ;
- обработка customer/private bytes или provider/LLM-вызовы;
- утверждение исчерпывающей налоговой методологии для всех видов активов.

### 2.3. Текущие repository authorities

- [Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md)
  — единственный authority по gate numbering и статусу.
- [Gate 4 -> Gate 5 Handoff v1](../../stage2/contracts/BROKER_REPORTS_GATE4_HANDOFF.v1.md)
  — официальный read boundary.
- [Gate 4 Financial Case Fact v1](../../stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md)
  — форма и provenance факта.
- [Gate 4 Case Assembly v1](../../stage2/contracts/BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md)
  — смысл текущего source set и технической completeness.
- [Gate 4 SQL Materialization v1](../../stage2/contracts/BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md)
  — SQL как удаляемый, неавторитетный cache.
- [Gate 3 Handoff v1](../../stage2/contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md)
  — запрет переносить tax/FIFO meaning upstream.
- [Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
  — карта единственных владельцев.
- [Financial label dictionary](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json)
  и [Role Pack](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.v1.json)
  — текущие девять типов и доступные роли.
- [G3.3V corpus validation](../2026-08-07/BROKER_REPORTS_GATE3_NDFL_DICTIONARY_CORPUS_VALIDATION_G3_3V.report.md)
  — privacy-safe evidence пяти missing candidates. Это evidence, не authority.

## 3. Неподвижная upstream-граница

Gate 5 получает runtime только так:

```python
Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()
```

Разрешенные публичные чтения:

```text
read_case
list_facts
get_fact
list_by_financial_type
list_by_asset
list_by_period
```

Доступно: immutable fact identity, authenticated case binding, financial type,
typed role values, missing roles, fact status и точный provenance до Gate 3 и
активного canonical artifact.

Недоступно и не должно восстанавливаться обходом:

- исходный broker report и его format-specific смысл;
- Gate 3 target grammar;
- subtype/relations, которых нет в Gate 4 fact;
- физическая схема SQL;
- сведения о налогоплательщике и других брокерах вне current source set;
- нормативные и справочные данные.

`asset` и `currency` в текущем materializer только нормализуются как непустые
строки. Это не стабильный instrument identity, не юрисдикция эмитента и не
налоговая классификация бумаги.

## 4. Минимальные налоговые зависимости

### 4.1. Tax Context — обязателен на case scope

| Поле | Зачем нужно | Владелец |
|---|---|---|
| `tax_period` | Выбор применимой редакции норм, ставок, курса и периода агрегации | caller / trusted tax context |
| `taxpayer_residency_status` | Определяет охват российских и иностранных источников и применимые ставки | caller, подтвержденный фактами периода |
| `special_taxpayer_statuses[]` | Только применимые статусы, меняющие правила; например, специальный режим для иноагента с 2026 года | caller / authoritative external evidence |
| `calculation_scope` | Явно отличает current input set от полного годового расчета по человеку | Gate 5 request contract |

Налоговое резидентство устанавливается за соответствующий период, а не
выводится из broker report. Налоговый период НДФЛ — календарный год.

### 4.2. Supplemental Tax Inputs — только по необходимости

| Input | Когда обязателен | Почему Gate 4 не владеет им |
|---|---|---|
| stable instrument identity и tax classification | продажа, погашение, купон, НКД, корпоративное действие | `asset` — source string; нет статуса organized/non-organized, вида бумаги, issuer/source jurisdiction |
| acquisition/opening lot history | disposal, redemption, FIFO, перенос позиции между брокерами | current case не доказывает полную историю приобретений |
| direct expense attribution | комиссии, custody, margin/debit interest | нет relation к покупке/продаже, категории и лоту |
| prior-year eligible losses и подтверждение | уменьшение соответствующей базы | это внешний переносимый остаток, не факт текущего broker report |
| foreign income/tax evidence | зачет налога у иностранного источника | `TAX_WITHHELD` не содержит вида дохода, страны, proof и связи с доходом |
| corporate-action legal characterization | return of capital, stock distribution, split | source label не определяет российское налоговое последствие |
| external tax payments/refunds | только если нужен settlement по человеку | могут отсутствовать в брокерском current source set |

Социальные, имущественные и иные общие вычеты не нужны для интерпретации
broker facts. Они потребуются только более позднему расчету общей обязанности
или декларации. Минимальный Gate 5 не должен заявлять общий payable/refund без
полного внешнего контекста.

### 4.3. Reference Snapshot

Минимальный reference snapshot должен быть воспроизводимым и содержать:

- официальные курсы Банка России по валюте и дате признания дохода/расхода;
- идентификатор и hash редакции Tax Methodology;
- effective dates применимых норм и rate schedule;
- использованную instrument classification и источник ее доказательства;
- применимый treaty/foreign-tax-credit status, если заявлен зачет.

Дневные значения курса, instrument registry и treaty facts — данные snapshot,
а не содержимое Tax Methodology.

## 5. Tax Dependency Matrix — девять текущих типов

Легенда sufficiency:

- `PARTIAL` — из Gate 4 можно получить часть налогового элемента, но не
  завершить безопасный расчет;
- `BLOCKED` — доступных ролей недостаточно даже для однозначной применимости
  специальной нормы;
- `CONDITIONAL` — расчет возможен только в доказанном узком subtype/scope.

| `financial_type` | Налоговый смысл и минимальное правило | Нужные данные сверх текущих ролей | Gate 4 sufficiency | Решение |
|---|---|---|---|---|
| `SECURITY_PURCHASE` | Само приобретение обычно не создает текущую базу; формирует lot/cost basis для последующего выбытия. Фактические прямые расходы могут входить в стоимость | stable instrument ID, tax category, связь прямых charges, полная lot history | `PARTIAL` | Создать cost-basis input, не налог/расход периода сам по себе |
| `SECURITY_DISPOSAL` | Доход от продажи/погашения минус допустимые расходы; расходы распределяются по применимой категории. Для частичного погашения нужна отдельная пропорция | subtype `sale/full redemption/partial redemption/other compensated disposal`, instrument class, matched lots, charges | `PARTIAL`; `BLOCKED` для partial redemption | Не считать subtype из source literal в Gate 5; требовать явную семантику |
| `DIVIDEND_INCOME` | Отдельный дивидендный доход; расходы по сделкам с бумагами его не уменьшают. Для иностранного дивиденда возможен зачет только при выполнении условий и наличии документов | issuer/source country, gross-vs-net, linked withholding, payment evidence, treaty status | `PARTIAL` | Gross income можно признать только если семантика amount доказана; credit отдельно |
| `COUPON_INCOME` | Денежный купон по бумаге. Для первого купона после приобретения может быть важен уплаченный при покупке НКД | stable instrument ID, coupon event identity, lot/purchase link, linked accrued coupon | `PARTIAL` | Без связи с НКД считать только неподтвержденный gross candidate, не итоговую базу |
| `INTEREST_INCOME` | Правило зависит от источника: банковский вклад, заем, broker cash balance и иной процент — не одна налоговая методика | source/legal type, payer jurisdiction, agreement/account context, gross-vs-net | `PARTIAL` | Текущий label финансово полезен, но слишком широк как tax discriminator |
| `SECURITIES_LENDING_INCOME` | Специальная методика ст. 214.4 НК РФ по совокупности договоров займа; важны роли lender/borrower, проценты, передача/возврат и valuation | agreement identity, taxpayer role, security identity, loan/return dates, market/calculated price, substitute issuer payments | `BLOCKED` | `date/amount/currency[/asset]` недостаточно для специальной нормы |
| `ACCRUED_COUPON_COMPONENT` | НКД — компонент цены/расхода и связи с купонным доходом, а не самостоятельный универсальный доход или расход | date, asset, purchase/disposal direction, exact transaction/lot link | `BLOCKED` | Главный upstream-блокер; использовать amount отдельно запрещено |
| `TRANSACTION_CHARGE` | Документированный прямой расход может учитываться при приобретении, реализации, хранении или погашении. Нужна атрибуция | expense subtype, purchase/disposal/other direction, exact fact/lot/category link, documentability | `PARTIAL`; часто `BLOCKED` для allocation | Не создавать generic relation engine; достаточно точной typed attribution |
| `TAX_WITHHELD` | Не доход и не расход сделки; кандидат на уплаченный/удержанный налог или foreign tax credit | linked income, domestic/foreign nature, country, tax kind, period/date, proof, gross income | `BLOCKED` для зачета/settlement | Хранить как credit candidate; не вычитать автоматически из базы или налога |

### 5.1. Что можно вычислять даже при частично заблокированном case

Gate 5 не нужен один глобальный флаг «case tax-ready». Допустимы scoped results:

- подтвержденная рублевая сумма отдельного дохода при известной tax category;
- подтвержденный disposal proceeds без утверждения итогового cost basis;
- отдельная база по полной категории, только если все требуемые inputs этой
  категории представлены;
- issue на конкретный fact, allocation, category или весь scope.

Нельзя выдавать итоговый годовой налог, если неизвестны другие брокеры,
соответствующие категории убытков, opening lots или применимые credits.

## 6. Tax Dependency Matrix — пять missing candidates

| Candidate | Налоговая релевантность | Минимальная семантика | Где пробел | Решение |
|---|---|---|---|---|
| `REPO_EVENT` | Высокая: для РЕПО действует специальная ст. 214.3 НК РФ; две части нельзя превращать в обычные purchase/disposal | agreement/event ID, first/second part, dates, securities, prices/amounts, taxpayer side, execution/adjustments | upstream type отсутствует | Нужен отдельный узкий upstream contract slice до расчета таких операций |
| `SECURITIES_CUSTODY_CHARGE` | Потенциально допустимый документированный расход на хранение/профессиональные услуги | date, amount/currency, service subtype, period, instrument/category attribution, document evidence | current dictionary намеренно исключает custody из transaction charge | Зарегистрировать upstream gap; не маскировать как trade commission |
| `RETURN_OF_CAPITAL` | Может менять basis или иметь иной характер выплаты; универсальное правило по одному тексту недоказуемо | issuer/country, corporate-action legal type, cash/non-cash, amount, quantity/basis effect, source documents | отсутствует type и authoritative characterization | `AMBIGUOUS_SEMANTICS`; human/legal evidence required |
| `STOCK_DISTRIBUTION_EVENT` | Split может только менять quantity/basis, stock dividend может иметь иной режим; объединять нельзя | subtype `split/stock dividend/other`, instrument mapping before/after, ratio, issuer/country, legal documents | отсутствует type и subtype | Не создавать широкий `CORPORATE_ACTION`; исследовать только встретившиеся subtypes |
| `TAX_SETTLEMENT_OR_REFUND` | Влияет на tax paid/credited/returned и межпериодный settlement, но не на financial result сделки | direction `payment/refund`, tax kind, jurisdiction, tax period, payment/refund date, linked assessment/income | current combined source wording не дает direction | Нужен direction-aware fact или trusted supplemental input |

Corpus evidence остается частичным: пять visual-only документов не получили
synthetic meaning. Поэтому матрица признает найденные candidates реальными, но
не утверждает полноту corpus taxonomy.

## 7. Excluded и смежные классы

| Класс | Налоговая оценка | Boundary decision |
|---|---|---|
| FX conversion / currency trade | Конвертация security income/expense в рубли требует курса ЦБ, но самостоятельное выбытие иностранной валюты — другой имущественный сценарий | Не включать в минимальную securities-методику; при наличии ставить `UNSUPPORTED_RULE`, а не игнорировать |
| cash deposit/withdrawal/transfer | Обычно не доход/расход сам по себе, но может доказывать перенос активов и отсутствие нового приобретения | Не превращать в tax item; использовать только как supplemental continuity evidence |
| positions/balances | Не налоговое событие, но opening position сигнализирует о недостающей истории лотов | Не использовать как cost basis; ставить issue о missing opening lots |
| debit/margin interest | Может быть допустимым расходом в установленных законом пределах при прямой связи с операциями | Отдельный зарегистрированный upstream gap; не смешивать с `INTEREST_INCOME` |
| tax calculated/base/payable | Производный результат или non-authoritative broker reference | Не принимать как authority; можно сравнивать после собственного расчета |
| generic totals | Не имеют event semantics и provenance достаточной гранулярности | Не использовать вместо фактов |

## 8. Separate Upstream Gap Register

`Deferrable` означает: другие независимые категории можно рассчитывать, но
затронутый scope должен fail closed.

| ID | Пробел | Затронуто | Blocking scope | Deferrable | Минимальное исправление, не реализация |
|---|---|---|---|---|---|
| `UG-01` | У НКД только `amount`, `currency`; нет даты, бумаги, направления и transaction link | coupon, bond purchase/disposal basis | каждый факт/лот с НКД | **Нет** для корректного bond scope | Расширить upstream semantic contract ровно этими связями |
| `UG-02` | Charge не связан с purchase/disposal/holding и tax category | acquisition cost, disposal expense, custody | allocation/category | Да | Typed attribution к точному факту/лоту и expense subtype |
| `UG-03` | Disposal не различает partial redemption | cost-basis allocation | соответствующее погашение | Да | Узкий disposal subtype; не новый общий event hierarchy |
| `UG-04` | Withholding не связан с income/source/jurisdiction/proof | domestic withholding, foreign credit | credit/settlement | Да | Direction/source-aware tax attribution |
| `UG-05` | Securities lending не содержит contract roles и lifecycle | ст. 214.4 calculation | весь lending scope | Да | Минимальный lending event contract по required legal inputs |
| `UG-06` | Нет `REPO_EVENT` | ст. 214.3 calculation | весь REPO scope | Да | Отдельные две части и agreement identity |
| `UG-07` | Нет custody charge | allowable expense | затронутая category | Да | Отдельный narrow fact; не расширять trade charge |
| `UG-08` | Return of capital и stock distribution отсутствуют и неоднозначны | basis/income/quantity | corporate-action event | Да | Разделить только доказанные subtypes и приложить legal characterization |
| `UG-09` | Settlement/refund не имеет direction и period | paid/refunded tax | settlement | Да | Direction-aware fact или supplemental evidence |
| `UG-10` | Debit/margin interest исключен | allowable expense | linked securities category | Да | Отдельный expense subtype с loan and limit inputs |

Stable instrument identity, opening lots, prior losses, residency и treaty
status не следует проталкивать в broker parsing. Это правильные supplemental
или reference inputs Gate 5. Upstream gap существует только там, где сам broker
event уже распознан, но его финансовая семантика недостаточна для безопасной
передачи.

## 9. Versioned Tax Methodology

### 9.1. Что это такое

Минимальный immutable, reviewable artifact, выбираемый по tax period и effective
date. Он нужен потому, что правила и ставки изменяются, а уже опубликованный
результат должен быть воспроизводим. Официально опубликованные изменения 2024,
2025 и 2026 годов подтверждают, что привязка только к «текущему коду» опасна;
часть изменений 425-ФЗ имеет отдельные будущие даты вступления в силу.

### 9.2. Чем он владеет

- `methodology_id`, semantic version, content hash, publication status;
- `effective_from`, `effective_to`, supported tax periods;
- stable `rule_id` и ссылка на статью/пункт/официальный источник;
- applicability predicates по tax context и tax category;
- требуемые semantic inputs и stop/ambiguity conditions;
- правила category grouping/netting и переноса соответствующих убытков;
- политика FIFO/cost allocation и применения НКД как нормативный смысл;
- rate bands и foreign-tax-credit eligibility/cap meaning;
- обязательный human review before publication.

### 9.3. Чем он не владеет

- broker/source parsing и label synonyms;
- taxpayer data и customer documents;
- циклы FIFO, decimal arithmetic, grouping implementation;
- формульный DSL или исполняемый произвольный код;
- дневные курсы ЦБ, instrument registry и treaty database;
- Gate 4 relations или SQL;
- поля формы 3-НДФЛ;
- LLM prompt и provider output.

Обычный deterministic calculator владеет валидацией decimal/date, выборкой
предварительно опубликованного rule set, конвертацией, FIFO iteration,
allocation, aggregation, rounding и созданием issues. Методика определяет
**что и когда применимо**, код — **как детерминированно посчитать**.

Runtime LLM не может быть владельцем правила, ставки, classification или
итогового расчета. Возможная будущая подсказка модели должна оставаться
неавторитетным proposal и не входит в минимальную границу.

## 10. Минимальный Tax Model — proposal, не контракт

Ниже не новая схема, а проверка достаточности будущей границы. Каждый блок
существует только при доказанной налоговой необходимости.

| Блок | Минимальное содержание | Почему нужен |
|---|---|---|
| `methodology_binding` | id, version, hash, effective tax period | воспроизводимость нормы |
| `scope` | tax period, taxpayer status, calculation scope, current-input-set assertion | не смешивать частичный case с годовым результатом |
| `tax_items[]` | kind `income/expense/basis/credit_candidate`, category, source amount/currency/date, RUB value, rule and provenance | единица налогового смысла без копии Gate 4 fact |
| `allocations[]` | только реальные lot/NKD/expense allocations | доказуемый cost basis без generic relation layer |
| `bases[]` | category, income, allowable expense, current/prior loss applied, base | закон требует расчета по соответствующим категориям |
| `tax_calculations[]` | rate band application и tax amount | детерминированный результат |
| `tax_credits[]` | withheld/paid candidate, eligibility, cap, applied amount или rejection reason | credit не равен expense |
| `issues[]` | code, scope, blocking, required input, reason, rule/provenance | честный partial/blocked outcome |
| `settlement` | только при полном внешнем контексте | не обещать payable/refund из broker facts |

Tax Model не должен дублировать source literal, role schema или весь Gate 4
fact. Он ссылается на `fact_id` и сохраняет обратимую provenance chain:

```text
tax result
-> methodology version + rule_id
-> calculation/allocation
-> Gate 4 fact_id(s)
-> supplemental/reference snapshot item(s)
-> existing Gate 4 upstream provenance
```

## 11. Readiness и ошибки

Минимальная outcome taxonomy без persisted workflow:

| Outcome | Смысл |
|---|---|
| `CALCULABLE` | Все inputs правила для этого scope доказаны |
| `PARTIALLY_CALCULABLE` | Есть независимые calculable результаты и отдельные blocked scopes |
| `BLOCKED_MISSING_INPUT` | Известно, какого обязательного input не хватает |
| `AMBIGUOUS_SEMANTICS` | Доступные факты допускают разные налоговые трактовки |
| `UNSUPPORTED_RULE` | Событие распознано, но опубликованной методики для него нет |

Issue должен быть привязан к `fact_id`, allocation/category или case scope.
Отсутствие одного input не должно уничтожать независимый calculable result, но
scope-wide отсутствие tax period, taxpayer status или опубликованной методики
блокирует весь расчет.

Не нужны event sourcing, статусы согласования, generic workflow engine и второй
case registry. Readiness каждый раз выводится из immutable inputs и выбранной
методики.

## 12. KISS review

| Предложение | Нужно сейчас | Решение |
|---|---:|---|
| Versioned Tax Methodology artifact | **Да** | Единственная новая semantic authority; минимальная и immutable |
| Обычный deterministic calculator | Позже, после контракта | Не Tax Engine и не framework |
| Универсальный Tax Engine | Нет | Нет доказанного множества независимых engines |
| Generic rules DSL | Нет | Усложняет review, безопасность и отладку |
| Generic relation engine | Нет | Нужны несколько typed allocations/attributions |
| Graph DB | Нет | Текущие связи малы и детерминированы |
| Новый Repository или отдельная БД | Нет | Gate 4 runtime и существующая artifact discipline достаточны |
| RAG / embeddings | Нет | Нормативные правила должны быть опубликованы и версионированы |
| Runtime LLM как rule owner | Нет | Невоспроизводимо и неавторитетно |
| Generic workflow/state engine | Нет | Outcomes выводятся детерминированно |
| Universal tax ontology | Нет | Только доказанные securities/3-НДФЛ concepts |
| Declaration DTO | Нет | Декларация — более поздняя boundary, не Tax Model |

## 13. Официальные источники и актуальность

Проверено 2026-08-09. При расхождении приоритет имеют действующая редакция НК
РФ и официально опубликованный акт на дату конкретного налогового периода.
Страницы ФНС используются как официальные пояснения; архивные страницы не
используются для фиксации текущих числовых ставок.

1. [ФНС: особенности определения налоговой базы по операциям с ценными бумагами](https://www.nalog.gov.ru/rn78/ifns/imns78_07/info/11815510/)
   — доходы/расходы, категории операций, рублевая конвертация и иностранные
   ценные бумаги.
2. [ФНС: доходы из зарубежных источников необходимо декларировать, публикация 2026 года](https://www.nalog.gov.ru/rn04/news/activities_fts/16626509/)
   — дивиденды, проценты и реализация/погашение иностранных финансовых активов.
3. [ФНС: иностранные доходы и зачет иностранного налога](https://www.nalog.gov.ru/rn21/taxation/taxes/ndfl/14642672/)
   — зависимость зачета от применимого международного договора.
4. [Письмо ФНС БС-4-11/20298@](https://www.nalog.gov.ru/rn77/about_fts/about_nalog/10300559/)
   и [приложенное письмо Минфина 03-04-07/106247](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/docs/minfin/minfin106247_031220.pdf)
   — для зачета нужны документы о виде/сумме/годе дохода, сумме и дате уплаты
   налога; при withholding — помесячные сведения и документ источника выплаты.
5. [ФНС: операции займа ценными бумагами](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/ndfl_fl/nb_ndfl/)
   — отдельная методика ст. 214.4, договорные роли, проценты, даты передачи и
   возврата, valuation. Страница давняя, поэтому числовые параметры должны
   браться из версии методики для периода, а не копироваться с нее.
6. [ФНС: перенос убытков по ценным бумагам](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/nv_ubit/)
   — соответствующие категории, срок переноса и документальное подтверждение.
7. [ФНС: решение по агрегации операций разных брокеров](https://www.nalog.gov.ru/rn77/service/complaint_decision/13156345/)
   — итог по соответствующей категории нельзя выводить из одного брокера, если
   в scope есть операции у других.
8. [ФНС: проценты по банковским вкладам](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/ndfl_fl/onb_ndfl/)
   — отдельная методика подтверждает, что общий `INTEREST_INCOME` не является
   достаточным tax discriminator.
9. [ФНС: налоговое резидентство физического лица](https://www.nalog.gov.ru/rn77/ip/interest/reg_ip/resident_rf/)
   — residency является внешним фактом соответствующего периода.
10. [ФНС: НДФЛ и актуальные ставки](https://www.nalog.gov.ru/rn20/taxation/taxes/ndfl/)
    и [ФНС: ставки для отдельных налоговых баз с 2025 года](https://www.nalog.gov.ru/rn77/news/tax_doc_news/15562179/).
11. [Банк России: официальная база курсов валют](https://www.cbr.ru/currency_base/)
    — официальный источник курса по дате; опубликованные на сайте сведения не
    требуют отдельного письменного подтверждения.
12. [Федеральный закон от 31.07.2023 № 389-ФЗ](https://publication.pravo.gov.ru/document/0001202307310002?index=1&pageSize=100)
    — официально опубликованные изменения, затрагивающие в том числе НКД.
13. [Федеральный закон от 12.07.2024 № 176-ФЗ](https://publication.pravo.gov.ru/document/0001202407120009?index=1&pageSize=100)
    — официально опубликованная налоговая реформа и ставки с 2025 года.
14. [Федеральный закон от 28.11.2025 № 425-ФЗ](https://publication.pravo.gov.ru/Document/View/0001202511280017)
    — изменения с разными датами вступления в силу, включая будущие правила;
    это прямое основание версионировать методику.
15. [Федеральный закон от 25.04.2026 № 104-ФЗ](https://publication.pravo.gov.ru/document/0001202604250003)
    — официально опубликованные изменения части второй НК РФ в 2026 году.
16. [ФНС: НДФЛ по купонам и результату реализации/погашения облигаций](https://www.nalog.gov.ru/rn28/news/activities_fts/16548710/)
    — подтверждает раздельную роль купона и финансового результата по бумаге.

Для проверки точной структуры действующей на дату аудита ст. 214.1, 214.3 и
214.4 использовалась также консолидированная справочная редакция. Она не
заменяет официальное опубликование и не является runtime-источником методики:
[ст. 214.1](https://www.consultant.ru/document/cons_doc_LAW_28165/d5ddddc549f21e5c4a826cda7cb4efd57a1cff46/),
[ст. 214.3](https://www.consultant.ru/document/cons_doc_LAW_28165/6936762c6b4f4e1a50aec68fd04b808ec7436883/),
[ст. 214.4](https://www.consultant.ru/document/cons_doc_LAW_28165/aaa73af97561e3aec66b3f6bb094a2811c9a4bd2/).

## 14. Acceptance accounting

| Требование | Результат |
|---|---|
| Все 9 текущих типов | `COVERED` в разделе 5 |
| Все 5 missing candidates | `COVERED` в разделе 6 |
| Current official Russian sources | `COVERED`, проверены 2026-08-09 |
| Tax Dependency Matrix | `COVERED` |
| Separate Upstream Gap Register | `COVERED` |
| Minimal boundary | `PROVEN` |
| KISS review | `PASSED` |
| Production/runtime changes | `NONE` |
| Private data/provider calls | `NONE` |

Ограничение: аудит не доказывает полноту всех возможных налоговых событий и не
закрывает G5 design. Он определяет минимальную границу, называет calculable и
blocked scopes и не превращает кандидаты corpus в принятые financial types.

## 15. NEXT GOAL

**G5.2 — ACCRUED_COUPON_COMPONENT tax-sufficiency upstream gap.**

Research/contract-only slice: определить минимальное совместимое расширение
Gate 3/Gate 4 semantic handoff для НКД — `date`, stable asset reference,
`purchase/disposal` direction и exact transaction/lot link — без реализации
Gate 5, без общей relation model и без изменения остальных зарегистрированных
пробелов.
