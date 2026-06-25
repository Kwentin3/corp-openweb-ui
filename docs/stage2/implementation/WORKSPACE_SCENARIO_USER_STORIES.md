# Workspace Scenario User Stories

Статус: внутренний skeleton для проектирования сценариев. Не является
утвержденной инструкцией для пользователей или администраторов.

Перед расширением или выбором user stories читать
[Corporate AI Workspace Use Cases Research](../research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md).
Он фиксирует внешнюю фактуру и не создает новые user stories.

## 1. Назначение

`User story` - это короткое описание задачи глазами пользователя:

```text
Как [роль], я хочу [действие], чтобы [результат].
```

В этом документе user stories нужны для Stage 2 planning: понять, какие рабочие
сценарии надо собрать в OpenWebUI, какие prompts и Knowledge понадобятся, что
можно проверить на synthetic data, а что требует заказчика.

`Synthetic data` - искусственные тестовые данные без данных заказчика.
`Acceptance signal` - признак, по которому понятно, что сценарий проверен на
нужном уровне.

Все сценарии ниже - черновики для будущего согласования. Если нужны реальные
группы, документы, регламенты или политика заказчика, это явно отмечено как
`requires customer input`.

## 2. Шаблон user story

Для каждой story использовать:

```text
Название:
Роль:
User story:
Зачем это нужно:
Входные данные:
Ожидаемый результат:
Какие prompts нужны:
Какие Knowledge/инструкции нужны:
Какие synthetic data нужны:
Что можно проверить без заказчика:
Что требует заказчика:
Acceptance signal:
Статус:
```

## 3. Первичный список сценариев

### 3.1. Общий корпоративный AI-чат

Название:

- Общий корпоративный AI-чат.

Роль:

- обычный сотрудник.

User story:

- Как сотрудник, я хочу задавать общие рабочие вопросы в корпоративном AI-чате,
  чтобы быстрее готовить тексты, черновики, резюме и рабочие идеи.

Зачем это нужно:

- это базовый безопасный сценарий, с которого удобно начинать правила,
  prompts, model catalog and data policy.

Входные данные:

- пользовательский запрос;
- утвержденные правила допустимых данных.

Ожидаемый результат:

- понятный ответ или черновик, который пользователь проверяет сам.

Какие prompts нужны:

- общий prompt для делового русского;
- prompt для резюме;
- prompt для письма/сообщения;
- prompt для списка задач.

Какие Knowledge/инструкции нужны:

- краткая инструкция по допустимым данным;
- примеры хороших и запрещенных запросов.

Какие synthetic data нужны:

- analytics_sample_prompts;
- forbidden_query_examples.

Что можно проверить без заказчика:

- видимость модели и prompts по группе;
- базовые ответы на безопасных synthetic prompts;
- отсутствие секретов в инструкциях.

Что требует заказчика:

- реальные группы;
- policy по данным;
- список допустимых сценариев.

Acceptance signal:

- пользователь видит только разрешенный сценарий и получает visible policy
  warning.

Статус:

- draft; ready for documentation.

### 3.2. Транскрибация встречи

Название:

- Транскрибация встречи.

Роль:

- сотрудник или руководитель встречи.

User story:

- Как участник встречи, я хочу загрузить аудио или видео и получить
  расшифровку, чтобы подготовить протокол, решения и follow-up.

Зачем это нужно:

- STT MVP path уже закрыт для текущего этапа; теперь нужны regression,
  hardening and workflow templates.

Входные данные:

- audio/video attachment;
- выбранный шаблон результата.

Ожидаемый результат:

- текст расшифровки и черновик протокола внутри OpenWebUI UX.

Какие prompts нужны:

- протокол встречи;
- решения и ответственные;
- follow-up письмо;
- краткое резюме.

Какие Knowledge/инструкции нужны:

- инструкция по качеству аудио;
- правила хранения транскриптов;
- ограничения по чувствительным данным.

Какие synthetic data нужны:

- fake_meeting_transcript;
- synthetic metadata for short/large media.

Что можно проверить без заказчика:

- documentation checklist;
- synthetic transcript workflow;
- prompts на искусственном тексте.

Что требует заказчика:

- реальные media samples;
- retention policy;
- правила доступа к транскриптам.

Acceptance signal:

- результат появляется в OpenWebUI, API keys не попадают в браузер, а
  production limits documented.

Статус:

