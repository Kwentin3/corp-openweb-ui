# Web Search External Research 2026-06-20

Status: current provider/runtime research for ADR-0007.

No provider key or live provider request was used.

## Executive Summary

- OpenWebUI has native Web Search with many provider engines and Admin UI/env
  configuration.
- Native OpenWebUI should be the first pilot path.
- Brave `brave_llm_context` is the best first paid API candidate if foreign
  provider use and budget are approved.
- Private SearXNG is the privacy/ops alternative, but it is not fully private:
  upstream engines can still see queries and may block automated traffic.
- Yandex Search API is the RU-provider candidate, but needs privacy review for
  metadata forwarding and mode/cost selection before live smoke.
- Tavily, Firecrawl, Exa, Kagi, Perplexity, You.com and SERP wrappers are useful
  fallback or enrichment options, not the default first slice.

## OpenWebUI Native Capability

Current OpenWebUI docs describe Web Search as a built-in feature with provider
configuration in Admin UI and env/config variables.

Important settings and behaviors to verify in the deployed version:

- `ENABLE_WEB_SEARCH`
- `WEB_SEARCH_ENGINE`
- `WEB_SEARCH_RESULT_COUNT`
- `WEB_SEARCH_CONCURRENT_REQUESTS`
- `WEB_LOADER_CONCURRENT_REQUESTS`
- `BYPASS_WEB_SEARCH_WEB_LOADER`
- `WEB_SEARCH_TRUST_ENV`
- domain/fetch filters
- group/feature permission for Web Search

Provider docs and env docs show native support for many engines, including
`brave`, `brave_llm_context`, `searxng`, `yandex`, `external`, `tavily`,
`firecrawl`, `serper`, `serpapi`, `searchapi`, `exa`, `kagi`, `perplexity` and
`youcom`.

Operational note: OpenWebUI troubleshooting says search may work while page
fetching fails behind a proxy unless the web loader is allowed to trust proxy
environment settings. This matters because PRD-1 already calls out
`WEB_SEARCH_TRUST_ENV=True` for the current proxy bridge.

## Provider Findings

### Brave

OpenWebUI Brave docs describe two relevant modes:

- `brave`: classic web search results, then OpenWebUI may fetch returned pages.
- `brave_llm_context`: Brave LLM Context endpoint, designed for AI/agent
  grounding and able to reduce separate page scraping.

Brave official pricing pages currently present Search, including LLM Context, at
about `$5 / 1,000` requests with monthly credits and commercial capacity. The
OpenWebUI Brave docs warn that free-tier users should set concurrency to `1` to
avoid HTTP 429.

Pilot implication: use `brave_llm_context`, result count `3`, concurrency `1`
for first smoke after approval.

### Private SearXNG

SearXNG provides an HTTP search API and requires JSON output to be enabled for
API use. The OpenWebUI SearXNG provider expects a SearXNG query URL.

Operational risks:

- public instances are not acceptable for acceptance;
- private deployment needs limiter/bot-protection tuning;
- upstream engines can still see searches;
- automated traffic may hit CAPTCHA/blocking;
- latency and quality depend on selected engines.

Pilot implication: good fallback if owner rejects foreign paid API, but needs
ops setup before smoke.

### Yandex Search API

Yandex Search API is a real RU-provider candidate. Official docs describe
quotas/limits and different request modes. Pricing differs materially by mode:
synchronous/deferred/generative response have different costs and rate limits.

OpenWebUI has a Yandex Web Search provider path, but the live smoke needs an
extra privacy check:

- whether user-info headers can be avoided;
- whether chat id/session metadata is forwarded;
- which `searchType` and endpoint mode are used;
- whether generative/expensive mode is disabled unless approved;
- what provider errors and raw results are logged.

Pilot implication: do not run live Yandex smoke before owner approves this
privacy/cost review.

### Tavily

Tavily is an LLM-oriented search/extract/crawl provider. Docs show free monthly
credits and pay-as-you-go credit pricing. It is useful when the product wants
RAG-ready search/extract behavior.

Pilot implication: fallback/enrichment, not first default because Brave/SearXNG
/Yandex map more directly to current ADR choices.

### Firecrawl

