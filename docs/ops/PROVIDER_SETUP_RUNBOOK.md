# Provider Setup Runbook

## Назначение

Runbook описывает подключение OpenAI и Gemini штатными средствами OpenWebUI.

## Preconditions

- OpenWebUI доступен по `https://gpt.alpha-soft.ru`.
- Администратор может войти в Admin UI.
- Primary provider через `.env`: OpenAI.
- Secondary provider через Admin UI: Gemini.
- Есть OpenAI API key и Gemini API key.
- Проверены billing, quota и region/project restrictions для обоих провайдеров.
- OpenAI model id: `gpt-5.4-mini`.
- Gemini model id: `gemini-3.5-flash`.

## 1. Primary provider через `.env`

Открыть server-local `.env` на сервере.

OpenAI primary:

```env
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=<openai-api-key>
DEFAULT_MODELS=gpt-5.4-mini
```

Gemini primary является допустимым fallback-вариантом, но не выбран для текущего PRD-0 `.env.example`:

```env
OPENAI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_API_KEY=<gemini-api-key>
DEFAULT_MODELS=gemini-3.5-flash
```

Не коммитить `.env`. После изменения:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Если OpenWebUI уже запускался, часть настроек могла сохраниться в persistent config. В таком случае проверить Connections в Admin UI и исправить provider там.

Важно: OpenAI и Gemini уже выбраны как provider set. Admin UI не является blocker по выбору provider; это штатное место для ввода second provider connection и Gemini API key без multi-value env.

Если OpenAI API блокирует регион исходящего IP, можно задать outbound proxy для OpenWebUI без fork/frontend changes:

```env
OPENWEBUI_OUTBOUND_PROXY=socks5h://user:password@proxy-host:1080
OPENWEBUI_NO_PROXY=localhost,127.0.0.1,::1,openwebui,traefik,openwebui-traefik,gpt.alpha-soft.ru
```

`socks5h://` предпочтителен для SOCKS5, потому что DNS provider API тоже идет через proxy. Реальные proxy credentials хранить только в server-local `.env`/password manager.

## 2. Secondary provider через Admin UI

1. Войти администратором.
2. Открыть Admin Settings.
3. Открыть Connections.
4. В секции OpenAI/OpenAI-compatible connection выбрать manage/add connection.
5. Ввести base URL:
   - OpenAI: `https://api.openai.com/v1`;
   - Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`.
6. Ввести API key.
7. Для Gemini secondary указать Model IDs: `gemini-3.5-flash`.
8. Сохранить connection.
9. Запустить проверку connection в UI или открыть список моделей.

Для Gemini не использовать trailing slash в этом runbook. Google SDK examples показывают slash в base URL, но OpenWebUI connection URL в PRD-0 нормализован без slash.

Если оператор намеренно тестирует Gemini 3 Flash Preview, использовать точный model id `gemini-3-flash-preview`. Строка `gemini-3-flash` без `preview` не является выбранным exact model id в PRD-0.

## 3. Проверить OpenAI

Проверить:

- connection сохраняется;
- список моделей загружается или `gpt-5.4-mini` доступен;
- тестовый чат получает ответ от OpenAI;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить API key;
- проверить billing/quota;
- проверить доступ к `gpt-5.4-mini`;
- проверить, что base URL указан как `https://api.openai.com/v1`;
- посмотреть логи OpenWebUI:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```

## 4. Проверить Gemini

Проверить:

- connection сохраняется;
- список моделей загружается или `gemini-3.5-flash` доступен;
- тестовый чат получает ответ от Gemini;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить Gemini API key;
- проверить Google Cloud/project billing, quota и региональные ограничения;
- проверить доступ к `gemini-3.5-flash`;
- проверить, что base URL указан как `https://generativelanguage.googleapis.com/v1beta/openai`;
- посмотреть логи OpenWebUI.

## 5. Acceptance evidence

В приватном deployment note зафиксировать без секретов:

- какой provider выбран primary;
- какой provider добавлен secondary;
- model ids: OpenAI `gpt-5.4-mini`, Gemini `gemini-3.5-flash`;
- дата и результат тестового ответа OpenAI;
- дата и результат тестового ответа Gemini;
- если один provider не проверен, почему он pending и кто владеет решением.

## Non-goals

Не настраивать в PRD-0:

- LiteLLM;
- model gateway;
- routing/fallback;
- per-user limits;
- budgets;
- provider-specific proxy.

## Sources

- OpenWebUI OpenAI-compatible connection docs: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenWebUI Starting with OpenAI: https://docs.openwebui.com/getting-started/quick-start/starting-with-openai/
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
- Gemini 3.5 Flash model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- OpenAI model catalog: https://developers.openai.com/api/docs/models/gpt
