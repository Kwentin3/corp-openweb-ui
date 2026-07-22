# Broker Reports Workflow Goal 5E — Handoff-Aware Completion

Date: 2026-07-22

Branch: `codex/broker-reports-goal5e-handoff-aware-completion-v1`

Correction family: native workflow completion and user-visible status

Implementation status: PASSED

Live native-workflow reproof: PENDING AFTER MERGE

## Trigger

The post-Goal 5D native run rendered all pages, invoked the live Gemini semantic runtime, accepted five semantic tables and persisted a fully ready Gate 2 handoff with zero handoff blockers. One additional visual candidate was review-required or unsupported. Gate 1 treated that candidate advisory as a global blocker, ended the shared workload in `awaiting_review`, and told the user that the processed data could not yet be used for questions.

## Narrow correction

Gate 1 now finalizes review-bearing work against the final persisted handoff status:

- `ready_with_safe_refs` and `ready_with_reduced_subset` complete with terminal code `completed_with_review_advisory`;
- the review count, handoff status and advisory-preservation flag remain in safe terminal metadata;
- a blocked or unknown handoff with review items remains `awaiting_review`;
- a run without review items retains the existing ordinary completion path.

The repeated native Function call now maps `completed_with_review_advisory` to concise user text stating both that processing completed and data are available for questions, while noting that unsupported scopes still require review. Internal JSON, artifact IDs and workload IDs are not exposed.

## Preserved boundaries

- WorkloadAuthority remains the sole state-transition owner;
- completion still occurs only through `WorkloadSession.complete()`;
- blocking handoffs still fail closed in `awaiting_review`;
- semantic JSON and the Gemini prompt are unchanged;
- model/provider selection, crop extraction and private intake are unchanged;
- ArtifactStore and Gate 2 ownership are unchanged;
- no Knowledge, RAG, embeddings, vectorization or local OCR was added.

## Verification

Focused state-machine tests prove ready-handoff completion with preserved advisory metadata, blocked-handoff review waiting, and correct user-visible reuse wording. The affected regression covers WorkloadAuthority, Gate 1 adapter and bundle, semantic migration, private-intake byte integration, architecture, atomic release and delivery verification.

Terminal local results:

- focused WorkloadAuthority and Gate 1 tests: 23 passed;
- affected regression: 85 passed;
- Ruff: passed;
- compile check: passed;
- `git diff --check`: passed;
- boundary-aware scan of sealed private control literals: zero findings.

Source and bundle SHA-256 identities:

- Gate 1 Function source: `470530bfb1c0d359dca4d61e1969f928b02fa50ddb4424219d17570d8dd7290c`;
- Gate 1 bundle: `ff1edd2fafa28476c2688080fea731a2a512e1bb3f04a7c51cefe5d41b789a3c`;
- unchanged Gate 2 source-fact bundle: `e286c9a8855dfcffff14dbd1d2a28582e7b3dc3258b8e3a1083dfec6f586505d`;
- unchanged Gate 2 domain bundle: `d5f7edc37eb8beebe020fc5b1de07661fe8f4e5b5bcb5348eb1803aab8dd67ef`.

## Acceptance disposition

- GATE2_READY_REVIEW_ADVISORY: COMPLETED
- BLOCKED_HANDOFF_REVIEW: FAIL_CLOSED
- REVIEW_ADVISORY_PRESERVED: PASSED
- DATA_AVAILABLE_MESSAGE_ON_ADVISORY: PASSED
- TECHNICAL_JSON_IN_NORMAL_CHAT: ZERO
- SEMANTIC CONTRACT OR VLM PROMPT CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5E implementation is complete. Goal 2 remains pending for a fresh live private-intake, Gate 1, Gate 2 and answer-chat reproof after merge and atomic release.
