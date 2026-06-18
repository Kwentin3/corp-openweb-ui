# OpenWebUI Corporate Chat PRD-1 Initial Draft

Статус: historical enriched draft, не source of truth
Дата: 2026-06-16
Проект: корпоративный портал AI-чата на базе OpenWebUI
Предыдущий этап: PRD-0 принят заказчиком и закрыт
Текущий этап: Stage 2 / PRD-1 discovery + implementation draft

Актуальный PRD-1 для согласования: [OPENWEBUI_CORPORATE_CHAT_PRD_1.md](OPENWEBUI_CORPORATE_CHAT_PRD_1.md).

## 1. Краткое описание

PRD-0 закрыл нулевую фазу: у заказчика появилась корпоративная точка входа в LLM-чат на базе OpenWebUI.

PRD-1 описывает следующий этап: развитие корпоративного чата в управляемую рабочую AI-среду для сотрудников, отделов и регулярных бизнес-сценариев.

Ключевая идея: сотрудники должны не просто заходить в чат и каждый раз заново объяснять задачу модели, а работать в подготовленных рабочих сценариях, где есть правила, шаблоны, промты, модели, документы, ограничения и понятная стоимость использования.

## 2. Контекст

После приемки PRD-0 заказчик сформировал направления Stage 2:

1. Брокерские отчеты и 3-НДФЛ.
2. Web-search через зарубежный и российский provider.
3. Транскрибация аудио/видео.
4. Работа с Word/PDF/Excel.
5. Корпоративный доступ через AD/домен.
6. YandexGPT и GigaChat.
7. Биллинг, лимиты и контроль расходов.
8. DeepSeek через API/Cloud.
9. Совместная работа: группы, проекты, общие шаблоны, промты и рабочие пространства.

Эти требования меняют характер системы: это уже не только корпоративный чат, а управляемый AI-инструмент для повторяемых рабочих задач.

## 3. Проблема

Сейчас сотрудники могут пользоваться ИИ, но делают это разрозненно:

- каждый создает свои чаты;
- хорошие промты не переиспользуются;
- опыт сильных пользователей не передается остальным;
- сотрудники заново объясняют ИИ одни и те же задачи;
- нет единого контекста для типовых процессов;
- нет контроля стоимости;
- нет понятного разделения по отделам, группам и задачам;
- работа с документами и аудио требует ручных действий;
- нет единой политики использования разных моделей;
- нет полноценного корпоративного управления доступом.

В результате компания получает набор индивидуальных чатов, а не управляемую AI-среду.

## 4. Цель PRD-1

Создать управляемую корпоративную AI-среду на базе OpenWebUI, где:

- сотрудники входят через корпоративную учетную запись;
- видят доступные им рабочие сценарии;
- используют заранее подготовленные шаблоны, промты и правила;
- работают с документами, аудио, видео и web-search;
- выбирают модели в рамках заданной политики;
- администратор управляет пользователями, группами, моделями и базовыми лимитами;
- расходы по моделям становятся видимыми и контролируемыми;
- регулярные бизнес-сценарии оформлены как воспроизводимые процессы.

## 5. Основной продуктовый принцип

PRD-1 строится не вокруг списка моделей, а вокруг рабочих сценариев.

Модель - это инструмент. Рабочий сценарий - это способ превратить инструмент в регулярный процесс.

Плохо: подключить Claude, DeepSeek, YandexGPT, GigaChat, Brave и Яндекс.

Хорошо: создать сценарий "Брокерские отчеты и 3-НДФЛ", где сотрудник загружает отчет, использует утвержденный шаблон, получает черновик разбора, видит предупреждения и передает результат на ручную проверку.

## 6. Native OpenWebUI first

PRD-1 должен максимально использовать штатные возможности OpenWebUI. Fork, отдельный frontend и gateway добавляются только после доказательства, что нативных возможностей недостаточно.

