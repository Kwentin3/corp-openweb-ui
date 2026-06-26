# Stage 2 Scope Reconciliation for 150K Contract

## 1. Purpose

Цель документа - зафиксировать, как корректно сузить полный Stage 2 из PRD-1 под договор на 150 000 рублей с учетом уже фактически выполненных работ.

Документ не является договором. Его назначение - дать безопасную основу для предмета договора, приложения к договору, акта или коммерческого описания результата.

Главный вывод: договор на 150 000 рублей не должен описывать весь PRD-1 как завершенный. Корректная формулировка - первый функционально-архитектурный срез Stage 2, где пользовательски реализованы транскрибация аудио/видео и базовый Web Search, а остальные направления Stage 2 подготовлены архитектурно, документально или вынесены в будущие этапы.

## 2. Inputs Reviewed

Проверены следующие источники и артефакты:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`
- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`
- `deploy/openwebui-static/loader.js`
- `services/stage2-stt/`
- `compose/openwebui.compose.yml`
- `compose/searxng.private.compose.yml`
- `deploy/searxng/`

Секреты, значения переменных окружения, приватные токены, тексты пользовательских транскриптов и административные доступы в этот документ не включались.

## 3. Full PRD-1 Planned Scope

Полный Stage 2 по PRD-1 шире бюджета 150 000 рублей. Он включает не только пользовательские функции, но и управляемую корпоративную среду, политики доступа, документы, OCR, брокерские сценарии, управленческую видимость, retention, аналитику стоимости и приемочные контуры.

Крупные направления полного PRD-1:

- корпоративная рабочая среда и workspace model;
- группы, RBAC и доступы;
- общие prompts, templates и knowledge;
- каталог моделей и provider policy;
- STT / transcription;
- Web Search;
- документы PDF/DOCX/XLSX;
- OCR / VL OCR / layout-aware PDF;
- broker reports / 3-НДФЛ;
- manager visibility / read-only access to work chats;
- no-delete / retention / audit;
- data policy / provider class policy;
- analytics / cost visibility;
- пользовательская и администраторская документация;
- acceptance, smoke, gates и backlog.

В рамках 150 000 рублей корректно принять не весь PRD-1, а ограниченный срез: реализованные пользовательские capabilities, архитектурную подготовку следующих направлений и приемочную документацию.

## 4. Actual Implementation Status by Direction

