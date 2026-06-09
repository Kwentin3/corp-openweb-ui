# Scope And Non-Goals

## Scope PRD-0

Входит:

- OpenWebUI;
- Docker и Docker Compose;
- Traefik;
- HTTPS;
- домен `gpt.alpha-soft.ru`;
- один API-провайдер LLM;
- одна модель по умолчанию;
- один администратор;
- 3-4 пользователя;
- persistent volume для данных OpenWebUI;
- минимальный backup;
- runbook;
- smoke и acceptance checks.

## Non-goals

В PRD-0 явно не входят:

- Hermes;
- LiteLLM;
- model gateway;
- несколько LLM-провайдеров;
- несколько моделей как пользовательская функция;
- web-поиск;
- SSO/OIDC;
- корпоративный admin dashboard;
- роли РО и подчиненных;
- Word/PDF/Excel skills;
- транскрибация;
- сложный RAG;
- memory/context layer;
- интеграции с 1С/CRM;
- кастомный интерфейс;
- white-label или смена брендинга OpenWebUI.

## Принцип удержания scope

Если новая функция не нужна для проверки "3-4 человека могут пользоваться единым LLM-чатом", она не входит в PRD-0.
