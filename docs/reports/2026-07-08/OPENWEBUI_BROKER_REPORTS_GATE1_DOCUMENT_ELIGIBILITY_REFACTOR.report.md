# OpenWebUI Broker Reports Gate 1 Document Eligibility Refactor Report

Date: 2026-07-08

## Result

Gate 1 now separates uploaded documents from Gate 2 source documents.
The backend emits `document_source_eligibility_v0`, computes a Gate 2 handoff
mode, persists the eligibility artifact in ArtifactStore, and passes Gate 2
private refs only for documents accepted into the validated subset.

No customer documents were processed in this refactor verification. The proof
used synthetic fixtures only.

## 1. Contract Changes

Added contract doc:

- `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`

Added backend contract constants:

- `document_source_eligibility_v0`
- source eligibility statuses:
  `accepted_for_gate2`, `excluded_from_gate2`, `requires_manual_review`,
  `requires_ocr_before_gate2`, `duplicate_needs_canonical_choice`,
  `unsupported_format`, `not_source_document`,
  `methodology_or_output_artifact`, `outside_case_scope`,
  `unknown_role_requires_review`
- handoff modes:
  `full_package_ready_for_gate2`, `reduced_subset_ready_for_gate2`,
  `gate2_blocked_requires_review`, `gate2_blocked_requires_ocr`,
  `gate2_blocked_no_eligible_sources`
- OCR policy statuses:
  `disabled`, `enabled-not-executed`, `required-before-gate2`,
  `manual-review-only`

## 2. Code Changes

Changed code under `services/broker-reports-gate1-proof/`:

- added eligibility builder after profiling, taxonomy and blockers;
- extended safe report with eligibility summary and handoff mode;
- updated compact Russian report with accepted/excluded/OCR/review/reduced counts;
- persisted `document_source_eligibility_v0` in ArtifactStore;
- changed `gate2_handoff_v0` so `private_slice_refs` include only included documents;
- added opaque handoff refs for included, excluded, review, OCR and duplicate groups;
- updated validators so terminal blockers are forbidden in included refs, but do not
  automatically block a valid reduced subset;
- updated bundled Pipe builder to include the new `eligibility` module.

Bundled Pipe SHA256 after rebuild:

- `23BA2AC9EF174EDADB09C25BE24AA536F75555C868C06DC46377149585F91AE6`

Eligibility module SHA256:

- `84201F9C9AB20E58E02D51E1EA7B6AF1AD4007FFDF6BEBBB9E005FF11F0226C3`

## 3. Eligibility Status Behavior

Accepted source documents:

- supported operations/source-report classes;
- no terminal Gate 2 blocker;
- `can_enter_gate2=true`;
- `included_in_reduced_subset=true`.

Excluded documents:

- unsupported, corrupt, encrypted or unreadable inputs;
- methodology/output artifacts;
- non-source artifacts.

Review documents:

- unknown role;
- archive/review-only packages;
- duplicate candidates needing a canonical choice.

OCR candidates:

- raster or scan-like documents;
- `source_eligibility=requires_ocr_before_gate2`;
- `ocr_policy_status=required-before-gate2`;
- not included in Gate 2 refs.

## 4. Gate 2 Handoff

`gate2_handoff_v0` now contains:

- `handoff_mode`;
- `reduced_subset_validated`;
- `eligibility_ref`;
- `included_document_refs`;
- `excluded_document_refs`;
- `pending_review_refs`;
- `ocr_required_refs`;
- `duplicate_review_refs`;
- `private_slice_refs` for included documents only;
- `reason_codes`.

For a mixed synthetic package, the proven result was:

- `gate2_handoff_status=ready_with_reduced_subset`;
- `gate2_handoff_mode=reduced_subset_ready_for_gate2`;
- included refs: 1;
- excluded refs: 1;
- OCR refs: 1;
- review refs: 2;
- duplicate refs: 1.

## 5. OCR Disabled Behavior

OCR was not implemented and not executed.

Raster-like synthetic PDF input with OCR disabled:

- got `requires_ocr_before_gate2`;
- got `ocr_policy_status=required-before-gate2`;
- was not included in Gate 2 refs;
- produced `gate2_blocked_requires_ocr` when no eligible source document existed.

## 6. Unknown Role

Unknown-role supported text input:

- got `unknown_role_requires_review`;
- entered `pending_review_document_ids`;
- was not included in reduced subset;
- did not block a separate eligible source document from forming a reduced subset.

## 7. Duplicates

Duplicate content:

- produced `duplicate_review`;
- second duplicate got `duplicate_needs_canonical_choice`;
- duplicate candidate entered `duplicate_review_document_ids`;
- duplicate private slices were not passed to Gate 2 unless accepted as canonical in a future decision.

## 8. case_group_002 Readiness

The previous customer-approved `case_group_002` safe aggregate had eligible
source candidates and separate blockers for duplicate, raster/OCR and unknown
role documents.

Under this refactor, the expected routing is:

- supported operation-table documents: included in reduced subset;
- calculation/methodology artifacts: excluded as non-source;
- raster/OCR candidates: held out for OCR/review;
- unknown-role documents: held out for specialist review;
- duplicate candidates: held out for canonical choice.

This means the code is ready for a separate `case_group_002` reduced Gate 2
proof via process=false private intake. This report does not claim that a new
live customer run was executed.

## 9. Tests Executed

PowerShell context:

- `python -m compileall -q services\broker-reports-gate1-proof`
- `python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_backend_contract -v`
- `python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_artifact_store -v`
- `python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_stub -v`
- `python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_bundle -v`
- `python -m unittest discover -s services\broker-reports-gate1-proof\tests -v`

Final full suite result after bundle rebuild:

- 52 tests ran;
- 52 passed;
- 0 failed;
- 0 errors.

## 10. Safety Boundary

Confirmed by tests and code path:

- no source-fact extraction;
- no tax calculation;
- no declaration generation;
- no XLS/XLSX export;
- no OCR/VLM execution;
- no Knowledge storage for private/customer artifacts;
- compact chat report is not full JSON;
- raw private slices are not present in chat;
- ArtifactStore resolver still denies wrong user/case/chat, expired, purged,
  blocked and privacy-failed refs.

## Final Statuses

GATE1_DOCUMENT_SOURCE_ELIGIBILITY_READY

GATE1_REDUCED_SUBSET_HANDOFF_READY

GATE1_OCR_POLICY_CONTRACT_READY

GATE1_ELIGIBILITY_ARTIFACTSTORE_READY

GATE1_COMPACT_REPORT_ELIGIBILITY_READY

READY_FOR_CASE_GROUP_002_REDUCED_GATE2_PROOF
