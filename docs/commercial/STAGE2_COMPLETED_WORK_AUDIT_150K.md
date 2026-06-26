# Аудит выполненных работ Stage 2 / Транш 1

## 1. Назначение документа

Этот документ фиксирует фактически выполненные работы по первому ограниченному срезу Stage 2 для корпоративного OpenWebUI.

Документ предназначен для подготовки второго договора и акта выполненных работ. Он не заменяет полный PRD-1 и не утверждает, что весь Practical Stage 2 завершен. Полный PRD-1 существенно шире и должен оцениваться отдельными траншами.

Рекомендуемое коммерческое название этапа:

```text
Этап 2. Часть 1: транскрибация аудио/видео и базовый веб-поиск в корпоративном OpenWebUI
```

Альтернативное короткое название:

```text
Stage 2 Tranche 1: OpenWebUI media transcription and web search baseline
```

## 2. Связь с PRD-1

PRD-1 описывает развитие OpenWebUI в управляемую корпоративную AI-среду: рабочие пространства, группы, prompts/templates, модельный каталог, web-search, документы, OCR pilot, базовую аналитику расходов, правила данных и другие направления.

В рамках этого аудита из PRD-1 выделен первый оплачиваемый срез: модуль транскрибации аудио/видео внутри OpenWebUI и базовый контур Web Search с тремя provider paths. STT-срез опирается на уже реализованный и проверенный путь:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization when needed
-> OpenWebUI prepared-audio upload
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> Lemonfox adapter
-> transcript returned to OpenWebUI composer/chat UX
```

Web Search-срез опирается на native OpenWebUI Web Search path:

```text
OpenWebUI native Web Search
-> Brave brave_llm_context / Yandex Search API / private SearXNG
-> candidate set / source context
-> LLM answer inside OpenWebUI
```

Остальные направления PRD-1 остаются будущими работами и не включаются автоматически в текущий limited Stage 2 tranche.

## 3. Политика коммерческой документации

```text
GitHub-документация фиксирует состав работ, трудозатраты, статусы,
доказательства и ограничения. Денежные суммы, график оплаты и финансовые
условия фиксируются только в договорах, счетах и актах и не хранятся в
markdown-документации репозитория.
```

Оценка трудозатрат подлежит отдельной фиксации. Финансовые условия данного этапа фиксируются только вне GitHub-документации в договорных документах.

Текущий limited Stage 2 tranche относится только к перечисленному ниже объему работ. Он не покрывает весь PRD-1 / Practical Stage 2. Эксплуатационные условия по серверу, хранению, provider API, STT-провайдеру, web-search или другим подпискам фиксируются отдельно, если это требуется эксплуатационной моделью.

## 4. Перечень фактически выполненных работ

### 4.1. Архитектура и проектирование

Выполнены работы по проектированию безопасной архитектуры транскрибации:

- зафиксирована серверная граница STT proxy: вызовы к внешнему STT-провайдеру идут через серверный контур, а не напрямую из браузера;
- описаны contract boundaries для provider calls, storage/retention, policy, usage и UI/backend split;
- подготовлена и актуализирована ADR-0004 по STT proxy boundary;
- подтвержден extension-first подход: сначала штатные механизмы OpenWebUI, затем Action Function, тонкий static loader, приватный backend-sidecar и provider adapter;
- зафиксирована модель без отдельного пользовательского STT-портала;
- описан capability-based input contract: расширение и MIME являются подсказками, а фактическая поддержка определяется через ffmpeg.wasm probe/decode, наличие аудиопотока и успешную нормализацию;
- подготовлены env/config contracts и runtime capabilities без публикации секретов в браузер.

Доказательная база:

- `docs/stage2/CONTRACT_BOUNDARIES.md`;
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`;
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`;
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`;
- `docs/stage2/IMPLEMENTATION_GATES.md`;
- `docs/stage2/ENGINEERING_BACKLOG.md`.

### 4.2. Backend/STT sidecar

Реализован отдельный backend-sidecar `stage2-stt` для серверной части транскрибации:

- сервис `services/stage2-stt`;
- FastAPI endpoint для runtime capabilities;
- job routes для создания задачи, получения статуса, получения результата и cancel-сценариев;
- internal auth boundary для job routes;
- Pydantic-контракты для jobs, transcript result, provider errors, usage event draft и runtime capabilities;
- `SttProviderAdapterFactory`;
- первый provider adapter: `LemonfoxSttAdapter`;
- нормализация ответа Lemonfox в внутренний transcript contract;
- typed validation для неподдержанного формата, превышения размера, storage/fallback решений и provider errors;
- in-memory job store для MVP/proof уровня;
- тесты для config, capabilities endpoint, Lemonfox adapter, validation/storage/jobs, job routes и OpenWebUI Action helper.

Доказательная база:

- `services/stage2-stt/`;
- `services/stage2-stt/stage2_stt/app.py`;
- `services/stage2-stt/stage2_stt/provider.py`;
- `services/stage2-stt/stage2_stt/lemonfox.py`;
- `services/stage2-stt/stage2_stt/runtime.py`;
- `services/stage2-stt/tests/`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`.

### 4.3. OpenWebUI integration

Реализована интеграция с OpenWebUI без отдельного пользовательского STT-интерфейса:

- OpenWebUI Action Function `stage2_media_transcription_action`;
- Action valves/configuration для связи с приватным sidecar;
- обработка media attachment metadata через доказанный runtime path;
- вызов sidecar из server-side Action context;
- возврат результата транскрибации в OpenWebUI composer/chat UX;
- static loader patch, добавляющий явное действие `Транскрибировать` на media attachments;
- локальные статусы и безопасные сообщения об ошибках для пользователя;
- сохранение провайдерских секретов и внутреннего sidecar token вне браузера.

Доказательная база:

- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`;
- `deploy/openwebui-static/loader.js`;
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_IMPLEMENTATION.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`.

### 4.4. Browser media processing

Реализована браузерная подготовка медиафайлов через self-hosted ffmpeg.wasm assets:

- static browser config `stage2-stt-normalization.json`;
- загрузка self-hosted ffmpeg.wasm assets только при необходимости нормализации;
- prepared MP3 passthrough без лишней ffmpeg-обработки;
- input probe/decode перед передачей в STT-контур;
- проверка наличия аудиопотока;
- нормализация MP4/WebM в prepared audio profile;
- typed safe errors для unsupported/decode-failed и no-audio cases;
- отдельный скрипт получения ffmpeg.wasm assets;
- proof matrix по generated proof media.

Доказательная база:

- `deploy/openwebui-static/loader.js`;
- `deploy/openwebui-static/stage2-stt-normalization.json`;
- `scripts/fetch-ffmpeg-wasm-assets.sh`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`;
- `docs/reports/2026-06-19/openwebui-stt-ffmpeg-browser-normalization-proof/ffmpeg-normalization-evidence.json`.

### 4.5. Deployment/runtime proof

Выполнены runtime/deployment работы и проверки для MVP-среза:

- `stage2-stt` добавлен как отдельный сервис в OpenWebUI compose-схему;
- OpenWebUI настроен на доступ к sidecar по внутренней Docker-сети;
- static loader и browser normalization config подключены как OpenWebUI static assets;
- Action Function установлен и проверен на runtime path;
- prepared MP3 path прошел end-to-end проверку: OpenWebUI upload -> Action -> `stage2-stt` sidecar -> Lemonfox -> transcript response;
- Lemonfox live smoke прошел через sidecar path;
- Playwright proof подтвердил UI-level behavior для static loader patch и browser normalization cases;
- публичный browser path не содержит прямого вызова Lemonfox.

Доказательная база:

- `compose/openwebui.compose.yml`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`.

### 4.6. Documentation

Подготовлен и актуализирован документационный контур Stage 2/STT:

- PRD-1 и customer summary фиксируют transcription module как часть Practical Stage 2;
- Stage 2 README, context index, implementation gates, acceptance matrix и backlog отражают текущий статус STT MVP;
- старые blockers по STT не удалены, но отделены от закрытого MVP-среза;
- подготовлены implementation reports по backend, Action Function, runtime proof, frontend patch, Playwright proof и ffmpeg browser normalization;
- создан context pack для нового чата с запретом переоткрывать уже доказанный STT MVP как discovery с нуля;
- зафиксирован extension-first implementation pattern для будущих OpenWebUI-facing функций.

Доказательная база:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`;
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`;
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md`;
- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`.

### 4.7. Web Search и три provider paths

Реализован и зафиксирован базовый Web Search контур через штатные механизмы OpenWebUI:

- подготовлен Stage 2 Web Search domain: context index, ADR, privacy/source/usage contracts, native pilot plan и acceptance criteria;
- выбран native-first подход: без отдельного sidecar, fork или custom search gateway для первого Web Search slice;
- подготовлен и проверен Brave `brave_llm_context` как прямой paid/native baseline;
- добавлен и зафиксирован Yandex Search API как рабочий RU direct API path, подтвержденный через OpenWebUI Web GUI/Admin UI;
- добавлен private SearXNG path как self-hosted/private meta-search comparison track;
- подготовлены optional compose/config artifacts для SearXNG: `compose/searxng.private.compose.yml`, `compose/searxng.debug.compose.yml`, `deploy/searxng/settings.yml`, `deploy/searxng/limiter.toml`;
- зафиксирован внутренний SearXNG URL для OpenWebUI: `http://searxng:8080/search?q=<query>`;
- добавлены env/config placeholders для Web Search providers без реальных ключей;
- выполнен runtime baseline по Brave;
- выполнена operator-confirmed фиксация Yandex path;
- выполнен runtime smoke private SearXNG в snippet/bypass mode;
- подготовлен план трехпутевого сравнения Brave / Yandex / private SearXNG по candidate set quality, latency, source visibility, privacy/logging и ops cost.

Доказательная база:

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`;
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`;
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`;
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`;
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`;
- `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md`;
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`;
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`;
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`;
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`;
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`;
- `compose/searxng.private.compose.yml`;
- `deploy/searxng/settings.yml`;
- `deploy/searxng/limiter.toml`;
- `.env.example`.

## 5. Результаты, доступные заказчику

По текущему траншу можно заявлять следующий результат:

- в OpenWebUI реализовано действие `Транскрибировать` для media attachments;
- пользователь остается в интерфейсе OpenWebUI и не переходит в отдельный STT-портал;
- можно загрузить аудио/видео и запустить транскрибацию явным действием пользователя;
- подготовленные MP3 проходят напрямую через Action/sidecar path;
- MP4/WebM с аудиодорожкой проходят через браузерную нормализацию в tested MVP cases;
- результат транскрибации возвращается в OpenWebUI composer/chat UX;
- серверный STT-контур обращается к внешнему STT-провайдеру через sidecar/provider adapter;
- секреты STT-провайдера не попадают в браузерный код;
- неподдержанные или no-audio файлы получают безопасные видимые ошибки до передачи в provider path;
- отдельный пользовательский STT-портал не создавался и не требуется для текущего MVP;
- в OpenWebUI подготовлен Web Search baseline через три provider paths: Brave, Yandex и private SearXNG;
- Brave `brave_llm_context` зафиксирован как рабочий direct-context baseline;
- Yandex Search API зафиксирован как рабочий RU direct API path;
- private SearXNG зафиксирован как внутренний meta-search comparison path без публичной публикации сервиса;
- Web Search provider keys и секреты не должны попадать в браузер или документацию.

## 6. Проверки и доказательства

Ключевые проверки, зафиксированные в отчетах:

- backend sidecar tests: config, capabilities, Lemonfox adapter, validation/storage/jobs, job routes;
- `python -m pytest services/stage2-stt/tests` в implementation reports: 22 tests passed на актуальном STT MVP этапе;
- prepared MP3 end-to-end runtime proof через OpenWebUI Action и sidecar;
- Lemonfox live smoke through sidecar path;
- Playwright proof для UI/static-loader behavior;
- browser ffmpeg.wasm proof для prepared MP3 passthrough;
- browser ffmpeg.wasm proof для MP4 video with audio;
- browser ffmpeg.wasm proof для WebM audio/video;
- safe error proof для unsupported fake MP4;
- safe error proof для MP4 without audio stream;
- static asset checks для `loader.js`, normalization config и ffmpeg.wasm assets;
- docs drift audit: living Stage 2 docs приведены к фактическому статусу MVP без утверждения production-final;
- Brave `brave_llm_context` runtime baseline;
- Yandex Search API owner/operator confirmation через OpenWebUI Web GUI/Admin UI;
- private SearXNG direct JSON smoke и native OpenWebUI snippet/bypass smoke;
- Web Search provider baseline closeout;
- Web Search privacy/source/usage contracts and candidate-set comparison plan.

