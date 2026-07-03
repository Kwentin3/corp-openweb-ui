# STT v2 Message-Level DOCX Export Research

Status: research / engineering anamnesis / implementation context pack.

Date: 2026-07-03.

Requested output path:

```text
docs/reports/2026-07-02/STT_V2_MESSAGE_LEVEL_DOCX_EXPORT_RESEARCH.report.md
```

## 1. Executive Summary

Verdict: **GO with guardrails**.

The feature should not be implemented as an STT-only export. The better product
and architecture shape is a generic **message-level DOCX export** for useful
completed OpenWebUI assistant messages. STT v2 then benefits naturally because
its raw transcript, post-processing summaries and future processed outputs are
rendered as assistant-visible message content.

Recommended MVP:

```text
OpenWebUI assistant message toolbar
-> static loader injects a DOCX icon button
-> loader builds MessageDocxExportRequestV1 from one selected completed message
-> OpenWebUI Action acts as an authenticated RPC bridge
-> stage2 sidecar generates DOCX
-> loader saves the returned DOCX in the browser
```

This keeps OpenWebUI core update-safe. It reuses the extension layer already used
by STT v2 and keeps binary generation away from OpenWebUI internals. The first
implementation should still include a small selector/API proof because OpenWebUI
message DOM is not a public API.

Hard constraints for implementation:

- do not patch OpenWebUI core;
- do not export whole chats in MVP;
- export only one selected message per click;
- default to completed assistant messages only;
- never include raw provider payloads, hidden prompts, cookies, tokens,
  internal URLs or sidecar config in the DOCX;
- make loader failure a safe no-op;
- do not let DOCX failure break normal chat, STT v2 or post-processing.

## 2. Scope And Non-Goals

In scope:

- research the OpenWebUI message UI anatomy;
- identify candidate sources of truth for a selected message;
- evaluate Action, static loader, sidecar and browser download paths;
- define MVP contracts and no-leak rules;
- propose a conservative implementation sequence and proof plan.

Out of scope for this report:

- no code changes;
- no production deployment;
- no OpenWebUI core patch;
- no PDF export;
- no branded Word templates;
- no WYSIWYG Word editor;
- no whole-chat export;
- no attachments, images, generated files or tool artifacts inside DOCX in MVP.

## 3. Evidence Sources

Local repository evidence:

- `deploy/openwebui-static/loader.js`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/pyproject.toml`
- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`
- `docs/stage2/operations/STT_V2_PILOT_READINESS_CHECKLIST.md`
- `docs/reports/2026-07-02/STT_V2_FINAL_CLOSEOUT_AND_PILOT_READINESS.report.md`

OpenWebUI documentation:

- OpenWebUI Action Function docs:
  <https://docs.openwebui.com/features/extensibility/plugin/functions/action/>
- OpenWebUI Functions docs:
  <https://docs.openwebui.com/features/extensibility/plugin/functions/>

OpenWebUI source-level references, pinned to the deployed upstream family:

- `src/lib/components/chat/Messages/Message.svelte`:
  <https://raw.githubusercontent.com/open-webui/open-webui/v0.9.6/src/lib/components/chat/Messages/Message.svelte>
- `src/lib/components/chat/Messages/ResponseMessage.svelte`:
  <https://raw.githubusercontent.com/open-webui/open-webui/v0.9.6/src/lib/components/chat/Messages/ResponseMessage.svelte>
- `backend/open_webui/routers/chats.py`:
  <https://raw.githubusercontent.com/open-webui/open-webui/v0.9.6/backend/open_webui/routers/chats.py>
- `backend/open_webui/routers/files.py`:
  <https://raw.githubusercontent.com/open-webui/open-webui/v0.9.6/backend/open_webui/routers/files.py>

Browser API references:

- `HTMLAnchorElement.download`:
  <https://developer.mozilla.org/en-US/docs/Web/API/HTMLAnchorElement/download>
- `URL.createObjectURL`:
  <https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static>
- `window.showSaveFilePicker`:
  <https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker>

