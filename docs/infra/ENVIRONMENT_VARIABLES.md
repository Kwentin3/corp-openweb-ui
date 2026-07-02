# Environment Variables

## Files

- `.env.example` коммитится.
- `.env` создается на сервере и не коммитится.
- Для PRD-0 серверный `.env` является источником правды; локальный workspace
  `.env` можно синхронизировать с сервера только как ignored runtime copy.

## Required variables

- `OPENWEBUI_HOST` - домен без схемы, для PRD-0 `gpt.alpha-soft.ru`.
- `LETSENCRYPT_EMAIL` - email для Let's Encrypt; для текущего PRD-0 operator value: `kwentin3@mail.ru`.
- `WEBUI_NAME` - мягкое имя инстанса, для PRD-0 `Alpha Soft AI Chat`.
- `WEBUI_BANNERS` - JSON array предупреждающих баннеров OpenWebUI.
- `OPENAI_API_BASE_URL` - URL primary OpenAI-compatible API.
- `OPENAI_API_KEY` - server-local API key для primary provider.
- `WEBUI_SECRET_KEY` - стабильный секрет для JWT и шифрования чувствительных данных. Генерировать один раз: `openssl rand -hex 32`.
- `CORS_ALLOW_ORIGIN` - разрешенный browser/WebSocket origin, для PRD-0 `https://gpt.alpha-soft.ru`.
- `WEBUI_ADMIN_EMAIL` - email первого администратора.
- `WEBUI_ADMIN_PASSWORD` - первичный пароль администратора. Работает для auto-bootstrap только на свежей базе при отсутствии пользователей.

## Optional variables

- `OPENWEBUI_IMAGE` - image OpenWebUI.
- `TRAEFIK_IMAGE` - image Traefik.
- `DEFAULT_MODELS` - primary model id, если оператор решил зафиксировать его через env.
- `ENABLE_SIGNUP` - для PRD-0 должно быть `false` после создания admin.
- `DEFAULT_USER_ROLE` - рекомендуется `pending`.
- `OPENWEBUI_OUTBOUND_PROXY` - optional HTTP proxy URI для provider egress, например `http://172.18.0.1:8118`.
- `OPENWEBUI_SOCKS5_UPSTREAM` - optional SOCKS5 upstream URI для local HTTP-to-SOCKS bridge; не прокидывается напрямую в OpenWebUI.
- `OPENWEBUI_NO_PROXY` - hosts/IPs, которые не должны ходить через outbound proxy.
- `BACKUP_DIR` - server-local directory для backup artifacts; default `/opt/backups/openwebui-prd0`.
- `BACKUP_RETENTION_DAYS` - сколько дней хранить backup-файлы, созданные `scripts/backup.sh`; pilot choices: `1`, `7`, `30`, default `7`.
- `STAGE2_STT_INTERNAL_API_KEY` - server-local token for OpenWebUI Action to
  call Stage 2 STT sidecar job routes. Never expose in browser or commit.
- `STAGE2_STT_ALLOW_STUB_TRANSCRIPT` - explicit probe/test flag for sidecar
  integration without a live STT provider. Keep `false` for live transcription.
- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS` - enables LemonFox diarization.
  Current Stage 2 STT v2 PRD-0 runtime has `true`.
- `STAGE2_STT_ARTIFACT_STORE_MODE` - internal STT v2 artifact store mode.
  Current server-local value is `sqlite`.
- `STAGE2_STT_ARTIFACT_STORE_PATH` - internal SQLite path mounted inside the
  `stage2-stt` container; current contract uses
  `/data/stage2-stt/artifacts.sqlite3`.
- `STAGE2_STT_ARTIFACT_PAYLOAD_DIR` - internal payload directory for future
  oversized internal payloads; current contract uses
  `/data/stage2-stt/artifact-payloads`.
- `STAGE2_STT_TRANSCRIPT_TTL_DAYS`, `STAGE2_STT_TRANSFORMATION_TTL_DAYS`,
  `STAGE2_STT_PREPARED_AUDIO_TTL_HOURS` - STT v2 retention knobs.
- `STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED` - must stay `false` for
  Gate 1-2 product paths; raw provider payload is not product storage.
- `STAGE2_STT_PROMPT_CATALOG_MODE` - STT v2 post-processing prompt catalog
  mode. Current MVP uses `openwebui_sqlite` with a read-only OpenWebUI data
  volume mount.
- `STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH` - sidecar-local read-only path to
  OpenWebUI `webui.db`, currently `/openwebui-data/webui.db`.
- `STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE` - post-processing executor mode.
  Keep `disabled` until Gate 4 runtime proof enables `openai_compatible`.
- `STAGE2_STT_POSTPROCESSING_OPENAI_MODEL` and
  `STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS` - Gate 4 post-processing
  model and explicit single-pass transcript threshold.
- `SEARXNG_SECRET` - server-local SearXNG secret used only when the optional
  private SearXNG overlay is enabled. Generate a real value in `.env`; do not
  commit it.

## Provider env contract

PRD-0 использует `.env` только для primary provider. Для текущего deployment decision primary provider - OpenAI, secondary provider - Gemini.

Secondary provider добавляется вручную через OpenWebUI Admin UI по [../ops/PROVIDER_SETUP_RUNBOOK.md](../ops/PROVIDER_SETUP_RUNBOOK.md).

Это не означает, что Gemini не выбран. Выбраны оба provider; Admin UI - это только место, где вводится second provider connection и его API key.

Причина: OpenWebUI поддерживает несколько OpenAI-compatible connections через Admin UI. В env reference также есть multi-value переменные `OPENAI_API_BASE_URLS` и `OPENAI_API_KEYS`, но для PRD-0 они не используются в deployment path, потому что:

- порядок URL/key становится частью скрытого контракта;
- ошибки в одном значении сложнее диагностировать;
- часть OpenWebUI настроек является persistent config и может сохраняться во внутренней базе после первого запуска;
- PRD-0 не требует маршрутизации, бюджетов или per-user лимитов.

## Low-cost customization

PRD-0 допускает только штатную и обратимую кастомизацию OpenWebUI через env/Admin UI:

- мягкое имя инстанса;
- предупреждающий баннер;
- закрытая регистрация;
- базовые настройки доступа.

Это не white-label, не смена логотипа и не изменение frontend-кода.

`WEBUI_NAME` является штатной переменной OpenWebUI. Значение PRD-0:

```env
WEBUI_NAME="Alpha Soft AI Chat"
```

OpenWebUI documentation указывает, что при override основного имени приложение добавляет `(Open WebUI)`. Это ожидаемо и не должно обходиться форком.

`WEBUI_BANNERS` является штатной переменной OpenWebUI для списка баннеров. Для `.env` использовать одну строку с экранированными кавычками:

```env
WEBUI_BANNERS="[{\"id\":\"prd0-policy-warning-v1\",\"type\":\"warning\",\"title\":\"Тестовый корпоративный AI-чат\",\"content\":\"Не отправляйте пароли, токены, API-ключи, приватные SSH-ключи и закрытые персональные данные. Ответы модели нужно проверять.\",\"dismissible\":true,\"timestamp\":1780963200}]"
```

Формат баннера:

- `id`: stable/versioned id для dismiss state;
- `type`: `warning`;
- `title`: `Тестовый корпоративный AI-чат`;
- `content`: короткое HTML/text сообщение;
- `dismissible`: `true`;
- `timestamp`: required integer, frontend не использует его для расписания показа.

Если после первого запуска OpenWebUI persistent config перекрывает env, исправлять `WEBUI_NAME` или banners через Admin UI. Не делать fork и не патчить OpenWebUI.

## Outbound proxy

OpenWebUI and `stage2-stt` support proxy configuration through standard environment variables `http_proxy`, `https_proxy` and `no_proxy`.

В PRD-0 repo-level variable `OPENWEBUI_OUTBOUND_PROXY` прокидывается в контейнеры OpenWebUI and `stage2-stt` как:

- `http_proxy`;
- `https_proxy`;
- `HTTP_PROXY`;
- `HTTPS_PROXY`.

`OPENWEBUI_NO_PROXY` прокидывается как `no_proxy` и `NO_PROXY`.

OpenWebUI OpenAI route uses `aiohttp` with `trust_env=True`; the STT v2 post-processing executor uses `httpx` with standard proxy environment handling. Both paths expect an HTTP proxy in `http_proxy`/`https_proxy`. Direct `socks5h://` in `OPENWEBUI_OUTBOUND_PROXY` is not supported for these paths.

Для SOCKS5 использовать local HTTP-to-SOCKS bridge, for example host-local Privoxy on the Docker bridge gateway:

```env
OPENWEBUI_OUTBOUND_PROXY=http://172.18.0.1:8118
OPENWEBUI_SOCKS5_UPSTREAM=socks5h://user:password@proxy-host:1080
OPENWEBUI_NO_PROXY=localhost,127.0.0.1,::1,openwebui,traefik,openwebui-traefik,stage2-stt,stage2-stt:8080,searxng,searxng:8080,searxng-valkey,gpt.alpha-soft.ru
```

Bridge listener не должен быть public. При UFW `deny incoming` нужен точечный allow только от Docker subnet к Docker gateway port bridge, например `172.18.0.0/16 -> 172.18.0.1:8118/tcp`. Не открывать `8118/tcp` для `Anywhere`.

Реальные proxy credentials не коммитить. Если proxy credentials были переданы через чат или ticket, считать их раскрытыми и заменить после стабилизации пилота.

When the private SearXNG overlay is enabled, `OPENWEBUI_NO_PROXY` must include
`searxng`, `searxng:8080` and `searxng-valkey`; otherwise OpenWebUI may try to
reach the internal SearXNG service through the outbound proxy.

If OpenWebUI was already running before these no-proxy entries were added,
restart/recreate the container through the native compose overlay. The
2026-06-23 SearXNG smoke showed that the old container without these entries
could route `http://searxng:8080` through the outbound proxy and fail.

## Stage 2 Web Search / Brave runtime baseline

Current working Brave smoke baseline on the deployed OpenWebUI instance:

```env
ENABLE_WEB_SEARCH=true
WEB_SEARCH_ENGINE=brave_llm_context
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
WEB_LOADER_CONCURRENT_REQUESTS=2
WEB_SEARCH_TRUST_ENV=true
BYPASS_WEB_SEARCH_WEB_LOADER=true
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true
BRAVE_SEARCH_API_KEY=<server-local-or-admin-ui-only>
BRAVE_SEARCH_CONTEXT_TOKENS=8192
```

Notes:

- Do not commit a real `BRAVE_SEARCH_API_KEY`.
- For `brave_llm_context`, the web loader and web-search embedding/retrieval
  bypasses are intentional. Brave already returns LLM-oriented passages.
- The vectorized `web-search-*` retrieval path is a known issue until it is
  separately fixed and proven. Keep it deferred unless long page loading,
  classic `brave`, SearXNG page loading, or full RAG over fetched content is in
  scope.
- Code Interpreter should not be enabled by default for the selected Web Search
  smoke model; otherwise the model may choose browser Pyodide instead of native
  Web Search context.

## Stage 2 Web Search / Yandex Search API

Yandex Search API is configured through OpenWebUI Admin UI on the deployed
instance and passed an operator/native smoke on 2026-06-23. Treat it as a
working RU-provider path, not merely a research candidate.

The local `.env` section is allowed as an operator notebook for variable names
and server-local values. Do not commit real keys. For runtime changes, prefer
OpenWebUI Admin UI when practical because OpenWebUI `ConfigVar` values may
override env after first initialization.

```env
YANDEX_WEB_SEARCH_API_KEY=<server-local-or-admin-ui-only>
YANDEX_WEB_SEARCH_URL=https://searchapi.api.cloud.yandex.net/v2/web/search
YANDEX_WEB_SEARCH_CONFIG=
```

Notes:

- Do not commit a real `YANDEX_WEB_SEARCH_API_KEY`.
- Prefer OpenWebUI Admin UI for operator-managed runtime keys when practical.
- Keep broad rollout gated by allowed data classes, query minimization,
  metadata-forwarding review and cost-mode acceptance.
- Do not enable generative/expensive Yandex search modes unless separately
  approved.

## Stage 2 Web Search / Private SearXNG

These variables are used only with
`compose/searxng.private.compose.yml`:

```env
SEARXNG_IMAGE=docker.io/searxng/searxng:latest
SEARXNG_VALKEY_IMAGE=docker.io/valkey/valkey:8-alpine
SEARXNG_SECRET=replace-with-random-strong-searxng-secret
SEARXNG_BASE_URL=
SEARXNG_LIMITER=true
SEARXNG_PUBLIC_INSTANCE=false
SEARXNG_IMAGE_PROXY=false
SEARXNG_VALKEY_URL=valkey://searxng-valkey:6379/0
ENABLE_WEB_SEARCH=true
WEB_SEARCH_ENGINE=searxng
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
WEB_LOADER_CONCURRENT_REQUESTS=2
WEB_SEARCH_TRUST_ENV=true
BYPASS_WEB_SEARCH_WEB_LOADER=false
SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>
SEARXNG_LANGUAGE=ru
SEARXNG_DEBUG_BIND=127.0.0.1
SEARXNG_DEBUG_PORT=18080
```

