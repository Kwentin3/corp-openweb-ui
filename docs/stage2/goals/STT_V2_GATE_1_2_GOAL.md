# STT v2 Gate 1-2 Goal

Status: implementation-goal contract.

Date: 2026-07-02.

Scope: autonomous implementation goal for STT v2 Gate 1-2 only.

## 1. Goal

Implement and prove the first two STT v2 gates without expanding into the later
post-processing product surface.

Gate 1 proves runtime diarization:

- LemonFox speaker labels are enabled in a test runtime;
- provider request uses `speaker_labels=true` and `response_format=verbose_json`;
- synthetic two-speaker audio returns speaker labels;
- labels are normalized into `TranscriptResultV1`;
- raw provider payload does not leak into product outputs.

Gate 2 preserves structured transcript output:

- `transcript_ref` exists;
- structured `TranscriptResultV1` is durable beyond the current in-memory job
  result path;
- internal artifact store records artifact refs, scope, retention and minimal
  lineage;
- flat transcript output remains backward compatible;
- artifact access fails closed when scope/access cannot be proven.

## 2. Non-goals

Do not implement in Gate 1-2:

- DOCX export;
- prompt catalog;
- quick actions;
- auto-run post-processing;
- prompt execution;
- long transcript chunking;
- CRM/task tracker integration;
- separate Meetings app;
- separate transcript history UI;
- OpenWebUI core patch.

## 3. Source Basis

Use these local documents:

- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`
- `docs/stage2/context/STT_V2_GATE_1_2_ENGINEERING_DOCS_PLAN.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`

External source basis:

- LemonFox STT API: https://www.lemonfox.ai/apis/speech-to-text
- Open WebUI API endpoints: https://docs.openwebui.com/reference/api-endpoints/
- Open WebUI Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- Open WebUI Prompts: https://docs.openwebui.com/features/workspace/prompts/

Source-derived constraints:

- LemonFox direct file upload is limited to 100 MB; URL input is documented as
  up to 1 GB.
- LemonFox speaker labels require `speaker_labels=true` and `verbose_json`.
- OpenWebUI API usage requires authenticated access.
- OpenWebUI Functions are server-side Python extension points; they are not a
  reason to patch OpenWebUI core.
- OpenWebUI Prompts are a later native prompt-catalog surface, not Gate 1-2
  implementation scope.

## 4. Allowed Implementation Areas

Likely allowed paths:

- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/stage2_stt/storage.py`
- new `services/stage2-stt/stage2_stt/artifact_store.py`
- new `services/stage2-stt/stage2_stt/transcript_store.py`
- new or extended focused tests under `services/stage2-stt/tests/`
- narrowly scoped Action bridge change only if required to carry/expose
  `transcript_ref` while preserving flat transcript output.

Any OpenWebUI core change requires a separate ADR and is out of Gate 1-2.

## 5. Forbidden Areas

Do not change for Gate 1-2:

- OpenWebUI core;
- DOCX code or dependencies;
- prompt catalog implementation;
- quick-action UI beyond what is strictly required to prove `transcript_ref`;
- post-processing executor;
- chunking;
- unrelated docs/code/tests;
- public provider URL upload path for files larger than direct provider upload.

## 6. Required Gate 1 Evidence

Gate 1 is Done only when proof shows:

- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true` in test runtime;
- capabilities report speaker-label support;
- LemonFox request includes `speaker_labels=true`;
- LemonFox request uses `response_format=verbose_json`;
- synthetic two-speaker audio is transcribed;
- normalized `TranscriptResultV1.segments[].speaker` is populated when provider
  returns speaker data;
- normalized `TranscriptResultV1.segments[].words[].speaker` is populated when
  provider returns word-level speaker data;
- product output does not contain raw LemonFox JSON;
- ordinary flat transcript output still works.

## 7. Required Gate 2 Evidence

Gate 2 is Done only when proof shows:

- `transcript_ref` exists as an opaque reference to the normalized transcript;
- `TranscriptResultV1` is retrievable by `transcript_ref`;
- artifact record is durable in an approved MVP store;
- `ArtifactScopeV1` carries only available context identifiers;
- missing `tenant_id` is not an error;
- artifact lineage links source file ref, prepared audio ref/metadata, STT job
  and transcript;
- artifact payloads do not appear in ordinary logs;
- SQLite/volume path is not browser-accessible;
- artifact refs are opaque and unguessable;
- expired artifacts are not retrievable;
- access failure returns typed refusal;
- loader-visible refs are not sufficient for access;
- product path works without diagnostic raw provider payload;
- product path works without full rendered prompt snapshot;
- flat `Transcript:` output remains backward compatible.

## 8. Done / Not Done

Done:

- Gate 1 and Gate 2 acceptance matrix rows pass;
- implementation is limited to Gate 1-2;
- tests and proof artifacts are recorded;
- no raw provider payload leak is proven;
- no OpenWebUI core patch was introduced;
- final proof report gives an explicit Ready verdict.

Not Done:

- diarization is only inferred from config without synthetic proof;
- `TranscriptResultV1` is still only transient in the current in-memory job path;
- `transcript_ref` is guessable, missing or not access-checked;
- flat transcript output regresses;
- implementation includes DOCX, prompt catalog, quick actions or post-processing.

## 9. Handoff Checklist

Before coding, the implementation agent must read:

- this goal;
- `STT_V2_ARTIFACT_CONTRACTS.md`;
- `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md`;
- `STT_V2_DIARIZATION_PROOF_CONTRACT.md`;
- `STT_V2_GATE_1_2_ENV_CONTRACT.md`;
- `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md`;
- `STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md`;
- `STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`.
