# ADR-0004 STT Proxy Boundary

Status: Proposed

## 1. Context

Transcription is a priority Stage 2 scenario. PRD-1 states that audio/video
transcription should reuse an existing browser ffmpeg workflow as a technical
asset, then send prepared audio to a server-side STT boundary.

The current repository contains Stage 2 planning docs and research, not the
source code of the external ffmpeg workflow. Earlier local inspection found
useful STT/upload context in `D:\Users\Roman\Desktop\Проекты\AutoProtokol`, but
did not find the browser ffmpeg preprocessing implementation there.

A later external inspection report and operator input confirmed the browser-side
ffmpeg workflow contract. The transferable source workflow uses
`@ffmpeg/ffmpeg` v0.12.6, accepts audio/video input and produces MP3 /
`audio/mpeg` with
`ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3` as the
source-proven compatibility fallback. MP3 / `audio/mpeg` is a proven source
workflow output, not a permanent architecture constraint. Browser preprocessing
must expose an output profile rather than hardcode MP3 as the only possible
output. Opus is the preferred default candidate if Lemonfox compatibility proof
passes.
The prepared browser `Blob` is uploaded through a presigned/internal-storage
path, then backend STT orchestration calls the provider. API keys do not go to
the browser and the browser does not call STT providers directly.

Operator manual proof also confirms that the workflow was manually tested on a
mobile device with large videos and large WAV files and worked correctly in
those reported cases. This is useful operator evidence, not a repository-owned
automated proof matrix. Stage 2 implementation acceptance still needs a
lightweight reproducible proof matrix with device/browser/file metadata and
production dependency decisions.

Lemonfox is the first STT provider for Stage 2, not hardwired architecture.
`LemonfoxSttAdapter` is the first adapter behind the mandatory STT Provider
Adapter Factory. Existing research also keeps native OpenWebUI STT as a useful
baseline to test, because OpenWebUI has native STT configuration and
OpenAI-compatible backend paths. PRD-1 transcription is broader than chat-input
STT: it includes audio/video preprocessing, STT Provider Adapter Factory
behavior, job lifecycle, progress/cancel UX, S3/object storage for normalized
audio, env-driven retention/limits/config, template output and usage visibility.

Stage 2 uses domain isolation and backend-first contract boundaries. OpenWebUI
remains the upstream product shell; custom Stage 2 logic should live in bounded
domain services, internal APIs or thin integration shims. API keys, policy,
retention, manager visibility and usage accounting must not be owned by the
browser UI.

Related boundary map: [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md).

## 2. Problem

If transcription is implemented as a UI/upload feature without a backend
boundary, several risks appear:

- STT API keys can leak into browser code, network calls or logs;
- provider-specific response shapes can leak into UI, prompts or templates;
- orchestration code can become coupled to one STT provider;
- the source-proven MP3 workflow can become a hardcoded output constraint;
- public CDN ffmpeg assets can become an unapproved production dependency;
- auth, permissions, data policy, limits and retention become split between
  browser, OpenWebUI and provider code;
- progress, cancel and retry behavior is hard to make stable;
- file lifecycle, temporary blobs, transcript storage and usage events become
  unclear;
- long audio/video can hit HTTP, upload, provider or browser timeouts;
- future provider replacement becomes expensive;
- ffmpeg preprocessing can be mistaken for a security boundary.

The ffmpeg workflow is media preprocessing only. The server-side boundary still
must validate auth/session, file metadata, policy, provider choice, limits,
retention and errors.

## 3. Decision Needed

Which boundary should Stage 2 use for transcription?

Options under review:

1. Native OpenWebUI STT only.
2. Server-side STT proxy/job service.
3. Direct browser-to-provider call.
4. External standalone transcription tool.
5. Deep OpenWebUI fork.

This ADR does not approve implementation. It defines the recommended boundary,
draft contracts, runtime proofs and inputs required before implementation
planning.

## 4. Options

### Option A. Native OpenWebUI STT only

Pros:

- smallest custom code surface;
- fastest baseline proof if deployed OpenWebUI supports the required settings;
- upstream-first and easier to maintain.

Cons:

- may not cover PRD-1 audio/video workflow and prepared ffmpeg output;
- may not expose Lemonfox-specific behavior such as `speaker_labels`,
  `callback_url`, verbose response handling or word timestamps;
- may not provide the needed job/progress/cancel lifecycle;
- may be weak for large files and meeting-output templates;
- still requires runtime proof on the pinned/deployed OpenWebUI version.

Review stance:

- keep as a baseline proof path;
- do not assume it replaces the proxy unless it satisfies all PRD-1 acceptance
  criteria.

### Option B. Server-side STT proxy/job service

Pros:

- keeps STT provider API keys server-side only;
- centralizes auth/session, permissions, data policy, limits and retention;
- normalizes transcripts before UI/templates see them;
- normalizes provider errors into stable UI-facing reason codes;
- supports usage events and cost review;
- supports long-running job status, progress, cancel and retry;
- can support Lemonfox, OpenAI or future STT providers through an adapter
  factory;
