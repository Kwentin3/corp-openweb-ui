# STT v2 OpenWebUI Prompt API Adapter Research

Status: research / proof design.

Date: 2026-07-02.

Target runtime:

```text
Host: root@178.72.138.169:/opt/openwebui-prd0
Branch/base commit: main @ e89b97e
OpenWebUI container: openwebui
OpenWebUI image: corp-openwebui/openwebui:v0.9.6-native-web-stt-v1
OpenWebUI ENV: prod
Stage2 sidecar container: stage2-stt
```

Scope:

- read current STT v2 contracts/code/reports;
- inspect official OpenWebUI documentation;
- inspect installed OpenWebUI source/routes on target runtime;
- run read-only or non-authenticated runtime probes;
- design the proof path for a future API-backed adapter.

Out of scope:

- no production replacement implementation;
- no OpenWebUI core patch;
- no behavior change to the current SQLite prompt catalog adapter;
- no prompt body, token, API key, cookie or secret disclosure.

## 1. Executive Summary

Verdict: **GO with guardrails, not a production replacement yet**.

OpenWebUI exposes enough prompt data in the installed runtime source to build an
API-backed `PromptCatalogAdapter`: prompt id, command, name, content, tags,
meta, access grants, `is_active`, `version_id`, timestamps and history endpoints.
That is enough to preserve the Gate 3-5 metadata/version/hash model if the
adapter keeps prompt content server-side and exposes only `PostProcessingTemplateV1`
metadata.

The blocking gap is not data shape. The blocking gap is **credential and access
parity**:

- OpenWebUI prompt API requires authentication.
- A user-scoped token preserves OpenWebUI visibility, but the current STT v2
  Action/sidecar path has not proven a safe way to forward the current user's
  JWT/session to the sidecar.
- An admin/service token can read the full prompt catalog, but it becomes a
  silent admin bypass unless the adapter re-applies user/group/resource access
  checks locally and the token is endpoint-restricted.
- The target runtime did not expose JSON OpenAPI schema in production mode, so
  the adapter contract must be anchored in source-level route tests, not only in
  `/openapi.json`.

Recommendation:

1. Keep `openwebui_sqlite` as the accepted MVP/default adapter.
2. Add a future `openwebui_api` adapter only behind explicit config.
3. Require a dedicated prompt catalog adapter contract document before coding:
   `docs/stage2/contracts/STT_V2_PROMPT_CATALOG_ADAPTER_CONTRACT.md`.
4. Treat the API adapter as **not safe for Gate 5 replacement** until runtime
   proof shows access-denied, missing, deleted, changed and old-result behavior
   match the SQLite adapter.

## 2. Evidence Sources

Official OpenWebUI docs:

- API endpoints and auth:
  <https://docs.openwebui.com/reference/api-endpoints/>
- Prompts feature: commands, tags, access control, version history:
  <https://docs.openwebui.com/features/workspace/prompts/>
- API keys:
  <https://docs.openwebui.com/features/authentication-access/api-keys/>
- Groups and access grants:
  <https://docs.openwebui.com/features/authentication-access/rbac/groups/>

Local STT v2 source:

- `services/stage2-stt/stage2_stt/prompt_catalog.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/post_processing.py`
- `services/stage2-stt/tests/test_prompt_catalog.py`
- `services/stage2-stt/tests/test_post_processing.py`
- `services/stage2-stt/tests/test_post_processing_routes.py`

Existing STT v2 proof reports:

- `docs/reports/2026-07-02/STT_V2_GATE_3_PROMPT_CATALOG_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_5_PROMPT_ACCESS_VERSION_PROOF.report.md`

Installed OpenWebUI target source:

- `/app/backend/open_webui/main.py`
- `/app/backend/open_webui/routers/prompts.py`
- `/app/backend/open_webui/models/prompts.py`
- `/app/backend/open_webui/models/prompt_history.py`
- `/app/backend/open_webui/models/access_grants.py`
- `/app/backend/open_webui/utils/auth.py`

Runtime probes were sanitized. Prompt bodies and secrets were not printed.

