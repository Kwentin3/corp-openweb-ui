# STT v2 Gate 1-2 Runtime / Env Contract

Status: Gate 1-2 runtime contract.

Date: 2026-07-02.

Scope: runtime/env knobs for STT v2 Gate 1-2.

## 1. Purpose

Define safe configuration expectations for proving:

- LemonFox speaker labels;
- durable internal artifact storage;
- retention basics;
- safe defaults when config is missing.

This document does not change runtime config by itself.

Current operational status as of 2026-07-02:

- server `.env` is the source of truth for PRD-0;
- local workspace `.env` was synchronized from server `.env`;
- server `stage2-stt` container was recreated with
  `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true`;
- server runtime env includes the STT v2 artifact-store block listed below.

## 2. Source Basis

Local:

- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/contracts/STT_V2_ARTIFACT_CONTRACTS.md`
- `docs/stage2/contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/runtime.py`

External:

- LemonFox STT API: https://www.lemonfox.ai/apis/speech-to-text
- OpenWebUI API endpoint auth: https://docs.openwebui.com/reference/api-endpoints/

## 3. Diarization Flag

Required for Gate 1 proof:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
```

Safe default:

```text
false
```

Current PRD-0 runtime decision:

```text
true
```

Behavior:

- false: ordinary STT remains available, speaker-label proof is Not Done;
- true: LemonFox adapter must request speaker labels and verbose JSON;
- config load must not expose API keys or raw env values through capabilities.

## 4. Provider Request Expectations

When speaker labels are enabled:

```text
speaker_labels=true
response_format=verbose_json
```

If word timestamp proof is required:

```text
timestamp_granularities[]=word
```

Provider direct upload remains constrained by LemonFox documented limits.
Gate 1-2 does not implement URL upload/object storage for larger provider input.

## 5. Artifact Store Configuration

Namespace decision:

- keep `STAGE2_LEMONFOX_*` for provider-specific LemonFox settings;
- use `STAGE2_STT_*` for new STT runtime and artifact-store settings;
- do not introduce `STT_V2_*` env names without updating this contract first.

Recommended variable names for implementation:

```text
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_ARTIFACT_STORE_PATH=/data/stage2-stt/artifacts.sqlite3
STAGE2_STT_ARTIFACT_PAYLOAD_DIR=/data/stage2-stt/artifact-payloads
```

Safe defaults:

- if store mode/path is missing in production-like runtime: fail Gate 2 startup
  or disable Gate 2 artifact features with typed `artifact_store_unavailable`;
- do not silently fall back to process memory for Gate 2 Done;
- in-memory store is allowed only for unit tests and explicit local proof.

## 6. Retention Configuration

Recommended variable names:

```text
STAGE2_STT_TRANSCRIPT_TTL_DAYS=14
STAGE2_STT_TRANSFORMATION_TTL_DAYS=14
STAGE2_STT_PREPARED_AUDIO_TTL_HOURS=24
STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED=false
STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_TTL_HOURS=0
STAGE2_STT_ARTIFACT_ROTATION_INTERVAL_HOURS=24
STAGE2_STT_ARTIFACT_HARD_DELETE_AFTER_EXPIRY=true
```

Safe defaults:

- diagnostic raw provider payload disabled;
- hard delete expired payloads;
- prepared audio refs/metadata short TTL;
- never retain media copies by default.

## 7. Capability Endpoint Expectations

Capabilities endpoint should expose UI-safe facts only:

```text
supports_speaker_labels: bool
selected_output_profile: string
fallback_output_profile: string
available_output_profiles: string[]
max_direct_upload_bytes: int | null
max_url_input_bytes: int | null
artifact_store_available: bool
artifact_store_mode: "sqlite" | "memory_test" | "disabled"
```

Must not expose:

- provider API key;
- provider headers;
- raw env values;
- internal storage path;
- signed URLs;
- raw provider payload.

## 8. Missing Config Behavior

Gate 1:

- missing speaker-label flag defaults to false;
- capabilities must show speaker labels disabled;
- proof cannot pass until enabled.

Gate 2:

- missing artifact store config must not produce fake durability;
- return typed `artifact_store_unavailable` for artifact retrieval;
- ordinary STT flat output should remain available if provider path is healthy.

## 9. Acceptance Criteria

This contract is satisfied when:

- runtime proof records effective config values without secrets;
- Gate 1 uses speaker-label flag and verbose JSON;
- Gate 2 uses persistent store config, not unlabelled memory fallback;
- diagnostic provider payload storage is disabled;
- missing config behavior is fail-safe;
- capabilities endpoint is UI-safe and contains no secrets.
