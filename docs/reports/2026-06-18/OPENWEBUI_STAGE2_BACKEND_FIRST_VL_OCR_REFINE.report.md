# OpenWebUI Stage 2 Backend-first and VL OCR Refine Report

## 1. Summary

Stage 2 engineering domain refined for backend-first ADR/proof planning. Implementation should still wait until ADRs, runtime proofs and customer test data are reviewed.

The refine locks the approved review conclusions into `docs/stage2`: backend/server-side boundaries first, Data Policy before provider setup, Manager Visibility as a controlled security capability, No Delete separated from Retention/Audit, and VL OCR added as a pilot candidate for complex documents.

## 2. Why Refine Was Needed

The previous PRD-1 and Stage 2 documents were already usable for planning, but several items could still drift during implementation:

- STT could be started from UI/browser work before the server-side proxy boundary is clear.
- Provider setup could start before allowed/prohibited data classes are approved.
- Manager visibility could be misread as "руководитель видит всё".
- No-delete could be misread as retention, audit or immutable archive.
- OCR pilot could be overpromised as production-grade OCR/layout pipeline.
- VL OCR had value for scans/images/complex PDF, but was not represented as a separate research/pilot candidate.

## 3. Files Reviewed

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md`
- `docs/stage2/blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md`
- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md`
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md`
- `docs/reports/2026-06-18/OPENWEBUI_PRD1_STAGE2_AGENT_REVIEW.report.md`

No mandatory file was missing.

## 4. Files Changed

Navigation and domain docs:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`

Blueprints:

- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md`
- `docs/stage2/blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md`

Research:

- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md`
- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md`
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`

Decisions and acceptance:

- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0001-data-policy-by-provider-class.md`
- `docs/stage2/decisions/ADR-0002-manager-visibility-policy.md`
- `docs/stage2/decisions/ADR-0003-chat-deletion-retention-audit.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

Reports:

- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_BACKEND_FIRST_VL_OCR_REFINE.report.md`
- `docs/reports/2026-06-18/OPENWEBUI_PRD1_STAGE2_AGENT_REVIEW.report.md` remains part of the docs set because the current task uses it as review input.

## 5. Backend-first Changes

Added the delivery principle:

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs. Frontend/UI work follows after backend contracts are clear.

Also added the explicit guard:

Frontend must not become the place where security, provider keys, data policy, retention rules or access rules are decided.

Applied this to:

- STT proxy;
- OCR/VL OCR pipeline;
- Manager Visibility;
- No Delete / Retention;
- Provider setup;
- Usage analytics;
- Web-search.

The practical order is now ADR/policy decision, backend contract/runtime proof, minimal backend/API slice, UI/browser integration, then polish/instructions.

## 6. Data Policy Changes

`SECURITY_DATA_POLICY` and backlog now state that provider setup must not start before data policy by provider class is approved.

Created ADR-0001 as a Proposed decision draft. It separates:

- foreign providers;
- Russian providers;
- local/self-hosted paths;
- future masked/tokenized path.

It also separates data classes:

- public/low-risk;
- internal working data;
- personal data;
- financial/accounting/tax data;
- broker reports;
- meeting transcripts;
- secrets/API keys/passwords.

Full masking/tokenization remains future. The refine did not move masking into Practical Stage 2.

## 7. Manager Visibility Changes

Manager Visibility is now documented as a policy/security-controlled capability, not a simple permission toggle.

Created ADR-0002 as a Proposed decision draft. It defines:

- working chats vs personal/draft chats;
- manager visibility only for assigned group/workspace chats;
- no hidden access to unrelated personal chats;
- employee awareness / policy notice;
- separate admin visibility;
- runtime proof actors: Admin, Manager/РО, employee inside group, employee outside group.

Fallbacks remain conservative: explicit shared workspace model, export/audit, reporting, policy-only, minimal customization or deferred custom supervisory view.

## 8. No Delete vs Retention Changes

Created ADR-0003 as a Proposed decision draft and added the core distinction:

No Delete is not Retention. Retention is not Audit. Audit is not immutable archive.

The docs now distinguish:

- disabling user delete;
- retention;
- backup;
- audit log;
- immutable archive.

Runtime proof now requires UI/API delete behavior for non-admin, additive-permission check and admin override documentation. Retention decisions are separate from no-delete.

## 9. VL OCR Research Additions

Created `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`.

The research frames VL OCR as a candidate class for:

- scans;
- images/photos;
- complex PDFs;
- PDFs with stamps/signatures;
- broker reports;
- tables and table-like layouts.

The pilot is intentionally bounded. It does not promise production OCR/layout pipeline or "OCR works for everything" acceptance.

## 10. Updated ADR Sequence

Roadmap now lists the ADR sequence:

1. ADR-0001 Data Policy by Provider Class.
2. ADR-0002 Manager Visibility Policy.
3. ADR-0003 Chat Deletion, Retention and Audit.
4. ADR-0004 STT Proxy Boundary.
5. ADR-0005 OCR / VL OCR Pilot Scope.
6. ADR-0006 Provider Model Catalog.
7. ADR-0007 Web-search Provider.
8. Billing approach: native analytics vs gateway.

Recommended next sequence now starts with Data Policy, then STT Proxy, then Provider Model Catalog and Web-search Provider. This is intentional: provider setup and document/transcript workflows depend on data policy, while transcription is a priority scenario with a real backend boundary.

## 11. Updated Runtime Proof Needs

Runtime proof needs now include:

- deployed/staging OpenWebUI native capability audit;
- native analytics proof;
- STT proxy contract and runtime smoke;
- manager visibility test matrix;
- non-admin chat delete UI/API proof;
- admin override proof;
- sharing/group behavior proof;
- OCR/VL OCR extraction preview on customer test data.

## 12. Updated Customer Inputs Needed

Customer inputs now explicitly include:

- broker report test set;
- OCR/scanned document samples;
- example good Claude result or manual expected output;
- group/role visibility matrix;
- provider accounts and allowed provider classes;
- allowed/prohibited data examples;
- answer whether OCR/VL OCR samples may be sent to foreign or Russian/cloud providers;
- retention requirements for chats, files, transcripts and backups.

## 13. Non-goals Preserved

The refine did not start implementation and did not expand Practical Stage 2 into:

- full data masking/tokenization subsystem;
- local LLM/NER for sensitive data;
- production OCR/layout pipeline;
- immutable audit archive;
- hard billing/gateway;
- full AD lifecycle/SCIM;
- frontend/custom fork implementation.

No code, provider setup, compose/env/scripts or production changes were made.

## 14. Final Status

Stage 2 engineering domain is refined for backend-first ADR/proof planning. Implementation should still wait until ADRs, runtime proofs and customer test data are reviewed.
