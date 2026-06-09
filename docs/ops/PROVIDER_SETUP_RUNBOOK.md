# Provider Setup Runbook

## Назначение

Runbook описывает подключение OpenAI и Gemini штатными средствами OpenWebUI.

## Preconditions

- OpenWebUI доступен по `https://gpt.alpha-soft.ru`.
- Администратор может войти в Admin UI.
- Решено, какой provider является primary через `.env`.
- Есть OpenAI API key и Gemini API key.
- Проверены billing, quota и region/project restrictions для обоих провайдеров.
- Выбраны точные model id или принято решение оставить model filter пустым до ручной проверки.

## 1. Primary provider через `.env`

Открыть server-local `.env` на сервере.

OpenAI primary:

```env
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=<openai-api-key>
DEFAULT_MODELS=
```

Gemini primary:

```env
OPENAI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_API_KEY=<gemini-api-key>
DEFAULT_MODELS=
```

Не коммитить `.env`. После изменения:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Если OpenWebUI уже запускался, часть настроек могла сохраниться в persistent config. В таком случае проверить Connections в Admin UI и исправить provider там.

## 2. Secondary provider через Admin UI

1. Войти администратором.
2. Открыть Admin Settings.
3. Открыть Connections.
4. В секции OpenAI/OpenAI-compatible connection выбрать manage/add connection.
5. Ввести base URL:
   - OpenAI: `https://api.openai.com/v1`;
   - Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`.
6. Ввести API key.
7. При необходимости заполнить Model IDs точными model id, выбранными оператором.
8. Сохранить connection.
9. Запустить проверку connection в UI или открыть список моделей.

Для Gemini не использовать trailing slash в этом runbook. Google SDK examples показывают slash в base URL, но OpenWebUI connection URL в PRD-0 нормализован без slash.

## 3. Проверить OpenAI

Проверить:

- connection сохраняется;
- список моделей загружается или выбранный model id доступен;
- тестовый чат получает ответ от OpenAI;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить API key;
- проверить billing/quota;
- проверить exact model id;
- проверить, что base URL указан как `https://api.openai.com/v1`;
- посмотреть логи OpenWebUI:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```

## 4. Проверить Gemini

Проверить:

- connection сохраняется;
- список моделей загружается или выбранный model id доступен;
- тестовый чат получает ответ от Gemini;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить Gemini API key;
- проверить Google Cloud/project billing, quota и региональные ограничения;
- проверить exact model id;
- проверить, что base URL указан как `https://generativelanguage.googleapis.com/v1beta/openai`;
- посмотреть логи OpenWebUI.

## 5. Acceptance evidence

В приватном deployment note зафиксировать без секретов:

- какой provider выбран primary;
- какой provider добавлен secondary;
- какие model id выбраны;
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
- OpenAI API reference: https://platform.openai.com/docs/api-reference/chat/create
