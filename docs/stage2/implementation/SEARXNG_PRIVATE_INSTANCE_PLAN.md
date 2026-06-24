# SearXNG Private Instance Plan

Status: runtime smoke passed in snippet/bypass mode on 2026-06-23; ready for
three-path comparison. If OpenWebUI Admin UI selects `searxng` as the active
Web Search engine, `searxng` and `searxng-valkey` are always-on internal
runtime dependencies.

## 1. Purpose

Prepare a private SearXNG instance as the self-hosted meta-search comparison
track for Stage 2 Web Search. Brave `brave_llm_context` remains the primary
paid API path; this plan covers the parallel candidate discovery gateway.

SearXNG is not a search provider with its own global web index and is not a
privacy guarantee. The SearXNG instance can be private to our Docker network,
but enabled upstream engines, public search pages, public APIs and
source-specific engines may still receive the minimized query.

Product value:

- single internal meta-search gateway;
- controlled list of upstream engines;
- normalized candidate set for OpenWebUI;
- comparison against Brave without direct paid search API calls;
- future candidate discovery layer for public web, docs/wiki, GitHub/npm/PyPI
  and internal catalogs if those are later configured.

## 2. Architecture

Topology:

- `openwebui` uses native OpenWebUI Web Search.
- `searxng` runs as an internal Docker service on the existing `openwebui_web`
  network.
- `searxng` aggregates and normalizes candidate results from configured
  upstream engines; it does not own the upstream index.
- `searxng-valkey` supports SearXNG limiter/bot-protection state.
- No public SearXNG port is exposed by default.
- Optional debug exposure is a separate local-only overlay.

Files:

- `compose/searxng.private.compose.yml`
- `compose/searxng.debug.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`

## 3. Compose Topology

Base run shape:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d searxng searxng-valkey
```

Full OpenWebUI + SearXNG run shape:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d
```

Always-on mode:

- `searxng` and `searxng-valkey` have `restart: unless-stopped`;
- keep both services running while OpenWebUI Admin UI uses
  `WEB_SEARCH_ENGINE=searxng`;
- do not use `docker compose stop searxng searxng-valkey` unless the WebGUI
  provider has first been changed away from `searxng`.

Optional local-only debug port:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml \
  -f compose/searxng.debug.compose.yml up -d searxng
```

The debug overlay binds to `127.0.0.1:${SEARXNG_DEBUG_PORT:-18080}` by default.
Do not use it for public exposure.

## 4. Config Files

`deploy/searxng/settings.yml`:

- uses SearXNG default settings with local overrides;
- enables `html` and `json` formats;
- sets `safe_search: 1`;
- sets default language to `ru`;
- binds the container on `0.0.0.0:8080`;
- keeps `public_instance: false`;
- keeps `image_proxy: false` for first smoke;
- uses `GET` because OpenWebUI SearXNG provider uses a query URL;
- enables limiter through server/env settings;
- removes the default `google` engine for the first pilot to reduce CAPTCHA and
  policy noise.

`deploy/searxng/limiter.toml`:

- keeps the limiter enabled;
- sets `link_token=false` for the private runtime path;
- passlists loopback and private Docker CIDR ranges for internal smoke;
- keeps `block_ip` empty.

The runtime smoke showed that the default limiter behavior could return `429`
for private internal JSON requests. The accepted stage fix is a private
Docker-network passlist, not public exposure and not a global limiter disable.

Server-local `.env` must provide a generated `SEARXNG_SECRET`. The committed
`.env.example` contains only a placeholder. Official SearXNG container docs
state that `server.secret_key` is overwritten by `SEARXNG_SECRET`.

## 5. OpenWebUI Integration Settings

Config names only; values belong in server-local `.env` or Admin UI:

- `ENABLE_WEB_SEARCH=true`
- `WEB_SEARCH_ENGINE=searxng`
- `SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>`
- `SEARXNG_LANGUAGE=ru`
- `WEB_SEARCH_RESULT_COUNT=3`
- `WEB_SEARCH_CONCURRENT_REQUESTS=1`
- `WEB_LOADER_CONCURRENT_REQUESTS=2`
- `WEB_SEARCH_TRUST_ENV=true` if the deployment uses proxy env for page fetch;
- `BYPASS_WEB_SEARCH_WEB_LOADER=false` for first source-card smoke unless
  latency/fetch failures require a snippet-only comparison.
- Runtime smoke passed with `BYPASS_WEB_SEARCH_WEB_LOADER=true` and
  `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true`; this proves the candidate
  set/snippet path, not full page loading.

OpenWebUI WebGUI value for **Settings -> Web Search -> Searxng request URL**:

```text
http://searxng:8080/search?q=<query>
```

Keep the `<query>` placeholder literal. OpenWebUI strips the legacy query string
and sends native SearXNG parameters such as `q`, `format=json`, `pageno`,
`safesearch` and `language`.

`OPENWEBUI_NO_PROXY` must include `searxng`, `searxng:8080` and
`searxng-valkey` so OpenWebUI does not try to reach the private SearXNG service
through an outbound proxy.

If the running OpenWebUI container predates the SearXNG overlay/env contract,
recreate it through the native compose overlay so `NO_PROXY` is actually present
inside the container. Without that, OpenWebUI may route `http://searxng:8080`
through the outbound proxy and fail.

