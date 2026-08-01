# Broker Reports LLM Document View Receipt v1

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_llm_document_view_receipt_v1`

Machine schema: `BROKER_REPORTS_LLM_DOCUMENT_VIEW_RECEIPT.v1.schema.json`

## Purpose

The private receipt binds one validated Managed Document to one deterministic
LLM Document View. It is evidence and accounting, not model-visible document
content.

## Required bindings

The receipt records the input document ID and canonical Managed Document
SHA-256, renderer and view versions, output view SHA-256, bytes, characters,
physical lines, whitespace lexical tokens, exact reference tokenizer identity,
library version and reference token count.

## Coverage

Every input block has one coverage row with block ID, type, ordinal, inclusive
view line range, source-visible projection hash, decoded rendered projection
hash and block reference-token count. Every metadata field has a line range and
projection hash. Every table records input/rendered row, cell and annotation
counts. Relations, issues and losses each have an ordered coverage row with
their ID, ordinal, inclusive view line range, source projection hash and
decoded rendered projection hash.

The aggregate coverage object is fail-closed. Omitted content, table cells,
UNKNOWN blocks, VISUAL blocks, relations and losses are schema-fixed to zero.
Unaccounted omissions, invented source content, private-source rendering,
truncation, block filtering, row filtering and semantic filtering are also
schema-fixed to zero.

## Field dispositions and privacy

The receipt contains the resolved DOC1 field paths, their allowed disposition
and exact owner. An input field without a rule is terminal. Private artifact
refs, source checksums, local paths, resolver/access context and provider
payloads are structurally excluded from the view and represented only by
private receipt accounting.

## Size accounting

All UTF-8 bytes are partitioned into encoded values and renderer overhead.
Metrics are retained by category, page and block type. The sum of
`source_values_bytes` and `renderer_overhead_bytes` must equal output bytes.

## Integrity and replay

The receipt is canonical JSON with sorted keys and compact separators.
`integrity_sha256` covers the full receipt without that field. The renderer
performs one internal exact replay and records `PASSED_SELF_REPLAY`; the corpus
proof additionally compares independent process outputs.

Receipts and full field paths remain private. Git may contain only aggregate,
privacy-scanned safe summaries and artifact hashes.
