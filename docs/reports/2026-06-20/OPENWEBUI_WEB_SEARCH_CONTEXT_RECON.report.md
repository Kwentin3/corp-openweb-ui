# OpenWebUI Web Search Context Recon

Date: 2026-06-20
Repo: `Kwentin3/corp-openweb-ui`
Scope: Stage 2 / PRD-1 Web Search context collection and first blueprint framing.

## 1. Executive Summary

Web Search already exists in the project as a Stage 2 / PRD-1 requirement, not as PRD-0 scope and
not as implemented local code. The current source-of-truth says: Web Search is needed for all users,
but only with explicit rules, limits, result count, concurrency settings, source visibility and
cost visibility.

The documented product goal is practical: let employees use current external information inside the
OpenWebUI workflow without turning search into a hidden cost/privacy channel. The feature must stay
inside OpenWebUI UX where possible.

Implementation readiness is partial:

- product intent is clear;
- native OpenWebUI Web Search is the preferred first path;
- Brave `brave_llm_context` is the documented first-pilot candidate if foreign provider use is
  approved;
- Yandex Search API is the documented Russian-provider candidate;
- provider setup is blocked by ADR-0001 data policy and ADR-0007 provider/cost/privacy approval;
- deployed OpenWebUI runtime still needs a read-only capability probe before implementation.

Nearest reasonable next slice: finish/approve the Web Search provider ADR and run a no-secrets
native OpenWebUI runtime probe for feature permissions, result count, concurrency, proxy behavior,
source display and analytics visibility. Do not build a sidecar or fork first.

No code, secrets, runtime env values or provider keys were read or changed in this recon.

## 2. Source Map

### Canonical and navigation docs

| Path | Why important | Extracted decisions / constraints |
| --- | --- | --- |
| `README.md` | Top-level repo entrypoint. | PRD-0 excluded web search; Stage 2 includes web-search, model catalog, analytics and data policy. Future OpenWebUI-facing features must follow extension-first. |
| `docs/README.md` | Requested path. | `missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`. No new navigation doc was created by this recon task. |
| `docs/_index/canon.md` | Requested path. | `missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`. |
| `docs/_index/domains.md` | Requested path. | `missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`. |
| `docs/services/architecture/manifest.md` | Requested path. | `missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`. |
| `docs/services/architecture/project-digest.md` | Requested path. | `missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` | Current PRD-1 source of truth. | Web-search is a Practical Stage 2 slice for all users with provider, limits, result count, concurrency, instruction and cost visibility. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md` | Customer-facing summary. | Web-search is priority 3 after transcription and broker reports; not a free/uncontrolled button. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md` | Shows latest PRD-1 changes. | Confirms Web Search became Practical Stage 2 scope during the 2026-06-18 actualization. |

### Stage 2 source-of-truth docs

| Path | Why important | Extracted decisions / constraints |
| --- | --- | --- |
| `docs/stage2/README.md` | Stage 2 hub. | Stage 2 is native/OpenWebUI-first, policy-driven and proof-gated. |
| `docs/stage2/CONTEXT_INDEX.md` | Discovery index. | Points Web Search to blueprint, provider research and older infra research. |
| `docs/stage2/DOMAIN_MAP.md` | Domain ownership map. | Web-search domain goal: managed search through policy, limits and backend/provider boundary; status: research complete, ADR needed. |
| `docs/stage2/ROADMAP.md` | Review/execution order. | ADR-0007 Web-search Provider is in the ADR set; Web-search Provider approval is an implementation gate. |
| `docs/stage2/ENGINEERING_BACKLOG.md` | Engineering backlog. | Web-search provider task depends on data policy, customer privacy/cost approval and smoke queries; Web-search smoke depends on ADR/provider key path. |
| `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md` | Integration rule. | Preferred order: native config, Functions/Actions/Tools/OpenAPI Tool Server, thin UI shim, private sidecar, deep fork only with proof and ADR. |
| `docs/stage2/CONTRACT_BOUNDARIES.md` | Cross-domain boundary rules. | Provider keys, policy, retention and usage accounting are backend/admin concerns; UI must not own provider keys or policy. |
| `docs/stage2/IMPLEMENTATION_GATES.md` | Start conditions. | Gate 4 Web-search Provider is blocked by ADR; runtime proof must include web-search smoke. |

### Web Search specific docs

