# OpenWebUI SearXNG Runtime Smoke

Date: 2026-06-23

Scope: Stage 2 / PRD-1 / Web Search / private SearXNG native OpenWebUI
connection.

Verdict: `searxng_ready_for_three_path_comparison`

## 1. Executive Summary

Private SearXNG was proven as a native OpenWebUI web-search provider path on the
stage host:

```text
OpenWebUI -> native provider searxng -> private SearXNG -> upstream engines
```

The first runtime attempt exposed two real config issues:

- SearXNG direct JSON returned `429` because the default limiter did not
  passlist the private Docker-network caller.
- OpenWebUI could not reach `http://searxng:8080` until the OpenWebUI container
  was recreated through the prepared compose overlay, because its shared
  `aiohttp` session uses `trust_env=True` and the old running container did not
  have `NO_PROXY` entries for `searxng`.

The minimal native fix was applied without sidecar, fork, or public SearXNG
exposure:

- keep SearXNG limiter enabled;
- set `link_token=false`;
- passlist loopback and private Docker ranges in `deploy/searxng/limiter.toml`;
- apply the existing private compose overlay to OpenWebUI so `NO_PROXY` includes
  `searxng` and `searxng-valkey`.

Direct JSON then passed. OpenWebUI was temporarily switched through its native
admin config API from `yandex` to `searxng`, six safe RU/EN searches were run,
and every query returned `200` with three source items. The original web-search
config was restored to `yandex` after the smoke. `searxng` and
`searxng-valkey` were stopped after evidence collection; OpenWebUI remained
healthy.

Important boundary: this smoke proves the native SearXNG candidate-set path in
snippet/bypass mode. It does not prove long-page loading or vectorized retrieval;
that remains a separate known issue for future RAG-over-fetched-content work.

## 2. Runtime Environment

Local workstation preflight:

| Check | Result |
| --- | --- |
| local branch | `main...origin/main` |
| local Docker Compose | unavailable: `docker: 'compose' is not a docker command` |
| local Docker server OS | `windows` |

Because local Docker is Windows-container mode and Compose is unavailable, no
local runtime was attempted.

Stage host:

| Check | Result |
| --- | --- |
| Host | `ai-corp` |
| Docker Compose | available on Linux host |
| Repo path | `/opt/openwebui-prd0` |
| OpenWebUI image | `corp-openwebui/openwebui:v0.9.6-native-web-stt-v1` |
| SearXNG image | `docker.io/searxng/searxng:latest` |
| Valkey image | `docker.io/valkey/valkey:8-alpine` |

Stage checkout note:

- The server checkout was already fast-forwarded to the current SearXNG overlay
  commit before this successful rerun.
- The server working tree now has the same intended limiter change as the local
  checkout: `deploy/searxng/limiter.toml`.
- A pre-existing untracked diagnostic backup remains on stage:
  `deploy/openwebui-static/loader.js.stage2-diagnostic-backup-20260619T172946Z`.

Server-local env note:

- `.env` contains server-local SearXNG runtime values.
- `SEARXNG_SECRET` was generated and stored server-side before this rerun.
- No real secret values, provider keys, or admin credentials were printed.

## 3. Config Change

Changed file:

```text
deploy/searxng/limiter.toml
```

Effective diff:

```toml
[botdetection.ip_limit]
link_token = false

[botdetection.ip_lists]
block_ip = []
pass_ip = [
  "127.0.0.0/8",
  "::1",
  "172.16.0.0/12",
]
```

Reason:

- direct internal JSON smoke was blocked by SearXNG limiter/bot-detection;
- OpenWebUI requests originate from the private Docker network;
- disabling limiter globally would be too broad;
- passlisting loopback and RFC1918 Docker range is the smallest practical
  private-runtime adjustment for this stage topology.

Validation:

- local TOML parse: passed;
- stage TOML parse: passed;
- stage effective passlist: `127.0.0.0/8`, `::1`, `172.16.0.0/12`;
- `link_token`: `false`.

## 4. Compose / Network Findings

The existing native overlays were used:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml ...
```

Rendered/runtime findings:

| Check | Result |
| --- | --- |
| `openwebui` service | present |
| `searxng` service | present |
| `searxng-valkey` service | present |
| `searxng` public host port | none |
| `searxng-valkey` public host port | none |
| OpenWebUI internal SearXNG URL | `http://searxng:8080/search?q=<query>` |
| OpenWebUI `NO_PROXY` before recreate | did not contain `searxng` |
| OpenWebUI `NO_PROXY` after native overlay recreate | contains `searxng` |
| Debug overlay | not enabled |

`docker port searxng` and `docker port searxng-valkey` produced no output,
which confirms no Docker host port was published.

## 5. Services Started

SearXNG and Valkey were started through the optional private overlay:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml \
  up -d searxng searxng-valkey
