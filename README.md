# corp-openweb-ui

Инженерный пакет для PRD-0: минимальный self-hosted запуск OpenWebUI как корпоративной точки входа в LLM-чат для 3-4 пользователей.

Цель репозитория - blueprint, runbooks и skeleton для безопасного развертывания на домене `gpt.alpha-soft.ru`. Это не AI-платформа и не Hermes.

## Scope PRD-0

Входит:

- OpenWebUI;
- Docker / Docker Compose;
- Traefik и HTTPS;
- один LLM API-провайдер;
- одна модель по умолчанию;
- один администратор;
- 3-4 пользователя;
- persistent volume;
- минимальный backup;
- smoke и acceptance checks.

Не входит: Hermes, LiteLLM, model gateway, SSO/OIDC, web-поиск, RAG, document skills, corporate dashboard, white-label и интеграции с внутренними системами.

## Быстрый старт на сервере

```bash
git clone https://github.com/Kwentin3/corp-openweb-ui.git /opt/openwebui-prd0
cd /opt/openwebui-prd0
cp .env.example .env
chmod 600 .env
vi .env
bash scripts/preflight.sh
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
bash scripts/smoke-test.sh
```

Реальный `.env` не коммитить.

## Навигация

- PRD: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Blueprint: [docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md](docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md)
- Architecture: [docs/blueprint/ARCHITECTURE_OVERVIEW.md](docs/blueprint/ARCHITECTURE_OVERVIEW.md)
- Scope/non-goals: [docs/blueprint/SCOPE_AND_NON_GOALS.md](docs/blueprint/SCOPE_AND_NON_GOALS.md)
- Infra target: [docs/infra/INFRA_TARGET.md](docs/infra/INFRA_TARGET.md)
- Traefik plan: [docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md](docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md)
- Compose plan: [docs/infra/DOCKER_COMPOSE_PLAN.md](docs/infra/DOCKER_COMPOSE_PLAN.md)
- Env variables: [docs/infra/ENVIRONMENT_VARIABLES.md](docs/infra/ENVIRONMENT_VARIABLES.md)
- Deployment runbook: [docs/ops/DEPLOYMENT_RUNBOOK.md](docs/ops/DEPLOYMENT_RUNBOOK.md)
- Backup/restore: [docs/ops/BACKUP_RESTORE_RUNBOOK.md](docs/ops/BACKUP_RESTORE_RUNBOOK.md)
- Smoke tests: [docs/ops/SMOKE_TESTS.md](docs/ops/SMOKE_TESTS.md)
- Acceptance tests: [docs/ops/ACCEPTANCE_TESTS.md](docs/ops/ACCEPTANCE_TESTS.md)
- Security minimum: [docs/security/SECURITY_MINIMUM.md](docs/security/SECURITY_MINIMUM.md)
- Pilot checklist: [docs/pilot/PILOT_CHECKLIST.md](docs/pilot/PILOT_CHECKLIST.md)
- Engineering report: [docs/reports/2026-06-09/OPENWEBUI_PRD_0_ENGINEERING_PACKAGE.report.md](docs/reports/2026-06-09/OPENWEBUI_PRD_0_ENGINEERING_PACKAGE.report.md)

## Skeleton

- Compose: [compose/openwebui.compose.yml](compose/openwebui.compose.yml)
- Env example: [.env.example](.env.example)
- Preflight: [scripts/preflight.sh](scripts/preflight.sh)
- Backup: [scripts/backup.sh](scripts/backup.sh)
- Restore notes: [scripts/restore.md](scripts/restore.md)
- Smoke test: [scripts/smoke-test.sh](scripts/smoke-test.sh)

## Безопасность

Не коммитить реальные API-ключи, пароли, токены, private keys, `.env` и backup-архивы. Точный SSH endpoint хранится только локально в ignored-файле `local/INFRA_TARGET.local.md`.
