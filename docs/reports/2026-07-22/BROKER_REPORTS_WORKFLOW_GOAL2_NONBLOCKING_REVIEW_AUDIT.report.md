# Broker Reports Workflow Goal 2 — Nonblocking Review Audit

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal2-nonblocking-review-audit-v1`

Audited source revision: `11b69a71f75b8de5870af7c8fe8bea5c2460ddb3`

Release identity: `broker-reports-11b69a71f75b`

Status: NOT_CLOSED

## Proven live path

The native private-intake route, deployed Action and `/api/chat/completions` path produced one native task, one Gate 1 workload and one domain context packet. The private-intake byte correction worked: all 12 pages were rendered, the live Gemini runtime completed eight provider calls, and the table-intake run completed without failed pages.

The run produced six visual-table candidates. Five passed the accepted semantic profile and became five validated semantic envelopes plus five validated normalized table projections. One candidate was classified as review-required or unsupported. All 64 artifacts validated, and Knowledge, RAG and vectorization remained unused.

Gate 1 nevertheless produced a valid full Gate 2 handoff:

- handoff status: `ready_with_safe_refs`;
- handoff mode: `full_package_ready_for_gate2`;
- source-fact extraction readiness: `ready`;
- source-ready documents: 1;
- dropped source-ready documents: 0;
- handoff blockers: 0.

## Failed invariant

The shared workload ended in `awaiting_review`, and the normal chat terminal message said that processing required review before the data could be used for questions. The chat task itself was terminal and error-free, but it did not say that usable data were available.

That result conflicts with the persisted package. The one unsupported visual candidate is advisory at the candidate scope: it did not invalidate the five accepted semantic tables, the document, or the full Gate 2 handoff. Treating any candidate-level review item as a global workload blocker prevents the accepted native workflow from reaching the required `COMPLETED` state and misstates data availability to the user.

The owning code computes one undifferentiated review count from candidate decisions and semantic migration dispositions, then always calls `WorkloadSession.await_review()` whenever that count is nonzero. It does not consider the final handoff status or source-fact readiness.

## Ownership and narrowest corrective slice

- Failed invariant: `GATE2_READY_NONBLOCKING_REVIEW -> WORKLOAD_COMPLETED_WITH_ADVISORY`.
- Measured evidence: 5 accepted semantic tables, 1 review-required candidate, 0 handoff blockers, 1 ready source, workload `awaiting_review`.
- Owning component: Gate 1 Function workload-publication policy and reused-workload chat wording.
- Blocker type: native workflow completion and user-visible status semantics.
- Narrowest corrective slice: distinguish a blocking review from a nonblocking candidate advisory by using the persisted final handoff readiness. Complete a Gate 1 workload when the handoff is ready, preserving the advisory count in safe terminal metadata and concise chat text. Continue to use `awaiting_review` when the final handoff is not usable.

The WorkloadAuthority state machine, semantic JSON contract, Gemini prompt, model choice, private-intake architecture, ArtifactStore and Gate 2 ownership do not need changes.

## Acceptance disposition

- NATIVE_OPENWEBUI_PRIVATE_INTAKE: PASSED
- PRIVATE_SOURCE_BYTES_AVAILABLE: PASSED
- LIVE_GEMINI_SEMANTIC_RUNTIME: PASSED
- SEMANTIC_TABLES_ACCEPTED_FOR_GATE2: 5
- GATE2_HANDOFF: READY
- GATE2_HANDOFF_BLOCKERS: ZERO
- WORKLOAD_TERMINAL_STATE: FAILED (`awaiting_review`)
- TERMINAL_STATUS_ACCURACY: FAILED
- TECHNICAL_JSON_IN_NORMAL_CHAT: ZERO
- KNOWLEDGE_RAG_VECTOR_DELTAS: ZERO
- CUSTOMER LABELS OR VALUES IN GIT: ZERO

This report is audit-only and contains no runtime change. Goal 2 remains NOT_CLOSED pending a separate Goal 5E correction and a fresh native live proof.
