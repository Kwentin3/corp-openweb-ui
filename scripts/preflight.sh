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
[ -n "${WEBUI_SECRET_KEY:-}" ] || fail "WEBUI_SECRET_KEY is empty"
[ -n "${CORS_ALLOW_ORIGIN:-}" ] || fail "CORS_ALLOW_ORIGIN is empty"
[ -n "${WEBUI_NAME:-}" ] || fail "WEBUI_NAME is empty"
[ -n "${WEBUI_BANNERS:-}" ] || fail "WEBUI_BANNERS is empty"

OPENAI_ENDPOINT="https://api.openai.com/v1"
GEMINI_ENDPOINT="https://generativelanguage.googleapis.com/v1beta/openai"

case "${LETSENCRYPT_EMAIL}:${OPENAI_API_KEY}:${WEBUI_ADMIN_EMAIL:-}:${WEBUI_ADMIN_PASSWORD:-}:${WEBUI_SECRET_KEY}:${CORS_ALLOW_ORIGIN}:${DEFAULT_MODELS:-}" in
  *example.com*|*replace-with*)
    fail ".env still contains placeholder values"
    ;;
esac

case "$CORS_ALLOW_ORIGIN" in
  "https://${OPENWEBUI_HOST}"*) info "CORS_ALLOW_ORIGIN includes primary HTTPS origin" ;;
  *) warn "CORS_ALLOW_ORIGIN does not start with https://${OPENWEBUI_HOST}" ;;
esac

case "$WEBUI_BANNERS" in
  *'"type":"warning"'*|*'"type": "warning"'*) info "WEBUI_BANNERS contains a warning banner" ;;
  *) warn "WEBUI_BANNERS does not clearly contain a warning banner" ;;
esac

case "$OPENAI_API_BASE_URL" in
  "$OPENAI_ENDPOINT")
    info "primary provider endpoint matches OpenAI"
    ;;
  "$GEMINI_ENDPOINT")
    info "primary provider endpoint matches Gemini OpenAI compatibility"
    ;;
  "$GEMINI_ENDPOINT/")
    warn "Gemini endpoint has trailing slash; PRD-0 runbook uses https://generativelanguage.googleapis.com/v1beta/openai"
    ;;
  https://*)
    warn "primary provider endpoint is not one of the two PRD-0 endpoints"
    ;;
  *)
    fail "OPENAI_API_BASE_URL must be an https URL"
    ;;
esac

if [ -n "${BACKUP_RETENTION_DAYS:-}" ]; then
  case "$BACKUP_RETENTION_DAYS" in
    *[!0-9]*)
      fail "BACKUP_RETENTION_DAYS must be a number of days"
      ;;
  esac

  if [ "$BACKUP_RETENTION_DAYS" -lt 1 ]; then
    fail "BACKUP_RETENTION_DAYS must be 1 or greater"
  fi

  info "backup retention is ${BACKUP_RETENTION_DAYS} days"
fi

if [ -n "${OPENWEBUI_OUTBOUND_PROXY:-}" ]; then
  case "$OPENWEBUI_OUTBOUND_PROXY" in
    socks5h://*|socks5://*|http://*|https://*)
      info "outbound proxy is configured"
      ;;
    *)
      fail "OPENWEBUI_OUTBOUND_PROXY must start with socks5h://, socks5://, http:// or https://"
      ;;
  esac
fi

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
