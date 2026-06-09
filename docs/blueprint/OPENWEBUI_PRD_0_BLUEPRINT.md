# OpenWebUI PRD-0 Blueprint

## Назначение

Blueprint описывает минимальный запуск OpenWebUI для фазы смотрин PRD-0: один домен, один OpenWebUI, два LLM API-провайдера через штатные OpenWebUI connections, один администратор и 3-4 пользователя.

Цель blueprint - дать безопасную инженерную основу для развертывания, не расширяя scope до AI-платформы.

## Домены и ответственность

- Ingress: Traefik принимает HTTP/HTTPS и выпускает TLS-сертификат.
- UI/runtime: OpenWebUI обслуживает пользователей, авторизацию, историю чатов и подключения к LLM API.
- Provider config: OpenAI primary хранится в server-local `.env`; Gemini secondary добавляется через OpenWebUI Admin UI.
- Low-cost customization: `WEBUI_NAME` и `WEBUI_BANNERS` задают мягкое имя инстанса и предупреждающий баннер без fork/frontend changes.
- Persistence: Docker volume `openwebui_data` хранит данные OpenWebUI и persistent config.
- Host hardening: UFW ограничивает public perimeter, fail2ban защищает SSH.
- Secrets: server-local `.env` хранит primary API-key, `WEBUI_SECRET_KEY`, admin-пароль и email для Let's Encrypt; secondary API-key вводится в Admin UI.
- Backup: скрипт сохраняет volume и локальный `.env` в server-local backup directory; default retention `BACKUP_RETENTION_DAYS=7`.
- Pilot operations: администратор создает 3-4 пользователей и собирает обратную связь.

## Non-goals

В PRD-0 нет LiteLLM, отдельного model gateway, SSO, web-поиска, RAG, memory layer, document tools, plugins/tools/functions, fork OpenWebUI, изменения логотипа, изменения frontend-кода, корпоративного dashboard, WAF/SIEM/DLP и white-label.

## Контейнеры

Минимально нужны два контейнера:

- `traefik` - reverse proxy, HTTPS, ACME HTTP challenge.
- `openwebui` - приложение OpenWebUI.

Дополнительные runtime-компоненты не добавляются.

## Поток запроса

```text
browser
  -> https://gpt.alpha-soft.ru
  -> Traefik :443
  -> openwebui:8080
  -> OpenAI API
  -> Gemini OpenAI-compatible API
```

HTTP `:80` нужен только для редиректа на HTTPS и ACME HTTP challenge.

## Boundary contracts

- Public network: только `22/tcp`, `80/tcp`, `443/tcp`.
- Compose env: `OPENAI_API_BASE_URL`, `OPENAI_API_KEY`, `DEFAULT_MODELS` относятся только к OpenAI primary provider.
- Compose env: `WEBUI_NAME` и `WEBUI_BANNERS` относятся только к дешевой штатной кастомизации.
- OpenAI base URL: `https://api.openai.com/v1`.
- Gemini base URL for OpenWebUI connection: `https://generativelanguage.googleapis.com/v1beta/openai`.
- Model ids: OpenAI primary `gpt-5.4-mini`; Gemini secondary `gemini-3.5-flash`.
- Provider routing, budgets and per-user limits: не реализуются в PRD-0.
- White-label, logo replacement, frontend customization and plugins: не реализуются в PRD-0.

## Volumes

- `openwebui_data` -> `/app/backend/data` внутри OpenWebUI.
- `traefik_letsencrypt` -> `/letsencrypt` внутри Traefik.

## Конфигурация

- Коммитится только `.env.example`.
- Реальный `.env` создается на сервере вручную и не попадает в Git.
- `WEBUI_SECRET_KEY` генерируется один раз через `openssl rand -hex 32` и остается стабильным.
- `WEBUI_NAME=Alpha Soft AI Chat` задает мягкое имя инстанса; OpenWebUI branding не скрывается.
- `WEBUI_BANNERS` задает warning banner с запретом отправлять секреты и закрытые персональные данные.
- `BACKUP_RETENTION_DAYS=7` хранит backup artifacts около недели; допустимые pilot values: `1`, `7`, `30`.
- `CORS_ALLOW_ORIGIN` ограничивается `https://gpt.alpha-soft.ru`, чтобы не оставлять CORS default `*`.
- Compose-файл хранится в `compose/openwebui.compose.yml`.
- Скрипты preflight, network hardening, backup и smoke хранятся в `scripts/`.
- OpenWebUI может сохранять часть настроек во внутренней persistent config; поэтому изменения provider config после первого запуска проверяются через Admin UI.

## Проверка готовности

Готовность подтверждается не фактом запуска контейнеров, а acceptance checks:

- домен открывается по HTTPS;
- UFW активен и public perimeter ограничен;
- fail2ban активен, `sshd` jail включен;
- администратор входит;
- созданы 3-4 пользователя;
- имя инстанса отображается как `Alpha Soft AI Chat` или подтвержденное оператором значение;
- warning banner виден пользователю и содержит запрет на секреты/закрытые персональные данные;
- OpenAI primary с `gpt-5.4-mini` и Gemini secondary с `gemini-3.5-flash` подключены или второй явно pending только по API key/quota/billing/region;
- пользователь получает ответ хотя бы от одного provider;
- история чата сохраняется после restart;
- strict TLS smoke проходит без отключения проверки сертификата;
- `.env` не попал в Git;
- backup создается и описан restore path.

## Риски

- На сервере preflight показал отсутствие Docker и Traefik: перед deploy нужен bootstrap.
- GitHub-репозиторий публичный: он не должен содержать SSH endpoint, публичный IP, API-ключи, реальные пароли и персональные данные участников.
- OpenWebUI часть настроек сохраняет в persistent config, поэтому изменения env после первого запуска могут не примениться без действий через Admin UI.
- Multi-provider env через `OPENAI_API_BASE_URLS`/`OPENAI_API_KEYS` возможен по документации OpenWebUI, но в PRD-0 не выбран как skeleton path из-за риска ошибки порядка URL/key и persistent config.
- `WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD` создают администратора только на свежей базе, когда пользователей еще нет.

## Ссылки

- PRD: [../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Provider plan: [../infra/PROVIDER_CONNECTIONS_PLAN.md](../infra/PROVIDER_CONNECTIONS_PLAN.md)
- Provider setup runbook: [../ops/PROVIDER_SETUP_RUNBOOK.md](../ops/PROVIDER_SETUP_RUNBOOK.md)
- Host hardening runbook: [../ops/HOST_HARDENING_RUNBOOK.md](../ops/HOST_HARDENING_RUNBOOK.md)
- Architecture overview: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- Non-goals: [SCOPE_AND_NON_GOALS.md](SCOPE_AND_NON_GOALS.md)
