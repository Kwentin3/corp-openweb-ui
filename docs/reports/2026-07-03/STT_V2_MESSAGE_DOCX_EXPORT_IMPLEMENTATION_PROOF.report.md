# STT v2 Message-Level DOCX Export Implementation Proof

Status: implemented, pushed and deployed to PRD-0; authenticated browser click
proof confirmed by operator.

Date: 2026-07-03.

## 1. Executive Summary

Gate 8 MVP is implemented and deployed as a message-level DOCX export for
completed assistant messages.

Implemented contour:

```text
completed assistant message toolbar
-> static loader DOCX button
-> existing OpenWebUI Action bridge operation export_message_docx
-> stage2-stt sidecar endpoint POST /stage2-api/message-docx/exports
-> python-docx renderer
-> generated DOCX no-leak scan
-> base64 result
-> browser save/download
```

OpenWebUI core was not patched.

## 2. Changed Runtime Surface

Contracts:

- `MessageDocxExportRequestV1`
- `MessageDocxExportResultV1`
- `MessageDocxSafeMetadataV1`
- `MessageDocxExportOptionsV1`

Sidecar:

- new DOCX renderer/factory module: `stage2_stt.message_docx`
- new internal-auth endpoint: `POST /stage2-api/message-docx/exports`
- new dependency: `python-docx`
- new config:

```text
STAGE2_STT_MESSAGE_DOCX_MAX_MESSAGE_CHARS=100000
STAGE2_STT_MESSAGE_DOCX_MAX_DOCX_MB=5
```

Action bridge:

- existing `stage2_media_transcription_action` now accepts
  `stage2_message_docx.operation=export_message_docx`;
- success returns `stage2_message_docx_export`;
- failures return `stage2_message_docx_error`;
- `content` remains empty for DOCX operations.

Loader:

- scans completed assistant message roots;
- requires scoped `.chat-assistant.markdown-prose`;
- requires `.buttons` toolbar;
- uses `.copy-response-button` as completion hint;
- injects one `data-stage2-docx-export` button per eligible message;
- extracts only selected scoped assistant message content;
- downloads through `showSaveFilePicker` when available, otherwise Blob URL and
  `<a download>`.

## 3. No-Leak Guard

The sidecar scans generated DOCX ZIP parts before returning the result:

```text
word/document.xml
docProps/core.xml
docProps/app.xml
word/_rels/document.xml.rels
_rels/.rels
```

The tests prove refusal for sentinel leakage before DOCX return and openability
of the generated package through `python-docx`.

## 4. Local Verification

Commands run from:

```text
<repository-root>
shell=powershell
```

Dependency installation to align local environment with the sidecar artifact:

```text
python -m pip install -e "services/stage2-stt[test]"
```

Focused verification:

```text
python -m pytest -q services/stage2-stt/tests/test_message_docx.py services/stage2-stt/tests/test_openwebui_action.py services/stage2-stt/tests/test_loader_static.py services/stage2-stt/tests/test_config.py
36 passed in 1.23s
```

Full sidecar verification:

```text
python -m pytest -q services/stage2-stt/tests
85 passed in 3.08s
```

Compile/syntax checks:

```text
python -m compileall -q services/stage2-stt
pass

node --check deploy/openwebui-static/loader.js
pass
```

Closed-world packaging proof:

```text
docker build -f services/stage2-stt/Dockerfile -t corp-openwebui-stage2-stt:gate8-local .
failed before project build steps: local Docker utility VM kernel was unavailable

python -m pip wheel --no-deps --wheel-dir local\gate8-wheel-proof services/stage2-stt
Successfully built openwebui-stage2-stt

wheel contains:
openwebui_actions/stage2_media_transcription_action.py
stage2_stt/app.py
stage2_stt/message_docx.py
openwebui_stage2_stt-0.1.0.dist-info/METADATA

wheel metadata:
Requires-Dist: python-docx<2,>=1.1
```

Interpretation:

