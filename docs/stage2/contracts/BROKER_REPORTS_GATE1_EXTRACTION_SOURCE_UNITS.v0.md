# Broker Reports Gate 1 extraction source units v0

Status: implemented
Schema id: `private_normalized_source_unit_v0`

## Purpose

Resolver-gated extraction-grade source unit built only from a `complete` full-source payload. It is the preferred Gate 2 parent unit and is not a chat preview.

## Required fields

| Field | Contract |
|---|---|
| `schema_version` | exactly `private_normalized_source_unit_v0` |
| `unit_ref`, `unit_id` | stable extraction unit ref |
| `parent_payload_ref` | owning `private_normalized_source_payload_v0` |
| `payload_checksum_ref` | parent normalized payload checksum |
| `source_unit_checksum_ref` | checksum binding unit, payload, slice payload and coverage refs |
| `normalization_run_id`, `document_id` | owning scope |
| `slice_id`, `slice_type` | compatibility identity and table/text kind |
| `source_unit_schema_version` | provenance schema `source_unit_provenance_v0` |
| `parser_ref`, `source_checksum_ref`, `slice_payload_checksum_ref` | parser/source/projection provenance |
| `table_ref` / `section_refs` / `page_refs` | location refs where available |
| `row_refs`, `row_range_ref`, `cell_refs`, `cell_value_refs` | table provenance |
| `text_segment_refs`, `character_span_refs` | text provenance |
| `source_value_refs`, `source_value_index` | mechanically reproducible private values |
| `coverage`, `coverage_scope` | exact selected/accounted refs |
| `declared_range_complete` | exactly `true` |
| `source_slice_truncated`, `parent_source_slice_truncated` | exactly `false` |
| `parent_remainder_status` | exactly `not_applicable_parent_complete` |
| `remaining_unit_refs`, `next_unit_refs` | explicit ordered sibling navigation |
| `visibility` | exactly `private_case` |
| `knowledge_rag_used`, `vectorization_performed` | exactly `false` |

## Coverage rules

1. Every selected row/text ref belongs to exactly one coverage bucket.
2. `selected_total == accounted_total` and `all_selected_refs_accounted=true`.
3. Every `source_value_ref` resolves to exactly one private payload path and its checksum reproduces.
4. A unit cannot be minted from a partial or blocked payload.
5. A complete unit may be segmented for model budgets; segmentation preserves refs and does not mint replacement source facts.
6. `remaining_unit_refs` / `next_unit_refs` are explicit; absence of a next unit cannot hide parser truncation.

## Gate 2 preference and legacy fallback

Gate 2 input readiness MUST:

1. resolve `private_normalized_source_unit_v0` first within the DCP scope;
2. validate provenance, coverage and source-value reproduction;
3. use legacy table/text slices only when no full-source units exist for the document;
4. label that path `legacy_bounded_preview_fallback`;
5. set limited expansion readiness false for every legacy fallback package.

For a full-source unit, the Gate 2 package uses:

- `source_input_mode=full_source_unit`;
- `whole_parent_source_coverage_claimed=true`;
- `limited_primary_expansion_ready=true` only when no parent truncation/remainder exists.

## Segmentation

Derived units contain only selected rows/segments and the corresponding narrowed private values. The implementation MUST NOT deep-copy the full parent projection into every segment. Parent coverage must be an ordered, duplicate-free partition and keep explicit deferred segment refs.

## ArtifactStore

- type: `private_normalized_source_unit_v0`;
- visibility: `private_case`;
- backend: `project_artifact_payload`;
- access: resolver + matching user/run/case-or-chat/workspace context;
- retention and purge: inherited from Gate 1 run;
- no chat, Knowledge, RAG or vector backend.

## Non-goals

This contract does not perform tax calculation, consolidation, declaration mapping, XLS/XLSX generation, OCR/VLM, or Gate 3 work.

## Status

`GATE1_EXTRACTION_SOURCE_UNITS_CONTRACT_READY`

## PDF source-unit Slice 1 runtime (2026-07-10)

PDF-specific units extend this generic schema; they do not create a parallel
ArtifactStore type. Proposed unit types are:

- `pdf_page_text_unit`;
- `pdf_section_text_unit`;
- `pdf_line_cluster_unit`;
- `pdf_table_candidate_unit`.

They may be minted only from a complete `pdf_text_layer_projection_v0` and must
carry page/block/line/word/span/value refs as available, plus source, page,
payload and unit checksum refs. Selected/accounted refs remain an exact,
duplicate-free partition. The whole PDF is never copied into a model package.

A table unit is explicitly a geometry candidate. Ambiguous table-like text
falls back to line/page units without losing source refs. A candidate does not
assert semantic table truth, and Gate 2 validators/stitcher are not weakened.

Normative PDF extension:
`BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md`.

`pdf_page_text_unit` is implemented and proven through ArtifactStore resolver
and no-model Gate 2 input readiness. `pdf_line_cluster_unit` remains a bounded
follow-up if a complete page exceeds model-unit budgets; table and summary
units remain deferred.

```text
PDF_TEXT_LAYER_SOURCE_UNITS_RUNTIME_IMPLEMENTED
PDF_PAGE_TEXT_UNIT_RUNTIME_READY
PDF_LINE_CLUSTER_AND_TABLE_RUNTIME_DEFERRED
```

## PDF layout unit Slice 2 runtime (2026-07-10)

`pdf_line_cluster_unit` and `pdf_table_candidate_unit` are now implemented.
Their selected/accounted layout refs form an exact duplicate-free partition;
supplemental source-value refs resolve to bounded unit text. Conflicting table
geometry is rejected to line fallback, and partial parent layout never mints a
layout unit.

```text
PDF_LINE_CLUSTER_UNITS_READY
PDF_TABLE_CANDIDATE_UNITS_READY
PDF_LAYOUT_UNIT_COVERAGE_EXACT
```

## Unified table bridge (2026-07-11)

Extraction source units are now inputs to, not replacements for, [BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md](./BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md). Native row/cell/source-value refs remain unchanged. A PDF candidate becomes a ready table only after deterministic geometry and ownership validation; rejection keeps line fallback coverage and emits no fake cells. Gate 2 table readiness is explicit opt-in through `prefer_table_projections=True` for the no-model slice.
