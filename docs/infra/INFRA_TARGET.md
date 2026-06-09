# Infra Target

## Public target

- Domain: `gpt.alpha-soft.ru`
- DNS A record: `gpt.alpha-soft.ru -> target public IPv4`
- Public ports needed: `22/tcp`, `80/tcp`, `443/tcp`
- OS target: Ubuntu Server LTS
- Required host hardening: UFW + fail2ban

Точный SSH endpoint и публичный IP не фиксируются в коммитимых документах, потому что GitHub-репозиторий может быть публичным. Локальная копия хранится в ignored-файле `local/INFRA_TARGET.local.md`.

GitHub-репозиторий публичный, поэтому коммитимые документы используют роли и placeholders вместо персональных данных и точных инфраструктурных адресов.

## Current preflight summary

На момент preflight:

- DNS для `gpt.alpha-soft.ru` резолвится в целевой public IPv4.
- SSH-доступ по ключу работает.
- Сервер: Ubuntu 24.04.4 LTS.
- Root filesystem: около 50 GB, свободно около 46 GB.
- Docker не установлен.
- Docker Compose не установлен.
- Traefik не найден.
- Контейнеров Docker нет.
- Docker networks нет.
- На сервере нет локального listener на `80/443`.
- UFW/fail2ban должны быть проверены и настроены перед deploy.

## Implication

Перед фактическим deploy нужен bootstrap:

1. Установить Docker Engine по [../ops/BOOTSTRAP_DOCKER_UBUNTU.md](../ops/BOOTSTRAP_DOCKER_UBUNTU.md).
2. Установить Docker Compose plugin.
3. Настроить UFW/fail2ban по [../ops/HOST_HARDENING_RUNBOOK.md](../ops/HOST_HARDENING_RUNBOOK.md).
4. Склонировать репозиторий.
5. Создать server-local `.env`.
6. Закрыть provider/operator decisions.
7. Поднять `compose/openwebui.compose.yml`.
