# Broker Reports Gate 2 Exit Contract v1

Status: `CURRENT`

Date: 2026-08-06

This document is the normative boundary summary for Broker Reports Gate 2. It
does not create a schema, reader, parser, store, projection engine, or product
route. DTO meaning remains owned by Canonical Artifact v1 and its JSON Schema;
read behavior remains owned by Canonical Reader v1.

## 1. Input

Gate 2 receives:

- one Gate 1 source artifact reference in authenticated scope;
- the trusted `ArtifactAccessContext`;
- format-specific extraction output created through the maintained Gate 1 and
  `FullSourceArtifactFactory` paths;
- validated table proposals where the governed format adapter permits them.

Supported source formats are PDF, HTML, CSV and XLSX. Format detection and
format-specific extraction are internal boundaries. Native OpenWebUI document
processing, Knowledge/RAG, embeddings and vectorization are not Gate 2 inputs.

## 2. Public output and authority

The only public logical output is:

```text
CanonicalArtifactV1 / schema_version = canonical_artifact_v1
```

The sole construction boundary is `CanonicalNormalizerFactory.create`. The
sole lifecycle facade is `CanonicalArtifactStoreFactory.create`. The sole read
boundary is `CanonicalReaderFactory.create`.

`gate2_handoff_v0` is deprecated compatibility authority for the unchanged
product path. It is not a second Gate 2 output and cannot be used as evidence
that canonical product cutover occurred.

## 3. Unified logical semantics

The following meanings do not depend on source format:

| Entity | Meaning |
| --- | --- |
| document | one immutable normalized source document and version |
| container | an ordered structural scope containing nodes or child containers |
| node | one ordered logical content or boundary item |
| text | literal source-visible text without financial interpretation |
| heading | literal source-visible heading with an optional level |
| list | ordered source-visible list items and nesting |
| table | one structured source table with ordered cells and values |
| note | literal source-visible note or table note |
| issue | an explicit unsupported, partial, conflict or ambiguity disposition |
| conflict | retained unresolved contradictory alternatives, never a fact |
| ambiguity | retained unresolved alternatives, never a fact |
| provenance | compact references from containers, nodes, cells and issues to the authenticated source graph |

`TABLE` has the same public meaning for PDF, HTML, CSV and XLSX. Header
classification may be empty when the source does not prove a header; ordered
cell coordinates and values remain authoritative. No consumer may infer a
header by source-format branching.

## 4. Ordering

Every container order and node order is zero-based, deterministic and
contiguous within its parent. The reader reconstructs one logical order across
single-payload, component-chunked and XLSX row-chunked storage.

Format boundaries are represented by the same container/node contract:

- PDF: `DOCUMENT -> PAGE`, with `PAGE_BREAK` where applicable;
- HTML: `DOCUMENT -> SECTION`;
- CSV: `DATASET -> TABLE`;
- XLSX: `WORKBOOK -> SHEET`, with `SHEET_BREAK` where applicable.

These container subtypes are source structure, not separate public contracts.

## 5. Full Evidence boundary

The three layers are:

```text
FULL EVIDENCE
-> CanonicalArtifactV1 (Gate 2 machine projection)
-> neutral proof view or a future separately authorized Gate 3 projection
```

Full Evidence retains original bytes, parser units, coordinates, crops, table
proposals, provider payloads and engineering receipts as applicable. It stays
private and resolver-backed.

The Gate 2 artifact contains compact provenance. Every container, node, cell
and issue resolves to an in-artifact provenance record, and every provenance
record links to the artifact's authenticated source reference. Raw provider
payloads and private evidence values are forbidden in the canonical artifact.

## 6. Reader guarantees

`CanonicalReaderFactory.create` returns a canonical artifact only after:

- persisted component checksums and the canonical root hash match;
- schema, source identity, root type, container type and node type are valid;
- parent, source, issue and cell references resolve;
- container and node order is contiguous;
- no blocking issue is present;
- at least one meaningful machine-content node exists, unless the source is
  explicitly proved empty;
- the PDF-specific counts-only atom receipt also passes for PDF.

