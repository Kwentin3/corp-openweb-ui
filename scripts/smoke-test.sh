#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
STRICT_TLS=false

case "${1:-}" in
  --strict-tls)
    STRICT_TLS=true
    ;;
  "" )
    ;;
  -h|--help)
    printf 'Usage: %s [--strict-tls]\n' "$0"
    exit 0
    ;;
  *)
    printf 'FAIL: unknown argument: %s\n' "$1" >&2
    exit 1
    ;;
esac

[ -f "$ENV_FILE" ] || {
  printf 'FAIL: .env not found\n' >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

[ -n "${OPENWEBUI_HOST:-}" ] || {
  printf 'FAIL: OPENWEBUI_HOST is empty\n' >&2
  exit 1
}

if [ "$STRICT_TLS" = true ]; then
  TLS_ARGS=""
  printf 'tls_mode=strict\n'
else
  TLS_ARGS="-k"
  printf 'tls_mode=insecure-smoke\n'
fi

HTTP_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "http://${OPENWEBUI_HOST}/" || true)"
# shellcheck disable=SC2086
HTTPS_CODE="$(curl $TLS_ARGS -sS -o /dev/null -w '%{http_code}' "https://${OPENWEBUI_HOST}/" || true)"

printf 'http_status=%s\n' "$HTTP_CODE"
printf 'https_status=%s\n' "$HTTPS_CODE"

case "$HTTP_CODE" in
  301|302|308) printf 'OK: HTTP redirects\n' ;;
  *) printf 'WARN: HTTP did not return redirect status\n' >&2 ;;
esac

case "$HTTPS_CODE" in
  200|301|302|307|308) printf 'OK: HTTPS endpoint responds\n' ;;
  *) printf 'FAIL: HTTPS endpoint is not healthy\n' >&2; exit 1 ;;
esac

docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/compose/openwebui.compose.yml" ps