## 3. Current SQLite Adapter Behavior

Current route:

```text
PromptCatalogFactory.create()
  -> OpenWebUISqlitePromptCatalogAdapter
  -> read-only file:/openwebui-data/webui.db?mode=ro
```

Current adapter is an accepted MVP adapter, not a bad design. It is isolated
behind `PromptCatalogAdapter`, reads OpenWebUI as source of truth, and keeps the
rest of STT v2 update-safe.

Current adapter behavior:

- reads active prompts from OpenWebUI `prompt` table;
- filters to `stage2-stt-v2` and `stt-post-processing` tags;
- requires `meta.template_kind == "post_processing"`;
- resolves stable STT template id from `meta.template_id` or
  `meta.stage2_template_id`;
- resolves by `template_id`;
- resolves by OpenWebUI `command`;
- computes `prompt_body_hash = sha256(content)`;
- preserves `version_id` as `prompt_version`;
- checks owner/admin/user/group access from `access_grant`;
- returns prompt body only in internal `ResolvedPromptTemplate`;
- returns browser/Action-safe metadata through `PostProcessingTemplateV1`.

Current public metadata contract:

```text
PostProcessingTemplateV1:
  template_id
  command
  label
  openwebui_prompt_id
  prompt_version
  prompt_body_hash
  tags
  requires_speakers
  chunkable
  access_grants
```

Current execution contract:

```text
PostProcessingService.execute()
  -> get transcript through TranscriptStoreAdapter
  -> resolve prompt through PromptCatalogFactory
  -> render from normalized TranscriptResultV1 projection only
  -> execute post-processing
  -> store PostProcessingResultV1 with original prompt version/hash
```

Gate 3 and Gate 5 already prove:

- two OpenWebUI Prompts exist as source of truth;
- prompt body is not returned in metadata responses;
- missing/deleted prompts return typed `prompt_not_found`;
- restricted prompt access fails closed;
- loader-visible refs do not bypass sidecar checks;
- prompt changes produce new version/hash;
- old processed results keep old version/hash.

## 4. OpenWebUI API Endpoints Discovered

Target OpenWebUI includes the prompt router at:

```text
/api/v1/prompts
```

Source proof:

- `main.py` includes `prompts.router` with prefix `/api/v1/prompts`.
- `routers/prompts.py` defines prompt list, tags, list/search, create, get by id,
  update, metadata update, version update, access update, toggle, delete and
  history endpoints.
- `utils/auth.py` requires a verified user for prompt reads.

Read endpoints relevant to STT v2:

| Endpoint | Source behavior | STT v2 use |
| --- | --- | --- |
| `GET /api/v1/prompts/` | Auth required. Admin with bypass sees all active prompts. Other users see prompts filtered by read access. Response model includes prompt content. | Candidate list source, but response must be transformed server-side before leaving sidecar. |
| `GET /api/v1/prompts/list` | Auth required. Search/list endpoint with `query`, `tag`, order/pagination inputs. Response includes prompt access response items. | Optional list/search path. Useful for tag filtering if proven stable. |
| `GET /api/v1/prompts/tags` | Auth required. Returns tags visible to current user. | Optional capability, not required for MVP adapter. |
| `GET /api/v1/prompts/id/{prompt_id}` | Auth required. Returns prompt by id if readable. Returns 404 when missing or unreadable. Response includes content and access grants. | Candidate get-by-id source. Needs failure mapping guardrails. |
| `GET /api/v1/prompts/id/{prompt_id}/history` | Auth required. Returns prompt history after read access check. | Optional version proof. Not required for current hash contract if `version_id` and content are present. |
| `GET /api/v1/prompts/id/{prompt_id}/history/{history_id}` | Auth required. Returns a history snapshot after read access check and prompt/history binding check. Snapshot can contain prompt content. | Avoid in normal adapter path. Use only in targeted proof if needed. |
| `GET /api/v1/prompts/id/{prompt_id}/history/diff` | Auth required. Returns diff between versions after read access check. | Not needed for STT v2 adapter. Avoid. |

