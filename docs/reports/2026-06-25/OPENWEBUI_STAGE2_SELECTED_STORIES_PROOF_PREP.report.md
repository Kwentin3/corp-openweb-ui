# OpenWebUI Stage 2 Selected Stories Proof Prep Report

Дата: 2026-06-25

Статус: docs-only отчет о подготовке первого execution-пакета Stage 2 user
stories. Runtime proof не запускался, OpenWebUI config не менялся.

`User story` - описание задачи глазами пользователя. `Synthetic data` -
искусственные тестовые данные без данных заказчика. `Proof plan` - план
проверки, что механизм работает. `VL OCR` - распознавание документа через
зрительно-языковую модель. `Analytics` - статистика использования. `Runtime` -
работающий стенд или приложение. `Docs-only` - только документация, без запуска
стенда и без настройки OpenWebUI.

## 1. Что прочитано

- [Corporate AI Workspace Use Cases Research](../../stage2/research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Corporate AI Use Case Research Report](OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md)
- [Stage 2 Scenario Shortlist](../../stage2/implementation/STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace Scenario User Stories](../../stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Stage 2 Scenario Shortlist and User Stories Report](OPENWEBUI_STAGE2_SCENARIO_SHORTLIST_AND_USER_STORIES.report.md)
- [Stage 2 Unblocked Work Plan](../../stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Synthetic Test Data Index](../../stage2/testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [Acceptance Matrix](../../stage2/acceptance/ACCEPTANCE_MATRIX.md)
- [Engineering Backlog](../../stage2/ENGINEERING_BACKLOG.md)
- [Implementation Gates](../../stage2/IMPLEMENTATION_GATES.md)
- [Stage 2 Context Index](../../stage2/CONTEXT_INDEX.md)
- [Stage 2 README](../../stage2/README.md)

Новый широкий research не выполнялся. Выбор сделан на базе уже созданных
research, shortlist and draft user stories.

## 2. Что создано

- [Stage 2 Selected User Stories](../../stage2/implementation/STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 Selected Stories Synthetic Data Requirements](../../stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
- [Stage 2 Selected Stories Proof Plans](../../stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)

## 3. Выбранные stories

| Story | Название | Почему выбрана |
| ----- | -------- | -------------- |
| `ST2-US-001` | Краткое резюме рабочего текста | Базовый AI-чат нужен как первый проверяемый scenario. |
| `ST2-US-002` | Предупреждение о чувствительных данных | Идет вместе с `ST2-US-001`, чтобы базовый чат не обходил data warning. |
| `ST2-US-003` | Резюме встречи и action items | Продолжает текущий STT path через post-transcription workflow, без проверки STT. |
| `ST2-US-009` | Публичное исследование с источниками | Web Search уже исследовался, но rollout остается policy-gated. |
| `ST2-US-011` | Отчет по использованию AI | Нужен конкретный analytics report shape до hard billing/gateway. |
| `ST2-US-013` | OCR/VL OCR candidate shortlist | Фиксирует synthetic benchmark / candidate selection без обещания OCR quality. |

Выбранный пакет не превышает 6 stories and covers: базовый чат, data warning,
meeting transcript workflow, safe Web Search, analytics and OCR/VL OCR
candidate planning.

## 4. Не выбранные stories

| Story | Решение | Причина |
| ----- | ------- | ------- |
| `ST2-US-004` | Later | Follow-up email лучше брать после проверки summary/decisions/action items. |
| `ST2-US-005` | Later / customer-linked | Knowledge/RAG полезен, но реальная ценность требует customer Knowledge, owners and access rules. |
| `ST2-US-006` | Later / customer-linked | No-source behavior связан с Knowledge/RAG и лучше идет после выбора Knowledge pack. |
| `ST2-US-007` | Later | Simple PDF/DOCX mechanics можно взять следующим срезом; первый пакет уже нагружен OCR/VL OCR selection. |
| `ST2-US-008` | Later | Review criteria without customer examples risk becoming fictional. |
| `ST2-US-010` | Later | Общая data warning включена через `ST2-US-002`; Web Search block лучше вынести в отдельный policy proof. |
| `ST2-US-012` | Later / future decision | Сначала нужен `ST2-US-011` report shape; gateway decision не входит в первый пакет. |

Broker reports / 3-НДФЛ не включены: это customer-blocked high-value scenario.
Без реальных отчетов, expected output and financial/data policy proof would be
fictional.

## 5. Связь с corporate use-case research

Research показывает повторяемые корпоративные сценарии: черновики, summary,
встречи, документы, поиск по знаниям, Web Search, analytics and governance.
Выбранный пакет берет те части, которые:

- полезны для Practical Stage 2;
- уже отражены в shortlist;
- могут быть подготовлены на synthetic data;
- не требуют production rollout;
- явно отделяют mechanics from production quality.

Knowledge/RAG and broker reports remain important, but first proof package
keeps them outside execution until domain data, owners and expected outputs are
available.

## 6. Связь с shortlist

Выбранные stories взяты из shortlist scenarios:

- общий управляемый AI-чат -> `ST2-US-001`, `ST2-US-002`;
- встречи / транскрибация / action items -> `ST2-US-003`;
- Web Search / внешние исследования -> `ST2-US-009`;
- usage analytics / отчет по токенам -> `ST2-US-011`;
- OCR / VL OCR candidate benchmark -> `ST2-US-013`.

Не выбран в первый пакет: Knowledge/RAG and PDF/DOCX simple document assistant.
Они остаются следующими кандидатами, но не должны вытеснять data warning,
analytics and OCR/VL OCR from the first proof-prep slice.

## 7. Что можно делать без заказчика

- Создать synthetic working text, forbidden examples, fake meeting transcript,
  safe public query set, synthetic usage rows and fake scan/table descriptions.
- Подготовить prompt/template drafts for selected stories.
- Подготовить safe Web Search query matrix.
- Подготовить analytics report shape.
- Подготовить OCR/VL OCR candidate benchmark matrix.
- Выполнить future proof only after separate runtime approval.

## 8. Что остается customer-blocked

- Реальные группы, роли, owners and access matrix.
- Финальная data policy and provider classes.
- Real meeting media, consent, retention and transcript access rules.
- Web Search rollout scope, logs, cost and group defaults.
- Real documents, scans, broker reports and expected output.
- OCR/VL OCR provider approval and data-egress stance.
- Analytics visibility level, price catalog acceptance and hard billing/gateway
  decision.

## 9. Synthetic data requirements

Synthetic data requirements подготовлены в
[STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](../../stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md).

Нужны:

- synthetic working text for `ST2-US-001`;
- forbidden/sensitive synthetic examples for `ST2-US-002`;
- fake meeting transcript for `ST2-US-003`;
- safe public Web Search query set for `ST2-US-009`;
- analytics sample prompts / synthetic usage rows for `ST2-US-011`;
- fake scan / fake invoice / fake table PDF descriptions for `ST2-US-013`.

Файлы пока не создавались.

## 10. Proof plans

Proof plans подготовлены в
[STAGE2_SELECTED_STORIES_PROOF_PLANS.md](../../stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md).

Каждый proof plan фиксирует:

- что проверяем;
- на каких synthetic данных;
- какой результат считается успехом;
- что proof не доказывает;
- какие customer decisions нужны позже;
- `Runtime changes needed: none`.

Proofs не запускались.

## 11. Что не делалось

- Runtime proof не запускался.
- Synthetic files не создавались.
- Пользователи, группы, модели, prompts and Knowledge не создавались.
- OpenWebUI config не менялся.
- `.env`, keys, tokens, private URLs and credentials не читались.
- Customer data не использовались.
- Production code не писался.
- Финальный scope Stage 2 не утверждался.
- User/admin instructions не готовились.

## 12. Риски и ограничения

- Synthetic data can only prove mechanics and output shape.
- Data warning remains draft until customer/security approval.
- Web Search query safety requires final policy before rollout.
- Analytics report shape is not hard billing or invoice parity.
- OCR/VL OCR synthetic benchmark does not prove quality on real scans or broker
  reports.
- Knowledge/RAG remains valuable but customer-domain dependent.

## 13. Рекомендуемый следующий шаг

Следующий шаг: отдельной docs/testdata задачей создать synthetic files/rows по
требованиям, затем после отдельного approval выполнить выбранные proof plans на
stage/runtime. Не переходить к customer data or production rollout until
customer decisions are closed.
