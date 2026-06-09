# Infra Target

## Public target

- Domain: `gpt.alpha-soft.ru`
- DNS A record: `gpt.alpha-soft.ru -> target public IPv4`
- Public ports needed: `80/tcp`, `443/tcp`, `22/tcp`
- OS target: Ubuntu Server LTS

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

## Implication

Перед фактическим deploy нужен bootstrap:

1. Установить Docker Engine по [../ops/BOOTSTRAP_DOCKER_UBUNTU.md](../ops/BOOTSTRAP_DOCKER_UBUNTU.md).
2. Установить Docker Compose plugin.
3. Склонировать репозиторий.
4. Создать server-local `.env`.
5. Поднять `compose/openwebui.compose.yml`.