- matches Stage 2 domain isolation and backend-first delivery.

Cons:

- more backend work than native-only STT;
- requires an approved OpenWebUI auth/session propagation path;
- requires job storage or an equivalent lifecycle model;
- requires smoke tests before UI integration.

Review stance:

- recommended option for PRD-1 transcription.

### Option C. Direct browser-to-provider call

Pros:

- shortest data path;
- less backend code.

Cons:

- exposes provider API keys or forces unsafe client-side credentials;
- prevents centralized usage, policy, retention and permission checks;
- makes provider response shape part of the browser contract;
- is not acceptable for a corporate portal boundary.

Review stance:

- reject.

### Option D. External standalone transcription tool

Pros:

- can reuse the existing workflow quickly if the artifact is already packaged;
- minimizes changes inside OpenWebUI.

Cons:

- weakens the single corporate portal experience;
- makes workspaces/templates/usage/policy integration harder;
- can create a parallel identity and retention surface;
- still needs server-side key handling if a provider is called.

Review stance:

- possible fallback or interim demo, not the preferred Stage 2 boundary.

### Option E. Deep OpenWebUI fork

Pros:

- maximum UX control.

Cons:

- high maintenance cost;
- higher upstream drift risk;
- harder upgrades;
- premature before native, sidecar and thin-shim options are proven.

Review stance:

- do not choose as the first path.

## 5. Recommended Option

Recommend:

`Option B. Server-side STT proxy/job service`.

Constraints:

- native OpenWebUI STT may be tested as a baseline;
- if native STT unexpectedly satisfies all PRD-1 acceptance criteria, proxy
  scope can be reduced;
- direct browser-to-provider is rejected;
- deep fork is not the first choice;
- final UI/browser integration starts only after backend contract and runtime
  proof;
- the previous `missing ffmpeg artifact` blocker is removed;
- implementation readiness still requires ADR approval, a lightweight
  reproducible proof matrix and production dependency decisions;
- browser preprocessing must use an output profile contract, not a permanent
  MP3-only architecture;
- backend provider calls must go through an STT Provider Adapter Factory;
- `LemonfoxSttAdapter` is the first Stage 2 adapter;
- self-hosted ffmpeg wasm assets are the corporate production default;
- CDN mode remains allowed for dev/proof/fallback only, or production with
  explicit approval and pinned versions;
- browser preprocessing input limit is `1024 MB`;
- Lemonfox direct prepared-audio upload limit is `100 MB`;
- normalized/prepared audio storage is controlled by `auto|s3|none` with
  env-configured bucket, prefix, health and retention when S3/object storage is
  used;
- cancel UX is required where technically possible across preprocessing,
  upload and job lifecycle.

## 6. Contract Boundary

### Browser

Owns:

- multimedia file selection;
- local file type detection before upload;
- local ffmpeg preprocessing after user action;
- audio extraction/conversion according to the selected output profile;
- transferable source-proven compatibility fallback: MP3 / `audio/mpeg`
  browser `Blob`;
