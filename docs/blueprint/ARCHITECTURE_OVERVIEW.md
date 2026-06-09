# Architecture Overview

## Схема

```text
internet user
  -> gpt.alpha-soft.ru
  -> public 80/443
  -> Traefik
  -> OpenWebUI
  -> LLM provider API
```

## Runtime boundary

OpenWebUI владеет:

- web-интерфейсом;
- локальными пользователями;
- пользовательскими чатами;
- подключением к модели через OpenAI-compatible API;
- настройками, которые сохраняются в persistent config.

Traefik владеет:

- входящим HTTP/HTTPS;
- TLS-сертификатом;
- редиректом HTTP -> HTTPS;
- маршрутом на контейнер OpenWebUI.

## Data boundary

Данные OpenWebUI не хранятся в bind mount внутри репозитория. Для PRD-0 используется named volume `openwebui_data`.

Секреты не являются частью data volume. Они хранятся в server-local `.env` и backup-копии вне Git.

## Network boundary

OpenWebUI не публикует порт напрямую наружу. Наружу открыты только `80` и `443` контейнера Traefik.

Внутренний доступ:

- Traefik видит OpenWebUI по Docker network.
- OpenWebUI ходит наружу к LLM API-провайдеру.

## Deployment boundary

Репозиторий содержит skeleton и runbook. Фактическое развертывание требует ручного заполнения `.env` и установки Docker/Compose на сервере.

## Deferred work

Отложены SSO, LiteLLM, несколько провайдеров, gateway, observability stack, корпоративный RBAC, RAG и интеграции.
