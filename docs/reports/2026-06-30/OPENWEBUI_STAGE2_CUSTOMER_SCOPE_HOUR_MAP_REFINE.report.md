# OpenWebUI Stage 2 Customer Scope Hour Map Refine Report

## 1. Summary

Refined the customer-facing Stage 2 scope document after adding F13. The update
removes potential hour-map ambiguity by stating that group estimates are
priority-management guides, not separate mechanically summed commitments.

Final verdict:

`stage2_customer_scope_hour_map_refined`

## 2. Files updated

Updated:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

Created:

- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CUSTOMER_SCOPE_HOUR_MAP_REFINE.report.md`

No code, compose or env files were changed.

## 3. Hour map clarification

The hour map now states that the group ranges are working guides for priority
management. They are not mechanically summed as independent stages.

The expanded Stage 2 orientation remains:

- baseline before the broker scenario: about 100 hours;
- original control corridor: 80-120 hours;
- expanded corridor after adding the broker scenario: about 105-140 hours.

The F1-F13 composition was not changed.

## 4. Timebox wording

Added explicit timebox wording:

- core functions are closed first;
- useful additions are delivered in a basic form inside the working corridor;
- if a point starts expanding, it is simplified to a basic variant or moved to
  a later stage.

The same principle was also reflected below the detailed effort table, so the
customer-facing document does not invite a mechanical sum of all group maxima.

## 5. F13 XLS wording update

Softened the F13 XLS wording.

Before, the text emphasized that the file is not an automatically verified tax
declaration. The updated wording says that XLS is a working draft for the
customer specialist to review, and that the final result appears only after
manual review and correction if needed.

The human-in-the-loop boundary remains unchanged.

## 6. Financial scan

The updated files are intended to contain hour ranges and agreed-condition
wording only. No monetary values, hourly-rate wording or commercial calculation
details were added.

Required scan target:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CUSTOMER_SCOPE_HOUR_MAP_REFINE.report.md`

Result: no matches.

## 7. Checks

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

## 8. Final verdict

stage2_customer_scope_hour_map_refined
