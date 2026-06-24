# Web Search Context Index

Status: provider connectivity baseline proven on 2026-06-23 for Brave, Yandex
and private SearXNG; production rollout and full provider comparison remain
pending.

Operational source of truth for this work is local `main / origin/main`; the
last committed baseline before this runtime refine is
`7d0e02c24808f3501e7c92b0ce48fcee646aa393`. Live runtime settings were verified
on 2026-06-23 on the deployed OpenWebUI container.

## Current Position

- Web Search is Stage 2 / PRD-1 scope.
- The first implementation slice must use native OpenWebUI Web Search unless
  runtime smoke proves a concrete privacy, cost, UX, security or runtime gap.
- No sidecar, fork or custom search gateway is approved for the first slice.
- Brave `brave_llm_context` is the current direct-context native baseline.
- Yandex Search API is the working RU direct API path, operator-confirmed
  through Admin UI/native smoke.
- Private SearXNG is a working private native meta-search comparison path in
  snippet/bypass mode, not the primary provider.
- Budget, data-egress policy, retention and group rollout remain owner
  decisions.

## Read First

- [WEB_SEARCH blueprint](blueprints/WEB_SEARCH.blueprint.md)
- [ADR-0007 Web Search Provider](decisions/ADR-0007-web-search-provider.md)
- [OpenWebUI Web Search integration boundary](contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md)
- [Web Search privacy boundary contract](contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md)
- [Web Search source attribution contract](contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md)
- [Web Search usage event contract](contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md)
- [Web Search external research 2026-06-20](research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md)
- [Native pilot plan](implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md)
- [Private SearXNG instance plan](implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md)
- [Candidate set comparison plan](implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)

## Runtime Evidence

- [Brave runtime baseline report](../reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md)
- [Yandex runtime baseline report](../reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md)
- [SearXNG runtime smoke report](../reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md)
- [Provider baseline closeout report](../reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md)
- [Context recon report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_CONTEXT_RECON.report.md)
- [Runtime probe report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md)
- [Domain and probe final report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md)
- [Private SearXNG report](../reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md)

## Acceptance Surface

- [Acceptance matrix](acceptance/ACCEPTANCE_MATRIX.md)
- [Test data requirements](acceptance/TEST_DATA_REQUIREMENTS.md)

Minimum pilot acceptance:

- provider ADR is proposed for owner review or accepted for pilot;
- provider key path is approved and server-side only;
- Web Search can be enabled/disabled for the approved group scope;
- result count and concurrency are low and documented;
- RU/EN smoke queries pass;
- source links/cards are visible;
- timeout/quota/no-results/policy errors are visible;
- raw sensitive queries and provider keys are not exposed in browser or logs by
  default;
- native analytics/cost visibility is proven or the gap is explicitly accepted.

Current Brave baseline status:

- safe RU smoke passed on the deployed OpenWebUI instance with visible search
  results and a grounded answer;
- provider key values were not printed into docs or diagnostic output;
- group permission, EN matrix, logging-retention and cost-visibility checks
  remain pending before all-user rollout.

Current provider baseline status:

- Brave `brave_llm_context`: native direct-context baseline proven.
- Yandex Search API: native RU direct API path works by owner/operator
  confirmation; full smoke evidence remains pending unless separately captured.
- Private SearXNG: native private meta-search path proven in snippet/bypass
  mode; ready for Brave/Yandex/SearXNG candidate-set comparison.

## Active Decisions

- Current working baseline: Brave `brave_llm_context` as the first paid native
  Web Search path.
- Runtime config baseline: result count `3`, search concurrency `1`, web loader
  bypass enabled, web-search embedding/retrieval bypass enabled.
- Known deferred issue: the vectorized Web Search path
  `search -> web-search-* vector collection -> retrieval sources` can return
  `0` sources after successful search and embedding. Do not fix it in the main
  Brave direct-context baseline; revisit it when a product scenario needs long
  page loading, classic `brave`, SearXNG page loading, or full RAG over fetched
  content.