- source workflow command:
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`;
- local preprocessing progress/cancel UI;
- selected output profile metadata;
- upload of the prepared audio blob to internal storage / Stage 2 backend;
- display of job status and normalized transcript result.

Does not own:

- STT provider API keys;
- provider selection policy;
- default output profile policy;
- storage/retention policy;
- STT env/config values;
- data policy decision;
- final usage accounting;
- retention decision;
- direct call to Lemonfox or another STT provider;
- source video upload unless an explicit fallback path is approved;
- internal transcript schema.

### Stage 2 Backend / STT Proxy

Owns:

- auth/session verification through OpenWebUI or an approved internal boundary;
- permission check for transcription use;
- data policy check;
- file validation;
- max size and duration limits;
- prepared-audio MIME/content-type validation;
- validation against the selected output profile;
- validation against the 100 MB direct-upload prepared-audio limit for
  Lemonfox;
- validation that does not trust browser-side file metadata blindly;
- prepared/normalized audio storage in S3/object storage;
- temporary file/blob cleanup;
- STT Provider Adapter Factory call;
- provider capability and supported-input-profile mapping;
- API key handling;
- transcript normalization;
- error normalization;
- usage event emission;
- retention and lifecycle decision;
- env-driven limits, provider, storage and retention config;
- job status;
- cancel/retry behavior;
- asset loading mode decision when it affects deployment policy;
- internal health/smoke endpoint.

Does not own:

- browser-local media decoding UX;
- raw provider response as a UI contract;
- final business templates unless a separate template contract approves that
  ownership.

### STT Provider

Owns:

- speech-to-text processing;
- provider-specific timestamps when available;
- provider-specific speaker labels when available;
- provider-specific response fields and errors.

Does not own:

- internal transcript schema;
- customer policy decision;
- OpenWebUI permissions;
- retention or audit policy;
- UI-facing error language.

## 7. FFMPEG Workflow Artifact Inspection Status

Status:

- `external ffmpeg workflow artifact inspected`;
- `transferable browser-side preprocessing contract found`;
- `operator manual proof confirms reported mobile and large-file scenarios`;
- `implementation readiness still requires lightweight proof matrix and
  production dependency decisions`;
- `Lemonfox selected as first STT provider for Stage 2`;
- `self_hosted selected as production default for ffmpeg assets`;
- `S3/object storage selected for normalized prepared audio`.

Source workflow contract found:

- browser input accepts `audio/*` and `video/*`;
- source project UI limit and Stage 2 browser preprocessing input limit:
  1 GB / `1024 MB`;
- source-confirmed formats: MP3, WAV, M4A, WebM, MP4 video and MOV video;
- package: `@ffmpeg/ffmpeg` v0.12.6;
- source asset hosting: CDN through `unpkg.com`;
- transformation command:
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`;
- source-proven fallback output profile: `mp3_high_compat`;
- source-proven output container: MP3;
- source-proven output codec: `libmp3lame`;
- source-proven output MIME: `audio/mpeg`;
- browser output shape: `Blob`;
- handoff pattern: browser prepared-audio blob -> presigned/internal-storage
  upload -> backend STT orchestration by object key;
- security shape: no STT provider API keys in browser, no direct browser call to
  STT provider.

Operator manual proof:

- operator reported manual testing on a mobile device;
- large videos were tested;
- large WAV files were tested;
- reported result: workflow completed correctly;
- this is useful operator evidence;
- this is not the same as a reproducible repository-owned proof matrix.

Required lightweight proof matrix before implementation acceptance:

| Case | Purpose |
| ---- | ------- |
| desktop audio | baseline audio preprocessing |
| desktop video | baseline video extraction |
| mobile audio | mobile browser audio path |
| mobile video | mobile browser video path |
| large WAV | large audio case |
| large video | large media case |

Required fields are device, browser, file type, file size, duration, selected
output profile, result and evidence. Operator manual proof exists. The
lightweight proof matrix captures reproducibility for the already observed
scenarios; it must not become a broad certification program.

Production decisions and caveats:

- MP3 / `audio/mpeg` is proven in the source workflow and remains the
  compatibility fallback;
- Opus is the preferred default candidate if Lemonfox compatibility proof
  passes;
- do not choose between `audio/webm;codecs=opus` and
  `audio/ogg;codecs=opus` without Lemonfox compatibility proof;
- public CDN dependency through `unpkg.com` must not be accepted silently as a
  corporate production default;
- production default for ffmpeg assets is `self_hosted`;
- define max accepted file size, max duration, fallback behavior and typed
  errors for unsupported/too-large files.

Inspection document:

- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)

## 8. Output Profiles

Browser preprocessing must support an output profile contract.

Example profile candidates:

```text
mp3_high_compat:
  mime: audio/mpeg
  container: mp3
  codec: libmp3lame
  status: source-proven fallback / compatibility profile

opus_webm_compact:
  mime: audio/webm;codecs=opus
  container: webm
  codec: opus
  status: preferred default candidate pending Lemonfox compatibility proof

opus_ogg_compact:
  mime: audio/ogg;codecs=opus
  container: ogg
  codec: opus
  status: preferred default candidate pending Lemonfox compatibility proof

wav_pcm_safe:
  mime: audio/wav
  container: wav
  codec: pcm_s16le
  status: fallback candidate, larger files
```

Rules:

- output profile is selected by policy, setting or STT provider compatibility;
- frontend must not hardcode MP3 as the only possible output;
- backend validates prepared audio against the selected output profile;
- STT provider adapter declares supported input profiles;
- default profile can be changed via env/config without changing orchestration
  code;
- Lemonfox official docs list `opus`, `ogg` and `webm` as supported formats,
  but do not explicitly prove exact WebM/Opus or OGG/Opus compatibility for
  the Stage 2 ffmpeg output contract;
- do not choose between WebM/Opus and OGG/Opus until Lemonfox compatibility
  proof is captured.

MP3 / `audio/mpeg` remains the source-proven compatibility profile. Opus is the
preferred default candidate if Lemonfox compatibility proof passes.

## 9. STT Provider Adapter Factory

Stage 2 backend orchestration must not depend directly on Lemonfox, OpenAI,
Deepgram, Yandex SpeechKit, Local Whisper or other OpenAI-compatible STT
response details.

Lemonfox is the first provider for Stage 2. That means the first adapter is
`LemonfoxSttAdapter`, with conceptual default adapter id `lemonfox`. This is a
provider decision, not permission to couple orchestration or browser
preprocessing to Lemonfox response shapes.

Concept:

```text
SttProviderAdapterFactory
  default_adapter_id: lemonfox
  -> LemonfoxSttAdapter
  -> OpenAiSttAdapter
  -> DeepgramSttAdapter
  -> YandexSpeechKitAdapter
  -> LocalWhisperAdapter
  -> OtherOpenAiCompatibleSttAdapter
```

Each adapter owns:

- provider endpoint;
- auth;
- request format;
- supported input profiles;
- provider limits;
- diarization/speaker label support;
- timestamp support;
- response parsing;
- error mapping;
- cost/usage metadata if available.

Adapters return normalized `TranscriptResultV1`. Errors are normalized into
`ProviderErrorV1` or documented error reason codes.

Rules:

- UI and orchestration must not depend on raw provider response;
- provider can be changed without rewriting browser preprocessing and
  templates;
- Lemonfox is the first provider, not hardwired architecture;
- future providers can be added without changing browser preprocessing.

## 10. STT Provider Capability Profile

Each STT adapter must expose a provider capability profile. The profile is
runtime/config evidence for orchestration and UI affordances. It is not a
secret store and does not replace adapter-specific request/response handling.

Draft `SttProviderCapabilityProfileV1` for Lemonfox:

```yaml
profile_version: 1
provider_id: lemonfox
adapter_id: lemonfox
source: official_docs_plus_runtime_proof
status: proposed_needs_runtime_proof
base_url_default: https://api.lemonfox.ai
eu_base_url_candidate: https://eu-api.lemonfox.ai
transcription_endpoint: /v1/audio/transcriptions
supported_input_profiles:
  mp3_high_compat: documented_format_mp3_source_proven
  opus_webm_compact: docs_list_opus_webm_needs_runtime_proof
  opus_ogg_compact: docs_list_opus_ogg_needs_runtime_proof
  wav_pcm_safe: documented_format_wav_larger_fallback
supported_provider_formats_documented:
  - mp3
  - wav
  - flac
  - aac
  - opus
  - ogg
  - m4a
  - mp4
  - mpeg
  - mov
  - webm
supports_direct_upload: true
max_direct_upload_mb: 100
supports_url_upload: true
max_url_upload_mb: 1024
max_duration_seconds: null # not documented / needs runtime proof
supports_callbacks: true
supports_provider_cancel: null # not documented / treat as unsupported until proof
response_formats:
  - json
  - text
  - srt
  - verbose_json
  - vtt
supports_segment_timestamps: true
supports_word_timestamps: true
supports_speaker_labels: true
speaker_labels_max_speakers: 4
language_ru_support: true
pricing_public_hint: "$0.50 per 3 hours; EU endpoint +20%"
error_behavior: not_documented_needs_runtime_proof
```

Lemonfox official documentation confirms direct file upload, public URL input,
100 MB direct upload limit, 1 GB URL input limit, response formats, speaker
labels, word timestamps, callback URL and Russian language support. The same
documentation does not document a provider-side cancellation endpoint, stable
job id for cancellation, maximum accepted audio duration, exact error taxonomy,
or explicit WebM/Opus versus OGG/Opus compatibility for Stage 2 output
profiles. These remain runtime-proof items.

Rules:

- `supports_provider_cancel=null` means "unknown from docs"; implementation
  treats it as unsupported until runtime/provider proof says otherwise;
- `max_duration_seconds=null` means no provider duration promise exists in the
  contract; Stage 2 must enforce an internal max duration before production;
- `supports_url_upload=true` is documented, but use of URL/object-storage
  provider paths requires access-control, expiry, sensitivity and runtime proof;
- response and error mapping must still go through `LemonfoxSttAdapter`, not
  through UI code.

## 11. FFMPEG asset loading strategy

If implementation chooses ffmpeg.wasm, treat it as an implementation dependency,
not as the provider boundary.

Source workflow facts:

- source workflow uses `@ffmpeg/ffmpeg` v0.12.6;
- source workflow loads ffmpeg assets from `unpkg.com`;
- source workflow produces MP3 / `audio/mpeg`.

Previously checked package facts on 2026-06-18 for production planning:

- `@ffmpeg/ffmpeg`: npm version `0.12.15`, MIT license, wrapper package.
- `@ffmpeg/core`: npm version `0.12.10`, GPL-2.0-or-later, single-thread core.
- `@ffmpeg/core-mt`: npm version `0.12.10`, GPL-2.0-or-later, multi-thread core.

Deployment modes:

### cdn mode

- fast setup;
- simple proof/dev/fallback;
- can leverage public CDN cache;
- depends on external availability;
- may be blocked by corporate network;
- must pin exact versions;
- must be explicitly approved for production.

### self_hosted mode

- assets hosted under portal domain or internal CDN;
- production default for corporate environments;
- predictable availability;
- requires ops/licensing/cache review;
- no public CDN dependency;
- larger deployment asset footprint.

Strategy:

- pin exact package versions during implementation planning;
- prefer single-thread `@ffmpeg/core` for first proof;
- use multi-thread `@ffmpeg/core-mt` only after SharedArrayBuffer /
  cross-origin isolation proof;
- implementation must support or at least document the chosen asset loading
  mode;
- production default is `self_hosted`;
- production must not silently depend on unpinned public CDN;
- CDN is not forbidden, but production CDN use requires explicit approval and
  pinned versions;
- do not commit heavy wasm/core binaries without a separate ADR;
- do not vendor the full FFmpeg source tree;
- define cache headers, asset path, rollback and license notices if core assets
  are self-hosted;
- select final output profile after provider compatibility and licensing/ops
  review.

Security/header implication:

- multi-thread ffmpeg.wasm requires `SharedArrayBuffer`;
- `SharedArrayBuffer` requires secure context and cross-origin isolation;
- COOP/COEP header changes may affect OpenWebUI, Traefik, embedded resources and
  third-party scripts, so they require a later infra/browser review.

## 12. STT Environment / Configuration Contract

Stage 2 STT provider, output profile, ffmpeg asset mode, limits, storage,
retention and cancel behavior must be env/config driven on the server side.

Draft contract:

- [STT_ENV_CONTRACT](../config/STT_ENV_CONTRACT.md)

Required decisions captured there:

- `STAGE2_STT_PROVIDER=lemonfox`;
- `STAGE2_STT_PROVIDER_ADAPTER=lemonfox`;
- `STAGE2_STT_OUTPUT_PROFILE` as an Opus candidate pending Lemonfox proof;
- `STAGE2_STT_FALLBACK_OUTPUT_PROFILE=mp3_high_compat`;
- `STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024`;
- `STAGE2_FFMPEG_ASSET_MODE=self_hosted`;
- `STAGE2_STT_STORAGE_MODE=auto`;
- `STAGE2_STT_REQUIRE_STORAGE_HEALTH=false`;
- `STAGE2_STT_MAX_PREPARED_AUDIO_MB=100`;
- `STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB=1024`;
- provider/internal duration limit envs remain blank/TBD until accepted;
- cancel flags for provider-side cancellation when available and local cancel
  when provider cancellation is unavailable.

This is a draft env contract, not a final `.env.example`. Real values and
secrets must stay server-side and out of Git. No provider key may use
`NEXT_PUBLIC_*` or any browser-exposed configuration path.

## 13. Limits and too-large behavior

Documented Stage 2 limits:

```text
STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB=100
STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB=1024
STAGE2_STT_PROVIDER_MAX_DURATION_MINUTES=
STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES=
```

Rules:

- browser-side wasm preprocessing input limit is 1 GB / 1024 MB;
- Lemonfox direct upload limit is 100 MB prepared audio;
- Lemonfox public URL input limit is documented as 1 GB, but use of this path
  is not approved until storage access, expiry and runtime compatibility are
  proven;
- Lemonfox maximum audio duration is not documented; Stage 2 must define an
  internal max duration and keep provider max duration as `TBD` until proven;
- backend must validate prepared audio size before direct Lemonfox upload;
- UI/backend should warn before provider upload when actual or estimated
  prepared audio exceeds 100 MB;
- if prepared audio is larger than 100 MB, default behavior is fail with a typed
  error unless a fallback path is approved and healthy;
- possible future fallback paths are URL/object-storage provider path,
  provider URL upload or chunking only if supported and approved;
- no fallback is silently assumed from Lemonfox URL support without compatibility
  proof, storage access design and expiry policy.

Typed error candidates:

```text
provider_direct_upload_limit_warning
prepared_audio_too_large
unsupported_input_format
preprocessing_failed
provider_direct_upload_limit_exceeded
storage_required_for_large_audio
duration_limit_exceeded
```

## 14. Storage and retention

Prepared/normalized audio storage is mode-driven. Stage 2 must not silently
store original source media.

Draft storage modes:

```text
auto
s3
none
```

Rules:

- `auto`: store prepared audio in S3/object storage when bucket/prefix are
  configured and storage health is good; otherwise use transient local/server
  lifecycle and do not pretend durable storage exists;
- `s3`: require configured and healthy S3/object storage; fail fast when
  unavailable;
- `none`: do not retain prepared audio after provider handoff/local lifecycle;
- storage bucket, prefix, mode and retention must be env-configurable;
- storage health must be visible to backend policy and runtime capabilities;
- source original media is not stored unless explicitly enabled;
- prepared audio storage is controlled by `STAGE2_STT_STORE_PREPARED_AUDIO`;
- prepared audio retention is controlled by
  `STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS`;
- transcript retention is controlled separately from prepared audio retention;
- object keys must not expose provider keys or sensitive metadata;
- cancelled jobs follow retention policy.

Cancelled-job behavior:

- if prepared audio exists, cleanup or retention follows config;
- if the provider returns after local cancellation, the result is ignored or
  stored only if policy explicitly allows it;
- source media storage remains off by default.

## 15. Lightweight Proof Matrix

Proof matrix is not certification. It is a lightweight reproducibility record.

Minimum cases:

| Case | Purpose |
| ---- | ------- |
| desktop audio | baseline audio preprocessing |
| desktop video | baseline video extraction |
| mobile audio | mobile browser audio path |
| mobile video | mobile browser video path |
| large WAV | large audio case |
| large video | large media case |

Required fields:

- device;
- browser;
- file type;
- file size;
- duration;
- selected output profile;
- result;
- evidence.

Operator manual proof exists. The lightweight proof matrix captures
reproducibility for the already observed scenarios; it must not become a broad
certification program.

## 16. Cancel UX

Cancel is required UX for Stage 2 transcription.

Preprocessing cancel:

- stop ffmpeg worker;
- terminate local preprocessing;
- cleanup local temporary objects.

Upload cancel:

- abort upload request;
- abort multipart upload if used;
- cleanup incomplete object where possible.

STT job cancel:

- mark job as cancelled;
- stop processing if provider call has not started;
- if provider API supports cancellation, call provider cancel;
- if provider call already started and provider has no documented/proven cancel
  API, mark local job cancelled and ignore/cleanup late result according to
  retention policy.

Possible job statuses:

```text
queued
preprocessing
uploading
processing
cancel_requested
completed
failed
cancelled
```

Reason code candidates:

```text
cancelled_by_user
provider_cancel_unsupported
provider_cancel_unknown
provider_cancel_supported
cancelled_locally_provider_continues
late_provider_result_ignored
```

Cancel support should be implemented where technically possible.
Provider-side cancellation depends on provider capabilities. UX must not leave
the user with a frozen long-running task.

For Lemonfox, provider-side cancellation is not documented in the checked
official STT API page. Until a job id/cancel endpoint is proven, Stage 2 treats
Lemonfox provider cancellation as unavailable and relies on local cancellation,
late-result ignoring and retention-controlled cleanup.

## 17. Draft Internal Contracts

These are review-level contract candidates, not final JSON schemas.

### TranscriptionJobV1

Purpose:

- stable lifecycle record for upload, processing, status, progress, errors and
  cancellation.

Candidate fields:

- `job_id`;
- `created_at`;
- `created_by_user_id`;
- `workspace_id`;
- `source_kind`;
- `source_file_name`;
- `source_mime_type`;
- `prepared_audio_mime_type`;
- `prepared_audio_object_key`;
- `prepared_audio_size_bytes`;
- `prepared_audio_retention_policy_id`;
- `source_media_stored`;
- `source_media_object_key`;
- `storage_mode`;
- `storage_health_status`;
- `output_profile_id`;
- `asset_loading_mode`;
- `preprocessing_status`;
- `upload_status`;
- `status`;
- `progress`;
- `cancel_requested`;
- `cancelled_at`;
- `selected_stt_provider`;
- `adapter_id`;
- `provider_capability_profile_version`;
- `provider_cancel_support`;
- `max_duration_seconds`;
- `model`;
- `language`;
- `speaker_labels_requested`;
- `timestamps_requested`;
- `retention_policy_id`;
- `error`.

### TranscriptResultV1

Purpose:

- normalized transcript output for UI, templates and exports.

Candidate fields:

- `job_id`;
- `language`;
- `text`;
- `segments`;
- `normalized_segments`;
- `speakers`;
- `word_timestamps`;
- `duration_seconds`;
- `source_output_profile_id`;
- `provider_adapter_id`;
- `model`;
- `confidence`;
- `provider_features_used`;
- `warnings`;
- `raw_provider_response_ref`.

Notes:

- `confidence` is optional because providers may not return comparable values;
- `raw_provider_response_ref` is optional and internal only.

### UsageEventV1

Purpose:

- normalized usage record for admin review and future cost visibility.

Candidate fields:

- `event_id`;
- `event_type`;
- `user_id`;
- `workspace_id`;
- `provider_adapter_id`;
- `model`;
- `units`;
- `unit_type`;
- `preprocessing_units`;
- `upload_bytes`;
- `stt_billable_units`;
- `estimated_cost`;
- `created_at`;
- `correlation_id`.

### PolicyDecisionV1

Purpose:

- backend decision record for whether this user/workspace/action can use the
  transcription path with the selected data/provider class.

Candidate fields:

- `decision_id`;
- `user_id`;
- `workspace_id`;
- `action`;
- `allowed`;
- `reason`;
- `data_class`;
- `provider_class`;
- `output_profile_id`;
- `selected_stt_provider`;
- `provider_adapter_id`;
- `policy_version`.

Supporting contracts from the broader Stage 2 boundary map:

- `RetentionPolicyV1`;
- `ProviderModelCatalogV1`;
- `ManagerVisibilityPolicyV1`.

### TranscriptionRuntimeCapabilitiesV1

Purpose:

- expose effective backend transcription capabilities to the UI without
  leaking secrets or raw provider details.

Candidate fields:

- `contract_version`;
- `default_provider_id`;
- `default_adapter_id`;
- `provider_profiles`;
- `default_output_profile_id`;
- `fallback_output_profile_id`;
- `output_profiles`;
- `browser_max_input_mb`;
- `provider_max_direct_upload_mb`;
- `provider_max_url_upload_mb`;
- `provider_max_duration_seconds`;
- `internal_max_duration_seconds`;
- `storage_modes`;
- `effective_storage_mode`;
- `storage_health`;
- `supports_url_upload`;
- `supports_callbacks`;
- `supports_provider_cancel`;
- `supports_segment_timestamps`;
- `supports_word_timestamps`;
- `supports_speaker_labels`;
- `max_speakers`;
- `supported_languages`;
- `warning_reason_codes`;
- `error_reason_codes`;
- `unknowns`.

## 18. Draft Endpoint Boundary

Draft endpoint names:

```text
GET /stage2-api/transcription/capabilities
POST /stage2-api/transcription/jobs
GET /stage2-api/transcription/jobs/{job_id}
GET /stage2-api/transcription/jobs/{job_id}/result
POST /stage2-api/transcription/jobs/{job_id}/cancel
```

Constraints:

- endpoint names are draft;
- final routing depends on OpenWebUI auth/session proof;
- request/response schemas must be versioned;
- long-running transcription should not rely on a single blocking HTTP request;
- short files may still be processed synchronously behind the job contract;
- `GET /stage2-api/transcription/capabilities` returns
  `TranscriptionRuntimeCapabilitiesV1` with effective limits, output profiles,
  storage mode/health and provider capability flags;
- browser calls only the internal Stage 2 backend boundary;
- provider keys live server-side only;
- routes should prefer sidecar/internal backend API or a thin integration shim
  over deep OpenWebUI core patching.

## 19. Runtime Proof Needed

Before implementation:

- verify deployed/staging OpenWebUI version and native STT baseline;
- verify auth/session propagation option to Stage 2 backend;
- verify user/group permission check source;
- verify Lemonfox smoke with approved test key and audio;
- verify `LemonfoxSttAdapter` as the first adapter behind the factory;
- capture lightweight reproducible proof matrix for the inspected ffmpeg
  workflow with device, browser, file type, file size, duration, selected
  output profile, result and evidence;
- verify source-proven MP3 / `audio/mpeg` prepared-audio output against the
  Stage 2 proxy contract without treating it as the only possible output;
- verify Opus candidate output profile compatibility with Lemonfox before
  making it default;
- separately verify WebM/Opus and OGG/Opus if both remain profile candidates;
- verify large-video and large-WAV behavior with recorded metadata;
- verify no STT API key appears in browser bundle, browser storage or browser
  network logs;
- verify production ffmpeg assets are self-hosted under portal/internal CDN or
  that any production CDN exception is explicitly approved;
- verify production output profile decision;
- verify STT Provider Adapter Factory contract and normalized error mapping;
- verify selected ffmpeg.wasm package/core version and self-hosted asset path;
- verify single-thread vs multi-thread choice;
- verify SharedArrayBuffer / cross-origin isolation only if multi-thread is
  selected;
- verify practical max file size and duration limits;
- verify browser 1 GB input limit and Lemonfox 100 MB direct upload limit;
- verify Lemonfox URL upload path only if approved; docs state 1 GB URL input
  limit, but Stage 2 still needs storage expiry/access proof;
- verify provider maximum duration or keep provider max duration `TBD` and
  enforce internal duration limits;
- verify prepared-audio-too-large behavior;
- verify storage mode behavior for `auto`, `s3` and `none`, including storage
  health reporting and fail-fast behavior for required storage;
- verify source media storage remains disabled unless explicitly enabled;
- verify unsupported/large-file error behavior;
- verify transcript result can be stored or returned without leaking raw
  provider details;
- verify `UsageEventV1` can be emitted;
- verify cancel behavior for preprocessing, upload, local STT job and provider
  job cancellation where Lemonfox/provider supports it; if provider cancel is
  not documented, prove local cancellation and late-result handling;
- verify `TranscriptionRuntimeCapabilitiesV1` does not expose secrets and
  matches effective server config;
- verify typed errors for unsupported/too-large files.

## 20. Customer / Operator Input Needed

- Existing ffmpeg workflow repo/path/artifact for implementation handoff.
- Minimal demo or runnable instructions for reproducible proof.
- Short audio sample.
- Short video sample.
- Large audio/video sample.
- Device/browser/file metadata for the operator-tested mobile and large-file
  cases.
- Expected result templates:
  - summary;
  - protocol;
  - tasks;
  - decisions;
  - follow-up.
- Retention preference for source media, prepared audio and transcript.
- Approved STT provider/account path.
- Whether speaker labels are mandatory or optional.
- Whether timestamps are mandatory or optional.
- Maximum acceptable processing time.
- Whether EU processing is required.
- Whether source video upload fallback is allowed when browser preprocessing
  fails.

## 21. Open Questions

- How will OpenWebUI session/auth be propagated to the Stage 2 backend?
- Which S3/object storage bucket and prefix hold prepared/normalized audio?
- What max file size and duration limits are acceptable for production?
- What is cancellation behavior for local ffmpeg work and server/provider work?
- Which Opus container is accepted by Lemonfox strongly enough to become the
  default output profile?
- Does Lemonfox accept the exact Stage 2 WebM/Opus and OGG/Opus ffmpeg outputs,
  not only generic `webm`, `ogg` and `opus` formats from documentation?
- Does Lemonfox expose any provider-side cancellation API or stable job id for
  cancellation? If not, local cancellation is the only Stage 2 behavior.
- What maximum provider duration is actually accepted by Lemonfox?
- What retention applies to prepared audio after completed, failed and
  cancelled jobs?
- Which transcript fields are mandatory for first acceptance?
- How are speaker labels and timestamps normalized?
- How are provider errors mapped into stable reason codes?
- How are usage events emitted and reviewed?
- Is Lemonfox URL/object-storage upload path approved for prepared audio larger
  than 100 MB, or should the first behavior remain fail-fast?
- Should `auto`, `s3` or `none` be the production storage mode?
- Is callback/async provider flow required in Practical Stage 2 or deferred?
- Is native OpenWebUI STT sufficient for a baseline smoke only, or can it reduce
  proxy scope after proof?
- Should production default to source-proven MP3 / `audio/mpeg`, or choose
  `audio/webm;codecs=opus`, `audio/ogg;codecs=opus` or `audio/wav` after
  licensing/ops/provider review?
- Are self-hosted ffmpeg core assets acceptable from licensing and ops
  perspectives?
- Is the source project's 1 GB UI limit acceptable, lower than required, or too
  high for corporate browser/mobile acceptance?

## 22. Consequences

- Frontend/UI work follows backend contract review.
- ffmpeg remains a media-preprocessing asset, not a security boundary.
- Provider adapters and transcript normalization stay server-side.
- STT Provider Adapter Factory is a required boundary so provider replacement
  does not rewrite browser preprocessing or templates.
- Lemonfox is the first Stage 2 provider, but provider coupling remains isolated
  inside `LemonfoxSttAdapter`.
- Output profiles prevent the source-proven MP3 workflow from becoming a
  permanent hardcoded constraint.
- Opus can become default only after Lemonfox compatibility proof; MP3 remains
  the compatibility fallback.
- Storage and retention must align with ADR-0001 and ADR-0003.
- Prepared/normalized audio storage is controlled by `auto|s3|none`; source
  media remains off unless explicitly enabled.
- Lemonfox-specific features must be tested before promising them.
- OpenWebUI upgrade risk is lower if the Stage 2 API remains isolated behind a
  sidecar/internal backend route or thin shim.
- ADR approval cannot close implementation readiness until the operator manual
  proof is converted into a lightweight reproducibility matrix and production
  dependency decisions are made.
- Heavy wasm/core assets and FFmpeg source are excluded from this repo.
- Self-hosted ffmpeg assets are the production default; CDN mode remains
  possible for dev/proof/fallback and production only with explicit approval
  and pinned versions.
- Source video upload fallback remains disallowed unless explicitly approved.

## 23. Acceptance Signals for ADR Approval

ADR can be approved only when:

- browser/server/provider boundary is understood;
- direct browser-to-provider is rejected;
- API key handling is server-side only;
- job model is accepted or explicitly rejected;
- draft internal contracts are reviewed;
- draft endpoint boundary is accepted, revised or rejected;
- runtime proof checklist is defined;
- output profiles are accepted, revised or rejected;
- STT Provider Adapter Factory is accepted, revised or rejected;
- Lemonfox first-adapter decision is accepted or explicitly revised;
- STT Provider Capability Profile is accepted, revised or rejected;
- `TranscriptionRuntimeCapabilitiesV1` and capabilities endpoint are accepted,
  revised or rejected;
- ffmpeg artifact inspection status is explicit;
- STT env/config contract is reviewed;
- unresolved open questions are closed or explicitly deferred;
- ffmpeg asset loading strategy is accepted, revised or rejected;
- operator manual proof is captured as manual evidence, not as automated proof;
- production output profile, asset hosting, licensing and file-limit decisions
  are accepted, revised or explicitly deferred;
- storage mode, storage health and prepared-audio retention decisions are
  accepted, revised or explicitly deferred;
- >100 MB warning/fail/fallback behavior is accepted, revised or explicitly
  deferred;
- cancel UX expectations are accepted, revised or explicitly deferred;
- no implementation has started.

Current review state:

- boundary and draft contracts are ready for human review;
- external ffmpeg workflow artifact is inspected;
- transferable MP3 / `audio/mpeg` preprocessing contract is found as a
  source-proven compatibility fallback;
- operator manual proof exists for reported mobile and large-file scenarios;
- implementation readiness still requires lightweight proof matrix, selected
  Opus output profile proof, storage mode/config, prepared-audio retention
  decision, provider cancel/duration proof or explicit TBD handling, and
  production dependency decisions.

## 24. Non-Goals

- No backend implementation.
- No frontend implementation.
- No Lemonfox setup.
- No real API keys.
- No `.env` read.
- No production change.
- No compose/env/scripts change.
- No OpenWebUI fork.
- No ADR acceptance without human review.
- No claim that operator manual proof is automated repository proof.
- No claim of universal mobile support or all-file support.
- No heavy wasm/core binaries or full FFmpeg source vendoring without a separate
  ADR.

## 25. Links

- [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md)
- [IMPLEMENTATION_GATES](../IMPLEMENTATION_GATES.md)
- [STT_ENV_CONTRACT](../config/STT_ENV_CONTRACT.md)
- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
- [ACCEPTANCE_MATRIX](../acceptance/ACCEPTANCE_MATRIX.md)
- [TEST_DATA_REQUIREMENTS](../acceptance/TEST_DATA_REQUIREMENTS.md)
