# OpenWebUI Stage 2 Scenario Shortlist And User Stories Report

Дата: 2026-06-25

Репозиторий: `Kwentin3/corp-openweb-ui`

Scope: docs-only аналитико-продуктовая задача. Runtime, env, provider settings,
users, groups, models, prompts, Knowledge and production code не менялись.

## 1. Задача

Выполнить первые четыре шага после corporate AI use-case research:

1. Принять research как исходную базу.
2. Отобрать 5-7 Stage 2 сценариев-кандидатов.
3. Разложить сценарии по корзинам: можно сейчас, нужен заказчик, future.
4. Написать первые draft user stories только по выбранным сценариям.

Этот отчет не создает synthetic data, proof plans или runtime resources.

## 2. Что было прочитано

Прочитанные локальные источники:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md`
- `docs/stage2/research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md`
- `docs/reports/2026-06-25/OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md`
- `docs/stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md`
- `docs/stage2/testdata/SYNTHETIC_TEST_DATA_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`

Новый широкий внешний research не проводился.

## 3. Research принят как база

Принятые research-артефакты:

- [Corporate AI Workspace Use Cases Research](../../stage2/research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Corporate AI Use Case Research Report](OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md)

Categories found in the research:

- meetings and transcription;
- documents and contracts;
- internal Knowledge/RAG;
- Web Search and external research;
- tables, reports and Excel;
- OCR / VL OCR / document AI;
- finance, tax and reporting;
- customer support;
- sales and marketing;
- HR, learning and onboarding;
- legal and compliance;
- development and IT support;
- usage analytics and cost governance;
- security and data policy.

Опорные выводы, которые считаются source-backed:

- Enterprise AI usage clusters around ordinary recurring work: drafts,
  summaries, meeting notes, document review, internal knowledge search,
  external research, support, sales/marketing, engineering and governance.
- Stage 2 fits controlled workspaces better than a loose list of models.
- Synthetic data can support mechanics and shape, but cannot prove quality on
  real broker reports, scans, real Knowledge or complex Excel.
- Native analytics/cost visibility should be separated from hard
  billing/gateway.

Аналитические гипотезы, не доказанные как customer facts:

- The first Stage 2 story set should be limited to 5-7 scenario groups.
- Broker reports / 3-НДФЛ should stay important but customer-blocked until
  real documents and expected outputs exist.
- Support, sales/marketing, HR/onboarding and Dev/IT support are useful later
  but not first shortlist items for the current Practical Stage 2.

## 4. Решение по shortlist

Выбранный shortlist:

| # | Scenario | Why selected |
| - | -------- | ------------ |
| 1 | Общий управляемый AI-чат | Baseline workspace, prompts/templates and data policy scenario. |
| 2 | Встречи / транскрибация / action items | Enterprise pattern and existing Stage 2 STT track. |
| 3 | Внутренний Knowledge / RAG | Core workspace value: answer with sources and access control. |
| 4 | PDF/DOCX document assistant | PRD-1 requires simple document handling with honest limits. |
| 5 | Web Search / внешние исследования | PRD-1 and existing provider/source-attribution track. |
| 6 | Usage analytics / отчет по токенам | Required for basic cost visibility and governance. |
| 7 | OCR / VL OCR candidate benchmark | Important OCR pilot input, but framed as synthetic-only candidate story now. |

Почему выбран такой shortlist:

- It covers the PRD-1 core: scenarios, prompts, Knowledge, documents,
  transcription, Web Search, analytics and governance.
- Every selected scenario can be expressed as a workspace or controlled
  workflow.
- Each scenario has at least one part that can be moved docs-only without
  customer data.
- High-risk customer-specific scenarios remain visible but not overclaimed.

## 5. Отклонено или отложено из первого shortlist

| Scenario | Status | Reason |
| -------- | ------ | ------ |
| Broker reports / 3-НДФЛ | Important, customer-blocked | Needs real reports, expected output and financial data policy. |
| Customer support | Later candidate | Repeats in research but not current PRD-1 priority. |
| Sales/marketing | Later candidate | Useful workspace, but after core governance and Web Search. |
| HR/onboarding | Later candidate | Sensitive data and employment-policy risk. |
| Dev/IT support | Later/future | Useful but outside current business focus. |
| Hard billing/gateway | Future slice | Requires gateway architecture and explicit hard-budget requirement. |
| Complex Excel parser | Future slice | Needs parser/tool path, not generic LLM chat. |
| Production OCR/layout pipeline | Future slice | Requires queue, validation UI, audit and human review after pilot. |
| Full data masking/tokenization | Future slice | Requires trusted subsystem and mapping store. |
| Full AD lifecycle / SCIM | Future slice | Optional identity lifecycle slice, not Practical Stage 2 base. |
| Deep OpenWebUI fork | Future slice | Only after native/configuration/integration path fails with proof. |
| Autonomous agent actions in 1C/CRM | Future/non-goal | Outside safe workspace scope. |

## 6. Матрица корзин

| Basket | Contents | Rule |
| ------ | -------- | ---- |
| A. Можно сейчас | AI-chat stories, fake transcript stories, synthetic Knowledge mechanics, simple PDF/DOCX stories, safe Web Search stories, analytics report shape, OCR/VL OCR candidate story. | Docs/user-story work only; no runtime and no customer data. |
| B. Нужен заказчик | Real groups/owners, real Knowledge, broker reports, scans/PDF tables/XLSX, meeting media/consent, provider/data policy, Web Search rollout, no-delete/retention/manager visibility, hard billing requirement. | Cannot be accepted without customer/admin/security decisions. |
| C. Future slice | Hard billing/gateway, complex Excel parser, production OCR pipeline, full masking/tokenization, full AD lifecycle/SCIM, deep fork, production DOCX/XLSX generation, autonomous 1C/CRM actions. | Do not include in Practical Stage 2 without separate decision. |

## 7. Созданные user stories

Создано 13 draft user stories в
[Workspace Scenario User Stories](../../stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md):

| ID | Scenario |
| -- | -------- |
| ST2-US-001 | Общий управляемый AI-чат |
| ST2-US-002 | Общий управляемый AI-чат |
| ST2-US-003 | Встречи / транскрибация / action items |
| ST2-US-004 | Встречи / транскрибация / action items |
| ST2-US-005 | Внутренний Knowledge / RAG |
| ST2-US-006 | Внутренний Knowledge / RAG |
| ST2-US-007 | PDF/DOCX document assistant |
| ST2-US-008 | PDF/DOCX document assistant |
| ST2-US-009 | Web Search / внешние исследования |
| ST2-US-010 | Web Search / внешние исследования |
| ST2-US-011 | Usage analytics / отчет по токенам |
| ST2-US-012 | Usage analytics / отчет по токенам |
| ST2-US-013 | OCR / VL OCR candidate benchmark |

## 8. Ключевые риски

- Synthetic data being mistaken for production quality evidence.
- RAG answers without reliable source attribution.
- OCR/VL OCR being treated as ready for real documents without customer pilot.
- Web Search queries leaking internal context.
- Native analytics being described as hard billing.
- Manager visibility being confused with administrator access to all chats.
- Financial/tax scenarios being overclaimed without real broker reports and
  human review.

## 9. Опасные иллюзии

- "AI can correctly handle any Excel."
- "OCR reads everything."
- "RAG solves knowledge automatically."
- "Native analytics is billing."
- "Manager visibility means give managers admin access."
- "SearXNG means full privacy."
- "Synthetic data proves production quality."
- "AI summary is the source of truth."

## 10. Измененные документы

Создано:

- [Stage 2 Scenario Shortlist](../../stage2/implementation/STAGE2_SCENARIO_SHORTLIST.md)
- This report.

Обновлено:

- [Workspace Scenario User Stories](../../stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md`

## 11. Что не делалось

- No synthetic files were created.
- No proof plans were written.
- No runtime smoke was run.
- No `.env`, keys, tokens, private URLs or credentials were read.
- No customer data was used.
- No users, groups, models, prompts or Knowledge were created.
- No provider settings were changed.
- No production code was written.
- No final scope was asserted.

## 12. Рекомендуемый следующий шаг

Использовать shortlist и 13 draft user stories как вход для отдельного отбора:

1. Choose the first 3-4 stories for actual proof planning.
2. Define safe synthetic data requirements for only those stories.
3. Keep customer-blocked stories marked until real data and policy decisions
   arrive.

Не начинать runtime configuration, пока для выбранной story нет отдельного
согласованного плана проверки и ясной границы customer/data.