## 7. Ограничения текущего этапа

Текущий транш не является production-final enterprise hardening. Ограничения нужно явно оставить в договорной и приемочной рамке:

- не гарантируется поддержка всех возможных аудио/видео форматов;
- broad input support является capability-based, а не обещанием "любой формат работает";
- mobile browser testing остается отдельным hardening-направлением;
- large/customer media testing остается отдельным hardening-направлением;
- low-memory browser behavior требует отдельной проверки;
- long files и практическое поведение около 1 GB требуют отдельного acceptance data;
- cancel during browser ffmpeg preprocessing не закрыт как production-ready UX;
- upload/job cancel и late-result cleanup требуют дальнейшего hardening;
- durable persistence beyond in-memory job store не входит в текущий транш;
- production storage/retention/cleanup policy не финализирована;
- Opus provider/default proof не закрыт как production default;
- transcript history/export/workflow не входит в текущий транш;
- multi-user/group permission hardening остается будущей работой;
- monitoring, structured logs и usage/cost events остаются future hardening;
- отдельный workflow "протокол встречи / история / экспорт / шаблоны результата" не включен в этот срез;
- Web Search production rollout для всех пользователей не закрыт;
- ordinary-user Web Search allow/deny permissions требуют отдельной проверки;
- full EN/RU comparative matrix по Brave / Yandex / SearXNG остается будущей работой;
- Web Search logging/retention policy и forbidden-query policy требуют owner approval;
- Yandex privacy/data-egress и metadata-forwarding review остаются открытыми перед широким rollout;
- private SearXNG остается comparison track, а не primary provider, пока не закрыты quality, privacy, logging и ops evidence;
- full page loading и vectorized `web-search-*` retrieval не доказаны для текущего Web Search baseline.

## 8. Что не входит в текущий limited Stage 2 tranche

В текущий транш не входят:

- полный Practical Stage 2;
- все workspace/group/prompt/knowledge работы из PRD-1;
- production rollout web-search для всех пользователей без pilot/group/policy gates;
- full Brave / Yandex / SearXNG comparative rollout matrix;
- OCR/layout-aware PDF pilot;
- broker reports / 3-НДФЛ full workflow;
- hard billing/gateway;
- full AD/SSO lifecycle / SCIM;
- full data masking/tokenization subsystem;
- local LLM/NER для sensitive data masking;
- production document pipeline;
- production-grade OCR/layout pipeline;
- complex Excel parser;
- production DOCX/XLSX generation;
- full corporate RAG over all documents;
- production audit/retention archive;
- полноценный meeting transcription workspace/history/export;
- отдельная система шаблонов протоколов встреч;
- deep OpenWebUI fork без отдельного fork rationale;
- отдельный пользовательский STT-портал;
- гарантия обработки любых медиафайлов любых размеров и кодеков.

## 9. Формулировка для договора

```text
Предмет работ:
Разработка, внедрение и проверка первого функционального среза Stage 2:
модуль транскрибации аудио/видео внутри интерфейса OpenWebUI с браузерной
нормализацией медиафайлов, серверным STT-контуром и интеграцией с внешним
STT-провайдером, а также базовый контур Web Search в OpenWebUI с тремя
провайдерскими путями: Brave, Yandex и private SearXNG.

Состав работ:
1. Проектирование архитектуры модуля транскрибации в контуре OpenWebUI.
2. Реализация серверного STT-sidecar для приема подготовленного аудио,
   управления задачами транскрибации и интеграции с STT-провайдером.
3. Реализация provider adapter для Lemonfox и нормализации результата
   транскрибации во внутренний контракт.
4. Реализация OpenWebUI Action Function для запуска транскрибации из интерфейса
   OpenWebUI.
5. Реализация static loader integration с действием "Транскрибировать" для
   media attachments.
6. Реализация браузерной нормализации аудио/видео через self-hosted ffmpeg.wasm
   assets для проверенных MVP-сценариев.
7. Настройка runtime wiring между OpenWebUI, static assets и приватным
   STT-sidecar.
8. Подготовка Web Search baseline через native OpenWebUI provider paths:
   Brave `brave_llm_context`, Yandex Search API и private SearXNG.
9. Подготовка optional private SearXNG runtime artifacts и документации для
   внутреннего candidate-set comparison track.
10. Проведение runtime, Playwright и unit/smoke проверок по MVP-сценариям.
11. Подготовка и актуализация технической документации, отчетов и acceptance
   статуса по текущему траншу.

Результат работ:
В интерфейсе OpenWebUI реализовано действие "Транскрибировать" для
медиафайлов. Пользователь загружает аудио/видео, запускает транскрибацию,
система подготавливает аудио в браузере, передает его в серверный STT-контур,
получает текст и возвращает его в интерфейс OpenWebUI.

В OpenWebUI также подготовлен базовый Web Search contour: Brave работает как
direct-context baseline, Yandex зафиксирован как RU direct API path, private
SearXNG зафиксирован как внутренний meta-search comparison path.

Ограничения:
Данный этап является первым ограниченным срезом Stage 2 и не является полным
Practical Stage 2. Production hardening, mobile/large-file матрица,
retention/persistence, transcript history/export, group permission hardening,
полный Web Search rollout для всех пользователей, OCR, broker-report workflow,
hard billing, full AD/SSO и data masking оформляются отдельными будущими
траншами.

Финансовые условия:
Финансовые условия данного этапа фиксируются только в договоре, счете и акте.
В GitHub-документации фиксируются состав работ, статусы, доказательства,
ограничения и оценка трудозатрат.
```