The local Docker daemon did not reach application build because the local
container utility VM was missing its kernel. The package-level artifact proof
confirms that the new runtime module and dependency declaration are in the
installable sidecar artifact. Server-side Docker build/recreate remains required
before marking runtime deployment complete.

Primary failure attribution during implementation:

```text
test_message_docx_export_generates_openable_docx_with_selected_message_only
expected generated DOCX to contain markdown heading; actual fixture left old
message_markdown while overriding message_text. Fixed the fixture to match the
contract precedence: renderer prefers message_markdown when provided.
```

## 5. Acceptance Matrix

| Criterion | Status | Evidence |
| --- | --- | --- |
| DOCX button appears on completed assistant messages | Local static proof | Loader scans assistant roots and completion hint. Browser proof pending. |
| No DOCX button for user messages in MVP | Local static proof | Loader requires `.chat-assistant.markdown-prose`. |
| No duplicate button after rerender | Local static proof | Loader checks `data-stage2-docx-export`. |
| Export uses only selected message | Local unit/static proof | Scoped extraction and sentinels absent in DOCX test. |
| No previous/next messages | Local unit proof | Sentinel absence asserted. |
| No toolbar text/icons | Local unit/static proof | Extraction removes controls; sentinel absence asserted. |
| Valid `.docx` | Pass | Opened with `python-docx`. |
| Readable selected content | Pass | Paragraph/list/heading/code assertions. |
| Sidecar generation | Pass | Renderer lives in `stage2_stt.message_docx`; route uses service. |
| Browser save/download | Local static proof | `showSaveFilePicker` and Blob URL fallback present. Browser proof pending. |
| No raw provider payload/prompt/secrets | Local proof | No-leak scanner and tests. |
| Existing STT quick actions still work | Local regression proof | Full `services/stage2-stt/tests` passed. Browser proof pending. |
| OpenWebUI core unpatched | Pass | No OpenWebUI core source changed. |
| Failure paths typed and safe | Pass | Route and Action tests assert typed error shapes. |

## 6. Runtime Deployment

Implementation commit:

```text
bea93c1 feat: add message docx export
```

Server git state:

```text
target=/opt/openwebui-prd0
git status: ## main...origin/main
HEAD=bea93c1
```

Sidecar build/recreate:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt

build installed:
python-docx-1.2.0

stage2_image_id=sha256:4eb259c6e037cf08fafb8e9210be26aec0a0554fcddeb0195161c7ec58231298
stage2_container_image=sha256:4eb259c6e037cf08fafb8e9210be26aec0a0554fcddeb0195161c7ec58231298
```

Runtime config/import proof:

```text
python_docx_import=True
message_docx_max_message_chars=100000
message_docx_max_docx_mb=5
artifact_store_mode=sqlite
```

OpenWebUI Action DB update:

```text
backup_dir=/opt/openwebui-prd0/backups/codex-stt-v2/20260703T104928Z-message-docx-export
rows_updated=1
file_sha256=766bdb0ce575f5a43272e39cf97d03a1a8e8dcd04653b52a17ae5fbdab3d1e20
db_sha256=766bdb0ce575f5a43272e39cf97d03a1a8e8dcd04653b52a17ae5fbdab3d1e20
has_export_operation=True
has_docx_endpoint=True
```

OpenWebUI restart/health:

```text
openwebui_health=healthy
openwebui: Up / healthy
stage2-stt: Up
```

Static loader proof:

```text
host_loader_sha256=33d32b94edbb13aab331bd0cf4edb5d5a98792fddfb0c0cfce73c80be5c2f56b
container_loader_sha256=33d32b94edbb13aab331bd0cf4edb5d5a98792fddfb0c0cfce73c80be5c2f56b
public_loader_sha256=33d32b94edbb13aab331bd0cf4edb5d5a98792fddfb0c0cfce73c80be5c2f56b
public_loader_has_export_message_docx=True
```

Public HTTPS proof:

```text
https://gpt.alpha-soft.ru/ -> HTTP 200
```

Runtime sidecar DOCX endpoint proof:

```text
POST http://127.0.0.1:8080/stage2-api/message-docx/exports from stage2-stt container
status_code=200
schema_version=MessageDocxExportResultV1
delivery=base64
content_type=application/vnd.openxmlformats-officedocument.wordprocessingml.document
size_bytes=37017
checksum_ok=True
docx_openable=True
selected_present=True
previous_absent=True
next_absent=True
no_stage2_internal_token=True
no_authorization=True
no_bearer=True
no_cookie=True
no_provider_payload=True
```

Recent log scan:

```text
stage2-stt logs since deploy:
no traceback/exception/error/secret/raw-provider markers

