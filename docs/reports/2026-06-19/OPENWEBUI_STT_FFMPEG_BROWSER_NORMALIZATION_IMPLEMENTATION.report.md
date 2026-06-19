# OpenWebUI STT ffmpeg.wasm browser normalization implementation

Date: 2026-06-19.

Final verdict: `ffmpeg_browser_normalization_passed`.

## 1. Scope

Implemented browser-side ffmpeg.wasm media normalization for the existing
OpenWebUI media attachment STT Action path.

The implementation keeps the existing path:

```text
OpenWebUI attachment -> browser normalization when needed -> OpenWebUI
process=false prepared-audio upload -> OpenWebUI Action -> stage2-stt sidecar
-> Lemonfox adapter -> transcript returned to the current composer UX
```

## 2. Non-goals preserved

- No separate STT GUI.
- No browser-to-Lemonfox path.
- No sidecar internal token in browser.
- No public sidecar job route.
- No committed test media.
- No committed ffmpeg wasm/core binaries.

## 3. Main files changed

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `scripts/fetch-ffmpeg-wasm-assets.sh`
- `compose/openwebui.compose.yml`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/tests/test_capabilities_endpoint.py`
- `services/stage2-stt/tests/test_config.py`
- `.env.example`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`

## 4. Browser loader behavior

The static loader now:

- recognizes broad media candidates by MIME prefix and extension hints;
- stores the original browser `File` during OpenWebUI upload interception;
- forces media uploads through `process=false`;
- preserves prepared MP3 passthrough without loading ffmpeg.wasm;
- loads pinned self-hosted ffmpeg.wasm assets only when normalization is needed;
- probes for an audio stream before provider handoff;
- normalizes source media to the configured prepared-audio output profile;
- re-uploads prepared audio to OpenWebUI with `process=false`;
- calls the existing OpenWebUI Action with the prepared audio file reference;
- shows typed safe UI errors before provider handoff for decode/no-audio cases.

## 5. Static browser config

The loader reads:

```text
/static/stage2-stt-normalization.json
```

Current deployed browser config selects:

```text
selected_output_profile=mp3_high_compat
fallback_output_profile=mp3_high_compat
ffmpeg_asset_mode=self_hosted
ffmpeg_package_version=0.12.6
ffmpeg_core_version=0.12.6
ffmpeg_util_version=0.12.1
```

This is a compatibility default for the current static OpenWebUI patch. The
loader supports the approved output profile set, but Opus should not become the
browser default until provider compatibility is proven on the deployed path.

## 6. ffmpeg.wasm assets

The repo now provides:

```text
scripts/fetch-ffmpeg-wasm-assets.sh
```

The script installs pinned UMD assets into:

```text
deploy/openwebui-static/stage2-assets/ffmpeg/0.12.6/
```

Generated assets are ignored by Git. Server proof:

```text
ffmpeg.js: present
ffmpeg-util.js: present
814.ffmpeg.js: present
ffmpeg-core.js: present
ffmpeg-core.wasm: present, 32129114 bytes
```

Public static proof:

```text
/static/stage2-stt-normalization.json -> 200
/static/stage2-assets/ffmpeg/0.12.6/ffmpeg-core.wasm -> 200, application/wasm, 32129114 bytes
```

## 7. Sidecar capabilities

`TranscriptionRuntimeCapabilitiesV1` now includes input-side safe fields:

```text
input_accept_mode
declared_input_mime_prefixes
declared_input_extensions
ffmpeg_probe_required
require_audio_stream
fallback_output_profile
max_browser_duration_minutes
```

Runtime proof from inside `stage2-stt`:

```text
capabilities_selected=opus_webm_compact
capabilities_fallback=mp3_high_compat
capabilities_input=broad_ffmpeg_probe
capabilities_prefixes=audio/,video/
capabilities_probe_required=True
capabilities_secret_markers=False
```

The browser still does not receive the internal sidecar token.

## 8. Auth and routing boundary

The browser calls OpenWebUI same-origin routes only:

```text
/api/v1/files/?process=false
/api/chat/actions/stage2_media_transcription_action
/static/...
```

The sidecar job route remains internal to Docker networking and is called by the
OpenWebUI Action with server-side auth.

Public `/stage2-api/transcription/capabilities` returned `text/html` from the
OpenWebUI SPA fallback, not sidecar JSON.

## 9. Error handling

