# OpenWebUI Stage 2 Customer Scope Broker Reports Refine Report

## 1. Summary

Refined the customer-facing Stage 2 scope document to add a limited broker
reports pilot. The new scope keeps the existing CloudCowork workflow shape:
customer-provided prompts, templates and methodology are transferred into
OpenWebUI, and the result is an XLS artifact for human review.

Final verdict:

`stage2_customer_scope_broker_reports_refined`

## 2. Files updated

Updated:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

Created:

- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CUSTOMER_SCOPE_BROKER_REPORTS_REFINE.report.md`

No code, compose or env files were changed.

## 3. Broker reports scenario added

Added `F13. Пилотный перенос сценария обработки брокерских отчетов из
CloudCowork в OpenWebUI`.

The scenario is intentionally limited:

- transfer the existing customer workflow from CloudCowork to OpenWebUI;
- use customer-provided prompts, templates and methodology;
- process text or machine-readable broker reports;
- produce an XLS artifact for manual specialist review and correction;
- test on a limited customer-provided sample set;
- document instructions and acceptance criteria.

The document now states that the XLS artifact is not an automatically verified
tax declaration and must be checked by the customer's specialist.

## 4. Input format boundary

The current Stage 2 broker reports pilot accepts only text or machine-readable
inputs:

- PDF with a text layer;
- XLS/XLSX;
- CSV;
- XML;
- text pasted into chat.

OCR, scans, photos and raster PDFs without a text layer are explicitly outside
the current Stage 2 scope and belong to a later stage.

## 5. Hour map update

Updated the Stage 2 hour map with a new row:

- `Пилотный брокерский сценарий`
- status: `к реализации`
- estimate: `12-24 ч`

The customer-facing document now states:

- baseline Stage 2 orientation: about 100 hours;
- original control corridor before the broker pilot: 80-120 hours;
- expected expanded volume with the broker pilot: about 105-140 hours;
- approximate overage above the original upper corridor: up to 20 hours.

## 6. Loyalty overage wording

Added transparent hour-overage wording without adding monetary values or
commercial calculation details.

The document explains that the broker pilot expands the original Stage 2 hour
volume, and that the contractor is ready to handle this expansion within the
already agreed contractual conditions as a loyalty gesture, without revising
those conditions.

## 7. Customer questions added

Added two quick-approval questions:

- whether 3-5 anonymized broker reports and 1-2 correct XLS examples are ready
  for the pilot;
- who on the customer's side checks the pilot broker scenario results.

Added a full broker reports / XLS artifact subsection requesting:

- 3-5 anonymized input broker reports;
- 1-2 correct XLS result examples;
- CloudCowork prompts, templates and methodology;
- expected XLS structure;
- a customer-side reviewer;
- acceptance criteria for the pilot sample set.

The OCR boundary is not phrased as a question; it is a scope boundary.

## 8. Future scope exclusions

The customer-facing document now clarifies that the current broker reports pilot
does not include:

- OCR;
- scan processing;
- photo processing;
- raster PDFs without a text layer;
- automatic declaration sending;
- FNS integration;
- tax methodology expertise;
- a separate tax platform;
- arbitrary non-standard documents;
- expansion to new input types without separate agreement.

## 9. Financial data scan

The updated files are intended to contain only hour ranges, agreed-condition
wording and loyalty-overage wording. No monetary values, hourly-rate wording or
commercial calculation details were added.

Required scan target:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CUSTOMER_SCOPE_BROKER_REPORTS_REFINE.report.md`

Result: no matches.

## 10. Checks

Checks run before commit:

- `git status --short`: one modified customer-facing document and this new
  report before staging;
- `git diff --check`: passed;
- financial data scan over the updated customer-facing document and this
  report: no matches;
- secret-like scan over the updated files: no matches;
- scope review: docs-only;
- no code, compose or env changes;
- no file deletion.

## 11. Final verdict

stage2_customer_scope_broker_reports_refined
