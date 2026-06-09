# Bootstrap Docker On Ubuntu 24.04

## Назначение

Документ описывает безопасный bootstrap Docker Engine и Docker Compose plugin на Ubuntu 24.04 LTS перед deploy OpenWebUI PRD-0.

Источник команд: Docker official docs for Ubuntu: https://docs.docker.com/engine/install/ubuntu/

## Preconditions

- Есть SSH-доступ к серверу.
- ОС: Ubuntu 24.04 LTS.
- Команды выполняются пользователем с `sudo` или `root`.
- Нет требования сохранять существующие Docker workloads. Если Docker уже используется, остановиться и отдельно проверить impact.

## 1. Проверить ОС

```bash
cat /etc/os-release
uname -a
```

Ожидаемо: Ubuntu Noble 24.04 LTS.

## 2. Удалить конфликтующие пакеты

Docker docs рекомендует удалить неофициальные или конфликтующие пакеты перед установкой Docker Engine из официального apt repository:

```bash
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)
```

Если `apt` сообщает, что таких пакетов нет, это нормально.

## 3. Добавить официальный Docker apt repository

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
```

## 4. Установить Docker Engine и Compose plugin

```bash
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 5. Проверить установку

```bash
sudo systemctl status docker --no-pager
docker --version
docker compose version
sudo docker run hello-world
```

Если Docker не запущен:

```bash
sudo systemctl start docker
```

## 6. После bootstrap

Вернуться к [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md).

Перед запуском OpenWebUI должны быть выполнены:

```bash
bash scripts/preflight.sh
bash scripts/network-hardening-check.sh
```

Если репозиторий еще не склонирован, сначала выполнить host hardening по [HOST_HARDENING_RUNBOOK.md](HOST_HARDENING_RUNBOOK.md), затем после clone повторить read-only check из `scripts/network-hardening-check.sh`.
