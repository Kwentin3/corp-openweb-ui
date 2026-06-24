# Web Search Provider Research

Дата исследования: 2026-06-09.

Stage 2 runtime update: 2026-06-23.

Brave `brave_llm_context` now has a working native OpenWebUI smoke baseline on
the deployed instance. Yandex works as the RU direct API path by
owner/operator confirmation. Private SearXNG works as a native meta-search
comparison path in snippet/bypass mode. This does not change PRD-0 scope; it
updates Stage 2 runtime status.

## Статус для PRD-0

Веб-поиск сейчас остается non-goal PRD-0. Этот документ фиксирует исследование и готовый выбор на случай, если оператор отдельно решит расширить scope.

Включать веб-поиск без отдельного решения не нужно: это добавляет внешний API, расходы, новые ключи, сетевую диагностику и риск утечки пользовательских запросов в поисковый provider.

## Короткое решение

Для дешевого пилота OpenWebUI лучший порядок проверки такой:

1. `brave_llm_context` - основной кандидат, если можно завести Brave Search API key. Он лучше обычного `brave` для LLM-чата, потому что OpenWebUI получает готовые релевантные passages и не обязан отдельно скрейпить найденные страницы.
2. `tavily` - лучший быстрый бесплатный старт без карты, если нужен managed provider с простым onboarding.
3. `searxng` - рабочий self-hosted comparison path без direct API fee, но он добавляет отдельный сервис, limiter/NO_PROXY config и эксплуатацию.
4. `serper` - дешевый Google SERP API на объеме, если нужна именно выдача Google и оператор готов купить пачку credits.
5. `ddgs` / DuckDuckGo-like engines - только для smoke/test, не как основной provider для пилота.

Не выбирать для нового PRD-0:

- `bing` - Microsoft объявила retirement Bing Search APIs с 2025-08-11.
- `google_pse` / Google Custom Search JSON API - Google закрыл API для новых customers; existing customers должны уйти до 2027-01-01.
- дорогие SERP wrappers вроде `serpapi` как первый вариант, если нет отдельной причины платить за зрелый SERP coverage.

## Что поддерживает OpenWebUI

OpenWebUI поддерживает web search штатно через Admin Panel и env-переменные. В документации перечислены engines, включая `searxng`, `google_pse`, `brave`, `brave_llm_context`, `kagi`, `mojeek`, `serper`, `searchapi`, `serpapi`, `duckduckgo`, `tavily`, `linkup`, `jina`, `bing`, `exa`, `perplexity`, `azure_ai_search`, `yandex`, `youcom` и другие.

Ключевые настройки:

| Setting | Назначение |
| --- | --- |
| `ENABLE_WEB_SEARCH` | включает web search |
| `WEB_SEARCH_ENGINE` | выбирает provider |
| `WEB_SEARCH_RESULT_COUNT` | сколько результатов брать |
| `WEB_SEARCH_CONCURRENT_REQUESTS` | concurrency запросов к поисковику |
| `WEB_LOADER_CONCURRENT_REQUESTS` | concurrency загрузки страниц из результатов |
| `WEB_SEARCH_TRUST_ENV` | разрешает web loader учитывать `http_proxy` / `https_proxy` |

Эти настройки относятся к OpenWebUI `ConfigVar`: после первого запуска значение может быть сохранено во внутренней базе, а Admin UI будет иметь приоритет над env. Для PRD-0 это значит: менять web search лучше через Admin Panel -> Settings -> Web Search, а env использовать как воспроизводимую подсказку.

## Важная сетевая оговорка

Текущий сервер использует host-local HTTP-to-SOCKS bridge для provider egress. Если включать web search, обязательно включить trust proxy environment:

```env
WEB_SEARCH_TRUST_ENV=True
```

Без этого поиск может сходить к search provider, но загрузка содержимого найденных страниц может обходить proxy и падать по timeout/region/network policy.

Минимальный осторожный профиль для теста:

```env
ENABLE_WEB_SEARCH=True
WEB_SEARCH_ENGINE=brave_llm_context
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
WEB_LOADER_CONCURRENT_REQUESTS=2
WEB_SEARCH_TRUST_ENV=True
BYPASS_WEB_SEARCH_WEB_LOADER=True
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=True
```

API key хранить только в server-local `.env` или Admin UI. Не коммитить ключи.
На 2026-06-23 Yandex Search также добавлен через OpenWebUI Admin UI и прошел
operator/native smoke как рабочий RU-provider path. Runtime status фиксируем
отдельно от policy approval: рабочий smoke не означает автоматический rollout
для всех пользователей и всех типов данных.

Для `brave_llm_context` текущий рабочий baseline намеренно обходит web loader и
вторичный embedding/retrieval. Brave уже возвращает LLM-oriented passages, а
runtime diagnostics показали, что vectorized `web-search-*` retrieval path мог
вернуть `0` sources после успешного поиска и embedding. Это deferred known
issue: чинить позже, только если нам понадобятся длинные страницы, classic
`brave`, SearXNG page loading или полноценный RAG over fetched content.

## Сравнение кандидатов

