# Broker Reports DOC26 Gate 2 Shadow Readiness

Status: `COMPLETED`

Date: 2026-08-05

## Decision

`CanonicalArtifactV1` is the stable output of Gate 2. Its storage lifecycle and
private reader facade are complete, frozen PDF and four-format fixture
regressions pass, and the approved actual corpus completed without canonical
regression or unresolved comparison. Gate 2 is shadow-ready.

This is not a product read cutover. `gate2_handoff_v0` remains the only product
read authority, canonical write is controlled shadow-only, compare is enabled,
and canonical product read remains disabled. No Gate 3 work was created.

## Documentation truth

The current contract set is:

- `BROKER_REPORTS_PIPELINE_GATES.v1.md`;
- `BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md` and its schema;
- `BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md`;
- `BROKER_REPORTS_CANONICAL_READER.v1.md`;
- `BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md`;
- `BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`.

The old global Gate architecture blueprint is `SUPERSEDED` and points to the
current Pipeline Gates contract. Root/stage2 READMEs, service instructions,
factory docstrings, flag descriptions and architecture tests use the same
boundary: Gate 1 owns intake/custody/routing; Gate 2 owns format extraction,
canonical storage, versions, provenance and issues; Gate 3 is future projection
and financial semantics. Historical `Gate2*` financial module names are legacy
identifiers, not the current global gate definition.

DOC7-DOC25 terminal reports, receipts and evidence were left unchanged. No
historical hash was rewritten to make a test green.

## Storage lifecycle

The ArtifactStore adapter remains the sole SQLite/file owner. The canonical
facade now provides immutable cross-run versions, source/root hashes, previous
version links, single-payload and chunked physical layouts, logical container
and large-table partial reads, atomic batch publication, CAS activation,
idempotent activation, rollback, safe rotation receipts and all eight retention
classes. Trusted `ArtifactAccessContext` checks document/user/workspace/case or
chat scope and fail closed. Failed batches and purge tests leave no orphan
payloads or chunks.

## Frozen PDF regression

Both existing DOC24 arms were read from frozen artifacts; provider, parser,
cropper and VLM reruns were zero. Each arm accounted for 6 documents, 663 pages,
34,541 parser refs and 24/24 tables through
`CanonicalNormalizerFactory.create`. Ordering, continuation, multiple-table
page ordering, unresolved refs and hidden conflicts were all zero.

- Opus baseline: 23/24 sufficient or rescued, 0 critical, 1 material ambiguous.
- Google baseline: 22/24 sufficient or rescued, 0 critical, 2 material ambiguous.

The research/product differences are an expected schema change and the explicit
canonical issue representation; unexplained differences are zero.

## Multi-format regression

PDF, HTML, CSV and XLSX fixtures passed the real storage lifecycle in three
independent runs. Root hashes, ordered content and issue sets were stable.

- HTML preserved title, heading/paragraph/list/link order, two captioned tables
  and notes while excluding hidden, script, style and comment content.
- CSV covered UTF-8 and Windows-1251, comma and semicolon, quoted newlines,
  escaped quotes, empty cells, duplicate headers, headerless input and 1,501
  rows with raw deterministic strings.
- XLSX preserved workbook/sheet order, hidden sheets, formulas, cached/display
  and raw values, styles, dates/currency, merges, named ranges, two tables,
  spacer rows and coordinate provenance.

No adapter introduced financial fields or unsupported generated content.

## Actual-corpus shadow

The private actual corpus ran once: 16 attempted, 16 completed, 0 failed and 0
unaccounted across 8 PDF, 2 CSV, 4 HTML and 2 XLSX documents. The run wrote 172
components (11 single-payload, 5 chunked), produced 16 compare receipts, changed
no active pointer and left canonical product reads disabled. Total elapsed time
was 460.405801 seconds; canonical storage was 105,510,165 bytes.

Comparison accounting was 9 `EXPECTED_SCHEMA_DIFFERENCE` and 7 `AMBIGUOUS`.
Every ambiguity was terminally classified rather than silently excluded;
`CANONICAL_REGRESSION=0` and `UNRESOLVED=0`. Two synthetic malformed inputs were
terminally accounted. A safe-evidence classifier bug was corrected without
rerunning the private corpus; the receipt records one private attempt and two
synthetic accounting attempts.

## Repository state

The pre-DOC26 baseline was preserved separately: one worktree at
`e85fc78e1dbf664c814e6b774122337e2fd8fb64`, 216 dirty paths (20 tracked, 196
untracked), 11,009 ignored paths, and 44 ignored/private files of at least 10 MB
(998,538,107 bytes aggregate). The inventory lists and classifies all 216 paths,
including nine unrelated user changes and DOC26-overlap markers. It exports no
private paths or content.

Tracked private artifacts and raw provider payloads are zero. Three generated
product bundles were rebuilt from the maintained builder. No legacy file,
historical evidence or unknown user change was deleted. Research-only surfaces
remain retained/classified for later archive work; compatibility producers,
readers, schemas and fixtures remain in place.

## Consumer migration

The exact 17 literal legacy surfaces are assigned to product runtime,
background/operator, research, test and migration groups in the migration plan.
Each has a required canonical read, planned fail-closed adapter, tests, evidence,
rollback, wave and deletion condition. DOC26 migrated zero consumers.

Wave 0 can start after DOC26 is integrated into a delivery route that preserves
the classified pre-existing tree. Product waves additionally require explicit
read-cutover authorization, consumer-specific shadow receipts, observation
thresholds and a policy resolution for historical hash guards. Legacy removal
requires all waves, zero dependency proof and retention-window expiry.

## Terminal test accounting

Ruff passed. The final focused suite passed 123 tests with 6 warnings in 57.68
seconds. After the full run exposed one missing architecture declaration, the
declaration was added and its targeted suite passed 6 tests in 0.64 seconds.

The one full service run was terminal, not timed out: 2,885 passed, 5 skipped, 6
failed, 11 errors and 6 warnings in 879.86 pytest seconds (881.6 wall seconds).
Five failures are DOC8-DOC11 historical receipt-hash guards. Eleven errors are
the Type-First audit's historical authority-map hash pin. The sixth failure was
the DOC26 module declaration fixed and retested after the run. New unexplained
failures are zero; the full suite is not represented as green.

## Final state

```text
CANONICALARTIFACTV1_CONTRACT = STABLE
CANONICAL_STORAGE_LIFECYCLE = COMPLETE
ACTUAL_CORPUS_SHADOW = PASSED
DOCUMENTATION = CURRENT_AND_CONSISTENT
REPOSITORY_STATE = CLASSIFIED_AND_SAFE
CONSUMER_MIGRATION = READY_TO_START
PRODUCT_CUTOVER = NOT_PERFORMED
GATE3 = NOT_STARTED
```