Firecrawl focuses on search/scrape/crawl/extract. Pricing is credit-based and
Search/Scrape have separate credit costs.

Pilot implication: useful as extraction layer if native page fetch is weak, but
not first provider for a minimal native search smoke.

### SERP Wrappers: Serper, SerpApi, SearchAPI

These providers expose structured Google-like SERP data with their own pricing
and compliance/ToS posture. Serper advertises a low-cost Google SERP API and
free starter queries. SerpApi is mature and broad but can be more expensive.
SearchAPI offers a paid SERP API with free trial requests.

Pilot implication: fallback if Google-like SERP coverage is the actual owner
requirement.

### Exa

Exa is an AI-oriented search/contents provider. Current pricing update describes
search-with-contents per 1k requests and add-on content/summarization charges.

Pilot implication: research/fallback for AI search, not first default.

### Kagi

Kagi docs describe Search API access through its API portal; Kagi announced
public preview for Search API in 2026.

Pilot implication: promising but preview/procurement status makes it research
only for this slice.

### Perplexity Search

Perplexity Search API docs describe a request-priced Search API. Perplexity also
has Sonar/answer APIs with separate token/request economics.

Pilot implication: avoid confusing Search API with answer-generation APIs; use
only if owner explicitly wants Perplexity.

### You.com

You.com publishes Search API and Contents API pricing; search returns
LLM-ready snippets and metadata.

Pilot implication: fallback foreign provider.

### YaCy

YaCy is self-host/distributed search. It gives control, but quality/ranking and
ops burden make it a poor first pilot for corporate OpenWebUI.

## Community / Runtime Risk Signals

Community issues and discussions point to practical risks to verify in runtime:

- Web Search may return results but the model may not use them unless native
  settings/tool mode are correct.
- Result count may behave differently in agentic/native function mode.
- Page fetching may fail behind proxies without trust-env behavior.
- SearXNG integration often fails when JSON output or query URL is wrong.
- Self-signed/internal TLS paths can break SearXNG/OpenWebUI connectivity.
- Yandex provider parsing may fail on incomplete XML result fields.
- Fetching pages can bloat context and latency.

These are smoke-test risks, not reasons to build a sidecar before native proof.

## Recommendation

Recommended first path:

1. Owner approves provider/budget/data classes/group scope.
2. Configure native OpenWebUI Web Search.
3. Smoke Brave `brave_llm_context` with result count `3`, concurrency `1`.
4. Verify source display, permission gating, no browser key exposure, no raw
   sensitive logs, quota/timeout/no-results UX and cost visibility.
5. Use private SearXNG only if foreign API use is not approved.
6. Use Yandex only after metadata-forwarding and mode/cost review.

## Sources Checked 2026-06-20

- https://docs.openwebui.com/category/web-search/
- https://docs.openwebui.com/reference/env-configuration/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/external/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/yandex/
- https://docs.openwebui.com/troubleshooting/web-search/
- https://docs.openwebui.com/features/chat-conversations/web-search/agentic-search/
- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/documentation/pricing
- https://api-dashboard.search.brave.com/documentation/services/llm-context
- https://yandex.cloud/en/services/search-api
- https://aistudio.yandex.ru/docs/en/search-api/concepts/limits
- https://aistudio.yandex.ru/docs/en/search-api/pricing
- https://yandex.cloud/en/docs/iam/concepts/authorization/api-key
- https://docs.searxng.org/dev/search_api.html
- https://docs.searxng.org/admin/searx.limiter.html
- https://docs.tavily.com/documentation/api-credits
- https://docs.tavily.com/faq/faq
- https://www.firecrawl.dev/pricing
- https://exa.ai/docs/changelog/pricing-update
- https://serper.dev/
- https://serpapi.com/pricing
- https://www.searchapi.io/pricing
- https://help.kagi.com/kagi/api/search.html
- https://help.kagi.com/kagi/api/overview.html
- https://kagi.com/changelog
- https://docs.perplexity.ai/docs/search/quickstart
- https://docs.perplexity.ai/docs/getting-started/overview
- https://you.com/pricing
- https://github.com/open-webui/open-webui/issues/21371
- https://github.com/open-webui/open-webui/issues/24243
- https://github.com/open-webui/open-webui/discussions/7008
