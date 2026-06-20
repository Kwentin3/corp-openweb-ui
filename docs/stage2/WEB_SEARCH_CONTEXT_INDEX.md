# Web Search Context Index

Status: native-first pilot preparation, provider not yet approved.

Operational source of truth for this work is local `main / origin/main` at
`be49bbdbcab56a50e7d88a80e22a78073740b8ca`.

## Current Position

- Web Search is Stage 2 / PRD-1 scope.
- The first implementation slice must use native OpenWebUI Web Search unless
  runtime smoke proves a concrete privacy, cost, UX, security or runtime gap.
- No sidecar, fork or custom search gateway is approved for the first slice.
- Provider choice, budget, data-egress policy and runtime credentials remain
  owner decisions.

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

## Active Decisions

- Default recommendation: Brave `brave_llm_context` for the first paid API
  smoke if foreign provider and budget are approved.
- Self-hosted meta-search comparison track: private SearXNG, with explicit
  warning that upstream engines still see queries.
- Private SearXNG has an optional compose/config plan, but remains a comparison
  track unless owner promotes it over Brave.
- RU-provider candidate: Yandex Search API, only after privacy review of
  user-info/chat-id forwarding and cost mode.
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
- The Brave vs SearXNG comparison checks whether SearXNG candidates are good
  enough for useful grounded answers, not whether SearXNG can stand in for
  Brave or Yandex as an index-owning provider.

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
- Path B: native OpenWebUI -> private SearXNG -> enabled upstream engines /
  public sources -> normalized candidate set -> OpenWebUI loader -> LLM answer.
- Path C later: native OpenWebUI -> Yandex Search API -> candidate set -> LLM
  answer, only after privacy/data-egress review.

## Open Questions For Owner

- Which provider is approved for the first smoke: Brave, private SearXNG,
  Yandex, or defer?
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
