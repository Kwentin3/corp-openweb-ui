# STT v2 Message-Level DOCX Export Contract

Status: implemented MVP contract plus implemented markdown-first semantic
formatting extension.

Date: 2026-07-03.

## 1. Purpose

Gate 8 adds a generic OpenWebUI message-level DOCX export. It exports one
selected completed assistant message, not a whole chat and not an STT-only
artifact.

The implemented MVP proves safe delivery and selected-message scoping. The
semantic chat export extension preserves the user-visible structure of the
selected chat message as document semantics when a structured source is
available, instead of flattening rich chat output into plain text.

Primary route:

```text
Completed assistant message toolbar
-> static loader DOCX button
-> OpenWebUI Action bridge
-> stage2-stt sidecar
-> DOCX base64 result
-> browser save/download
```

OpenWebUI core remains unpatched.

Semantic fidelity means:

- preserve visible headings, paragraphs, lists, tables, quotes, links and code
  blocks where the selected message contains them;
- preserve basic inline emphasis as Word runs where source structure exists;
- avoid pixel-perfect CSS cloning, theme replication or chat chrome export;
- degrade explicitly when only plain text is available.

## 2. Eligibility

MVP allows export only for:

- completed assistant messages;
- non-empty selected message content;
- one selected message per click;
- scoped visible content extracted under the selected assistant message root.

MVP refuses or does not show the button for:

- user messages;
- streaming/incomplete messages;
- empty messages;
- missing or ambiguous safe content selectors;
- messages above configured limits.

## 3. Request Contract

`MessageDocxExportRequestV1`:

```json
{
  "schema_version": "MessageDocxExportRequestV1",
  "request_id": "string",
  "chat_id": "string | null",
  "message_id": "string | null",
  "message_role": "assistant",
  "message_text": "string",
  "message_markdown": "string | null",
  "message_html": "string | null",
  "source": "openwebui_chat_api | dom | action_body | artifact",
  "safe_metadata": {
    "chat_title": "string | null",
    "model_name": "string | null",
    "message_timestamp": "string | null",
    "source_url_path": "string | null",
    "result_ref": "string | null"
  },
  "options": {
    "include_chat_title": true,
    "include_model_name": true,
    "include_timestamp": true,
    "formatting_profile": "simple_mvp | semantic_chat_v1"
  }
}
```

Validation:

- `schema_version` must match exactly.
- `message_role` must be `assistant`; other roles return
  `message_docx_unsupported_role`.
- `message_text` must be non-empty after trimming.
- `message_text` must fit `STAGE2_STT_MESSAGE_DOCX_MAX_MESSAGE_CHARS`.
- `safe_metadata` is allow-listed.
- `source_url_path` must be an application path, not a full external/internal URL.
- `formatting_profile=simple_mvp` is the current implemented compatibility
  profile.
- `formatting_profile=semantic_chat_v1` is the implemented semantic extension
  profile.
- `message_text` is always the required plain-text fallback and extraction
  safety source.
- `message_markdown` must contain real markdown/source markdown when provided.
  It must not be populated with plain text only to satisfy a field.
- `message_html` must contain sanitized selected-message HTML only when provided.
  It is ignored by the implemented `simple_mvp` renderer and is the fallback
  structured source for the implemented `semantic_chat_v1` renderer when
  canonical markdown is unavailable or not structured.
- Browser-provided identity and hidden runtime fields are not trusted.

Structured source precedence for `semantic_chat_v1`:

1. canonical OpenWebUI message markdown, if available through a safe native
   message source;
2. sanitized rendered HTML scoped to the selected assistant message root;
3. plain text fallback with a `message_docx_formatting_degraded` warning.

The loader must not silently convert a rich message to plain text when a
structured source can be extracted safely. If structured extraction fails, it
must either fall back with a typed warning or return a typed refusal.

## 4. Result Contract

`MessageDocxExportResultV1`:

```json
{
  "schema_version": "MessageDocxExportResultV1",
  "export_id": "string",
  "filename": "string.docx",
  "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 12345,
  "checksum_sha256": "hex",
  "delivery": "base64",
  "download_payload_base64": "base64",
  "download_url": null,
  "file_id": null,
  "warnings": []
}
```

MVP delivery is only `base64`. `download_url` and `file_id` remain null until a
separate OpenWebUI file API or temporary-download proof exists.

Warnings may include:

```text
message_docx_formatting_degraded
message_docx_html_sanitized
message_docx_unsupported_semantic_node
```

Warnings are user-safe and must not include raw HTML, prompt bodies, internal
selectors, provider payloads, tokens or internal URLs.

## 5. Endpoint

Sidecar endpoint:

```text
POST /stage2-api/message-docx/exports
```

Authentication:

- requires existing sidecar internal auth;
- accepts `Authorization: Bearer <internal-token>` or
  `X-Stage2-Internal-Token`;
