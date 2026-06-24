# OpenWebUI Admin/Test-User Runtime Proof

Date: 2026-06-24

Repository: `Kwentin3/corp-openweb-ui`

Scope: Stage 2 / PRD-1 native OpenWebUI capabilities, Admin/Test-User proof
matrix.

Verdict: `admin_test_user_runtime_proof_partial`

## Executive Summary

Admin/test-user runtime proof was re-attempted after the operator clarified that
`WEBUI_ADMIN_EMAIL` and `WEBUI_ADMIN_PASSWORD` are present in the local
workspace `.env`. The `.env` file was read only for those two variable names.
Credential values were not printed, committed, copied into docs, stored in
screenshots or exported as browser/session artifacts.

Admin authentication succeeded through the OpenWebUI API and returned admin
role. The proof therefore moved past the previous credentials blocker. The
result is still partial because no `stage2-proof-*` test actors or groups
existed on the deployed instance, and this run did not create users, groups,
models, prompts or knowledge items on a production-like stand without explicit
operator approval for those state changes.

Authenticated read-only proof confirmed:

- public deployed version is still `0.9.6`;
- public health endpoint responds;
- unauthenticated `/api/models` remains protected with `401 Unauthorized`;
- Stage 2 STT static loader is served;
- Stage 2 STT normalization config is served.
- admin API auth works with role `admin`;
- users/groups/models/prompts/knowledge/files/chats/functions/audio config and
  analytics endpoints are reachable with admin auth;
- default permission keys and several deployed values were captured without
  secrets;
- user/group Preview Access endpoints work.

The remaining blocker is the four-actor behavior matrix: Manager/РО, Employee
inside group and Employee outside group were not available as test actors.

## Runtime Access Status

Status: `authenticated_admin_api_available_actor_matrix_incomplete`

Admin credential env check:

| Variable | Present |
| --- | --- |
| `WEBUI_ADMIN_EMAIL` | yes |
| `WEBUI_ADMIN_PASSWORD` | yes |

Credential values were not printed. No password, cookie, bearer token or
session token was saved.

Available:

- repository working tree;
- local `.env` read only for `WEBUI_ADMIN_EMAIL` and `WEBUI_ADMIN_PASSWORD`;
- public unauthenticated runtime endpoints;
- authenticated admin API session in process memory only;
- official OpenWebUI documentation;
- repo Stage 2 PRD, gates, backlog, acceptance and prior runtime reports.

Not available:

- staging/test-user credentials;
- existing `stage2-proof-*` users/groups;
- explicit approval to create synthetic users/groups/resources on the deployed
  stand;
- approved permission to create users/groups on the deployed instance;
- approved customer test documents;
- approved Web Search rollout scope.

Hard limits observed:

- `.env` was read only for the two approved admin credential variable names;
- no provider keys, tokens, admin credentials, private URLs or customer data
  were printed or copied into this report;
- no production policy was changed;
- no provider was connected;
- no Web Search rollout was executed;
- no LiteLLM/gateway/deep fork work was started.

## Repo State

Preflight commands:

```text
git status --short --branch
## main...origin/main

git rev-parse HEAD
93d8ac4036de29381f82a18fe4ddbc5182b9c37f

git rev-list --left-right --count HEAD...origin/main
0 0

git worktree list
one canonical worktree on main

git branch --show-current
main
```

The tree was clean before this report route started. No unrelated dirty files
were present.

## Documents Read

Required local documents:

- `docs/reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STAGE2_OPENWEBUI.md`

Official OpenWebUI references checked for operator checklist labels:

- Groups:
  `https://docs.openwebui.com/features/authentication-access/rbac/groups/`
- Permissions:
  `https://docs.openwebui.com/features/authentication-access/rbac/permissions/`
- Workspace Models:
  `https://docs.openwebui.com/features/workspace/models/`
- Prompts:
  `https://docs.openwebui.com/features/workspace/prompts/`
- Knowledge:
  `https://docs.openwebui.com/features/workspace/knowledge/`
