# OpenWebUI Broker Reports: case_group_002 Eligibility Gate 1 Rerun

Date: 2026-07-08

## Final Status

CASE_GROUP_002_ELIGIBILITY_GATE1_RERUN_READY

CASE_GROUP_002_REDUCED_SUBSET_READY

CASE_GROUP_002_GATE2_HANDOFF_REDUCED_READY

CASE_GROUP_002_GATE2_INCLUDED_REFS_READY

CASE_GROUP_002_OCR_REVIEW_REFS_READY

CASE_GROUP_002_VECTOR_GUARD_PASSED

CUSTOMER_APPROVED_RETENTION_APPLIED

READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF

## 1. Live Pipe Update

Live OpenWebUI Function was updated:

- Function id: `broker_reports_gate1_pipe`
- Workspace Model id: `test`
- Workspace Model base model: `broker_reports_gate1_pipe`
- deployed bundled Pipe SHA-256: `e78db9c4e70a161b49bbc03e2ade4d30c129a4205ae3d46c2f273ba5c1ab292b`
- live SHA parity: yes
- live bundle contains `eligibility` module: yes
- live bundle contains `document_source_eligibility_v0`: yes
- live bundle contains `reduced_subset_ready_for_gate2`: yes

## 2. Source Intake

The rerun reused retained process=false source refs from the previous
customer-approved custody run.

- package: `case_group_002`
- broker/provider candidate: `Interactive Brokers / IBKR`
- retained process=false refs reused: yes
- new process=false upload performed: no
- ordinary OpenWebUI chat attachment upload used: no
- source ref count: `16`
- process status values: all absent/null, not `completed`
- uploaded file content endpoint payload count: `0`

No raw filenames, OpenWebUI file ids, private paths, rows, text, sheet names or
ZIP member names are printed in this report.

## 3. Retention Policy

Requested and applied:

```text
mode=customer_approved_test
explicit=true
ttl_seconds=1209600
```

ArtifactStore records in the final rerun namespace:

- total records: `69`
- records with `customer_approved_test`: `69`
- records with `explicit=false`: `0`
- purge status: `active`

## 4. Runtime Counters

The rerun used retained source refs, so no new OpenWebUI file rows were created.

| Counter | Before | After intake | After chat | Delta after chat |
| --- | ---: | ---: | ---: | ---: |
| OpenWebUI file rows | 176 | 176 | 176 | 0 |
| OpenWebUI document rows | 0 | 0 | 0 | 0 |
| OpenWebUI Knowledge rows | 0 | 0 | 0 | 0 |
| Vector collections | 123 | 123 | 123 | 0 |
| Vector dirs | 123 | 123 | 123 | 0 |
| Vector files | 502 | 502 | 502 | 0 |
| Vector bytes | 210086652 | 210086652 | 210086652 | 0 |
| ArtifactStore records | 573 | 573 | 642 | +69 |

Proof result:

- OpenWebUI Knowledge delta: `0`
- OpenWebUI vector DB delta: `0`
- OpenWebUI document delta: `0`

## 5. Files And Containers

Gate 1 processed:

- files_total: `16`

Container counts:

- `csv`: `2`
- `html_text`: `4`
- `pdf`: `8`
- `xlsx`: `2`

Document class counts:

- `calculation_template`: `2`
- `operations_table`: `2`
- `unknown_or_needs_review`: `12`

## 6. Eligibility Counts

Persisted artifact:

- `document_source_eligibility_v0`: yes
- entries: `16`

Per-status eligibility counts:

- `accepted_for_gate2`: `2`
- `excluded_from_gate2`: `0`
- `requires_manual_review`: `0`
- `requires_ocr_before_gate2`: `7`
- `duplicate_needs_canonical_choice`: `1`
- `methodology_or_output_artifact`: `2`
- `unknown_role_requires_review`: `4`

Summary buckets:

