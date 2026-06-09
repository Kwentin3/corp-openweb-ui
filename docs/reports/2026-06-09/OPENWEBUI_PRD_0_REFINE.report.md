# OpenWebUI PRD-0 Refine Report

Дата: 2026-06-09

## Что проверено

- PRD: `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`.
- `.env.example`, Docker Compose, scripts, runbooks, security и pilot docs.
- GitHub repository visibility: public.
- Коммитимые документы на точный SSH endpoint, public IP и реальные имена участников.
- OpenWebUI env reference, hardening docs, quick start and image guidance.
- Docker official Ubuntu install docs.
- Traefik official Docker provider / ACME docs.
- Google Gemini OpenAI compatibility docs.

## Официальные источники

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI hardening / CORS: https://docs.openwebui.com/getting-started/advanced-topics/hardening/
- OpenWebUI quick start / image pinning: https://docs.openwebui.com/getting-started/quick-start/
- OpenWebUI container image guidance: https://docs.openwebui.com/enterprise/deployment/container-service/
- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Traefik Docker provider: https://doc.traefik.io/traefik/v3.3/providers/docker/
- Traefik ACME resolver: https://doc.traefik.io/traefik/v3.6/reference/install-configuration/tls/certificate-resolvers/acme/
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai

## Найдено

- `.env.example` и compose не задавали `WEBUI_SECRET_KEY`.
- `CORS_ALLOW_ORIGIN` отсутствовал и оставлял риск default `*`/WebSocket origin проблем.
- `DEFAULT_MODELS` содержал искусственный placeholder model id и конфликтовал с preflight, хотя переменная optional.
- Не было Docker bootstrap-документа для Ubuntu 24.04.
- `smoke-test.sh` проверял HTTPS только с `curl -k`.
- `backup.sh` сохранял `traefik_letsencrypt`, но restore-документация не описывала этот volume.
- Admin bootstrap переменные были не подтверждены в документации.
- Public repo содержал реальные имена участников в PRD.
- Выбор API provider/model id был размыт.
- `OPENWEBUI_IMAGE` использовал floating `:main`.

## Исправлено

- Добавлен `WEBUI_SECRET_KEY` в `.env.example`, compose, preflight и docs.
- Добавлен `CORS_ALLOW_ORIGIN=https://gpt.alpha-soft.ru` в `.env.example`, compose, preflight и docs.
- `DEFAULT_MODELS=` теперь пустой optional default; preflight не падает на незаполненный model id.
- Добавлен [../../ops/BOOTSTRAP_DOCKER_UBUNTU.md](../../ops/BOOTSTRAP_DOCKER_UBUNTU.md).
- `scripts/smoke-test.sh` получил режим `--strict-tls`.
- Restore notes теперь описывают оба пути для `traefik_letsencrypt`: перевыпуск сертификата или восстановление volume.
- Admin bootstrap задокументирован как fresh-install-only механизм.
- Реальные имена участников заменены на роли.
- Добавлен [../../ops/DEPLOYMENT_DECISIONS.md](../../ops/DEPLOYMENT_DECISIONS.md).
- OpenWebUI image pinned to `ghcr.io/open-webui/open-webui:v0.9.6`.
- Traefik image updated to `traefik:v3.6`.

## Operator decisions

- Выбрать API provider.
- Выбрать model id.
- Задать рабочий email для Let's Encrypt.
- Подтвердить image tags перед запуском.
- Выбрать первого администратора.
- Задать backup retention.

## Готовность

Пакет готов к отдельной задаче `bootstrap/deploy` после заполнения operator decisions и server-local `.env`.

В рамках refine deploy не выполнялся.

## Валидация

- `git diff --check` прошел без ошибок whitespace; остались только Windows CRLF warnings.
- Shell scripts прошли `bash -n`.
- `compose/openwebui.compose.yml` успешно распарсен как YAML.
- `scripts/smoke-test.sh --help` работает и показывает режим `--strict-tls`.
- `scripts/preflight.sh` корректно падает на `.env.example` placeholders до Docker-check; optional `DEFAULT_MODELS=` не ломает preflight.
- Secret scan коммитимых файлов не нашел явных private key/API key/password/token assignments.
- Public repo scan не нашел точный SSH endpoint, target public IP или реальные имена пилотных участников.
- `local/INFRA_TARGET.local.md` остается ignored через `.gitignore`.

## Следующий шаг

1. Закрыть `docs/ops/DEPLOYMENT_DECISIONS.md`.
2. На сервере выполнить `docs/ops/BOOTSTRAP_DOCKER_UBUNTU.md`.
3. Заполнить `.env`.
4. Выполнить `bash scripts/preflight.sh`.
5. Запускать deploy отдельной командой.
