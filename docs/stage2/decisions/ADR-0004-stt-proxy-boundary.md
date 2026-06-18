# ADR-0004 STT Proxy Boundary

Status: Proposed

## 1. Context

Transcription is a priority Stage 2 scenario. PRD-1 states that audio/video
transcription should reuse an existing browser ffmpeg workflow as a technical
asset, then send prepared audio to a server-side STT boundary.

The current repository contains Stage 2 planning docs and research, but not the
actual ffmpeg workflow artifact. Local inspection found only documentation
references to ffmpeg/STT/transcription, not implementation code, examples, demo
assets or package files for that workflow. This ADR therefore treats the
ffmpeg workflow as a known external/customer/executor asset whose contract still
must be inspected before implementation.

Lemonfox is the priority STT provider candidate. Existing research also keeps
native OpenWebUI STT as a useful baseline to test, because OpenWebUI has native
STT configuration and OpenAI-compatible backend paths. PRD-1 transcription is
broader than chat-input STT: it includes audio/video preprocessing, provider
adapter behavior, job lifecycle, progress/cancel UX, template output and usage
visibility.

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
- can support Lemonfox, OpenAI or future STT providers through adapters;
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
- implementation is blocked until the actual ffmpeg workflow artifact contract
  is inspected or a replacement preprocessing contract is approved.

## 6. Contract Boundary

### Browser

Owns:

- multimedia file selection;
- local file type detection before upload;
- local ffmpeg preprocessing after user action;
- audio extraction/conversion into the agreed prepared-audio format;
- local preprocessing progress/cancel UI;
- upload of the prepared audio blob to the Stage 2 backend;
- display of job status and normalized transcript result.

Does not own:

- STT provider API keys;
- provider selection policy;
- data policy decision;
- final usage accounting;
- retention decision;
- direct call to Lemonfox or another STT provider;
- internal transcript schema.

### Stage 2 Backend / STT Proxy

Owns:

- auth/session verification through OpenWebUI or an approved internal boundary;
- permission check for transcription use;
- data policy check;
- file validation;
- max size and duration limits;
- prepared-audio MIME/content-type validation;
- temporary file/blob handling;
- provider adapter call;
- API key handling;
- transcript normalization;
- error normalization;
- usage event emission;
- retention and lifecycle decision;
- job status;
- cancel/retry behavior;
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

- `blocked by artifact inspection`.

Local inspection performed for this ADR found no implementation artifact in this
repo. There are documentation references to an existing ffmpeg workflow, but no
code, README, examples, package metadata, demo files or notes from which an
actual contract can be extracted.

Contract fields that must be inspected from the real artifact:

- supported input formats;
- output format;
- output MIME/content type;
- whether output is mp3, wav, m4a, webm or another format;
- browser support;
- mobile support;
- max observed file size and duration;
- ffmpeg core version and asset hosting model;
- worker model;
- progress event shape;
- cancellation behavior;
- error behavior;
- timeout behavior;
- licensing and core asset hosting notes.

Operator/customer input needed:

- repo/path/source of the existing ffmpeg workflow;
- minimal runnable demo;
- supported format matrix;
- desktop/mobile proof;
- output contract and sample prepared audio;
- known size/duration limits.

## 8. Draft Internal Contracts

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
- `status`;
- `progress`;
- `provider`;
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
- `speakers`;
- `word_timestamps`;
- `duration_seconds`;
- `provider`;
- `model`;
- `confidence`;
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
- `provider`;
- `model`;
- `units`;
- `unit_type`;
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
- `policy_version`.

Supporting contracts from the broader Stage 2 boundary map:

- `RetentionPolicyV1`;
- `ProviderModelCatalogV1`;
- `ManagerVisibilityPolicyV1`.

## 9. Draft Endpoint Boundary

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

## 10. Runtime Proof Needed

Before implementation:

- verify deployed/staging OpenWebUI version and native STT baseline;
- verify auth/session propagation option to Stage 2 backend;
- verify user/group permission check source;
- verify Lemonfox smoke with approved test key and audio;
- verify existing ffmpeg workflow output contract;
- verify desktop and mobile prepared-audio output;
- verify practical max file size and duration limits;
- verify unsupported/large-file error behavior;
- verify transcript result can be stored or returned without leaking raw
  provider details;
- verify `UsageEventV1` can be emitted;
- verify no STT API key appears in browser bundle, browser storage or network
  logs.

## 11. Customer / Operator Input Needed

- Existing ffmpeg workflow repo/path/artifact.
- Minimal demo or runnable instructions.
- Short audio sample.
- Short video sample.
- Large audio/video sample.
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

## 12. Open Questions

- How will OpenWebUI session/auth be propagated to the Stage 2 backend?
- Where are prepared audio blobs temporarily stored?
- What are max file size and duration limits?
- What is cancellation behavior for local ffmpeg work and server/provider work?
- Which transcript fields are mandatory for first acceptance?
- How are speaker labels and timestamps normalized?
- How are provider errors mapped into stable reason codes?
- How are usage events emitted and reviewed?
- What retention applies to source media, prepared audio and transcript?
- Is callback/async provider flow required in Practical Stage 2 or deferred?
- Is native OpenWebUI STT sufficient for a baseline smoke only, or can it reduce
  proxy scope after proof?

## 13. Consequences

- Frontend/UI work follows backend contract review.
- ffmpeg remains a media-preprocessing asset, not a security boundary.
- Provider adapters and transcript normalization stay server-side.
- Storage and retention must align with ADR-0001 and ADR-0003.
- Lemonfox-specific features must be tested before promising them.
- OpenWebUI upgrade risk is lower if the Stage 2 API remains isolated behind a
  sidecar/internal backend route or thin shim.
- ADR approval cannot close implementation readiness while the actual ffmpeg
  artifact is missing.

## 14. Acceptance Signals for ADR Approval

ADR can be approved only when:

- browser/server/provider boundary is understood;
- direct browser-to-provider is rejected;
- API key handling is server-side only;
- job model is accepted or explicitly rejected;
- draft internal contracts are reviewed;
- draft endpoint boundary is accepted, revised or rejected;
- runtime proof checklist is defined;
- ffmpeg artifact inspection status is explicit;
- unresolved open questions are closed or explicitly deferred;
- no implementation has started.

Current review state:

- boundary and draft contracts are ready for human review;
- implementation readiness is blocked by the missing ffmpeg artifact.

## 15. Non-Goals

- No backend implementation.
- No frontend implementation.
- No Lemonfox setup.
- No real API keys.
- No `.env` read.
- No production change.
- No compose/env/scripts change.
- No OpenWebUI fork.
- No ADR acceptance without human review.
- No claim that the ffmpeg artifact has been inspected.

## 16. Links

- [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md)
- [IMPLEMENTATION_GATES](../IMPLEMENTATION_GATES.md)
- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
- [ACCEPTANCE_MATRIX](../acceptance/ACCEPTANCE_MATRIX.md)
- [TEST_DATA_REQUIREMENTS](../acceptance/TEST_DATA_REQUIREMENTS.md)
