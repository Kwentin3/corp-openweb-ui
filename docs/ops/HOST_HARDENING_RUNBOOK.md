# Host Hardening Runbook

## Назначение

Runbook задает минимальный host hardening для Ubuntu Server перед deploy OpenWebUI PRD-0.

Не запускать эти команды вслепую на сервере с чужими workloads. Перед включением UFW держать текущую SSH-сессию открытой и проверить, что SSH разрешен.

## Preconditions

- Есть рабочий SSH-доступ.
- Оператор имеет `sudo`.
- Известен текущий SSH port. Если он не `22/tcp`, заменить `22/tcp` на фактический порт в командах и документации deployment note.
- Нет отдельной корпоративной firewall policy, конфликтующей с UFW.

## Docker/UFW caveat

Docker может управлять iptables и публиковать порты в обход ожидаемой UFW-модели. Поэтому UFW не считается единственной границей защиты.

В PRD-0 запрещено публиковать наружу что-либо, кроме SSH `22` и Traefik `80/443`. OpenWebUI должен быть доступен только через Traefik, без прямого public port. Если используется host-local HTTP-to-SOCKS bridge для provider egress, его port должен быть разрешен только от Docker subnet к Docker gateway, не для `Anywhere`.

После `docker compose up -d` обязательно проверить реальные listeners через `ss` и `bash scripts/network-hardening-check.sh --strict`.

## 1. Проверить текущую сеть

```bash
hostnamectl
ss -tulpen
sudo ufw status verbose || true
```

Если уже есть firewall rules, остановиться и понять impact.

## 2. Установить UFW и fail2ban

```bash
sudo apt update
sudo apt install ufw fail2ban
```

## 3. Настроить UFW

Сначала разрешить SSH:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw status verbose
```

Проверить, что правила для `22/tcp`, `80/tcp`, `443/tcp` видны в status.

Затем включить:

```bash
sudo ufw --dry-run enable
sudo ufw enable
sudo ufw status verbose
```

Открыть новую SSH-сессию в отдельном терминале и убедиться, что доступ не потерян.

Если после deploy включается provider proxy bridge, сначала определить Docker subnet/gateway:

```bash
docker network inspect openwebui_web --format '{{json .IPAM.Config}}'
```

Затем добавить только узкое правило. Пример для subnet `172.18.0.0/16`, gateway `172.18.0.1`, bridge port `8118/tcp`:

```bash
sudo ufw allow in on <docker-bridge-interface> proto tcp from 172.18.0.0/16 to 172.18.0.1 port 8118 comment 'OpenWebUI outbound proxy bridge'
```

Не использовать `sudo ufw allow 8118/tcp`.

## 4. Настроить fail2ban для SSH

Создать jail override:

```bash
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled = true
port = ssh
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
ignoreip = 127.0.0.1/8 ::1
EOF
```

Если нужно исключить текущий операторский public IP, добавить его в `ignoreip` локально на сервере. Не коммитить этот IP.

Запустить и проверить:

```bash
sudo systemctl enable --now fail2ban
sudo systemctl status fail2ban --no-pager
sudo fail2ban-client ping
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

## 5. Проверить hardening read-only скриптом

После clone репозитория:

```bash
bash scripts/network-hardening-check.sh
```

До запуска Traefik предупреждение об отсутствии listeners `80/443` допустимо. После `docker compose up -d` эти порты должны слушаться, а строгая проверка должна проходить:

```bash
bash scripts/network-hardening-check.sh --strict
```

## 6. Логи и recovery

Посмотреть логи fail2ban:

```bash
sudo journalctl -u fail2ban -n 100 --no-pager
```

Посмотреть SSH логи:

```bash
sudo journalctl -u ssh -n 100 --no-pager
```

Снять ошибочный бан:

```bash
sudo fail2ban-client set sshd unbanip <operator-public-ip>
```

Временно отключать UFW можно только если есть альтернативный доступ к серверу или подтвержденный SSH allow:

```bash
sudo ufw status numbered
```

## 7. Acceptance evidence

В приватном deployment note зафиксировать:

- `sudo ufw status verbose` без персональных IP;
- `sudo fail2ban-client status sshd`;
- результат `bash scripts/network-hardening-check.sh --strict` после deploy;
- подтверждение, что новая SSH-сессия открывается после включения UFW.

Не фиксировать в публичном Git точный SSH endpoint, public IP, личные IP операторов и реальные имена.

## Sources

- Ubuntu firewall docs: https://documentation.ubuntu.com/server/how-to/security/firewalls/
- Ubuntu UFW community docs: https://help.ubuntu.com/community/UFW
- Ubuntu fail2ban-client manpage: https://manpages.ubuntu.com/manpages/jammy/man1/fail2ban-client.1.html
