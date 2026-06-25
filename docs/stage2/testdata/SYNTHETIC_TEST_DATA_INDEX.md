# Synthetic Test Data Index

Статус: внутренний индекс искусственных тестовых данных. В этом документе не
хранятся реальные данные заказчика.

## 1. Назначение

`Synthetic data` - это искусственные тестовые данные, которые не содержат
данных заказчика.

Они нужны, чтобы готовить proof/benchmark работы без ожидания клиентских
документов и без риска утечки. Synthetic data помогает проверить механику:
загрузку, доступы, prompts, Knowledge, базовое извлечение, safe Web Search
matrix и analytics proof shape.

Детальные требования для первого selected story package:
[STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md).

`Proof` - проверка, что механизм реально работает.
`Benchmark` - сравнение вариантов по одним и тем же тестам.

Synthetic data не доказывает production quality на реальных документах
заказчика.

## 2. Что можно проверять на synthetic data

- механику загрузки;
- доступы;
- prompts;
- Knowledge;
- OCR/VL OCR candidates;
- простое извлечение из PDF/DOCX/XLSX;
- аналитику использования;
- Web Search safe matrix.

## 3. Что нельзя доказывать на synthetic data

- качество на реальных документах заказчика;
- качество на реальных брокерских отчетах;
- юридическую корректность;
- production OCR;
- корректную обработку сложного Excel.

## 4. Планируемый набор synthetic data

### 4.1. simple_text_pdf

Назначение:

- простой текстовый PDF для проверки загрузки, extraction preview and summary
  prompt.

Формат:

- PDF with plain synthetic Russian text.

Для каких user stories:

- общий корпоративный AI-чат;
- анализ простого PDF/DOCX.

Что проверяет:

- upload mechanics;
- basic text extraction;
- summary prompt behavior.

Что не доказывает:

- качество OCR;
- работу с таблицами, печатями, сканами или реальными документами.

Статус:

- planned; file not created in this task.

### 4.2. structured_docx_with_table

Назначение:

- DOCX с искусственной таблицей и разделами.

Формат:

- DOCX with fake headings and simple table.

Для каких user stories:

- анализ простого PDF/DOCX;
- админское управление сценариями.

Что проверяет:

- basic DOCX handling;
- ability to summarize visible structure.

Что не доказывает:

- track changes, comments, embedded objects or legal comparison.

Статус:

- planned; file not created in this task.

### 4.3. simple_xlsx_table

Назначение:

- простая таблица для проверки XLSX mechanics.

Формат:

- XLSX with one sheet, simple columns and synthetic values.

Для каких user stories:

- анализ простой XLSX-таблицы;
- usage analytics proof if used as sample report output.

Что проверяет:

- upload and simple table extraction mechanics.

Что не доказывает:

- формулы, pivot tables, merged cells, macros or external links.

Статус:

- planned; file not created in this task.

### 4.4. complex_xlsx_placeholder

Назначение:

- placeholder для сложного Excel case без обещания обработки.

Формат:

- metadata-only description or tiny placeholder file if later needed.

Для каких user stories:

- анализ простой XLSX-таблицы.

Что проверяет:

- visible limitation messaging.

Что не доказывает:

- корректную обработку сложного Excel.

Статус:

- planned; placeholder only.

### 4.5. fake_scan_pdf

Назначение:

- искусственный скан для OCR/VL OCR benchmark mechanics.

Формат:

- PDF/image with generated fake text and degraded scan-like appearance.

Для каких user stories:

- OCR / VL OCR pilot;
- анализ простого PDF/DOCX as negative/limitation case.

Что проверяет:

- candidate OCR path and error reporting.

Что не доказывает:

- качество на реальных сканах заказчика.

Статус:

- planned; file not created in this task.

### 4.6. fake_invoice_or_act

Назначение:

- простой искусственный акт/счет без реальных реквизитов.

Формат:

- PDF/DOCX with fake company names, fake amounts and obvious synthetic labels.

Для каких user stories:

- OCR / VL OCR pilot;
- брокерский отчет / 3-НДФЛ as mechanics-only adjacent case.

