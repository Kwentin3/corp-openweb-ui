# Provider Connections Plan

## Назначение

Документ фиксирует, как в PRD-0 подключаются OpenAI и Gemini штатными средствами OpenWebUI.

## Решение PRD-0

- Два допустимых provider: OpenAI и Gemini.
- Подключение выполняется средствами OpenWebUI.
- Primary provider задается через server-local `.env`: OpenAI.
- Secondary provider добавляется вручную через OpenWebUI Admin UI: Gemini.
- `OPENAI_API_BASE_URLS` и `OPENAI_API_KEYS` не используются в skeleton PRD-0.

Такой вариант проще проверить и меньше зависит от порядка multi-value env. Это важно, потому что OpenWebUI часть настроек хранит как persistent config во внутренней базе.

Это не blocker по выбору provider: OpenAI и Gemini уже выбраны. Admin UI используется только потому, что second provider key/connection хранится штатными средствами OpenWebUI после входа администратора.

## Контракт endpoints

| Provider | OpenWebUI connection URL | Key requirement | Model requirement |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | OpenAI API key с доступом к выбранной модели | `gpt-5.4-mini` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | Gemini API key, billing/quota/region проверены | `gemini-3.5-flash` |

Для Gemini использовать endpoint без trailing slash в OpenWebUI. Google SDK examples могут показывать slash в конце base URL; для этого репозитория runbook нормализует значение без slash и не оставляет альтернатив в deployment path.

Если нужен именно Gemini 3 Flash Preview, точный model id - `gemini-3-flash-preview`. Строка `gemini-3-flash` без suffix не используется.

## Primary/secondary варианты

Вариант по умолчанию для skeleton:

- Primary through `.env`: OpenAI.
- Secondary through Admin UI: Gemini.

Допустимый обратный вариант:

- Primary through `.env`: Gemini.
- Secondary through Admin UI: OpenAI.

Выбор фиксируется в [../ops/DEPLOYMENT_DECISIONS.md](../ops/DEPLOYMENT_DECISIONS.md) до deploy.

## `.env` mapping

OpenAI primary:

```env
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=<openai-api-key>
DEFAULT_MODELS=gpt-5.4-mini
```

Gemini primary remains допустимым fallback-вариантом, но не выбран для текущего `.env.example`:

```env
OPENAI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_API_KEY=<gemini-api-key>
DEFAULT_MODELS=gemini-3.5-flash
```

`DEFAULT_MODELS` можно оставить пустым, если оператор хочет сначала проверить список моделей в UI. Не подставлять искусственный placeholder для model id.

## Admin UI secondary provider

Secondary provider добавляется после входа администратора:

1. Открыть Admin Settings.
2. Открыть Connections.
3. В секции OpenAI-compatible/OpenAI connection добавить provider.
4. Указать base URL из таблицы выше.
5. Указать API key.
6. Указать Model IDs: `gemini-3.5-flash` для текущего Gemini secondary path.
7. Сохранить и проверить connection.

OpenWebUI проверяет OpenAI-compatible connection через endpoint моделей. Для Gemini OpenAI compatibility OpenWebUI documentation указывает, что auto-detection работает.

## Операторские проверки

До пилота оператор подтверждает:

- OpenAI API key существует и не просрочен;
- Gemini API key существует и не просрочен;
- billing включен там, где это требуется;
- quota достаточна для 3-4 пользователей;
- region/project restrictions не блокируют запросы;
- OpenAI model id `gpt-5.4-mini` доступен на API key;
- Gemini model id `gemini-3.5-flash` доступен на API key;
- хотя бы один provider отвечает в пользовательском чате;
- второй provider либо отвечает, либо явно отмечен pending только по API key/quota/billing/region.

## Non-goals

Не добавлять в PRD-0:

- LiteLLM;
- model gateway;
- provider routing;
- budget enforcement;
- per-user provider limits;
- большую матрицу моделей;
- отдельный сервис для API keys.

## Sources

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI OpenAI-compatible connections: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenWebUI Starting with OpenAI: https://docs.openwebui.com/getting-started/quick-start/starting-with-openai/
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
- Gemini 3.5 Flash model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- OpenAI model catalog: https://developers.openai.com/api/docs/models/gpt
