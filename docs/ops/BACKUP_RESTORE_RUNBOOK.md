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

Provider keys могут находиться в `.env` и/или в OpenWebUI persistent data, если secondary provider добавлен через Admin UI. Поэтому backup считается секретным.

## Retention

`scripts/backup.sh` читает retention из environment или server-local `.env`:

```env
BACKUP_RETENTION_DAYS=7
```

Для PRD-0 используются простые значения:

- `1` - test retention на 1 день;
- `7` - default для короткого пилота;
- `30` - около месяца.

Скрипт удаляет только свои known artifacts в `BACKUP_DIR`: `openwebui_data-*.tgz`, `traefik_letsencrypt-*.tgz`, `env-*.backup`.

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

3. Восстановить `openwebui_data` по инструкции [../../scripts/restore.md](../../scripts/restore.md). Это восстанавливает пользователей, историю и настройки OpenWebUI, включая provider connections, сохраненные через Admin UI.

4. Для `traefik_letsencrypt` выбрать один путь:

- штатно не восстанавливать volume и дать Traefik перевыпустить сертификат через Let's Encrypt, если DNS и порт `80/tcp` доступны;
- восстановить volume по [../../scripts/restore.md](../../scripts/restore.md), если нужно сохранить ACME account/certificate state.

5. Запустить сервисы:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

6. Проверить strict TLS, hardening, вход администратора, provider connections, историю чатов и новый запрос к модели:

```bash
bash scripts/network-hardening-check.sh
bash scripts/smoke-test.sh --strict-tls
```

## Важно

Backup содержит секреты, если копируется `.env`, и может содержать provider secrets в `openwebui_data`. Не переносить такие архивы в Git, публичные чаты или незащищенные хранилища.
