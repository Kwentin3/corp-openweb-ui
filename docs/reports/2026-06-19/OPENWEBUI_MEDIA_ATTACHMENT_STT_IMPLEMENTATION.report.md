# OpenWebUI Media Attachment STT Implementation Report

Date: 2026-06-19
Status: partial implementation + runtime blocker
Final verdict: `blocked_by_runtime_environment`

## 1. Summary

Implemented the safe repo-local part of the OpenWebUI-native STT media
attachment path:

- sidecar job routes behind internal auth;
- OpenWebUI integration envelope;
- probe/test stub transcript mode;
- result/status/cancel endpoints;
- admin-installable OpenWebUI Action Function template;
- tests for sidecar route auth, validation, stub transcript result and cancel
  terminal behavior.

Not completed end-to-end because this repository does not contain OpenWebUI
frontend/backend source or a live admin OpenWebUI runtime session. Process env
also did not contain `STAGE2_LEMONFOX_API_KEY` or
`STAGE2_STT_INTERNAL_API_KEY`, and no approved non-sensitive media file was
available for live provider smoke. The actual OpenWebUI Action runtime probe,
browser ffmpeg.wasm normalization and Lemonfox live transcription remain blocked
by runtime environment.

## 2. Phases executed

| Phase | Status | Evidence |
| --- | --- | --- |
| Required docs read | Done | Task docs and STT Stage 2 docs were read before edits. |
| Runtime probe | Blocked | No live/admin OpenWebUI runtime or credentials in repo. |
| Path selection | Partial | Implemented Action-template + sidecar job route path, with runtime probe still required. |
| Sidecar job routes | Done for internal/probe use | `services/stage2-stt/stage2_stt/app.py` |
| Browser normalization | Deferred | Requires OpenWebUI frontend/runtime integration. |
| Lemonfox live smoke | Not run | Env key absent and no approved media. |
| Tests/smokes | Done for sidecar | `python -m pytest`, compileall, wheel build. |

## 3. Runtime probe result

Outcome:

```text
blocked_by_runtime_environment
```

Probe blockers:

- no OpenWebUI source tree in this repo;
- OpenWebUI is consumed as `ghcr.io/open-webui/open-webui:v0.9.6`;
- no admin/staging OpenWebUI session was available to install/run an Action;
- no proof of Action access to `__files__`, `body["files"]`,
  `__metadata__`, chat/message ids or file bytes could be captured;
- no browser ffmpeg.wasm attachment normalization path could be verified.

## 4. Selected implementation path

Selected repo-local path:

```text
Action Function template -> internal sidecar job route -> Lemonfox adapter/stub
```

Reason:

- it preserves OpenWebUI as user-facing UX;
- it keeps sidecar backend-only;
- it avoids a deep OpenWebUI fork;
- it avoids provider keys in browser;
- it provides concrete sidecar job routes for the later runtime probe.

This is not yet a verified OpenWebUI-native attachment button, because the
actual Action/runtime install was not possible in this environment.

## 5. Files changed

Code:

- `services/stage2-stt/pyproject.toml`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/openwebui_actions/__init__.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `services/stage2-stt/tests/test_job_routes.py`

Docs/report:

- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_IMPLEMENTATION.report.md`

## 6. OpenWebUI integration implemented

Created:

```text
services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py
```

Shape:

- admin-installable OpenWebUI Action Function template;
- collects file metadata from `__files__`, `__metadata__["files"]` or
  `body["files"]`;
- emits OpenWebUI status events when an event emitter is provided;
- reads uploaded file bytes from OpenWebUI upload storage only inside the
  OpenWebUI Action process, not from the sidecar;
- calls `POST /stage2-api/transcription/jobs`;
- returns transcript text into current OpenWebUI message content.

Limitations:

- not installed in live OpenWebUI during this run;
- assumes OpenWebUI Action receives file metadata in a supported shape;
- supports already-prepared audio profiles for the Action-only path;
- browser ffmpeg.wasm normalization for source video/media remains the next
  runtime/frontend probe.

## 7. Browser normalization behavior

Not implemented.

Reason:

- no OpenWebUI frontend source exists in this repo;
- no runtime Action/browser probe was available;
- adding ffmpeg.wasm through a blind frontend patch would violate the
  no-deep-fork/no-fake-proof constraints.

The Action template accepts prepared audio MIME/profile candidates:

- `audio/mpeg` -> `mp3_high_compat`;
- `audio/webm*` -> `opus_webm_compact`;
- `audio/ogg*` -> `opus_ogg_compact`;
- `audio/wav` / `audio/x-wav` -> `wav_pcm_safe`.

Unsupported media returns a visible safe message.

## 8. Sidecar job routes / contract

Implemented routes:

```text
POST /stage2-api/transcription/jobs
GET /stage2-api/transcription/jobs/{job_id}
GET /stage2-api/transcription/jobs/{job_id}/result
POST /stage2-api/transcription/jobs/{job_id}/cancel
```

Auth behavior:

- job routes require `STAGE2_STT_INTERNAL_API_KEY`;
- token can be passed by `Authorization: Bearer <token>` or
  `X-Stage2-Internal-Token`;
- routes return `503 stage2_stt_internal_auth_not_configured` when auth is not
  configured;
- routes return `401 stage2_stt_internal_auth_failed` on wrong token.

Create-job input:

- multipart `prepared_audio`;
- form field `envelope` as `OpenWebUITranscriptionEnvelopeV1` JSON;
- `source_context=openwebui`;
- user/chat/message/file metadata;
- selected output profile.

Persistence:

- in-memory job store only;
- suitable for probe/unit smoke, not production queue/persistence.

## 9. Lemonfox integration

Live Lemonfox call was not run.

Implemented path:

- with `STAGE2_LEMONFOX_API_KEY`, the job route calls
  `LemonfoxSttAdapter.transcribe_bytes(..., live=True)`;
- without key, route fails with `provider_auth_missing` unless
  `STAGE2_STT_ALLOW_STUB_TRANSCRIPT=true`;
- stub mode is explicit probe/test mode and returns a normalized
  `TranscriptResultV1` warning, not a production transcript.

No Lemonfox key was printed, read from `.env`, committed or logged.

## 10. Transcript return behavior

Sidecar:

- `POST /jobs` returns `TranscriptionJobCreateResponseV1` with `job` and
  optional `result`;
- `GET /jobs/{job_id}/result` returns normalized `TranscriptResultV1`.

Action template:

- returns `Transcript:\n\n...` in current OpenWebUI Action response content;
- returns visible safe messages for unsupported media or sidecar errors;
- does not expose raw provider response.

Runtime placement in real OpenWebUI was not verified.

## 11. Progress/cancel behavior

Progress:

- Action template emits status events:
  - checking attachment;
  - sending prepared audio to sidecar;
  - complete;
  - safe error terminal messages.

Cancel:

- sidecar exposes `POST /jobs/{job_id}/cancel`;
- completed jobs are terminal and cancel is a no-op;
- domain cancel model remains local-cancel-safe for pending/nonterminal jobs.

Runtime cancel UI was not verified in OpenWebUI.

## 12. Tests and smoke

Shell context:

- Windows PowerShell;
- workdir: `services/stage2-stt`.

Commands:

```text
python -m pytest
python -m compileall stage2_stt tests openwebui_actions
python -m pip wheel --no-deps . -w dist
```

Results:

- `22 passed in 0.99s`;
- compileall passed;
- wheel build passed:
  `openwebui_stage2_stt-0.1.0-py3-none-any.whl`,
  `sha256=f19067ea36ee11431b709889334cb4ec894097e622d39acfb56f81e095d7c7ec`;
- wheel contents include `stage2_stt/*.py` and
  `openwebui_actions/stage2_media_transcription_action.py`.

Additional checks:

- process env check reported `STAGE2_LEMONFOX_API_KEY_ABSENT`;
- process env check reported `STAGE2_STT_INTERNAL_API_KEY_ABSENT`;
- closed-world quick scan found no workspace imports/path hacks in
  `services/stage2-stt`.

Test terminal outcomes asserted:

- `POST /jobs` without configured internal auth -> `503` + typed detail;
- wrong token -> `401` + typed detail;
- missing Lemonfox key without stub -> `503 provider_auth_missing`;
- wrong MIME/profile -> `422 unsupported_input_format`;
- explicit stub mode -> `200 completed` + normalized result;
- `GET /result` -> `200` + result `job_id`;
- cancel completed job -> `200 completed` and no fake cancel mutation.

Irreversible boundary:

- provider upload starts only after internal auth, envelope parsing and prepared
  audio validation pass. Tests assert terminal outcomes before this boundary and
  use explicit stub mode to avoid live provider side effects.

## 13. Self-check against docs

| Requirement | Status | Evidence |
| --- | --- | --- |
| OpenWebUI-native UX | Partial | Action template created, but runtime install/probe blocked. |
| No separate STT GUI | Pass | No GUI/portal added. |
| Explicit Transcribe action | Partial | Action template exists; real attachment button not runtime-proven. |
| Sidecar backend-only | Pass | Sidecar exposes API only. |
| Lemonfox hidden behind adapter | Pass | Route calls `SttProviderAdapterFactory` / `LemonfoxSttAdapter`. |
| No provider key in browser | Pass | No frontend key path added; Action uses internal sidecar token. |
| No direct browser-to-Lemonfox | Pass | No browser/provider route added. |
| Authenticated job routes | Partial | Internal token required; production auth boundary still operator/runtime decision. |
| Transcript returns to OpenWebUI UX | Partial | Action returns content; live OpenWebUI placement not verified. |
| Browser ffmpeg normalization | Blocked | No OpenWebUI frontend/runtime source. |
| Error/cancel visible | Partial | Action safe messages + sidecar cancel route; live UI not verified. |
| Tests/smokes executed | Pass | `22 passed`, compileall, wheel. |

## 14. Known limitations

- No live OpenWebUI Action runtime probe was possible.
- No real attachment button was added to OpenWebUI UI.
- No browser ffmpeg.wasm normalization was implemented.
- Action-only path supports prepared audio candidates, not arbitrary source
  video normalization.
- Job store is in-memory and not production persistence.
- No production sidecar compose/Traefik route was added.
- Production auth boundary is still not selected.
- Lemonfox live smoke did not run.
- No approved non-sensitive media file was available.

## 15. Deviations from ADR/plan

- The task asked for end-to-end implementation if context was sufficient. The
  context was not sufficient for runtime OpenWebUI and Lemonfox live validation.
- Sidecar job routes were implemented with explicit internal-token gating to
  avoid public unauthenticated routes.
- Stub transcript mode was added only for probe/tests and must not be treated as
  production transcription.
- Browser normalization was not faked.

## 16. Next recommended slice

Next smallest safe slice:

1. In staging/admin OpenWebUI, install
   `stage2_media_transcription_action.py`.
2. Configure Action valve/internal env with `STAGE2_STT_INTERNAL_API_KEY`
   without exposing it to browser/users.
3. Attach approved non-sensitive MP3 and verify `__files__`/metadata shape.
4. Verify status events and same-chat transcript placement.
5. Decide whether a small frontend patch is required for browser ffmpeg.wasm
   normalization and video-source support.
6. Only after auth/runtime proof, wire production route/compose and run Lemonfox
   live smoke with approved media.

## 17. Final verdict

```text
blocked_by_runtime_environment
```

The repo-local sidecar contract and Action template are implemented and tested,
but the requested end-to-end OpenWebUI media attachment feature cannot be
claimed until a live OpenWebUI admin/runtime probe, browser normalization path,
approved internal token, approved Lemonfox key and approved media are available.
