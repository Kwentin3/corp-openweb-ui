# OpenWebUI Corporate Chat PRD-1 Refined

Статус: refined draft перед согласованием с заказчиком
Дата: 2026-06-16
Проект: корпоративный портал AI-чата на базе OpenWebUI
Предыдущий этап: PRD-0 принят заказчиком и закрыт
Текущий этап: Stage 2 / PRD-1 discovery + implementation draft

## 1. Executive summary

PRD-1 - это этап превращения корпоративного OpenWebUI из пилотного AI-чата в управляемую среду регулярных рабочих сценариев.

Главная ценность PRD-1 не в количестве подключенных моделей и сервисов, а в том, что регулярные задачи сотрудников превращаются в управляемые рабочие сценарии: с готовыми промтами, шаблонами, правилами, доступами, ограничениями и понятной стоимостью.

Stage 2 не должен быть бесконечной AI-платформой. Его нужно вести как набор проверяемых business slices:

- сначала обязательное ядро управления сценариями;
- затем пилотные сценарии;
- отдельно architecture decisions для fork, gateway, hard billing, сложного document pipeline и full AD lifecycle.

## 2. Customer-facing explanation

На втором этапе мы не предлагаем просто подключить еще несколько моделей. Основная задача - превратить корпоративный чат в управляемые рабочие сценарии. Это позволит сильным пользователям один раз настроить правила, шаблоны и промты, а остальным сотрудникам работать внутри этих готовых сценариев без постоянной борьбы с ИИ.

Отдельно важно зафиксировать ограничение по офисным документам. Word, PDF и Excel - это не просто текстовые файлы. В них есть структура, таблицы, формулы, форматирование, сканы, комментарии и скрытые данные. Поэтому корректная работа с такими файлами строится не на магии LLM, а на связке: парсер -> структурированное представление -> LLM -> шаблон/экспорт -> проверка человеком.

В PRD-1 мы предлагаем начать с управляемых типовых сценариев и явно описанных ограничений, не обещая идеальную обработку любых документов.

## 3. Контекст и связь с PRD-0

PRD-0 был фазой смотрин: поднять OpenWebUI на `gpt.alpha-soft.ru`, подключить provider, дать 3-4 пользователям рабочую точку входа и проверить интерес.

Post-acceptance audit зафиксировал:

- PRD-0 accepted;
- production path не включал LiteLLM, model gateway, RAG, web-search, document skills, fork OpenWebUI и custom frontend;
- OpenAI primary исторически проверен;
- Gemini secondary, pilot users и часть Admin UI state требуют operator confirmation, если их нужно использовать как исходную точку Stage 2;
- Stage 2 должен начинаться с discovery, а не с silent implementation.

PRD-1 не расширяет PRD-0 задним числом. Он описывает следующий этап.

## 4. Проблема

Сотрудники уже могут пользоваться ИИ, но делают это разрозненно:

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

Риск Stage 2 - попытаться решить все это списком функций. Правильный путь - оформлять рабочие сценарии с ясными границами.

## 5. Цель PRD-1

Создать управляемую корпоративную AI-среду на базе OpenWebUI, где:

- сотрудники входят через корпоративную учетную запись или согласованную interim-схему;
- видят доступные им рабочие сценарии;
- используют подготовленные prompts, templates, knowledge и правила;
- работают с документами, аудио, видео и web-search в рамках описанных ограничений;
- используют модели в рамках заданной политики;
- администратор управляет пользователями, группами, моделями и базовой аналитикой расходов;
- сложные решения вроде gateway, fork и full AD lifecycle принимаются отдельно.

## 6. Product principle

PRD-1 строится вокруг рабочих сценариев, а не вокруг списка моделей.

Модель - это инструмент. Рабочий сценарий - это способ превратить инструмент в регулярный процесс.

Плохо: подключить Claude, DeepSeek, YandexGPT, GigaChat, Brave и Яндекс.

Хорошо: создать сценарий "Брокерские отчеты и 3-НДФЛ", где сотрудник загружает отчет, использует утвержденный шаблон, получает черновик разбора, видит предупреждения и передает результат на ручную проверку.

## 7. Scope buckets

### 7.1. Корзина 1. Обязательное ядро Stage 2

Это то, без чего Stage 2 теряет смысл:

- рабочие сценарии;
- группы доступа;
- curated workspace models;
- общие prompts;
- общие инструкции/knowledge;
- базовый model catalog;
- базовая аналитика расходов;
- пользовательская инструкция;
- админская инструкция;
- smoke/acceptance checks;
- политика допустимых данных.

Цель ядра - дать управляемость: кто чем пользуется, по каким правилам, с какими ограничениями и как это проверяется.

### 7.2. Корзина 2. Пилотные сценарии Stage 2

Это проверяемые business slices:

- брокерские отчеты / 3-НДФЛ;
- транскрибация встреч;
- работа с PDF/DOCX/XLSX;
- web-search;
- DeepSeek/YandexGPT/GigaChat/Claude provider evaluation.

Каждый пилотный сценарий должен иметь отдельный owner, входные данные, ограничения, acceptance criteria и test set.

### 7.3. Корзина 3. Отдельные architecture decisions / future slices

Эти пункты учтены, но не становятся обязательной реализацией Stage 2 автоматически:

- fork OpenWebUI;
- browser-side ffmpeg.wasm;
- LiteLLM/gateway;
- hard budgets/enforcement;
- full AD lifecycle / SCIM rollout;
- полноценный document pipeline;
- production-grade генерация DOCX/XLSX;
- сложный Excel parser;
- OCR/layout pipeline;
- доступ руководителей к чатам сотрудников;
- полноценный RAG по всем документам компании;
- агентная система, которая сама выполняет действия в 1С/CRM.

Если один из этих пунктов нужен заказчику, он оформляется отдельным decision/slice с оценкой стоимости, риска и acceptance.

## 8. Native OpenWebUI first

PRD-1 должен максимально использовать штатные возможности OpenWebUI. Fork, отдельный frontend и gateway добавляются только после доказательства, что нативных возможностей недостаточно.

| Потребность PRD-1 | Нативный механизм OpenWebUI | Статус | Комментарий |
| --- | --- | --- | --- |
| Рабочие сценарии | Workspace Models + Prompts + Knowledge + Groups + access control | can be done by configuration | В OpenWebUI нет единой product-сущности "business workspace", но сценарий можно собрать из нативных механизмов. |
| Общие prompts | Workspace Prompts, slash commands, variables, version history, sharing | can be done by configuration | Подходит для 3-НДФЛ, документов, встреч, web-search. |
| Общие инструкции/knowledge | Workspace Knowledge, directories, attach to model, reference with `#` | can be done by configuration | Не считать полноценным корпоративным RAG. |
| Доступ по группам | Groups, RBAC, resource access control | can be done by configuration | Permission model additive/union-based: deny-прав нет. |
| Model catalog | Workspace Models and model access control | can be done by configuration | Рекомендуемый путь: curated models вместо хаотичного списка provider-моделей. |
| File upload / документы | Chat file upload, Knowledge, RAG/full context, storage settings | partly native | Хорошо для Level 1-2, но сложные XLSX/PDF требуют parser/tool decisions. |
| Web-search | Native Web Search providers and feature permissions | can be done by configuration | Для текущего proxy bridge проверить `WEB_SEARCH_TRUST_ENV=True`. |
| STT | Native STT settings, OpenAI-compatible/OpenAI, local Whisper, other providers by version | partly native | Lemonfox проверить как OpenAI-compatible STT endpoint. |
| SSO/AD | OIDC/OAuth, LDAP, trusted header, SCIM | can be done by configuration / requires customer decision | Зависит от инфраструктуры заказчика. |
| Billing/usage | OpenWebUI Analytics and cost estimation | partly native | Приоритет для PRD-1. Hard enforcement может потребовать gateway. |
| Hard budgets | Нет полного native enforcement для всех LLM/web-search/STT расходов | architecture decision | Не обещать без gateway decision. |
| Browser-side ffmpeg.wasm | Нет штатного сценария | possible implementation/fork slice | Требует proof по памяти, браузерам, UX и fallback. |

### 8.1. Billing decision

В исходном draft упоминался "LightLLM". Корректное название кандидата - LiteLLM.

Порядок для PRD-1:

1. Сначала использовать нативные возможности OpenWebUI: Analytics, token usage, per-user/per-model reports, group/model access control, отключение дорогих функций по группам, provider-side budgets.
2. Если нужно только видеть примерную стоимость - gateway не обязателен.
3. Если нужны hard budgets, rate limits, virtual keys, team budgets, centralized routing и единая стоимость по providers - изучать LiteLLM отдельным gateway-slice.
4. LiteLLM не должен появляться в production path автоматически. Его внедрение требует architecture decision, backup/restore path, security review, monitoring и rollback.

## 9. Сценарии Stage 2

### 9.1. Рабочие сценарии, группы и шаблоны

Минимальный набор:

1. Брокерские отчеты и 3-НДФЛ.
2. Транскрибация встреч.
3. Работа с документами.
4. Web-search и исследование.
5. Общий корпоративный AI-чат.

Implementation path:

- создать группы доступа;
- создать curated workspace models под сценарии;
- прикрепить system prompt, knowledge и prompts;
- добавить shared prompts с переменными;
- ограничить доступ по группам;
- описать владельца каждого сценария.

Acceptance:

- минимум 3 сценария;
- каждый сценарий имеет описание, правила, prompts, owner и access group;
- пользователь видит только разрешенные сценарии;
- методолог может обновлять prompts через согласованный процесс.

### 9.2. Брокерские отчеты и 3-НДФЛ

Цель - пилотная помощь сотрудникам при работе с брокерскими отчетами и подготовкой материалов для 3-НДФЛ.

Граница обещаний:

- система не является налоговым консультантом;
- система не подает декларации;
- результат ИИ - черновик и аналитическая помощь;
- итог требует проверки человеком.

Native-first path:

- curated workspace model "Брокерские отчеты / 3-НДФЛ";
- system prompt с запретом финальных налоговых утверждений;
- shared prompt templates для извлечения данных, вопросов к пользователю и черновика пояснений;
- Knowledge с утвержденной инструкцией и примерами;
- file upload для тестовых PDF/XLSX/DOCX;
- access group только для разрешенных пользователей.

Requires implementation if:

- нужно надежно извлекать таблицы из XLSX/PDF;
- нужны валидаторы налоговых полей;
- нужен экспорт в строгий формат;
- нужны audit logs по каждому обработанному отчету.

Acceptance:

- пользователь выбирает сценарий;
- загружает тестовый отчет;
- получает структурированный черновик;
- видит предупреждение о ручной проверке;
- система выделяет неуверенные места и вопросы к пользователю;
- сценарий документирован для пользователя и администратора.

### 9.3. Web-search

Цель - управляемый web-search с контролем стоимости, источников и доступа.

Native-first path:

- использовать штатный OpenWebUI Web Search;
- начать с `brave_llm_context` как зарубежного provider;
- исследовать Yandex Search API или native Yandex provider path как российский provider;
- включать web-search только для разрешенной группы;
- для текущего proxy bridge проверить `WEB_SEARCH_TRUST_ENV=True`;
- ограничить concurrency и result count.

Acceptance:

- администратор может включить/выключить web-search;
- пользователь из разрешенной группы выполняет русский и английский запрос;
- пользователь без прав не использует web-search;
- в документации указаны provider, тарифы, лимиты и smoke-запросы;
- есть инструкция, когда web-search использовать нельзя.

### 9.4. Транскрибация аудио и видео

Цель - отдельный рабочий сценарий "Транскрибация встреч", а не случайная загрузка файла в обычный чат.

Native-first path:

- проверить native OpenWebUI STT;
- проверить Lemonfox как OpenAI-compatible STT endpoint;
- если нужен только короткий audio-to-text в chat input, начинать без fork;
- если нужен процесс "загрузить запись -> получить протокол/задачи/follow-up", оформить отдельный сценарий.

Possible implementation/fork slice:

- browser-side extraction audio from video;
- ffmpeg.wasm UX;
- chunking больших файлов;
- async callback flow;
- diarization with `speaker_labels`;
- серверный fallback для больших файлов.

Fork is not a product goal. Fork is an implementation tool.

Перед browser-side ffmpeg.wasm нужно проверить:

- память браузера;
- длительные видео;
- Chrome/Edge/Firefox/Safari;
- mobile constraints;
- fallback на сервер;
- UX прогресса;
- отмену задачи;
- повторную загрузку;
- обработку ошибок.

Acceptance:

- пользователь загружает mp3 и получает расшифровку;
- пользователь загружает видеофайл и получает расшифровку аудиодорожки или понятное ограничение;
- пользователь выбирает шаблон результата: резюме, протокол, задачи, решения, follow-up;
- большие файлы не ломают обычный чат;
- неподдерживаемый формат дает понятную ошибку;
- текущий затык с mp3 исследован и описан.

### 9.5. Работа с Word/PDF/Excel

Цель - оформить типовые сценарии работы с документами, а не обещать магическую обработку любых файлов.

Минимальные сценарии:

1. Анализ PDF.
2. Анализ DOCX.
3. Анализ XLSX.
4. Сравнение двух простых документов с оговорками.
5. Извлечение ключевых тезисов.
6. Извлечение таблиц там, где это технически надежно.
7. Подготовка черновика по шаблону.

#### Почему работа с офисными документами требует осторожности

LLM и агенты часто плохо работают с офисными документами не потому, что модель "глупая", а потому что офисные файлы - это не простой текст.

##### Word / DOCX

DOCX - это контейнер со структурой, стилями, таблицами, комментариями, заголовками, сносками, track changes, изображениями и embedded objects.

Если просто извлечь текст и отправить его в LLM, теряется часть структуры:

- форматирование;
- таблицы;
- комментарии;
- правки;
- колонтитулы;
- сноски;
- вложенные объекты;
- смысловая иерархия документа.

"Анализировать текст DOCX" и "сформировать корректный DOCX обратно" - разные задачи.

##### PDF

PDF часто хранит не логический документ, а визуальную страницу.

Проблемы:

- порядок чтения может быть неправильным;
- таблицы могут разваливаться;
- колонки могут смешиваться;
- сканы требуют OCR;
- подписи, печати, изображения и мелкий текст требуют layout-aware обработки;
- извлечение таблиц из PDF часто нестабильно.

PDF нужно делить на типы:

- текстовый PDF;
- сканированный PDF;
- PDF с таблицами;
- PDF с формами;
- PDF с подписями/печатями;
- отчет/выписка/договор.

##### Excel / XLSX

Excel - самый рискованный формат для "просто спросить у ИИ".

XLSX - это рабочая книга:

- несколько листов;
- формулы;
- форматирование;
- скрытые строки/колонки;
- merged cells;
- фильтры;
- сводные таблицы;
- ссылки между листами;
- типы данных;
- даты;
- локали;
- валюты;
- комментарии;
- именованные диапазоны;
- макросы;
- внешние ссылки.

Если просто превратить Excel в текст, можно потерять формулы, связи и смысл таблицы.

В PRD-1 Excel не должен позиционироваться как бесшовная магическая загрузка любых таблиц. Базовый сценарий - анализ простых XLSX с описанными ограничениями. Для сложных Excel-файлов требуется отдельный parser/tool decision.

LLM может хорошо объяснять таблицу, искать странности и формировать выводы, но точные расчеты, формулы и преобразования XLSX должны выполняться инструментами, а не самой моделью.

#### Recommended document processing strategy

Общий принцип: не отправлять сырой офисный файл напрямую в LLM как единственный источник истины.

Правильный pipeline:

1. Определить тип файла.
2. Извлечь структуру специальным инструментом.
3. Преобразовать в промежуточный формат.
4. Отдать LLM очищенное и структурированное представление.
5. Получить ответ.
6. При необходимости сформировать файл обратно через шаблонизатор/генератор, а не руками LLM.
7. Проверить результат тестами или человеком.

Для DOCX:

- извлекать текст, заголовки, таблицы и комментарии отдельно;
- сохранять структуру документа;
- для генерации использовать шаблоны DOCX;
- не просить LLM самостоятельно сделать правильный DOCX без шаблонизатора;
- для production-сценариев использовать docx template pipeline.

Для PDF:

- различать текстовый PDF и скан;
- для сканов использовать OCR;
- для таблиц использовать отдельный extractor;
- для договоров/текстовых документов начинать с text extraction;
- для отчетов/выписок с таблицами нужен layout/table-aware parser;
- результат всегда сопровождать предупреждением о возможной потере структуры.

Для XLSX:

- использовать XLSX parser, например openpyxl/pandas или аналогичный tool;
- извлекать листы, диапазоны, заголовки, типы колонок, формулы;
- для LLM передавать summary + schema + sample rows + calculated facts;
- для больших таблиц не отправлять весь файл в контекст;
- для расчетов использовать код/табличный движок, а не LLM;
- для генерации XLSX использовать template/export tool;
- LLM использовать для объяснения, анализа, поиска аномалий и формирования выводов.

#### Document capability levels

| Level | Название | Что входит | Статус для PRD-1 |
| --- | --- | --- | --- |
| Level 1 | Basic file understanding | загрузка файла, извлечение текста, краткое резюме, Q/A по содержанию | target для PDF/DOCX и простых XLSX |
| Level 2 | Structured extraction | таблицы, структура, листы Excel, поля, JSON/CSV intermediate representation | target для PDF/DOCX; XLSX только после parser/tool decision |
| Level 3 | Template-based generation | DOCX/XLSX по утвержденному шаблону, controlled export | один пилотный DOCX-сценарий, если есть шаблон |
| Level 4 | Production document workflow | очередь, OCR, layout parsing, validation, audit logs, версии, rights, human approval | out of scope PRD-1 |

Целевой уровень PRD-1:

- PDF/DOCX: Level 1-2;
- XLSX: Level 1 для простых файлов, Level 2 только после parser/tool decision;
- генерация DOCX: один пилотный Level 3 сценарий, если есть шаблон;
- production document workflow Level 4 - out of scope.

#### Acceptance criteria для документов

- пользователь загружает простой текстовый PDF и получает структурированный анализ;
- пользователь загружает DOCX и получает анализ текста/структуры с описанными ограничениями;
- пользователь загружает простой XLSX и получает анализ таблицы с указанием листов, колонок и ограничений;
- система явно предупреждает, если файл слишком сложный: скан, тяжелый PDF, сложный XLSX, много листов, формулы, макросы, merged cells;
- для Excel-расчетов система использует parser/tool/code path или явно пишет, что точные расчеты не выполнялись;
- есть минимум 3 prompt templates для документов;
- есть минимум 1 сценарий генерации DOCX по шаблону или явно описано, почему генерация перенесена;
- причины медленной загрузки файлов исследованы: OpenWebUI limits, Traefik timeouts, storage, RAG/indexing, browser upload, file parsing;
- есть тестовый набор файлов: простой PDF, сканированный PDF, DOCX с таблицей, простой XLSX, сложный XLSX с несколькими листами/формулами;
- по каждому тестовому файлу есть expected result.

### 9.6. Корпоративный доступ через AD/домен

Цель - сотрудники входят через корпоративную учетную запись, а доступ управляется через группы.

Native options:

- OIDC/OAuth with role and group claim management;
- LDAP auth;
- Trusted Header auth behind authenticating reverse proxy;
- SCIM 2.0 for automated user/group provisioning.

Граница обещаний:

- PRD-1 включает AD/SSO discovery и пилотную схему;
- full AD lifecycle / SCIM rollout не обещается без customer infrastructure discovery;
- маппинг групп должен быть подтвержден на тестовой группе.

Acceptance:

- выбранная схема documented;
- есть тестовая группа;
- пользователь из группы входит;
- пользователь вне группы не получает доступ;
- есть карта соответствия групп AD и групп/ролей OpenWebUI;
- описан процесс offboarding.

### 9.7. Provider evaluation: DeepSeek, YandexGPT, GigaChat, Claude

Цель - понять, какие provider реально полезны для русскоязычных корпоративных сценариев, сколько стоят и как подключаются.

Tasks:

- изучить API и auth;
- проверить OpenAI-compatible path или adapter need;
- проверить цены;
- выполнить smoke-test при наличии доступа;
- оценить качество на задачах: резюме документа, письмо, анализ текста, таблица, встреча;
- добавить вывод в model catalog.

Важное уточнение по DeepSeek: исходный PRD-1 говорит, что DeepSeek уже подключен через API/Cloud. В текущем репозитории это не подтверждено, поэтому статус для refined PRD: needs operator evidence.

Acceptance:

- provider описан: подключение, модели, цена, ограничения;
- если доступ получен - выполнен тестовый запрос;
- если доступ не получен - явно описано, что мешает;
- есть рекомендация: production / pilot / reject / deferred.