| Потребность PRD-1 | Нативный механизм OpenWebUI | Статус | Комментарий |
| --- | --- | --- | --- |
| Рабочие пространства для задач | Workspace Models + Prompts + Knowledge + Groups + access control | can be done by configuration | В OpenWebUI нет отдельной сущности "business workspace" в смысле PRD, но ее можно собрать из модели-пресета, knowledge, prompts и группы доступа. |
| Общие промты | Workspace Prompts, slash commands, variables, version history, controlled sharing | can be done by configuration | Подходит для шаблонов 3-НДФЛ, документов, встреч и web-search. |
| Общие инструкции/knowledge | Workspace Knowledge, directories, attach to model, reference with `#` | can be done by configuration | Подходит для методичек и шаблонов. Не считать полноценным корпоративным RAG по всем документам. |
| Доступ по группам | Groups, RBAC, resource access control | can be done by configuration | Учитывать additive/union permission model: deny-прав нет, права только добавляются. |
| Ролевое подключение моделей | Workspace Models and model access control | can be done by configuration | Рекомендуемый паттерн: скрывать базовые модели и публиковать curated workspace models. |
| File upload / документы | Chat file upload, Knowledge, RAG/full context, storage settings | partly native | PDF/DOCX можно начинать нативно. XLSX и точное извлечение таблиц могут потребовать parser/tool. |
| Web-search | Native Web Search providers, including Brave and Yandex engines, per-feature permissions | can be done by configuration | Для текущего proxy bridge обязательно проверить `WEB_SEARCH_TRUST_ENV=True`. |
| STT | Native STT settings: local Whisper, OpenAI-compatible/OpenAI, Deepgram, Mistral/Azure paths depending on version | partly native | Базовую STT можно делать нативно. Lemonfox нужно проверить как OpenAI-compatible STT endpoint. |
| SSO/AD | OIDC/OAuth, LDAP, trusted header, SCIM | can be done by configuration / requires customer decision | Выбор зависит от инфраструктуры заказчика. |
| Биллинг/usage | Native Analytics: token usage by user/model, cost estimation formula | partly native | В приоритете. Для hard budgets и enforcement может понадобиться gateway. |
| Hard per-user/per-team spend limits | Нет полного нативного enforcement для всех LLM/web-search/STT расходов | requires gateway decision | Не внедрять LiteLLM по умолчанию. Сначала подтвердить, что native analytics + группы + provider-side budgets недостаточны. |
| Browser-side ffmpeg.wasm | Нет штатного OpenWebUI сценария | requires implementation / possible fork | Делать отдельным slice после проверки памяти, размера файлов, браузеров и fallback. |

### Billing decision

В draft упоминался "LightLLM". Корректное название кандидата - LiteLLM.

Для PRD-1 порядок такой:

1. Сначала использовать нативные возможности OpenWebUI: Analytics, token usage tracking, per-user/per-model reports, group/model access control, отключение дорогих функций по группам, provider-side budgets.
2. Если нужно только видеть примерную стоимость - gateway не обязателен.
3. Если нужны hard budgets, rate limits, virtual keys, team budgets, centralized model routing и единая стоимость по providers - изучать LiteLLM отдельным gateway-slice.
4. LiteLLM не должен появляться в production path автоматически. Его внедрение требует architecture decision, backup/restore path, security review, monitoring и rollback.

## 7. Scope PRD-1

### 7.1. Рабочие сценарии, проекты и шаблоны

Минимальный набор:

1. Брокерские отчеты и 3-НДФЛ.
2. Транскрибация встреч.
3. Работа с документами.
4. Web-search и исследование.
5. Общий корпоративный AI-чат.

Implementation path:

- создать группы доступа;
- создать curated workspace models под каждый сценарий;
- прикрепить системный prompt, knowledge и инструменты;
- добавить shared prompts с переменными;
- ограничить доступ по группам;
- описать владельца каждого сценария.

Acceptance criteria:

- создано минимум 3 сценария;
- каждый сценарий имеет описание, правила, prompts, owner и группу доступа;
- пользователь видит только разрешенные сценарии;
- методолог может обновлять шаблоны через согласованный процесс.

### 7.2. Брокерские отчеты и 3-НДФЛ

Цель - пилотная помощь сотрудникам при работе с брокерскими отчетами и подготовкой материалов для 3-НДФЛ.

Жесткая граница: система не является налоговым консультантом, не подает декларации и не делает финальные юридически/налоговые утверждения. Результат ИИ - черновик и аналитическая помощь, требующая проверки человеком.

Native-first implementation:

- curated workspace model "Брокерские отчеты / 3-НДФЛ";
- системный prompt с запретом финальных налоговых утверждений;
- shared prompt templates для извлечения данных, вопросов к пользователю и черновика пояснений;
- Knowledge с утвержденной инструкцией и примерами;
- file upload для тестовых PDF/XLSX/DOCX;
- access control только для разрешенной группы.

Requires implementation if:

- нужно надежно извлекать таблицы из XLSX/PDF;
- нужны валидаторы налоговых полей;
- нужен экспорт в строго заданный файл/формат;
- нужны audit logs по каждому обработанному отчету.

Acceptance criteria:

- пользователь выбирает сценарий;
- загружает тестовый отчет;
- получает структурированный черновик;
- видит предупреждение о ручной проверке;
- система явно выделяет неуверенные места и вопросы к пользователю;
- сценарий документирован для пользователя и администратора.

### 7.3. Web-search

Цель - управляемый web-search с контролем стоимости, источников и доступа.

Native-first implementation:

- использовать штатный OpenWebUI Web Search;
- начать с `brave_llm_context` как зарубежного provider;
- исследовать штатный Yandex provider или внешний Yandex Search API path как российский provider;
- включать web-search только для разрешенной группы;
- для текущего proxy bridge включить `WEB_SEARCH_TRUST_ENV=True`;
- ограничить concurrency и result count.

Acceptance criteria:

- администратор может включить/выключить web-search;
- пользователь из разрешенной группы может выполнить русский и английский web-search запрос;
- пользователь без прав не может использовать web-search;
- в документации указаны provider, тарифы, лимиты и smoke-запросы;
- есть инструкция, когда web-search использовать нельзя.

### 7.4. Транскрибация аудио и видео

Цель - отдельный рабочий сценарий "Транскрибация встреч", а не случайная загрузка файла в обычный чат.

Native-first implementation:

- проверить native OpenWebUI STT: local Whisper или OpenAI-compatible STT;
- проверить Lemonfox как STT provider через OpenAI-compatible endpoint;
- если нужен только короткий audio-to-text в chat input, начинать без fork;
- если нужен процесс "загрузить запись -> получить протокол/задачи/follow-up", оформить отдельный сценарий через model + prompts + user instruction.

Requires implementation / possible fork:

- browser-side extraction audio from video;
- ffmpeg.wasm UX;
- chunking больших файлов;
- async callback flow;
- diarization with `speaker_labels`;
- серверный fallback для больших файлов.

Lemonfox facts to validate in pilot:

- цена: $0.50 за 3 часа STT, то есть около $0.1667/час;
- прямой upload ограничен 100MB;
- URL upload ограничен 1GB;
- поддерживаются `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`, `m4a`, `mp4`, `mpeg`, `mov`, `webm`;
- speaker labels поддерживаются, но максимум 4 speakers;
- для speaker labels нужен `response_format=verbose_json`;
- русский язык указан среди поддерживаемых.

Acceptance criteria:

- пользователь загружает mp3 и получает расшифровку;
- пользователь загружает видеофайл и получает расшифровку аудиодорожки или понятное описание ограничения;
- пользователь выбирает шаблон результата: резюме, протокол, задачи, решения, follow-up;
- большие файлы не ломают обычный чат;
- неподдерживаемый формат дает понятную ошибку;
- текущий затык с mp3 исследован и описан.

### 7.5. Работа с Word/PDF/Excel

Цель - оформить типовые сценарии работы с документами, а не просто разрешить file upload.

Минимальные сценарии:

1. Анализ PDF.
2. Анализ DOCX.
3. Анализ XLSX.
4. Сравнение двух документов.
5. Извлечение ключевых тезисов.
6. Извлечение таблиц.
7. Подготовка черновика по шаблону.
8. Проверка документа на противоречия.

Native-first implementation:

- file upload в чате;
- Knowledge для стабильных инструкций и шаблонов;
- prompts с переменными;
- workspace model "Документы";
- full context для небольших файлов, RAG для больших;
- ограничения размера и понятные ошибки.

Requires implementation if:

- XLSX должен анализироваться как структурированная таблица, а не как текст;
- нужно сравнение документов с точной разметкой;
- нужно генерировать DOCX/XLSX output;
- нужны server-side parsers, queue, chunking, OCR или document pipeline.

Acceptance criteria:

- пользователь загружает PDF и получает структурированный анализ;
- пользователь загружает DOCX и получает анализ/черновик ответа;
- пользователь загружает XLSX и получает анализ таблицы с известными ограничениями;
- есть минимум 3 prompt templates;
- причины медленной загрузки файлов исследованы: OpenWebUI limits, Traefik timeouts, storage, RAG/indexing, browser upload.

### 7.6. Корпоративный доступ через AD/домен

Цель - сотрудники входят через корпоративную учетную запись, а доступ управляется через группы.

