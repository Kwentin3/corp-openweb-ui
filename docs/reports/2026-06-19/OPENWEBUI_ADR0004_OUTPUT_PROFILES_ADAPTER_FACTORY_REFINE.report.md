# OpenWebUI ADR-0004 Output Profiles and Adapter Factory Refine Report

Date: 2026-06-19

Canonical path:

- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`

Moved from the wrong date folder:

- `docs/reports/2026-06-18/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`

## 1. Summary

ADR-0004 was refined as documentation only. No implementation, provider setup,
runtime configuration or production change was started.

The refine makes ADR-0004 more precise for human review in five areas:

- output profiles replace MP3-only architecture wording;
- STT provider access is routed through an adapter/factory boundary;
- ffmpeg asset loading has explicit `cdn mode` and `self_hosted mode`;
- proof matrix stays lightweight and reproducibility-focused;
- cancel UX is required across preprocessing, upload and STT job lifecycle
  where technically possible.

ADR-0004 remains `Status: Proposed`.

## 2. Why refine was needed

The previous ADR state already had the correct main boundary:

- selected direction: server-side STT proxy/job service;
- direct browser-to-provider calls rejected;
- provider API keys forbidden in browser;
- external ffmpeg workflow inspected;
- source-proven workflow output found: MP3 / `audio/mpeg`;
- operator manual proof recorded for mobile and large-file scenarios.

However, several details could still be misread during implementation planning:

- MP3 / `audio/mpeg` could be treated as the only future prepared-audio format;
- Lemonfox priority could be treated as hardcoded provider architecture;
- source use of `unpkg.com` could be treated as either forbidden or silently
  production-approved;
- proof matrix wording could grow into broad certification work;
- cancel could remain an implied UI convenience instead of a required lifecycle
  behavior.

The refine keeps the useful source facts, but separates them from future
production decisions.

## 3. Files reviewed

Primary decision and boundary files:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`

Research and source-fact files:

- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`

Planning, gates and acceptance files:

- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

Previous report context:

- `docs/reports/2026-06-18/OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md`

## 4. Files changed

Modified:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/_index/redirects.md`

Created / moved:

- canonical report:
  `docs/reports/2026-06-19/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`
- moved from:
  `docs/reports/2026-06-18/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`

## 5. Scope guardrails

The refine intentionally did not do the following:

- no backend implementation;
- no frontend implementation;
- no provider setup;
- no real API keys;
- no `.env` read;
- no compose/env/scripts changes;
- no production changes;
- no ffmpeg wasm/core binaries vendored;
- no full FFmpeg source vendored;
- no ADR status change to Accepted.

The changed files are documentation and report files under `docs/`.

## 6. Output profiles update

ADR-0004 now treats browser preprocessing output as an explicit output profile
contract.

Source-proven default candidate:

```text
mp3_high_compat:
  mime: audio/mpeg
  container: mp3
  codec: libmp3lame
  status: source-proven candidate
```

Additional candidates kept open for review:

```text
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

Rules now documented:

- output profile is selected by policy, setting or STT provider compatibility;
- frontend must not hardcode MP3 as the only possible output;
- backend validates prepared audio against the selected output profile;
- STT provider adapter declares supported input profiles;
- default output profile is a separate implementation decision.

Important wording added:

MP3 / `audio/mpeg` is a proven source workflow output, not a permanent
architecture constraint.

## 7. STT Provider Adapter Factory update

ADR-0004 now requires a backend adapter/factory boundary for provider calls.

Documented concept:

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

The stable outer contract is:

- successful provider result returns normalized `TranscriptResultV1`;
- provider error returns normalized `ProviderErrorV1` or documented reason
  codes;
- UI and orchestration do not depend on raw provider response;
- provider can be changed without rewriting browser preprocessing or templates;
- Lemonfox remains the priority candidate, not hardwired architecture.

## 8. FFMPEG asset loading strategy

ADR-0004 now separates source workflow facts from production deployment choice.

Source fact:

- source workflow loads ffmpeg assets from `unpkg.com`.

Documented deployment modes:

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

Production rule:

- CDN is not forbidden;
- production must not silently depend on unpinned public CDN;
- self-host/internal cache is the preferred fallback for corporate
  environments;
- no heavy wasm/core assets should be vendored into the repo without a separate
  decision.

## 9. Lightweight proof matrix

ADR-0004 now states that proof matrix is not certification. It is a lightweight
reproducibility record.

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

Operator manual proof remains useful evidence, but it is not an automated
repository proof and not a universal mobile/all-file support claim.

## 10. Cancel UX

ADR-0004 now makes cancel required UX for Stage 2 transcription where
technically possible.

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

Possible job statuses now documented:

```text
queued
preprocessing
uploading
processing
completed
failed
cancelled
```

The UX requirement is explicit: a user must not be left with a frozen
long-running task.

## 11. Contract updates

`TranscriptionJobV1` was expanded with lifecycle and decision fields:

- `output_profile_id`;
- `asset_loading_mode`;
- `preprocessing_status`;
- `upload_status`;
- `cancel_requested`;
- `cancelled_at`;
- `selected_stt_provider`;
- `adapter_id`.

`TranscriptResultV1` was expanded with normalization and provenance fields:

- `source_output_profile_id`;
- `provider_adapter_id`;
- `normalized_segments`;
- `provider_features_used`.

`UsageEventV1` was expanded for future cost/usage review:

- `preprocessing_units`;
- `upload_bytes`;
- `stt_billable_units`;
- `provider_adapter_id`.

`PolicyDecisionV1` was clarified so policy can include:

- output profile decision;
- selected STT provider;
- provider adapter decision.

## 12. Related document synchronization

`CONTRACT_BOUNDARIES.md` now references:

- STT Provider Adapter Factory;
- output profile fields in contracts;
- anti-pattern: UI hardcodes MP3 as the only possible output;
- asset loading mode as an explicit production decision.

`TRANSCRIPTION_STT.blueprint.md` now references:

- selected output profile in the target user workflow;
- provider adapter factory in backend boundary;
- cancel lifecycle as a boundary requirement;
- asset loading mode and adapter compatibility as open decisions.

`FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md` now references:

- `mp3_high_compat` as source-proven output profile;
- output profile rule;
- `cdn mode` and `self_hosted mode`;
- lightweight proof matrix;
- cancel requirements.

`FFMPEG_BROWSER_WORKFLOW_RESEARCH.md` now references:

- CDN as allowed but explicit deployment mode;
- MP3 not as permanent architecture constraint;
- adapter factory in proxy call;
- output profile in acceptance proof.

`IMPLEMENTATION_GATES.md` now blocks Gate 2 on:

- lightweight proof matrix;
- output profile decision;
- STT adapter/factory decision;
- ffmpeg asset loading strategy;
- cancel UX expectations.

`ENGINEERING_BACKLOG.md` now tracks:

- output profiles;
- provider adapter factory;
- lightweight proof matrix;
- adapter compatibility proof;
- asset loading mode decision;
- cancel lifecycle proof where technically possible.

`ACCEPTANCE_MATRIX.md` now requires:

- adapter/factory boundary;
- selected output profile validation;
- lightweight proof matrix cases;
- cancel UX coverage;
- production asset loading mode decision.

`TEST_DATA_REQUIREMENTS.md` now asks for:

- selected output profile per proof case;
- minimum six proof cases;
- provider adapter compatibility notes;
- cancel behavior notes.

## 13. Remaining decisions

The refine does not close implementation readiness. Remaining decisions:

- human approval of ADR-0004;
- default output profile;
- selected STT provider adapter;
- ffmpeg asset loading mode for production;
- licensing/ops review for MP3 / `libmp3lame` and ffmpeg core assets;
- lightweight proof matrix evidence;
- production file size and duration limits;
- provider-side cancellation capability;
- local fallback behavior when provider-side cancellation is unavailable;
- retention behavior for cancelled or late-arriving provider results.

## 14. Verification performed

Checks performed after the refine:

- `git status --short`;
- `git diff --check`;
- staged file scope review;
- ADR status check: `Status: Proposed`;
- browser-to-provider rejection check;
- API keys in browser forbidden check;
- MP3-only wording check;
- adapter factory wording check;
- CDN production approval wording check;
- lightweight proof matrix wording check;
- cancel UX wording check;
- secret-pattern scan over changed docs.

Observed scope:

- only markdown/report documentation under `docs/` was changed;
- no source code was changed;
- no compose/env/scripts were changed;
- no provider setup was added;
- no secrets were added;
- no wasm/core binaries were added.

## 15. Final status

`ADR-0004 remains Proposed and is more precise for human review. Implementation still waits for ADR acceptance, selected output profile, STT adapter decision, asset loading mode and lightweight proof matrix.`
