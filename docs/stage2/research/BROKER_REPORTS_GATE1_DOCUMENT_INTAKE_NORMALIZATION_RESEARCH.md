# Broker Reports Gate 1 Document Intake & Normalization Research

Status: GATE1_RESEARCH_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 "Document Intake & Normalization"

## 1. Executive Verdict

Use OpenWebUI as the user-facing shell, not as the whole normalization engine.

Recommended route:

```text
OpenWebUI chat/project
-> user uploads customer source files
-> explicit Gate 1 normalize command/action
-> backend-only normalization helper receives OpenWebUI file ids
-> deterministic inventory/readability/slice/taxonomy artifacts
-> safe normalization report returned to the same chat
```

This keeps the user inside OpenWebUI and avoids a separate customer sidecar UI. The helper is justified because Gate 1 needs deterministic hashes, MIME/container detection, table/text slicing, PDF/XLSX technical profiling, ZIP/raster blockers, and safe artifact separation. Native RAG/Knowledge extraction is useful context, but it is not enough to be the authoritative Gate 1 contract.

## 2. Gate 1 Boundary

Gate 1 does:

- build a safe document inventory;
- identify file/container type and technical readability;
- produce normalized text/table slices for downstream proof workflow;
- assign conservative document taxonomy candidates;
- report unsupported, raster, encrypted, corrupt, archive and OCR-needed blockers;
- return a chat-visible safe package report.

Gate 1 does not:

- calculate NDFL;
- generate a declaration;
- generate XLS/XLSX;
- claim official tax correctness;
- perform source-fact extraction through an LLM;
- publish customer PII, raw local paths, full account numbers, raw financial rows, secrets or environment values.

## 3. OpenWebUI Native Capability Audit

### 3.1 Workspace Model

Workspace Models are the right native shell for the Broker Reports experience. They can bind a base model with instructions, Knowledge, tools, skills and capabilities. For Gate 1, a dedicated Workspace Model should:

- define the Gate 1 boundary in the system prompt;
- require safe reporting only;
- expose the approved normalization trigger;
- avoid automatic tax calculation wording;
- separate customer source documents from methodology/reference Knowledge.

### 3.2 Prompts

Workspace Prompts are useful as operator entrypoints, for example:

```text
/broker_gate1_normalize
/broker_gate1_report_package
```

Prompts alone should not be treated as a normalization engine. They can start the workflow and shape the chat answer, but file hashing, parsing, sheet/table profiling and blocker detection must be deterministic.

### 3.3 Files, RAG and Knowledge

OpenWebUI has native file upload, file manager, chat file usage, RAG and Knowledge workflows. These are valuable for keeping the user in one product surface.

Gate 1 should not rely on Knowledge/RAG as the source of truth because:

- processing is asynchronous and status-dependent;
- retrieval chunks are optimized for context, not audit-grade normalization;
- table fidelity and workbook metadata are not guaranteed by retrieval;
- customer source documents should not be silently promoted into long-lived Knowledge collections;
- Gate 1 needs stable file hashes and parser diagnostics, not only extracted text.

Recommended split:

- methodology, official instructions and stable reference docs may live in Knowledge after review;
- customer broker source files stay in the case/chat file flow and normalization artifact store;
- safe report snippets may be returned to chat;
- private file ids, original names, local paths and raw slices remain outside public docs.

### 3.4 Actions, Tools and OpenAPI Tool Servers

OpenWebUI extensibility gives three practical integration options:

| Option | Fit for Gate 1 | Notes |
| --- | --- | --- |
| Action Function | Good UX if it can access selected message/chat files in the deployed version. | User-triggered, chat-native, can emit progress/status. Needs runtime proof for file-id access. |
| Workspace Tool | Useful if the model calls a normalizer tool with file ids. | Keep tool admin-controlled; avoid arbitrary raw-content LLM extraction. |
| OpenAPI Tool Server | Best backend-helper boundary when a separate normalizer service is needed. | Keeps parser dependencies outside OpenWebUI image and allows typed request/response contracts. |

