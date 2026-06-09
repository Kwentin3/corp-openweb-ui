# OpenWebUI PRD-0 Engineering Package Report

Дата: 2026-06-09

## Что прочитано

- PRD: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`.
- Текущее дерево проекта.
- Git remote, branch, worktree и status.
- Existing docs по прежнему scope на тот момент были оставлены без удаления; REFINE-3 удаляет устаревший контур.

## Git

- Ветка: `main`.
- Worktree: один canonical tree.
- До изменения remote `origin` указывал на прежний репозиторий.
- Старый remote сохранен как `old-origin`.
- Новый `origin`: `https://github.com/Kwentin3/corp-openweb-ui.git`.
- Целевой GitHub repository доступен, `HEAD` на момент проверки не вернул коммитов.

## Secret scan

В текущих файлах не найдено явных private key/API key/password/token assignments по базовому `rg`-скану. Это не заменяет полноценный secret scanner перед публикацией.

## Server preflight

Проверено без destructive actions:

- SSH-доступ по ключу работает.
- ОС: Ubuntu 24.04.4 LTS.
- Hostname: `ai-corp`.
- Root filesystem: около 50 GB, свободно около 46 GB.
- Docker не установлен.
- Docker Compose не установлен.
- Traefik не найден.
- Docker containers и networks отсутствуют.
- DNS `gpt.alpha-soft.ru` резолвится в целевой public IPv4.
- Извне TCP connect на `80/443` проходит, но на самом сервере нет локального listener на `80/443`; перед deploy это нужно перепроверить после запуска Traefik.

## Что создано

Создан инженерный пакет:

- blueprint docs;
- infra docs;
- ops runbooks;
- security docs;
- pilot docs;
- technical skeleton Compose/env/scripts;
- локальный ignored target-файл для SSH endpoint;
- отчет.

Ключевые новые файлы:

- `docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md`
- `docs/blueprint/ARCHITECTURE_OVERVIEW.md`
- `docs/blueprint/SCOPE_AND_NON_GOALS.md`
- `docs/infra/INFRA_TARGET.md`
- `docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/infra/STORAGE_AND_VOLUMES.md`
- `docs/ops/DEPLOYMENT_RUNBOOK.md`
- `docs/ops/BACKUP_RESTORE_RUNBOOK.md`
- `docs/ops/UPDATE_ROLLBACK_RUNBOOK.md`
- `docs/ops/SMOKE_TESTS.md`
- `docs/ops/ACCEPTANCE_TESTS.md`
- `docs/ops/TROUBLESHOOTING.md`
- `docs/security/SECURITY_MINIMUM.md`
- `docs/security/SECRETS_POLICY.md`
- `docs/security/ACCESS_POLICY.md`
- `docs/pilot/USER_ONBOARDING.md`
- `docs/pilot/PILOT_CHECKLIST.md`
- `docs/pilot/PILOT_FEEDBACK_FORM.md`
- `compose/openwebui.compose.yml`
- `.env.example`
- `scripts/preflight.sh`
- `scripts/backup.sh`
- `scripts/restore.md`
- `scripts/smoke-test.sh`

## Риски

- Перед deploy нужно установить Docker Engine и Docker Compose plugin.
- Нужно проверить, что public NAT/firewall корректно пробрасывает `80/443` на сервер после запуска Traefik.
- Нужно вручную заполнить `.env` на сервере.
- Нужно выбрать конкретного LLM API-провайдера и модель.
- Нужно убедиться, что OpenWebUI admin bootstrap применяется на первом запуске.

## Готовность

Проект готов как инженерный пакет для минимального deploy PRD-0. К фактическому production-like запуску он будет готов после server bootstrap, заполнения `.env`, запуска Compose и прохождения acceptance checks.

## Итоговая валидация

- `git diff --check` прошел без ошибок whitespace; есть только предупреждения Git о будущей CRLF-нормализации для `.gitignore` и `README.md`.
- Shell scripts прошли `bash -n`.
- `compose/openwebui.compose.yml` успешно распарсен как YAML.
- `local/INFRA_TARGET.local.md` игнорируется через `.gitignore`.
- Повторный secret scan коммитимых файлов не нашел явных секретов.
- Локальный Docker Compose plugin отсутствует, поэтому `docker compose config` не запускался.

## Следующие команды

После установки Docker/Compose на сервере:

```bash
git clone https://github.com/Kwentin3/corp-openweb-ui.git /opt/openwebui-prd0
cd /opt/openwebui-prd0
cp .env.example .env
chmod 600 .env
vi .env
bash scripts/preflight.sh
docker compose --env-file .env -f compose/openwebui.compose.yml pull
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
bash scripts/smoke-test.sh
```

Затем выполнить acceptance checks из `docs/ops/ACCEPTANCE_TESTS.md`.
