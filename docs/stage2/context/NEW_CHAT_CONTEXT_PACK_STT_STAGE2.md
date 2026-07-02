# Stage 2 / STT / OpenWebUI New Chat Context Pack

Date: 2026-06-19

Purpose: compact transfer context for a new Codex/chat session. This file is
intentionally dense, implementation-oriented and secret-free.

## 1. One-screen summary

Stage 2 STT MVP for OpenWebUI is implemented/proven for the current stage.

Canonical path:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization when needed
-> OpenWebUI process=false prepared-audio upload
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> Lemonfox adapter
-> transcript returned to OpenWebUI composer/chat UX
```

Current verdict:

```text
stt_mvp_current_stage_closed_ready_for_broader_testing
```

Do not restart architecture discovery. Future work should continue from testing,
hardening, policy and acceptance gaps.

The strategic implementation pattern is extension-first:

```text
static loader UX shim + Action Function + private sidecar + provider adapter
```

The user remains inside native OpenWebUI UX. The Stage 2 sidecar is backend-only.
There is no separate STT GUI, no browser-to-provider call and no provider key in
the browser.

## 2. What is implemented/proven

Implemented/proven for current stage:

- private `stage2-stt` backend sidecar foundation;
- sidecar job/capabilities routes;
- internal sidecar job-route auth;
- `LemonfoxSttAdapter` behind provider adapter boundary;
- Lemonfox live smoke through the sidecar path;
- OpenWebUI Action Function path;
- static loader `Transcribe` button on media attachments;
- prepared MP3 passthrough path;
- browser ffmpeg.wasm normalization path;
- self-hosted ffmpeg.wasm asset path through OpenWebUI static assets;
- MP4 video with audio proof;
- WebM audio/video proof;
- unsupported/decode-failed media safe visible error;
- no-audio media safe visible error;
- transcript returned to the current OpenWebUI composer/chat UX;
- provider keys and internal sidecar token kept out of the browser;
- no separate user-facing STT sidecar GUI.

Proof status by slice:

- backend slice: sidecar, config, provider adapter, job routes, validation,
  storage-mode decision path and tests were implemented;
- runtime slice: prepared-MP3 OpenWebUI upload -> Action -> sidecar ->
  Lemonfox -> transcript response passed;
- frontend media action slice: explicit attachment action and composer
  insertion passed;
- ffmpeg browser normalization slice: MP3 passthrough, MP4-with-audio,
  WebM audio/video, unsupported fake media and no-audio media passed.

Current browser output profile is:

```text
mp3_high_compat
```

Opus remains a candidate for production default only after provider/path proof.

## 3. Current architecture with diagram and responsibilities

```text
User in OpenWebUI chat
  |
  | attach audio/video + click Transcribe
  v
OpenWebUI static loader
  - visible action and local status
  - safe browser config
  - process=false upload interception
  - ffmpeg.wasm probe/normalization
  - typed browser errors before provider handoff
  |
  | /api/v1/files/?process=false
  | /api/chat/actions/stage2_media_transcription_action
  v
OpenWebUI Action Function
  - OpenWebUI context bridge
  - uses body.files proven path
  - reads prepared file through approved upload handoff
  - configured by valves
  - calls private sidecar with server-side internal auth
  - returns transcript content to current composer/chat UX
  |
  | private Docker/internal route
  v
stage2-stt sidecar
  - FastAPI job/capabilities routes
  - config/env parsing and validation
  - internal auth enforcement
  - prepared-audio validation
  - output-profile validation
  - storage mode auto/s3/none decision path
  - in-memory job store for MVP
  - local cancel semantics
  - provider adapter factory
  |
  v
Lemonfox adapter
  - provider request/auth server-side only
  - response parsing
  - normalized Stage 2 transcript contract