The preferred implementation path is Action or Tool in OpenWebUI that calls a backend-only normalizer. Deep OpenWebUI fork or custom user-facing UI is not justified for Gate 1.

### 3.5 Document Extraction Engines

OpenWebUI documents extraction can be backed by different engines:

- Default/native extraction: useful for basic text flow, but table and workbook profile guarantees must be proven.
- Apache Tika: broad text/metadata extraction across many file types; useful for text/metadata, weaker as a table contract.
- Docling: stronger candidate for structured document/table conversion and OCR configuration, but requires runtime setup and proof.
- Mistral OCR: useful for scanned PDFs/images only if data policy permits external OCR; it should not be the default Gate 1 path for sensitive broker documents.

For Gate 1, parser choice should be contract-driven:

- PDF profile: page count, text layer, raster likelihood, table candidates, OCR-needed flag.
- XLS/XLSX profile: sheets, hidden sheets, formulas, table dimensions, parser-readability.
- CSV/TXT profile: encoding, delimiter, row/column counts, machine-readable-table flag.
- DOCX profile: paragraph/headings estimate and document-type candidate.
- ZIP/image/unknown: blocker unless an explicit review policy exists.

## 4. Recommended OpenWebUI-Native Workflow

User workflow:

```text
1. User creates a client chat/project/workspace context in OpenWebUI.
2. User uploads broker documents to that chat/context.
3. User runs the Gate 1 normalization prompt/action.
4. OpenWebUI sends approved file ids to the normalizer.
5. Normalizer builds private and safe artifacts.
6. Same chat receives a safe normalization report.
7. Downstream proof workflow consumes safe artifact ids and private artifact refs.
```

Implementation boundary:

```text
OpenWebUI UI
  owns: chat, upload UX, model/prompt/action surface, chat-visible report

OpenWebUI file layer
  owns: uploaded file object and access control

Gate 1 normalizer/helper
  owns: byte-level hashing, MIME/container detection, parsers, slice generation,
        technical profile, taxonomy candidates, blocker classification

Artifact store
  owns: private registry and safe report artifacts with separate retention rules
```

## 5. Artifact Contract

Gate 1 should create these artifact families.

| Artifact | Visibility | Purpose |
| --- | --- | --- |
| `private_file_registry.json` | Private only, never committed | File ids, original filenames if needed, full storage refs, private paths, raw parser diagnostics. |
| `safe_document_inventory.json` | Safe | Document ids, hashes, size, modified time if available, sanitized filename/path hash, extension, MIME, container type, readable flag. |
| `technical_readability_profile.json` | Safe with redaction | PDF/XLSX/CSV/TXT/DOCX/image/zip parser-readiness profile. |
| `normalized_text_slices.jsonl` | Private by default | Bounded text slices with document refs; safe projections only after redaction/review. |
| `normalized_table_slices.jsonl` | Private by default | Bounded table slices; no full financial operation rows in chat-visible reports. |
| `document_taxonomy_candidates.json` | Safe if labels only | Primary class candidate, alternatives, confidence, reasons without PII snippets. |
| `normalization_blockers.json` | Safe | Unsupported/raster/encrypted/corrupt/archive/OCR-needed blockers and next review action. |
| `chat_visible_normalization_report.md` | Safe | Package readiness, counts, case groups, blockers and next steps. |

Safe report fields must use stable document ids and sanitized labels. Do not print full local paths, original raw customer filenames if they may contain PII, account numbers, raw financial rows or extracted personal identifiers.

## 6. Classification Approach

Gate 1 taxonomy candidates should be conservative and rule-assisted. The initial classifier can use:

- container type;
- parser-readable text/table presence;
- non-sensitive structural cues;
- safe workbook/sheet metadata after PII screening;
- known broker/report layout signatures;
- explicit official/methodology document signatures;
- manually reviewed override status.

If evidence is weak, assign `unknown_or_needs_review`.

Supported primary classes:

