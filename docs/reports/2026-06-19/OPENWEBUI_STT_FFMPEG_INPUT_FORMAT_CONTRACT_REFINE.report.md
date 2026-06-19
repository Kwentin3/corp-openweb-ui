# OpenWebUI STT FFmpeg Input Format Contract Refine Report

Date: 2026-06-19

## 1. Summary

Refined Stage 2 STT input-format contracts from a narrow/static format model to
a capability-based ffmpeg.wasm normalization model.

Prepared-MP3 remains the current proven frontend/runtime MVP. Broad media input
support is now documented as the next capability-based target, not as a product
promise for every upstream FFmpeg-supported format.

## 2. Owner Decision Encoded

Encoded decision:

```text
Stage2 STT input compatibility is ffmpeg.wasm capability-based.
```

The UI may accept broad audio/video/media candidates, but actual processing is
approved only if the configured browser ffmpeg.wasm build can probe/decode the
file into an audio stream and normalize it into an approved Stage2 prepared-audio
output profile within limits.

## 3. Input Compatibility Model

Input side is now defined as:

```text
broad media candidate
-> configured browser ffmpeg.wasm probe/decode
-> audio stream detected
-> normalization into approved prepared-audio output profile
```

Rules added:

- extension/MIME are UI hints only;
- no provider handoff without successful probe/normalization;
- no-audio-stream files fail before provider calls;
- browser/device memory, file size, duration, container and codec support can
  reject a source file even when upstream FFmpeg supports that family generally.

Created candidate contract:

```text
SttMediaInputProfileV1
```

## 4. Output Profile Contract

Output side remains strict and contract-based.

Existing prepared-audio output profiles remain separate from input
compatibility:

```text
opus_webm_compact
opus_ogg_compact
mp3_high_compat
wav_pcm_safe
```

Created/refined candidate result metadata:

```text
PreparedAudioMetadataV1
```

## 5. Runtime Capability Changes

`TranscriptionRuntimeCapabilitiesV1` was refined with input-side fields:

```text
input_accept_mode
declared_input_mimes
declared_input_extensions
ffmpeg_probe_required
max_browser_input_mb
max_browser_duration_minutes
selected_output_profile
fallback_output_profile
```

These fields are UI-safe capability hints and must not expose provider keys,
raw env values, storage credentials or raw provider responses.

## 6. Env/Config Changes

Added candidate input-side env keys:

```text
STAGE2_STT_INPUT_ACCEPT_MODE=broad_ffmpeg_probe
STAGE2_STT_DECLARED_INPUT_EXTENSIONS=mp3,wav,m4a,webm,ogg,mp4,mov,mkv,avi,flac,aac
STAGE2_STT_DECLARED_INPUT_MIME_PREFIXES=audio/,video/
STAGE2_STT_REQUIRE_AUDIO_STREAM=true
STAGE2_STT_FFMPEG_PROBE_BEFORE_ACTION=true
STAGE2_STT_ON_FFMPEG_UNSUPPORTED=visible_error
```

Clarified that declared input extensions/MIME prefixes are UI hints, not
guaranteed decode proof.

Output profile env remains separate:

```text
STAGE2_STT_OUTPUT_PROFILE
STAGE2_STT_FALLBACK_OUTPUT_PROFILE
```

## 7. UI Behavior Changes

Current proven path remains:

```text
prepared MP3 attachment -> process=false upload -> Transcribe action ->
OpenWebUI Action -> stage2-stt sidecar -> transcript in composer
```

Next target behavior:

1. User attaches an audio/video media candidate.
2. UI may show `Transcribe` for broad media candidates.
3. On click, UI runs ffmpeg probe/normalization.
4. If no audio stream is found, UI shows a safe visible error.
5. If ffmpeg cannot decode the source, UI shows a safe visible browser error.
6. If normalization succeeds, UI sends prepared audio through the existing
   Action/sidecar path.
7. Transcript returns to current OpenWebUI UX.

No separate STT GUI is introduced or planned.

## 8. Error/Reason Codes

Added/refined reason codes:

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

## 9. Docs Changed

Created:

- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_INPUT_FORMAT_CONTRACT_REFINE.report.md`

Updated:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md`
- `docs/stage2/CONTEXT_INDEX.md`

## 10. Code Touched, If Any

No runtime code changed.

`deploy/openwebui-static/loader.js` remains the prepared-MP3 frontend MVP path.
Broad media ffmpeg.wasm normalization was not implemented in this task.

## 11. Remaining Implementation Work

- Implement browser ffmpeg.wasm asset loading from approved self-hosted path.
- Probe media input.
- Detect audio stream.
- Normalize to selected output profile.
- Emit progress and terminal status.
- Map ffmpeg/memory/size/duration failures to typed safe errors.
- Send prepared audio through the existing Action/sidecar path.
- Prove behavior with Playwright.

## 12. Next Recommended Slice

Implement browser ffmpeg.wasm input probe and normalization.

Acceptance proof should cover:

- MP3 prepared/passthrough path;
- MP4 video with audio;
- WebM audio/video if available;
- unsupported file safe error;
- no-audio-stream safe error.

## 13. Final Verdict

```text
ffmpeg_input_contract_refined
```

The product decision is encoded. Input compatibility is now capability-based,
while prepared-audio output profiles remain strict runtime/config contracts.
