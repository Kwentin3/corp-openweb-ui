# OpenWebUI Stage 2 Web Search Anamnesis Audit

Date: 2026-06-23

Superseded by:
`docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`.
This report remains the pre-smoke anamnesis snapshot; later same-day runtime
work proved the Brave baseline.

Verdict: `superseded_by_brave_runtime_baseline`

Scope: audit/anamnesis only. No production code was written. Runtime was not
changed. No live provider smoke was run. `.env`, provider keys, admin
credentials, private URLs and customer data were not read.

## 1. Executive Summary

Project: `Kwentin3/corp-openweb-ui`, local operational checkout:
`D:\Users\Roman\Desktop\Проекты\corp-openweb ui`.

Current active feature: Stage 2 / PRD-1 / Web Search.

Closed feature: Stage 2 STT MVP is documented as implemented/proven/current
stage closed. It should not be reopened in the Web Search slice.

Current phase: provider/runtime-smoke preparation. The documentation domain,
privacy/source/usage contracts, native pilot plan, SearXNG optional overlay and
Brave-vs-SearXNG comparison plan exist in current `HEAD` and `origin/main`.

The expected statement from the task is mostly confirmed, with one correction:

> Stage 2 Web Search is in provider/runtime-smoke preparation phase. Docs and
> SearXNG optional overlay are prepared. At that time, live provider smoke was
> not yet proven.
> Next practical path is Brave native smoke, then SearXNG comparison smoke, then
> Yandex privacy/data-egress review.

Correction: docs refine is not pending anymore. It was completed in
`docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOCS_REFINE_CANDIDATE_SET_MODEL.report.md`.

Nearest fork in the road:

- if owner approves live smoke, runtime access and approved server-side key
  path, run Brave `brave_llm_context` native smoke first;
- if owner wants self-host comparison evidence, run private SearXNG runtime
  smoke on a Linux-container Docker/Compose host;
- do not run Yandex live smoke before privacy/data-egress review.

## 2. Current Repo State

Commands required by the task were rerun in this audit.