### 9.8. Billing, лимиты и контроль расходов

Цель - сделать расходы видимыми и управляемыми.

Native-first target:

- OpenWebUI Analytics;
- token usage по пользователям и моделям;
- формула расчета стоимости;
- price catalog в docs;
- доступ к дорогим моделям через Groups/Model access;
- web-search/STT по группам;
- provider-side budgets там, где доступны.

Что не обещаем без отдельного решения:

- hard monthly budget enforcement;
- лимиты по всем provider и всем external API в одном месте;
- guaranteed blocking при превышении лимита;
- централизованные virtual keys;
- единый router по всем provider.

Для этого нужен gateway decision, например LiteLLM.

Acceptance:

- администратор видит примерный расход по пользователям/группам;
- дорогие модели доступны только разрешенным группам;
- есть price catalog;
- есть список сервисов: LLM tokens, web-search requests, STT hours, storage/files;
- принято решение: native-only for PRD-1 или gateway slice.

## 10. Recommended Stage 2 delivery model

### Stage 2A. Discovery and capability proof

- проверить deployed version OpenWebUI;
- проверить native capabilities;
- проверить AD/SSO;
- проверить Lemonfox;
- проверить web-search;
- проверить file upload/document handling;
- проверить native analytics;
- проверить DeepSeek/YandexGPT/GigaChat/Claude;
- подготовить final scope.

### Stage 2B. Configuration-first implementation

- группы;
- workspace models;
- prompts;
- knowledge;
- model catalog;
- первые рабочие сценарии;
- базовые инструкции.

### Stage 2C. Technical slices

Отдельные slices, каждый с отдельным acceptance:

- transcription slice;
- document processing slice;
- web-search slice;
- billing/gateway slice;
- AD/SSO slice;
- provider catalog slice.

### Stage 2D. Hardening and handoff

- smoke tests;
- admin docs;
- user docs;
- price catalog;
- security notes;
- backup/update notes.

### Effort estimate (рабочая оценка)

Это оценка трудозатрат на реализацию, а не стоимость LLM/API, web-search, STT, сервера или хранения. Коммерческий расчет считается отдельно по формуле: `согласованная ставка * утвержденный диапазон часов`. После Stage 2A диапазоны нужно уточнить по фактической версии OpenWebUI, доступам, провайдерам и требованиям заказчика.

| Блок | Что входит | Оценка |
| --- | --- | --- |
| Stage 2A. Discovery and capability proof | deployed version, native capabilities, providers, AD/SSO, web-search, STT, документы, analytics | 6-10 ч |
| Stage 2B. Native configuration core | группы, workspace models, prompts, Knowledge, model catalog, базовые инструкции | 14-22 ч |
| Рабочие сценарии v1 | 3 сценария, права доступа, шаблоны, smoke cases, пользовательские формулировки | 10-16 ч |
| Billing/cost visibility native-first | price catalog, OpenWebUI analytics check, формула стоимости, первичные admin views/инструкции | 5-8 ч |
| Provider evaluation | DeepSeek/YandexGPT/GigaChat/Claude smoke, короткая матрица качества/цены, рекомендация default models | 5-8 ч |
| Pilot slices package | web-search pilot, STT pilot, базовая проверка DOCX/PDF/XLSX без production document pipeline | 14-22 ч |
| AD/SSO discovery/pilot scheme | проверка варианта подключения, схема ролей/групп, acceptance для дальнейшего rollout | 6-10 ч |
| Hardening and handoff | smoke tests, admin/user docs, backup/update notes, финальная приемка | 8-12 ч |

Рекомендуемый baseline для согласования: 72-108 часов. Он покрывает native-first ядро, 3 рабочих сценария, видимость расходов, provider evaluation и 2-3 пилотных сценария без fork OpenWebUI и без обязательного LiteLLM/gateway.

Опциональные работы не включать в baseline без отдельного решения:

- LiteLLM/gateway для hard budgets/enforcement: +16-28 ч после подтверждения, что native analytics недостаточно;
- production document pipeline, OCR/layout parsing, сложный Excel parser: отдельная оценка после discovery;
- fork OpenWebUI или отдельный frontend: отдельная оценка после fork rationale;
- full AD lifecycle / SCIM rollout: отдельная оценка после customer infrastructure discovery.