| Path | Why important | Extracted decisions / constraints |
| --- | --- | --- |
| `docs/stage2/blueprints/WEB_SEARCH.blueprint.md` | Current Web Search blueprint. | Target workflow: user runs allowed search, gets grounded answer/source links, sees limits and knows when search is forbidden. |
| `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md` | Stage 2 provider research. | Native OpenWebUI Web Search first; Brave `brave_llm_context` first pilot if approved; Yandex Search API as Russian candidate; no custom gateway unless native fails or policy requires. |
| `docs/stage2/decisions/ADR-0007-web-search-provider.md` | Provider decision record. | Status proposed; decision must approve provider, rules, limits, result count, concurrency, cost visibility and smoke checks. |
| `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md` | Earlier infra/provider research. | PRD-0 non-goal; OpenWebUI supports Web Search via Admin UI/env; `WEB_SEARCH_TRUST_ENV=True` matters for current proxy bridge; API keys stay server-local/Admin UI. |
| `docs/stage2/research/OPENWEBUI_CAPABILITY_RESEARCH.md` | Native capability research. | Web-search is native in OpenWebUI docs, but deployed v0.9.6 must be checked; permissions may support web-search access by group. |

### Security, privacy and cost docs

| Path | Why important | Extracted decisions / constraints |
| --- | --- | --- |
| `docs/stage2/decisions/ADR-0001-data-policy-by-provider-class.md` | Data policy dependency. | Provider setup must not start before data policy by provider class is approved; secrets/API keys/passwords are prohibited in prompts for every provider class. |
| `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md` | Policy blueprint. | Web-search needs scenario-specific warnings; final allowed/prohibited matrix requires customer approval. |
| `docs/stage2/decisions/ADR-0008-native-analytics-vs-hard-billing.md` | Cost boundary. | Practical Stage 2 starts with native analytics/cost visibility; hard budgets/gateway are optional/future unless explicitly required. |
| `docs/stage2/blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md` | Cost blueprint. | Cost visibility should cover LLM tokens, web-search requests, STT hours and storage/files; do not store full prompts unnecessarily. |
| `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md` | Analytics research. | Native OpenWebUI analytics may be enough for basic visibility, but runtime proof is required. |

### Acceptance and reports

