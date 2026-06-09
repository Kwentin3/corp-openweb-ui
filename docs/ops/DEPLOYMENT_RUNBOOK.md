# Deployment Runbook

## 1. Подготовить DNS

Проверить, что `gpt.alpha-soft.ru` указывает на целевой public IPv4:

```bash
dig +short gpt.alpha-soft.ru
```

## 2. Зайти на сервер

```bash
ssh <deploy-user>@<server>
```

Точный endpoint хранить локально, не в Git.

## 3. Установить Docker

Если Docker отсутствует, выполнить [BOOTSTRAP_DOCKER_UBUNTU.md](BOOTSTRAP_DOCKER_UBUNTU.md). Для текущего target preflight показал Ubuntu 24.04 LTS и отсутствие Docker/Compose.

Проверить:

```bash
docker --version
docker compose version
```

## 4. Склонировать репозиторий

```bash
mkdir -p /opt/openwebui-prd0
cd /opt/openwebui-prd0
git clone https://github.com/Kwentin3/corp-openweb-ui.git .
```

## 5. Создать `.env`

```bash
cp .env.example .env
chmod 600 .env
vi .env
```

Заполнить реальные значения. Не коммитить `.env`.

Сгенерировать стабильный `WEBUI_SECRET_KEY`:

```bash
openssl rand -hex 32
```

До запуска должны быть приняты решения из [DEPLOYMENT_DECISIONS.md](DEPLOYMENT_DECISIONS.md): API-провайдер, model id, email Let's Encrypt, image tag, backup retention и первый администратор.

## 6. Выполнить preflight

```bash
bash scripts/preflight.sh
```

## 7. Поднять сервисы

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml pull
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

## 8. Проверить HTTPS

```bash
curl -I http://gpt.alpha-soft.ru
bash scripts/smoke-test.sh --strict-tls
```

## 9. Создать администратора и пользователей

Если база свежая и заданы `WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD`, OpenWebUI создает admin на первом запуске и отключает signup. Если admin bootstrap не сработал или база уже содержит пользователей, создать первого администратора через UI/recovery-процедуру OpenWebUI и зафиксировать это в deployment notes.

После входа администратора создать или активировать 3-4 пользователей через Admin UI. Оставить signup отключенным или `DEFAULT_USER_ROLE=pending`.

## 10. Проверить LLM

Администратор или тестовый пользователь задает простой рабочий вопрос. Ожидаемо: модель отвечает, ответ сохраняется в истории.

## 11. Проверить persistence

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml restart openwebui
bash scripts/smoke-test.sh --strict-tls
```

После restart войти снова и проверить, что история чата сохранилась.

## 12. Сделать backup

```bash
bash scripts/backup.sh
```
