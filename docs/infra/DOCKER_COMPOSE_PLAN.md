# Docker Compose Plan

## Compose file

Основной файл:

```text
compose/openwebui.compose.yml
```

Optional Stage 2 Web Search overlays:

```text
compose/searxng.private.compose.yml
compose/searxng.debug.compose.yml
```

Запуск:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Private SearXNG candidate запуск:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d
```

Requires Docker Compose v2 or a compatible `docker-compose` binary on a
Linux-container Docker host. The local Codex Windows Docker context used during
planning did not provide Compose and reported `Server OS=windows`, so SearXNG
runtime smoke must run on stage/server or a Linux-container Docker host.

Stage runtime update 2026-06-23: private SearXNG smoke passed on the stage
Linux Docker host in native OpenWebUI snippet/bypass mode. After operator
selection of WebGUI provider `searxng`, `searxng` and `searxng-valkey` are
treated as always-on internal runtime dependencies.

Local-only SearXNG debug exposure:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml \
  -f compose/searxng.debug.compose.yml up -d searxng
```

`searxng.debug.compose.yml` binds SearXNG to `127.0.0.1` by default. Do not use
it for public exposure.

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

`searxng` optional:

- image задается через `SEARXNG_IMAGE`;
- default discovery tag is `docker.io/searxng/searxng:latest`;
- production-like rollout must pin a reviewed SearXNG tag;
- restart policy is `unless-stopped`;
- keep running whenever OpenWebUI Admin UI selects Web Search engine
  `searxng`;
- no public port by default;
- internal URL for OpenWebUI: `http://searxng:8080/search?q=<query>`;
- config: `deploy/searxng/settings.yml`;
- limiter config: `deploy/searxng/limiter.toml`.

`searxng-valkey` optional:

- image задается через `SEARXNG_VALKEY_IMAGE`;
- default tag `docker.io/valkey/valkey:8-alpine`;
- restart policy is `unless-stopped`;
- keep running whenever OpenWebUI Admin UI selects Web Search engine
  `searxng`;
- supports SearXNG limiter/bot-protection;
- no public port.

## Named volumes

Используются явные имена:

- `openwebui_data`;
- `traefik_letsencrypt`.
- optional `searxng_cache`;
- optional `searxng_valkey`.

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

## Web Search / SearXNG note

Private SearXNG is a Stage 2 Web Search candidate, not PRD-0 scope and not the
primary paid provider path. It is enabled only when the optional SearXNG compose
overlay is included.

OpenWebUI WebGUI value for the SearXNG request URL:

```text
http://searxng:8080/search?q=<query>
```

If WebGUI provider is `searxng`, both optional containers must be running.
Check through SSH:

```bash
ssh <stage-target>
cd <openwebui-deploy-dir>
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml ps openwebui searxng searxng-valkey
```

If `searxng` or `searxng-valkey` is stopped, recover with:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d searxng searxng-valkey
```

SearXNG is private only as an instance boundary. Upstream engines may still
receive minimized queries. Public SearXNG instances must not be used for
corporate acceptance.

Runtime notes from the successful smoke:

- `deploy/searxng/limiter.toml` needs the private Docker passlist and
  `link_token=false` for this stage topology.
- OpenWebUI must run with `NO_PROXY` entries for `searxng`,
  `searxng:8080` and `searxng-valkey`.
- If the OpenWebUI container was started before those env values existed,
  recreate it with the private overlay before testing SearXNG.
- The private overlay did not publish SearXNG or Valkey host ports; the debug
  overlay was not enabled.