| PRD-1 direction | Planned in full Stage 2 | Actual status | Evidence | Include in 150K? | Commercial wording | Notes |
|---|---|---|---|---|---|---|
| Корпоративная рабочая среда / workspace model | Управляемая корпоративная рабочая среда, сценарии работы, workspace rules. | DONE_ARCHITECTURE | `docs/stage2/README.md`, `docs/stage2/CONTEXT_INDEX.md`, `docs/stage2/ENGINEERING_BACKLOG.md`, PRD-1. | Да, как архитектурная подготовка. | Архитектурная подготовка управляемой корпоративной рабочей среды OpenWebUI. | Полноценная настройка рабочих пространств и эксплуатационные правила остаются будущим scope. |
| Groups/RBAC/access | Группы пользователей, роли, доступы, правила включения функций. | PARTIAL | PRD-1, `docs/stage2/IMPLEMENTATION_GATES.md`, `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`. | Частично. | Анализ и подготовка рамки для дальнейшего управления доступами и группами. | Не заявлять как завершенную RBAC-функцию. Политики групп, allow/deny и rollout governance остаются будущим scope. |
| Shared prompts/templates/knowledge | Общие prompts, templates, инструкции и knowledge-базы. | PLANNED_FUTURE | PRD-1, Stage 2 backlog/context docs. | Нет, кроме фиксации как следующего направления. | Направление включено в дальнейший Stage 2 roadmap. | Не включать в 150K как готовую пользовательскую функцию. |
| Model catalog/provider policy | Каталог моделей, provider classes, правила выбора и ограничения провайдеров. | PARTIAL | PRD-1, `docs/stage2/CONTEXT_INDEX.md`, Web Search contracts, STT context pack. | Да, как архитектурная подготовка. | Подготовлены границы и принципы provider policy для STT и Web Search. | Единый production model catalog, hard budgets и централизованный gateway не завершены. |
| STT / transcription | Транскрибация аудио/видео через безопасный серверный контур. | DONE_FEATURE | `services/stage2-stt/`, `deploy/openwebui-static/loader.js`, `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`, `OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`, `OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`. | Да. | Реализован модуль транскрибации аудио/видео в OpenWebUI через browser normalization, private STT sidecar и provider proxy. | Production hardening для mobile, long files, cancel, retention, history/export и monitoring остается будущим scope. |
| Web Search | Web Search для пользователей с политиками, лимитами, governance и cost visibility. | DONE_BASELINE | `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`, `OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`, `OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`, `OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`, `OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`, `compose/searxng.private.compose.yml`, `deploy/searxng/`. | Да. | Реализован базовый контур Web Search как LLM search tool с provider paths Brave, Yandex Search API и private SearXNG. | Brave/Yandex были относительно простыми через native API/config/Admin GUI. SearXNG потребовал отдельной private-infra подготовки. Full governance, policies, logs, limits, forbidden-query policy, cost visibility и quality matrix не закрыты. |
| Documents: PDF/DOCX/XLSX | Документные сценарии, загрузка и обработка PDF/DOCX/XLSX. | RESEARCH_ONLY | PRD-1, Stage 2 backlog/context docs. | Нет. | Документный pipeline сохранен как будущий этап. | Не включать как готовую функцию в 150K. |
| OCR / VL OCR / layout-aware PDF | OCR, vision-language OCR, layout-aware PDF processing. | RESEARCH_ONLY | PRD-1, Stage 2 backlog/context docs. | Нет. | OCR/VL OCR рассматривается как отдельный будущий пилот/этап. | Не заявлять production OCR или pilot как завершенные в 150K. |
| Broker reports / 3-НДФЛ | Брокерские отчеты и сценарии подготовки 3-НДФЛ. | PLANNED_FUTURE | PRD-1. | Нет. | Брокерские отчеты и 3-НДФЛ остаются отдельным будущим направлением. | Не включать в текущий договор как выполненную работу. |
| Manager visibility / read-only access to work chats | Управленческий read-only доступ к рабочим чатам и правила видимости. | PLANNED_FUTURE | PRD-1, Stage 2 backlog/context docs. | Нет. | Направление зафиксировано для дальнейшей проработки. | Требует отдельного решения по privacy, ролям, retention и UX. |
| No-delete / retention / audit | Запрет удаления, retention policy, аудит действий и технические проверки. | PLANNED_FUTURE | PRD-1, Stage 2 gates/backlog. | Нет. | Требования retention и audit вынесены в следующий scope. | В 150K не заявлять как завершенную compliance-функцию. |
| Data policy / provider class policy | Классы данных, правила отправки во внешние провайдеры, privacy/data-egress controls. | DONE_ARCHITECTURE | `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`, `WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`, STT proxy boundary docs, PRD-1. | Да, как архитектурный результат. | Подготовлены boundary contracts для STT и Web Search, включая privacy/source/usage constraints. | Финальная утвержденная data policy и enforcement остаются будущим scope. |
| Analytics / cost visibility | Видимость стоимости, usage analytics, лимиты и отчеты. | PLANNED_FUTURE | PRD-1, Web Search backlog and closeout reports. | Нет. | Cost visibility и analytics сохранены как отдельный следующий этап. | В Web Search baseline cost visibility прямо остается незакрытым governance gap. |
| User/admin docs | Документация для пользователя, администратора и передачи контекста. | DONE_ARCHITECTURE | `README.md`, `docs/stage2/README.md`, `docs/stage2/CONTEXT_INDEX.md`, `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`, reports. | Да. | Подготовлен комплект Stage 2 документации, audit/reports и context handoff для дальнейшей приемки и развития. | Это не заменяет полный пользовательский manual для всех будущих направлений PRD-1. |
| Acceptance/smoke/gates/backlog | Приемочная матрица, smoke evidence, gates, backlog и staged delivery discipline. | DONE_ARCHITECTURE | `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`, `docs/stage2/IMPLEMENTATION_GATES.md`, `docs/stage2/ENGINEERING_BACKLOG.md`, runtime and Playwright reports. | Да. | Актуализированы acceptance matrix, implementation gates, smoke evidence и backlog по Stage 2. | Acceptance закрывает текущий срез, а не весь полный PRD-1. |