```

OpenWebUI was later recreated through the same native overlay to apply
`NO_PROXY`:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml \
  up -d openwebui
```

Post-recreate health:

| Service | Status during smoke |
| --- | --- |
| `openwebui` | healthy |
| `searxng` | healthy |
| `searxng-valkey` | running |

The recreate caused a short OpenWebUI restart but did not change the persistent
provider config permanently. After the smoke, provider config was restored to
`yandex`.

## 6. Direct SearXNG JSON Smoke

Direct JSON from inside the `searxng` container:

```text
http://127.0.0.1:8080/search?q=OpenWebUI&format=json
```

Result after limiter fix:

| Check | Result |
| --- | --- |
| JSON valid | true |
| `results` key present | true |
| result count | `28` |
| elapsed | about `1285 ms` |
| sample domains | `github.com`, `openwebui.com`, `docs.openwebui.com`, `timeweb.cloud` |

Direct JSON from inside the `openwebui` container to private SearXNG:

```text
http://searxng:8080/search?q=OpenWebUI&format=json
```

Result after OpenWebUI overlay recreate:

| Check | Result |
| --- | --- |
| JSON valid | true |
| result count | `28` |

Before the OpenWebUI recreate, the same check returned `502` because the
request was routed through proxy settings. This is why `NO_PROXY` is part of
the runtime contract, not just a cosmetic env value.

## 7. OpenWebUI Native SearXNG Smoke

OpenWebUI native runtime code path verified from the packaged image:

- router prefix: `/api/v1/retrieval`;
- search endpoint: `/api/v1/retrieval/process/web/search`;
- SearXNG dispatcher: `search_web(... engine == "searxng")`;
- provider implementation: `open_webui/retrieval/web/searxng.py`;
- OpenWebUI strips legacy `<query>` query strings and sends `q`,
  `format=json`, `pageno`, `safesearch`, and `language` as native SearXNG
  parameters.

Temporary active web config during smoke:

| Setting | Value |
| --- | --- |
| `ENABLE_WEB_SEARCH` | `true` |
| `WEB_SEARCH_ENGINE` | `searxng` |
| `WEB_SEARCH_RESULT_COUNT` | `3` |
| `WEB_SEARCH_CONCURRENT_REQUESTS` | `1` |
| `WEB_LOADER_CONCURRENT_REQUESTS` | `2` |
| `BYPASS_WEB_SEARCH_WEB_LOADER` | `true` |
| `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL` | `true` |
| `SEARXNG_QUERY_URL` | internal Docker URL |
| `SEARXNG_LANGUAGE` | `all` |

The bypass settings were intentional for this smoke: they prove candidate-set
search and source-item return without re-opening the known vectorized retrieval
and page-loading issue.

Original config before smoke:

| Setting | Value |
| --- | --- |
| `WEB_SEARCH_ENGINE` | `yandex` |
| `WEB_SEARCH_RESULT_COUNT` | `3` |
| `WEB_SEARCH_CONCURRENT_REQUESTS` | `1` |
| `BYPASS_WEB_SEARCH_WEB_LOADER` | `true` |
| `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL` | `true` |

Rollback confirmation after smoke:

| Setting | Restored value |
| --- | --- |
| `WEB_SEARCH_ENGINE` | `yandex` |
| `WEB_SEARCH_RESULT_COUNT` | `3` |
| `WEB_SEARCH_CONCURRENT_REQUESTS` | `1` |
| `BYPASS_WEB_SEARCH_WEB_LOADER` | `true` |
| `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL` | `true` |
| internal SearXNG URL active | `false` |

## 8. RU/EN Query Results

All searches were sent through the native OpenWebUI endpoint with provider path:

```text
OpenWebUI -> private SearXNG
```

| Label | HTTP | Items | Loaded | Latency | Source domains |
| --- | ---: | ---: | ---: | ---: | --- |
| `ru_tax` | `200` | `3` | `3` | `1081 ms` | `ru.wikipedia.org`, `kotlasreg.gosuslugi.ru`, `www.galacentre.ru` |
| `ru_ndfl` | `200` | `3` | `3` | `756 ms` | `burdastyle.ru`, `www.klerk.ru`, `www.calend.ru` |
| `ru_openwebui` | `200` | `3` | `3` | `583 ms` | `docs.openwebui.com`, `www.reddit.com` |
| `en_openwebui` | `200` | `3` | `3` | `2347 ms` | `docs.openwebui.com`, `www.reddit.com` |
| `en_searxng_json` | `200` | `3` | `3` | `838 ms` | `docs.searxng.org`, `github.com` |
| `en_brave_openwebui` | `200` | `3` | `3` | `748 ms` | `docs.openwebui.com`, `brave.com` |

Source cards / candidate items:

- `items_count > 0` for every query;
- `loaded_count == 3` for every query;
- snippets were converted into docs because web loader bypass was enabled;
- final LLM answer groundedness was not evaluated in this endpoint-level smoke.

