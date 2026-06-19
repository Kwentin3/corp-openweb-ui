# OpenWebUI STT MVP Feature Closure Report

Date: 2026-06-19

## 1. Summary

Stage 2 STT MVP is implemented and Playwright-proven for the current stage.

Implemented path:

```text
OpenWebUI media attachment -> static loader Transcribe action ->
browser ffmpeg.wasm normalization -> OpenWebUI Action Function ->
private stage2-stt sidecar -> Lemonfox adapter -> transcript returned to
OpenWebUI composer/chat UX.
```

This closes the current implementation stage. Remaining STT work is
testing/hardening, not architectural discovery.

## 2. Implemented/Proven Scope

Current-stage completed/proven items:

- private `stage2-stt` sidecar backend foundation;
- private job routes and internal auth;
- `LemonfoxSttAdapter` and Lemonfox live smoke;
- OpenWebUI Action Function path;
- static loader `Transcribe` button on media attachments;
- prepared MP3 passthrough path;
- browser ffmpeg.wasm normalization;
- MP4 video with audio proof;
- WebM audio/video proof;
- unsupported/decode-failed media safe visible error;
- no-audio media safe visible error;
- self-hosted ffmpeg.wasm assets through OpenWebUI static assets;
- transcript returned to the current OpenWebUI composer/chat UX;
- provider keys and internal sidecar token kept out of the browser;
- no separate user-facing STT sidecar GUI.

## 3. Extension-First Pattern Confirmed

STT confirms the Stage 2 extension-first implementation pattern:

```text
static loader UX shim + Action Function + private sidecar + provider adapter
```

The user remains in native OpenWebUI UX, OpenWebUI stays updateable, and domain
logic stays isolated behind the sidecar/provider-adapter boundary.

Canonical pattern doc:

- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`

## 4. Documents Updated

Living docs updated:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`

Historical implementation reports were not edited.

## 5. Acceptance Status

Current-stage acceptance: passed.

Reasons:

- user stays inside OpenWebUI;
- media attachment shows explicit `Transcribe` action;
- prepared MP3 path passes;
- browser ffmpeg normalization passes for tested generated media;
- transcript returns to OpenWebUI UX;
- sidecar remains backend-only;
- Lemonfox key is not exposed;
- no separate STT GUI was introduced.

Production hardening: pending.

Reasons:

- broad real-world media matrix is not complete;
- mobile, large-file and low-memory browser testing are not complete;
- cancel, retention and persistence are not complete;
- permission, monitoring and cost-event hardening are not complete.

## 6. Remaining Testing/Hardening Backlog

Keep active:

- mobile browser testing;
- large/customer file testing;
- low-memory browser testing;
- browser ffmpeg cancel;
- duration limits;
- retention/cleanup policy;
- persistence beyond in-memory job store;
- group/permission hardening;
- Opus default proof if promoted;
- transcript export/history/workflow;
- monitoring/logging/cost events;
- rollback/cache/versioning of ffmpeg assets.

## 7. Sticky Comments Added

Sticky comments were added to the Stage 2 living docs so future agents do not:

- re-plan STT from zero;
- fork OpenWebUI without proven necessity;
- treat the sidecar as a user-facing GUI;
- move provider keys or provider decisions into the browser;
- reopen the Action/static-loader/browser-normalization path as discovery work.

## 8. What Future Agents Should Not Reopen

Do not reopen as active architectural discovery:

- whether STT needs a private backend/domain sidecar;
- whether provider keys may live in browser;
- whether a separate user-facing STT GUI is needed for MVP;
- whether the OpenWebUI media attachment Action path can work;
- whether browser ffmpeg.wasm normalization can work for the tested MVP cases;
- whether prepared MP3 passthrough is viable;
- whether generated MP4/WebM media can reach the Action/sidecar path.

## 9. What Future Agents Should Work On Next

Work on testing/hardening:

- mobile, large and low-memory acceptance matrix;
- cancel UX and late-result cleanup;
- production storage/retention policy;
- durable job store if needed;
- Opus output-profile proof if Opus becomes default;
- permissions/group policy hardening;
- transcript history/export/workflow;
- monitoring, logs and usage/cost events;
- ffmpeg asset cache/rollback/versioning.

## 10. Final Verdict

```text
stt_mvp_current_stage_closed_ready_for_broader_testing
```
