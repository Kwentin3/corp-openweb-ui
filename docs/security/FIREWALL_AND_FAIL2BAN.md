# Firewall And Fail2ban

## Назначение

PRD-0 публикует OpenWebUI в интернет, поэтому минимальный host hardening обязателен до фактического deploy.

В scope входят только:

- UFW firewall;
- fail2ban для SSH;
- проверка public ports.

Не входят WAF, SIEM, DLP, IDS/IPS, корпоративный аудит и сложные политики доступа.

## Public perimeter

Ожидаемые публичные порты:

| Port | Purpose |
| --- | --- |
| `22/tcp` | SSH admin access |
| `80/tcp` | HTTP redirect and Let's Encrypt HTTP challenge |
| `443/tcp` | HTTPS OpenWebUI through Traefik |

OpenWebUI не должен публиковать свой порт напрямую наружу.

## Docker/UFW caveat

Docker может управлять iptables и публиковать порты в обход ожидаемой UFW-модели. Поэтому UFW не считается единственной границей защиты.

В PRD-0 запрещено публиковать наружу что-либо, кроме:

- SSH `22/tcp`;
- Traefik `80/tcp`;
- Traefik `443/tcp`.

Если включен host-local HTTP-to-SOCKS bridge для provider egress, его port должен быть доступен только внутри host/Docker boundary. Для текущего deployment это узкое правило UFW от Docker subnet к Docker gateway port `8118/tcp`, без public allow для `Anywhere`.

После `docker compose up -d` обязательна проверка реальных listeners через `ss` и:

```bash
bash scripts/network-hardening-check.sh --strict
```

## UFW target state

- UFW установлен.
- UFW active.
- Default incoming: deny.
- Default outgoing: allow.
- `22/tcp` разрешен до включения firewall.
- `80/tcp` разрешен для Traefik и Let's Encrypt HTTP challenge.
- `443/tcp` разрешен для HTTPS.
- Internal provider proxy bridge, если используется, разрешен только от Docker subnet к Docker gateway.

Порядок важен: не включать firewall до проверки, что SSH разрешен.

## Fail2ban target state

- fail2ban установлен.
- systemd service active.
- `sshd` jail enabled.
- Операторский текущий IP не заблокирован.
- Есть понятная команда для просмотра статуса и снятия ошибочного бана.

## Проверки

Read-only проверка из репозитория:

```bash
bash scripts/network-hardening-check.sh
```

Строгая проверка после deploy:

```bash
bash scripts/network-hardening-check.sh --strict
```

Скрипт предупреждает, если:

- UFW отсутствует или inactive;
- UFW не показывает правила для `22/tcp`, `80/tcp`, `443/tcp`;
- fail2ban отсутствует или inactive;
- `sshd` jail не виден;
- публичные listeners отличаются от ожидаемых.

Скрипт не меняет firewall и не должен использоваться как замена runbook.

В режиме `--strict` скрипт завершится с non-zero exit code, если есть warnings. До запуска Traefik использовать нестрогий режим, потому что `80/443` могут еще не слушаться.

## Recovery commands

Проверить UFW:

```bash
sudo ufw status verbose
sudo ufw status numbered
```

Проверить fail2ban:

```bash
sudo fail2ban-client ping
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

Посмотреть логи:

```bash
sudo journalctl -u fail2ban -n 100 --no-pager
sudo journalctl -u ssh -n 100 --no-pager
```

Снять ошибочный бан:

```bash
sudo fail2ban-client set sshd unbanip <operator-public-ip>
```

`<operator-public-ip>` не коммитить в репозиторий.

## Sources

- Ubuntu firewall docs: https://documentation.ubuntu.com/server/how-to/security/firewalls/
- Ubuntu UFW community docs: https://help.ubuntu.com/community/UFW
- Ubuntu fail2ban-client manpage: https://manpages.ubuntu.com/manpages/jammy/man1/fail2ban-client.1.html
