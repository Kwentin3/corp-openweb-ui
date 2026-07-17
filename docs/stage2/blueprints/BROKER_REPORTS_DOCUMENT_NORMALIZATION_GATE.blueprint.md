# Broker Reports Document Normalization Gate Blueprint

Status: `SUPERSEDED_HISTORICAL_ARCHITECTURE`
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 "Document Intake & Normalization"

Authority note: this early decision blueprint is preserved for architecture
history. It is superseded for current routing by the
[global Gate 1 Normalization Pipeline](BROKER_REPORTS_GATE1_NORMALIZATION_PIPELINE.blueprint.md)
and, for the supported PDF child capability, by
[PDF Table Intake](BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md). Open questions,
trigger recommendations and readiness markers below are historical and do not
govern current runtime behavior.

## 1. Purpose

Gate 1 turns an uploaded customer document package into a safe, technical, reviewable intake layer.

It exists before any source-fact extraction because downstream extraction must know:

- which uploaded files exist;
- which files are technically readable;
- which files are source-evidence candidates, methodology/output artifacts or blockers;
- which slices are available for controlled downstream extraction;
- which files require review, OCR, archive handling or replacement.

Gate 1 is an intake and normalization gate. It is not a tax calculation gate.

## 2. Accepted Direction

Human review accepted the main architecture direction:

```text
OpenWebUI customer chat/project
-> upload broker/customer files
-> explicit Normalize Documents action/prompt
-> backend-only normalization helper
-> safe/private normalization artifacts
-> safe report returned to the same chat
```

OpenWebUI remains the user workspace. A backend helper is allowed only as an internal parser/normalizer boundary. A separate user-facing sidecar UI is rejected.

## 3. Scope

Gate 1 owns:

- document intake run identity;
- safe document inventory;
- MIME/container detection;
- file size, modified time and original-byte hash;
- duplicate detection by hash;
- technical readability profile;
- bounded text/table slice creation;
- ZIP member inventory where archive review is allowed;
- conservative document taxonomy candidates;
- blockers and review-state inputs;
- chat-visible safe normalization report.

Gate 1 may use existing safe intake artifacts such as:

- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INTAKE_INDEX.report.md`

Gate 1 must not use raw customer documents in repository docs.

## 4. Non-Goals

Gate 1 does not:

- calculate NDFL;
- perform LLM source-fact extraction;
- generate a declaration;
- generate XLS/XLSX;
- file anything with FNS;
- decide tax treatment;
- decide fee eligibility;
- decide foreign tax treatment;
- populate OpenWebUI Knowledge with raw customer documents automatically;
- expose raw filenames, private paths, account numbers or full financial operation rows in safe/chat-visible artifacts.

## 5. Why Gate 1 Goes Before Source-Fact Extraction

Source-fact extraction should only run after a selected case group and approved source-evidence candidates exist.

Gate 1 prevents these failures:

- extracting from templates or output examples as if they were evidence;
- extracting from ZIP archives before archive review;
- treating raster PDFs as text-layer evidence;
- ignoring duplicate files;
- mixing broker source documents with calculation workbooks;
- sending raw customer rows to a chat report;
- starting methodology-dependent extraction before the package is technically understood.

The next gate consumes Gate 1 references, not raw file paths.

## 6. Why OpenWebUI Remains The UI

The user already works in OpenWebUI. Gate 1 should preserve that workflow:

- client chat/project/workspace context;
- native file upload;
- explicit command/action inside chat;
- progress/status visible in the same product surface;
- safe report returned to the same chat;
- next prompt/action starts from the selected `case_group_id`.

This avoids creating a second place where the user must upload or inspect customer files.

## 7. Why Backend Helper Is Acceptable

The backend helper is acceptable because Gate 1 has deterministic parser responsibilities that are not a language-model task:

- byte-level SHA-256 over original uploaded bytes;
- MIME and container detection;
- PDF page/text-layer/raster/table profiling;
- XLS/XLSX sheet, hidden-sheet and formula profiling;
- CSV/TXT encoding and delimiter inference;
- DOCX structural profiling;
- ZIP member inventory;
- bounded slice generation;
- safe/private artifact separation.

The helper must be internal only. It is not a user-facing app.

## 8. Why User-Facing Sidecar UI Is Rejected

A separate user-facing UI is rejected because it would:

- duplicate OpenWebUI upload/chat/workspace behavior;
- split the customer workflow across products;
- create extra authentication, authorization and retention surfaces;
- make same-chat reporting harder;
- increase fork/maintenance risk before runtime proof.

If native OpenWebUI affordances are insufficient, the next escalation should be the smallest OpenWebUI extension path, not a separate customer app.

## 9. OpenWebUI-Native Elements

Gate 1 uses these OpenWebUI-native elements:

| Element | Role |
| --- | --- |
| Workspace Model | Holds Gate 1 boundary, safety instructions and approved tools/actions. |
| Prompt | Provides `/broker_gate1_normalize` or a named "Normalize Documents" fallback command. |
| Action | Preferred explicit user trigger when the runtime can access selected chat/file refs. |
| Tool | Allows the model to call the normalizer under admin-controlled policy. |
| OpenAPI Tool Server | Preferred backend boundary when helper parser dependencies are outside the OpenWebUI image. |
| Chat file upload | User uploads customer files in the client chat/project context. |
| Same-chat report | Safe normalization report is returned into the same conversation. |

Recommended UX: Action/Tool-triggered normalization from chat, with slash prompt as fallback.

## 10. Mandatory Gate Flow

```text
uploaded files
-> normalization run
-> safe document inventory
-> technical readability profile
-> normalized text/table slices
-> taxonomy candidates
-> blockers/review state
-> chat-visible report
-> next gate: source-fact extraction
```

## 11. Domain And Ownership Map

| Domain | Owns | Does not own |
| --- | --- | --- |
| OpenWebUI UI | chat, project/workspace context, upload UX, trigger UX, report placement | parser internals, tax logic |
| OpenWebUI file layer | uploaded file object and access control | public safe report contents |
| Gate 1 normalizer/helper | deterministic file profiling, slices, taxonomy candidates, blockers | tax calculation, source facts, declaration output |
| Artifact store | private registry and safe artifacts with retention policy | customer-facing app UI |
| Case package | safe refs to selected run/case group/artifacts | embedded raw files or full child artifacts |
| Next gate | source-fact extraction from approved refs | intake hashing or file discovery |

## 12. Artifacts Created

Gate 1 creates or updates:

- `broker_reports_normalization_run_v0`
- `broker_reports_document_inventory_v0`
- `broker_reports_technical_readability_profile_v0`
- `broker_reports_normalized_text_slice_v0`
- `broker_reports_normalized_table_slice_v0`
- `broker_reports_zip_member_inventory_v0`
- `broker_reports_document_taxonomy_candidates_v0`
- `broker_reports_normalization_blockers_v0`
- `broker_reports_chat_visible_normalization_report_v0`

The detailed proposal is in:

- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`

