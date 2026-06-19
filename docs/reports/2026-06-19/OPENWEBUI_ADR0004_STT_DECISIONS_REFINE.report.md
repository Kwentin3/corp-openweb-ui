# OpenWebUI ADR-0004 STT Decisions Refine Report

Date: 2026-06-19

## 1. Summary

ADR-0004 and related Stage 2 planning docs were refined to capture newly
accepted STT decisions without starting implementation.

The update records:

- Lemonfox as the first Stage 2 STT provider through `LemonfoxSttAdapter`;
- STT Provider Adapter Factory remains mandatory;
- Opus as preferred default output-profile candidate pending Lemonfox proof;
- MP3 / `audio/mpeg` as source-proven compatibility fallback;
- `self_hosted` as production default for ffmpeg wasm assets;
- CDN as dev/proof/fallback option, or production only with explicit approval;
- browser preprocessing input limit: 1 GB / 1024 MB;
- Lemonfox direct prepared-audio upload limit: 100 MB;
- S3/object storage for normalized/prepared audio sent to provider;
- env-driven provider, output profile, asset, storage, retention, limits and
  cancel configuration;
- cancel behavior for local job and provider job where supported.

ADR-0004 remains `Status: Proposed`.

## 2. New decisions

New decisions reflected in docs:

- First STT provider: Lemonfox.
- First adapter: `LemonfoxSttAdapter`.
- Conceptual default adapter id: `lemonfox`.
- Production ffmpeg asset mode: `self_hosted`.
- CDN mode: allowed for dev/proof/fallback; production only by explicit
  approval with pinned versions.
- Preferred output default candidate: Opus, pending Lemonfox compatibility
  proof.
- Proven compatibility fallback: MP3 / `audio/mpeg`.
- Browser-side wasm input limit: 1 GB / 1024 MB.
- Lemonfox direct upload limit: 100 MB prepared audio.
- Prepared audio over 100 MB: fail by default unless URL/object-storage provider
  path is approved.
- Prepared/normalized audio sent to provider: stored in S3/object storage.
- Source media storage: disabled unless explicitly enabled.
- Storage and retention: env-configurable.
- Cancel: provider cancel if supported; otherwise local cancel and ignore/clean
  late result according to retention policy.

## 3. Files reviewed

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`

## 4. Files changed

Modified:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

Created:

- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_STT_DECISIONS_REFINE.report.md`

## 5. Output profile decision update

ADR-0004 now keeps output profiles flexible while reflecting the current
decision:

- Opus is the preferred default candidate if Lemonfox compatibility proof
  passes.
- Do not choose permanently between `opus_webm_compact` and
  `opus_ogg_compact` until Lemonfox compatibility proof is captured.
- MP3 / `audio/mpeg` remains the source-proven compatibility fallback.
- Frontend must not hardcode output format.
- Backend validates prepared audio against the selected profile.
- STT adapter declares supported input profiles.
- Default profile can change through env/config without orchestration changes.

## 6. Lemonfox adapter update

ADR-0004 now states:

- Lemonfox is the first provider for Stage 2.
- `LemonfoxSttAdapter` is the first adapter.
- Conceptual `default_adapter_id` is `lemonfox`.
- Lemonfox remains isolated behind `SttProviderAdapterFactory`.
- Future providers can be added without changing browser preprocessing.

Future adapter candidates remain:

- OpenAI STT;
- Deepgram;
- Yandex SpeechKit;
- Local Whisper;
- other OpenAI-compatible STT.

## 7. Env/config contract

Created:

- `docs/stage2/config/STT_ENV_CONTRACT.md`

The draft contract covers:

- provider selection: `STAGE2_STT_PROVIDER=lemonfox`;
- Lemonfox server-side config and placeholders;
- output profile and fallback output profile;
- browser preprocessing limits;
- ffmpeg asset loading mode and versions;
- S3/object storage settings;
- prepared-audio retention and source media storage flag;
- prepared-audio size behavior;
- cancel flags;
- security notes.

It is explicitly not a final `.env.example` and contains no real keys.

## 8. FFMPEG asset delivery

