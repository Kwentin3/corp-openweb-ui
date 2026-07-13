# Broker Reports PDF Hybrid Reliability v2

Status: implemented and proven for private shadow use. Production Gate 2 selection remains unchanged.

## Boundary

```text
table crop + reversible compact source ledger
-> deterministic row windows with one shared column/header model
-> provider-calibrated pre-call guard
-> candidate-id placement only
-> deterministic window join and materialization
-> independent structural and provenance validation
-> monotonic repeatability ledger
-> typed non-authoritative arbitration
```

The model cannot return free-form values, source refs or business facts. OCR, whole-PDF provider transport, Knowledge/RAG/vector writes, other document formats, Gate 3 and production authority remain out of scope.

## Versioned artifacts

| Schema | Responsibility |
|---|---|
| `broker_reports_pdf_hybrid_compact_ledger_v2` | Reversible private dictionary, dense ids, exact source values/refs, word refs, bboxes and checksums. |
| `broker_reports_pdf_hybrid_row_window_plan_v2` | One table identity, immutable column/header model, ordered row ranges and exactly-once candidate ownership. |
| `broker_reports_pdf_hybrid_window_evidence_v2` | One bounded crop/package revision with shared-header reference and no column split. |
| `broker_reports_pdf_hybrid_provider_token_count_v2` | Exact provider `countTokens` result, local estimate, actual usage and calibration error. |
| `broker_reports_pdf_hybrid_structural_placement_validation_v2` | Independent row/column, empty, spatial, header and continuation placement checks. |
| `broker_reports_pdf_hybrid_continuation_contract_v2` | Group identity, ordered fragments, shared columns, repeated-header and row/subtotal policy. |
| `broker_reports_pdf_hybrid_continuation_validation_v2` | Fragment and joined coverage, order, column compatibility and duplicate accounting. |
| `broker_reports_pdf_hybrid_repeatability_ledger_v2` | Monotonic checksum history; a conflict cannot be cleared by later agreement. |
| `broker_reports_pdf_hybrid_shadow_arbitration_v2` | Explicit terminal decision across deterministic, 150-DPI, 200-DPI and structural signals. |
| `broker_reports_pdf_hybrid_reliability_summary_v2` | Safe aggregate without customer values, raw responses, crops or private paths. |

## Compact evidence

Each model id resolves exactly to the existing private source value, `source_value_ref[]`, `word_ref[]`, bbox and checksum. Repeated headers and word fragments are stored once in the private ledger and referenced through dense ids. The model-facing package is a projection of that ledger, not a lossy summary.

Every source candidate has exactly one owner window. Unknown, duplicated, unowned or silently dropped ids block before acceptance. Joining restores the original logical candidate order and is checked against the full ledger.

## Row windows

Windows are deterministic, row-aligned and balanced under candidate and grid limits. They share one immutable column/header hash. Each declares an exact inclusive/exclusive logical row range and contains every column for those rows. Column splitting and candidate truncation are forbidden.

The joined placement must be a complete rectangular logical table and pass the same materialization, provenance and structural gates as a single-package table.

## Provider-calibrated budget

The guard includes raster dimensions/DPI, image bytes, candidate text, task, schema and expected output grid. It first applies conservative local hard limits and then invokes the provider's exact token-count endpoint with the same text, schema and inline image used by generation. A generation call is forbidden when either guard fails.

Each attempt persists local estimate, exact provider count, actual input usage and count-to-actual error. Hidden retry and failover remain forbidden.

## Independent structural placement

Source authenticity does not imply correct placement. Acceptance additionally requires independent checks of:

- candidate-to-column and candidate-to-row compatibility;
- row ordering and grid boundaries;
- explicit empty-cell positions;
- repeated and merged header relations;
- fragment and joined continuation coverage.

Any incompatible placement returns a typed structural terminal even when all candidate values are authentic.

## Continuations

A required continuation is one logical group with ordered fragments, one shared column model, explicit repeated-header handling, a row-order contract and subtotal/duplicate policy. All fragment candidates and word refs must have exactly-once joined coverage. A passing page-local fragment cannot be accepted independently if a required sibling fragment blocks the logical group.

## Repeatability and arbitration

For the same evidence task, provider, model, config and schema, accepted placement checksums must match. Retries are explicit and bounded. A DPI revision is a separate task. Once any checksum conflict is recorded, `ever_conflicted=true` remains monotonic.

Allowed terminals are:

- `accepted_shadow`;
- `human_review_required`;
- `blocked_context_budget`;
- `blocked_non_repeatable`;
- `blocked_structural_placement`;
- `unsupported`.

There is no score-based or “best-looking” winner and no silent selection between revisions. Every accepted result remains `authority_state=non_authoritative` and cannot change `gate2_handoff_v0`.
