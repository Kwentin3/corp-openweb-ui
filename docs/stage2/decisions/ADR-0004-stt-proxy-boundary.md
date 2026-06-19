# ADR-0004 STT Proxy Boundary

Status: Proposed

## 1. Decision Summary

Stage 2 transcription uses a server-side STT proxy/job boundary.

Accepted planning decisions:

- browser-to-provider STT calls are rejected;
- STT API keys stay server-side only;
- user-facing STT UX lives inside OpenWebUI chat/workspace UX;
- the Stage 2 STT sidecar is backend-only and has no separate user-facing GUI;
- MVP user-facing entrypoint is an explicit `Transcribe` action on an
  OpenWebUI audio/video media attachment;
- Lemonfox is the first STT provider through `LemonfoxSttAdapter`;
- orchestration uses `SttProviderAdapterFactory`, not direct Lemonfox coupling;
- browser ffmpeg preprocessing is a media-preparation asset, not a security
  boundary;
- output format is selected by env/config;
- WebM/Opus vs OGG/Opus is selected by env/config;
- MP3 remains compatibility fallback;
- provider capabilities are returned by adapter capability profile;
- frontend reads effective limits/capabilities from runtime endpoint;
- prepared-audio storage, source-media storage and retention are env-driven;
- ffmpeg wasm assets are self-hosted/internal static assets by production
  default;
- proof matrix is not an ADR or implementation-planning gate.

No implementation starts from this ADR. ADR acceptance still requires owner
approval or an explicit status change request.

## 2. Owner Proof Decision

Owner/operator proof is accepted for ADR planning.

The ffmpeg workflow is reported and accepted by the project owner as proven in
two projects with the same stack/architecture, including mobile and large-file
cases.

Additional smoke tests may be executed during implementation/debug, but a proof
matrix is not an ADR or implementation-planning gate.

Optional implementation smoke checklist:

- desktop audio;
- desktop video;
- mobile audio;
- mobile video;
- large WAV;
- large video.

Smoke status:

- `owner accepted`;
- `implementation smoke optional`;
- `not a blocking ADR gate`.

## 3. Boundary

### Browser

Owns:

- file selection;
- local media preprocessing after user action;
- selected output profile metadata;
- upload/progress/cancel UI;
- calls to internal Stage 2 endpoints only.

Does not own:

- provider API keys;
- provider selection authority;
- data policy;
- retention policy;
- provider capability inference;
- direct Lemonfox calls.

### OpenWebUI UX Surface

Owns:

- user-triggered transcription entrypoint through approved native extension
  mechanisms or a minimal integration patch;
- visible `Transcribe` affordance on supported media attachments;
- file attachment/reference handoff to the backend-side STT contract;
- transcript placement in chat/message/file/artifact UX;
- user-visible progress, error and cancel affordances sourced from backend
  state/events.

Does not own:

- provider keys;
- Lemonfox-specific decisions;
- sidecar domain orchestration;
- separate STT portal or user-facing sidecar UI.
- magic/implicit LLM-triggered transcription for MVP. Typed convenience such as
  "транскрибируй" may only map to the same explicit media attachment action
  contract.

### Stage 2 Backend / STT Proxy

Owns:

- auth/session and permission checks;
- output-profile validation;
- selected provider adapter;
- provider capability profile;
- runtime capabilities endpoint;
- prepared-audio size/duration/MIME checks;
- storage mode, storage health and retention;
- job lifecycle/status/progress/cancel;
- provider error mapping;
- transcript normalization;
- usage/cost metadata where available.

### STT Provider Adapter

Owns:

- provider endpoint and auth;
- request shape;
- supported input profiles;
- provider limits;
- URL upload support;
- timestamp/speaker-label support;
- provider cancellation capability;
- response parsing;
- normalized errors.

Provider responses are not product contracts. Adapters translate provider
responses into Stage 2 contracts.

## 4. Output Profiles

Draft env:

```text
STAGE2_STT_OUTPUT_PROFILE=opus_webm_compact
STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat
```

Allowed values:

```text
opus_webm_compact
opus_ogg_compact
mp3_high_compat
wav_pcm_safe
```

Profile candidates:

```text
opus_webm_compact:
  mime: audio/webm;codecs=opus
  container: webm
  codec: opus
  status: preferred candidate, selected by env/config

opus_ogg_compact:
  mime: audio/ogg;codecs=opus
  container: ogg
  codec: opus
  status: preferred candidate, selected by env/config

mp3_high_compat:
  mime: audio/mpeg
  container: mp3
  codec: libmp3lame
  status: source-proven compatibility fallback

wav_pcm_safe:
  mime: audio/wav
  container: wav
  codec: pcm_s16le
  status: large fallback candidate
```

Rules:

- frontend does not hardcode audio format;
- backend validates prepared audio against selected profile;
- adapter declares supported input profiles;
- WebM/Opus vs OGG/Opus is a config/runtime decision;
- MP3 remains fallback, not a permanent architecture constraint.

## 5. Provider Capability Contract

`SttProviderCapabilityProfileV1` required fields:

```text
provider_id
adapter_id
supported_input_profiles
max_direct_upload_mb
max_url_upload_mb
max_duration_seconds
supports_url_upload
supports_provider_cancel
supports_callbacks
supports_timestamps
supports_word_timestamps
supports_speaker_labels
max_speakers
supported_languages
response_formats
retention_policy_notes
cancel_strategy
unknowns
```

Rules:

- orchestration code reads provider capability profile;
- frontend receives effective capabilities through runtime endpoint;
- provider-specific behavior does not leak into UI/templates;
- `supports_provider_cancel=false` means
  `cancel_strategy=local_cancel_ignore_late_result`;
- `supports_provider_cancel=null` means
  `cancel_strategy=local_cancel_until_provider_proof`.

## 6. Lemonfox Capability Profile

Official Lemonfox docs checked: Speech-to-Text API and Lemonfox homepage.

Draft `SttProviderCapabilityProfileV1`:

```yaml
provider_id: lemonfox
adapter_id: lemonfox
supported_input_profiles:
  - mp3_high_compat
  - opus_webm_compact
  - opus_ogg_compact
  - wav_pcm_safe
max_direct_upload_mb: 100
max_url_upload_mb: 1024
max_duration_seconds: null
supports_url_upload: true
supports_provider_cancel: null
supports_callbacks: true
supports_timestamps: true
supports_word_timestamps: true
supports_speaker_labels: true
max_speakers: 4
supported_languages:
  - russian
response_formats:
  - json
  - text
  - srt
  - verbose_json
  - vtt
retention_policy_notes: homepage_says_deleted_immediately_after_processing_needs_policy_review
cancel_strategy: local_cancel_until_provider_proof
unknowns:
  - exact_webm_opus_stage2_profile
  - exact_ogg_opus_stage2_profile
  - provider_max_duration
  - provider_cancel_endpoint_or_job_id
  - provider_error_taxonomy
```

Documented:

- direct upload limit: 100 MB;
- URL upload limit: 1 GB;
- supported formats include `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`,
  `m4a`, `mp4`, `mpeg`, `mov`, `webm`;
- response formats: `json`, `text`, `srt`, `verbose_json`, `vtt`;
- `verbose_json` contains duration and segment timestamps;
- word timestamps are available with `timestamp_granularities[]=word`;
- speaker labels are available, max 4 speakers, with `verbose_json`;
- Russian is listed as supported;
- `callback_url` is documented for async/long audio completion;
- homepage states data is deleted immediately after processing.

Not documented enough for product contract:

- exact Stage 2 WebM/Opus output compatibility;
- exact Stage 2 OGG/Opus output compatibility;
- provider-side cancellation endpoint or stable job id;
- provider maximum duration;
- provider error taxonomy;
- retention details beyond public homepage statement.

