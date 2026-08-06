# Backup Restore Runbook

## Backup

Запуск:

```bash
bash scripts/backup.sh
```

Скрипт сохраняет:

- Docker volume `openwebui_data`;
- Docker volume `stage2_stt_data` после реализации quiesced backup в скрипте;
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

Текущий `scripts/backup.sh` ещё не включает `stage2_stt_data` и архивирует
работающий `openwebui_data`; поэтому он не считается application-consistent
для Broker/STT SQLite. До исправления использовать один из двух режимов:

- cold: остановить writers, архивировать volumes, запустить writers;
- coordinated: поставить canonical mutations на паузу, выполнить SQLite Online
  Backup, скопировать только immutable payloads из manifest и проверить hashes.

Неконтролируемый `cp` или tar работающей SQLite с отдельно меняющимся payload
root запрещён.

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

## DOC29 canonical-store verification

Broker Reports canonical metadata and payloads are expected below the existing
`openwebui_data` mount. A backup/restore run is accepted for DOC28 only when a
safe receipt proves all of the following on the approved target deployment:

- metadata and payload manifests match before backup and after restore;
- every sampled active pointer resolves to the same canonical root hash;
- every referenced chunk is readable under the same tenant/access context;
- rollback targets still resolve after restart;
- no private bytes, paths, filenames, secrets, or payloads enter Git evidence.

On 2026-08-05 an isolated coordinated drill passed with 172 payload files,
16/16 active pointers/root hashes, 0 missing chunks and fail-closed access. A
target pre-change SQLite snapshot outside `openwebui_data` also passed
`integrity_check=ok`. The target restore drill was not run because the bounded
backfill made the host control plane unresponsive. Therefore target
`BACKUP_RESTORE=NOT_CONFIRMED`; the isolated PASS must not be promoted to a
target claim.

## DOC30 target status

DOC30 recovered SSH and proved current Broker and STT integrity. DOC29 wrote no
canonical state, so the evidence-bound recovery action was `RETAIN`; the
historical pre-change backup was not restored. The resource-bounded target run
then stopped at an XLSX container OOM after 8 of 16 active versions.

No new complete DOC30 backup or isolated restore is accepted because complete
backfill and restart/recreation proof were not reached. Therefore target
`BACKUP_RESTORE=BLOCKED_BACKFILL_INCOMPLETE`. Do not promote the historical
snapshot or isolated DOC29 drill to current target proof, and never restore or
delete STT data without separate integrity evidence.
