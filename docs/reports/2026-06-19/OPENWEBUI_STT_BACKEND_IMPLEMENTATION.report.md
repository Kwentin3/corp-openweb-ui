# OpenWebUI STT Backend Implementation Report

## 1. Summary

Implemented the first Stage 2 STT backend slice as an isolated sidecar service:

- service package: `services/stage2-stt`;
- backend/domain package: `services/stage2-stt/stage2_stt`;
- runtime endpoint: `GET /stage2-api/transcription/capabilities`;
- provider boundary: `SttProviderAdapterFactory` with first adapter
  `LemonfoxSttAdapter`;
- server-side STT config loader for the documented `STAGE2_*` env contract;
- Pydantic V1 contract models for jobs, transcript results, usage events,
  policy decisions, provider capabilities, runtime capabilities and provider
  errors;
- output profile validation;
- storage mode decision path for `auto|s3|none`;
- prepared-audio size validation with 100 MB direct upload limit behavior;
- cancel state transitions and late provider result ignore behavior;
- targeted pytest coverage and build-artifact simulation.

Discovery found that this repository is a deployment/docs skeleton and does not
contain OpenWebUI backend source. The implementation therefore does not patch
OpenWebUI core, does not change production compose and does not claim session
handoff is solved. Job execution routes remain intentionally deferred until
OpenWebUI auth/session propagation is approved.

## 2. Files changed

Created:

- `services/stage2-stt/pyproject.toml`
- `services/stage2-stt/stage2_stt/__init__.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/jobs.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/output_profiles.py`
- `services/stage2-stt/stage2_stt/provider.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/stage2_stt/validation.py`
- `services/stage2-stt/tests/test_capabilities_endpoint.py`
- `services/stage2-stt/tests/test_config.py`
- `services/stage2-stt/tests/test_lemonfox_adapter.py`
- `services/stage2-stt/tests/test_validation_storage_jobs.py`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`

Relevant pre-existing worktree change:

- `.env.example` already contained the Stage 2 STT env example block before
  this implementation pass and matches the implemented config keys.

## 3. Architecture implemented

Discovery:

| Discovery item | Result |
| --- | --- |
| Backend entrypoint | No OpenWebUI backend source exists in this repo. PRD-0 uses `compose/openwebui.compose.yml` with `ghcr.io/open-webui/open-webui:v0.9.6`. |
| Route registration pattern | No local OpenWebUI route code exists. New sidecar uses FastAPI in `services/stage2-stt/stage2_stt/app.py`. |
| Auth/session/current user | Not determinable from this repo. No job execution route was added. |
| Server-side env/config | Implemented in `services/stage2-stt/stage2_stt/config.py`. |
| Isolated Stage 2 service location | `services/stage2-stt`. |
| Storage/S3 helper | No repo helper exists. Implemented minimal storage health contract/stub in `storage.py`. |
| Logging/error pattern | No local backend pattern exists. The sidecar returns typed HTTP errors and avoids secret logging. |
| Test runner/style | `pytest` under `services/stage2-stt/tests`. |
| Smoke/test scripts | Existing `scripts/smoke-test.sh` is deployment-only. Added service-local tests and endpoint smoke through TestClient. |

The service is intentionally sidecar-shaped. It can be mounted behind the same
reverse proxy later, but this slice does not change production compose because
the task forbids unnecessary production configuration changes.

## 4. Config/env implemented

Implemented server-side parsing and validation for:

- `STAGE2_STT_PROVIDER`
- `STAGE2_STT_PROVIDER_ADAPTER`
- `STAGE2_LEMONFOX_API_KEY`
- `STAGE2_LEMONFOX_BASE_URL`
- `STAGE2_LEMONFOX_MODEL`
- `STAGE2_LEMONFOX_LANGUAGE`
- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS`
- `STAGE2_LEMONFOX_ENABLE_TIMESTAMPS`
- `STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB`
- `STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB`
- `STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES`
- `STAGE2_STT_OUTPUT_PROFILE`
- `STAGE2_STT_FALLBACK_OUTPUT_PROFILE`
- `STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB`
- `STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES`
- `STAGE2_STT_MAX_PREPARED_AUDIO_MB`
- `STAGE2_STT_DIRECT_UPLOAD_WARNING_MB`
- `STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE`
- `STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES`
- `STAGE2_STT_STORAGE_MODE`
- `STAGE2_STT_REQUIRE_STORAGE_HEALTH`
- `STAGE2_STT_AUDIO_BUCKET`
- `STAGE2_STT_AUDIO_PREFIX`
- `STAGE2_STT_STORE_PREPARED_AUDIO`
- `STAGE2_STT_STORE_SOURCE_MEDIA`
- `STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS`
- `STAGE2_STT_TRANSCRIPT_RETENTION_DAYS`
- `STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED`
- `STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL`
- `STAGE2_STT_PROVIDER_CANCEL_SUPPORT`