## 4. Current STT v2 Baseline

The current STT v2 contour already has useful extension primitives:

- static loader scans OpenWebUI DOM through `MutationObserver`;
- loader calls an OpenWebUI Action endpoint through `/api/chat/actions/{id}`;
- loader parses JSON Action responses;
- stage2 sidecar exposes authenticated internal endpoints;
- normalized transcript artifacts are stored through the sidecar layer;
- post-processing quick actions already return processed text into chat.

Important current gaps for this feature:

- `python-docx` is not a current sidecar dependency;
- no generic message-level DOCX endpoint exists;
- current DOCX notes in older STT docs are STT/post-processing-specific;
- OpenWebUI Action file-return behavior is documented, but the exact browser
  "click icon -> save DOCX" flow is not proven in our runtime;
- OpenWebUI file API can download stored files, but sidecar-safe file creation
  through OpenWebUI storage is not yet proven.

## 5. OpenWebUI UI Anatomy

OpenWebUI v0.9.6 separates user and assistant messages at the component level.
`Message.svelte` routes `role === 'user'` to `UserMessage` and other message
roles to `ResponseMessage`.

Relevant assistant-message DOM/source observations from `ResponseMessage.svelte`:

- assistant root uses `id="message-{message.id}"` and class
  `message-{message.id}`;
- assistant content wrapper includes `chat-{message.role}` and
  `markdown-prose`;
- the rendered response content is under a `response-content-container` id, but
  that id is repeated per message and must never be queried globally;
- the toolbar container uses a `buttons` class;
- default message controls, including copy, are shown only once `message.done`
  is true;
- model Actions are rendered in the same toolbar and call
  `actionMessage(action.id, message)`.

Selector consequence:

```text
Good scoped root:
  div[id^="message-"]

Good scoped assistant content:
  root.querySelector(".chat-assistant.markdown-prose")

Acceptable toolbar anchor:
  root.querySelector(".buttons")

Useful completion hint:
  root.querySelector(".copy-response-button")

Avoid:
  document.querySelector("#response-content-container")
```

`#response-content-container` is a duplicate id in the page. It can only be used
when scoped under a concrete message root, and even then it should be treated as
an implementation detail.

## 6. Message Source-Of-Truth Variants

### Variant A: OpenWebUI Chat API

Candidate route:

```text
GET /api/v1/chats/{chat_id}
```

Source-level evidence in `chats.py` shows that the route returns the chat to the
owner, admin or a user with an access grant. The chat blob contains
`history.messages`, and message update routes also operate on message ids.

Pros:

- best semantic source for `message.content`;
- avoids lossy DOM text extraction;
- can validate message role, chat id and message id;
- matches OpenWebUI access control if called with the active user's browser
  credentials.

Cons:

- loader must derive `chat_id` and `message_id` safely;
- authentication/session behavior must be proven in browser;
- OpenWebUI route shape is source-level evidence, not a formal stable API
  contract for extension code.

Recommendation: **preferred source after a browser proof**.

### Variant B: OpenWebUI Action Body

Native Action functions receive the message body and user context. OpenWebUI
documentation describes Actions as toolbar buttons for messages, with access to
`body`, `__user__`, event emitters, model data and request context.

Pros:

- native toolbar mechanism;
- server-side current-user context;
- no DOM content extraction;
- less browser-side contract surface.

Cons:

- binary file save UX is not proven for our desired "click -> save DOCX"
  experience;
- Action output tends to modify or append chat content unless wrapped carefully;
- visible native Action may duplicate a loader-injected button.

Recommendation: use an Action as an authenticated bridge, and keep native visible
Action-only export as a fallback path if the loader path becomes too brittle.

### Variant C: DOM Extraction

The loader can extract the rendered assistant message from the DOM.

Pros:

- no extra OpenWebUI API dependency;
- works with the UI the user actually sees;
- direct integration with the browser save flow.

Cons:

- lossy for markdown/source semantics;
- selector drift risk across OpenWebUI upgrades;
- requires aggressive removal of toolbar/control/status text;
- easy to accidentally include neighboring content if root scoping is weak.

Recommendation: acceptable as fallback, not as the only source of truth.

### Variant D: STT ArtifactStore / TranscriptResultV1

The sidecar stores normalized STT transcript artifacts.

Pros:

- strongest source for structured transcript data;
- preserves speaker labels, timestamps and segment semantics;
- avoids raw LemonFox JSON.

Cons:

- STT-only, not generic message-level export;
- does not cover arbitrary LLM answers;
- requires artifact access checks and typed refusals.

Recommendation: keep for a future STT-specific export mode. It should not be the
MVP path for generic message-level DOCX export.

## 7. Recommended Target Architecture

Recommended MVP architecture:

```text
Browser / OpenWebUI
  static loader
    - scans completed assistant messages
    - injects one DOCX icon button per eligible message
    - builds MessageDocxExportRequestV1
    - calls /api/chat/actions/stage2_message_docx_export_action
    - receives DOCX payload metadata
    - saves file through browser download APIs

OpenWebUI Action
  stage2_message_docx_export_action
    - validates request envelope
    - takes authenticated user context from OpenWebUI
    - refuses non-assistant, empty, too-large or malformed messages
    - calls sidecar through internal authenticated HTTP
    - returns MessageDocxExportResultV1

stage2-stt sidecar
  POST /stage2-api/message-docx/exports
    - validates contract
    - sanitizes safe metadata
    - renders DOCX using python-docx
    - scans generated ZIP/XML for forbidden markers
    - returns base64 DOCX for MVP
```

Key boundary decision:

The sidecar should generate DOCX, not the static loader. The loader should stay
small and safe-to-fail. The sidecar is the right place for `python-docx`,
contract validation, deterministic tests and no-leak checks.

## 8. DOCX Generation Location Options

| Option | Verdict | Reason |
| --- | --- | --- |
| Browser-only DOCX generation | Not MVP | Requires a JS DOCX bundle in the static loader, increases loader size and makes sanitizer/formatting harder to test. |
| OpenWebUI Action-only generation | Possible fallback | Native toolbar placement is attractive, but exact browser save UX and binary result handling are not proven. |
| Sidecar generation through Action bridge | Recommended MVP | Keeps dependencies isolated, testable and update-safe while reusing the proven Action bridge. |
| OpenWebUI file API storage | Future path | Download route exists, but safe sidecar-to-OpenWebUI file registration needs a separate proof. |

MVP delivery mode should be:

```text
delivery = "base64"
```

The sidecar returns a small DOCX payload in JSON, the loader converts it to a
`Blob`, then triggers browser save. This avoids inventing a temporary public file
storage system for the first slice.

Add a hard output size limit. If the generated DOCX exceeds the limit, return a
typed refusal and do not append raw binary or a partial document into chat.

## 9. Browser Save Strategy

Preferred runtime behavior:

1. User clicks the DOCX icon.
2. Loader sends export request while the click context is still fresh.
3. If `window.showSaveFilePicker` is available and allowed, use it.
4. Otherwise create a `Blob`, call `URL.createObjectURL(blob)`, click a temporary
   `<a download="...">`, then call `URL.revokeObjectURL`.

Reasons:

- `showSaveFilePicker` gives the best user-controlled save path, but it is not
  universally available and has stricter activation/security constraints.
- `<a download>` plus an object URL is a mature fallback, though the browser can
  still adjust filename behavior.
- All save logic stays in the browser; the server does not need to know the
  user's local filesystem.

## 10. Message Eligibility Policy

MVP policy:

- show the DOCX button for completed assistant messages only;
- do not show it for user messages;
- do not show it while a response is streaming;
- do not show it for empty/error/status-only messages;
- show it on all eligible assistant messages, not only the latest one;
- keep the button hidden/no-op if selectors cannot be proven on a given page.

Rationale:

The user's need is "export this useful LLM answer/transcript/summary". Assistant
messages are the reliable first target. User-message export can be added later
if there is a real use case, but it increases ambiguity around prompts and
private instructions.

## 11. Contract Model

### MessageDocxExportRequestV1

```json
{
  "schema_version": "MessageDocxExportRequestV1",
  "request_id": "uuid-or-random-id",
  "chat_id": "string-or-null",
  "message_id": "string-or-null",
  "message_role": "assistant",
  "message_text": "plain visible message text",
  "message_markdown": "optional markdown source",
  "message_html": "optional sanitized rendered html",
  "source": "openwebui_chat_api",
  "safe_metadata": {
    "chat_title": "string-or-null",
    "model_name": "string-or-null",
    "message_timestamp": "iso8601-or-null",
    "source_url_path": "path-only-or-null",
    "result_ref": "optional-public-ref-or-null"
  },
  "requested_by": {
    "user_id": "server-derived-or-null",
    "user_role": "server-derived-or-null"
  },
  "options": {
    "include_chat_title": true,
    "include_model_name": true,
    "include_timestamp": true,
    "formatting_profile": "simple_mvp"
  }
}
```

Validation rules:

- `schema_version` must match exactly;
- `message_role` must be `assistant` in MVP;
- `message_text` is required after normalization;
- `message_text` must not exceed the configured maximum;
- `message_html` is optional and must be sanitized if provided;
- `requested_by` must be taken from Action context server-side, not trusted from
  browser input;
- `source_url_path` must be a path, not a full URL with host or token;
- metadata is allow-listed, not copied wholesale from OpenWebUI or the DOM.

Allowed `source` values:

```text
openwebui_chat_api
dom
action_body
artifact
```

### MessageDocxExportResultV1

```json
{
  "schema_version": "MessageDocxExportResultV1",
  "export_id": "uuid-or-random-id",
  "filename": "message-export.docx",
  "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 12345,
  "checksum_sha256": "hex",
  "delivery": "base64",
  "download_payload_base64": "base64-docx",
  "download_url": null,
  "file_id": null,
  "warnings": []
}
```

Validation rules:

- `content_type` must be the DOCX MIME type;
- `filename` must be sanitized and end in `.docx`;
- `checksum_sha256` must match generated bytes;
- `delivery=base64` requires `download_payload_base64`;
- `download_url` and `file_id` must be null for the first MVP unless a separate
  proof enables them;
- warnings must be typed and safe to display.

### Typed Refusals

Recommended refusal codes:

```text
message_docx_unsupported_role
message_docx_empty_message
message_docx_streaming_message
message_docx_message_too_large
message_docx_generation_failed
message_docx_no_safe_source
message_docx_access_denied
message_docx_no_leak_check_failed
```

Refusals must be returned as structured JSON. The loader may show a small
notification, but must not append noisy failure text into the chat transcript.

## 12. No-Leak Requirements

DOCX content must include only:

- selected visible assistant message text;
- safe optional formatting derived from selected visible content;
- safe metadata explicitly selected by contract: title, model display name,
  timestamp and result reference.

DOCX content must not include:

- raw provider payloads;
- provider JSON;
- prompt bodies;
- hidden system/developer instructions;
- browser cookies;
- Authorization or bearer-token headers;
- API key values or API key environment values;
- internal Docker hostnames;
- internal sidecar URLs;
- OpenWebUI internal file paths;
- debug logs;
- full chat history;
- neighboring user or assistant messages;
- toolbar labels and UI controls.

Implementation should scan the generated DOCX ZIP parts, not only the source
message. At minimum scan:

```text
word/document.xml
docProps/core.xml
docProps/app.xml
word/_rels/document.xml.rels
_rels/.rels
```

The scanner should look for forbidden marker families:

- token/header marker family: API key prefixes, bearer-token headers,
  authorization headers, cookie headers;
- provider marker family: raw provider payload labels and LemonFox raw response
  markers;
- internal URL marker family: sidecar hostnames, Docker service names and
  private runtime URLs;