Native options:

- OIDC/OAuth with role and group claim management;
- LDAP auth;
- Trusted Header auth behind an authenticating reverse proxy;
- SCIM 2.0 for automated user/group provisioning.

Customer decision required:

- какая инфраструктура есть у заказчика: AD, LDAP, Entra ID/Azure AD, ADFS, Keycloak/Authentik/Authelia;
- нужен ли passwordless внутри доменной сети;
- можно ли передавать groups claim;
- кто владеет lifecycle удаленных/заблокированных пользователей.

Acceptance criteria:

- выбранная схема documented;
- есть тестовая группа;
- пользователь из группы входит;
- пользователь вне группы не получает доступ;
- есть карта соответствия групп AD и групп/ролей OpenWebUI;
- описан процесс offboarding.

### 7.7. YandexGPT и GigaChat

Цель - проверить российские LLM providers для русскоязычных корпоративных сценариев.

Tasks:

- изучить API и auth;
- проверить наличие OpenAI-compatible path или необходимость адаптера;
- проверить цены;
- выполнить smoke-test при наличии доступа;
- оценить качество на задачах: резюме документа, письмо, анализ текста, таблица, встреча;
- добавить вывод в provider catalog.

Acceptance criteria:

- есть документ по YandexGPT: подключение, модели, цена, ограничения;
- есть документ по GigaChat: подключение, модели, цена, ограничения;
- если доступ получен - выполнен тестовый запрос;
- если доступ не получен - явно описано, что мешает;
- есть рекомендация: production / pilot / reject.

### 7.8. DeepSeek

В draft указано, что DeepSeek уже подключен через API/Cloud. В текущем репозитории PRD-0 это не подтверждает, поэтому статус для PRD-1: needs operator evidence.

Tasks:

- подтвердить фактический способ подключения;
- указать base URL, model ids, группы доступа без секретов;
- выполнить smoke-test;
- добавить DeepSeek в provider catalog;
- добавить цены и ограничения;
- отдельно учесть planned deprecation старых aliases `deepseek-chat` и `deepseek-reasoner`.

Acceptance criteria:

- DeepSeek отображается в доступных моделях или есть план подключения;
- тестовый запрос проходит;
- есть описание recommended scenarios;
- есть стоимость и ограничения;
- доступ ограничен группой или documented gateway plan.

### 7.9. Биллинг, лимиты и контроль расходов

Цель - сделать расходы видимыми и управляемыми.

Native-first minimal target:

- включить/использовать OpenWebUI Analytics;
- считать token usage по пользователям и моделям;
- зафиксировать формулу расчета стоимости;
- хранить price catalog в docs;
- ограничивать дорогие модели через Groups/Model access;
- ограничивать web-search/STT по группам;
- использовать provider-side budgets where available.

Gateway target, only if needed:

- LiteLLM или аналог;
- virtual keys;
- budget per key/user/team;
- rate limits;
- spend tracking by model/provider/team;
- centralized API keys;
- dashboard/reporting.

Acceptance criteria:

- администратор видит примерный расход по пользователям/группам;
- дорогие модели доступны только разрешенным группам;
- есть price catalog;
- есть список сервисов: LLM tokens, web-search requests, STT hours, storage/files;
- принято решение: native-only for PRD-1 или gateway slice.

### 7.10. Совместная работа: группы, проекты, общие промты

Цель - перенести опыт сильных пользователей в общие сценарии.

Implementation path:

- отдельные permission groups и sharing groups;
- shared prompts с version history;
- curated workspace models;
- Knowledge directories;
- controlled sharing для групп;
- naming convention для сценариев и владельцев.

Acceptance criteria:

- минимум 3 рабочих сценария;
- каждый имеет owner, description, prompts, rules, access group;
- пользователи работают внутри общего сценария, но не видят лишнего;
- методолог может обновлять шаблоны;
- есть инструкция для пользователя и администратора.

## 8. Технический подход

### 8.1. Принцип доставки

1. Discovery и подтверждение native capabilities.
2. Configuration-first implementation.
3. External provider integration.
4. Gateway only for hard cost governance.
5. Fork only for UX/file-processing gaps that нельзя закрыть штатно.

### 8.2. Boundary map

