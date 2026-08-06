# DOC21 — Research-first Gate 1 material adequacy audit

## Outcome

The agent directly compared all 24 full pages and evaluator overlays with both existing image-only Gate 1 JSON artifacts. All 48 cases were reviewed; none were excluded and no provider was called.

```text
DOC21_RESEARCH = COMPLETED
DIRECT_MATERIAL_SUFFICIENCY = NOT_CONFIRMED
BEST_GATE1_ARTIFACT = anthropic_opus
AUTOMATED_AUDIT = NOT_STARTED
CROP_RESEARCH_POLICY = DEFINE_MINIMUM_CRITICAL_CROP_CONTRACT
```

Phase A failed the eligibility rule for both providers. Phase B qualification and automated verifier calls were therefore not started.

## Provider comparison

| Provider | Sufficient | Noncritical | Critical | Ambiguous | Material | Phase B |
|---|---:|---:|---:|---:|---:|---|
| google_flash_lite | 1 | 0 | 23 | 0 | 1/24 | NO |
| anthropic_opus | 1 | 3 | 20 | 0 | 4/24 | NO |

Opus is the relative best artifact because it preserved the full statement identity in two contaminated Jefferies cases and preserved the Section 12(g) result in the StoneX case. It is not an acceptable Gate 1 artifact under the DOC21 threshold.

## Repeated findings

- Harmless defects: page numbers, issuer/form footers, blank spacer rows, and a secondary table serialized as an ordered note when its header/value associations remain explicit.
- Meaning-changing defects: lost table or consolidation scope, lost as-of versus years-ended basis, missing currency/unit/scale, missing multi-level headers, unbound numeric columns, missing continuation identity, and missing secondary reconciliation content.
- The dominant defect is not a particular cut-off string. Meaning-bearing context regularly remains outside the target boundary across issuers and table families.
- No critical case was attributed to a lost sign. Period and column binding were the repeated systematic losses.

## Crop-class result

The DOC16 counts remain 12 clean, 7 clipped, and 5 contaminated. The geometry label does not establish material adequacy: even the clean class produced only 1/12 material Google cases and 2/12 material Opus cases. Every clipped case was critical for both providers. Contaminated crops sometimes remained usable with Opus, but not enough to change the terminal result.

## Crop research decision

Continue only as a bounded definition of a minimum critical crop contract. The contract is generic: table identity/scope, period basis and column binding, currency/unit/scale, complete logical/continuation boundary, and material qualifiers. No issuer-, row-, or phrase-specific crop rule was created.

## Direct verdicts — all 48 cases

