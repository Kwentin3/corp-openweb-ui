# OpenWebUI PRD-1 Changelog

Дата: 2026-06-16
Последняя актуализация: 2026-06-18
Исторический draft: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md`
Актуальный PRD / source of truth: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`

## Актуализация 2026-06-18: customer clarifications

Внесены уточнения заказчика и исполнителя без переписывания PRD-1 с нуля.

Что изменилось по транскрибации и ffmpeg:

- browser-side media preprocessing больше не описывается как сомнительная research-идея с нуля;
- зафиксировано, что у исполнителя уже есть рабочий ffmpeg workflow для desktop/mobile;
- транскрибация аудио/видео поднята в основной Practical Stage 2 deliverable;
- архитектура уточнена: GUI upload -> browser-side ffmpeg/wasm preprocessing -> server-side STT proxy -> Lemonfox/другой STT provider -> UI templates;
- STT API keys запрещено передавать в браузер;
- основной риск перенесен с ffmpeg на OpenWebUI integration: UI, proxy endpoint, права, лимиты, хранение результата, шаблоны и обновляемость.

Что изменилось по data masking:

- полноценная автоматическая подмена данных на теги не включена как реализация Practical Stage 2;
- добавлена customer-facing формулировка: идея правильная, но поверхностная реализация создает ложное чувство безопасности;
- data masking/tokenization вынесен в future security/data-protection slice;
- добавлены требования к будущему доверенному контуру: локальное распознавание, теги, защищенная карта маппинга, отправка обезличенного контекста, обратная подстановка, логирование и контроль утечек;
- local LLM/NER для чувствительных сущностей оценен как отдельный optional slice.

Что изменилось по Claude API:

- терминологически закреплено `Claude API / Claude models`;
- `Claude Code` описан как отдельный dev/agentic coding tool, не provider для обычного OpenWebUI-чата;
- `Claude Code` не входит в Practical Stage 2 без отдельного dev-agent scenario.

Что стало обязательным scope Practical Stage 2:

- транскрибация аудио/видео на базе существующего ffmpeg workflow;
- server-side STT proxy и Lemonfox как приоритетный STT provider candidate;
- web-search для всех пользователей с правилами, лимитами, result count/concurrency settings, инструкцией и cost visibility;
- OCR/layout-aware PDF discovery + pilot на реальных документах заказчика;
- проверка и настройка доступа руководителей к рабочим чатам своей группы/рабочего пространства;
- technical check запрета удаления пользовательских чатов всем кроме админов;
- policy допустимых данных, warnings и ручные рекомендации по обезличиванию;
- уточненные группы пользователей и владельцы templates/prompts.

Что осталось optional/future:

- full data masking/tokenization subsystem;
- local LLM/NER for sensitive data;
- full AD lifecycle / SCIM;
- hard billing/gateway;
- production-grade OCR/layout pipeline;
- complex Excel parser;
- production DOCX/XLSX generation;
- deep OpenWebUI fork;
- full document management/storage.

Как изменились часы:

- старый baseline `72-108 hours` больше не соответствует обновленному scope;
- новая оценка `Base Stage 2 Lite`: `104-148-208 hours`;
- новая оценка `Practical Stage 2`: `144-212-304 hours`;
- новая оценка `Extended Stage 2`: `220-320-480 hours`;
- optional slices оценены отдельно и не включены автоматически в Practical Stage 2.

## Что изменено

- PRD-1 переформулирован как актуальный customer-facing документ перед согласованием.
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
   - транскрибация встреч, аудио и видео на базе existing ffmpeg workflow;
   - PDF/DOCX/XLSX;
   - OCR/layout-aware PDF pilot;
   - web-search;
   - DeepSeek/YandexGPT/GigaChat/Claude API/GPT-mini provider evaluation.

3. Отдельные architecture decisions / future slices:
   - fork OpenWebUI;
   - LiteLLM/gateway;
   - hard budgets/enforcement;
   - full AD lifecycle / SCIM rollout;
   - production document pipeline;
   - сложный Excel parser;
   - production-grade OCR/layout pipeline;
   - full data masking/tokenization subsystem;
   - local LLM/NER for sensitive data;
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
- Доступ руководителей к рабочим чатам сотрудников включен в Stage 2 как requirement/check, но требует privacy/security policy.
- OpenWebUI pinned в PRD-0 на `v0.9.6`, а native capability map нужно сверить с deployed version перед implementation.

## Что осталось outside Practical Stage 2 после актуализации

- LiteLLM/gateway.
- Hard budgets/enforcement.
- Deep fork OpenWebUI.
- Production-grade document pipeline.
- Production-grade OCR/layout-aware PDF pipeline.
- Complex Excel parser.
- Template/export tools для production DOCX/XLSX.
- Full AD lifecycle / SCIM rollout.
- Full data masking/tokenization subsystem.
- Local LLM/NER for sensitive data.

## Новые non-goals

Добавлены:

- гарантия корректной обработки любых офисных документов;
- бесшовное сохранение исходной верстки DOCX/PDF;
- юридически значимое сравнение документов;
- точная обработка любых Excel-файлов с формулами, макросами, сводными таблицами и внешними ссылками;
- production-grade OCR/layout pipeline;
- автоматическая генерация любых DOCX/XLSX без утвержденных шаблонов;
- автоматическая подмена чувствительных данных на теги без отдельного защищенного subsystem;
- local LLM/NER для data masking;
- замена бухгалтера, налогового консультанта, юриста или финансового аналитика;
- автоматическое принятие решений на основе брокерских/налоговых документов;
- hard billing без gateway decision;
- full AD lifecycle без customer infrastructure discovery;
- обязательный deep fork OpenWebUI без fork rationale.

## Финансовая таблица

- Финансовая таблица из enriched draft сохранена.
- Тарифы не удалялись.
- В актуальный PRD добавлена оговорка: цены проверены на 2026-06-16 и должны быть перепроверены перед коммерческим предложением и production-включением.

## Оценка трудозатрат

- Оценка пересчитана по обновленному scope.
- `Base Stage 2 Lite`: 104-148-208 часов.
- `Practical Stage 2`: 144-212-304 часов.
- `Extended Stage 2`: 220-320-480 часов.
- LiteLLM/gateway, production document pipeline, deep fork OpenWebUI, complex Excel, production OCR/layout, full AD lifecycle и data masking subsystem оставлены как optional/future slices.

## Итог

Актуальный PRD-1 лучше подходит для согласования с заказчиком: он показывает пользу Stage 2, удерживает реалистичные границы обещаний, отделяет обязательное ядро от пилотных сценариев и выносит рискованные технические решения в отдельные architecture decisions.
