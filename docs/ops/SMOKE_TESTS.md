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
- Если задан `OPENWEBUI_OUTBOUND_PROXY`, контейнер OpenWebUI может подключиться к HTTP proxy, provider `/models` отвечает, а proxy port не является public listener.

## Логи

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 traefik
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```

## Provider proxy smoke

Не выводить API keys и proxy credentials. Проверять только наличие env, схему и HTTP status:

```bash
docker exec -i openwebui python - <<'PY'
import asyncio, json, os
import aiohttp

async def main():
    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    print("proxy_present=" + str(bool(proxy)).lower())
    print("proxy_scheme=" + (proxy.split(":", 1)[0] if ":" in proxy else ""))
    headers = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get("https://api.openai.com/v1/models", headers=headers) as resp:
            print("openai_models_http=" + str(resp.status))

asyncio.run(main())
PY
```

Ожидаемо для текущего deployment через bridge: `proxy_present=true`, `proxy_scheme=http`, `openai_models_http=200`.
