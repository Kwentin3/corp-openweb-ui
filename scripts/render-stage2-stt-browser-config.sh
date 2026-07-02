#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"
OUTPUT_FILE="${2:-$ROOT_DIR/deploy/openwebui-static/stage2-stt-normalization.json}"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[ -f "$ENV_FILE" ] || fail ".env not found: $ENV_FILE"
command -v python3 >/dev/null 2>&1 || fail "python3 is required to render Stage 2 STT browser config"

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PYTHONPATH="$ROOT_DIR/services/stage2-stt${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m stage2_stt.browser_config "$OUTPUT_FILE"

printf 'rendered_stage2_stt_browser_config=%s\n' "$OUTPUT_FILE"
