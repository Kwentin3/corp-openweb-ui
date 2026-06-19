# STT Environment / Configuration Contract

## 1. Purpose

This document defines the draft server-side environment/configuration contract
for Stage 2 transcription.

It is a planning contract, not a final `.env.example` and not implementation.
Real values, provider keys and storage credentials must stay server-side and
out of Git.

## 2. Provider selection

Draft env names:

```text
STAGE2_STT_PROVIDER=lemonfox
STAGE2_STT_PROVIDER_ADAPTER=lemonfox
```

Rules:

- Lemonfox is the first STT provider for Stage 2.
- `LemonfoxSttAdapter` is the first adapter behind
  `SttProviderAdapterFactory`.
- Lemonfox is not hardwired architecture; future providers can be added through
  adapters without changing browser preprocessing.

## 3. Lemonfox

Draft env names:

```text
STAGE2_LEMONFOX_API_KEY=
STAGE2_LEMONFOX_BASE_URL=https://api.lemonfox.ai
STAGE2_LEMONFOX_MODEL=
STAGE2_LEMONFOX_LANGUAGE=ru
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=false
STAGE2_LEMONFOX_ENABLE_TIMESTAMPS=true
STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB=100
STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB=1024
STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES=
```

Rules:

- `STAGE2_LEMONFOX_API_KEY` is server-side only.
- No Lemonfox key may be exposed through browser config, browser storage,
  browser logs or `NEXT_PUBLIC_*`.
- The 100 MB value reflects the Lemonfox direct upload prepared-audio limit.
- The 1024 MB value reflects the documented Lemonfox public URL input limit.
- Lemonfox maximum audio duration is not documented and remains blank/TBD until
  runtime proof or provider confirmation.
- URL/object-storage provider paths remain fallback candidates only until
  compatibility, expiry and storage-access behavior are approved.
- Provider-side cancellation is not documented on the checked Lemonfox STT API
  page; treat it as unknown/unsupported until proven.

## 4. Output profiles

Draft env names:

```text
STAGE2_STT_OUTPUT_PROFILE=opus_webm_compact
STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat
```

Allowed `STAGE2_STT_OUTPUT_PROFILE` values:

```text
opus_webm_compact
opus_ogg_compact
mp3_high_compat
wav_pcm_safe
```

Rules:

- Output profile is selected through policy/config.
- Opus is the preferred default candidate if Lemonfox compatibility proof
  passes.
- Do not choose permanently between `opus_webm_compact` and
  `opus_ogg_compact` until Lemonfox compatibility proof is captured.
- MP3 / `audio/mpeg` remains the source-proven compatibility fallback.
- Frontend must not hardcode output format.
- Default profile can change via env/config without changing orchestration code.

## 5. Browser preprocessing limits

Draft env names:

```text
STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES=
STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES=
```

Rules:

- Browser-side wasm input limit is 1 GB / 1024 MB.
- Browser and internal duration limits are not selected yet and stay blank/TBD
  until accepted.
- Backend still validates size, duration, MIME/content-type and selected output
  profile; browser metadata is not trusted as authority.

## 6. ffmpeg asset loading

Draft env names:

```text
STAGE2_FFMPEG_ASSET_MODE=self_hosted
STAGE2_FFMPEG_CORE_BASE_URL=/stage2-assets/ffmpeg/0.12.6/
STAGE2_FFMPEG_PACKAGE_VERSION=0.12.6
STAGE2_FFMPEG_CORE_VERSION=0.12.6
```

Rules:

- `self_hosted` is the production default.
- `cdn` is allowed for dev/proof/fallback, or production only with explicit
  approval and pinned versions.
- Self-hosted assets should be served under the app public/static path, portal
  domain or an internal CDN.
- Cache headers, rollback path and license notices must be documented before
  implementation.
- No wasm/core binaries or full FFmpeg source are committed by this docs
  contract.
- Typical implementation loads ffmpeg with explicit `coreURL`, `wasmURL` and
  `workerURL` derived from `STAGE2_FFMPEG_CORE_BASE_URL`.

## 7. Storage

Draft env names:

