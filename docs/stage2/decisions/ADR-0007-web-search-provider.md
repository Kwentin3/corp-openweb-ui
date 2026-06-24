# ADR-0007 Web Search Provider

Status: accepted_for_provider_baseline; pilot_rollout_pending_policy_and_comparison

Date: 2026-06-20

Runtime update: 2026-06-23

## 1. Context

Web Search is a Stage 2 / PRD-1 feature. PRD-1 requires controlled web
grounding for OpenWebUI users with rules, limits, result count, concurrency,
instructions and cost visibility.

OpenWebUI has native Web Search configuration and provider support. The first
Stage 2 Web Search slice should therefore start with native OpenWebUI Web
Search, then prove runtime behavior on the deployed/staging instance. A sidecar,
fork or custom search gateway is not justified until native runtime smoke proves
a concrete gap.

Web Search can become a hidden privacy and cost channel. The system must not
silently send full prompts, secrets, financial/accounting data or customer data
to a search provider.

## 2. Decision To Make

Choose the first pilot-provider strategy:

- A. Brave `brave_llm_context` as first paid API pilot.
- B. Private SearXNG as self-hosted meta-search candidate discovery gateway.
- C. Yandex Search API as RU-provider pilot path after native smoke and
  policy/cost approval.
- D. Defer provider setup until owner approves data and cost policy.

This ADR now marks the native provider connectivity baseline as closed for
Brave, Yandex and private SearXNG. It does not approve all-user rollout until
the owner approves budget, data classes, retention, group scope and comparison
outcome.

Owner/runtime matrix as of 2026-06-23:

- primary paid API pilot: Brave Search API / `brave_llm_context`, runtime smoke
  baseline proven;
- self-host comparison track: private SearXNG instance, runtime smoke proven in
  snippet/bypass mode;
- RU-provider path: Yandex Search API configured through Admin UI and native
  smoke passed on 2026-06-23; broader rollout still requires
  privacy/data-egress, metadata-forwarding and cost-mode approval.

## 3. Recommended Decision

Recommended default:

- Use native OpenWebUI Web Search first.
- Use Brave `brave_llm_context` for the first paid API smoke baseline.
- Start with result count `3` and search concurrency `1`.
- For `brave_llm_context`, bypass the web loader and web-search
  embedding/retrieval path so Brave's LLM-oriented context is passed directly
  to the LLM.
- Keep vectorized Web Search retrieval as a deferred known issue. Fix it later
  only if a product scenario needs long page loading, classic `brave`, SearXNG
  page loading, or full RAG over fetched content.
- Do not enable Code Interpreter by default for the selected Web Search smoke
  model.
- Keep source attribution visible and required.
- Use native analytics/provider dashboard for pilot cost visibility unless the
  owner requires hard budget enforcement before any pilot.

Alternatives:

- Use private SearXNG as a comparison track if the owner wants more operational
  control and accepts SearXNG maintenance plus upstream-engine leakage risk.
  Runtime connectivity is proven, but SearXNG is not primary.
- Use Yandex Search API as the working RU-provider path after its Admin
  UI/native smoke; keep rollout behind provider-specific privacy review,
  especially user-info/chat-id forwarding and search mode/cost behavior.
- Treat Tavily, Firecrawl, Exa, Perplexity and You.com as fallback/enrichment
  candidates, not the first default, unless their LLM-oriented extraction is
  explicitly desired.

## 4. Provider Comparison

