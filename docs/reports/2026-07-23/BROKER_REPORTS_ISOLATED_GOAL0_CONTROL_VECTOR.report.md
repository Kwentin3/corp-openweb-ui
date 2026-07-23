# Broker Reports — изолированный Goal 0: контрольный вектор и границы контекста

Дата: 2026-07-23

Статус: `COMPLETED`

## Результат

Для новой изолированной проверки Gate 1 и Gate 2 повторно использован ранее
запечатанный source-only контрольный вектор. Его целостность и независимость от
новых запусков подтверждены до начала Gate 1:

- вектор содержит ровно три метрики;
- все три метрики относятся к semantic visual table route;
- одна метрика имеет заранее определённую арифметическую сверку;
- hash приватного reference совпадает с hash, записанным в seal;
- source, control-vector, время запечатывания и число метрик совпадают между
  reference и seal;
- в локальном разрешённом корпусе найден ровно один PDF с ожидаемым source hash;
- reference был запечатан 2026-07-22 до workflow execution;
- provider output не использовался как источник истины;
- ожидаемые значения не передавались runtime, VLM или answering LLM.

Названия, значения, суммы, страницы, исходные имена и приватные ссылки в Git не
записаны.

## Авторитет эталона

Контрольный вектор имеет статус `sealed`. Авторитет проверки —
`delegated_agent`; `human_reviewed=false`, `customer_accepted=false`. Поэтому
результаты программы доказывают техническую воспроизводимость относительно
этого запечатанного эталона, но не подменяют пользовательское утверждение
содержания исходного отчёта.

## Контракт `GATE1_ONLY`

В диагностический контекст Gate 1 разрешено включать только нейтральную память
документа: нормализованный текст и таблицы, semantic visual tables, исходные
метки, нейтральные метаданные и provenance.

Запрещены:

- типизированные финансовые факты Gate 2 и их register-проекции;
- Gate 2 answer context и любой смешанный answer context;
- данные Gate 3;
- PDF bytes, crops и provider raw output;
- приватный reference, его метрики и ожидаемые значения.

## Контракт `GATE2_ONLY`

В диагностический контекст Gate 2 разрешено включать только принятые
типизированные source/domain facts и их register-подобные проекции: ownership,
period, currency, unit, sign, value и source references.

Запрещены:

- память, нормализованный текст, таблицы, semantic visual tables и строки Gate 1;
- PDF bytes и crops;
- provider raw output;
- приватный reference и ожидаемые значения;
- Gate 1 answer context, смешанный answer context и данные Gate 3.

## Разделение проверок

Gate 1 и Gate 2 получают один и тот же вопрос к одним и тем же трём метрикам, но
работают с разными разрешёнными представлениями данных. Сравнение ответа с
эталоном выполняется детерминированным comparator только после ответа модели.
Эталон не участвует в сборке prompt или runtime-контекста.

Browser workflow, автоматическая передача результата в чат и Gate 3 находятся
за пределами этой программы и не влияют на технический terminal status Gate 1
или Gate 2.

## Безопасные идентичности

- source document SHA-256:
  `738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57`;
- control vector SHA-256:
  `ea7ad387abd9380a94020fd0d6837cbda12c1ac03a3dcbe85dda96387b27ac5c`;
- private reference SHA-256:
  `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`;
- private seal SHA-256:
  `607000fb3a42ba1cacfd081af29c2b6dbe79ad9d181bfa0a8b4de82a11d6431d`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_ISOLATED_GOAL0_CONTROL_VECTOR.receipt.safe.json).

## Решение

`GOAL_0_CONTROL_VECTOR_AND_ISOLATION: COMPLETED`

Gate 1 разрешено запускать только после принятия этой отдельной ветки в
актуальный `main`.