Write endpoints discovered but not needed:

- `POST /api/v1/prompts/create`
- `POST /api/v1/prompts/id/{prompt_id}/update`
- `POST /api/v1/prompts/id/{prompt_id}/update/meta`
- `POST /api/v1/prompts/id/{prompt_id}/update/version`
- `POST /api/v1/prompts/id/{prompt_id}/access/update`
- `POST /api/v1/prompts/id/{prompt_id}/toggle`
- `DELETE /api/v1/prompts/id/{prompt_id}/delete`
- `DELETE /api/v1/prompts/id/{prompt_id}/history/{history_id}`

The future STT adapter should be read-only and must not call write endpoints.

No dedicated get-by-command route was found on target runtime. Source contains
model-level `get_prompt_by_command`, but not a router-level `GET /command/...`.
The unauthenticated probe to `/api/v1/prompts/command/stt-summary` returned the
frontend HTML fallback, not a JSON prompt API response. Therefore:

```text
resolve_command(command, user_context)
  -> call list/search
  -> filter exact command server-side
```

## 5. Runtime API Probes

OpenAPI probe:

```text
GET http://127.0.0.1:8080/openapi.json
status: 200
body: HTML, not JSON
result: runtime OpenAPI schema is not available as machine-readable JSON in prod
```

This matches the official docs guidance that Swagger/API docs require `ENV=dev`.
The adapter contract should therefore not depend on live `/openapi.json` being
available in production.

Unauthenticated prompt probes:

```text
GET /api/v1/prompts/                                      -> 401 Not authenticated
GET /api/v1/prompts/list                                  -> 401 Not authenticated
GET /api/v1/prompts/tags                                  -> 401 Not authenticated
GET /api/v1/prompts/id/bee65fbb-c9ba-428e-b1e2-c1fdf8ee03b4 -> 401 Not authenticated
GET /api/v1/prompts/command/stt-summary                   -> 200 HTML frontend fallback
```

The 401 results prove there is no safe unauthenticated internal trust path for
prompt reads. The command-path result proves the command endpoint is not present
as a JSON API route in this runtime.

Target DB schema probe, sanitized:

```text
prompt table:
  id, command, user_id, name, content, data, meta, is_active,
  version_id, created_at, updated_at
  row count: 2

prompt_history table:
  id, prompt_id, parent_id, snapshot, user_id, commit_message, created_at
  row count: 4

access_grant table:
  id, resource_type, resource_id, principal_type, principal_id, permission, created_at
  row count: 7
```

Active STT prompt metadata, sanitized:

```json
[
  {
    "id": "bee65fbb-c9ba-428e-b1e2-c1fdf8ee03b4",
    "command": "stt-summary",
    "template_id": "stage2.stt.summary.v1",
    "template_kind": "post_processing",
    "tags": ["stage2-stt-v2", "stt-post-processing", "summary"],
    "is_active": true,
    "version_id_present": true,
    "content_len": 268,
    "history_count": 2,
    "grant_count": 1
  },
  {
    "id": "33fa981d-7342-4b70-a206-9aaa670b037b",
    "command": "stt-meeting-protocol",
    "template_id": "stage2.stt.meeting_protocol.v1",
    "template_kind": "post_processing",
    "tags": ["stage2-stt-v2", "stt-post-processing", "meeting-protocol"],
    "is_active": true,
    "version_id_present": true,
    "content_len": 313,
    "history_count": 2,
    "grant_count": 1
  }
]
```

Prompt content was not printed.

## 6. Auth Options And Security Analysis

### A. Service API Key

How obtained:

- create a dedicated OpenWebUI service account;
- enable API keys through OpenWebUI admin settings;
- generate an API key;
- store it as a server-side secret for the sidecar only.

Security properties:

- API key acts as the creating user;
- if the service account is non-admin, it sees only that account's prompts and
  grants, not the current user's view;
- if the service account is admin, it can see all prompts and the adapter must
  re-apply user-context access checks locally.

Pros:

- operationally simple;
- no browser/session forwarding required;
- can call prompt API from sidecar over internal network.

