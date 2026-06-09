#!/usr/bin/env bash
set -u

WARNINGS=0

ok() {
  printf 'OK: %s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1" >&2
  WARNINGS=$((WARNINGS + 1))
}

run_readonly() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -n "$@" 2>/dev/null || "$@" 2>/dev/null || true
  else
    "$@" 2>/dev/null || true
  fi
}

check_ufw() {
  if ! command -v ufw >/dev/null 2>&1; then
    warn "ufw is not installed"
    return
  fi

  local status
  status="$(run_readonly ufw status verbose)"
  if [ -z "$status" ]; then
    warn "ufw status is unavailable; run as sudo-capable user"
    return
  fi

  if printf '%s\n' "$status" | grep -qi '^Status: active'; then
    ok "ufw is active"
  else
    warn "ufw is installed but not active"
  fi

  if printf '%s\n' "$status" | grep -Eiq 'Default:.*deny \(incoming\).*allow \(outgoing\)'; then
    ok "ufw default policy is deny incoming / allow outgoing"
  else
    warn "ufw default policy is not clearly deny incoming / allow outgoing"
  fi

  for port in 22 80 443; do
    if printf '%s\n' "$status" | grep -Eiq "(^|[[:space:]])${port}/tcp([[:space:]]|$)"; then
      ok "ufw has rule for ${port}/tcp"
    else
      warn "ufw rule for ${port}/tcp is not visible"
    fi
  done
}

check_fail2ban() {
  if ! command -v fail2ban-client >/dev/null 2>&1; then
    warn "fail2ban-client is not installed"
    return
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
      ok "fail2ban service is active"
    else
      warn "fail2ban service is not active"
    fi
  else
    warn "systemctl is not available; fail2ban service state skipped"
  fi

  local status
  status="$(run_readonly fail2ban-client status)"
  if [ -z "$status" ]; then
    warn "fail2ban status is unavailable; run as sudo-capable user"
    return
  fi

  if printf '%s\n' "$status" | grep -qi 'sshd'; then
    ok "fail2ban reports sshd jail"
  else
    warn "fail2ban sshd jail is not visible"
  fi

  local sshd_status
  sshd_status="$(run_readonly fail2ban-client status sshd)"
  if printf '%s\n' "$sshd_status" | grep -Eiq 'Status for the jail: sshd|Currently banned|Total failed'; then
    ok "fail2ban sshd jail status is readable"
  else
    warn "fail2ban sshd jail status is not readable"
  fi
}

has_public_listener() {
  local port="$1"
  printf '%s\n' "$LISTENERS" | awk -v p="$port" '
    {
      local_addr = $5
      if (local_addr ~ ("^0\\.0\\.0\\.0:" p "$") ||
          local_addr ~ ("^\\[::\\]:" p "$") ||
          local_addr ~ ("^\\*:" p "$")) {
        found = 1
      }
    }
    END { exit found ? 0 : 1 }
  '
}

check_listeners() {
  if ! command -v ss >/dev/null 2>&1; then
    warn "ss is not installed; listener check skipped"
    return
  fi

  LISTENERS="$(ss -H -tuln 2>/dev/null || true)"
  if [ -z "$LISTENERS" ]; then
    warn "no listening sockets reported by ss"
    return
  fi

  if has_public_listener 22; then
    ok "public listener for 22/tcp is present"
  else
    warn "public listener for 22/tcp is not visible; verify SSH access"
  fi

  for port in 80 443; do
    if has_public_listener "$port"; then
      ok "public listener for ${port}/tcp is present"
    else
      warn "public listener for ${port}/tcp is not visible; acceptable before Traefik, blocker after deploy"
    fi
  done

  local unexpected
  unexpected="$(printf '%s\n' "$LISTENERS" | awk '
    {
      local_addr = $5
      port = local_addr
      sub(/^.*:/, "", port)
      gsub(/[^0-9].*$/, "", port)
      if ((local_addr ~ /^0\.0\.0\.0:/ || local_addr ~ /^\[::\]:/ || local_addr ~ /^\*:/) &&
          port !~ /^(22|80|443)$/) {
        print local_addr
      }
    }
  ' | sort -u)"

  if [ -n "$unexpected" ]; then
    warn "unexpected public listeners: $(printf '%s' "$unexpected" | tr '\n' ' ')"
  else
    ok "no unexpected public listeners detected by ss"
  fi
}

check_ufw
check_fail2ban
check_listeners

if [ "$WARNINGS" -eq 0 ]; then
  ok "network hardening check complete"
else
  printf 'WARNINGS=%s\n' "$WARNINGS" >&2
fi

exit 0
