#!/usr/bin/env bash
set -eu
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

strip_quotes() {
  value="$1"
  case "$value" in
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
  esac
  printf '%s' "$value"
}

read_env_value() {
  name="$1"
  file="$ROOT_DIR/.env"

  [ -f "$file" ] || return 1

  value="$(awk -v name="$name" '
    BEGIN { prefix = name "=" }
    index($0, prefix) == 1 {
      value = substr($0, length(prefix) + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$file")"

  [ -n "$value" ] || return 1
  strip_quotes "$value"
}

BACKUP_DIR_FROM_ENV_FILE="$(read_env_value BACKUP_DIR || true)"
BACKUP_RETENTION_DAYS_FROM_ENV_FILE="$(read_env_value BACKUP_RETENTION_DAYS || true)"

BACKUP_DIR="${BACKUP_DIR:-${BACKUP_DIR_FROM_ENV_FILE:-/opt/backups/openwebui-prd0}}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-${BACKUP_RETENTION_DAYS_FROM_ENV_FILE:-}}"

if [ -n "$BACKUP_RETENTION_DAYS" ]; then
  case "$BACKUP_RETENTION_DAYS" in
    *[!0-9]*)
      printf 'invalid BACKUP_RETENTION_DAYS=%s\n' "$BACKUP_RETENTION_DAYS" >&2
      exit 1
      ;;
  esac

  if [ "$BACKUP_RETENTION_DAYS" -lt 1 ]; then
    printf 'BACKUP_RETENTION_DAYS must be 1 or greater\n' >&2
    exit 1
  fi
fi

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

prune_old_backups() {
  [ -n "$BACKUP_RETENTION_DAYS" ] || return 0

  printf 'pruning backups older than %s days in %s\n' "$BACKUP_RETENTION_DAYS" "$BACKUP_DIR"
  find "$BACKUP_DIR" -maxdepth 1 -type f \( \
    -name 'openwebui_data-*.tgz' -o \
    -name 'traefik_letsencrypt-*.tgz' -o \
    -name 'env-*.backup' \
  \) -mtime +"$BACKUP_RETENTION_DAYS" -print -delete
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

prune_old_backups
