# Broker Reports Gate 1 No-RAG Source Intake Blueprint

Status:

- BROKER_REPORTS_NO_RAG_SOURCE_INTAKE_BLUEPRINT_READY
- NATIVE_NO_RAG_MODE_NOT_FOUND
- PROJECT_OWNED_PRIVATE_INTAKE_READY
- PROCESS_FALSE_UPLOAD_PROVEN
- READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE

Date: 2026-07-08

Scope: Source-file intake for Broker Reports / XLS NDFL Gate 1 in OpenWebUI without native RAG/vector processing of case files.

This blueprint intentionally does not print raw customer filenames, OpenWebUI file ids, private payload paths, extracted rows, document text, secrets, SSH targets or env values.

## 1. Decision

Gate 1 source intake must be no-RAG by default for Broker Reports customer case files.

The intended product route remains:

```text
OpenWebUI Workspace Model
-> Broker Reports Gate 1 Pipe
-> backend normalizer
-> project ArtifactStore
-> compact Russian chat report
-> Gate 2 opaque handoff refs
```

The source upload stage must not rely on OpenWebUI Knowledge, file-context retrieval or vector DB entries for customer case documents.

## 2. Required Invariants

The intake slice is valid only if all of these are true on synthetic files:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
private_slices_loaded_to_knowledge=false
private_slices_visible_in_chat=false
gate1_pipe_receives_opaque_refs=true
gate1_artifactstore_retention_applied=true
```

`customer_docs_loaded_to_knowledge=false` alone is not sufficient.

## 3. Preferred Native Candidate

Model configuration:

```text
Broker Reports Workspace Model
base model: broker_reports_gate1_pipe
file_upload: true
file_context: false
Knowledge attachments: 0
```

Upload contract:

```text
OpenWebUI creates native file rows and source custody metadata.
OpenWebUI does not extract source content for RAG.
OpenWebUI does not create a file-scoped vector collection for the uploaded case files.
OpenWebUI does not attach files to Knowledge.
The Pipe receives refs and the backend normalizer reads bytes under the approved runtime boundary.
```

This native path was tested on 2026-07-08 and rejected for the target route. `file_context=false` was applied, Knowledge stayed empty, and the Pipe still received opaque refs, but default OpenWebUI upload processing extracted synthetic content and increased vector DB counters.

The accepted route is the project-owned private intake wrapper around
`POST /api/v1/files/?process=false`, proven on 2026-07-08. Customer-approved
packages may proceed through that wrapper only, not through ordinary OpenWebUI
bulk upload.

## 4. Backend Boundary

Gate 1 backend behavior stays unchanged in principle:

- collect OpenWebUI file refs from the Pipe request;
- validate same-user and same-context access;
- read source bytes through the approved OpenWebUI source custody boundary;
- build technical profiles, document inventory, taxonomy candidates and blockers;
- persist safe and private artifacts in the project ArtifactStore;
- apply an explicit retention policy;
- return a compact Russian report;
- hand Gate 2 opaque refs, not chat JSON.

Gate 1 still must not:

- process customer documents outside the approved run;
- run source-fact extraction;
- calculate tax;
- generate a declaration;
- generate XLS/XLSX;
- run OCR/VLM;
- load customer case files or private slices into Knowledge;
- print raw filenames, file ids, paths, rows, text, secrets or env values.

## 5. Synthetic Smoke Plan

The smoke must use synthetic files only.

Minimum synthetic package:

- one small document-like file;
- one small table-like file;
- one small office/PDF-like file where safe and available;
- all content artificial and non-customer.

Pre-smoke snapshot:

- model capability snapshot for the Broker Reports test model;
- OpenWebUI file/document/knowledge counts;
- vector DB collection/file count;
- upload payload count;
- ArtifactStore count for the test namespace.

Actions:

1. Use a dedicated synthetic Broker Reports test model, or temporarily update the existing Broker Reports model with operator approval.
2. Set `file_context=false`.
3. Keep `file_upload=true`.
4. Keep Knowledge attachments empty.
5. Upload the synthetic package through the intended OpenWebUI route.
6. Run the Gate 1 Pipe through the Workspace Model.
7. Collect post-smoke counters and privacy checks.
8. Purge the ArtifactStore run and verify tombstones.
9. Remove synthetic OpenWebUI uploads through the native file manager/API if the operator approves cleanup.

Pass criteria:

- OpenWebUI file rows increase for synthetic source custody;
- OpenWebUI document and knowledge counters do not increase;
- vector DB does not gain a synthetic file collection;
- uploaded file metadata does not contain extracted synthetic document text;
- chat-visible output is the compact Russian Gate 1 report;
- chat-visible output contains no raw filename, file id, source text, rows or private path;
- ArtifactStore persists all required Gate 1 artifacts;
- retention policy is explicit and enforced;
- resolver allows same-user/same-context and denies wrong-user, wrong-case, expired and purged refs;
- purge removes private payloads and leaves only allowed tombstones.

Fail criteria:

- normal upload still runs OpenWebUI file processing;
- synthetic source content appears in OpenWebUI Knowledge;
- synthetic source content appears in chat;
- synthetic source content appears in OpenWebUI vector storage;
- the Pipe cannot access the source bytes from opaque refs;
- retention is missing in customer-approved mode.

## 6. Fallback If Native Chat UX Fails

Because `file_context=false` did not make ordinary upload no-RAG on the target runtime, use the native backend primitive directly in the next project-owned proof:

```text
POST /api/v1/files/?process=false
```

That fallback is project-owned source intake, not unmodified native OpenWebUI UX. It may be implemented as an OpenWebUI-integrated helper around the existing Workspace Model flow, but it must still obey these constraints:

- no OpenWebUI core patch;
- no separate user-facing sidecar UI;
- no customer docs in Knowledge;
- no private slices in Knowledge;
- no vectorization of customer case files;
- no raw identifiers or text in chat-visible output;
- all derived artifacts in project ArtifactStore with retention and purge.

The fallback should be promoted only after a separate synthetic proof shows:

- `process=false` upload creates source custody without extraction/vectorization;
- Pipe can receive or resolve the resulting refs;
- same-user/same-context access checks hold;
- wrong-user/wrong-case/expired/purged access checks fail closed.

## 7. Why Global Bypass Is Rejected

Global `BYPASS_EMBEDDING_AND_RETRIEVAL` is not the product answer for Broker Reports Gate 1.

Reasons:

- it is global or admin-level, not scoped to the Broker Reports model;
- it can affect normal OpenWebUI chat and Knowledge scenarios where RAG is desired;
- target source inspection indicates extraction can still happen even when vector save is bypassed;
- it does not give the explicit per-case source custody and retention proof Gate 1 needs.

## 8. Why Knowledge-Off Alone Is Rejected

No Knowledge attachments is required, but it does not prove no-RAG upload.

The incident showed the exact failure mode:

- Knowledge stayed empty;
- OpenWebUI still held uploaded source files;
- vector storage activity still existed during the upload window.

Therefore the accepted guard is:

```text
Knowledge delta = 0
Vector delta = 0
File-context extraction delta = 0
```

## 9. ArtifactStore Contract

The no-RAG source intake does not replace the ArtifactStore. It makes the source upload stage compatible with it.

ArtifactStore must still persist:

- normalization run;
- source file refs;
- document inventory;
- technical profiles;
- taxonomy candidates;
- blockers;
- validation result;
- compact safe report artifact;
- private normalized slices;
- Gate 2 handoff;
- retention policy;
- purge state and tombstones.

Private artifacts must use the project payload backend. The store must reject `openwebui_knowledge` as a backend for customer/private artifact categories.

## 10. Operator Runbook Gate

The 2026-07-08 process-false smoke closed the synthetic no-RAG gate for the
project-owned private intake path:

```text
PROJECT_OWNED_PRIVATE_INTAKE_READY
PROCESS_FALSE_UPLOAD_PROVEN
LIVE_GATE1_VECTOR_DB_GUARD_PROVEN
LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN
LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN
LIVE_GATE1_ARTIFACTSTORE_PERSISTENCE_PASSED
LIVE_GATE1_COMPACT_RUSSIAN_REPORT_READY
READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE
```

The customer-approved package may be scheduled by the operator only through
the project-owned `process=false` intake wrapper. Ordinary OpenWebUI bulk upload
remains outside the approved route.
