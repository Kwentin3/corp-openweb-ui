# Corporate AI Workspace Use Cases Research

Дата: 2026-06-25

Статус: research base для выбора будущих Stage 2 user stories. Этот документ
не содержит user stories и не утверждает продуктовый scope.

`Use case` - сценарий использования. `User story` - описание задачи глазами
пользователя; в этом документе они не создаются. `RAG` - поиск ответа с опорой
на документы. `Knowledge` - база знаний или набор подключенных материалов.
`Workspace` - рабочая зона с моделью, правилами, шаблонами и доступами.
`Governance` - правила управления: доступы, ограничения, безопасность,
usage/cost visibility. `VL OCR` - распознавание документа через зрительно-языковую модель.
`Analytics` - статистика использования.

## 1. Scope

Цель: собрать повторяющиеся реальные корпоративные сценарии AI-чатов и
AI-workspace инструментов, чтобы позже выбрать, какие сценарии превращать в
Stage 2 user stories.

Что не сделано:

- не написаны новые user stories;
- не выбран окончательный scope Stage 2;
- не использованы данные заказчика;
- не запускался runtime smoke;
- не менялись users, groups, models, prompts, Knowledge, env или provider
  settings.

Локальные входы:

- [PRD-1](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Stage 2 README](../README.md)
- [Stage 2 Context Index](../CONTEXT_INDEX.md)
- [Stage 2 Unblocked Work Plan](../implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Workspace Scenario User Stories](../implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Documents OCR Excel Research](DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [VL OCR Provider Research](VL_OCR_PROVIDER_RESEARCH.md)
- [Usage Analytics Billing Research](USAGE_ANALYTICS_BILLING_RESEARCH.md)

## 2. Source Quality

| Quality | Used as | Examples |
| ------- | ------- | -------- |
| High | Base evidence | Official product docs, official customer stories, engineering blogs, reports from Microsoft, McKinsey, Deloitte, BCG, OpenAI, Microsoft, Google, Anthropic, Perplexity, OpenWebUI, LiteLLM, OWASP. |
| Medium | Supporting signal | Public case-study articles, interviews and vendor-neutral writeups where the facts are concrete but not enough for acceptance. |
| Weak | Warning only | Reddit, HN, GitHub/community threads and personal posts. No weak signal is used here as primary proof. |

High-quality source list is at the end of the document. When a conclusion is
not directly proven by a source, it is marked as analytical hypothesis.

## 3. Executive Findings

- Real enterprise adoption clusters around ordinary work: drafts, summaries,
  meeting notes, document review, internal knowledge search, external research,
  customer support, sales/marketing, engineering and usage governance. This is
  supported by Microsoft Work Trend Index, McKinsey, Deloitte, BCG and multiple
  official customer stories.
- The most Stage 2-relevant pattern is not "one global bot", but controlled
  workspaces: selected models, access rules, prompt templates, Knowledge,
  safe web search, analytics and explicit data policy.
- Document/OCR and finance/tax scenarios are valuable but acceptance depends on
  real samples, expected outputs and provider/data-policy approval.
- Synthetic data can prove mechanics: loading, prompts, Knowledge routing,
  safe Web Search comparison, OCR/VL OCR candidate comparison and analytics
  shape. It cannot prove quality on real broker reports, real scans or complex
  Excel.
- Cost governance is repeatedly present in enterprise tooling. Native analytics
  can start Stage 2 visibility, but hard budgets and enforced quotas are a
  gateway-level decision.

## 4. Scenario Category Map

| Category | Repeated enterprise pattern | Source strength | Stage 2 note |
| -------- | --------------------------- | --------------- | ------------ |
| Meetings and transcription | Meeting summaries, action items, follow-up drafts, searchable notes | High | Fits STT and prompt flows; real media acceptance needs customer samples. |
| Documents and contracts | Summaries, clause review, contract Q&A, long-document analysis | High | Fits Knowledge/RAG and document extraction; legal/tax output must be draft-only. |
| Internal knowledge search | RAG over policies, research, manuals, sales/operations content | High | Core fit for Knowledge and workspaces; requires clean sources and access policy. |
| Web Search and external research | Cited research, market/customer/company lookup, due diligence | High | Fits existing Web Search provider comparison; rollout is policy-gated. |
| Tables and reports | Excel analysis, report drafting, data prep, spreadsheet automation | High | Simple synthetic proof is possible; complex Excel parser remains future. |
| OCR / VL OCR / document AI | Scans, invoices, forms, document classification, extraction | High | Candidate benchmark can start; production OCR needs real docs and review flow. |
| Finance, tax and reporting | Financial analysis, due diligence, investor docs, accounting workflows | Medium-high | Broker/3-NDFL is plausible but customer-blocked and high-risk. |
| Customer support | Contact-center summaries, answer suggestions, ticket triage, QA | High | Good corporate pattern; Stage 2 relevance depends on customer support process. |
| Sales and marketing | Proposal drafts, account research, campaign briefs, call summaries | High | Good prompt/template candidates; needs company-specific materials for Knowledge. |
| HR, learning, onboarding | Candidate feedback, onboarding Q&A, training content, policy lookup | Medium-high | Good synthetic prompt candidate; real HR data is sensitive. |
| Legal and compliance | Contract/legal research, policy checks, audit traces, data controls | High | Relevant as governance and safe-output rules, not as legal guarantee. |
| Development and IT support | Code assistant, incident help, internal runbook search, ticket answers | High | Relevant if Stage 2 expands to IT/dev users; keep separate from business docs. |
| Usage analytics and cost governance | Usage reports, adoption analytics, token/spend tracking, budget limits | High | Native analytics first; hard billing/gateway is future ADR. |
| Security and data policy | Access controls, retention, prompt injection, oversharing, BYOAI risk | High | Must frame every scenario; not optional. |

## 5. Scenario Cards

### 5.1. Общий корпоративный AI-чат для рабочих черновиков

Название сценария: общий корпоративный AI-чат.

Краткое описание: сотрудник использует корпоративный AI-чат для черновиков
писем, резюме, идей, перевода, переписывания текста и простых объяснений.

Кто использует: обычные сотрудники, менеджеры, юристы, маркетинг, аналитики,
операционные команды.

Какая задача: ускорить повседневную работу без передачи чувствительных данных
в неподходящий provider.

Какие входные данные: текст запроса, публичные или разрешенные рабочие данные,
политика допустимого ввода.

Какой результат: черновик или объяснение, которое человек проверяет сам.

Какие инструменты/класс инструментов используются: ChatGPT Enterprise/Team,
Microsoft 365 Copilot, Google Gemini for Workspace, Claude Team/Enterprise,
внутренний AI-chat.

Примеры компаний/источников: Moderna и OpenAI описывают массовое внутреннее
использование GPTs; PwC использует ChatGPT Enterprise для работы сотрудников;
Google Workspace customer stories описывают productivity use cases.

Повторяемость в источниках: высокая.

Польза: быстрый старт, низкий порог входа, хорошая основа для правил, prompts,
model catalog and data policy.

Риски: утечка данных, ложная уверенность в ответе, отсутствие единого стиля,
BYOAI - самостоятельное использование внешних AI без контроля компании.

Какие данные чувствительные: персональные данные, коммерческие тайны, договоры,
финансы, HR, клиентская переписка, credentials.

Какие ограничения нужны: data policy, provider allowlist, запрещенные данные,
пользовательское предупреждение, audit/analytics.

Можно ли проверить на synthetic data: да, как mechanics-only prompt flow и
analytics sample.

Нужны ли реальные данные заказчика: нет для базовой механики; да для реальных
шаблонов и политики.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: это базовый сценарий для Workspace Model,
prompts, groups, data policy and analytics.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://openai.com/index/openai-and-moderna/
- https://openai.com/index/pwc/
- https://www.microsoft.com/en-us/worklab/work-trend-index/ai-at-work-is-here-now-comes-the-hard-part
- https://cloud.google.com/customers/gordon-food-service

### 5.2. Встречи, транскрибация и action items

Название сценария: meeting assistant.

Краткое описание: AI помогает получить расшифровку встречи, краткое резюме,
решения, action items - задачи после встречи, и follow-up draft.

Кто использует: менеджеры, sales, support, project teams, HR.

Какая задача: не терять решения и быстро готовить протоколы и следующие шаги.

Какие входные данные: аудио/видео, transcript, участники, тема встречи,
разрешенные внутренние материалы.

Какой результат: краткое резюме, список решений, список задач, черновик письма.

Какие инструменты/класс инструментов используются: Microsoft Teams Copilot,
Google Meet/Gemini notes, Zoom AI Companion, Otter.ai, OpenWebUI STT + prompt
flow.

Примеры компаний/источников: Microsoft и Google документируют meeting recap,
notes and action items; Zoom/Otter публикуют enterprise meeting assistant
cases; Microsoft customer stories связывают Copilot с meeting productivity.

Повторяемость в источниках: высокая.

Польза: очень понятный business value и хорошо проверяемый output shape.

Риски: запись встреч, согласие участников, персональные данные, неверное
резюме, хранение transcript.

Какие данные чувствительные: голоса, имена, решения, коммерческие темы,
клиентская информация.

Какие ограничения нужны: consent, retention, allowed groups, transcript
storage rules, warning that summary is not source of truth.

Можно ли проверить на synthetic data: да, через fake meeting transcript и
prompt flow.

Нужны ли реальные данные заказчика: нужны для приемки STT качества и retention
policy.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: уже есть STT track; synthetic transcript
может проверить prompts, но production acceptance зависит от реальных media.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://support.microsoft.com/en-us/teams/copilot/catch-up-on-meetings-with-microsoft-365-copilot-in-teams
- https://workspace.google.com/solutions/ai/ai-note-taking/
- https://www.zoom.com/en/products/ai-assistant/
- https://otter.ai/enterprise

### 5.3. Внутренний поиск по знаниям и RAG

Название сценария: internal knowledge assistant.

Краткое описание: сотрудник задает вопрос по внутренним документам, policy,
инструкциям, research archive или sales/operations materials; AI отвечает с
опорой на источники.

Кто использует: сотрудники, support, sales, operations, аналитики, менеджеры.

Какая задача: быстрее находить актуальные правила и материалы.

Какие входные данные: Knowledge base, документы, политики, FAQ, research docs,
права доступа.

Какой результат: ответ с источниками, цитатами или ссылками на документы.

Какие инструменты/класс инструментов используются: Morgan Stanley GPT-4
knowledge assistant, Microsoft 365 Copilot over Graph, Google Gemini/Workspace,
OpenWebUI Knowledge/RAG, Claude Projects/Enterprise search.

Примеры компаний/источников: Morgan Stanley and OpenAI describe AI assistant
for wealth management knowledge; Google Gordon Food Service uses Gemini to
search and summarize internal information; OpenWebUI documents Knowledge and
RAG.

Повторяемость в источниках: высокая.

Польза: хорошо совпадает с PRD-1, groups, Knowledge и prompt templates.

Риски: устаревшие документы, неверный chunking, отсутствие source attribution,
oversharing через слишком широкие права доступа, prompt injection в документах.

Какие данные чувствительные: внутренние регламенты, клиентские данные,
коммерческие материалы, HR и security docs.

Какие ограничения нужны: curated Knowledge, access control, source visibility,
refresh policy, no-answer behavior, document intake rules.

Можно ли проверить на synthetic data: да, на synthetic Knowledge pack.

Нужны ли реальные данные заказчика: да для production relevance и доступа по
группам.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: это один из центральных Stage 2
сценариев, но качество нельзя доказать без реальной базы знаний.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://openai.com/index/morgan-stanley/
- https://cloud.google.com/customers/gordon-food-service
- https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-overview
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/chat-conversations/rag/

### 5.4. Документы, договоры и длинные материалы

Название сценария: document assistant.

Краткое описание: AI помогает читать PDF/DOCX, договоры, спецификации,
регламенты и длинные материалы: summary, Q&A, сравнение версий, извлечение
важных пунктов.

Кто использует: юристы, менеджеры, аналитики, procurement, finance, operations.

Какая задача: сократить время первичного чтения и подготовки черновиков.

Какие входные данные: PDF/DOCX, текстовые документы, договоры, policies,
expected output rules.

Какой результат: summary, clause list, risks draft, вопрос-ответ по документу,
черновик письма.

Какие инструменты/класс инструментов используются: Claude Enterprise/Team,
Microsoft 365 Copilot, Gemini Workspace, OpenWebUI document extraction/RAG,
specialized legal/document AI tools.

Примеры компаний/источников: Anthropic use-case guides include document and
long-document workflows; Microsoft/Google product docs describe document
summarization and drafting; OpenWebUI documents extraction engines.

Повторяемость в источниках: высокая.

Польза: сильный корпоративный сценарий, подходит для prompt catalog and
Knowledge.

Риски: legal hallucination, потеря таблиц/layout, неполный extraction preview,
ошибочные выводы по договору.

Какие данные чувствительные: договоры, персональные данные, финансовые условия,
коммерческие условия.

Какие ограничения нужны: draft-only warning, source links, extraction preview,
manual review, allowed provider policy.

Можно ли проверить на synthetic data: да, на simple PDF/DOCX и fake contract.

Нужны ли реальные данные заказчика: да для приемки качества на реальных
документах.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: Stage 2 может проверить simple document
handling; production legal review не должен обещаться.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://docs.anthropic.com/en/docs/about-claude/use-case-guides/overview
- https://support.microsoft.com/en-us/microsoft-365-copilot
- https://workspace.google.com/products/docs/ai/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/

### 5.5. Web Search и внешние исследования

Название сценария: external research assistant.

Краткое описание: AI ищет и сравнивает публичные источники, готовит краткое
резюме с ссылками и показывает, какие источники использованы.

Кто использует: аналитики, sales, marketing, procurement, legal research,
руководители.

Какая задача: быстро собрать внешний срез по компании, рынку, новости,
регуляторной теме или поставщику.

Какие входные данные: безопасные публичные queries, source policy, result count,
language, forbidden topics.

Какой результат: candidate set - набор найденных источников, затем answer draft
с ссылками.

Какие инструменты/класс инструментов используются: Perplexity Enterprise,
Microsoft Copilot with web, ChatGPT with web/search, OpenWebUI Web Search,
SearXNG/Brave/Yandex search providers.

Примеры компаний/источников: Perplexity Enterprise customer stories describe
research for legal, investment, GTM and public-sector workflows; Microsoft and
OpenAI products include web-grounded answers in approved contexts.

Повторяемость в источниках: высокая.

Польза: directly relevant to existing Stage 2 Web Search comparison work.

Риски: source quality, hallucinated citations, private queries in logs,
provider leakage, cost and rate limits.

Какие данные чувствительные: private company names if confidential, deal
context, customer names, internal strategy.

Какие ограничения нужны: safe query rules, result count, timeout, source
visibility, forbidden query policy, log retention, provider approval.

Можно ли проверить на synthetic data: да, через safe public query matrix.

Нужны ли реальные данные заказчика: не нужны для provider comparison; нужны для
production rollout policy.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: уже есть Web Search research and
contracts; rollout must stay policy-gated.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://www.perplexity.ai/enterprise/customers
- https://learn.microsoft.com/en-us/copilot/microsoft-365/manage-public-web-access
- https://docs.openwebui.com/category/web-search/

### 5.6. Таблицы, Excel и отчеты

Название сценария: spreadsheet and report assistant.

Краткое описание: AI помогает понять таблицу, подготовить отчет, найти
аномалии, пересказать spreadsheet, подготовить формулы или summary.

Кто использует: finance, sales operations, marketing analytics, procurement,
analysts.

Какая задача: ускорить черновой анализ таблиц и отчетов.

Какие входные данные: XLSX/CSV, таблица, dashboard export, manual context,
allowed-data policy.

Какой результат: summary, list of anomalies, draft report, formula suggestion,
chart/slide draft.

Какие инструменты/класс инструментов используются: Microsoft Excel Copilot,
Gemini in Sheets, ChatGPT Enterprise, Claude, Perplexity Enterprise, document
extraction plus LLM.

Примеры компаний/источников: Microsoft and Google document spreadsheet
assistants; Perplexity and Google customer stories include financial/research
and data-prep workflows; PwC/OpenAI describe CFO and business workflows.

Повторяемость в источниках: высокая.

Польза: common business scenario and useful prompt-template candidate.

Риски: formulas, hidden sheets, pivots, merged cells, external links, wrong
numeric interpretation, unsafe financial conclusion.

Какие данные чувствительные: finance, payroll, customer lists, sales pipeline,
tax data.

Какие ограничения нужны: draft-only warning, extraction preview, parser
decision, no legal/tax guarantee, customer expected output.

Можно ли проверить на synthetic data: да for simple XLSX mechanics.

Нужны ли реальные данные заказчика: да for complex Excel and broker/tax
acceptance.

Подходит ли для нашего Stage 2: частично.

Почему подходит / почему не подходит: simple extraction fits; complex Excel
parser remains deferred.

Предварительный приоритет: средний-высокий.

Ссылки на источники:

- https://support.microsoft.com/en-us/office/365-copilot-app/get-started-with-word-excel-and-powerpoint-agents-in-microsoft-365-copilot
- https://workspace.google.com/resources/spreadsheet-ai/
- https://openai.com/index/pwc/
- https://www.perplexity.ai/enterprise/customers

### 5.7. OCR / VL OCR / Document AI

Название сценария: scanned document extraction.

Краткое описание: AI/OCR извлекает текст, таблицы и поля из сканов, фото,
инвойсов, форм, договоров и PDF без надежного text layer.

Кто использует: finance, legal, operations, procurement, accounting, support.

Какая задача: превратить визуальный документ в проверяемый текст/структуру для
дальнейшего анализа.

Какие входные данные: scanned PDF, фото, invoice, акт, договор, таблица,
ожидаемая структура.

Какой результат: extracted text, structured fields, table draft, confidence or
manual review queue.

Какие инструменты/класс инструментов используются: Google Document AI, Azure AI
Document Intelligence, ABBYY Vantage, UiPath Document Understanding, Mistral
OCR, Docling/Tika/OpenWebUI extraction, VL OCR models.

Примеры компаний/источников: Google, Microsoft, UiPath and ABBYY publish
document AI/OCR product docs and customer stories for invoices/forms/document
processing.

Повторяемость в источниках: высокая.

Польза: important for broker reports and scanned documents.

Риски: OCR hallucination, wrong table structure, stamps/signatures, handwriting,
privacy, auditability, high cost.

Какие данные чувствительные: invoices, contracts, ID-like fields, broker
reports, tax data, signatures, stamps.

Какие ограничения нужны: provider/data approval, sample classification,
manual review, extraction preview, no production OCR promise from pilot.

Можно ли проверить на synthetic data: да for candidate comparison mechanics.

Нужны ли реальные данные заказчика: да for production quality.

Подходит ли для нашего Stage 2: да as pilot/research, not as production
pipeline.

Почему подходит / почему не подходит: Stage 2 can benchmark candidates; real
quality remains customer-blocked.

Предварительный приоритет: высокий as research/pilot, not production.

Ссылки на источники:

- https://cloud.google.com/document-ai
- https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
- https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding
- https://www.abbyy.com/vantage/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/docling/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/mistral-ocr/

### 5.8. Finance, tax draft and broker reports

Название сценария: finance and broker-report draft analysis.

Краткое описание: AI помогает разобрать финансовый документ, брокерский отчет
или налоговый черновик и подготовить draft analysis for human review.

Кто использует: finance team, tax/accounting, private banking, investment
research, владельцы документов.

Какая задача: ускорить первичную классификацию, извлечение сумм/дат/операций и
подготовку вопросов к специалисту.

Какие входные данные: broker report, statement, tax draft, expected output,
provider/data policy.

Какой результат: structured draft, warning, list of uncertain fields,
questions for accountant/tax specialist.

Какие инструменты/класс инструментов используются: ChatGPT Enterprise/Claude
for finance analysis, internal RAG, OCR/document AI, Perplexity Enterprise for
research, specialized finance AI tools.

Примеры компаний/источников: Morgan Stanley uses GPT-4 for wealth-management
knowledge; PwC describes finance/CFO AI workflows; Perplexity customer stories
include investment research; Anthropic has financial services customers.

Повторяемость в источниках: средняя-высокая for finance, низкая for exact
3-NDFL/broker workflow.

Польза: aligns with PRD-1 broker/tax interest.

Риски: tax/legal liability, wrong numbers, OCR/table errors, provider privacy,
false confidence.

Какие данные чувствительные: broker reports, tax data, passport-like fields,
income, assets, account identifiers.

Какие ограничения нужны: draft-only, manual review, customer sample set,
expected output, approved provider, no automated filing promise.

Можно ли проверить на synthetic data: only mechanics, warnings and routing.

Нужны ли реальные данные заказчика: да.

Подходит ли для нашего Stage 2: да only as blocked pilot scenario.

Почему подходит / почему не подходит: value is high, but acceptance cannot be
claimed on synthetic or imaginary documents.

Предварительный приоритет: высокий after customer input; blocked now.

Ссылки на источники:

- https://openai.com/index/morgan-stanley/
- https://openai.com/index/pwc/
- https://www.perplexity.ai/enterprise/customers
- https://www.anthropic.com/solutions/financial-services

### 5.9. Customer support and service operations

Название сценария: support assistant.

Краткое описание: AI помогает отвечать на customer tickets, summarise calls,
classify requests, find policy answers and draft support responses.

Кто использует: customer support, contact center, service operations, QA leads.

Какая задача: ускорить ответы и повысить consistency of support.

Какие входные данные: ticket, chat/call transcript, policy docs, product docs,
customer profile if allowed.

Какой результат: response draft, ticket summary, escalation reason, QA note.

Какие инструменты/класс инструментов используются: Microsoft/Google/ServiceNow
AI, Claude/OpenAI support agents, RAG over support knowledge, meeting/call
summary tools.

Примеры компаний/источников: Google and ServiceNow customer materials describe
customer-service AI; Anthropic use-case guides include support-agent patterns;
Microsoft Copilot scenarios include customer operations.

Повторяемость в источниках: высокая.

Польза: repeatable corporate category.

Риски: customer PII, wrong answer, policy mismatch, uncontrolled automation,
lack of audit.

Какие данные чувствительные: customer data, claims, contracts, support history,
call recordings.

Какие ограничения нужны: human-in-the-loop, policy-grounded answers, no
automatic final send unless approved, access control, retention.

Можно ли проверить на synthetic data: да for sample tickets and response
templates.

Нужны ли реальные данные заказчика: да for production Knowledge and policy fit.

Подходит ли для нашего Stage 2: maybe.

Почему подходит / почему не подходит: useful if customer has support workflow;
otherwise lower priority than core workspaces/docs/search.

Предварительный приоритет: средний.

Ссылки на источники:

- https://cloud.google.com/customers
- https://www.servicenow.com/products/ai.html
- https://docs.anthropic.com/en/docs/about-claude/use-case-guides/overview
- https://www.microsoft.com/en-us/worklab/work-trend-index/ai-at-work-is-here-now-comes-the-hard-part

### 5.10. Sales, marketing and go-to-market research

Название сценария: sales and marketing workspace.

Краткое описание: AI помогает готовить account research, proposal drafts,
campaign briefs, конкурентный срез, sales call summary and follow-up.

Кто использует: sales, marketing, account managers, business development.

Какая задача: ускорить подготовку к клиентам and improve consistency of
materials.

Какие входные данные: public web research, CRM notes if allowed, product docs,
brand guidelines, meeting transcript.

Какой результат: account brief, proposal draft, campaign idea, follow-up email,
objection handling draft.

Какие инструменты/класс инструментов используются: Microsoft 365 Copilot,
Google Gemini Workspace, Perplexity Enterprise, ChatGPT/Claude workspaces,
RAG over sales materials.

Примеры компаний/источников: Microsoft, Google and Perplexity customer stories
include GTM and sales research; OpenAI/PwC and Moderna describe custom GPTs for
business functions.

Повторяемость в источниках: высокая.

Польза: clear prompt-template and Web Search candidate.

Риски: confidential deal context, hallucinated facts, brand/legal issues,
wrong competitor data.

Какие данные чувствительные: customer names, pipeline, pricing, proposals,
contracts.

Какие ограничения нужны: public/private data separation, source links, brand
guidelines, allowed CRM data policy.

Можно ли проверить на synthetic data: да for public research and fake account
brief.

Нужны ли реальные данные заказчика: да for customer-specific materials and
CRM-like data.

Подходит ли для нашего Stage 2: да, but after core governance.

Почему подходит / почему не подходит: strong workspace/prompt fit; real sales
data is sensitive.

Предварительный приоритет: средний-высокий.

Ссылки на источники:

- https://www.microsoft.com/en-us/microsoft-365/blog/customer-stories/
- https://cloud.google.com/customers/gordon-food-service
- https://www.perplexity.ai/enterprise/customers
- https://openai.com/index/openai-and-moderna/

### 5.11. HR, onboarding and training

Название сценария: HR and onboarding assistant.

Краткое описание: AI helps draft job descriptions, onboarding plans, policy Q&A,
training materials and feedback summaries.

Кто использует: HR, team leads, learning and development, new employees.

Какая задача: ускорить обучение, ответы по policies and routine HR drafts.

Какие входные данные: HR policy, onboarding docs, training materials, job
description draft, synthetic candidate feedback.

Какой результат: onboarding checklist, policy answer, training summary, draft
JD or feedback note.

Какие инструменты/класс инструментов используются: Microsoft/Google workspace
AI, ChatGPT/Claude Team, internal RAG over HR policies.

Примеры компаний/источников: enterprise AI reports repeatedly include HR and
knowledge-work functions; Anthropic customer examples include HR/people
workflows; Microsoft Work Trend Index describes broad knowledge-worker AI use.

Повторяемость в источниках: средняя-высокая.

Польза: good template and Knowledge category.

Риски: discrimination, privacy, employment-law sensitivity, inappropriate
automation of decisions.

Какие данные чувствительные: candidate data, employee data, reviews, salary,
health/leave information.

Какие ограничения нужны: no automated employment decision, allowed HR data
policy, role-based access, manual review.

Можно ли проверить на synthetic data: да.

Нужны ли реальные данные заказчика: да for HR policy relevance; not for
mechanics.

Подходит ли для нашего Stage 2: maybe.

Почему подходит / почему не подходит: useful but should not outrank core
documents/search unless customer asks.

Предварительный приоритет: средний.

Ссылки на источники:

- https://www.microsoft.com/en-us/worklab/work-trend-index/ai-at-work-is-here-now-comes-the-hard-part
- https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai
- https://www.anthropic.com/learn/claude-for-work

### 5.12. Legal, compliance and safe policy checks

Название сценария: legal/compliance assistant.

Краткое описание: AI helps find policy clauses, compare legal materials,
prepare compliance checklists and surface risks for human review.

Кто использует: legal, compliance, security, procurement, management.

Какая задача: speed up review while keeping final accountability with humans.

Какие входные данные: policy docs, contract extracts, public regulations,
customer-specific allowed/prohibited data classes.

Какой результат: draft risk list, checklist, source-linked answer, unresolved
questions.

Какие инструменты/класс инструментов используются: Claude/ChatGPT enterprise
tools, Perplexity Enterprise for legal research, Microsoft/Google workspace AI,
specialized legal AI tools.

Примеры компаний/источников: Perplexity has legal customer stories; Anthropic
and OpenAI publish enterprise/use-case and data-control materials; Microsoft and
Google document enterprise compliance controls.

Повторяемость в источниках: высокая.

Польза: necessary as guardrail for all Stage 2 domains.

Риски: legal hallucination, outdated law, missing source, access oversharing,
data retention.

Какие данные чувствительные: contracts, claims, legal opinions, internal
investigations, personal data.

Какие ограничения нужны: human legal review, source links, no legal guarantee,
approved provider class, retention rules.

Можно ли проверить на synthetic data: да for checklist shape, not legal quality.

Нужны ли реальные данные заказчика: да for actual policy.

Подходит ли для нашего Stage 2: да as governance and prompt pattern; not as
legal product.

Почему подходит / почему не подходит: directly supports data policy, warnings
and Knowledge restrictions.

Предварительный приоритет: высокий for governance, средний for domain workflow.

Ссылки на источники:

- https://www.perplexity.ai/enterprise/customers
- https://www.anthropic.com/enterprise
- https://openai.com/enterprise-privacy/
- https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-privacy

### 5.13. Development and IT support

Название сценария: engineering and IT assistant.

Краткое описание: AI helps with code explanation, ticket triage, runbook search,
incident notes, shell/SQL draft and internal developer docs.

Кто использует: developers, IT support, DevOps, security engineers.

Какая задача: accelerate technical work and reduce time spent searching docs.

Какие входные данные: code snippets, logs, tickets, runbooks, internal docs,
approved repositories.

Какой результат: explanation, draft fix, runbook answer, incident summary,
support reply.

Какие инструменты/класс инструментов используются: GitHub Copilot Enterprise,
GitLab Duo, Claude Code/Enterprise, ChatGPT Enterprise, internal RAG.

Примеры компаний/источников: GitHub/GitLab publish enterprise AI coding
assistant docs; Anthropic publishes Claude Code and internal engineering usage
research; Microsoft customer materials include developer productivity.

Повторяемость в источниках: высокая.

Польза: clear enterprise category.

Риски: secrets in logs/code, unsafe commands, license/IP questions, wrong code,
production incident leakage.

Какие данные чувствительные: source code, credentials, logs, infra topology,
customer data in logs.

Какие ограничения нужны: secrets policy, repo allowlist, no credential paste,
review gate, audit.

Можно ли проверить на synthetic data: да with fake runbooks/tickets.

Нужны ли реальные данные заказчика: only if this becomes customer IT workflow.

Подходит ли для нашего Stage 2: maybe/future.

Почему подходит / почему не подходит: valuable but not central to current PRD-1
unless customer asks for IT support workspace.

Предварительный приоритет: низкий-средний for current Stage 2.

Ссылки на источники:

- https://docs.github.com/en/copilot/get-started/what-is-github-copilot
- https://docs.gitlab.com/user/gitlab_duo/
- https://www.anthropic.com/claude-code
- https://docs.github.com/en/copilot/get-started/what-is-github-copilot

### 5.14. Usage analytics, cost governance and audit

Название сценария: AI usage and cost visibility.

Краткое описание: admins and owners see who uses AI, which models, how many
messages/tokens, approximate cost, adoption, risky usage and whether hard
limits are needed.

Кто использует: admins, finance/ops, security, managers, platform owner.

Какая задача: управлять usage/cost signal, adoption and risk.

Какие входные данные: usage events, model catalog, provider prices, groups,
users, retention policy.

Какой результат: usage report, cost estimate, gap list, decision whether hard
billing/gateway is needed.

Какие инструменты/класс инструментов используются: OpenWebUI analytics,
Microsoft Copilot usage reports, OpenAI workspace analytics, Anthropic admin
usage, LiteLLM budgets/spend tracking.

Примеры компаний/источников: Microsoft documents Copilot usage reports and
analytics; OpenAI and Anthropic document enterprise admin controls; LiteLLM
documents budgets, virtual keys and spend tracking.

Повторяемость в источниках: высокая.

Польза: directly matches PRD-1 cost visibility and current Stage 2 research.

Риски: confusing analytics with billing, incomplete provider cost mapping,
privacy around user-level reporting, false budget enforcement.

Какие данные чувствительные: user activity, prompts if logged, model/provider
usage, cost centers.

Какие ограничения нужны: minimal logging, role-based admin access, provider
price catalog, separate hard billing ADR.

Можно ли проверить на synthetic data: да for report shape.

Нужны ли реальные данные заказчика: not for mechanics; yes for actual budgets
and reporting policy.

Подходит ли для нашего Stage 2: да.

Почему подходит / почему не подходит: native analytics proof is an unblocked
Stage 2 slice; hard billing remains future.

Предварительный приоритет: высокий.

Ссылки на источники:

- https://learn.microsoft.com/en-us/microsoft-365/admin/activity-reports/microsoft-365-copilot-usage?view=o365-worldwide
- https://learn.microsoft.com/en-us/viva/insights/copilot-analytics-introduction
- https://docs.openwebui.com/features/administration/analytics/
- https://docs.litellm.ai/docs/proxy/virtual_keys
- https://docs.litellm.ai/docs/proxy/users
- https://support.anthropic.com/en/articles/9797557-usage-and-cost

## 6. Applicability Matrix

| Category | Example scenario | Frequency in sources | Fits Stage 2 | Can move without customer | Needs customer data | Risk | Recommendation |
| -------- | ---------------- | -------------------- | ------------ | ------------------------- | ------------------ | ---- | -------------- |
| Meetings/STT | Transcript -> summary/action items | High | Yes | Yes, with fake transcript | Yes for STT acceptance | Medium | Prepare prompt flow and synthetic transcript; wait for media policy. |
| Documents/contracts | PDF/DOCX summary and risk draft | High | Yes | Yes for simple docs/fake contract | Yes for real docs | High | Keep draft-only; prove extraction preview before claims. |
| Internal Knowledge/RAG | Policy Q&A with sources | High | Yes | Yes with synthetic Knowledge | Yes for real Knowledge | High | Start with synthetic Knowledge pack and source attribution rules. |
| Web Search | Public research with citations | High | Yes | Yes with safe query matrix | Only for rollout policy | Medium-high | Continue candidate-set comparison; keep source separation explicit. |
| Tables/reports | Simple XLSX summary | High | Partial | Yes for simple XLSX | Yes for complex Excel | High | Limit Stage 2 to simple proof; defer complex parser. |
| OCR/VL OCR | Scan/table extraction comparison | High | Pilot only | Yes for synthetic benchmark | Yes for real acceptance | High | Select candidates; require provider/data approval. |
| Finance/tax | Broker-report draft analysis | Medium-high | Blocked pilot | Only warning/routing mechanics | Yes | Very high | Do not claim quality before customer samples and expected output. |
| Customer support | Ticket answer draft | High | Maybe | Yes with synthetic tickets | Yes for real policy | High | Keep as optional workspace candidate unless customer prioritizes it. |
| Sales/marketing | Account brief + follow-up | High | Yes | Yes with public/synthetic data | Yes for CRM/company data | Medium-high | Good prompt catalog candidate after governance. |
| HR/onboarding | Policy Q&A and onboarding draft | Medium-high | Maybe | Yes with synthetic HR docs | Yes for policies | High | Do not automate HR decisions; treat as future/optional. |
| Legal/compliance | Compliance checklist draft | High | Governance yes | Yes for synthetic checklist | Yes for actual policy | Very high | Use as guardrail category, not legal-answer product. |
| Dev/IT support | Runbook/ticket assistant | High | Future/maybe | Yes with fake runbooks | Maybe | High | Defer unless customer asks for IT workspace. |
| Analytics/cost | User/model/token/cost report | High | Yes | Yes with synthetic usage | Yes for budget policy | Medium | Native analytics proof first; gateway only if hard limits required. |
| Security/data policy | Allowed/prohibited data rules | High | Yes | Yes as draft policy | Yes for final approval | Very high | Make data policy a gate before provider rollout. |

## 7. Scenarios That Can Move Without Customer Data

- External research synthesis and this scenario taxonomy.
- Prompt template catalog draft for common tasks: summary, rewrite, meeting
  minutes, document Q&A, Web Search answer, data-policy warning.
- Synthetic meeting transcript prompt flow.
- Synthetic Knowledge pack for policy Q&A and source attribution mechanics.
- Simple PDF/DOCX/XLSX extraction proof on synthetic files.
- VL OCR candidate shortlist and synthetic benchmark plan.
- Safe Web Search comparison matrix with public non-sensitive queries.
- Usage analytics proof shape: user/day/week/model/token/message/approximate
  cost.
- Provider/model catalog skeleton with use case, status, data policy and cost
  fields.
- Data policy draft with allowed/prohibited examples, clearly marked as not
  approved by customer.

## 8. Scenarios That Need Customer Input

- Real broker reports and 3-NDFL expected outputs.
- Real scanned PDFs, poor scans, stamps/signatures, PDF tables and XLSX.
- Customer Knowledge: policies, regulations, product docs, sales materials,
  support docs and access groups.
- Real groups, owners, managers and visibility policy.
- No-delete, retention, audit and transcript storage policy.
- Provider allowlist, foreign/Russian/local provider policy and data classes.
- Production Web Search rollout: allowed query classes, logging, cost, group
  defaults and source policy.
- Hard billing/gateway: budget owners, virtual keys, quota behavior, provider
  routing.
- Real meeting media and consent/recording policy.
- Real HR/support/customer datasets.

## 9. Dangerous Illusions

| Illusion | Why it is unsafe | Stage 2 handling |
| -------- | ---------------- | ---------------- |
| AI will correctly process any Excel. | Spreadsheet tools help, but formulas, pivots, hidden sheets and external links can break interpretation. | Simple XLSX proof only; complex parser future. |
| OCR will read everything. | OCR/document AI depends on scan quality, layout, handwriting, stamps and provider limits. | Benchmark candidates and keep manual review. |
| RAG solves knowledge automatically. | RAG quality depends on extraction, chunking, source freshness and access control. | Curate Knowledge and require source visibility. |
| Native analytics equals billing. | Usage reports do not enforce budgets or provider spend limits. | Native analytics first; hard billing via gateway ADR only. |
| Manager visibility means give manager admin access. | Admin access can expose unrelated chats and private data. | Separate manager visibility matrix and retention policy. |
| SearXNG means full privacy. | Private SearXNG can still forward queries to upstream engines. | Document upstream leakage and require owner approval. |
| Synthetic data proves production quality. | Synthetic data proves mechanics, not real broker/OCR/Excel quality. | Use synthetic for proof shape only. |
| Enterprise AI is safe if tenant permissions exist. | Oversharing and broad permissions can still expose data through AI search. | Enforce least privilege and data policy. |
| AI summary is the source of truth. | Summaries can omit, distort or be affected by prompt injection. | Keep source links, warnings and human review. |
| BYOAI is harmless productivity. | Microsoft Work Trend Index reports broad employee AI use; unmanaged use creates data/control risk. | Provide controlled workspace and rules. |

## 10. Candidate Groups For Future User Story Selection

These are not user stories. They are scenario groups that look worth selecting
from in the next task.

High-confidence Stage 2 candidates:

- controlled corporate AI-chat workspace;
- meeting transcript -> summary/action items;
- internal Knowledge/RAG with source attribution;
- document assistant for simple PDF/DOCX and fake contract;
- safe Web Search research with candidate-set comparison;
- usage analytics/cost visibility;
- data policy and provider/model catalog.

Good candidates after customer input:

- broker-report / 3-NDFL draft analysis;
- OCR/VL OCR pilot on real scans and broker reports;
- customer Knowledge on real regulations and internal docs;
- manager visibility and retention/no-delete policy;
- production Web Search rollout.

Keep as optional/future unless customer prioritizes:

- customer support assistant;
- sales/marketing workspace;
- HR/onboarding assistant;
- Dev/IT support assistant;
- hard billing/gateway;
- complex Excel parser;
- production OCR/layout pipeline.

## 11. Source Register

High-quality sources used:

- OpenAI / Moderna customer story: https://openai.com/index/openai-and-moderna/
- OpenAI / Morgan Stanley customer story: https://openai.com/index/morgan-stanley/
- OpenAI / PwC customer story: https://openai.com/index/pwc/
- OpenAI enterprise privacy: https://openai.com/enterprise-privacy/
- Microsoft Work Trend Index 2024: https://www.microsoft.com/en-us/worklab/work-trend-index/ai-at-work-is-here-now-comes-the-hard-part
- Microsoft 365 Copilot overview: https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-overview
- Microsoft 365 Copilot usage report: https://learn.microsoft.com/en-us/microsoft-365/admin/activity-reports/microsoft-365-copilot-usage?view=o365-worldwide
- Copilot Analytics introduction: https://learn.microsoft.com/en-us/viva/insights/copilot-analytics-introduction
- Microsoft 365 Copilot privacy: https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-privacy
- Microsoft Copilot public web access: https://learn.microsoft.com/en-us/copilot/microsoft-365/manage-public-web-access
- Microsoft Copilot in Teams meetings: https://support.microsoft.com/en-us/teams/copilot/catch-up-on-meetings-with-microsoft-365-copilot-in-teams
- Microsoft Word/Excel/PowerPoint agents: https://support.microsoft.com/en-us/office/365-copilot-app/get-started-with-word-excel-and-powerpoint-agents-in-microsoft-365-copilot
- Google Gordon Food Service customer story: https://cloud.google.com/customers/gordon-food-service
- Gemini in Google Docs: https://workspace.google.com/products/docs/ai/
- Gemini in Google Sheets: https://workspace.google.com/resources/spreadsheet-ai/
- Google Meet AI note taking: https://workspace.google.com/solutions/ai/ai-note-taking/
- Google Document AI: https://cloud.google.com/document-ai
- Anthropic Claude use-case guides: https://docs.anthropic.com/en/docs/about-claude/use-case-guides/overview
- Anthropic Claude Enterprise: https://www.anthropic.com/enterprise
- Anthropic financial services: https://www.anthropic.com/solutions/financial-services
- Anthropic usage and cost help: https://support.anthropic.com/en/articles/9797557-usage-and-cost
- Perplexity Enterprise customer stories: https://www.perplexity.ai/enterprise/customers
- GitHub Copilot overview: https://docs.github.com/en/copilot/get-started/what-is-github-copilot
- GitLab Duo docs: https://docs.gitlab.com/user/gitlab_duo/
- Azure AI Document Intelligence: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
- UiPath Document Understanding: https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding
- ABBYY Vantage: https://www.abbyy.com/vantage/
- OpenWebUI Knowledge: https://docs.openwebui.com/features/workspace/knowledge/
- OpenWebUI RAG: https://docs.openwebui.com/features/chat-conversations/rag/
- OpenWebUI document extraction: https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/
- OpenWebUI analytics: https://docs.openwebui.com/features/administration/analytics/
- LiteLLM virtual keys: https://docs.litellm.ai/docs/proxy/virtual_keys
- LiteLLM budgets and rate limits: https://docs.litellm.ai/docs/proxy/users
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- McKinsey State of AI: https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai
- Deloitte State of AI in the Enterprise: https://www.deloitte.com/us/en/what-we-do/capabilities/applied-artificial-intelligence/content/state-of-ai-in-the-enterprise.html
- BCG AI Radar 2026: https://www.bcg.com/publications/2026/as-ai-investments-surge-ceos-take-the-lead

Weak/community signals:

- No weak source is used as proof. Community threads remain useful only as
  warning material for implementation tasks, especially around RAG quality,
  source attribution, OpenWebUI feature gaps and provider/runtime drift.