- hidden config marker family: STT internal auth config names and provider key
  config names;
- UI-control marker family: copy, edit, regenerate, rate, read-aloud and
  continue-response labels;
- adjacency marker family: sentinel text from previous and next messages in
  tests.

## 13. DOCX Layout MVP

Minimal layout:

```text
Title: Exported Assistant Message

Metadata table:
  Chat title: optional
  Model: optional
  Message time: optional
  Export time: current server time
  Source: OpenWebUI message

Content:
  selected message content

Footer:
  Generated by STT v2 extension layer
```

Formatting profile `simple_mvp`:

- headings preserved where markdown source is available;
- paragraphs preserved;
- bullet and numbered lists preserved;
- code blocks rendered as monospace-style paragraphs;
- tables may be flattened into readable text in MVP;
- links may render as visible text plus URL only if the URL is already visible in
  the assistant message;
- images and attachments are omitted.

No custom branded template is needed for MVP.

## 14. STT v2 Integration

The feature should integrate with STT v2 at the message layer:

```text
STT raw transcript assistant message
  -> eligible for DOCX export as visible message content

STT post-processing result assistant message
  -> eligible for DOCX export as visible message content

Future structured transcript DOCX
  -> can use artifact source only after access-proof and contract extension
```

This preserves the existing STT v2 rule: raw LemonFox JSON must not leak into
chat output, prompt input, storage output or DOCX. The generic message exporter
must only see normalized/user-visible OpenWebUI message content.

The older STT-specific DOCX blueprint sections should be treated as future
specialized export work. The recommended MVP supersedes them for the first
delivery slice.

## 15. UX Placement

Recommended UX:

- a compact DOCX icon button in the existing assistant message toolbar;
- tooltip: `Export to DOCX`;
- no visible marketing copy;
- no chat message appended on success;
- failure as a small notification/status only;
- loading state on the button while export is running;
- one button per eligible message, protected by a `data-stage2-docx-export`
  marker to avoid duplicates after rerenders.

Mobile behavior:

- button must fit inside the existing horizontal toolbar;
- no fixed overlays;
- no layout shift in message content;
- no dependency on hover-only visibility for discoverability in high-contrast or
  touch environments.

## 16. Selector Risk Matrix

| Signal | Risk | Recommendation |
| --- | --- | --- |
| `div[id^="message-"]` | Medium | Use as root only; derive id carefully. |
| `.chat-assistant.markdown-prose` | Medium | Use scoped under root; fallback to API message content. |
| `#response-content-container` | High globally | Never query globally; scoped fallback only. |
| `.buttons` toolbar | Medium | Preferred injection target; no-op if missing. |
| `.copy-response-button` | Medium | Good completion/anchor hint; do not require forever. |
| URL-derived chat id | Medium | Prefer proven helper; fallback to null metadata or DOM-only source. |
| model name DOM node | High | Optional metadata only; never block export. |

Upgrade-safe rule:

If selectors are missing or ambiguous, the loader must not throw and must not
inject a broken button. It should simply skip the message.

## 17. OpenWebUI File API Assessment

OpenWebUI v0.9.6 file router supports:

- uploading files through `POST /api/v1/files/`;
- authenticated file access checks;
- `GET /api/v1/files/{id}/content`;
- attachment-style `Content-Disposition` for downloads.

This is useful for a later `delivery=openwebui_file_id` mode.

It is not the recommended MVP because sidecar-safe file creation through
OpenWebUI storage needs a separate proof:

- how the sidecar authenticates as the current user or a constrained service;
- how file ownership and access grants are applied;
- how metadata is sanitized;
- how cleanup/retention works;
- whether uploaded/generated DOCX files should appear in the user's file
  library.

## 18. Action Design

Recommended new Action id:

```text
stage2_message_docx_export_action
```

Action responsibilities:

- accept only `MessageDocxExportRequestV1`;
- derive `requested_by` from `__user__`;
- apply role, length and source validation;
- call sidecar over internal authenticated HTTP;
- return `MessageDocxExportResultV1`;
- return typed refusals without chat pollution;
- never embed sidecar errors, tokens or internal URLs into user-visible content.

