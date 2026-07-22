# Broker Reports Workflow Goal 2: Native User Workflow

Date: 2026-07-22  
Status: `NOT_CLOSED`  
Audit revision: `a68ac222ec77b034990625a6e275ce1648f7be51`

## Objective

Exercise the selected broker-report PDF through the deployed server-authoritative private intake, deployed Action, native OpenWebUI chat/task lifecycle, live Gate 1 and shared WorkloadAuthority before proceeding to Gate 2 and the answer model.

The source was selected only by its sealed SHA-256. Customer filenames, labels and values were not placed in Git or diagnostic output.

## Measured live evidence

The native path successfully proved the following:

- `POST /api/v1/broker-reports/intake` accepted the selected PDF with `process=false` and all native processing, Knowledge, RAG, embedding and vectorization permissions false;
- the deployed `broker_reports_private_intake_action` returned `receipt_verified` for exactly one source;
- `/api/chat/completions` created one server-owned chat and one asynchronous OpenWebUI task;
- task polling observed an active task and then a terminal empty task set;
- the user-visible Gate 1 completion text was persisted in native chat history;
- WorkloadAuthority persisted queued, active processing phases and completed terminal states;
- both intake and Gate 1 produced zero Knowledge/RAG/vector deltas.

However, one native chat task invoked Gate 1 twice. In each of two controlled trials, including a repeat with explicit empty background-task configuration, the measured result was:

- native OpenWebUI task count: `1`;
- Gate 1 WorkloadAuthority jobs: `2`;
- completed Gate 1 jobs: `2`;
- full Gate 1 artifact sets: `2`;
- domain context packets: `2`;
- ArtifactStore record delta: `40` (`20` per duplicated run);
- normalization run identities: `1` deterministic identity shared by the duplicate executions;
- Knowledge rows delta: `0`;
- document rows delta: `0`;
- vector collection, directory, file and byte deltas: `0`.

Both jobs followed the same terminal transition chain: `queued -> source_intake -> normalizing -> building_document_memory -> validating -> completed`. The second job began immediately after the first completed. The result persisted even when title/follow-up background tasks were explicitly disabled.

## Failed invariant

One server-attested native user request must produce one Gate 1 workload and one authoritative domain-context packet. The live system instead produced two complete representations for the same chat, message intent, source and deterministic normalization identity.

Selecting either context packet in the audit driver would be an unapproved deduplication guess. Proceeding to Gate 2 or the answer model on that basis would hide a real double-processing and potential double-counting defect.

## Ownership and blocker classification

- Owning component: `broker_reports_gate1_pipe` native invocation/idempotency boundary, coordinated with WorkloadAuthority.
- Blocker type: implementation defect in native workflow integration.
- Narrowest corrective slice: add a fail-closed, server-attested idempotency identity derived from chat/message/model/source scope; atomically reuse the existing terminal Gate 1 result or reject an in-flight duplicate instead of admitting a second workload. Preserve the existing private-intake, semantic visual-table, provider, ArtifactStore and Gate 1/Gate 2 contracts.
- Explicitly out of scope: semantic JSON changes, Gemini prompt changes, model retuning, crop changes, OCR, Knowledge/RAG/vectorization, or selecting one duplicate in the audit harness.

## Terminal classification

`NATIVE_OPENWEBUI_PRIVATE_INTAKE`: `PASSED`  
`WORKLOAD_TERMINAL_STATE`: `COMPLETED_BUT_DUPLICATED`  
`KNOWLEDGE_RAG_VECTOR_USE`: `ZERO`  
`CONTROL_VECTOR_QUESTION`: `NOT_RUN_FAIL_CLOSED`  
`SEMANTIC_TABLE_FOLLOWUP`: `NOT_RUN_FAIL_CLOSED`  
`TECHNICAL_JSON_IN_NORMAL_CHAT`: `ZERO_FOR_GATE1_TERMINAL_MESSAGE`  
`GOAL_2_NATIVE_USER_WORKFLOW`: `NOT_CLOSED`

The corrective work must be performed on a separate Goal 5 native-workflow branch, followed by a fresh Goal 2 reproving run.
