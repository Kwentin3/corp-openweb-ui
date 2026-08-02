# Broker Reports LLM Document View v2

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_llm_document_view_v2`

Owner: `ManagedDocumentLlmViewV2Factory`

## Decision

LLM Document View v2 is the deterministic span-aware tagged-text projection
of a validated Managed Document v2. It remains derived, provider-free and
disconnected from every product route. Historical View v1 bytes and grammar
remain unchanged.

The authority chain is:

```text
source PDF -> Managed Document v2 -> LLM Document View v2
```

The v2 codec reuses the historical v1 tagged-text encoding for unchanged
fields. Only the version markers and TABLE span records are additive.

## Encoding

UTF-8 without BOM and LF line endings are mandatory. Source-derived values are
compact canonical JSON on one physical line. The outer markers are:

```text
BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2
CONTENT_TRUST UNTRUSTED_SOURCE_DOCUMENT
DOCUMENT_BEGIN
...
DOCUMENT_END
END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2
```

There is exactly one final LF. Empty physical lines, CR, duplicate JSON keys
and data after the end marker are invalid.

## Span-aware TABLE records

Rows remain explicit `ROW <index> <json-array>` records. After the rows and
before cell states, every span appears exactly once in Managed Document order:

```text
CELL_SPAN {"covers":{"column_end":3,"column_start":0,"row_end":4,"row_start":4},"issue_ids":[],"origin":"DETERMINISTIC_DERIVED","sources":[{"anchor_id":"anchor_safe","format":"PDF","page":1,"source_part_index":1}],"span_id":"span_safe","value_at":[4,0]}
```

`sources` contains only v1-safe anchor pointers. Checksums, bbox, source block
refs, private locators, parser refs and storage refs are forbidden.

Every covered coordinate remains an explicit cell state:

```text
CELL_STATE {"column_index":1,"evidence_anchor_ids":[],"issue_ids":[],"origin":"DETERMINISTIC_DERIVED","row_index":4,"span_id":"span_safe","state":"COVERED_BY_SPAN"}
```

An auditor must never interpret `COVERED_BY_SPAN` as `EMPTY`. Non-covered
states carry `"span_id":null`.

## Independent readback

`ManagedDocumentLlmViewV2Auditor` is the view-only grammar owner. It imports
neither the renderer nor a Managed Document validator. It reconstructs each
span ID, value coordinate, covered range, covered coordinates and cell state,
then independently rejects overlap, orphan coverage, non-null covered values,
out-of-range coordinates and state/span disagreement.

Mandatory exact parity is:

```text
INPUT_SPANS_TOTAL = RENDERED_SPANS_TOTAL
INPUT_COVERED_COORDINATES_TOTAL = RENDERED_COVERED_COORDINATES_TOTAL
SPAN_PARITY_MISMATCHES_TOTAL = 0
```

## Non-change boundary

- View v1 module, contract, fixtures and artifacts are historical read-only.
- V2 performs no selection, summarization, repair or semantic inference.
- Private geometry never enters the model-visible view.
- No provider, RAG, embedding, vectorization, Gate 2, product or live route is
  reachable from this inactive codec.
