# OpenWebUI Broker Reports Gate 1 No-RAG Source Intake Synthetic Smoke Report

Date: 2026-07-08

Scope: Broker Reports / XLS NDFL Gate 1 synthetic runtime proof for per-model no-RAG source intake.

Status:

- NATIVE_NO_RAG_MODE_NOT_FOUND
- PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
- CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED
- LIVE_GATE1_VECTOR_DB_GUARD_FAILED
- LIVE_GATE1_SOURCE_UPLOAD_CLEANUP_PARTIAL
- LIVE_GATE1_PIPE_AND_ARTIFACTSTORE_STILL_FUNCTIONAL

This report intentionally does not print raw customer filenames, synthetic raw filenames, OpenWebUI file ids, private payload paths, extracted rows, document text, secrets, SSH targets or env values.

## 1. Executive Result

The native per-model candidate was rejected on synthetic files.

Tested candidate:

```text
Workspace Model id: test
base Pipe Function: broker_reports_gate1_pipe
file_upload=true
file_context=false
Knowledge attachments=0
```

Observed result:

- `file_context=false` was applied before upload;
- Knowledge delta stayed zero;
- document row delta stayed zero;
- Pipe received opaque refs;
- compact chat report returned;
- ArtifactStore persisted Gate 1 artifacts;
- OpenWebUI native upload still extracted synthetic content into file data;
- OpenWebUI vector DB counters increased during upload processing;
- native upload deletion removed file rows but did not return vector counters to baseline.

Therefore:

```text
NATIVE_NO_RAG_MODE_NOT_FOUND
PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED
```

## 2. Docs And Contracts Refined

Updated:

- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md`
- `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md`
- `docs/stage2/proof/BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_PROOF_PLAN.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_WORKSPACE_GATE1_OPERATOR_HANDOFF.md`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_PER_MODEL_NO_RAG_UPLOAD_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_NO_RAG_SOURCE_INTAKE.blueprint.md`

Created:

- `docs/stage2/proof/BROKER_REPORTS_GATE1_NO_RAG_SOURCE_INTAKE_SMOKE_CHECKLIST.md`
- `services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py`

