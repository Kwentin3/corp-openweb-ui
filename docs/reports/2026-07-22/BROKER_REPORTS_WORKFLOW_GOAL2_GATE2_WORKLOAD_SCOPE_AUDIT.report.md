# Broker Reports Workflow Goal 2 — Gate 2 Workload Scope Audit

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal2-gate2-workload-scope-audit-v1`

Audited source revision: `fdd0548b4e4b2bdfd309a3db4d919606cbc1c041`

Release identity: `broker-reports-fdd0548b4e4b`

Status: NOT_CLOSED

## Proven upstream path

The fresh native run after Goal 5E completed through private intake, Action and `/api/chat/completions`. Gate 1 reached `completed_with_review_advisory`, rendered all 12 pages, persisted five accepted semantic tables, produced a full ready Gate 2 handoff with zero handoff blockers, and returned concise normal-chat text that data were available while unsupported scopes required review.

The maintained Gate 2 preflight passed: one source-ready and packageable document, ten full source units, complete reference accounting, no truncation, and zero Knowledge/RAG/vector use.

## Failed invariant

The subsequent native Gate 2 source Function returned its safe blocked response before creating a Gate 2 workload or extraction artifacts.

Read-only factory-backed evidence localized the failure:

- the DCP has the owning Gate 1 workload receipt;
- the owning Gate 1 workload is terminal `completed`;
- the DCP artifact scope has no `workspace_model_id`;
- the owning Gate 1 workload uses the stable Function-owned scope `broker_reports_gate1_pipe` introduced by Goal 5C;
- authorizing the receipt with the DCP-derived workload scope fails with `workload_access_denied`;
- authorizing the same receipt with the stable Gate 1 workload scope succeeds and returns `completed`.

Both deployed Gate 2 Functions currently build one `WorkloadAccessContext` directly from the DCP artifact context and use it both to verify the owning Gate 1 job and to own the new Gate 2 job. The first use is invalid after Gate 1 workload scope canonicalization. The failure occurs before provider selection or model execution.

## Ownership and narrowest corrective slice

- Failed invariant: `DCP_WORKLOAD_RECEIPT -> OWNING_GATE1_COMPLETION_AUTHORIZATION`.
- Measured evidence: valid DCP receipt, completed Gate 1 job, DCP-scope authorization denied, stable Gate 1 scope authorization passed, zero Gate 2 jobs/artifacts.
- Owning component: Gate 2 source-fact and domain Function admission checks.
- Blocker type: native workflow integration and workload authorization scope.
- Narrowest corrective slice: in both Gate 2 Functions, verify the DCP's owning Gate 1 workload using an explicitly constructed stable Gate 1 workload access context. Retain the DCP-derived context for Gate 2 artifact access and Gate 2 workload ownership. Keep authorization bound to the same authenticated user and case/chat identity.

The ArtifactStore scope, DCP schema, WorkloadAuthority, semantic JSON, Gemini prompt, provider selection and private-intake architecture do not need changes.

## Acceptance disposition

- NATIVE_GATE1_TERMINAL_STATE: COMPLETED
- GATE2_INPUT_READINESS: PASSED
- DCP_WORKLOAD_RECEIPT: PRESENT
- OWNING_GATE1_WORKLOAD: COMPLETED
- DCP_DERIVED_WORKLOAD_AUTHORIZATION: FAILED (`workload_access_denied`)
- STABLE_GATE1_WORKLOAD_AUTHORIZATION: PASSED
- GATE2_WORKLOADS_CREATED: ZERO
- GATE2_PROVIDER_CALLS: ZERO
- KNOWLEDGE_RAG_VECTOR_DELTAS: ZERO
- CUSTOMER LABELS OR VALUES IN GIT: ZERO

This report is audit-only and contains no runtime change. Goal 2 remains NOT_CLOSED pending a separate Goal 5F correction and a fresh Gate 2 live proof.