| Домен | Владелец | Граница |
| --- | --- | --- |
| UI/chat/workspace | OpenWebUI | Не менять frontend без fork rationale. |
| Users/groups/access | OpenWebUI + IdP | OIDC/LDAP/SCIM/trusted header. |
| Model provider catalog | OpenWebUI connections or gateway | API keys только server-local/Admin UI/gateway. |
| Usage analytics | OpenWebUI native first | Hard limits may require gateway. |
| Web-search | OpenWebUI Web Search | Provider keys, proxy, permissions. |
| STT | OpenWebUI STT first, custom integration if needed | Large files, diarization, async callback. |
| Documents | OpenWebUI file upload/Knowledge first | Structured XLSX/DOCX generation may require tools. |
| Finance/catalog | docs + admin process | Prices checked before commercial proposal. |

### 8.3. Fork rationale

Fork is allowed only if:

- native OpenWebUI UX cannot support a required scenario;
- external tool/function is insufficient;
- change is isolated and documented;
- there is an update/rollback plan;
- expected customer value justifies maintenance cost.

Likely fork candidates:

- dedicated transcription UX;
- browser-side ffmpeg.wasm;
- large file preprocessing;
- specialized file upload and chunking.

## 9. Роли пользователей

### 9.1. Обычный сотрудник

Может:

- входить в портал;
- использовать доступные сценарии;
- создавать чаты внутри разрешенных сценариев;
- загружать разрешенные файлы;
- использовать разрешенные модели;
- видеть свои результаты.

Не может:

- менять системные prompts;
- менять общие шаблоны;
- подключать модели;
- видеть чужие чаты без явного решения privacy/security;
- менять лимиты;
- видеть API keys.

### 9.2. Руководитель отдела / РО

Может:

- использовать сценарии своего отдела;
- предлагать шаблоны;
- видеть общие шаблоны отдела;
- согласовывать методологию;
- видеть агрегированную статистику только если это согласовано privacy/security policy.

### 9.3. AI-методолог / опытный пользователь

Может:

- создавать и улучшать prompt templates;
- настраивать сценарии;
- описывать правила работы;
- готовить примеры хороших запросов;
- обновлять инструкции;
- тестировать новые сценарии;
- обучать сотрудников.

Это не обязательно разработчик. Это владелец методологии использования AI в конкретной задаче.

### 9.4. Администратор

Может:

- управлять пользователями;
- управлять группами;
- подключать модели;
- управлять доступом к web-search/STT;
- смотреть usage analytics;
- выполнять диагностику;
- управлять server-local configuration вместе с оператором.

## 10. Данные и безопасность

PRD-1 затрагивает чувствительные данные:

- брокерские отчеты;
- налоговые документы;
- персональные данные;
- финансовую информацию;
- аудио встреч;
- внутренние документы;
- договоры;
- таблицы;
- коммерческую информацию.

Требования:

- добавить политику допустимых данных;
- явно указать, что нельзя отправлять в ИИ;
- добавить warnings в сценариях;
- разграничить доступ по группам;
- не раскрывать API keys пользователям;
- не хранить секреты в git;
- не логировать чувствительные данные без необходимости;
- определить срок хранения загруженных файлов;
- определить срок хранения транскрибаций;
- определить, кто имеет доступ к результатам;
- для налоговых/финансовых сценариев явно указывать, что результат требует проверки человеком;
- отдельно решить, может ли администратор видеть чужие чаты через OpenWebUI admin surfaces.

## 11. Финансовая информация

Цены проверены 2026-06-16 по официальным или первичным страницам. Перед коммерческим предложением и production-включением тарифы нужно перепроверить.