Cons:

- dangerous if implemented as "admin key reads everything, sidecar trusts it";
- endpoint restrictions limit paths, not resource visibility;
- does not naturally prove current-user access parity.

Use only with:

- endpoint allowlist restricted to `/api/v1/prompts`;
- no write endpoints in adapter code;
- local owner/user/group/public access check against returned access grants;
- no prompt body in metadata;
- explicit `requires_admin_service_token=true` capability;
- Gate 5 parity proof before production switch.

### B. Admin API Key

This is a special case of service API key.

It can support exact local filtering because it can retrieve prompt rows and
access grants, but it is also the highest-risk option. It should never be the
silent default.

Minimum guardrails:

- dedicated service account, not a human admin account;
- endpoint restrictions enabled and limited;
- adapter refuses to start if endpoint restriction proof is missing, unless an
  explicit unsafe override is set for a non-production proof;
- all OpenWebUI API responses are normalized and redacted before logging;
- local access check is mandatory before returning metadata or prompt body.

### C. User Token / Session Forwarded From Action

This is the cleanest access model if it can be proven.

Expected shape:

```text
OpenWebUI browser/session
  -> native Action receives current-user identity/session token
  -> sidecar receives opaque user credential or calls OpenWebUI directly
  -> OpenWebUI API enforces current user's prompt visibility
```

Pros:

- closest to native OpenWebUI access behavior;
- no admin service bypass;
- no need to reconstruct all access logic locally.

Cons:

- not proven in current STT v2 Action/loader path;
- storing or logging user JWT/cookies is unacceptable;
- `GET /id/{prompt_id}` returns 404 for both missing and unreadable prompts, so
  exact Gate 5 error-code parity may still need an additional proof or local
  admin-side comparison;
- authenticated GET in OpenWebUI source updates user activity, so a strict
  read-only runtime research pass should not casually exercise real user tokens.

Recommendation:

- make this the preferred long-term model only after an Action-side proof shows
  a safe pass-through credential path without exposing cookies/tokens.

### D. Internal Container / Network Trust Path

Runtime probe shows unauthenticated prompt endpoints return 401. There is no
acceptable unauthenticated trust path.

Recommendation:

- do not build an internal unauthenticated API adapter;
- do not whitelist sidecar network traffic around OpenWebUI auth.

### E. Endpoint-Restricted API Key

Official docs and installed source support endpoint restrictions for API keys.
Installed source checks allowed paths during API-key auth.

Important boundary:

- endpoint restrictions reduce which routes the key can call;
- they do not make an admin key user-scoped;
- they do not replace per-prompt access checks.

Recommended allowlist for proof:

```text
/api/v1/prompts
```

If OpenWebUI supports exact endpoint entries only in a target release, use:

```text
/api/v1/prompts/
/api/v1/prompts/list
/api/v1/prompts/tags
/api/v1/prompts/id
```

The exact match semantics must be proven against the installed version before
production use.

## 7. Access Model Analysis

OpenWebUI prompt access in target source:

- list route uses `get_prompts_by_user_id(user.id, "read")` for non-admins;
- get-by-id route allows admin, owner, or `AccessGrants.has_access(..., "read")`;
- access grants support public `user:*`, direct user grants and group grants;
- owner access is included in list filtering;
- group membership is resolved from OpenWebUI groups.

Important mismatch:

```text
GET /api/v1/prompts/id/{prompt_id}
  missing prompt       -> 404
  existing unreadable  -> 404
```

This is a safe OpenWebUI behavior because it avoids resource enumeration. It is
not identical to current STT v2 Gate 5 behavior, where the sidecar can return
typed `prompt_access_denied` for a known restricted prompt.

API adapter access strategies:

| Strategy | Access parity | Risk |
| --- | --- | --- |
| User token only | Native OpenWebUI visibility, but missing vs denied may collapse to 404. | Needs safe token forwarding proof. |
| Admin service token + local grants | Can preserve current typed `prompt_access_denied` vs `prompt_not_found`. | Admin bypass if local checks drift or are skipped. |
| Non-admin service token | Safe for service account, not current user. | Does not model current user/group visibility. |
| Internal unauthenticated | Not possible on target; 401. | Should not be built. |

