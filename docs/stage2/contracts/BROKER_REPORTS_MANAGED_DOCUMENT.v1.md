# Broker Reports Managed Document v1

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_managed_document_v1`

Owner: `services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_contracts.py`

Schema: `BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json`

## 1. Contract decision

A managed document is one source-bound document with one ordered `blocks[]`
stream. Every heading, paragraph, list, table, note, visual, source boundary or
unknown element occupies one position in that stream. `relations[]` adds only
relationships that source order alone cannot express.

This is a Global Gate 1 representation contract. It contains no financial
classification, provider execution, product entrypoint, parser, renderer,
retrieval surface or persistence side effect. DOC2 may later construct this
artifact from a PDF; DOC1 does not.

The core invariant is:

```text
UNACCOUNTED_CONTEXT_LOSS = 0
```

A normalizer may return `PARTIAL` or `BLOCKED`. It may not silently discard or
invent context and call the result complete.

## 2. Ownership and boundary

The single contract owner provides:

- closed enums and the validated `ManagedDocument` value;
- strict Draft 2020-12 schema validation;
- deterministic semantic invariant validation;
- duplicate-key-rejecting JSON parsing;
- canonical JSON serialization and SHA-256 integrity;
- sealing of an already constructed candidate.

The owner accepts a JSON object and a schema object. It does not load repository
files, read source documents, call a model, infer structure, repair data or
write an artifact. A future adapter must construct a candidate outside this
module and submit it to the validator.

## 3. Information partition

The top-level `information_partition` is fixed and machine-readable:

```json
{
  "CONTENT": ["/metadata", "/blocks/*/content"],
  "PROVENANCE": ["/source", "/anchors", "/relations"],
  "CONTROL": [
    "/information_partition",
    "/blocks/*/restoration",
    "/quality"
  ],
  "PRIVATE_SOURCE": [
    "/source/artifact",
    "/anchors/*/locator/private_locator",
    "/blocks/*/content/private_artifact"
  ]
}
```

This does not create an LLM view. It gives DOC3 a deterministic policy input:
content can be considered for a later governed view, provenance and control
remain separately identifiable, and private-source refs must never be expanded
into model-visible bytes by default.

## 4. Top-level document

Every document has exactly these fields:

| Field | Responsibility |
| --- | --- |
| `schema_version` | Exact v1 contract identity. |
| `document_id` | Stable document-local identity. |
| `information_partition` | Fixed content/provenance/control/private-source routing. |
| `source` | Source format, private artifact binding, checksum, MIME type, size, part count and normalizer identity. |
| `metadata` | Status-bearing document passport. |
| `anchors` | Typed source locators owned by provenance. |
| `blocks` | Sole contiguous zero-based reading order. |
| `relations` | Explicit non-order relations. |
| `quality` | Status, counters, issue ledger and loss ledger. |
| `integrity_sha256` | SHA-256 over canonical JSON without this field. |

Unknown top-level properties fail schema validation. There is no generic
`extensions` object that can hide an unmodelled DOC0 facet.

## 5. Source

Supported formats are:

```text
PDF HTML CSV XLSX XLS UNKNOWN
```

`source.artifact` is a `PRIVATE_SOURCE` ref, not source bytes or a filesystem
path. `source.checksum_sha256` binds the original artifact. The normalizer name
and version identify the future producer, not the contract validator.

Typed `source_details` are deliberately small:

- PDF: encryption status;
- HTML: typed HTML identity;
- CSV: source row count;
- XLSX/XLS: sheet count and formula status;
- UNKNOWN: explicit reason.

Source-specific details do not define common document meaning. Consumers use
the common block, relation, anchor and quality fields.

## 6. Metadata

The required passport fields are document type, title, issuer, document date,
reporting period, owner/account, language and primary currency. Additional
fields use a named list, not an unconstrained object.

Each field contains:

```json
{
  "information_class": "CONTENT",
  "status": "PRESENT",
  "origin": "SOURCE_EXPLICIT",
  "value": "Synthetic value",
  "candidates": [],
  "evidence_anchor_ids": ["anchor_example"]
}
```

Allowed statuses:

```text
PRESENT UNKNOWN NOT_APPLICABLE CONFLICTING
```

Allowed origins:

```text
SOURCE_EXPLICIT
DETERMINISTIC_DERIVED
MODEL_PROPOSED
OPERATOR_SUPPLIED
UNKNOWN_ORIGIN
```

`PRESENT` requires one value and no candidates. `UNKNOWN` and
`NOT_APPLICABLE` require a null value and no candidates. `CONFLICTING` requires
at least two distinct candidates and no chosen value. `SOURCE_EXPLICIT`
requires an evidence anchor. A future model proposal must remain
`MODEL_PROPOSED`; changing it to `SOURCE_EXPLICIT` would be a provenance lie.

## 7. Source anchors

Every content block has at least one source anchor. Metadata and relations may
cite the same anchor registry.

The typed locators are:

- PDF: source part, page, source block ref, optional bbox and private locator;
- HTML: source part, DOM path or block ref, ordinal and private locator;
- CSV: source part plus row and column ranges;
- XLSX/XLS: source part, sheet, cell range, source ref and private locator;
- UNKNOWN: source part plus private locator.

The validator requires each anchor format to match `source.format` and each
source part index to fall within `source.source_part_count`. Common consumers
must treat locator internals as provenance, not document semantics. A bbox is
a locator only; it is never a claim that physical geometry is canonical table
meaning.

## 8. Ordered blocks

`blocks[]` is the only primary reading order. Ordinals are unique, contiguous
and exactly `0..n-1`. Every block contains:

- `block_id`;
- `ordinal`;
- `block_type`;
- typed `content`;
- one or more source anchor IDs;
- `restoration` status and classification origin;
- issue IDs.

Allowed block types:

```text
HEADING PARAGRAPH LIST TABLE NOTE VISUAL BOUNDARY UNKNOWN
```

### 8.1 HEADING

Keeps source-normalized raw text, optional logical level and
`KNOWN | UNKNOWN` level status. An unknown level is null; it is not guessed.

### 8.2 PARAGRAPH

Keeps source-normalized raw text. Line joins, word joins and removed
hyphenation are explicit `join_events` with `APPLIED | UNCERTAIN` status. A
paragraph is not a summary.

### 8.3 LIST

Keeps contiguous item order, text and optional nesting. Unknown nesting uses
null plus `nesting_status=UNKNOWN`.

### 8.4 NOTE

Keeps note text and a bounded kind. `NOTE_FOR` or `FOOTNOTE_FOR` records the
target. Adjacency is not sufficient evidence for a relation.

### 8.5 VISUAL

Keeps bounded visual type, status-bearing caption and safe description,
processing status and the private source artifact. An unprocessed visual is
not deleted because it lacks a description.

### 8.6 BOUNDARY

Preserves `PAGE`, `SHEET` or `SOURCE_PART` boundaries in the reading stream.
It does not replace section headings.

### 8.7 UNKNOWN

Keeps available raw text and/or a private artifact ref, the original ordinal,
anchors and an explicit reason. At least raw text or a private artifact must
remain. A new structure does not fail validation merely because its semantic
block type is unfamiliar.

## 9. TABLE block

The table content reuses the proven core unchanged:

```json
{
  "description": "Source-oriented description.",
  "rows": [["visible text", null, "100.00"]]
}
```

The managed-document envelope adds only logical context:

- stable table ID and status-bearing title;
- completeness status;
- block ordinal and source anchors;
- optional logical header hierarchy and row groups;
- optional total/subtotal/group markers;
- optional unit-to-logical-column bindings;
- optional cell-state annotations;
- note, footnote and continuation relation IDs;
- known loss IDs.

It does not require or claim physical column widths, line thickness, pixel
alignment, merged-cell truth or reconstructed physical spans.

### 9.1 Cell state

The `rows` array remains strings or null. Optional annotations distinguish:

```text
PRESENT EMPTY UNREADABLE UNKNOWN
```

`PRESENT` requires a string. `EMPTY` and `UNREADABLE` require null. Every
annotation must address an existing logical row and cell. Thus a blank source
cell and unreadable source content remain distinguishable without changing the
existing table core.

### 9.2 Multi-page tables

Both safe representations are allowed:

1. one TABLE block with anchors from multiple source parts; or
2. multiple TABLE blocks connected by `CONTINUATION_OF` or
   `SAME_LOGICAL_OBJECT`.

The contract does not choose the DOC2 normalization policy. A continuation is
never inferred solely from adjacency or a repeated header.

## 10. Relations

Every relation has a unique ID, type, source endpoint, target endpoint, status,
origin, evidence anchors and issue IDs. Endpoints always name an existing
block and may additionally name an existing logical table row or cell.

Allowed types:

```text
BELONGS_TO_SECTION
CAPTION_FOR
NOTE_FOR
FOOTNOTE_FOR
CONTINUATION_OF
SAME_LOGICAL_OBJECT
EXPLAINS
UNKNOWN_RELATION
```

`MODEL_PROPOSED`, `DETERMINISTIC_DERIVED` and `SOURCE_EXPLICIT` remain
different origins. Reading order never depends on relation traversal.

## 11. Quality and loss ledger

Document status is:

```text
COMPLETE PARTIAL BLOCKED
```

The quality object contains source element, preserved block, unknown block,
unsupported element, known loss, conflict, unaccounted loss and blocking loss
counters. Counters are recomputed or cross-checked by the validator.

Every loss states:

- context class and what was lost;
- where and why;
- recoverability;
- whether source reread is required;
- whether semantic analysis is blocked;
- anchors and affected blocks;
- `accounted=true`.

`unaccounted_context_loss_total` is schema-fixed to zero. `COMPLETE` rejects a
blocking loss and also rejects unknown blocks, unsupported elements, known
losses, conflicts or non-restored blocks. `PARTIAL` requires at least one such
explicit incomplete-context signal and rejects a blocking loss. `BLOCKED`
requires at least one blocking loss. A `PARTIAL` artifact remains a valid and
honest contract result.

## 12. Canonical JSON and integrity

Canonical bytes are UTF-8 JSON with:

```text
ensure_ascii = false
keys = sorted
separators = (",", ":")
```

`integrity_sha256` is SHA-256 over the complete canonical document after
removing the top-level `integrity_sha256` field. Duplicate JSON keys are
rejected before validation. The validator never repairs or reseals input while
validating; `seal()` is an explicit operation for an already constructed
candidate.

## 13. Full minimal document example

This complete example is the safe CSV fixture shape. The hash is valid for the
exact object shown.

```json
{
  "schema_version": "broker_reports_managed_document_v1",
  "document_id": "document_fixture_d_csv",
  "information_partition": {
    "CONTENT": ["/metadata", "/blocks/*/content"],
    "PROVENANCE": ["/source", "/anchors", "/relations"],
    "CONTROL": ["/information_partition", "/blocks/*/restoration", "/quality"],
    "PRIVATE_SOURCE": ["/source/artifact", "/anchors/*/locator/private_locator", "/blocks/*/content/private_artifact"]
  },
  "source": {
    "information_class": "PROVENANCE",
    "format": "CSV",
    "artifact": {
      "information_class": "PRIVATE_SOURCE",
      "status": "PRESENT",
      "ref": "private_fixture_d_source",
      "checksum_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    },
    "checksum_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "mime_type": "text/csv",
    "size_bytes": 128,
    "source_part_count": 1,
    "normalizer": {"name": "synthetic_contract_fixture", "version": "1.0.0"},
    "created_at": "2026-08-01T00:00:00Z",
    "source_details": {"kind": "CSV", "row_count": 3}
  },
  "metadata": {
    "document_type": {"information_class": "CONTENT", "status": "PRESENT", "origin": "DETERMINISTIC_DERIVED", "value": "Delimited table document", "candidates": [], "evidence_anchor_ids": ["anchor_d_csv"]},
    "title": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
    "issuer": {"information_class": "CONTENT", "status": "NOT_APPLICABLE", "origin": "SOURCE_EXPLICIT", "value": null, "candidates": [], "evidence_anchor_ids": ["anchor_d_csv"]},
    "document_date": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
    "reporting_period": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
    "owner_or_account": {"information_class": "CONTENT", "status": "NOT_APPLICABLE", "origin": "SOURCE_EXPLICIT", "value": null, "candidates": [], "evidence_anchor_ids": ["anchor_d_csv"]},
    "language": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
    "primary_currency": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
    "additional": []
  },
  "anchors": [
    {
      "information_class": "PROVENANCE",
      "anchor_id": "anchor_d_csv",
      "source_format": "CSV",
      "checksum_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "locator": {"kind": "CSV", "source_part_index": 1, "row_start": 1, "row_end": 3, "column_start": 1, "column_end": 2}
    }
  ],
  "blocks": [
    {
      "block_id": "block_d_table",
      "ordinal": 0,
      "block_type": "TABLE",
      "content": {
        "information_class": "CONTENT",
        "table_id": "table_fixture_d_csv",
        "title": {"information_class": "CONTENT", "status": "UNKNOWN", "origin": "UNKNOWN_ORIGIN", "value": null, "candidates": [], "evidence_anchor_ids": []},
        "description": "Complete synthetic CSV table.",
        "rows": [["Label", "Value"], ["Synthetic A", "1"], ["Synthetic B", "2"]],
        "completeness_status": "COMPLETE",
        "header_hierarchy": {"status": "KNOWN", "entries": [{"label": "Label", "level": 1, "row_index": 0, "column_start": 0, "column_end": 0, "origin": "SOURCE_EXPLICIT"}, {"label": "Value", "level": 1, "row_index": 0, "column_start": 1, "column_end": 1, "origin": "SOURCE_EXPLICIT"}]},
        "row_groups": {"status": "UNKNOWN", "groups": []},
        "row_markers": [],
        "units": [],
        "cell_annotations": [],
        "related_relation_ids": [],
        "continuation_relation_ids": [],
        "known_gap_ids": []
      },
      "source_anchor_ids": ["anchor_d_csv"],
      "restoration": {"information_class": "CONTROL", "status": "RESTORED", "classification_origin": "DETERMINISTIC_DERIVED", "issue_ids": []},
      "issue_ids": []
    }
  ],
  "relations": [],
  "quality": {
    "information_class": "CONTROL",
    "status": "COMPLETE",
    "source_elements_total": 1,
    "preserved_blocks_total": 1,
    "unknown_blocks_total": 0,
    "unsupported_elements_total": 0,
    "known_losses_total": 0,
    "conflicts_total": 0,
    "unaccounted_context_loss_total": 0,
    "blocking_losses_total": 0,
    "issue_ledger": [],
    "loss_ledger": []
  },
  "integrity_sha256": "16609cc7ccec6f19195b12ccd8d113b41fe93085abb670a86243226af02432cf"
}
```

## 14. Full TABLE block example

```json
{
  "block_id": "block_a_table",
  "ordinal": 3,
  "block_type": "TABLE",
  "content": {
    "information_class": "CONTENT",
    "table_id": "table_fixture_a_positions",
    "title": {
      "information_class": "CONTENT",
      "status": "PRESENT",
      "origin": "SOURCE_EXPLICIT",
      "value": "Positions",
      "candidates": [],
      "evidence_anchor_ids": ["anchor_a_table"]
    },
    "description": "Synthetic source-visible positions table.",
    "rows": [
      ["Asset", "Amount"],
      ["Synthetic A", "100.00"],
      ["Synthetic B", null]
    ],
    "completeness_status": "COMPLETE",
    "header_hierarchy": {
      "status": "KNOWN",
      "entries": [
        {"label": "Asset", "level": 1, "row_index": 0, "column_start": 0, "column_end": 0, "origin": "SOURCE_EXPLICIT"},
        {"label": "Amount", "level": 1, "row_index": 0, "column_start": 1, "column_end": 1, "origin": "SOURCE_EXPLICIT"}
      ]
    },
    "row_groups": {"status": "UNKNOWN", "groups": []},
    "row_markers": [],
    "units": [{"label": "USD", "column_indexes": [1], "status": "KNOWN", "origin": "SOURCE_EXPLICIT"}],
    "cell_annotations": [
      {"row_index": 1, "column_index": 1, "state": "PRESENT", "origin": "SOURCE_EXPLICIT", "evidence_anchor_ids": ["anchor_a_table"], "issue_ids": []},
      {"row_index": 2, "column_index": 1, "state": "EMPTY", "origin": "SOURCE_EXPLICIT", "evidence_anchor_ids": ["anchor_a_table"], "issue_ids": []}
    ],
    "related_relation_ids": ["relation_a_note_for_table", "relation_a_table_section"],
    "continuation_relation_ids": [],
    "known_gap_ids": []
  },
  "source_anchor_ids": ["anchor_a_table"],
  "restoration": {
    "information_class": "CONTROL",
    "status": "RESTORED",
    "classification_origin": "DETERMINISTIC_DERIVED",
    "issue_ids": []
  },
  "issue_ids": []
}
```

## 15. Ordered surrounding context example

Fixture A proves that text and a table do not become independent fragments:

```text
ordinal 2 PARAGRAPH "The following table contains synthetic positions."
ordinal 3 TABLE     table_fixture_a_positions
ordinal 4 NOTE      "Synthetic values are illustrative."
```

The note remains later in source order and is explicitly bound by:

```json
{
  "relation_id": "relation_a_note_for_table",
  "relation_type": "NOTE_FOR",
  "source": {"block_id": "block_a_note", "row_index": null, "column_index": null},
  "target": {"block_id": "block_a_table", "row_index": null, "column_index": null},
  "status": "PRESENT",
  "origin": "SOURCE_EXPLICIT"
}
```

## 16. Multi-page table example

Fixture C stores two TABLE blocks around explicit PAGE boundaries. The second
fragment points to the first:

```json
{
  "relation_id": "relation_c_continuation",
  "relation_type": "CONTINUATION_OF",
  "source": {"block_id": "block_c_table_2", "row_index": null, "column_index": null},
  "target": {"block_id": "block_c_table_1", "row_index": null, "column_index": null},
  "status": "PRESENT",
  "origin": "DETERMINISTIC_DERIVED",
  "evidence_anchor_ids": ["anchor_c_table_1", "anchor_c_table_2"],
  "issue_ids": []
}
```

Its footnote targets logical row 1 of the second fragment. One null cell has
`state=UNREADABLE`; the repeated header remains literal in the second
`rows` array. This proves contract expressiveness only. No real multi-page PDF
normalizer is claimed.

## 17. Loss ledger example

```json
{
  "loss_id": "loss_c_unreadable_cell",
  "context_class": "CONTENT",
  "what_lost": "Visible text in logical cell row 1 column 1.",
  "where": "Second table fragment on source part 2.",
  "reason": "Source content is unreadable in the synthetic scenario.",
  "recoverability": "RECOVERABLE",
  "requires_source_reread": true,
  "blocks_semantic_analysis": false,
  "accounted": true,
  "anchor_ids": ["anchor_c_table_2"],
  "block_ids": ["block_c_table_2"]
}
```

## 18. Validation boundary

The sole validator checks schema and at least these cross-object invariants:

- all IDs are unique;
- block ordinals are contiguous;
- relation endpoints and optional row/cell targets exist;
- source anchors match source format and part range;
- metadata state/value/origin/evidence combinations are coherent;
- table annotations, headers, groups, row markers and unit columns exist;
- table relation/loss refs resolve and continuation refs have an allowed type;
- quality counters equal their ledgers and block inventory;
- `COMPLETE`, `PARTIAL` and `BLOCKED` agree with blocking losses;
- unaccounted loss is zero;
- canonical integrity is exact.

Validation returns a copied value. It does not correct the candidate.

## 19. Scope and evidence boundary

Safe corpus:

```text
PDF ordinary broker-like document
PDF unfamiliar structure
PDF continued table with footnote and unreadable cell
CSV one-table document
XLSX two-sheet document with unsupported formula semantics
HTML ordered document
```

All fixtures are hand-authored synthetic safe data. They prove that the
contract can express the required structures. They do not prove that current
PDF, HTML, CSV or XLSX parsers produce this contract.

```text
REAL_CORPUS_GAP = TRUE
PDF_NORMALIZER = NOT_STARTED
LLM_FRIENDLY_RENDERER = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