## 5. Recommended 150K Tranche Framing

Рекомендуемое название:

**Этап 2. Часть 1: первый функционально-архитектурный срез Stage 2 корпоративного OpenWebUI**

Рекомендуемый подзаголовок:

**Включает реализованные модули транскрибации аудио/видео и базового Web Search, а также архитектурную подготовку дальнейших направлений Stage 2.**

Такое framing точнее, чем "STT + Web Search", потому что фактически выполнены не только две функции, но и значимый архитектурный слой: decomposition, extension-first pattern, contracts, runtime evidence, acceptance/gates/backlog и коммерческий audit.

Такое framing безопаснее, чем "полный Stage 2", потому что PRD-1 включает больше направлений, чем можно корректно закрыть бюджетом 150 000 рублей.

## 6. Included Scope

### A. Implemented User Capabilities

Включить как фактически реализованные пользовательские возможности:

- транскрибация аудио/видео внутри OpenWebUI;
- загрузка media attachment, запуск transcribe action и возврат текста в пользовательский UX;
- browser-side input normalization через ffmpeg.wasm assets;
- backend STT proxy через private `stage2-stt` sidecar;
- интеграция Lemonfox path как серверного provider path;
- базовый Web Search как LLM search tool в OpenWebUI;
- Brave provider path как подтвержденный native direct-context baseline;
- Yandex Search API provider path как добавленный и operator-confirmed native path;
- private SearXNG provider path как self-hosted/private meta-search comparison path.

### B. Architecture Work

Включить как архитектурные результаты Stage 2:

- decomposition полного Stage 2 на направления и deliverable boundaries;
- extension-first pattern без форка OpenWebUI для текущего среза;
- contract boundaries между OpenWebUI, browser assets, Action Function, sidecar и внешними providers;
- STT proxy boundary: browser не хранит provider secrets, OpenWebUI не становится прямым provider client;
- provider adapter pattern для STT и Web Search;
- env/config contracts без раскрытия секретов;
- input normalization contract для media files;
- Web Search privacy boundary;
- Web Search source attribution contract;
- Web Search usage/governance gaps как явные future gates;
- acceptance matrix, implementation gates и backlog actualization.

### C. Runtime and Infrastructure

Включить как runtime/infrastructure work:

- `stage2-stt` sidecar;
- static loader для OpenWebUI;
- self-hosted ffmpeg.wasm assets;
- Lemonfox provider path через backend boundary;
- Brave native search path;
- Yandex Search API native path;
- private SearXNG native path;
- SearXNG compose/config artifacts;
- runtime smoke reports;
- Playwright UI proof для STT;
- provider baseline closeout для Web Search.

### D. Docs and Acceptance

Включить как документационный и приемочный пакет:

- Stage 2 context index;
- Stage 2 README navigation;
- engineering backlog;
- acceptance matrix;
- implementation gates;
- STT context pack;
- Web Search context index;
- Web Search privacy/source contracts;
- commercial completed-work audit;
- runtime and smoke reports.

## 7. Excluded / Future Scope

Следующие направления не следует включать в договор на 150 000 рублей как завершенные:

- полный managed workspace model;
- полный groups/RBAC/access rollout;
- shared prompts/templates/knowledge как готовый managed catalog;
- полный model catalog и централизованный provider governance;
- document pipeline для PDF/DOCX/XLSX;
- OCR / VL OCR / layout-aware PDF как production или accepted pilot;
- broker reports и 3-НДФЛ;
- manager read-only visibility в рабочие чаты;
- no-delete, retention и audit как compliance-ready feature;
- hard billing, gateway, budgets и enforcement;
- AD/SSO или SCIM lifecycle;
- data masking/tokenization/local NER;
- analytics и cost visibility;
- full Web Search rollout governance;
- Web Search policies/logs/limits;
- forbidden-query policy;
- full Web Search quality matrix;
- privacy/data-egress review for broad rollout.

STT hardening также остается будущим scope:

- mobile UX;
- large/long files;
- low-memory devices;
- cancel flow;
- upload/job cancellation;
- retention/persistence;
- transcript history;
- transcript export;
- monitoring and cost events.

