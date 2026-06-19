# OpenWebUI STT Runtime Completion Report

Date: 2026-06-19
Status: partial runtime proof + auth/routing blocker
Final verdict: `blocked_by_auth_or_routing`

## 1. Summary

This run removed part of the previous runtime uncertainty:

- OpenWebUI admin API login works with local ignored `.env` credentials.
- The Stage 2 OpenWebUI Action Function was installed in the live OpenWebUI
  runtime as `stage2_media_transcription_action`.
- The Action was intentionally left disabled and non-global because the server
  sidecar route/token is not live yet.
- Local sidecar live smoke with the provided MP3 and Lemonfox passed through
  the implemented job route and returned a normalized non-empty result.
- Repo compose/env wiring was extended for a backend-only `stage2-stt` service
  without publishing a public host port.

The end-to-end OpenWebUI attachment path is still not proven because the live
server does not currently run or route `stage2-stt`, local `.env` did not
contain `STAGE2_STT_INTERNAL_API_KEY`, and non-interactive SSH failed with
`publickey`.

## 2. Runtime/env audit

Local ignored `.env`:

| Key | Local status |
| --- | --- |
| `OPENWEBUI_HOST` | present |
| `WEBUI_ADMIN_EMAIL` | present |
| `WEBUI_ADMIN_PASSWORD` | present |
| `STAGE2_LEMONFOX_API_KEY` | present |
| `STAGE2_STT_PROVIDER` | present |
| `STAGE2_STT_PROVIDER_ADAPTER` | present |
| `STAGE2_STT_OUTPUT_PROFILE` | present |
| `STAGE2_STT_FALLBACK_OUTPUT_PROFILE` | present |
| `STAGE2_STT_INTERNAL_API_KEY` | absent |
| `STAGE2_STT_ALLOW_STUB_TRANSCRIPT` | absent |

Process environment did not contain useful project SSH variables. No SSH user
or key path was found in repo docs or local SSH config. Public SSH port on
`gpt.alpha-soft.ru:22` was reachable, but default non-interactive SSH failed:

```text
Permission denied (publickey)
```

No secrets were printed.

## 3. Env propagation fix

Repo-side wiring added:

- `services/stage2-stt/Dockerfile`
- `compose/openwebui.compose.yml` service `stage2-stt`
- `.env.example` keys:
  - `STAGE2_STT_INTERNAL_API_KEY`
  - `STAGE2_STT_ALLOW_STUB_TRANSCRIPT`
- `docs/infra/ENVIRONMENT_VARIABLES.md` entries for both keys
- `.gitignore` guard for local proof media under `audio/`

The compose service is backend-only:

- attached to `openwebui_web`;
- exposes container port `8080` only to the Docker network;
- does not publish `ports`;
- does not add a Traefik public route.

Server `.env` was not changed because SSH authentication was unavailable from
this environment.

## 4. Sidecar runtime status

Local sidecar contract:

- unit routes are implemented and tested;
- local Lemonfox live smoke through `POST /stage2-api/transcription/jobs`
  passed with a temporary process-only internal token.

Live server sidecar:

- not proven running;
- public `https://gpt.alpha-soft.ru/stage2-api/transcription/capabilities`
  returned OpenWebUI SPA HTML, not `TranscriptionRuntimeCapabilitiesV1`;
- current deployed routing therefore does not expose or route the sidecar.

## 5. OpenWebUI Action install/probe

OpenWebUI admin API:

- `POST /api/v1/auths/signin` succeeded with admin role;
- `/api/v1/functions/` initially returned zero functions;
- `POST /api/v1/functions/create` installed
  `stage2_media_transcription_action`;
- installed function summary:

```text
id=stage2_media_transcription_action
type=action
active=False
global=False
```

Valves spec is visible in runtime:

```text
allow_upload_path_access
internal_api_key
priority
request_timeout_seconds
sidecar_base_url
upload_root
```

The Action was not activated because the server-side `stage2-stt` route and
internal token are not configured in live runtime.

## 6. File attachment evidence

No live chat attachment probe was completed.

Reason:

- Action is installed but disabled;
- server sidecar route is not live;
- no safe internal token is configured on the server;
- enabling the Action for users would expose a known non-working command.

Therefore, the live Action file-context shape remains unproven:

- `__user__`: not observed in Action execution;
- `__metadata__`: not observed in Action execution;
- `body["files"]`: not observed in Action execution;
- `__files__`: not observed in Action execution;
- file id/name/mime/size: not observed in Action execution;
- bytes or approved file handoff: not observed in Action execution.

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

The audio file was not committed. The transcript text was not printed or added
to this report.

## 8. Lemonfox live smoke

Local live smoke through sidecar route:

```text
local_sidecar_live_status=200
job_status=completed
result_text_nonempty=True
result_language=ru
duration_present=True
segments_count=1
output_profile=mp3_high_compat
provider_id=lemonfox
warnings_count=0
```

This proves the local ignored `.env` Lemonfox key works with the implemented
sidecar adapter and the provided MP3. It does not prove that the key reached the
server container runtime.

## 9. Transcript return behavior

Local sidecar returned a normalized `TranscriptResultV1` with non-empty text.