Что проверяет:

- structured extraction prompts and warning language.

Что не доказывает:

- бухгалтерскую, юридическую or tax correctness.

Статус:

- planned; file not created in this task.

### 4.7. fake_contract

Назначение:

- искусственный договор для prompt and Knowledge mechanics.

Формат:

- DOCX/PDF with fake parties and synthetic clauses.

Для каких user stories:

- общий корпоративный AI-чат;
- анализ простого PDF/DOCX.

Что проверяет:

- summary, obligations list and human-review warning.

Что не доказывает:

- юридическую экспертизу or real contract comparison.

Статус:

- planned; file not created in this task.

### 4.8. fake_broker_report

Назначение:

- искусственный брокерский отчет для mechanics-only checks.

Формат:

- PDF/XLSX-like fake report with explicit "synthetic" markings.

Для каких user stories:

- брокерский отчет / 3-НДФЛ;
- OCR / VL OCR pilot.

Что проверяет:

- prompt skeleton, warning and document-class routing.

Что не доказывает:

- tax correctness, financial correctness or quality on real broker reports.

Статус:

- planned; file not created in this task.

### 4.9. fake_meeting_transcript

Назначение:

- искусственная расшифровка встречи для prompts and workflow checks.

Формат:

- Markdown or TXT transcript with synthetic speakers and decisions.

Для каких user stories:

- транскрибация встречи;
- usage analytics / отчет по использованию if used as sample chat activity.

Что проверяет:

- protocol, decisions, action items and summary prompts.

Что не доказывает:

- STT quality on real audio/video.

Статус:

- planned; file not created in this task.

### 4.10. safe_web_search_queries

Назначение:

- безопасные публичные queries для Web Search comparison.

Формат:

- Markdown/CSV list of RU/EN public queries.

Для каких user stories:

- Web Search / исследование.

Что проверяет:

- candidate set comparison;
- source visibility;
- no-results/conflicting-source behavior.

Что не доказывает:

- безопасность любых пользовательских запросов;
- production rollout policy.

Статус:

- planned; query list not created in this task.

### 4.11. forbidden_query_examples

Назначение:

- примеры запросов, которые нельзя отправлять в Web Search или внешние
  providers.

Формат:

- redacted synthetic examples without real secrets, private URLs or customer
  data.

Для каких user stories:

- общий корпоративный AI-чат;
- Web Search / исследование;
- админское управление сценариями.

Что проверяет:

- documentation and policy warnings.

Что не доказывает:

- runtime blocking unless a separate proof implements and tests it.

Статус:

- planned; examples not created in this task.

### 4.12. analytics_sample_prompts

Назначение:

- безопасные prompts для generating synthetic usage records.

Формат:

- Markdown/CSV list of ordinary synthetic prompts.

Для каких user stories:

- usage analytics / отчет по использованию;
- общий корпоративный AI-чат.

Что проверяет:

- proof shape for user/day/week/model/token/messages/approx cost reporting.

Что не доказывает:

- provider invoice parity or hard billing.

Статус:

- planned; prompts not executed in this task.

## 5. Правила создания файлов

Если synthetic files будут создаваться в отдельной задаче:

- каждый файл должен явно содержать marker вроде `SYNTHETIC TEST DATA`;
- нельзя использовать реальные имена, emails, телефоны, реквизиты, private URLs,
  customer documents, tokens or secrets;
- нельзя копировать реальные документы и просто менять несколько полей;
- expected output должен отдельно указывать, что проверяется только mechanics;
- файлы должны храниться в согласованном docs/testdata или artifacts path,
  который не смешивается с customer samples.

## 6. Ссылки

- [Stage 2 Unblocked Work Plan](../implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Workspace Scenario User Stories](../implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Stage 2 Selected User Stories](../implementation/STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 Selected Stories Synthetic Data Requirements](STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
- [Stage 2 Selected Stories Proof Plans](../implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Test Data Requirements](../acceptance/TEST_DATA_REQUIREMENTS.md)
