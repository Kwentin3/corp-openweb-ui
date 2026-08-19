# Broker Reports Canonical Artifact v1

The XLSX specialization is defined by
`BROKER_REPORTS_XLSX_CANONICAL_PROFILE.v1.md`. Its additive cell fields retain
formula/cache separation and shared dictionary references; its physical
`xlsx_row_chunked_v1` layout does not change the logical root contract.

Status: `CURRENT`

Date: 2026-08-06

Schema identity: `canonical_artifact_v1`

## Ownership and boundary

`CanonicalArtifactV1` is the immutable, deterministic, machine-readable
representation of one uploaded document after format-specific Gate 2
extraction and normalization. It is exactly `OUTPUT OF GATE 2`; the historical
package name and `gate2_handoff_v0` compatibility route do not reassign it to
Gate 1. The artifact contains no financial interpretation.

The sole construction boundary is `CanonicalNormalizerFactory.create`.
Format adapters consume Gate 1-authorized source refs plus validated output
from `FullSourceArtifactFactory` and
validated table projections. They must not create a second parser, provider
route, ArtifactStore, or financial semantic authority.

Full engineering evidence remains separate and resolver-backed. The canonical
artifact may reference evidence; it never replaces, deletes, or weakens it.

## Logical envelope

The fully resolved logical artifact validates against
`BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json` and contains:

- opaque `artifact_id` and authenticated `tenant_id`;
- immutable `artifact_version`, `schema_version`, `normalizer_version`,
  optional `previous_version_ref`, and `canonical_root_hash`;
- original source identity, format, MIME type, and source SHA-256;
- one root container plus ordered format-appropriate child containers;
- ordered nodes, compact provenance, explicit issues, and logical chunks.

The logical artifact can be physically split into one manifest and many chunks.
Chunking is transparent to the reader and cannot change logical bytes or the
canonical root hash.

## Container types

- `DOCUMENT`: root for PDF and HTML;
- `PAGE`: ordered PDF page;
- `SECTION`: ordered HTML section;
- `WORKBOOK`: root for XLSX;
- `SHEET`: ordered XLSX sheet;
- `DATASET`: root for CSV.

CSV does not synthesize pages. PDF does not synthesize sheets.

## Node types

- `HEADING`, `TEXT`, `NOTE`: literal source-visible text;
- `LIST`: ordered source-visible list items;
- `TABLE`: structured source table represented once in the primary flow;
- `PAGE_BREAK`, `SHEET_BREAK`: explicit format boundaries;
- `CONFLICT`, `AMBIGUITY`: unresolved alternatives, never facts.

Every node has a stable `node_id`, `container_ref`, zero-based `order`,
typed content or a `content_ref`, source refs, evidence refs, and issue refs.

## Table content

A table contains optional title/header/notes, ordered rows, and typed cells.
Every cell preserves its row/column coordinate, source refs, and applicable:

- raw value;
- displayed value;
- formula;
- cell type;
- merged range;
- source coordinate;
- hidden state and number-format identity.

For a source-bound PDF table, merged ranges come from parser-native row/column
spans. A table segment that is mechanically linked across a page boundary also
carries `logical_table_id` and the validated `continuation` metadata. Segments
remain separate ordered `TABLE` nodes; Canonical does not join their values or
claim that they are semantically one table.

CSV preserves encoding, delimiter, quote rules, header state, empty cells, row
order, and row/column coordinates. XLSX preserves workbook/sheet order, sheet
visibility, formulas and cached displayed values, raw values, cell types,
merged ranges, named ranges, and table definitions when present.

## Required invariants

1. The original source artifact always remains stored and resolvable.
2. Schema and normalizer versions are mandatory.
3. A published artifact version and every chunk are immutable.
4. Container and node order are deterministic and contiguous.
5. Every content node resolves to at least one source ref.
6. Every source ref resolves inside the same authenticated artifact graph.
7. Each accepted table appears once in the primary flow.
8. Suppressed duplicate parser atoms retain evidence/provenance accounting.
9. Conflicts and ambiguities remain explicit.
10. Provider raw payload is absent from canonical and safe outputs.
11. Financial facts, roles, ontology, tax meaning, and Gate 3 logic are absent.
12. Re-normalization creates a new version; it never overwrites one.
13. Three identical normalizations produce identical canonical root hashes.

## Format adapters

### PDF

The adapter orders parser units by page and source reading order, inserts each
validated structured table at its source position, and preserves unmatched
parser content plus explicit conflict/ambiguity issues. DOC23 conservative
deduplication is allowed only when source coverage is proved. DOC24 remains the
material regression baseline; it is evidence, not product authority.

PDF table text is owned by the original locator region even when the parser
uses a one-point crop margin to recover a clipped ruling. Globally empty parser
axes may be removed, but populated axes and source refs remain accounted.
Ambiguous wrapped-text row boundaries retain their physical ordering and low
quality marker instead of being semantically joined.

For every non-empty PDF, the root container carries a counts-only
`canonical_pdf_completeness_v1` receipt. Validation requires page and container
counts, at least one logical node, 100% source-atom accounting, zero unresolved
atoms, source refs on primary nodes, and one terminal disposition for every
table projection. A proved empty PDF is the only zero-node exception and must
carry `EMPTY_SOURCE_DOCUMENT`. A failed completeness check cannot change the
active pointer.

Full Evidence can retain parser lines, coordinates, visual atoms, crops and
provider proposals. Those private artifacts are not canonical nodes. The
format-neutral proof projection is derived only from a resolved
`CanonicalArtifactV1`; it cannot reopen Full Evidence or source bytes.

### HTML

The adapter preserves visible title, headings, paragraphs, lists, links,
tables, notes, and section order. Script, style, comments, hidden templates, and
tracking markup remain only in original source/full evidence.

### CSV

The adapter emits `DATASET -> TABLE`. Duplicate or absent headers are
preserved and explicitly described; they are not silently repaired.

### XLSX

The adapter emits `WORKBOOK -> ordered SHEET` containers and structured table
nodes. It never flattens a workbook to one CSV.

## Validation and failure

Construction fails closed on unsupported format, incomplete source accounting,
unresolved refs, duplicate node/container identity, non-contiguous order,
hidden conflicts, non-deterministic rebuild, or financial fields. A blocked
candidate may be stored as safe failure evidence but cannot be activated.

The shared validator enforces the public source format and root-container
mapping, the common container/node vocabulary, parent/source/issue/table-cell
reference resolution, zero blocking issues and at least one meaningful content
node for PDF, HTML, CSV and XLSX. A zero-content artifact is valid only for a
source explicitly proved empty. `assess_canonical_completeness` repeats the
counts-only decision after durable reader reconstruction and verifies that
every provenance record links to the authenticated source artifact reference.

PDF retains its stricter source-atom completeness receipt. HTML, CSV and XLSX
retain their direct format-adapter accounting; these internal accounting
methods do not create different public contracts.

## Non-goals

- LLM-friendly projection;
- financial extraction or ontology;
- Gate 3 case assembly;
- provider calls;
- parser/cropper research;
- automatic legacy deletion.

The [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md)
defines the unified input/output, evidence, reader, consumer-opacity and
non-cutover boundary. `CanonicalArtifactV1` is the one Gate 2 machine
projection for PDF, HTML, CSV and XLSX. Source format, page/sheet structure,
CSV dialect and XLSX formula/cache details remain auditable metadata; consumers
use the common ordered node/table contract and do not require format branching.