- excluded bucket total: `2`
- pending review bucket total: `5`
- included in reduced subset: `2`
- terminal exclusions: `2`
- specialist decisions required: `12`

The duplicate document also had another blocker category, but duplicate/canonical
choice now takes precedence for Gate 2 handoff routing.

## 7. Compact Russian Report

Chat-visible report:

- compact Russian report: yes
- full JSON primary output: no
- JSON fence: no
- private refs in chat: no
- length: `778`
- eligibility counts visible: yes
- Gate 2 hint visible: yes

Private slices did not enter chat.

## 8. ArtifactStore

Persisted artifact types:

- `source_file_ref_v0`: `16`
- `normalization_run_v0`: `1`
- `document_inventory_v0`: `1`
- `technical_readability_profile_v0`: `1`
- `taxonomy_candidates_v0`: `1`
- `normalization_blockers_v0`: `1`
- `document_source_eligibility_v0`: `1`
- `validation_result_v0`: `1`
- `chat_visible_normalization_report_v0`: `1`
- `private_normalized_text_slice_v0`: `4`
- `private_normalized_table_slice_v0`: `40`
- `gate2_handoff_v0`: `1`

Storage backend counts:

- `openwebui_file`: `16`
- `openwebui_chat`: `1`
- `project_artifact_store`: `8`
- `project_artifact_payload`: `44`
- `openwebui_knowledge`: `0`

Private slices did not enter Knowledge.

## 9. Gate 2 Handoff

Gate 2 handoff result:

- `gate2_handoff_status`: `ready_with_reduced_subset`
- `handoff_mode`: `reduced_subset_ready_for_gate2`
- `reduced_subset_validated`: yes

Handoff refs:

- included document refs: `2`
- excluded document refs: `2`
- pending review refs: `5`
- OCR required refs: `7`
- duplicate review refs: `1`
- private slice refs: `2`

Checks:

- private slice refs point only to included documents: yes
- terminal blockers are absent from included refs: yes
- handoff uses opaque ArtifactStore refs, not chat JSON: yes

## 10. Safety Flags

All required safety flags remained false:

```text
source_fact_extraction_performed=false
tax_correctness_claimed=false
declaration_generated=false
xlsx_generated=false
ocr_performed=false
customer_docs_loaded_to_knowledge=false
```

Not performed:

- Gate 2 source-fact extraction;
- tax calculation;
- declaration generation;
- XLS/XLSX export;
- OCR/VLM;
- Knowledge upload;
- ordinary chat attachment upload.

## 11. Gate 2 Readiness

A separate Gate 2 source-fact proof can start only on the reduced subset:

- included source refs: `2`;
- excluded methodology/output refs: `2`;
- OCR/review/duplicate refs are held out of the source subset;
- private slice refs in handoff are limited to included documents.

This report does not run Gate 2.

## 12. Specialist Questions

Specialist/customer decisions still needed:

- confirm whether the two included source documents are sufficient for the
  first reduced Gate 2 proof scope;
- decide OCR/VLM route or manual treatment for the seven OCR-required documents;
- classify the four unknown-role documents;
- choose or ignore the duplicate canonical candidate;
- confirm that the two methodology/output artifacts remain excluded from Gate 2
  source extraction.

## 13. Commands

Executed in PowerShell:

```powershell
python -m compileall -q services\broker-reports-gate1-proof
python -m unittest discover -s services\broker-reports-gate1-proof\tests -v
python services\broker-reports-gate1-proof\scripts\build_openwebui_pipe_bundle.py
python services\broker-reports-gate1-proof\scripts\live_case_group_eligibility_rerun.py
git diff --check -- docs services\broker-reports-gate1-proof
```

Local verification before live rerun:

- compileall: passed
- unittest: `52` tests passed

Live rerun:

- status: `passed`
- retained process=false refs reused: yes
- ArtifactStore records added for final rerun: `69`

No customer file was committed or copied into the repository.
