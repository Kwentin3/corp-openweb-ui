# OPENWEBUI ADR-0004 Lemonfox Capabilities and Runtime Limits Report

Date: 2026-06-19

Status: completed as documentation refinement. ADR-0004 remains `Proposed`.

Scope: refine ADR-0004 and related Stage 2 planning docs for Lemonfox
capabilities, provider capability profile, output profiles, storage modes,
runtime capabilities, limits, duration and cancellation. No implementation,
provider setup, API keys, `.env`, compose, scripts or production configuration
were changed.

## 1. Official Lemonfox docs checked

Primary source:

- https://www.lemonfox.ai/apis/speech-to-text

Relevant documented facts captured in Stage 2 docs:

- Transcription endpoint: `POST https://api.lemonfox.ai/v1/audio/transcriptions`.
- Input can be a direct file upload or a public URL.
- Direct upload limit is documented as 100 MB.
- Public URL input limit is documented as 1 GB.
- Supported formats include `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`, `m4a`,
  `mp4`, `mpeg`, `mov`, `webm` and more.
- Response formats include `json`, `text`, `srt`, `verbose_json` and `vtt`.
- `verbose_json` gives duration and segment timestamps.
- Word timestamps are available through `timestamp_granularities[]=word` with
  `verbose_json`.
- Speaker labels are available through `speaker_labels=true`, require
  `verbose_json`, and are documented with max 4 speakers.
- `callback_url` is documented for long audio/asynchronous completion.
- Russian is listed as a supported language.
- EU endpoint is documented as `eu-api.lemonfox.ai` with 20% surcharge.
- Public pricing hint is documented as $0.50 per 3 hours.

## 2. Lemonfox facts not documented enough for product contract

These items were deliberately kept as `not documented / needs runtime proof`:

- Exact Stage 2 `audio/webm;codecs=opus` compatibility.
- Exact Stage 2 `audio/ogg;codecs=opus` compatibility.
- Maximum accepted provider-side audio duration.
- Provider-side cancellation endpoint, stable provider job id and cancel status
  model.
- Provider error taxonomy and retryability.

Important distinction: Lemonfox docs list `webm`, `ogg` and `opus`, but they do
not prove the exact ffmpeg-produced WebM/Opus or OGG/Opus profiles that Stage 2
would generate. MP3 / `audio/mpeg` therefore remains the source-proven
compatibility fallback until runtime proof says otherwise.

## 3. ADR-0004 changes

Updated:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`

Key refinements:

- Added `STT Provider Capability Profile` section.
- Added draft `SttProviderCapabilityProfileV1` for Lemonfox.
- Captured documented Lemonfox formats, upload limits, URL upload support,
  timestamps, word timestamps, speaker labels, Russian language support,
  callbacks and pricing hint.
- Marked WebM/Opus, OGG/Opus, max duration, provider-side cancellation and
  error taxonomy as runtime-proof items.
- Changed storage model from implied S3-only to `auto|s3|none`.
- Defined optional S3 behavior:
  - `auto`: use S3/object storage only when configured and healthy, otherwise
    transient lifecycle.
  - `s3`: require configured and healthy storage, fail fast if unavailable.
  - `none`: do not retain prepared audio after provider handoff/local lifecycle.
- Added `>100 MB` warning/fail/fallback reason codes.
- Added provider cancellation capability handling:
  - `supports_provider_cancel=true`: call provider cancel.
  - `supports_provider_cancel=false`: local cancel only.
  - `supports_provider_cancel=null/TBD`: treat as unsupported until proof.
- Added max duration as provider/internal capability instead of an implicit
  promise.
- Added draft `TranscriptionRuntimeCapabilitiesV1`.
- Added candidate endpoint:
  `GET /stage2-api/transcription/capabilities`.

## 4. Env/config contract changes

Updated:

- `docs/stage2/config/STT_ENV_CONTRACT.md`

Key refinements:

- Added documented Lemonfox direct and URL upload limits:
  - `STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB=100`
  - `STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB=1024`
- Kept duration env values blank/TBD:
  - `STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES=`
  - `STAGE2_STT_PROVIDER_MAX_DURATION_MINUTES=`
  - `STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES=`
- Added allowed output profiles:
  - `mp3_high_compat`
  - `opus_webm_compact`
  - `opus_ogg_compact`
  - `wav_pcm_safe`
- Changed storage default candidate to:
  - `STAGE2_STT_STORAGE_MODE=auto`
- Added allowed storage modes:
  - `auto`
  - `s3`
  - `none`
- Added storage health semantics through
  `TranscriptionRuntimeCapabilitiesV1`.
- Added `STAGE2_STT_DIRECT_UPLOAD_WARNING_MB=100`.
- Added provider cancel support flag:
  - `STAGE2_STT_PROVIDER_CANCEL_SUPPORT=unknown`
- Added runtime capabilities endpoint contract.

## 5. Related docs updated

Updated:

- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

Cross-doc alignment:

- Lemonfox docs facts now match across ADR, research and acceptance docs.
- Capability profile and runtime capabilities endpoint are treated as contracts,
  not implementation.
- Opus output remains a preferred candidate, not a final default.
- MP3 remains the source-proven fallback.
- S3 is optional by storage mode, not silently mandatory.
- Provider cancellation and max duration are explicit TBDs.

## 6. Runtime proof still required

Before implementation acceptance:

- Run Lemonfox smoke with approved key and approved non-sensitive audio.
- Prove `mp3_high_compat` against the Stage 2 proxy contract.
- Prove or reject `opus_webm_compact`.
- Prove or reject `opus_ogg_compact`.
- Decide final default output profile.
- Prove behavior for prepared audio over 100 MB.
- Decide whether Lemonfox public URL input path is allowed for corporate data.
- Prove storage mode behavior for `auto`, `s3` and `none`.
- Decide prepared-audio retention.
- Prove internal duration limit and provider max duration, or keep provider
  duration as accepted `TBD`.
- Prove provider-side cancellation if Lemonfox exposes it; otherwise keep local
  cancellation with late-result ignoring.
- Prove runtime capabilities endpoint does not expose secrets.

## 7. Non-goals preserved

- No Lemonfox account setup.
- No API key handling.
- No `.env.example` update.
- No compose update.
- No scripts update.
- No backend implementation.
- No frontend implementation.
- No production change.
- No ADR acceptance.

## 8. Result

ADR-0004 is more precise and reviewable, but still intentionally conservative:
the provider is selected as first adapter, not hardwired architecture; Lemonfox
documented facts are separated from runtime-proof gaps; operational choices are
captured as contracts and blockers instead of hidden assumptions.
