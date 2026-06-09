# Environment Variables

## Files

- `.env.example` коммитится.
- `.env` создается на сервере и не коммитится.

## Required variables

- `OPENWEBUI_HOST` - домен без схемы, для PRD-0 `gpt.alpha-soft.ru`.
- `LETSENCRYPT_EMAIL` - email для Let's Encrypt.
- `OPENAI_API_BASE_URL` - URL OpenAI-compatible API, например `https://api.openai.com/v1`.
- `OPENAI_API_KEY` - server-local API key.
- `WEBUI_ADMIN_EMAIL` - email первого администратора.
- `WEBUI_ADMIN_PASSWORD` - первичный пароль администратора.

## Optional variables

- `OPENWEBUI_IMAGE` - image OpenWebUI.
- `TRAEFIK_IMAGE` - image Traefik.
- `DEFAULT_MODELS` - модель по умолчанию, если требуется зафиксировать ее через env.
- `ENABLE_SIGNUP` - для PRD-0 должно быть `false` после создания admin.
- `DEFAULT_USER_ROLE` - рекомендуется `pending`.

## OpenWebUI notes

Часть переменных OpenWebUI относится к persistent config: после первого запуска значения могут сохраниться во внутренней базе и не всегда меняться простой правкой `.env`. Если настройка не меняется после restart, проверить Admin UI.

Reference: https://docs.openwebui.com/reference/env-configuration

## Security

Никогда не коммитить `.env`, API-ключи, пароли, private keys, OAuth secrets и токены.
