# STT v2 Gate 1-2 Engineering Docs Design Report

Date: 2026-07-02.

Status: design/materialization report.

Scope: engineering document pool for STT v2 Gate 1-2 implementation handoff.

## 1. Executive Summary

The Gate 1-2 engineering document pool has been materialized.

The package is intentionally narrow:

- Gate 1 proves LemonFox diarization at runtime and normalization into
  `TranscriptResultV1`.
- Gate 2 proves internal artifact storage, `transcript_ref`, structured
  transcript preservation, minimal lineage, retention basics and fail-closed
  access behavior.
- Later STT v2 capabilities remain out of scope: DOCX, OpenWebUI prompt catalog,
  quick actions, auto-run post-processing, chunking and user-facing transcript
  history.

The package is sufficient to hand an autonomous implementation agent a bounded
Gate 1-2 goal, provided the agent uses the acceptance matrix as the proof
closure mechanism.

## 2. Documents Created

Goal and scope:

- `docs/stage2/goals/STT_V2_GATE_1_2_GOAL.md`

Contracts:

- `docs/stage2/contracts/STT_V2_ARTIFACT_CONTRACTS.md`
- `docs/stage2/contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md`
- `docs/stage2/contracts/STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md`

Runtime/config:

- `docs/stage2/config/STT_V2_GATE_1_2_ENV_CONTRACT.md`

Acceptance:

- `docs/stage2/acceptance/STT_V2_DIARIZATION_PROOF_CONTRACT.md`
- `docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/STT_V2_GATE_1_2_PROOF_REPORT_TEMPLATE.md`

Implementation boundary:

- `docs/stage2/implementation/STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md`

Planning source retained:

- `docs/stage2/context/STT_V2_GATE_1_2_ENGINEERING_DOCS_PLAN.md`

## 3. Sources Used

Local source documents:

- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`
- `docs/stage2/context/STT_V2_GATE_1_2_ENGINEERING_DOCS_PLAN.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`

Local code/source references inspected:

- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`

External sources checked on 2026-07-02:

- LemonFox Speech-to-Text API: https://www.lemonfox.ai/apis/speech-to-text
- Open WebUI API Endpoints: https://docs.openwebui.com/reference/api-endpoints/
- Open WebUI Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- Open WebUI Prompts: https://docs.openwebui.com/features/workspace/prompts/

External-source impact:

- LemonFox documents direct upload as 100 MB and URL input as 1 GB.
- LemonFox documents `speaker_labels=true` and requires `verbose_json` to access
  speaker labels.
- LemonFox documents word timestamps through `timestamp_granularities[]=word`
  with `verbose_json`.
- OpenWebUI API docs confirm authenticated API usage expectations.
- OpenWebUI Functions docs support the extension-first framing but also warn that
  Functions execute server-side Python and should remain trusted/admin-managed.
- OpenWebUI Prompts docs confirm prompt versioning/access-control value, but
  prompt catalog is deliberately deferred beyond Gate 1-2.

## 4. Design Decisions

### 4.1. Keep Gate 1-2 Narrow

The document pool avoids implementing the whole STT v2 epic. This matters
because artifact storage and diarization proof are already enough risk for one
implementation slice.

Deferred:

- DOCX;
- prompt catalog;
- quick actions;
- post-processing execution;
- chunking;
- transcript history UI;
- OpenWebUI core patch.

### 4.2. Use Goal + Contracts + Matrix

The handoff structure is:

```text
Goal
-> artifact/runtime/compatibility contracts
-> acceptance matrix
-> implementation goal
-> proof report
```

This keeps implementation autonomy high while making proof obligations explicit.

### 4.3. Treat ArtifactStore As Internal

The storage contract explicitly says ArtifactStore is internal technical storage,
not a user-facing archive. This prevents scope drift into a Meetings app or
transcript portal.

### 4.4. Keep ArtifactScopeV1 Non-authoritative

`ArtifactScopeV1` is context metadata only. It is not an ACL, ownership proof,
security boundary or tenant model. Access must still be validated through
available OpenWebUI user/session/chat/file context and sidecar checks.

### 4.5. Keep Lineage Minimal

`ArtifactChainV1` is lineage-only. It does not orchestrate execution, replace job
state, replace access checks or become a workflow engine.

### 4.6. Make Provider Payload Safety Testable

The document pool requires proof that product flow works without diagnostic raw
provider payload and that raw LemonFox JSON does not appear in chat, Action,
loader, ordinary logs or product artifact rows.

## 5. Document-by-document Analysis

### 5.1. Goal Document

The goal document is the implementation agent's top-level contract. It defines
Gate 1 and Gate 2, allowed areas, forbidden areas and Done/Not Done criteria.

Important choice:

- `transcript_ref` and artifact storage are required for Gate 2;
- prompt catalog and DOCX are named non-goals;
- Action changes are allowed only narrowly and must preserve flat transcript
  output.

### 5.2. Artifact Contracts

The artifact contract document includes only Gate 1-2 contracts. This prevents
the implementation agent from building prompt execution and export contracts too
early.

