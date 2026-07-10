# Broker Reports OpenWebUI Per-Model No-RAG Upload Research

Status:

- OPENWEBUI_PER_MODEL_NO_RAG_UPLOAD_RESEARCH_READY
- NATIVE_NO_RAG_MODE_NOT_FOUND
- PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
- CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED

Date: 2026-07-08

Scope: Broker Reports / XLS NDFL Gate 1 source-file intake boundary in OpenWebUI.

This document intentionally does not print raw customer filenames, OpenWebUI file ids, private payload paths, extracted rows, document text, secrets, SSH targets or env values.

## 1. Executive Conclusion

The native OpenWebUI per-model candidate was tested on 2026-07-08 and rejected for the target Broker Reports route. `file_context=false` was applied to the Workspace Model, but ordinary OpenWebUI upload still extracted synthetic file content and increased native vector DB counters.

The candidate is the combination of:

- Workspace Model capability `file_context=false`;
- OpenWebUI native file upload API parameter `process=false`;
- Broker Reports Gate 1 Pipe consuming opaque file refs and reading source bytes under its own approved boundary;
- project ArtifactStore persisting derived private artifacts and retention state;
- no customer files in OpenWebUI Knowledge and no OpenWebUI vector collection for the source upload.

The reason is now proven, not theoretical: official OpenWebUI docs describe File Context as model-scoped RAG behavior, but the target upload path is still processed by the native file upload endpoint. The backend endpoint supports `process=false`, but the ordinary route tested here did not use that primitive automatically.

Operational decision:

- do not repeat normal customer bulk chat upload;
- do not disable global RAG;
- do not patch OpenWebUI core;
- do not use customer documents for this proof;
- customer-approved upload remains blocked;
- use the narrow project-owned private intake fallback around `POST /api/v1/files/?process=false` as the next proof candidate.

## 2. Safety Property

The earlier Gate 1 contract already required:

```text
customer_docs_loaded_to_knowledge=false
```

The upload incident showed that this is necessary but not sufficient. For Broker Reports Gate 1, the source intake property must be:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
gate1_pipe_receives_only_opaque_source_refs=true
```

Gate 1 may still read source bytes through its approved backend boundary. That read is not OpenWebUI Knowledge/RAG. It is the controlled normalization path that produces private ArtifactStore slices and a compact safe report.

## 3. Local Contract Context

Reviewed and reused existing local contract material:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_ARTIFACT_STORAGE_RETENTION.blueprint.md`
- `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_ARTIFACTSTORE_PERSISTENCE_AND_RETENTION.report.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_LIVE_ARTIFACTSTORE_RETENTION_SMOKE.report.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_RAW_UPLOAD_RAG_VECTORIZATION_GAP.report.md`
- `services/broker-reports-gate1-proof/`

The stable architecture remains hybrid native-first:

- OpenWebUI owns the user shell, Workspace Model, chat history, source upload identity, source file access checks and optional approved Knowledge.
- Broker Reports ArtifactStore owns normalization runs, private derived slices, validation, retention, purge state and Gate 2 handoff refs.

This research does not redesign that architecture.

## 4. Official OpenWebUI Evidence

Official OpenWebUI documentation currently exposes three relevant facts.

First, the file upload API has a native processing switch:

- `POST /api/v1/files/`;
- `process` defaults to `true`;
- when processing is enabled, uploaded file content is extracted and embeddings are computed.

