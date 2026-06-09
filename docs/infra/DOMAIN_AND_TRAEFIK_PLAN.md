# Domain And Traefik Plan

## DNS

Нужна A-запись:

```text
gpt.alpha-soft.ru -> target public IPv4
```

Перед deploy проверить:

```bash
dig +short gpt.alpha-soft.ru
```

## Traefik

Traefik запускается в Docker Compose и слушает:

- `80/tcp` для HTTP redirect и ACME HTTP challenge;
- `443/tcp` для HTTPS.

## TLS

TLS-сертификат выпускается через Let's Encrypt HTTP challenge. Для этого порт `80/tcp` должен быть доступен извне до первого запуска Traefik.

ACME storage хранится в Docker volume `traefik_letsencrypt`.

## Routing

Маршрут:

```text
Host(`gpt.alpha-soft.ru`) -> openwebui:8080
```

OpenWebUI не публикует внешний порт.

## Checks

После запуска:

```bash
curl -I http://gpt.alpha-soft.ru
curl -I https://gpt.alpha-soft.ru
docker compose -f compose/openwebui.compose.yml logs --tail=100 traefik
```

Ожидаемо: HTTP редиректит на HTTPS, HTTPS открывает OpenWebUI.