| Сервис | Назначение | Цена | Единица тарификации | Лимиты / условия | Источник | Комментарий |
| --- | --- | --- | --- | --- | --- | --- |
| Brave Search API - Search | Зарубежный web-search | $5 за 1,000 requests | request | $5 monthly credits, 50 QPS | https://brave.com/search/api/ | Хороший первый кандидат для web-search. |
| Brave Search API - Answers | Grounded answers | $4 за 1,000 requests + $5 за 1M input/output tokens | request + tokens | $5 monthly credits, 2 QPS | https://brave.com/search/api/ | Не путать с обычным Search. Для PRD-1 лучше начать с `brave_llm_context`. |
| Yandex Search API | Российский web-search | $4 за 1,000 daytime sync requests; $0.25 за 1,000 daytime deferred; $41.64 за 1,000 sync requests with generative response | request | Night rates дешевле; в РФ примеры: 488 ₽ / 1,000 sync, 30.5 ₽ / 1,000 deferred, 5,080 ₽ / 1,000 generative | https://aistudio.yandex.ru/docs/en/search-api/pricing.html | Проверить native Yandex provider или внешний adapter. |
| YandexGPT Lite | Российский LLM | $0.001639344 input; $0.001639344 output | 1,000 tokens | USD for non-RU contracts, RUB for Yandex.Cloud LLC | https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html | Дешевый кандидат для массовых русских задач, требует quality smoke. |
| YandexGPT Pro 5.1 | Российский LLM | $0.006557376 input; $0.006557376 output | 1,000 tokens | Tool/cached tokens тарифицируются отдельно | https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html | Проверить качество для документов и делового русского. |
| GigaChat API Lite legal PAYG | Российский LLM | 0.065 ₽ sync; 0.0325 ₽ async | 1,000 tokens | Минимальные расходы 600 ₽/month if used | https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs | Для юрлиц. Старые модели перенаправляются на GigaChat-2 equivalents. |
| GigaChat API Pro legal PAYG | Российский LLM | 0.5 ₽ sync; 0.25 ₽ async | 1,000 tokens | Минимальные расходы 600 ₽/month if used | https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs | Проверить auth, contracts, commercial terms. |
| GigaChat API Max legal PAYG | Российский LLM | 0.65 ₽ sync; 0.325 ₽ async | 1,000 tokens | Минимальные расходы 600 ₽/month if used | https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs | Premium RU path after pilot. |
| Claude Haiku 4.5 | LLM economy | $1 input / $5 output | 1M tokens | context 200k | https://platform.claude.com/docs/en/about-claude/models/overview | Быстрая и дешевая Claude-модель. |
| Claude Sonnet 4.6 | LLM balanced | $3 input / $15 output | 1M tokens | context 1M | https://platform.claude.com/docs/en/about-claude/models/overview | Основной Claude candidate по price/quality. |
| Claude Opus 4.8 | LLM premium | $5 input / $25 output | 1M tokens | context 1M | https://platform.claude.com/docs/en/about-claude/models/overview | Дорогая модель для сложных задач. |
| OpenAI GPT-5.4 mini | LLM primary PRD-0 | $0.75 input / $4.50 output | 1M tokens | Standard, short context | https://openai.com/api/pricing/ | Сохранять как default, если качество устраивает. |
| OpenAI GPT-5.4 | LLM stronger | $2.50 input / $15 output | 1M tokens | Standard, short context | https://openai.com/api/pricing/ | Для более сложных задач. |
| OpenAI GPT-5.5 | LLM premium | $5 input / $30 output | 1M tokens | Standard, short context | https://openai.com/api/pricing/ | Не включать всем по умолчанию. |
| OpenAI STT | Transcription fallback | gpt-4o-mini-transcribe $0.003/min; gpt-4o-transcribe $0.006/min | minute | OpenAI Audio API | https://developers.openai.com/api/docs/pricing | Альтернатива Lemonfox, дороже Lemonfox. |
| OpenAI Web Search tool | Web-search alternative | $10 за 1,000 calls + model token costs | call + tokens | Built-in tool pricing | https://developers.openai.com/api/docs/pricing | Не основной путь для OpenWebUI web-search. |
| Gemini 3.5 Flash | LLM, current Gemini candidate | $1.50 input / $9 output | 1M tokens | Google Search grounding: 5,000 prompts/month free, then $14 / 1,000 search queries | https://ai.google.dev/gemini-api/docs/pricing | Использовать после проверки key/quota. |
| DeepSeek V4 Flash | LLM low-cost | cache hit $0.0028 input; cache miss $0.14 input; $0.28 output | 1M tokens | Concurrency 2500; aliases `deepseek-chat`/`deepseek-reasoner` planned deprecation 2026-07-24 | https://api-docs.deepseek.com/quick_start/pricing | Draft says connected, but repo needs operator evidence. |
| DeepSeek V4 Pro | LLM stronger | cache hit $0.003625 input; cache miss $0.435 input; $0.87 output | 1M tokens | Concurrency 500 | https://api-docs.deepseek.com/quick_start/pricing | Проверить качество и use cases. |
| Lemonfox STT | Speech-to-text | $0.50 за 3 hours, около $0.1667/hour | audio hour | Direct upload 100MB, URL upload 1GB, max 4 speaker labels | https://www.lemonfox.ai/apis/speech-to-text | Цена подтверждает вводную $0.17/h. |
| LiteLLM Gateway | Gateway/cost control | OSS/gateway cost is infra/ops; provider token costs remain separate | infra + optional support | Budgets, virtual keys, rate limits, spend tracking require deployment | https://docs.litellm.ai/docs/proxy/virtual_keys | Не внедрять до решения, что native analytics недостаточно. |
| Infrastructure/storage | Сервер, storage, backups | TBD | month/GB/CPU | Зависит от STT/files/web-search нагрузок | local deployment estimates | Уточнить после volume/file-retention decisions. |