## 11. Роли пользователей

### 11.1. Обычный сотрудник

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
- видеть чужие чаты без явного privacy/security decision;
- менять лимиты;
- видеть API keys.

### 11.2. Руководитель отдела / РО

Может:

- использовать сценарии своего отдела;
- предлагать шаблоны;
- согласовывать методологию;
- видеть агрегированную статистику только если это согласовано privacy/security policy.

Не должен автоматически получать доступ к чатам подчиненных.

### 11.3. AI-методолог / опытный пользователь

Может:

- создавать и улучшать prompt templates;
- настраивать сценарии;
- описывать правила работы;
- готовить примеры хороших запросов;
- обновлять инструкции;
- тестировать новые сценарии;
- обучать сотрудников.

### 11.4. Администратор

Может:

- управлять пользователями;
- управлять группами;
- подключать модели;
- управлять доступом к web-search/STT;
- смотреть usage analytics;
- выполнять диагностику;
- управлять server-local configuration вместе с оператором.

## 12. Данные и безопасность

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

## 13. Финансовая информация

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
| Gemini 3.5 Flash | LLM, current Gemini candidate | $1.50 input / $9 output | 1M tokens | Google Search grounding: 5,000 prompts/month free, then $14 / 1,000 search queries | https://ai.google.dev/gemini-api/docs/pricing | Использовать после проверки key/quota. |
| DeepSeek V4 Flash | LLM low-cost | cache hit $0.0028 input; cache miss $0.14 input; $0.28 output | 1M tokens | Concurrency 2500; aliases `deepseek-chat`/`deepseek-reasoner` planned deprecation 2026-07-24 | https://api-docs.deepseek.com/quick_start/pricing | Draft says connected, but repo needs operator evidence. |
| DeepSeek V4 Pro | LLM stronger | cache hit $0.003625 input; cache miss $0.435 input; $0.87 output | 1M tokens | Concurrency 500 | https://api-docs.deepseek.com/quick_start/pricing | Проверить качество и use cases. |
| Lemonfox STT | Speech-to-text | $0.50 за 3 hours, около $0.1667/hour | audio hour | Direct upload 100MB, URL upload 1GB, max 4 speaker labels | https://www.lemonfox.ai/apis/speech-to-text | Цена подтверждает вводную $0.17/h. |
| LiteLLM Gateway | Gateway/cost control | OSS/gateway cost is infra/ops; provider token costs remain separate | infra + optional support | Budgets, virtual keys, rate limits, spend tracking require deployment | https://docs.litellm.ai/docs/proxy/virtual_keys | Не внедрять до решения, что native analytics недостаточно. |
| Infrastructure/storage | Сервер, storage, backups | TBD | month/GB/CPU | Зависит от STT/files/web-search нагрузок | local deployment estimates | Уточнить после volume/file-retention decisions. |

## 14. Acceptance criteria верхнего уровня

PRD-1 можно принимать, если выполнено следующее:

1. Есть минимум 3 рабочих сценария с правилами, prompts и доступом по группам.
2. Есть policy по допустимым данным и предупреждениям.
3. Есть user/admin instructions.
4. Есть базовый model catalog и price catalog.
5. Есть native usage analytics или зафиксирован gateway decision.
6. Есть работающий или явно deferred сценарий транскрибации mp3.
7. Есть проверенный сценарий обработки видео с извлечением аудио или документированным ограничением.
8. Есть сценарий анализа простого PDF/DOCX/XLSX с честными ограничениями.
9. Есть пилотный сценарий брокерского отчета/3-НДФЛ с ручной проверкой.
10. Есть минимум один web-search provider или документированное решение defer.
11. DeepSeek/YandexGPT/GigaChat/Claude описаны, проверены или отклонены с объяснением.
12. Есть AD/SSO discovery и выбранная пилотная схема.
13. Есть smoke/acceptance checks.
14. Нет утечки секретов в git.
15. Все architecture decisions вынесены отдельно и не подменяют обязательное ядро.

## 15. Метрики успеха

PRD-1 успешен, если:

- сотрудники используют не только общий чат, но и рабочие сценарии;
- минимум 3 регулярных сценария оформлены как повторяемые процессы;
- опытные пользователи могут создавать и улучшать шаблоны;
- новые сотрудники пользуются готовыми сценариями без долгого обучения;
- администратор видит расходы или получает базовую оценку стоимости;
- доступ ограничивается по группам;
- документы и аудио обрабатываются через понятные сценарии;
- web-search работает управляемо;
- по каждому new provider есть цена, назначение и ограничения;
- заказчик понимает, за что платит и как контролировать рост расходов.

## 16. Drift notes

Перед согласованием важно проговорить:

- DeepSeek "уже подключен" не подтвержден текущим repo evidence; нужен operator evidence.
- "Бесшовная работа с любыми Word/PDF/Excel" может быть неверно понята как гарантия production document workflow. Формулировка заменена на "типовые сценарии работы с документами с описанными ограничениями".
- "Excel-анализ" не означает, что LLM самостоятельно делает точные расчеты и проверяет формулы. Для этого нужен parser/tool/code path.
- "Генерация документов" не означает свободное создание любых DOCX/XLSX. Для PRD-1 допустим только template-based generation.
- "Загрузка файлов в чат" и "корпоративный document pipeline" - разные уровни продукта.
- OCR, layout-aware PDF parsing, сложные Excel, макросы, track changes, юридически значимое сравнение документов - отдельные implementation decisions или future scope.
- Billing через LiteLLM не является обязательным Stage 2 output. Native analytics and access control first.
- Репозиторий PRD-0 pinned на OpenWebUI `v0.9.6`, а native capability map сверялся по актуальной документации. Перед implementation нужно проверить feature parity на deployed версии или запланировать controlled update.
- Доступ руководителей к чатам сотрудников требует отдельного privacy/security decision.

## 17. Non-goals PRD-1

В PRD-1 не входит:

- создание собственной LLM-модели;
- локальное обучение модели;
- полная замена налогового консультанта;
- автоматическая подача 3-НДФЛ;
- замена бухгалтера, налогового консультанта, юриста или финансового аналитика;
- автоматическое принятие решений на основе брокерских/налоговых документов;
- полноценная DLP/SIEM/security-платформа;
- полный корпоративный документооборот;
- полноценный RAG по всем документам компании;
- полная автоматизация всех бизнес-процессов;
- собственный custom frontend с нуля;
- агентная система, которая сама ходит в 1С/CRM и выполняет действия;
- гарантия корректной обработки любых офисных документов;
- бесшовное сохранение исходной верстки DOCX/PDF;
- юридически значимое сравнение документов;
- точная обработка любых Excel-файлов с формулами, макросами, сводными таблицами и внешними ссылками;
- production-grade OCR/layout pipeline;
- автоматическая генерация любых DOCX/XLSX без утвержденных шаблонов;
- hard billing без gateway decision;
- full AD lifecycle без customer infrastructure discovery;
- обязательный fork OpenWebUI без fork rationale.

## 18. Sources

Local sources:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/blueprint/*`
- `docs/infra/*`
- `docs/ops/*`
- `docs/security/*`
- `docs/reports/2026-06-09/*`

External sources retained from enriched PRD:

- https://docs.openwebui.com/features/authentication-access/
- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/auth/sso/
- https://docs.openwebui.com/features/authentication-access/auth/ldap/
- https://docs.openwebui.com/features/authentication-access/auth/scim/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/administration/analytics/
- https://brave.com/search/api/
- https://aistudio.yandex.ru/docs/en/search-api/pricing.html
- https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html
- https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://openai.com/api/pricing/
- https://ai.google.dev/gemini-api/docs/pricing
- https://api-docs.deepseek.com/quick_start/pricing
- https://www.lemonfox.ai/apis/speech-to-text
- https://docs.litellm.ai/docs/proxy/virtual_keys

## 19. Итоговая формулировка

PRD-1 - это этап превращения корпоративного OpenWebUI из пилотного AI-чата в управляемую среду регулярных рабочих сценариев.

Главный результат - не количество подключенных моделей, а возможность создавать и сопровождать сценарии для отделов: с prompts, templates, доступами, моделями, контролем расходов и понятными ограничениями.

Документ специально отделяет обязательное ядро Stage 2 от пилотных сценариев и от architecture decisions, чтобы второй этап был обсуждаемым, проверяемым и не превращался в бесконечную AI-платформу.
