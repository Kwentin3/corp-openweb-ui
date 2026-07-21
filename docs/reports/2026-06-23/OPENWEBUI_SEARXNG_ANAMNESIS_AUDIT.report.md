# OpenWebUI SearXNG Anamnesis Audit

Date: 2026-06-23

Scope: Stage 2 / PRD-1 / Web Search / private SearXNG.

Verdict: `searxng_ready_but_should_follow_direct_provider_comparison`

Superseded runtime note: this was a pre-smoke anamnesis report. The later
runtime smoke report on 2026-06-23 proves private SearXNG native provider
connectivity in snippet/bypass mode. Keep this report for historical audit
context, not as the current runtime status.

## 1. Executive Summary

Private SearXNG is prepared in the repo as an optional self-hosted meta-search
comparison track. The committed package includes compose overlays, SearXNG
settings, limiter config, env placeholders, implementation plan, acceptance
hooks and prior reports.

At the time of this anamnesis audit, SearXNG runtime proof had not yet been
collected. That gap was later closed for native snippet/bypass provider
connectivity by
`docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`. Full page
loading, permissions, cost/logging gates and the complete RU/EN comparison
matrix remain outside that smoke.

Brave `brave_llm_context` already works as the direct API baseline. Yandex
Search API also passed Admin UI/native smoke and is now the working RU direct
API path. SearXNG is therefore no longer needed to make Web Search work at all.
Its remaining value is comparative: whether a private meta-search gateway is
worth running as a fallback/alternative candidate-discovery path.

Recommended next move: first produce a dedicated Yandex runtime baseline report
if one does not already exist, then update the comparison output/report shape to
cover Brave / Yandex / SearXNG consistently, then run SearXNG runtime smoke as
the third comparison path if the owner still wants that evidence.

## 2. Current Repo State

Repository: `Kwentin3/corp-openweb-ui`

Working directory audited:

```text
<repository-root>
```

Git state checked:

| Check | Result |
| --- | --- |
| Branch | `main...origin/main` |
| `HEAD` | `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |
| `origin/main` | `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |
| Remote heads | `origin/main` at `7d0e02c24808f3501e7c92b0ce48fcee646aa393` |
| Primary remote | `origin` -> GitHub repo `Kwentin3/corp-openweb-ui` |
| Secondary remote | `old-origin` -> GitHub repo `Kwentin3/corp-hermes` |
| Commit sync | local `HEAD == origin/main` |
| Working tree | dirty; see below |

Uncommitted changes were present before this report was created. They include
previous docs/env/compose refinements from the same workstream:

- `.env.example`
- `README.md`
- `compose/openwebui.compose.yml`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`
- multiple `docs/stage2/**` Web Search/STT docs
- untracked `docs/reports/2026-06-23/`

This means committed `HEAD` matches `origin/main`, but current local docs are
ahead of committed state through uncommitted documentation refinements.

Recent relevant commits:

| Commit | Subject | Relevance |
| --- | --- | --- |
| `7d0e02c` | `docs: prepare web search candidate comparison` | Added SearXNG overlay/config/report and candidate-set comparison package. |
| `7cbb9ed` | `docs: prepare web search native pilot` | Added native Web Search pilot docs, contracts and runtime probe framing. |
| `239a281` | `Document OpenWebUI web search provider research` | Earlier provider research baseline. |

## 3. SearXNG Artifact Inventory

| Artifact | Exists? | Purpose | Runtime effect | Current status |
| --- | --- | --- | --- | --- |
| `compose/searxng.private.compose.yml` | yes | Optional private SearXNG/OpenWebUI overlay. Adds `searxng`, `searxng-valkey`, and OpenWebUI `searxng` provider env defaults. | Only when explicitly included with `-f compose/searxng.private.compose.yml`. | Prepared; not active by default. |
| `compose/searxng.debug.compose.yml` | yes | Optional local debug exposure. | Only when explicitly included with the private overlay. | Prepared; binds to `127.0.0.1` by default. |
| `deploy/searxng/settings.yml` | yes | SearXNG settings for private Stage 2 candidate. | Mounted read-only into SearXNG only when overlay runs. | YAML-valid; placeholder secret only. |
| `deploy/searxng/limiter.toml` | yes | Limiter/bot-detection config. | Mounted read-only into SearXNG only when overlay runs. | Present; conservative empty block/pass lists. |
| `.env.example` | yes | Placeholder env contract for SearXNG, Brave, Yandex and base deployment. | None unless copied by operator to server-local `.env`. | Contains placeholders only for SearXNG values. Real `.env` was not opened. |
| `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md` | yes | SearXNG runtime-smoke plan and operational model. | Docs-only. | Superseded by runtime smoke closeout; current plan says ready for three-path comparison, not primary provider. |
| `docs/reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md` | yes | Prior SearXNG overlay/config audit and static validation report. | Docs-only. | Confirms static package and runtime blockers from 2026-06-20. |
| `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` | yes | Candidate-set comparison methodology. | Docs-only. | Brave path proven; SearXNG pending; Yandex present as optional RU path. |
| `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | yes | Acceptance matrix for Web Search. | Docs-only. | Includes SearXNG JSON/internal-only/upstream-leakage expectations. |
| `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md` | yes | Test data and query matrix requirements. | Docs-only. | Includes SearXNG query/direct JSON requirements. |
| `docs/infra/DOCKER_COMPOSE_PLAN.md` | yes | Compose operations plan. | Docs-only. | Documents private overlay, debug overlay, volumes and runtime caveats. |
| `docs/infra/ENVIRONMENT_VARIABLES.md` | yes | Env variable contract. | Docs-only. | Documents SearXNG placeholders, no-proxy, debug bind, public-instance prohibition. |

Runtime-effect files only affect the deployment when an operator explicitly
includes the SearXNG compose overlay. The docs and reports have no runtime
effect.

Files that must never contain real secrets:

- `.env.example`
- `deploy/searxng/settings.yml`
- `docs/**`
- `compose/**`

Real `SEARXNG_SECRET`, provider API keys, admin credentials and private runtime
URLs belong only in server-local `.env`, OpenWebUI Admin UI or an approved
secret store. This audit did not open the real `.env`.

## 4. Compose Topology

Private overlay services:

| Service | Role | Network | Public exposure | Volumes/state |
| --- | --- | --- | --- | --- |
| `openwebui` | Existing app; receives Web Search env defaults for `searxng` when overlay is included. | `web` -> `openwebui_web` from main compose. | Existing Traefik route only. | Existing `openwebui_data`. |
| `searxng` | Internal private meta-search service. | `web` -> `openwebui_web`. | No `ports` in private overlay; only `expose: 8080`. | `searxng_cache`, read-only settings/limiter mounts. |
| `searxng-valkey` | Valkey state for limiter/bot-detection. | `web` -> `openwebui_web`. | No `ports`; only `expose: 6379`. | `searxng_valkey`. |

OpenWebUI should reach SearXNG through the internal Docker URL:

```text
http://searxng:8080/search?q=<query>
```

The private overlay sets:

- `WEB_SEARCH_ENGINE=searxng`
- `SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>`
- `SEARXNG_LANGUAGE=ru`
- result count `3`
- search concurrency `1`
- loader concurrency `2`
- `BYPASS_WEB_SEARCH_WEB_LOADER=false`

Proxy/no-proxy:

- `OPENWEBUI_NO_PROXY` in `.env.example` and docs includes `searxng`,
  `searxng:8080` and `searxng-valkey`.
- The overlay passes this through as both `no_proxy` and `NO_PROXY`.
- This is required so OpenWebUI does not route private Docker service calls
  through the outbound proxy.

Debug overlay:

- `compose/searxng.debug.compose.yml` adds a `ports` mapping only when included.
- Default bind is `127.0.0.1:${SEARXNG_DEBUG_PORT:-18080}:8080`.
- It is intended for operator/admin troubleshooting only.
- It must not be used to expose SearXNG publicly.

Current public exposure finding:

- Private overlay has no public `ports` for `searxng` or `searxng-valkey`.
- Debug overlay is local-only by default.
- Host firewall/proxy/public reachability is not proven until runtime smoke on
  the target host.

## 5. Config Status

`deploy/searxng/settings.yml` current static properties:

| Setting | Current value/status | Audit note |
| --- | --- | --- |
| JSON output | enabled through `search.formats: html, json` | Suitable for OpenWebUI/direct JSON smoke. |
| Safe search | `safe_search: 1` | Conservative default. |
| Default language | `ru` | Matches first RU-oriented smoke. |
| Bind address | `0.0.0.0:8080` inside container | Safe only because compose keeps service internal unless debug overlay is used. |
| `public_instance` | `false` | Correct for private/internal instance. |
| `image_proxy` | `false` | Conservative first-smoke value. |
| HTTP method | `GET` | Matches OpenWebUI SearXNG query URL shape. |
| Limiter | `true` | Uses Valkey URL. |
| Valkey URL | `valkey://searxng-valkey:6379/0` | Matches compose service name. |
| Secret key | `replace-with-server-local-searxng-secret` | Placeholder only; real secret must be supplied server-side via `SEARXNG_SECRET`. |
| Google engine | removed via `use_default_settings.engines.remove: google` | Reduces CAPTCHA/policy noise for first smoke. |

`deploy/searxng/limiter.toml`:

- enables `botdetection.ip_limit.link_token`;
- keeps `block_ip=[]`;
- keeps `pass_ip=[]`;
- should be tuned only with runtime evidence.

Upstream engines:

- The committed config uses SearXNG default engines except `google`, which is
  removed.
- There is no explicit first-smoke allowlist in the committed config.
- Owner/operator still needs to approve the exact upstream engine set for the
  first runtime smoke, especially because upstream engines can see minimized
  queries.

Committed config safety:

- Real `SEARXNG_SECRET` is not committed.
- `.env.example` contains `replace-with-random-strong-searxng-secret`.
- `settings.yml` contains `replace-with-server-local-searxng-secret`.
- This is acceptable as placeholder configuration, not runtime secret material.

## 6. Static Validation Status

### Already Statically Validated

Current audit:

- YAML parse passed for:
  - `compose/searxng.private.compose.yml`
  - `compose/searxng.debug.compose.yml`
  - `deploy/searxng/settings.yml`
- `git diff --check` passed for the SearXNG compose/config/docs set. Git printed
  only Windows CRLF warnings.
- Secret-pattern scan across SearXNG compose/config/docs, `.env.example`,
  `docs/stage2` and `docs/infra` found no actual provider keys or known secret
  token shapes. The scan intentionally excluded real `.env`.
- Private overlay has no default public port for SearXNG.
- Debug overlay binds to `127.0.0.1` by default.
- `OPENWEBUI_NO_PROXY` includes SearXNG service names.

Prior report evidence:

- `OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md` recorded YAML validation,
  no-production-runtime-change, placeholder-only secret findings, and the same
  Docker/Compose blocker.

### Not Validated Yet

- Rendered Docker Compose config for the merged main + SearXNG overlays.
- Runtime-resolved environment values on the stage/server host.
- Whether `SEARXNG_SECRET` is generated and passed correctly on the target host.
- Whether SearXNG starts with the current `settings.yml` and `limiter.toml`.
- Whether SearXNG default engines minus Google are acceptable and stable.

### Blocked By Environment

Local environment blocker confirmed in this audit:

- `docker compose version` fails: Compose is not available as a Docker command.
- `docker-compose version` is not installed.
- `docker version --format '{{.Server.Os}}'` reports `windows`.
- SearXNG and Valkey images are Linux containers.

Therefore rendered compose validation and container smoke must run on a
Linux-container Docker host with Docker Compose v2 or compatible compose
binary, or on the stage/server host after owner approval.

## 7. Runtime Proof Status

### Proven

- SearXNG compose/config artifacts exist in repo.
- Optional private overlay exists and is inactive unless explicitly included.
- Private overlay is private-by-default at compose level: `expose`, no `ports`.
- Debug overlay is local-only by default.
- JSON output is configured.
- Valkey/limiter configuration exists.
- OpenWebUI internal Docker URL is documented and configured in overlay.
- `OPENWEBUI_NO_PROXY` includes SearXNG service names.
- Docs prohibit public SearXNG instances for corporate acceptance.
- Smoke commands are documented in the SearXNG plan and prior report.

### Not Proven

- `searxng` container health.
- `searxng-valkey` health.
- `/healthz` response.
- `/search?q=OpenWebUI&format=json` response and `results` shape.
- OpenWebUI native provider smoke with `WEB_SEARCH_ENGINE=searxng`.
- Source cards/links visibility in OpenWebUI UI.
- RU query quality.
- EN query quality.
- User/group permission gating.
- Quota/timeout/no-results UX.
- Runtime logs sanitized from raw sensitive query/result bodies.
- No public exposure on actual stage/server host.
- No provider key or internal endpoint leak to browser runtime.
- SSRF/local/private URL fetch boundary.
- Whether enabled upstream engines will CAPTCHA/rate-limit or return useful
  Russian results.

### Blocked By

- No owner approval in this task to run the overlay.
- No runtime/stage action in this audit by design.
- No generated server-local `SEARXNG_SECRET` was inspected or confirmed.
- Local Docker is Windows-container mode and lacks Compose.
- Upstream engine allowlist is not owner-approved.

## 8. Relation To Brave And Yandex

Current provider matrix:

| Provider path | Current status | Role |
| --- | --- | --- |
| Brave Search API / `brave_llm_context` | Works; direct-context baseline proven on 2026-06-23. | Current direct API baseline. |
| Yandex Search API | Works; Admin UI/native smoke passed on 2026-06-23 per current docs/user report. | RU direct API path. |
| Private SearXNG | Runtime smoke later passed in snippet/bypass mode. | Self-hosted meta-search comparison track. |

SearXNG is not needed now to make Web Search work. Brave and Yandex already do
that. SearXNG should be evaluated only if the owner wants evidence for one of
these questions:

- Can a self-hosted meta-search gateway provide a useful candidate set?
- Is the candidate set close enough to Brave/Yandex quality?
- What latency and source-card behavior does it create?
- Is the operational burden acceptable?
- Are upstream-engine privacy/data-egress risks acceptable?
- Is SearXNG useful as a fallback or alternative path, not as a drop-in substitute
  for direct API providers?

SearXNG must not be described as:

- a full search engine with its own global index;
- a privacy guarantee;
- a Brave/Yandex drop-in substitute;
- an LLM agent;
- a final-answer generator.

## 9. Candidate Comparison Readiness

`WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` exists and is usable as a
starting point.

Current status of that plan:

- Original status said the Brave side had a proven runtime baseline while
  SearXNG still awaited smoke; this is superseded by the runtime smoke report.
- It compares Brave and private SearXNG as candidate-set generators.
- It explicitly says SearXNG is not a universal benchmark, public SearXNG
  instance, full index, or replacement for Brave/Yandex.
- Path A: Brave `brave_llm_context` direct-context path.
- Path B: private SearXNG -> upstream engines/public sources -> normalized
  candidate set -> OpenWebUI loader -> LLM answer.
- Path C: Yandex Search API is now present as optional RU-provider path.
- The plan says Yandex should be included in controlled comparison only after
  allowed data classes, metadata-forwarding behavior and cost mode are accepted.

Query sets currently present:

- RU ordinary:
  - `актуальные ставки НДС в России 2026`
  - `изменения в 6-НДФЛ 2026`
  - `OpenWebUI SearXNG настройка`
  - `лучшие практики корпоративного AI чата`
  - `как работает Brave Search API`
- EN ordinary:
  - `OpenWebUI SearXNG web search setup`
  - `Brave Search API OpenWebUI brave_llm_context`
  - `SearXNG JSON API settings`
- freshness-sensitive examples:
  - current OpenWebUI latest stable release
  - current Brave Search API pricing
  - current Yandex Search API pricing
- conflicting-source and no-sufficient-evidence slots.
- forbidden examples are policy tests, not live external-search queries unless
  mocked or blocked by a policy gate.

Readiness gap:

- The plan has Path C for Yandex, but most wording/output template still reads
  like a Brave-vs-SearXNG report.
- A follow-up should extend the comparison report shape to three paths:
  Brave direct API baseline, Yandex direct RU API path, and private SearXNG
  meta-search path.
- Future comparison report input should include:
  - provider/path;
  - query text or query hash;
  - candidate URLs/titles/snippets/source provider;
  - source-card visibility;
  - latency;
  - errors/no-results/CAPTCHA/rate-limit;
  - log/privacy observations;
  - cost/ops notes;
  - final answer groundedness.

## 10. SearXNG Risk Register

| Risk | Severity | Current control | Remaining action |
| --- | --- | --- | --- |
| Upstream engines see minimized queries. | High | Docs state SearXNG is only a private instance boundary, not private upstream search. | Owner approves upstream engines and allowed query classes before live smoke. |
| Public SearXNG instance misuse. | High | Docs prohibit public SearXNG instances for corporate acceptance. | Runtime smoke must verify private/internal instance only. |
| Accidental public exposure. | High | Private overlay has no `ports`; debug overlay binds `127.0.0.1` by default. | Confirm host firewall/proxy routes and debug bind on stage. |
| CAPTCHA/rate-limit from upstream engines. | Medium | Google removed; result count/concurrency low; limiter enabled. | Runtime quality monitoring and engine allowlist tuning. |
| HTML/parser drift. | Medium | Treat SearXNG as comparison track, not baseline. | Monitor empty-result/error rate after smoke; review SearXNG templates before upgrades. |
| Weak RU source quality. | Medium | Default language `ru`; RU query set exists. | Run RU matrix against Brave/Yandex before promotion. |
| Unstable source cards. | Medium | Candidate/source attribution contract exists. | OpenWebUI UI smoke must capture source cards. |
| Raw query logs. | High | Privacy contract forbids raw sensitive query/result retention by default. | Inspect sanitized runtime logs after smoke; never print sensitive queries. |
| Valkey/limiter misconfig. | Medium | Valkey service and limiter config exist. | Prove Valkey health and limiter behavior in runtime smoke. |
| `latest` image drift. | Medium | Docs say `latest` acceptable only for initial discovery if owner accepts. | Pin reviewed image before production-like rollout. |
| Proxy/no-proxy issue. | Medium | `OPENWEBUI_NO_PROXY` includes SearXNG services. | Prove OpenWebUI reaches `http://searxng:8080` internally on stage. |
| `ENABLE_RAG_LOCAL_WEB_FETCH` accidentally enabled. | High | SearXNG plan says keep it disabled unless separately approved. | Check runtime env/config before smoke; stop if enabled without approval. |
| Ops burden greater than value. | Medium | SearXNG remains comparison track. | Compare quality/latency/maintenance against Brave/Yandex. |
| SearXNG duplicates Brave/Yandex without added value. | Medium | Docs say do not promote if it only proxies Brave API or quality is weaker. | Run comparison and reject/defer if no distinct value appears. |

## 11. Owner / Operator Decisions Needed

Before SearXNG runtime smoke, owner/operator must decide:

1. Run SearXNG smoke now, or after Brave/Yandex direct-provider comparison.
2. Target host: stage/server/Linux Docker host with Compose.
3. Permission to include `compose/searxng.private.compose.yml`.
4. Whether debug overlay may be used, and only local-only by default.
5. Generate `SEARXNG_SECRET` server-side and store it in server-local `.env` or
   approved secret storage.
6. Image tag policy: allow `latest` only for discovery, or pin immediately.
7. Upstream engine allowlist for first smoke.
8. Default language for first smoke: currently `ru`.
9. Retention/logging policy for SearXNG/OpenWebUI logs.
10. Whether SearXNG is intended as fallback provider, comparison-only track, or
    candidate for later promotion.
11. Whether SearXNG is still worth testing now that Brave and Yandex both work.

## 12. Recommended Next Bounded Tasks

### A. Run SearXNG Runtime Smoke

Purpose: prove the prepared SearXNG overlay actually starts and works as a
native OpenWebUI provider.

Prerequisites:

- Owner approves runtime smoke.
- Linux-container Docker host with Compose is available.
- Server-local `SEARXNG_SECRET` is generated.
- Upstream engines and allowed query classes are approved.
- OpenWebUI provider switch window and rollback are approved.

Expected output:

- `docs/reports/YYYY-MM-DD/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`
- container health evidence;
- `/healthz` evidence;
- JSON API evidence;
- OpenWebUI `searxng` provider smoke evidence;
- source cards, logs, permissions and exposure findings.

Stop conditions:

- SearXNG would be exposed publicly.
- Missing or placeholder `SEARXNG_SECRET` in runtime.
- Docker host is not Linux-container capable.
- Compose rendered config would leak secrets or bind public debug port.
- Upstream engines are not owner-approved.
- Raw sensitive query text would be sent or logged.

### B. Extend Comparison Plan To Brave vs Yandex vs SearXNG

Purpose: align the comparison method with current provider reality: two direct
providers already work and SearXNG is the third comparison path.

Prerequisites:

- Current Brave baseline is accepted as Path A.
- Current Yandex smoke status is documented or accepted as Path C.
- Owner agrees whether comparison comes before SearXNG runtime smoke.

Expected output:

- updated comparison plan/report template for Brave / Yandex / SearXNG;
- shared query matrix;
- provider-specific capture format;
- explicit decision rules for keeping, deferring or rejecting SearXNG.

Stop conditions:

- Yandex baseline evidence is too vague to use as comparison input.
- Owner has not accepted data classes or metadata/cost mode for Yandex.
- The plan starts treating SearXNG as a drop-in substitute rather than candidate
  discovery comparison.

### C. Run Direct API Comparison: Brave vs Yandex

Purpose: compare the two already-working direct API providers before spending
ops time on SearXNG.

Prerequisites:

- Brave baseline remains working.
- Yandex baseline is recorded with safe queries.
- Owner approves shared safe query matrix and provider data policy.

Expected output:

- comparison report for Brave vs Yandex;
- RU/EN/freshness/source-card/latency/cost findings;
- decision whether SearXNG still has enough value to test.

Stop conditions:

- Direct provider credentials are not approved for test.
- Query matrix includes sensitive/customer/private data.
- Source attribution or logging cannot be safely captured.

### D. Defer SearXNG Until Direct Providers Baseline Is Complete

Purpose: avoid operational work if Brave and Yandex cover the needed product
scenarios.

Prerequisites:

- Owner accepts deferral.
- Brave/Yandex baseline and policy docs remain current.

Expected output:

- backlog item keeping SearXNG as deferred comparison track;
- no runtime changes.

Stop conditions:

- Owner requires self-hosted meta-search evidence now.
- Direct providers fail a policy, cost, RU quality or availability requirement.

Recommended bounded next task: B, with a short pre-step to create a dedicated
Yandex runtime baseline report if it is not already present. Then run C or A
depending on owner priority.

## 13. Final Recommendation

Do not switch directly to SearXNG runtime smoke as the next task unless the
owner explicitly wants to test the third track immediately.

The repo is technically ready for SearXNG runtime smoke, but the project
sequence should reflect the new provider reality:

1. Brave works.
2. Yandex works.
3. SearXNG is optional comparison infrastructure.

The most useful next step is to make the comparison method explicit for all
three paths and record Yandex baseline evidence cleanly. After that, SearXNG
runtime smoke becomes a bounded third-path check, not an urgent fix for broken
search.

## 14. Final Verdict

`searxng_ready_but_should_follow_direct_provider_comparison`

Meaning:

- SearXNG static repo/config layer is ready enough for runtime smoke.
- Runtime smoke is still pending and must not be claimed as passed.
- No production/runtime change was made in this audit.
- SearXNG must stay internal-only and comparison-only unless owner explicitly
  approves a broader role.
- Because Brave and Yandex already work, SearXNG should follow baseline/direct
  provider documentation and comparison planning rather than lead the next
  Web Search task by default.