## 13. Handoff To Next Gate

Gate 1 hands off:

- `normalization_run_id`;
- `case_group_id`;
- selected safe `document_id[]`;
- `document_inventory_ref`;
- `technical_readability_profile_ref`;
- private slice refs available to the approved extraction process;
- `document_taxonomy_candidates_ref`;
- `normalization_blockers_ref`;
- `review_state_ref` when blockers exist.

The next gate must not use raw filenames or private paths. It starts from selected safe refs and the private artifact access boundary.

## 14. Privacy And Security Boundaries

Hard rules:

- raw customer filenames must not appear in safe/chat-visible artifacts if they may contain PII;
- private local paths must not appear in safe/chat-visible artifacts;
- account numbers and personal identifiers must not appear in safe/chat-visible artifacts;
- full financial operation rows must not be printed in chat-visible reports;
- normalized text/table slices are private by default;
- safe projections are allowed only after review/redaction;
- customer documents are not copied into the repository;
- customer documents are not committed;
- secrets, keys and environment values are not read or printed;
- Knowledge is not populated automatically with customer source documents.

## 15. Validation Gates

Gate 1 must pass these validation gates before the runtime proof can be accepted:

1. Uploaded file refs are visible to the chosen trigger path.
2. Normalizer can access original bytes under the approved trust boundary.
3. SHA-256 hashes are stable across repeated runs.
4. Safe inventory exists for every uploaded file.
5. Technical readability profile exists for every supported file.
6. Private slices are created only where parser output is available.
7. ZIP/raster/unsupported/corrupt/encrypted inputs create blockers.
8. Taxonomy candidates use the approved document taxonomy.
9. Chat-visible report has no raw filenames, private paths, account numbers or full financial rows.
10. Case package can reference the normalization run without embedding child artifacts.
11. Validation rules pass or fail closed.

## 16. Historical open questions

- Which OpenWebUI runtime trigger path can reliably access selected chat file ids: Action, Tool or OpenAPI Tool Server?
- Will the helper read original bytes through OpenWebUI APIs or through an internal file-store boundary?
- Which parser engine is the first proof default for PDF and XLSX?
- What is the retention policy for private slices?
- What archive policy is acceptable for ZIP members with signatures/XML/PDF payloads?
- Is external OCR allowed for customer documents, or is raster handling review-only for the first proof?

## 17. Historical readiness marker

```text
GATE1_BLUEPRINT_READY
OPENWEBUI_NATIVE_UX_RECOMMENDED
BACKEND_NORMALIZATION_HELPER_RECOMMENDED
SEPARATE_USER_FACING_SIDECAR_UI_REJECTED
READY_FOR_GATE1_RUNTIME_PROOF_REVIEW
```
