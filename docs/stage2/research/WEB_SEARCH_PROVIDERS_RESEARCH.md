# Web Search Providers Research

## 1. Question

Which web-search provider path should Stage 2 use for OpenWebUI: Brave, Yandex Search API,
self-hosted/metasearch, or external custom provider?

## 2. Research status

Status: researched from official OpenWebUI, Brave and Yandex Search API docs on 2026-06-18.

Result type: provider decision input. No provider key or live query was used.

Runtime note: this research was followed by 2026-06-23 deployed-instance smoke
tests. Brave `brave_llm_context` became the first working native baseline.
Yandex Search was also configured through OpenWebUI Admin UI and passed
operator/native smoke as a working RU-provider path.

## 3. Findings

- OpenWebUI has native Web Search and provider-specific engines.
- Current OpenWebUI docs describe Brave support with two engines: `brave` and `brave_llm_context`.
  The LLM context path returns LLM-optimized passages and avoids separate page scraping.
- OpenWebUI environment docs include Yandex Web Search variables: `YANDEX_WEB_SEARCH_URL` and
  `YANDEX_WEB_SEARCH_API_KEY`.
- Existing repo research already recommended `brave_llm_context` with low result count/concurrency
  for PRD-0-adjacent planning. That remains directionally valid, but external billing terms need
  owner approval.
- Brave official billing docs describe Search request units, credits and capacity. Brave LLM Context
  is positioned for AI/agent grounding.
- Yandex Search API supports text search, image search and generative response. Text results may
  return XML/HTML raw data depending on query mode; generative response uses YandexGPT over search
  results.
- Yandex Search API commercial terms are materially different by mode: synchronous, deferred and
  generative response paths have separate billing and quota implications.
- Yandex Search API is a real Russian provider path. The 2026-06-23 Admin
  UI/native smoke passed, but broader use still requires metadata-forwarding,
  data-policy and cost-mode approval.

## 4. Recommendation

Preferred Stage 2 decision path:

1. Use native OpenWebUI Web Search first.
2. Select Brave `brave_llm_context` for the first pilot if foreign provider use is allowed and
   customer accepts external billing terms.
3. Keep Yandex Search API as the working Russian-provider path for controlled
   follow-up after Admin UI/native smoke, with rollout gated by data policy,
   metadata-forwarding and cost-mode decisions.
4. Do not build a custom search gateway unless native providers fail smoke tests or source policy
   requires a controlled intermediary.

## 5. Required controls

- Enable web-search only for approved groups or all users per customer decision.
- Start with low `WEB_SEARCH_RESULT_COUNT` and low concurrency.
- Document that web queries may leave the system to the selected search provider.
- Track approximate request count and provider cost.
- Define smoke queries in Russian and English.
- Reject unlimited agentic browsing until cost/rate policy is explicit.

## 6. Decision options

### Brave `brave_llm_context`

Fit:

- Best first pilot: simple native support, AI-oriented context.

Risk:

- Foreign provider.
- Paid per request.

### Yandex Search API

Fit:

- Russian provider path.
- Official OpenWebUI env exists.
- Admin UI/native smoke passed on 2026-06-23.

Risk:

- XML/HTML/raw result handling.
- Quotas.
- Higher generative-response cost.

### SearXNG / self-hosted

Fit:

- More control over provider surface.

Risk:

- Ops burden.
- Result quality and anti-bot maintenance.

### External custom search API

Fit:

- Maximum policy/control.

Risk:

- More implementation and ownership.

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

Research complete. Brave `brave_llm_context` is now proven as the first native
smoke baseline. Yandex Search is also proven by Admin UI/native smoke as a
working RU-provider path, with policy/cost/metadata approval still required
before broader rollout. SearXNG comparison remains a separate follow-up track.
