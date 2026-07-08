# OpenWebUI Broker Reports Gate 1 Document Normalization Doc Packet Completion Report

Status: GATE1_DOC_PACKET_COMPLETED
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, docs-only completion

## 1. What Was Completed

The Gate 1 documentation package was completed around the accepted human-review direction:

```text
OpenWebUI customer chat/project
-> upload broker/customer files
-> explicit Normalize Documents action/prompt
-> backend-only normalization helper
-> safe/private normalization artifacts
-> safe report returned to the same chat
```

The package now has research, audit, blueprint, UX, artifact contracts, proof plan and completion report.

## 2. Documents Created

- `docs/stage2/blueprints/BROKER_REPORTS_DOCUMENT_NORMALIZATION_GATE.blueprint.md`
- `docs/stage2/ux/BROKER_REPORTS_OPENWEBUI_DOCUMENT_NORMALIZATION_UX.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`
- `docs/stage2/proof/BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_PROOF_PLAN.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_DOC_PACKET_COMPLETION.report.md`

Existing base documents used:

- `docs/stage2/research/BROKER_REPORTS_GATE1_DOCUMENT_INTAKE_NORMALIZATION_RESEARCH.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_DOCUMENT_INTAKE_NORMALIZATION_AUDIT.report.md`
- existing Broker Reports contract family docs under `docs/stage2/contracts/`
- safe source document index and safe intake report.

## 3. Human Review Notes Closed

Closed documentation gaps:

- Gate 1 blueprint now exists.
- OpenWebUI UX flow now exists.
- Gate 1 artifact contract proposal now exists.
- Gate 1 runtime proof plan now exists.
- Completion report now ties the package together.

The accepted architecture direction was preserved:

- OpenWebUI remains the user-facing workspace.
- Normalization starts from an explicit chat action/prompt/tool trigger.
- Backend helper remains internal only.
- Safe report returns to the same chat.
- Separate user-facing sidecar UI remains rejected.

## 4. Link To Previous Research

The previous research/audit established that OpenWebUI should own the user shell, while Gate 1 normalization needs deterministic parser/helper behavior.

The new documents convert that research into:

- blueprint: ownership, boundaries, validation gates and handoff;
- UX: practical OpenWebUI user flow and transcript example;
- artifact contracts: proposed JSON shapes and privacy rules;
- proof plan: small runtime proof checks and acceptance criteria.

## 5. OpenWebUI-Native UX Preservation

The UX remains OpenWebUI-native because:

- user creates the client chat/project in OpenWebUI;
- user uploads files through OpenWebUI;
- user triggers "Normalize Documents" in the same chat;
- user sees progress/status in the same product surface;
- user receives the safe normalization report in the same chat;
- next gate starts from a selected `case_group_id`.

## 6. Backend Helper Boundary

The backend helper is recommended only for deterministic normalization:

- original-byte hash;
- MIME/container detection;
- PDF/XLSX/CSV/TXT/DOCX technical profiles;
- ZIP member inventory;
- private text/table slices;
- taxonomy candidates;
- blocker classification;
- safe/private artifact separation.

It does not own a user-facing UI and does not perform tax calculation or declaration generation.

## 7. Separate User-Facing Sidecar UI Rejected

A separate customer-facing sidecar UI remains rejected because it would split the workflow, duplicate OpenWebUI upload/chat behavior, add extra auth/retention surfaces and complicate same-chat reporting.

The only acceptable sidecar/helper boundary in this package is backend-only.

## 8. Privacy Constraints Fixed In The Pack

The new docs repeat and operationalize these constraints:

- no raw customer filenames in safe/chat-visible artifacts if they may contain PII;
- no private local paths in safe/chat-visible artifacts;
- no account numbers or personal identifiers in safe/chat-visible artifacts;
- no full financial operation rows in chat-visible reports;
- normalized text/table slices are private by default;
- safe slice projections only after review/redaction;
- customer documents are not copied into the repo;
- customer documents are not committed;
- Knowledge is not populated automatically with raw customer source docs;
- no secrets, keys or environment values are read or printed.

## 9. What Remains Open

- Prove which OpenWebUI trigger path can access uploaded file refs reliably.
- Prove normalizer access to original bytes under approved boundary.
- Choose initial parser stack for PDF/XLSX proof.
- Define private artifact retention rules.
- Define ZIP unpack/review policy.
- Decide raster OCR policy before using external OCR on customer documents.

## 10. Next Step

Review and approve the Gate 1 doc pack for a small runtime proof:

```text
OpenWebUI upload
-> Normalize Documents
-> helper receives file ids / bytes
-> helper creates safe/private artifacts
-> safe report returns to the same chat
```

Run synthetic files first. Use customer-approved files only after the synthetic proof passes and the privacy boundary is accepted.

## 11. Final Statuses

```text
GATE1_DOC_PACKET_COMPLETED
GATE1_BLUEPRINT_READY
GATE1_UX_FLOW_READY
GATE1_ARTIFACT_CONTRACTS_READY
GATE1_PROOF_PLAN_READY
OPENWEBUI_NATIVE_UX_RECOMMENDED
BACKEND_NORMALIZATION_HELPER_RECOMMENDED
SEPARATE_USER_FACING_SIDECAR_UI_REJECTED
READY_FOR_GATE1_RUNTIME_PROOF_REVIEW
```