| Table | Provider | Crop | Verdict | Critical categories | Evidence |
|---|---|---|---|---|---|
| ACORNS_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, CURRENCY | The rows remain readable, but the result does not identify the statement, its as-of date, or the currency; the same values can therefore be assigned a different financial meaning. |
| ACORNS_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | Currency marks survive on selected rows, but statement identity and the as-of date do not; that context is necessary to interpret the balances. |
| ACORNS_T02 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, ROW_RELATION, UNSUPPORTED_VALUE | The level columns are visible, but measurement scope and date are absent and one investment is represented by an unsupported duplicate row. |
| ACORNS_T02 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | The row and level bindings are preserved, but the result omits the recurring-measurement scope and as-of date shown on the page. |
| ACORNS_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | Liability rows and level bindings survive, but the measurement scope and date are absent. |
| ACORNS_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | Liability rows and level bindings survive, but the measurement scope and date are absent. |
| JEFFERIES_T01 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE | Periods, scale, rows, and totals survive, but the result does not identify the consolidated statement of financial condition; consolidation and statement scope are material. |
| JEFFERIES_T01 | anthropic_opus | CROP_CONTAMINATED | NONCRITICAL_LOSS | — | The title, periods, scale, row bindings, and totals are preserved. Extra footer text is decorative and does not change the financial meaning. |
| JEFFERIES_T02 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE | Periods, scale, rows, and notes survive, but consolidated statement scope is missing. |
| JEFFERIES_T02 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE | The financial rows are preserved, but consolidated statement scope is missing; decorative footer contamination is secondary. |
| JEFFERIES_T03 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | The body values survive, but the title, scale, and year header lie outside the usable result, leaving the value columns unbound. |
| JEFFERIES_T03 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | The body values survive, but title, scale, and year binding are absent; footer contamination does not repair the missing context. |
| JEFFERIES_T04 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | This is a partial cash-flow continuation, but the result omits its statement identity, periods, and scale. |
| JEFFERIES_T04 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | This is a partial cash-flow continuation, but the result omits its statement identity, periods, and scale. |
| JEFFERIES_T05 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE, MISSING_VALUE, GROUP_OR_TOTAL_RELATION | The financing and disclosure rows are readable, but continuation identity and the complete secondary reconciliation inside the target are missing. |
| JEFFERIES_T05 | anthropic_opus | CROP_CONTAMINATED | NONCRITICAL_LOSS | — | The continuation title, periods, scale, signs, main rows, and secondary reconciliation values remain associated; flattening and footer text are noncritical for understanding. |
| JEFFERIES_T06 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE | Periods, scale, signs, groups, and totals survive, but consolidated earnings-statement scope is absent. |
| JEFFERIES_T06 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | TABLE_SCOPE | Periods, scale, signs, groups, and totals survive, but consolidated statement scope is absent; footer text is only decorative. |
| LPL_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | Rows, units, and years survive, but the page-level header distinguishing as-of metrics from years-ended metrics is missing. |
| LPL_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, PERIOD | Rows, units, and years survive, but the page-level header distinguishing as-of metrics from years-ended metrics is missing. |
| LPL_T02 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | UNIT_OR_SCALE | Title, dates, row bindings, and signs survive, but the page states that the reconciliation is in millions and the result omits that scale. |
| LPL_T02 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | UNIT_OR_SCALE | Title, dates, row bindings, and signs survive, but the result omits the millions scale; neighboring heading contamination is secondary. |
| LPL_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | PERIOD, UNIT_OR_SCALE | The reconciliation title, rows, and year numbers survive, but the years-ended basis and millions scale do not. |
| LPL_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | PERIOD, UNIT_OR_SCALE | The reconciliation title, rows, and year numbers survive, but the years-ended basis and millions scale do not. |
| LPL_T04 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, UNIT_OR_SCALE | Dates and rows survive, but the table identity and thousands scale supplied by the surrounding sentence are absent. |
| LPL_T04 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, UNIT_OR_SCALE | Dates and rows survive, but the table identity and thousands scale supplied by the surrounding sentence are absent. |
| STONEX_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE, MISSING_VALUE | The listed security row survives, but both legal scope headings and the adjacent no-registration result are missing. |
| STONEX_T01 | anthropic_opus | CROP_CLEAN | NONCRITICAL_LOSS | — | The security class, symbol, exchange, Section 12(g) heading, and its none result survive; the missing first scope heading is recoverable from the exchange-registration columns and causes no financial ambiguity here. |
| STONEX_T02 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | COLUMN_RELATION | The questions and marks survive, but the clipped YES/NO header makes the marks directionally ambiguous. |
| STONEX_T02 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | COLUMN_RELATION | The questions and marks survive, but the clipped YES/NO header makes the marks directionally ambiguous. |
| STONEX_T03 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, COLUMN_RELATION | The body rows survive, but the clipped multi-level header leaves values and percentage changes unbound to years and column roles. |
| STONEX_T03 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, COLUMN_RELATION | The body rows survive, but the clipped multi-level header leaves values and percentage changes unbound to years and column roles. |
| STONEX_T04 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | Only the tail of the statement survives; statement identity, periods, scale, and the opening value needed for the comprehensive-income relation are outside the result. |
| STONEX_T04 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | Only the tail of the statement survives; statement identity, periods, scale, and the opening value needed for the comprehensive-income relation are outside the result. |
| STONEX_T05 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | The crop begins inside financing activities; statement identity, years, scale, and continuation context are absent. |
| STONEX_T05 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | The crop begins inside financing activities; statement identity, years, scale, and continuation context are absent. |
| TRADEWEB_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE | Locations, sizes, expirations, and uses survive, but the result does not say that these are the principal offices rather than the broader set of rented locations listed below. |
| TRADEWEB_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | TABLE_SCOPE | Locations, sizes, expirations, and uses survive, but the result does not say that these are the principal offices rather than the broader set of rented locations listed below. |
| TRADEWEB_T02 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | Rows and scale survive, but the entire multi-level header is outside the result, so values and changes cannot be assigned to years and roles. |
| TRADEWEB_T02 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | Rows and scale survive, but the entire multi-level header is outside the result, so values and changes cannot be assigned to years and roles. |
| TRADEWEB_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | Scale and rows survive, but year and change headers are missing, leaving the numeric columns semantically unbound. |
| TRADEWEB_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | Scale and rows survive, but year/change headers are missing; an extra currency cell further destabilizes the column structure. |
| TRADEWEB_T04 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | The working-capital rows and scale survive, but the as-of dates are missing, so the two value columns cannot be assigned to reporting dates. |
| TRADEWEB_T04 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | The working-capital rows and scale survive, but the as-of dates are missing, so the two value columns cannot be assigned to reporting dates. |
| TRADEWEB_T05 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | The reconciliation rows and scale survive, but the year header is clipped from the result. |
| TRADEWEB_T05 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | PERIOD, COLUMN_RELATION | The reconciliation rows and scale survive, but the year header is missing; a clipped footnote fragment adds non-authoritative content. |
| OPPENHEIMER_T01 | google_flash_lite | CROP_CLEAN | SUFFICIENT | — | Title, all five year columns, both scale bands, row/value bindings, and the attribution footnote are preserved. |
| OPPENHEIMER_T01 | anthropic_opus | CROP_CLEAN | SUFFICIENT | — | Title, all five year columns, both scale bands, row/value bindings, and the attribution footnote are preserved. |

## Boundaries and accounting

```text
DIRECT_AGENT_REVIEW_COMPLETED = TRUE
DIRECT_CASES_TOTAL = 48
FAILED_CASES_EXCLUDED = 0
MANUAL_VERDICTS_REPORTED = TRUE
CROP_CLASS_EFFECT_REPORTED = TRUE
PROVIDER_COMPARISON_REPORTED = TRUE
AUTOMATION_ELIGIBILITY_DECISION_REPORTED = TRUE
MANUAL_RESEARCH_VERDICT = NOT_CONFIRMED
AUTOMATED_TESTS_STARTED = FALSE
NEW_PROVIDER_CALLS_TOTAL = 0
GATE1_CHANGED = FALSE
CROPPER_CHANGED = FALSE
GATE2_CHANGED = FALSE
GATE3_CREATED = FALSE
PRODUCT_PIPELINE_ACTIVATED = FALSE
```

The DOC21 ledger is a research record. It is not a Gate 3 contract, financial extractor, ontology, product API, or cropper implementation.
