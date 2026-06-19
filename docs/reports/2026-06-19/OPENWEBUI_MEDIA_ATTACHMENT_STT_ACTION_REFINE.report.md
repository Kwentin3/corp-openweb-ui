# OpenWebUI Media Attachment STT Action Refine Report

Date: 2026-06-19
Status: docs refine / next probe planning only
Final verdict: `ready_for_openwebui_media_action_runtime_probe`

## 1. Summary

The owner decision is now encoded as a concrete MVP UX contract:

```text
OpenWebUI chat media attachment -> explicit Transcribe action ->
browser-side normalization -> Stage2 STT sidecar -> Lemonfox adapter ->
transcript returned to current OpenWebUI chat UX
```

This task did not implement the Action Function, frontend code, backend job
routes, compose wiring, production config or Lemonfox live transcription.

## 2. Owner decision encoded

The MVP STT UX is an OpenWebUI-native media attachment action. When an
audio/video file is attached in OpenWebUI chat, supported attachments should
expose an explicit `Transcribe` / `Транскрибировать` action.

That action is the user intent contract for:

- browser-side media normalization through ffmpeg.wasm;
- prepared-audio handoff/job creation;
- backend/provider transcription;
- transcript return into the current OpenWebUI chat/message/artifact UX.

Rejected for MVP:

- separate STT GUI;
- separate user-facing sidecar portal;
- media upload outside OpenWebUI;
- manual transcript copy-back;
- fully implicit/magic LLM inference without explicit user action;
- provider-specific Lemonfox UI.

## 3. Docs refined

Updated:

- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/CONTEXT_INDEX.md`

Created:

- `docs/stage2/implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_ACTION_REFINE.report.md`

## 4. MVP UX contract

MVP contract:

```text
Attach media -> explicit Transcribe action -> browser normalization ->
sidecar job -> Lemonfox -> transcript in current OpenWebUI chat UX
```

Boundary:

- OpenWebUI UI owns visible attachment action, immediate feedback, progress and
  transcript placement.
- Browser/OpenWebUI integration may run ffmpeg.wasm normalization after explicit
  user action.
- Stage2 sidecar owns validation, limits, storage mode, job state, cancel,
  provider adapter and transcript normalization.
- Lemonfox remains hidden behind `LemonfoxSttAdapter`.

Optional convenience later:

- If user types "транскрибируй" while a media attachment is present, OpenWebUI
  may surface or invoke the same explicit media attachment action path.

## 5. Future workflow boundary

Marked future/later:

- dedicated transcription workflow;
- meeting transcription workspace;
- transcript history/export;
- protocol/minutes workflow;
- full production storage/retention implementation;
- production Lemonfox job execution routes.

These are not part of the MVP media attachment action probe.

## 6. Implementation gates updated

Gate added/refined:

```text
OpenWebUI media attachment action runtime probe must pass before production job
routes or final UI.
```

Gate checks:

- Action sees attached media;
- Action can access file bytes or approved handoff;
- Action can show status/progress;
- Action can call sidecar dummy endpoint;
- Action can place transcript in chat/message/artifact;
- unsupported files show no action or safe error;
- no separate STT GUI;
- no provider key in browser.

## 7. Acceptance criteria updated

Added MVP UX acceptance criteria:

- media attachment shows explicit `Transcribe` action;
- unsupported file does not show action or shows safe visible error;
- explicit action triggers browser-side normalization;
- user sees immediate acknowledgment, progress/busy state and terminal state;
- result appears in the same OpenWebUI chat/message/artifact UX;
- error/cancel state is visible;
- user does not leave OpenWebUI;
- magic LLM-triggered transcription is not accepted as MVP.

## 8. Next refactor/probe plan

Created:

```text
docs/stage2/implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md
```

The plan defines:

- goal;
- probe scope;
- non-goals;
- refactor target;
- evidence to capture;
- UI integrity checklist;
- decision outcomes;
- stop conditions.

Allowed probe outcomes:

- `action_path_approved`
- `action_path_needs_small_patch`
- `openapi_tool_server_probe_needed`
- `minimal_frontend_patch_required`
- `blocked_by_openwebui_file_context`

## 9. Remaining unknowns

- Whether pinned OpenWebUI exposes attached media to Action Functions.
- Whether Action can access file bytes or only metadata.
- Whether browser-side normalization can be attached to the Action path without
  a small frontend patch.
- Whether event/status behavior is sufficient for progress and cancel UX.
- Whether transcript placement can be cleanly done as chat/message/artifact.
- Whether Action permissions can be restricted by group/workspace as needed.
- Which auth boundary protects the later sidecar job route.

## 10. Final verdict

```text
ready_for_openwebui_media_action_runtime_probe
```

No repo/docs blocker was found. The next correct step is a staging/admin
OpenWebUI runtime probe for the media attachment `Transcribe` action, not
production STT job routes and not a separate STT GUI.
