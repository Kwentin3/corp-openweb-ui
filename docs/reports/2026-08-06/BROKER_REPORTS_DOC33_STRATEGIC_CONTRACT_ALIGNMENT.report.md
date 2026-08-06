# Broker Reports DOC33 Strategic Contract Alignment

Date: 2026-08-06

This report aligns the stricter DOC33 strategic wording with the already
completed reader-bound proof. It does not replace or rewrite the earlier DOC33
report or safe receipts. The normative current-state document remains
`BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md`.

## Decision

```text
DOC33_PROGRAM = COMPLETED
GATE2_CONTRACT_AUTHORITY = REFINED
SUPPORTED_FORMATS = PDF_HTML_CSV_XLSX
CROSS_FORMAT_CONFORMANCE = PASS
ONE_PUBLIC_SCHEMA = CONFIRMED
ONE_PUBLIC_READER = CONFIRMED
DOWNSTREAM_FORMAT_OPACITY = CONFIRMED
EVIDENCE_BOUNDARY = CONFIRMED
LLM_PROJECTION_BOUNDARY = CONFIRMED
COMPLETENESS_FAIL_CLOSED = CONFIRMED
CROSS_FORMAT_EQUIVALENCE = CONFIRMED_WITH_LIMITS
DURABLE_ROUNDTRIP = CONFIRMED
GATE2_UNIFIED_MACHINE_PROJECTION = CONFIRMED
WAVE2_CUTOVER = NOT_PERFORMED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
GATE3 = NOT_STARTED
```

## 1. Existing authority

The one schema authority is `CanonicalArtifactV1` with
`schema_version=canonical_artifact_v1`. Construction remains owned by
`CanonicalNormalizerFactory.create`; lifecycle remains owned by
`CanonicalArtifactStoreFactory.create`. No second DTO, schema, validator,
store, reader or engine was created.

## 2. Public reader

`CanonicalReaderFactory.create` is the sole public canonical read boundary. It
hides single-payload, component-chunked and `xlsx_row_chunked_v1` layouts and
fails closed before returning invalid content. `gate2_handoff_v0` remains only
the unchanged product compatibility authority because cutover is out of scope.

## 3. Cross-format differences found

The permissible differences are source identity and provenance locator shape;
`DOCUMENT/PAGE`, `DOCUMENT/SECTION`, `DATASET` and `WORKBOOK/SHEET` boundaries;
availability of source-proved header roles; PDF page, CSV dialect and XLSX
sheet/formula metadata; physical layout and root hash. CSV and XLSX have no
standalone heading/list/note nodes when those elements are absent in source.

## 4. Differences resolved

The common validator now applies meaningful-content, reference, provenance and
blocking-issue rules to all four formats. The neutral renderer accepts the
common canonical artifact instead of a PDF-specific model. Wave 2 shadow output
does not expose source format. The v2 matrix replaces the non-contract term
`supported` with the required `conformant` vocabulary without changing runtime.

## 5. Public format branching

Mandatory public format branches are zero and mandatory format-specific fields
are zero. Branches remain only in Gate 2 extraction/normalization adapters,
diagnostics and unchanged legacy product paths. They do not define public
machine semantics.

## 6. Reader-visible completeness

After durable reconstruction, `assess_canonical_completeness` requires a
meaningful node or proved-empty source, resolved container/node/issue/cell
source refs, provenance links to the authenticated source and zero blocking
issues. Root hash and component checks precede the read. Four-format tests
prove that non-empty zero-content candidates fail closed; PDF additionally
retains complete source-atom accounting.

## 7. Cross-format equivalence

One equivalent ordered 3x2 table was normalized, persisted, activated, reopened
and read as PDF, HTML, CSV and XLSX. It produced one six-cell ordered logical
signature and four non-empty neutral projections across single and chunked
layouts. The result is `CONFIRMED_WITH_LIMITS`: root hashes, optional document
nodes, source boundaries, provenance graphs and physical layouts intentionally
remain different.

## 8. Evidence linkage

Every public container, node, issue and table cell resolves to compact
in-artifact provenance, and each provenance record links to the authenticated
source artifact. Original bytes, parser output, coordinates, crops, provider
payloads and detailed receipts remain private Full Evidence. The v2 receipts
bind the earlier immutable DOC33 receipts by hash.

## 9. LLM-friendly projection

`render_neutral_canonical_projection` accepts only a validated artifact returned
by the public reader. It preserves order, text, headings, lists, tables, notes,
conflicts, ambiguities and issues without source-format branching, private
evidence access, provider access or financial interpretation. It is proof
tooling, not a persisted Gate 2 output, product API or Gate 3 runtime.

## 10. Sixteen-document cohort

All 16 retained active artifacts read through the same reader contract: 8 PDF,
4 HTML, 2 CSV and 2 XLSX. All root hashes matched, all completeness assessments
passed and all neutral projections were non-empty. The proof combines the
corrected DOC32 PDF isolated store and the isolated non-PDF restore; no private
identity or content appears in safe output.

## 11. Concerns confirmed

Two historical concerns were real: storage/root/activation success can coexist
with reader-visible content failure, and envelope validation alone can miss
semantic completeness. The former zero-node PDF state demonstrated both. DOC32
repaired the artifacts; DOC33 generalized the consumer-boundary guard.

## 12. Concerns refuted

Current evidence refutes multiple public machine models, separate public format
contracts, downstream source-format dependency, projector access to private
evidence, format metadata replacing common content, a parallel schema/reader/
engine, a current authority conflict, and Gate 2 closure based only on adapter
or storage success.

## 13. Gate 2 verdict

Gate 2 is architecturally complete as one non-financial machine-projection
layer: one schema, one reader, four conforming formats, format-opaque consumers,
separate evidence and LLM-view boundaries, fail-closed completeness and durable
round-trip are all confirmed. This verdict does not claim product activation.

## 14. Wave 2 next decision

A separately authorized Wave 2 cutover GOAL is technically admissible after
DOC33 closure. DOC33 does not authorize or perform it. Primary product cutover,
global canonical reads, legacy removal, Gate 3 and financial semantics remain
separate decisions.

## Evidence and verification accounting

- Current authority: `BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md`.
- Exact matrix: `BROKER_REPORTS_DOC33_CROSS_FORMAT_CONFORMANCE.v2.safe.json`.
- Exact decision: `BROKER_REPORTS_DOC33_STRATEGIC_DECISION.v2.safe.json`.
- Earlier DOC33 report and five safe receipts were not modified.
- Final focused reader/conformance/consumer/DOC31/DOC32/DOC33 plus generated
  bundle parity contour: 63 passed in 9.60 seconds.
- The read-only 16-document proof exactly matched the immutable cohort receipt.
- Runtime, schema, reader, provider, activation and product-data changes in this
  alignment: zero.
- Historical hashes rewritten: zero.
