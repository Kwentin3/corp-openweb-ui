# OpenWebUI PRD-0 REFINE-3: Low-Cost Customization

Дата: 2026-06-09

## Что добавлено

- `WEBUI_NAME="Alpha Soft AI Chat"` в `.env.example`.
- `WEBUI_BANNERS` warning banner в `.env.example`.
- `WEBUI_NAME` и `WEBUI_BANNERS` в `compose/openwebui.compose.yml`.
- Проверка `WEBUI_NAME`/`WEBUI_BANNERS` в `scripts/preflight.sh`.
- Acceptance criteria для имени инстанса и warning banner.
- Пользовательское предупреждение в onboarding.
- Security note: banner помогает, но не заменяет политику безопасности.

## Low-cost customization boundary

PRD-0 допускает только штатную обратимую настройку:

- env;
- Admin UI;
- мягкое имя инстанса;
- warning banner;
- закрытая регистрация;
- базовые настройки доступа.

Не добавлены fork, white-label, logo replacement, custom frontend, plugins, tools/functions, document skills, gateway, RAG или web search.

## Документы изменены

- `.env.example`
- `compose/openwebui.compose.yml`
- `scripts/preflight.sh`
- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md`
- `docs/blueprint/SCOPE_AND_NON_GOALS.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/ops/DEPLOYMENT_DECISIONS.md`
- `docs/ops/DEPLOYMENT_RUNBOOK.md`
- `docs/ops/ACCEPTANCE_TESTS.md`
- `docs/ops/SMOKE_TESTS.md`
- `docs/ops/TROUBLESHOOTING.md`
- `docs/pilot/USER_ONBOARDING.md`
- `docs/pilot/PILOT_CHECKLIST.md`
- `docs/security/SECURITY_MINIMUM.md`
- `docs/requirements/ACCEPTANCE_CRITERIA.md`
- `docs/requirements/SECURITY_REQUIREMENTS.md`

Также удалены устаревшие документы прежнего контура, не относящиеся к OpenWebUI PRD-0.

## WEBUI_BANNERS format

Формат в `.env.example`:

```env
WEBUI_BANNERS="[{\"id\":\"prd0-policy-warning-v1\",\"type\":\"warning\",\"title\":\"Тестовый корпоративный AI-чат\",\"content\":\"Не отправляйте пароли, токены, API-ключи, приватные SSH-ключи и закрытые персональные данные. Ответы модели нужно проверять.\",\"dismissible\":true,\"timestamp\":1780963200}]"
```

Проверено:

- Git Bash `source .env.example` корректно читает `WEBUI_NAME` как одну строку.
- Python JSON parse строки из `.env.example` проходит.
- `docker compose --env-file .env.example -f compose/openwebui.compose.yml config` проходит.

Локально Docker CLI был без compose plugin, поэтому для проверки использован временный Docker CLI config с Docker Compose standalone v5.1.4 как `docker --config <temp> compose ...`. Временный config удален после проверки.

Compose config показал:

- `WEBUI_NAME: Alpha Soft AI Chat`;
- `WEBUI_BANNERS` как одну JSON-строку;
- service `openwebui` и `traefik` корректно рендерятся.

## Official sources

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI customizable banners: https://docs.openwebui.com/features/administration/banners/

По OpenWebUI docs:

- `WEBUI_NAME` является штатной env-переменной и задает main WebUI name.
- `WEBUI_BANNERS` является штатной env-переменной для списка баннеров.
- Banner object содержит `id`, `type`, `title`, `content`, `dismissible`, `timestamp`.
- Для `.env` нужно экранировать JSON quotes.
- Banners также можно настраивать через Admin UI.

## Operator decisions remain

- Primary provider through `.env`.
- Secondary provider through Admin UI.
- OpenAI API key.
- Gemini API key.
- Exact OpenAI model id.
- Exact Gemini model id.
- Let's Encrypt email.
- First admin email/password.
- Backup retention.

Имя инстанса принято как `Alpha Soft AI Chat`, но оператор может подтвердить другое мягкое имя без white-label/fork.

## Scope status

Scope не расширен до платформы. Кастомизация остается дешевой, штатной и обратимой: только env/Admin UI.

Если `WEBUI_NAME` или `WEBUI_BANNERS` будут перекрыты persistent config после первого запуска, runbook направляет оператора в Admin UI. Fork и frontend patches запрещены.
