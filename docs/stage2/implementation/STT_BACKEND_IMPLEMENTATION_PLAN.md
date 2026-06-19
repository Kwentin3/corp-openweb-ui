# STT Backend Implementation Plan

Status: planning document. No implementation started.

## 1. Scope

First backend slice includes:

- STT env/config loading;
- provider capability profile;
- STT Provider Adapter Factory;
- `LemonfoxSttAdapter` proof-oriented implementation plan;
- runtime capabilities endpoint;
- output profile selection/validation;
- prepared audio size validation;
- storage mode decision path: `auto|s3|none`;
- transcription job model;
- cancel state model;
- usage event draft;
- backend validation/error model.

Out of scope:

- final UI;
- OpenWebUI fork;
- browser ffmpeg implementation;
- OCR;
- web-search;
- manager visibility;
- hard billing/gateway;
- data masking;
- production-ready retention/audit archive.

## 2. Context documents

| Purpose | Document | Why |
| ------- | -------- | --- |
| STT boundary decision | `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md` | Defines proxy, adapter, capabilities, storage, limits and cancel contracts. |
| Env contract | `docs/stage2/config/STT_ENV_CONTRACT.md` | Lists server-side config keys and defaults/TBDs. |
| Domain boundaries | `docs/stage2/CONTRACT_BOUNDARIES.md` | Keeps Stage 2 logic outside browser/provider leakage. |
| STT blueprint | `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md` | Summarizes workflow and backend-first path. |
| Lemonfox facts | `docs/stage2/research/LEMONFOX_STT_RESEARCH.md` | Captures documented provider capabilities and unknowns. |
| ffmpeg handoff | `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md` | Defines prepared-audio source contract and optional smoke cases. |
| Gates | `docs/stage2/IMPLEMENTATION_GATES.md` | Lists remaining owner/runtime decisions. |
| Acceptance | `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | Defines expected STT acceptance signals and test data. |

## 3. Decisions already made

- Server-side STT proxy/job service.
- No browser-to-provider STT calls.
- No STT API keys in browser.
- Lemonfox is first provider.
- Adapter factory is mandatory.
- Output profile is env/config driven.
- Storage mode is env/config driven.
- Cancel lifecycle is required.
- Runtime capabilities endpoint is needed.
- Prepared audio over 100 MB has warning/fail behavior.
- Source media storage is off by default.

## 4. Contracts to preserve

- `TranscriptionJobV1`: job id, user/workspace, source metadata,
  prepared-audio metadata, storage mode/health, output profile, provider,
  adapter, status, progress, cancel fields, retention and typed error.
- `TranscriptResultV1`: normalized transcript text, language, segments,
  speakers, word timestamps, duration, output profile, provider adapter and
  warnings.
- `UsageEventV1`: provider adapter, model, upload bytes, preprocessing units,
  STT billable units, estimated cost and correlation id.
- `PolicyDecisionV1`: allowed/denied action with user/workspace, data class,
  provider class, output profile, adapter and reason.
- `SttProviderCapabilityProfileV1`: provider/adapter id, supported input
  profiles, upload limits, duration, URL upload, cancel, callbacks, timestamps,
  speaker labels, languages, response formats and unknowns.
- `TranscriptionRuntimeCapabilitiesV1`: UI-safe effective capabilities, limits,
  output profiles, storage mode/health, provider id, adapter id, cancel strategy
  and warnings.
- `ProviderErrorV1`: normalized provider error reason, retryability, provider
  status/code where safe, and user-safe message.

Source of truth: ADR-0004.

## 5. Runtime endpoints draft

```text
GET /stage2-api/transcription/capabilities
POST /stage2-api/transcription/jobs
GET /stage2-api/transcription/jobs/{job_id}
GET /stage2-api/transcription/jobs/{job_id}/result
POST /stage2-api/transcription/jobs/{job_id}/cancel
```

Rules:

- endpoint names are draft;
- final routing depends on OpenWebUI auth/session proof;
- first implementation may start with config, capability model and
  `GET /capabilities` before full job lifecycle;
- no endpoint exposes provider keys, raw `.env`, storage credentials or raw
  provider responses.

## 6. Env/config keys

Provider:

- `STAGE2_STT_PROVIDER`;
- `STAGE2_STT_PROVIDER_ADAPTER`.

Lemonfox:

- `STAGE2_LEMONFOX_API_KEY`;
- `STAGE2_LEMONFOX_BASE_URL`;
- `STAGE2_LEMONFOX_MODEL`;
- `STAGE2_LEMONFOX_LANGUAGE`;
- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS`;
- `STAGE2_LEMONFOX_ENABLE_TIMESTAMPS`;
- `STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB`;
- `STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB`;
- `STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES`.

Output profiles:

- `STAGE2_STT_OUTPUT_PROFILE`;
- `STAGE2_STT_FALLBACK_OUTPUT_PROFILE`.

ffmpeg assets:

- `STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB`;
- `STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES`;
- `STAGE2_FFMPEG_ASSET_MODE`;
- `STAGE2_FFMPEG_CORE_BASE_URL`;
- `STAGE2_FFMPEG_PACKAGE_VERSION`;
- `STAGE2_FFMPEG_CORE_VERSION`.

Storage and retention:

- `STAGE2_STT_STORAGE_MODE`;
- `STAGE2_STT_REQUIRE_STORAGE_HEALTH`;
- `STAGE2_STT_AUDIO_BUCKET`;
- `STAGE2_STT_AUDIO_PREFIX`;
- `STAGE2_STT_STORE_PREPARED_AUDIO`;
- `STAGE2_STT_STORE_SOURCE_MEDIA`;
- `STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS`;
- `STAGE2_STT_TRANSCRIPT_RETENTION_DAYS`.