| Check | Current result |
| --- | --- |
| Branch/status | `## main...origin/main` |
| Uncommitted changes before this report | none |
| `HEAD` | `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |
| `origin/main` | `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |
| Previous recorded SHA | `be49bbdbcab56a50e7d88a80e22a78073740b8ca` |
| New commits after previous SHA | yes, two commits |
| `origin` | `https://github.com/Kwentin3/corp-openweb-ui.git` |
| Extra remote | `old-origin` still points to `Kwentin3/corp-hermes.git` |
| Remote heads | only `refs/heads/main` at `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |

Recent commits after `be49bbdbcab56a50e7d88a80e22a78073740b8ca`:

| Commit | Meaning | File count / summary |
| --- | --- | --- |
| `7cbb9ed docs: prepare web search native pilot` | Created native Web Search context, ADR/contracts/plans and runtime probe reports. | 15 files, 2261 insertions, 94 deletions |
| `7d0e02c docs: prepare web search candidate comparison` | Added docs refine, SearXNG optional overlay/config and candidate comparison plan. | 21 files, 1648 insertions, 24 deletions |

Files changed or created since the previous recorded SHA:

- `.env.example`
- `README.md`
- `compose/searxng.debug.compose.yml`
- `compose/searxng.private.compose.yml`
- `deploy/searxng/limiter.toml`
- `deploy/searxng/settings.yml`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md`
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_CONTEXT_RECON.report.md`
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOCS_REFINE_CANDIDATE_SET_MODEL.report.md`
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md`
- `docs/reports/2026-06-20/OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`
- `docs/stage2/research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md`

Note: `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` still states that its
operational source is the old `be49bbd...` SHA. In the current repo that is now
stale documentation context, not the current checkout truth.

## 3. Timeline / Anamnesis

| Date | Artifact / decision | Meaning | Current status |
| --- | --- | --- | --- |
| 2026-06-16 | PRD-0 post-acceptance / Stage 2 boundary docs | Web Search remained outside PRD-0 runtime scope; Stage 2 boundaries were clarified. | Historical context |
| 2026-06-18 | Stage 2 / PRD-1 actualization | Web Search became a Practical Stage 2 area, gated by data policy, provider choice and runtime proof. | Current Stage 2 context |
| 2026-06-19 | STT runtime completion and MVP closure reports | STT MVP implemented/proven/current-stage closed. | Do not reopen for Web Search |
| 2026-06-20 | `OPENWEBUI_WEB_SEARCH_CONTEXT_RECON.report.md` | Reconstructed Web Search context; native OpenWebUI first; no sidecar/fork before proof. | Superseded by later same-day docs, still useful |
| 2026-06-20 | `OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md` | Created Web Search contracts, ADR update, research, pilot plan and runtime probe. | Documentation domain ready |
| 2026-06-20 | `OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md` | Read-only probe; at that time live runtime smoke was blocked by access/key/approval. | Superseded by 2026-06-23 Brave runtime baseline |
| 2026-06-20 | `OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md` | Prepared optional private SearXNG overlay/config and smoke plan. | Static/config ready; runtime proof was still pending at that time |
| 2026-06-20 | `OPENWEBUI_WEB_SEARCH_DOCS_REFINE_CANDIDATE_SET_MODEL.report.md` | Refined SearXNG as candidate discovery/meta-search comparison track, not a Brave/Yandex replacement. | Completed |
| 2026-06-20 | `WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` | Defines Brave vs SearXNG query matrix, capture format, scoring and recommendation values. | Ready for runtime comparison after approvals |
| 2026-06-23 | This audit | Revalidated current local checkout after pause. | Created |

## 4. Owner Decisions

Owner decisions already recorded or carried by the task context:

- STT is closed for the current stage; do not reopen it.
- Web Search is the active Stage 2 / PRD-1 feature.
- Provider matrix is Brave, private SearXNG and Yandex.
- Brave Search API / `brave_llm_context` is primary paid native smoke path.
- Private SearXNG is a self-hosted meta-search comparison track and candidate
  set generator.
- Yandex Search API is later RU-provider candidate after privacy/data-egress
  review.
- Owner stated Brave account/API key exists. This audit did not read or verify
  the key.

Owner decisions still needed before runtime:

- approval to run live Brave smoke;
- approved server-side storage path for the Brave key;
- runtime/Admin UI access path for the deployed or staging OpenWebUI instance;
- pilot group scope;
- allowed data classes for foreign provider search;
- forbidden query examples;
- result count/concurrency if different from `3` and `1`;
- metadata/log retention period;
- whether native/provider-dashboard cost visibility is enough for pilot;
- Yandex account/API key status and privacy/data-egress approval;
- whether SearXNG smoke runs before or after Brave;
- allowed SearXNG upstream engines;
- SearXNG image tag policy: `latest` only for discovery or pinned immediately.

## 5. Current Artifacts Inventory

All files explicitly requested by the task exist locally, in current `HEAD`, and
in current `origin/main`. None had uncommitted changes at audit start.

| Artifact | Exists? | Last modified | Purpose | Runtime effect | Current status |
| --- | --- | --- | --- | --- | --- |
| `README.md` | yes | 2026-06-20 10:03:47 | Root navigation; links Stage 2 Web Search context. | Docs only | Present |
| `.env.example` | yes | 2026-06-20 10:20:09 | Placeholder env contract; includes SearXNG/Web Search names. | None unless copied by operator | Present; no real keys read |
| `compose/openwebui.compose.yml` | yes | 2026-06-19 20:50:22 | Main OpenWebUI compose file. | Runtime when deployed | Existing base |
| `compose/searxng.private.compose.yml` | yes | 2026-06-20 10:19:52 | Optional SearXNG/OpenWebUI overlay. | No effect unless included with `-f` | Prepared |
| `compose/searxng.debug.compose.yml` | yes | 2026-06-20 10:19:52 | Optional localhost debug exposure. | No effect unless included | Prepared; not for public exposure |
| `deploy/searxng/settings.yml` | yes | 2026-06-20 10:20:09 | SearXNG config. | Mounted only when overlay runs | Static validated by prior report |
| `deploy/searxng/limiter.toml` | yes | 2026-06-20 10:19:52 | SearXNG limiter config. | Mounted only when overlay runs | Prepared |
| `OPENWEBUI_WEB_SEARCH_CONTEXT_RECON.report.md` | yes | 2026-06-20 12:03:14 | Initial context recon. | Docs only | Present |
| `OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md` | yes | 2026-06-20 10:03:47 | Domain/probe closeout. | Docs only | Present |
| `OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md` | yes | 2026-06-20 10:03:47 | No-secrets runtime readiness probe. | Docs only | Present; live smoke blocked |
| `OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md` | yes | 2026-06-20 12:03:14 | SearXNG overlay/config evidence. | Docs only | Present |
| `OPENWEBUI_WEB_SEARCH_DOCS_REFINE_CANDIDATE_SET_MODEL.report.md` | yes | 2026-06-20 12:05:41 | Product-model refine. | Docs only | Present; refine completed |
| `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` | yes | 2026-06-20 12:03:14 | Web Search entrypoint. | Docs only | Present; contains stale old SHA |
| `WEB_SEARCH_NATIVE_PILOT_PLAN.md` | yes | 2026-06-20 12:03:14 | Brave/native smoke plan. | Docs only | Ready for approval |
| `SEARXNG_PRIVATE_INSTANCE_PLAN.md` | yes | 2026-06-20 12:03:14 | SearXNG runtime-smoke plan. | Docs only | Ready for stage/Linux Docker |
| `WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` | yes | 2026-06-20 12:03:14 | Originally Brave/SearXNG comparison; superseded by three-path closeout. | Docs only | Ready for comparison task |
| `ADR-0007-web-search-provider.md` | yes | 2026-06-20 12:03:14 | Provider ADR. | Docs only | Proposed for owner review |
| `ADR-0001-data-policy-by-provider-class.md` | yes | 2026-06-18 21:36:36 | Provider-class data policy. | Docs only | Proposed; still a policy dependency |
| `WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md` | yes | 2026-06-20 12:03:14 | Query/data egress rules. | Docs only | Draft |
| `WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md` | yes | 2026-06-20 12:03:14 | Grounding/source rules. | Docs only | Draft |
| `WEB_SEARCH_USAGE_EVENT_CONTRACT.md` | yes | 2026-06-20 10:03:47 | Sanitized usage/cost event expectations. | Docs only | Draft |
| `OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md` | yes | 2026-06-20 10:03:47 | Native/wrapper/sidecar/fork order. | Docs only | Draft |
| `WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md` | yes | 2026-06-20 12:03:14 | Provider/runtime research. | Docs only | Current local research |
| `ACCEPTANCE_MATRIX.md` | yes | 2026-06-20 12:03:14 | Acceptance checklist. | Docs only | Updated for Web Search |
| `TEST_DATA_REQUIREMENTS.md` | yes | 2026-06-20 12:03:14 | Query/test data requirements. | Docs only | Updated for Web Search |
| `DOCKER_COMPOSE_PLAN.md` | yes | 2026-06-20 12:03:14 | Compose operations plan. | Docs only | Updated |
| `ENVIRONMENT_VARIABLES.md` | yes | 2026-06-20 12:03:14 | Env variable reference. | Docs only | Updated |

## 6. Runtime Proof Status

### Proven / Prepared With Evidence

- Local current `HEAD` equals `origin/main` at
  `7d0e02c24808f3501e7c92b0ce48fcee646aa393`.
- `origin` points to `Kwentin3/corp-openweb-ui`.
- `git ls-remote --heads origin` shows only `main`.
- OpenWebUI base image remains pinned in compose/env example to
  `ghcr.io/open-webui/open-webui:v0.9.6`; repo image is
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-v1`.
- Native-first Web Search route is documented.
- Privacy, source-attribution, usage-event and integration-boundary contracts
  exist.
