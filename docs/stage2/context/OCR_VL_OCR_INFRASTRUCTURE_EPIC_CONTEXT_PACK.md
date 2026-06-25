# OCR / VL OCR Infrastructure Epic Context Pack

## 1. Назначение

Этот context pack нужен для будущего агента, который откроет новый Stage 2
эпик: **OCR / VL OCR Infrastructure & Provider Benchmark**.

Эпик открыт потому, что `ST2-US-013` не должен двигаться как обычная
user story / proof execution. User story фиксирует полезный пользовательский
маркер, но OCR / VL OCR infrastructure ещё не определена:

- нет утверждённого provider shortlist;
- нет безопасного input/output contract;
- нет error/limitation contract;
- не определено, что отдаётся в OCR-контур и что возвращается обратно;
- нет synthetic benchmark plan;
- нет customer pilot boundary.

Сначала нужно описать OCR / VL OCR контур и benchmark рамку. Только после этого
можно возвращаться к пользовательским OCR scenarios and proof execution.

## 2. Короткий статус

```text
ST2-US-013 remains draft.
Execution is paused as user-story proof.
Reason: OCR / VL OCR provider shortlist, input/output contract, safety boundary and benchmark plan are not defined yet.
Next step: OCR / VL OCR Infrastructure & Provider Benchmark Epic.
```

## 3. Архитектурная позиция

Не считать правильной базовой архитектурой прямую отправку растровых страниц
документа в мультимодальную LLM как единственный OCR path.

Плохой baseline:

```text
image/page -> multimodal LLM -> answer
```

Такой путь может дать красивый ответ, но плохо подходит как корпоративная
архитектура: результат трудно проверять, трудно отделить OCR extraction от LLM
interpretation, трудно увидеть потерянные таблицы, low confidence, unsupported
features and provider errors.

Предпочтительный baseline:

```text
document -> OCR/VL OCR provider -> structured extraction -> normalized representation -> LLM analysis -> human review
```

OCR / VL OCR должен быть отдельным контуром. LLM анализирует уже извлечённое и
нормализованное представление: JSON, Markdown, page blocks, tables, fields and
warnings. Результат OCR должен быть проверяемым:

- страницы;
- текстовые блоки;
- таблицы;
- поля;
- confidence / uncertainty;
- warnings;
- errors;
- unsupported features;
- safe metadata subset.

Человек остаётся в цепочке проверки. OCR/VL OCR output не является юридическим,
налоговым или бухгалтерским итогом без human review and customer acceptance.

## 4. Что уже есть в Stage 2

- [PRD-1](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md) включает Documents /
  OCR / Excel and OCR/layout-aware PDF pilot.
- OCR/layout-aware PDF описан как pilot/research; production pipeline не
  обещается.
- [VL OCR Provider Research](../research/VL_OCR_PROVIDER_RESEARCH.md) уже
  фиксирует candidate classes and risks.
