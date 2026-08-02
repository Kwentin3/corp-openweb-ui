# Broker Reports LLM Document View v2

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_llm_document_view_v2`

Owner: `ManagedDocumentLlmViewV2Factory`

## 1. Decision

LLM Document View v2 is the deterministic row-oriented UTF-8 projection of
one validated Managed Document v2. It changes representation only:

```text
source -> Managed Document v2 -> LLM Document View v2
```

The factory must first validate its complete input with
`ManagedDocumentContractV2Validator`. The factory does not select, summarize,
rank, translate, repair, infer, filter or truncate content. It makes no
provider call and has no product-route consumer.

The validator accepts only the Managed Document v2 schema with its exact `$id`
and pinned canonical-schema SHA-256. Supplying a changed schema under the same
`$id` cannot weaken the view boundary.

Managed Document v2 remains authoritative. View v2 is derived and
reproducible; it is not a fact store, retrieval index, prompt or rectangular
table authority.

## 2. Encoding and line grammar

The view uses UTF-8 without BOM, LF line endings and exactly one final LF.
Empty physical lines, CR, duplicate JSON keys and trailing content are
invalid.

Every non-marker record is one tag, one ASCII space and one compact JSON
value. JSON uses `ensure_ascii=false`, sorted object keys and separators
`(",", ":")`. Source newlines, quotes and renderer-like strings therefore
remain escaped inside one physical line.

The exact envelope is:

```text
BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2
CONTENT_TRUST "UNTRUSTED_SOURCE_DOCUMENT"
DOCUMENT_BEGIN
...
DOCUMENT_END
END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2
```

## 3. Document passport

The fixed passport records are:

```text
SOURCE_FORMAT <json-string>
SOURCE_PARTS_TOTAL <json-integer>
DOCUMENT_QUALITY_STATUS <json-string>
KNOWN_LOSSES_TOTAL <json-integer>
BLOCKING_LOSSES_TOTAL <json-integer>
UNKNOWN_BLOCKS_TOTAL <json-integer>
SOURCE_CONTEXT <json-object>
```

`SOURCE_CONTEXT` contains only `mime_type` and typed `source_details`.
Artifact refs, source checksum, size, normalizer identity and creation time do
not enter the model-visible view.

Managed Document v2 `document_id` is private diagnostic state. It is not a
passport record, safe pointer or parity field and never enters View v2.

## 4. Metadata and safe source pointers

All eight standard metadata fields and every additional field appear in
Managed Document order:

```text
METADATA_BEGIN
METADATA_FIELD_BEGIN
METADATA_NAME "title"
METADATA {"candidates":[],"origin":"UNKNOWN_ORIGIN","sources":[],"status":"UNKNOWN","value":null}
METADATA_FIELD_END
METADATA_END
```

The complete safe anchor registry appears once between `ANCHORS_BEGIN` and
`ANCHORS_END`. A pointer may contain only:

- `anchor_id`;
- `format`;
- `source_part_index`;
- PDF `page`;
- CSV row and column ranges;
- HTML source ordinal.

Pointers never contain source checksums, bbox, coordinates, DOM paths, sheet
names, cell ranges, parser/storage refs or private locator data. Every pointer
used later must be byte-equivalent as JSON data to its registry entry.

## 5. Ordered blocks

`BLOCKS_BEGIN` contains every Managed Document block in exact block-ordinal
order. The common envelope is:

```text
BLOCK_BEGIN
BLOCK_ORDINAL 0
BLOCK_ID "block_example"
BLOCK_TYPE "PARAGRAPH"
BLOCK_SOURCE [{"anchor_id":"anchor_example","format":"PDF","page":1,"source_part_index":1}]
RESTORATION {"classification_origin":"DETERMINISTIC_DERIVED","issue_ids":[],"status":"RESTORED"}
BLOCK_ISSUE_IDS []
BLOCK_CONTENT {"join_events":[],"raw_text":"Source text."}
BLOCK_END
```

All non-table content fields are kept in `BLOCK_CONTENT` except their redundant
information-class marker. `VISUAL` and `UNKNOWN` omit private artifact objects
and may expose only `private_source_available` as a boolean. Status-bearing
visual metadata and boundary labels use the same metadata projection as
section 4.

## 6. Row-oriented TABLE grammar

A TABLE is an ordered collection of logical rows. It is not normalized into a
rectangle, and the renderer creates no empty entries, cells, spans or covered
coordinates.

Each table is emitted in this fixed nesting order:

```text
TABLE_BEGIN
TABLE_ID <json-string>
TABLE_COMPLETENESS <json-string>
SOURCE_PARTS_BEGIN
  SOURCE_PART_BEGIN ... SOURCE_PART_END
