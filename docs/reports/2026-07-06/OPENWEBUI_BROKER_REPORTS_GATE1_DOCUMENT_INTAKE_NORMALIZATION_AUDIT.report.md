# OpenWebUI Broker Reports Gate 1 Document Intake Normalization Audit Report

Status: GATE1_DOCUMENT_INTAKE_NORMALIZATION_AUDIT_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, research/audit only

## 1. Constraints Observed

- Code was not changed.
- Runtime was not changed.
- OpenWebUI was not populated.
- Customer documents were not read, copied, uploaded or committed.
- Tax calculation was not performed.
- Declaration generation was not performed.
- XLS/XLSX export was not generated.
- LLM source-fact extraction was not designed as Gate 1 behavior.
- Separate user-facing sidecar UI was not recommended.
- Secrets, keys and environment values were not read or printed.
- Tax correctness was not claimed.

## 2. Documents And Sources Studied

Local repo documents:

- `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- `docs/stage2/proof/BROKER_REPORTS_DOCUMENT_INTAKE_AND_JSON_EXTRACTION_MVP_PROOF_PLAN.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- existing research docs under `docs/stage2/research/`

Public OpenWebUI sources:

- Knowledge, RAG, file management and API endpoint docs.
- Workspace Models, Prompts and Skills docs.
- Tools, Functions and Action Function docs.
- Document extraction integration docs for Docling, Apache Tika and Mistral OCR.

## 3. Audit Verdict

The Gate 1 user journey should stay OpenWebUI-native:

```text
client workspace/chat
-> file upload in OpenWebUI
-> explicit normalize action/prompt
-> safe report returned in the same chat
```

However, the normalization engine should not be implemented as prompt-only RAG/Knowledge behavior. Gate 1 needs deterministic technical outputs:

- original file hashes;
- MIME/container classification;
- parser readability profile;
- PDF text-layer/raster/table indicators;
- XLS/XLSX workbook metadata;
- CSV/TXT encoding and table shape;
- DOCX paragraph/headings profile;
- image/ZIP/unknown blockers;
- safe/private artifact separation.

These are backend/parser responsibilities, not LLM extraction responsibilities.

## 4. Recommended Architecture

Recommended integration:

```text
OpenWebUI Workspace Model
  + Gate 1 system boundary
  + slash prompt or Action button
  + optional admin-controlled Tool/OpenAPI Tool Server

Backend-only Gate 1 normalizer
  + deterministic file parsing
  + safe/private artifact split
  + taxonomy candidates
  + blocker classification

OpenWebUI chat
  + safe normalization report
```

This follows the repo's extension-first boundary: native OpenWebUI mechanisms first, then Actions/Tools/OpenAPI Tool Servers, then private helper only where parser reliability requires it. A customer-facing sidecar UI is not needed.

## 5. Why Not RAG-Only

RAG/Knowledge is useful for context and reference retrieval, but it is not an audit-grade Gate 1 normalizer because:

- OpenWebUI file processing is asynchronous and status-dependent.
- RAG chunks do not guarantee stable table slices or workbook metadata.
- Knowledge collections are persistent and should not silently become the home for raw customer source packages.
- Gate 1 must identify unreadable, raster, archive, encrypted and unsupported files before downstream extraction.
- Gate 1 must produce safe artifacts even when no text is extractable.

## 6. Backend Helper Conditions

A helper is required if the proof confirms any native gap in:

- byte-level SHA-256;
- PDF page/text-layer/raster/table profiling;
- XLS/XLSX sheet, formula and hidden-sheet detection;
- CSV delimiter/encoding inference;
- DOCX structural profiling;
- ZIP entry review;
- bounded normalized text/table slice generation;
- artifact retention and safe/private separation.

The helper should stay internal and be called from OpenWebUI. It should not add a separate user-facing workflow.

## 7. Safe Artifact Set

Recommended Gate 1 outputs:

- `private_file_registry.json` - private only, never committed.
- `safe_document_inventory.json` - safe ids, hashes, sizes, MIME/container/readability.
- `technical_readability_profile.json` - parser profiles and confidence.
- `normalized_text_slices.jsonl` - private by default.
- `normalized_table_slices.jsonl` - private by default.
- `document_taxonomy_candidates.json` - safe labels and confidence, no raw snippets.
- `normalization_blockers.json` - unsupported/raster/zip/encrypted/corrupt/OCR-needed blockers.
- `chat_visible_normalization_report.md` - safe summary returned to OpenWebUI chat.

## 8. Proof Workflow To Run Next

Use a synthetic and then customer-approved sample set:

1. Upload files through OpenWebUI chat.
2. Trigger Gate 1 normalization through the selected Action/Tool path.
3. Verify that file ids and original bytes are accessible under approved permissions.
4. Generate inventory, profiles, slices, taxonomy candidates and blockers.
5. Confirm the chat report is safe and contains no PII, raw local paths, account numbers, full financial rows or secrets.
6. Confirm raw customer files are not copied into the repository.
7. Confirm Knowledge is not used as raw customer document storage unless reviewed and approved.

## 9. Final Statuses

- `OPENWEBUI_NATIVE_WORKFLOW_ROUTE_SELECTED`
- `BACKEND_HELPER_CONDITIONALLY_REQUIRED`
- `NO_USER_FACING_SIDECAR_UI`
- `GATE1_NO_TAX_CALCULATION`
- `GATE1_NO_DECLARATION_GENERATION`
- `GATE1_NO_LLM_SOURCE_FACT_EXTRACTION`
- `CUSTOMER_SOURCE_DOCS_NOT_TOUCHED`
- `READY_FOR_GATE1_PROOF_PLAN`

## 10. Created Artifact

- `docs/stage2/research/BROKER_REPORTS_GATE1_DOCUMENT_INTAKE_NORMALIZATION_RESEARCH.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_DOCUMENT_INTAKE_NORMALIZATION_AUDIT.report.md`

## 11. Source Links

- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/chat-conversations/rag/
- https://docs.openwebui.com/reference/api-endpoints/
- https://docs.openwebui.com/features/extensibility/plugin/tools/
- https://docs.openwebui.com/features/extensibility/plugin/functions/
- https://docs.openwebui.com/features/extensibility/plugin/functions/action/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/skills/
- https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- https://docs.openwebui.com/tutorials/integrations/document-extraction/docling/
- https://docs.openwebui.com/tutorials/integrations/document-extraction/tika/
- https://docs.openwebui.com/tutorials/integrations/document-extraction/mistral-ocr/
