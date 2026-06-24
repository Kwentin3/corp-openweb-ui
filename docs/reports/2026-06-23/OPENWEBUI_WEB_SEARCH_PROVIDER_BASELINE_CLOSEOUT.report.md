# OpenWebUI Web Search Provider Baseline Closeout

Date: 2026-06-23

Scope: Stage 2 / PRD-1 / Web Search provider connectivity, native runtime
baseline and comparison readiness.

Verdict: `web_search_provider_baseline_closed_with_yandex_full_evidence_pending`

## 1. Executive Summary

Stage 2 Web Search provider connectivity is no longer blocked by missing
provider runtime proof. Three native OpenWebUI paths now have baseline status:

- Brave `brave_llm_context`: proven direct-context native baseline.
- Yandex Search API: working RU direct API path by owner/operator confirmation.
- Private SearXNG: proven private native meta-search path in snippet/bypass
  mode.

This is not a production rollout closeout. Production rollout, full
Brave/Yandex/SearXNG comparison, permission gates, logging/retention and cost
visibility remain pending.

## 2. Scope And Non-Goals

This closeout covers:

- provider connectivity;
- native runtime baseline status;
- comparison readiness;
- documentation alignment after Brave, Yandex and SearXNG checks.

This closeout does not cover:

- all-user or pilot rollout approval;
- new live smoke execution;
- `.env` or API key inspection;
- STT/mobile microphone issues;
- sidecar/fork/custom gateway design;
- full page loading;
- vectorized `web-search-*` retrieval.

## 3. Provider Matrix Final Status

| Provider path | Current status | Role | Proof level | Not proven |
| --- | --- | --- | --- | --- |
| Brave `brave_llm_context` | works | current direct-context native baseline | runtime baseline report | full EN/RU comparison, rollout gates |
| Yandex `yandex` | works by owner/operator confirmation | RU direct API path | operator-confirmed baseline report | source cards, logs, browser key exposure, permissions, cost/metadata review |
| Private SearXNG `searxng` | works in snippet/bypass mode | private meta-search comparison path | runtime smoke report | full page loading, vectorized retrieval, primary-provider viability |

## 4. What Changed Since Pre-Smoke

- Brave has moved from pre-smoke troubleshooting to a working direct-context
  `brave_llm_context` path with web-loader and web-search embedding/retrieval
  bypass.
- Yandex is documented as a working RU direct API path, with proof level
  explicitly limited to owner/operator confirmation.
- SearXNG moved from prepared runtime-smoke candidate to proven native
  snippet/bypass provider path.
- The comparison plan now targets three paths, not only Brave vs SearXNG.
- SearXNG runtime docs now include the limiter passlist and `NO_PROXY` recreate
  requirement observed during smoke.

## 5. Runtime Proof Summary

Brave:

- `brave_llm_context` native smoke baseline passed on 2026-06-23.
- Accepted baseline: result count `3`, search concurrency `1`,
  `BYPASS_WEB_SEARCH_WEB_LOADER=true`,
  `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true`,
  `BRAVE_SEARCH_CONTEXT_TOKENS=8192`.
- The broken vectorized retrieval path is not accepted as baseline.

Yandex:

- Added through OpenWebUI Web GUI/Admin UI.
- Owner/operator confirmed that search works.
- Dedicated report created with verdict
  `yandex_native_search_operator_confirmed; full_smoke_evidence_pending`.

SearXNG:

- Started through optional private compose overlay.
- Direct JSON passed after limiter config was adjusted for private Docker
  caller.
- OpenWebUI native provider path passed after `NO_PROXY` was applied through
  native overlay recreate.
- Six safe RU/EN queries returned `200` with source items in snippet/bypass
  mode.
- SearXNG and Valkey were stopped after evidence collection; OpenWebUI provider
  config was restored to Yandex.

## 6. Known Issues

- Vectorized `web-search-*` retrieval can return zero sources after successful
  search/embedding. Keep it deferred unless long pages, classic `brave`,
  SearXNG page loading or full RAG over fetched content becomes necessary.
- Full page loading is not proven for the provider baseline.
- Yandex source cards/logs/browser-key exposure/permissions/cost evidence remain
  pending.
- SearXNG upstream instability was observed: DuckDuckGo CAPTCHA and
  Brave-through-SearXNG rate-limit noise.
- SearXNG narrows the private instance boundary, but upstream engines may still
  receive minimized queries and it does not own a global search index.

## 7. Docs Updated

- `README.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/blueprints/WEB_SEARCH.blueprint.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_ANAMNESIS_AUDIT.report.md`

## 8. Accepted Baseline Configs

Brave direct-context baseline:

```text
WEB_SEARCH_ENGINE=brave_llm_context
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
BYPASS_WEB_SEARCH_WEB_LOADER=true
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true
BRAVE_SEARCH_CONTEXT_TOKENS=8192
```

Yandex RU path:

```text
WEB_SEARCH_ENGINE=yandex
YANDEX_WEB_SEARCH_URL=https://searchapi.api.cloud.yandex.net/v2/web/search
```

The real Yandex key remains server-local/Admin UI only.

SearXNG comparison path:

```text
WEB_SEARCH_ENGINE=searxng
SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>
OPENWEBUI_NO_PROXY includes searxng,searxng:8080,searxng-valkey
```

Use SearXNG only through the private overlay unless owner explicitly approves a
different exposure model.

## 9. Pending Gates

- three-path comparison;
- pilot group selection;
- ordinary-user allow/deny permissions;
- forbidden query handling;
- logs/retention;
- browser secret exposure checks;
- source cards and final answer groundedness matrix;
- cost visibility and budget guardrails;
- Yandex metadata-forwarding review;
- SearXNG engine tuning and image pinning if it remains valuable.

## 10. Recommended Next Bounded Tasks

1. Run Brave vs Yandex vs private SearXNG candidate-set comparison.
2. Close rollout policy gates: pilot group, permissions, forbidden queries,
   logs/retention and cost visibility.
3. Tune SearXNG only if comparison shows value: engine allowlist, RU quality,
   CAPTCHA/rate-limit handling and image pinning.
4. Keep vectorized retrieval and long page loading as separate known issues.

## 11. Final Verdict

`web_search_provider_baseline_closed_with_yandex_full_evidence_pending`

The project can now move from "can OpenWebUI reach working search providers?"
to "which provider path is best enough for pilot, under what policy and cost
constraints?"