Production default:

```text
STAGE2_FFMPEG_ASSET_MODE=self_hosted
```

Documented rules:

- self-hosted assets are served under the portal domain or internal CDN;
- cache headers, rollback path and license notices are required before
  implementation;
- CDN is allowed for dev/proof/fallback;
- CDN in production requires explicit approval and pinned versions;
- no wasm/core binaries or full FFmpeg source are committed by this docs task.

## 9. Limits

Documented limits:

```text
STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB=1024
STAGE2_STT_MAX_PREPARED_AUDIO_MB=100
```

Typed error candidates:

```text
prepared_audio_too_large
unsupported_input_format
preprocessing_failed
provider_direct_upload_limit_exceeded
```

Prepared audio over 100 MB:

- default behavior: fail with typed error;
- fallback candidates: provider URL upload or object-storage provider path;
- fallback is not approved until Lemonfox compatibility, storage access, expiry
  and sensitivity behavior are proven.

## 10. Storage and retention

ADR-0004 now records that normalized/prepared audio sent to the provider should
be stored in S3/object storage.

Documented rules:

- storage mode default: `s3`;
- bucket, prefix and retention are env-configurable;
- prepared audio storage is controlled by config;
- source media storage is disabled unless explicitly enabled;
- cancelled jobs follow retention policy;
- late provider results after local cancel are ignored or stored only if policy
  explicitly allows it.

New `TranscriptionJobV1` fields:

- `prepared_audio_object_key`;
- `prepared_audio_size_bytes`;
- `prepared_audio_retention_policy_id`;
- `source_media_stored`;
- `source_media_object_key`;
- `storage_mode`.

## 11. Cancel behavior

ADR-0004 now documents:

- preprocessing cancel terminates ffmpeg worker;
- upload cancel aborts upload/multipart upload where possible;
- STT job cancel calls provider cancel if provider supports it;
- if provider cancel is unsupported, local job becomes cancelled and late
  provider result is ignored/cleaned by retention policy.

Status/reason candidates:

```text
cancel_requested
cancelled
cancelled_by_user
provider_cancel_unsupported
cancelled_locally_provider_continues
```

## 12. Gates/backlog/acceptance updates

`IMPLEMENTATION_GATES.md` Gate 2 now blocks on:

- ADR-0004 approval;
- Opus/Lemonfox compatibility proof;
- Lemonfox adapter config;
- STT env/config contract review;
- self-hosted ffmpeg asset path;
- S3/object storage env decision;
- prepared-audio retention;
- prepared audio over 100 MB behavior;
- lightweight proof matrix.

`ENGINEERING_BACKLOG.md` now tracks:

- STT env/config contract review;
- Lemonfox adapter proof;
- Opus output profile compatibility proof;
- self-hosted ffmpeg asset decision;
- S3 prepared audio storage and retention decision;
- cancel lifecycle proof;
- prepared audio over 100 MB behavior.

`ACCEPTANCE_MATRIX.md` and `TEST_DATA_REQUIREMENTS.md` now require:

- Lemonfox adapter proof;
- Opus profile compatibility notes;
- MP3 fallback confirmation;
- 1 GB browser input limit;
- 100 MB Lemonfox direct upload limit;
- S3/object storage config decision;
- prepared-audio retention decision;
- cancel behavior proof.

## 13. Remaining decisions

Still open before implementation acceptance:

- Human approval of ADR-0004.
- Lemonfox compatibility proof for Opus.
- Final choice between WebM/Opus and OGG/Opus.
- Self-hosted ffmpeg asset path under portal/internal CDN.
- ffmpeg cache headers, rollback and license notes.
- S3 bucket/prefix for prepared audio.
- Prepared audio retention days.
- Transcript retention days.
- Whether source media storage is ever enabled.
- Behavior for prepared audio over 100 MB beyond default fail-fast.
- Whether Lemonfox/provider supports provider-side cancellation.
- Maximum duration limit.

## 14. Final status

`ADR-0004 remains Proposed, but Stage 2 STT decisions are now explicit enough for human ADR review.`
