# OpenWebUI STT Sidecar Routing and Auth Audit

## 1. Summary

This audit researched how to connect the implemented Stage 2 STT sidecar to the
current OpenWebUI deployment without a deep OpenWebUI fork.

Current verdict:

```text
needs_operator_decision
```

Reason:

- deployment shape is clear enough: Traefik is the only public HTTP/HTTPS
  entrypoint and OpenWebUI is routed by Docker labels;
- the sidecar exists as `services/stage2-stt` and exposes
  `GET /stage2-api/transcription/capabilities`;
- there is no production Authelia/auth middleware in the current PRD-0 compose;
- OpenWebUI session/current-user propagation is not proven in this repo;
- authenticated job routes must not be implemented until the identity boundary
  is selected and tested.

Recommended direction:

- MVP: Traefik path route to the sidecar under the same domain, protected by an
  explicit auth boundary. If Authelia is selected, use ForwardAuth and trusted
  identity headers only on the internal Docker network.
- Production: prefer corporate OIDC/SSO as source of truth, align OpenWebUI and
  the sidecar on the same identity provider, and keep OpenWebUI upstream
  updatable.

## 2. Current implementation baseline

Already implemented:

- service: `services/stage2-stt`;
- package: `services/stage2-stt/stage2_stt`;
- FastAPI app: `services/stage2-stt/stage2_stt/app.py`;
- endpoint: `GET /stage2-api/transcription/capabilities`;
- provider boundary: `SttProviderAdapterFactory`;
- first adapter: `LemonfoxSttAdapter`;
- server-side STT config loader;
- provider capability profile;
- output profile validation;
- storage mode model for `auto|s3|none`;
- prepared-audio validation and cancel domain model.

Not implemented:

- production sidecar container wiring;
- Traefik route to sidecar;
- OpenWebUI frontend integration;
- OpenWebUI session/current-user propagation;
- authenticated `POST /stage2-api/transcription/jobs`;
- result/cancel job routes;
- queue/persistence/storage SDK wiring.

Baseline evidence:

- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/contracts.py`

## 3. Repository/deployment findings

Repository shape:

- This repo is still mainly a deployment/docs skeleton plus the new
  `services/stage2-stt` sidecar package.
- OpenWebUI backend source is not present.
- OpenWebUI is consumed as an upstream image, not a forked local backend.
- Production compose file is `compose/openwebui.compose.yml`.
- Existing smoke scripts are PRD-0 deployment checks and do not know about the
  STT sidecar.

Relevant files reviewed:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `compose/openwebui.compose.yml`
- `deploy/hermes-corporate-v1/authelia/configuration.yml.template`
- `deploy/hermes-corporate-v1/authelia/users_database.yml.template`
- `deploy/hermes-corporate-v1/compose.node.yml.placeholder`
- `docs/decisions/ADR-0004-traefik-ingress.md`
- `docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/ops/SMOKE_TESTS.md`
- `scripts/preflight.sh`
- `scripts/smoke-test.sh`

External primary docs checked:

- OpenWebUI API keys:
  `https://docs.openwebui.com/features/authentication-access/api-keys/`
- OpenWebUI API endpoints:
  `https://docs.openwebui.com/reference/api-endpoints/`
- OpenWebUI SSO/OIDC/trusted header docs:
  `https://docs.openwebui.com/features/authentication-access/auth/sso/`
- OpenWebUI hardening docs:
  `https://docs.openwebui.com/getting-started/advanced-topics/hardening/`
- Authelia Traefik integration:
  `https://www.authelia.com/integration/proxies/traefik/`
- Authelia trusted header SSO:
  `https://www.authelia.com/integration/trusted-header-sso/introduction/`
- Authelia forwarded headers:
  `https://www.authelia.com/integration/proxies/forwarded-headers/`

## 4. OpenWebUI deployment findings

Current OpenWebUI deployment:

- image: `${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:v0.9.6}`;
- container: `openwebui`;
- internal port: `8080`;
- external ports: none on OpenWebUI service;
- Traefik routes the configured OpenWebUI host to `openwebui:8080`;
- persistent data volume: `openwebui_data:/app/backend/data`;
- auth env:
  - `WEBUI_AUTH=${WEBUI_AUTH:-true}`;
  - `ENABLE_SIGNUP=${ENABLE_SIGNUP:-false}`;
  - `DEFAULT_USER_ROLE=${DEFAULT_USER_ROLE:-pending}`;
  - `WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}`;
  - `WEBUI_ADMIN_EMAIL`;
  - `WEBUI_ADMIN_PASSWORD`.

Implications:

- OpenWebUI is not directly public in compose.
- OpenWebUI owns its own local auth/session surface today.
- The repo does not include OpenWebUI backend internals needed to validate
  session cookies directly.