- [VL OCR API Provider Shortlist Research](../research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
  уже выбирает первых benchmark candidates for raster image -> external
  VL/OCR API -> JSON -> LLM context MVP: Mistral OCR 4 / Document AI, Alibaba
  Qwen-OCR / Qwen3-VL and Azure Document Intelligence.
- [Documents OCR Excel Research](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
  уже фиксирует OpenWebUI extraction engines, Tika, Docling, Mistral OCR and
  pilot limitations.
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md) уже
  содержит synthetic OCR-related placeholders.
- [Stage 2 Selected User Stories](../implementation/STAGE2_SELECTED_USER_STORIES.md)
  уже содержит `ST2-US-013`.
- `ST2-US-013` теперь paused as user-story proof до завершения infrastructure
  epic.
- Context routing rules already say that OCR/VL OCR synthetic benchmark is not
  production OCR readiness.

## 5. Почему это отдельный epic

Здесь сначала нужно решить инфраструктурные вопросы, а не пользовательскую
задачу:

- provider candidates;
- data policy;
- input contract;
- output contract;
- error contract;
- benchmark criteria;
- synthetic test pack;
- future customer pilot boundary.

User story отвечает на вопрос "какая пользовательская ценность нужна".
Infrastructure epic отвечает на вопрос "какой безопасный и проверяемый OCR
контур вообще можно использовать".

## 6. Цели эпика

1. Выбрать 2-3 OCR / VL OCR candidates for benchmark.
2. Описать provider capability profile.
3. Описать input contract.
4. Описать output contract.
5. Описать error/limitation contract.
6. Описать privacy/data policy boundary.
7. Подготовить synthetic benchmark plan.
8. Подготовить future customer pilot prerequisites.
9. Обновить статус `ST2-US-013` как blocked by infrastructure epic.
10. Подготовить основу для ADR-0005 или отдельной decision note.

## 7. Non-goals

Первый шаг этого эпика не делает:

- не запускает OCR provider API;
- не подключает provider accounts;
- не использует реальные документы заказчика;
- не отправляет документы внешним провайдерам;
- не утверждает production OCR provider;
- не обещает production OCR quality;
- не строит full production document pipeline;
- не делает complex Excel parser;
- не делает automatic tax/broker-report analysis;
- не меняет OpenWebUI runtime;
- не создаёт user-facing OCR feature.

## 8. Provider candidate classes

Не выбирать production provider в этом context pack. Классы кандидатов для
будущего shortlist research:

- native OpenWebUI extraction baseline;
- text extraction / parser baseline, for example Apache Tika, Docling or
  similar;
- специализированный OCR / Document AI provider;
- VL OCR provider;
- cloud OCR provider;
- local/open-source OCR or local VLM candidate;
- hybrid pipeline: OCR/layout extraction + LLM analysis.

Existing research already names candidate classes and examples such as
Tika/Docling/Mistral OCR. Do not invent production choice without a new
shortlist research task.

## 9. Provider capability profile template

Future agent should fill this profile for each candidate:

```text
Provider / candidate:
Provider class:
API / deployment mode:
Input formats:
Max file size:
Max pages:
Russian language support:
Tables:
Layout:
Scans/photos:
Stamps/signatures:
Handwriting:
Confidence / uncertainty:
Structured JSON:
Markdown output:
Coordinates / page references:
Batch mode:
Latency:
Cost:
Privacy/data policy fit:
Data retention by provider:
Region / cross-border risk:
Auth/secrets model:
Error model:
Known limitations:
Pilot suitability:
Production suitability:
Source links:
Status:
```

## 10. Input contract draft

OCR/VL OCR contour should receive an explicit request envelope:

```text
document_id
file
file_type
page_range
document_class_hint
language_hint
extraction_profile
data_class
provider_policy_class
expected_output_profile
max_pages
max_file_size
request_id
```

Plain meaning: the system must know which file is being processed, which pages
are allowed, what kind of document it probably is, which extraction mode is
requested, which data class applies and which provider class is allowed.

## 11. Output contract draft

Desired top-level result:

```text
request_id
provider
status
pages[]
text_blocks[]
tables[]
fields[]
warnings[]
errors[]
confidence
unsupported_features[]
raw_provider_metadata_safe_subset
normalized_markdown
normalized_json
```

For pages:

```text
page_number
text
blocks
tables
images_detected
confidence
warnings
```

For tables:

```text
page_number
table_id
rows
columns
cells
confidence
warnings
```

Do not pass raw provider response directly into prompts as the stable contract.
Provider adapters should translate external responses into a normalized internal
contract.

## 12. Error / limitation contract

Typical error and limitation types:

```text
unsupported_file_type
file_too_large
too_many_pages
scan_quality_too_low
table_not_reliable
handwriting_not_supported
stamp_or_signature_not_interpreted
provider_timeout
provider_rate_limited
provider_error
data_policy_blocked
low_confidence
partial_extraction
```

Errors and limitations must be visible to the user/operator. They must not be
hidden under a confident LLM answer.

## 13. Synthetic benchmark boundary

Synthetic benchmark is needed to compare candidates safely. It does not prove
quality on real customer documents and does not approve production OCR
readiness.

Synthetic benchmark classes to plan:

- fake text PDF;
- fake scan;
- fake invoice/act;
- fake table PDF;
- fake stamped/signature document;
- poor-quality fake scan;
- fake broker-like report.

Do not create synthetic files in this task. This context pack only says what
classes are needed.

## 14. Customer pilot boundary

Customer pilot requires:

- real scanned PDF;
- real PDF with tables;
- real poor scan/photo;
- real broker report if customer wants broker scenario;
- expected good output;
- provider/data policy approval;
- secure transfer method;
- allowed provider classes;
- human review owner.

Real customer documents must not be used until the owner explicitly approves
data handling, transfer method and provider class.

## 15. Как этот epic связан с ST2-US-013

- `ST2-US-013` не удаляется.
- `ST2-US-013` remains draft user story / marker.
- Execution is paused until OCR / VL OCR infrastructure epic creates provider
  shortlist, contracts and benchmark plan.
- После epic можно вернуться к user stories:
  - scan extraction;
  - invoice/form extraction;
  - broker-report extraction;
  - document classification;
  - table extraction.

## 16. Что будущий агент должен читать первым

Ordered context route:

1. [CONTEXT_INDEX.md](../CONTEXT_INDEX.md)
2. [CONTEXT_USAGE_RULES.md](../CONTEXT_USAGE_RULES.md)
3. [OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md](OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md)
4. [VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md](../research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
5. [VL_OCR_PROVIDER_RESEARCH.md](../research/VL_OCR_PROVIDER_RESEARCH.md)
6. [DOCUMENTS_OCR_EXCEL_RESEARCH.md](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
7. [SYNTHETIC_TEST_DATA_INDEX.md](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
8. [STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](../testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
9. [STAGE2_SELECTED_USER_STORIES.md](../implementation/STAGE2_SELECTED_USER_STORIES.md)
10. [STAGE2_SELECTED_STORIES_PROOF_PLANS.md](../implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
11. [ACCEPTANCE_MATRIX.md](../acceptance/ACCEPTANCE_MATRIX.md)
12. [IMPLEMENTATION_GATES.md](../IMPLEMENTATION_GATES.md)
13. [CONTRACT_BOUNDARIES.md](../CONTRACT_BOUNDARIES.md)

## 17. Open questions

- Какие 2-3 кандидата брать в первый benchmark?
- Нужен ли локальный baseline?
- Нужен ли облачный provider baseline?
- Какие output profiles нужны: text-only, table-aware, field extraction?
- Какой minimum JSON contract?
- Где хранить raw OCR output?
- Нужно ли сохранять raw provider metadata?
- Как обрабатывать low-confidence extraction?
- Как маркировать partial extraction?
- Как не смешать OCR extraction и LLM interpretation?
- Какие data classes можно отправлять внешним OCR providers?
- Какие документы нельзя отправлять вообще?
- Когда synthetic benchmark считается достаточным для перехода к customer
  pilot?

## 18. Next action

Recommended next step:

```text
Prepare OCR / VL OCR synthetic benchmark plan and `DocumentExtractionResultV1`
adapter contract.
```

Do not start benchmark execution immediately. Provider shortlist and capability
profiles now exist; next prepare benchmark plan, input/output/error contract and
synthetic test classes.