| Provider | Role | Data egress | API key path | RU quality expectation | EN quality expectation | Pricing/limits signal checked 2026-06-20 | Latency/ops | Source visibility | Native OpenWebUI support | Risks | Pilot fit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brave `brave_llm_context` | First paid API baseline | Foreign provider receives minimized query | Server-side Admin UI/env only | Runtime smoke passed for safe RU query | Good expected, EN matrix pending | Brave Search lists Search/LLM Context at about `$5 / 1k` requests, monthly credits, high capacity; OpenWebUI docs warn free-tier users to set concurrency `1` | Low ops, API latency | LLM-optimized passages and URLs | Yes | Foreign provider; paid; token/context bloat if overused; vectorized retrieval path needs separate fix | Current working default |
| Brave classic `brave` | Search snippets then page fetch | Foreign provider plus fetched source sites | Server-side only | Medium/TBD | Good expected | Same Brave Search commercial plan family | More page-fetch variability | Search result URLs/snippets plus loader output | Yes | Fetch failures/proxy issues; more scraping surface | Backup to LLM Context |
| Private SearXNG | Self-hosted meta-search candidate discovery gateway | Private instance plus upstream engines/public sources | SearXNG URL/server config; no external provider key in OpenWebUI | Runtime smoke passed in snippet/bypass mode; RU quality mixed/TBD | Runtime smoke passed in snippet/bypass mode; EN quality usable/TBD | No direct paid API path, but infra/ops cost remains; upstream blocks/CAPTCHA risk | Ops-heavy; limiter/JSON/NO_PROXY config required | Normalized candidate URLs/snippets | Yes | Not a full web index; not fully private; DuckDuckGo CAPTCHA and Brave-through-SearXNG rate-limit noise observed | Comparison track, not primary |
| Yandex Search API | Working RU-provider path after Admin UI/native smoke | Yandex Cloud receives query and optional metadata | Server-side Admin UI/env only | Operator-confirmed native smoke passed for safe RU path; full evidence report remains to be captured | Medium/TBD | Yandex docs separate quotas/limits and pricing by synchronous/deferred/generative modes | Cloud/procurement setup | XML/HTML/rawData parsing via native provider | Yes/community/provider docs | User-info/chat-id forwarding review; XML parser issues; generative mode cost | RU path for controlled pilot after policy/cost approval |
| Tavily | LLM-oriented search/extract | Foreign provider | Server-side only | TBD | Good expected | Docs list free credits and PAYG credit pricing | Managed API | Structured search/extract | Yes | Credit model; another foreign processor | Fallback/enrichment |
| Firecrawl | Search/scrape/extract | Foreign provider or self-host if separately deployed | Server-side only | TBD | Good extraction expected | Pricing page lists credit costs for scrape/search/extract | Good extraction, more moving parts | Search plus page text | Yes | Search is not the simplest first provider; extraction costs | Follow-up extraction layer |
| Serper | Google SERP wrapper | Foreign SERP wrapper | Server-side only | Good Google-like expected | Good Google-like expected | Site advertises free queries and low per-1k pricing | Managed API | Structured SERP | Yes | SERP wrapper compliance/ToS; provider review | Low-cost fallback |
| SerpApi | Mature SERP wrapper | Foreign SERP wrapper | Server-side only | Good Google-like expected | Good Google-like expected | Pricing page lists free tier and paid plans | Mature but paid | Rich structured SERP | Yes | Cost/compliance | Special SERP coverage only |
| SearchAPI | SERP wrapper | Foreign SERP wrapper | Server-side only | Good Google-like expected | Good Google-like expected | Pricing page lists free requests and paid plans from monthly tiers | Managed API | Structured SERP | Yes | No first-pilot advantage over Brave/SearXNG/Yandex | Fallback |
| Exa | AI search/contents | Foreign provider | Server-side only | TBD | Good AI-search expected | Exa pricing update lists search-with-contents per 1k and content add-ons | Managed API | Contents/highlights | Yes | Cost model; foreign provider | Fallback for AI-oriented search |
| Kagi | Premium search API | Foreign provider | Server-side only | TBD | Good expected | Kagi docs describe API portal; public preview opened in 2026 | Newer API surface | Premium results | Yes | Preview/availability/procurement | Research-only for now |
| Perplexity Search | Search API / grounded APIs | Foreign provider | Server-side only | TBD | Good expected | Docs say Search API is per request without token-based pricing; Sonar is separate | Managed API | Search results/citations | Yes | Answer API vs search API confusion; foreign provider | Fallback if approved |
| You.com | Search/contents API | Foreign provider | Server-side only | TBD | Good expected | Pricing page lists Search API per 1k calls and Contents API per 1k pages | Managed API | LLM-ready snippets | Yes | Foreign provider; cost | Fallback |
| YaCy | Self-host/distributed search | Local/distributed peers depending setup | Local config | Weak/TBD | Weak/TBD | Self-host operational cost | High ops; quality risk | Search result URLs | Yes | Index quality/ranking/ops | Not first pilot |

## 5. Privacy And Cost Rules

- Do not send the full user prompt to an external search provider by default.
- Apply query minimization.
- Do not send secrets, tokens, private keys, credentials, private URLs or
  customer documents to search providers.
- Broker, tax, financial, personal and accounting data are allowed only if the
  data policy explicitly permits the selected provider class.
- Provider keys must live only in server-local env/Admin UI/approved secret
  store.
- Browser must not receive provider keys.
- Raw queries and raw result bodies must not be logged by default without
  retention approval.
