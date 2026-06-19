# OpenWebUI ADR-0004 Output Profiles and Adapter Factory Refine Report

Date: 2026-06-18

## 1. Summary

ADR-0004 was refined without starting implementation.

The refine clarifies:

- MP3 / `audio/mpeg` is the source-proven default candidate, not a permanent
  architecture constraint;
- Stage 2 backend provider calls must go through an STT Provider Adapter
  Factory;
- CDN ffmpeg asset loading is allowed as an explicit deployment mode, not as a
  silent production dependency;
- the proof matrix is a lightweight reproducibility record;
- cancel UX is required across preprocessing, upload and STT job lifecycle where
  technically possible.

ADR-0004 remains `Status: Proposed`.

## 2. Why refine was needed

The previous ADR state correctly selected a server-side STT proxy/job boundary
and rejected browser-to-provider calls, but several items needed sharper review
wording before implementation planning:

- source-proven MP3 output could be misread as the only future output;
- Lemonfox priority could be misread as hardwired architecture;
- `unpkg.com` source usage could be misread as either forbidden or silently
  production-approved;
- proof matrix wording could drift into broad certification;
- cancel needed to be explicit, not an implied progress feature.

## 3. Files reviewed

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
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

Created:

- `docs/reports/2026-06-18/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`

## 5. Output profiles update

ADR-0004 now defines output profiles:

- `mp3_high_compat`: source-proven candidate, `audio/mpeg`, `mp3`,
  `libmp3lame`;
- `opus_webm_compact`: candidate pending provider compatibility proof;
- `opus_ogg_compact`: candidate pending provider compatibility proof;
- `wav_pcm_safe`: fallback candidate, larger files.

Rule: frontend must not hardcode MP3 as the only possible output. Backend
validates prepared audio against the selected output profile. STT adapters
declare supported input profiles.

## 6. STT Provider Adapter Factory update

ADR-0004 now requires `SttProviderAdapterFactory` with provider-specific
adapters such as Lemonfox, OpenAI, Gemini, Yandex SpeechKit, Deepgram and Local
Whisper.

Adapters own provider endpoint, auth, request format, supported input profiles,
provider limits, diarization/timestamp support, response parsing, error mapping
and usage metadata when available.

Adapters return `TranscriptResultV1`; provider errors normalize into
`ProviderErrorV1` or documented reason codes.

## 7. FFMPEG asset loading strategy

ADR-0004 now separates:

- `cdn mode`: fast proof/dev, can use public CDN cache, must pin versions, and
  needs explicit production approval;
- `self_hosted mode`: assets hosted under portal/internal CDN, preferred
  fallback for corporate environments, with ops/licensing/cache review.

Production must not silently depend on unpinned public CDN. Heavy wasm/core
assets are still not vendored without a separate decision.

## 8. Lightweight proof matrix

The proof matrix is now defined as a lightweight reproducibility record, not
certification.

Minimum cases:

- desktop audio;
- desktop video;
- mobile audio;
- mobile video;
- large WAV;
- large video.

Required fields: device, browser, file type, file size, duration, selected
output profile, result and evidence.

## 9. Cancel UX

ADR-0004 now requires cancel UX where technically possible:

- preprocessing cancel: stop ffmpeg worker, terminate local preprocessing,
  cleanup local temporary objects;
- upload cancel: abort request, abort multipart upload if used, cleanup
  incomplete object where possible;
- STT job cancel: mark job cancelled, stop before provider call when possible,
  or ignore/cleanup late provider result by retention policy.

Possible statuses: `queued`, `preprocessing`, `uploading`, `processing`,
`completed`, `failed`, `cancelled`.

## 10. Contract updates

ADR-0004 draft contracts now include:

- `TranscriptionJobV1`: `output_profile_id`, `asset_loading_mode`,
  `preprocessing_status`, `upload_status`, `cancel_requested`, `cancelled_at`,
  `selected_stt_provider`, `adapter_id`;
- `TranscriptResultV1`: `source_output_profile_id`, `provider_adapter_id`,
  `normalized_segments`, `provider_features_used`;
- `UsageEventV1`: optional preprocessing/upload metrics, `stt_billable_units`
  and `provider_adapter_id`;
- `PolicyDecisionV1`: output profile and provider/adapter decision fields.

## 11. Remaining decisions

- Human approval of ADR-0004.
- Default output profile.
- Selected STT provider adapter.
- ffmpeg asset loading mode for production.
- Licensing/ops review for MP3 / `libmp3lame` and ffmpeg core assets.
- Lightweight proof matrix evidence.
- Production file size and duration limits.
- Provider-side cancellation capability and fallback retention behavior.

## 12. Final status

`ADR-0004 remains Proposed and is more precise for human review. Implementation still waits for ADR acceptance, selected output profile, STT adapter decision, asset loading mode and lightweight proof matrix.`
