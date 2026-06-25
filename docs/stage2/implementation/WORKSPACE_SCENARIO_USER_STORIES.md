# Workspace Scenario User Stories

Статус: внутренний draft для проектирования Stage 2 сценариев. Это не
утвержденная инструкция для пользователей или администраторов, не proof-plan и
не production scope.

Research base:

- [Corporate AI Workspace Use Cases Research](../research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Stage 2 Scenario Shortlist](STAGE2_SCENARIO_SHORTLIST.md)
- [Corporate AI Use Case Research Report](../../reports/2026-06-25/OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md)

## 1. Назначение

`User story` - это короткое описание задачи глазами пользователя:

```text
Как [роль], я хочу [действие], чтобы [результат].
```

В этом документе user stories нужны для Stage 2 planning: понять, какие рабочие
сценарии надо собрать в OpenWebUI, какие prompts/templates и Knowledge
понадобятся, что можно описывать на synthetic data, а что требует заказчика.

`Synthetic data` - искусственные тестовые данные без данных заказчика.
`Knowledge` - база знаний или набор подключенных материалов. `RAG` - поиск
ответа с опорой на документы. `VL OCR` - распознавание документа через
зрительно-языковую модель. `Analytics` - статистика использования.

Все stories ниже - draft для последующего отбора и proof. Они не создают
synthetic files, не создают prompts/Knowledge в OpenWebUI и не меняют runtime.

## 2. Выбранный shortlist сценариев

Shortlist - короткий список сценариев-кандидатов. Первый shortlist выбран из
research и зафиксирован отдельно в
[STAGE2_SCENARIO_SHORTLIST.md](STAGE2_SCENARIO_SHORTLIST.md).

| # | Scenario | Status |
| - | -------- | ------ |
| 1 | Общий управляемый AI-чат | Можно двигать сейчас как draft. |
| 2 | Встречи / транскрибация / action items | Можно двигать сейчас на fake transcript; production acceptance требует media/consent policy. |
| 3 | Внутренний Knowledge / RAG | Можно двигать механику на synthetic Knowledge; real Knowledge требует заказчика. |
| 4 | PDF/DOCX document assistant | Можно двигать simple mechanics; реальные документы customer-blocked. |
| 5 | Web Search / внешние исследования | Можно двигать safe public query stories; rollout customer-blocked. |
| 6 | Usage analytics / отчет по токенам | Можно двигать report-shape stories; hard billing future. |
| 7 | OCR / VL OCR candidate benchmark | Можно описывать candidate story; real OCR pilot customer-blocked. |

Не в первом shortlist, но остаются важными: broker reports / 3-НДФЛ, customer
support, sales/marketing, HR/onboarding, Dev/IT support, hard billing/gateway,
complex Excel parser, production OCR/layout pipeline, full data
masking/tokenization, full AD lifecycle / SCIM, deep OpenWebUI fork and
autonomous agent actions in 1C/CRM.

## 3. Корзины

### Basket A. Можно двигать сейчас без заказчика

- user stories ниже;
- prompt/template catalog draft;
- synthetic meeting transcript prompt flow;
- synthetic Knowledge mechanics;
- simple PDF/DOCX mechanics;
- safe Web Search query matrix;
- usage analytics report shape;
- OCR/VL OCR candidate-comparison story.

### Basket B. Нужен заказчик

- реальные группы, роли, владельцы сценариев;
- реальная Knowledge base and access rules;
- реальные broker reports / 3-НДФЛ and expected output;
- реальные scans, PDF tables, XLSX and OCR samples;
- real meeting media and consent policy;
- provider/data policy;
- Web Search rollout policy;
- no-delete, retention and manager visibility policy;
- hard billing requirement.

### Basket C. Отложить / future slice

- hard billing/gateway;
- complex Excel parser;
- production OCR/layout pipeline;
- full data masking/tokenization;
- full AD lifecycle / SCIM;
- deep OpenWebUI fork;
- production DOCX/XLSX generation;
- autonomous agent actions in 1C/CRM.