| Path | Why important | Extracted decisions / constraints |
| --- | --- | --- |
| `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | Acceptance source. | Web-search acceptance: Russian/English smoke queries work; result count, concurrency and policy documented; status research complete/provider ADR needed. |
| `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md` | Test data source. | Needs 5-10 Russian queries, 3-5 English queries, forbidden examples, expected result count and citation/source requirements. |
| `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md` | Prior research report. | Confirms Web-search native provider path, Brave/Yandex split and provider ADR requirement. |
| `docs/reports/2026-06-18/OPENWEBUI_PRD1_SOURCE_OF_TRUTH_SYNC.report.md` | PRD sync report. | Confirms Web-search remains for all users with rules, result count, concurrency, cost visibility. |
| `docs/reports/2026-06-18/OPENWEBUI_PRD1_STAGE2_AGENT_REVIEW.report.md` | Review report. | Warns Web Search can become hidden privacy/cost drift without policy and limits. |
| `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md` | PRD-0 closure context. | Web search research exists but did not expand PRD-0 runtime path. |
| `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md` | STT closure context. | STT is current-stage closed; do not mix Web Search with STT or reopen STT architecture. |

### Implementation files

No Web Search implementation code was found in `services/`, `deploy/`, `compose/`, `scripts` or
`.env.example`. Existing implementation files are Stage 2 STT-specific and out of scope for this
feature.

## 3. Product Intent

Web Search solves the "current information" problem: users need answers grounded in external web
sources, not only model memory or internal prompts. In Stage 2 this supports research, comparison,
source lookup and current public information checks inside the corporate OpenWebUI environment.

Primary users:

- ordinary corporate users who need controlled search inside approved workflows;
- admins who need to enable, limit and explain the feature;
- scenario/template owners who define when search is allowed or forbidden.

Expected UX:

- user enables or invokes Web Search inside OpenWebUI, ideally through native Web Search controls;
- search is visible, not hidden magic;
- the answer shows that it is search-grounded;
- source links / source attribution are expected for acceptance;
- the user sees failure states when provider quota, network/proxy or policy blocks search;
- admin can configure provider, access, result count, concurrency and cost visibility path.

Explicit vs automatic search:

- MVP should prefer explicit user intent or clearly visible native OpenWebUI Web Search state;
- automatic/background search is a later policy decision and must not become hidden browsing;
- if an LLM decides to search automatically, the UI still needs a visible contract: search happened,
  which provider/source class was used, and what limitations apply.

Boundary between answer and evidence:

- LLM answer is synthesis;
- search evidence is external provider result/source list;
- prompts/templates should not treat provider raw response as a stable product contract;
- source attribution/citations are required enough for the user to inspect where the answer came
  from.

## 4. Architecture Candidates

### A. Native OpenWebUI Web Search / Tools path

What it gives:

- lowest implementation surface;
- stays inside OpenWebUI UX;
- uses documented provider engines and Admin UI/env configuration;
- aligns with extension-first rule.

Risks:

- deployed v0.9.6 may differ from current docs;
- native analytics/permissions/source display need runtime proof;
- provider-specific settings and Admin UI values may live in OpenWebUI DB after first run.

Secrets:

- server-local `.env` or OpenWebUI Admin UI only;
- never browser.

Logging:

- OpenWebUI/provider logs may contain query metadata;
- exact content logging behavior must be checked in runtime and provider terms.

Rights:

- native groups/permissions if available in deployed version.

Usage/cost:

- native analytics plus manual/provider price catalog first;
- provider dashboard cross-check for request counts.

Extension-first fit: strongest.

### B. OpenWebUI Function / Action

What it gives:

- thin custom behavior while staying in OpenWebUI;
- possible place for explicit query minimization, redaction, cost event emission or policy checks.

Risks:

- unnecessary if native Web Search already satisfies UX and policy;
- upgrade/testing burden;
- must not become hidden magic.

Secrets:

- Action valves/admin config may hold endpoint references or internal tokens;
- external provider keys should still stay backend-side or in OpenWebUI Admin UI, not browser.

Logging:

- custom logs must avoid raw prompts and sensitive query text unless approved.

Rights:

- should use OpenWebUI identity/session/group context, not a parallel identity system.

Usage/cost:

- can emit normalized usage events if native analytics is insufficient.

Extension-first fit: acceptable after native gap proof.

### C. OpenAPI Tool Server

What it gives:

- clean tool contract for search as an external capability;
- useful if native providers cannot satisfy Yandex/custom policy, query minimization or normalized
  result shape.

Risks:

- more moving parts than native search;
- must design auth, rate limits, logging, result normalization and failure states;
- may duplicate native feature.

Secrets:

- tool server/server-local secret store only;
- OpenWebUI receives a tool endpoint, not provider keys.

Logging:

- tool server owns sanitized request/response metadata logs.

Rights:

- tool calls must be authorized by OpenWebUI user/group/scenario context or a narrow service token
  plus policy resolver.

Usage/cost:

- tool server can count `search_request`, provider, result count, status, latency and estimated
  cost.

Extension-first fit: valid if native/provider proof shows a real gap.

### D. Private sidecar

What it gives:

- maximum control over provider adapters, query minimization, logging, usage events and policy;
- can normalize Brave/Yandex/SearXNG/custom providers behind one internal contract.

Risks:

- more custom code and ownership;
- likely premature for first pilot;
- must avoid becoming a separate user-facing portal.

Secrets:

- sidecar env/secret store only.

Logging:

- sidecar emits sanitized usage/cost/security events; raw query retention requires explicit policy.

Rights:

- should consume approved OpenWebUI identity/session context or a narrow backend trust boundary.

Usage/cost:

- strongest for normalized cost tracking, but not needed until native path fails.

Extension-first fit: later option, not first slice.

### E. Deep OpenWebUI fork

What it gives:

- full UI/control ownership.

Risks:

- upgrade burden, merge conflicts, hidden maintenance cost;
- contradicts current project principles without proof;
- not justified by current repo evidence.

Secrets:

- still must not enter browser.

Logging/rights/usage:

- all become custom responsibilities.

Extension-first fit: unacceptable now. Only after native/Action/Tool/sidecar paths are proven
insufficient and owner/ADR approves.

## 5. Provider Landscape Inside The Project

### Brave Search / `brave_llm_context`

Status:

- first-pilot candidate if foreign provider use is allowed;
- documented in both infra and Stage 2 research;
- preferred over plain `brave` for LLM context because it returns AI-oriented passages.

Need to verify:

- current account/procurement path;
- current pricing/limits before commercial commitment;
- native OpenWebUI settings in deployed v0.9.6;
- source display and Russian/English query quality.

Secrets needed:

- Brave Search API key, held server-local/Admin UI only.

Limits/cost/policies:

- request cost, free credits, QPS/concurrency, provider terms.

Privacy concerns:

- foreign provider; search query may expose sensitive intent/data.

Smoke tests:

- approved Russian queries;
- approved English queries;
- forbidden-query examples must be rejected by user instruction/policy;
- verify source display and proxy behavior.

Pilot fit: strongest if foreign provider approval is granted.

### Yandex Search API

Status:

- Russian-provider candidate;
- OpenWebUI env docs reportedly include `YANDEX_WEB_SEARCH_URL` and `YANDEX_WEB_SEARCH_API_KEY`;
- must not be confused with YandexGPT or GigaChat.

Need to verify:

- native Yandex Web Search behavior in deployed OpenWebUI;
- result format handling;
- sync/deferred/generative mode choice;
- procurement/billing and quotas.

Secrets needed:

- Yandex Web Search API key / endpoint values, held server-local/Admin UI only.

Limits/cost/policies:

- sync/deferred/generative pricing differs materially;
- default quotas and generative response cost must be approved.

Privacy concerns:

- still an external provider; Russian-provider status does not remove data policy requirements.

Smoke tests:

- Russian-heavy queries;
- source display;
- quota exceeded;
- disabled/generative mode not accidentally used if not approved.

Pilot fit: good if Russian-provider stance is decisive, but likely needs more verification than
Brave.

### Tavily

Status:

- older infra research lists it as a quick managed fallback with simple onboarding;
- not the primary Stage 2 ADR candidate compared with Brave/Yandex.

Need to verify:

- current pricing/credit accounting;
- native engine behavior;
- whether customer accepts another foreign managed search provider.

Pilot fit: fallback only.

### SearXNG / self-hosted metasearch

Status:

- documented low API-cost option with ops burden.

Need to verify:

- hosting/maintenance ownership;
- result quality;
- JSON/API configuration;
- anti-bot reliability.

Pilot fit: later self-host path, not smallest first slice.

### Serper, SearchAPI, SerpApi, Exa, Linkup, DDGS

Status:

- mentioned in older infra research as candidates or non-first choices;
- not selected as primary Stage 2 candidates.

Pilot fit:

- only if Brave/Yandex/Tavily/SearXNG fail a specific requirement.

Provider facts from older in-repo docs may be stale and should be re-verified when
ADR/commercial approval is finalized. The next section records the external research performed after
this internal provider landscape was collected.

## 6. External Research: Community/Provider Landscape

External research was performed after the initial repo-context recon. Sources were limited to
official OpenWebUI docs/code, official provider docs/pricing pages and a small number of community
threads where they expose practical failure modes. No credentials, live provider keys or customer
data were used.

### 6.1. Upstream OpenWebUI native capability

Current OpenWebUI docs and upstream `main` code confirm that Web Search is already a native backend
capability, not something this repo should duplicate first.

What exists upstream:

- `WEB_SEARCH_ENGINE` supports many engines: `searxng`, `brave`, `brave_llm_context`, `kagi`,
  `serper`, `searchapi`, `serpapi`, `duckduckgo`, `tavily`, `exa`, `perplexity`,
  `perplexity_search`, `firecrawl`, `yacy`, `yandex`, `youcom`, `external` and others.
- Admin config covers `ENABLE_WEB_SEARCH`, result count, search concurrency, web-loader concurrency,
  domain filter list, bypass flags and provider-specific keys/settings.
- `features.web_search` permission is checked in `/process/web/search` for non-admin users in the
  current upstream router.
- OpenWebUI separates search from web loading: search returns URLs/snippets, then the loader fetches
  returned URLs unless `BYPASS_WEB_SEARCH_WEB_LOADER` is enabled.
- The web loader has SSRF protections: non-HTTP(S) protocols are rejected, parser-confusing URL
  characters are rejected, and private/non-global IP fetches are blocked unless local fetch is
  explicitly enabled.
- `WEB_SEARCH_TRUST_ENV` is an Admin UI / ConfigVar setting; it is required when web content loading
  must respect `http_proxy` / `https_proxy`.
- `brave_llm_context` is materially different from `brave`: it returns pre-extracted,
  relevance-scored passages and can skip the post-search scrape step.
- OpenWebUI has an `external` search provider contract: POST query/count to a custom endpoint and
  expect normalized search result objects.

Implication for this repo:

- first architecture path should be native OpenWebUI Web Search config/probe;
- do not build a sidecar before native smoke proves a policy or runtime gap;
- do not patch OpenWebUI core before checking the exact deployed version and Admin UI settings;
- if custom policy is needed, `external` search provider is a narrower option than a deep fork.

Important upstream code findings to verify in runtime:

- `Yandex` and `external` search implementations call helpers that may forward user info headers
  and chat id to the provider/custom endpoint. That is acceptable only if ADR-0001/ADR-0007 approve
  this egress, or if config/code path disables it.
- `Yandex` default config path uses `SEARCH_TYPE_RU` and parses `rawData` XML returned from Yandex.
  Russian fit looks plausible, but privacy and query payload details need review first.
- SearXNG code forwards `safesearch`, `language`, `time_range` and `categories` to the instance;
  current OpenWebUI Admin UI must be checked for which of these are exposed in the deployed version.
- Upstream logs include provider result logging in some provider modules. Runtime log level and
  sanitization must be checked before production.

External sources:

- OpenWebUI env/config docs: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI Web Search troubleshooting: https://docs.openwebui.com/troubleshooting/web-search/
- OpenWebUI Brave provider docs:
  https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- OpenWebUI SearXNG provider docs:
  https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/
- OpenWebUI External provider docs:
  https://docs.openwebui.com/features/chat-conversations/web-search/providers/external/
- OpenWebUI Tools docs:
  https://docs.openwebui.com/features/extensibility/plugin/tools/
- Upstream code:
  `backend/open_webui/routers/retrieval.py`,
  `backend/open_webui/retrieval/web/*.py`,
  `backend/open_webui/config.py`.

### 6.2. Provider candidate table

| Provider / engine | Role | Fit for first pilot | Key benefits | Main risks / checks |
| --- | --- | --- | --- | --- |
| Brave `brave_llm_context` | External web-search API with LLM-ready passages. | Best first paid API pilot if foreign provider is allowed. | Native OpenWebUI support; no separate page scrape; predictable Search pricing; retry on 429 exists upstream. | Foreign-provider approval; cost approval; RU quality smoke; current pricing/limits; provider key path. |
| Brave `brave` | Classic web search snippets + OpenWebUI page loading. | Second to `brave_llm_context`. | Native support and familiar result shape. | More page-fetch failures, latency and SSRF/web-loader surface than LLM Context path. |
| SearXNG private instance | Self-hosted metasearch. | Best privacy/ops pilot if avoiding external paid API key is more important than stable quality. | No direct paid API key; local control; community pattern for OpenWebUI; JSON/safesearch/language controls. | Still sends queries to upstream engines; public instances are unreliable; CAPTCHA/rate-limit/bot blocking; ops burden; result quality varies by engines. |
| Yandex Search API | Russian-provider search candidate. | Strong RU candidate after privacy ADR. | Native OpenWebUI `yandex` engine; Russian search type; useful for Russian customer stance. | Current upstream path may forward user/chat headers; API returns raw XML payload; mode/pricing/quotas differ; procurement and data egress approval required. |
| Tavily | LLM-oriented search/extract API. | Fallback/enrichment layer, not mandatory first step. | AI-oriented structured results; search/extract/crawl APIs; easy integration. | Another foreign provider; credit model; extraction depth can affect cost/latency; native OpenWebUI integration is simple but less transparent than raw SERP. |
| Firecrawl | Search + scrape/extract/read layer. | Prefer as loader/extraction layer after URL search, not first search provider unless extraction is the real need. | Strong page extraction/scraping; retry/backoff in upstream OpenWebUI Firecrawl module; self-host option may exist. | Costs and rate/concurrency limits; scrape timeouts; not a replacement for provider/privacy policy. |
| Exa | Neural/semantic search. | Research-only candidate. | Useful for semantic/research discovery; native OpenWebUI engine exists. | Higher cost than Brave/Serper class; quality for Russian corporate use unknown. |
| Serper | Commercial Google-like SERP wrapper. | Good paid fallback if Google-like SERP is required. | Cheap at volume; structured Google SERP; native OpenWebUI engine. | External wrapper/ToS/compliance; not first choice if Brave/SearXNG/Yandex fits. |
| SerpAPI | Mature multi-engine SERP wrapper. | Only with special SERP coverage need. | Broad engine coverage, CAPTCHA/proxy infrastructure, structured results. | More expensive; vendor/compliance review. |
| SearchAPI | Commercial SERP wrapper. | Fallback if specific SERP engines are required. | Native OpenWebUI engine; multi-engine real-time SERP. | Paid plan; wrapper ToS/compliance; no clear advantage for first pilot. |
| Kagi | Premium search API. | Not first pilot unless customer already uses Kagi/API. | High-quality paid search, API portal/usage controls. | Account/subscription model; pricing and corporate procurement need review. |
| Perplexity / `perplexity_search` | Search API or answer engine. | Not first pilot for transparent evidence contract. | Search API returns structured results; Sonar can return cited prose answers. | Answer-engine path can blur LLM answer vs evidence; token/request pricing can surprise; data policy needed. |
| You.com | LLM-ready Search/Contents/Research APIs. | Research-only for now. | Search returns LLM-ready web/news snippets and optional content; pricing appears simple. | Foreign provider; native integration exists as `youcom`, but customer/privacy fit unproven. |
| YaCy | Self-hosted/distributed search engine. | Not first pilot for general web search quality. | Full self-host/intranet search possibilities; native OpenWebUI engine. | Community reports quality/ranking concerns; better for internal/intranet index than broad web search. |

### 6.3. Community practice

Observed pattern:

- self-hosted LLM/OpenWebUI users often start with SearXNG because it is free, familiar in Docker
  stacks and avoids immediate paid API onboarding;
- production-minded users quickly hit the SearXNG tradeoff: self-hosting the metasearch instance
  does not make upstream search private or reliable;
- API-backed providers such as Brave are preferred when stable latency, fewer CAPTCHA failures and
  lower ops burden matter;
- Firecrawl/Tavily/Playwright are often discussed as extraction/read layers after search, not as a
  reason to bypass native search configuration;
- users commonly reduce result count and concurrency to avoid rate limits and noisy context;
- public SearXNG instances are a poor corporate dependency; a private instance is the only serious
  SearXNG option.

SearXNG practical setup notes:

- JSON output must be enabled in `settings.yml`; otherwise OpenWebUI gets HTML/no useful JSON.
- OpenWebUI sends `format=json`, `safesearch`, `language`, `time_range`, `categories`, `theme` and
  `image_proxy` query params.
- A private SearXNG instance should usually run adjacent to OpenWebUI in compose/networking if chosen
  for pilot.
- Public instances should not be used for corporate pilot acceptance because availability, rate
  limiting and result quality are outside our control.
- SearXNG limiter/bot-detection exists for a reason: upstream engines may CAPTCHA/block SearXNG
  because it relays automated queries.

Community failure modes worth carrying into smoke tests:

- web search works but page extraction fails behind proxy unless `WEB_SEARCH_TRUST_ENV=True`;
- local SearXNG can fail because JSON format is not enabled;
- self-signed cert / internal Caddy paths can break loader fetch;
- DuckDuckGo/DDGS and public metasearch paths can be unstable;
- high result count or high concurrency can make responses slow, expensive or empty;
- model context window can be too small after fetching pages, so "search succeeded" does not mean
  answer used evidence correctly.

Community sources:

- OpenWebUI GitHub discussion on performance and page fetching:
  https://github.com/open-webui/open-webui/discussions/7402
- OpenWebUI GitHub issue on built-in search result count behavior:
  https://github.com/open-webui/open-webui/issues/21371
- OpenWebUI GitHub issue on SearXNG with self-signed cert:
  https://github.com/open-webui/open-webui/issues/18030
- SearXNG limiter docs: https://docs.searxng.org/admin/searx.limiter.html
- SearXNG search API docs: https://docs.searxng.org/dev/search_api.html
- SearXNG public-instance discussion:
  https://github.com/searxng/searxng/discussions/2802

### 6.4. Practical tricks to carry into our blueprint

- Query minimization: never send the full user prompt to the search provider by default. Generate a
  short search query from the visible user intent and strip sensitive/customer context.
- Two-step evidence pipeline: query rewrite -> search -> fetch/extract selected URLs -> rerank or
  filter -> answer with sources.
- Separate search and extraction: Brave `brave_llm_context` can skip extraction for first pilot;
  classic providers need controlled loader/extractor behavior.
- Limit result count: start with top 3 or top 5; top 10 only after latency/cost proof.
- Limit concurrency: Brave free/low tier and SearXNG public-like behavior need sequential or low
  concurrency.
- Use domain allow/block filters: OpenWebUI already has a domain filter list; use it for source
  policy, finance/legal domains and internal/private network blocking.
- Freshness policy: news/prices/laws require explicit freshness; evergreen references do not.
- Source attribution contract: answer without visible sources is not a grounded Web Search answer.
- "No sufficient evidence" mode: conflicting/weak sources must produce a visible uncertainty answer,
  not a hallucinated synthesis.
- TTL cache for identical safe queries can reduce cost/rate pressure, but cache key should be a
  query hash and provider/config tuple, not raw sensitive query text.
- Audit events: record user/group/scenario, provider, query hash, result count, latency, status and
  cost estimate; do not log full sensitive query without retention approval.
- Graceful degradation: quota/timeout/no-results must be visible; if answering without search, the
  UI/assistant must say the response is not web-grounded.
- SSRF/URL-fetch boundary: keep local/private IP/file/ftp/parser-confusing URL protections enabled;
  test redirects and private network URLs explicitly.

### 6.5. Pitfalls / decisions not to repeat

- Do not treat SearXNG as "private web search" without saying that upstream engines still receive
  queries.
- Do not use public SearXNG instances for corporate acceptance.
- Do not increase result count/concurrency to hide quality issues; it increases latency, cost and
  noise.
- Do not route Yandex/external search before deciding whether user identity/chat id may be forwarded.
- Do not choose Perplexity/answer-engine style providers if the first requirement is transparent
  source evidence and cost accounting.
- Do not introduce Firecrawl/Tavily as mandatory if Brave LLM Context already supplies usable
  passages.
- Do not patch OpenWebUI core before checking native settings and `external` provider contract.
- Do not store raw queries/results by default; define retention first.

### 6.6. Security / privacy checklist from external research

Must verify before pilot:

- API keys live only in server-local env, OpenWebUI Admin UI or approved secret storage.
- API keys are not exposed to browser/localStorage/logs.
- Exact query payload sent to provider is minimized and documented.
- Yandex/external provider path does not forward user identity/chat id unless approved.
- Backend log level does not print full result lists or raw sensitive query content.
- Domain filter list and web-fetch filter list are configured for private/internal URL blocking.
- `ENABLE_RAG_LOCAL_WEB_FETCH` remains off unless explicitly approved.
- `WEB_SEARCH_TRUST_ENV=True` is set if provider/web-loader egress must use proxy.
- Search result retention and audit event retention are defined separately.
- Per-group `features.web_search` permission works on deployed version.
- Toxic/personal/financial/broker/tax query examples are blocked by instruction/policy before
  provider call where feasible.
- Provider 429/403/500/timeout has typed user-facing errors.

### 6.7. External provider recommendations

Recommended first architecture path:

1. Native OpenWebUI Web Search config/runtime probe.
2. Native provider pilot with `brave_llm_context` if foreign provider use and budget are approved.
3. Private SearXNG pilot only if the owner prioritizes self-host/no-paid-API over provider
   reliability and accepts upstream-engine leakage/ops work.
4. Yandex Search API as RU-provider candidate after explicit privacy ADR, because upstream code may
   forward user/chat headers and Yandex config/mode affects payload and cost.
5. `external` provider contract or thin wrapper only if native provider smoke fails policy needs
   such as query minimization, custom logging, source policy or Yandex header stripping.
6. Sidecar only if the wrapper/external contract is insufficient.
7. Deep fork: still not justified.

Recommended first provider:

- default recommendation: Brave `brave_llm_context`;
- privacy/self-host alternative: private SearXNG;
- RU provider candidate: Yandex Search API, but privacy ADR first;
- extraction/enrichment follow-up: Firecrawl or Tavily after search provider is selected.

Runtime smoke tests required:

- OpenWebUI Admin UI exposes Web Search settings and does not leak secrets in config responses/logs.
- `features.web_search` works for allowed and blocked users/groups.
- `brave_llm_context` returns source-bearing answer for 3 RU and 3 EN approved queries.
- Result count 3 and concurrency 1 produce stable latency and no 429.
- With web loader bypass off/on, source display and docs/chunks behave as expected.
- `WEB_SEARCH_TRUST_ENV=True` route is tested through current proxy bridge.
- Domain filter blocks a known disallowed domain and private-network URL fetch.
- Provider quota/timeout is surfaced as visible error.
- Yandex path, if tested, proves whether user info/chat id headers are forwarded and whether they
  can be disabled or stripped before production.

Hypothesis verdict:

- Confirmed: first pilot does not need a fork and likely does not need a sidecar.
- Refined: first pilot should prefer native OpenWebUI + Brave `brave_llm_context` if foreign
  provider approval exists; otherwise evaluate private SearXNG as a controlled self-host pilot.
- Refined: Yandex is a serious RU candidate, but not before privacy/data-egress ADR.

## 7. Data / Privacy / Security Boundary

Data that may leave the system:

- the search query;
- result fetch URLs and metadata;
- possibly page-loading requests from OpenWebUI web loader;
- provider account/request metadata.

Do not send full user prompt by default. The first safe contract should use query minimization:
construct a narrow search query from the user's intent and avoid copying confidential context into
the provider request.

Required controls:

- scenario-specific warning before/near search use;
- prohibited examples: passwords, tokens, API keys, private SSH keys, internal credentials,
  personal data, financial/accounting/tax data, broker reports and meeting transcripts unless policy
  explicitly allows the provider class;
- redaction/sanitization before custom logging;
- no provider keys in browser;
- no raw `.env`, Admin UI secrets, tokens or customer data in docs/reports/log output.

Logging:

- log minimum metadata for observability: user/group id reference, scenario, provider, request id,
  result count, status, latency, quota/cost bucket;
- do not log full prompt or raw sensitive query unless owner approves a retention policy;
- failures should be typed without exposing secrets.

Retention:

- define separate retention for query metadata, source/result snapshots and usage events;
- default for first slice should avoid retaining full result content unless needed for audit and
  approved by policy.

Permissions:

- Web Search may be all-user feature only after policy approval;
- otherwise enable by approved groups/scenarios first;
- group permissions must be verified in deployed OpenWebUI.

## 8. Cost / Usage / Rate Limits

Events to count:

- `web_search_request_started`;
- `web_search_request_completed`;
- `web_search_request_failed`;
- `web_search_request_blocked_by_policy`;
- provider quota/rate-limit failures;
- result count/concurrency used;
- estimated cost unit where available.

Counting model:

- one user-visible search invocation should map to one or more provider requests;
- record provider, engine/mode, result count and whether page loading happened;
- for Yandex, mode matters because sync/deferred/generative pricing differs.

Limits:

- start with low result count and low concurrency;
- older infra research suggests `WEB_SEARCH_RESULT_COUNT=3`,
  `WEB_SEARCH_CONCURRENT_REQUESTS=1`, `WEB_LOADER_CONCURRENT_REQUESTS=2`;
- final numbers require ADR/customer approval.

Quota exceeded behavior:

- show a user-facing error that search is temporarily unavailable or quota-limited;
- do not silently answer as if grounded;
- log sanitized provider/quota status for admin review.

Budget enforcement:

- first stage should use observability/native analytics plus provider dashboard checks;
- hard budgets, virtual keys, guaranteed blocking and centralized routing are separate gateway work.

## 9. UX Contract

Where user enables search:

- preferred: native OpenWebUI Web Search control/settings as available in deployed version;
- admin config controls provider and group availability.

Searching state:

- visible `searching`/busy state;
- no hidden background search for MVP.

Sources:

- show source links or source cards;
- answer should indicate when it is grounded in web search;
- if sources are unavailable, mark the answer as not fully grounded.

Errors:

- provider not configured;
- provider quota/rate limit exceeded;
- network/proxy fetch failure;
- policy block;
- no relevant results;
- source loading failed.

Citations/source attribution:

- required for acceptance enough that the user can inspect used sources;
- exact citation format can follow native OpenWebUI behavior unless it is insufficient.

Admin settings:

- provider/engine;
- API key path without exposing values;
- result count;
- concurrency;
- enabled groups/features;
- proxy/trust-env behavior;
- usage/cost visibility path;
- forbidden-query/user instruction text.

## 10. MVP / Pilot Slice Proposal

Scope:

- approve/update ADR-0007 with provider choice, result count, concurrency, cost/privacy stance and
  smoke queries;
- run read-only/native runtime probe of deployed/staging OpenWebUI Web Search settings and group
  permissions;
- configure a controlled pilot only after provider key/account path is approved by owner;
- use native OpenWebUI Web Search first;
- prove Russian and English smoke queries and visible sources;
- record sanitized usage/cost evidence.

Non-goals:

- no universal search orchestration framework;
- no deep fork;
- no separate external portal/GUI;
- no direct browser-to-provider secret path;
- no hard billing gateway unless customer explicitly requires enforceable budgets;
- no STT architecture changes.

Acceptance criteria:

- ADR-0001 data policy has an accepted interim rule for web-search provider class;
- ADR-0007 approved or explicitly accepted for pilot;
- provider selected: Brave, Yandex Search or defer;
- result count/concurrency set and documented;
- provider key path approved without committing/printing secrets;
- native search works for approved Russian/English smoke queries;
- source links are visible;
- forbidden examples are documented in user/admin instruction;
- admin has basic usage/cost review path or documented gap.

Smoke tests:

- 5-10 approved Russian queries;
- 3-5 approved English queries;
- forbidden sensitive-data examples;
- provider quota/rate-limit simulated or safely observed;
- network/proxy behavior, especially `WEB_SEARCH_TRUST_ENV=True` if the current proxy bridge is used;
- group with Web Search enabled vs disabled, if native permissions support it.

Files likely to change:

- `docs/stage2/decisions/ADR-0007-web-search-provider.md`;
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`;
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`;
- possible new `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`;
- possible admin/user handoff docs after pilot;
- `.env.example` only if the team decides to document non-secret variable names, never real keys.

Risks:

- deployed OpenWebUI version differs from current docs;
- provider pricing/limits changed since research;
- user queries leak sensitive information;
- native analytics is insufficient for web-search cost visibility;
- Yandex native path may need adapter work;
- source quality is poor or hard to inspect.

Open questions:

- Brave, Yandex Search or defer?
- What data classes may be sent to foreign/Russian search providers?
- What exact result count/concurrency should be used?
- What source/citation UX is enough for acceptance?
- Does customer require hard monthly limits or only cost visibility?
- Who owns provider account/procurement and cost review cadence?

## 11. Required ADRs / Contracts

Required now:

- `docs/stage2/decisions/ADR-0007-web-search-provider.md`: provider choice, provider class,
  result count, concurrency, smoke queries, cost/privacy approval and key path.
- `docs/stage2/decisions/ADR-0001-data-policy-by-provider-class.md`: web-search allowed/prohibited
  data classes and warning text.

Likely contract/doc updates before implementation:

- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`: query minimization,
  prohibited data, provider data egress and retention.
- `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md`: normalized request/cost metadata.
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`: minimum source/citation
  expectations and failure behavior.
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`: native vs Action/Tool/server
  boundary, group permissions and no-secret rule.

Not required yet:

- deep fork ADR;
- custom sidecar ADR;
- hard billing/gateway ADR, unless owner requires enforceable budgets/rate limits.

## 12. Final Verdict

`web_search_native_path_ready_for_provider_adr`

Reason: internal repo context plus external OpenWebUI/provider research confirm the first architecture
path should be native OpenWebUI Web Search configuration and runtime proof. The provider ADR can now
choose between Brave `brave_llm_context` as the preferred first paid API pilot, private SearXNG as the
self-host/privacy pilot, or Yandex Search after a stricter privacy decision. No fork or sidecar is
justified for the first pilot unless runtime smoke proves a concrete policy gap.
