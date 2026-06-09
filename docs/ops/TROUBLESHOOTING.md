# Troubleshooting

## DNS не указывает на сервер

Проверить:

```bash
dig +short gpt.alpha-soft.ru
```

Если IP неверный, исправить A-запись и дождаться TTL.

## HTTPS не выпускается

Проверить:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=200 traefik
```

Частые причины:

- порт `80/tcp` закрыт firewall или внешним provider firewall;
- DNS указывает не туда;
- неверный `LETSENCRYPT_EMAIL`;
- Traefik не видит Docker labels.

## UFW/fail2ban warning

Проверить:

```bash
bash scripts/network-hardening-check.sh
sudo ufw status verbose
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

До запуска Traefik отсутствие listeners `80/443` может быть нормальным. После deploy это blocker.

Если fail2ban ошибочно заблокировал IP:

```bash
sudo fail2ban-client set sshd unbanip <operator-public-ip>
```

Операторский IP не коммитить.

## OpenWebUI не открывается

Проверить:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml ps
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=200 openwebui
```

## Provider не отвечает

Проверить:

- какой provider выбран primary через `.env`;
- `OPENAI_API_BASE_URL`;
- `OPENAI_API_KEY`;
- наличие доступа сервера к внешним API;
- billing/quota/region;
- exact model id;
- Connections в Admin UI.

Ожидаемые base URL:

- OpenAI: `https://api.openai.com/v1`;
- Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`.

Для Gemini не использовать trailing slash в этом PRD-0 runbook.

Если OpenAI/Gemini API блокирует прямой egress сервера по региону:

- не задавать `socks5h://` напрямую в `OPENWEBUI_OUTBOUND_PROXY`;
- поднять host-local HTTP-to-SOCKS bridge;
- в `.env` задать `OPENWEBUI_OUTBOUND_PROXY=http://<docker-gateway>:8118`;
- хранить SOCKS5 upstream отдельно в `OPENWEBUI_SOCKS5_UPSTREAM`;
- проверить, что bridge port доступен из контейнера, но не открыт публично.

Проверить bridge без вывода секретов:

```bash
grep -E '^(OPENWEBUI_OUTBOUND_PROXY|OPENWEBUI_NO_PROXY)=' .env
systemctl status privoxy --no-pager
ss -tulpen | grep ':8118'
docker exec -i openwebui python - <<'PY'
import asyncio, os
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

## Имя инстанса или баннер не отображаются

Проверить `.env`:

```bash
grep -E '^(WEBUI_NAME|WEBUI_BANNERS)=' .env
docker compose --env-file .env -f compose/openwebui.compose.yml config
```

`WEBUI_BANNERS` должен быть валидной JSON-строкой. Если env корректен, но UI не меняется после restart, проверить Admin UI -> Settings -> General. Не менять frontend-код и не делать fork.

## WebSocket или CORS errors

Проверить `CORS_ALLOW_ORIGIN`:

```bash
grep CORS_ALLOW_ORIGIN .env
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=200 openwebui
```

Для PRD-0 ожидаемо:

```text
CORS_ALLOW_ORIGIN=https://gpt.alpha-soft.ru
```

Если пользователи заходят через другой hostname, его нужно добавить явно через `;`, либо запретить такой способ доступа.

## Пользователей разлогинило после пересоздания контейнера

Проверить, что `WEBUI_SECRET_KEY` задан в `.env` и не менялся:

```bash
grep WEBUI_SECRET_KEY .env
```

Если ключ менялся, старые сессии станут недействительными. Менять `WEBUI_SECRET_KEY` только как осознанную rotation-операцию.

## История не сохраняется

Проверить, что volume `openwebui_data` подключен:

```bash
docker volume inspect openwebui_data
```

Не удалять volume без backup.

## Env изменили, но поведение не изменилось

OpenWebUI может сохранять часть настроек в persistent config. Проверить настройку в Admin UI и перезапустить `openwebui`.
