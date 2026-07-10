# Broker Reports Gate 1 Document Normalization Proof Plan

Status: GATE1_PROOF_PLAN_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 runtime proof planning

## 1. Purpose

Prove a small OpenWebUI-native Gate 1 workflow:

```text
OpenWebUI upload
-> Normalize Documents trigger
-> normalizer receives uploaded file refs
-> normalizer safely reads original bytes
-> normalizer creates Gate 1 artifacts
-> safe normalization report returns to the same chat
```

This is a proof plan, not production implementation.

The proof does not calculate NDFL, extract source facts through an LLM, generate a declaration, generate XLS/XLSX or file anything with FNS.

## 2. Preconditions

Record before proof execution:

- OpenWebUI runtime version.
- Enabled file upload settings.
- Enabled document extraction engine configuration.
- Chosen trigger path: Action, Tool or OpenAPI Tool Server.
- Whether trigger can see selected chat/message file ids.
- Whether normalizer can access original uploaded bytes under approved boundary.
- Storage/access boundary for private artifacts.
- Synthetic test files prepared first.
- Customer-approved files allowed only after synthetic proof passes and scope is approved.
- Knowledge population disabled for raw customer source documents unless review approves otherwise.
- No-RAG/no-vector source-intake guard proven for the exact Broker Reports Workspace Model route.
- Vector DB delta, document table delta, Knowledge delta and extracted file-content checks captured before customer-approved upload.

## 3. Test Set

Use synthetic files first:

| Test file | Purpose |
| --- | --- |
| PDF with text layer | Prove pages/text-layer profile and text slice creation. |
| Raster PDF | Prove OCR/review blocker and no fake text-layer claim. |
| CSV | Prove encoding/delimiter/table profile. |
| XLSX with multiple sheets/formulas | Prove workbook sheet/formula/hidden-sheet profile. |
| HTML/TXT | Prove text profile and bounded text slices. |
| ZIP with nested files | Prove member inventory and archive review blocker. |
| Corrupt/unsupported file | Prove fail-safe blocker. |
| Duplicate file | Prove stable hash and duplicate detection. |

Customer-approved files can be used later only under the same safety rules.

## 4. Proof Steps

1. Create or select a Broker Reports test chat/project in OpenWebUI.
2. Upload the synthetic test set.
3. Prove the source upload path does not enter native OpenWebUI RAG/vector processing, or record a fail-closed blocker.
4. Trigger "Normalize Documents" through the chosen path.
5. Capture the trigger request shape without printing secrets or raw file contents.
6. Confirm opaque file refs are visible to the trigger.
7. Confirm the normalizer can read original bytes through the approved boundary.
8. Generate `broker_reports_normalization_run_v0`.
9. Generate `broker_reports_document_inventory_v0`.
10. Generate `broker_reports_technical_readability_profile_v0`.
11. Generate private text/table slices where supported.
12. Generate ZIP member inventory where applicable.
13. Generate taxonomy candidates using `BROKER_REPORTS_DOCUMENT_TAXONOMY.v0`.
14. Generate blockers for raster, ZIP, corrupt, unsupported and unknown-role files.
15. Return `broker_reports_chat_visible_normalization_report_v0` to the same chat.
16. Validate safety and privacy rules.
17. Confirm the case package can reference the normalization run.

## 5. Checks

Required checks:

- file ids are visible to trigger;
- normalizer can access original bytes under approved boundary;
- hashes are stable across repeated runs;
- PDF text-layer profile is correct;
- raster PDF creates blocker;
- CSV encoding/delimiter/table profile is correct;
- XLSX sheet/formula/hidden-sheet profile is correct;
- HTML/TXT profile is correct;
- ZIP member inventory is correct and blocked until review;
- corrupt/unsupported file creates blocker;
- duplicate file is detected by hash;
- no raw local paths in safe report;
- no raw customer filenames/private paths in chat-visible output;
- no account numbers or personal identifiers in chat-visible output;
- no full financial rows printed;
- customer docs are not copied to repo;
- customer docs are not committed;
- Knowledge is not populated automatically;
- OpenWebUI vector DB delta is zero for source uploads;
- OpenWebUI file data does not contain extracted source text for no-RAG intake;
- source-fact extraction is not performed;
- tax calculation is not performed;
- declaration and XLS/XLSX generation are not performed.

## 6. Acceptance Criteria

The proof passes when:

1. Safe document inventory is created for every uploaded test file.
2. Technical readability profile is created for every supported file.
3. Private text/table slices are created where parser output exists.
4. Unsupported/raster/ZIP/corrupt blockers are created.
5. Taxonomy candidates are produced with safe document ids.
6. Chat-visible report is returned to the same OpenWebUI chat.
7. Chat-visible report contains only safe counts, refs and messages.
8. Case package can reference the normalization run through safe refs.
9. Validation rules pass or fail closed with explicit blockers.
10. No forbidden Gate 1 non-goals are performed or claimed.
11. No-RAG/no-vector source-intake guard passes before any customer-approved package upload.

## 7. Failure Modes

| Failure mode | Expected handling |
| --- | --- |
| Action cannot access file ids | Record as trigger-path failure; test Tool/OpenAPI route next. |
| File processing race | Add status polling or direct-byte access requirement. |
| File bytes unavailable | Block proof until approved storage boundary exists. |
| Parser fails on supported file | Create `parser_failed` blocker and keep inventory record. |
| Privacy violation in artifact | Stop report publication and mark proof failed. |
| Table extraction unreliable | Keep table slices private and lower confidence; do not advance as source evidence. |
| ZIP policy unclear | Block ZIP members until archive review policy is approved. |
| Raster OCR not approved | Mark raster files as OCR/review blockers. |
| Knowledge populated automatically | Fail proof; raw customer docs must not be auto-loaded into Knowledge. |
| Vector DB delta is non-zero | Fail proof; native no-RAG mode is not proven for customer upload. |
| Uploaded file data contains extracted source text | Fail proof; source upload entered native extraction. |
| OpenWebUI native delete leaves vector residue | Record source cleanup as not proven; require fallback cleanup plan. |

## 8. Evidence To Capture

Safe evidence only:

- OpenWebUI runtime/version note;
- selected trigger path;
- synthetic file count and safe ids;
- generated artifact refs;
- summary counts;
- validation result;
- chat-visible report screenshot or text with no PII;
- proof blockers and next decision.

Do not capture:

- raw uploaded file contents;
- raw filenames that may contain PII;
- private local paths;
- secrets, keys or environment values;
- full financial operation rows.

## 9. Next Decision

After proof:

1. Choose the stable trigger path: Action, Tool or OpenAPI Tool Server.
2. Decide the minimal helper scope.
3. Decide whether PDF/XLSX parsers are sufficient for proof-to-pilot.
4. Decide whether raster OCR remains blocked/review-only or gets an approved OCR provider path.
5. Decide retention rules for private slices.
6. Decide whether to proceed to proof implementation.

## 10. Status

```text
GATE1_PROOF_PLAN_READY
OPENWEBUI_NATIVE_TRIGGER_TO_BE_PROVEN
BACKEND_HELPER_SCOPE_TO_BE_PROVEN
CUSTOMER_DOCS_NOT_REQUIRED_FOR_SYNTHETIC_PROOF
READY_FOR_GATE1_RUNTIME_PROOF_REVIEW
CUSTOMER_APPROVED_UPLOAD_BLOCKED_UNTIL_NO_RAG_SOURCE_INTAKE_PROOF
```
