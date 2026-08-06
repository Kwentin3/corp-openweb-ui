# Broker Reports DOC25 Implementation Plan v1

Status: `PARTIALLY_IMPLEMENTED_SHADOW_ONLY`

Date: 2026-08-05

## Scope and authority

DOC25 consolidates neutral whole-document representation inside Global Gate 1.
It does not add a product gate and does not move financial interpretation out
of Gate 2. `FullSourceArtifactFactory.create` remains the parser authority,
`CanonicalNormalizerFactory.create` is the only canonical assembly boundary,
and `ArtifactStoreFactory.create` remains the storage authority.

No Knowledge/RAG, embeddings, vectorization, provider call, cropper rerun or
Gate 3 implementation is part of this plan.

## Delivered slice

1. Classified the pre-existing worktree and legacy representation consumers.
2. Added the versioned logical contract and Draft 2020-12 schema.
3. Added PDF, HTML, CSV and XLSX adapters over existing FullSource/table output.
4. Added immutable file-backed canonical candidate persistence and safe compare
   receipts through the existing ArtifactStore.
5. Added product valves for write/read/compare; defaults preserve legacy.
6. Added a read-disabled resolver boundary and typed failure behavior.
7. Added deterministic, schema, format, isolation and anti-drift tests.

## Remaining slices

1. Implement physical container/table chunks and independent chunk validation.
2. Implement authenticated cross-run version discovery and allocation.
3. Implement atomic expected-pointer promotion and rollback receipts.
4. Execute a controlled actual-corpus shadow run with private evidence outside
   Git and privacy-safe aggregate receipts in Git.
5. Prove current DOC24 regression parity against the product adapter without
   invoking providers or changing parser/cropper policy.
6. Migrate every maintained consumer behind `CanonicalReaderFactory` and prove
   rollback before enabling reads.
7. Remove legacy writers/readers only after the cutover and rollback windows.

## Slice proof boundaries

| Slice | Proof | Current result |
| --- | --- | --- |
| Repository baseline | 100% initial dirty-path classification plus dependency map | passed |
| Contract | schema metaschema check and instance validation | passed |
| Determinism | three rebuilds with different storage refs | passed |
| Format behavior | synthetic PDF/HTML/CSV/XLSX focused tests | passed |
| Tenant safety | authenticated tenant derived from context and cross-user denial | passed |
| Shadow compatibility | flags-off absence plus flags-on candidate/receipt | passed on synthetic input |
| Actual corpus | private controlled run | not run |
| Cutover | active pointer, all consumers, rollback | blocked |
| Cleanup | migration and rollback windows | not started |

## Risk register

- PDF order is derived from established page/line locators; current DOC24
  product-route parity still needs an actual-corpus shadow receipt.
- HTML semantics are captured by the same parser but have not been evaluated on
  a representative production HTML corpus.
- XLSX formulas/cached values are preserved in canonical metadata even where the
  legacy FullSource completeness status remains partial; this is shadow-only.
- CSV header detection for unsupported legacy profiles is explicit but relies
  on deterministic stdlib dialect/header heuristics and must remain visible in
  metadata.
- Candidate payloads are immutable and file-backed, but not physically chunked.
- `artifact_version=1` is run-local until cross-run version allocation exists.

## Stop conditions

Any unresolved private-source ref, schema/root-hash mismatch, cross-scope read,
non-contiguous order, hidden conflict, critical-loss indication, missing
rollback proof or legacy consumer without a migration path stops promotion.

