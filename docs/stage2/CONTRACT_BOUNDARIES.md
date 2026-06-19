# Stage 2 Contract Boundaries

## 1. Purpose

Этот документ фиксирует доменные границы Stage 2, чтобы реализация не
размазывала custom logic по OpenWebUI core или frontend.

Stage 2 должен оставаться upgrade-safe: OpenWebUI остается upstream product
shell, а custom capabilities добавляются через bounded domain services,
internal APIs или thin integration shims.

OpenWebUI-facing features should follow the
[extension-first implementation pattern](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
before any deep fork is considered.

Документ задает рамку для ADR, proof gates and implementation slices.

Implementation baseline note, 2026-06-19:

- Initial STT backend sidecar/job routes, Lemonfox adapter, OpenWebUI
  attachment Action patch and browser ffmpeg.wasm normalization are now
  implemented/proven in the 2026-06-19 reports.
- The boundary rule is unchanged: provider keys and policy stay server-side,
  sidecar is private/backend-only, and browser preprocessing is a media
  preparation step, not a security boundary.
- Remaining STT work is hardening/product acceptance, not re-selection of the
  MVP architecture: mobile/large-file proof, low-memory behavior, cancel during
  ffmpeg, final duration policy, Opus/provider proof, retention/storage,
  transcript history/export/workflow and multi-user permission hardening.
- Sticky instruction for future agents: do not re-plan STT from zero, do not
  create a separate user-facing sidecar GUI, and do not fork OpenWebUI unless
  native mechanisms, Actions/Tools, thin static/UI shims and the sidecar pattern
  are proven insufficient.

## 2. Principles

- Domain isolation: каждый risky domain имеет owner, contract and acceptance.
- Backend-first: security, provider keys, policy, retention and usage decisions
  принадлежат backend/domain services.
- Contract-first: UI and templates depend on stable internal contracts, not raw
  provider responses.
- OpenWebUI upstream-first: native capabilities используются первыми, deep fork
  допускается только после proof that native/config/sidecar path is insufficient.
- Extension-first: OpenWebUI-facing features are evaluated through native
  mechanisms, Functions/Actions/Tools, thin static/UI shims and private
  sidecars before a fork is considered.
- OpenWebUI-native STT UX: user-facing transcription starts and finishes inside
  OpenWebUI chat/workspace UX. The Stage 2 STT sidecar is backend-only; no
  separate user-facing STT GUI is planned.
- MVP STT trigger: audio/video chat attachments expose an explicit
  `Transcribe` media attachment action. This action is the user intent contract
  for browser-side media normalization, backend STT job creation, provider
  transcription and transcript return into the current OpenWebUI chat UX.
- STT input compatibility is capability-based: broad media candidates may be
  accepted for ffmpeg.wasm probe/normalization, but output remains restricted to
  approved prepared-audio profiles.
- Thin frontend: frontend отвечает за user interaction, upload/progress/cancel
  UX and calls to internal Stage 2 APIs.
- No API keys in browser: browser never calls STT/LLM/OCR providers with
  provider secrets.
- No policy decisions in UI: frontend can display decisions and warnings, but
  cannot be source of truth.
- Versioned internal contracts: breaking changes require a new version suffix or
  ADR update.
- Runtime proof before implementation: contracts and gates must be proven before
  final UI or production changes.

## 3. Boundary map

### OpenWebUI core

- auth/session surface;
- users/groups/RBAC where native;
- chat/workspace UI;
- user-facing STT trigger/result surface through an approved native media
  attachment action or a minimal integration patch;
- visible `Transcribe` affordance on proven prepared audio or broad media
  candidates that still require ffmpeg probe/normalization;
- prompts/knowledge/workspace models where native;
- native analytics if sufficient.

### Stage 2 backend/domain services

- STT proxy/job service;
- STT Provider Adapter Factory and provider adapters;
- first STT adapter: `LemonfoxSttAdapter`;
- backend/domain engine only; not a user-facing portal;
- policy resolver;
- usage event collector;
- transcript normalization;
- STT provider capability profile and runtime capabilities endpoint;
- STT media input profile and normalization result contracts;
- retention/export lifecycle;
- OCR/VL OCR pilot adapters;
- internal health/smoke endpoints.
- no separate user-facing STT GUI.

### Frontend/thin UI

- user interaction;
- detects/receives media attachment context;
- shows the explicit `Transcribe` action for supported audio/video;
- upload/progress/cancel UX;
- local media preprocessing only when covered by an approved contract;
- may run ffmpeg.wasm normalization after explicit user action;
- treats source extension/MIME as hints until ffmpeg probe detects an audio
  stream;
- sends prepared audio/job request to internal Stage 2 APIs;
- displays transcript/status/result inside the current OpenWebUI chat UX;
- never stores provider API keys;
- never decides data policy;
- never decides manager visibility;
- never owns retention or usage accounting.

### External providers

- STT provider;
- LLM providers;
- web-search providers;
- OCR/VL OCR providers.

External provider responses are not product contracts. Provider adapters translate
them into internal Stage 2 contracts.

Lemonfox is an external STT provider behind `LemonfoxSttAdapter`. It must never
be visible to the browser/user as a provider-specific workflow.

### Storage/retention

- temporary files and prepared audio blobs;
- normalized/prepared audio storage through `auto|s3|none`;
- transcript storage if approved by policy;
- document/OCR pilot artifacts;
- usage metadata;
- retention/delete/export lifecycle.

Storage and retention follow data policy, manager visibility policy and chat
deletion/retention ADRs. No-delete is not retention. Retention is not audit.

### Admin/operator surface

- provider/model configuration;
- STT env/config contract for provider, output profile, asset mode, limits,
  storage and retention;
- usage review;
- smoke/proof evidence;
- feature flags and limits;
- safe operational checks without secrets.

Operator surfaces must not print provider keys, `.env` contents or raw sensitive
customer media.

## 4. Stage 2 internal contracts

Draft internal contracts:

- `TranscriptionJobV1`:
  job lifecycle for preprocessing, upload, STT processing, selected output
  profile, asset loading mode, selected provider adapter, prepared-audio object
  key, storage mode, retention policy, progress, cancellation and typed errors.
- `SttMediaInputProfileV1`:
  source media hints, ffmpeg probe/decode status, detected audio stream,
  duration/container/codec and rejection reason.
- `PreparedAudioMetadataV1`:
  normalized prepared-audio metadata, source input profile, selected output
  profile, output MIME/size/duration, ffmpeg command profile and warnings.
- `TranscriptResultV1`:
  normalized transcript shape for UI, templates and exports, including source
  output profile, provider adapter and normalized segments.
- `SttProviderCapabilityProfileV1`:
  adapter-owned provider capability declaration for supported output profiles,
  upload limits, URL upload support, duration limits, timestamps, speaker
  labels, callbacks, provider-side cancellation and unknowns.
- `TranscriptionRuntimeCapabilitiesV1`:
  effective server-side transcription capabilities for UI affordances and
  warnings, including output profiles, storage mode/health, size/duration
  limits and provider capability flags without secrets.
- `UsageEventV1`:
  normalized usage record for LLM, web-search, STT, OCR and storage review,
  including preprocessing units, upload bytes, STT billable units and provider
  adapter when available.
- `PolicyDecisionV1`:
  backend decision for feature access, data class, provider class, output
  profile, provider adapter, limits and warnings.
- `ProviderModelCatalogV1`:
  curated provider/model catalog with production, pilot, research, rejected and
  deferred labels.
- `DocumentExtractionResultV1`:
  normalized output for document extraction/OCR pilot, including document class,
  extracted text, tables and quality warnings.
- `ManagerVisibilityPolicyV1`:
  controlled visibility model for work chats and shared scenarios.
- `RetentionPolicyV1`:
  storage and deletion rules for source files, prepared blobs, transcripts,
  extracted documents, usage metadata and exports.

These are planning contracts. They are not API implementation.

## 5. Contract versioning rule

- Contract names must include a version suffix, for example `TranscriptResultV1`.
- Breaking changes require a new version or ADR update.
- UI/templates should depend on normalized internal contracts, not raw provider
  responses.
- Provider adapters translate external responses into internal contracts.
- Contract changes require updated smoke/acceptance checks.

## 6. Anti-patterns

- Frontend directly calls external STT provider with API key.
- UI decides whether data may be sent to provider.
- UI hardcodes MP3 as the only possible transcription output.
- UI presents every upstream FFmpeg-supported format as guaranteed product
  support without proving the configured ffmpeg.wasm build/browser can decode it.
- UI sends unsupported source media directly to the STT provider when
  normalization has failed or no audio stream was detected.
- Production silently loads ffmpeg wasm assets from public CDN.
- Source media is stored by default without explicit retention decision.
- OpenWebUI core is patched deeply for every custom workflow.
- Users are sent to a separate STT service UI, then asked to copy transcript
  back into OpenWebUI manually.
- Transcription is triggered by magic/implicit LLM inference without an explicit
  user action on the media attachment. If a user types "транскрибируй" while a
  media attachment is present, it must map to the same explicit media attachment
  action contract.
- Provider response shape leaks into prompts/templates.
- Manager visibility is implemented through blanket admin access.
- No-delete is treated as audit/retention.
- OCR pilot is treated as production OCR pipeline.
- Native OpenWebUI analytics is assumed sufficient without runtime proof.
- Stage 2 backend creates a parallel identity system instead of using approved
  OpenWebUI identity/session context.
- External provider setup starts before data policy by provider class is
  approved.

## 7. First contract to define

First implementation-facing contract must be STT proxy boundary:

- `TranscriptionJobV1`;
- `SttMediaInputProfileV1`;
- `PreparedAudioMetadataV1`;
- `TranscriptResultV1`;
- `SttProviderCapabilityProfileV1`;
- `TranscriptionRuntimeCapabilitiesV1`;
- `UsageEventV1`;
- `PolicyDecisionV1`.

`ADR-0004 STT Proxy Boundary` is now the proposed review document for this
boundary. It recommends a server-side STT proxy/job service and rejects direct
browser-to-provider calls.

Current implementation state:

- the external browser ffmpeg preprocessing contract is inspected;
- private sidecar job routes and internal auth are implemented;
- prepared-MP3 OpenWebUI Action path is implemented and proven;
- browser ffmpeg.wasm normalization is implemented and proven on generated MP3,
  MP4-with-audio and WebM proof media;
- unsupported/decode-failed and no-audio inputs fail safely before provider
  handoff;
- OpenWebUI static browser config currently selects MP3 / `audio/mpeg` as the
  proven compatibility output profile, not a permanent architecture constraint;
- input compatibility is now broad/capability-based: declared extensions and
  MIME prefixes are UI hints, while actual support requires ffmpeg probe/decode
  and audio-stream detection in the configured browser build;
- Lemonfox is the first Stage 2 STT provider through `LemonfoxSttAdapter`;
- Opus is the preferred default output-profile candidate pending Lemonfox
  compatibility proof;
- production ffmpeg asset mode is `self_hosted`;
- normalized/prepared audio storage is controlled by `auto|s3|none`, with S3
  required only when storage mode/policy says so;
- runtime capabilities must expose effective output profiles, upload limits,
  input affordance hints, duration TBDs, storage mode/health and provider-side
  cancellation support;
- owner/operator proof is accepted for ADR planning and the generated proof
  matrix now covers the implemented browser-normalization path;
- remaining production decisions are ADR review/status, final Opus/default
  output profile policy, storage mode/env decision, prepared-audio retention,
  provider cancel/duration TBD handling, large/mobile acceptance and transcript
  lifecycle/workflow.

The ffmpeg workflow is a media preprocessing asset, not a security boundary.
The current dependency strategy makes self-host/internal cache the production
default. CDN mode remains allowed for proof/dev/fallback and production only
with explicit approval and pinned versions. No heavy wasm/core assets should be
vendored in this docs-only decision.

## 8. Related docs

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Stage 2 README](README.md)
- [Extension-First Implementation Pattern](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [Implementation Gates](IMPLEMENTATION_GATES.md)
- [STT Env Contract](config/STT_ENV_CONTRACT.md)
- [STT Media Input Normalization Contract](contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)
- [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md)
- [Transcription STT Blueprint](blueprints/TRANSCRIPTION_STT.blueprint.md)
- [FFMPEG Workflow Artifact Inspection](research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG Browser Workflow Research](research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [Transcription STT Research](research/TRANSCRIPTION_STT_RESEARCH.md)
- [OpenWebUI-native STT UX Integration Research](../reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md)
