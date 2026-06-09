#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

warn() {
  printf 'WARN: %s\n' "$1" >&2
}

info() {
  printf 'OK: %s\n' "$1"
}

[ -f "$ENV_FILE" ] || fail ".env not found. Copy .env.example to .env first."

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

[ -n "${OPENWEBUI_HOST:-}" ] || fail "OPENWEBUI_HOST is empty"
[ -n "${LETSENCRYPT_EMAIL:-}" ] || fail "LETSENCRYPT_EMAIL is empty"
[ -n "${OPENAI_API_BASE_URL:-}" ] || fail "OPENAI_API_BASE_URL is empty"
[ -n "${OPENAI_API_KEY:-}" ] || fail "OPENAI_API_KEY is empty"

case "${LETSENCRYPT_EMAIL}:${OPENAI_API_KEY}:${WEBUI_ADMIN_PASSWORD:-}:${DEFAULT_MODELS:-}" in
  *example.com*|*replace-with*)
    fail ".env still contains placeholder values"
    ;;
esac

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin is not available"
command -v curl >/dev/null 2>&1 || warn "curl is not installed; smoke-test.sh needs it"

if command -v getent >/dev/null 2>&1; then
  getent hosts "$OPENWEBUI_HOST" >/dev/null 2>&1 || fail "DNS does not resolve for $OPENWEBUI_HOST"
  info "DNS resolves for $OPENWEBUI_HOST"
else
  warn "getent not available; DNS check skipped"
fi

if ss -tulpen 2>/dev/null | grep -E ':(80|443)[[:space:]]' >/dev/null 2>&1; then
  warn "Ports 80/443 already have listeners. Check conflicts before compose up."
else
  info "No local listeners detected on 80/443"
fi

info "preflight complete"
