# OpenWebUI SearXNG Private Instance Report

Date: 2026-06-20

Verdict: `searxng_private_instance_ready_for_candidate_set_runtime_smoke`

## 1. Executive Summary

Prepared a private SearXNG self-hosted meta-search comparison track for Stage 2
Web Search without changing production runtime and without touching Brave smoke,
STT, sidecars, custom gateways or OpenWebUI fork code.

Brave `brave_llm_context` remains the primary paid API path. Private SearXNG is
now a runnable candidate discovery gateway for local/stage comparison after
owner approves compose runtime access.

## 2. What Was Created Or Changed

Created:

- `compose/searxng.private.compose.yml`
- `compose/searxng.debug.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
- `docs/reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md`

Updated:

- `.env.example`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

## 3. Compose / Config Findings

Existing repo pattern:

- main compose file is `compose/openwebui.compose.yml`;
- OpenWebUI and Stage 2 STT use the `openwebui_web` Docker network;
- compose intentionally passes env variables explicitly;
- real `.env` is server-local and not committed.

SearXNG design:

- optional overlay compose file, not automatically active;
- SearXNG and Valkey share the same internal Docker network as OpenWebUI;
- no public port by default;
- optional local-only debug port requires explicit debug overlay;
- OpenWebUI uses `http://searxng:8080/search?q=<query>`;
- `OPENWEBUI_NO_PROXY` includes SearXNG service names.
- SearXNG aggregates configured upstream engines and returns a normalized
  candidate set; it does not own a global web index.

## 4. SearXNG Config Decisions

- JSON API enabled through `search.formats: [html, json]`.
- Safe search default set to `1`.
- Default language set to `ru`.
- `public_instance` disabled.
- `image_proxy` disabled for first smoke.
- `server.method` set to `GET` for OpenWebUI query URL compatibility.
- Limiter enabled with Valkey.
- `google` engine removed from defaults for first smoke to reduce CAPTCHA and
  policy noise.
- Real `SEARXNG_SECRET` remains server-local only.
- Official SearXNG container docs state that `server.secret_key` is overwritten
  by `SEARXNG_SECRET`; the committed config contains only a placeholder.

## 5. OpenWebUI Integration Path

Native OpenWebUI Web Search config through the optional overlay:

- `ENABLE_WEB_SEARCH=true`
- `WEB_SEARCH_ENGINE=searxng`
- `WEB_SEARCH_RESULT_COUNT=3`
- `WEB_SEARCH_CONCURRENT_REQUESTS=1`
- `WEB_LOADER_CONCURRENT_REQUESTS=2`
- `WEB_SEARCH_TRUST_ENV=true`
- `SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>`
- `SEARXNG_LANGUAGE=ru`

No SearXNG external provider API key is required in OpenWebUI.

## 6. Smoke Results Or Blocked Checks

Completed in repo:

- compose/config files created;
- no production runtime changed;
- official SearXNG/OpenWebUI docs checked;
- YAML syntax validated for:
  - `compose/searxng.private.compose.yml`;
  - `compose/searxng.debug.compose.yml`;
  - `deploy/searxng/settings.yml`;
- smoke commands documented.

Blocked/not run in this turn:

- Docker Compose rendered-config validation;
- local/stage SearXNG container smoke;
- JSON API runtime request;
- OpenWebUI Admin UI native Web Search smoke;
- source-card visibility;
- group permission behavior;
- log-retention check.

Reason:

- no instruction to change production runtime;
- no deployed/staging access was provided;
- local Docker has no Compose plugin or `docker-compose` binary;
- local Docker daemon is in Windows container mode:
  `Client=19.03.5 Server=19.03.5 OS=windows`;
- SearXNG and Valkey runtime images are Linux containers;
- local runtime smoke should be run as the next bounded task using the new
  optional compose overlay on a Linux-container Docker host or stage server.

## 7. Privacy / Security Findings

- Private SearXNG is private only as an instance boundary.
- Upstream engines can still receive minimized queries.
- Public SearXNG instances are not acceptable for corporate acceptance.
- SearXNG must not be public without separate owner/security decision.
- Raw sensitive queries must not be sent to upstream engines.
- `ENABLE_RAG_LOCAL_WEB_FETCH` must remain disabled unless separately approved.
- SearXNG does not require a provider API key in browser.
- Generated `SEARXNG_SECRET` must stay in server-local `.env`.

