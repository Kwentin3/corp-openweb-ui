# OpenWebUI Stage 2 Docs Format and Gates Refine Report

## 1. Summary

Stage 2 docs are now formatted for review and ready for ADR work.
Implementation is still blocked by ADR approval, runtime proof and customer test
data.

The task was documentation-only. No code, provider setup, compose/env/scripts or
production changes were made.

## 2. Why refine was needed

The Stage 2 engineering domain was already approved by content, but several
markdown files were hard to review in raw/GitHub view:

- long glued paragraphs;
- wide tables in context/domain/acceptance docs;
- mixed ADR registry order and execution order;
- missing ADR stubs for the next decisions;
- no single implementation-gates document before ADR work.

The cleanup improves:

- GitHub review;
- line-based diff;
- grep/search;
- agent context reading;
- future ADR work;
- implementation planning.

## 3. Files reviewed

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/decisions/*.md`
- `docs/stage2/blueprints/*.md`
- `docs/stage2/research/*.md`
- `docs/reports/2026-06-18/*.md`

## 4. Files changed

Navigation and planning:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

Acceptance and ADR:

- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0001-data-policy-by-provider-class.md`
- `docs/stage2/decisions/ADR-0002-manager-visibility-policy.md`
- `docs/stage2/decisions/ADR-0003-chat-deletion-retention-audit.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md`
- `docs/stage2/decisions/ADR-0006-provider-model-catalog.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/decisions/ADR-0008-native-analytics-vs-hard-billing.md`

Format cleanup also touched PRD, customer summary, blueprints, research and
reports where long non-table paragraphs were wrapped.

## 5. Markdown cleanup performed

- Replaced wide `CONTEXT_INDEX.md` table with per-domain sections.
- Replaced wide `DOMAIN_MAP.md` table with per-domain cards.
- Replaced wide `ACCEPTANCE_MATRIX.md` table with per-requirement sections.
- Wrapped long plain paragraphs and list items.
- Kept markdown tables for financial/pricing and hour estimates to preserve
  numeric integrity.
- Kept table separators as markdown tables where tables remain.
- Preserved UTF-8 BOM for Russian markdown files.

## 6. ADR registry vs execution order

ADR registry order is now documented separately from execution/review order.

Registry order:

1. ADR-0001 Data Policy by Provider Class.
2. ADR-0002 Manager Visibility Policy.
3. ADR-0003 Chat Deletion, Retention and Audit.
4. ADR-0004 STT Proxy Boundary.
5. ADR-0005 OCR / VL OCR Pilot Scope.
6. ADR-0006 Provider Model Catalog.
7. ADR-0007 Web-search Provider.
8. ADR-0008 Native Analytics vs Hard Billing.

Recommended execution / review order:

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.
9. Runtime proof matrix.
10. Customer test data package.
11. Implementation backlog by slices.

Numbers are registry order. Execution order reflects implementation
dependencies.

## 7. ADR stubs created/updated

Updated to unified stub format:

- ADR-0001 Data Policy by Provider Class.
- ADR-0002 Manager Visibility Policy.
- ADR-0003 Chat Deletion, Retention and Audit.

Created:

- ADR-0004 STT Proxy Boundary.
- ADR-0005 OCR / VL OCR Pilot Scope.
- ADR-0006 Provider Model Catalog.
- ADR-0007 Web-search Provider.
- ADR-0008 Native Analytics vs Hard Billing.

All ADRs remain `Status: Proposed`.

## 8. Implementation Gates added

Created:

- `docs/stage2/IMPLEMENTATION_GATES.md`

The gates cover:

- Data Policy approval;
- STT Proxy Boundary;
- Provider Model Catalog;
- Web-search Provider;
- Manager Visibility and Retention policy;
- OCR / VL OCR pilot scope;
- runtime proof;
- customer test data package;
- implementation slices.

No gate is marked completed without evidence.

## 9. Navigation updates

Added Implementation Gates links to:

- root `README.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `docs/stage2/ROADMAP.md`.

Updated `docs/stage2/decisions/README.md` with registry order and execution
order.

## 10. Backlog updates

`ENGINEERING_BACKLOG.md` now explicitly includes:

- Ready for ADR: Data Policy, STT Proxy, Provider Model Catalog, Web-search,
  Manager Visibility, Chat Deletion/Retention/Audit, OCR/VL OCR, Native
  Analytics vs Hard Billing.
- Ready for runtime proof: OpenWebUI capability audit, RBAC/groups proof,
  no-delete UI/API proof, manager visibility matrix, native analytics proof,
  web-search smoke, STT proxy smoke plan, document extraction/OCR smoke after
  test data.
- Blocked by customer input: broker reports, good Claude result, audio/video,
  scanned PDF, PDF with tables, XLSX, group/role matrix, provider accounts/keys
  and data policy examples.
- Deferred/future: full masking/tokenization, local LLM/NER masking, hard
  billing/gateway, production OCR/layout pipeline, complex Excel parser,
  production DOCX/XLSX generation, full AD lifecycle/SCIM, immutable audit
  archive and deep OpenWebUI fork.

## 11. Non-goals preserved

- No implementation started.
- No code changed.
- No production changes.
- No provider setup.
- No `.env` or secrets read/printed.
- No compose/env/scripts changes.
- No PRD-1 semantic scope change.
- No financial figures changed.
- No future slices moved into Practical Stage 2.
- No production OCR/layout pipeline promised.
- No hard billing/gateway promised.
- No full data masking/tokenization promised.
- No deep OpenWebUI fork made mandatory.

## 12. Checks performed

Checks are recorded in the final agent response for the exact committed state.

Planned checks before commit:

- docs-only scope;
- no source/compose/env/scripts changes;
- root README navigation;
- Stage2 README navigation;
- `IMPLEMENTATION_GATES.md` exists and is linked;
- ADR-0001..ADR-0008 exist;
- ADR registry order and execution order separated;
- markdown table shape;
- no trailing whitespace;
- secret-like assignment scan;
- UTF-8 BOM spot check;
- `git diff --check`;
- push to `origin/main`.

## 13. Final status

Stage 2 docs are now formatted for review and ready for ADR work.
Implementation is still blocked by ADR approval, runtime proof and customer test
data.
