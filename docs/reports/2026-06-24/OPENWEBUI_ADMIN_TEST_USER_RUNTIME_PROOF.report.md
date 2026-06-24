# OpenWebUI Admin/Test-User Runtime Proof

Date: 2026-06-24

Repository: `Kwentin3/corp-openweb-ui`

Scope: Stage 2 / PRD-1 native OpenWebUI capabilities, Admin/Test-User proof
matrix.

Verdict: `admin_test_user_runtime_proof_blocked_by_access`

## Executive Summary

Admin/test-user runtime proof was not completed in this run because no
approved admin/staging credentials or pre-created test actors were available.
No attempt was made to read `.env`, recover credentials, inspect cookies,
extract tokens or create users/groups without operator approval.

The only runtime checks performed were safe unauthenticated access checks on
the already documented deployed OpenWebUI surface:

- public deployed version is still `0.9.6`;
- public health endpoint responds;
- unauthenticated `/api/models` remains protected with `401 Unauthorized`;
- Stage 2 STT static loader is served;
- Stage 2 STT normalization config is served.

This means the previous native-first conclusion is unchanged, but the required
Admin/Test-User matrix is still not proven. The next step is an operator-run or
operator-approved authenticated proof with four actors: Admin, Manager/РО,
Employee inside group and Employee outside group.

## Runtime Access Status

Status: `blocked_by_admin_or_staging_access`

Available:

- repository working tree;
- public unauthenticated runtime endpoints;
- official OpenWebUI documentation;
- repo Stage 2 PRD, gates, backlog, acceptance and prior runtime reports.

Not available:

- admin session;
- staging/test-user credentials;
- approved permission to create users/groups on the deployed instance;
- approved customer test documents;
- approved Web Search rollout scope.

Hard limits observed:

- no real `.env` was read;
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

Local Docker:

```text
docker ps --format ...
NAMES IMAGE STATUS PORTS
```

No local containers were running, so no local Admin UI proof was possible.

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

The deployed host URL is intentionally omitted from this report. The checks
above prove only public reachability and public/static behavior. They do not
prove Admin UI settings, user visibility, group grants, analytics, file upload
or Web Search permissions.

## Actors Used

No authenticated actors were used.

Required actors for the next proof:

| Actor | Purpose | Required constraints |
| --- | --- | --- |
| Admin | Configure users, groups, defaults, resource access and analytics proof | Use approved admin account only; do not export tokens/cookies |
| Manager/РО | Validate manager visibility and approved work-scenario scope | Must not receive blanket admin access |
| Employee inside group | Validate allowed scenario, model, prompt, knowledge and feature visibility | Member of test business/sharing group and needed permission groups |
| Employee outside group | Validate negative access proof | Must not belong to any group that grants the tested resources |

## Test Data Used

Runtime test data was not created because authenticated proof was blocked.

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
| Groups / RBAC | Default permissions, group grants, additive union, no deny | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | no admin session; official docs say permissions are additive and deny is absent | effective deployed settings unknown | run Admin Panel > Users > Groups > Default Permissions and group editor proof |
| Workspace Models | Curated model over safe base model, system instructions, group visibility | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | public `/api/models` is protected without auth | allowed/outside visibility unknown | create one test Workspace Model and validate access from both employee actors |
| Shared Prompts | Prompt with variables, slash visibility, group sharing, version history | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | official docs describe Workspace > Prompts, access control and version history | deployed UI behavior unknown | create one synthetic prompt and verify slash menu visibility |
| Knowledge | Synthetic knowledge item, model binding, retrieval, group access | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | official docs support Workspace Knowledge/RAG; no local proof | retrieval/access quality unknown | upload safe TXT/PDF and prove inside/outside group behavior |
| Analytics / usage / costs | User, model, group filter, tokens/messages, export/cost estimate | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | official docs describe admin Analytics and group filtering | deployed analytics sufficiency unknown | generate minimal sample usage by two test users and capture dashboard |
| Web Search permissions | Feature permission, model capability, per-chat toggle, browser exposure | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | previous provider baselines exist; no permission proof in this run | rollout permission/cost/logging proof pending | use safe query matrix only; do not roll out broadly |
| Chat deletion / no-delete | Non-admin UI delete, API delete, admin override | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | official permissions include Delete Chat/Delete Message categories; deployed behavior unknown | native no-delete not proven | test with non-admin chat before custom slice decisions |
| Manager visibility | Manager sees only approved shared work resource, not personal/draft chat | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | no authenticated manager actor | supervisory model not proven | prove explicit group-sharing scenario; do not use blanket admin access |
| File upload / documents | Synthetic TXT/PDF/DOCX/XLSX upload and extraction | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | no authenticated chat/file upload access | extraction and OCR quality unknown | test only synthetic files; customer samples remain separate gate |
| Native STT vs sidecar | Native microphone settings inventory vs Stage 2 media attachment sidecar | not tested | not tested | not tested | not tested | `blocked-by-runtime-access` | public Stage 2 STT loader and normalization config are served | Admin Audio settings not inspected | inventory native STT settings only; do not reopen sidecar architecture |

## Capability Results

### Groups / RBAC

Verdict: `not-proven`, `blocked-by-runtime-access`

What is known:

- repo docs require Stage 2 group/model visibility proof;
- official OpenWebUI docs describe Admin Panel group management, default
  permissions, additive permission merging and resource access grants;
