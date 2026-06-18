# Stage 2 Engineering Domain

Этот домен не является реализацией Stage 2. Это инженерная карта, roadmap и research-план перед реализацией.

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
6. Не начинать implementation до review roadmap/blueprints/research.

## 5. Карта документов

| Документ | Назначение |
| -------- | ---------- |
| [ROADMAP.md](ROADMAP.md) | Дорожная карта подготовки к реализации. |
| [CONTEXT_INDEX.md](CONTEXT_INDEX.md) | Быстрый индекс: что читать по домену/задаче. |
| [DOMAIN_MAP.md](DOMAIN_MAP.md) | Карта инженерных доменов Stage 2. |
| [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md) | Planning backlog без issue-tracker семантики. |
| [blueprints/](blueprints/) | Доменные инженерные рамки, не реализация. |
| [research/](research/) | Что нужно проверить перед implementation. |
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

## 8. Что пока требует research

- Deployed OpenWebUI version и native capabilities.
- Workspaces, prompts, knowledge, groups, RBAC и manager visibility.
- STT path, Lemonfox limits, ffmpeg browser workflow integration.
- Web-search provider choice: Brave и российский provider.
- Documents/OCR/Excel limits и pilot scope.
- Provider catalog: Claude API, GPT-mini, DeepSeek, YandexGPT/GigaChat.
- Usage analytics vs gateway/hard billing.
- Chat deletion/retention behavior.
- Future data masking architecture.

## 9. Что не является реализацией на текущем шаге

- Нет кода.
- Нет provider setup.
- Нет server changes.
- Нет compose/env/scripts changes.
- Нет OpenWebUI fork.
- Нет API keys.
- Нет production changes.

## 10. Следующий шаг

Review planning docs before implementation. После review можно отдельно согласовать implementation plan, architecture decisions и slice backlog.

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