The Action should be implemented as a bridge, not as the DOCX renderer. This
keeps DOCX dependencies and tests inside the sidecar package.

## 19. Sidecar Endpoint Design

Recommended endpoint:

```text
POST /stage2-api/message-docx/exports
```

Authentication:

- same internal-auth pattern as existing sensitive sidecar routes;
- no public unauthenticated DOCX generation endpoint.

Request:

- `MessageDocxExportRequestV1`

Response:

- `MessageDocxExportResultV1`

Dependency:

- add `python-docx` only to sidecar dependency set when implementation starts;
- pin or constrain version in the same style as existing sidecar dependencies.

Limits:

```text
message_text max: 100000 characters for MVP
generated DOCX max: 5 MB for base64 delivery
timeout: short bounded HTTP timeout from Action to sidecar
```

These thresholds are intentionally conservative. They should be env-backed if
the implementation owner expects frequent tuning.

## 20. Architecture Options

### Option 1: Native Action Only

Verdict: **prototype fallback**.

This is closest to OpenWebUI native extensibility. It should be tested, but not
assumed to satisfy the exact browser-save UX until proven. It may return files or
links, but the current desired behavior is direct selected-message download.

### Option 2: Loader + Action + Sidecar

Verdict: **recommended MVP**.

This is consistent with the current STT v2 extension architecture. It avoids
OpenWebUI core patches and keeps binary generation isolated in sidecar tests.

### Option 3: Loader + Browser DOCX Library

Verdict: **not recommended for MVP**.

It can produce direct downloads without server work, but makes the static loader
large and harder to audit. Sanitization and deterministic DOCX tests are weaker.

### Option 4: Sidecar + OpenWebUI File API

Verdict: **future hardening path**.

This is attractive for large files and auditability, but first requires proof of
ownership/access parity and retention behavior.

## 21. Recommended Implementation Sequence

Gate A: selector/API proof

- verify assistant message selectors in live browser;
- verify button insertion does not duplicate after rerenders;
- verify chat id and message id derivation;
- verify same-origin `GET /api/v1/chats/{chat_id}` works from loader context;
- if API proof fails, fall back to DOM extraction for MVP.

Gate B: sidecar DOCX contract

- add request/result models;
- add `python-docx`;
- generate simple DOCX from a contract payload;
- validate checksum, content type and filename;
- add generated-DOCX no-leak scan.

Gate C: Action bridge

- add `stage2_message_docx_export_action`;
- prove authenticated user context;
- prove typed refusals;
- prove no internal URL or token is returned.

Gate D: loader UX

- inject icon for completed assistant messages only;
- call Action bridge;
- save DOCX with `showSaveFilePicker` when available and object URL fallback
  otherwise;
- handle failures without appending text to chat.

Gate E: runtime proof

- manual browser click on a normal LLM answer;
- manual browser click on an STT raw transcript message;
- manual browser click on an STT post-processing result;
- open generated DOCX with `python-docx`;
- scan extracted DOCX XML for forbidden markers.

## 22. Test And Proof Plan

Unit tests:

- contract validation accepts valid assistant message request;
- contract validation refuses user/system/unknown role in MVP;
- empty and whitespace-only messages are refused;
- too-large messages are refused;
- filename sanitizer handles Russian, spaces and unsafe characters;
- sanitizer strips scripts, styles, event handlers and hidden controls;
- markdown conversion handles paragraphs, headings, lists and code blocks;
- generated DOCX has correct MIME type and checksum;
- generated DOCX ZIP/XML contains selected message content;
- generated DOCX ZIP/XML excludes forbidden marker families.

Action tests:

- Action derives user context from OpenWebUI `__user__`;
- Action refuses malformed payloads;
- Action maps sidecar typed refusals to safe user-visible refusals;
- Action does not return sidecar hostnames, stack traces or env names;
- Action timeout returns typed failure.