## 4. Формат user story

```text
ID:
Название:
Сценарий:
Роль:
User story:
Зачем это нужно:
Входные данные:
Ожидаемый результат:
Какие prompts/templates нужны:
Какие Knowledge/инструкции нужны:
Какие данные можно заменить synthetic data:
Что можно проверить без заказчика:
Что требует заказчика:
Основные риски:
Ограничения:
Acceptance signal:
Статус:
```

## 5. Первые draft user stories

### ST2-US-001. Краткое резюме рабочего текста

```text
ID: ST2-US-001
Название: Краткое резюме рабочего текста
Сценарий: Общий управляемый AI-чат
Роль: сотрудник
User story: Как сотрудник, я хочу вставить рабочий текст и получить краткое резюме, чтобы быстрее понять суть и подготовить черновик ответа.
Зачем это нужно: Это базовый безопасный сценарий для controlled workspace, общего prompt style and data policy.
Входные данные: Текст без запрещенных данных, выбранный рабочий workspace, правила допустимых данных.
Ожидаемый результат: Краткое резюме, список ключевых пунктов и напоминание, что ответ нужно проверить.
Какие prompts/templates нужны: "краткое резюме", "ключевые пункты", "черновик ответа", "проверить тон".
Какие Knowledge/инструкции нужны: Инструкция по допустимым данным, примеры безопасных и запрещенных запросов.
Какие данные можно заменить synthetic data: Любой рабочий текст можно заменить искусственным текстом без имен, реквизитов и private URLs.
Что можно проверить без заказчика: Prompt behavior, warning text, видимость scenario/prompt для тестовой группы.
Что требует заказчика: Реальные группы, approved data policy, список допустимых типов рабочих текстов.
Основные риски: Утечка чувствительных данных, ложная уверенность в резюме, использование внешних AI вне правил.
Ограничения: Не использовать customer secrets, персональные данные, договоры или финансовые данные без policy.
Acceptance signal: Пользователь получает краткое резюме и видит понятное предупреждение о допустимых данных.
Статус: Draft; можно двигать сейчас без заказчика как сценарий и template.
```

### ST2-US-002. Предупреждение о чувствительных данных

```text
ID: ST2-US-002
Название: Предупреждение о чувствительных данных
Сценарий: Общий управляемый AI-чат
Роль: сотрудник
User story: Как сотрудник, я хочу видеть короткое правило перед вводом чувствительных данных, чтобы не отправить в чат запрещенную информацию.
Зачем это нужно: Stage 2 должен управлять безопасностью сценария, а не только давать модель.
Входные данные: Запрос пользователя, draft data policy, примеры allowed/prohibited data.
Ожидаемый результат: Короткое понятное предупреждение и подсказка, как обезличить ввод вручную.
Какие prompts/templates нужны: "data policy warning", "safe rewrite request", "reject unsafe input".
Какие Knowledge/инструкции нужны: Draft allowed/prohibited matrix, provider class notes, examples of safe input.
Какие данные можно заменить synthetic data: Примеры запрещенных запросов можно делать искусственными и явно маркировать как synthetic.
Что можно проверить без заказчика: Текст предупреждения, category examples, отказ от обработки явно запрещенного synthetic input.
Что требует заказчика: Финальное утверждение allowed/prohibited data and provider classes.
Основные риски: Слишком мягкое предупреждение, обещание автоматического masking, неясные правила для пользователя.
Ограничения: Не обещать DLP, автоматическую подмену данных или гарантированную защиту.
Acceptance signal: В сценарии явно есть предупреждение и нет обещания автоматического data masking.
Статус: Draft; можно двигать сейчас как policy/template text.
```

### ST2-US-003. Резюме встречи и action items