- `openwebui_data` can contain sensitive OpenWebUI config and provider secrets;
  a sidecar must not read it as an auth shortcut.

## 5. Traefik routing findings

Current Traefik deployment:

- image: `${TRAEFIK_IMAGE:-traefik:v3.6}`;
- public ports: `80:80`, `443:443`;
- Docker provider enabled;
- `exposedbydefault=false`;
- OpenWebUI route is defined only by container labels;
- no existing middleware is attached to the OpenWebUI router;
- no existing `/stage2-api/*` route exists;
- no path-strip middleware exists;
- no sidecar service exists in compose.

Sidecar routing is technically compatible with the current pattern:

```text
Host(`${OPENWEBUI_HOST}`) && PathPrefix(`/stage2-api/transcription`)
  -> stage2-stt:<sidecar-port>
```

Path handling:

- The sidecar currently serves the full path
  `/stage2-api/transcription/capabilities`.
- A Traefik route should not strip the prefix unless the sidecar app route is
  changed later.

Required route properties:

- sidecar must join the same internal Docker network as Traefik;
- sidecar must not publish a host port;
- `traefik.enable=true` should be set only on the sidecar container;
- router priority should prevent accidental catch-all routing to OpenWebUI;
- route should inherit TLS on `websecure`;
- route must attach auth middleware before job routes go live.

## 6. Authelia/auth findings

Repo-local Authelia state:

- `deploy/hermes-corporate-v1/authelia/configuration.yml.template` is explicitly
  placeholder-only and not production-ready.
- `deploy/hermes-corporate-v1/authelia/users_database.yml.template` is
  placeholder-only and forbids real users/password hashes in Git.
- `deploy/hermes-corporate-v1/compose.node.yml.placeholder` describes a future
  per-node stack, not the current PRD-0 deployment.
- `compose/openwebui.compose.yml` does not include Authelia.

External Authelia facts from primary docs:

- Authelia supports Traefik integration through forward authentication.
- Authelia trusted-header SSO can return headers such as `Remote-User`,
  `Remote-Groups`, `Remote-Name` and `Remote-Email` to the reverse proxy for
  internal forwarding to backend applications.
- Authelia warns that forwarded headers must come from trusted sources and must
  be removed/replaced when they originate from untrusted clients.

Implication:

- Authelia is a plausible auth boundary, but this repo does not yet contain a
  deployable Authelia configuration.
- Treating Authelia as already present would be a false positive.

## 7. Identity propagation options

### Identity source candidates

Candidate identity sources:

- reverse proxy identity headers from Authelia or another trusted auth proxy;
- OpenWebUI JWT/API token validation;
- OpenWebUI backend shim that passes current user to sidecar;
- separate Stage 2 auth/session.

### Header identity contract if Option A is selected

Minimum candidate headers from a trusted auth proxy:

- `Remote-User` or a project-specific normalized `X-Stage2-User`;
- `Remote-Email` or `X-Stage2-Email`;
- `Remote-Groups` or `X-Stage2-Groups`;
- `X-Forwarded-Proto`;
- `X-Forwarded-Host`;
- optional `X-Request-Id`.

Sidecar must treat these headers as authoritative only when:

- request source is Traefik/internal network;
- direct public access to the sidecar is impossible;
- Traefik/auth middleware strips client-supplied identity headers before adding
  verified headers;
- sidecar rejects requests missing the required identity on job routes.

### OpenWebUI API token/JWT facts

OpenWebUI docs state:

- API keys are personal access tokens and inherit the creating user's role/group
  permissions.
- OpenWebUI API endpoints accept API keys and JWT tokens for API
  authentication.
- The web UI uses JWT tokens internally for API endpoints.

Implication:

- OpenWebUI token validation may be usable, but this repo does not contain a
  stable local contract for sidecar-to-OpenWebUI token introspection.
- Passing user API keys from browser to sidecar would be poor UX and creates a
  new sensitive credential surface.
- Cookie/JWT introspection against OpenWebUI internals is not acceptable until
  proven against the pinned image and documented as a stable boundary.

## 8. Option comparison

| Option | Description | MVP fit | Production fit | Main risk | Verdict |
| --- | --- | --- | --- | --- | --- |
| A | Traefik route + Authelia/ForwardAuth identity headers | Good if Authelia is approved and configured | Good with hardened header stripping and internal-only sidecar | Header spoofing if proxy/header trust is wrong | Recommended direction after operator decision |
| B | OpenWebUI backend shim/proxy to sidecar | Weak in this repo | Weak unless an official extension point is proven | Requires OpenWebUI backend changes or unsupported plugin route | Do not choose now |
| C | Sidecar validates OpenWebUI session/API token | Possible research path | Possible only with stable token/JWT/introspection contract | Depends on OpenWebUI internals or exposes user API keys | Defer until runtime proof |
| D | Separate Stage 2 auth/session | Possible but awkward | Possible for larger platform | Duplicate login/session/admin model | Not recommended for current MVP |
| E | Direct browser-to-sidecar with no auth, relying only on same domain | Bad | Not acceptable | Auth bypass and spoofable user context | Reject |