- Brave remains primary paid native smoke path in the docs.
- SearXNG optional overlay/config exists and is not active by default.
- Prior SearXNG report states YAML parse passed for the SearXNG compose/config
  files.
- Candidate-set comparison plan exists.
- Prior docs refine states secret scan found placeholders/env references only,
  not real secrets.

### Not Proven Live

- deployed/staging Admin UI Web Search settings;
- selected provider dropdown contents;
- Brave live smoke;
- SearXNG live smoke;
- Yandex live smoke;
- source cards/links in OpenWebUI;
- final answer grounding from Web Search evidence;
- group/feature permissions for allowed and blocked users;
- no provider key exposure in browser responses/config/storage;
- logging sanitization and retention behavior;
- analytics/cost visibility;
- proxy/trust-env behavior;
- SSRF/web-loader/fetch boundary;
- current deployed build beyond repo-pinned image/config.

### Blocked By

- no runtime/Admin UI access in this audit;
- no approved live provider smoke permission;
- no approved provider key path supplied to the audit;
- SearXNG runtime needs Linux-container Docker host with Compose;
- Yandex needs privacy/data-egress review before any live smoke.

## 7. Architecture Status

Current architectural line is coherent and should be preserved:

- native OpenWebUI Web Search first;
- no sidecar for the first Web Search slice;
- no fork;
- provider keys server-side only: Admin UI/env/approved secret store;
- OpenWebUI native Web Search config is the first route;
- `external` provider or thin wrapper only after native proof shows a concrete
  policy/runtime gap;
- private sidecar only after native/external-wrapper paths cannot satisfy
  privacy, cost, source or runtime requirements;
- deep fork only after separate proof, owner approval and ADR;
- SearXNG is an optional self-hosted comparison track, not a custom gateway;
- Yandex is deferred until privacy/data-egress review.

