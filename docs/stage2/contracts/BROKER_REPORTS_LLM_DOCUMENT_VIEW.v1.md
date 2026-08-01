# Broker Reports LLM Document View v1

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_llm_document_view_v1`

Owner: `ManagedDocumentLlmViewFactory`

## 1. Decision

LLM Document View v1 is one deterministic UTF-8 tagged-text projection of a
validated Managed Document v1. It changes representation only. It does not
select, summarize, rank, repair, translate or interpret source content.

Authority remains:

```text
source document -> Managed Document v1 -> LLM Document View v1
```

The view is derived and reproducible. It is not a fact store, document
authority, prompt, retrieval index or product route.

## 2. Encoding and physical-line law

The file uses UTF-8 without BOM and LF line endings. Every source-derived
value is one compact JSON value with `ensure_ascii=false`, sorted object keys
and separators `(",", ":")`. JSON escaping keeps quotes, backslashes, tabs,
newlines, HTML, Markdown and renderer-like text inside the value. No source
value may create a physical renderer line.

The file begins exactly with:

```text
BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1
CONTENT_TRUST UNTRUSTED_SOURCE_DOCUMENT
DOCUMENT_BEGIN
```

It ends exactly with:

```text
DOCUMENT_END
END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1
```

Only one final LF follows the end marker. Empty physical lines, CR, BOM,
duplicate JSON keys and content after the end marker are invalid.

## 3. Document passport

The fixed passport records are:

```text
DOCUMENT_ID <json-string>
SOURCE_FORMAT <json-string>
SOURCE_PARTS_TOTAL <json-integer>
DOCUMENT_QUALITY_STATUS <json-string>
KNOWN_LOSSES_TOTAL <json-integer>
BLOCKING_LOSSES_TOTAL <json-integer>
UNKNOWN_BLOCKS_TOTAL <json-integer>
SOURCE_CONTEXT <json-object>
```

`SOURCE_CONTEXT` contains only MIME type and typed `source_details`. It excludes
the source checksum, private artifact, filename, path, resolver context and
access context.

## 4. Metadata and anchors

All eight required passport fields and every named additional field appear in
Managed Document order:

```text
METADATA_BEGIN
METADATA "title"
STATUS "UNKNOWN"
ORIGIN "UNKNOWN_ORIGIN"
VALUE null
CANDIDATES []
SOURCE []
METADATA_END
...
METADATA_SECTION_END
```

Unknown and not-applicable metadata is never omitted. `SOURCE` is an array of
safe anchor pointers. The complete anchor registry then appears once:

```text
ANCHORS_BEGIN
ANCHOR {"anchor_id":"anchor_safe","format":"PDF","page":1,"source_part_index":1}
ANCHORS_END
```

Safe pointers may contain anchor ID, source format, source part, page, row and
column ranges, or source ordinal. They never contain checksums, bbox, private
locator, DOM path, sheet name, cell range, parser ref or storage ref.

## 5. Ordered block stream

`BLOCKS_BEGIN` is followed by exactly one record for every Managed Document
block in `blocks[].ordinal` order. Grouping by type is forbidden.

Every block has this envelope:

```text
BLOCK_BEGIN
ORDINAL 0
BLOCK_ID "block_safe"
BLOCK_TYPE "PARAGRAPH"
SOURCE [{"anchor_id":"anchor_safe","format":"PDF","page":1,"source_part_index":1}]
RESTORATION_STATUS "RESTORED"
STRUCTURE_ORIGIN "DETERMINISTIC_DERIVED"
RESTORATION_ISSUE_IDS []
ISSUE_IDS []
<type-specific records>
BLOCK_END
```

After the final block the stream closes with `BLOCKS_END`.

### HEADING

```text
HEADING_TEXT <json-string>
HEADING_LEVEL_STATUS <json-string>
HEADING_LEVEL <json-integer-or-null>
```

### PARAGRAPH

```text
TEXT <json-string>
JOIN_EVENT <json-object>
```

Every join event is preserved. The renderer never creates a heading or joins
paragraphs.

### LIST

```text
LIST_BEGIN
ITEM 0 <json-object>
ITEM 1 <json-object>
LIST_END
```

The indexed prefix and each item's `ordinal` must agree.

### NOTE

```text
NOTE {"note_kind":"FOOTNOTE","text":"Synthetic note."}
```

Relations remain in the relation ledger; the renderer does not infer a target.

### BOUNDARY

```text
BOUNDARY {"kind":"PAGE","label":{"candidates":[],"origin":"UNKNOWN_ORIGIN","sources":[],"status":"UNKNOWN","value":null},"source_part_index":1}
```

PAGE, SHEET and SOURCE_PART boundaries remain real ordered blocks.

## 6. TABLE

A table stays at its original block ordinal. Markdown tables are forbidden.

```text
TABLE_BEGIN
TABLE_ID "table_safe"
TITLE {"candidates":[],"origin":"UNKNOWN_ORIGIN","sources":[],"status":"UNKNOWN","value":null}
DESCRIPTION "Synthetic table."
COMPLETENESS "PARTIAL"
ROWS_TOTAL 2
COLUMNS_MAX_TOTAL 2
HEADER_HIERARCHY {"entries":[],"status":"UNKNOWN"}
ROW_GROUPS {"groups":[],"status":"UNKNOWN"}
ROW_MARKER <json-object>
UNIT <json-object>
ROW 0 ["Label","Value"]
ROW 1 ["Synthetic A",null]
CELL_STATE {"column_index":1,"evidence_anchor_ids":[],"issue_ids":[],"origin":"SOURCE_EXPLICIT","row_index":1,"state":"EMPTY"}
RELATED_RELATION "relation_safe"
CONTINUATION_RELATION "relation_safe"
KNOWN_GAP "loss_safe"
TABLE_END
```

All rows and all cells appear in logical order. JSON `null` and the PRESENT,
EMPTY, UNREADABLE and UNKNOWN annotations remain distinct. Header hierarchy,
row groups, markers, units, relations and known gaps are never silently
discarded; an UNKNOWN status remains visible.

## 7. UNKNOWN and VISUAL

UNKNOWN uses:

```text
UNKNOWN_REASON "pdf_table_grid_not_validated"
RAW_TEXT <json-string-or-null>
PRIVATE_SOURCE_AVAILABLE true
```

VISUAL uses:

```text
VISUAL_TYPE "UNKNOWN"
CAPTION <status-bearing-json-object>
DESCRIPTION <status-bearing-json-object>
PROCESSING_STATUS "UNPROCESSED"
PRIVATE_SOURCE_AVAILABLE true
```

Only the availability boolean represents a private artifact. Its ref,
checksum and bytes never enter the view. An unprocessed visual stays visible
and is not described by the renderer.

## 8. Relations, quality, issues and losses

After the block stream, relations retain Managed Document order:

```text
RELATIONS_BEGIN
RELATION <json-object-with-safe-evidence-pointers>
RELATIONS_END
```

`QUALITY` contains all quality status and counters except its information-class
label and the two ledgers. The ledgers follow in original order:

```text
QUALITY <json-object>
ISSUES_BEGIN
ISSUE <json-object-with-safe-source-pointers>
ISSUES_END
LOSSES_BEGIN
LOSS <json-object-with-safe-source-pointers>
LOSSES_END
```

The renderer creates no relation, issue or loss. It preserves every message,
reason, affected ID, status, recoverability flag and safe source pointer.

## 9. Information classes and omissions

- `CONTENT`: rendered in full.
- `PROVENANCE`: rendered as bounded safe pointers.
- `CONTROL`: model-relevant quality/restoration fields are rendered; internal
  policy, hash and producer fields remain in the private receipt.
- `PRIVATE_SOURCE`: never rendered; only an availability boolean may be shown.

The machine authority is
`BROKER_REPORTS_DOC1_TO_DOC3_VIEW_COVERAGE.v1.json`. Each concrete input field
must resolve to exactly one of `RENDERED`, `RENDERED_AS_SAFE_POINTER`,
`OMITTED_CONTROL_FIELD`, `OMITTED_PRIVATE_SOURCE_FIELD`, or
`OMITTED_REDUNDANT_WITH_EXACT_OWNER`. `UNACCOUNTED_FIELD` is terminal.

## 10. Reference tokenizer

The reference tokenizer is `broker_reports_utf8_byte_bpe_v1`, implemented by
the pinned `tiktoken==0.12.0` library with an in-memory 256-byte vocabulary.
It performs no network or vocabulary-file read and round-trips exact UTF-8.
Its token count is an exact reference count, not a model context-window claim.
Model-specific counting remains DOC4 work after an exact candidate exists.

## 11. Required invariants

```text
PRIMARY_BLOCK_ORDER_PRESERVED = TRUE
CONTENT_BLOCKS_OMITTED_TOTAL = 0
TABLE_CELLS_OMITTED_TOTAL = 0
UNKNOWN_BLOCKS_OMITTED_TOTAL = 0
VISUAL_BLOCKS_OMITTED_TOTAL = 0
RELATIONS_OMITTED_TOTAL = 0
KNOWN_LOSSES_OMITTED_TOTAL = 0
UNACCOUNTED_RENDER_OMISSIONS_TOTAL = 0
INVENTED_SOURCE_CONTENT_TOTAL = 0
PRIVATE_SOURCE_FIELDS_RENDERED_TOTAL = 0
TRUNCATED_DOCUMENTS_TOTAL = 0
SEMANTIC_FILTERING_TOTAL = 0
```

The independent auditor owns the grammar readback. It imports neither the
renderer nor the Managed Document validator. Managed Document-to-view parity
uses separately sealed Pass A and Pass B checklists and a checklist-only Pass C.
