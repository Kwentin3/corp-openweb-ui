# corp-openweb-ui

Инженерный пакет для PRD-0: минимальный self-hosted запуск OpenWebUI как корпоративной точки входа в LLM-чат для 3-4 пользователей.

Цель репозитория - blueprint, runbooks и skeleton для безопасного развертывания на домене `gpt.alpha-soft.ru`. Это не AI-платформа.

## Scope PRD-0

Входит:

- OpenWebUI;
- Docker / Docker Compose;
- Traefik и HTTPS;
- OpenAI + Gemini как API-провайдеры;
- мягкое имя инстанса и warning banner штатными средствами OpenWebUI;
- один primary provider через `.env`;
- второй provider через OpenWebUI Admin UI;
- один администратор;
- 3-4 пользователя;
- persistent volume;
- базовый host hardening: UFW + fail2ban;
- минимальный backup;
- smoke и acceptance checks.

Не входит: LiteLLM, model gateway, SSO/OIDC, web-поиск, RAG, document skills, plugins/tools/functions, fork OpenWebUI, custom frontend, logo replacement, corporate dashboard, white-label, маршрутизация провайдеров, бюджеты и интеграции с внутренними системами.

## Быстрый старт на сервере

Полный порядок см. в [docs/ops/DEPLOYMENT_RUNBOOK.md](docs/ops/DEPLOYMENT_RUNBOOK.md). Коротко:

```bash
git clone https://github.com/Kwentin3/corp-openweb-ui.git /opt/openwebui-prd0
cd /opt/openwebui-prd0
cp .env.example .env
chmod 600 .env
vi .env
bash scripts/preflight.sh
bash scripts/network-hardening-check.sh
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
bash scripts/smoke-test.sh --strict-tls
```

Реальный `.env` не коммитить.
Перед запуском закрыть операторские решения в [docs/ops/DEPLOYMENT_DECISIONS.md](docs/ops/DEPLOYMENT_DECISIONS.md).

## Навигация

- PRD: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Blueprint: [docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md](docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md)
- Architecture: [docs/blueprint/ARCHITECTURE_OVERVIEW.md](docs/blueprint/ARCHITECTURE_OVERVIEW.md)
- Scope/non-goals: [docs/blueprint/SCOPE_AND_NON_GOALS.md](docs/blueprint/SCOPE_AND_NON_GOALS.md)
- Infra target: [docs/infra/INFRA_TARGET.md](docs/infra/INFRA_TARGET.md)
- Traefik plan: [docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md](docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md)
- Compose plan: [docs/infra/DOCKER_COMPOSE_PLAN.md](docs/infra/DOCKER_COMPOSE_PLAN.md)
- Env variables: [docs/infra/ENVIRONMENT_VARIABLES.md](docs/infra/ENVIRONMENT_VARIABLES.md)
- Provider plan: [docs/infra/PROVIDER_CONNECTIONS_PLAN.md](docs/infra/PROVIDER_CONNECTIONS_PLAN.md)
- Deployment runbook: [docs/ops/DEPLOYMENT_RUNBOOK.md](docs/ops/DEPLOYMENT_RUNBOOK.md)
- Docker bootstrap: [docs/ops/BOOTSTRAP_DOCKER_UBUNTU.md](docs/ops/BOOTSTRAP_DOCKER_UBUNTU.md)
- Host hardening runbook: [docs/ops/HOST_HARDENING_RUNBOOK.md](docs/ops/HOST_HARDENING_RUNBOOK.md)
- Provider setup runbook: [docs/ops/PROVIDER_SETUP_RUNBOOK.md](docs/ops/PROVIDER_SETUP_RUNBOOK.md)
- Deployment decisions: [docs/ops/DEPLOYMENT_DECISIONS.md](docs/ops/DEPLOYMENT_DECISIONS.md)
- Backup/restore: [docs/ops/BACKUP_RESTORE_RUNBOOK.md](docs/ops/BACKUP_RESTORE_RUNBOOK.md)
- Smoke tests: [docs/ops/SMOKE_TESTS.md](docs/ops/SMOKE_TESTS.md)
- Acceptance tests: [docs/ops/ACCEPTANCE_TESTS.md](docs/ops/ACCEPTANCE_TESTS.md)
- Security minimum: [docs/security/SECURITY_MINIMUM.md](docs/security/SECURITY_MINIMUM.md)
- Firewall/fail2ban: [docs/security/FIREWALL_AND_FAIL2BAN.md](docs/security/FIREWALL_AND_FAIL2BAN.md)
- Pilot checklist: [docs/pilot/PILOT_CHECKLIST.md](docs/pilot/PILOT_CHECKLIST.md)
- Engineering report: [docs/reports/2026-06-09/OPENWEBUI_PRD_0_ENGINEERING_PACKAGE.report.md](docs/reports/2026-06-09/OPENWEBUI_PRD_0_ENGINEERING_PACKAGE.report.md)
- REFINE-2 report: [docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_2_PROVIDERS_AND_HARDENING.report.md](docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_2_PROVIDERS_AND_HARDENING.report.md)
- REFINE-3 report: [docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_3_LOW_COST_CUSTOMIZATION.report.md](docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_3_LOW_COST_CUSTOMIZATION.report.md)

## Skeleton

- Compose: [compose/openwebui.compose.yml](compose/openwebui.compose.yml)
- Env example: [.env.example](.env.example)
- Preflight: [scripts/preflight.sh](scripts/preflight.sh)
- Network hardening check: [scripts/network-hardening-check.sh](scripts/network-hardening-check.sh)
- Backup: [scripts/backup.sh](scripts/backup.sh)
- Restore notes: [scripts/restore.md](scripts/restore.md)
- Smoke test: [scripts/smoke-test.sh](scripts/smoke-test.sh)

## Безопасность

Не коммитить реальные API-ключи, пароли, токены, private keys, `.env` и backup-архивы. Точный SSH endpoint хранится только локально в ignored-файле `local/INFRA_TARGET.local.md`.