## 12. Метрики успеха

PRD-1 считается успешным, если:

- сотрудники используют не только общий чат, но и рабочие сценарии;
- минимум 3 регулярных сценария оформлены как повторяемые процессы;
- опытные пользователи могут создавать и улучшать шаблоны;
- новые сотрудники пользуются готовыми сценариями без долгого обучения;
- администратор видит расходы или хотя бы получает базовую оценку стоимости;
- доступ можно ограничивать по группам;
- документы и аудио обрабатываются через понятные сценарии;
- web-search работает управляемо;
- по каждому новому provider есть цена, назначение и ограничения;
- заказчик понимает, за что платит и как контролировать рост расходов.

## 13. Acceptance criteria верхнего уровня

PRD-1 можно принимать, если выполнено следующее:

1. Есть минимум 3 рабочих сценария с правилами, prompts и доступом по группам.
2. Есть работающий сценарий транскрибации mp3.
3. Есть проверенный сценарий обработки видео с извлечением аудио или описанием технических ограничений.
4. Есть рабочий сценарий анализа PDF/DOCX/XLSX с описанными ограничениями.
5. Есть пилотный сценарий брокерского отчета/3-НДФЛ с ручной проверкой.
6. Есть минимум один рабочий web-search provider.
7. Есть исследование и решение по второму web-search provider.
8. DeepSeek описан и проверен или явно помечен как pending operator evidence.
9. YandexGPT и GigaChat исследованы, подключены или отклонены с объяснением.
10. Есть решение по native billing vs gateway.
11. Есть базовая таблица цен по providers.
12. Есть AD/SSO discovery и выбранная схема интеграции.
13. Есть инструкция для пользователей.
14. Есть инструкция для администратора.
15. Есть smoke/acceptance checks.
16. Нет утечки секретов в git.
17. Все новые функции документированы.

## 14. Этапность реализации

### Этап 1. Discovery и архитектурное уточнение

- проверить текущие возможности OpenWebUI на установленной версии;
- проверить, что можно сделать штатно;
- уточнить AD/SSO схему;
- уточнить native billing vs gateway;
- уточнить providers и тарифы;
- согласовать финальный scope.

Результат:

- обновленный PRD;
- architecture decision record;
- список confirmed / deferred / rejected features.

### Этап 2. Рабочие сценарии и шаблоны

- создать группы;
- настроить curated workspace models;
- добавить shared prompts и Knowledge;
- добавить инструкции;
- протестировать на пилотных пользователях.

### Этап 3. Providers, web-search и cost control

- описать model catalog;
- подключить/проверить DeepSeek;
- исследовать YandexGPT/GigaChat;
- подключить web-search;
- включить native Analytics;
- принять gateway decision.

### Этап 4. Транскрибация

- исследовать текущий затык с mp3;
- проверить Lemonfox/OpenAI STT/native STT;
- реализовать отдельный сценарий транскрибации;
- исследовать browser-side ffmpeg.wasm;
- протестировать большие аудио/видео.

### Этап 5. Документы

- проверить PDF/DOCX/XLSX;
- добавить шаблоны анализа;
- описать ограничения file upload/RAG;
- определить, где нужен parser/tool/document pipeline.

### Этап 6. AD/SSO pilot

- настроить тестовую группу;
- проверить вход;
- проверить маппинг групп;
- проверить отключение пользователя;
- подготовить инструкцию администратора.

## 15. Открытые вопросы

