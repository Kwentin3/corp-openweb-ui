# Broker Reports DOC25 Follow-up Plan v1

Status: `REQUIRED_BEFORE_CUTOVER`

Date: 2026-08-05

## Ordered actions

1. Design and implement immutable manifest/container/table chunks through the
   existing ArtifactStore, with independent hash/ref reconstruction tests.
2. Add an authenticated case/source version catalog and atomic expected-pointer
   activation/rollback transaction; do not expose unchecked store queries.
3. Add lifecycle tests for expiry, source/chat deletion cascades, superseded
   versions and rollback-window retention.
4. Execute one bounded private actual-corpus shadow run for all four formats;
   emit only privacy-scanned aggregate receipts.
5. Build a current DOC24 product-adapter comparison from existing parser output;
   no provider call, cropper rerun or parser-policy change.
6. Enumerate the exact 17 legacy handoff consumers by maintained entrypoint and
   migrate them in the cutover order.
7. Run the full current service suite to a terminal result and classify every
   failure as DOC25 regression, historical baseline or infrastructure.
8. Perform canary reads, forced rollback and observation-window proof.
9. Record an explicit cutover decision; only then enable reads by default.
10. After the rollback window, re-audit and delete only proven unreachable
    legacy writers/readers, generated outputs rebuilt from maintained sources,
    and obsolete tests/docs with redirect records where required.

Gate 3 remains out of scope throughout these actions.

