# OpenWebUI Broker Reports Gate 1 Domain Ingestion And Issue Ledger Refactor Report

Date: 2026-07-09

Status: passed.

## Proven Statuses

- `GATE1_DOMAIN_INGESTION_RESEARCH_READY`
- `GATE1_ISSUE_LEDGER_CONTRACT_READY`
- `GATE1_DOCUMENT_USAGE_CLASSIFICATION_CONTRACT_READY`
- `GATE1_DOMAIN_CONTEXT_PACKET_CONTRACT_READY`
- `GATE1_APPROVAL_SEMANTICS_REMOVED_FROM_INGESTION`
- `GATE1_UNRESOLVED_ISSUES_CARRIED_FORWARD`
- `GATE1_DOMAIN_CONTEXT_PACKET_READY`
- `GATE1_DOMAIN_INGESTION_SYNTHETIC_PASSED`
- `CASE_GROUP_002_DOMAIN_INGESTION_RERUN_READY`
- `CASE_GROUP_002_DOMAIN_CONTEXT_PACKET_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `READY_FOR_CASE_GROUP_002_DOMAIN_SOURCE_FACT_EXTRACTION_WITH_ISSUE_CONTEXT`

Not claimed: tax calculation, declaration generation, XLS generation, OCR/VLM,
Knowledge/RAG loading, or final consolidation/declaration-support readiness.
Those stages remain downstream work and must carry the issue context.

## Contract Outputs

Added Gate 1 domain-ingestion contracts:

- `docs/stage2/contracts/BROKER_REPORTS_GATE1_ISSUE_LEDGER.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_USAGE_CLASSIFICATION.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOMAIN_CONTEXT_PACKET.v0.md`

Research note:

- `docs/stage2/research/BROKER_REPORTS_GATE1_DOMAIN_INGESTION_REFACTOR_RESEARCH.md`

Compatibility contract updates:

- `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_METADATA_CLARIFICATION.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`

## Implementation Anchors

- `services/broker-reports-gate1-proof/broker_reports_gate1/domain_ingestion.py`
  builds:
  - `gate1_issue_ledger_v0`;
  - `document_usage_classification_v0`;
  - `domain_context_packet_v0`.
- `services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py`,
  `document_passport.py`, and `clarification.py` apply domain-ingestion
  artifacts before validation and safe report rendering.
- `services/broker-reports-gate1-proof/broker_reports_gate1/taxonomy.py` and
  `eligibility.py` no longer treat PDF/HTML source-role uncertainty as a
  Gate 1 ingestion approval blocker. That uncertainty is carried as
  `source_role_policy_uncertainty`.
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_handoff.py`
  persists the new safe artifacts and handoff refs.
- `services/broker-reports-gate1-proof/broker_reports_gate1/compact_report.py`
  renders domain ingestion and issue context in compact Russian wording, not
  approval-centric wording.

## Runtime Deployment

OpenWebUI Function updated:

- function id: `broker_reports_gate1_pipe`
- final live content sha256: `cc0c2105cfb5164bf63b59e98c067e6aeeb83212c33aefc8d55e347b41067648`
- contains document passport code: true
- contains metadata clarification code: true

Managed prompts remained valid:

- passport prompt hash: `7b93fcf0f29402520d7c774da559df3deab26953686cb8cef67fd1b803dc997d`
- clarification prompt hash: `f16e07393070cb697fe76f1da2af2d800234b2cd0246669e290e90a0185757ac`

## Synthetic Live Proof

Command:

```powershell
python "services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py" --enable-llm-passport --enable-clarification --clarification-synthetic-answers --synthetic-fixture-mode clarification_gap --timeout 240
```

Result: `status=passed`.

Key evidence:

- process=false upload count: 1
- file content endpoint payload count: 0
- document rows delta after chat: 0
- knowledge rows delta after chat: 0
- vector collections/files/bytes delta after chat: 0
- passport validation: 1/1 passed
- clarification request: 2 questions
- clarification resolutions: 2 usable `missing_period` resolutions
- issue ledger: 4 issues, 3 unresolved, 2 skipped unresolved, 1 awaiting answer
- domain context packet: `completed_with_unresolved_issues`
- source fact extraction readiness: `ready`
- document usage classification: 1 document, 1 source-ready, 0 source-blocked
- compact Russian report: true, length 2234, no JSON fence
- private slices not in chat: true
- upload deleted after smoke: true