SOURCE_PARTS_END
COLUMNS_BEGIN
  COLUMN_BEGIN ... COLUMN_END
COLUMNS_END
ROWS_BEGIN
  ROW_BEGIN
    ...
    ENTRIES_BEGIN
      ENTRY_BEGIN ... ENTRY_END
    ENTRIES_END
  ROW_END
ROWS_END
TABLE_RELATION_IDS <json-array>
TABLE_ISSUE_IDS <json-array>
TABLE_KNOWN_GAP_IDS <json-array>
TABLE_END
```

Indentation above is explanatory only; physical records are not indented.

### 6.1 Source parts

Every source part appears in ordinal order and contains:

```text
SOURCE_PART_ORDINAL
SOURCE_PART_ID
SOURCE_PART_PAGE
SOURCE_PART_SOURCE
SOURCE_PART_FIRST_ROW_ID
SOURCE_PART_LAST_ROW_ID
SOURCE_PART_CONTINUATION
SOURCE_PART_ISSUE_IDS
```

`SOURCE_PART_SOURCE` contains the safe pointer for the source-region anchor.
Geometry evidence IDs and continuation-evidence IDs remain private. The
observable `SINGLE`, `START`, `CONTINUATION` or `END` status remains visible.

### 6.2 Optional logical columns

Every proven logical column appears in ordinal order and contains:

```text
COLUMN_ORDINAL
COLUMN_ID
COLUMN_HEADER_PATH
COLUMN_SOURCE
COLUMN_ISSUE_IDS
```

`COLUMN_HEADER_PATH` is the ordered list of header entry IDs. The column list
may be empty. The renderer never invents columns for a sparse or narrative
row.

### 6.3 Logical rows and entries

Every logical row appears in exact ordinal order and contains:

```text
ROW_ORDINAL
ROW_ID
ROW_ROLE
ROW_ROLE_ORIGIN
ROW_NESTING_LEVEL
ROW_PARENT_ID
ROW_SOURCE
ROW_ISSUE_IDS
```

Every row then contains every entry in exact entry-ordinal order:

```text
ENTRY_ORDINAL
ENTRY_ID
ENTRY_KIND
ENTRY_TEXT
ENTRY_ORIGIN
ENTRY_COLUMN_BINDING_STATUS
ENTRY_LOGICAL_COLUMN_ID
ENTRY_COVERS_LOGICAL_COLUMN_IDS
ENTRY_SOURCE
ENTRY_ISSUE_IDS
```

Null, `UNKNOWN`, unresolved column binding and explicit issue references remain
visible. `covers_logical_column_ids` describes one real source entry covering
multiple logical columns; it never produces synthetic covered entries.

The binding truth table is preserved exactly and is independently audited:

- `BOUND` requires a direct `logical_column_id`, a non-empty
  `covers_logical_column_ids`, or both;
- a cover-only `BOUND` entry is valid;
- when a `BOUND` entry has both forms, its direct column must equal the first
  covered column;
- a `SUBTOTAL` or `TOTAL` entry with coverage must use that first covered
  column as its direct column;
- `NOT_APPLICABLE` and `UNKNOWN` have neither a direct nor covered column;
- every `UNKNOWN` binding cites at least one issue present in the top-level
  issue ledger;
- coverage contains at least two distinct existing columns in table order.

A header path may cite only an entry in a `COLUMN_HEADER` or
`CONTINUATION_HEADER` row. That entry must be `BOUND` and must bind the column
directly or include it in its coverage.

## 7. Relations and quality

After the block stream, every relation appears in original order between
`RELATIONS_BEGIN` and `RELATIONS_END`. Relation endpoints preserve block, row
and entry IDs. Evidence anchor IDs are replaced with safe `sources` pointers.

`QUALITY` retains all model-relevant counters and status except its redundant
information-class marker and the two ledgers. Every issue and every known loss
then appears in original order between its begin/end markers, with anchor IDs
replaced by safe pointers.

## 8. Prohibited model-visible data

The following are forbidden anywhere in View v2:

- bbox or other coordinates;
- source, evidence or artifact checksums;
- private artifact or private locator refs;
- geometry evidence IDs or traces;
- continuation-evidence IDs;
- internal confidence scores;
- source-word ownership records or word IDs.

`geometry_evidence` and `source_word_ownership` remain validated Managed
Document v2 evidence but are wholly absent from the view.

View v2 cannot re-prove private geometry. The renderer therefore accepts only
a Managed Document v2 that has already passed its complete schema and semantic
validation; rendering projects that validated truth without replacing it.

The renderer scans decoded JSON string keys and values, not serialized escape
sequences. Private refs, checksums and internal IDs of at least eight
characters fail closed if they occur anywhere inside a rendered string. A
shorter private token fails closed when it equals the complete decoded string
value, but does not fail merely because its characters occur inside a longer
ordinary source string. Private-shaped keys are always rejected after
case/separator-insensitive normalization.

## 9. Independent audit

`ManagedDocumentLlmViewV2Auditor` is an independent stdlib-only grammar and
semantic readback. It imports neither the renderer nor the Managed Document
validator. It rejects malformed physical lines, unknown tag order, unsafe
pointers, private fields, non-continuous ordinals, invalid parent/nesting,
invalid column/header bindings, broken source-part row coverage and invalid
continuation sequences.

The independent auditor has no access to Managed Document private values and
does not guess whether an arbitrary short source string is private. Exact
private-value taint comparison remains the validated Managed Document -> View
renderer boundary; the auditor independently rejects private-shaped fields and
invalid public structure from View bytes alone.

Renderer success is not audit success. Acceptance requires the independent
auditor to reconstruct the complete model-visible row structure.

## 10. Complete model-visible parity

Managed Document and independently parsed View checklists are sealed before a
checklist-only comparison. Pass A rejects a Managed Document whose claimed
`integrity_sha256` does not match its canonical content, including when a
corresponding View was changed in the same way. Every dimension has its own
item count and SHA-256; the comparator verifies those inner seals, the
inventory and the outer seal.
The parity dimensions are exactly:

```text
DOCUMENT
SOURCE_CONTEXT
METADATA
BLOCK
NON_TABLE_BLOCK_CONTENT
TABLE_IDENTITY
TABLE_ASSOCIATION
SOURCE_PART
COLUMN
HEADER_PATH
ROW
ENTRY
RELATION
QUALITY
ISSUE
LOSS
SOURCE_POINTER
```

Row comparison includes order, role, role origin, nesting and parent. Entry
comparison includes row binding, order, kind, exact text and optional logical
column binding. Source-part comparison includes boundary row IDs and
continuation status. The additional dimensions cover source context, metadata,
block order/restoration, non-table content, table relation/issue/gap
associations, relation endpoints and status, quality, issues and losses. Cell
counts, grid dimensions and span counts are not parity authorities.

Required terminal invariant:

```text
MANAGED_DOCUMENT_V2_TO_LLM_VIEW_V2_PARITY = PASSED
CRITICAL_ROW_MISMATCHES_TOTAL = 0
CRITICAL_ENTRY_MISMATCHES_TOTAL = 0
PRIVATE_SOURCE_FIELDS_RENDERED_TOTAL = 0
TRUNCATED_DOCUMENTS_TOTAL = 0
SEMANTIC_FILTERING_TOTAL = 0
```