## 10. Формулировка для акта

```text
Исполнитель выполнил работы по разработке, внедрению и проверке модуля
транскрибации аудио/видео и базового Web Search contour для корпоративного
OpenWebUI в рамках первого ограниченного среза Stage 2.

В состав выполненных работ вошли: проектирование архитектуры модуля
транскрибации, реализация серверного STT-sidecar, интеграция с STT-провайдером
через provider adapter, реализация OpenWebUI Action Function, добавление
действия "Транскрибировать" для media attachments, браузерная нормализация
медиафайлов через self-hosted ffmpeg.wasm assets, подготовка Web Search baseline
по Brave, Yandex и private SearXNG, runtime wiring и проверка MVP-сценариев.

Результатом работ является работоспособный MVP-срез: пользователь в интерфейсе
OpenWebUI может загрузить аудио/видео, запустить действие "Транскрибировать",
получить результат транскрибации в интерфейсе OpenWebUI, при этом секреты
STT-провайдера остаются на серверной стороне. Дополнительно в OpenWebUI
подготовлены три Web Search provider paths: Brave direct-context baseline,
Yandex RU direct API path и private SearXNG meta-search comparison path.

Заказчик принял результат работ в рамках ограниченного объема Stage 2 Tranche 1.
Финансовые условия приемки фиксируются только во внешних договорных документах.

Стороны подтверждают, что данный акт относится только к перечисленному объему
работ и не закрывает полный PRD-1 / Practical Stage 2. Работы по production
hardening, расширенной матрице тестирования, хранению/ретеншну, истории и
экспорту транскриптов, полном Web Search rollout, OCR, broker-report workflow,
hard billing, AD/SSO, data masking и другим направлениям PRD-1 оформляются
отдельными траншами при необходимости.
```

## 11. Рекомендация

Рекомендуется оформлять этот объем как:

```text
Этап 2. Часть 1: транскрибация аудио/видео и базовый веб-поиск в корпоративном OpenWebUI
```

или как:

```text
Stage 2 Tranche 1: OpenWebUI media transcription and web search baseline
```

Состав работ текущего commercial tranche обоснован уже выполненным и доказанным первым функциональным срезом Stage 2: архитектура, backend-sidecar, provider adapter, OpenWebUI Action Function, static loader UI action, browser ffmpeg.wasm normalization, Web Search provider baseline по Brave/Yandex/private SearXNG, runtime proof, Playwright proof, tests/smoke и документационная фиксация.

Полный PRD-1 следует оформлять отдельными траншами. Следующий транш рационально выбирать из двух вариантов:

- testing/hardening транш для STT: mobile/large/customer media, retention/persistence, cancel, permissions, monitoring, transcript history/export;
- Web Search hardening/rollout транш: pilot groups, allow/deny permissions, forbidden-query policy, logging/retention, cost visibility и Brave/Yandex/SearXNG comparative matrix;
- другой функциональный блок PRD-1 по согласованию: OCR/layout-aware PDF pilot, broker reports / 3-НДФЛ, workspaces/groups/prompts или analytics/cost visibility.
