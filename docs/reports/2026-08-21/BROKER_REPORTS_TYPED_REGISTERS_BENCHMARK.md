# Canonical → Typed Broker Registers Benchmark

Status: `BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN`

## Короткий вывод

Ни один из трёх кандидатов пока не доказал стабильный переход от Canonical к runtime-ready typed broker registers.

Самый содержательный результат дал вариант A: он сохранил source accounting и provenance, правильно удержал сумму налога пустой там, где источник сообщает только сам факт удержания, но его проекция менялась между прогонами и не была достаточно точной для Gate 5.

Вариант B не дошёл до детерминированной материализации: table-schema mapping трижды нарушил закрытый контракт. Вариант C трижды вернул внутренне противоречивый withholding status и был отклонён до материализации. Поэтому объявлять deterministic-first или direct extraction победителем нельзя.

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

## Сравнительный verdict

`BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN`

Почему не выбран B: он не прошёл собственный table-mapping contract ни в одном run, поэтому его предполагаемая deterministic share не была доказана.

Почему не выбран A: он единственный дал валидную проекцию, но три результата различались, а точные downstream-critical roles/types были нестабильны.

Почему не выбран C: большой контекст не дал рабочей проекции и добавил стоимость без доказанной пользы.

На этом GOAL остановлен. Результат не разрешает production activation или замену current Gate 3.

## Evidence

- Safe machine receipt: `BROKER_REPORTS_TYPED_REGISTERS_BENCHMARK.receipt.json`.
- Private frozen plan, source truth, raw accepted outputs and provider responses: вне Git, privacy-scoped evidence directory.
- Harness tests: source accounting, invented literal rejection, withholding-without-amount, deterministic component materialization, idempotency without value-based dedupe, terminal selection and valid provenance supersets.