Recommended access design for first API adapter implementation:

```text
OpenWebUIPromptApiCatalogAdapter
  mode: service_admin_read_with_local_access_filter
  startup capability: requires_admin_service_token = true
  required proof: endpoint restrictions + local access checks + Gate 5 parity
```

Recommended long-term design:

```text
mode: user_forwarded_credential
```

only if the native Action can provide a safe non-persistent current-user
credential to the sidecar.

## 8. Metadata / Version / Hash / History Analysis

Installed source model includes:

```text
PromptModel:
  id
  command
  user_id
  name
  content
  data
  meta
  tags
  is_active
  version_id
  created_at
  updated_at
  access_grants
```

OpenWebUI docs describe Prompts as slash commands with tags, access control and
version history. Runtime source and DB confirm those fields exist on target.

API adapter mapping:

| OpenWebUI field | STT v2 field |
| --- | --- |
| `meta.template_id` or `meta.stage2_template_id` | `template_id` |
| `command` | `command` |
| `name` | `label` |
| `id` | `openwebui_prompt_id` |
| `version_id` | `prompt_version` |
| `content` | internal `prompt_body` only |
| `sha256(content)` | `prompt_body_hash` |
| `tags` | `tags` |
| `meta.requires_speakers` | `requires_speakers` |
| `meta.chunkable` | `chunkable` |
| `access_grants` | safe projected `access_grants` |

Version model:

- `version_id` exists in target prompt rows;
- `prompt_history` rows exist for each STT prompt;
- current Gate 5 can be preserved by storing `prompt_version` and
  `prompt_body_hash` in `PostProcessingResultV1`;
- if a future OpenWebUI release returns no `version_id`, the adapter can still
  compute `prompt_body_hash` and set `prompt_version = None`, but capabilities
  must report `supports_version_id=false`.

Hash model:

- hash is computed from the prompt body fetched server-side;
- prompt body hash can be returned as metadata;
- prompt body itself must never be returned to loader/Action metadata, stored in
  sidecar config, or logged.

History endpoints:

- useful for proof and diagnostics;
- not needed in the normal adapter path;
- history snapshots can contain prompt bodies and must be treated as sensitive.

## 9. Contract Equivalence Table

| Requirement | SQLite adapter status | API adapter candidate status | Gap | Proof needed |
| --- | --- | --- | --- | --- |
| List two STT templates | Pass | Likely pass via `GET /api/v1/prompts/` or `/list` with tag filtering | Requires credential | Authenticated target proof |
| Resolve by `template_id` | Pass | Pass by list/filter on `meta.template_id` | No direct API route | Unit + runtime proof |
| Resolve by command | Pass | Pass by list/filter on `command` | No direct command route | Prove command HTML fallback is not used |
| Resolve by prompt id | Not in current protocol, available internally through row id | Candidate via `GET /id/{prompt_id}` | Add protocol method | Contract + tests |
| Prompt body is source of truth | Pass | Pass if content read from API only | API returns body in response | Server-side normalization proof |
| No prompt body in metadata response | Pass | Must be implemented | High leakage risk | Loader/Action response scan |
| Prompt body not duplicated in loader/Action/config | Pass | Must be preserved | None if adapter boundary kept | Static scan + tests |
| Prompt version/hash captured | Pass | Likely pass via `version_id` + `sha256(content)` | Version may be null in future | Capability + runtime proof |
| Missing prompt -> `prompt_not_found` | Pass | Pass | OpenWebUI 404 has generic detail | Failure mapping test |
| Deleted prompt -> `prompt_not_found` | Pass | Likely pass if API excludes inactive prompts | Need deleted/toggled proof | Runtime proof with temporary prompt |
| Changed prompt -> new version/hash | Pass | Likely pass if no body cache | Need authenticated proof | Runtime update proof |
| Old result keeps old version/hash | Pass | Should pass because result contract unchanged | None if service unchanged | Gate 5 replay |
| Restricted prompt inaccessible | Pass | User-token mode likely safe; admin-token mode must local-filter | Credential strategy | Gate 5 access proof |
| Loader-visible refs cannot bypass access | Pass | Should be unchanged outside adapter | None if routes unchanged | Existing Gate 5 route proof |
| No OpenWebUI core patch | Pass | Pass if only sidecar adapter added | None | Git diff proof |
| Safe failure if API unavailable | Current SQLite path unaffected | Must map HTTP/network failures | Need new error codes | Unit + route tests |

