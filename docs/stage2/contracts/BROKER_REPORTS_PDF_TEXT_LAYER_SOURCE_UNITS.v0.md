# Broker Reports PDF text-layer source units v0

Date: 2026-07-10
Status: Slice 2 line-cluster and non-semantic table-candidate units implemented
Parent schema: `private_normalized_source_unit_v0`

## Purpose

PDF-specific bounded unit rules for extraction-grade children of a complete
`pdf_text_layer_projection_v0`. These rules extend, and do not replace,
`BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md`.

## Allowed unit types

| Type | Declared range | Use |
|---|---|---|
| `pdf_page_text_unit` | one complete page projection | default unit |
| `pdf_section_text_unit` | contiguous block/line range under a pinned section policy | deterministic section candidate |
| `pdf_line_cluster_unit` | contiguous line/fragment range | safe fallback and oversized-page split |
| `pdf_table_candidate_unit` | one geometry-qualified table candidate | table-shaped extraction candidate |

`pdf_summary_block_unit` is not defined in v0. Gate 1 must not invent semantic
summary ownership.

## Common required fields

In addition to the generic source-unit fields:

```json
{
  "pdf_unit_type": "pdf_page_text_unit|pdf_section_text_unit|pdf_line_cluster_unit|pdf_table_candidate_unit",
  "pdf_projection_schema_version": "pdf_text_layer_projection_v0",
  "declared_page_refs": [],
  "page_refs": [],
  "block_refs": [],
  "line_refs": [],
  "word_refs": [],
  "text_segment_refs": [],
  "character_span_refs": [],
  "source_value_refs": [],
  "source_value_index": [],
  "coverage": {},
  "source_slice_truncated": false,
  "parent_source_slice_truncated": false,
  "parent_remainder_status": "not_applicable_parent_complete",
  "ocr_vlm_used": false,
  "page_rendering_used_for_extraction": false
}
```

`parser_ref`, source/payload/page/unit checksum refs and parent payload ref are
mandatory.

## Unit creation gate

A PDF unit may be minted only when:

- parent generic payload and PDF projection are complete for the declared
  text-layer projection;
- every selected ref resolves in the parent payload exactly once;
- every source-value path/checksum reproduces;
- the unit range is contiguous under its declared ordering policy;
- selected/accounted coverage reconciles with no duplicates;
- no selected ref belongs to another fact-bearing sibling unit unless the
  overlap is explicit non-fact fallback metadata;
- the unit and parent are not truncated and have no pending remainder.

Mixed/image pages may have a complete text-layer unit while visible content is
out of scope. The unit carries that status and Gate 2 may use only text-backed
facts.

## Page text unit

- one `page_ref`;
- all fact-bearing text refs for the page, unless deterministic layout refs are
  accounted separately;
- ordered page fragment/line refs and full page character range;
- explicit blank/layout/non-text coverage;
- page checksum and parent payload checksum.

Oversized pages are not silently truncated. Use line clusters with an exact
partition or keep the page unit partial/deferred.

## Section and line-cluster units

- contiguous block/line/fragment refs;
- explicit ordering and section/cluster policy ref;
- first/last page and character-span refs;
- sibling/next/deferred refs;
- exact partition of the parent selected refs.

A section label is a safe ordinal/policy result, not source semantic truth.

## Table candidate unit

Required extension:

```json
{
  "table_reconstruction_status": "candidate|validated_geometry",
  "table_strategy_ref": "pdf_table_strategy_opaque",
  "geometry_confidence": "high|medium|low",
  "table_bbox_ref": "bbox_opaque",
  "row_refs": [],
  "cell_refs": [],
  "contributing_word_refs": [],
  "fallback_text_refs": [],
  "reconstruction_reason_codes": []
}
```

Rules:

- `low` confidence does not mint a table candidate unit;
- words/lines are linked to one candidate and one fallback representation, but
  only one becomes the fact-bearing coverage owner;