## 7. Runtime Capabilities Endpoint

Endpoint:

```text
GET /stage2-api/transcription/capabilities
```

Contract:

```yaml
TranscriptionRuntimeCapabilitiesV1:
  selected_output_profile: string
  available_output_profiles: string[]
  max_browser_input_mb: number
  max_prepared_audio_mb: number
  max_duration_seconds: number | null
  storage_mode: auto | s3 | none
  storage_available: boolean
  provider_id: string
  adapter_id: string
  supports_provider_cancel: boolean | null
  cancel_strategy: string
  supports_speaker_labels: boolean
  supports_timestamps: boolean
  warnings: string[]
```

Frontend uses this endpoint to:

- show limits;
- show early warnings;
- select/label output profile behavior;
- expose cancel behavior;
- avoid hardcoded provider assumptions.

The endpoint must not expose API keys, raw `.env` values, storage credentials or
raw provider responses.

## 8. Env Contract

Canonical draft:

- [STT_ENV_CONTRACT](../config/STT_ENV_CONTRACT.md)

Required env groups:

```text
STAGE2_STT_PROVIDER=lemonfox
STAGE2_STT_PROVIDER_ADAPTER=lemonfox
STAGE2_STT_OUTPUT_PROFILE=opus_webm_compact
STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat

STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES=
STAGE2_FFMPEG_ASSET_MODE=self_hosted
STAGE2_FFMPEG_CORE_BASE_URL=/stage2-assets/ffmpeg/0.12.6/
STAGE2_FFMPEG_PACKAGE_VERSION=0.12.6
STAGE2_FFMPEG_CORE_VERSION=0.12.6

STAGE2_STT_STORAGE_MODE=auto
STAGE2_STT_AUDIO_BUCKET=
STAGE2_STT_AUDIO_PREFIX=stage2/stt/prepared-audio/
STAGE2_STT_REQUIRE_STORAGE_HEALTH=false
STAGE2_STT_STORE_PREPARED_AUDIO=true
STAGE2_STT_STORE_SOURCE_MEDIA=false
STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS=
STAGE2_STT_TRANSCRIPT_RETENTION_DAYS=

STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_STT_DIRECT_UPLOAD_WARNING_MB=100
STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE=fail
STAGE2_STT_PROVIDER_MAX_DURATION_MINUTES=
STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES=

STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED=true
STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL=true
STAGE2_STT_PROVIDER_CANCEL_SUPPORT=unknown
```

This is a planning contract, not a `.env.example`.

## 9. FFMPEG Assets

Production default:

```text
STAGE2_FFMPEG_ASSET_MODE=self_hosted
STAGE2_FFMPEG_CORE_BASE_URL=/stage2-assets/ffmpeg/0.12.6/
STAGE2_FFMPEG_PACKAGE_VERSION=0.12.6
STAGE2_FFMPEG_CORE_VERSION=0.12.6
```

Rules:

- production assets are same-origin app static assets or internal CDN;
- public CDN is allowed for dev/proof/fallback;
- production CDN requires explicit approval and pinned versions;
- exact versions are pinned;
- no wasm/core binaries or full FFmpeg source are vendored by this docs task.

Typical implementation pattern:

- place core/wasm/worker assets under public/static path or internal CDN;
- configure base URL via env;
- load ffmpeg with explicit `coreURL`, `wasmURL`, `workerURL`;
- keep same-origin/self-hosted assets as production default.

## 10. Storage and Retention

Draft env:

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

- `auto`: if bucket configured and healthy, store prepared audio; otherwise use
  transient lifecycle and do not persist prepared audio;
- `s3`: require configured/healthy storage; fail fast if unavailable;
- `none`: do not persist prepared audio; transcript retention remains separate.

Source media:

- never stored unless `STAGE2_STT_STORE_SOURCE_MEDIA=true`.

Retention:

- prepared-audio retention days are env-driven;
- transcript retention days are env-driven;
- late provider results follow retention/cancel policy.

## 11. Limits and Warnings

Draft env:

```text
STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_STT_DIRECT_UPLOAD_WARNING_MB=100
STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE=fail
```

Rules:

- frontend receives effective limits from runtime capabilities endpoint;
- if source file is likely to exceed provider prepared-audio limit, UI shows
  early warning;
- backend checks exact prepared-audio size after preprocessing;
- if prepared audio exceeds 100 MB and no approved fallback is active, backend
  fails with typed error.

Reason codes:

```text
provider_direct_upload_limit_warning
prepared_audio_too_large
provider_direct_upload_limit_exceeded
storage_required_for_large_audio
```

## 12. Cancel Contract

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

Rules:

- preprocessing cancel terminates ffmpeg worker;
- upload cancel aborts upload;
- provider cancel is called only if capability says supported;
- otherwise local cancel marks job cancelled and ignores/cleans late result;
- late provider result follows retention policy.

For Lemonfox, provider cancel is not documented on the checked STT API page, so
Stage 2 uses local cancel until provider proof exists.

## 13. Internal Contracts

Contract candidates:

- `TranscriptionJobV1`:
  job id, user/workspace, source metadata, prepared-audio metadata, storage
  mode/health, output profile, provider/adapter, status, progress, cancel
  fields, retention and typed error.
- `TranscriptResultV1`:
  job id, language, text, normalized segments, speakers, word timestamps,
  duration, output profile, provider adapter, warnings and internal raw-response
  reference if retained.
- `UsageEventV1`:
  provider adapter, model, upload bytes, preprocessing units, STT billable
  units, estimated cost and correlation id.
- `PolicyDecisionV1`:
  allowed/denied transcription action with user/workspace, data class, provider
  class, output profile, selected adapter and reason.
- `TranscriptionRuntimeCapabilitiesV1`:
  effective UI-safe transcription capability contract.

## 14. Endpoint Boundary

Draft endpoints:

```text
GET /stage2-api/transcription/capabilities
POST /stage2-api/transcription/jobs
GET /stage2-api/transcription/jobs/{job_id}
GET /stage2-api/transcription/jobs/{job_id}/result
POST /stage2-api/transcription/jobs/{job_id}/cancel
```

Rules:

- final routing depends on OpenWebUI auth/session proof;
- authenticated job routes also depend on a passed OpenWebUI media attachment
  action runtime probe for explicit trigger, files, transcript return, progress
  and cancel;
- request/response schemas are versioned;
- long-running transcription uses job lifecycle;
- short files may still complete synchronously behind job contract;
- routes prefer sidecar/internal backend API or thin shim over deep core fork.
- no route is implemented to support a separate user-facing STT GUI.
- sidecar route/API is not a standalone UX.

## 15. Remaining Implementation Notes

Implementation/debug should verify:

- Lemonfox smoke with approved key and approved non-sensitive audio;
- selected Opus profile or MP3 fallback against Lemonfox;
- prepared audio over 100 MB behavior;
- URL upload only if storage expiry/access review approves it;
- storage mode behavior for `auto`, `s3`, `none`;
- selected internal max duration;
- provider max duration if Lemonfox documents/proves one;
- local cancel and late-result cleanup;
- no STT key in browser bundle, storage or network logs.

These are implementation/debug checks, not ADR planning blockers.

## 16. Non-Goals

- No backend implementation.
- No frontend implementation.
- No Lemonfox setup.
- No real API keys.
- No `.env` changes.
- No compose/env/scripts changes.
- No production changes.
- No wasm/core binary vendoring.
- No ADR status change.

## 17. Links

- [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md)
- [IMPLEMENTATION_GATES](../IMPLEMENTATION_GATES.md)
- [STT_ENV_CONTRACT](../config/STT_ENV_CONTRACT.md)
- [TRANSCRIPTION_STT.blueprint](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