Reference: [OpenWebUI API Endpoints - Uploading Files](https://docs.openwebui.com/reference/api-endpoints)

Second, Workspace Model capabilities include File Context:

- when File Context is enabled, attached files are processed via RAG;
- when disabled, file content is not extracted.

References:

- [OpenWebUI Models - Model Capabilities](https://docs.openwebui.com/features/workspace/models/)
- [OpenWebUI RAG - File Context Capability](https://docs.openwebui.com/features/chat-conversations/rag/)

Third, `BYPASS_EMBEDDING_AND_RETRIEVAL` exists but is global/admin-level behavior, not a per-model Broker Reports intake contract.

Reference: [OpenWebUI Environment Variable Configuration](https://docs.openwebui.com/reference/env-configuration/)

Community issues are consistent with the risk we saw operationally:

- users have asked for file uploads without backend processing for custom pipelines;
- users report that normal chat uploads can require RAG processing before the file can be used;
- users have asked for an attachment-level or model-level way to disable RAG.

References:

- [open-webui/open-webui#12228](https://github.com/open-webui/open-webui/issues/12228)
- [open-webui/open-webui#18431](https://github.com/open-webui/open-webui/issues/18431)
- [open-webui/open-webui#3556](https://github.com/open-webui/open-webui/issues/3556)

Community issues are not the product contract, but they support treating the no-RAG intake path as something that must be proven on the exact runtime.

## 5. Target Runtime Source Findings

The target runtime was inspected read-only. No production config change, customer upload, source-fact extraction, OCR, tax calculation, declaration generation or XLS export was performed.

Backend upload behavior:

- deployed backend source has `POST /api/v1/files/`;
- both the route and helper default to `process=true`;
- after the file row is created, the processing branch only runs when `process` is true;
- with `process=false`, the handler returns the uploaded file item without calling the processing function.

Backend processing behavior:

- file processing eventually calls the retrieval file processor;
- the default per-file vector collection name is file-scoped;
- processing can write extracted content into the OpenWebUI file data;
- without global bypass, processing saves chunks and embeddings into the vector DB;
- with global bypass, vector save is bypassed, but extraction has still happened.

Chat retrieval behavior:

- chat completion middleware uses attached file metadata to retrieve sources and inject context;
- model metadata capability `file_context` gates that file-context path;
- disabling `file_context` is therefore the correct per-model RAG-injection control.

Frontend behavior:

- deployed frontend source has a file API helper that can send the `process` query parameter;
- ordinary chat file upload paths inspected in the target source default to processing enabled;
- some non-document paths can explicitly call upload with processing disabled;
- the model capability UI exposes `file_upload` and `file_context`;
- the target Broker Reports model currently has upload enabled and File Context enabled;
- the model currently has no attached Knowledge collection.

Project static extension behavior:

- the mounted static loader contains a call to `/api/v1/files/?process=false`;
- this proves our project extension can use the native API parameter;
- it must not be described as unmodified native OpenWebUI UX.

## 6. Current Risk State

Current Broker Reports model state is not the desired no-RAG intake state.

Observed target model shape:

```text
Workspace Model: Broker Reports Gate 1 model
Base: broker_reports_gate1_pipe
file_upload: true
file_context: true
Knowledge attachments: 0
```

`Knowledge attachments: 0` is good but insufficient. With `file_context=true`, ordinary source upload can still enter native OpenWebUI RAG processing and vector storage even when Knowledge stays empty.

The incident report already recorded the consequence: Knowledge remained empty, while OpenWebUI file rows, upload payloads, vector DB files and embedding/vector log activity still existed during the overloaded upload window.

## 7. Option Matrix

| Option | Native | Per-model | Avoids Knowledge | Avoids vectorization | Suitable for Gate 1 |
| --- | --- | --- | --- | --- | --- |
| Set `file_context=false` on Broker Reports model | Yes | Yes | Yes | No on target smoke | Rejected for ordinary upload route |
| Upload through `/api/v1/files/?process=false` | Yes API | Not by itself | Yes | Source-proven yes for upload processing; fallback smoke still required | Preferred backend/API primitive for project-owned intake |
| Disable global `BYPASS_EMBEDDING_AND_RETRIEVAL` | Yes | No | Partial | Vector bypass only; extraction can still happen | Reject |
| Only detach Knowledge | Yes | Yes | Yes | No | Reject as insufficient |
| Use project static loader with `process=false` | Uses native API | Project-owned | Yes | Yes if smoke passes | Fallback, not primary native UX |
| Temporary chat mode | Native | User/session-level | Likely yes | Needs separate proof | Not primary: weak Workspace Model/Pipe contract |
| OpenWebUI core patch | No | Could be | Could be | Could be | Reject by constraint |
| Separate sidecar UI | No | Project-owned | Could be | Could be | Reject by constraint |

## 8. Rejected Native Candidate

The rejected candidate was:

```text
Broker Reports Workspace Model
  file_upload=true
  file_context=false
  Knowledge attachments=0

OpenWebUI upload
  native file row created
  upload source bytes available to same user/context
  expected no extraction into chat context
  expected no file-scoped vector collection
  no Knowledge/document row

broker_reports_gate1_pipe
  receives opaque file refs
  never returns full JSON as primary business output
  calls backend normalizer
  persists private/safe artifacts in project ArtifactStore
  returns compact Russian report
```

The 2026-07-08 synthetic smoke showed that the ordinary tested route did not satisfy the expected upload properties. The fallback should be a project-owned source intake wrapper that calls the native API with `process=false`, still inside OpenWebUI and still without a separate user-facing sidecar UI. The fallback must be marked as project-owned, not native unmodified OpenWebUI behavior.

## 9. Required Fallback Runtime Smoke

The next smoke must prove the project-owned private intake fallback on synthetic files.

Preconditions:

- no customer documents;
- no production bulk upload;
- no source-fact extraction;
- no OCR/VLM;
- no tax calculation;
- no declaration or XLS/XLSX export.

Synthetic files:

- one small text-like document;
- one small tabular document;
- one small office/PDF-like document where safe;
- no real taxpayer, broker, account, trade, declaration or customer data.

Required before/after checks:

- OpenWebUI `file` row delta is expected;
- OpenWebUI `document` delta is zero;
- OpenWebUI `knowledge` delta is zero;
- OpenWebUI vector DB delta is zero for the synthetic upload;
- no new file-scoped vector collection for the synthetic refs;
- uploaded file data does not contain extracted text content;
- chat-visible answer contains compact Russian Gate 1 report only;
- chat-visible answer contains no raw filename, file id, source text, rows or private path;
- Pipe receives opaque refs rather than chat JSON;
- ArtifactStore persists expected Gate 1 artifacts with explicit retention;
- Gate 2 resolver can resolve same-user/same-context refs and deny wrong-user, wrong-case, expired and purged refs.

Fail conditions:

- any synthetic upload creates a file-scoped vector collection;
- any synthetic source text is stored in Knowledge;
- any private slice appears in chat;
- fallback upload still runs backend processing;
- the only working path is a brittle DOM/static loader while no backend-owned source-intake contract is proven.

## 10. Recommendation

Proceed in this order:

1. Keep customer-approved upload blocked.
2. Do not use ordinary OpenWebUI bulk upload for Broker Reports customer packages.
3. Prepare the narrow project-owned private intake proof around `POST /api/v1/files/?process=false`.
4. Prove vector DB delta zero, file-data extraction false, Knowledge delta zero and Pipe opaque refs on synthetic files.
5. Preserve the current Pipe, normalizer, ArtifactStore, retention and resolver architecture.
6. Only after fallback proof passes, prepare the customer-approved package flow with explicit `customer_approved_test` retention.

Current operational statement:

```text
native per-model no-RAG mode not found on target route; customer-approved upload remains blocked
```
