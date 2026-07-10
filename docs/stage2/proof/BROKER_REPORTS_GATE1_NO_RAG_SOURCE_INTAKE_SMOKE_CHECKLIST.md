# Broker Reports Gate 1 No-RAG Source Intake Smoke Checklist

Status:

- NO_RAG_SOURCE_INTAKE_SMOKE_CHECKLIST_READY
- NATIVE_NO_RAG_MODE_NOT_FOUND
- PROJECT_OWNED_PRIVATE_INTAKE_READY
- PROCESS_FALSE_UPLOAD_PROVEN
- LIVE_GATE1_VECTOR_DB_GUARD_PROVEN
- READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE

Date: 2026-07-08

Scope: synthetic-only proof template for Broker Reports Gate 1 source upload without OpenWebUI native RAG/vector processing.

Do not use customer documents. Do not print raw filenames, OpenWebUI file ids, private paths, rows, source text, secrets or env values.

## 1. Required Guard

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
gate1_pipe_receives_only_opaque_source_refs=true
```

`Knowledge count = 0` is not sufficient.

## 2. Native Candidate Result

The 2026-07-08 synthetic runtime smoke rejected the native per-model candidate:

```text
file_upload=true
file_context=false
Knowledge attachments=0
```

Observed result:

- Knowledge delta was zero;
- document delta was zero;
- Pipe received opaque refs;
- compact report returned;
- extracted synthetic text appeared in OpenWebUI file data;
- vector DB counters increased;
- native upload delete removed file rows but did not return vector counters to baseline.

Native OpenWebUI bulk upload remains blocked for Broker Reports customer packages.
Customer-approved upload may proceed only through the project-owned `process=false`
private intake path proven in the 2026-07-08 process-false smoke report.

## 3. Proven Fallback Path

The accepted path is the narrow project-owned private intake wrapper around:

```text
POST /api/v1/files/?process=false
```

The fallback stays inside the OpenWebUI workflow, does not patch OpenWebUI core,
and does not create a separate user-facing sidecar UI.

## 4. Pre-Smoke Snapshot

Record safe counters only:

- Workspace Model id and base Pipe id;
- effective model capabilities;
- Knowledge attachment count;
- OpenWebUI file row count;
- OpenWebUI document row count;
- OpenWebUI knowledge row count;
- vector DB collection/file/size counters;
- ArtifactStore record count.

## 5. Pass Criteria

The fallback proof passes only if:

- source upload creates only allowed source custody state;
- document row delta is zero;
- knowledge row delta is zero;
- vector DB collection/file delta is zero;
- uploaded file data does not contain extracted source text;
- Pipe receives opaque refs;
- compact Russian report returns;
- ArtifactStore persists required artifacts;
- explicit retention policy is applied;
- Gate 2 handoff uses opaque refs;
- resolver access checks pass;
- purge removes private payloads and leaves allowed tombstones.

## 6. Fail Criteria

Fail closed if any of these happen:

- vector DB delta is non-zero;
- OpenWebUI file data contains extracted source text;
- private slices appear in chat;
- private slices appear in Knowledge;
- customer-approved mode accepts missing retention policy;
- source upload cleanup leaves unexplained vector residue.

## 7. Required Report Path

Use the latest process-false proof report:

```text
docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_PROCESS_FALSE_PRIVATE_INTAKE_SMOKE.report.md
```
