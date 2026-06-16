# OpenWebUI PRD-1 Refined Changelog

Дата: 2026-06-16
Исходный документ: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
Новый документ: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED.md`

## Что изменено

- PRD-1 переформулирован как customer-facing refined draft перед согласованием.
- Сохранена основная логика enriched draft: OpenWebUI native-first, рабочие сценарии, группы, prompts, Knowledge, web-search, транскрибация, документы, providers, analytics/cost control, AD/SSO discovery.
- Усилена продуктовая рамка: Stage 2 продает не количество моделей, а управляемые рабочие сценарии.
- Добавлено объяснение для заказчика, почему PRD-1 не должен обещать "магическую" обработку любых Word/PDF/Excel.
- Добавлена явная связь с PRD-0 post-acceptance audit: PRD-0 accepted, но Stage 2 должен начинаться с discovery и подтверждения текущих operator/runtime фактов.

## Новые разделы

- `Customer-facing explanation`.
- `Scope buckets`.
- `Recommended document processing strategy`.
- `Document capability levels`.
- `Recommended Stage 2 delivery model`.
- `Effort estimate` с рабочей оценкой реализации по часам.
- Расширенный блок по офисным документам: DOCX, PDF, XLSX.
- Расширенные `Drift notes`.

## Scope buckets

Добавлено разделение scope на три корзины:

1. Обязательное ядро Stage 2:
   - рабочие сценарии;
   - группы доступа;
   - curated workspace models;
   - общие prompts;
   - общие инструкции/Knowledge;
   - model catalog;
   - базовая аналитика расходов;
   - user/admin docs;
   - smoke/acceptance checks;
   - политика допустимых данных.

2. Пилотные сценарии Stage 2:
   - брокерские отчеты / 3-НДФЛ;
   - транскрибация встреч;
   - PDF/DOCX/XLSX;
   - web-search;
   - DeepSeek/YandexGPT/GigaChat/Claude provider evaluation.

3. Отдельные architecture decisions / future slices:
   - fork OpenWebUI;
   - browser-side ffmpeg.wasm;
   - LiteLLM/gateway;
   - hard budgets/enforcement;
   - full AD lifecycle / SCIM rollout;
   - production document pipeline;
   - сложный Excel parser;
   - OCR/layout pipeline;
   - доступ руководителей к чатам сотрудников;
   - полноценный RAG по всем документам компании;
   - агентная система для действий в 1С/CRM.

## Смягченные формулировки

- "Работа с Word/PDF/Excel" заменена на "типовые сценарии работы с документами с описанными ограничениями".
- "Excel-анализ" уточнен: LLM не считается единственным вычислителем; точные расчеты должны идти через parser/tool/code path.
- "Генерация документов" ограничена template-based generation, а не свободным созданием любых DOCX/XLSX.
- "Биллинг" уточнен как native analytics and cost estimation first; hard enforcement только после gateway decision.
- "AD/SSO" уточнен как discovery и pilot scheme, а не полный AD lifecycle.
- "Fork OpenWebUI" сформулирован как implementation tool, not product goal.
- "DeepSeek уже подключен" переведен в `needs operator evidence`, потому что текущий repo evidence это не подтверждает.

## Риски, вынесенные отдельно

- Бесшовная обработка любых офисных документов может быть неверно понята заказчиком как production document workflow.
- XLSX с формулами, merged cells, макросами, сводными таблицами и внешними ссылками требует parser/tool decision.
- PDF с таблицами, сканами, подписями и печатями требует OCR/layout-aware approach.
- DOCX generation требует шаблонов, иначе сохранение структуры и верстки не гарантируется.
- Доступ руководителей к чатам сотрудников требует privacy/security decision.
- OpenWebUI pinned в PRD-0 на `v0.9.6`, а native capability map нужно сверить с deployed version перед implementation.

## Что перенесено из обязательного scope в architecture decisions

- LiteLLM/gateway.
- Hard budgets/enforcement.
- Browser-side ffmpeg.wasm.
- Fork OpenWebUI.
- Production-grade document pipeline.
- OCR/layout-aware PDF parsing.
- Complex Excel parser.
- Template/export tools для production DOCX/XLSX.
- Full AD lifecycle / SCIM rollout.
- Manager access to subordinate chats.

## Новые non-goals

Добавлены:

- гарантия корректной обработки любых офисных документов;
- бесшовное сохранение исходной верстки DOCX/PDF;
- юридически значимое сравнение документов;
- точная обработка любых Excel-файлов с формулами, макросами, сводными таблицами и внешними ссылками;
- production-grade OCR/layout pipeline;
- автоматическая генерация любых DOCX/XLSX без утвержденных шаблонов;
- замена бухгалтера, налогового консультанта, юриста или финансового аналитика;
- автоматическое принятие решений на основе брокерских/налоговых документов;
- hard billing без gateway decision;
- full AD lifecycle без customer infrastructure discovery;
- обязательный fork OpenWebUI без fork rationale.

## Финансовая таблица

- Финансовая таблица из enriched draft сохранена.
- Тарифы не удалялись.
- В refined PRD добавлена оговорка: цены проверены на 2026-06-16 и должны быть перепроверены перед коммерческим предложением и production-включением.

## Оценка трудозатрат

- Добавлена легкая рабочая оценка реализации по часам.
- Рекомендуемый baseline для согласования: 72-108 часов.
- Baseline покрывает native-first ядро, 3 рабочих сценария, видимость расходов, provider evaluation и 2-3 пилотных сценария.
- LiteLLM/gateway, production document pipeline, fork OpenWebUI, сложный Excel/OCR и full AD lifecycle оставлены как опциональные оценки после отдельного decision/discovery.

## Итог

Новый PRD-1 refined лучше подходит для согласования с заказчиком: он показывает пользу Stage 2, удерживает реалистичные границы обещаний, отделяет обязательное ядро от пилотных сценариев и выносит рискованные технические решения в отдельные architecture decisions.
