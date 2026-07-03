# STT v2 Message-Level DOCX Export Implementation Proof

Status: local implementation verified; runtime deployment pending.

Date: 2026-07-03.

## 1. Executive Summary

Gate 8 MVP is implemented locally as a message-level DOCX export for completed
assistant messages.

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

Runtime deployment is pending at the time of this initial local proof report.

Required after commit/push:

```text
server pull/fast-forward
rebuild stage2-stt
update OpenWebUI Action DB content
restart/recreate OpenWebUI if needed
verify HTTPS 200
verify sidecar endpoint through Docker network
manual authenticated browser export proof if credentials/session are available
```

## 7. Current Verdict

```text
LOCAL_PASS_RUNTIME_PENDING
```