Missing components, stale versions, invalid roots, empty non-empty inputs,
unresolved references and blocking issues fail closed. There is no reader-side
legacy fallback.

## 7. Completeness

Completeness is checked after durable reconstruction by the shared
`assess_canonical_completeness` rule. It requires meaningful content, complete
internal source-reference coverage, complete table-cell source references,
one authenticated source link for every provenance record, and zero blocking
issues.

Format adapters additionally own source-specific accounting:

- PDF accounts every parser/source atom and every table proposal terminally;
- HTML maps every visible canonical block and applies explicit hidden/script/
  style suppression rules in the extractor;
- CSV maps the parsed dataset, dialect, header state, empty cells and all row/
  column coordinates into one table;
- XLSX maps workbook/sheet order and streamed row/cell chunks, records supported
  formulas/caches and emits explicit issues for unsupported features.

No candidate that fails these rules may become active.

## 8. Consumer contract and format opacity

The canonical consumer model is:

```text
projection = reader.read(report_ref)
process(projection)
```

Consumers use schema, containers, ordered nodes, tables, issues and provenance.
They do not require `source.source_format`. Branches on PDF/HTML/CSV/XLSX are
permitted only in Gate 2 adapters and diagnostic tools. The six Wave 2 shadow
contracts use one reader path and do not expose source format as an input or
output requirement.

The source format remains available in canonical source identity for audit.
Page numbers, sheet names, CSV dialect, XLSX formula/cache details and source
locators intentionally remain format-specific metadata. They never replace
the common node/table content.

## 9. Neutral projection verification

`render_neutral_canonical_projection` is a reader-only, format-neutral proof
helper in the existing research compatibility boundary. It traverses common
container and node types, preserves order, text, lists, tables, notes,
conflicts, ambiguities and remaining issues, and reconstructs streamed table
rows from canonical cells when rows are not materialized.

It accepts only a validated `CanonicalArtifactV1`. It has no source resolver,
raw PDF/XLSX/parser payload, private evidence, provider or financial-semantic
dependency. It is not a prompt, product API, persisted Gate 2 output, or Gate 3
runtime.

## 10. Cross-format equivalence

Equivalent table content is compared through ordered canonical cell
coordinates and values, not root hashes, component counts, container subtype
or provenance shape. Header classification, page/sheet boundaries and physical
chunking are explicit source-induced differences. They do not change the
common table values or consumer API.

The current conformance matrix uses exactly four classifications:

- `conformant`: the format implements the common public meaning;
- `divergent`: source-induced metadata or evidence shape intentionally differs;
- `absent`: the source does not contain that optional logical element;
- `unsupported`: Gate 2 cannot represent the element and must emit an explicit
  issue instead of dropping it.

Every mandatory public element is `conformant` for all four formats. `absent`
and `divergent` are permitted only for source-optional or forbidden elements;
there are no unsupported mandatory elements in the approved cohort.

## 11. Storage and lifecycle

Single-payload, chunked and `xlsx_row_chunked_v1` layouts are private storage
choices. The canonical version identity, active pointer, access control,
reader API, root validation, restart/recreation behavior and backup/restore
semantics are common. Re-normalization creates an immutable successor; it does
not overwrite prior evidence.

Additive source metadata may remain in v1 only when it does not change public
entity meaning, required fields, ordering or reader behavior. A change to any
of those public guarantees requires an explicit schema-version decision,
migration and compatibility plan. A compatibility adapter may delegate to a
versioned authority but cannot become a second schema or reader authority.
Readers reject unknown schema versions rather than guessing compatibility.

## 12. Prohibitions and exit boundary

Gate 2 does not contain financial interpretation, ontology, tax meaning,
cross-document reconciliation, task-specific prompts, provider-generated
facts or product cutover policy.

DOC33 confirms the unified machine projection contract only. Wave 2 cutover,
primary product cutover, global canonical reads, legacy deletion and Gate 3
remain separate decisions. A future product/task-specific LLM projection or
financial-semantic result belongs to a separately authorized Gate 3 contract.