| Provider / engine | Цена/лимит на дату исследования | Плюсы | Минусы | Вывод |
| --- | --- | --- | --- | --- |
| Brave `brave_llm_context` | Brave Search plan: `$5` за 1,000 requests, есть `$5` monthly credits | Хороший fit для LLM, меньше отдельного scraping, штатно описан в OpenWebUI | Вероятно нужна учетная запись/API key; для free/low tier держать concurrency `1` | Первый кандидат для пилота |
| Yandex `yandex` | Yandex Search API: цена зависит от sync/deferred/generative mode | Российский provider path; 2026-06-23 Admin UI/native smoke passed | Нужно контролировать cost mode, metadata forwarding, raw XML/HTML/rawData parsing и запрет sensitive queries | Рабочий RU-provider path после operator smoke; rollout только после policy/cost approval |
| Tavily `tavily` | Free: 1,000 API credits/month, no credit card; PAYG `$0.008`/credit | Самый простой бесплатный managed старт | Стоимость зависит от credit accounting; не Google SERP | Хороший fallback без карты |
| SearXNG `searxng` | API fee отсутствует, но есть VPS/ops cost | Self-hosted meta-search comparison path; native smoke passed in snippet/bypass mode | Нужны сервис, limiter/NO_PROXY config, engine tuning; качество зависит от upstream engines; CAPTCHA/rate-limit observed | Готов к three-path comparison, не primary |
| Serper `serper` | 2,500 free queries; Starter `$50` за 50k credits, `$1.00`/1k, credits valid 6 months | Дешевый Google SERP на объеме | Нужно покупать пакет; это внешний SERP wrapper | Хороший paid вариант при регулярном использовании |
| DDGS / DuckDuckGo-style | Бесплатно как библиотека/metasearch | Можно быстро проверить механику web search | Нестабильность, backend-зависимость, возможные блокировки | Только smoke/test |
| SearchAPI `searchapi` | Developer: `$40`/month за 10,000 searches, `$4`/1k | Managed SERP provider | Дороже Serper/Brave для простого пилота | Не первый выбор |
| SerpApi `serpapi` | Free 250/month; Starter `$25`/month за 1,000 searches | Зрелый SERP provider, много engines | Дорого для PRD-0 | Только при особой потребности |
| Exa `exa` | Search `$7`/1k requests | Хорош для AI/coding/search use cases | Дороже базовых вариантов | Не low-cost first choice |
| Linkup `linkup` | `$0.005`-`$0.006` per request | Агентный web search provider | Не дешевле Brave/Serper в базовом сценарии | Можно тестировать позже |

## Рекомендованный порядок теста

1. Оставить PRD-0 без web search до отдельного operator decision.
2. Для Stage 2 текущий первый baseline держать на рабочем `brave_llm_context`.
3. Выставить `WEB_SEARCH_RESULT_COUNT=3`, `WEB_SEARCH_CONCURRENT_REQUESTS=1`, `WEB_LOADER_CONCURRENT_REQUESTS=2`, `WEB_SEARCH_TRUST_ENV=True`, `BYPASS_WEB_SEARCH_WEB_LOADER=True`, `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=True`.
4. Проверить один русский и один английский запрос.
5. Проверить, что ответы содержат источники и не падают при загрузке страниц через proxy.
6. Yandex Search считать рабочим альтернативным RU-provider path после
   Admin UI/native smoke; перед расширением аудитории отдельно принять
   policy/cost/metadata rules.
7. Если Brave/Yandex onboarding или лимиты неудобны, проверить `tavily`.
8. SearXNG уже доказан как private native comparison path; следующий шаг -
   сравнить Brave / Yandex / SearXNG, а не назначать SearXNG основным
   provider path.

## Acceptance для будущего включения

Если web search станет частью отдельного scope, минимальная приемка:

- web search явно включен оператором;
- search provider и API key не закоммичены;
- `WEB_SEARCH_TRUST_ENV=True` включен из-за текущего proxy bridge;
- результат web search работает в UI для русского и английского запроса;
- в ответе видны источники;
- пользовательское предупреждение о секретах остается актуальным: не отправлять пароли, токены, API-ключи, приватные SSH-ключи и закрытые персональные данные;
- PRD/blueprint обновлены, потому что web search сейчас является non-goal PRD-0.

## Sources

- OpenWebUI environment variables: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI Brave provider: https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- OpenWebUI SearXNG provider: https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/
- OpenWebUI web search troubleshooting / proxy: https://docs.openwebui.com/troubleshooting/web-search/
- Brave Search API pricing: https://brave.com/search/api/
- Tavily pricing: https://www.tavily.com/pricing
- Serper pricing: https://serper.dev/
- SerpApi pricing: https://serpapi.com/pricing
- SearchAPI pricing: https://www.searchapi.io/pricing
- Exa pricing: https://exa.ai/pricing
- Linkup pricing: https://www.linkup.so/pricing
- Google Custom Search JSON API: https://developers.google.com/custom-search/v1/overview
- Microsoft Bing Search API retirement: https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement
- DDGS repository: https://github.com/deedy5/ddgs