- no public unauthenticated DOCX endpoint.

The OpenWebUI Action bridge is responsible for taking user context from the
Action runtime. Browser-provided user identity is not trusted.

## 6. Config

Server-side env:

```text
STAGE2_STT_MESSAGE_DOCX_MAX_MESSAGE_CHARS=100000
STAGE2_STT_MESSAGE_DOCX_MAX_DOCX_MB=5
```

Defaults are conservative and loaded through `stage2_stt.config.load_stt_config`.

## 7. DOCX Layout And Formatting Profiles

MVP layout:

- title: `Exported Assistant Message`;
- metadata table with export time and optional safe chat/model/message metadata;
- selected assistant message content;
- footer: `Generated by STT v2 extension layer`.

`simple_mvp` formatting:

- paragraphs;
- headings;
- bullet lists;
- numbered lists;
- simple monospace code block rendering;
- tables flattened as readable text.

`semantic_chat_v1` formatting:

- headings map to Word heading styles;
- paragraphs and blank-line separation are preserved as paragraphs;
- unordered and ordered lists preserve nesting for at least three visible levels;
- tables preserve rows, columns, header cells when detectable, and multiline cell
  text;
- blockquotes preserve quote grouping;
- fenced/preformatted code preserves monospaced code blocks and line breaks;
- inline strong, emphasis and inline code are preserved where source structure
  exists;
- links preserve display text and URL in a safe Word hyperlink representation;
- speaker-labelled transcript blocks remain readable as speaker-separated
  paragraphs or a simple two-column table when the source is structured that way.

`semantic_chat_v1` must not export:

- chat toolbar controls, buttons, icons, avatars or status labels;
- hidden prompts, hidden config or data attributes;
- raw unsanitized HTML;
- scripts, styles, event handlers or external resource loads;
- images, attachments and tool artifacts in the first semantic slice.

Pixel-perfect chat CSS parity is explicitly not a goal. The goal is semantic
document parity: a DOCX reader should see the same information hierarchy and
tables/lists/code structure that the user saw in chat.

Images, attachments and tool artifacts are not included.

## 8. No-Leak Rules

DOCX must not contain:

- full chat history;
- neighboring messages;
- user prompts;
- raw LemonFox/provider JSON;
- prompt bodies;
- hidden system/developer instructions;
- tokens, cookies or API keys;
- internal service URLs;
- OpenWebUI internal file paths;
- toolbar labels, icons or status controls;
- debug logs.

The sidecar scans generated DOCX ZIP parts before returning:

```text
word/document.xml
docProps/core.xml
docProps/app.xml
word/_rels/document.xml.rels
_rels/.rels
```

Failure returns `message_docx_no_leak_check_failed`.

## 9. Typed Refusals

Implemented refusal codes:

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

Target semantic-extension refusal codes:

```text
message_docx_unsupported_formatting_profile
message_docx_unsafe_html
message_docx_structured_source_unavailable
```

`message_docx_structured_source_unavailable` is required only when the caller
requests strict semantic export without plain-text fallback. The default browser
flow may fall back to `simple_mvp` semantics with
`message_docx_formatting_degraded`.

The loader must not append refusal text into chat content. It may show a local
button state or status.

## 10. Update-Safety

OpenWebUI source is not patched. The fragile boundary is the static loader DOM
selector layer. Loader rules:

- scope all extraction under the selected message root;
- require `.chat-assistant.markdown-prose`;
- require a toolbar `.buttons`;
- use `.copy-response-button` as a completion hint;
- never query duplicate `#response-content-container` globally;
- prefer canonical message markdown over DOM text when a safe native source is
  available;
- when using DOM, preserve sanitized semantic HTML for `semantic_chat_v1` instead
  of relying on `innerText`/`textContent` only;
- never set `message_markdown` to plain text if markdown is unavailable;
- no-op safely when selectors are absent.

## 11. Acceptance For Semantic Chat Export

`semantic_chat_v1` implementation must keep these checks green:

- exported DOCX must preserve at least one fixture each for headings, paragraphs,
  nested bullet lists, numbered lists, tables, blockquotes, code blocks, links and
  inline emphasis;
- a rich fixture must prove that tables are not flattened into plain text;
- a loader test must prove that the browser first attempts canonical OpenWebUI
  message markdown and that `message_markdown` is not a duplicate of plain text
  unless the source is actually markdown;
- a renderer test must prove that structured `message_markdown` wins over
  truncated or incomplete DOM HTML when both are provided;
- an HTML sanitizer test must prove scripts, styles, event handlers, hidden
  config and data attributes are removed before rendering;
- a generated DOCX no-leak scan must pass on semantic fixtures;
- a fallback test must prove a typed warning or typed refusal when only plain
  text can be sourced;
- existing `simple_mvp` behavior must remain available as a compatibility
  fallback.
