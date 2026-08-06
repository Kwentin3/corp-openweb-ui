# Broker Reports DOC25 Gate 2 Productization

Status: `BLOCKED`

Date: 2026-08-05

## Outcome

`CanonicalArtifactV1` is implemented as a non-financial Global Gate 1 shadow
candidate for PDF, HTML, CSV and XLSX. Construction reuses the existing
FullSource/table authorities; persistence reuses ArtifactStore; no provider,
RAG, vectorization, cropper or Gate 3 path was added.

Product cutover is not ready. The implemented storage slice is immutable,
private, file-backed and tenant-safe, but physical chunks, cross-run versions,
atomic activation and rollback are absent. No legacy consumer was migrated or
deleted.

## Contract and implementation

- Logical contract and Draft 2020-12 schema are versioned under
  `docs/stage2/contracts`.
- `CanonicalNormalizerFactory.create` is the sole assembly entrypoint.
- `CanonicalArtifactStoreFactory.create` delegates to the existing store.
- `CanonicalReaderFactory.create` is read-disabled by default.
- Product defaults are write=false, read=false, compare=true; compare is inert
  without a candidate write.
- Legacy `gate2_handoff_v0` remains authoritative.

## Format results

- PDF: focused page/line ordering and table-once test passed. Current DOC24
  product-corpus regression was not run, so critical-loss parity is unconfirmed.
- HTML: title, headings, text, links, list, table and order focused test passed.
- CSV: supported profile and duplicate-header preservation focused tests passed.
- XLSX: sheet order/visibility, formula, cached/raw value, merge and named range
  focused test passed.

## Storage, retention and safety

Canonical candidates use private `project_artifact_payload` records; compare
receipts are safe internal records. The original source is resolved before
candidate persistence and remains retained. Existing access, expiry, cascade
and two-phase purge policies apply. Tenant identity comes only from trusted
`ArtifactAccessContext`; cross-user resolution fails closed.

Chunk lists are currently empty. Cross-run version allocation, active-pointer
promotion, rotation and rollback receipts must be implemented before cutover.

## Migration and cleanup

The repository inventory found 17 files with literal legacy handoff usage and
mapped their consumer classes. Migrated classes: 0. Deleted files/components:
0. Research artifacts remain archived evidence; product factories and
ArtifactStore remain kept; legacy handoff and PDF compact dual-write are marked
for deprecation only after migration proof.

## Verification

- architecture/storage/full-source/retention/canonical/DOC25 safe evidence: 58 passed;
- DOC23/DOC24 safe-evidence validation: 9 passed;
- changed-file Ruff: clean;
- new DOC25 failures: 0;
- full current service suite: not confirmed.

Three implementation-time regressions were resolved before terminal proof:
generated-bundle parity after maintained-source edits, one collection syntax
error, and one XLSX helper name error.

Historical DOC24 full-suite timeout/failures were not rewritten or called a
pass. No private actual-corpus shadow run was executed.

## Decision

`READY_FOR_SHADOW` means bounded controlled shadow only. It does not authorize
canonical product reads, consumer migration defaults, legacy deletion or Gate 3.

Exact blockers and next actions are recorded in the acceptance matrix,
cutover strategy and follow-up plan.
