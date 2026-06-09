# Scope And Non-Goals

## Scope PRD-0

Входит:

- OpenWebUI;
- Docker и Docker Compose;
- Traefik;
- HTTPS;
- домен `gpt.alpha-soft.ru`;
- OpenAI и Gemini как API-провайдеры;
- один primary provider через `.env`;
- второй provider через Admin UI;
- мягкое имя инстанса через `WEBUI_NAME`;
- warning banner через `WEBUI_BANNERS`;
- закрытая регистрация и базовые настройки доступа;
- один администратор;
- 3-4 пользователя;
- persistent volume для данных OpenWebUI;
- UFW firewall;
- fail2ban для SSH;
- минимальный backup;
- runbook;
- smoke и acceptance checks.

## Non-goals

В PRD-0 явно не входят:

- LiteLLM;
- model gateway;
- provider routing, fallback, budgets и per-user limits;
- несколько моделей как пользовательская продуктовая функция;
- web-поиск;
- SSO/OIDC;
- корпоративный admin dashboard;
- роли РО и подчиненных;
- Word/PDF/Excel skills;
- plugins, tools/functions;
- fork OpenWebUI;
- изменение логотипа;
- изменение frontend-кода или кастомный frontend;
- транскрибация;
- сложный RAG;
- memory/context layer;
- интеграции с 1С/CRM;
- кастомный интерфейс;
- white-label или смена брендинга OpenWebUI;
- WAF, SIEM, DLP и корпоративный security audit.

## Принцип удержания scope

Если новая функция не нужна для проверки "3-4 человека могут пользоваться единым LLM-чатом", она не входит в PRD-0.
