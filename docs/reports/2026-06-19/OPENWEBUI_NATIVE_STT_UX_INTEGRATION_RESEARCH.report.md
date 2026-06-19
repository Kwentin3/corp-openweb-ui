# OpenWebUI-native STT UX Integration Research

Date: 2026-06-19
Status: research / docs refine only
Verdict: `needs_runtime_probe`

## 1. Summary

Stage 2 STT must be OpenWebUI-native from the user's perspective.

The implemented `services/stage2-stt` sidecar remains a backend/domain service:
provider keys, provider adapters, normalization, limits, storage, usage and
cancel semantics stay server-side. Users must not open a separate STT portal,
upload media there, copy a transcript and return to OpenWebUI manually.

Recommended MVP path: prove an OpenWebUI Action Function that appears as a
user-triggered chat/workspace action, receives OpenWebUI user/file context,
calls the Stage 2 sidecar, emits status, and returns transcript into OpenWebUI.

Recommended production path: keep the sidecar as an OpenAPI-described backend
service, with Action Function or Global OpenAPI Tool Server wiring selected
after runtime proof. Avoid Pipelines, separate STT GUI and deep OpenWebUI fork
unless native mechanisms fail in a documented probe.

## 2. Baseline

Already implemented:

- sidecar service/package: `services/stage2-stt` / `stage2_stt`;
- endpoint: `GET /stage2-api/transcription/capabilities`;
- provider adapter factory;
- first adapter: `LemonfoxSttAdapter`;
- env/config contract;
- output profiles;
- storage modes;
- validation;
- cancel model.

Current blockers from the routing/auth audit still apply:

- OpenWebUI session/current-user propagation to the sidecar is not proven;
- production auth middleware/identity boundary is not selected;
- authenticated job routes must not start before auth and UX route are proven.

## 3. Product constraint

Required rule:

```text
Stage2 STT must be OpenWebUI-native from the user's perspective.
The sidecar is a backend/domain service, not a separate user-facing GUI.
Users must start and consume transcription from inside OpenWebUI chat/workspace UX.
```

Rejected UX:

- user opens a separate STT app;
- uploads audio/video outside OpenWebUI;
- copies transcript manually;
- returns to OpenWebUI.

Accepted UX:

- user attaches or selects audio/video in OpenWebUI;
- user triggers transcription through an OpenWebUI action/tool/button/model
  workflow;
- OpenWebUI calls Stage 2 STT backend;
- transcript returns to chat/message/file/artifact/knowledge flow inside
  OpenWebUI.

## 4. OpenWebUI extension mechanisms reviewed

Primary OpenWebUI docs reviewed:

- Extensibility:
  `https://docs.openwebui.com/features/extensibility/`
- Tools:
  `https://docs.openwebui.com/features/extensibility/plugin/tools/`
- OpenAPI Tool Servers:
  `https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/`
- Open WebUI integration for OpenAPI Tool Servers:
  `https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui/`
- Action Function:
  `https://docs.openwebui.com/features/extensibility/plugin/functions/action/`
- Events:
  `https://docs.openwebui.com/features/extensibility/plugin/development/events/`
- Reserved arguments / file metadata:
  `https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/`
- MCP:
  `https://docs.openwebui.com/features/extensibility/mcp/`
- API endpoints / file upload:
  `https://docs.openwebui.com/reference/api-endpoints/`
- Workspace Models:
  `https://docs.openwebui.com/features/workspace/models/`
- RBAC permissions and groups:
  `https://docs.openwebui.com/features/authentication-access/rbac/permissions/`
  and `https://docs.openwebui.com/features/authentication-access/rbac/groups/`

Useful OpenWebUI facts:

- Extensibility has two main layers: in-process Python Tools/Functions and
  external HTTP OpenAPI/MCP servers.
- Pipelines are legacy and not recommended for new work.
- Action Functions are user-triggered per-message operations.
- OpenAPI/MCP servers are suitable for external sidecar services.
- Tools and Functions execute arbitrary Python inside OpenWebUI and must be
  admin-installed/audited.