- MVP current stage closed; hardening checklist ready to document.

### 3.3. Web Search / исследование

Название:

- Web Search / исследование.

Роль:

- сотрудник, которому нужен поиск по публичным источникам.

User story:

- Как сотрудник, я хочу использовать Web Search для безопасных публичных
  запросов, чтобы собрать источники и получить ответ с понятными ссылками.

Зачем это нужно:

- Web Search технически работает, но production rollout требует правил,
  ограничений, логов и cost visibility.

Входные данные:

- safe public query;
- выбранный provider/path.

Ожидаемый результат:

- candidate set, source visibility and final answer separated where possible.

Какие prompts нужны:

- исследование с источниками;
- сравнение источников;
- ответ "недостаточно данных";
- проверка конфликтующих источников.

Какие Knowledge/инструкции нужны:

- forbidden query examples;
- правила источников и цитирования;
- policy по private/internal data.

Какие synthetic data нужны:

- safe_web_search_queries;
- forbidden_query_examples.

Что можно проверить без заказчика:

- safe query matrix;
- candidate set capture format;
- forbidden examples in docs.

Что требует заказчика:

- rollout scope;
- allowed data classes;
- cost/logging policy;
- решение, global or group-scoped.

Acceptance signal:

- Web Search не используется с private/customer data и не обещается как
  production default без customer decision.

Статус:

- draft; safe matrix ready to document.

### 3.4. Анализ простого PDF/DOCX

Название:

- Анализ простого PDF/DOCX.

Роль:

- сотрудник, который готовит краткий разбор простого документа.

User story:

- Как сотрудник, я хочу загрузить простой PDF или DOCX и получить краткий
  структурированный разбор, чтобы быстрее понять содержание.

Зачем это нужно:

- простые документы можно проверить отдельно от production OCR pipeline.

Входные данные:

- simple text PDF или structured DOCX.

Ожидаемый результат:

- краткое резюме, список ключевых пунктов and visible limitations.

Какие prompts нужны:

- краткий разбор документа;
- таблица фактов;
- вопросы для ручной проверки.

Какие Knowledge/инструкции нужны:

- правила работы с файлами;
- предупреждение, что результат требует проверки человеком.

Какие synthetic data нужны:

- simple_text_pdf;
- structured_docx_with_table.

Что можно проверить без заказчика:

- upload mechanics;
- extraction preview;
- prompt behavior on synthetic docs.

Что требует заказчика:

- реальные документы и expected outputs.

Acceptance signal:

- synthetic proof confirms mechanics only, not production quality.

Статус:

- draft; ready after synthetic data index.

### 3.5. Анализ простой XLSX-таблицы

Название:

- Анализ простой XLSX-таблицы.

Роль:

- сотрудник, который работает с простой таблицей.

User story:

- Как сотрудник, я хочу загрузить простую XLSX-таблицу и получить обзор строк,
  колонок и явных значений, чтобы быстро понять структуру файла.

Зачем это нужно:

- нужно отделить простую таблицу от сложного Excel с формулами, сводными
  таблицами, внешними ссылками and macros.

Входные данные:

- simple_xlsx_table.

Ожидаемый результат:

- обзор структуры и ограничений без обещания точных расчетов.

Какие prompts нужны:

- описание структуры таблицы;
- список возможных вопросов к данным;
- warning про формулы и сложные Excel cases.

Какие Knowledge/инструкции нужны:

- ограничения XLSX;
- human review rule.

Какие synthetic data нужны:

- simple_xlsx_table;
- complex_xlsx_placeholder.

Что можно проверить без заказчика:

- upload and basic extraction mechanics.

Что требует заказчика:

- реальные XLSX examples and expected outputs.

Acceptance signal:

- complex Excel не считается accepted на synthetic simple table.

Статус:

- draft; ready after synthetic data index.

### 3.6. OCR / VL OCR pilot

Название:

- OCR / VL OCR pilot.

Роль:

- инженер/методолог, который оценивает candidates для распознавания документов.

User story:

- Как инженер Stage 2, я хочу сравнить OCR/VL OCR candidates на одинаковых
  тестах, чтобы выбрать безопасный pilot path для документов.

Зачем это нужно:

- VL OCR не должен считаться полностью заблокированным до customer samples:
  research и synthetic benchmark можно начать отдельно.

Входные данные:

- synthetic scans and fake table-like documents;
- candidate list.

Ожидаемый результат:

- shortlist и benchmark notes.

Какие prompts нужны:

- extract text;
- extract table;
- classify document type;
- report uncertainty.

Какие Knowledge/инструкции нужны:

- criteria for Russian text, layout, tables, privacy, cost and latency.

Какие synthetic data нужны:

- fake_scan_pdf;
- fake_invoice_or_act;
- fake_contract;
- fake_broker_report.

Что можно проверить без заказчика:

- benchmark mechanics and candidate shortlist on synthetic data.

Что требует заказчика:

- реальные scans, provider/data approval and expected good output.

Acceptance signal:

- synthetic benchmark selected candidates, but customer pilot remains blocked.

Статус:

- draft; ready for research/benchmark.

### 3.7. Брокерский отчет / 3-НДФЛ

Название:

- Брокерский отчет / 3-НДФЛ.

Роль:

- специалист, который готовит черновой разбор финансового документа.

User story:

- Как специалист, я хочу получить черновой разбор брокерского отчета, чтобы
  быстрее подготовить материал для ручной проверки.

Зачем это нужно:

- это приоритетный customer scenario, но качество нельзя принимать на
  выдуманных документах.

Входные данные:

- requires customer input for real broker reports;
- synthetic fake_broker_report only for mechanics.

Ожидаемый результат:

- draft analysis with strong manual-review warning.

Какие prompts нужны:

- извлечение видимых фактов;
- список вопросов к документу;
- предупреждение "не налоговая консультация".

Какие Knowledge/инструкции нужны:

- policy по финансовым данным;
- human review rule.

Какие synthetic data нужны:

- fake_broker_report;
- fake_invoice_or_act.

Что можно проверить без заказчика:

- prompt shape and warning mechanics on fake data.

Что требует заказчика:

- реальные anonymized reports;
- example good result;
- policy for financial/customer data.

Acceptance signal:

- no production acceptance without customer documents and human review.

Статус:

- draft; customer acceptance blocked.

### 3.8. Usage analytics / отчет по использованию

Название:

- Usage analytics / отчет по использованию.

Роль:

- администратор или владелец сервиса.

User story:

- Как администратор, я хочу видеть использование по пользователям, периодам и
  моделям, чтобы понимать нагрузку и примерную стоимость.

Зачем это нужно:

- PRD-1 требует basic analytics/cost visibility, но hard billing является
  отдельным решением.

Входные данные:

- synthetic usage events;
- provider price catalog draft.

Ожидаемый результат:

- отчет по пользователю, дню/неделе, модели, токенам, сообщениям и примерной
  стоимости.

Какие prompts нужны:

- не обязательно; нужны report fields and proof plan.

Какие Knowledge/инструкции нужны:

- price catalog notes;
- analytics limitations.

Какие synthetic data нужны:

- analytics_sample_prompts.

Что можно проверить без заказчика:

- proof plan and synthetic usage shape.

Что требует заказчика:

- required reporting granularity;
- нужна ли групповая детализация;
- hard billing decision.

Acceptance signal:

- native analytics gap или sufficiency documented.

Статус:

- draft; next independent proof.

### 3.9. Админское управление сценариями

Название:

- Админское управление сценариями.

Роль:

- администратор OpenWebUI или AI-методолог.

User story:

- Как администратор, я хочу управлять сценариями, группами, prompts и
  Knowledge, чтобы пользователи работали по согласованным правилам.

Зачем это нужно:

- Stage 2 должен быть управляемым, а не набором случайных prompts and models.

Входные данные:

- scenario skeletons;
- group matrix;
- data policy.

Ожидаемый результат:

- draft checklist for scenario setup and change process.

Какие prompts нужны:

- prompts for each scenario, not for admin control itself.

Какие Knowledge/инструкции нужны:

- admin checklist;
- owner/change process;
- rollback/defer conditions.

Какие synthetic data нужны:

- simple docs, prompts and Knowledge examples.

Что можно проверить без заказчика:

- draft workflow;
- synthetic configuration-first proof plan.

Что требует заказчика:

- actual owners, groups and policy decisions.

Acceptance signal:

- admin workflow remains configuration-first where native OpenWebUI supports it.

Статус:

- draft; ready after user stories and synthetic data.

## 4. Ссылки

- [Stage 2 Unblocked Work Plan](STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [OpenWebUI Native Capability Audit](OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Engineering Backlog](../ENGINEERING_BACKLOG.md)
