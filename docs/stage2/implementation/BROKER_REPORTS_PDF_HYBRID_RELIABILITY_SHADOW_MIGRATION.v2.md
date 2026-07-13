# Broker Reports PDF Hybrid Reliability Shadow Migration v2

Status: Goal 3 closure implemented. Eligible for a separately approved Gate 2 shadow E2E integration; not connected to production Gate 2.

## Runtime ownership

`PdfHybridReliabilityShadowFactory` is the only Goal 3 orchestration entrypoint. It owns compact-ledger construction, row-window packages, calibrated provider calls, deterministic joins, independent structure validation, continuation validation, repeatability recording and arbitration. Stage factories remain independently testable and are not bypassed.

The controlled runner is `scripts/local_pdf_hybrid_reliability_proof.py`. It reuses the Goal 1 compact document and the five Goal 2 hybrid targets. All crops, provider responses, source values and detailed ledgers stay in private ArtifactStore payloads; only the safe aggregate is reportable.

## Roll-forward sequence

1. Keep current Goal 2 Pipe flag disabled by default and preserve the unchanged production Gate 2 bundles.
2. Run Goal 3 through the private proof entrypoint or a future explicitly enabled shadow E2E adapter.
3. Require provider qualification and exact pre-call token count for each window.
4. Persist every window, attempt, join, structural result, repeat record and terminal arbitration.
5. Permit only `accepted_shadow`; retain all other terminals as evidence without fallback selection.
6. Add a Gate 2 shadow consumer only in a separate change with its own feature flag and regression proof.

## Failure semantics

- Budget failure stops before generation as `blocked_context_budget`.
- Unknown, missing, duplicated or unowned candidates fail closed.
- Full-grid provenance does not override a structural placement failure.
- A required continuation blocks as one logical group if any fragment fails.
- Same-evidence checksum disagreement is permanently recorded as `blocked_non_repeatable` for that task/class/model.
- Provider, table and fragment failures do not erase sibling artifacts.
- No retry or DPI revision is implicit.

## Rollback

Goal 3 is additive and private. Rollback consists of disabling or removing the future shadow adapter while retaining versioned evidence. Production Gate 2 requires no rollback because this migration does not modify its bundle or selection path.

## Promotion boundary

`BROKER_REPORTS_PDF_HYBRID_VERTICAL_READY_FOR_GATE2_SHADOW_E2E` means the contracts can be consumed by a separately authorized non-authoritative Gate 2 shadow route. It does not mean production selection, cleanup, customer-visible correctness, or authority to replace deterministic tables.