Synthetic statuses included:

- `GATE1_UNRESOLVED_ISSUES_CARRIED_FORWARD`
- `GATE1_DOMAIN_CONTEXT_PACKET_READY`
- `GATE1_DOMAIN_INGESTION_SYNTHETIC_PASSED`

## Case Group 002 Live Proof

Command:

```powershell
python "services/broker-reports-gate1-proof/scripts/live_case_group_process_false_gate1_run.py" --enable-llm-passport --enable-clarification --timeout 300
```

Result: `status=passed`.

Case:

- case id: `customer_case_group_002_process_false_gate1_20260709164740`
- case group: `case_group_002`
- uploaded package: 16 files
- formats: 2 CSV, 4 HTML text, 8 PDF, 2 XLSX
- upload path: `POST /api/v1/files/?process=false`
- process status values: all `null`
- file content endpoint payload count: 0

No-RAG / no-vector proof:

- document rows delta after chat: 0
- knowledge rows delta after chat: 0
- vector collections delta after chat: 0
- vector files delta after chat: 0
- vector bytes delta after chat: 0
- ArtifactStore knowledge records: 0
- `vector_knowledge_guard.customer_docs_loaded_to_knowledge=false`
- `vector_knowledge_guard.vectorization_performed=false`
- `vector_knowledge_guard.rag_used_for_gate1=false`

Domain ingestion proof:

- document passports: 16/16 validated
- document usage classification: 16 documents
- source fact extraction ready documents: 14
- source fact extraction blocked documents: 0
- issue ledger: 83 issues, 83 unresolved
- skipped unresolved issues: 38
- awaiting-answer unresolved issues: 31
- issue types:
  - `metadata_gap`: 66
  - `source_role_policy_uncertainty`: 12
  - `duplicate_canonical_choice`: 4
  - `outside_scope_confirmation`: 1
- domain context packet: `completed_with_unresolved_issues`
- source fact extraction readiness: `ready_with_issue_context`
- cross-check readiness: `ready`
- consolidation readiness: `blocked`
- declaration support readiness: `ready_with_issue_context`

Approval/source-policy blocker removal proof:

- `source_policy_review_required`: 0
- `source_policy_review`: 0
- handoff mode: `reduced_subset_ready_for_gate2`
- handoff status: `ready_with_reduced_subset`
- reduced subset included documents: 12
- PDF/HTML source-role uncertainty is preserved as issue context, not as a
  Gate 1 approval blocker.

Compact report proof:

- compact Russian report: true
- report length: 3118
- no JSON fence
- does not start with JSON
- private refs not in chat: true

Case statuses included:

- `CASE_GROUP_002_DOMAIN_INGESTION_RERUN_READY`
- `CASE_GROUP_002_DOMAIN_CONTEXT_PACKET_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `READY_FOR_CASE_GROUP_002_DOMAIN_SOURCE_FACT_EXTRACTION_WITH_ISSUE_CONTEXT`

## Local Verification

Commands:

```powershell
python -m compileall "services/broker-reports-gate1-proof/broker_reports_gate1" "services/broker-reports-gate1-proof/scripts"
python -m unittest discover -s "services/broker-reports-gate1-proof/tests" -q
python -m unittest "services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_pipe_bundle.py" -v
python "services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py"
```

Results:

- compileall: passed
- unittest discovery: 90 tests passed
- bundle test: 1 test passed
- bundle rebuild: passed

## Boundary Notes

- Uploaded package remains the input reality: readable documents are ingested,
  normalized, passported, classified, and carried forward.
- Unanswered or skipped questions do not stop ingestion. They remain unresolved
  in `gate1_issue_ledger_v0` and are referenced by `domain_context_packet_v0`.
- Semantic duplicates and unclear source roles do not stop source extraction
  readiness. They can still block consolidation or declaration-support policy.
- No raw private customer data is present in chat-visible output or report.
- No customer document was loaded to Knowledge/RAG/vector storage.