```text
STAGE2_STT_STORAGE_MODE=auto
STAGE2_STT_REQUIRE_STORAGE_HEALTH=false
STAGE2_STT_AUDIO_BUCKET=
STAGE2_STT_AUDIO_PREFIX=stage2/stt/prepared-audio/
STAGE2_STT_STORE_PREPARED_AUDIO=true
STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS=
STAGE2_STT_STORE_SOURCE_MEDIA=false
STAGE2_STT_TRANSCRIPT_RETENTION_DAYS=
```

Allowed `STAGE2_STT_STORAGE_MODE` values:

```text
auto
s3
none
```

Rules:

- `auto`: store normalized/prepared audio in S3/object storage when bucket,
  prefix and storage health are available; otherwise use transient
  local/server lifecycle and report non-durable storage through runtime
  capabilities.
- `s3`: require configured and healthy S3/object storage; fail fast if storage
  is unavailable.
- `none`: do not retain prepared audio after provider handoff/local lifecycle.
- `STAGE2_STT_STORE_PREPARED_AUDIO` must not override `none`; it is only a
  retention detail for storage-capable modes.
- Storage must be configurable through server-side env/config.
- Storage health must be visible to backend policy and
  `TranscriptionRuntimeCapabilitiesV1`.
- Source media storage is not enabled silently.
- Retention days must be decided before implementation acceptance.
- Object keys must not include provider secrets or unnecessary sensitive
  metadata.

## 8. Limits

Draft env names:

```text
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_STT_DIRECT_UPLOAD_WARNING_MB=100
STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE=fail
STAGE2_STT_PROVIDER_MAX_DURATION_MINUTES=
STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES=
```

Allowed `STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE` values:

```text
fail
use_url_upload_if_supported
use_object_storage_provider_path
```

Rules:

- Warn before provider upload when prepared audio actual/estimated size exceeds
  `STAGE2_STT_DIRECT_UPLOAD_WARNING_MB`.
- Default behavior is `fail` with a typed error unless fallback path is
  approved.
- Do not assert URL upload or object-storage provider path until Lemonfox
  compatibility, expiry and access-control behavior are proven.
- Provider max duration remains blank/TBD because Lemonfox docs do not document
  it; internal max duration must be chosen before production acceptance.
- Candidate reason codes include:
  - `provider_direct_upload_limit_warning`;
  - `prepared_audio_too_large`;
  - `provider_direct_upload_limit_exceeded`;
  - `storage_required_for_large_audio`;
  - `duration_limit_exceeded`;
  - `unsupported_input_format`;
  - `preprocessing_failed`.

## 9. Cancel behavior

Draft env names:

```text
STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED=true
STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL=true
STAGE2_STT_PROVIDER_CANCEL_SUPPORT=unknown
```

Allowed `STAGE2_STT_PROVIDER_CANCEL_SUPPORT` values:

```text
true
false
unknown
```

Rules:

- If provider API supports job cancellation, backend should call provider
  cancel.
- If provider cancel support is `unknown`, backend must not claim provider-side
  cancellation and must use local cancellation behavior.
- If provider API does not support cancellation, backend marks local job
  cancelled and ignores/cleans late provider result according to retention
  policy.
- Candidate reason codes include:
  - `cancelled_by_user`;
  - `provider_cancel_unsupported`;
  - `provider_cancel_unknown`;
  - `provider_cancel_supported`;
  - `late_provider_result_ignored`;
  - `cancelled_locally_provider_continues`.

## 10. Runtime capabilities endpoint

Candidate endpoint:

```text
GET /stage2-api/transcription/capabilities
```

Candidate contract:

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

Rules:

- The endpoint returns effective server-side provider profile, output profiles,
  size/duration limits, storage mode/health, timestamp/speaker-label support
  and provider-cancel support.
- UI uses the endpoint to show limits, warnings, output-profile behavior and
  cancel behavior without hardcoded provider assumptions.
- It must not expose API keys, storage credentials, raw `.env` values or raw
  provider responses.
- UI reads this endpoint for warnings and affordances; UI does not infer
  provider capabilities from hardcoded Lemonfox assumptions.

## 11. Security notes

- No API keys in browser.
- Env values are server-side only.
- No secrets in Git.
- No provider keys in `NEXT_PUBLIC_*` or browser bundle.
- Do not print `.env` values in reports, logs, screenshots or operator proof.
- This document is a draft env/config contract, not a final `.env.example`.
