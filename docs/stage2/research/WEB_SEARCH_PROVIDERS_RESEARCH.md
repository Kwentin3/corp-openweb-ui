# Web Search Providers Research

## 1. Question

Which web-search provider path should Stage 2 use for OpenWebUI: Brave, Yandex Search API, self-hosted/metasearch, or external custom provider?

## 2. Research status

Status: researched from official OpenWebUI, Brave and Yandex Search API docs on 2026-06-18.

Result type: provider decision input. No provider key or live query was used.

## 3. Findings

- OpenWebUI has native Web Search and provider-specific engines.
- Current OpenWebUI docs describe Brave support with two engines: `brave` and `brave_llm_context`. The LLM context path returns LLM-optimized passages and avoids separate page scraping.
- OpenWebUI environment docs include Yandex Web Search variables: `YANDEX_WEB_SEARCH_URL` and `YANDEX_WEB_SEARCH_API_KEY`.
- Existing repo research already recommended `brave_llm_context` with low result count/concurrency for PRD-0-adjacent planning. That remains directionally valid, but pricing changed/currently needs budget approval.
- Brave official pricing currently lists Search at $5 per 1,000 requests, with $5 free credits per month and 50 requests/second capacity. Brave LLM Context is positioned for AI/agent grounding.
- Yandex Search API supports text search, image search and generative response. Text results may return XML/HTML raw data depending on query mode; generative response uses YandexGPT over search results.
- Yandex Search API pricing is materially different by mode: daytime synchronous search is about $4 per 1,000 requests; deferred search is much cheaper; generative response is much more expensive. Quotas include 10 synchronous requests/sec and 1 generative response/sec by default.
- Yandex Search API is a real Russian provider candidate, but it may require more integration work and billing/procurement setup than Brave.

## 4. Recommendation

Preferred Stage 2 decision path:

1. Use native OpenWebUI Web Search first.
2. Select Brave `brave_llm_context` for the first pilot if foreign provider use is allowed and customer accepts pricing.
3. Keep Yandex Search API as the Russian-provider candidate for a separate ADR/smoke if data residency/procurement or Russian search quality is decisive.
4. Do not build a custom search gateway unless native providers fail smoke tests or source policy requires a controlled intermediary.

## 5. Required controls

- Enable web-search only for approved groups or all users per customer decision.
- Start with low `WEB_SEARCH_RESULT_COUNT` and low concurrency.
- Document that web queries may leave the system to the selected search provider.
- Track approximate request count and provider cost.
- Define smoke queries in Russian and English.
- Reject unlimited agentic browsing until cost/rate policy is explicit.

## 6. Decision options

| Option | Fit | Risk |
| ------ | --- | ---- |
| Brave `brave_llm_context` | Best first pilot: simple native support, AI-oriented context | Foreign provider, paid per request |
| Yandex Search API | Russian provider candidate, official OpenWebUI env exists | XML/HTML/raw result handling, quotas, higher gen-response cost |
| SearXNG/self-hosted | More control over provider surface | Ops burden, result quality and anti-bot maintenance |
| External custom search API | Maximum policy/control | More implementation and ownership |

## 7. Sources

- https://docs.openwebui.com/category/web-search/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- https://docs.openwebui.com/reference/env-configuration/
- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/documentation/pricing
- https://api-dashboard.search.brave.com/app/documentation/web-search/get-started
- https://api-dashboard.search.brave.com/documentation/services/llm-context
- https://yandex.cloud/en/docs/search-api/concepts/
- https://yandex.cloud/en/docs/search-api/pricing
- https://yandex.cloud/en/docs/search-api/concepts/limits
- https://yandex.cloud/en/docs/search-api/concepts/web-search
- https://yandex.cloud/en/docs/search-api/concepts/generative-response

## 8. Status

Research complete. Provider ADR required before setup.
