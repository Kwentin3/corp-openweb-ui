# Stage 2 Engineering Domain

Этот домен не является реализацией Stage 2. Это инженерная карта, roadmap и research findings перед
реализацией.

## 1. Что такое Stage 2

Stage 2 развивает корпоративный OpenWebUI-портал из пилотного AI-чата в управляемую рабочую
AI-среду: рабочие сценарии, группы, prompts/templates, транскрибация, брокерские отчеты, web-search,
документы, провайдеры, basic analytics и контроль доступа.

## 2. Финальная PRD-1

Актуальный источник истины:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md).

Короткое customer summary:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md).

## 3. PRD-0 и post-acceptance audit

- PRD-0: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Post-acceptance audit:
  [PRD-0 post-acceptance audit][prd0-post-acceptance-audit].

[prd0-post-acceptance-audit]: ../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md

## 4. Как пользоваться этим доменом

1. Начать с [CONTEXT_INDEX.md](CONTEXT_INDEX.md), если задача точечная.
2. Открыть [DOMAIN_MAP.md](DOMAIN_MAP.md), если нужно понять границы Stage 2.
3. Открыть [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md), если задача касается custom logic,
   provider calls, storage, policy, usage or UI/backend split.
4. Открыть профильный blueprint в [blueprints/](blueprints/).
5. Открыть связанные research-документы в [research/](research/).
6. Проверить acceptance в [acceptance/ACCEPTANCE_MATRIX.md](acceptance/ACCEPTANCE_MATRIX.md).
7. Проверить implementation gates в [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md).
8. Не начинать implementation до review roadmap/blueprints/research, ADR по спорным точкам и runtime
   proof.

## 5. Backend-first delivery principle

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs.
Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or
access rules are decided.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live in
bounded domain services, internal APIs, or thin integration shims.

The frontend must not own security, provider keys, data policy, retention,
manager visibility or usage accounting.

Практический порядок для спорных доменов:

1. ADR / policy decision.
2. Backend contract and runtime proof.
3. Minimal backend/API slice.
4. UI/browser integration.
5. Polish and user-facing instructions.

Этот порядок обязателен для STT proxy, OCR/VL OCR pipeline, manager visibility, no-delete/retention,
provider setup, usage analytics and web-search.

## 6. Карта документов

| Документ | Назначение |
| -------- | ---------- |
| [ROADMAP.md](ROADMAP.md) | Дорожная карта подготовки к реализации. |
| [CONTEXT_INDEX.md](CONTEXT_INDEX.md) | Быстрый индекс: что читать по домену/задаче. |
| [DOMAIN_MAP.md](DOMAIN_MAP.md) | Карта инженерных доменов Stage 2. |
| [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md) | Доменные границы и versioned internal contracts. |
| [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md) | Gates перед implementation planning. |
| [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md) | Planning backlog без issue-tracker семантики. |
| [blueprints/](blueprints/) | Доменные инженерные рамки, не реализация. |
| [research/](research/) | Research findings, источники, blockers и next steps. |
| [decisions/](decisions/) | ADR-шаблон и будущие architecture decisions. |
| [acceptance/](acceptance/) | Acceptance matrix и требования к тестовым данным. |

## 7. Домены Stage 2

1. Workspaces / RBAC / shared prompts.
2. Transcription / STT / ffmpeg browser workflow.
3. Broker reports / 3-НДФЛ.
4. Web-search.
5. Documents / OCR / VL OCR / Excel.
6. Provider catalog / models.
7. Usage analytics / cost visibility.
8. Security / data policy / future masking.
9. Manager visibility / no-delete / retention / audit policy.
10. Operations / acceptance / testing.

## 8. Что уже согласовано с заказчиком

- PRD-1 является source of truth для Stage 2.
- Приоритеты: транскрибация, брокерские отчеты, web-search.
- Транскрибация использует существующий ffmpeg workflow как technical asset.
- STT provider call должен идти через server-side proxy; API keys не попадают в браузер.
- Lemonfox - приоритетный STT candidate.
- Web-search нужен всем пользователям, но с rules, limits, result count, concurrency и cost
  visibility.
- OCR/layout-aware PDF включается как pilot/research, production-grade pipeline не обещается.
- Доступ руководителей к рабочим чатам включен как requirement/check, но не как просмотр всех личных
  чатов.