```

Responsibility boundaries:

- Browser/static loader owns visible UX affordance, browser preprocessing and
  calls to OpenWebUI-native APIs. It does not own provider keys, provider
  policy, retention or authorization.
- OpenWebUI Action owns bridge logic between OpenWebUI file/action context and
  the sidecar. It should stay thin.
- Sidecar owns backend/domain policy: auth, limits, validation, storage mode,
  job lifecycle, provider selection, provider errors and transcript
  normalization.
- Provider adapter owns provider-specific HTTP shape and response parsing.

## 4. Extension-first implementation pattern

Preferred order for OpenWebUI-facing features:

1. Native OpenWebUI configuration/workspace/model/prompt/knowledge mechanisms.
2. OpenWebUI Functions / Actions / Tools / OpenAPI Tool Servers.
3. Thin static loader or minimal UI integration patch.
4. Private backend/domain sidecar.
5. Deep OpenWebUI fork only with proof and owner/ADR approval.

STT confirms this pattern. Keep future Stage 2 features in native OpenWebUI UX
and isolate custom domain behavior behind backend contracts.

## 5. Key architectural decisions

- STT uses a server-side proxy/job boundary.
- Provider keys stay server-side only.
- Browser-to-Lemonfox is rejected.
- User-facing STT UX lives inside OpenWebUI.
- The sidecar is backend-only, not a user-facing portal.
- MVP trigger is explicit attachment `Transcribe`, not magic LLM inference.
- Lemonfox is first provider through `LemonfoxSttAdapter`, not hardwired
  architecture.
- Input compatibility is ffmpeg.wasm capability-based. MIME and extension are
  hints, not support guarantees.
- Output profile is contract/config-driven. Current browser path uses
  `mp3_high_compat`; Opus requires provider/path proof before default.
- Self-hosted ffmpeg.wasm assets are the production-default direction.
- Prepared-audio storage is controlled by storage mode `auto|s3|none`; source
  media storage is off unless explicitly enabled by policy.
- Public sidecar route is not required for the current Action path.
- OpenWebUI native microphone/Web API dictation is a separate feature path from
  the attachment-level Stage 2 `Transcribe` workflow.

## 6. Important pitfalls / do not reopen

Do not reopen as active architectural discovery:

- whether STT needs a private backend/domain sidecar;
- whether provider keys may live in browser;
- whether a separate user-facing STT GUI is needed for MVP;
- whether the OpenWebUI media attachment Action path can work;
- whether prepared MP3 passthrough is viable;
- whether browser ffmpeg.wasm normalization can work for tested MVP cases;
- whether generated MP4/WebM media can reach the Action/sidecar path.

Do not introduce:

- direct browser-to-provider calls;
- provider keys or internal sidecar token in browser config/logs/storage;
- hidden fuzzy/magic LLM trigger as the only MVP UX;
- broad OpenWebUI fork without proof;
- sidecar public host port as a shortcut;
- user-facing sidecar portal;
- claims of universal media support.

Special warning note:

- `prepared_audio_storage_transient` is not a transcription failure. Human
  alias: "At this MVP stage the prepared audio sent for transcription is not
  saved durably." This must stay driven by storage capabilities/config, not
  hardcoded forever. When durable object storage is configured and healthy, the
  user-facing warning should disappear.

Native microphone note:

- Native OpenWebUI Web API microphone dictation had a separate repeated-text /
  accumulator bug. That is not the Stage 2 media attachment STT path. Treat it
  as native recorder maintenance unless the user explicitly asks about the
  microphone route.
- Known issue as of 2026-06-23: on mobile, native microphone dictation can show
  the recording waveform but produce no audio transcription and stop after about
  five seconds. Current evidence points to browser Web Speech API/mobile
  recognition behavior under `audio.stt.engine = web`, not to the `stage2-stt`
  sidecar. See
  `docs/reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md`.

## 7. Current limitations / hardening backlog

Current hardening backlog:

- mobile browser acceptance;
- low-memory browser acceptance;
- large/customer media matrix;
- practical prepared audio >100 MB behavior;
- duration-limit policy;
- browser ffmpeg cancel;
- upload/job cancel and late-result cleanup;
- persistence beyond in-memory sidecar job store;
- storage/retention/cleanup policy;
- durable prepared-audio storage if storage mode requires it;
- transcript history/export/workflow;
- group/permission policy hardening;
- monitoring/logging/usage/cost events;
- Opus output-profile provider proof if promoted;
- ffmpeg asset cache headers, rollback and versioning;
- OpenWebUI image upgrade compatibility revalidation.

Known current limitations:

- Current generated browser config defaults to `mp3_high_compat`; changing it
  must go through `STAGE2_STT_OUTPUT_PROFILE` and provider/browser proof.
- Input support depends on the configured ffmpeg.wasm build, browser memory,
  duration/size limits, container/codec and audio-stream detection.
- The sidecar job store is in-memory in the MVP.
- Production storage/retention is not closed.
- URL/object-storage provider upload path is not approved until access/expiry
  proof exists.
- Provider-side cancellation and provider max duration remain unknown unless
  proven later.

## 8. Suggested next work

Suggested next work:

1. Add a focused acceptance matrix for mobile, low-memory and large/customer
   media.
2. Convert technical warnings to dynamic human-facing aliases sourced from
   capabilities/config.
3. Harden storage/retention: decide `auto|s3|none`, cleanup, and transcript
   retention.
4. Add durable job storage only if product workflow needs history/cancel across
   restarts.
5. Add browser ffmpeg cancel and late-result cleanup.
6. Prove or reject Opus as production default.
7. Harden permissions/groups around who may run transcription.
8. Add monitoring, structured logs and usage/cost events.
9. Revalidate static loader on every OpenWebUI image upgrade.

## 9. Key files for future agent

Read first:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`