```text
ID: ST2-US-003
Название: Резюме встречи и action items
Сценарий: Встречи / транскрибация / action items
Роль: участник встречи
User story: Как участник встречи, я хочу получить резюме, решения и action items из расшифровки, чтобы быстро подготовить протокол.
Зачем это нужно: Meeting assistant повторяется в enterprise research и совпадает с Stage 2 STT track.
Входные данные: Transcript встречи, тема, список участников, выбранный template результата.
Ожидаемый результат: Краткое резюме, решения, задачи, ответственные и вопросы без ответа.
Какие prompts/templates нужны: "meeting summary", "decisions", "action items", "unresolved questions".
Какие Knowledge/инструкции нужны: Правила качества аудио, правила хранения transcript, предупреждение о manual review.
Какие данные можно заменить synthetic data: Реальный transcript заменить fake_meeting_transcript.
Что можно проверить без заказчика: Форму результата и prompt behavior на fake transcript.
Что требует заказчика: Реальные media samples, consent policy, retention policy, access rules for transcript.
Основные риски: Неверное резюме, персональные данные, запись без согласия, неправильное хранение transcript.
Ограничения: Summary не является source of truth; спорные решения проверяет человек.
Acceptance signal: На fake transcript story формирует резюме, решения и задачи с visible manual-review warning.
Статус: Draft; можно двигать сейчас без runtime.
```

### ST2-US-004. Follow-up письмо после встречи

```text
ID: ST2-US-004
Название: Follow-up письмо после встречи
Сценарий: Встречи / транскрибация / action items
Роль: руководитель встречи
User story: Как руководитель встречи, я хочу получить черновик follow-up письма по transcript, чтобы быстро отправить участникам согласованные следующие шаги.
Зачем это нужно: Это естественное продолжение STT: transcript становится рабочим материалом, а не просто текстом.
Входные данные: Transcript, список участников, decisions/action items из предыдущего шага.
Ожидаемый результат: Черновик письма с коротким summary, задачами и сроками.
Какие prompts/templates нужны: "follow-up email", "formal tone", "short action list".
Какие Knowledge/инструкции нужны: Правила делового стиля, data policy, retention/access policy для transcript.
Какие данные можно заменить synthetic data: Fake transcript, synthetic participants, fake decisions.
Что можно проверить без заказчика: Форму письма и отделение фактов от предположений.
Что требует заказчика: Реальные правила коммуникации, доступ к transcript, consent/retention.
Основные риски: AI добавляет несуществующие договоренности, путает ответственных, раскрывает sensitive discussion.
Ограничения: Письмо отправляет человек после проверки; автоматическая отправка не входит.
Acceptance signal: Draft follow-up не содержит новых фактов сверх transcript and action list.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-005. Ответ по внутренней базе знаний с источниками

```text
ID: ST2-US-005
Название: Ответ по внутренней базе знаний с источниками
Сценарий: Внутренний Knowledge / RAG
Роль: сотрудник
User story: Как сотрудник, я хочу задать вопрос по внутренней инструкции и получить ответ со ссылкой на источник, чтобы не искать документ вручную.
Зачем это нужно: Knowledge/RAG - один из главных enterprise patterns и core fit для Stage 2 workspaces.
Входные данные: Вопрос пользователя, synthetic Knowledge pack или approved Knowledge, access group.
Ожидаемый результат: Ответ, источник, краткая цитата/ссылка и отметка, если источник недостаточен.
Какие prompts/templates нужны: "answer with sources", "quote source", "say insufficient data".
Какие Knowledge/инструкции нужны: Curated Knowledge, source attribution rules, refresh/ownership notes.
Какие данные можно заменить synthetic data: Internal policy можно заменить synthetic policy document.
Что можно проверить без заказчика: Source attribution shape, no-source behavior, group visibility mechanics.
Что требует заказчика: Реальные документы, владельцы Knowledge, права доступа, refresh policy.
Основные риски: Устаревшие документы, oversharing, prompt injection in docs, unsupported answer without source.
Ограничения: Не строить "RAG по всем документам компании" как обязательный Stage 2 output.
Acceptance signal: Ответ содержит источник или честно говорит, что источника недостаточно.
Статус: Draft; можно двигать сейчас на synthetic Knowledge.
```

### ST2-US-006. Отказ от ответа без надежного источника

```text
ID: ST2-US-006
Название: Отказ от ответа без надежного источника
Сценарий: Внутренний Knowledge / RAG
Роль: сотрудник
User story: Как сотрудник, я хочу видеть явный отказ или уточняющий вопрос, если в Knowledge нет надежного ответа, чтобы не принять выдуманный ответ за правило компании.
Зачем это нужно: Research фиксирует опасную иллюзию "RAG решает знания автоматически".
Входные данные: Вопрос вне synthetic Knowledge, неполный документ или конфликтующие источники.
Ожидаемый результат: Ответ "недостаточно данных", список недостающих источников или уточняющий вопрос.
Какие prompts/templates нужны: "no reliable source", "ask clarification", "conflicting sources".
Какие Knowledge/инструкции нужны: Source quality rules, no-answer policy, escalation guidance.
Какие данные можно заменить synthetic data: Неполные и конфликтующие synthetic docs.
Что можно проверить без заказчика: Поведение при missing source and conflicting source.
Что требует заказчика: Правила эскалации и владельцы документов.
Основные риски: Hallucination, устаревшее правило, неверная ссылка, пользователь игнорирует warning.
Ограничения: Не обещать юридически или операционно обязательный ответ без owner review.
Acceptance signal: Сценарий предпочитает отказ или уточнение неподтвержденному ответу.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-007. Краткий разбор простого PDF/DOCX

