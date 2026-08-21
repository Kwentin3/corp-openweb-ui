# Canonical → Typed Broker Registers Benchmark

Status: `BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN`

## Короткий вывод

Ни один из трёх кандидатов пока не доказал стабильный переход от Canonical к runtime-ready typed broker registers.

Самый содержательный результат дал вариант A: он сохранил source accounting и provenance, правильно удержал сумму налога пустой там, где источник сообщает только сам факт удержания, но его проекция менялась между прогонами и не была достаточно точной для Gate 5.

Вариант B не дошёл до детерминированной материализации: table-schema mapping трижды нарушил закрытый контракт. Вариант C трижды вернул внутренне противоречивый withholding status и был отклонён до материализации. Поэтому объявлять deterministic-first или direct extraction победителем нельзя.

## Зафиксированная граница после обсуждения

Canonical уже нормализован физически: в нём есть logical tables, headers, rows, cells, порядок и provenance. Но это ещё не нормализация финансового смысла названий.

Canonical остаётся неизменяемым источником правды. Исходные названия вроде `Сумма`, `Комиссия Брокера` или `НКД` нельзя заменять нормализованными именами внутри Canonical: значение такого заголовка зависит от таблицы, а ошибочная замена загрязнит source authority.

Нормализация нейминга должна быть отдельным проверяемым контрактом:

```text
Canonical
↓
Canonical Table Schema Mapping
↓
Typed Broker Source Registers
↓
deterministic runtime
```

Минимальная запись mapping должна одновременно сохранять:

- исходный header literal;
- нормализованную column role;
- точный Canonical `source_ref`;
- статус `CONFIRMED`, `UNMAPPED` или `CONFLICT`;
- identity/version схемы, на которой mapping был подтверждён.

Mapping не является новым источником истины и не изменяет Canonical. Его можно отклонить или заменить целиком. Неизвестная либо изменившаяся структура должна fail closed.

Ручной профиль под каждого брокера не принимается как целевая архитектура: он быстро превратится в набор исключений для брокера, версии и года отчёта. При этом автоматически подтверждённый mapping для точного schema fingerprint остаётся допустимой исследовательской гипотезой, если он не применяется к изменившейся форме документа.

## Что было заморожено

- Canonical root: `bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d`.
- Один и тот же model, schema и settings внутри каждого варианта.
- Три независимых прогона.
- Без semantic retry, repair, best-of-N и ручной правки model output.
- Current Gate 3 взят только из уже сохранённых трёх прогонов.
- Production, current Gate 3, Gate 4 и Gate 5 не изменялись.

Ручная source truth была зафиксирована до новых model calls и хранится вне Git.

## Проверенный срез

12 настоящих source rows из трёх logical tables, 20 ожидаемых typed records:

- обычная строка брокерской комиссии;
- cash movement без названного downstream consumer;
- общий cash total;
- продажа с НКД и двумя комиссиями;
- покупка с нулевым НКД, нулевой брокерской и ненулевой биржевой комиссией;
- continuation trade row на следующей странице без повторного заголовка;
- trade totals с двумя самостоятельными commission totals;
- обычные купоны;
- две compound coupon/tax строки;
- две похожие купонные строки, которые нельзя дедуплицировать по близким значениям.

## Минимальный BrokerSourceDialect_v0

Dialect выведен из фактических consumers Gate 5 и существующего source-fact contract:

- `SECURITY_PURCHASE`;
- `SECURITY_DISPOSAL`;
- `COUPON_INCOME`;
- `ACCRUED_COUPON_COMPONENT`;
- `TRANSACTION_CHARGE`;
- `COMMISSION`;
- `COMMISSION_TOTAL`;
- `TAX_WITHHELD`;
- `TAX_WITHHELD_TOTAL`.

Роли ограничены существующими source roles: `date`, `asset`, `quantity`, `unit_price`, `amount`, `currency`.

Типы налоговой методологии в dialect не включены. Универсальная ontology, DSL и broker-specific regex не создавались.

## Контракт стенда

