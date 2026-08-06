# Broker Reports DOC25 Cutover Strategy v1

Status: `NOT_READY`

Date: 2026-08-05

## Rule

Canonical read activation is an explicit product decision after all proof
gates. A merge, schema pass, synthetic test, historical DOC24 receipt or shadow
write does not authorize cutover.

## Required sequence

1. Complete physical chunking and cross-run immutable version allocation.
2. Implement authenticated active-version lookup and atomic compare-and-set
   promotion/rollback.
3. Pass actual-corpus PDF/HTML/CSV/XLSX shadow comparison with terminal source
   accounting and no critical loss.
4. Pass current DOC24 product-adapter regression without provider or cropper
   policy changes.
5. Inventory every legacy consumer and migrate it behind the one reader API.
6. Run consumer contract tests with canonical reads off, shadowed, then on in a
   canary scope.
7. Exercise rollback to legacy and to a previous canonical version.
8. Observe the configured rollback window with no unresolved blocker.
9. Record an explicit cutover decision and only then change product defaults.

## Consumer migration order

1. diagnostic/offline comparison consumers;
2. Gate2 input-readiness compatibility adapter;
3. source-unit/domain routing consumers;
4. maintained Gate2 runtime consumers;
5. scripts and operational tooling;
6. deletion of legacy writer/reader code after the rollback window.

No consumer may read ArtifactStore records, SQLite or payload paths directly.
No silent fallback is allowed; compatibility fallback must be typed and
observable.

## Current blockers

- physical chunk/read model incomplete;
- cross-run versions and active pointer absent;
- actual-corpus shadow run not executed;
- DOC24 current product regression not confirmed;
- maintained legacy consumers not migrated;
- rollback and canary evidence absent;
- full current service suite not confirmed.

Therefore `CANONICAL_GATE2_READ_ENABLED` remains false and legacy cleanup is
forbidden.

