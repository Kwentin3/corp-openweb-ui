# STT v2 Gate 1-2 Engineering Docs Plan

Status: planning document.

Date: 2026-07-02.

Scope: document pool design for STT v2 Gate 1-2 implementation handoff.

Non-code note: this plan does not implement STT v2 behavior. It defines the
engineering documents that should exist before giving an implementation agent an
autonomous Gate 1-2 goal.

## 1. Purpose

Design the minimum useful engineering documentation pool for STT v2 Gate 1-2.

Gate 1 covers:

- runtime diarization proof;
- LemonFox speaker labels;
- synthetic two-speaker proof;
- normalized speaker labels in `TranscriptResultV1`;
- no raw provider leak.

Gate 2 covers:

- internal artifact store;
- `transcript_ref`;
- structured `TranscriptResultV1` preservation;
- durable artifact record;
- `ArtifactScopeV1`;
- minimal artifact lineage;
- backward-compatible flat transcript output;
- fail-closed access behavior;
- storage and retention basics.

This plan intentionally does not include implementation scope for:

- DOCX;
- full prompt catalog;
- quick actions;
- auto-run post-processing;
- chunking;
- CRM/task tracker integration;
- separate Meetings app;
- separate transcript history UI;
- OpenWebUI core patch.

## 2. Source Documents

The proposed document pool should use these inputs:

- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`

## 3. Recommended Document Pool

### 3.1. Gate Goal Document

Proposed path:

```text
docs/stage2/goals/STT_V2_GATE_1_2_GOAL.md
```

Status: mandatory.

Timing: required before implementation goal.

Purpose:

- main goal contract for the implementation agent;
- defines exact Gate 1-2 scope;
- prevents drift into post-processing, DOCX, prompt catalog and UI work.

Questions closed:

- what must be implemented;
- what must not be implemented;
- which files/modules are likely in scope;
- which evidence is required;
- what counts as Done and Not Done.

Contracts referenced:

- `TranscriptResultV1`;
- `ArtifactScopeV1`;
- `ArtifactRefV1`;
- `ArtifactRecordV1`;
- minimal `ArtifactChainV1`;
- `ArtifactRetentionPolicyV1`;
- `TranscriptStoreAdapter`.

Input documents:

- STT v2 refined blueprint;
- ADR-0004 STT proxy boundary;
- Stage 2 STT backend implementation plan;
- this engineering docs plan.

Consumers:

- implementation agent;
- reviewer;
- deploy/operator reviewer if runtime proof is needed.

Acceptance role:

- top-level source for Done/Not Done;
- points to the contract docs and acceptance matrix.

Recommended sections:

1. Goal.
2. Gate 1 scope.
3. Gate 2 scope.
4. Explicit non-goals.
5. Allowed/likely files.
6. Forbidden areas.
7. Required proof.
8. Done/Not Done criteria.
9. Handoff checklist.

### 3.2. Artifact Contracts Document

Proposed path:

```text
docs/stage2/contracts/STT_V2_ARTIFACT_CONTRACTS.md
```

Status: mandatory.

Timing: required before Gate 2 implementation.

Purpose:

- define only MVP-required Gate 1-2 contracts;
- keep future post-processing/DOCX contracts out of the first slice.

Questions closed:

- what exactly is preserved in `TranscriptResultV1`;
- how `transcript_ref` maps to an artifact ref;
- what `ArtifactScopeV1` means and does not mean;
- how lineage is represented without becoming workflow orchestration.

Contracts contained:

- `TranscriptResultV1` preservation rules;
- `ArtifactScopeV1`;
- `ArtifactRefV1`;
- `ArtifactRecordV1`;
- minimal `ArtifactChainV1`;
- `ArtifactRetentionPolicyV1`;
- `TranscriptProjectionV1` only if needed for speaker-labeled proof;
- `TranscriptStoreAdapter` facade over `ArtifactStoreAdapter`.

Input documents:

- STT v2 refined blueprint;
- ADR-0004;
- existing backend implementation plan.

Consumers:

- implementation agent;
- unit/integration test author;
- reviewer.

Acceptance role:

- source for contract validation tests;
- source for acceptance matrix contract rows.

Recommended sections:

1. Contract tier: Gate 1-2 only.
2. `TranscriptResultV1` preservation.
3. `ArtifactScopeV1`.
4. `ArtifactRefV1`.
5. `ArtifactRecordV1`.
6. Minimal `ArtifactChainV1`.
7. `ArtifactRetentionPolicyV1`.
8. `TranscriptStoreAdapter` facade.
9. Explicit future-only contracts.

### 3.3. Artifact Storage / Retention Contract

Proposed path:

```text
docs/stage2/contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md
```

Status: mandatory.

Timing: required before Gate 2 implementation.

Purpose:

- specify the internal technical artifact store for Gate 2;
- make storage safety testable.

Questions closed:

- SQLite/volume MVP store shape;
- what records and indexes exist;
- what retention defaults are used;
- what happens on expiry and rotation;
- how access failure behaves;
- what must never be browser-accessible or logged.

Contracts contained:

- artifact records table/schema sketch;
- artifact edges table/schema sketch;
- `transcript_index`;
- optional `processed_result_index` as future-ready lookup, not Gate 2 scope;
- retention policy fields;
- source/prepared audio refs-first policy.

Input documents:

- STT v2 refined blueprint;
- artifact contracts document;
- STT env contract.

Consumers:

- implementation agent;
- test author;
- runtime operator/reviewer.

Acceptance role:

- source for storage safety rows in the acceptance matrix.

Recommended sections:

1. Store purpose: internal technical store, not user history.
2. Backend recommendation.
3. Schema sketch.
4. Indexes.
5. Retention defaults.
6. Expiry and rotation.
7. Deletion behavior.
8. Access fail-closed behavior.
9. Opaque refs.
10. No ordinary payload logs.
11. Media refs-first policy.

### 3.4. Diarization Proof Contract

Proposed path:

```text
docs/stage2/acceptance/STT_V2_DIARIZATION_PROOF_CONTRACT.md
```

Status: mandatory.

Timing: required before Gate 1 implementation/proof.

Purpose:

- define exactly how LemonFox speaker-label support is proven at runtime.

Questions closed:

- which flags/parameters must be set;
- what synthetic audio proof is required;
- where normalized speaker labels must appear;
- how to prove no raw provider leak.

Contracts contained:

- diarization runtime flag expectation;
- provider request expectations;
- normalized speaker fields;
- speaker-labeled projection proof if used;
- no-raw-provider-leak proof.

Input documents:

- STT v2 refined blueprint;
- LemonFox provider adapter/capability context from existing STT plan;
- runtime/env contract.

Consumers:

- implementation agent;
- tester;
- reviewer.

Acceptance role:

- source for Gate 1 acceptance rows.

Recommended sections:

1. Objective.
2. Runtime flag.
3. Provider request parameters.
4. Synthetic two-speaker fixture/proof.
5. Expected normalized output.
6. Projection proof.
7. No raw provider leak checks.
8. Failure modes.

### 3.5. Runtime / Env Contract

Proposed path:

```text
docs/stage2/config/STT_V2_GATE_1_2_ENV_CONTRACT.md
```

Status: mandatory.

Timing: required before implementation if new env/config is introduced.

Purpose:

- define safe runtime knobs for Gate 1-2 without changing them in this planning
  task.

Questions closed:

- which env vars control diarization;
- where artifact store lives;
- what retention defaults are expected;
- how config should fail safe;
- diagnostic raw provider payload defaults.

Contracts contained:

- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS`;
- artifact store path variable names to be finalized during implementation;
- retention defaults;
- prepared audio TTL;
- diagnostic raw provider payload disabled by default;
- capability endpoint expectations.

Input documents:

- existing `docs/stage2/config/STT_ENV_CONTRACT.md`;
- STT v2 refined blueprint;
- artifact storage/retention contract.

Consumers:

- implementation agent;
- operator;
- reviewer.

Acceptance role:

- source for config proof rows in the acceptance matrix.

Recommended sections:

1. Config principles.
2. Diarization flag.
3. Artifact store path.
4. SQLite/volume requirements.
5. Retention defaults.
6. Diagnostic mode defaults.
7. Prepared audio TTL.
8. Capability endpoint expectations.
9. Missing config behavior.

### 3.6. Backward Compatibility Contract

Proposed path:

```text
docs/stage2/contracts/STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md
```

Status: mandatory, but can be merged into the Gate Goal Document for a compact
handoff.

Timing: required before implementation goal, either as a standalone doc or as a
goal-doc section.

Purpose:

- make it explicit that Gate 1-2 cannot break the existing STT/chat path.

Questions closed:

- what chat output must remain stable;
- what happens if artifact store is unavailable;
- how normal chat degrades safely;
- why loader-visible refs are not trust boundaries;
- why OpenWebUI core is not patched.

Contracts contained:

- flat transcript output compatibility;
- artifact failure behavior;
- no OpenWebUI core patch;
- safe degradation.