```text
ID: ST2-US-007
Название: Краткий разбор простого PDF/DOCX
Сценарий: PDF/DOCX document assistant
Роль: сотрудник
User story: Как сотрудник, я хочу загрузить простой PDF или DOCX и получить структурированный разбор, чтобы быстрее понять содержание документа.
Зачем это нужно: PRD-1 требует базовую работу с документами, но без обещания production OCR/layout pipeline.
Входные данные: Simple text PDF или structured DOCX without customer data.
Ожидаемый результат: Summary, ключевые пункты, вопросы для ручной проверки, visible limitations.
Какие prompts/templates нужны: "document summary", "key facts", "questions for review", "limitations".
Какие Knowledge/инструкции нужны: File-handling rules, extraction-preview guidance, manual-review warning.
Какие данные можно заменить synthetic data: simple_text_pdf, structured_docx_with_table.
Что можно проверить без заказчика: Upload/extraction mechanics shape and prompt output on synthetic docs.
Что требует заказчика: Реальные документы, expected outputs, allowed provider class.
Основные риски: Неполное извлечение, потеря структуры, hallucinated conclusions, sensitive document leakage.
Ограничения: Только draft analysis; не юридическая, налоговая или финансовая гарантия.
Acceptance signal: Synthetic document gives structured draft and clearly marks limitations.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-008. Список рисков и вопросов по документу

```text
ID: ST2-US-008
Название: Список рисков и вопросов по документу
Сценарий: PDF/DOCX document assistant
Роль: менеджер или специалист
User story: Как менеджер, я хочу получить список возможных рисков и вопросов по документу, чтобы быстрее передать его на ручную проверку.
Зачем это нужно: Документальный сценарий должен помогать review, но не заменять специалиста.
Входные данные: Synthetic contract/document, краткий контекст задачи, rules for draft-only output.
Ожидаемый результат: Список пунктов для проверки, нерешенные вопросы, предупреждение о human review.
Какие prompts/templates нужны: "review questions", "risk checklist", "uncertain fields".
Какие Knowledge/инструкции нужны: Manual-review rule, safe document data policy, allowed document classes.
Какие данные можно заменить synthetic data: fake_contract, fake_invoice_or_act.
Что можно проверить без заказчика: Checklist shape and warning behavior.
Что требует заказчика: Реальные договоры/акты, approved review criteria, data policy.
Основные риски: Legal hallucination, ложная уверенность, пропуск важного пункта, неправильная интерпретация таблиц.
Ограничения: Не давать юридическое заключение; только draft checklist.
Acceptance signal: Output clearly separates visible facts, questions and assumptions.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-009. Публичное исследование с источниками