openwebui logs since restart:
startup emitted read-only static loader filesystem warnings because loader.js is
bind-mounted read-only; service continued to healthy and served /static/loader.js
with HTTP 200.
```

Manual authenticated browser proof still required:

```text
click DOCX under a completed assistant message
verify browser save prompt/download
open downloaded DOCX locally
repeat on STT transcript and STT post-processing result
```

## 7. Current Verdict

```text
SERVER_SIDE_PASS_BROWSER_MANUAL_PENDING
```

## 8. Follow-Up: DOCX Action HTTP 400

Observed browser symptom after initial deploy:

```text
DOCX export failed with HTTP 400. [message_docx_generation_failed]
```

Runtime log boundary:

```text
POST /api/chat/actions/stage2_media_transcription_action -> HTTP 400
no corresponding sidecar /stage2-api/message-docx/exports call
```

Root cause:

The message-level DOCX loader called the native OpenWebUI Action endpoint with
only `stage2_message_docx`. OpenWebUI's Action wrapper validates and reads the
standard chat action envelope before calling the custom Action code, including
`id`, `chat_id`, `session_id`, `model`, and `messages`. Because these fields
were absent, the request failed at the OpenWebUI Action boundary and never
reached the sidecar DOCX generator.

Fix:

`callMessageDocxAction(request)` now sends the same native Action envelope shape
used by the STT and post-processing loader calls:

```text
id
chat_id
session_id
model
messages
stage2_message_docx.operation=export_message_docx
```

Regression proof added:

```text
test_loader_docx_action_payload_includes_openwebui_action_envelope
```

Local verification after fix:

```text
python -m pytest -q services/stage2-stt/tests
86 passed in 3.05s

python -m compileall -q services/stage2-stt
pass

node --check deploy/openwebui-static/loader.js
pass