Input documents:

- STT v2 refined blueprint;
- ADR-0004;
- existing Stage 2 STT path docs.

Consumers:

- implementation agent;
- reviewer;
- QA/test author.

Acceptance role:

- source for regression rows in acceptance matrix.

Recommended sections:

1. Compatibility commitments.
2. Flat transcript output.
3. Existing STT flow.
4. Artifact-store failure behavior.
5. Chat availability.
6. Safe degradation.
7. Forbidden regressions.

### 3.7. Acceptance Matrix

Proposed path:

```text
docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md
```

Status: mandatory.

Timing: required before implementation goal.

Purpose:

- turn Gate 1-2 requirements into a testable checklist.

Questions closed:

- what must be proven;
- where evidence belongs;
- which contract document owns each requirement;
- what pass/fail means.

Contracts contained:

- no new domain contracts;
- table rows that reference the contract documents.

Input documents:

- goal document;
- artifact contracts;
- storage/retention contract;
- diarization proof contract;
- runtime/env contract;
- backward compatibility contract.

Consumers:

- implementation agent;
- reviewer;
- final proof report author.

Acceptance role:

- primary verification checklist for Gate 1-2.

Recommended sections:

1. Matrix usage.
2. Gate 1 rows.
3. Gate 2 rows.
4. Regression rows.
5. Storage-safety rows.
6. No-leak rows.
7. Evidence artifact column.
8. Final verdict section.

Required columns:

```text
requirement | expected proof | test/report artifact | pass/fail | notes | linked contract
```

Required example rows:

- capabilities show speaker support;
- synthetic audio returns speaker labels;
- `TranscriptResultV1` retrievable by `transcript_ref`;
- flat transcript output unchanged;
- SQLite path not browser-accessible;
- artifact refs opaque/unguessable;
- expired artifact not retrievable;
- raw provider payload absent from chat/action/loader/logs;
- product path works without diagnostic provider payload.

### 3.8. Implementation Boundary / Files Scope Document

Proposed path:

```text
docs/stage2/implementation/STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md
```

Status: mandatory, but can be merged into the Gate Goal Document if the goal doc
is sufficiently explicit.

Timing: required before implementation goal, either standalone or merged.

Purpose:

- prevent implementation drift into future STT v2 work.

Questions closed:

- likely allowed code paths;
- likely new modules;
- likely tests;
- forbidden areas;
- what is explicitly not Gate 1-2.

Contracts contained:

- no new runtime contracts;
- implementation boundary and file scope rules.

Input documents:

- goal document;
- STT v2 refined blueprint;
- existing STT backend implementation plan.

Consumers:

- implementation agent;
- reviewer.

Acceptance role:

- supports code review and scope validation.

Recommended sections:

1. Allowed likely code paths.
2. Likely new modules.
3. Likely tests.
4. Forbidden areas.
5. No DOCX.
6. No prompt catalog/quick actions/post-processing.
7. No OpenWebUI core patch.
8. Review checklist.

### 3.9. Evidence Report Template

Proposed path:

```text
docs/stage2/reports/STT_V2_GATE_1_2_PROOF_REPORT_TEMPLATE.md
```

Status: optional as a standalone doc, recommended as an appendix in the
Acceptance Matrix.

Timing: before implementation is useful, but can be deferred until proof work
starts.

Purpose:

- standardize the final implementation/proof report.

Questions closed:

- what evidence the implementation agent must return;
- how limitations and open questions are reported;
- what final verdict format is expected.

Contracts contained:

- no domain contracts;
- reporting shape.

Input documents:

- acceptance matrix;
- goal document;
- all Gate 1-2 contracts.

Consumers:

- implementation agent;
- reviewer;
- operator/deploy reviewer.

Acceptance role:

- closes the acceptance matrix after implementation.

Recommended sections:

1. Summary.
2. Changed files.
3. Config used.
4. Test commands.
5. Diarization proof.
6. Artifact-store proof.
7. Backward compatibility proof.
8. No-secrets/no-raw-provider-leak proof.
9. Known limitations.
10. Open questions.
11. Final verdict.

## 4. Recommended Creation Order

1. `STT_V2_GATE_1_2_GOAL.md`
2. `STT_V2_ARTIFACT_CONTRACTS.md`
3. `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md`
4. `STT_V2_DIARIZATION_PROOF_CONTRACT.md`
5. `STT_V2_GATE_1_2_ENV_CONTRACT.md`
6. `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md`, or merge into the goal doc
7. `STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`
8. `STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md`, or merge into the goal doc
9. `STT_V2_GATE_1_2_PROOF_REPORT_TEMPLATE.md`, or add as matrix appendix