- Analytics:
  `https://docs.openwebui.com/features/administration/analytics/`
- STT:
  `https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/`
- RAG/Documents:
  `https://docs.openwebui.com/features/chat-conversations/rag/`
- Tools:
  `https://docs.openwebui.com/features/extensibility/plugin/tools/`

## Runtime Checks Performed

Credential environment checks:

```text
dotenv_present: yes
WEBUI_ADMIN_EMAIL present: yes
WEBUI_ADMIN_PASSWORD present: yes
```

No credential values were displayed or captured.

Authenticated admin API checks:

| Check | Result |
| --- | --- |
| `POST /api/v1/auths/signin` | success, role `admin`, token not printed |
| `GET /api/v1/users/` | `200`, `users_total=4`, roles `admin=2`, `user=2`, `pending=0` |
| `GET /api/v1/groups/` | `200`, `groups_total=1`, group member count `0` |
| `stage2-proof-*` users/groups | not present |
| user group membership | `users_with_groups=0` |
| `GET /api/v1/models` | `200`, `models_total=4`, `models_with_access_control=0` |
| `GET /api/v1/prompts/` | `200`, `prompts_total=0` |
| `GET /api/v1/knowledge/` | `200`, `knowledge_total=0` |
| `GET /api/v1/files/` | `200`, `files_total=40` |
| `GET /api/v1/chats/` | `200`, `chats_total=18` |
| `GET /api/v1/functions/` | `200`, `functions_total=1` |
| `GET /api/v1/tools/` | `200`, `tools_total=0` |
| `GET /api/v1/audio/config` | `200`, `stt` and `tts` config objects present; credential values not printed |
| `GET /api/v1/analytics/models` | `200`, `analytics_models_count=3` |
| `GET /api/v1/analytics/users` | `200`, `analytics_users_count=4` |
| `GET /api/v1/users/{id}/preview` | `200`, returns `user,groups,models,knowledge,tools` |
| `GET /api/v1/groups/id/{id}/preview` | `200`, returns `group,models,knowledge,tools,permissions` |

Default permission values from authenticated `/api/config`:

| Category | Runtime finding |
| --- | --- |
| Workspace defaults | `knowledge=False`, `models=False`, `prompts=False`, `tools=False`, imports/exports false |
| Sharing defaults | models/prompts/knowledge/tools/notes/skills public/share defaults false |
| Chat defaults | `file_upload=True`, `delete=True`, `delete_message=True`, `stt=True`, `web_upload=True`, `temporary=True`, `temporary_enforced=False` |
| Feature defaults | `web_search=True`, `code_interpreter=True`, `image_generation=True`, `api_keys=False`, `direct_tool_servers=False` |

Browser-facing `/api/config` exposure check:

- no `api_key`, `token`, `bearer`, `authorization`, `sk-`, `AKIA` or private-key
  marker was detected in the public config response;
- the literal word `password` appears in public config metadata, but no
  password value was printed or copied;
- authenticated config contains credential field names for audio providers, but
  values were not printed.

Local Docker:

```text
docker ps --format ...
NAMES IMAGE STATUS PORTS
```

No local containers were running. Authenticated proof used the deployed admin
API, not a local container or screenshot-based browser session.

Safe public deployed checks:

| Check | Result |
| --- | --- |
| `GET /` | `200`, HTML returned |
| `GET /api/config` | `200`, JSON keys include `status,name,version,default_locale,oauth,features`, version `0.9.6` |
| `GET /api/version` | `200`, version `0.9.6` |
| `GET /health` | `200`, status JSON |
| `GET /api/models` without auth | `401 Unauthorized` |
| `GET /static/loader.js` | `200`, contains `stage2_media_transcription_action` |
| `GET /static/stage2-stt-normalization.json` | `200`, version `stage2-stt-browser-normalization-v1` |

The deployed host URL is intentionally omitted from this report.

## Actors Used

Authenticated actor used:

| Actor | Used | Evidence |
| --- | --- | --- |
| Admin | yes | login succeeded with role `admin`; token not printed |
| Manager/РО | no | no `stage2-proof-manager` actor existed and none was created |
| Employee inside group | no | no `stage2-proof-inside` actor existed and none was created |
| Employee outside group | no | no `stage2-proof-outside` actor existed and none was created |

Required actors for the next proof:

| Actor | Purpose | Required constraints |
| --- | --- | --- |
| Admin | Configure users, groups, defaults, resource access and analytics proof | Use approved admin account only; do not export tokens/cookies |
| Manager/РО | Validate manager visibility and approved work-scenario scope | Must not receive blanket admin access |
| Employee inside group | Validate allowed scenario, model, prompt, knowledge and feature visibility | Member of test business/sharing group and needed permission groups |
| Employee outside group | Validate negative access proof | Must not belong to any group that grants the tested resources |

## Test Data Used

Runtime test data was not created because authenticated proof was blocked.

No synthetic runtime data was created in this follow-up. This was intentional:
creating users, groups, models, prompts, knowledge items or files on the
deployed stand is a state-changing action and still needs explicit operator
approval.

Allowed synthetic test data for the next run:

- one safe TXT with artificial instructions;
- one simple generated PDF with no customer data;
- one simple generated DOCX with no customer data;
- one simple generated XLSX with artificial rows only;
- safe Web Search queries with no customer, personal, payroll, banking,
  tax, token, internal URL or private project data;
- two short synthetic chat prompts for analytics sample usage.

Not allowed without customer approval:

- real client documents;
- broker reports;
- scans with signatures/stamps;
- complex XLSX with real formulas/data;
- customer-sensitive Web Search queries;
- production policy changes.

## Proof Matrix

| Domain | Check | Admin | Manager/РО | Employee inside group | Employee outside group | Result | Evidence | Gap | Recommendation |
| ------ | ----- | ----- | ---------- | --------------------- | ---------------------- | ------ | -------- | --- | -------------- |
| Groups / RBAC | Default permissions, group grants, Preview Access | admin API proven | no actor | no actor | no actor | `proven-native-partial` | users/groups endpoints and Preview Access endpoints return `200`; one group has zero members; users have no groups | no inside/outside actor proof; no synthetic group grants | get approval to create/use test actors and a `Team-Stage2-Proof` group |
| Workspace Models | Curated model over safe base model, system instructions, group visibility | admin API proven | no actor | no actor | no actor | `proven-native-partial` | models endpoint returns 4 models; `models_with_access_control=0` | no restricted scenario model exists | create one synthetic restricted Workspace Model after approval |
| Shared Prompts | Prompt with variables, slash visibility, group sharing, version history | endpoint proven | no actor | no actor | no actor | `proven-native-partial` | prompts endpoint returns `200`, `prompts_total=0` | no prompt exists; no slash visibility proof | create one synthetic prompt after approval |
| Knowledge | Synthetic knowledge item, model binding, retrieval, group access | endpoint proven | no actor | no actor | no actor | `proven-native-partial` | knowledge endpoint returns `200`, `knowledge_total=0`; files endpoint returns 40 files | no synthetic knowledge/retrieval proof | upload synthetic TXT/PDF only after approval |
| Analytics / usage / costs | User/model usage visibility | admin API proven | no actor | no actor | no actor | `proven-native-partial` | analytics models count 3; analytics users count 4; item keys include token counts | no fresh two-user synthetic usage; no export/cost proof | generate minimal usage with test actors after approval |
| Web Search permissions | Feature permission, model capability, per-chat toggle, browser exposure | default config proven | no actor | no actor | no actor | `proven-native-partial` | default `features.web_search=True`; public config secret scan found no key/token markers | no group allow/outside deny proof; no safe query run | restrict by test group and run safe query matrix after approval |
| Chat deletion / no-delete | Non-admin UI delete, API delete, admin override | default config proven | no actor | no actor | no actor | `proven-native-partial` | default `chat.delete=True`, `chat.delete_message=True` | current default is not no-delete; non-admin UI/API not tested | customer retention policy plus test actor proof required |
| Manager visibility | Manager sees only approved shared work resource, not personal/draft chat | preview endpoint proven | no actor | no actor | no actor | `not-proven` | Preview Access endpoints work, but no manager actor or shared work resource exists | supervisory policy and actor proof missing | do not use blanket admin; create explicit shared test resource after policy approval |
| File upload / documents | Synthetic TXT/PDF/DOCX/XLSX upload and extraction | default config proven | no actor | no actor | no actor | `proven-native-partial` | default `chat.file_upload=True`, `chat.web_upload=True`; files endpoint returns 40 | no synthetic upload/extraction proof | use synthetic files only after approval |
| Native STT vs sidecar | Native microphone settings inventory vs Stage 2 media attachment sidecar | endpoint proven | no actor | no actor | no actor | `proven-native-partial` | audio config endpoint has `stt` object; default `chat.stt=True`; Stage 2 loader/config served | no mobile microphone retest; no UI screenshot | inventory UI labels in operator session; do not reopen sidecar architecture |