git diff --check
pass
```

Follow-up implementation commit:

```text
b834cc2 fix: include action envelope for docx export
```

Server deployment:

```text
target=/opt/openwebui-prd0
git pull --ff-only origin main
HEAD=b834cc2
```

Static loader remount note:

After `git pull`, the host file changed but the OpenWebUI container still saw
the old bind-mounted file inode:

```text
host_loader_sha256=ea92e94d68daf3571991b644a769d137d6f97ea2763d9f29860fc386d331898c
container_loader_sha256=33d32b94edbb13aab331bd0cf4edb5d5a98792fddfb0c0cfce73c80be5c2f56b
public_loader_sha256=33d32b94edbb13aab331bd0cf4edb5d5a98792fddfb0c0cfce73c80be5c2f56b
```

To make the static loader update effective, only the OpenWebUI container was
recreated with `--force-recreate --no-deps openwebui`. The sidecar was not
rebuilt because the runtime sidecar code did not change.

Post-remount runtime proof:

```text
host_loader_sha256=ea92e94d68daf3571991b644a769d137d6f97ea2763d9f29860fc386d331898c
container_loader_sha256=ea92e94d68daf3571991b644a769d137d6f97ea2763d9f29860fc386d331898c
public_loader_sha256=ea92e94d68daf3571991b644a769d137d6f97ea2763d9f29860fc386d331898c
public_loader_has_docx_id_fallback=True
public_loader_has_messages_envelope=True
public_loader_has_chat_id_envelope=True
public_loader_has_model_envelope=True
openwebui: Up / healthy
stage2-stt: Up
https://gpt.alpha-soft.ru/ -> HTTP 200
```

Follow-up verdict:

```text
SERVER_LOADER_ENVELOPE_FIX_DEPLOYED_BROWSER_RETRY_PENDING
```

## 9. Follow-Up: Semantic Chat Formatting Gap

Observed product gap after successful browser download:

```text
The DOCX export is scoped and openable, but rich assistant-message formatting is
simplified compared with the chat view.
```

Current implementation boundary:

- loader extracts scoped visible text from the selected assistant message;
- `message_text` and `message_markdown` are populated from that plain-text
  extraction;
- `message_html` is null;
- sidecar renderer uses the `simple_mvp` profile and a small markdown subset.

Interpretation:

The behavior is consistent with the implemented MVP, but it does not satisfy the
new product expectation that "DOCX exports what the user sees in chat" for rich
messages containing tables, nested lists, links, blockquotes or code blocks.

Documentation/contract follow-up:

- `STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md` now defines the target
  `semantic_chat_v1` formatting profile;
- `semantic_chat_v1` requires structured markdown or sanitized selected-message
  HTML before falling back to plain text;
- `simple_mvp` remains the implemented compatibility profile until code and proof
  are added;
- future implementation must prove semantic fixtures, sanitizer behavior,
  no-leak checks and typed degradation/refusal.

Follow-up verdict:

```text
DOCX_DELIVERY_MVP_PASS_SEMANTIC_FORMATTING_TARGET_DOCUMENTED
```

## 10. Follow-Up: Semantic Chat Formatting Implementation

Implementation summary:

- loader now builds `semantic_chat_v1` requests when sanitized selected-message
  HTML is available;
- loader no longer sets `message_markdown` to a plain-text duplicate;
- sidecar accepts `semantic_chat_v1` in `MessageDocxFormattingProfileV1`;
- sidecar renders semantic HTML through the existing `DocxExportAdapterFactory`
  path without adding a new runtime dependency;
- sidecar preserves headings, paragraphs, lists, tables, blockquotes, links and
  code blocks as DOCX document semantics;
- `simple_mvp` remains available as fallback when structured source is absent;
- fallback returns `message_docx_formatting_degraded`;
- unsafe HTML links return typed refusal `message_docx_unsafe_html`.

Local proof:

```text
python -m pytest -q services/stage2-stt/tests/test_message_docx.py
13 passed in 1.50s

python -m pytest -q services/stage2-stt/tests/test_loader_static.py
10 passed in 0.46s

python -m pytest -q services/stage2-stt/tests/test_openwebui_action.py
14 passed in 0.74s

python -m pytest -q services/stage2-stt/tests
98 passed in 3.53s

python -m compileall -q services/stage2-stt
pass

node --check deploy/openwebui-static/loader.js
pass
```

Acceptance added:

- semantic HTML fixture preserves visible chat structure in generated DOCX;
- generated DOCX contains a real table instead of flattened table text;
- generated DOCX contains a hyperlink relationship;
- fallback warning is asserted when structured source is unavailable;
- unsafe JavaScript link is rejected through typed sidecar error;
- loader static proof asserts `message_markdown: null`,
  `message_html: html`, and `semantic_chat_v1` request selection.

Follow-up verdict:

```text
SEMANTIC_DOCX_LOCAL_PASS_SERVER_DEPLOY_PENDING
```

## 11. Follow-Up: Semantic Chat Formatting Deployment

Implementation commit:

```text
c6826df feat: preserve chat formatting in docx export
```

Server deployment:

```text
target=/opt/openwebui-prd0
git pull --ff-only origin main
HEAD=c6826df
docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate --no-deps openwebui
openwebui_health=healthy
```

Runtime image proof:

```text
stage2_image_id=sha256:ac3f2187266109cfcc585fb02fde16388684b76b05fe3575c5957f42c4edfe2e
openwebui_image_id=sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175
```

Runtime semantic sidecar proof:

```text
POST /stage2-api/message-docx/exports semantic_chat_v1
semantic_status_code=200
schema_ok=True
delivery_ok=True
warnings_empty=True
heading_present=True
nested_list_present=True
blockquote_present=True
code_present=True
table_header_present=True
table_row_present=True
hyperlink_present=True
no_internal_token=True