- Code Interpreter must not be enabled by default for Web Search smoke on the
  selected model; otherwise the model can choose browser Pyodide instead of
  native Web Search context.
- Self-hosted meta-search comparison track: private SearXNG, with explicit
  warning that upstream engines still see queries.
- Private SearXNG runtime smoke passed in snippet/bypass mode. It remains a
  comparison track unless owner promotes it after quality, privacy, logging and
  ops evidence.
- Working RU-provider path: Yandex Search API passed Admin UI/native smoke on
  2026-06-23. Keep broad rollout gated by user-info/chat-id forwarding review,
  allowed data classes and cost mode.
- Defer provider setup if owner cannot approve provider, budget, data classes,
  retention or group scope.

## Plain-Language Model

- Brave/Yandex are direct access paths to an external provider search index.
- SearXNG is our dispatcher. It asks enabled external sources and engines, then
  returns one normalized candidate list.
- SearXNG does not own a global internet index.
- SearXNG is not an LLM.
- SearXNG does not write the final answer.
- The search provider returns candidate sources.
- OpenWebUI loader/extraction prepares context/evidence where enabled.
- The LLM writes the answer and should show sources or say evidence is
  insufficient.
- The Brave/Yandex/SearXNG comparison checks candidate quality, latency,
  source visibility, privacy/logging and ops cost. It does not claim SearXNG can
  stand in for Brave or Yandex as an index-owning provider.

## Conceptual Model: Candidate Discovery vs Answer Generation

Candidate set means the pre-answer list returned by Web Search:

- URL;
- title;
- snippet or content preview;
- source/engine/provider;
- score/rank when available;
- freshness/time metadata when available.

Search stage:

- finds candidates;
- returns URL/snippet/source metadata;
- does not write the final answer.

Web loading / extraction stage:

- fetches selected candidate URLs when enabled;
- extracts and normalizes text;
- prepares evidence chunks for the LLM.

LLM answer stage:

- synthesizes the final answer;
- cites or displays sources;
- reports insufficient evidence when candidate/evidence quality is too weak.

Comparison model:

- Path A: native OpenWebUI -> Brave `brave_llm_context` -> paid
  LLM-oriented candidate/context -> LLM answer.
- Path B: native OpenWebUI -> Yandex Search API -> candidate set -> LLM
  answer. Operator/native smoke passed on 2026-06-23; production rollout still
  needs policy/cost/metadata approval.
- Path C: native OpenWebUI -> private SearXNG -> enabled upstream engines /
  public sources -> normalized candidate set -> OpenWebUI snippet/bypass path
  -> LLM answer. Runtime smoke passed on 2026-06-23; full page loading and
  vectorized retrieval are not proven.

## Explicitly Not Proven Yet

- production rollout;
- ordinary-user allow/deny permissions;
- full EN/RU comparative matrix;
- cost visibility and budget guardrails;
- logging/retention policy;
- full page loading;
- vectorized `web-search-*` retrieval;
- Yandex privacy/data-egress and metadata-forwarding review;
- SearXNG as primary provider.

## Recommended Next Tasks

1. Run the three-path comparison: Brave / Yandex / private SearXNG.
2. Close rollout policy gates: pilot group, permission allow/deny, forbidden
   query handling, logs/retention and cost visibility.
3. Tune SearXNG only if comparison shows enough value: engine allowlist, RU
   quality, CAPTCHA/rate-limit handling and image pinning.
4. Keep vectorized retrieval and long-page loading as a separate future known
   issue.

## Open Questions For Owner

- Which groups receive the proven Brave baseline first?
- Are foreign search providers allowed for ordinary non-sensitive business
  queries?
- Which data classes are forbidden for Web Search under all provider classes?
- Is native usage visibility enough for pilot, or is hard budget enforcement
  required before any user pilot?
- Which groups receive Web Search first?
- What retention policy applies to search metadata and provider errors?

## Non-Goals

- No production code in this documentation slice.
- No STT changes or STT architecture reopening.
- No universal web-search framework promise.
- No separate user-facing search portal.
- No sidecar/fork until native runtime smoke proves a gap.
