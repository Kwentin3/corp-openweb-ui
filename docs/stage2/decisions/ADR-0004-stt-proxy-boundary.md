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
source-proven default candidate. MP3 / `audio/mpeg` is a proven source workflow
output, not a permanent architecture constraint. Browser preprocessing must
expose an output profile rather than hardcode MP3 as the only possible output.
The prepared browser `Blob` is uploaded through a presigned/internal-storage
path, then backend STT orchestration calls the provider. API keys do not go to
the browser and the browser does not call STT providers directly.

Operator manual proof also confirms that the workflow was manually tested on a
mobile device with large videos and large WAV files and worked correctly in
those reported cases. This is useful operator evidence, not a repository-owned
automated proof matrix. Stage 2 implementation acceptance still needs a
lightweight reproducible proof matrix with device/browser/file metadata and
production dependency decisions.

Lemonfox is the priority STT provider candidate, not hardwired architecture.
Existing research also keeps native OpenWebUI STT as a useful baseline to test,
because OpenWebUI has native STT configuration and OpenAI-compatible backend
paths. PRD-1 transcription is broader than chat-input STT: it includes
audio/video preprocessing, STT Provider Adapter Factory behavior, job lifecycle,
progress/cancel UX, template output and usage visibility.

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
- ffmpeg asset loading mode must be an explicit deployment choice;
- cancel UX is required where technically possible across preprocessing,
  upload and job lifecycle.

## 6. Contract Boundary

### Browser

Owns:

- multimedia file selection;
- local file type detection before upload;
- local ffmpeg preprocessing after user action;
- audio extraction/conversion according to the selected output profile;
- transferable source-proven default candidate: MP3 / `audio/mpeg` browser
  `Blob`;
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
- validation that does not trust browser-side file metadata blindly;
- temporary file/blob handling;
- STT Provider Adapter Factory call;
- provider capability and supported-input-profile mapping;
- API key handling;
- transcript normalization;
- error normalization;
- usage event emission;
- retention and lifecycle decision;
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
  production dependency decisions`.

Source workflow contract found:

- browser input accepts `audio/*` and `video/*`;
- source project UI limit: 1 GB;
- source-confirmed formats: MP3, WAV, M4A, WebM, MP4 video and MOV video;
- package: `@ffmpeg/ffmpeg` v0.12.6;
- source asset hosting: CDN through `unpkg.com`;
- transformation command:
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`;
- source-proven output profile: `mp3_high_compat`;
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

Production caveats:

- MP3 / `audio/mpeg` is proven in the source workflow, but not automatically the
  final production format;
- select production output profile after STT provider compatibility and
  licensing/ops review;
- alternatives remain possible: `audio/webm;codecs=opus`,
  `audio/ogg;codecs=opus` or `audio/wav` if size is acceptable;
- public CDN dependency through `unpkg.com` must not be accepted silently for
  corporate production;
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
  status: source-proven candidate

opus_webm_compact:
  mime: audio/webm;codecs=opus
  container: webm
  codec: opus
  status: candidate pending STT provider compatibility proof

opus_ogg_compact:
  mime: audio/ogg;codecs=opus
  container: ogg
  codec: opus
  status: candidate pending STT provider compatibility proof

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
- default output profile is a separate implementation decision.

MP3 / `audio/mpeg` is a proven source workflow output, not a permanent
architecture constraint.

## 9. STT Provider Adapter Factory

Stage 2 backend orchestration must not depend directly on Lemonfox, OpenAI,
Gemini, Yandex SpeechKit, Deepgram or Local Whisper response details.

Concept:

```text
SttProviderAdapterFactory
  -> LemonfoxSttAdapter
  -> OpenAiSttAdapter
  -> GeminiSttAdapter
  -> YandexSpeechKitAdapter
  -> DeepgramSttAdapter
  -> LocalWhisperAdapter
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
- Lemonfox is a priority candidate, not hardwired architecture.

## 10. FFMPEG asset loading strategy

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
- simple proof/dev;
- can leverage public CDN cache;
- depends on external availability;
- may be blocked by corporate network;
- must pin exact versions;
- must be explicitly approved for production.

### self_hosted mode

- assets hosted under portal domain or internal CDN;
- better for corporate controlled environments;
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
- production must not silently depend on unpinned public CDN;
- self-host/internal-cache is the preferred fallback for corporate
  environments;
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

## 11. Lightweight Proof Matrix

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

## 12. Cancel UX

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
- if provider call already started and provider has no cancel API, mark local
  job cancelled and ignore/cleanup result according to retention policy.

Possible job statuses:

```text
queued
preprocessing
uploading
processing
completed
failed
cancelled
```

Cancel support should be implemented where technically possible.
Provider-side cancellation depends on provider capabilities. UX must not leave
the user with a frozen long-running task.

## 13. Draft Internal Contracts

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

## 14. Draft Endpoint Boundary

Draft endpoint names:

```text
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
- browser calls only the internal Stage 2 backend boundary;
- provider keys live server-side only;
- routes should prefer sidecar/internal backend API or a thin integration shim
  over deep OpenWebUI core patching.

## 15. Runtime Proof Needed

Before implementation:

- verify deployed/staging OpenWebUI version and native STT baseline;
- verify auth/session propagation option to Stage 2 backend;
- verify user/group permission check source;
- verify Lemonfox smoke with approved test key and audio;
- capture lightweight reproducible proof matrix for the inspected ffmpeg
  workflow with device, browser, file type, file size, duration, selected
  output profile, result and evidence;
- verify source-proven MP3 / `audio/mpeg` prepared-audio output against the
  Stage 2 proxy contract without treating it as the only possible output;
- verify selected output profile compatibility with the selected provider
  adapter;
- verify large-video and large-WAV behavior with recorded metadata;
- verify no STT API key appears in browser bundle, browser storage or browser
  network logs;
- verify source workflow CDN dependency is replaced, explicitly accepted or
  rejected for production;
- verify production output profile decision;
- verify STT Provider Adapter Factory contract and normalized error mapping;
- verify selected ffmpeg.wasm package/core version and asset hosting path;
- verify `cdn mode` or `self_hosted mode` is documented for deployment;
- verify single-thread vs multi-thread choice;
- verify SharedArrayBuffer / cross-origin isolation only if multi-thread is
  selected;
- verify practical max file size and duration limits;
- verify unsupported/large-file error behavior;
- verify transcript result can be stored or returned without leaking raw
  provider details;
- verify `UsageEventV1` can be emitted;
- verify cancel behavior for preprocessing, upload and STT job lifecycle where
  technically possible;
- verify typed errors for unsupported/too-large files.

## 16. Customer / Operator Input Needed

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

## 17. Open Questions

- How will OpenWebUI session/auth be propagated to the Stage 2 backend?
- Where are prepared audio blobs temporarily stored?
- What max file size and duration limits are acceptable for production?
- What is cancellation behavior for local ffmpeg work and server/provider work?
- Which output profile is the first default, and which profiles are accepted by
  each provider adapter?
- Which ffmpeg asset loading mode is approved for production?
- Which transcript fields are mandatory for first acceptance?
- How are speaker labels and timestamps normalized?
- How are provider errors mapped into stable reason codes?
- How are usage events emitted and reviewed?
- What retention applies to source media, prepared audio and transcript?
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

## 18. Consequences

- Frontend/UI work follows backend contract review.
- ffmpeg remains a media-preprocessing asset, not a security boundary.
- Provider adapters and transcript normalization stay server-side.
- STT Provider Adapter Factory is a required boundary so provider replacement
  does not rewrite browser preprocessing or templates.
- Output profiles prevent the source-proven MP3 workflow from becoming a
  permanent hardcoded constraint.
- Storage and retention must align with ADR-0001 and ADR-0003.
- Lemonfox-specific features must be tested before promising them.
- OpenWebUI upgrade risk is lower if the Stage 2 API remains isolated behind a
  sidecar/internal backend route or thin shim.
- ADR approval cannot close implementation readiness until the operator manual
  proof is converted into a lightweight reproducibility matrix and production
  dependency decisions are made.
- Heavy wasm/core assets and FFmpeg source are excluded from this repo until a
  separate ADR approves vendoring or self-hosting.
- CDN mode remains possible, but production CDN use requires explicit approval
  and pinned versions.
- Source video upload fallback remains disallowed unless explicitly approved.

## 19. Acceptance Signals for ADR Approval

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
- ffmpeg artifact inspection status is explicit;
- unresolved open questions are closed or explicitly deferred;
- ffmpeg asset loading strategy is accepted, revised or rejected;
- operator manual proof is captured as manual evidence, not as automated proof;
- production output profile, asset hosting, licensing and file-limit decisions
  are accepted, revised or explicitly deferred;
- cancel UX expectations are accepted, revised or explicitly deferred;
- no implementation has started.

Current review state:

- boundary and draft contracts are ready for human review;
- external ffmpeg workflow artifact is inspected;
- transferable MP3 / `audio/mpeg` preprocessing contract is found as a
  source-proven candidate;
- operator manual proof exists for reported mobile and large-file scenarios;
- implementation readiness still requires lightweight proof matrix, selected
  output profile, STT adapter decision, asset loading mode and production
  dependency decisions.

## 20. Non-Goals

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

## 21. Links

- [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md)
- [IMPLEMENTATION_GATES](../IMPLEMENTATION_GATES.md)
- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
- [ACCEPTANCE_MATRIX](../acceptance/ACCEPTANCE_MATRIX.md)
- [TEST_DATA_REQUIREMENTS](../acceptance/TEST_DATA_REQUIREMENTS.md)
