# OpenWebUI Stage 2 Customer Scope And Questions Refine Report

## 1. Summary

Refined the customer-facing Stage 2 scope document before sharing it with the
customer. The update adds an hour map, makes the work corridor explicit,
improves the customer-question flow, and adds safeguards against scope growth.

Final verdict:

`stage2_customer_scope_refined_for_customer_approval`

## 2. Files updated

Updated:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

Created:

- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS_REFINE.report.md`

No code, compose or env files were changed.

## 3. Hour map changes

Added the section `Часовая карта Stage 2` before the detailed effort table.

The customer-facing document now states:

- working orientation: about 100 hours;
- control corridor: 80-120 hours;
- already completed base: 40-55 hours;
- STT v2 work: 35-50 hours;
- user readiness work: 15-25 hours;
- final packaging: 5-10 hours.

The previous broad total for only new work was replaced with a scope-control
statement: current Stage 2 should stay inside the 80-120 hour corridor, and
larger additions should be simplified or moved to a later stage.

## 4. Customer questions structure

Added a new top-level section for quick approval:

- `Ключевые вопросы для быстрого согласования`

It contains 7 priority questions covering:

- first-launch transcript templates;
- pilot access for transcription;
- pilot access for Web Search;
- ownership of shared templates;
- simple DOCX expectations;
- test audio files;
- customer-side acceptance owner.

The full 28-question checklist was retained below as:

- `Полный список вопросов для согласования`

## 5. Scope control changes

Added the `Как контролируем объем` block. It explains that the current Stage 2
uses a limited-work principle:

- core functions are closed first;
- useful additions are handled only inside the remaining work corridor;
- large new functions move to a later stage or a separate agreement path.

The future-scope section was retained and no future direction was moved into
the current Stage 2.

## 6. Added safeguards

F4 safeguard:

- if standard OpenWebUI capabilities are insufficient, the parties separately
  agree on a minimal implementation method without creating a complex separate
  template editor.

F11 safeguard:

- the pilot access matrix records pilot rules and access settings only within
  the capabilities of the current OpenWebUI stand.

These safeguards keep the current stage from silently becoming a custom
template-editor or enterprise-access-control project.

## 7. Financial data exclusion check

The refined customer-facing document and this report include only hour
orientation and hour ranges. No monetary values, hourly-rate wording or
settlement terms were added.

Validation results before staging:

- whitespace check: passed;
- financial-expression scan over the updated customer-facing document and this
  report: no matches;
- secret-like pattern scan: no matches;
- UTF-8 BOM check: `239 187 191` for both files;
- docs-only staged diff check: passed.

## 8. Final verdict

stage2_customer_scope_refined_for_customer_approval
