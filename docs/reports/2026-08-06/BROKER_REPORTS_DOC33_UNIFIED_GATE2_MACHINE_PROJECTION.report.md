# Broker Reports DOC33 Unified Gate 2 Machine Projection

Date: 2026-08-06

## Decision

```text
DOC33_PROGRAM = COMPLETED
GATE2_MACHINE_PROJECTION_AUTHORITY = REFINED
SUPPORTED_FORMATS = PDF_HTML_CSV_XLSX
CROSS_FORMAT_CONFORMANCE = PASS
ONE_PUBLIC_CONTRACT = CONFIRMED
ONE_PUBLIC_READER = CONFIRMED
DOWNSTREAM_FORMAT_OPACITY = CONFIRMED
EVIDENCE_BOUNDARY = CONFIRMED
LLM_PROJECTION_BOUNDARY = CONFIRMED
CROSS_FORMAT_EQUIVALENCE = CONFIRMED
DURABLE_ROUNDTRIP = CONFIRMED
GATE2_UNIFIED_MACHINE_PROJECTION = CONFIRMED
WAVE2_CUTOVER = NOT_PERFORMED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
GATE3 = NOT_STARTED
```

## 1. Authority

The existing authority is sufficient and remains singular:

- schema and DTO: `CanonicalArtifactV1` / `canonical_artifact_v1`;
- builder: `CanonicalNormalizerFactory.create`;
- lifecycle: `CanonicalArtifactStoreFactory.create`;
- reader: `CanonicalReaderFactory.create`.

DOC33 did not create a schema, reader, store, parser or engine. It minimally
refined the existing validator, generalized the existing reader-only research
renderer and added one normative boundary summary:
`BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md`.

## 2. Cross-format conformance

PDF, HTML, CSV and XLSX use the same envelope, version identity, ordered
container/node model, `TABLE` entity, issue model and provenance model. The
machine-readable matrix is
`BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.safe.json`.

Explicit source-induced differences are retained rather than hidden:

- root/boundary containers (`DOCUMENT/PAGE`, `DOCUMENT/SECTION`, `DATASET`,
  `WORKBOOK/SHEET`);
- source format identity and locators;
- PDF page metadata, CSV dialect, XLSX sheet/formula/cache metadata;
- table header role only when the source proves that role.

CSV and XLSX do not synthesize standalone heading/list/note nodes. This is
absence in the source data model, not a second public contract. Ordered table
cells and values remain common.

## 3. Refinements made

The shared canonical validator now rejects:

- a source format/root-container mismatch;
- unknown container or node types;
- unresolved parent, source, issue or table-cell references;
- provenance that does not link to the authenticated source artifact;
- blocking issues in any supported format;
- a non-empty input that yields no meaningful machine-content node.

PDF retains the stricter counts-only source-atom receipt. The XLSX streaming
validator applies the same meaningful-content, source-link and blocking-issue
rules without materializing the full workbook.

The former PDF-only proof renderer is now
`render_neutral_canonical_projection`. It traverses only common canonical
containers/nodes and reconstructs streamed tables from canonical cells when
rows are not materialized.

The Wave 2 shadow output no longer exposes `source_format`. Format remains in
canonical source identity for audit but is not a consumer input/output
requirement.

## 4. Remaining format-specific branches

No mandatory format branch exists in the unified reader, neutral renderer or
Wave 2 shadow consumer contract. Format branches remain where allowed:

- Gate 2 extraction/normalization adapters;
- PDF-specific research/compatibility diagnostics;
- legacy product paths retained behind the no-cutover boundary.

Those paths do not define the canonical public contract. Consumers migrated in
DOC33: zero.

## 5. Cross-format equivalence

One equivalent ordered 3x2 table was normalized, persisted, activated and read
as PDF, HTML, CSV and XLSX. All four artifacts used `canonical_artifact_v1` and
produced one identical ordered six-cell logical signature. All four neutral
projections were non-empty. Both single-payload and chunked layouts were
exercised.