Implementation entrypoints:

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `scripts/fetch-ffmpeg-wasm-assets.sh`
- `compose/openwebui.compose.yml`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/stage2_stt/jobs.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `services/stage2-stt/tests/`

Most relevant reports:

- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_SIDECAR_ROUTING_AUTH_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md`

## 10. How to talk to next chat

Recommended prompt for the next chat:

```text
We are in the corp-openweb ui repo. Read
docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md first, then follow the
linked Stage 2 docs/reports. Treat Stage 2 STT MVP as implemented/proven/current
stage closed. Do not re-plan STT from zero, do not add a separate STT GUI, do
not put provider keys in browser, and do not fork OpenWebUI unless runtime proof
shows the extension-first path is insufficient. Work on the requested next
hardening slice only, keep it docs/code scoped, and do not print secrets,
runtime env-file contents, admin credentials, transcript content, sensitive media
filenames or SSH details.
```

## Copy-paste compact context

```text
Stage 2 STT/OpenWebUI context:

Status: STT MVP is implemented/proven/current-stage closed as of 2026-06-19.
Do not restart STT architecture discovery. Continue from hardening/testing.

Implemented path:
OpenWebUI media attachment -> static loader Transcribe action -> browser
ffmpeg.wasm normalization when needed -> OpenWebUI process=false prepared-audio
upload -> OpenWebUI Action Function -> private stage2-stt sidecar -> Lemonfox
adapter -> transcript returned to OpenWebUI composer/chat UX.

Proven scope:
- private stage2-stt sidecar job/capabilities routes and internal auth;
- LemonfoxSttAdapter live smoke through sidecar;
- OpenWebUI Action Function path using body.files/upload handoff;
- static loader media attachment Transcribe button;
- prepared MP3 passthrough;
- browser ffmpeg.wasm normalization;
- generated MP4-with-audio and WebM audio/video proof;
- unsupported/decode-failed and no-audio safe visible errors;
- self-hosted ffmpeg.wasm assets;
- no provider key/internal sidecar token in browser;
- no separate STT GUI.

Architecture:
Browser/static loader owns visible UX, process=false uploads, ffmpeg.wasm
probe/normalization and safe UI errors. Action Function bridges OpenWebUI file
context to the private sidecar and returns transcript content to current composer.
stage2-stt sidecar owns auth, validation, output profile, storage mode, job
lifecycle, provider adapter factory and transcript normalization. Lemonfox is
first adapter, not hardwired architecture.

Extension-first rule:
native OpenWebUI mechanisms -> Functions/Actions/Tools/OpenAPI Tool Servers ->
thin static loader/minimal UI patch -> private sidecar -> deep fork only with
proof and owner/ADR approval.

Key decisions:
- STT proxy/job boundary is server-side.
- Browser-to-provider is rejected.
- Provider keys stay server-side.
- Sidecar is backend-only; no separate user-facing STT GUI.
- MVP UX is explicit attachment Transcribe, not magic LLM inference.
- Input support is ffmpeg.wasm capability-based; MIME/extension are hints.
- Current browser output profile is mp3_high_compat; Opus needs provider proof
  before default.
- Storage is controlled by auto/s3/none policy; source media storage is off
  unless explicitly approved.

Pitfalls:
- Do not reopen sidecar need, browser key prohibition, Action path viability,
  prepared MP3 viability, or tested ffmpeg.wasm normalization.
- Do not claim universal media support.
- Do not add public sidecar host port, browser provider key, browser internal
  token, deep OpenWebUI fork, or separate sidecar portal.
- prepared_audio_storage_transient means: at MVP stage prepared audio is not
  saved durably. This warning must be driven by storage capabilities/config and
  disappear when durable storage is configured and healthy.
- Native OpenWebUI microphone dictation is a separate path from attachment
  Transcribe.
- Native mobile microphone dictation currently has a known issue: waveform is
  visible, but audio transcription is not produced and recording stops after
  about five seconds; keep it separate from attachment `Transcribe` sidecar
  status.

Hardening backlog:
mobile/large/low-memory media, practical >100 MB behavior, browser ffmpeg
cancel, native mobile microphone Web Speech API trace/fallback, upload/job
cancel and late-result cleanup, duration policy,
storage/retention/cleanup, durable job store if needed, permissions/groups,
transcript history/export/workflow, monitoring/logging/usage/cost events, Opus
proof if promoted, ffmpeg asset cache/rollback/versioning, OpenWebUI image
upgrade revalidation.

Read first:
docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md
docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md
docs/stage2/CONTRACT_BOUNDARIES.md
docs/stage2/ENGINEERING_BACKLOG.md
docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md
docs/stage2/config/STT_ENV_CONTRACT.md
docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md
docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md

Implementation entrypoints:
deploy/openwebui-static/loader.js
deploy/openwebui-static/stage2-stt-normalization.json
services/stage2-stt/
services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py
compose/openwebui.compose.yml
```