### Option A. Traefik route + Authelia identity headers

Pros:

- keeps OpenWebUI upstream image untouched;
- keeps STT provider keys only in the sidecar;
- uses same public domain and path;
- aligns with sidecar/domain isolation;
- can protect both capabilities and job routes;
- supports group-aware policy decisions if groups are forwarded and normalized.

Risks:

- current repo has no production Authelia deployment;
- header spoofing is possible if identity headers are not stripped from client
  requests before proxy injection;
- group format and role mapping must be defined;
- OpenWebUI local auth and Authelia auth may diverge unless SSO alignment is
  planned.

Required before implementation:

- operator decision to introduce Authelia or another auth proxy;
- explicit middleware labels/config;
- header strip/inject contract;
- sidecar trust boundary contract;
- smoke tests proving forged public headers are ignored/rejected.

### Option B. OpenWebUI backend shim/proxy to sidecar

Pros:

- would reuse OpenWebUI's current session/current-user if implemented inside
  OpenWebUI;
- browser would call only OpenWebUI routes.

Risks:

- this repo has no OpenWebUI backend source;
- no local plugin/custom-route mechanism is proven;
- likely creates deep fork pressure;
- increases upgrade risk.

Verdict:

- do not use for the next slice unless an official OpenWebUI extension point is
  proven and documented.

### Option C. Sidecar validates OpenWebUI session/API token

Pros:

- could keep a single OpenWebUI login for users;
- OpenWebUI docs confirm API keys/JWT tokens are accepted by OpenWebUI API
  endpoints.

Risks:

- no stable sidecar token introspection endpoint is documented in this repo;
- validating OpenWebUI JWT directly would couple sidecar to OpenWebUI internals
  and `WEBUI_SECRET_KEY`;
- user API keys should not become a browser-to-sidecar requirement;
- cookie handling/CORS/CSRF behavior must be proven on the pinned image.

Verdict:

- research-only until a runtime proof identifies a stable and safe validation
  path.

### Option D. Separate Stage 2 auth/session

Pros:

- sidecar owns auth completely;
- avoids OpenWebUI internals;
- can integrate with corporate identity directly.

Risks:

- duplicate login/permissions;
- UX friction;
- separate admin lifecycle;
- possible mismatch with OpenWebUI users/groups and workspaces.

Verdict:

- not recommended for MVP unless the operator rejects shared proxy identity and
  rejects OpenWebUI SSO/token validation.

### Option E. No auth / same-domain only

Pros:

- fastest to wire.

Risks:

- fails security requirements;
- job routes could process sensitive audio without authenticated identity;
- browser/client can spoof user headers if accepted.

Verdict:

- rejected.

## 9. Recommended MVP path

Recommended MVP path:

```text
Same domain + Traefik PathPrefix route + explicit auth middleware +
trusted proxy identity headers + sidecar identity validator.
```

MVP target shape:

```text
https://gpt.alpha-soft.ru/stage2-api/transcription/*
  -> Traefik websecure router
  -> auth middleware
  -> stage2-stt sidecar internal service
```

MVP rules:

- do not expose sidecar host ports;
- keep sidecar on internal Docker network only;
- protect `/stage2-api/transcription/*` with auth middleware before job routes;
- capabilities endpoint may be less sensitive, but should follow the same route
  policy to avoid later split-brain behavior;
- sidecar must reject job requests without verified identity;
- sidecar must ignore untrusted client-supplied identity headers;
- add smoke tests:
  - anonymous request to job route is rejected;
  - request with forged identity header from outside is rejected;
  - authenticated request through Traefik gets normalized user/email/groups;
  - provider key is absent from browser-visible response and logs.

MVP cannot start until:

- operator selects the auth middleware: Authelia, another forward-auth proxy, or
  a proven OpenWebUI/SSO token path;
- the sidecar identity header contract is approved.

## 10. Recommended production path

Recommended production path:

- use a corporate identity provider through OIDC/SSO;
- align OpenWebUI and the sidecar to the same identity source;
- avoid direct coupling to OpenWebUI session database or private JWT internals;
- use proxy identity only over a trusted internal network;
- strip all inbound identity headers from external clients before injecting
  verified identity;