- geometry conflicts or unresolved merged cells fall back to text/line units;
- Gate 1 does not claim financial/economic row semantics;
- Gate 2 may produce `unknown_source_row` or text-backed source facts, but may
  not upgrade candidate geometry to source truth.

## Coverage

```json
{
  "schema_version": "source_unit_coverage_v0",
  "coverage_ref": "coverage_opaque",
  "selected_source_refs": [],
  "text_candidate_refs": [],
  "deterministic_no_fact_refs": [],
  "layout_or_blank_refs": [],
  "table_candidate_refs": [],
  "rejected_or_deferred_refs": [],
  "selected_total": 0,
  "accounted_total": 0,
  "all_selected_refs_accounted": true,
  "duplicate_accounted_refs": [],
  "unaccounted_refs": []
}
```

Every selected ref is in exactly one accounted bucket. Fallback metadata does
not create a second coverage owner.

## Gate 2 package rule

Gate 2 readiness resolves and validates the generic unit first. A PDF package:

- uses `source_input_mode=full_source_unit`;
- includes `pdf_unit_type` and safe layout/candidate policy metadata;
- contains only the bounded private projection and allowed source-value refs;
- never contains the whole PDF or unseen pages;
- preserves all parent/source/page/payload/unit checksums;
- keeps existing issue, privacy, fact and stitch validators unchanged.

Derived segmentation partitions parent refs exactly once and records all
deferred siblings. One valid PDF unit does not establish whole-document or
whole-case completeness beyond its declared range.

## Persistence and privacy

- artifact type: `private_normalized_source_unit_v0`;
- visibility: `private_case`;
- backend: `project_artifact_payload`;
- resolver + matching user/run/case-or-chat/workspace scope required;
- no chat, Knowledge, RAG or vector persistence;
- safe reports expose only counts, statuses and reason codes.

## Non-goals

- OCR/VLM or image-text inference;
- guaranteed visual reading order;
- guaranteed semantic table reconstruction;
- Gate 1 financial fact interpretation;
- tax, consolidation, declaration, XLS/XLSX or Gate 3.

## Status

```text
PDF_TEXT_LAYER_SOURCE_UNITS_CONTRACT_READY
PDF_PAGE_TEXT_UNIT_RUNTIME_IMPLEMENTED
PDF_TABLES_REMAIN_CANDIDATES
PDF_SOURCE_UNITS_RESOLVER_GATED
```

## Slice 1 runtime profile (2026-07-10)

The runtime mints one `pdf_page_text_unit` for each text-bearing page only when
the whole parent `pdf_text_layer_projection_v0` is complete. Blank pages remain
explicitly accounted in parent coverage and do not create empty model units.
If any page is image-only or parser-partial, the parent remains partial and no
page units are minted for that document.

`pdf_line_cluster_unit` is contract-valid but was not needed by the proven
fixtures/customer PDFs because no complete page exceeded the configured
page-text budget. Budget overflow fails partial without truncation.
`pdf_table_candidate_unit` and semantic summary units remain unimplemented.

## Slice 2 layout source-unit runtime (2026-07-10)

Complete layout pages now partition selected word/line refs into bounded
`pdf_line_cluster_unit` and `pdf_table_candidate_unit` artifacts. Candidate
ownership requires complete contributing lines; overlap or ambiguity falls
back to line clusters. Unit text, bbox, page, source-value and checksum refs
resolve through the private parent payload. A table candidate asserts geometry
only, never semantic table truth.

```text
PDF_LINE_CLUSTER_UNITS_READY
PDF_TABLE_CANDIDATE_UNITS_READY
PDF_TABLE_CANDIDATES_REMAIN_NON_SEMANTIC
```

## Table projection hardening (2026-07-11)

`pdf_table_candidate_unit` remains a geometry candidate. [BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md](./BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md) adds the only promotion gate to `validated_geometry`: candidate inventory, confidence, row/column minimums, bbox presence, unique word-to-cell ownership and exact contributing-word coverage. `validated_geometry` is structural only. Failed candidates become `rejected_to_line_cluster`, preserve fallback/rejected refs and contain no rows/cells.