Quality note:

- RU tax/accounting queries returned mixed-quality candidate sets.
- This is acceptable for comparison-track readiness, but not sufficient to
  promote SearXNG as a primary RU provider.

## 9. Public Exposure Findings

Proven:

- private overlay was used;
- debug overlay was not enabled;
- `searxng` had no published host port;
- `searxng-valkey` had no published host port;
- `docker port searxng` returned no bindings;
- `docker port searxng-valkey` returned no bindings.

Not proven:

- external firewall scan from outside the host.

Current evidence is enough to say this smoke did not publish SearXNG or Valkey
through Docker ports.

## 10. Logs / Privacy Findings

High-confidence token scan over recent OpenWebUI/SearXNG/Valkey logs:

```json
{"bearer_token": 0, "long_assignment_after_sensitive_name": 0, "openai_style_sk_token": 0}
```

No real provider API keys, `SEARXNG_SECRET`, admin credentials, or bearer tokens
were printed in the report.

Observed log/runtime caveats:

- SearXNG logs can include safe query material or upstream request URLs during
  engine failures. Do not send sensitive/customer/private queries through this
  path unless log retention and redaction policy are explicitly accepted.
- Valkey prints `vm.overcommit_memory` host tuning warnings.
- SearXNG `ahmia` and `torch` engines fail to load and become inactive.
- DuckDuckGo produced CAPTCHA errors during the smoke.
- Brave upstream through SearXNG produced rate-limit / too-many-request noise.
- OpenWebUI startup still logs read-only filesystem errors for
  `/app/backend/open_webui/static/loader.js`; the service nevertheless becomes
  healthy. This looks like a separate static-loader/runtime-hardening issue,
  not a SearXNG blocker.

## 11. Failure Modes / Open Issues

| Issue | Status | Impact | Recommended action |
| --- | --- | --- | --- |
| SearXNG limiter blocked private direct JSON with `429` | fixed for stage smoke | Was a hard blocker | Keep private passlist in `limiter.toml`; do not expose publicly. |
| OpenWebUI old container lacked `NO_PROXY` for `searxng` | fixed by native overlay recreate | Caused `502` via proxy path | Treat `NO_PROXY` as required runtime contract. |
| DuckDuckGo CAPTCHA inside SearXNG | observed | Upstream instability; aggregate still returned results | Tune first-smoke engines before pilot. |
| Brave rate-limit noise through SearXNG | observed | Upstream instability; aggregate still returned results | Do not treat SearXNG as primary without engine tuning. |
| Valkey `vm.overcommit_memory` warning | observed | Non-blocking for smoke; production risk | Decide whether to tune host sysctl before longer run. |
| Full web loader / vectorized retrieval | not tested | Still a known issue | Keep separate task for long pages, page loading, classic Brave, SearXNG page loading, or full RAG over fetched content. |
| Mobile microphone transcription | unrelated | Not reopened | Keep in separate known issue. |

## 12. Rollback Status

Executed after evidence collection:

```bash
docker compose --env-file .env \
  -f compose/openwebui.compose.yml \
  -f compose/searxng.private.compose.yml \
  stop searxng searxng-valkey
```

Final runtime state:

| Component | Final state |
| --- | --- |
| OpenWebUI | running and healthy |
| OpenWebUI provider config | restored to `yandex` |
| `searxng` | stopped |
| `searxng-valkey` | stopped |
| SearXNG public exposure | none |

Left in place:

- server-local `.env` SearXNG section;
- generated server-local `SEARXNG_SECRET`;
- SearXNG/Valkey images and volumes;
- limiter config change in repo checkout.

These do not switch the active provider away from Yandex and do not expose
SearXNG publicly.

## 13. Comparison Readiness

SearXNG is now ready to be included in a bounded three-path comparison:

```text
Brave direct API / brave_llm_context
Yandex direct API
Private SearXNG candidate-set path
```

Use this readiness narrowly:

- ready for candidate-set comparison;
- ready for source-domain/source-card comparison in snippet mode;
- ready for latency and upstream-stability comparison;
- not ready as primary provider;
- not proven for full page loading;
- not proven for vectorized retrieval over fetched pages.

## 14. Recommendation

Keep SearXNG as a comparison track, not as default provider.

Recommended next bounded task:

```text
Run Brave vs Yandex vs Private SearXNG candidate-set comparison.
```

Scope:

- use safe RU/EN query sets;
- keep SearXNG private and optional;
- keep OpenWebUI default provider on the current working direct API path;
- record source domains, source cards, latency, query quality, and upstream
  error noise;
- decide whether SearXNG adds enough value to justify engine tuning and ops
  burden.

Follow-up only if comparison justifies it:

```text
Tune SearXNG engines and revisit full page loading / vectorized retrieval.
```
