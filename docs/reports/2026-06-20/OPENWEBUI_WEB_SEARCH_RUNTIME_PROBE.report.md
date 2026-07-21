# OpenWebUI Web Search Runtime Probe

Date: 2026-06-20

Verdict: `web_search_runtime_live_probe_blocked_by_missing_runtime_access_and_provider_credentials`

## 1. Scope

Read-only/no-secrets probe for the current Web Search pilot readiness.

This probe did not read `.env`, provider keys, admin credentials, private URLs
or customer data. No production code was changed.

## 2. Operational Source

- Repo: `Kwentin3/corp-openweb-ui`
- cwd: `<repository-root>`
- branch: `main`
- `HEAD == origin/main == be49bbdbcab56a50e7d88a80e22a78073740b8ca`
- `git ls-remote --heads origin` shows only `main` at the same SHA.

## 3. Commands Run

Read-only commands:

- `git status --short --branch`
- `git rev-parse HEAD`
- `git rev-parse origin/main`
- `git ls-remote --heads origin`
- `rg -n "ghcr\.io/open-webui/open-webui|WEB_SEARCH|ENABLE_WEB_SEARCH|BRAVE|YANDEX|SEARXNG|..."`
- `docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"`
- `git ls-tree -r --name-only HEAD docs | rg "^(docs/README\.md|docs/_index/(canon|domains)\.md|docs/services/architecture/)"`

## 4. Local Repo / Config Findings

Passed:

- Local `HEAD` and `origin/main` are both
  `be49bbdbcab56a50e7d88a80e22a78073740b8ca`.
- Active origin is `https://github.com/Kwentin3/corp-openweb-ui.git`.
- OpenWebUI image/tag is pinned in local repo docs/config:
  - `compose/openwebui.compose.yml`: `ghcr.io/open-webui/open-webui:v0.9.6`
  - `.env.example`: `ghcr.io/open-webui/open-webui:v0.9.6`
- Existing PRD/docs mention Web Search as PRD-1 / Stage 2, not PRD-0.
- Existing docs already call out `WEB_SEARCH_TRUST_ENV=True` as a proxy-bridge
  item to verify.

Not found in local `origin/main` after fetch-equivalent verification:

- `docs/README.md`
- `docs/_index/canon.md`
- `docs/_index/domains.md`
- `docs/services/architecture/*`

Classification for those files:

`missing from local main / origin/main at be49bbdbcab56a50e7d88a80e22a78073740b8ca after fetch`

## 5. Live Runtime Findings

Blocked/not run:

- No deployed/staging Admin UI URL or credentials were provided.
- No approved provider key path was provided.
- No owner approval for live provider smoke was present.
- `docker ps` returned only the header row; no running local OpenWebUI container
  was available for runtime inspection from this workspace.

Therefore these checks remain unproven:

- exact live OpenWebUI build/commit beyond repo-pinned image tag;
- live Admin UI Web Search settings;
- live provider-engine dropdown contents;
- live `brave`, `brave_llm_context`, `searxng`, `yandex`, `external`
  availability;
- live result count and concurrency controls;
- live web loader controls;
- live domain/fetch filters;
- live `WEB_SEARCH_TRUST_ENV` behavior;
- live group permission behavior;
- live browser secret exposure check;
- live logs sanitization check;
- live source links/cards;
- live analytics/cost visibility.

## 6. Provider Smoke Readiness

Not run:

- Brave smoke was not run because no approved key/owner approval was present.
- SearXNG smoke was not run because no private SearXNG endpoint was present.
- Yandex smoke was not run because metadata-forwarding/privacy review is not
  approved and no key was present.

No-key readiness:

- Native-first plan is documented.
- Provider ADR is proposed for owner review.
- Safe smoke matrix is documented in the pilot plan and test-data requirements.

## 7. Secret Exposure Probe

Live secret exposure checks were not run because there was no runtime/browser
session. The probe did not print or inspect any provider key values.

Required future checks:

- provider keys absent from browser network responses;
- provider keys absent from frontend config;
- provider keys absent from localStorage/sessionStorage;
- provider keys masked or hidden in Admin UI;
- key values absent from logs;
- provider errors sanitized.

## 8. Proxy / Trust Env

Repo docs and PRD-1 identify `WEB_SEARCH_TRUST_ENV=True` as relevant for the
current proxy bridge. Live verification is blocked until runtime access exists.

Future smoke must separately prove:

- provider request succeeds through the deployment egress path;
- page loader/fetch succeeds through the deployment egress path;
- failure mode is visible if proxy/trust-env is wrong.

## 9. SSRF / URL Fetch Boundary

Not run against live runtime.

Future test plan should use safe local fixtures and verify:

- private IP URL blocked;
- localhost blocked;
- metadata IP blocked;
- `file://` rejected;
- `ftp://` rejected;
- parser-confusing URL rejected;
- redirect to private IP blocked.

Do not send dangerous probes to real private/customer targets.

## 10. Runtime Verdict

The repo/config side supports a native-first pilot plan, but live runtime proof
is incomplete.

Blocking items for live smoke:

- deployed/staging Admin UI access;
- approved provider key path;
- owner approval for provider/budget/data classes/group scope;
- provider-specific privacy review if Yandex is selected.

This is not evidence for a sidecar/fork. It is evidence that the next slice must
be a controlled native runtime smoke after owner/provider approval.
