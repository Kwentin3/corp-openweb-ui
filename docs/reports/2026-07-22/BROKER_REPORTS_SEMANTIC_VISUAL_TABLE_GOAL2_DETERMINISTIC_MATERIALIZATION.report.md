# Broker Reports Semantic Visual Table Goal 2 Report

Date: 2026-07-22

Status: `GOAL_2_DETERMINISTIC_MATERIALIZATION: COMPLETED`

## Outcome

The application now deterministically wraps a valid semantic VLM response in a
private, hash-bound system envelope and converts ragged semantic rows into a
rectangular logical table. No additional model, provider stack, crop pipeline,
storage subsystem, review framework, OCR dependency, or Markdown parser was
introduced.

## Acceptance evidence

- `SYSTEM_METADATA: APPLICATION_OWNED` — table/source/crop IDs, provider/model,
  prompt/schema/request/response hashes, usage, latency, terminal state, and
  validator state are copied or derived from the maintained execution record.
- `SEMANTIC_ROWS_TO_LOGICAL_GRID: DETERMINISTIC` — repeated materialization of
  the same decision and evidence produces byte-equivalent objects and hashes.
- `MODEL_GENERATED_INDEXES: ZERO` — the response remains only `description` and
  `rows`; the factory creates every row and column index.
- `MODEL_GENERATED_SPANS: ZERO` — the factory assigns span 1 to every logical
  cell.
- `SHORT_ROW_NULL_PADDING: DETERMINISTIC` — maximum semantic row width defines
  the column count; shorter rows receive explicit null cells distinguishable
  from source-returned nulls.
- `CROP_LEVEL_PROVENANCE: PRESERVED` — document, PDF hash, page, crop, renderer,
  crop hash, selected execution, provider evidence, and transcription are
  cryptographically bound.
- `PHYSICAL_GEOMETRY_CLAIM: ZERO` — envelope, logical table, canonical contract,
  projection metadata, and Gate 2 handoff all state false.
- `GATE2_COMPATIBILITY: PASSED` — the semantic projection passes the existing
  TableProjection validator and is packaged and revalidated by the existing
  Gate2TablePackage factory with an explicit semantic origin/profile.

## Private evidence

The maintained runtime now returns raw provider response and parsed semantic
response in a separate private evidence collection. The Gate 1 package retains
that collection privately. Execution records and safe summaries still exclude
raw response content. Missing, duplicated, mismatched, or hash-tampered evidence
fails closed before materialization.

## Verification

- Full service suite: 1056 passed, 20 skipped. The five warnings are existing
  SWIG deprecation warnings.
- Future Gate 1, Gate 2, and Gate 2 Domain bundles: rendered and loaded from
  source in memory under the closed module order.
- Generated bundle and stage files: unchanged by design until Goal 7.
- New production dependencies: zero.
- Production route selection: unchanged and default-off pending Goals 5 and 6.