## 8. Ops Risks

- No direct API fee, but there is infrastructure and maintenance cost.
- Upstream engines can rate-limit/CAPTCHA the SearXNG server IP.
- Result quality may degrade or vary by engine.
- SearXNG/Valkey need monitoring and upgrade discipline.
- `latest` image tag should be pinned before production-like rollout.
- Debug overlay must remain local-only.

## 9. Recommendation

Private SearXNG is suitable as a self-hosted meta-search comparison track, but
not as a stronger first provider than Brave while Brave account/API key already
exists.

Recommended order:

1. Run Brave `brave_llm_context` primary smoke.
2. Run private SearXNG as parallel comparison if owner wants candidate discovery
   evidence without a direct paid API path.
3. Compare RU/EN result quality, latency, source visibility, logs and ops cost.
4. Keep Yandex for later privacy/data-egress review.

## 10. Owner Answer

1. Does private SearXNG fit as self-host alternative?
   Yes, as a private instance and comparison provider.

2. Is it enough for first pilot if Brave is already available?
   Not by default. Brave remains simpler and more stable for first paid smoke;
   SearXNG is useful if self-hosted meta-search and candidate discovery
   comparison are priorities.

3. Should Brave smoke run first?
   Yes. Keep SearXNG as parallel comparison unless owner explicitly changes
   primary provider.

4. What owner actions are needed?
   - approve running the optional compose overlay;
   - provide runtime access;
   - choose internal-only vs debug local-only exposure;
   - approve allowed upstream engines;
   - approve retention/logging policy;
   - approve whether SearXNG image tag can remain `latest` for discovery or must
     be pinned before stage.

## 11. Next Bounded Task

Run local/stage SearXNG runtime smoke:

1. Generate server-local `SEARXNG_SECRET`.
2. Use a Linux-container Docker host with Docker Compose v2 or compatible
   `docker-compose`.
3. Start `searxng` and `searxng-valkey` with the optional compose overlay.
4. Verify `/healthz`.
5. Verify `/search?q=OpenWebUI&format=json` returns valid JSON.
6. Start OpenWebUI with the overlay.
7. Run 3 RU and 3 EN safe Web Search queries.
8. Verify source links/cards, result count, concurrency, logs and permission
   behavior.
9. Produce sanitized runtime smoke report.

## 12. Sources

- https://docs.searxng.org/admin/installation-docker.html
- https://docs.searxng.org/admin/settings/settings.html
- https://docs.searxng.org/dev/search_api.html
- https://docs.searxng.org/admin/searx.limiter.html
- https://docs.searxng.org/src/searx.botdetection.html
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/

## 13. Detailed File Inventory

| File | Type | Purpose | Runtime effect |
| --- | --- | --- | --- |
| `compose/searxng.private.compose.yml` | optional compose overlay | Adds `searxng`, `searxng-valkey` and OpenWebUI Web Search env for native `searxng` provider. | No effect unless explicitly included with `-f compose/searxng.private.compose.yml`. |
| `compose/searxng.debug.compose.yml` | optional debug overlay | Binds SearXNG to localhost for operator troubleshooting. | No effect unless explicitly included; default bind is `127.0.0.1`. |
| `deploy/searxng/settings.yml` | SearXNG config | Enables JSON API, conservative safe search, internal instance defaults and Valkey limiter. | Mounted read-only into SearXNG container. |
| `deploy/searxng/limiter.toml` | SearXNG limiter config | Keeps bot-detection config explicit and conservative. | Mounted read-only into SearXNG container. |
| `.env.example` | env contract | Documents non-secret variable names and placeholders for optional SearXNG overlay. | Operator copies values to server-local `.env`; real secrets are not committed. |
| `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md` | implementation plan | Full setup/smoke/rollback handoff for the meta-search comparison track. | Documentation only. |
| `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` | implementation plan | Defines Brave vs SearXNG candidate-set comparison and scoring. | Documentation only. |
| `docs/reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md` | report | This evidence and decision report. | Documentation only. |

## 14. Detailed Compose Topology

