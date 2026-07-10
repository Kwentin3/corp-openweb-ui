# OpenWebUI Broker Reports Domain Context Packet Handoff Audit

Date: 2026-07-09
Repository: `corp-openweb ui` repository root
Scope: Gate 1 domain context packet, issue-ledger carry-forward, Gate 2/source-fact handoff refs.

## Result

Status: passed for Gate 1 DCP/handoff no-loss invariant.

Gate 1 now treats `domain_context_packet_v0.next_stage_refs` as the canonical source-fact context. `gate2_handoff_v0.included_document_refs` remains a primary/reduced subset only.

No readable/source-ready document is silently lost when moving through:

`document_usage_classification_v0 -> gate1_issue_ledger_v0 -> domain_context_packet_v0 -> gate2_handoff_v0 / source-fact extraction input`

## Code Changes

- `domain_ingestion.py`
  - Adds `next_stage_refs`, `next_stage_ref_summary`, and `document_issue_refs`.
  - Buckets refs into primary, secondary, cross-check, declaration-support, audit, duplicate/non-primary, source-ready-not-primary, and dropped-source-ready.
  - Adds downstream instruction `must_consume_next_stage_refs`.
- `validators.py`
  - Validates every DCP ref is known.
  - Requires DUC source-ready refs to exactly match DCP `source_fact_ready_refs`.
  - Requires every source-ready ref to land in an explicit next-stage bucket.
  - Fails if `dropped_source_ready_refs` is non-empty.
- `gate2_handoff.py`
  - Carries DCP `next_stage_refs`, `next_stage_ref_summary`, `document_issue_refs`.
  - Adds `private_slice_refs_by_next_stage_bucket` for resolver-gated private payload access.
- `safe_report.py` and `compact_report.py`
  - Surface only safe summary counts.
  - Compact Russian report now explains primary source docs, non-primary/source-warning refs, and cross-check/audit refs.

## Contract Updates

Updated contracts:

- `docs/stage2/contracts/BROKER_REPORTS_DOMAIN_CONTEXT_PACKET.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_USAGE_CLASSIFICATION.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_ISSUE_LEDGER.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`

Contract meaning:

- source-ready is not the same as primary/reduced subset;
- reduced subset is not the only next-stage input;
- skipped/unanswered issues remain issue refs, not hidden stop/continue decisions;
- no approval/rejection wording was added to the updated handoff/docs wording.

## Synthetic Proof

Local synthetic unit proof:

- Test: `test_domain_context_packet_classifies_next_stage_refs_without_source_ready_loss`
- Package shape: primary source-ready, secondary source-ready with unresolved issue, duplicate/non-primary source-ready, audit/reference doc.
- Result: validation passed.
- Counts: source-ready 3, primary 1, secondary 1, duplicate/non-primary 1, dropped 0.
- Issue carry-forward: secondary doc issue ref appears in `document_issue_refs` and `unresolved_issue_refs`.
- Compact report contains primary and non-primary/source-warning lines.

ArtifactStore handoff unit proof:

- Test: `test_gate2_handoff_carries_next_stage_refs_for_source_ready_non_primary_docs`
- Result: handoff carries primary and duplicate/non-primary refs plus private slice refs by next-stage bucket.

Live synthetic process=false proof:

- Script: `live_process_false_private_intake_smoke.py --synthetic-fixture-mode blocking_policy --enable-llm-passport`
- Status: `passed`
- Uploads: 3 synthetic files, `process=false`.
- DUC source-ready: 3.
- DCP source-ready: 3.
- Primary source refs: 2.
- Source-ready not primary: 1.
- Dropped source-ready: 0.
- Issue ledger: 2 unresolved issues carried forward.
- Knowledge rows delta: 0.
- Vector delta after upload/chat/delete: 0.
- OpenWebUI upload rows returned to baseline after delete.
- Private payload artifacts purged/tombstoned.

## case_group_002 Proof

Complete process=false rerun:

- Case id: `customer_case_group_002_process_false_gate1_20260709175007`
- Uploads: 16, `process=false`.
- Passports: 16/16 validated.
- DUC documents: 16.
- DUC source-ready: 15.
- DCP source-ready: 15.
- Primary source extraction refs: 12.
- Secondary source extraction refs: 1.
- Duplicate/non-primary refs: 2.
- Source-ready not primary: 3.
- Audit refs: 1.
- Cross-check refs: 16.
- Declaration-support refs: 2.
- Dropped source-ready: 0.
- DCP issue ledger: 91 unresolved issue refs carried forward.
- Handoff carries the same `next_stage_ref_summary`.
- Compact Russian report length: 3580, not JSON, no private refs in chat.
- Knowledge rows delta: 0.
- Vector delta after upload/chat: 0.
- ArtifactStore `openwebui_knowledge_records`: 0.

Recheck against persisted ArtifactStore records:

- Case record count: 138.
- `source_ready_count_reconciled`: true.
- `no_source_ready_doc_loss`: true.
- `primary_refs_match_reduced_subset`: true.
- `issue_ledger_refs_visible`: true.
- `openwebui_knowledge_records`: 0.

Note: a second full rerun after proof-script cleanup hit an external `/api/chat/completions` read timeout at 240 seconds before creating artifacts. It does not invalidate the complete persisted rerun above.

## 14 vs 12 / Current 15 vs 12

The old concern was valid: comparing only `source_fact_ready_total` to `included_in_reduced_subset` is the wrong reconciliation.

The current rerun produced 15 source-ready refs and 12 primary refs. That is intentional and now explicit:

- 12 primary refs are the reduced primary source extraction subset;
- 1 secondary source-ready ref remains available with issue context;
- 2 duplicate/non-primary source-ready refs remain available for issue/canonical handling;
- 0 source-ready refs are dropped.

So the reconciliation is:

`15 source-ready = 12 primary + 3 source-ready-not-primary + 0 dropped`

The previous 14 vs 12 shape would be interpreted the same way:

`14 source-ready = 12 primary + 2 explicit non-primary buckets + 0 dropped`

## Boundaries Preserved

No evidence of:

- OpenWebUI core patch;
- ordinary upload/RAG/Knowledge/vector path;
- source-fact extraction;
- tax calculation;
- declaration generation;
- XLS/XLSX generation;
- OCR/VLM;
- private/raw payload in chat report.

## Final Statuses

```text
GATE1_DOMAIN_CONTEXT_HANDOFF_AUDIT_READY
GATE1_NO_SOURCE_READY_DOC_LOSS_PROVEN
GATE1_NEXT_STAGE_REFS_REFINED
GATE1_DOMAIN_CONTEXT_PACKET_DOCS_UPDATED
GATE1_ISSUE_LEDGER_CARRY_FORWARD_PROVEN
GATE1_DOMAIN_CONTEXT_HANDOFF_SYNTHETIC_PASSED
CASE_GROUP_002_HANDOFF_RECONCILIATION_READY
CASE_GROUP_002_NO_SOURCE_READY_DOC_LOSS_PROVEN
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_CASE_GROUP_002_DOMAIN_SOURCE_FACT_EXTRACTION_WITH_ISSUE_CONTEXT
```

Not claimed:

```text
CASE_GROUP_002_FULL_GATE2_HANDOFF_READY
```

Reason: current live handoff mode is `gate2_blocked_requires_metadata_review`; source-fact extraction is ready with issue context, but full Gate 2 handoff still has actionable metadata issues.
