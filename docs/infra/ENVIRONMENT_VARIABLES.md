# Environment Variables

## Files

- `.env.example` коммитится.
- `.env` создается на сервере и не коммитится.

## Required variables

- `OPENWEBUI_HOST` - домен без схемы, для PRD-0 `gpt.alpha-soft.ru`.
- `LETSENCRYPT_EMAIL` - email для Let's Encrypt.
- `OPENAI_API_BASE_URL` - URL OpenAI-compatible API, например `https://api.openai.com/v1`.
- `OPENAI_API_KEY` - server-local API key.
- `WEBUI_SECRET_KEY` - стабильный секрет для JWT и шифрования чувствительных данных. Генерировать один раз: `openssl rand -hex 32`.
- `CORS_ALLOW_ORIGIN` - разрешенный browser/WebSocket origin, для PRD-0 `https://gpt.alpha-soft.ru`.
- `WEBUI_ADMIN_EMAIL` - email первого администратора.
- `WEBUI_ADMIN_PASSWORD` - первичный пароль администратора. Работает для auto-bootstrap только на свежей базе при отсутствии пользователей.

## Optional variables

- `OPENWEBUI_IMAGE` - image OpenWebUI.
- `TRAEFIK_IMAGE` - image Traefik.
- `DEFAULT_MODELS` - модель по умолчанию, если требуется зафиксировать ее через env.
- `ENABLE_SIGNUP` - для PRD-0 должно быть `false` после создания admin.
- `DEFAULT_USER_ROLE` - рекомендуется `pending`.

## OpenWebUI notes

Часть переменных OpenWebUI относится к persistent config: после первого запуска значения могут сохраниться во внутренней базе и не всегда меняться простой правкой `.env`. Если настройка не меняется после restart, проверить Admin UI.

`DEFAULT_MODELS` является optional и по документации имеет пустое значение по умолчанию. Заполнять его только после выбора точного model id.

`WEBUI_SECRET_KEY` рекомендуется явно задавать даже для single-instance deployment, чтобы пересоздание контейнера не сбрасывало сессии и не ломало расшифровку чувствительных данных.

`CORS_ALLOW_ORIGIN` по умолчанию равен `*`; для публичного домена PRD-0 он должен быть ограничен доменом OpenWebUI.

`WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` поддерживаются OpenWebUI для headless/container bootstrap. Условие: база свежая, пользователей еще нет, обе переменные заданы.

## Provider options

Выбор провайдера остается operator decision до заполнения `.env`.

| Provider | `OPENAI_API_BASE_URL` | Example `DEFAULT_MODELS` | Notes |
| --- | --- | --- | --- |
| OpenAI-compatible default | `https://api.openai.com/v1` | operator-selected model id | Подходит, если используется OpenAI API key или совместимый провайдер с таким же endpoint contract. |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` | Официальный Gemini OpenAI compatibility endpoint; проверить тарифы, региональную доступность и quota до пилота. |

Reference: https://docs.openwebui.com/reference/env-configuration
Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai

## Security

Никогда не коммитить `.env`, API-ключи, пароли, private keys, OAuth secrets и токены.