## 6. Smoke Tests

SearXNG direct smoke:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml ps searxng searxng-valkey

docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml exec -T searxng \
  python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8080/search?q=OpenWebUI&format=json', timeout=20)); print(len(data.get('results', [])))"
```

Expected:

- container is healthy;
- JSON response parses;
- `results` is present;
- result count is non-zero for safe public queries.

2026-06-23 stage result:

- SearXNG `/healthz` returned `200`;
- direct JSON returned valid JSON with non-zero results;
- OpenWebUI-to-SearXNG internal JSON returned non-zero results after
  `NO_PROXY` was applied;
- six safe RU/EN OpenWebUI native searches returned `200` with source items in
  snippet/bypass mode.

OpenWebUI native smoke:

- Admin UI shows Web Search settings.
- Engine is `searxng`.
- Query URL is the internal URL.
- Result count is `3`.
- Concurrency is `1`.
- 3 RU safe queries work.
- 3 EN safe queries work.
- Source links/cards are visible.
- User without Web Search permission is blocked.
- No provider key exists for SearXNG in browser because SearXNG does not require
  an external API key for OpenWebUI.
- OpenWebUI/SearXNG logs do not retain raw sensitive query content by default.
- Private/local/metadata IP fetch boundary remains enabled.

Forbidden examples must only be used for policy/UX validation and must not be
sent to external upstream engines without a policy gate.

SSH troubleshooting when WebGUI shows `An error occurred while searching the web`:

```bash
ssh <stage-target>
cd <openwebui-deploy-dir>

docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml ps openwebui searxng searxng-valkey
```

Expected:

- `openwebui` is `Up` and `healthy`;
- `searxng` is `Up` and `healthy`;
- `searxng-valkey` is `Up`.

If `searxng` or `searxng-valkey` is stopped while WebGUI still uses
`searxng`, start them through the native overlay:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml up -d searxng searxng-valkey
```

Then verify internal connectivity from OpenWebUI:

```bash
docker exec -i openwebui python - <<'PY'
import json, urllib.request
url = "http://searxng:8080/search?q=OpenWebUI&format=json"
data = json.load(urllib.request.urlopen(url, timeout=20))
print(len(data.get("results", [])))
PY
```

The command should print a non-zero result count for a normal public query.

## 7. Security And Privacy Notes

- Do not use public SearXNG instances for corporate acceptance.
- Do not expose SearXNG publicly without separate owner/security decision.
- Treat upstream engines as external recipients of the minimized query.
- Treat public/free APIs and HTML parsing as external egress, not as local-only
  processing.
- Do not send full prompts, secrets, customer data, broker reports, tax data,
  payroll data or private URLs.
- Keep `ENABLE_RAG_LOCAL_WEB_FETCH` disabled unless a separate owner decision
  allows local/private URL fetch.
- Keep SearXNG and Valkey on the internal Docker network.
- Do not commit generated `SEARXNG_SECRET`.
- Do not log or retain raw query/result bodies without retention approval.

## 8. Ops Notes

- Direct API fee is absent, but infrastructure and maintenance cost remain.
- Result quality depends on upstream engines.
- Upstream engines may CAPTCHA/rate-limit the server IP.
- Limiter requires Valkey and correct client IP headers if SearXNG is exposed
  through a proxy.
- Start with low OpenWebUI result count/concurrency.
- Monitor SearXNG health, latency and empty-result rate.
- Pin the SearXNG image tag before production-like rollout; `latest` is
  acceptable only for initial local/stage discovery if explicitly accepted.
- Review upstream SearXNG templates before upgrades.

## 9. Rollback

Fast rollback to primary paid path:

1. Disable Web Search or change `WEB_SEARCH_ENGINE` back to the approved paid
   provider.
2. Remove `compose/searxng.private.compose.yml` from the runtime command.
3. Only after the WebGUI provider is no longer `searxng`, stop SearXNG
   services:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml stop searxng searxng-valkey
```

4. Preserve sanitized smoke report only.
5. Remove debug overlay from any operator command.

## 10. Known Limitations

- Private SearXNG gives a private instance boundary, not private upstream
  search.
- SearXNG has no owned global web index.
- SearXNG is not an LLM and does not write the final answer.
- Result quality and latency may be worse than Brave `brave_llm_context`.
- Some engines may break or throttle without warning.
- HTML/parser drift and public API rate limits can affect candidate quality.
- If SearXNG is configured to use only Brave API, it becomes Brave-through-proxy
  and loses most comparison value.
- JSON API success alone does not prove full OpenWebUI answer quality. Native
  OpenWebUI snippet/bypass smoke has passed, but full page loading and
  vectorized retrieval remain separate known issues.
- This plan does not create a sidecar, custom gateway, OpenAPI Tool Server or
  separate GUI.

## 11. Sources

- SearXNG container installation: https://docs.searxng.org/admin/installation-docker.html
- SearXNG `settings.yml`: https://docs.searxng.org/admin/settings/settings.html
- SearXNG Search API: https://docs.searxng.org/dev/search_api.html
- SearXNG limiter: https://docs.searxng.org/admin/searx.limiter.html
- SearXNG bot detection: https://docs.searxng.org/src/searx.botdetection.html
- OpenWebUI SearXNG provider: https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/
