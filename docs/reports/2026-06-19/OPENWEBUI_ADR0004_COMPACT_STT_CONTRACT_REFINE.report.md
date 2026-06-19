# OpenWebUI ADR-0004 Compact STT Contract Refine Report

Date: 2026-06-19

## 1. Summary

ADR-0004 was compacted from a narrative review document into a contract-oriented
engineering ADR. The refine preserves the STT proxy decision, Lemonfox first
provider, env-driven output/storage/limits/cancel behavior, and non-goals.

No backend, frontend, provider setup, `.env`, compose, scripts, production
configuration or wasm/core binaries were changed.

## 2. Owner decisions applied

Applied owner decisions:

- proof matrix is no longer an ADR or implementation-planning gate;
- owner/operator proof is accepted for ADR planning;
- ffmpeg workflow is accepted as proven in two same-stack projects, including
  mobile and large-file cases;
- additional smoke tests are optional implementation/debug checks;
- output format is env/config driven;
- WebM/Opus vs OGG/Opus is env/config driven;
- Lemonfox is the first STT provider;
- Lemonfox capabilities are captured from docs and left for short
  implementation smoke where not documented;
- provider adapter returns capability profile;
- cancel uses provider cancel only when capability says supported;
- otherwise cancel is local and late provider result is ignored/cleaned by
  retention policy;
- prepared-audio storage follows env-driven `auto|s3|none`;
- source media storage is env-driven and off by default;
- retention days are env-driven;
- browser wasm input limit is 1 GB;
- Lemonfox direct upload limit is 100 MB;
- UI warning is required when file/prepared-audio is likely to exceed provider
  limit;
- ffmpeg assets default to self-hosted/internal static path in production.

## 3. Lemonfox docs/capabilities update

Checked sources:

- https://www.lemonfox.ai/apis/speech-to-text
- https://www.lemonfox.ai/

Documented facts retained:

- direct upload limit: 100 MB;
- URL upload limit: 1 GB;
- supported formats include `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`, `m4a`,
  `mp4`, `mpeg`, `mov`, `webm`;
- response formats: `json`, `text`, `srt`, `verbose_json`, `vtt`;
- `verbose_json` includes duration and segment timestamps;
- word timestamps are available;
- speaker labels are available, max 4 speakers;
- Russian is listed as supported;
- `callback_url` is documented;
- homepage says data is deleted immediately after processing.

Undocumented/TBD:

- exact Stage 2 WebM/Opus profile compatibility;
- exact Stage 2 OGG/Opus profile compatibility;
- provider-side cancel endpoint or stable job id;
- provider max duration;
- provider error taxonomy;
- retention detail beyond public homepage statement.

## 4. Proof matrix gate removed

ADR-0004 now states:

```text
Owner/operator proof is accepted for ADR planning.

The ffmpeg workflow is reported and accepted by the project owner as proven in
two projects with the same stack/architecture, including mobile and large-file
cases.

Additional smoke tests may be executed during implementation/debug, but a proof
matrix is not an ADR or implementation-planning gate.
```

The optional smoke checklist remains:

- desktop audio;
- desktop video;
- mobile audio;
- mobile video;
- large WAV;
- large video.

## 5. Runtime capability contract

ADR-0004 and `STT_ENV_CONTRACT` now keep:

```text
GET /stage2-api/transcription/capabilities
```

Contract fields:

```text
TranscriptionRuntimeCapabilitiesV1:
  selected_output_profile
  available_output_profiles
  max_browser_input_mb
  max_prepared_audio_mb
  max_duration_seconds
  storage_mode
  storage_available
  provider_id
  adapter_id
  supports_provider_cancel
  cancel_strategy
  supports_speaker_labels
  supports_timestamps
  warnings
```

Frontend uses this endpoint for limits, warnings, output-profile behavior and
cancel behavior without hardcoded Lemonfox assumptions.

## 6. Env/config contract