Каждая входная source row обязана получить ровно один disposition:

- `MATERIALIZED`;
- `NOT_RELEVANT`;
- `UNMAPPED`;
- `FAILED`.

Каждая materialized роль содержит literal fragment и ссылку на конкретную Canonical cell. Валидатор отклоняет invented literal, чужую cell, потерянную source row, повторную роль и недопустимый тип.

Typed record ID строится из версии Canonical, logical table, source row, record type и конкретных source cells. Одинаковые дата, сумма или бумага не используются для дедупликации.

SQLite использован только как rebuildable runtime projection. Двукратная материализация одной проекции проверяется на отсутствие новых записей; SQL не является authority.

## Результаты

| Вариант | Valid runs | Repeatability | Source accounting | Exact field fidelity | Результат |
| --- | ---: | --- | --- | --- | --- |
| A — structural direct | 3/3 | нет, 3 разных hash | 12/12 во всех runs | 3/20 exact records во всех runs | структурно валиден, семантически недостаточен |
| B — deterministic-first | 0/3 | не доказана | не достигнуто | не достигнуто | table mapping трижды отклонён |
| C — large-context direct | 0/3 | не доказана | не достигнуто | не достигнуто | трижды отклонён по withholding contract |
| Current Gate 3 baseline | frozen 3/3 | нет | не имеет обязательного row accounting | type matches 13/20, 11/20, 10/20 | слабее целевого контракта |

Вариант A создал 18, 20 и 18 typed records. Provider input был одинаковым, но projection hashes различались.

Для A подтверждены:

- 100% source accounting;
- все literals действительно присутствуют в указанных Canonical cells;
- все typed IDs уникальны;
- повторная запись той же projection не создаёт SQL duplicates;
- compound rows во всех трёх runs сохранили `TAX_WITHHELD` как stated-without-amount без выдуманной суммы.

Но A не прошёл по смыслу:

- пять комиссий внутри trade rows во всех runs стали `COMMISSION`, а не `TRANSACTION_CHARGE`; Gate 5 теряет доказанную same-row связь для direct disposal expense;
- два commission totals появились только в одном из трёх runs;
- один cash movement менял disposition;
- в третьем run у всех coupon records исчезла роль `asset`;
- asset literal часто оставался слишком широким source wording вместо точной идентичности бумаги.

## Ручной аудит source → typed record

Ручной просмотр Canonical и сохранённых projections подтвердил машинные метрики.

Положительные находки:

- физическая таблица сделок уже содержит достаточно структуры для детерминированного чтения колонок;
- continuation row корректно адресуется через Canonical и может использовать frozen header context;
- source accounting и field provenance технически обеспечиваются простым закрытым контрактом;
- compound coupon/tax не требует выдумывать сумму удержания: `withholding_stated=true`, amount отсутствует;
- одинаковые или похожие source observations остаются отдельными благодаря source identity.

Неустранённые проблемы:

- LLM всё ещё нестабильно выбирает source-level type для trade charges и totals;
- table mapping сам по себе пока не оказался более надёжной semantic границей;
- large context не исправил проблему и не прошёл даже внутреннюю валидацию;
- существующий Gate 5 требует точный `asset` для купона и точный `TRANSACTION_CHARGE` для same-row расходов; A этого стабильно не обеспечивает.

У rejected B/C runs сохранён terminal/error class, но ранняя версия harness не сохранила raw rejected model output. Это ограничение evidence: причины контрактного отказа известны, детальный offending object — нет. Harness исправлен для будущего запуска, но повторные calls ради восстановления этого raw evidence не делались.

## Downstream sufficiency

Gate 5 пока не может работать только через полученную projection.

Причина не в SQL и не в Canonical. Не хватает стабильной source semantics на двух конкретных границах:

- trade-row commission должна оставаться `TRANSACTION_CHARGE` с той же Canonical row;
- coupon должен стабильно сохранять точную роль `asset`.

`TAX_WITHHELD` без отдельной суммы корректно остаётся role-incomplete и должен fail closed дальше по конвейеру. Это сохранение источника, а не дефект projection.

