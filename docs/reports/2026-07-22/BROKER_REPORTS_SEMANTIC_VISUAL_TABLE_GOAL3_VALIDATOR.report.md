# Broker Reports Semantic Visual Table Goal 3 Report

Date: 2026-07-22

Status: `GOAL_3_SEMANTIC_VALIDATOR: COMPLETED`

## Outcome

The maintained runtime now uses one bounded deterministic semantic validator
for the simplified model response. The same validator is composed at the
private envelope boundary to bind exact raw JSON, parsed response, selected
execution, provider response, and immutable crop lineage.

## Acceptance evidence

- `SEMANTIC_SCHEMA_VALIDATION: STRICT` — valid JSON, exact root fields,
  description, non-empty rows, row arrays, string/null cells, and absence of
  nested values are enforced.
- `GEOMETRIC_VALIDATION: ABSENT` — the validator contains no span, coordinate,
  bounding-box, physical-grid, or review-receipt requirements and reports
  `geometric_validation_performed=false`.
- `HIDDEN_REPAIR: ZERO` — comments, prose, code fences, raw/parsed mismatch,
  numeric coercion candidates, nested values, and invalid shapes fail; the only
  response-copy helper returns an unchanged deep copy.
- `DESCRIPTION_BUDGET: ENFORCED` — 120 tokens under the versioned
  `unicode_word_or_punctuation_v1` counter plus a 2,048-character hard guard.
- `ROW_COLUMN_AND_TEXT_BOUNDS: ENFORCED` — 200 rows, 200 columns per row, and
  12,000 characters per cell remain closed upper bounds.
- `SCHEMA_VALID_EQUALS_CONTENT_CORRECT: NOT_CLAIMED` — passing results explicitly
  set source-content and financial-correctness claims to false.

## Runtime behavior

The provider adapters already expose exact generated JSON text privately. The
runtime now validates that text before accepting `json_output`; explanation
outside the object or raw/parsed mismatch terminates as
`semantic_schema_violation`. Raw text is retained only in hash-bound private
provider evidence and remains absent from execution records and safe summaries.

## Verification

- Full service suite: 1074 passed, 20 skipped. The five warnings are existing
  SWIG deprecation warnings.
- Focused validator/runtime/materialization/authority suite: 45 passed.
- Future Gate 1, Gate 2, and Gate 2 Domain bundles: rendered and loaded from
  source in memory under the closed module order.
- Generated bundle and stage files: unchanged by design until Goal 7.
- New production dependencies: zero.
