# Stage 2 Selected User Stories

Дата: 2026-06-25

Статус: внутренний execution-пакет для подготовки первых Stage 2 proof plans.
Это не финальный scope Stage 2, не инструкция для пользователей и не runtime
change.

`User story` - описание задачи глазами пользователя. `Synthetic data` -
искусственные тестовые данные без данных заказчика. `Proof plan` - план
проверки, что механизм работает. `Candidate set` - список найденных источников
или вариантов до финального ответа модели. `VL OCR` - распознавание документа
через зрительно-языковую модель. `Analytics` - статистика использования.
`Runtime` - работающий стенд или приложение. `Docs-only` - только
документация, без запуска стенда и без настройки OpenWebUI.

## 1. Основа

Этот пакет продолжает уже выполненную цепочку:

Research -> scenario shortlist -> draft user stories -> selected user stories.

Ссылки:

- [Corporate AI Workspace Use Cases Research](../research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Corporate AI Use Case Research Report](../../reports/2026-06-25/OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md)
- [Stage 2 Scenario Shortlist](STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace Scenario User Stories](WORKSPACE_SCENARIO_USER_STORIES.md)
- [Stage 2 Unblocked Work Plan](STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)

## 2. Выбранный первый пакет

Первый execution-пакет ограничен шестью stories:

1. `ST2-US-001` - краткое резюме рабочего текста.
2. `ST2-US-002` - предупреждение о чувствительных данных.
3. `ST2-US-003` - резюме встречи и action items.
4. `ST2-US-009` - публичное исследование с источниками.
5. `ST2-US-011` - отчет по использованию AI.
6. `ST2-US-013` - OCR/VL OCR candidate shortlist.

Пакет малый намеренно: он дает разные проверяемые поверхности Stage 2 без
customer data, production rollout and runtime changes.

## 3. Причина выбора

- `ST2-US-001` и `ST2-US-002` идут вместе: базовый AI-чат без предупреждения о
  данных создает слабую и опасную проверку.
- `ST2-US-003` продолжает уже закрытый текущий STT MVP path, но проверяет не
  сам STT, а post-transcription workflow: summary, decisions and action items
  из transcript.
- `ST2-US-009` нужен, потому что Web Search уже исследовался и тестировался, но
  rollout остается policy-gated. Сейчас готовится safe public query proof, а не
  включение Web Search всем.
- `ST2-US-011` выделен отдельно: Stage 2 нужна конкретная форма отчета
  пользователь -> день/неделя -> модель -> сообщения -> токены -> примерная
  usage/cost visibility.
- `ST2-US-013` фиксирует OCR/VL OCR как marker, но execution paused: сначала
  нужен OCR / VL OCR Infrastructure & Provider Benchmark epic.
- Knowledge/RAG и broker reports не включены в первый пакет, потому что их
  полезность и acceptance зависят от домена заказчика, реальных документов,
  владельцев и expected output.

## 4. Таблица выбранных stories

| Story | Scenario | Почему сейчас | Что можно без заказчика | Что customer-blocked |
| ----- | -------- | ------------- | ----------------------- | -------------------- |
| `ST2-US-001` | Общий управляемый AI-чат | Базовый безопасный сценарий для prompt/template и workspace rules. | Форма резюме на synthetic working text. | Реальные типы рабочих текстов, группы и approved data policy. |
| `ST2-US-002` | Data warning | Нужен рядом с базовым чатом, чтобы не проверять AI-чат вне правил данных. | Warning text, forbidden examples, safe rewrite wording. | Финальная allowed/prohibited data policy and provider classes. |
| `ST2-US-003` | Meetings / post-transcription workflow | STT MVP path уже закрыт; следующий риск - полезная обработка transcript. | Summary, decisions, action items на fake meeting transcript. | Реальные media, consent, retention and transcript access rules. |
| `ST2-US-009` | Web Search / public research | Web Search ценен, но rollout policy-gated. | Safe public query matrix, source-list shape, candidate-set wording. | Rollout scope, logs, cost, allowed data and group defaults. |
| `ST2-US-011` | Usage analytics | Basic visibility нужна до hard billing/gateway. | Report shape and synthetic usage rows. | Reporting granularity, manager/admin visibility and price catalog acceptance. |
| `ST2-US-013` | OCR / VL OCR candidate shortlist | OCR/VL OCR не должен потеряться, но proof execution paused до infrastructure epic. | Context pack, provider taxonomy, input/output contract draft and benchmark frame. | Provider shortlist, real scans, broker reports, provider approval and expected output sample. |

