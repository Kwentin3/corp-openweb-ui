# Broker Reports — Transferable Semantic Layer

Дата: 2026-08-21

Статус: research-only; production не изменён

Verdict: `TRANSFERABLE_WITH_EXPLICIT_BOUNDARIES`

## Короткий ответ

Минимальный переносимый слой найден. Это не новая финансовая ontology и не
профиль брокера. Его форма:

```text
immutable Canonical
→ Source Observation (одна реальная строка/наблюдение источника)
→ schema-local fields (role + исходный header/ref)
→ маленькая deterministic runtime binding
→ существующие Gate 5 source facts
```

Главная поправка к прошлой гипотезе: semantic role не является уникальным
именем колонки. Две валюты, две комиссии и две даты остаются разными source
fields. Их различает исходный заголовок и собственный `source_field_id`, а не
глобальные имена `currency_1/currency_2`.

Полной квалификации без оговорок пока нет. Обычные таблицы сделок прошли новый
контракт. РЕПО, неизвестные операции и недоказанные межстраничные продолжения
сохраняются, но останавливаются как `RELEVANT_UNMAPPED`. Смешанный денежный
журнал ещё не доведён до Gate 5 целиком.

## Что фактически проверено

Новых model calls не было. Пересчитаны сохранённые development и holdout
результаты. Retry, repair и best-of-N не использовались.

Старый holdout H3 был отклонён только старым запретом повторяющихся ролей. Под
новым контрактом взят хронологически первый сохранённый валидный ответ, а не
лучший из нескольких. Он естественно представил:

- 2 currency fields;
- 2 commission fields;
- 2 settlement-date fields;
- все остальные source columns без потери адресов.

На holdout код собрал 15 обычных сделок и 19 отдельных ненулевых комиссионных
компонентов. РЕПО и три выбранных строки mixed cash journal не были ошибочно
превращены в обычные сделки или отброшены.

## Итоговые метрики

| Метрика | Результат | Точная граница |
| --- | ---: | --- |
| Source records accounted | **36/36 = 100%** | 12 development + 24 выбранных holdout records |
| Runtime values deterministic | **241/241 = 100%** | каждое emitted value — exact Canonical literal или доказуемый substring по source ref |
| Source records requiring row-level LLM work | **12/36 = 33.33%** | фактически сохранённые residual tasks; schema mapping амортизирован на fingerprint |
| Gate 5 required facts supplied | **35/35 = 100%** | 20 development facts + 15 primary holdout trade facts внутри квалифицированной границы |
| Новые broker/year special rules или profiles | **0** | ни брокер, ни год не участвуют в contract или reuse key |

Дополнительные 19 holdout commission facts материализованы и полностью связаны
с source, но не добавлены в знаменатель `35/35`: для них в старом holdout не
было независимо frozen fact-level truth. Поэтому они являются положительным
runtime evidence, но не повышают score.

Физическая сохранность полного holdout остаётся прежней: 14 270/14 270
адресуемых Canonical targets, потеря 0, технические дубли 0.

## Почему именно этот контракт

Проверены четыре формы.

| Кандидат | Решение |
| --- | --- |
| Flat dialect, одна role на таблицу | Отброшен: не выражает реальный источник |
| Generic EAV без consumer binding | Отброшен: source сохраняет, но Gate 5 ничего не получает |
| Глобальная event ontology | Отброшена: будет расти под каждый новый отчёт |
| Source Observation + local fields + runtime binding | Выбран: source truth отдельно, consumer needs отдельно |

У каждого слоя один владелец смысла:

- Canonical владеет исходными literals и source refs и не меняется;
- Observation владеет идентичностью строки, section/perspective и explicit
  event key, если он есть в источнике;
- schema-local field владеет связью `column → broad role` и исходным qualifier;
- runtime binding выбирает только те source fields, которые нужны конкретному
  Gate 5 fact;
- Gate 5 не читает PDF, Canonical или model output и не восстанавливает смысл.

## Повторяющиеся роли и дубли

Повторяющиеся роли больше не конфликтуют. Для валюты сделки runtime binding
принимается только когда связь с `gross_amount` однозначна; в проверенном
holdout это ровно одна соседняя source currency. При двух возможных связях
compiler останавливается.

Две комиссии не склеиваются: каждая ненулевая source cell становится отдельным
`TRANSACTION_CHARGE` с собственным provenance.

Две строки с одинаковыми значениями сохраняют разные `observation_id`, потому
что identity включает Canonical row/source refs. Value-based dedupe запрещён.
Explicit trade/event key хранится как дополнительная связь, но не заменяет
source observation identity.

## Mixed tables и LLM surface

Гипотеза `unique operation literal → closed meaning` подтверждена только как
правильный масштаб задачи: в реальном журнале 122 строки и 8 уникальных
operation literals, то есть потенциально 6.56% decision-equivalent вместо 122
row calls.

Это ещё не end-to-end qualification. Сохранённый H8 дважды назвал релевантные
купон/налог `NOT_RELEVANT`. Новый контракт не принимает такую потерю: эти строки
остаются `RELEVANT_UNMAPPED`. До runtime score они не допускаются.

## Structural lineage

Связь частей таблицы на разных страницах не относится к финансовой семантике.
Если continuation нельзя доказать по структуре, semantic compiler не имеет
права «склеить» её сам.

Правильная граница — отдельный immutable `LINK` sidecar над Canonical. Он должен
сохранять обе физические таблицы и их geometry. В этом исследовании новый
lineage runtime не квалифицирован, поэтому недоказанные continuation остаются
явной границей verdict.

## Детерминизм и fail-closed

- development projection: один hash в 3/3 сохранённых runs, 20/20 facts;
- holdout replay: один deterministic projection, 15/15 primary trade facts;
- safe receipt два последовательных раза получил один SHA-256;
- exact source/header accounting обязателен;
- перестановка header refs отклоняется;
- неоднозначная связь currency с amount отклоняется;
- неизвестное становится `RELEVANT_UNMAPPED`, а не `NOT_RELEVANT`;
- production и legacy не участвовали.

## Архитектурный ответ

`BrokerObservationDialect_v1` как большая новая сущность не нужен. Нужен
маленький source-shaped contract и отдельная consumer binding. Это переносимый
паттерн для самостоятельно читаемых таблиц с доказанной структурой.

Граница честная: мы не утверждаем поддержку всех broker report semantics.
Сейчас квалифицирован обычный trade path; mixed operations, РЕПО и multi-page
lineage остаются сохранёнными и fail-closed, а не замаскированными под успех.

Машиночитаемое подтверждение:
[BROKER_REPORTS_TRANSFERABLE_SEMANTIC_LAYER.receipt.json](./BROKER_REPORTS_TRANSFERABLE_SEMANTIC_LAYER.receipt.json)
