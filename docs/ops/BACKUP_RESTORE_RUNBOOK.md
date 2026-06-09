# Backup Restore Runbook

## Backup

Запуск:

```bash
bash scripts/backup.sh
```

Скрипт сохраняет:

- Docker volume `openwebui_data`;
- server-local `.env`, если файл существует;
- опционально volume `traefik_letsencrypt`, если он создан.

Backup directory по умолчанию:

```text
/opt/backups/openwebui-prd0
```

## Restore

1. Остановить сервисы:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml down
```

2. Восстановить `.env` из server-local backup и выставить права:

```bash
cp /opt/backups/openwebui-prd0/env-<timestamp>.backup .env
chmod 600 .env
```

3. Восстановить `openwebui_data` по инструкции [../../scripts/restore.md](../../scripts/restore.md).

4. Для `traefik_letsencrypt` выбрать один путь:

- штатно не восстанавливать volume и дать Traefik перевыпустить сертификат через Let's Encrypt, если DNS и порт `80/tcp` доступны;
- восстановить volume по [../../scripts/restore.md](../../scripts/restore.md), если нужно сохранить ACME account/certificate state.

5. Запустить сервисы:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

6. Проверить strict TLS, вход администратора, историю чатов и новый запрос к модели.

## Важно

Backup содержит секреты, если копируется `.env`. Не переносить такие архивы в Git, публичные чаты или незащищенные хранилища.