```text
ID: ST2-US-009
Название: Публичное исследование с источниками
Сценарий: Web Search / внешние исследования
Роль: сотрудник
User story: Как сотрудник, я хочу выполнить безопасный публичный Web Search запрос и получить ответ со списком источников, чтобы быстро собрать внешний срез по теме.
Зачем это нужно: Web Search нужен в PRD-1, но должен быть управляемым: source visibility, result count, cost and query policy.
Входные данные: Safe public query, selected provider/path, rules for source attribution.
Ожидаемый результат: Candidate sources, краткий answer draft, links and no-results/conflict behavior.
Какие prompts/templates нужны: "research with sources", "compare sources", "answer with uncertainty", "no results".
Какие Knowledge/инструкции нужны: Forbidden query examples, source attribution rules, logging/cost notes.
Какие данные можно заменить synthetic data: safe_web_search_queries.
Что можно проверить без заказчика: Query wording, source-list format, answer/source separation on public queries.
Что требует заказчика: Rollout scope, allowed data classes, logging policy, cost policy, group defaults.
Основные риски: Private data in query, weak sources, hallucinated citations, provider leakage, cost growth.
Ограничения: Не использовать customer/private queries; не считать SearXNG полной privacy-гарантией.
Acceptance signal: Story output separates candidate set from final answer and shows sources.
Статус: Draft; можно двигать сейчас as documentation/story.
```

### ST2-US-010. Запрещенный или чувствительный Web Search запрос

```text
ID: ST2-US-010
Название: Запрещенный или чувствительный Web Search запрос
Сценарий: Web Search / внешние исследования
Роль: сотрудник
User story: Как сотрудник, я хочу получить понятный отказ или подсказку, если мой Web Search запрос содержит внутреннюю или чувствительную информацию, чтобы не отправить ее внешнему поисковому provider.
Зачем это нужно: Web Search повышает риск утечки через query and logs.
Входные данные: Synthetic forbidden query example, draft data policy, Web Search rules.
Ожидаемый результат: Объяснение, почему запрос нельзя отправлять, и безопасная альтернатива.
Какие prompts/templates нужны: "forbidden query block", "safe rewrite suggestion", "policy explanation".
Какие Knowledge/инструкции нужны: Web Search privacy boundary, allowed/prohibited query examples, provider notes.
Какие данные можно заменить synthetic data: forbidden_query_examples.
Что можно проверить без заказчика: Policy text, examples, safe rewrite behavior.
Что требует заказчика: Финальная policy по data classes, logging and rollout.
Основные риски: Слишком широкий разрешающий режим, непонятный отказ, утечка customer/internal context.
Ограничения: Не включать production rollout without owner approval.
Acceptance signal: Sensitive synthetic query is classified as not safe for external search.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-011. Отчет по использованию AI

```text
ID: ST2-US-011
Название: Отчет по использованию AI
Сценарий: Usage analytics / отчет по токенам
Роль: администратор
User story: Как администратор, я хочу видеть использование по пользователям, периодам, моделям, сообщениям и токенам, чтобы понимать нагрузку и примерную стоимость Stage 2.
Зачем это нужно: PRD-1 требует basic analytics/cost visibility, а не сразу hard billing.
Входные данные: Usage events, model catalog, provider price catalog draft, reporting period.
Ожидаемый результат: Report shape by user/day/week/model/messages/tokens/approx cost.
Какие prompts/templates нужны: Не основной prompt; нужны report fields and admin explanation template.
Какие Knowledge/инструкции нужны: Analytics limitations, price catalog notes, privacy guidance for user-level reporting.
Какие данные можно заменить synthetic data: analytics_sample_prompts and synthetic usage records.
Что можно проверить без заказчика: Report field list and synthetic usage shape.
Что требует заказчика: Reporting granularity, manager/admin visibility, price catalog acceptance.
Основные риски: Confusing analytics with billing, incomplete cost estimate, privacy issues.
Ограничения: Не обещать hard budget enforcement or provider invoice parity.
Acceptance signal: Story lists minimum report fields and explicitly separates analytics from billing.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-012. Решение: native analytics достаточно или нужен gateway