## Capability Results

### Groups / RBAC

Verdict: `proven-native-partial`

What is known:

- repo docs require Stage 2 group/model visibility proof;
- official OpenWebUI docs describe Admin Panel group management, default
  permissions, additive permission merging and resource access grants;
- official docs explicitly make deny-style permissions unavailable;
- authenticated users/groups endpoints work;
- authenticated Preview Access endpoints work for user and group views;
- runtime default permissions were captured;
- current stand has 4 users, 1 group, no users with groups, and no
  `stage2-proof-*` actors.

What is not proven:

- exact screenshot/UI labels from Admin Panel;
- whether an ordinary user can regain access through another global/group path;
- inside/outside group behavior with synthetic actors.

### Workspace Models / Scenario Model

Verdict: `proven-native-partial`

What is known:

- native-first scenario assembly remains the preferred path;
- unauthenticated `/api/models` is protected;
- authenticated models endpoint returns 4 models;
- no model currently has `access_control` populated.

What is not proven:

- group-restricted curated model visibility;
- hidden/raw provider model behavior;
- exact settings for system instructions, knowledge attachment and capabilities
  on the deployed UI.

### Shared Prompts / Templates

Verdict: `proven-native-partial`

What is known:

- official docs describe `/command` prompts, variables, access control and
  version history;
- authenticated prompts endpoint works;
- `prompts_total=0` on the current stand.

What is not proven:

- deployed slash-menu visibility for inside/outside actors;
- group sharing behavior;
- rollback/version history behavior on `0.9.6`.

### Knowledge

Verdict: `proven-native-partial`, with customer-document work
still `blocked-by-test-data`

What is known:

- native Knowledge/RAG can be useful for instructions, methodics, templates and
  synthetic examples;
- authenticated knowledge endpoint works;
- `knowledge_total=0`;
- authenticated files endpoint works and returns `files_total=40`.

What is not proven:

- safe synthetic TXT/PDF upload;
- Knowledge access grants;
- retrieval behavior;
- PDF/DOCX/XLSX extraction quality;
- OCR/scanned document behavior.

### Analytics / Usage / Cost Visibility

Verdict: `proven-native-partial`

What is known:

- official docs describe admin Analytics with group filtering;
- PRD-1 keeps hard billing/gateway optional unless native analytics is
  insufficient;
- authenticated analytics models endpoint works and returns 3 model rows;
- authenticated analytics users endpoint works and returns 4 user rows with
  token-count fields.

What is not proven:

- token/message visibility after two test users generate usage;
- cost/export availability;
- whether native analytics is enough for first-stage cost visibility.

### Web Search Permissions

Verdict: `proven-native-partial` for default feature permission; provider
baselines remain separate prior evidence.

What is known:

- prior Stage 2 reports record Brave/Yandex/SearXNG baseline status;
- rollout gates remain open;
- PRD-1 forbids exposing provider keys and requires group/scope/cost policy;
- default `features.web_search=True` on the current runtime;
- public config exposure check did not detect `api_key`, `token`, `bearer`,
  `authorization`, `sk-`, `AKIA` or private-key markers.

