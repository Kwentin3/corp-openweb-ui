# Docker Compose Plan

## Compose file

Основной файл:

```text
compose/openwebui.compose.yml
```

Запуск:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

## Services

`traefik`:

- image задается через `TRAEFIK_IMAGE`;
- default tag pinned to `traefik:v3.6`;
- публикует `80:80` и `443:443`;
- читает Docker labels;
- хранит ACME в `traefik_letsencrypt`.

`openwebui`:

- image задается через `OPENWEBUI_IMAGE`;
- default tag pinned to `ghcr.io/open-webui/open-webui:v0.9.6`;
- принимает трафик только от Traefik;
- хранит данные в `openwebui_data`;
- получает `WEBUI_NAME` и `WEBUI_BANNERS` из `.env` для штатной low-cost customization;
- читает primary OpenAI-compatible provider config из `.env`;
- secondary provider получает через OpenWebUI Admin UI и persistent config.

## Named volumes

Используются явные имена:

- `openwebui_data`;
- `traefik_letsencrypt`.

Это упрощает backup/restore и снижает риск случайного project-prefix mismatch.

`openwebui_data` может содержать provider connection secrets, если secondary provider добавлен через Admin UI. Backup этого volume хранить как секретный.

## First launch

На первом запуске нужно задать:

- `OPENWEBUI_HOST=gpt.alpha-soft.ru`;
- `LETSENCRYPT_EMAIL`;
- `OPENAI_API_BASE_URL`;
- `OPENAI_API_KEY`;
- `WEBUI_NAME`;
- `WEBUI_BANNERS`;
- `WEBUI_SECRET_KEY`;
- `CORS_ALLOW_ORIGIN`;
- `WEBUI_ADMIN_EMAIL`;
- `WEBUI_ADMIN_PASSWORD`.

Реальные значения хранятся только в server-local `.env`.

`WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` создают admin только при fresh install, когда в базе еще нет пользователей. Если база уже содержит пользователей, администратор управляется через UI или recovery-процедуру OpenWebUI.

`WEBUI_BANNERS` должен быть одной JSON-строкой в `.env` с экранированными кавычками. Проверять формат:

```bash
docker compose --env-file .env.example -f compose/openwebui.compose.yml config
```

В compose намеренно не используется `env_file`: все runtime-переменные передаются явно через `environment`, чтобы `config` мог проверять `.env.example` без server-local `.env`.

## Provider note

Compose intentionally does not define `OPENAI_API_BASE_URLS` or `OPENAI_API_KEYS`. PRD-0 uses a single primary provider through `.env`; the secondary OpenAI/Gemini connection is configured in Admin UI.
