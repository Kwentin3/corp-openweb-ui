# Restore Notes

Run restore only during a maintenance window.

## Restore `openwebui_data`

Stop services:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml down
```

Recreate the target volume:

```bash
docker volume rm openwebui_data
docker volume create openwebui_data
```

Restore archive:

```bash
BACKUP=/opt/backups/openwebui-prd0/openwebui_data-YYYYMMDDTHHMMSSZ.tgz
docker run --rm \
  -v openwebui_data:/data \
  -v "$(dirname "$BACKUP"):/backup:ro" \
  alpine:3.20 \
  sh -c "cd /data && tar xzf /backup/$(basename "$BACKUP")"
```

Restore `.env` if needed:

```bash
cp /opt/backups/openwebui-prd0/env-YYYYMMDDTHHMMSSZ.backup .env
chmod 600 .env
```

Start services:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Then run smoke and manually verify admin login, chat history and a new LLM response.

## Restore `traefik_letsencrypt`

Usually you can skip restoring `traefik_letsencrypt`: Traefik can request a fresh Let's Encrypt certificate if DNS is correct and port `80/tcp` is reachable from the internet.

Restore this volume only if you need to preserve ACME account/certificate state or avoid re-issuance.

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml down
docker volume rm traefik_letsencrypt
docker volume create traefik_letsencrypt

BACKUP=/opt/backups/openwebui-prd0/traefik_letsencrypt-YYYYMMDDTHHMMSSZ.tgz
docker run --rm \
  -v traefik_letsencrypt:/data \
  -v "$(dirname "$BACKUP"):/backup:ro" \
  alpine:3.20 \
  sh -c "cd /data && tar xzf /backup/$(basename "$BACKUP")"

docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

After either path, run:

```bash
bash scripts/smoke-test.sh --strict-tls
```