What is not proven:

- group permission behavior for Web Search;
- ordinary user toggle visibility;
- outside-user restriction;
- logging behavior for safe queries.

### Chat Deletion / No-Delete

Verdict: `proven-native-partial`, `needs-customer-decision`

What is known:

- official permission categories include chat delete-related permissions;
- repo acceptance requires non-admin UI/API delete proof and admin override
  documentation;
- current runtime default has `chat.delete=True` and `chat.delete_message=True`.

What is not proven:

- deployed non-admin UI delete behavior;
- deployed API delete behavior;
- whether native no-delete is sufficient;
- retention/audit/archive policy.

### Manager Visibility

Verdict: `not-proven`, `needs-customer-decision`

What is known:

- native groups/sharing may help with explicit work resources;
- repo docs prohibit treating blanket admin access as manager visibility;
- Preview Access endpoints work, but no manager actor or explicit shared work
  resource exists.

What is not proven:

- manager can see only approved work chats/resources;
- unrelated personal/draft chats remain hidden;
- audit/export behavior for manager access.

### File Upload / Documents

Verdict: `proven-native-partial` for default file permissions,
`blocked-by-test-data` for customer documents/OCR/Excel.

What is known:

- PRD-1 distinguishes chat file upload from a corporate document pipeline;
- current runtime default has `chat.file_upload=True` and `chat.web_upload=True`;
- authenticated files endpoint works.

What is not proven:

- synthetic TXT/PDF/DOCX/XLSX upload behavior on deployed instance;
- extraction/retrieval quality;
- OCR/layout-heavy behavior;
- broker report acceptance.

### STT Native vs Stage 2 Sidecar

Verdict: Stage 2 media attachment sidecar remains current-stage path; native STT
settings are `proven-native-partial` through admin API.

What is known:

- public Stage 2 static STT loader and normalization config are served;
- prior Stage 2 STT MVP evidence remains current-stage closed;
- official docs describe local, browser and remote STT options;
- authenticated audio config endpoint exposes `stt` and `tts` config objects;
- current runtime default has `chat.stt=True`.

What is not proven:

- screenshot/UI labels for Admin Audio/STT settings;
- mobile microphone issue status;
- any native-STT replacement for media attachment transcription.

## Operator Checklist For Authenticated Proof

Use this checklist only with approved test accounts and synthetic data.

### 1. Prepare Actors

Create or identify these accounts:

| Actor | Suggested label | Required membership |
| --- | --- | --- |
| Admin | `stage2-proof-admin` | admin role |
| Manager/РО | `stage2-proof-manager` | manager test group only; no admin |
| Employee inside group | `stage2-proof-inside` | business sharing group and required permission groups |
| Employee outside group | `stage2-proof-outside` | no membership in the tested groups |

Do not include real employee names, emails, tokens or cookies in evidence.

### 2. Prepare Groups

Create or identify:

- one permission group, for example `P-Stage2-WebSearch`;
- one permission group, for example `P-Stage2-FileUpload`;
- one business/sharing group, for example `Team-Stage2-Proof`;
- one negative-control group or outside user with no grants.

For each group capture:

- display name;
- purpose;
- members;
- `Who can share to this group` / access-control setting;
- enabled permissions;
- whether the group is permission-only or sharing/business.

### 3. Groups / RBAC Proof

Open:

- `Admin Panel > Users > Groups`;
- `Admin Panel > Users > Groups > Default Permissions`;
- group editor;
- user/group access preview if available.

Record:

- exact setting labels for default permissions;
- exact setting labels for group permissions;
- whether effective permissions are additive;
- whether a deny control exists;
- user preview for `stage2-proof-inside`;
- user preview for `stage2-proof-outside`;
- group preview for `Team-Stage2-Proof`.

Expected safe conclusion:

- `proven-native-with-configuration` only if inside user gains the intended
  grants and outside user does not regain them through defaults or another
  group.

### 4. Workspace Model Proof