| Service | Image | Network | Public exposure | Persistent state | Notes |
| --- | --- | --- | --- | --- | --- |
| `openwebui` | existing repo image | `openwebui_web` | existing Traefik route only | `openwebui_data` | Receives Web Search env only when SearXNG overlay is included. |
| `searxng` | `${SEARXNG_IMAGE:-docker.io/searxng/searxng:latest}` | `openwebui_web` | none by default | `searxng_cache` | Internal endpoint: `http://searxng:8080/search?q=<query>`. |
| `searxng-valkey` | `${SEARXNG_VALKEY_IMAGE:-docker.io/valkey/valkey:8-alpine}` | `openwebui_web` | none | `searxng_valkey` | Supports limiter/bot detection; not exposed to browser or public network. |

Debug exposure is deliberately separated:

- file: `compose/searxng.debug.compose.yml`;
- default bind: `127.0.0.1:${SEARXNG_DEBUG_PORT:-18080}`;
- purpose: operator/admin troubleshooting only;
- not acceptable as public corporate endpoint without separate decision.

## 15. Env Contract

Required for private SearXNG overlay:

- `SEARXNG_SECRET`: generated server-local secret; never committed.
- `ENABLE_WEB_SEARCH`: enables native OpenWebUI Web Search.
- `WEB_SEARCH_ENGINE`: `searxng` for this overlay.
- `SEARXNG_QUERY_URL`: internal Docker URL.
- `OPENWEBUI_NO_PROXY`: must include SearXNG service names.

Recommended first-smoke defaults:

- `WEB_SEARCH_RESULT_COUNT=3`
- `WEB_SEARCH_CONCURRENT_REQUESTS=1`
- `WEB_LOADER_CONCURRENT_REQUESTS=2`
- `WEB_SEARCH_TRUST_ENV=true`
- `BYPASS_WEB_SEARCH_WEB_LOADER=false`
- `SEARXNG_LANGUAGE=ru`

Explicit placeholders only:

- `.env.example` contains `replace-with-random-strong-searxng-secret`.
- `deploy/searxng/settings.yml` contains
  `replace-with-server-local-searxng-secret`.
- Real values belong only in server-local `.env` or approved secret storage.

## 16. Validation Evidence

Completed commands:

```text
git status -sb
python -c "import yaml; ..."
git diff --check
rg -n -i "(sk-...|api key...|secret...|token...)" ...
docker compose version
docker-compose --version
docker version --format "Client={{.Client.Version}} Server={{.Server.Version}} OS={{.Server.Os}}"
```

Observed:

- YAML parse succeeded for:
  - `compose/searxng.private.compose.yml`;
  - `compose/searxng.debug.compose.yml`;
  - `deploy/searxng/settings.yml`.
- `git diff --check` passed; only Windows CRLF warnings were printed.
- Secret scan found only placeholders, env variable references and the literal
  limiter field `link_token`; no real secrets were found.
- Docker Compose is not available in this local environment:
  - `docker compose version` returned that `compose` is not a Docker command;
  - `docker-compose` is not installed.
- Docker daemon is Windows-container mode:
  `Client=19.03.5 Server=19.03.5 OS=windows`.

Conclusion:

- Static config is ready for runtime smoke.
- Rendered Compose validation and container smoke require stage/server or a
  Linux-container Docker host with Compose.

## 17. Blocked Checks Matrix

| Check | Status | Reason | Next action |
| --- | --- | --- | --- |
| Compose rendered config | Blocked | No Compose plugin / no `docker-compose`. | Run on stage/server with Compose. |
| SearXNG container health | Blocked | Local Docker is Windows-container mode. | Run Linux containers on stage/server. |
| `/search?...format=json` | Blocked | SearXNG container not running locally. | Execute direct JSON smoke after container start. |
| OpenWebUI native provider smoke | Blocked | No live OpenWebUI Admin UI/runtime access in this task. | Run after overlay start and admin access. |
| Source links/cards | Blocked | Requires OpenWebUI browser/runtime smoke. | Capture sanitized UI/runtime evidence. |
| Permissions/groups | Blocked | Requires configured OpenWebUI users/groups. | Test allowed and blocked users. |
| Logging retention | Blocked | Requires runtime logs. | Inspect sanitized logs, without printing sensitive query content. |
| Public exposure check | Partially prepared | Compose has no public port by default. | Confirm host firewall/proxy on stage. |

## 18. Runtime Smoke Command Set

Generate server-local secret:

```bash
printf 'SEARXNG_SECRET=%s\n' "$(openssl rand -hex 32)" >> .env
```