`ST2-US-013` execution paused as user-story proof. Moved under OCR / VL OCR
Infrastructure & Provider Benchmark Epic. Reason: provider shortlist,
input/output contract, safety boundary and synthetic benchmark plan must be
defined first.

## 5. Таблица отложенных stories

| Story | Decision | Почему не в первом пакете |
| ----- | -------- | ------------------------- |
| `ST2-US-004` Follow-up письмо после встречи | Later | Полезное продолжение `ST2-US-003`, но сначала нужно стабилизировать summary/decisions/action items. |
| `ST2-US-005` Ответ по Knowledge/RAG с источниками | Later / customer-linked | Synthetic Knowledge доказывает механику, но полезность зависит от реальных документов, владельцев и прав доступа. |
| `ST2-US-006` Отказ без надежного источника | Later / customer-linked | Логически связан с Knowledge/RAG; лучше брать после выбора synthetic Knowledge pack или customer domain. |
| `ST2-US-007` Краткий разбор простого PDF/DOCX | Later | Механика ценная, но первый пакет уже включает OCR/VL OCR selection; simple document proof можно взять следующим срезом. |
| `ST2-US-008` Риски и вопросы по документу | Later | Требует аккуратных review criteria; без customer examples легко превратить в фантазию. |
| `ST2-US-010` Запрещенный Web Search запрос | Later | В первом пакете общая data warning покрыта `ST2-US-002`; Web Search block лучше вынести в следующий policy proof. |
| `ST2-US-012` Native analytics или gateway | Later / future decision | Сначала нужен report shape `ST2-US-011`; gateway decision не должен входить в первый proof-пакет. |

Не включать сейчас как proof-package story: broker reports / 3-НДФЛ. Это
customer-blocked high-value scenario: нужны реальные отчеты, expected output,
финансовая/data policy and owner review.

## 6. Связь с unblocked work plan

Пакет покрывает первые независимые работы из
[Stage 2 Unblocked Work Plan](STAGE2_UNBLOCKED_WORK_PLAN.md):

- workspace scenario user stories;
- synthetic test data pack requirements;
- usage analytics proof plan;
- VL OCR synthetic benchmark plan;
- Web Search safe comparison matrix;
- post-transcription workflow on fake transcript.

Простое извлечение PDF/DOCX/XLSX и configuration-first Knowledge/RAG proof
остаются следующими кандидатами после этого пакета.

## 7. Связь с customer decisions

Можно продолжать без заказчика:

- подготовить synthetic data files in a separate approved task;
- подготовить prompt/template drafts;
- подготовить safe query matrix;
- подготовить analytics sample usage rows;
- подготовить OCR/VL OCR candidate benchmark matrix.

Нужно решение заказчика позже:

- реальные группы, роли and scenario owners;
- approved allowed/prohibited data policy;
- Web Search rollout policy, logs and cost stance;
- transcript retention/consent/access rules;
- реальные documents, scans, broker reports and expected output;
- provider class approval for OCR/VL OCR and external AI providers;
- analytics visibility level and whether hard billing/gateway is required.

## 8. Следующий шаг

Следующий безопасный шаг: создать synthetic data files по требованиям из
[STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](../testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
и только после отдельного approval выполнять proof plans from
[STAGE2_SELECTED_STORIES_PROOF_PLANS.md](STAGE2_SELECTED_STORIES_PROOF_PLANS.md).
