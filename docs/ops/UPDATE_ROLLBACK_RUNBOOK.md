# Update Rollback Runbook

## Before update

1. Сделать backup:

```bash
bash scripts/backup.sh
```

2. Зафиксировать текущие images:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml images
```

3. Проверить текущий smoke:

```bash
bash scripts/smoke-test.sh
```

## Update

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml pull
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

После update выполнить smoke и короткий пользовательский тест.

## Rollback

Для PRD-0 предпочтительно rollback через pinned image tag в `.env`:

```text
OPENWEBUI_IMAGE=ghcr.io/open-webui/open-webui:<previous-tag>
TRAEFIK_IMAGE=traefik:<previous-tag>
```

Затем:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Если данные повреждены, восстановить backup по [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md).

## Rule

Не обновлять и не откатывать во время пользовательского пилота без backup и понятного окна работ.