Key contract choices:

- `TranscriptResultV1` remains canonical.
- `internal_provider_response_ref` is optional diagnostic-only.
- `ArtifactScopeV1` excludes transcript/result refs.
- `ArtifactRefV1` is opaque and unguessable.
- `ArtifactChainV1` contains minimal edges only.
- `TranscriptProjectionV1` is optional and only for speaker-labeled proof.

### 5.3. Storage / Retention Contract

This document makes SQLite/volume MVP storage testable.

Key acceptance points:

- transcript index;
- artifact records;
- artifact edges;
- opaque refs;
- expiry behavior;
- no browser access to SQLite/volume;
- no ordinary payload logs;
- refs/metadata-first media policy.

### 5.4. Diarization Proof Contract

This is the Gate 1 proof spec.

It converts provider documentation into concrete acceptance:

- enable speaker labels;
- request verbose JSON;
- use synthetic two-speaker audio;
- normalize segment and word speakers;
- prove no raw provider leak.

### 5.5. Runtime / Env Contract

This document separates config expectations from code. It proposes env variable
names and safe defaults, but the implementation still owns final wiring.

Important point:

- missing artifact store config must not silently fall back to memory for Gate 2
  Done.

### 5.6. Backward Compatibility Contract

This contract protects the current user path.

It requires:

- flat `Transcript:` output compatibility;
- normal chat remains usable;
- artifact-store failures fail closed;
- OpenWebUI core remains unpatched.

### 5.7. Acceptance Matrix

The matrix is the primary proof object.

It covers:

- Gate 1 diarization rows;
- Gate 2 artifact-store rows;
- backward compatibility rows;
- no-leak rows;
- scope review rows.

The matrix prevents narrative-only completion claims.

### 5.8. Implementation Boundary

The boundary doc gives allowed and forbidden code areas. It is intentionally
not a low-level implementation plan.

The goal is to stop drift into:

- DOCX;
- prompt catalog;
- quick actions;
- post-processing;
- OpenWebUI core patch.

### 5.9. Proof Report Template

The template makes the future final report predictable. It requires commands,
config, test outputs, synthetic audio proof, artifact-store proof and final
verdict.

## 6. Missing Information Captured As Open Questions

The following remain open for implementation proof, not for architecture:

1. Which exact OpenWebUI user/chat/file identifiers are available to Action,
   loader and sidecar in the target runtime?
2. Which final artifact-store env variable names should be used in code?
3. What exact synthetic two-speaker fixture will be used in CI/runtime proof?
4. Which runtime command proves SQLite/volume is not browser-accessible?
5. Which log sources are authoritative for no raw provider leak proof?
6. Whether sidecar restart durability must be proven in Gate 2 or explicitly
   accepted as a controlled limitation for the first implementation pass.

These questions do not require expanding the Gate 1-2 scope.

## 7. Risk Analysis

### Risk: overbuilding artifact infrastructure

Mitigation:

- contracts are tiered;
- Gate 1-2 excludes prompt execution and DOCX;
- `ArtifactChainV1` is lineage-only.

### Risk: treating scope as authorization

Mitigation:

- `ArtifactScopeV1` is explicitly not ACL/ownership/security;
- access fail-closed behavior is required in acceptance matrix.

### Risk: fake diarization proof

Mitigation:

- runtime flag alone is insufficient;
- synthetic two-speaker proof is required;
- normalized speaker fields must be inspected.

### Risk: provider payload leakage

Mitigation:

- raw payload is not product artifact;
- diagnostic raw payload disabled;
- no-leak checks are required across chat/action/loader/logs/storage.

### Risk: breaking existing STT

Mitigation:

- backward compatibility contract;
- flat transcript output rows in matrix;
- artifact-store failure must not corrupt chat.

## 8. Verification Performed For This Documentation Task

Performed:

- read current refined STT v2 blueprint;
- read engineering docs plan;
- searched local docs and code for current STT contracts and runtime shape;
- checked external LemonFox and OpenWebUI documentation;
- created the Gate 1-2 document pool;
- kept all outputs in `docs/stage2/*` or `docs/reports/2026-07-02/`;
- did not change code/runtime/config/tests/OpenWebUI Action/loader.

Expected local verification:

```text
git diff --check -- <created-docs>
rg -n "DOCX|quick actions|post-processing|OpenWebUI core patch" <created-docs>
```

## 9. Final Verdict

The engineering document pool is ready to support an autonomous Gate 1-2
implementation goal.

Ready because:

- scope is bounded;
- contracts are separated from future STT v2 work;
- provider diarization proof is explicit;
- artifact store is internal and testable;
- backward compatibility is protected;
- acceptance matrix and proof template exist.

Not yet an implementation package because:

- code has not been changed;
- runtime config has not been changed;
- synthetic audio proof has not been executed;
- acceptance matrix rows are not yet closed.

Recommended next step:

Create an implementation goal for Gate 1-2 that instructs the agent to read the
new goal, contracts, boundary, env contract and acceptance matrix before making
code changes.