- official docs explicitly make deny-style permissions unavailable.

What is not proven:

- current deployed default permissions;
- exact group editor labels on deployed `0.9.6`;
- whether an ordinary user can regain access through another global/group path;
- effective user/group access preview on the deployed instance.

### Workspace Models / Scenario Model

Verdict: `not-proven`, `blocked-by-runtime-access`

What is known:

- native-first scenario assembly remains the preferred path;
- unauthenticated `/api/models` is protected.

What is not proven:

- group-restricted curated model visibility;
- hidden/raw provider model behavior;
- exact settings for system instructions, knowledge attachment and capabilities
  on the deployed UI.

### Shared Prompts / Templates

Verdict: `not-proven`, `blocked-by-runtime-access`

What is known:

- official docs describe `/command` prompts, variables, access control and
  version history.

What is not proven:

- deployed slash-menu visibility for inside/outside actors;
- group sharing behavior;
- rollback/version history behavior on `0.9.6`.

### Knowledge

Verdict: `not-proven`, `blocked-by-runtime-access`, with customer-document work
still `blocked-by-test-data`

What is known:

- native Knowledge/RAG can be useful for instructions, methodics, templates and
  synthetic examples.

What is not proven:

- safe synthetic TXT/PDF upload;
- Knowledge access grants;
- retrieval behavior;
- PDF/DOCX/XLSX extraction quality;
- OCR/scanned document behavior.

### Analytics / Usage / Cost Visibility

Verdict: `not-proven`, `blocked-by-runtime-access`

What is known:

- official docs describe admin Analytics with group filtering;
- PRD-1 keeps hard billing/gateway optional unless native analytics is
  insufficient.

What is not proven:

- user/model/group breakdown on deployed `0.9.6`;
- token/message visibility after two test users generate usage;
- cost/export availability;
- whether native analytics is enough for first-stage cost visibility.

### Web Search Permissions

Verdict: `not-proven` for permissions; provider baselines remain separate prior
evidence.

What is known:

- prior Stage 2 reports record Brave/Yandex/SearXNG baseline status;
- rollout gates remain open;
- PRD-1 forbids exposing provider keys and requires group/scope/cost policy.

What is not proven:

- group permission behavior for Web Search;
- ordinary user toggle visibility;
- outside-user restriction;
- browser config/network exposure check in this run;
- logging behavior for safe queries.

### Chat Deletion / No-Delete

Verdict: `not-proven`, `needs-customer-decision`

What is known:

- official permission categories include chat delete-related permissions;
- repo acceptance requires non-admin UI/API delete proof and admin override
  documentation.

What is not proven:

- deployed non-admin UI delete behavior;
- deployed API delete behavior;
- whether native no-delete is sufficient;
- retention/audit/archive policy.

### Manager Visibility

Verdict: `not-proven`, `needs-customer-decision`

What is known:

- native groups/sharing may help with explicit work resources;
- repo docs prohibit treating blanket admin access as manager visibility.

What is not proven:

- manager can see only approved work chats/resources;
- unrelated personal/draft chats remain hidden;
- audit/export behavior for manager access.

### File Upload / Documents

Verdict: `not-proven` for synthetic upload, `blocked-by-test-data` for customer
documents/OCR/Excel.

What is known:

- PRD-1 distinguishes chat file upload from a corporate document pipeline.

What is not proven:

- synthetic TXT/PDF/DOCX/XLSX upload behavior on deployed instance;
- extraction/retrieval quality;
- OCR/layout-heavy behavior;
- broker report acceptance.

### STT Native vs Stage 2 Sidecar

Verdict: Stage 2 media attachment sidecar remains current-stage path; native STT
settings are `not-proven` in Admin UI for this run.

What is known:

- public Stage 2 static STT loader and normalization config are served;
- prior Stage 2 STT MVP evidence remains current-stage closed;
- official docs describe local, browser and remote STT options.

What is not proven:

- deployed Admin Audio/STT settings;
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

- No authenticated Admin UI proof.
- No four-actor access matrix.
- No exact deployed setting names.
- No user/group/model visibility proof.
- No prompts/knowledge sharing proof.
- No native analytics proof.
- No Web Search permission proof.
- No no-delete UI/API proof.
- No manager visibility proof.
- No synthetic file upload/extraction proof.
- No native STT settings inventory.

## Risks

- Treating public version/health proof as Admin UI proof.
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
9. Update `OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md` only after real authenticated
   proof is captured.

## What Can Move Without Customer Approval

- Prepare synthetic users/groups checklist for operator review.
- Prepare synthetic TXT/PDF/DOCX/XLSX files.
- Prepare screenshots checklist and redaction rules.
- Prepare scenario model/prompt/knowledge names and expected access matrix.
- Prepare Web Search safe-query and forbidden-query examples.
- Prepare analytics worksheet for user/model/group metrics.
- Keep Stage 2 docs and gates updated with the blocked proof status.

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

`admin_test_user_runtime_proof_blocked_by_access`

The current run did not prove Admin/Test-User native capability behavior. It
confirmed only that the deployed OpenWebUI public surface is still reachable on
version `0.9.6`, unauthenticated model access is protected and Stage 2 STT
static assets are served.

Gate 7 remains open. The next evidence-bearing step is an approved
authenticated operator proof using the actor matrix and checklist above.
