# Broker Reports — десять форм задачи для Semantic Compiler

Дата: 2026-08-21

Статус: `TASK_FORM_SEMANTIC_COMPILER_PROVEN`

Режим: frozen research-only. Canonical, current Gate 3–5 и production не менялись.

## Короткий вывод

Проблема была не в том, что модель принципиально не понимает Canonical. Мы давали ей слишком смешанную задачу: понять смысл, выбрать нашу taxonomy, скопировать исходный текст и сразу собрать финансовые records.

Когда эти обязанности разделены, один и тот же frozen Canonical три раза подряд дал:

- 30/30 правильных schema decisions: 3 table types и 27 column roles;
- 2/2 правильных значения `side` через один выбор `purchase_value_ref`;
- 9/9 правильных residual rows;
- 12/12 source dispositions;
- 20/20 exact Gate 5 facts;
- один projection hash во всех трёх end-to-end runs;
- 0 missing, 0 extra и 0 SQL duplicates.

Это не доказательство для любых брокеров и PDF. Это доказательство рабочего task-form pattern на текущем frozen брокерском отчёте.

## Что подсказала внешняя практика

Наш результат не уникальный велосипед:

- AWS Textract отдельно хранит нормализованный `Type`, исходный `LabelDetection` и `ValueDetection`. Это тот же принцип: машинное имя не заменяет source evidence. [AWS Textract response objects](https://docs.aws.amazon.com/textract/latest/dg/expensedocuments.html)
- Google Document AI различает `EXTRACT` — значение взято из документа — и `DERIVE` — значение получено выводом; для extracted entity сохраняется `textAnchor`, а normalized value идёт отдельно. [Google Document model](https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/Document)
- Gemini structured output поддерживает enum в JSON Schema именно для закрытых классификационных решений. [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- Исследование LLM schema matching показывает, что mapping может работать по именам и описаниям схемы без строк данных, а лишний контекст способен ухудшать качество. [Schema Matching with LLMs](https://arxiv.org/abs/2407.11852)
- Magneto разделяет поиск кандидатов и окончательный semantic match, уменьшая стоимость и свободу LLM. На нашем маленьком закрытом каталоге retrieval пока не нужен, но принцип разделения совпадает. [Magneto](https://arxiv.org/abs/2412.08194)
- EVAPORATE отдельно рассматривает schema identification и повторно используемое code extraction. Мы используем более консервативную версию: модель не генерирует код, а только маленький mapping; код принадлежит репозиторию и проверяется тестами. [EVAPORATE](https://arxiv.org/abs/2304.09433)

Не перенесены: fine-tuning, универсальная ontology, embedding-retrieval, синтез regex и ensemble нескольких ответов. Для текущего corpus они не понадобились и добавили бы новые владельцы и риски.

## Frozen условия

- Canonical root: `bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d`;
- 3 логические таблицы;
- 12 выбранных source rows;
- 20 ожидаемых typed facts;
- 75 runtime role values;
- 10 заранее зафиксированных гипотез;
- 3 независимых запуска каждой гипотезы;
- 42 provider calls;
- retry, repair и best-of-N запрещены.

## Результаты десяти гипотез

| ID | Форма задачи | Результат 3/3 | Вывод |
|---|---|---:|---|
| H1 | `header_ref → normalized_role`, одна trade table | 16/16, exact, один hash | Прямой header mapping устойчив |
| H2 | Обратный `normalized_role → header_ref` | 16/16, exact, один hash | Направление mapping несущественно |
| H3 | Все 3 table types + все headers одним ответом | 30/30, exact, один hash | Победитель для schema mapping |
| H4 | Модель копирует оба side literals | 2/2, exact, один hash | Копирование само по себе не было проблемой; ломалась смешанная задача |
| H5 | Модель возвращает два stable value refs | 2/2, exact, один hash | Refs работают без копирования текста |
| H6 | Модель выбирает только purchase ref, второй код выводит сама | 2/2, exact, один hash | Победитель: одна semantic decision вместо двух |
| H7 | Один общий residual batch: codes + spans | 7/9, стабильно неправильно | Общий контракт смешивает разные типы таблиц |
| H8 | Отдельный residual contract на каждый table type | 9/9, exact, один hash | Победитель для residual |
| H9 | Общий residual, только codes без spans | 8/9, стабильно неправильно | Удаление spans не устраняет смысловую ошибку |
| H10 | Source-shaped event + token refs | 0/3 strict-valid | Модель начала изобретать собственные event names; лишний dialect вреден |

### Почему H8 не получил спрятанный правильный ответ

H8 знал только `table_type` и закрытый список допустимых для него codes. Ожидаемый code конкретной строки в model input отсутствовал.

На строке, где H7 и H9 стабильно выбирали `UNMAPPED`, H8 всё ещё разрешал и `UNMAPPED`, и `NOT_RELEVANT`. В отдельном cash-контексте модель три раза выбрала правильный вариант. Значит, помогло разделение разных задач, а не исключение неправильного ответа из enum.

В benchmark H8 requests были заранее сгруппированы frozen truth. Это допустимый контроль, потому что H3 во всех трёх runs независимо вернул те же table types. Подстановка фактического H3 output создаёт идентичную группировку.

## Рабочий pattern

```text
immutable Canonical
  ↓
H3: table types + header refs → normalized roles
  ↓
H6: один purchase_value_ref для бинарной side-колонки
  ↓
deterministic structured-row materialization
  ↓
H8: residual rows, раздельно по table type
  ↓
deterministic BrokerSourceProjection / SQL
  ↓
existing deterministic Gate 5 adapter
```

Модель больше не должна:

- переписывать Canonical;
- переносить числовые значения;
- собирать typed records;
- решать, какая комиссия относится к какой сделке;
- выбирать date, amount и обычную currency;
- придумывать налоговую методологию.

Она решает только:

- что означает структура таблицы;
- какое из двух source values означает покупку;
- какой закрытый смысл выражает остаточный свободный текст;
- какой короткий source span является asset/currency evidence там, где он действительно нужен.

## Почему я раньше видел ситуацию лучше модели

У меня были дополнительные инструменты, которых не было внутри одного inference:

- frozen source truth;
- результаты нескольких запусков;
- детерминированные validators;
- возможность отдельно сравнивать structure, meaning, copied evidence и downstream result.

Поэтому это не было доказательством, что «агент умнее модели». Это было доказательством, что evaluator видел задачу по частям, а runtime prompt заставлял модель решать всё сразу. Новая форма даёт модели те же чёткие границы, которыми пользовался evaluator.

## Semantic surface area

Победивший путь оставляет модели 48 ограниченных решений:

- 3 table type decisions;
- 27 header role decisions;
- 1 side decision;
- 17 residual code/span decisions.

После этого 75 runtime role values и все 20 typed facts собираются кодом с provenance. Для сравнения, direct projection заставлял модель принимать около 107 решений непосредственно над строками и давал только 3/20 exact facts при трёх разных projection hashes.

## Стоимость

Полный исследовательский цикл:

- 42 provider calls;
- 23 181 input tokens;
- 9 599 output tokens;
- суммарно 239 297 ms provider duration;
- денежная стоимость в provider receipt отсутствует.

Это стоимость сравнения десяти гипотез, не будущего runtime.

На новом fingerprint текущего документа рабочий путь требует:

- 1 schema mapping call;
- 1 side call;
- 3 residual calls по типам таблиц.

После exact fingerprint reuse schema mapping и side mapping могут переиспользоваться; останутся только residual calls. Cross-document reuse пока не доказан, поэтому это архитектурная оценка, а не production SLA.

## Ограничения

- Проверен один frozen брокерский отчёт, а не разные брокеры.
- Проверены 3 таблицы и 12 выбранных строк, а не весь возможный BrokerSourceDialect.
- H10 показал, что даже structured schema не всегда удерживает модель от собственной vocabulary; такой ответ должен оставаться fail-closed.
- Exact fingerprint reuse между разными документами ещё не квалифицирован.
- Current Gate 3–5 не заменены, server/product smoke не выполнялся.

## Практический следующий шаг

Не запускать ещё один prompt benchmark. Следующий узкий GOAL — реализовать этот pattern как изолированный research/runtime candidate sidecar:

1. H3 mapping artifact, привязанный к exact Canonical fingerprint;
2. H6 side mapping как отдельная часть schema mapping;
3. H8 residual router с отдельным контрактом каждого table type;
4. deterministic materializer в существующий Gate 4/5 handoff;
5. end-to-end прогон на нескольких других брокерских отчётах до любого production включения.

Машиночитаемый safe receipt: [BROKER_REPORTS_SEMANTIC_TASK_FORMS.receipt.json](./BROKER_REPORTS_SEMANTIC_TASK_FORMS.receipt.json)
