# Карта архитектуры и воркфлоу (`corp-openweb-ui`)

Актуальный срез: **OpenWebUI 0.12.2** (`gpt.alpha-soft.ru`).

> **Интерактивная карта на одном листе:** [открыть в браузере (GitHub Pages)](https://kwentin3.github.io/corp-openweb-ui/architecture-map.html) или локально [`docs/architecture-map.html`](architecture-map.html) — там можно переключать 6 потоков данных (включая внешний контур 1С «Нейро-помощник»), подсвечивать зону патчей перед апгрейдом и кликать по любому узлу, чтобы увидеть точные пути в репозитории, внешние ссылки и границы с ядром.

Проект построен по принципу **extension-first**: вместо глубокого форка OpenWebUI поверх ванильного `0.12.2` применяются всего **4 узких патча ядра** (плюс **1 патч в LiteLLM**), а вся остальная корпоративная логика вынесена в штатные расширения OpenWebUI и соседние Docker-сервисы. Интеграция с 1С («Нейро-помощник») работает как отдельный внешний контур через публичный API портала (`POST /api/chat/completions`) без правок ядра OpenWebUI.

## Общая схема на одном листе

```mermaid
flowchart LR
  User["Сотрудник / Браузер"] --> Traefik["Traefik (HTTPS)"]
  User -.->|"ffmpeg.wasm"| Shim["Static Browser Shim"]

  subgraph OneC["Внешний контур 1С «Нейро-помощник» (отдельный деплой · пилот)"]
    OneCChat["Пользователь 1С\nHTML-чат «Нейро-помощник»"]
    OneCExt["Расширение «НейроИнтеграция»\n(метаданные, чтение, проекты,\nпроведение с подтверждением)"]
    OneCDB["Информационная база 1С\n(данные, права 1С,\nас_ИсторияНейроЧата)"]
    OneCBroker["Сервер-посредник интеграции\n(контекст, проверка ответов,\nобмен заданиями)"]
    OneCLic["Лицензии, рабочие места и учёт\n(1 пользователь = 1 место;\n1 API-токен на лицензию)"]
  end

  subgraph OWUI["Контейнер OpenWebUI 0.12.2 (openwebui-0122)"]
    Core["Ядро: Chat / Files / RAG / ACL\n(SQLite + ChromaDB)"]
    Audio["Ядро: Audio STT & Realtime WS"]

    subgraph Patches["4 патча ядра (зона апгрейда)"]
      P1["tool-context-v0.12.2\n(3 backend)"]
      P2["media-upload-v0.12.2\n(2 backend + 2 frontend)"]
      P3["status-position-v0.12.2\n(1 Svelte)"]
      P4["provider-context-v0.12.2\n(default-off debug)"]
    end

    subgraph Ext["Штатные расширения (без правок ядра)"]
      EBud["Бюджеты: Cost Filter / Pipe / Tools"]
      EOff["Office: Filters / Word Export / Tools"]
      EOCR["luna_pdf_ocr (Event /process)"]
      EMed["stage2_media_intake"]
      ESkl["Skills & Knowledge (5 Skills + KB)"]
      E1CTool["Tool 1С в портале\n(пилот · требует сверки)"]
    end
  end

  subgraph Services["Внутренние Docker-сервисы"]
    LiteLLM["LiteLLM v1.105.1\n+ floor.patch\n(Шлюз + Биллинг)"]
    OfficeCLI["OfficeCLI\n(DOCX / XLSX / PPTX)"]
    Terminal["Open Terminal\n(Linux multi-user)"]
    STT["Stage2 STT\n(sidecar)"]
    SearXNG["SearXNG\n(приватный поиск)"]
  end

  subgraph External["Egress и внешние API"]
    Proxy["Privoxy :8118\n(AmneziaWG / Xray)\nHTTPS_PROXY / WSS_PROXY"]
    LLM["OpenAI / Anthropic / Google"]
    RT["OpenAI Realtime\ngpt-realtime-2.1 (мимо LiteLLM!)"]
    LF["Lemonfox STT API"]
    Web["DuckDuckGo / Web"]
  end

  OneCChat <--> OneCExt
  OneCExt <-->|"чтение / разрешённые изменения"| OneCDB
  OneCExt <-->|"HTTPS: запрос, данные, результат"| OneCBroker
  OneCBroker -->|"активация / проверка лицензии"| OneCLic
  OneCBroker <-->|"API портала: POST /api/chat/completions"| Traefik
  Core -.->|"ветка Tool (требует сверки)"| E1CTool -.->|"HTTPS"| OneCBroker

  Traefik --> Core
  Traefik --> Audio
  Shim --> P2
  Core --> P1 --> LiteLLM
  LiteLLM -->|"остаток / расходы"| EBud --> P3
  Core --> ESkl
  Core --> EOff --> OfficeCLI
  EOff --> Terminal
  Core --> EOCR --> LiteLLM
  P2 --> EMed --> STT -->|"HTTPS"| Proxy
  Audio -->|"HTTPS / WSS"| Proxy
  LiteLLM -->|"HTTPS"| Proxy
  Proxy --> LLM
  Proxy --> RT
  Proxy --> LF
  Core --> SearXNG -->|"прямой выход"| Web
```

## 6 ключевых потоков данных (воркфлоу)

| Воркфлоу | Как идут данные | Ключевые файлы / ссылки |
| --- | --- | --- |
| **1. Чат + Бюджеты** | `Пользователь → Traefik → OpenWebUI [tool-context] → LiteLLM (auth + floor.patch) → Privoxy (AmneziaWG/Xray) → LLM → Cost Filter.outlet (читает остаток из LiteLLM) → [status-position] → строка «Ответ · Чат · Остаток»` | [`deploy/openwebui-budgets/`](../deploy/openwebui-budgets), [`compose/openwebui.employee-budgets.compose.yml`](../compose/openwebui.employee-budgets.compose.yml), [`docs/infra-ops/employee-budgets-goal584.md`](infra-ops/employee-budgets-goal584.md) |
| **2. Офис и корп-шаблоны** | `Запрос + файл → Skills (artifact-workflow / corporate-template) + Knowledge → LiteLLM → Privoxy → LLM → officecli_auto_attach_filter → OfficeCLI (DOCX/XLSX/PPTX) или Open Terminal (terminal_file_transfer) → готовый файл вложением` | [`services/officecli-openapi-proof/`](../services/officecli-openapi-proof), [`deploy/openwebui-tools/`](../deploy/openwebui-tools), [`docs/infra-ops/officecli-openapi-docx-release.md`](infra-ops/officecli-openapi-docx-release.md) |
| **3. PDF OCR (Luna)** | `Загрузка PDF → OpenWebUI Files → External Document Extraction → Event Function luna_pdf_ocr (/process) → native Responses (gpt-6-luna) через LiteLLM и Privoxy → текст в штатный File/RAG кэш` | [`deploy/openwebui-functions/luna_pdf_ocr.py`](../deploy/openwebui-functions/luna_pdf_ocr.py), [`docs/infra-ops/luna-ocr.md`](infra-ops/luna-ocr.md) |
| **4. Голос и аудио (3 пути, все через Privoxy)** | **A (Файлы):** `media-upload → stage2_media_intake → stage2-stt → Privoxy → Lemonfox`. **B (Микрофон / TTS):** `Audio → Privoxy → Lemonfox / OpenAI tts-1` (мимо sidecar). **C (Realtime):** `Voice Mode WS → Privoxy (WSS_PROXY) → OpenAI gpt-realtime-2.1` *(мимо LiteLLM-бюджетов!)* | [`services/stage2-stt/`](../services/stage2-stt), [`docs/infra-ops/microphone-stt.md`](infra-ops/microphone-stt.md), [`docs/infra-ops/realtime-voice.md`](infra-ops/realtime-voice.md) |
| **5. Веб-поиск** | `Чат / Realtime handoff → native web_search (по умолчанию на 14 моделях) → приватный SearXNG (+ Valkey) → прямой выход в DuckDuckGo → контекст модели` *(дозагрузка страниц `fetch_url` идёт из OpenWebUI через Privoxy)* | [`compose/searxng.private.compose.yml`](../compose/searxng.private.compose.yml), [`docs/infra-ops/web-search-defaults.md`](infra-ops/web-search-defaults.md) |
| **6. 1С: «Нейро-помощник» (внешний контур · пилот)** | **Основной путь (чат внутри 1С):** `Пользователь 1С → HTML-чат → Расширение НейроИнтеграция ↔ HTTPS ↔ Сервер-посредник (лицензии и рабочие места) ↔ API портала (POST /api/chat/completions) ↔ Traefik → OpenWebUI → LiteLLM (общий бюджет владельца токена лицензии) → Privoxy → LLM`. Обмен циклический: модель запрашивает метаданные/данные, расширение исполняет разрешённые операции в БД 1С (создание и проведение — только после подтверждения пользователя). **Отдельная ветка:** `OpenWebUI Tool → посредник → исполнитель в 1С` *(пилот / требует сверки актуального Tool; веб-публикация без сеанса — в планах)*. | [Документация пилота интеграции 1С (внешняя справка)](https://github.com/Severus56/alfinator-demo/blob/main/docs/1c-integration.md), [`docs/commercial/COMPLETED_WORK_2026-11-12_EMPLOYEE_BUDGETS.md`](commercial/COMPLETED_WORK_2026-11-12_EMPLOYEE_BUDGETS.md), [`docs/commercial/planning/DATA_ANONYMIZATION_CUSTOMER_PROPOSAL_2026-11-21.md`](commercial/planning/DATA_ANONYMIZATION_CUSTOMER_PROPOSAL_2026-11-21.md) |

### Границы внешнего контура 1С

- **Без патчей ядра и без прямого SQL:** посредник ходит в OpenWebUI по API (`POST /api/chat/completions`, создание контекста чата — `/api/v1/chats/new`); чтение и изменение данных исполняет расширение `НейроИнтеграция` в контуре 1С с правами пользователя 1С.
- **Лицензии ≠ бюджеты LiteLLM:** один пользователь 1С = одно рабочее место (проверяется серверным кодом посредника), а на одну лицензию используется один API-токен портала (= общий плательщик в LiteLLM, не персональные бюджеты сотрудников 1С). Сквозная бюджетная приёмка реального клиента 1С не проводилась; маршрут 1С вынесен за рамки первого контура обезличивания.
- **Статус конфигураций (на 27.11.2026):** УНФ — работающий пилот на внутреннем локальном тестовом стенде (не полная совместимость со всеми версиями); БП и УТ — отдельные удалённые испытания без текущей сквозной приёмки конкретных баз; ветка `OpenWebUI Tool → 1С` требует проверки актуального Tool; доступ к веб-публикации 1С через служебного пользователя без открытого сеанса — планируемый вариант.

## Зона апгрейда (все патчи ядра)

Полные условия снятия и хэши ведутся в [`docs/infra-ops/patch-registry.md`](infra-ops/patch-registry.md).

1. **OpenWebUI `tool-context-v0.12.2`** (3 backend-файла) — reasoning/картинки из tool-results и проекция длинных call/result ID (>64 символов).
2. **OpenWebUI `media-upload-v0.12.2`** (2 backend + 2 frontend-файла) — лимит вложений на сообщение и same-ID media handoff в UI.
3. **OpenWebUI `status-position-v0.12.2`** (1 Svelte-файл) — позиция статуса `after_content` под ответом.
4. **OpenWebUI `provider-context-v0.12.2`** (1 router seam, выключен по умолчанию) — операторская запись финального JSON-запроса к провайдеру.
5. **LiteLLM `positive-floor-v1.105.1`** (`floor.patch`) — защита месячного сброса счётчика от старого cached DB floor.

## Что на хосте и что заморожено

- **Хост:** `Flight Recorder` (`deploy/openwebui-flight-recorder/`, systemd-самописец 5 контейнеров), `AmneziaWG + Privoxy` (`deploy/transport/`), CI `active-ci` (`.github/workflows/active-ci.yml`).
- **Не в проде (отдельные контуры в репе):** `services/broker-reports-gate1-proof/` (замороженный контур Broker Reports / НДФЛ / XML, ручной `broker-reports-ci.yml`) и `deploy/hermes-corporate-v1/` (отдельный задел).

## Контракт актуализации карты

Карта поддерживается в актуальном состоянии как часть PR (см. также корневой [`AGENTS.md`](../AGENTS.md)).

### Когда обновлять
- **Обязательно:** добавлен/снят патч ядра (`deploy/openwebui-patches/`, `deploy/litellm-patches/`), добавлен/удалён Docker-сервис (`compose/`, `services/`), добавлена/перенесена точка расширения OpenWebUI (`deploy/openwebui-*`), либо изменился маршрут данных (воркфлоу, egress/прокси, внешний контур интеграции, контур биллинга).
- **Не обновлять:** обычные багфиксы, тесты, внутренние рефакторинги без смены границ, коммерческие предложения и разовые отчёты.

### Чек-лист для кодового агента
1. В [`docs/architecture-map.html`](architecture-map.html) обновить три места согласованно:
   - DOM-карточку узла (`id="node-<id>"`, `data-id="<id>"`, категория `cat-core` / `cat-patch` / `cat-ext` / `cat-svc` / `cat-infra` / `cat-1c` / `cat-frozen`);
   - описание узла в объекте `NODES` (реальные относительные пути в `paths` для файлов внутри `corp-openweb-ui`; для внешних контуров — `paths: []` и внешние ссылки в `externalRefs`);
   - затронутые маршруты в `WORKFLOWS` (и вкладку `patches`, если менялась зона апгрейда).
2. Синхронизировать Mermaid-схему, таблицу потоков и список патчей в [`docs/ARCHITECTURE_MAP.md`](ARCHITECTURE_MAP.md).
3. Проверить перед коммитом, что:
   - все пути в `NODES.*.paths` реально существуют в репозитории (для внешних узлов `paths` пуст, а ссылки вынесены в `externalRefs`, без секретов, внутренних доменов и приватных админ-роутов);
   - все `from`/`to` в `WORKFLOWS` соответствуют существующим `id="node-..."`;
   - `<script>` в `docs/architecture-map.html` не содержит синтаксических ошибок JS.
4. После слияния PR в `main` workflow [`.github/workflows/pages-architecture-map.yml`](../.github/workflows/pages-architecture-map.yml) автоматически перепубликует `docs/architecture-map.html` на GitHub Pages.