Create one synthetic model:

- base model: existing safe deployed chat model;
- model name: `Stage2 Proof Scenario`;
- description: synthetic proof only;
- system instructions: synthetic short instruction;
- access: restricted to `Team-Stage2-Proof`;
- capabilities: only required features for the test.

Check:

- Admin sees and edits the model;
- inside employee sees the curated model;
- outside employee does not see it;
- raw/base model exposure is recorded separately;
- access does not appear through another group/global path.

### 5. Shared Prompt Proof

Create one synthetic prompt:

- command: `/stage2_proof_summary`;
- variables: one text variable and one date/context variable;
- access: `Team-Stage2-Proof`;
- commit message: `initial synthetic proof`.

Check:

- inside employee sees slash command;
- outside employee does not see slash command;
- version history appears after one edit;
- rollback or "set production" behavior is captured if available.

### 6. Knowledge Proof

Create one synthetic Knowledge item:

- file: artificial TXT or simple generated PDF;
- no real customer data;
- access: `Team-Stage2-Proof`;
- attach to `Stage2 Proof Scenario` model if the UI supports it.

Check:

- inside employee can retrieve/reference it;
- outside employee cannot access it;
- model uses only attached/allowed knowledge;
- retrieval output does not leak unrelated data.

### 7. Analytics Proof

Generate minimal usage:

- inside employee sends one short synthetic prompt through the test model;
- outside employee sends one short synthetic prompt through any allowed baseline
  model, if permitted;
- manager actor does not need admin access unless explicitly approved.

Open admin Analytics and capture:

- time filter;
- group filter;
- user breakdown;
- model breakdown;
- message/token metrics;
- cost estimate if available;
- export if available.

Conclusion options:

- `proven-native-partial` if dashboards show basic usage but no hard budgets;
- `needs-custom-slice` only if native analytics cannot satisfy the approved
  first-stage reporting requirement.

### 8. Web Search Permission Proof

Do not run a broad rollout.

Use only safe queries:

- `OpenWebUI release notes`;
- `Российские праздники 2026 официальный календарь`;
- `weather API documentation example` only if external freshness is allowed.

Check:

- where Web Search is enabled globally;
- whether Web Search permission appears under feature permissions;
- whether it can be granted by permission group;
- whether model capability and per-chat toggle are visible;
- inside employee can use it only when approved;
- outside employee cannot use it;
- provider keys are absent from browser config, localStorage/sessionStorage and
  network responses;
- logs/screenshots omit raw sensitive data.

### 9. Chat Deletion / No-Delete Proof

With non-admin employee:

- create a test chat;
- attempt UI delete;
- if approved, attempt API delete using an approved authenticated test route;
- record result and error text without token/cookie capture.

With Admin:

- record override behavior;
- do not change production retention policy.

Conclusion options:

- `proven-native-with-configuration` only if the non-admin delete path is
  blocked through native settings and admin override is understood;
- `needs-custom-slice` if native permission cannot enforce approved no-delete
  behavior.

### 10. Manager Visibility Proof

Create an explicitly shared work-scenario resource:

- one test chat/resource shared to `Team-Stage2-Proof`;
- one unrelated personal/draft chat created by inside employee;
- one resource outside manager scope.

Check:

- Manager/РО can see only the approved work resource;
- Manager/РО cannot see unrelated personal/draft chat;
- outside employee cannot see manager-only or team-only resources;
- admin can audit the grants without treating manager as admin.

### 11. File Upload / Documents Proof

Use only synthetic files:

- simple TXT;
- simple PDF;
- simple DOCX;
- simple XLSX.

Check:

- upload acceptance;
- visible extraction/retrieval behavior;
- file size/type limits shown in UI;
- retrieval accuracy at a basic level;
- no conclusions about OCR, scans, broker reports or complex Excel.

### 12. Native STT Settings Inventory

Inventory only:

- Admin audio/STT provider area;
- user microphone setting if visible;
- whether browser STT is available;
- whether remote provider settings would require keys.

