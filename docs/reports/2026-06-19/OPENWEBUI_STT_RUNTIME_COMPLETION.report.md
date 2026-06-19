# OpenWebUI STT Runtime Completion Report

Date: 2026-06-19
Status: runtime proof passed for OpenWebUI Action prepared-MP3 path
Final verdict: `mp3_prepared_audio_path_proven_browser_normalization_pending`

## 1. Summary

The previous `blocked_by_runtime_environment` state is removed for the current
prepared-MP3 MVP path.

- SSH access was found in ignored local infrastructure docs and worked as
  passwordless root SSH.
- The server repo was fast-forwarded to the previously pushed Stage 2 STT
  implementation commit `03ac27f`.
- Server `.env` received the required Stage 2 STT runtime keys from local
  ignored `.env`; values were not printed.
- `stage2-stt` was built and started on the Docker network without a public
  host port.
- OpenWebUI was fixed to bypass outbound proxy for `stage2-stt`.
- OpenWebUI Action `stage2_media_transcription_action` was configured, active,
  and non-global.
- The provided MP3 test media passed:
  `OpenWebUI file upload -> Action -> stage2-stt sidecar -> Lemonfox -> Action response`.

Browser ffmpeg.wasm normalization is still not proven. No separate STT GUI was
added.

## 2. Runtime/env audit

Workspace ignored `.env` had the required provider/admin inputs. Server `.env`
initially missed all checked Stage 2 STT keys:

```text
STAGE2_LEMONFOX_API_KEY: ABSENT
STAGE2_STT_INTERNAL_API_KEY: ABSENT
STAGE2_STT_PROVIDER: ABSENT
STAGE2_STT_PROVIDER_ADAPTER: ABSENT
STAGE2_STT_OUTPUT_PROFILE: ABSENT
STAGE2_STT_FALLBACK_OUTPUT_PROFILE: ABSENT
STAGE2_STT_STORAGE_MODE: ABSENT
```

After propagation, server runtime audit showed:

```text
STAGE2_LEMONFOX_API_KEY: PRESENT
STAGE2_STT_INTERNAL_API_KEY: PRESENT
STAGE2_STT_PROVIDER: PRESENT
STAGE2_STT_PROVIDER_ADAPTER: PRESENT
STAGE2_STT_OUTPUT_PROFILE: PRESENT
STAGE2_STT_FALLBACK_OUTPUT_PROFILE: PRESENT
STAGE2_STT_STORAGE_MODE: PRESENT
STAGE2_STT_ALLOW_STUB_TRANSCRIPT: PRESENT
```

No key values were printed. `.env` remains ignored and uncommitted.

## 3. Env propagation fix

Server-side:

- merged only `STAGE2_*` runtime keys into `/opt/openwebui-prd0/.env`;
- generated a server-local `STAGE2_STT_INTERNAL_API_KEY` when absent;
- wrote timestamped `.env` backups before changes;
- applied `chmod 600`;
- removed temporary transfer/merge files.

The first OpenWebUI-container-to-sidecar check failed with:

```text
HTTP Error 502: No data received from server or forwarder
```

Root cause: OpenWebUI inherited outbound proxy env and `OPENWEBUI_NO_PROXY` did
not include `stage2-stt`. Server `.env` was updated to include:

```text
stage2-stt,stage2-stt:8080
```

Repo defaults were updated in:

- `.env.example`
- `compose/openwebui.compose.yml`
- `docs/infra/ENVIRONMENT_VARIABLES.md`

## 4. Sidecar runtime status

Server compose services:

```text
openwebui: running, healthy
stage2-stt: running, no published host port
traefik: running, public 80/443
```

The sidecar image was built from the packaged wheel in Docker. Container runtime
capabilities check:

```text
capabilities_status=OK
provider_id=lemonfox
selected_output_profile=opus_webm_compact
storage_mode=auto
warnings_count=3
```

OpenWebUI container to sidecar after `NO_PROXY` fix:

```text
openwebui_to_stage2=OK
provider_id=lemonfox
selected_output_profile=opus_webm_compact
warnings_count=3
```

Public OpenWebUI GET returned:

```text
public_get_status=200
```