POST /stage2-api/message-docx/exports with javascript: link
unsafe_status_code=422
unsafe_code=message_docx_unsafe_html
```

Public loader proof:

```text
host_loader_sha256=17c15f71cb8ffc3b28b4df26b6e53350e8b57e341e5b002a48421def5da2f8b9
container_backend_loader_sha256=17c15f71cb8ffc3b28b4df26b6e53350e8b57e341e5b002a48421def5da2f8b9
public_loader_sha256=17c15f71cb8ffc3b28b4df26b6e53350e8b57e341e5b002a48421def5da2f8b9
public_loader_has_semantic_chat_v1=True
public_loader_has_message_markdown_null=True
```

`/app/build/static/loader.js` in the OpenWebUI container is an empty non-served
artifact. The served public file matches
`/app/backend/open_webui/static/loader.js` and the host bind-mounted loader.

Public HTTPS proof:

```text
https://gpt.alpha-soft.ru/ -> HTTP 200
```

Recent log scan:

```text
stage2-stt logs since deploy:
startup OK, semantic DOCX probe returned 200, unsafe HTML probe returned 422

openwebui logs since recreate:
service healthy; startup emitted the known read-only static loader filesystem
warnings because loader.js is bind-mounted read-only.
```

Browser-authenticated save-dialog proof is still a manual UX check. Server-side
generation, public loader delivery and typed unsafe-HTML refusal are proven.

Follow-up verdict:

```text
SEMANTIC_DOCX_SERVER_SIDE_PASS_BROWSER_MANUAL_RECOMMENDED
```

## 12. Follow-Up: Markdown-First DOCX Source Refactor

Reason:

- a user-provided DOCX generated after the semantic rollout preserved the first
  rendered part of the assistant answer but lost the markdown table and tail
  content after a horizontal rule;
- audit showed the served loader sent sanitized DOM HTML with
  `message_markdown: null`, while the sidecar renderer preferred HTML over
  structured markdown;
- this contradicted the intended contract precedence: canonical OpenWebUI
  message markdown first, DOM HTML second, plain text fallback last.

Implementation changes:

- `deploy/openwebui-static/loader.js`
  - `buildMessageDocxRequest` is now async;
  - the loader fetches `/api/v1/chats/{chat_id}` with `cache: no-store`;
  - it searches common OpenWebUI chat shapes:
    `chat.messages`, `chat.history.messages`, `messages`,
    `history.messages`;
  - it extracts canonical message content from `content`, `text` or `message`;
  - when canonical markdown is found, request source becomes
    `openwebui_chat_api`;
  - sanitized DOM HTML remains as fallback and is still sent for resilience;
  - empty/whitespace markdown safely degrades to `null`;
  - duplicate `currentChatId` behavior was collapsed to the later shared helper,
    now supporting both `/c/{id}` and `/chat/{id}`.

- `services/stage2-stt/stage2_stt/message_docx.py`
  - `semantic_chat_v1` now renders structured `message_markdown` before
    `message_html`;
  - `message_html` remains fallback when canonical markdown is missing or not
    structured.

- `docs/stage2/contracts/STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md`
  - status and validation wording now state markdown-first semantic export;
  - acceptance explicitly requires proof that markdown wins over truncated DOM
    HTML.

- `docs/stage2/operations/STT_V2_MESSAGE_DOCX_EXPORT_RUNBOOK.md`
  - runtime behavior now documents markdown -> sanitized HTML -> plain text
    source precedence;
  - manual proof now includes content after markdown horizontal rules.

Regression tests added:

- renderer test proves structured markdown with a table after `---` wins over a
  truncated HTML source and preserves:
  - the `Action items` heading;
  - the markdown table as a real DOCX table;
  - the paragraph after the table;
  - absence of the HTML-only truncated marker.
- loader static tests prove:
  - request construction awaits canonical markdown fetch;
  - `message_markdown` is populated from canonical markdown, not plain text;
  - source becomes `openwebui_chat_api` only when markdown is present;
  - OpenWebUI chat API fetch uses no-store and supports current known message
    containers.

Local verification:

```text
python -m pytest -q services/stage2-stt/tests/test_message_docx.py services/stage2-stt/tests/test_loader_static.py
25 passed in 1.57s