- OpenAPI Tool Servers can be registered as User Tool Servers or Global Tool
  Servers. Global tool calls originate from the OpenWebUI backend and are hidden
  until explicitly enabled by users/admins.
- OpenAPI/MCP custom headers can include server-expanded user/chat/message
  tokens such as `{{USER_ID}}`, `{{USER_EMAIL}}`, `{{USER_ROLE}}`, `{{CHAT_ID}}`
  and `{{MESSAGE_ID}}`.
- External OpenAPI/MCP tools can emit OpenWebUI events only with forwarded
  chat/message headers and their own OpenWebUI API key or session token.
- OpenWebUI file upload API exists, but native file processing is primarily a
  RAG/Knowledge path and is asynchronous.
- The reserved-arguments file details are useful but still need runtime proof on
  the pinned deployment before they become a sidecar contract.

## 5. Option comparison

| Option | MVP fit | Production fit | UX quality | Fork risk | Auth/file complexity | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| A. OpenAPI Tool Server | Medium | Good | Medium | Low | Medium/high | Not primary MVP until file handoff/events are proven; good production candidate |
| B. Action Function | Good | Medium/good | Good | Low | Medium | Recommended MVP probe |
| C. Tool/Function inside OpenWebUI | Medium | Medium | Medium | Low | Medium | Useful helper, but risky as LLM-invoked rather than deliberate user action |
| D. Minimal frontend patch | Medium | Medium | Best if small | Medium | Medium | Fallback only if native Action/OpenAPI mechanisms are insufficient |
| E. Existing file upload/file manager flow | Partial | Partial | Good as input source | Low | High if sidecar reads internals | Use as file source, not as a sidecar storage contract |
| F. Pipeline/MCP | Weak/medium | Medium | Agent/tool oriented | Low | Medium | MCP is possible; Pipelines are not recommended |

### Option A. OpenAPI Tool Server

This aligns well with the sidecar boundary: the sidecar can publish an OpenAPI
schema and stay outside OpenWebUI process. Global Tool Server mode keeps calls
server-side from OpenWebUI backend.

Not enough for primary MVP yet because the exact user-triggered file/audio flow
must be proven on the pinned deployment. OpenAPI tools are exposed as model/tool
capabilities, not necessarily the cleanest "user clicked transcribe this file"
interaction. Progress requires the external-events contract, forwarded
chat/message headers and a service/admin OpenWebUI API key.

Answer: OpenAPI Tool Server can become the production sidecar contract and can
be MVP only after runtime proof of file handoff, transcript return, events and
access control.

### Option B. OpenWebUI Action Function

Action Function is the best MVP candidate because the UX is explicitly
user-triggered inside OpenWebUI. It can access reserved context such as user,
metadata, files and event emitters, then call the sidecar as a backend service.

Tradeoff: Action code is arbitrary Python running in OpenWebUI. It must be
admin-installed, reviewed and not editable by regular workspace users. The
Action should remain a thin integration shim and must not duplicate STT domain
logic.

Answer: Action Function is better than a generic Tool for deliberate
user-triggered transcription, provided runtime probe confirms file metadata and
event behavior on the pinned version.

### Option C. Tool / Function inside OpenWebUI

A Tool can call the sidecar, but Tools are model-callable capabilities. That is
good when a curated "Meeting Summarizer" model may decide to invoke
transcription, but weaker for a deliberate user action over an uploaded file.

Use this only as a helper or curated model binding after the Action path is
understood. Do not let STT drift into an implicit agent tool when the desired
product behavior is "user chooses transcribe".

### Option D. Minimal OpenWebUI frontend patch

A small patch could give the best UX: explicit file action, upload/progress,
cancel and transcript placement. It also creates fork/update cost.

Keep this as a fallback only if Actions/OpenAPI cannot provide file access,
status/cancel and result placement with acceptable UX. If needed, the patch must
be thin: it calls sidecar contracts and owns no provider keys, policy, retention
or Lemonfox behavior.

### Option E. Existing file upload / file manager flow

Native file attachment/upload is a good source for audio/video selection.
However, the sidecar must not depend on OpenWebUI's private upload directory or
database layout as an unversioned contract.

