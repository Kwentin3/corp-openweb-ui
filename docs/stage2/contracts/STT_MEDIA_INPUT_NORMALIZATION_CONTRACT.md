# STT Media Input Normalization Contract

Status: contract candidate; initial browser normalization implementation is
proven on generated proof media.

Implementation baseline note, 2026-06-19:

- `deploy/openwebui-static/loader.js` implements prepared-MP3 passthrough and
  browser ffmpeg.wasm probe/normalization after explicit user action.
- `deploy/openwebui-static/stage2-stt-normalization.json` selects
  `mp3_high_compat` with self-hosted ffmpeg.wasm assets.
- Playwright proof passed for prepared MP3 passthrough, MP4 with audio, WebM
  audio/video, unsupported fake MP4 safe error and no-audio MP4 safe error.
- This proof does not close mobile, low-memory browser, large/customer media,
  cancel-during-ffmpeg or production duration/retention questions.

This document separates Stage 2 STT input compatibility from prepared-audio
output profiles.

## 1. Decision

Stage2 STT input compatibility is ffmpeg.wasm capability-based.

The UI may accept broad audio/video/media candidates, but actual processing is
approved only if the configured browser ffmpeg.wasm build can probe/decode the
file into an audio stream and normalize it into an approved Stage2 prepared-audio
output profile within configured limits.

Input format support is therefore runtime/build capability, not a static product
promise for every format supported by upstream FFmpeg.

```text
broad media candidate
-> configured browser ffmpeg.wasm probe/decode
-> approved prepared-audio output profile
-> stage2-stt sidecar
-> provider adapter
-> transcript
```

## 2. Boundary Rule

Input side:

- broad and capability-based;
- owned by the configured ffmpeg.wasm build, browser runtime, memory limits,
  file size, duration, container and codec support;
- represented to users as "attempt normalization", not guaranteed support for
  every exotic upstream FFmpeg format.

Output side:

- strict and contract-based;
- selected by env/runtime capabilities;
- validated against the approved Stage2 prepared-audio output profiles before
  provider handoff.

Do not collapse input compatibility and output profile selection into one
concept.

## 3. `SttMediaInputProfileV1`

Candidate shape for UI/runtime probe metadata:

```yaml
SttMediaInputProfileV1:
  input_file_name: string
  input_mime: string | null
  input_extension: string | null
  input_size_bytes: number
  browser_media_kind: audio | video | unknown
  ffmpeg_probe_status: not_started | supported | unsupported | failed
  audio_stream_detected: boolean | null
  detected_duration_seconds: number | null
  detected_audio_codec: string | null
  detected_container: string | null
  normalization_required: boolean
  normalization_strategy: string | null
  rejection_reason: string | null
```

Rules:

- `input_mime` and `input_extension` are hints, not proof.
- `ffmpeg_probe_status=supported` requires a successful probe/decode path in the
  configured ffmpeg.wasm build, not just a matching filename.
- `audio_stream_detected=false` must stop before provider handoff.
- Source media is not sent directly to Lemonfox unless a separate approved
  provider/storage path exists.

## 4. `PreparedAudioMetadataV1`

Candidate shape after successful normalization:

```yaml
PreparedAudioMetadataV1:
  source_input_profile: SttMediaInputProfileV1
  output_profile: string
  output_mime: string
  output_size_bytes: number
  duration_seconds: number | null
  audio_codec: string
  container: string
  ffmpeg_command_profile: string
  normalization_warnings: string[]
```

Rules:

- `output_profile` must be one of the approved Stage2 output profile values.
- Backend/sidecar still validates prepared audio size, MIME/content type,
  duration and selected profile.
- Browser metadata is advisory until validated server-side.

## 5. Reason Codes

Input/probe/normalization reason codes:

```text
ffmpeg_probe_failed
ffmpeg_decode_unsupported
ffmpeg_no_audio_stream
ffmpeg_browser_memory_limit
ffmpeg_input_too_large
ffmpeg_duration_limit_exceeded
ffmpeg_normalization_failed
prepared_audio_too_large
provider_direct_upload_limit_exceeded
unsupported_input_format
```

Guidance:

- Use `unsupported_input_format` only when no more specific ffmpeg reason is
  available.
- Use `prepared_audio_too_large` after normalization when the source may have
  decoded correctly but the resulting prepared audio exceeds configured limits.
- Keep provider-specific failures behind adapter error mapping.

## 6. Runtime Capabilities Additions

`TranscriptionRuntimeCapabilitiesV1` should include input-side fields in
addition to output profile fields:

```yaml
TranscriptionRuntimeCapabilitiesV1:
  input_accept_mode: declared | broad_ffmpeg_probe
  declared_input_mime_prefixes: string[]
  declared_input_extensions: string[]
  ffmpeg_probe_required: boolean
  require_audio_stream: boolean
  max_browser_input_mb: number
  max_browser_duration_minutes: number | null
  selected_output_profile: string
  fallback_output_profile: string
```

Rules:

- `declared_input_mime_prefixes` and `declared_input_extensions` are UI hints.
- `input_accept_mode=broad_ffmpeg_probe` means the UI can offer the action for
  broad media candidates, but successful ffmpeg probe/normalization is still
  required.
- Runtime capabilities must not expose provider keys, raw env values, storage
  credentials or raw provider responses.

## 7. Candidate Env Keys

Candidate input-side config:

```text
STAGE2_STT_INPUT_ACCEPT_MODE=broad_ffmpeg_probe
STAGE2_STT_DECLARED_INPUT_EXTENSIONS=mp3,wav,m4a,webm,ogg,mp4,mov,mkv,avi,flac,aac
STAGE2_STT_DECLARED_INPUT_MIME_PREFIXES=audio/,video/
STAGE2_STT_REQUIRE_AUDIO_STREAM=true
STAGE2_STT_FFMPEG_PROBE_BEFORE_ACTION=true
STAGE2_STT_ON_FFMPEG_UNSUPPORTED=visible_error
```

Rules:

- Declared extensions are affordance hints, not guaranteed decode support.
- Actual support is determined by ffmpeg probe/normalization on the configured
  build and browser.
- Keep these separate from `STAGE2_STT_OUTPUT_PROFILE` and
  `STAGE2_STT_FALLBACK_OUTPUT_PROFILE`.

## 8. UI Behavior

Current proven paths:

```text
prepared MP3 attachment -> process=false upload -> OpenWebUI Action -> sidecar
```

```text
broad media candidate -> ffmpeg probe -> audio stream detected ->
normalization -> prepared audio -> existing Action/sidecar path
```

Current static OpenWebUI patch implementation:

- `deploy/openwebui-static/loader.js` reads safe browser config from
  `/static/stage2-stt-normalization.json`.
- Self-hosted ffmpeg.wasm assets are expected under
  `/static/stage2-assets/ffmpeg/0.12.6/` and are installed with
  `scripts/fetch-ffmpeg-wasm-assets.sh`.
- Prepared MP3 uses passthrough and does not load ffmpeg.wasm.
- Broad media candidates are uploaded with `process=false`, then normalized in
  the browser to the configured prepared-audio profile and re-uploaded to
  OpenWebUI before the existing Action/sidecar handoff.
- The static browser config defaults to `mp3_high_compat` until Opus provider
  compatibility is proven on the deployed path.

UI rules:

- Broad media support must be shown as an attempt to normalize.
- If ffmpeg finds no audio stream, show a safe visible error:
  `В файле не найден аудиопоток`.
- If ffmpeg cannot decode the input, show a safe visible error:
  `Формат не удалось обработать в браузере`.
- Do not rely on extension alone.
- Do not expose Lemonfox/provider details in UI.
- Do not create a separate STT GUI.