- `source_broker_report`
- `operations_table`
- `dividends_report`
- `withholding_report`
- `fees_report`
- `currency_rate_table`
- `official_form`
- `official_filling_instruction`
- `official_electronic_format`
- `methodology_instruction`
- `calculation_template`
- `tax_base_calculation`
- `explanation_template`
- `expected_output_example`
- `broker_help_article`
- `public_layout_sample`
- `synthetic_fixture`
- `customer_sample_pending_review`
- `unrelated`
- `unsupported`
- `unknown_or_needs_review`

The classifier should also emit:

- `can_be_source_evidence`: `yes | no | conditional`
- `can_be_methodology`: `yes | no | conditional`
- `can_be_loaded_to_knowledge`: `yes | no | after_review`
- `declaration_relevance`: `source_fact | official_requirement | methodology | review_output | layout_only | none`

## 7. Backend Helper Justification

A backend/helper is justified when any of these are required:

- exact SHA-256 over original uploaded bytes;
- deterministic MIME and container detection;
- PDF page count, text-layer and raster/scan classification;
- workbook sheet/hidden-sheet/formula detection;
- bounded text/table slice generation;
- ZIP entry inventory and archive policy;
- encrypted/corrupt/unsupported-file blocker handling;
- safe/private artifact split;
- parser dependency isolation from the OpenWebUI image.

The helper should be internal only. It must not expose a customer-facing UI.

## 8. Proof Plan Before Implementation

Minimum proof checks:

- OpenWebUI runtime version and enabled document extraction engines are recorded.
- Uploaded test files can be referenced by stable file ids from the chosen Action/Tool path.
- The normalizer can access original uploaded bytes under the approved trust boundary.
- Hashes computed by the normalizer are stable across repeated runs.
- PDF, XLSX, CSV/TXT, DOCX, image, ZIP, corrupt and encrypted samples produce expected profiles/blockers.
- Chat-visible report contains no raw local paths, PII, account numbers, full financial rows, secrets or environment values.
- Customer source files are not copied into the repository.
- Customer source files are not automatically promoted into Knowledge unless reviewed and approved.
- Async file-processing races are handled through status polling or direct byte access.

## 9. Risks And Open Questions

- Exact OpenWebUI deployment version and enabled extraction engine configuration must be confirmed.
- It must be proven whether the chosen Action path can reliably see selected chat file ids.
- Data retention for uploaded customer files and generated private artifacts needs a policy.
- External OCR providers need explicit data-policy approval before use.
- XLS/XLSX parser behavior must be tested on real broker-style workbooks.
- ZIP handling needs a conservative archive policy.
- Chat report generation must be tested against PII leakage and overclaiming.

## 10. Recommended Status Labels

- `OPENWEBUI_NATIVE_WORKFLOW_ROUTE_SELECTED`
- `BACKEND_HELPER_CONDITIONALLY_REQUIRED`
- `NO_USER_FACING_SIDECAR_UI`
- `GATE1_NO_TAX_CALCULATION`
- `GATE1_NO_DECLARATION_GENERATION`
- `GATE1_NO_LLM_SOURCE_FACT_EXTRACTION`
- `CUSTOMER_SOURCE_DOCS_NOT_COMMITTED`
- `READY_FOR_GATE1_PROOF_PLAN`

## 11. Sources

- OpenWebUI Knowledge: https://docs.openwebui.com/features/workspace/knowledge/
- OpenWebUI RAG: https://docs.openwebui.com/features/chat-conversations/rag/
- OpenWebUI API Endpoints: https://docs.openwebui.com/reference/api-endpoints/
- OpenWebUI Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- OpenWebUI Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- OpenWebUI Action Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/action/
- OpenWebUI Workspace Models: https://docs.openwebui.com/features/workspace/models/
- OpenWebUI Workspace Prompts: https://docs.openwebui.com/features/workspace/prompts/
- OpenWebUI Workspace Skills: https://docs.openwebui.com/features/workspace/skills/
- OpenWebUI File Management: https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- OpenWebUI Docling integration: https://docs.openwebui.com/tutorials/integrations/document-extraction/docling/
- OpenWebUI Apache Tika integration: https://docs.openwebui.com/tutorials/integrations/document-extraction/tika/
- OpenWebUI Mistral OCR integration: https://docs.openwebui.com/tutorials/integrations/document-extraction/mistral-ocr/
