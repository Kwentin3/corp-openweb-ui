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
- читает OpenAI-compatible provider config из `.env`.

## Named volumes

Используются явные имена:

- `openwebui_data`;
- `traefik_letsencrypt`.

Это упрощает backup/restore и снижает риск случайного project-prefix mismatch.

## First launch

На первом запуске нужно задать:

- `OPENWEBUI_HOST=gpt.alpha-soft.ru`;
- `LETSENCRYPT_EMAIL`;
- `OPENAI_API_BASE_URL`;
- `OPENAI_API_KEY`;
- `WEBUI_SECRET_KEY`;
- `CORS_ALLOW_ORIGIN`;
- `WEBUI_ADMIN_EMAIL`;
- `WEBUI_ADMIN_PASSWORD`.

Реальные значения хранятся только в server-local `.env`.

`WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` создают admin только при fresh install, когда в базе еще нет пользователей. Если база уже содержит пользователей, администратор управляется через UI или recovery-процедуру OpenWebUI.
