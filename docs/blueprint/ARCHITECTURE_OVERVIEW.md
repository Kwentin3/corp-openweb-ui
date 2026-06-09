# Architecture Overview

## Схема

```text
internet user
  -> gpt.alpha-soft.ru
  -> public 80/443
  -> Traefik
  -> OpenWebUI
  -> OpenAI API
  -> Gemini OpenAI-compatible API
```

## Runtime boundary

OpenWebUI владеет:

- web-интерфейсом;
- локальными пользователями;
- пользовательскими чатами;
- подключениями к OpenAI-compatible API;
- настройками, которые сохраняются в persistent config.

Traefik владеет:

- входящим HTTP/HTTPS;
- TLS-сертификатом;
- редиректом HTTP -> HTTPS;
- маршрутом на контейнер OpenWebUI.

Host OS владеет:

- UFW firewall;
- fail2ban для SSH;
- public listeners `22/tcp`, `80/tcp`, `443/tcp`.

## Data boundary

Данные OpenWebUI не хранятся в bind mount внутри репозитория. Для PRD-0 используется named volume `openwebui_data`.

Секреты не являются частью Git. Primary provider key хранится в server-local `.env`; secondary provider key, введенный через Admin UI, может попасть в persistent data и backup volume.

## Network boundary

OpenWebUI не публикует порт напрямую наружу. Наружу открыты только:

- `22/tcp` для SSH;
- `80/tcp` для HTTP redirect и ACME HTTP challenge;
- `443/tcp` для HTTPS.

Внутренний доступ:

- Traefik видит OpenWebUI по Docker network.
- OpenWebUI ходит наружу к OpenAI и Gemini API.

## Deployment boundary

Репозиторий содержит skeleton и runbook. Фактическое развертывание требует ручного заполнения `.env`, установки Docker/Compose, host hardening и закрытия operator decisions.

## Deferred work

Отложены SSO, LiteLLM, model gateway, provider routing/budgets, observability stack, корпоративный RBAC, RAG и интеграции.