OpenWebUI chat placement was not proven because the Action was not executed in
chat runtime. No transcript content was copied into this report.

## 10. Browser normalization status

Browser ffmpeg.wasm normalization remains pending.

Current proven path:

```text
mp3_prepared_audio_path_passed locally through sidecar + Lemonfox
```

Current unproven path:

```text
browser ffmpeg.wasm normalization inside OpenWebUI media attachment path
```

No frontend patch or deep fork was made.

## 11. Tests and commands

Commands run:

```text
python -m pytest
python -m compileall stage2_stt tests openwebui_actions
python -m pip wheel --no-deps . -w dist
python -c "import yaml ... yaml.safe_load(...)"
Invoke-WebRequest https://gpt.alpha-soft.ru/
OpenWebUI admin API signin/functions checks
local sidecar live smoke with MP3
```

Results:

- `22 passed in 1.39s`;
- compileall passed;
- wheel build passed:
  `openwebui_stage2_stt-0.1.0-py3-none-any.whl`,
  `sha256=a9dd984bb18fc38c4cd3e66bd02dc079ce42112a1bf3fd980c8af756005083bf`;
- wheel contains `stage2_stt/*.py` and `openwebui_actions/*.py`;
- compose YAML parsed;
- compose services: `openwebui`, `stage2-stt`, `traefik`;
- `stage2-stt` has no public `ports`, only `expose=8080`.

Local Docker limitation:

- local Docker CLI is old and has no `docker compose` plugin, so full
  `docker compose config` / image build was not run locally.

## 12. Security/no-secret checks

Applied controls:

- `.env` was read only for runtime use and was not staged;
- no secret values were printed;
- admin token was used in process/temp curl config only and temp files were
  deleted;
- no full transcript was printed or committed;
- test audio is ignored through `.gitignore`;
- no direct browser-to-Lemonfox route was added;
- sidecar compose service has no public host port;
- Action was installed disabled because server route/token is not live.

## 13. Remaining limitations

- Server-side `stage2-stt` container was not deployed.
- Server `.env` was not updated with `STAGE2_STT_INTERNAL_API_KEY`.
- Non-interactive SSH failed with `publickey`.
- OpenWebUI Action was not executed against a live attachment.
- File-context shape is still unproven.
- Transcript did not appear in OpenWebUI chat during this run.
- Browser normalization remains unproven.
- Production persistence remains in-memory for this slice.

## 14. Deviations from ADR/plan

- The requested full runtime proof could not be completed because deployment
  SSH/auth was unavailable.
- A safe repo-side compose/env propagation fix was added, but not applied on
  the server.
- Local Lemonfox live proof was executed because the workspace `.env` had a
  Lemonfox key; the server runtime key propagation remains unproven.
- The Action was installed but intentionally not activated.

## 15. Next recommended slice

Next smallest safe runtime slice:

1. Provide or configure non-interactive SSH user/key/alias for
   `gpt.alpha-soft.ru`.
2. On the server, pull the committed compose/Dockerfile changes.
3. Add `STAGE2_STT_INTERNAL_API_KEY` to server-local `.env`.
4. Run:
   `docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt`.
5. From inside the OpenWebUI container, verify:
   `curl http://stage2-stt:8080/stage2-api/transcription/capabilities`.
6. Configure the installed Action valves:
   - `sidecar_base_url=http://stage2-stt:8080`
   - `internal_api_key=<server-local internal token>`
7. Activate the Action for the intended admin/test scope.
8. Attach the MP3 in chat and capture only safe technical evidence.
9. If Action receives metadata but not bytes, implement the approved handoff
   path or record `blocked_by_openwebui_action_file_context`.
10. Only after MP3 Action proof, decide the minimal frontend patch for
    browser ffmpeg.wasm normalization.

## 16. Final verdict

```text
blocked_by_auth_or_routing
```

Local MP3 prepared-audio path through sidecar and Lemonfox is proven. The live
OpenWebUI Action is installed but disabled. End-to-end runtime remains blocked
until the server can run/reach `stage2-stt` with a server-local internal token
and the Action can be executed against an actual attachment.

## Self-check matrix

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| OpenWebUI-native UX | Partial | Action installed in OpenWebUI runtime, not executed. |
| No separate STT GUI | Pass | No GUI added; sidecar remains backend-only. |
| Explicit Action path | Partial | Function type is `action`; disabled until routing/auth is live. |
| Action sees attachment | Blocked | No live Action execution. |
| Action can access bytes or approved handoff | Blocked | No file-context execution proof. |
| Sidecar job routes reachable | Partial | Local route live smoke passed; server route not live. |
| Internal auth works | Partial | Local temporary token worked; server token absent. |
| Lemonfox key server-side only | Pass | Key used only from ignored `.env` in local sidecar process. |
| Lemonfox live smoke | Pass locally | MP3 live smoke returned `200` and normalized result. |
| Transcript returns to OpenWebUI | Blocked | Chat placement not executed. |
| No secrets leaked | Pass | Values/tokens/transcript omitted from outputs and report. |
| Test audio not committed | Pass | `audio/` ignored; file remains untracked/ignored. |
| Browser normalization status | Pending | No frontend/browser ffmpeg proof claimed. |