Loader tests:

- button appears on completed assistant messages;
- button does not appear on user messages;
- button does not appear on streaming/incomplete responses;
- no duplicate button after `MutationObserver` rescans;
- scoped extraction does not include previous or next messages;
- missing selectors produce a no-op, not an exception loop;
- object URL fallback triggers a download and revokes the URL.

Runtime proof:

- run against a normal assistant message;
- run against STT raw transcript output;
- run against post-processing output;
- test desktop and mobile-width toolbar behavior;
- verify STT transcription and quick actions still work after loader change;
- verify OpenWebUI normal chat works after Action/sidecar failures.

Upgrade-safety checks:

- source diff check for `Message.svelte` and `ResponseMessage.svelte` selectors
  on OpenWebUI upgrades;
- smoke test that loader degradation is silent if toolbar/content selectors move;
- smoke test that native Actions still render and the existing STT Action still
  responds.

## 23. Risks

Selector drift:

OpenWebUI DOM is not a public extension API. Mitigation: scoped selectors,
feature flags, no-op degradation and upgrade smoke checks.

Binary delivery through Action:

Direct JSON/base64 works for small DOCX files but is not ideal for large output.
Mitigation: strict size limits in MVP, later `download_url` or
`openwebui_file_id` delivery mode.

Accidental content leakage:

DOM extraction can capture toolbar text or adjacent content if scoped poorly.
Mitigation: prefer chat API source after proof, clone only scoped content, strip
controls and scan generated DOCX.

Native Action mismatch:

If the Action endpoint changes behavior across OpenWebUI versions, the loader
bridge can break. Mitigation: keep Action contract isolated, test
`/api/chat/actions/{id}` during deploy, and make the loader hide the button when
the bridge is unavailable.

Large messages:

Very long transcripts may generate oversized DOCX payloads. Mitigation: typed
refusal in MVP; later file-backed delivery or chunked document generation.

## 24. Open Questions Before Coding

1. Should the DOCX button be visible for all completed assistant messages by
   default, or only after a feature flag enables it globally?
2. What exact max message size should product accept for MVP: 60000, 100000 or
   another threshold?
3. Should successful export show a small toast, or stay silent after the browser
   download starts?
4. Should filename include chat title, timestamp, or both?
5. Should the Action be visible as a native OpenWebUI Action fallback, or used
   only as a loader bridge?

Recommended defaults:

- enable by feature flag first;
- `100000` characters max input;
- success toast only if the browser download API does not visibly prompt;
- filename: sanitized chat title plus timestamp;
- Action as bridge first, native visible Action fallback only after proof.

## 25. Files Likely To Change In Implementation

Expected docs:

- `docs/stage2/contracts/STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md`
- `docs/stage2/operations/STT_V2_MESSAGE_DOCX_EXPORT_RUNBOOK.md`
- implementation proof report under `docs/reports/YYYY-MM-DD/`

Expected sidecar code:

- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/app.py`
- new DOCX renderer module under `services/stage2-stt/stage2_stt/`
- `services/stage2-stt/pyproject.toml`
- sidecar tests under `services/stage2-stt/tests/`

Expected Action code:

- OpenWebUI Action source under the existing sidecar/openwebui action packaging
  path used by STT v2.

Expected loader code:

- `deploy/openwebui-static/loader.js`
- optional static config file if feature flags and limits are loaded client-side.

Expected deployment files:

- only if dependency installation or sidecar image build requires an update;
- no OpenWebUI core source changes.

## 26. Final Recommendation

Proceed with a narrow implementation slice:

```text
assistant message only
single selected message only
loader button
Action bridge
sidecar python-docx renderer
base64 delivery
browser save fallback
strict no-leak scan
safe no-op degradation
```

Do not implement STT-specific DOCX first. It solves a narrower problem and would
duplicate the generic user need: exporting the useful visible result of an LLM
message. Keep structured STT artifact export as a later specialized mode once
generic message-level DOCX is proven.
