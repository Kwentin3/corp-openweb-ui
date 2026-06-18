# Stage 2 Engineering Domain

Этот домен не является реализацией Stage 2. Это инженерная карта, roadmap и research findings перед реализацией.

## 1. Что такое Stage 2

Stage 2 развивает корпоративный OpenWebUI-портал из пилотного AI-чата в управляемую рабочую AI-среду: рабочие сценарии, группы, prompts/templates, транскрибация, брокерские отчеты, web-search, документы, провайдеры, basic analytics и контроль доступа.

## 2. Финальная PRD-1

Актуальный источник истины: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md).

Короткое customer summary: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md).

## 3. PRD-0 и post-acceptance audit

- PRD-0: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Post-acceptance audit: [docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md](../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md)

## 4. Как пользоваться этим доменом

1. Начать с [CONTEXT_INDEX.md](CONTEXT_INDEX.md), если задача точечная.
2. Открыть [DOMAIN_MAP.md](DOMAIN_MAP.md), если нужно понять границы Stage 2.
3. Открыть профильный blueprint в [blueprints/](blueprints/).
4. Открыть связанные research-документы в [research/](research/).
5. Проверить acceptance в [acceptance/ACCEPTANCE_MATRIX.md](acceptance/ACCEPTANCE_MATRIX.md).
6. Не начинать implementation до review roadmap/blueprints/research и ADR по спорным точкам.

## 5. Карта документов

| Документ | Назначение |
| -------- | ---------- |
| [ROADMAP.md](ROADMAP.md) | Дорожная карта подготовки к реализации. |
| [CONTEXT_INDEX.md](CONTEXT_INDEX.md) | Быстрый индекс: что читать по домену/задаче. |
| [DOMAIN_MAP.md](DOMAIN_MAP.md) | Карта инженерных доменов Stage 2. |
| [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md) | Planning backlog без issue-tracker семантики. |
| [blueprints/](blueprints/) | Доменные инженерные рамки, не реализация. |
| [research/](research/) | Research findings, источники, blockers и next steps. |
| [decisions/](decisions/) | ADR-шаблон и будущие architecture decisions. |
| [acceptance/](acceptance/) | Acceptance matrix и требования к тестовым данным. |

## 6. Домены Stage 2

1. Workspaces / RBAC / shared prompts.
2. Transcription / STT / ffmpeg browser workflow.
3. Broker reports / 3-НДФЛ.
4. Web-search.
5. Documents / OCR / Excel.
6. Provider catalog / models.
7. Usage analytics / cost visibility.
8. Security / data policy / future masking.
9. Manager visibility / chat retention / no-delete policy.
10. Operations / acceptance / testing.

## 7. Что уже согласовано с заказчиком

- PRD-1 является source of truth для Stage 2.
- Приоритеты: транскрибация, брокерские отчеты, web-search.
- Транскрибация использует существующий ffmpeg workflow как technical asset.
- STT provider call должен идти через server-side proxy; API keys не попадают в браузер.
- Lemonfox - приоритетный STT candidate.
- Web-search нужен всем пользователям, но с rules, limits, result count, concurrency и cost visibility.
- OCR/layout-aware PDF включается как pilot/research, production-grade pipeline не обещается.
- Доступ руководителей к рабочим чатам включен как requirement/check, но не как просмотр всех личных чатов.
- Запрет удаления чатов пользователями требует technical check.
- Data masking/tokenization - future security slice, не implementation текущего Practical Stage 2.

## 8. Research snapshot от 2026-06-18

Research выполнен по первичным источникам и локальным repo evidence. Это не runtime implementation и не настройка провайдеров.

Подробный отчет: [../reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md](../reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md).

| Тема | Вывод | Следующее действие |
| ---- | ----- | ------------------ |
| OpenWebUI native capabilities | Native-first оправдан для RBAC/groups, shared resources, web-search, RAG/docs and analytics. | Read-only Admin UI audit on deployed/staging v0.9.6. |
| Transcription / STT | Lemonfox подходит как priority candidate, но PRD-1 workflow требует server-side STT proxy/adapter. | ADR for STT proxy boundary. |
| ffmpeg browser workflow | Browser ffmpeg viable as sidecar/module; actual workflow artifact not in repo. | Inspect existing workflow and run browser smoke. |
| Web-search | Brave `brave_llm_context` is best first pilot if foreign provider is allowed; Yandex Search API is Russian-provider candidate. | Provider ADR and customer cost/privacy approval. |
| Documents/OCR/Excel | OpenWebUI has extraction engines; OCR/layout-aware broker reports must stay pilot until customer samples are tested. | Collect test documents and run extraction preview. |
| Providers/model catalog | Use exact model IDs; Claude API is not Claude Code; DeepSeek/YandexGPT/GigaChat need policy/procurement decision. | Provider catalog ADR. |
| Analytics/costs | Native analytics may satisfy basic visibility; hard budgets require gateway/future ADR. | Runtime analytics proof with test users/groups. |
| Manager visibility/no-delete | Native RBAC/sharing and chat-delete permission are plausible, but manager supervision and no-delete need runtime proof. | Test user matrix and customer privacy policy. |
| Data masking | Useful building blocks exist, but masking/tokenization is future security slice. | Data policy now; masking ADR later. |

## 9. Что не является реализацией на текущем шаге

- Нет кода.
- Нет provider setup.
- Нет server changes.
- Нет compose/env/scripts changes.
- Нет OpenWebUI fork.
- Нет API keys.
- Нет production changes.

## 10. Следующий шаг

Согласовать ADR/decision notes по спорным точкам:

- STT proxy boundary;
- web-search provider;
- provider model catalog;
- manager visibility and no-delete policy;
- native analytics vs hard billing;
- OCR pilot scope.

После этого можно готовить implementation slices and acceptance sequence.

## 11. Source inventory

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