python -m pytest -q services/stage2-stt/tests
100 passed in 3.42s

python -m compileall -q services/stage2-stt
pass

node --check deploy/openwebui-static/loader.js
pass

git diff --check
pass with Windows LF/CRLF Git warnings only
```

Local verdict:

```text
MARKDOWN_FIRST_DOCX_LOCAL_PASS_SERVER_DEPLOY_PENDING
```

Deployment commit:

```text
5341b78 feat: render docx from canonical markdown
```

Server deployment:

```text
target=/opt/openwebui-prd0
git pull --ff-only origin main
HEAD=5341b78
docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate --no-deps openwebui
openwebui_status=Up healthy
stage2_stt_status=Up
```

Runtime image proof:

```text
stage2_image_id=sha256:73db807e05756cade3caa547e9ed6975bc68c4f725d1bf3d39f10b2c079c0073
openwebui_image_id=sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175
```

Public loader proof:

```text
host_loader_sha256=3abc19eab98e6a26db39543c93a9b40930e019f58d48174d48fa44f85d6c4db5
container_backend_loader_sha256=3abc19eab98e6a26db39543c93a9b40930e019f58d48174d48fa44f85d6c4db5
public_loader_sha256=3abc19eab98e6a26db39543c93a9b40930e019f58d48174d48fa44f85d6c4db5
public_loader_has_fetchCanonicalMessageMarkdown=True
public_loader_has_api_v1_chats=True
public_loader_has_message_markdown_markdown=True
public_loader_has_openwebui_chat_api_source=True
public_loader_has_message_markdown_null=False
https://gpt.alpha-soft.ru/ -> HTTP 200
```

Runtime markdown-first sidecar proof:

```text
POST /stage2-api/message-docx/exports semantic_chat_v1
payload: message_markdown includes heading, horizontal rule, markdown table and tail paragraph
payload: message_html is intentionally truncated and contains DOM-only marker

status_code=200
schema_ok=True
delivery_ok=True
warnings=[]
action_heading_present=True
tail_present=True
truncated_marker_absent=True
table_header_present=True
table_row_present=True
no_internal_token=True
size_bytes=37143
```

Recent log scan:

```text
stage2-stt logs since deploy:
startup OK; runtime markdown-first DOCX proof returned 200

openwebui logs since recreate:
service healthy; startup emitted the known read-only static loader filesystem
warnings because loader.js is bind-mounted read-only.
```

Remaining manual proof:

- an authenticated browser export should be repeated on a real assistant message
  with a markdown table after `---`;
- automated proof verifies that the public loader ships markdown-first code and
  that the sidecar renders markdown before truncated HTML, but it does not hold
  an authenticated OpenWebUI browser session to prove the live `/api/v1/chats`
  response shape for a real user chat.

Follow-up verdict:

```text
MARKDOWN_FIRST_DOCX_SERVER_SIDE_PASS_BROWSER_MANUAL_RECOMMENDED
```

## 13. Operator Browser Proof Closeout

Operator result reported after the markdown-first deployment:

```text
browser_docx_export_ok=True
save_dialog_ok=True
downloaded_docx_opens=True
message_level_export_ok=True
markdown_table_formatting_ok=True
```

Interpretation:

- the remaining browser-authenticated proof gap from section 12 is closed by
  operator manual testing;
- the canonical runtime status is now markdown-first semantic DOCX export for
  selected completed assistant messages;
- specialized processed-result-only DOCX artifact delivery remains future work,
  separate from the implemented generic message-level exporter.

Current verdict:

```text
MARKDOWN_FIRST_DOCX_FEATURE_CLOSED_FOR_CURRENT_SCOPE
```
