# OpenWebUI STT Frontend Media Action Patch Report

Date: 2026-06-19

## Verdict

`prepared_mp3_frontend_mvp_passed`

Prepared MP3 upload now exposes an explicit media attachment action in the
OpenWebUI composer, calls the existing OpenWebUI Action contract, shows local
progress/status and places the returned transcript content back into the current
chat composer.

No separate STT GUI, public sidecar route, browser provider key or browser
sidecar token was added.

## Implementation

Changed files:

- `compose/openwebui.compose.yml`
- `deploy/openwebui-static/loader.js`

The local repository does not contain OpenWebUI Svelte/Vite frontend source. The
deployed image is `ghcr.io/open-webui/open-webui:v0.9.6` and contains the built
frontend under `/app/build`.

The pinned OpenWebUI `index.html` already loads `/static/loader.js`, and the
FastAPI backend serves `/static` from `/app/backend/open_webui/static`. The patch
uses that existing static hook through a git-controlled compose bind mount:

```text
../deploy/openwebui-static/loader.js:/app/backend/open_webui/static/loader.js:ro
```

## Behavior

The loader patch:

- installs a browser `fetch` wrapper after page load;
- rewrites only MP3 uploads sent to `/api/v1/files/` to `process=false`;
- records the returned OpenWebUI file id/name/mime/size from the upload response;
- injects `Транскрибировать` only onto supported MP3 attachment cards in the
  composer;
- calls `POST /api/chat/actions/stage2_media_transcription_action`;
- passes the proven `body.files[0].file.id/name/mime/size` shape;
- obtains the OpenWebUI model id from `/api/models`;
- keeps progress/status local to the attachment card;
- inserts the Action response content into the current composer.

Unsupported media is not advertised by this patch. Browser ffmpeg.wasm
normalization remains a later slice.

## Runtime Deployment

Implementation commit:

```text
37f44f5 feat: add stt transcribe action to media attachments
```

Server update:

```text
cd /opt/openwebui-prd0
git pull --ff-only
docker compose --env-file .env -f compose/openwebui.compose.yml up -d openwebui
```

Runtime checks:

```text
openwebui health: healthy
stage2-stt: running
/app/backend/open_webui/static/loader.js: mounted, 10240 bytes
```

## Playwright Proof

### Injected pre-deploy proof

The same `deploy/openwebui-static/loader.js` was injected into a live browser
session before deployment to prove behavior without modifying the running
container.

Sanitized result:

```json
{
  "mode": "injected-loader-before-deploy",
  "upload": {
    "status": 200,
    "query": "?process=false",
    "file_id_present": true,
    "mime": "audio/mpeg",
    "size_present": true
  },
  "action": {
    "status": 200,
    "has_content": true,
    "has_transcript_marker": true,
    "nonempty": true,
    "warning_present": true
  },
  "ui": {
    "button_visible": true,
    "button_label_present": true,
    "transcript_marker_visible": true,
    "status_text_present": true,
    "button_disabled_after_done": true
  },
  "cleanup": {
    "file_delete_status": 200,
    "chat_id_present": false
  }
}
```

### Deployed static-loader proof

After server pull and OpenWebUI recreate, a fresh browser session loaded
`/static/loader.js` from the deployed OpenWebUI instance. No `addScriptTag`
injection was used.

Sanitized result:

```json
{
  "mode": "deployed-static-loader",
  "loader": {
    "fetch_patched": true,
    "script_loaded": true
  },
  "upload": {
    "status": 200,
    "query": "?process=false",
    "file_id_present": true,
    "mime": "audio/mpeg",
    "size_present": true
  },
  "action": {
    "status": 200,
    "has_content": true,
    "has_transcript_marker": true,
    "nonempty": true,
    "warning_present": true
  },
  "ui": {
    "button_visible": true,
    "button_label_present": true,
    "transcript_marker_visible": true,
    "status_text_present": true,
    "button_disabled_after_done": true
  },
  "cleanup": {
    "file_delete_status": 200,
    "chat_id_present": false
  }
}
```

Observed network sequence:

```text
GET /static/loader.js -> 200
POST /api/v1/files/?process=false -> 200
POST /api/chat/actions/stage2_media_transcription_action -> 200
DELETE /api/v1/files/{id} -> 200
```

The transcript text itself was not copied into logs, screenshots, docs, commits
or final output.

## Validation

Passed:

```text
node --check deploy/openwebui-static/loader.js
git diff --check
Playwright injected-loader proof
Playwright deployed-static-loader proof
server git status clean at 37f44f5 before report commit
```

Not run:

- OpenWebUI frontend lint/typecheck/build, because this repository does not
  contain the OpenWebUI frontend source/toolchain.
- Sidecar unit tests, because no sidecar code changed in this slice.

## Caveats

- This is a static-loader integration, not an upstream Svelte component patch.
  It is intentionally small and git-controlled, but it must be revalidated when
  the OpenWebUI image version changes.
- The MVP supports prepared MP3 only.
- The transcript is inserted into the current composer as editable text; the
  patch does not auto-send a chat message or create a separate transcript
  history.
- OpenWebUI still issued its file process-status request after the upload, but
  the upload request itself was rewritten to `process=false` and the prior
  visible processing blocker did not block the STT path.