```text
ID: ST2-US-012
Название: Native analytics или gateway
Сценарий: Usage analytics / отчет по токенам
Роль: владелец сервиса
User story: Как владелец сервиса, я хочу увидеть ограничения native analytics, чтобы решить, достаточно ли ее для Stage 2 или нужен отдельный gateway.
Зачем это нужно: Hard billing/gateway - future slice, его нельзя тащить в Practical Stage 2 без требования.
Входные данные: Native analytics findings, expected report fields, customer cost-control requirement.
Ожидаемый результат: Короткий gap list: что видно native, чего не хватает для hard budgets.
Какие prompts/templates нужны: Admin explanation template, decision note template.
Какие Knowledge/инструкции нужны: Usage analytics research, LiteLLM/gateway boundary notes, provider price notes.
Какие данные можно заменить synthetic data: Synthetic usage examples and approximate price rows.
Что можно проверить без заказчика: Draft gap taxonomy and decision wording.
Что требует заказчика: Требование к hard budgets, virtual keys, rate limits, blocking behavior.
Основные риски: Перепутать отчетность с биллингом, пообещать блокировку без gateway, недооценить ops.
Ограничения: Не проектировать gateway implementation in this story.
Acceptance signal: Native analytics and hard billing are separated in plain language.
Статус: Draft; можно двигать сейчас.
```

### ST2-US-013. OCR/VL OCR candidate shortlist

```text
ID: ST2-US-013
Название: OCR/VL OCR candidate shortlist
Сценарий: OCR / VL OCR candidate benchmark
Роль: инженер Stage 2
User story: Как инженер Stage 2, я хочу описать candidate shortlist для OCR/VL OCR на искусственных сканах, чтобы позже выбрать безопасный pilot path для реальных документов заказчика.
Зачем это нужно: OCR/VL OCR важен для documents/broker reports, но production quality customer-blocked.
Входные данные: Candidate classes, synthetic scan/table-like examples, evaluation criteria.
Ожидаемый результат: Candidate shortlist and criteria, without running benchmark or claiming production quality.
Какие prompts/templates нужны: "extract text", "extract table", "classify document type", "report uncertainty".
Какие Knowledge/инструкции нужны: VL OCR provider research, document/OCR/Excel research, privacy/cost/latency criteria.
Какие данные можно заменить synthetic data: fake_scan_pdf, fake_invoice_or_act, fake_contract, fake_broker_report.
Что можно проверить без заказчика: Candidate taxonomy and criteria wording only; benchmark execution is a later task.
Что требует заказчика: Real scans, broker reports, allowed provider class, expected output sample.
Основные риски: OCR hallucination, wrong table structure, privacy issue, false production promise.
Ограничения: Не запускать benchmark in this task; не отправлять реальные документы; не обещать OCR works for everything.
Acceptance signal: Story clearly states synthetic-only boundary and customer-blocked pilot conditions.
Статус: Draft; можно двигать сейчас как story/selection input, not proof-plan.
```

## 6. Ссылки

- [Stage 2 Scenario Shortlist](STAGE2_SCENARIO_SHORTLIST.md)
- [Stage 2 Unblocked Work Plan](STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [OpenWebUI Native Capability Audit](OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Engineering Backlog](../ENGINEERING_BACKLOG.md)
