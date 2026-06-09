# Infra Target

## Public target

- Domain: `gpt.alpha-soft.ru`
- DNS A record: `gpt.alpha-soft.ru -> target public IPv4`
- Public ports needed: `22/tcp`, `80/tcp`, `443/tcp`
- OS target: Ubuntu Server LTS
- Required host hardening: UFW + fail2ban

Точный SSH endpoint и публичный IP не фиксируются в коммитимых документах, потому что GitHub-репозиторий может быть публичным. Локальная копия хранится в ignored-файле `local/INFRA_TARGET.local.md`.

GitHub-репозиторий публичный, поэтому коммитимые документы используют роли и placeholders вместо персональных данных и точных инфраструктурных адресов.

## Current deployment summary

Актуально на 2026-06-09:

- DNS для `gpt.alpha-soft.ru` резолвится в целевой public IPv4.
- SSH-доступ по ключу работает.
- Сервер: Ubuntu 24.04.4 LTS.
- Root filesystem: около 50 GB, свободно около 46 GB.
- Docker Engine установлен.
- Docker Compose установлен.
- Traefik запущен и публикует только `80/tcp` и `443/tcp`.
- OpenWebUI запущен и healthy, без прямого public port.
- TLS strict smoke проходит: HTTP редиректит на HTTPS, HTTPS отвечает без `curl -k`.
- UFW active: default deny incoming / allow outgoing.
- fail2ban active, `sshd` jail readable.
- Public listeners ограничены `22/tcp`, `80/tcp`, `443/tcp`.
- Provider egress для OpenAI идет через host-local HTTP-to-SOCKS bridge, если прямой egress блокируется provider region policy.
- Bridge port `8118/tcp` не public; разрешен только с Docker subnet на Docker gateway.
- Backup script отработал, retention управляется `BACKUP_RETENTION_DAYS`.
- OpenAI primary через OpenWebUI API проверен с model id `gpt-5.4-mini`.

## Implication

Репозиторий описывает текущий поднятый target PRD-0. Для повторного разворачивания или восстановления использовать:

1. Docker bootstrap: [../ops/BOOTSTRAP_DOCKER_UBUNTU.md](../ops/BOOTSTRAP_DOCKER_UBUNTU.md).
2. Host hardening: [../ops/HOST_HARDENING_RUNBOOK.md](../ops/HOST_HARDENING_RUNBOOK.md).
3. Deploy/restart flow: [../ops/DEPLOYMENT_RUNBOOK.md](../ops/DEPLOYMENT_RUNBOOK.md).
4. Provider setup: [../ops/PROVIDER_SETUP_RUNBOOK.md](../ops/PROVIDER_SETUP_RUNBOOK.md).
5. Backup/restore: [../ops/BACKUP_RESTORE_RUNBOOK.md](../ops/BACKUP_RESTORE_RUNBOOK.md).

Оставшиеся operator actions для пилота:

- добавить Gemini secondary provider через Admin UI, если нужен второй provider в acceptance;
- создать или активировать 3-4 пилотных пользователя;
- ротировать секреты, которые передавались вне password manager.