Do not change Stage 2 media attachment architecture. The current sidecar path
remains the accepted path for audio/video attachments.

### 13. Evidence Handling

Allowed evidence:

- screenshots with redacted usernames/emails if needed;
- exact non-secret setting labels;
- actor matrix;
- visible success/failure states;
- timestamp and deployed version.

Forbidden evidence:

- admin tokens;
- cookies;
- provider keys;
- `.env` contents;
- private URLs;
- real customer data;
- raw sensitive Web Search queries;
- raw uploaded customer documents.

## Gaps

- No screenshot-based Admin UI proof; this run is admin API-backed.
- No four-actor access matrix.
- No existing `stage2-proof-*` actors or groups.
- No approval was given to create synthetic users/groups/resources on the
  deployed stand.
- No inside/outside group visibility proof.
- No group-restricted Workspace Model proof.
- No prompt creation, slash visibility or version-history proof.
- No synthetic Knowledge upload/retrieval proof.
- No fresh two-user analytics sample.
- No Web Search safe-query permission proof.
- No no-delete UI/API proof with non-admin actor.
- No manager visibility proof with explicit work resource and unrelated
  personal/draft negative control.
- No synthetic file upload/extraction proof.
- No browser/mobile native microphone retest.

## Risks

- Treating admin API proof as full four-actor UI proof.
- Treating upstream documentation as deployed behavior.
- Granting Manager/РО admin access and calling it manager visibility.
- Testing Web Search with sensitive queries.
- Exposing provider keys through screenshots, browser storage or network logs.
- Promising OCR/XLSX/broker report quality without customer samples.
- Reopening STT architecture despite the current-stage sidecar closure.
- Starting LiteLLM/gateway before native analytics proof and customer decision.

## Recommendations

1. Run the authenticated proof as a controlled operator session, not as a
   production rollout.
2. Use four actors and one synthetic business group.
3. Keep permission groups separate from sharing/business groups.
4. Start from minimal global defaults and explicit group grants.
5. Capture exact setting labels and access-preview evidence.
6. Treat Web Search as permission proof only; no broad user rollout.
7. Treat documents as synthetic upload proof only; no customer OCR conclusion.
8. Keep STT sidecar architecture closed; inventory native microphone/STT only.
9. Run the remaining actor/resource proof only after explicit approval to
   create or use synthetic test accounts on the deployed stand.

## What Can Move Without Customer Approval

- Prepare synthetic users/groups checklist for operator review.
- Prepare synthetic TXT/PDF/DOCX/XLSX files.
- Prepare screenshots checklist and redaction rules.
- Prepare scenario model/prompt/knowledge names and expected access matrix.
- Prepare Web Search safe-query and forbidden-query examples.
- Prepare analytics worksheet for user/model/group metrics.
- Keep Stage 2 docs and gates updated with the partial proof status.

## What Needs Customer Approval

- Real group/department matrix.
- Manager/РО visibility policy.
- Retention/no-delete/audit policy.
- Customer document and broker-report samples.
- Provider/data policy by provider class.
- Web Search rollout scope, logging, retention and cost policy.
- Any production user impact.
- Any custom delete guard, manager visibility customization, gateway or deep
  fork.

## Final Verdict

`admin_test_user_runtime_proof_partial`

The follow-up run proved that the local workspace `.env` contains the approved
admin credential variable names, credential values were not printed, and
authenticated OpenWebUI admin API access works on the deployed `0.9.6`
instance.

Native capabilities are partially proven at the admin surface level:

- default permissions are readable;
- users/groups/models/prompts/knowledge/files/functions/audio config endpoints
  are reachable;
- analytics endpoints return model/user usage aggregates;
- Preview Access endpoints work;
- Web Search, file upload, chat delete and STT default permission switches are
  visible through config.

Gate 7 is not fully closed because the four-actor behavior matrix was not run.
The stand has no `stage2-proof-*` users/groups, users currently have no groups,
and this run did not create synthetic users, groups, models, prompts, knowledge
or files without explicit operator approval for those state-changing actions.
