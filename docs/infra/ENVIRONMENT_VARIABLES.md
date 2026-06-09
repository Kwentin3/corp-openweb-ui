# Environment Variables

## Files

- `.env.example` коммитится.
- `.env` создается на сервере и не коммитится.

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

## Provider env contract

PRD-0 использует `.env` только для primary provider. Для текущего deployment decision primary provider - OpenAI, secondary provider - Gemini.

Secondary provider добавляется вручную через OpenWebUI Admin UI по [../ops/PROVIDER_SETUP_RUNBOOK.md](../ops/PROVIDER_SETUP_RUNBOOK.md).

Это не означает, что Gemini не выбран. Выбраны оба provider; Admin UI - это только место, где вводится second provider connection и его API key.

Причина: OpenWebUI поддерживает несколько OpenAI-compatible connections через Admin UI. В env reference также есть multi-value переменные `OPENAI_API_BASE_URLS` и `OPENAI_API_KEYS`, но для PRD-0 они не используются в skeleton, потому что:

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

OpenWebUI supports proxy configuration through standard environment variables `http_proxy`, `https_proxy` and `no_proxy`.

В PRD-0 repo-level variable `OPENWEBUI_OUTBOUND_PROXY` прокидывается в контейнер OpenWebUI как:

- `http_proxy`;
- `https_proxy`;
- `HTTP_PROXY`;
- `HTTPS_PROXY`.

`OPENWEBUI_NO_PROXY` прокидывается как `no_proxy` и `NO_PROXY`.

OpenWebUI OpenAI route uses `aiohttp` with `trust_env=True`; this path expects an HTTP proxy in `http_proxy`/`https_proxy`. Direct `socks5h://` in `OPENWEBUI_OUTBOUND_PROXY` is not supported for this path.

Для SOCKS5 использовать local HTTP-to-SOCKS bridge, for example host-local Privoxy on the Docker bridge gateway:

```env
OPENWEBUI_OUTBOUND_PROXY=http://172.18.0.1:8118
OPENWEBUI_SOCKS5_UPSTREAM=socks5h://user:password@proxy-host:1080
OPENWEBUI_NO_PROXY=localhost,127.0.0.1,::1,openwebui,traefik,openwebui-traefik,gpt.alpha-soft.ru
```

Bridge listener не должен быть public. При UFW `deny incoming` нужен точечный allow только от Docker subnet к Docker gateway port bridge, например `172.18.0.0/16 -> 172.18.0.1:8118/tcp`. Не открывать `8118/tcp` для `Anywhere`.

Реальные proxy credentials не коммитить. Если proxy credentials были переданы через чат или ticket, считать их раскрытыми и заменить после стабилизации пилота.

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