Limits and cancel:

- `STAGE2_STT_MAX_PREPARED_AUDIO_MB`;
- `STAGE2_STT_DIRECT_UPLOAD_WARNING_MB`;
- `STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE`;
- `STAGE2_STT_PROVIDER_MAX_DURATION_MINUTES`;
- `STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES`;
- `STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED`;
- `STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL`;
- `STAGE2_STT_PROVIDER_CANCEL_SUPPORT`.

## 7. Codebase discovery plan

| Question | Search terms | Expected output |
| -------- | ------------ | --------------- |
| Where is backend entrypoint? | `backend`, `main`, `fastapi`, `openwebui` | Candidate service root and runtime entrypoint. |
| Where are API routes registered? | `api`, `router`, `routes`, `APIRouter` | Route registration pattern and extension point. |
| How does auth/session work? | `auth`, `session`, `user`, `current_user`, `get_current` | Approved way to identify caller/workspace. |
| How is server env read? | `env`, `config`, `settings`, `os.environ`, `pydantic` | Single server-side config entrypoint or needed addition. |
| Where can Stage 2 domain service live? | `stage2`, `services`, `domain`, `routers`, `apps` | Minimal non-core location for STT proxy code. |
| Are storage/S3 helpers present? | `s3`, `storage`, `bucket`, `object`, `presigned` | Reusable storage abstraction or missing helper. |
| How is logging/errors done? | `logger`, `logging`, `HTTPException`, `error` | Existing error/log mapping style. |
| Where are tests/smokes? | `test`, `pytest`, `smoke`, `scripts` | Test runner and minimal smoke pattern. |

Discovery output must name exact files before implementation starts.

## 8. Implementation slices

### Slice 1. Config and capability model

- locate server config entrypoint;
- load Stage 2 STT env;
- validate required/default values;
- define output profile constants;
- define `SttProviderCapabilityProfileV1`;
- define `TranscriptionRuntimeCapabilitiesV1`;
- add config validation tests.

Acceptance:

- missing required provider key is allowed only when no live provider call is
  attempted;
- invalid output/storage/cancel values fail fast;
- no browser-exposed config path is used.

### Slice 2. Lemonfox adapter proof

- define provider adapter interface;
- implement `LemonfoxSttAdapter.get_capabilities()`;
- prepare request-shape method behind adapter boundary;
- use mock/stub when no key is present;
- run live smoke only when operator provides key outside Git.

Acceptance:

- capabilities match ADR/research;
- no real API key in repo, logs or tests;
- provider response parsing stays inside adapter.

### Slice 3. Output profile validation

- implement allowed profiles;
- apply selected and fallback profile from config;
- validate prepared audio MIME/profile metadata;
- map unsupported profile to typed error.

Acceptance:

- `opus_webm_compact`, `opus_ogg_compact`, `mp3_high_compat`,
  `wav_pcm_safe` are recognized;
- MP3 fallback remains available;
- UI does not define allowed profiles.

### Slice 4. Storage mode logic

- implement `auto`, `s3`, `none`;
- define storage health contract;
- generate object keys without secrets/sensitive metadata;
- attach retention metadata;
- keep source media off unless explicitly enabled.

Acceptance:

- `auto` uses S3 only when configured and healthy;
- `s3` fails fast when storage unavailable;
- `none` does not persist prepared audio;
- retention fields are recorded without enforcing final archive policy.

### Slice 5. Job model and cancel states

- define job statuses:
  `queued`, `preprocessing`, `uploading`, `processing`, `completed`, `failed`,
  `cancel_requested`, `cancelled`;
- implement local cancel;
- call provider cancel only when capability says supported;
- ignore/cleanup late provider result by retention policy.

Acceptance:

- local cancel works without provider cancel support;
- `provider_cancel_unknown` and `late_provider_result_ignored` are typed
  reason codes;
- late result cannot overwrite a cancelled job silently.

### Slice 6. Runtime capabilities endpoint

- add `GET /stage2-api/transcription/capabilities`;
- return effective provider, adapter, profiles, limits, storage mode/health,
  timestamps/speaker-label support, cancel strategy and warnings;
- omit secrets and raw provider details.

Acceptance:

- endpoint works without Lemonfox API key;
- response matches `TranscriptionRuntimeCapabilitiesV1`;
- no secret-like values appear in response.

### Slice 7. Minimal smoke / tests

- config validation;
- adapter capability profile;
- capability endpoint;
- no API key leak;
- prepared audio over 100 MB warning/fail behavior;
- storage mode branching;
- local cancel state transition.

Acceptance:

- tests run without real provider key;
- live Lemonfox smoke is optional/operator-triggered;
- no frontend code is required.

## 9. Stop conditions

Stop and report before coding further if:

- no backend/domain-service location exists without deep OpenWebUI fork;
- auth/session propagation is unclear;
- server-side env cannot be read through a safe config entrypoint;
- there is no safe place for provider secrets;
- Lemonfox key is needed for a step but not provided by operator;
- `s3` mode is selected but bucket/config/health is unavailable;
- implementation requires frontend changes before backend contract;
- implementation requires production/compose/env/scripts changes without a
  separate command;
- any path would put API key in browser, `NEXT_PUBLIC_*`, logs or tests;
- implementation requires vendoring wasm/core binaries;
- storage helper would require ad hoc filesystem secret paths;
- provider response would leak into UI/templates instead of normalized
  contracts.

## 10. Acceptance for this plan

Plan is ready when:

- required docs are listed;
- decisions are summarized;
- contracts are listed;
- endpoints are drafted;
- env keys are referenced;
- codebase discovery plan is defined;
- implementation slices are defined;
- stop conditions are defined;
- no code has started.

Current status: ready for review. No implementation started.
