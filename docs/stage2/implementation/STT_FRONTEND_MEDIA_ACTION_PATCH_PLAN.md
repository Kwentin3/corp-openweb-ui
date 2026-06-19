# STT Frontend Media Action Patch Plan

Status: historical patch plan; MVP attachment action patch is implemented and
proven for prepared MP3 and browser-normalized generated media.

Implementation baseline note, 2026-06-19:

- `deploy/openwebui-static/loader.js` adds the visible attachment-level
  `Transcribe` action through a static OpenWebUI loader patch.
- The action reuses OpenWebUI upload/Action APIs and the private `stage2-stt`
  sidecar; no Lemonfox/provider key is exposed in the browser.
- Browser ffmpeg.wasm normalization now runs after explicit user action and
  reuses the same prepared-audio Action/sidecar contract.
- Remaining work is hardening and product workflow acceptance, not initial
  visibility of the action.

## 1. Original problem and residual risk

The visibility gap described below is closed for the MVP static loader path.
The remaining risk is regression/hardening: richer progress/cancel behavior,
mobile/large-file proof, transcript persistence/export and avoiding drift into
a separate STT GUI.

The backend/API path works:

```text
OpenWebUI Action API -> stage2-stt sidecar -> Lemonfox -> transcript
```

The browser UI path does not expose a discoverable attachment-level
`Transcribe` / `Транскрибировать` action. Users can upload an MP3, but they
cannot clearly run the Stage 2 transcription action from the tested chat UI.

Risk:

- users will use ordinary chat/file processing instead of Stage 2 STT;
- OpenWebUI's default MP3 processing may show unrelated errors;
- the project could drift into a separate STT GUI unless the OpenWebUI-native
  affordance is fixed.

## 2. Domain and ownership map

OpenWebUI frontend owns:

- visible attachment action;
- user intent event;
- attachment-level ready/busy/error/success state;
- transcript placement in current chat UX.

OpenWebUI backend/Action owns:

- authenticated Action invocation;
- OpenWebUI user/file/chat context;
- upload-storage handoff or equivalent safe file reference;
- status events returned to the UI.

`stage2-stt` sidecar owns:

- provider keys;
- capabilities and limits;
- prepared-audio validation;
- job/result/cancel contract;
- Lemonfox adapter behavior;
- transcript normalization.

The UI must not own Lemonfox logic, provider keys, provider limits, storage
policy, or retention decisions.

## 3. Boundary contracts

Primary prepared-MP3 slice:

```text
attachment card click -> OpenWebUI frontend intent ->
POST /api/chat/actions/stage2_media_transcription_action ->
Action reads body["files"] -> sidecar job route -> transcript result
```

Minimum UI payload context:

```text
chat_id
message_id or composer draft context
model/model_item as required by OpenWebUI action endpoint
files[0].file.id
files[0].file.filename
files[0].file.mime_type
files[0].file.size
```

Capability check:

```text
GET /stage2-api/transcription/capabilities
```

The frontend may use this only for UI-safe limits/profile labels. It must not
infer provider secrets or provider-specific behavior.

## 4. Proposed slices

### Slice 1. Prepared-MP3 attachment action button

Status: implemented/proven.

- Add a visible `Транскрибировать` control to supported audio attachment cards.
- Supported first MIME: `audio/mpeg`.
- Hide or disable the control for unsupported files with a clear reason.
- Call the existing Action route or a thin OpenWebUI backend shim.
- Show immediate busy state and terminal success/error.
- Place transcript in the current chat as the Action result.

Validation:

- Playwright: login -> upload MP3 -> click `Транскрибировать` -> transcript
  marker/result appears in current chat.
- Network: browser calls OpenWebUI backend only; no Lemonfox/browser call.
- Security scan: no keys in browser payloads or screenshots.

### Slice 2. Upload processing isolation

Status: implemented for the Stage 2 path through explicit `process=false`
uploads and prepared-audio re-upload.

- Avoid or suppress unrelated OpenWebUI default MP3 processing errors for the
  Stage 2 path.
- Prefer an explicit Stage 2 attachment mode or upload metadata flag if the
  upstream extension point supports it.
- If upstream does not support it, document the smallest compatible patch.

Validation:

- Uploading MP3 for Stage 2 does not show the current `NoneType` processing
  toast.
- Unsupported-file errors remain visible and safe.

### Slice 3. Progress and cancel surface

Status: basic ready/busy/success/error states are implemented. Cancel and
richer progress remain hardening items.

- Render Action status events as attachment/chat progress.
- Add cancel affordance only if it maps to the sidecar cancel contract.
- If provider cancel is still unknown, label cancel as local cancellation.

Validation:

- Playwright covers ready, busy, completed, failed and cancel-shaped states.

### Slice 4. Browser ffmpeg.wasm normalization

Status: implemented/proven on generated proof media.

- Trigger normalization after explicit user action.
- Read output profile and limits from capabilities.
- Produce prepared audio, then reuse the same Action/sidecar contract.
- Keep ffmpeg assets self-hosted/internal per ADR-0004.

Validation:

- desktop audio/video smoke;
- no provider key in browser;
- prepared audio respects selected output profile and size limits.

## 5. Tests and acceptance checks

Required:

- Playwright UI proof for prepared MP3;
- API smoke for Action route;
- sidecar capabilities smoke;
- no-secret scan of browser network and committed artifacts;
- screenshot evidence with transcript redacted or omitted.

Acceptance:

- user sees `Транскрибировать` near supported media;
- click yields immediate feedback;
- result appears in current chat;
- no separate STT GUI;
- sidecar remains private;
- unsupported media has safe visible behavior.

## 6. Non-goals and deferred work

Not in this patch:

- separate STT portal;
- provider-specific UI;
- Lemonfox calls from browser;
- deep OpenWebUI fork;
- meeting workspace/history/export;
- full source-media/video normalization before prepared-MP3 UX passes.

Deferred:

- browser ffmpeg.wasm for video/source media;
- production transcript retention UX;
- richer progress/cost metadata;
- provider-side cancel proof.