The refined contract now treats this guard as mandatory:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
gate1_pipe_receives_only_opaque_source_refs=true
```

## 3. Runtime Target

Tested route:

```text
OpenWebUI Workspace Model -> broker_reports_gate1_pipe -> Gate 1 backend normalizer -> ArtifactStore
```

Live model facts:

| Field | Value |
| --- | --- |
| Workspace Model id | `test` |
| Base Pipe Function | `broker_reports_gate1_pipe` |
| Original `file_upload` | `true` |
| Original `file_context` | `true` |
| Tested `file_upload` | `true` |
| Tested `file_context` | `false` |
| Knowledge attachments | `0` |
| Model config restored after failure | `true` |

No global RAG disable was used. No OpenWebUI core patch was applied. No separate user-facing sidecar UI was created.

## 4. Synthetic Inputs

Synthetic files used:

- count: `2`;
- one text-like synthetic broker-report fixture;
- one synthetic CSV operations-table fixture.

No customer documents were used. Exact source filenames are intentionally not printed.

## 5. Counter Evidence

Counters are safe aggregates only.

| Snapshot | File rows | Document rows | Knowledge rows | Vector collections | Vector files | Vector size bytes | ArtifactStore records |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before | 165 | 0 | 0 | 121 | 494 | 209697204 | 188 |
| After upload processing | 167 | 0 | 0 | 123 | 502 | 210086652 | 188 |
| After chat/Pipe | 167 | 0 | 0 | 123 | 502 | 210086652 | 224 |
| After upload delete | 165 | 0 | 0 | 123 | 502 | 210086652 | 224 |
| Delayed re-snapshot | 165 | 0 | 0 | 123 | 502 | 210086652 | 224 |

Delta after upload processing:

```text
file_rows=+2
document_rows=0
knowledge_rows=0
vector_collections=+2
vector_files=+8
vector_size_bytes=+389448
artifactstore_records=0
```

Delta after chat:

```text
artifactstore_records=+36
```

After upload delete:

```text
file_rows returned to baseline
vector_collections remained +2
vector_files remained +8
vector_size_bytes remained +389448
```

## 6. Source Intake Findings

`file_context=false` was applied successfully, but it did not stop native OpenWebUI upload processing on the tested route.

Proof facts:

| Check | Result |
| --- | --- |
| `file_upload=true` applied | pass |
| `file_context=false` applied | pass |
| Knowledge attachments = 0 | pass |
| document row delta = 0 | pass |
| Knowledge row delta = 0 | pass |
| vector DB delta for case = 0 | fail |
| uploaded file data contains extracted synthetic text | fail |
| Pipe receives opaque refs | pass |
| chat output compact, not full JSON | pass |
| raw file id leak in chat | pass: 0 |
| forbidden source marker leak in chat | pass: 0 |

The failure is before the Pipe/ArtifactStore boundary: native OpenWebUI file upload processed the source files.

## 7. Chat Output

The chat output was a compact report, not primary full JSON.

Safe checks:

- `chat_compact_report=true`;
- `chat_full_json_primary_output=false`;
- `chat_forbidden_marker_count=0`;
- `chat_file_id_leak_count=0`;
- private slice content was not observed in chat.

The report text itself is not copied here to avoid raw source markers and noisy runtime text.

## 8. ArtifactStore And Resolver

The Pipe and ArtifactStore path still functioned.

Evidence:

- ArtifactStore record count increased by `36` after chat/Pipe execution;
- required Gate 1 artifact families were present for the smoke case;
- the `artifactstore retention smoke` branch completed without surfacing private data;
- case-scoped ArtifactStore records for the smoke ended as allowed tombstones after source cleanup/purge behavior.

Sanitized ArtifactStore aggregate for the smoke case:

```text
case_record_count=24
lifecycle_status=purged: 24
purge_status=purged: 24
storage_backend=none_tombstone: 24
```

Type coverage included:

- `normalization_run_v0`;
- `source_file_ref_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `validation_result_v0`;
- `chat_visible_normalization_report_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `gate2_handoff_v0`.

## 9. Cleanup And Purge

OpenWebUI source upload cleanup:

- uploaded synthetic file rows were deleted;
- file row count returned to baseline;
- vector counters did not return to baseline.

ArtifactStore cleanup:

- smoke-case ArtifactStore records were purged to tombstones;
- private payload storage was not exposed in chat or report.

Conclusion:

```text
source upload row cleanup: proven
ArtifactStore purge/tombstones: proven
OpenWebUI vector cleanup after native delete: not proven
```

## 10. Forbidden Work Not Performed

The smoke did not:

- upload customer documents;
- repeat customer bulk upload;
- run source-fact extraction;
- calculate tax;
- generate declaration;
- generate XLS/XLSX export;
- run OCR/VLM;
- load customer docs or private slices into Knowledge;
- disable global RAG;
- patch OpenWebUI core;
- create a sidecar UI.

Safety flags:

```text
source_fact_extraction_performed=false
tax_correctness_claimed=false
declaration_generated=false
xlsx_generated=false
ocr_performed=false
```

## 11. Commands Executed

Local script verification:

```text
python -m py_compile services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py
python -m compileall -q services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py
```

Synthetic runtime smoke:

```text
python services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py --env-file .env
```

The smoke runner returned a non-zero process status by design because the native candidate failed acceptance. The JSON result status was:

```text
status=failed_native_candidate
outcome=NATIVE_NO_RAG_MODE_NOT_FOUND
recommendation=PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
```

Additional read-only runtime probes:

- verified Workspace Model capabilities were restored after the failed candidate test;
- re-snapshotted DB/vector counters after a short delay;
- inspected ArtifactStore aggregate counts for the smoke case without printing artifact ids.

## 12. Customer-Approved Package Decision

Customer-approved upload is not allowed yet.

Allowed next step:

```text
Prepare a narrow project-owned private intake proof around POST /api/v1/files/?process=false.
```

That fallback must:

- stay inside the OpenWebUI workflow;
- avoid OpenWebUI core patches;
- avoid a separate user-facing sidecar UI;
- prove vector DB delta zero;
- prove no extracted source text in OpenWebUI file data;
- keep Pipe/ArtifactStore/retention/resolver architecture unchanged;
- require explicit `customer_approved_test` retention policy before customer documents.
