# Broker Reports Workflow Goal 2 — Native Private Bytes Reproof

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal2-native-bytes-reproof-audit-v1`

Audited source revision: `567f07bbfe20cecc4739a5f5fc917783c1025cd4`

Release identity: `broker-reports-567f07bbfe20`

Status: NOT_CLOSED

## Proven correction

The complete Goal 5C Function set was atomically released from approved `main`. Release and independent readback both passed, including exact Function, Action, loader, image and managed-prompt identities; exact rollback identity; a clean staging area; and a quiescent workload.

The native private-intake, Action and `/api/chat/completions` path then produced exactly one native task, one terminal Gate 1 job, one completed transition, one domain context packet and one 20-artifact Gate 1 set. The idempotency defect is closed. Knowledge, RAG and vector deltas remained zero.

## Newly exposed failure

Gate 1 reached terminal `completed` with a concise chat response but the document itself was classified as unavailable:

- blocker code: `bytes_unavailable`;
- reason code: `upload_file_not_found`;
- table-intake terminal code: `pdf_table_intake_source_bytes_unavailable`;
- rendered pages: 0;
- semantic table candidates: 0;
- Gate 2 handoff: `gate2_blocked_no_eligible_sources`;
- Gate 2 source-ready documents: 0.

The VLM was never reached. This is not a semantic JSON, prompt, model or table-recognition result.

Read-only server evidence localized the mismatch:

- the receipt-owned OpenWebUI file row exists;
- file-row owner equals the authenticated artifact owner;
- receipt source identity equals the file-row identity;
- file-row hash equals the sealed intake receipt hash;
- the persisted storage object exists;
- the persisted object has the private-intake nonce-qualified object-name shape;
- Gate 1's generic guessed path does not exist and is not the persisted path.

The private-intake service intentionally stores a unique nonce-qualified object name, while Gate 1 currently reconstructs only `<file_id>_<filename>` under the generic upload root. The deployed Function does not resolve the authenticated receipt-owned file row and storage provider before falling back to the generic path.

## Failed invariant and ownership

- Failed invariant: `NATIVE_OPENWEBUI_PRIVATE_INTAKE -> GATE1_SOURCE_BYTES_AVAILABLE`.
- Measured evidence: one valid receipt-backed source, one completed workload, zero readable pages/candidates, blocked Gate 2 handoff.
- Owning component: Gate 1 Function source-byte resolver at the private-intake boundary.
- Blocker type: native workflow integration.
- Narrowest corrective slice: for reserved Broker Reports source identities, resolve the persisted file row through the installed OpenWebUI file repository and storage provider using the authenticated server user; revalidate the persisted receipt owner, identity and hash; return exact bytes only after byte-hash verification; fail closed with typed errors. Keep generic uploads on their existing path and do not accept a client-supplied filesystem path.

## Acceptance disposition

- NATIVE_OPENWEBUI_PRIVATE_INTAKE: PASSED
- PRIVATE_INTAKE_ACTION: PASSED
- ONE_NATIVE_TASK_ONE_GATE1_JOB_ONE_DCP: PASSED
- GATE1_SOURCE_BYTES_AVAILABLE: FAILED
- WORKLOAD_TERMINAL_STATE: COMPLETED_WITH_BLOCKING_SOURCE_ERROR
- CONTROL_VECTOR_QUESTION: NOT_EXECUTED
- SEMANTIC_TABLE_FOLLOWUP: NOT_EXECUTED
- ANSWERING_MODEL_RAW_PDF_ACCESS: ZERO
- ANSWERING_MODEL_CROP_ACCESS: ZERO
- KNOWLEDGE_RAG_VECTOR_DELTAS: ZERO
- CUSTOMER LABELS OR VALUES IN GIT: ZERO

This report is audit-only and contains no runtime change. Goal 2 remains NOT_CLOSED pending the separate Goal 5D byte-resolution correction and a fresh end-to-end live proof.