## Следующие проверяемые гипотезы

Предыдущий вариант B не доказывает, что сама идея schema mapping неверна. Он проверял слишком широкий переход: несколько видов таблиц, mapping, последующую materialization и residual extraction в одном benchmark route. Следующие проверки должны разделить эти решения.

### H1 — Header-only schema mapping

LLM получает одну logical table, её заголовки и минимальный structural context. Она не видит задачу извлечения строк и не создаёт financial records. Результат ограничен типом таблицы и соответствием `source header → normalized column role`.

Гипотеза подтверждается только если один и тот же mapping повторяется независимо, все ссылки ведут в Canonical, неизвестные колонки остаются `UNMAPPED`, а continuation table получает ту же схему без догадки по значениям строк.

### H2 — Deterministic row materialization after frozen mapping

После подтверждённого mapping обычный код переносит все строки и значения. LLM больше не выбирает даты, суммы, валюты, количество или source refs.

Проверяется, какая доля trade records, НКД и колонковых комиссий получается без LLM; сохраняются ли нулевые и повторяющиеся observations; остаются ли source accounting и idempotency точными.

### H3 — Closed semantic residuals

LLM получает только поля, где смысл действительно записан свободным текстом: например, описание cash movement или compound coupon/tax. Она выбирает закрытый набор source types и при необходимости exact literal span бумаги. Код привязывает date, amount и currency из уже mapped columns.

Проверяется отдельно от H1/H2: repeatability типов, точность asset span, compound cardinality и запрет invented amount. Если residual contract нестабилен, детерминированная часть не считается неуспешной вместе с ним.

### H4 — Reusable schema fingerprint, не broker profile

Успешный mapping можно повторно использовать только при точном совпадении структурного fingerprint: набор и порядок headers, column count, table identity и continuation contract. Любое изменение создаёт новый `UNMAPPED` случай.

Гипотеза должна сравниваться с ручными broker profiles по maintenance cost и на holdout-формах. Если для каждого отчёта всё равно требуется новая ручная настройка, подход отклоняется как казуистический.

### H5 — Direct LLM extraction как frozen comparator

Structural direct extraction остаётся контрольным вариантом. Его prompt не улучшается по результатам holdout. Он нужен, чтобы проверить, действительно ли разбиение H1–H3 уменьшает стоимость и нестабильность, а не только добавляет код.

### Общее условие сравнения

Все гипотезы должны проверяться на одинаковых Canonical source records и затем на нескольких формах реальных брокерских отчётов. Сравниваются:

- exact repeatability;
- source accounting и provenance;
- downstream-critical field fidelity;
- доля полностью детерминированной materialization;
- semantic residual rate;
- устойчивость к continuation tables и изменению формы;
- количество специальных правил и ручных профилей;
- provider calls, tokens и runtime complexity;
- способность обнаружить неизвестную схему и остановиться.

Ни одна гипотеза заранее не объявлена победителем. Production остаётся неизменным до отдельного доказанного terminal.

## Сравнительный verdict

`BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN`

Почему не выбран B: он не прошёл собственный table-mapping contract ни в одном run, поэтому его предполагаемая deterministic share не была доказана.

Почему не выбран A: он единственный дал валидную проекцию, но три результата различались, а точные downstream-critical roles/types были нестабильны.

Почему не выбран C: большой контекст не дал рабочей проекции и добавил стоимость без доказанной пользы.

Закрытый benchmark GOAL остановлен на этом terminal. Добавленные гипотезы описывают следующий research scope, но не разрешают production activation или замену current Gate 3.

## Evidence

- Safe machine receipt: `BROKER_REPORTS_TYPED_REGISTERS_BENCHMARK.receipt.json`.
- Private frozen plan, source truth, raw accepted outputs and provider responses: вне Git, privacy-scoped evidence directory.
- Harness tests: source accounting, invented literal rejection, withholding-without-amount, deterministic component materialization, idempotency without value-based dedupe, terminal selection and valid provenance supersets.
