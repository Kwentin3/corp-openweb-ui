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

Для PRD-0 image должен быть pinned в `.env`, например:

```text
OPENWEBUI_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
```

Не использовать `:main` для пилота без явного решения: официальный OpenWebUI guidance предупреждает, что `:main` является floating/development-like tag и может принести breaking changes.

3. Проверить текущий smoke и hardening:

```bash
bash scripts/network-hardening-check.sh
bash scripts/smoke-test.sh --strict-tls
```

4. Зафиксировать primary/secondary provider и model ids без секретов.

## Update

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml pull
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
bash scripts/smoke-test.sh --strict-tls
```

После update выполнить smoke, provider check и короткий пользовательский тест.

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

После rollback проверить:

```bash
bash scripts/network-hardening-check.sh
bash scripts/smoke-test.sh --strict-tls
```

И вручную проверить LLM-ответ хотя бы от одного provider.

## Rule

Не обновлять и не откатывать во время пользовательского пилота без backup и понятного окна работ.
