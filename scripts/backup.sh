#!/usr/bin/env bash
set -eu
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/openwebui-prd0}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

backup_volume() {
  volume="$1"
  target="$BACKUP_DIR/${volume}-${TS}.tgz"

  if docker volume inspect "$volume" >/dev/null 2>&1; then
    docker run --rm \
      -v "${volume}:/data:ro" \
      -v "${BACKUP_DIR}:/backup" \
      alpine:3.20 \
      tar czf "/backup/$(basename "$target")" -C /data .
    chmod 600 "$target"
    printf 'created %s\n' "$target"
  else
    printf 'skip missing volume %s\n' "$volume" >&2
  fi
}

backup_volume openwebui_data
backup_volume traefik_letsencrypt

if [ -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env" "$BACKUP_DIR/env-${TS}.backup"
  chmod 600 "$BACKUP_DIR/env-${TS}.backup"
  printf 'created %s\n' "$BACKUP_DIR/env-${TS}.backup"
else
  printf 'skip missing .env\n' >&2
fi