For MVP, an Action should copy/stream the selected uploaded file or prepared
audio to the sidecar through an explicit sidecar API. If browser ffmpeg
preprocessing is required, the approved path still needs a runtime decision:
browser/OpenWebUI UI, Action-mediated backend preprocessing, or sidecar
preprocessing.

### Option F. Pipeline/MCP path

Pipelines are legacy and should not be selected. MCP is relevant as an external
tool protocol and supports custom header tokens, but it does not improve the
user-triggered file transcription UX over Action/OpenAPI for this slice.

## 6. Recommended MVP path

MVP path:

```text
OpenWebUI Action Function
  -> receives user/file/chat context from OpenWebUI
  -> calls Stage2 STT sidecar internal API
  -> emits OpenWebUI status/progress events
  -> returns transcript to OpenWebUI message/file/artifact UX
```

MVP rules:

- Action is a thin OpenWebUI-native wrapper, not the STT engine.
- Sidecar remains backend-only.
- Provider keys stay only in sidecar env/secrets.
- Action passes authenticated user/context to the sidecar through an approved
  internal contract.
- Action uses OpenWebUI events for status where available.
- No separate STT user GUI.
- If Action cannot handle files cleanly on the pinned version, stop and fall
  back to OpenAPI runtime probe or a minimal frontend patch decision.

Transcript return priority for MVP:

1. chat/message output inside the current OpenWebUI conversation;
2. optional transcript file/artifact attachment for long transcripts;
3. Knowledge/document ingestion only if the user explicitly wants persistent
   searchable material;
4. copied text is a fallback, not the planned workflow.

## 7. Recommended production path

Production path:

- sidecar publishes explicit OpenAPI schema for capabilities, job creation,
  status/result and cancel;
- OpenWebUI integration uses either:
  - Action Function as the deliberate user-trigger wrapper; or
  - Global OpenAPI Tool Server if runtime proof shows good user trigger, file
    handoff, progress and result UX;
- curated Workspace Model can bind tools/actions for a "Meeting Transcription"
  scenario;
- auth boundary follows the prior routing/auth audit: no public unauthenticated
  sidecar job routes, no forged user headers, no browser provider keys;
- minimal frontend patch remains a fallback only after native mechanisms fail.

## 8. Files/upload handling

Recommended handling:

- user selects or uploads audio/video in OpenWebUI;
- MVP Action probe inspects what OpenWebUI passes in `__files__`,
  `body["files"]` and `__metadata__["files"]`;
- Action must not expose provider keys or raw OpenWebUI storage internals to the
  browser;
- sidecar should receive an explicit upload/multipart stream or a signed,
  OpenWebUI-mediated file handoff, not a private `openwebui_data/uploads` path
  contract;
- OpenWebUI native Knowledge/RAG upload API is not the STT contract, because it
  is asynchronous text extraction/vector processing and may not fit raw
  audio/video transcription;
- final ffmpeg preprocessing location remains open until probe:
  browser/OpenWebUI UI, Action-mediated backend, or sidecar backend.

Direct browser prepared-audio upload to sidecar is acceptable only after the
auth/session boundary is selected and the route is protected. It must still feel
like an OpenWebUI action to the user.

## 9. Progress/cancel handling

MVP:

- Action uses `__event_emitter__` for status such as queued, uploading,
  processing, completed, failed and cancelled;
- sidecar exposes job status and cancel APIs;
- Action polls/subscribes as needed and maps sidecar states into OpenWebUI
  status messages;
- cancel must be local-safe even when provider-side cancel is unknown.

External OpenAPI/MCP path:

- events require OpenWebUI header forwarding;
- sidecar needs chat/message identifiers;
- sidecar must hold its own service/admin OpenWebUI API key to call the event
  endpoint;
- interactive event calls are less available to external tools than native
  Action callbacks.

Required UI states for any path:

- no file selected;
- unsupported media;
- too large;
- uploading/preprocessing;
- processing;
- completed;
- failed;
- cancel requested;
- cancelled.

## 10. Auth/session implications

Action MVP:

- OpenWebUI provides `__user__` and metadata to the Action;
- sidecar should receive normalized user/chat/message context from the Action;
- sidecar must authenticate the Action/internal caller and must not trust raw
  browser-supplied user headers;
- normal users must not edit Action code.

OpenAPI Tool Server:

- Global Tool Server calls come from OpenWebUI backend;
- custom headers can carry expanded user/chat/message values;
- forwarded identity headers are identification, not credentials;
- external events require a sidecar-held OpenWebUI service/admin key;
- sidecar job routes still need the routing/auth boundary selected in the
  previous audit.

Shared rule:

- no user API key should be requested from the user for STT;
- no provider key in browser, bundle, logs or OpenWebUI user-visible config.

## 11. Required sidecar contract changes

Yes, the sidecar contract should change before authenticated jobs.

Required additions:

- publish OpenAPI schema for Stage 2 STT;
- define `POST /stage2-api/transcription/jobs`;
- define `GET /stage2-api/transcription/jobs/{job_id}`;
- define `GET /stage2-api/transcription/jobs/{job_id}/result`;
- define `POST /stage2-api/transcription/jobs/{job_id}/cancel`;
- define an OpenWebUI integration request envelope with:
  - `source_context=openwebui`;
  - user id/email/role/groups when approved;
  - chat id/message id when available;
  - file reference metadata;
  - selected output profile;
  - callback/event context if external events are used;
- ensure capabilities expose enough UI-safe data for action/tool affordances:
  output profiles, size/duration limits, storage mode/health, cancel strategy
  and warnings;
- keep provider details and secrets out of OpenAPI responses.

No separate OpenWebUI-specific endpoint is required as the first contract if
`POST /stage2-api/transcription/jobs` accepts the OpenWebUI envelope. Add a
narrow Action/OpenAPI facade endpoint only if the runtime probe proves that
native OpenWebUI routing needs it; it must still map to the same job contract.

Do not add endpoints for a standalone STT web app.

## 12. Docs refined

Updated docs:

- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/CONTEXT_INDEX.md`

Main refinement: "backend sidecar" and "OpenWebUI-native user UX" are now both
explicit constraints. Authenticated job routes and final UI work are gated on
selecting/proving the OpenWebUI-native integration path.

## 13. Remaining unknowns

- Does deployed/pinned OpenWebUI `v0.9.6` expose the same Action, file metadata,
  event and header-token behavior as current docs?
- Can an Action access the uploaded audio/video bytes or only metadata?
- Can Action result placement update a message cleanly enough, or should it
  attach a transcript file/artifact?
- Should browser ffmpeg preprocessing live in a minimal frontend patch, or
  should first MVP use server/sidecar preprocessing?
- Which auth boundary will protect sidecar job routes: Authelia/ForwardAuth,
  OpenWebUI/SSO token path, or another approved proxy identity model?
- Which OpenWebUI service/admin key model is acceptable if external events are
  used?
- How will regular-user access to the Action/Tool be limited by groups/models?

## 14. Next implementation slice

Next slice should be a runtime probe, not production job routes:

1. In staging/admin OpenWebUI, create a minimal Action Function probe.
2. Upload a non-sensitive audio/video file in chat.
3. Capture what `__user__`, `__metadata__`, `body["files"]` and `__files__`
   contain.
4. Emit status events from the Action.
5. Call a dummy/internal sidecar endpoint without provider key.
6. Prove transcript return shape: appended chat message, replaced message,
   file/artifact attachment or explicit fallback.
7. Probe cancel semantics against a mocked long-running sidecar job.
8. Repeat with Global OpenAPI Tool Server only if Action file/result behavior is
   insufficient or if production strongly prefers external-only integration.
9. Update ADR-0004 and the backend implementation plan with the selected path.
10. Only then implement authenticated job routes.

## 15. Final verdict

```text
needs_runtime_probe
```

OpenWebUI docs show viable native mechanisms, and the recommended MVP direction
is clear: Action Function as a thin user-triggered wrapper over the backend
sidecar. However, file/audio access, transcript placement, events, cancel and
auth/user propagation must be proven on the pinned deployment before
authenticated STT job routes or final UI work.