1. Какие отделы первыми участвуют в PRD-1?
2. Кто будет AI-методологом/владельцем шаблонов?
3. Какие 3 сценария самые важные для первого релиза?
4. Нужно ли хранить загруженные файлы после обработки?
5. Нужно ли хранить транскрибации?
6. Кто может видеть аудио/транскрибации встреч?
7. Какие персональные/финансовые данные разрешено отправлять в модели?
8. Какие модели допустимы для чувствительных данных?
9. Нужна ли отдельная политика для 3-НДФЛ и брокерских отчетов?
10. Какой AD/SSO используется у заказчика?
11. Нужна ли авторизация без ввода пароля внутри доменной сети?
12. Какие лимиты по расходам приемлемы на пользователя/отдел/месяц?
13. Кто оплачивает и контролирует API keys?
14. Нужно ли отделять тестовые модели от production-моделей?
15. Делать ли fork OpenWebUI уже в PRD-1 или сначала реализовать внешнюю обвязку?
16. Какие форматы аудио/видео реально используют сотрудники?
17. Какие шаблоны документов уже есть у заказчика?
18. Какие реальные брокерские отчеты можно использовать для тестирования?
19. Нужен ли web-search всем пользователям или только отдельным ролям?
20. Нужно ли логировать запросы пользователей, и если да - в каком объеме?

## 16. Drift notes

Эти пункты требуют внимания перед утверждением PRD-1:

- Draft говорит, что DeepSeek уже подключен. В текущем PRD-0 репозитории это не подтверждено, нужен operator evidence.
- Draft предполагает billing через LiteLLM. В PRD-1 зафиксирован native-first подход: OpenWebUI Analytics и access control сначала, LiteLLM только при необходимости hard budgets/enforcement.
- Draft говорит о рабочих пространствах как единой product-сущности. В OpenWebUI это лучше собирать из Workspace Models, Prompts, Knowledge, Groups и Permissions. Если нужен отдельный first-class UX, это уже implementation/fork question.
- Web-search уже был non-goal PRD-0, но есть research-документ. В PRD-1 это можно включать только отдельным scope decision.
- Транскрибация через Lemonfox вероятно подходит по цене и API, но diarization, large files и browser-side processing требуют pilot proof.
- Работа с Excel как с таблицей может не закрыться простым upload/RAG. Нужен отдельный parser/tool decision.
- Доступ руководителей к чатам сотрудников требует отдельного privacy/security решения, не должен появляться как побочный эффект админских прав.
- Репозиторий PRD-0 pinned на OpenWebUI `v0.9.6`, а native capability map сверялся по актуальной документации OpenWebUI. Перед implementation нужно проверить feature parity на текущей deployed версии или запланировать controlled update.

## 17. Non-goals PRD-1

В PRD-1 не входит:

- создание собственной LLM-модели;
- локальное обучение модели;
- полная замена налогового консультанта;
- автоматическая подача 3-НДФЛ;
- полноценная DLP/SIEM/security-платформа;
- полный корпоративный документооборот;
- полноценный RAG по всем документам компании;
- полная автоматизация всех бизнес-процессов;
- собственный custom frontend с нуля;
- агентная система, которая сама ходит в 1С/CRM и выполняет действия;
- гарантия идеальной обработки любых PDF/Excel;
- гарантия юридической/налоговой корректности результатов ИИ.

## 18. Sources

OpenWebUI:

- https://docs.openwebui.com/features/authentication-access/
- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/authentication-access/auth/sso/
- https://docs.openwebui.com/features/authentication-access/auth/ldap/
- https://docs.openwebui.com/features/authentication-access/auth/scim/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/chat-conversations/chat-features/conversation-organization/
- https://docs.openwebui.com/category/web-search/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/openai-stt-integration/
- https://docs.openwebui.com/features/administration/analytics/

Provider pricing and integration:

- https://brave.com/search/api/
- https://aistudio.yandex.ru/docs/en/search-api/pricing.html
- https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html
- https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://openai.com/api/pricing/
- https://developers.openai.com/api/docs/pricing
- https://ai.google.dev/gemini-api/docs/pricing
- https://api-docs.deepseek.com/quick_start/pricing
- https://www.lemonfox.ai/apis/speech-to-text
- https://docs.litellm.ai/docs/proxy/virtual_keys

## 19. Итоговая формулировка

PRD-1 - это этап превращения корпоративного OpenWebUI из простого пилотного чата в управляемую рабочую AI-среду.

Основные результаты этапа:

- рабочие сценарии;
- общие prompts и templates;
- сценарии для документов, аудио, web-search и брокерских отчетов;
- управляемые модели;
- базовый контроль расходов;
- корпоративный доступ;
- первые правила безопасного использования.

PRD-1 не должен превращаться в бесконечную AI-платформу. Его задача - создать управляемый, понятный и расширяемый контур для регулярных корпоративных AI-сценариев.