Root hashes, source identity, root container subtype, provenance locator shape
and physical layout were intentionally not compared. The machine-readable
receipt is `BROKER_REPORTS_DOC33_SEMANTIC_EQUIVALENCE.safe.json`.

## 6. Completeness

`assess_canonical_completeness` is evaluated after reader reconstruction. It
requires meaningful content or an explicit proved-empty disposition, complete
container/node/issue/table-cell source refs, complete provenance links and zero
blocking issues. New tests show all four non-empty zero-content candidates fail
closed.

The retained-cohort proof read 16/16 artifacts through one reader:

- 8 corrected PDF active versions from the DOC32 isolated store;
- 4 HTML, 2 CSV and 2 XLSX active versions from the isolated non-PDF restore.

All 16 root hashes matched, all 16 completeness assessments passed and all 16
neutral projections were non-empty. No document identity or content entered
safe output.

## 7. Evidence linkage and boundary

Every public container, node, issue and table cell resolves to compact
in-artifact provenance. Every provenance record links to the authenticated
source artifact reference. Store publication verifies that source reference in
the trusted artifact graph.

Original bytes, parser units, coordinates, crops, proposals and raw provider
payloads remain private Full Evidence. The canonical reader and neutral
renderer do not read them. Provider output remains evidence/proposal, never
canonical authority.

## 8. Neutral LLM-friendly verification

The proof renderer accepts only validated reader-returned
`CanonicalArtifactV1`. It preserves container order, text, headings, lists,
tables, notes, conflicts, ambiguities and unrepresented issues. It has zero
format branches, source resolver, raw source, private evidence, provider or
financial-semantic dependency.

This helper is non-active proof tooling. It is not persisted as a Gate 2
output, is not a prompt/product API and does not start Gate 3.

## 9. Storage and durability

The current reader proof exercised single and chunked layouts. Focused DOC31
tests re-proved `xlsx_row_chunked_v1` publication and reader behavior. Existing
DOC31/DOC32 target evidence remains applicable because DOC33 did not change
storage, active-pointer, restart, recreation, backup or restore code:

- the 16-document cohort retained active roots across restart/recreation and
  isolated restore;
- the corrected eight PDFs retained root/node/table parity and 76 components;
- missing chunks and ordering errors were zero in the corrected contour.

## 10. Consumers

The six Wave 2 consumers remain shadow-only. Their factory-routed contract uses
`CanonicalReaderFactory.create`, has no source-format API field, performs no
legacy fallback and produced no provider/product side effect in DOC33.
DOC32's three stable 16-document shadow runs remain the expensive target proof;
they were not mechanically repeated because storage/consumer orchestration was
not changed.

## 11. Gate 2 exit and next decision

Gate 2 has one supported machine projection and one reader for PDF, HTML, CSV
and XLSX. Mandatory content loss, unresolved public refs and parallel authority
are zero. The exit contract is current and code/schema/reader terminology is
aligned.

A separate Wave 2 cutover goal is technically allowed for proposal, but DOC33
does not authorize or perform it. Primary product cutover, global canonical
read activation, legacy removal and Gate 3 remain separate decisions.

## Verification accounting

The machine-readable terminal and triage receipt is
`BROKER_REPORTS_DOC33_TEST_RESULTS.safe.json`.

- pre-change focused baseline: 47 passed;
- DOC33 plus DOC31/DOC32 focused closure: 23 passed;
- canonical/multiformat/consumer/DOC31/DOC32/DOC33 combined: 53 passed;
- final focused closure including safe-evidence validation: 57 passed;
- full suite terminal before generated-bundle rebuild: 2972 passed, 7 failed,
  11 errors, 5 skipped; the five failures are frozen DOC8-DOC11 source-hash
  debt, the eleven errors are the frozen authority hash lock and two failures
  were generated-bundle parity;
- deterministic rebuild of all three generated bundles followed by the two
  affected parity tests plus all ten DOC33 tests: 12 passed;
- new unexplained DOC33 failures: 0; historical hashes rewritten: 0;
- retained cohort: 16/16 reader/completeness/projection PASS;
- provider calls: 0;
- product writes: 0;
- activation changes: 0;
- legacy fallbacks: 0.