Web Search hardening также остается будущим scope:

- group-level rollout rules;
- allow/deny policies;
- logs and retention policy;
- cost visibility;
- forbidden-query policy;
- full RU/EN quality matrix;
- provider-by-provider SLA/latency comparison;
- broad privacy/data-egress review;
- final decision on Brave/Yandex/SearXNG as default provider path.

## 8. Relationship to Existing 75K Act/Invoice

Существующий акт/счет на 75 000 рублей следует трактовать как частичную оплату или первый закрывающий документ в рамках более широкого согласованного среза на 150 000 рублей.

Рекомендуемая логика:

- не считать 75 000 рублей отдельным завершением полного Stage 2;
- не дублировать оплату за уже принятые работы;
- в договоре или приложении на 150 000 рублей указать, что ранее оформленные 75 000 рублей относятся к первой части этого же Stage 2 tranche, если это соответствует бухгалтерской схеме сторон;
- второй закрывающий документ на оставшуюся часть должен закрывать согласованный "Этап 2. Часть 1", а не весь PRD-1;
- полный PRD-1 должен остаться roadmap/future scope за пределами текущих 150 000 рублей.

Коммерчески безопасная формула: 150 000 рублей покрывают первый функционально-архитектурный срез Stage 2, включая фактически реализованные STT и Web Search baseline, архитектурную подготовку будущих направлений и приемочную документацию. Существующие 75 000 рублей учитываются как ранее оформленная часть оплаты этого среза, если стороны подтверждают такую связку.

## 9. Commercial Wording Recommendation

Рекомендуемый предмет для договора или приложения:

> Выполнение работ по этапу "Этап 2. Часть 1: первый функционально-архитектурный срез Stage 2 корпоративного OpenWebUI", включая реализацию модулей транскрибации аудио/видео и базового Web Search, настройку и проверку provider paths, подготовку серверных и инфраструктурных контуров, а также архитектурную и приемочную документацию для дальнейшего развития Stage 2.

Рекомендуемое описание результата:

> В результате работ подготовлен и проверен первый функционально-архитектурный срез Stage 2: реализована транскрибация аудио/видео через OpenWebUI и приватный STT proxy, реализован базовый Web Search как LLM search tool с provider paths Brave, Yandex Search API и private SearXNG, подготовлены архитектурные boundaries, acceptance gates, backlog и документация для последующих направлений PRD-1.

Рекомендуемое ограничение scope:

> Работы не включают завершение полного PRD-1, production rollout всех корпоративных политик, полный document/OCR pipeline, broker reports/3-НДФЛ, AD/SSO, hard billing/gateway, data masking, analytics/cost visibility и полный Web Search governance. Эти направления фиксируются как future scope.

Формулировка по Web Search:

> Базовый контур Web Search реализован как возможность LLM-поиска актуальной информации в OpenWebUI. Brave и Yandex Search API подключены через native/API/Admin GUI paths. Private SearXNG подготовлен как self-hosted/private meta-search path с отдельными infrastructure artifacts. Политики, логи, лимиты, forbidden-query policy, cost visibility и полный rollout governance остаются будущим scope.

## 10. Final Recommendation

Контракт на 150 000 рублей можно готовить, если его предмет будет сформулирован как первый функционально-архитектурный срез Stage 2, а не как полный PRD-1.

Рекомендуемый title для коммерческих документов:

**Этап 2. Часть 1: первый функционально-архитектурный срез Stage 2 корпоративного OpenWebUI**

Рекомендуемый subtitle:

**Включает реализованные модули транскрибации аудио/видео и базового Web Search, а также архитектурную подготовку дальнейших направлений Stage 2.**

Договорную подготовку можно считать готовой при условии, что:

- 15 направлений PRD-1 отражены как done/architecture/partial/future без завышения статуса;
- STT и Web Search включены как фактически реализованные capabilities;
- architecture/contracts/acceptance/backlog включены как выполненная подготовительная работа;
- полный PRD-1 явно отделен как future scope;
- существующие 75 000 рублей учтены как ранее оформленная часть оплаты этого же tranche или как отдельная предоплата/закрытие, в зависимости от бухгалтерского решения сторон.

Итоговый статус:

`stage2_150k_scope_reconciliation_ready_for_contract_draft`