Updated env/config decisions:

```text
STAGE2_STT_OUTPUT_PROFILE=opus_webm_compact
STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat
STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_STT_DIRECT_UPLOAD_WARNING_MB=100
STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE=fail
STAGE2_STT_PROVIDER_CANCEL_SUPPORT=unknown
```

Allowed output profiles:

- `opus_webm_compact`;
- `opus_ogg_compact`;
- `mp3_high_compat`;
- `wav_pcm_safe`.

## 7. FFMPEG asset path decision

Updated production default:

```text
STAGE2_FFMPEG_ASSET_MODE=self_hosted
STAGE2_FFMPEG_CORE_BASE_URL=/stage2-assets/ffmpeg/0.12.6/
STAGE2_FFMPEG_PACKAGE_VERSION=0.12.6
STAGE2_FFMPEG_CORE_VERSION=0.12.6
```

Implementation note:

- place core/wasm/worker assets under app public/static path or internal CDN;
- configure base URL via env;
- load ffmpeg with explicit `coreURL`, `wasmURL`, `workerURL`;
- keep same-origin/self-hosted assets as production default.

## 8. Storage and retention modes

Storage env:

```text
STAGE2_STT_STORAGE_MODE=auto
STAGE2_STT_AUDIO_BUCKET=
STAGE2_STT_AUDIO_PREFIX=stage2/stt/prepared-audio/
STAGE2_STT_REQUIRE_STORAGE_HEALTH=false
STAGE2_STT_STORE_PREPARED_AUDIO=true
STAGE2_STT_STORE_SOURCE_MEDIA=false
STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS=
STAGE2_STT_TRANSCRIPT_RETENTION_DAYS=
```

Modes:

- `auto`: store prepared audio only when bucket is configured and healthy;
  otherwise transient lifecycle;
- `s3`: require configured and healthy storage; fail fast if unavailable;
- `none`: do not persist prepared audio.

Source media is never stored unless `STAGE2_STT_STORE_SOURCE_MEDIA=true`.

## 9. Cancel contract

Statuses:

```text
queued
preprocessing
uploading
processing
completed
failed
cancel_requested
cancelled
```

Reason codes:

```text
cancelled_by_user
provider_cancel_supported
provider_cancel_unsupported
provider_cancel_unknown
cancelled_locally_provider_continues
late_provider_result_ignored
```

For Lemonfox, provider cancel is `null/TBD` because the checked API docs do not
document cancel endpoint or stable job id. Stage 2 uses local cancel until
provider proof exists.

## 10. ADR compaction

ADR-0004 was reduced from about 993 lines to about 429 lines.

Removed/reduced:

- repeated explanatory prose;
- duplicated proof-matrix gate wording;
- repeated long runtime-proof lists;
- stale S3-only wording;
- narrative sections that duplicated decisions.

Kept:

- status `Proposed`;
- server-side STT proxy boundary;
- provider adapter factory;
- Lemonfox first-provider decision;
- provider capability profile;
- runtime capabilities endpoint;
- env-driven output/storage/limits/cancel;
- self-hosted ffmpeg asset default;
- non-goals.

## 11. Files changed

Primary files:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ROADMAP.md`

Report:

- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_COMPACT_STT_CONTRACT_REFINE.report.md`

## 12. Remaining implementation notes

Before or during implementation/debug:

- confirm selected output profile against Lemonfox with approved key/media;
- keep MP3 fallback available;
- decide internal max duration;
- verify prepared audio over 100 MB behavior;
- approve or reject Lemonfox URL upload path for corporate data;
- verify storage mode behavior for `auto`, `s3`, `none`;
- verify local cancel and late-result cleanup;
- verify no STT API key reaches browser bundle/storage/network logs.

These are implementation/debug tasks, not ADR planning blockers.

## 13. Final status

ADR-0004 remains Proposed but is now compact, contract-oriented and ready for
owner acceptance.