- define group/role mapping for transcription permission;
- keep authorization decisions in sidecar/backend policy, not in the browser;
- add operational logs without provider keys or raw audio/transcript content;
- treat `openwebui_data`, `.env`, STT audio storage and transcript storage as
  sensitive.

Production can use Option A or a hardened OIDC-token validation model, but must
not rely on an unauthenticated sidecar route.

## 11. Security requirements

Must hold before job route implementation:

- sidecar is never directly public without auth boundary;
- sidecar publishes no host port;
- Traefik is the only public HTTP/HTTPS entrypoint;
- identity headers are trusted only from Traefik/internal network;
- Traefik/auth middleware strips client-supplied identity headers before
  injecting verified headers;
- external clients cannot spoof user/group/email headers;
- sidecar rejects missing/invalid identity on job routes;
- provider API keys remain only in sidecar server-side env;
- no `NEXT_PUBLIC_*` provider secret exists;
- CORS is restricted to the OpenWebUI domain and does not open a provider proxy
  to arbitrary origins;
- logs do not include API keys, Authorization headers, raw sensitive audio or
  raw transcript content;
- storage/object keys do not include user email, provider key or unnecessary
  sensitive metadata;
- capabilities response stays secret-free;
- direct sidecar access from outside Docker network is denied.

## 12. Required config changes

No config changes were made in this audit.

Future changes required for Option A:

- add `stage2-stt` service to compose or a separate compose file;
- connect `stage2-stt` to `openwebui_web`;
- add Traefik labels equivalent to:

```text
Host(`${OPENWEBUI_HOST}`) && PathPrefix(`/stage2-api/transcription`)
```
- do not publish sidecar ports;
- add auth middleware labels;
- add middleware/header rules to strip user-controlled identity headers;
- pass only server-side `STAGE2_*` env values into sidecar;
- extend smoke scripts for sidecar route/auth tests;
- document exact identity headers and group mapping.

If Authelia is chosen:

- add production-ready Authelia service/config outside placeholder templates;
- define Authelia users/identity source outside Git;
- configure ForwardAuth middleware;
- forward only approved identity headers to the sidecar;
- verify forged header rejection.

## 13. Stop conditions for implementation

Stop before implementing job routes if any condition holds:

- no auth middleware or token validation path is selected;
- sidecar would be public without authenticated route policy;
- sidecar would trust `Remote-*` or `X-Stage2-*` headers from public clients;
- OpenWebUI session validation requires reading private DB/session internals;
- implementation requires a deep OpenWebUI fork;
- provider key would be exposed to browser, logs, docs or tests;
- CORS would allow arbitrary origins for job routes;
- group/permission mapping is undefined;
- direct sidecar host port is required for public access;
- storage/retention policy for prepared audio is still undefined for job
  execution.

## 14. Next implementation slice

Next slice should be routing/auth implementation only, not STT job execution.

Recommended scope:

1. Add sidecar route behind Traefik in a non-production or explicitly approved
   compose slice.
2. Select auth boundary:
   - preferred: Authelia/ForwardAuth or equivalent trusted auth proxy;
   - alternative: proven OpenWebUI/OIDC token validation.
3. Implement sidecar identity middleware:
   - parse normalized user/email/groups;
   - reject missing identity for non-capabilities routes;
   - accept identity headers only from trusted proxy context.
4. Add smoke tests:
   - capabilities through Traefik;
   - unauthenticated rejection;
   - forged header rejection;
   - authenticated identity projection.
5. Only after this passes, implement authenticated job create/result/cancel
   routes.

## 15. Unknowns / questions

Unknowns:

- Will the operator approve Authelia for PRD-0/Stage 2, or use a different
  corporate identity provider?
- Should OpenWebUI itself move to SSO/trusted-header auth, or only the STT
  sidecar route?
- What exact identity headers should be standardized?
- What group/role grants transcription usage?
- Should capabilities endpoint be public within same domain or authenticated
  consistently with job routes?
- Will Stage 2 sidecar run in the same compose project or separate compose
  project on the same Docker network?
- What is the accepted internal service name and port?
- What CORS policy will the sidecar enforce if called directly from browser UI?
- What log retention and transcript retention rules apply after job routes?
- Is live runtime access available to test real Traefik middleware behavior?

## 16. Final verdict

```text
needs_operator_decision
```

We are not ready to implement authenticated STT job routes.

We are ready to prepare a sidecar routing/auth implementation plan once the
operator chooses the identity boundary. The safest next decision is whether the
MVP uses Traefik + Authelia/ForwardAuth identity headers or a proven
OpenWebUI/OIDC token validation path. Until that decision is made, adding
`POST /stage2-api/transcription/jobs` would create an auth bypass risk.