No current Web Search document found in the requested set justifies a sidecar or
fork before native runtime proof. Mentions of STT sidecar are STT-specific and
must not be transferred to Web Search without proof.

## 8. SearXNG Conceptual Status

The conceptual correction is reflected in current docs.

SearXNG is documented as:

- self-hosted meta-search gateway;
- candidate set generator;
- normalizer/aggregator of upstream results;
- private instance boundary;
- optional comparison track.

SearXNG is explicitly not documented as:

- full web index;
- privacy guarantee;
- replacement for Brave/Yandex;
- LLM;
- final answer generator.

Important nuance: private SearXNG can keep the instance internal, but enabled
upstream engines/public sources can still receive minimized queries. Public
SearXNG instances remain prohibited for corporate acceptance.

## 9. Comparison Program Status

`docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
exists. Brave Path A now has a runtime baseline; SearXNG Path B remains pending.

Comparison paths:

- Path A: `OpenWebUI -> Brave brave_llm_context -> candidate/context -> LLM answer`
- Path B: `OpenWebUI -> private SearXNG -> upstream engines/public sources -> candidate set -> OpenWebUI web loader -> LLM answer`
- Path C later: `OpenWebUI -> Yandex Search API -> candidate set -> LLM answer`

The plan defines:

- same RU/EN/freshness/conflicting/no-evidence query set for both paths;
- capture format for candidate URLs, snippets, source/provider, latency,
  logs/privacy and cost/ops notes;
- 0-3 scoring for candidate relevance, answer groundedness, source quality,
  stability and operational fit;
- output report path:
  `docs/reports/YYYY-MM-DD/OPENWEBUI_WEB_SEARCH_THREE_PATH_COMPARISON.report.md`.

Current readiness: comparison design is prepared; runtime evidence is missing.

## 10. Risk Register

| Risk | Severity | Current control | Remaining action |
| --- | --- | --- | --- |
| Brave foreign provider privacy/cost | High | Privacy contract, low result count/concurrency, owner approval gate. | Approve allowed data classes, budget and key path before smoke. |
| SearXNG upstream leakage | High | Docs state private instance is a boundary only. | Owner approves upstream engines and allowed query classes. |
| SearXNG CAPTCHA/rate-limit | Medium | Low concurrency, limiter, no default public port. | Runtime smoke and quality/empty-result monitoring. |
| Public SearXNG instance misuse | High | Docs prohibit public SearXNG for corporate acceptance. | Verify runtime uses private/internal instance only. |
| Yandex metadata forwarding / chat id / user info | High | Yandex deferred behind privacy review. | Review Yandex path before any smoke. |
| Raw query/result logs | High | Usage/privacy contracts prohibit default raw retention. | Inspect sanitized runtime logs after smoke. |
| Source attribution insufficient | High | Source attribution contract requires visible sources and no confident grounded answer without evidence. | Verify source cards/links in OpenWebUI. |
| Group permission bypass | High | Acceptance matrix requires allowed/blocked user checks. | Runtime permission smoke. |
| Cost visibility insufficient | Medium | Native/provider dashboard first, hard billing separated. | Prove dashboard/native visibility or record accepted gap. |
| SearXNG image `latest` drift | Medium | Report flags pin-before-production. | Owner chooses tag policy before production-like rollout. |
| Docker/Compose runtime mismatch | Medium | Static config prepared; prior local blocker recorded. | Run on Linux-container Docker host with Compose. |
| Stale SHA in Web Search context index | Low | Current audit records true `HEAD/origin/main`. | Future docs cleanup can update stale source line. |
| Overbuilding sidecar/fork too early | Medium | Integration boundary forbids it before native proof. | Keep first slice native unless runtime proof shows a gap. |

## 11. Blockers vs Decisions

### Real Blockers

- No deployed/staging Admin UI/runtime access in this audit.
- No approved live smoke permission in this audit.
- No approved provider key path was supplied to the audit.
- Private SearXNG runtime smoke needs Linux-container Docker/Compose host.
- Yandex live smoke is blocked until privacy/data-egress review.

### Owner Decisions

- Provider order: Brave first, SearXNG before/after Brave, or defer.
- Pilot group scope.
- Allowed/forbidden data classes.
- Budget and monthly stop condition.
- Metadata/log retention.
- Whether native/provider-dashboard cost visibility is enough.
- SearXNG upstream engines.
- SearXNG image tag policy.
- Yandex account/key and metadata-forwarding acceptability.

### Not Blockers

- No Web Search sidecar.
- No OpenWebUI fork.
- No hard billing gateway in the first native smoke.
- No Yandex key for first Brave smoke.
- SearXNG not being fully private.
- SearXNG not owning a full web index.

## 12. Recommended Next Bounded Tasks

### 1. Owner Preflight For Brave Native Smoke

Goal: approve the exact runtime conditions for first live Web Search smoke.

Input conditions:

- owner approves Brave live smoke;
- server-side key path is selected;
- runtime/Admin UI access is available;
- allowed data classes and pilot group are selected.

Result:

- short owner decision note or task prompt for Brave smoke.

Stop conditions:

- no approved key path;
- no runtime access;
- foreign provider use not approved for ordinary non-sensitive queries.

### 2. Brave Native Smoke Report

Goal: prove native OpenWebUI `brave_llm_context` behavior with sanitized
evidence.

Input conditions:

- approved Brave key stored server-side;
- Admin UI/runtime access;
- safe RU/EN query set;
- result count `3`, concurrency `1` unless owner changes them.

Result:

- `docs/reports/YYYY-MM-DD/OPENWEBUI_WEB_SEARCH_BRAVE_NATIVE_SMOKE.report.md`
  with source cards, permissions, no-key-exposure, logs, proxy and cost
  visibility evidence.

Stop conditions:

- provider key appears in browser/logs;
- source attribution absent;
- permission bypass found;
- costs cannot be observed at all and owner has not accepted the gap.

### 3. Private SearXNG Runtime Smoke

Goal: prove the prepared optional overlay on a Linux-container Docker/Compose
host.

Input conditions:

- owner approves optional compose overlay;
- generated server-local `SEARXNG_SECRET`;
- allowed upstream engines;
- Linux-container Docker host with Compose;
- runtime access.

Result:

- direct `/healthz` and JSON API smoke;
- OpenWebUI native `searxng` smoke;
- sanitized report.

Stop conditions:

- public exposure required;
- JSON output fails;
- upstream leakage not accepted;
- logs retain raw sensitive query content.

### 4. Brave vs SearXNG Comparison Report

Goal: compare candidate set and answer grounding using the same query matrix.

Input conditions:

- Brave native smoke passed or failed with typed evidence;
- SearXNG runtime smoke passed or failed with typed evidence;
- same query matrix approved.

Result:

- `OPENWEBUI_WEB_SEARCH_THREE_PATH_COMPARISON.report.md` with candidate
  quality, source quality, answer groundedness, latency, logs/privacy and
  cost/ops comparison.

Stop conditions:

- one path lacks minimum runtime evidence;
- query set cannot be run safely;
- source/candidate capture is unavailable.

### 5. Yandex Privacy/Data-Egress Review

Goal: decide whether Yandex Search API is allowed as RU-provider path.

Input conditions:

- Yandex account/API-key status known;
- owner wants RU-provider path considered;
- privacy review includes user-info/chat-id forwarding and mode/cost behavior.

Result:

- decision/checklist for Yandex onboarding or deferral.

Stop conditions:

- metadata forwarding cannot be accepted;
- pricing/mode cannot be bounded;
- provider terms/procurement are unresolved.

## 13. Final Owner-Facing Summary

We stopped after preparing the Web Search documentation, provider strategy,
contracts, optional private SearXNG overlay and Brave-vs-SearXNG comparison
plan.

What is ready:

- native-first architecture and provider order;
- Brave first-smoke plan;
- private SearXNG optional overlay/config and smoke plan;
- candidate-set comparison model and plan;
- privacy/source/usage contracts;
- acceptance/test-data requirements.

What is not ready:

- no live Brave smoke;
- no live SearXNG smoke;
- no live Yandex smoke;
- no runtime proof for Admin UI settings, source cards, permissions, browser
  key exposure, logs or cost visibility.

What to do first:

- approve and run Brave native smoke through an approved server-side key path,
  or explicitly decide to run SearXNG first for comparison.

Owner decisions needed:

- live smoke approval;
- provider order;
- key path;
- pilot group;
- allowed/forbidden data classes;
- budget/cost visibility rule;
- retention/logging policy.

Do not do prematurely:

- do not reopen STT;
- do not build Web Search sidecar/fork;
- do not use public SearXNG for corporate acceptance;
- do not run Yandex before privacy/data-egress review;
- do not claim SearXNG/Yandex/provider comparison smoke passed until it is
  actually run.

## 14. Final Verdict

`superseded_by_brave_runtime_baseline`

Reason: this report captured the pre-smoke state. Later same-day work proved
the Brave `brave_llm_context` native runtime baseline and recorded it in
`OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`. SearXNG is prepared for
comparison runtime smoke, not promoted to primary. Yandex remains deferred
pending privacy/data-egress review.