- Запрет удаления чатов пользователями требует technical check.
- No Delete, Retention, Audit and immutable archive are separate decisions.
- Provider setup не стартует до утверждения data policy by provider class.
- OCR pilot должен отдельно проверить VL OCR / vision-language OCR candidates на сканах,
  изображениях, сложных PDF и таблицах.
- Data masking/tokenization - future security slice, не implementation текущего Practical Stage 2.
- Custom capabilities изолируются за backend/domain contracts; OpenWebUI core не патчится глубоко без
  отдельного rationale.

## 9. Research snapshot от 2026-06-18

Research выполнен по первичным источникам и локальным repo evidence. Это не runtime implementation и
не настройка провайдеров.

Подробный отчет:
[Research actualization report][research-actualization-report].

[research-actualization-report]: ../reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md

### OpenWebUI native capabilities

Finding:

- Native-first оправдан для RBAC/groups, shared resources, web-search, RAG/docs and analytics.

Next action:

- Read-only Admin UI audit on deployed/staging v0.9.6.

### Transcription / STT

Finding:

- Lemonfox подходит как priority candidate, но PRD-1 workflow требует server-side STT proxy/adapter.

Next action:

- Human review of [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md).
- Operator/customer input for the missing actual ffmpeg workflow artifact.

### ffmpeg browser workflow

Finding:

- Browser ffmpeg viable as sidecar/module; actual workflow artifact not in repo.

Next action:

- Inspect existing workflow and run browser smoke.

### Web-search

Finding:

- Brave `brave_llm_context` is best first pilot if foreign provider is allowed.
- Yandex Search API is Russian-provider candidate.

Next action:

- Provider ADR and customer cost/privacy approval.

### Documents / OCR / Excel

Finding:

- OpenWebUI has extraction engines.
- OCR/layout-aware broker reports must stay pilot until customer samples are tested.
- VL OCR is promising but unproven.

Next action:

- Collect test documents, select OCR/VL OCR candidates and run extraction preview.

### Providers / model catalog

Finding:

- Use exact model IDs.
- Claude API is not Claude Code.
- DeepSeek/YandexGPT/GigaChat need policy/procurement decision.

Next action:

- Provider catalog ADR.

### Analytics / costs

Finding:

- Native analytics may satisfy basic visibility.
- Hard budgets require gateway/future ADR.

Next action:

- Runtime analytics proof with test users/groups.

### Manager visibility / no-delete

Finding:

- Native RBAC/sharing and chat-delete permission are plausible.
- Manager supervision and no-delete need runtime proof.

Next action:

- Test user matrix and customer privacy policy.

### Data masking

Finding:

- Useful building blocks exist, but masking/tokenization is future security slice.

Next action:

- Data policy now; masking ADR later.

## 10. Что не является реализацией на текущем шаге

- Нет кода.
- Нет provider setup.
- Нет server changes.
- Нет compose/env/scripts changes.
- Нет OpenWebUI fork.
- Нет API keys.
- Нет production changes.

## 11. ADR order and execution order

ADR registry order:

1. [ADR-0001 Data Policy by Provider Class](decisions/ADR-0001-data-policy-by-provider-class.md).
2. [ADR-0002 Manager Visibility Policy](decisions/ADR-0002-manager-visibility-policy.md).
3. [ADR-0003 Chat Deletion, Retention and
   Audit](decisions/ADR-0003-chat-deletion-retention-audit.md).
4. [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md).
5. [ADR-0005 OCR / VL OCR Pilot Scope](decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md).
6. [ADR-0006 Provider Model Catalog](decisions/ADR-0006-provider-model-catalog.md).
7. [ADR-0007 Web-search Provider](decisions/ADR-0007-web-search-provider.md).
8. [ADR-0008 Native Analytics vs Hard
   Billing](decisions/ADR-0008-native-analytics-vs-hard-billing.md).

Recommended execution / review order:

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.
9. Runtime proof matrix.
10. Customer test data package.
11. Implementation backlog by slices.

Numbers are the ADR registry order. Execution order reflects implementation
dependencies.

## 12. Следующий шаг

Review [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md)
and provide the actual ffmpeg workflow artifact for contract inspection.

После ADR/gates можно готовить implementation slices and acceptance sequence.

## 13. Source inventory

Найдены и использованы как контекст:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md`
- `docs/blueprint/*`
- `docs/infra/*`
- `docs/ops/*`
- `docs/security/*`
- `docs/reports/2026-06-09/*`

Отсутствует:

- `docs/README.md`
