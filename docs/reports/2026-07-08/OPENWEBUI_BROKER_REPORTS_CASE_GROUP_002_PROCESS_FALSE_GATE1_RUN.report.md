# OpenWebUI Broker Reports: case_group_002 process=false Gate 1 run

Date: 2026-07-08

Final status:

- `CUSTOMER_CASE_GROUP_002_PROCESS_FALSE_GATE1_PARTIAL`
- `GATE1_COMPLETED_WITH_BLOCKERS_GATE2_HANDOFF_BLOCKED`
- `CUSTOMER_GATE2_PROOF_BLOCKED`

Proven sub-results:

- `CUSTOMER_APPROVED_RETENTION_APPLIED`
- `CUSTOMER_VECTOR_DB_GUARD_PASSED`
- `CUSTOMER_KNOWLEDGE_GUARD_PASSED`
- `CUSTOMER_ARTIFACTSTORE_PERSISTENCE_READY`
- `CUSTOMER_COMPACT_REPORT_READY`

`READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF` is not used because the Gate 1 handoff status is `blocked`.

## 1. Package

Processed package:

- case group: `case_group_002`
- broker/provider candidate: `Interactive Brokers / IBKR`
- files_total: `16`
- grouping confidence: `high`
- registry readiness: `needs_review`

Customer approval for this package was treated as confirmed by the operator request.

## 2. Private Registry Resolution

Files were resolved from the ignored private local registry and cross-checked against the safe registries:

- safe case group document ids: `16`
- private registry matches: `16`
- private files found on disk: `16`
- SHA-256 matches: `16`
- customer files copied into repo: no
- raw filenames/private paths printed: no

The upload used sanitized aliases, not raw customer filenames.

## 3. Intake Path

Used controlled upload path only:

```text
POST /api/v1/files/?process=false
```

Not used:

- ordinary OpenWebUI chat attachment upload;
- OpenWebUI Knowledge upload;
- source-fact extraction;
- tax calculation;
- declaration generation;
- XLS/XLSX export;
- OCR/VLM.

## 4. Live Function

Live Function:

- Function id: `broker_reports_gate1_pipe`
- Workspace Model id: `test`
- Workspace Model base model: `broker_reports_gate1_pipe`
- model `file_upload`: `true`
- model `file_context`: `false`
- Knowledge attachments: `0`

Deployed bundle:

- live bundle SHA-256: `1c183a67bee45e8b5b95069664f598fe3e9cabe1719d8152a814db3f2cc3b437`
- hash parity after deploy: yes

The Pipe was updated to accept an explicit per-run retention policy from request metadata/body. Missing explicit `customer_approved_test` remains fail-closed.

## 5. Retention Policy

Requested and applied:

```text
mode=customer_approved_test
explicit=true
ttl_seconds=1209600
```

ArtifactStore evidence:

- records in final case namespace: `68`
- records with `customer_approved_test`: `68`
- records with `explicit=false`: `0`
- purge status: `active`

An earlier attempt in this run used the old `api_smoke` retention because the override did not reach the live Pipe. That attempt was treated as failed, its 16 temporary source uploads were deleted, and its 68 ArtifactStore records were tombstoned before the final run.

## 6. Runtime Counters

Final customer-approved run counters:

| Counter | Before | After process=false upload | After chat |
| --- | ---: | ---: | ---: |
| OpenWebUI `file` rows | 157 | 173 | 173 |
| OpenWebUI `document` rows | 0 | 0 | 0 |
| OpenWebUI `knowledge` rows | 0 | 0 | 0 |
| Vector collections | 123 | 123 | 123 |
| Vector dirs | 123 | 123 | 123 |
| Vector files | 502 | 502 | 502 |
| Vector bytes | 210086652 | 210086652 | 210086652 |
| ArtifactStore records | 436 | 436 | 504 |

Deltas after chat:

- OpenWebUI file rows: `+16`
- OpenWebUI document rows: `0`
- OpenWebUI Knowledge rows: `0`
- vector collections/files/bytes: `0 / 0 / 0`
- ArtifactStore records: `+68`

The `+16` OpenWebUI file rows are the retained process=false source custody rows for this customer-approved test policy. They were not vectorized.

## 7. Gate 1 Result

Compact Russian report:

- returned: yes
- full JSON primary output: no
- JSON fence: no
- private refs in chat: no
- length: `499`

Gate 1 safe report:

- files_total: `16`
- run_status: `completed_with_blockers`
- validation_status: `passed`
- gate2_handoff_status: `blocked`
- duplicate_count: `1`
- blockers_total: `21`

Container counts:

- `csv`: `2`
- `html_text`: `4`
- `pdf`: `8`
- `xlsx`: `2`

Document class counts:

- `calculation_template`: `2`
- `operations_table`: `2`
- `unknown_or_needs_review`: `12`

Blocker code counts:

- `duplicate_review`: `1`
- `raster_requires_ocr_or_review`: `8`
- `unknown_role`: `12`

Gate 2 blocking blockers: `8`.

## 8. ArtifactStore

Derived artifacts live in the project ArtifactStore inside the OpenWebUI runtime boundary. Private payload paths are intentionally not printed.

Artifact types:

- `source_file_ref_v0`: `16`
- `normalization_run_v0`: `1`
- `document_inventory_v0`: `1`
- `technical_readability_profile_v0`: `1`
- `taxonomy_candidates_v0`: `1`
- `normalization_blockers_v0`: `1`
- `validation_result_v0`: `1`
- `chat_visible_normalization_report_v0`: `1`
- `private_normalized_text_slice_v0`: `4`
- `private_normalized_table_slice_v0`: `40`
- `gate2_handoff_v0`: `1`

Storage backends:

- `openwebui_file`: `16`
- `openwebui_chat`: `1`
- `project_artifact_store`: `7`
- `project_artifact_payload`: `44`
- `openwebui_knowledge`: `0`

Private slices are persisted in the project payload backend and are not loaded into chat or Knowledge.

## 9. Source Upload Cleanup

Final run cleanup policy:

- cleanup performed immediately: no
- reason: retained for `customer_approved_test` source custody and possible follow-up review/Gate 2
- process status values: all absent/null, not `completed`
- file content endpoint payload count: `0`

The source uploads remain as process=false custody rows under the customer-approved retention window. Deleting them now would either remove source custody or, if cascaded through ArtifactStore policy, purge private payloads needed for follow-up. Cleanup should be performed after the operator decides whether to proceed with review/Gate 2 or close the case.

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

## 11. Gate 2 Decision

Gate 2 source-fact proof must not start yet.

Reason: Gate 1 produced a valid customer-approved ArtifactStore run, but the handoff is blocked by review blockers, especially raster/OCR-review and unknown-role blockers.

Next allowed step is specialist/customer review of the blockers and an explicit decision:

- whether raster-like PDFs may be handled by a later OCR/VLM-approved route;
- whether unknown-role documents should be reclassified, excluded, or accepted as context;
- whether the duplicate should be ignored or selected as canonical;
- whether to run Gate 2 on a reduced unblocked subset or wait for full review.

## 12. Commands

```powershell
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_stub -v
python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py
python services/broker-reports-gate1-proof/scripts/live_case_group_process_false_gate1_run.py
python -m compileall -q services/broker-reports-gate1-proof
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
git diff --check -- docs services/broker-reports-gate1-proof
```

Final local validation:

- compileall: passed
- unittest: `50` tests passed
- diff check: passed; only CRLF working-copy warnings were printed

Supporting live actions:

- updated live Function `broker_reports_gate1_pipe`;
- verified bundle/live hash parity;
- cleaned the failed `api_smoke` partial run before the final customer-approved run.

No customer file was committed or copied into the repository.
