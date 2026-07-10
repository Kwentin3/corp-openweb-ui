# OpenWebUI Broker Reports Per-Model No-RAG Upload Research Report

Date: 2026-07-08

Scope: Broker Reports / XLS NDFL Gate 1 no-RAG source intake research after the OpenWebUI bulk upload incident.

Status:

- SUPERSEDED_BY_SYNTHETIC_SMOKE_OUTCOME_B
- BROKER_REPORTS_NO_RAG_SOURCE_INTAKE_BLUEPRINT_READY
- NATIVE_NO_RAG_MODE_NOT_FOUND
- PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
- CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED

This report intentionally does not print raw customer filenames, OpenWebUI file ids, private payload paths, extracted rows, document text, secrets, SSH targets or env values.

## 1. Executive Summary

Update after synthetic smoke: the native per-model candidate was rejected on the target route. See `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_NO_RAG_SOURCE_INTAKE_SYNTHETIC_SMOKE.report.md`.

The original research found a credible native no-RAG candidate, but runtime smoke later proved that `file_context=false` did not stop default upload extraction/vectorization for the tested Broker Reports route.

The candidate is:

```text
Broker Reports Workspace Model
file_upload=true
file_context=false
Knowledge attachments=0
native upload processing disabled for source case files
Gate 1 Pipe receives opaque refs
Gate 1 backend reads source bytes under approved boundary
ArtifactStore persists private/safe artifacts with retention
```

Official OpenWebUI docs supported testing this direction: File Context disabled means attached files are not processed for RAG, and the file upload API has a `process=false` switch. The target backend source also confirms that `process=false` skips file processing.

The later synthetic smoke closed this proof gap with a negative result: ordinary tested upload still processed/vectorized files even after `file_context=false` was applied.

## 2. What Was Found

OpenWebUI native surfaces:

- `POST /api/v1/files/` supports a `process` query parameter;
- default upload processing is enabled;
- processing can extract file content and save embeddings;
- File Context is a model capability that controls attached-file RAG behavior;
- Knowledge/File Manager deletion can clean associated vector embeddings, but cleanup is not the same as proving no vectorization happened.

Target runtime source evidence:

- backend upload route has a processing branch guarded by `process`;
- with `process=false`, the upload path returns without calling the file processor;
- file processing can write extracted content into OpenWebUI file data and vector DB;
- global embedding/retrieval bypass is not acceptable as the Broker Reports solution because it is not per-model and extraction can still occur;
- chat middleware gates file-context retrieval by model metadata capability;
- current Broker Reports model has upload enabled and File Context enabled;
- current Broker Reports model has no Knowledge attachments.

Project extension evidence:

- the project static layer already knows how to call the native upload API with `process=false`;
- this is useful fallback evidence;
- it is not proof that unmodified native OpenWebUI chat upload is already safe.

## 3. Answer To The Core Question

Is there a native supported way to make Broker Reports uploads no-RAG per model?

Answer:

```text
Candidate found, not yet promoted to final proof.
```

The native pieces exist:

- per-model File Context capability;
- native upload `process=false`;
- backend source behavior that skips processing when `process=false`.

The missing proof:

- synthetic runtime evidence that the Broker Reports Workspace Model route uses the no-RAG behavior end to end;
- vector DB delta zero;
- Knowledge delta zero;
- no extracted source text in OpenWebUI file data/chat context;
- Pipe still receives usable opaque refs.

## 4. Why The Previous Guard Was Insufficient

Before the incident, the proven guard was mostly:

```text
customer_docs_loaded_to_knowledge=false
private_slices_loaded_to_knowledge=false
private_slices_not_visible_in_chat=true
```

That remains correct, but it misses native file upload processing.

The required guard is now:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
```

## 5. Superseded Product Path

The original candidate path was tested and rejected:

1. Create or use a dedicated Broker Reports synthetic test model.
2. Set `file_upload=true`.
3. Set `file_context=false`.
4. Keep Knowledge attachments empty.
5. Upload synthetic files through the intended OpenWebUI route.
6. Run the Broker Reports Gate 1 Pipe.
7. Verify no Knowledge delta, no vector delta and no extracted source content in chat.
8. Verify ArtifactStore persistence, retention, resolver checks and purge.

Runtime result: this did not pass on the target route.

The remaining acceptable direction is to keep the native backend primitive but mark the intake as project-owned:

```text
POST /api/v1/files/?process=false
```

That fallback must stay inside the OpenWebUI workflow, must not patch OpenWebUI core, and must not introduce a separate user-facing sidecar UI.

## 6. What Must Not Be Done

Do not resume normal customer bulk upload.

Do not disable global RAG for the whole OpenWebUI instance.

Do not treat empty Knowledge as proof of no vectorization.

Do not use customer files for the proof.

Do not run source-fact extraction, tax calculation, declaration generation, XLS/XLSX export, OCR or VLM.

Do not print raw filenames, file ids, private paths, rows, source text, secrets or env values in chat or reports.

Do not patch OpenWebUI core.

## 7. Created Outputs

Created:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_PER_MODEL_NO_RAG_UPLOAD_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_NO_RAG_SOURCE_INTAKE.blueprint.md`

This report:

- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_PER_MODEL_NO_RAG_UPLOAD_RESEARCH.report.md`

## 8. Sources

Official OpenWebUI docs:

- [API Endpoints - Uploading Files](https://docs.openwebui.com/reference/api-endpoints)
- [Models - Model Capabilities](https://docs.openwebui.com/features/workspace/models/)
- [RAG - File Context Capability](https://docs.openwebui.com/features/chat-conversations/rag/)
- [File Management](https://docs.openwebui.com/features/chat-conversations/data-controls/files/)
- [Environment Variable Configuration](https://docs.openwebui.com/reference/env-configuration/)

OpenWebUI community signals:

- [open-webui/open-webui#12228](https://github.com/open-webui/open-webui/issues/12228)
- [open-webui/open-webui#18431](https://github.com/open-webui/open-webui/issues/18431)
- [open-webui/open-webui#3556](https://github.com/open-webui/open-webui/issues/3556)

Local references:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_ARTIFACT_STORAGE_RETENTION.blueprint.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_RAW_UPLOAD_RAG_VECTORIZATION_GAP.report.md`
- `services/broker-reports-gate1-proof/`

## 9. Commands And Checks

Repository checks:

- inspected existing Stage 2 research, blueprints and reports;
- checked git status before writing;
- searched the project static OpenWebUI loader for `process=false`;
- compared project-owned static extension behavior against native OpenWebUI behavior.

External research:

- checked official OpenWebUI API, Models, RAG, File Management and environment configuration docs;
- checked relevant upstream issues as non-authoritative community signals.

Runtime boundary:

- used only read-only runtime/source evidence for this research stage;
- did not upload customer documents;
- did not change production model configuration;
- did not run customer smoke;
- did not expose private runtime values in this report.

## 10. Final Recommendation

Proceed to fallback proof before any customer-approved package upload.

Current operational status:

```text
NATIVE_NO_RAG_MODE_NOT_FOUND
PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED
CUSTOMER_APPROVED_UPLOAD_REMAINS_BLOCKED
```

Next proof target: project-owned source intake around `POST /api/v1/files/?process=false`, with vector delta zero and no extracted file data on synthetic files.
