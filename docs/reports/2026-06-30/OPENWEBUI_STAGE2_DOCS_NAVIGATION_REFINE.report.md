# OpenWebUI Stage 2 Docs Navigation Refine Report

Date: 2026-06-30.
Scope: docs-only navigation and historical-marking refine.

## 1. Summary

This refine reduces Stage 2 documentation drift risk without changing scope.
It marks legacy commercial docs as historical, makes the customer-facing versus
internal documentation split visible from the Stage 2 context index, separates
current contract-scope acceptance from broad PRD/future acceptance, and marks
the OCR/VL OCR V1 shortlist as historical because V2 exists.

## 2. Files updated

- `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md`
- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_DOCS_NAVIGATION_REFINE.report.md`

Checked but not edited:

- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md`

## 3. Historical notices added

Historical notices were added at the top of:

- `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`

Both notices point readers to:

- current customer-facing scope:
  `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- current internal handoff:
  `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`

The legacy `_150K` filenames were not renamed.

## 4. Context index updates

`docs/stage2/CONTEXT_INDEX.md` now has a short
`Stage 2 documentation representation` section near the top of the file.

It points to:

- the customer-facing source of truth;
- the internal contract/evidence handoff;
- the documentation representation model;
- the role of dated reports as evidence and historical context.

## 5. Acceptance matrix split

`docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` now starts with two explicit
levels:

- `Current Stage 2 contract-scope acceptance`;
- `Broad PRD-1 / future acceptance`.

The matrix also has `Scope marker` notes on major sections:

- `CURRENT_SCOPE`;
- `FUTURE_SCOPE`;
- `BROAD_PRD`.

This keeps existing detailed acceptance rows while making clear that broad
PRD-1 items are not automatically in the current Stage 2 contract slice.

## 6. OCR/VL OCR historical marking

Both V1 and V2 OCR/VL OCR shortlist files exist.

The V1 file now has a historical note pointing to:

- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md`

OCR/VL OCR remains research/future scope for the current Stage 2 contract
slice.

## 7. Financial scan results

The required financial-expression scan was run after edits over `docs` and
`README.md`.

Result:

- no content matches;
- no new financial values were added.

Classification:

| Finding | Classification | Action |
| --- | --- | --- |
| Required scan returned no content matches | false_positive not applicable | No rewrite needed. |
| `_150K` in legacy filenames | legacy_accepted | Keep filenames unchanged. |

## 8. Checks

Checks completed before commit:

- `git status --short`: docs-only markdown changes plus this report.
- `git diff --check`: passed; only Git LF/CRLF working-copy warnings were
  printed.
- Required financial-expression scan: no content matches.
- Secret-pattern scan on edited docs/report: no matches.
- BOM check: edited markdown/report files are UTF-8 with BOM.
- No code, compose or env files changed.

## 9. Remaining recommendations

1. Keep the customer-facing Stage 2 scope in
   `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`.
2. Keep internal evidence and risks in
   `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` and Stage 2 core
   docs.
3. Do not expand current acceptance by copying broad PRD-1 items into
   customer-facing scope.
4. Keep V1 research files available as history, but link current OCR/VL OCR
   work to V2.

## 10. Final verdict

`stage2_docs_navigation_refined`
