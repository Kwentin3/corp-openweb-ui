# Broker Reports Workflow Goal 5F — Gate 2 Workload Scope Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5f-gate2-workload-scope-v1`

Correction family: native workflow integration and workload authorization scope

Implementation status: PASSED

Live Gate 2 reproof: PENDING AFTER MERGE

## Trigger

The native Gate 2 input was ready and the DCP contained a valid receipt for a completed Gate 1 workload. Both Gate 2 Functions nevertheless authorized that receipt with the DCP artifact's empty workspace scope rather than the stable Function-owned Gate 1 workload scope. WorkloadAuthority correctly returned `workload_access_denied` before any Gate 2 job or provider call was created.

## Narrow correction

The source-fact and domain Gate 2 adapters now construct a dedicated access context for the owning Gate 1 receipt check:

- authenticated user identity is copied from the already resolved DCP context;
- case and chat identities are copied unchanged;
- workspace scope is fixed to the existing Gate 1 workload identity `broker_reports_gate1_pipe`;
- the receipt job must still be in terminal `completed` state.

The DCP-derived artifact context remains unchanged and continues to control ArtifactStore access. The DCP-derived workload context remains the owner of each newly created Gate 2 job. Only the cross-stage Gate 1 receipt lookup uses the owning Gate 1 scope.

## Security and failure semantics

The correction does not weaken user, case or chat authorization. Tests prove that an empty DCP workspace can authorize the completed owning Gate 1 receipt, a pending Gate 1 job is still rejected, a missing receipt is still rejected, and a different authenticated user is rejected with `workload_access_denied`.

## Preserved boundaries

- WorkloadAuthority remains the only workload state and authorization owner;
- ArtifactStore scope and DCP schema are unchanged;
- Gate 1 and Gate 2 workload ownership remain distinct;
- semantic JSON and the Gemini prompt are unchanged;
- model/provider selection, private intake and crop processing are unchanged;
- no Knowledge, RAG, embeddings, vectorization or local OCR was added.

## Verification

Terminal local results:

- focused WorkloadAuthority and both Gate 2 bundle regressions: 51 passed;
- extended Gate 2 affected regression: 119 passed;
- Ruff: passed;
- compile check: passed;
- `git diff --check`: passed;
- boundary-aware scan of sealed private source labels and formatted values: zero findings.

Source and bundle SHA-256 identities:

- unchanged Gate 1 bundle: `ff1edd2fafa28476c2688080fea731a2a512e1bb3f04a7c51cefe5d41b789a3c`;
- Gate 2 source Function source: `c9afca415a924ed52ca00559c8b6c6d8d14b3cb109d7b0593bba16722fc179f6`;
- Gate 2 source bundle: `ed669ce586905b4c8f55b16c3311c00889263b36c0ad7d5bb876c2f9c400273c`;
- Gate 2 domain Function source: `e5a0e684c80fd53a95288969bc444ab10eafc3db9a6d1264d56b0d6f547b219a`;
- Gate 2 domain bundle: `2f6cbab2e1f832dcb9de7eb09f1041a7a8aaa26bdd8910d9be3fde06d4b7981e`.

## Acceptance disposition

- OWNING_GATE1_SCOPE: EXPLICIT
- DCP_EMPTY_WORKSPACE_COMPATIBILITY: PASSED
- PENDING_GATE1_WORKLOAD: REJECTED
- MISSING_GATE1_RECEIPT: REJECTED
- CROSS_USER_ACCESS: REJECTED
- GATE2_ARTIFACT_SCOPE: UNCHANGED
- GATE2_WORKLOAD_SCOPE: UNCHANGED
- SEMANTIC CONTRACT OR VLM PROMPT CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5F implementation is complete. Goal 2 remains pending for a fresh native Gate 2 and answer-chat reproof after merge and atomic release.
