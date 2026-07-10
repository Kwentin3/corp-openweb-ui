# Broker Reports Gate 1: passport-based eligibility v2 and Gate 2 handoff

Date: 2026-07-09

Scope: final Gate 1 / Gate 1.5 chain from validated `document_metadata_passport_v0` to source eligibility v2, deterministic Gate 2 handoff, and compact Russian chat report.

Out of scope and not run: Gate 2 source-fact extraction, operations/dividends/cashflow extraction, tax calculation, declaration generation, XLS/XLSX generation, OCR/VLM, ordinary upload, Knowledge/RAG ingestion.

## Result

The generic post-passport blocker was removed from the current decision chain.

`case_group_002` now reaches a specific Gate 2 handoff state:

- `document_metadata_passport_v0`: `16/16` valid.
- structured output: `openwebui_response_format_json_schema=16`.
- source eligibility version: `passport_based_source_eligibility_v2`.
- final handoff status: `blocked`.
- final handoff mode: `gate2_blocked_requires_metadata_review`.
- accepted for Gate 2: `0`.
- accepted as source candidate for Gate 2: `0`.
- metadata review required: `12`.
- duplicate canonical choice required: `1`.
- methodology/output artifact: `2`.
- outside case scope: `1`.
- source policy review required: `0`.
- OCR required before Gate 2: `0`.
- unsupported format: `0`.

The pipeline is not ready for `case_group_002` Gate 2 source-fact proof yet. It is blocked for specific, evidence-backed Gate 1.5 reasons instead of the old generic `gate2_blocked_requires_review`.

## Root Cause

The previous blocked state after valid passports had two causes:

1. Passport validation proved schema, safety, evidence-ref integrity and managed Prompt execution, but it did not mean each document had enough source metadata to enter Gate 2.
2. The old eligibility/handoff path still collapsed review states into stale generic buckets, so valid passports could end as `gate2_blocked_requires_review` instead of a specific metadata, policy, duplicate, OCR or no-eligible-source mode.

The latest live run shows the concrete `case_group_002` blocker: the passports are valid, but source eligibility v2 found no eligible source document because `12` documents require metadata review, `1` duplicate requires canonical choice, and `3` documents are terminal exclusions.

## Refactor

Changed code paths:

- `services/broker-reports-gate1-proof/broker_reports_gate1/eligibility.py`
  - introduced `passport_based_source_eligibility_v2`;
  - added accepted/review/excluded decision statuses;
  - consumes validated passport role hypotheses, confidence, missing metadata, conflict flags, evidence refs and blocker state;
  - computes safe aggregate counts and handoff blocker counts.
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_handoff.py`
  - persists eligibility v2 decision counts, blocker counts and accepted source-candidate refs in the safe handoff metadata.
- `services/broker-reports-gate1-proof/broker_reports_gate1/document_passport.py`
  - keeps strict validator semantics;
  - records validator-guided repair count for the narrow safe case where the LLM omits declaration of missing critical metadata;
  - this repair does not accept a document for Gate 2, it only turns the issue into explicit `metadata_review_required`.
- `services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py`, `safe_report.py`, `taxonomy.py`, `compact_report.py`
  - replaced generic review fallback with specific handoff modes and Russian compact-report counts.
- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`
  - kept OpenWebUI managed Prompt architecture and schema-first structured output.
- Contracts updated:
  - `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`
  - `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md`

Legacy status names remain allowed for older artifacts, but the current v2 runtime path no longer emits generic `gate2_blocked_requires_review` when a more precise passport-derived reason exists.

## Eligibility Rules

Eligibility v2 now uses passport data as follows:

- source role hypothesis plus sufficient confidence can promote a document to `accepted_for_gate2` or `accepted_as_source_candidate_for_gate2`;
- missing critical metadata blocks as `metadata_review_required`;
- source policy ambiguity blocks as `source_policy_review_required`;
- duplicate content blocks as `duplicate_needs_canonical_choice`;
- methodology/templates/output artifacts are terminally excluded from Gate 2 source fact extraction;
- outside-scope documents are terminally excluded;
- OCR-only inputs remain `requires_ocr_before_gate2`;
- unsupported containers remain `unsupported_format` or terminal exclusions.

Gate 2 handoff is computed from eligibility v2 decisions:

- all included documents valid: `full_package_ready_for_gate2`;
- accepted reduced subset valid: `reduced_subset_ready_for_gate2`;
- otherwise specific blocked modes are selected in this order: OCR, metadata, policy, duplicate, no eligible sources;
- secondary blockers remain visible in `handoff_blocker_counts`.

## Proof

Local verification:

```text
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_document_passport services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_stub services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_passport_eligibility_v2 -v
Result: 27 tests OK

python -m compileall -q services\broker-reports-gate1-proof
Result: passed

python -m unittest discover -s services\broker-reports-gate1-proof\tests -v
Result: 70 tests OK

python services\broker-reports-gate1-proof\scripts\build_openwebui_pipe_bundle.py
Result: bundled pipe rebuilt

python -m py_compile services\broker-reports-gate1-proof\openwebui_actions\broker_reports_gate1_pipe_bundled.py
Result: passed

python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_bundle -v
Result: 1 test OK
```

Live deployment:

```text
Function id: broker_reports_gate1_pipe
Function SHA-256: 9c39d648259803939fd6e0437b25e58c676a91279045f83358e26d0cb9202b3c
Previous SHA-256: 9b4bba408585c415e8f25c726300fc4293f5aeb2d245be8fa1aeb8c30662bce8
Prompt hash: 7b93fcf0f29402520d7c774da559df3deab26953686cb8cef67fd1b803dc997d
Prompt version: passport-v0-2026-07-08-implementation
OpenWebUI readiness after restart: 404, 404, 404, 404, 404, 404, 404, 200
```

Synthetic process=false proof:

```text
status: passed
passports_total: 2
passport validator: passed
structured output mode: openwebui_response_format_json_schema=2
fallback used: 0
handoff_status: ready_with_safe_refs
handoff_mode: full_package_ready_for_gate2
decision_status_counts: accepted_for_gate2=2
document rows delta: 0
knowledge rows delta: 0
vector delta after upload/chat/delete: 0
source_fact_extraction_performed: false
tax/declaration/xlsx/ocr flags: false
```

`case_group_002` process=false proof:

```text
status: partial
case_id: customer_case_group_002_process_false_gate1_20260709102351
passports_total: 16
passport validator: passed
structured output mode: openwebui_response_format_json_schema=16
fallback used: 0
repair_attempted_count: 2
validator_guided_repair_count: 0
source eligibility v2: passed
gate2_handoff_created: true
gate2_handoff_ready: false
handoff_status: blocked
handoff_mode: gate2_blocked_requires_metadata_review
accepted_for_gate2: 0
accepted_as_source_candidate_for_gate2: 0
metadata_review_required: 12
duplicate_needs_canonical_choice: 1
methodology_or_output_artifact: 2
outside_case_scope: 1
included_in_reduced_subset: 0
reduced_subset_validated: false
uploaded process=false files: 16
cleanup deleted uploads: 16
document rows delta: 0
knowledge rows delta: 0
vector delta after upload/chat/cleanup: 0
openwebui_knowledge_records: 0
```

## ArtifactStore And Safety

Synthetic proof persisted and then purged private payloads:

- `document_metadata_passport_v0`: `2`;
- `document_metadata_passport_validation_v0`: `1`;
- `document_source_eligibility_v0`: `2`;
- `gate2_handoff_v0`: `2`;
- active private payload records after purge: `0`;
- Knowledge rows: `0`;
- vector delta: `0`.

`case_group_002` persisted customer-approved test artifacts without Knowledge backend:

- case record count: `131`;
- `document_metadata_passport_v0`: `16`;
- `document_metadata_passport_validation_v0`: `1`;
- `document_source_eligibility_v0`: `1`;
- `gate2_handoff_v0`: `1`;
- `openwebui_knowledge_records`: `0`;
- document rows delta: `0`;
- vector delta after upload/chat/cleanup: `0`;
- source uploads deleted after proof: `16`.

No raw filenames, OpenWebUI file ids, private paths, source rows, account numbers, personal data, secrets or env values are included in this report.

## Final Statuses

Proven:

- `GATE1_PASSPORT_BASED_ELIGIBILITY_RESEARCH_READY`
- `GATE1_SOURCE_ELIGIBILITY_V2_REFACTORED`
- `GATE1_GATE2_HANDOFF_REFACTORED`
- `GATE1_PASSPORT_BASED_SUMMARY_READY`
- `LIVE_GATE1_PASSPORT_ELIGIBILITY_SYNTHETIC_PASSED`
- `CASE_GROUP_002_PASSPORT_ELIGIBILITY_RERUN_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `CASE_GROUP_002_GATE2_HANDOFF_BLOCKED_WITH_SPECIFIC_REASONS`

Specific blocker counts:

- `metadata_review_required=12`
- `duplicate_needs_canonical_choice=1`
- `excluded_from_gate2=3`
- `source_policy_review_required=0`
- `requires_ocr_before_gate2=0`

Not claimed:

- `READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF`

Next step: metadata review for the `12` blocked source candidates and canonical duplicate choice for the duplicate group. After that, rerun Gate 1.5 handoff; only a ready handoff should be used to start Gate 2 source-fact proof.