## 10. Proposed API Adapter Contract

Future adapter name:

```text
OpenWebUIPromptApiCatalogAdapter
```

It should implement the same boundary as the current adapter and add prompt-id
resolution:

```python
class PromptCatalogAdapter(Protocol):
    def list_templates(
        self,
        user_context: PromptCatalogUserContextV1,
    ) -> list[PostProcessingTemplateV1]: ...

    def get_template(
        self,
        template_id: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate: ...

    def resolve_command(
        self,
        command: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate: ...

    def resolve_prompt(
        self,
        prompt_id: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate: ...

    def adapter_capabilities(
        self,
    ) -> PromptCatalogAdapterCapabilitiesV1: ...
```

Proposed capabilities:

```python
class PromptCatalogAdapterCapabilitiesV1(Stage2Model):
    adapter_id: str
    source: Literal["openwebui_sqlite", "openwebui_api", "disabled"]
    supports_prompt_list: bool
    supports_prompt_get_by_id: bool
    supports_prompt_get_by_command: bool
    supports_tags: bool
    supports_metadata: bool
    supports_access_grants: bool
    supports_version_id: bool
    supports_history: bool
    supports_user_scoped_access: bool
    supports_endpoint_restricted_api_key: bool
    requires_admin_service_token: bool
    returns_prompt_body_from_source_api: bool
    normalizes_prompt_body_server_side_only: bool
    safe_for_gate5_replacement: bool
    warnings: list[str]
```

Expected candidate capability values for first API adapter:

```json
{
  "source": "openwebui_api",
  "supports_prompt_list": true,
  "supports_prompt_get_by_id": true,
  "supports_prompt_get_by_command": false,
  "supports_tags": true,
  "supports_metadata": true,
  "supports_access_grants": true,
  "supports_version_id": true,
  "supports_history": true,
  "supports_user_scoped_access": false,
  "supports_endpoint_restricted_api_key": true,
  "requires_admin_service_token": true,
  "returns_prompt_body_from_source_api": true,
  "normalizes_prompt_body_server_side_only": true,
  "safe_for_gate5_replacement": false
}
```

`safe_for_gate5_replacement` becomes true only after authenticated target proof.

Normalization rules:

- accept only active prompts;
- require STT tags and `meta.template_kind == "post_processing"`;
- require stable `template_id`;
- never return raw OpenWebUI API JSON to STT routes;
- never return prompt body in `PostProcessingTemplateV1`;
- compute hash from API content before discarding the body from public metadata;
- map OpenWebUI access grants into the existing safe projection.

## 11. Proposed Contract Document / Update Point

Create before implementation:

```text
docs/stage2/contracts/STT_V2_PROMPT_CATALOG_ADAPTER_CONTRACT.md
```

Required content:

- `PromptCatalogAdapter` interface;
- `OpenWebUISqlitePromptCatalogAdapter` behavior;
- `OpenWebUIPromptApiCatalogAdapter` behavior;
- supported OpenWebUI source version/image evidence;
- required OpenWebUI endpoints;
- auth/credential model;
- access model;
- version/hash/history model;
- UI-safe metadata model;
- typed failure mapping;
- fallback policy;
- compatibility tests;
- update procedure when OpenWebUI API changes.

Update rule:

```text
If OpenWebUI prompt API changes:
  update STT_V2_PROMPT_CATALOG_ADAPTER_CONTRACT.md
  update only OpenWebUIPromptApiCatalogAdapter / adapter tests
  do not change loader, Action, post-processing service or transcript contracts
```

