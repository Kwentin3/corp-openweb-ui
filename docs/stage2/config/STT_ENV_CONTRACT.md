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
```

Rules:

- `STAGE2_LEMONFOX_API_KEY` is server-side only.
- No Lemonfox key may be exposed through browser config, browser storage,
  browser logs or `NEXT_PUBLIC_*`.
- The 100 MB value reflects the Lemonfox direct upload prepared-audio limit.
- URL/object-storage provider paths remain fallback candidates only until
  compatibility, expiry and storage-access behavior are approved.

## 4. Output profiles

Draft env names:

```text
STAGE2_STT_OUTPUT_PROFILE=opus_webm_compact
STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat
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
```

Rules:

- Browser-side wasm input limit is 1 GB / 1024 MB.
- Duration limit is not selected yet and stays blank/TBD until accepted.
- Backend still validates size, duration, MIME/content-type and selected output
  profile; browser metadata is not trusted as authority.

## 6. ffmpeg asset loading

Draft env names:

```text
STAGE2_FFMPEG_ASSET_MODE=self_hosted
STAGE2_FFMPEG_CORE_BASE_URL=/stage2-assets/ffmpeg/
STAGE2_FFMPEG_PACKAGE_VERSION=0.12.6
STAGE2_FFMPEG_CORE_VERSION=0.12.6
```

Rules:

- `self_hosted` is the production default.
- `cdn` is allowed for dev/proof/fallback, or production only with explicit
  approval and pinned versions.
- Self-hosted assets should be served under the portal domain or an internal
  CDN.
- Cache headers, rollback path and license notices must be documented before
  implementation.
- No wasm/core binaries or full FFmpeg source are committed by this docs
  contract.

## 7. Storage

Draft env names:

```text
STAGE2_STT_STORAGE_MODE=s3
STAGE2_STT_AUDIO_BUCKET=
STAGE2_STT_AUDIO_PREFIX=stage2/stt/prepared-audio/
STAGE2_STT_STORE_PREPARED_AUDIO=true
STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS=
STAGE2_STT_STORE_SOURCE_MEDIA=false
STAGE2_STT_TRANSCRIPT_RETENTION_DAYS=
```

Rules:

- Store normalized/prepared audio that was sent to the provider.
- Storage must be configurable through server-side env/config.
- Source media storage is not enabled silently.
- Retention days must be decided before implementation acceptance.
- Object keys must not include provider secrets or unnecessary sensitive
  metadata.

## 8. Limits

Draft env names:

```text
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE=fail
```

Allowed `STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE` values:

```text
fail
use_url_upload_if_supported
use_object_storage_provider_path
```

Rules:

- Default behavior is `fail` with a typed error unless fallback path is
  approved.
- Do not assert URL upload or object-storage provider path until Lemonfox
  compatibility, expiry and access-control behavior are proven.
- Candidate reason codes include:
  - `prepared_audio_too_large`;
  - `provider_direct_upload_limit_exceeded`;
  - `unsupported_input_format`;
  - `preprocessing_failed`.

## 9. Cancel behavior

Draft env names:

```text
STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED=true
STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL=true
```

Rules:

- If provider API supports job cancellation, backend should call provider
  cancel.
- If provider API does not support cancellation, backend marks local job
  cancelled and ignores/cleans late provider result according to retention
  policy.
- Candidate reason codes include:
  - `cancelled_by_user`;
  - `provider_cancel_unsupported`;
  - `cancelled_locally_provider_continues`.

## 10. Security notes

- No API keys in browser.
- Env values are server-side only.
- No secrets in Git.
- No provider keys in `NEXT_PUBLIC_*` or browser bundle.
- Do not print `.env` values in reports, logs, screenshots or operator proof.
- This document is a draft env/config contract, not a final `.env.example`.
