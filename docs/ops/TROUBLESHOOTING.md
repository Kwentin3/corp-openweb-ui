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

## История не сохраняется

Проверить, что volume `openwebui_data` подключен:

```bash
docker volume inspect openwebui_data
```

Не удалять volume без backup.

## Env изменили, но поведение не изменилось

OpenWebUI может сохранять часть настроек в persistent config. Проверить настройку в Admin UI и перезапустить `openwebui`.