Validate rendered config:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml config
```

Start only SearXNG dependencies:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d searxng searxng-valkey
```

Check service health:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml ps searxng searxng-valkey
```

Check JSON API:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml exec -T searxng \
  python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8080/search?q=OpenWebUI&format=json', timeout=20)); print(len(data.get('results', [])))"
```

Start OpenWebUI with overlay:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d
```

Rollback:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml stop searxng searxng-valkey
```

## 19. Runtime Smoke Acceptance Checklist

Direct SearXNG:

- `searxng` is healthy.
- `searxng-valkey` is running.
- `/healthz` returns success.
- `/search?q=OpenWebUI&format=json` returns valid JSON.
- JSON response contains `results`.
- SearXNG is not publicly reachable unless debug/local-only overlay is used.

OpenWebUI:

- Admin UI Web Search settings are visible.
- Engine is `searxng`.
- Query URL is the internal Docker URL.
- Result count is `3`.
- Search concurrency is `1`.
- 3 RU safe queries work.
- 3 EN safe queries work.
- Source links/cards are visible.
- User without Web Search permission is blocked.
- Provider/key leakage is absent.
- No raw sensitive query is retained by default.
- Failure mode for unavailable SearXNG is visible to admin/user.

Security:

- `ENABLE_RAG_LOCAL_WEB_FETCH` remains disabled unless separately approved.
- Private/local/metadata IP fetch boundary remains enabled.
- Public SearXNG instances are not used.
- Upstream query leakage is accepted and documented by owner.

## 20. Risk Register

| Risk | Severity | Current control | Remaining action |
| --- | --- | --- | --- |
| Upstream engines see queries | High | Explicit docs/privacy warning. | Owner approves allowed data classes and upstream engines. |
| Public exposure by mistake | High | No port in private overlay; debug overlay binds localhost. | Confirm host firewall/proxy on stage. |
| CAPTCHA / upstream rate limits | Medium | Low result count/concurrency; limiter enabled. | Runtime quality/empty-result monitoring. |
| Candidate quality weaker than Brave | Medium | Treat SearXNG as comparison track. | Compare RU/EN candidate sets against Brave. |
| SearXNG `latest` drift | Medium | Report flags pin-before-production. | Owner chooses pinned tag before production-like rollout. |
| Compose/runtime unavailable locally | Medium | Static YAML validated; blocker recorded. | Run smoke on Linux Docker host. |
| Raw query logs | High | Contract forbids default raw sensitive retention. | Inspect runtime logs after smoke. |

## 21. Owner Decision Register

Owner must decide before stage smoke:

- allow optional compose overlay on stage/server;
- choose generated `SEARXNG_SECRET` storage path;
- approve SearXNG image tag policy: `latest` for discovery or pinned immediately;
- approve internal-only SearXNG exposure, or explicitly approve debug/local-only
  binding for operator troubleshooting;
- approve upstream engines for pilot;
- approve retention/logging policy;
- decide whether SearXNG comparison runs before or after Brave smoke.

Recommended owner decision:

- run Brave smoke first because the account/key already exists;
- run SearXNG as parallel comparison if self-hosted meta-search candidate
  discovery evidence is valuable;
- do not promote SearXNG to primary provider until runtime quality, latency,
  logs and source display are proven.

## 22. Final Owner-Facing Verdict

Private SearXNG is suitable as a self-hosted meta-search candidate discovery
path for Stage 2 Web Search, but it is not a privacy guarantee, not a global
web index and not the lowest-risk first provider while Brave `brave_llm_context`
is already available.

The current repo state is ready for runtime smoke on a Linux-container Docker
host with Docker Compose. The remaining blocker is environment/access, not a
missing repo artifact.

## 23. Candidate Set Refinement

This report uses the refined product model:

- Search provider returns a candidate set.
- OpenWebUI loader/extraction prepares evidence where enabled.
- LLM writes the final answer.

For SearXNG, the candidate set is produced by enabled upstream engines, public
search pages, public APIs or source-specific engines. SearXNG normalizes that
candidate set for OpenWebUI. It does not own the underlying web index and does
not generate the final answer.

The comparison target is therefore not "which search engine is better in
general". The target is whether SearXNG candidate sets are good enough for
OpenWebUI/LLM grounded answers compared with Brave `brave_llm_context`.
