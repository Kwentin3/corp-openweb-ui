# Environment Variables

## Files

- `.env.example` коммитится.
- `.env` создается на сервере и не коммитится.

## Required variables

- `OPENWEBUI_HOST` - домен без схемы, для PRD-0 `gpt.alpha-soft.ru`.
- `LETSENCRYPT_EMAIL` - email для Let's Encrypt.
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

## Provider env contract

PRD-0 использует `.env` только для primary provider.

Secondary provider добавляется вручную через OpenWebUI Admin UI по [../ops/PROVIDER_SETUP_RUNBOOK.md](../ops/PROVIDER_SETUP_RUNBOOK.md).

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

## Provider endpoints

| Provider | Base URL for OpenWebUI | API key | Model id |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | OpenAI API key с доступом к выбранной модели | Operator-selected exact model id |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai` | Gemini API key с включенным billing/quota/region | Operator-selected exact Gemini model id |

Для Gemini в этом репозитории используется endpoint без trailing slash. Google SDK examples показывают тот же path со slash в конце, но OpenWebUI connection URL должен быть единым нормализованным значением, чтобы UI мог добавлять `/models` и chat paths без неоднозначности.

## OpenWebUI notes

Часть переменных OpenWebUI относится к persistent config: после первого запуска значения могут сохраниться во внутренней базе и не всегда меняться простой правкой `.env`. Если настройка не меняется после restart, проверить Admin UI.

`DEFAULT_MODELS` является optional и по документации имеет пустое значение по умолчанию. Заполнять его только после выбора точного model id.

`WEBUI_SECRET_KEY` рекомендуется явно задавать даже для single-instance deployment, чтобы пересоздание контейнера не сбрасывало сессии и не ломало расшифровку чувствительных данных.

`CORS_ALLOW_ORIGIN` по умолчанию равен `*`; для публичного домена PRD-0 он должен быть ограничен доменом OpenWebUI.

`WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` поддерживаются OpenWebUI для headless/container bootstrap. Условие: база свежая, пользователей еще нет, обе переменные заданы.

`WEBUI_BANNERS` относится к ConfigVar/persistent configuration. Если баннер не появился после restart, проверить Admin UI -> Settings -> General -> Banners.

## Security

Никогда не коммитить `.env`, API-ключи, пароли, private keys, OAuth secrets и токены.

## Sources

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI customizable banners: https://docs.openwebui.com/features/administration/banners/
- OpenWebUI OpenAI-compatible connections: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenAI API reference: https://platform.openai.com/docs/api-reference/chat/create
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
