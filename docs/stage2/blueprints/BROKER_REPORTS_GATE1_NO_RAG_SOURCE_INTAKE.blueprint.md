# Broker Reports Gate 1 No-RAG Source Intake Blueprint

Status:

- BROKER_REPORTS_NO_RAG_SOURCE_INTAKE_BLUEPRINT_READY
- ORDINARY_NATIVE_UPLOAD_PRODUCT_ROUTE
- PROCESS_FALSE_UPLOAD_PROVEN
- OPENWEBUI_0_9_6_COMPATIBILITY_SEAM_TEMPORARY

Updated: 2026-09-05

Scope: Source-file intake for Broker Reports / XLS NDFL Gate 1 in OpenWebUI without native RAG/vector processing of case files.

This blueprint intentionally does not print raw customer filenames, OpenWebUI file ids, private payload paths, extracted rows, document text, secrets, SSH targets or env values.

## 1. Decision

Gate 1 source intake must be no-RAG by default for Broker Reports customer case files.

The intended product route remains:

```text
OpenWebUI Workspace Model
-> Broker Reports Gate 1 Pipe
-> native Files owner check / Storage byte read
-> backend normalizer
-> project ArtifactStore
-> owner-scoped full-source.zip projection
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

The 2026-07-08 test proved that `file_context=false` alone was insufficient:
default upload processing still extracted synthetic content and changed vector
counters. The current product route keeps the ordinary OpenWebUI attachment UX
and native upload response. On OpenWebUI 0.9.6 only, a temporary frontend seam
sets `process=false` for PDF uploads when the exact selected model ID is
`broker_reports_gate1_pipe`. There is no project-owned intake endpoint, custom
Action, response schema or DOM-derived file mapping.

## 4. Backend Boundary

Gate 1 backend behavior stays unchanged in principle:

- collect OpenWebUI file refs from the Pipe request;
- resolve the native file ID through `Files` and require exact owner equality;
- read source bytes through native `Storage`;
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
- run any PDF OCR path except the single configured Mistral adapter behind
  `PdfDocumentExtractorFactory`;
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

## 6. Temporary OpenWebUI 0.9.6 compatibility seam

Because `file_context=false` does not make upload no-RAG on OpenWebUI 0.9.6,
the ordinary attachment request uses the native primitive:

```text
POST /api/v1/files/?process=false
```

The loader only rewrites this URL for a PDF when the exact selected model ID is
`broker_reports_gate1_pipe`. OpenWebUI still owns the file row and response;
the Pipe still receives the native ID. The seam must obey these constraints:

- no OpenWebUI core patch;
- no separate user-facing sidecar UI;
- no custom intake endpoint or Action;
- no filename-, position- or DOM-based file identity;
- no customer docs in Knowledge;
- no private slices in Knowledge;
- no vectorization of customer case files;
- no raw identifiers or text in chat-visible output;
- all derived artifacts in project ArtifactStore with retention and purge.

The seam remains valid only while tests show:

- `process=false` upload creates source custody without extraction/vectorization;
- Pipe can receive or resolve the resulting refs;
- same-user/same-context access checks hold;
- wrong-user/wrong-case/expired/purged access checks fail closed.

Remove it when upstream OpenWebUI provides an equivalent per-model
upload-processing policy.

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

The 2026-07-08 process-false smoke proved the native upload primitive. The
current ordinary Pipe route reuses it through the temporary exact-model seam:

```text
ORDINARY_NATIVE_UPLOAD_PRODUCT_ROUTE
PROCESS_FALSE_UPLOAD_PROVEN
LIVE_GATE1_VECTOR_DB_GUARD_PROVEN
LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN
LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN
LIVE_GATE1_ARTIFACTSTORE_PERSISTENCE_PASSED
LIVE_GATE1_COMPACT_RUSSIAN_REPORT_READY
CUSTOM_INTAKE_OR_ACTION_NOT_PRESENT
```

The operator uses the ordinary OpenWebUI attachment control with exactly
`broker_reports_gate1_pipe` selected. The server trusts only the native file ID
and exact owner read through `Files`/`Storage`. The frontend seam owns no source
identity and is not a fallback route.
