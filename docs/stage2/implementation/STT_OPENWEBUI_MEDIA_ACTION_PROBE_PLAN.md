# STT OpenWebUI Media Action Probe Plan

Status: planning document. No production implementation started.

## 1. Goal

Prove that OpenWebUI can host a native media attachment `Transcribe` /
`Транскрибировать` action that calls the Stage2 STT sidecar and returns a
transcript to the current chat UX.

The action is the MVP user intent contract:

```text
media attachment -> explicit Transcribe action -> browser normalization ->
sidecar dummy/job call -> transcript in current OpenWebUI chat UX
```

## 2. Probe scope

- Create a minimal Action Function in staging/admin OpenWebUI.
- Attach non-sensitive audio/video file in chat.
- Inspect `__user__`, `__metadata__`, `body["files"]` and `__files__`.
- Check whether Action can access bytes or only metadata.
- Check whether approved file handoff is possible without binding sidecar to
  private `openwebui_data` layout.
- Emit status events for queued/busy/completed/error states.
- Call sidecar dummy endpoint without provider key.
- Return dummy transcript to current chat/message/artifact UX.
- Test unsupported-file error state.
- Test cancel-shaped interaction if possible.
- Record whether Action can be restricted by admin/group/workspace policy.

## 3. Not in scope

- Production job routes.
- Full Lemonfox transcription.
- Full browser ffmpeg implementation.
- Dedicated transcription GUI.
- Dedicated transcription workspace/history/export/protocol workflow.
- OpenWebUI deep fork.
- Storage/retention production implementation.
- Provider keys in Action, browser, logs or docs.

## 4. Refactor target

If the probe passes, the next refactor should create a thin OpenWebUI Action
integration layer:

- Action remains thin.
- Action owns only the OpenWebUI media attachment intent surface.
- Action emits UI feedback and passes approved context to the sidecar.
- Action does not contain provider keys.
- Action does not contain Lemonfox logic.
- Action does not decide provider capabilities, data policy, retention or
  storage mode.
- Action calls the sidecar only.
- Sidecar remains source of truth for capabilities, limits, storage, job state,
  cancel semantics, provider behavior and transcript normalization.

If the probe proves Action cannot see bytes or perform approved handoff, stop
and decide between a small OpenWebUI patch, OpenAPI Tool Server probe or a
backend-mediated upload path.

## 5. Evidence to capture

- Exact OpenWebUI version/tag.
- Whether attached media is visible to Action.
- Exact safe summary of `__user__`, `__metadata__`, `body["files"]` and
  `__files__` shape.
- Whether file bytes are accessible.
- Whether approved file handoff works without sidecar reading private
  OpenWebUI storage directly.
- Whether event emitter/status works.
- Transcript placement behavior: chat message, assistant/tool message,
  artifact/file or limitation.
- Error-state behavior for unsupported file and sidecar dummy failure.
- Cancel-shaped behavior or explicit limitation.
- Whether Action can be restricted to admin/group/workspace.
- Whether sidecar dummy call works without provider key.
- Confirmation that no separate STT GUI was used.
- Confirmation that no provider key appears in browser-visible payloads/logs.

## 6. UI integrity checklist

The probe must cover user-visible states:

- empty/no media attachment;
- unsupported media;
- ready with visible `Transcribe` action;
- disabled/unavailable action with reason;
- busy/loading normalization;
- uploading/sidecar call in progress;
- completed transcript;
- failed transcript with safe message;
- cancel requested;
- cancelled.

Interaction rules:

- Primary action is explicit and unambiguous.
- Action is operable with keyboard/focus if the runtime surface allows it.
- Every user action yields immediate acknowledgment and terminal feedback.
- UI emits intent/events; backend/sidecar owns domain decisions.

## 7. Decision after probe

Allowed outcomes:

- `action_path_approved`
- `action_path_needs_small_patch`
- `openapi_tool_server_probe_needed`
- `minimal_frontend_patch_required`
- `blocked_by_openwebui_file_context`

Any outcome must include evidence links/notes and the next smallest safe slice.

## 8. Stop conditions

Stop the probe before production implementation if:

- Action cannot see attached media at all.
- Action cannot access bytes or approved handoff.
- Status/error feedback cannot be shown.
- Transcript cannot be returned to the current OpenWebUI UX.
- The path requires provider key in browser/Action.
- The path requires sidecar to read private OpenWebUI storage as an unversioned
  contract.
- The path requires a deep OpenWebUI fork before a small patch is evaluated.
- The path turns MVP into a separate STT portal.