Notes:

- `SEARXNG_SECRET` must be generated server-side, for example with
  `openssl rand -hex 32`.
- `SEARXNG_IMAGE=latest` is acceptable only for first discovery if owner accepts
  it; pin a reviewed tag before production-like rollout.
- `SEARXNG_DEBUG_BIND` must stay local-only unless owner/security explicitly
  approves another exposure model.
- Public SearXNG instances are not acceptable for corporate acceptance.
- Runtime smoke passed on 2026-06-23 in native OpenWebUI snippet/bypass mode.
  It did not prove full page loading or vectorized retrieval.
- OpenWebUI WebGUI SearXNG request URL must be exactly
  `http://searxng:8080/search?q=<query>` when the provider is `searxng`.
- `searxng` and `searxng-valkey` must stay running while WebGUI provider is
  `searxng`; both services use `restart: unless-stopped` in the private
  overlay.
- `deploy/searxng/limiter.toml` uses `link_token=false` plus loopback/private
  Docker CIDR passlist for the private stage topology. Keep the limiter enabled
  and do not expose SearXNG publicly.

## Provider endpoints

| Provider | Base URL for OpenWebUI | API key | Model id |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | OpenAI API key с доступом к выбранной модели | `gpt-5.4-mini` |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai` | Gemini API key с включенным billing/quota/region | `gemini-3.5-flash` |

Для Gemini в этом репозитории используется endpoint без trailing slash. Google SDK examples показывают тот же path со slash в конце, но OpenWebUI connection URL должен быть единым нормализованным значением, чтобы UI мог добавлять `/models` и chat paths без неоднозначности.

Если оператор намеренно тестирует именно Gemini 3 Flash Preview, точный model id - `gemini-3-flash-preview`. Строка `gemini-3-flash` без `preview` не используется как exact model code.

## OpenWebUI notes

Часть переменных OpenWebUI относится к persistent config: после первого запуска значения могут сохраниться во внутренней базе и не всегда меняться простой правкой `.env`. Если настройка не меняется после restart, проверить Admin UI.

`DEFAULT_MODELS` является optional и по документации имеет пустое значение по умолчанию. В текущем `.env.example` он заполнен как `gpt-5.4-mini`, потому что OpenAI выбран primary provider.

`WEBUI_SECRET_KEY` рекомендуется явно задавать даже для single-instance deployment, чтобы пересоздание контейнера не сбрасывало сессии и не ломало расшифровку чувствительных данных.

`CORS_ALLOW_ORIGIN` по умолчанию равен `*`; для публичного домена PRD-0 он должен быть ограничен доменом OpenWebUI.

`WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` поддерживаются OpenWebUI для headless/container bootstrap. Условие: база свежая, пользователей еще нет, обе переменные заданы.

`WEBUI_BANNERS` относится к ConfigVar/persistent configuration. Если баннер не появился после restart, проверить Admin UI -> Settings -> General -> Banners.

## Backup retention

`scripts/backup.sh` читает `BACKUP_DIR` и `BACKUP_RETENTION_DAYS` из environment или server-local `.env`.

Для PRD-0 не добавляется отдельный backup scheduler. Оператор запускает backup вручную или через внешний cron/systemd timer.

Retention в PRD-0 - одно число дней:

- `1` - очень короткий test retention;
- `7` - default для короткого пилота;
- `30` - около месяца.

Скрипт удаляет только свои known artifacts в `BACKUP_DIR`: `openwebui_data-*.tgz`, `traefik_letsencrypt-*.tgz`, `env-*.backup`.

## Security

Никогда не коммитить `.env`, API-ключи, пароли, private keys, OAuth secrets и токены.

## Sources

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI customizable banners: https://docs.openwebui.com/features/administration/banners/
- OpenWebUI OpenAI-compatible connections: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenAI model catalog: https://developers.openai.com/api/docs/models/gpt
- OpenAI API reference: https://platform.openai.com/docs/api-reference/chat/create
- Gemini 3.5 Flash model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
