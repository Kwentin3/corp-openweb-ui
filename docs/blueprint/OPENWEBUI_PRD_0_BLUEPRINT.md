# OpenWebUI PRD-0 Blueprint

## Назначение

Blueprint описывает минимальный запуск OpenWebUI для фазы смотрин PRD-0: один домен, один OpenWebUI, один LLM API-провайдер, один администратор и 3-4 пользователя.

Цель blueprint - дать безопасную инженерную основу для развертывания, не расширяя scope до AI-платформы.

## Домены и ответственность

- Ingress: Traefik принимает HTTP/HTTPS и выпускает TLS-сертификат.
- UI/runtime: OpenWebUI обслуживает пользователей, авторизацию, историю чатов и подключение к LLM API.
- Persistence: Docker volume `openwebui_data` хранит данные OpenWebUI.
- Secrets: server-local `.env` хранит API-ключи, admin-пароль и email для Let's Encrypt.
- Backup: скрипт сохраняет volume и локальный `.env` в server-local backup directory.
- Pilot operations: администратор создает 3-4 пользователей и собирает обратную связь.

## Границы

В PRD-0 нет Hermes, LiteLLM, SSO, web-поиска, RAG, memory layer, document tools, корпоративного dashboard и white-label.

## Контейнеры

Минимально нужны два контейнера:

- `traefik` - reverse proxy, HTTPS, ACME HTTP challenge.
- `openwebui` - приложение OpenWebUI.

Дополнительные runtime-компоненты не добавляются.

## Поток запроса

```text
browser
  -> https://gpt.alpha-soft.ru
  -> Traefik :443
  -> openwebui:8080
  -> external OpenAI-compatible LLM API
```

HTTP `:80` нужен только для редиректа на HTTPS и ACME HTTP challenge.

## Volumes

- `openwebui_data` -> `/app/backend/data` внутри OpenWebUI.
- `traefik_letsencrypt` -> `/letsencrypt` внутри Traefik.

## Конфигурация

- Коммитится только `.env.example`.
- Реальный `.env` создается на сервере вручную и не попадает в Git.
- Compose-файл хранится в `compose/openwebui.compose.yml`.
- Скрипты preflight, backup и smoke хранятся в `scripts/`.

## Проверка готовности

Готовность подтверждается не фактом запуска контейнеров, а acceptance checks:

- домен открывается по HTTPS;
- администратор входит;
- созданы 3-4 пользователя;
- пользователь получает ответ модели;
- история чата сохраняется после restart;
- `.env` не попал в Git;
- backup создается и описан restore path.

## Риски

- На сервере preflight показал отсутствие Docker и Traefik: перед deploy нужен bootstrap.
- Публичный или неизвестный GitHub-репозиторий не должен содержать SSH endpoint, API-ключи и реальные пароли.
- OpenWebUI часть настроек сохраняет в persistent config, поэтому изменения env после первого запуска могут не примениться без действий через Admin UI.

## Ссылки

- PRD: [../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Architecture overview: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- Non-goals: [SCOPE_AND_NON_GOALS.md](SCOPE_AND_NON_GOALS.md)