## 12. Failure Mapping

Required adapter errors:

| Adapter error | Trigger | HTTP mapping in sidecar | Chat-safe message rule |
| --- | --- | --- | --- |
| `prompt_not_found` | Missing prompt, inactive/deleted prompt, wrong STT tags/meta | 404 | No raw API body |
| `prompt_access_denied` | Existing prompt not readable for user context | 403 | No prompt id enumeration beyond user-known refs |
| `prompt_api_unavailable` | Connection timeout, DNS failure, OpenWebUI down | 503 | No URL with credentials |
| `prompt_api_unauthorized` | Invalid/missing service credential, 401 from OpenWebUI | 503 or 401 internal policy | No token fragments |
| `prompt_api_forbidden` | Endpoint restriction denies path or service lacks permission | 503 or 403 internal policy | No raw response |
| `prompt_api_contract_mismatch` | Response shape missing required fields or non-JSON HTML fallback | 502 | Include endpoint name only |
| `prompt_version_unavailable` | Version id required by configured policy but absent | 502 | No prompt body |
| `prompt_metadata_incomplete` | Missing tags/meta/template id/command | 502 or skip in list | No raw OpenWebUI JSON |
| `prompt_body_unavailable` | Prompt content missing/empty when resolving for execution | 502 | No raw response |
| `prompt_catalog_disabled` | Adapter disabled by config | 503 | Existing behavior |

HTTP status from OpenWebUI should not be passed through blindly.

Recommended mapping details:

- 401 from OpenWebUI -> `prompt_api_unauthorized`;
- 403 from OpenWebUI -> `prompt_api_forbidden`;
- 404 from get-by-id:
  - user-token mode: map to `prompt_not_found` unless a separate safe existence
    proof can distinguish denied;
  - admin-token/local-filter mode: map missing to `prompt_not_found` and local
    access failure to `prompt_access_denied`;
- HTML response where JSON expected -> `prompt_api_contract_mismatch`;
- network timeout -> `prompt_api_unavailable`.

All error objects must be safe for chat display and logs.

## 13. Fallback Policy

Options:

| Option | Assessment |
| --- | --- |
| API adapter primary, SQLite disabled | Not recommended now. Access parity is not proven. |
| API adapter primary, silent SQLite fallback | Not recommended. Masks API breakage and makes proof ambiguous. |
| SQLite remains primary until API adapter fully proven | Recommended current production stance. |
| Runtime-configurable mode | Recommended for implementation. |

Recommended config modes:

```text
STAGE2_STT_PROMPT_CATALOG_MODE=disabled
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_sqlite
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_api
```

Optional non-default proof mode:

```text
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_api_then_sqlite
```

Only allow `openwebui_api_then_sqlite` if:

- response includes a warning capability;
- report/tests explicitly record fallback use;
- production quick action telemetry makes fallback visible.

Preferred behavior:

- production default remains `openwebui_sqlite`;
- `openwebui_api` failure returns typed safe failure, not silent fallback;
- SQLite fallback is allowed only as an explicit proof/rollout guard.

## 14. Runtime Proof Plan Before Replacement

Gate A: contract and unit tests

- create `STT_V2_PROMPT_CATALOG_ADAPTER_CONTRACT.md`;
- add API adapter unit tests with a fake OpenWebUI HTTP server;
- prove prompt content is stripped from public metadata;
- prove failure mapping for 401/403/404/HTML/non-JSON/timeouts;
- prove resolve-by-command uses list/filter, not missing command route.

Gate B: credential proof

- choose one credential model:
  - preferred: user-forwarded token from Action if safely available;
  - fallback: dedicated admin service key with endpoint restrictions and local
    access filtering;
- prove credential is present without printing it;
- prove OpenWebUI API key endpoint restrictions are enabled if service/admin key
  is used;
- prove sidecar logs redact Authorization and API-key headers.

Gate C: target API metadata proof

- API lists exactly the two STT MVP prompts;
- API returns ids, command, name, tags, meta, access grants, version id and
  content length;