## 5. Minimum Mandatory Set Before Implementation Goal

Minimum standalone set:

1. Gate Goal Document.
2. Artifact Contracts Document.
3. Artifact Storage / Retention Contract.
4. Diarization Proof Contract.
5. Runtime / Env Contract.
6. Acceptance Matrix.

Minimum merged set:

1. Gate Goal Document with embedded backward compatibility and implementation
   boundary sections.
2. Artifact Contracts Document.
3. Artifact Storage / Retention Contract.
4. Diarization Proof Contract.
5. Runtime / Env Contract.
6. Acceptance Matrix with embedded evidence report template appendix.

Do not start implementation goal without:

- explicit Gate 1-2 non-goals;
- Gate 1 diarization proof expectations;
- Gate 2 artifact-store and structured transcript contracts;
- storage-safety requirements;
- backward compatibility requirements;
- acceptance matrix.

## 6. Documents That Can Be Deferred

Can be deferred as standalone documents:

- Evidence Report Template, if embedded in the acceptance matrix.
- Implementation Boundary, if embedded in the goal document.
- Backward Compatibility Contract, if embedded in the goal document.

Should not be created for Gate 1-2:

- DOCX export contract;
- prompt catalog contract;
- quick action UX contract;
- post-processing execution contract;
- chunking contract;
- CRM/task tracker integration contract;
- transcript history UI contract.

## 7. Recommended Merges To Avoid Bureaucracy

Recommended compact packet:

- Keep `STT_V2_GATE_1_2_GOAL.md` standalone.
- Keep `STT_V2_ARTIFACT_CONTRACTS.md` standalone.
- Keep `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` standalone.
- Keep `STT_V2_DIARIZATION_PROOF_CONTRACT.md` standalone.
- Keep `STT_V2_GATE_1_2_ENV_CONTRACT.md` standalone if env/config changes are
  expected.
- Merge backward compatibility and implementation boundary into the goal doc.
- Merge evidence report template into the acceptance matrix as an appendix.

Reasoning:

- artifact contracts and storage/retention are different ownership surfaces;
- diarization proof is operational enough to deserve a separate acceptance doc;
- goal/boundary/backward compatibility can be one agent-facing contract;
- proof report template can live next to the matrix to reduce document count.

## 8. Relationship Map

```text
STT v2 refined blueprint
  -> Gate Goal Document
       -> Implementation Boundary section/doc
       -> Backward Compatibility section/doc
       -> Artifact Contracts
       -> Artifact Storage / Retention Contract
       -> Diarization Proof Contract
       -> Runtime / Env Contract
            -> Acceptance Matrix
                 -> Implementation Goal
                      -> Evidence Report
                           -> Acceptance Matrix closure
```

Document dependency rules:

- Goal references contracts.
- Contracts feed the acceptance matrix.
- Acceptance matrix feeds the implementation goal.
- Proof report closes the acceptance matrix.
- No Gate 1-2 document should require DOCX, quick actions, prompt catalog,
  post-processing execution or chunking.

## 9. Open Questions Before Implementation Goal

These should be answered in the document pool, not during code review:

1. Which exact OpenWebUI user/chat/file identifiers are available to Action,
   loader and sidecar in the target runtime?
2. What artifact store path/env variable names will be accepted for Gate 2?
3. What retention defaults are acceptable for transcript artifacts and prepared
   audio refs?
4. How will synthetic two-speaker audio be generated or provided for proof?
5. Which command/test artifact proves no raw provider payload appears in
   chat/action/loader/logs?
6. Which proof is sufficient that SQLite/volume is not browser-accessible?
7. Which exact flat transcript output shape must remain backwards compatible?

None of these open questions require expanding Gate 1-2 scope.

## 10. Final Verdict

This document pool is sufficient to prepare an autonomous implementation goal
for STT v2 Gate 1-2 if the minimum mandatory set is created first.

The recommended packet should stay narrow:

- Gate 1: prove runtime speaker labels and normalized diarization.
- Gate 2: preserve structured transcript through an internal artifact store and
  `transcript_ref`.
- Keep user-facing durable context in OpenWebUI chat.
- Keep ArtifactStore internal and technical.
- Keep `ArtifactScopeV1` as context metadata, not ACL, tenant model or ownership
  proof.
- Keep `ArtifactChainV1` lineage-only, not workflow engine.
- Defer DOCX, prompt catalog, quick actions, post-processing execution and
  chunking.
