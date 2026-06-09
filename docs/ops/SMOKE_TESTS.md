# Smoke Tests

## Цель

Smoke checks подтверждают, что сервис поднят, доступен и базовая сеть не противоречит PRD-0. Они не заменяют acceptance tests.

## Команды

```bash
bash scripts/preflight.sh
bash scripts/network-hardening-check.sh
docker compose --env-file .env -f compose/openwebui.compose.yml ps
bash scripts/smoke-test.sh
bash scripts/smoke-test.sh --strict-tls
bash scripts/network-hardening-check.sh --strict
```

До запуска Traefik использовать нестрогий `network-hardening-check.sh`: предупреждения по `80/443` могут быть ожидаемыми. После `docker compose up -d` использовать `--strict`; любые warnings должны либо исправляться, либо блокировать acceptance.

## Проверки

- DNS резолвится.
- UFW активен или warning явно объяснен до hardening.
- Fail2ban active или warning явно объяснен до hardening.
- `22/tcp`, `80/tcp`, `443/tcp` находятся в ожидаемом состоянии.
- `80/tcp` и `443/tcp` доступны извне после запуска Traefik.
- После запуска Traefik `bash scripts/network-hardening-check.sh --strict` проходит без warnings.
- Контейнеры `traefik` и `openwebui` запущены.
- HTTP редиректит на HTTPS.
- HTTPS endpoint отвечает.
- Strict TLS endpoint отвечает без `curl -k`.
- В UI вручную проверяется soft instance name и warning banner.
- В логах Traefik нет ошибок ACME.
- В логах OpenWebUI нет циклического падения.
- Primary provider из `.env` не вызывает ошибок при запросе.

## Логи

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 traefik
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```