- sidecar returns only `PostProcessingTemplateV1` metadata;
- prompt body does not appear in loader, Action response, route response or
  proof report.

Gate D: Gate 5 parity proof

- temporary public prompt resolves;
- temporary restricted prompt is inaccessible to unauthorized context;
- unauthorized execution fails before LLM call;
- loader-visible refs remain insufficient for access;
- missing prompt returns typed safe error;
- deleted/toggled-off prompt returns typed safe error;
- prompt content change produces new hash/version;
- first processed result keeps original hash/version after a second execution.

Gate E: rollback proof

- switch back to `openwebui_sqlite`;
- prove quick actions still work;
- prove no OpenWebUI core files changed.

## 15. Risks

1. Admin key bypass.
   - Impact: restricted prompt content can leak if local checks are skipped.
   - Mitigation: endpoint restriction, local access filter, anti-drift tests,
     `requires_admin_service_token` capability warning.

2. Prompt body leakage through API response.
   - Impact: prompt body can reach browser/report/logs.
   - Mitigation: normalize to `ResolvedPromptTemplate` internally and
     `PostProcessingTemplateV1` externally; add response scans.

3. Missing vs access-denied collapse.
   - Impact: exact Gate 5 typed errors can drift.
   - Mitigation: admin/local-filter mode or explicit contract change. Do not
     silently accept user-token 404 collapse as equivalent.

4. Runtime API docs unavailable in prod.
   - Impact: cannot rely on `/openapi.json` as production proof.
   - Mitigation: source-route smoke tests and endpoint probes.

5. OpenWebUI API drift.
   - Impact: adapter breaks after upstream update.
   - Mitigation: single contract document, adapter-local tests, factory boundary.

6. History endpoints include snapshots.
   - Impact: old prompt content can leak.
   - Mitigation: avoid history endpoints in normal path; if used for proof,
     sanitize output.

7. Silent fallback.
   - Impact: hides failed API migration.
   - Mitigation: default hard typed failure in `openwebui_api` mode; fallback
     only if explicitly configured and reported.

## 16. Open Questions

1. Can the native OpenWebUI Action safely forward the current user's JWT/session
   to the sidecar without exposing it to browser-visible code or logs?

2. Will production policy accept a dedicated admin service API key if endpoint
   restrictions and local access filtering are mandatory?

3. Should STT v2 preserve separate `prompt_access_denied` vs `prompt_not_found`
   forever, or is a safe non-enumerating `prompt_not_found` acceptable in
   user-token API mode?

4. Are OpenWebUI API keys currently enabled in target persistent config, or must
   an admin enable them before proof? This research did not change target config.

5. Should `resolve_prompt(prompt_id, user_context)` be added to the public
   adapter protocol before implementing API mode?

## 17. Recommended Sequence

1. Add `STT_V2_PROMPT_CATALOG_ADAPTER_CONTRACT.md`.
2. Add `PromptCatalogAdapterCapabilitiesV1`.
3. Add API adapter tests with fake HTTP responses.
4. Implement `OpenWebUIPromptApiCatalogAdapter` behind
   `STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_api`.
5. Add redaction/no-body-leak tests.
6. Prove credential strategy on target.
7. Run Gate 3 and Gate 5 parity proof with API mode.
8. Keep SQLite as default until the report says `safe_for_gate5_replacement=true`.

## 18. Final Verdict

```text
Verdict: GO with guardrails
```

Meaning:

- It is reasonable to implement an API-backed adapter behind a config flag.
- It is not reasonable to replace the SQLite adapter as production default yet.
- SQLite remains the accepted MVP-safe adapter and fallback source until API
  credential/access parity is proven.
- The future API adapter must normalize OpenWebUI API responses into the current
  STT v2 contract and must never expose raw OpenWebUI JSON, prompt bodies,
  secrets or internal URLs.

Do not change:

- OpenWebUI core;
- loader/Action contracts;
- prompt body storage rules;
- `TranscriptResultV1`;
- current SQLite adapter behavior.
