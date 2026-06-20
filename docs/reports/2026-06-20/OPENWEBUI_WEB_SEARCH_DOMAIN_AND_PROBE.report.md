# OpenWebUI Web Search Domain And Probe Report

Date: 2026-06-20

Verdict: `web_search_native_pilot_ready_after_owner_provider_approval`

## 1. Executive Summary

The Web Search documentation domain is now ready for owner review and the first
native OpenWebUI pilot slice.

What changed:

- created a compact Web Search context index;
- updated ADR-0007 with native-first provider strategy;
- created privacy, usage-event, source-attribution and integration-boundary
  contracts;
- created current external provider research;
- created a native pilot plan;
- updated acceptance and test-data requirements;
- created a read-only runtime probe report.

Runtime result:

- Local repo/config evidence confirms OpenWebUI is pinned to
  `ghcr.io/open-webui/open-webui:v0.9.6`.
- Live deployed/staging Admin UI and provider smoke were not run because no
  runtime access, provider credentials or owner approval were available.
- No secrets were read or printed.

Pilot conclusion:

- Native pilot is the correct next path after owner approves provider, budget,
  data classes and pilot group.
- There is no current proof that a sidecar, fork or custom search gateway is
  required.

## 2. Documents Created Or Updated

Created:

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` - compact domain entrypoint.
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md` - query/data
  egress rules.
- `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md` - sanitized
  usage/cost event model.
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md` - grounded
  answer/source display rules.
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md` -
  native/wrapper/sidecar/fork boundary.
- `docs/stage2/research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md` - current
  provider/OpenWebUI research.
- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md` - controlled
  native pilot plan.
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md` -
  read-only runtime probe.
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md` -
  this closeout.

Updated:

- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `README.md`

## 3. Provider Recommendation

Primary recommendation:

- Brave `brave_llm_context` for first paid native smoke if foreign provider use
  and budget are approved.

Why:

- native OpenWebUI support;
- AI/agent-oriented context path;
- simpler first smoke than self-hosting SearXNG;
- less page-fetch dependency than Brave classic;
- clear pricing and rate-limit guidance.

Alternatives:

- private SearXNG if owner rejects foreign paid API use and accepts ops burden;
- Yandex Search API if RU-provider policy/procurement is decisive, but only
  after metadata-forwarding/cost-mode review;
- defer provider if data/cost/group-scope decisions are not approved.

## 4. Runtime Findings

Proven locally:

- repo is on `main` at `be49bbdbcab56a50e7d88a80e22a78073740b8ca`;
- origin is `https://github.com/Kwentin3/corp-openweb-ui.git`;
- `origin/main` matches local `HEAD`;
- only `main` exists on origin;
- OpenWebUI image/tag is pinned as `ghcr.io/open-webui/open-webui:v0.9.6` in
  local config/docs;
- no running local OpenWebUI container was visible through `docker ps`.

Not proven live:

- exact deployed build info beyond pinned tag;
- Admin UI Web Search availability;
- provider dropdown contents;
- group permission behavior;
- source display;
- no browser key exposure;
- logging sanitization;
- proxy/trust-env behavior;
- analytics/cost visibility;
- RU/EN provider smoke.

## 5. Risks

- Privacy: minimized query must be enforced by policy/instruction; sensitive
  data must not leave the system.
- Cost: agentic/multiple-query behavior can multiply provider requests.
- Source quality: sources may be stale, weak or conflicting.
- RU quality: Brave/foreign providers need RU smoke; Yandex needs privacy/cost
  approval.
- Provider availability: 429/timeouts must be visible.
- Logs: raw queries/results must not be logged by default.
- Permissions: Web Search must not bypass group policy.
- Retention: metadata retention period is not yet approved.

## 6. Blockers And Decisions

Real blockers for live smoke:

- deployed/staging Admin UI access;
- approved provider key path;
- owner provider/budget/data-class/group-scope decision.

Owner decisions:

- Brave, private SearXNG, Yandex or defer;
- allowed foreign-provider data class;
- forbidden query examples;
- result count/concurrency defaults;
- metadata retention;
- whether native/provider-dashboard cost visibility is enough.

Implementation follow-ups:

- run native runtime smoke;
- record source display and permission evidence;
- record sanitized logging/secret exposure evidence;
- decide whether usage-event implementation is needed after native analytics
  gap is proven.

Nice-to-have:

- compare Brave classic vs `brave_llm_context`;
- private SearXNG latency/quality benchmark;
- Yandex parser/mode smoke after privacy approval.

## 7. Recommended Next Slice

Run a controlled native Brave `brave_llm_context` smoke, only after owner
approval and credential path are available.

Bounded task:

1. Confirm deployed OpenWebUI version/Admin UI settings.
2. Configure native Web Search with result count `3`, concurrency `1`.
3. Use approved server-side provider key path.
4. Run 3 RU and 3 EN safe queries.
5. Verify source links/cards, permission behavior, no browser key exposure,
   logs, proxy/trust-env, no-results and cost visibility.
6. Produce sanitized runtime evidence report.

Stop if provider keys appear in browser, raw sensitive query text is logged,
source attribution is absent, permission bypass is found or costs cannot be
observed at all.

## 8. Questions For Owner

- Choose Brave, private SearXNG, Yandex or defer?
- Are foreign providers allowed for ordinary non-sensitive business queries?
- Which data classes are always forbidden for Web Search?
- Is native/provider-dashboard cost visibility enough for pilot?
- Who owns provider account and billing?
- Which groups receive access first?
- Is native OpenWebUI source display sufficient for acceptance?
- What retention period applies to sanitized Web Search metadata?