## 5. OpenWebUI Action install/probe

Action function:

```text
id=stage2_media_transcription_action
type=action
active=True
global=False
```

Configured valves:

```text
sidecar_base_url=http://stage2-stt:8080
internal_api_key=<server-local value, not printed>
upload_root=/app/backend/data/uploads
allow_upload_path_access=True
request_timeout_seconds=180
priority=0
```

The OpenWebUI runtime handler for `POST /api/chat/actions/{action_id}` passes
`body`, `__user__`, model/id/event/request context. It does not pass
`__metadata__` or `__files__` as separate parameters for this endpoint, so the
working Action path uses `body["files"]`.

## 6. File attachment evidence

Probe path:

```text
POST /api/v1/files/?process=false
POST /api/chat/actions/stage2_media_transcription_action
```

Evidence from the OpenWebUI container:

```text
action_signin_status=200
action_upload_status=200
action_file_context_id_present=True
action_file_context_filename_sanitized=True
action_file_context_mime=audio/mpeg
action_file_context_size=3336525
action_call_status=200
action_result_content_present=True
action_result_transcript_marker=True
action_result_transcript_nonempty=True
action_result_warning_present=True
```

Observed context:

| Context item | Status | Evidence |
| --- | --- | --- |
| `__user__` | Pass | OpenWebUI action handler passes verified user; Action call succeeded. |
| `body["files"]` | Pass | File id/name/mime/size reached Action. |
| file id/name/mime/size | Pass | id present; sanitized filename; `audio/mpeg`; `3336525` bytes. |
| bytes or approved handoff | Pass | Action read the file from OpenWebUI upload storage and called sidecar. |
| `__metadata__` | Not passed by this endpoint | Runtime handler did not provide it separately. |
| `__files__` | Not passed by this endpoint | Runtime handler did not provide it separately. |

The proof upload was deleted through `DELETE /api/v1/files/{id}` after the
probe:

```text
action_upload_deleted_count=1
action_tmp_cleanup=True
```

## 7. Test audio used

Local file class:

```text
ignored audio/*.mp3 test media
```

Technical metadata:

```text
size_bytes=3336525
mime_used=audio/mpeg
selected_output_profile=mp3_high_compat
```

The original filename is not included because it contains sensitive-looking
data. The file was copied only to temporary sanitized paths for runtime proof,
then cleaned up. The transcript text was not printed or written to this report.

## 8. Lemonfox live smoke

Direct server sidecar live smoke from inside the `stage2-stt` container:

```text
server_sidecar_live_status=200
job_status=completed
result_text_nonempty=True
result_language=ru
duration_present=True
segments_count=1
output_profile=mp3_high_compat
provider_id=lemonfox
warnings_count=1
```

This proves the server-side Lemonfox key reached the container runtime and the
job route normalized the provider result into the Stage 2 response contract.

## 9. Transcript return behavior

The transcript returned through OpenWebUI Action API:

```text
action_call_status=200
action_result_transcript_marker=True
action_result_transcript_nonempty=True
```

This proves the OpenWebUI-native Action path returns transcript content for the
prepared-MP3 route. A visual browser/chat placement screenshot was not captured
in this run; the API path used is the same Action endpoint the UI calls.

No transcript content was copied into logs, docs, commits, or final output.

## 10. Browser normalization status

Browser ffmpeg.wasm normalization remains pending.

Proven path:

```text
OpenWebUI upload of already prepared MP3
-> OpenWebUI Action
-> OpenWebUI upload-storage handoff
-> stage2-stt sidecar
-> Lemonfox
-> normalized transcript returned by Action
```

Unproven path:

```text
browser/source media -> ffmpeg.wasm normalization -> prepared audio
```

Next frontend slice should be minimal and should only add browser-side media
normalization if OpenWebUI native extension points cannot supply prepared audio
without a small patch.

## 11. Tests and commands

Runtime commands/probes completed:

```text
ssh root target from ignored local infra docs
git pull --ff-only on /opt/openwebui-prd0
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml up -d openwebui
GET /stage2-api/transcription/capabilities from sidecar container
GET /stage2-api/transcription/capabilities from OpenWebUI container to stage2-stt
POST /stage2-api/transcription/jobs from sidecar container with sanitized MP3
POST /api/v1/functions/id/stage2_media_transcription_action/valves/update
POST /api/chat/actions/stage2_media_transcription_action
DELETE /api/v1/files/{id}
```

Local validation after this report update:

```text
python -m pytest -> 22 passed in 1.16s
python -m compileall stage2_stt tests openwebui_actions -> passed
python -m pip wheel --no-deps . -w dist -> passed
wheel sha256=072cfb0e9f33979901ecd54e51f5f6b32ea1287a5403a8ad450b27d7cacee974
wheel contains stage2_stt and openwebui_actions packages
python -c "import yaml ... yaml.safe_load(...)" -> services=openwebui,stage2-stt,traefik; stage2-stt ports=None; expose=8080
```

## 12. Security/no-secret checks

Controls applied:

- `.env` was not staged or committed;
- secret values and admin tokens were never printed;
- Lemonfox key stayed server-side;
- OpenWebUI Action did not contain the Lemonfox key;
- Action was configured with only the internal sidecar token;
- no transcript text was printed or committed;
- original audio filename was not written into the report;
- local `audio/` remains ignored;
- temporary server/container audio copies were removed;
- OpenWebUI proof upload was deleted after the Action probe;
- `stage2-stt` has no public host port and no Traefik public route.

## 13. Remaining limitations

- Browser ffmpeg.wasm normalization is not proven.
- Visual browser/chat rendering was not captured; proof used OpenWebUI's Action
  HTTP endpoint.
- OpenWebUI `POST /api/chat/actions/{action_id}` did not provide
  `__metadata__` or `__files__` separately; `body["files"]` is the proven
  context path.
- This slice still uses in-memory sidecar job storage.

## 14. Deviations from ADR/plan

- The completed proof is for prepared MP3 input, not arbitrary source media.
- The Action uses OpenWebUI upload-storage handoff because the Action endpoint
  does not pass raw bytes directly.
- No separate GUI and no public sidecar route were introduced.
- Server `.env` was fixed directly because the required runtime keys were
  present only in ignored local/server environment material.

## 15. Next recommended slice

Recommended smallest next slice:

1. Add a browser-level proof for the actual OpenWebUI UI button/chat placement,
   or capture it with Playwright against the live runtime.
2. Decide whether browser ffmpeg.wasm can be attached through native OpenWebUI
   extension points.
3. If not, implement a small frontend patch that normalizes source media to the
   existing prepared-audio Action contract.
4. Keep the sidecar private and keep provider keys server-side only.

## 16. Final verdict

```text
mp3_prepared_audio_path_proven_browser_normalization_pending
```

The runtime blocker is removed for the prepared-MP3 OpenWebUI Action path. The
remaining work is browser normalization and visual UI proof, not server env,
sidecar routing, Action configuration, or Lemonfox runtime.

## Self-check matrix

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| OpenWebUI-native UX | Pass for Action API | `POST /api/chat/actions/stage2_media_transcription_action` returned transcript content. |
| No separate STT GUI | Pass | No GUI added; sidecar remains backend-only. |
| Explicit Action path | Pass | Function is `type=action`, active, non-global. |
| Action sees attachment | Pass | `body["files"]` carried id/name/mime/size. |
| Action can access bytes or approved handoff | Pass | OpenWebUI upload-storage handoff succeeded. |
| Sidecar job routes reachable | Pass | OpenWebUI container and sidecar container reached job/capabilities routes. |
| Internal auth works | Pass | Sidecar job route and Action used server-local internal token. |
| Lemonfox key server-side only | Pass | Key stayed in server/container env, not browser/report. |
| Lemonfox live smoke | Pass | Server sidecar returned `200`, completed job, non-empty result. |
| Transcript returns to OpenWebUI | Pass for Action API | Action response had `Transcript:` marker and non-empty body. |
| No secrets leaked | Pass | Values/tokens/transcript omitted; temp files removed. |
| Test audio not committed | Pass | `audio/` ignored; proof upload deleted. |
| Browser normalization status | Pending | ffmpeg.wasm/source-media path not claimed. |