Observed typed browser errors:

```text
ffmpeg_decode_unsupported
ffmpeg_no_audio_stream
```

Implemented reason-code path also covers:

```text
ffmpeg_probe_failed
ffmpeg_browser_memory_limit
ffmpeg_input_too_large
ffmpeg_duration_limit_exceeded
ffmpeg_normalization_failed
prepared_audio_too_large
provider_direct_upload_limit_exceeded
unsupported_input_format
```

Provider-specific failures stay behind the Action/sidecar boundary.

## 10. Deployment

Server repo:

```text
/opt/openwebui-prd0
```

Deployed commit:

```text
3b9b292 feat: add browser ffmpeg normalization for stt media action
```

Deployment commands used the explicit server-local env file:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt openwebui
```

Container proof:

```text
openwebui=running
stage2-stt=running
openwebui_health=healthy
openwebui_env_and_static_mounts=OK
```

Note: an initial compose command without `--env-file .env` showed unset-env
warnings because the compose file lives under `compose/`. Services were
immediately recreated again with explicit `--env-file .env`, and the safe
runtime env/mount check passed.

## 11. Local validation

Passed:

```text
node --check deploy/openwebui-static/loader.js
python -m compileall services\stage2-stt\stage2_stt
python -m pytest services\stage2-stt\tests
git diff --check
node --check local\playwright-ui-proof\ffmpeg-normalization-runner.js
```

Pytest result:

```text
22 passed
```

Local Windows `bash -n` and local Docker compose config checks were not usable
because of local shell/Docker tooling. Equivalent shell syntax and compose
checks passed on the server.

## 12. Playwright proof

Evidence file:

```text
docs/reports/2026-06-19/openwebui-stt-ffmpeg-browser-normalization-proof/ffmpeg-normalization-evidence.json
```

All media were generated synthetic proof files under ignored `audio/`; no
customer media and no transcript text were committed.

Result:

```text
prepared_mp3_passthrough=PASS
mp4_video_with_audio=PASS
webm_audio_video=PASS
unsupported_fake_mp4=PASS
no_audio_stream_mp4=PASS
ffmpeg_normalization_cases_passed=true
```

## 13. Playwright case matrix

| Case | Result | Proof signal |
| --- | --- | --- |
| Prepared MP3 passthrough | Pass | Source MP3 upload `200`; no ffmpeg asset requests; Action `200`; transcript marker present. |
| MP4 video with audio | Pass | Source MP4 upload `200`; ffmpeg assets `200`; prepared `.stage2-stt.mp3` upload `200`; Action `200`; transcript marker present. |
| WebM audio/video | Pass | Source WebM upload `200`; ffmpeg assets `200`; prepared `.stage2-stt.mp3` upload `200`; Action `200`; transcript marker present. |
| Unsupported fake MP4 | Pass | Source upload `200`; no Action call; safe reason `ffmpeg_decode_unsupported`. |
| No-audio MP4 | Pass | Source upload `200`; no Action call; safe reason `ffmpeg_no_audio_stream`. |

Uploaded proof files were deleted through OpenWebUI file delete API after each
case. No chat was created by these composer-only Action insertions, so chat
cleanup was not applicable.

## 14. Security review

- No real env values were printed.
- Static browser config contains no secret markers.
- Capabilities response contains no secret markers.
- Browser does not receive `STAGE2_STT_INTERNAL_API_KEY`.
- Browser does not call Lemonfox.
- Static wasm assets are public static files, not provider credentials.
- Test evidence does not include transcript text.

## 15. Remaining limits

- Input support is still capability-based; do not claim every upstream FFmpeg
  format works.
- Static browser config currently prefers `mp3_high_compat`; Opus default needs
  provider proof before switching.
- Large files, mobile browsers, low-memory browsers and duration-limit policy
  still need separate acceptance data.
- Cancel is not implemented for browser ffmpeg work in this slice.
- Prepared audio storage/retention and >100 MB fallback behavior remain policy
  decisions.

## 16. References

- ffmpeg.wasm usage documentation:
  `https://ffmpegwasm.netlify.app/docs/getting-started/usage/`
- ffmpeg.wasm repository:
  `https://github.com/ffmpegwasm/ffmpeg.wasm`
- Stage 2 input contract:
  `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- Stage 2 env contract:
  `docs/stage2/config/STT_ENV_CONTRACT.md`