- Result count and concurrency start low.
- Source attribution is mandatory for grounded answers.

## 6. Required Runtime Probes Before Pilot

Before exposing Web Search to a pilot group, prove or explicitly block:

- exact OpenWebUI deployed/staging version/image;
- native Web Search settings exist in the deployed Admin UI;
- provider engines available include the selected provider and relevant
  alternatives;
- result count, search concurrency, web-loader controls, domain/fetch filters,
  bypass loader and trust-env/proxy controls are available or gaps recorded;
- `features.web_search` or equivalent group permission behavior;
- ordinary user without permission cannot use Web Search;
- approved pilot user can use Web Search;
- provider key values are not visible in browser responses, frontend config,
  localStorage/sessionStorage or logs;
- RU/EN safe smoke queries return visible source links/cards;
- timeout, quota/rate-limit, no-results and policy-blocked states are visible;
- proxy path works if the deployment requires `WEB_SEARCH_TRUST_ENV=True`;
- SSRF/fetch-boundary tests are planned with safe fixtures;
- analytics/cost visibility path is documented or gap accepted.

Runtime status after 2026-06-23 smoke:

- selected provider engine and key path were configured through deployed
  OpenWebUI runtime/Admin UI;
- safe RU Brave smoke produced usable online answer after direct-context config;
- Yandex Search was added through OpenWebUI Admin UI and passed operator/native
  smoke as a working RU-provider path;
- private SearXNG native provider path passed runtime smoke in snippet/bypass
  mode after limiter passlist and `NO_PROXY` runtime fixes;
- vectorized web-search retrieval is not accepted yet because it returned `0`
  sources after embedding web-search results; this is deferred until long pages,
  classic `brave`, SearXNG page loading, or full RAG over fetched content are in
  scope;
- permission, full EN/RU comparison, logging-retention and cost-visibility
  checks remain pending before pilot rollout.

## 7. Consequences

- Native-first reduces custom code and keeps the user workflow inside
  OpenWebUI.
- Provider choice creates privacy, cost, procurement and retention obligations.
- SearXNG provides a private instance boundary only; upstream engine exposure
  must be handled.
- SearXNG is a working comparison path, but future decision is still needed:
  keep it, tune it, defer it, or reject it after comparison.
- Yandex runtime smoke is no longer blocked, but broader use still requires
  metadata-forwarding, allowed data class and search mode/cost review.
- Hard billing and custom event capture remain future work unless owner requires
  them as a pilot gate.
- Sidecar and fork remain future options only after native runtime proof shows a
  specific gap.

## 8. Owner Decisions Needed

- Provider strategy after comparison: Brave primary, Yandex RU path, private
  SearXNG fallback/comparison, or defer SearXNG.
- Budget and provider account owner.
- Allowed provider class for ordinary business queries.
- Forbidden query/data examples.
- First pilot group.
- Default result count and concurrency.
- Metadata retention period.
- Whether native/provider-dashboard cost visibility is enough for pilot.
- Whether Yandex user-info/chat-id forwarding is acceptable for rollout beyond
  admin/manual smoke.

## 9. Acceptance Signals

- Provider strategy is owner-approved for pilot or explicitly deferred.
- Runtime probe report exists and separates passed checks from blockers.
- Brave native smoke baseline is recorded and reproducible.
- Yandex native smoke is recorded at least as operator-confirmed before it is
  offered beyond admin/manual testing.
- SearXNG native smoke is recorded as snippet/bypass passed before it is
  included in three-path comparison.
- Provider key path is server-side only.
- No provider secrets are visible in browser/runtime evidence.
- RU/EN safe smoke queries pass.
- Source cards/links are visible.
- Policy-blocked sensitive examples are documented.
- Usage/cost visibility path is documented or gap accepted.

## 10. Links

- [WEB_SEARCH blueprint](../blueprints/WEB_SEARCH.blueprint.md)
- [Web Search context index](../WEB_SEARCH_CONTEXT_INDEX.md)
- [Privacy boundary contract](../contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md)
- [Usage event contract](../contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md)
- [Source attribution contract](../contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md)
- [Integration boundary](../contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md)
- [External research 2026-06-20](../research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md)
- [Native pilot plan](../implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md)
- [Private SearXNG instance plan](../implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md)
- [Candidate set comparison plan](../implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)
- [ADR-0001 Data Policy](ADR-0001-data-policy-by-provider-class.md)
- [ADR-0008 Native Analytics vs Hard Billing](ADR-0008-native-analytics-vs-hard-billing.md)
