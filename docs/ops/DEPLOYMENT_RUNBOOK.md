# Deployment Runbook

## 1. Подготовить DNS

Проверить, что `gpt.alpha-soft.ru` указывает на целевой public IPv4:

```bash
dig +short gpt.alpha-soft.ru
```

## 2. Зайти на сервер

```bash
ssh root@<server>
```

Точный endpoint хранить локально, не в Git.

## 3. Установить Docker

Если Docker отсутствует, установить Docker Engine и Docker Compose plugin по актуальной инструкции провайдера/дистрибутива.

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
curl -I https://gpt.alpha-soft.ru
```

## 9. Создать администратора и пользователей

Если заданы `WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD`, admin должен быть создан на первом запуске. После входа администратора создать или активировать 3-4 пользователей через Admin UI.

## 10. Проверить LLM

Администратор или тестовый пользователь задает простой рабочий вопрос. Ожидаемо: модель отвечает, ответ сохраняется в истории.

## 11. Проверить persistence

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml restart openwebui
```

После restart войти снова и проверить, что история чата сохранилась.

## 12. Сделать backup

```bash
bash scripts/backup.sh
```
