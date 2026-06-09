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

- порт `80/tcp` закрыт;
- DNS указывает не туда;
- неверный `LETSENCRYPT_EMAIL`;
- Traefik не видит Docker labels.

## OpenWebUI не открывается

Проверить:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml ps
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=200 openwebui
```

## Модель не отвечает

Проверить:

- `OPENAI_API_BASE_URL`;
- `OPENAI_API_KEY`;
- наличие доступа сервера к внешнему API;
- выбранную модель в Admin UI.

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