Invalid enum and invalid numeric values fail fast. Missing Lemonfox key does not
break the non-live capabilities endpoint. Live provider calls require a key.

## 5. Provider adapter implemented

Implemented:

- `SttProviderAdapter` protocol;
- `SttProviderAdapterFactory`;
- `LemonfoxSttAdapter.capabilities()`;
- `LemonfoxSttAdapter.transcribe_bytes()`;
- Lemonfox request form construction;
- Lemonfox verbose JSON normalization to `TranscriptResultV1`;
- Lemonfox error normalization to `ProviderErrorV1`;
- no raw provider response in public contract;
- no API key in capability response.

The adapter supports deterministic stub mode when no Lemonfox key is present and
`live=False`. `live=True` fails with typed `provider_auth_missing` if the key is
absent.

## 6. Runtime capabilities endpoint

Implemented:

```text
GET /stage2-api/transcription/capabilities
```

Route location:

- `services/stage2-stt/stage2_stt/app.py`

Response model:

- `TranscriptionRuntimeCapabilitiesV1`

The response includes provider id, adapter id, output profiles, size limits,
storage mode/availability, timestamps/speaker labels support, cancel strategy
and warnings. It does not include API keys, raw env, bucket name, provider
headers or provider raw responses.

## 7. Storage mode behavior

Implemented in `services/stage2-stt/stage2_stt/storage.py`:

- `auto`: uses persistent prepared-audio storage only when a bucket is configured
  and available; otherwise reports transient lifecycle.
- `s3`: requires configured healthy storage and fails fast if unavailable.
- `none`: disables persistent prepared-audio storage and source-media storage.
- object key generation sanitizes job id and does not include user, provider key
  or sensitive metadata.
- retention metadata is represented on `PreparedAudioMetadataV1`.

Because the repo has no S3 helper, the slice uses a minimal
`StorageHealthProbe` contract and test stub instead of inventing storage
credentials or SDK wiring.

## 8. Output profile behavior

Implemented profiles:

- `opus_webm_compact`
- `opus_ogg_compact`
- `mp3_high_compat`
- `wav_pcm_safe`

Validation checks:

- selected profile is known;
- MIME matches selected profile;
- selected profile is declared by the adapter capability profile;
- prepared-audio size respects the configured limit;
- prepared-audio at/over warning threshold emits
  `provider_direct_upload_limit_warning`;
- prepared-audio over 100 MB defaults to typed fail behavior.

## 9. Cancel behavior

Implemented:

- statuses: `queued`, `preprocessing`, `uploading`, `processing`, `completed`,
  `failed`, `cancel_requested`, `cancelled`;
- reason codes: `cancelled_by_user`, `provider_cancel_supported`,
  `provider_cancel_unsupported`, `provider_cancel_unknown`,
  `cancelled_locally_provider_continues`, `late_provider_result_ignored`;
- provider cancel request path when capability says supported;
- local cancel when provider cancel is unsupported or unknown;
- late provider result cannot turn a cancelled job into completed.

No full queue was added. The job model is domain-level and persistence-compatible
for a later route/worker slice.

## 10. Tests/smoke performed

Commands:

```text
PowerShell: python -m pytest
PowerShell: python -m compileall stage2_stt tests
PowerShell: python -m pip wheel --no-deps . -w dist
PowerShell: import service from built wheel and list capabilities route
PowerShell: TestClient GET /stage2-api/transcription/capabilities
```

Results:

- `15 passed in 0.86s`
- compileall passed;
- wheel built: `openwebui_stage2_stt-0.1.0-py3-none-any.whl`;
- wheel contains only `stage2_stt/*` package files;
- endpoint smoke returned `200` with `lemonfox lemonfox opus_webm_compact auto`;
- no workspace-only import/path-hack matches were found by targeted `rg`.

Test isolation:

- pytest `monkeypatch` sets/restores env per test;
- no real provider key is used;
- external provider network is not called in tests.

Terminal route outcome asserted:

- `GET /stage2-api/transcription/capabilities` returns status `200` and typed
  response body;
- secret-bearing env values are absent from serialized response.

Irreversible boundary:

- no irreversible provider upload/storage action happens in this slice; tests
  assert validation/cancel outcomes before provider handoff.

## 11. Lemonfox live smoke result

Not run.

Reason:

- no approved non-sensitive test audio exists in the repo;
- `.env` was not read or printed;
- provider key must not be exposed in logs, docs, tests or browser-visible
  responses.

Mock/stub and normalization tests were run instead. The live method is present
and requires the key only for `live=True` calls.

## 12. Known limitations

- Sidecar is not wired into `compose/openwebui.compose.yml`.
- OpenWebUI session/current-user propagation is not solved in this repo.
- Job creation/result/cancel HTTP endpoints are not exposed yet.
- No persistent queue or database model was added.
- S3 is represented by a health contract/stub, not by a concrete storage SDK.
- Lemonfox URL upload path is not enabled as an approved corporate data path.
- Lemonfox provider-side cancellation remains unknown.
- Provider max duration remains unknown unless configured.
- No final UI/browser preprocessing implementation is included.

## 13. Deviations from ADR/plan

- ADR-0004 remains `Proposed`; this implementation is a first backend slice, not
  production acceptance.
- Because the repo has no OpenWebUI backend source, implementation uses a new
  isolated sidecar instead of an OpenWebUI route shim.
- Because auth/session propagation is not discoverable from this repo, only the
  non-sensitive capabilities endpoint is exposed. Job routes are deferred.
- Compose/env/scripts were not changed, except the pre-existing `.env.example`
  Stage 2 env block already present in the worktree.

## 14. Next recommended slice

Next slice:

1. Decide and document the production sidecar routing model behind Traefik.
2. Prove OpenWebUI session/user propagation or approved reverse-proxy identity
   handoff.
3. Add authenticated `POST /stage2-api/transcription/jobs` and cancel/result
   routes.
4. Add persistence/queue decision.
5. Run Lemonfox live smoke with approved non-sensitive audio.

## Self-check against documents

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| Isolated backend/domain service | Done | `services/stage2-stt/stage2_stt` |
| Server-side STT config loader | Done | `stage2_stt/config.py`, `test_config.py` |
| Adapter factory | Done | `stage2_stt/provider.py` |
| Lemonfox adapter | Done | `stage2_stt/lemonfox.py`, `test_lemonfox_adapter.py` |
| Provider capability profile | Done | `LemonfoxSttAdapter.capabilities()` |
| Output profile validation | Done | `stage2_stt/output_profiles.py`, `stage2_stt/validation.py` |
| Runtime capabilities endpoint | Done | `GET /stage2-api/transcription/capabilities`, endpoint smoke `200` |
| Storage mode `auto|s3|none` | Done | `stage2_stt/storage.py`, `test_storage_mode_auto_s3_none_branches` |
| Prepared audio 100 MB limit | Done | `test_prepared_audio_over_100_mb_fails_by_default` |
| Provider direct upload limit exceeded | Done | `test_provider_direct_upload_limit_exceeded_when_internal_limit_is_higher` |
| Transcription job model | Done | `TranscriptionJobV1`, `stage2_stt/jobs.py` |
| Cancel state model | Done | `CancelStateV1`, cancel tests |
| Normalized transcript result | Done | `TranscriptResultV1`, Lemonfox normalization test |
| Usage event draft | Done | `UsageEventV1` |
| Secrets not exposed by capabilities | Done | `test_runtime_capabilities_endpoint_does_not_expose_secrets` |
| No browser-to-provider call | Done | no frontend/browser code added |
| No compose/env production change | Done | compose unchanged |
| Live Lemonfox smoke | Not run | no approved non-sensitive audio; no `.env` read |
| Authenticated job route | Deferred | OpenWebUI session propagation not available in repo |
