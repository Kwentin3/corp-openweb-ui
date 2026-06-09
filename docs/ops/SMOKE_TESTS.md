# Smoke Tests

## Цель

Smoke checks подтверждают, что сервис поднят и доступен. Они не заменяют acceptance tests.

## Команды

```bash
bash scripts/preflight.sh
docker compose --env-file .env -f compose/openwebui.compose.yml ps
bash scripts/smoke-test.sh
```

## Проверки

- DNS резолвится.
- `80/tcp` и `443/tcp` доступны извне.
- Контейнеры `traefik` и `openwebui` запущены.
- HTTP редиректит на HTTPS.
- HTTPS endpoint отвечает.
- В логах Traefik нет ошибок ACME.
- В логах OpenWebUI нет циклического падения.

## Логи

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 traefik
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```
