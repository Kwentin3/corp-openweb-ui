# STT v2 Message-Level DOCX Export Implementation Proof

Status: implemented, pushed and deployed to PRD-0; manual authenticated browser click proof pending.

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
D:\Users\Roman\Desktop\Проекты\corp-openweb ui
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
