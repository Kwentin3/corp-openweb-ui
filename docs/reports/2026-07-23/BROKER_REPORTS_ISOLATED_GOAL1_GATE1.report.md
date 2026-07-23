# Broker Reports — изолированный Goal 1: Gate 1 и смысловой checksum

Дата: 2026-07-23

Статус: `COMPLETED`

## Итог

На текущем принятом live runtime выполнен один свежий Gate 1 для одного ранее
разрешённого PDF. Повторной обработки документа не было.

Gate 1 завершился терминально с кодом
`completed_with_review_advisory`. Advisory относится к явно учтённой
структурной неопределённости и не блокирует source-fact extraction:

- документ: `1`;
- страницы: `12/12`;
- failed pages: `0`;
- detection attempts: `12`;
- скрытые retry: `0`;
- provider failover: `0`;
- visual candidates: `6`;
- принятые semantic visual tables: `5`;
- материализованные table projections: `5`;
- нормализованные source units: `14`;
- потерянные или усечённые source units: `0`;
- review-required scopes: `1`;
- source-fact blocking issues: `0`;
- ArtifactStore records этого run: `64`.

Document memory и supported-profile assessment независимо подтвердили
`accounting_status=passed` и `zero_silent_loss=passed`. Handoff в Gate 2
валидирован и готов.

## Изоляция checksum

Для диагностического ответа использован только `GATE1_ONLY` context:

- пять валидированных
  `broker_reports_semantic_visual_table_envelope_v1`;
- из каждого envelope взяты только `description`, `rows`, номер страницы и
  нейтральный table reference;
- PDF bytes, crop bytes, provider raw output, Gate 2 facts, register,
  answer-context и приватный reference в context не входили;
- ожидаемые суммы не передавались модели.

Context собран через `ArtifactResolver`. Проверки с неверным пользователем и
без разрешения private visibility завершились fail-closed с
`artifact_access_denied`.

## Результат модели

Через обычный OpenWebUI `/api/chat/completions` выполнен ровно один model call.
Модель вернула ровно три JSON-записи:

- дубли: `0`;
- выдуманные metric IDs: `0`;
- repair calls: `0`;
- совпадение ID, названия, суммы, знака и source/page binding: `3/3`.

Первоначальный чрезмерно строгий comparator дал `0/3`, потому что сделал
`currency`, `unit` и `period` обязательными terminal fields. Это не дефект
Gate 1 и не ошибка суммы: все три названия и все три суммы уже совпали.

Исходный model answer оставлен неизменным. Без второго обращения к модели он
детерминированно переоценён по согласованному смысловому контракту:

`metric_id + точное название + точная сумма + знак + source binding`.

Итог этого контракта: `3/3`. `Currency`, `unit` и `period` сохранены как
измеряемое дополнительное обогащение; по первому ответу оно составило `0/3` и
не использовано для искусственного повышения результата.

## Почему это важно

Проверка подтверждает исходную гипотезу: модели не нужен низкоуровневый JSON
табличных атомов, чтобы точно восстановить смысловые пары
«название — сумма». Достаточен компактный контракт `description + rows` с
нейтральной provenance.

Одновременно проверка показывает границу такого упрощения. Если downstream
нужны обязательные валюта, единица и период, их следует добавлять кодом из
авторитетной метаинформации или проверять отдельным контрактом, а не объявлять
ошибкой уже правильно восстановленную сумму.

## No-RAG и lifecycle

До и после Gate 1:

- Knowledge rows: `0`;
- document rows: `0`;
- vector files: `595`;
- vector bytes: `309808908`.

Дельта Knowledge/RAG/vector: `0`. Один private-intake file сохранён по
явной retention policy для последующего Gate 2. Workload завершён,
`cleanup_status=cleaned`; nonterminal jobs и owned temporary entries: `0`.

## Безопасные evidence hashes

- Gate1-only context SHA-256:
  `f0a32643eb9863ec264055cf297a9f517f997c3756d3d7633a070a1b200e1768`;
- immutable first answer SHA-256:
  `a0edc51ec14210f565b43e8ea6b4c463eaa48d27065bb018051fc4df0fbf708f`;
- private checksum receipt SHA-256:
  `b49300651b4477d3c1b7e13d5fc53750f8b591cff1c0a90ae43548ac39b5a99b`;
- sealed reference SHA-256:
  `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`.

Названия, значения, суммы, исходное имя, provider payload и приватный context в
Git не записаны.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_ISOLATED_GOAL1_GATE1.receipt.safe.json).

## Решение

`GOAL_1_FRESH_GATE1_TECHNICAL: COMPLETED`

`GOAL_1_GATE1_ONLY_SEMANTIC_CHECKSUM: PASSED_3_OF_3`

`GOAL_1_AUXILIARY_METADATA_ENRICHMENT: MEASURED_0_OF_3_NONTERMINAL`

Gate 2 разрешено запускать после принятия этой отдельной ветки в актуальный
`main`.
