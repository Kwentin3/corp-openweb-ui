# Broker Reports PDF text-layer payload v0

Date: 2026-07-10
Status: Slice 2 layout-rich runtime implemented; tables remain non-semantic candidates
Projection schema: `pdf_text_layer_projection_v0`

## Purpose

Format-specific private projection nested in
`private_normalized_source_payload_v0`. It represents an ordered PDF text-layer
projection and its parser/provenance/coverage evidence. It is not a separate
ArtifactStore type and is never chat-visible.

## Generic parent requirements

The parent payload follows
`BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md`, including:

- run/document/profile/parser/source/payload refs;
- `parser_completeness_status` and typed reasons;
- private normalized projection and source-value index;
- exact coverage index;
- resolver-only private persistence;
- `knowledge_rag_used=false` and `vectorization_performed=false`.

## Required PDF projection shape

```json
{
  "schema_version": "pdf_text_layer_projection_v0",
  "projection_policy_ref": "pdf_text_layer_projection_policy_v0",
  "parser_engine": "pypdf|pdfplumber|pymupdf",
  "parser_engine_version": "pinned-version",
  "parser_config_ref": "pdf_parser_config_opaque",
  "requested_capability": "page_text|layout_words|table_candidates",
  "provided_capabilities": [],
  "pdf_content_kind": "text_layer_pdf|mixed_pdf_with_text|raster_pdf_or_image_only|encrypted_or_corrupt|parser_partial_pdf|pdf_text_layer_complete_candidate",
  "declared_page_range": {
    "page_start": 1,
    "page_end": 1,
    "pages_total": 1
  },
  "page_inventory": [],
  "text_fragment_inventory": [],
  "block_inventory": [],
  "line_inventory": [],
  "word_inventory": [],
  "table_candidate_inventory": [],
  "source_value_index": [],
  "page_checksum_refs": [],
  "coverage": {},
  "completeness": {},
  "ocr_vlm_used": false,
  "page_rendering_used_for_extraction": false
}
```

All arrays containing raw text or values are private. Safe reports expose only
counts, statuses, opaque refs and reason-code counts.

## Page inventory entry

Every declared page has exactly one ordered entry:

```json
{
  "page_ref": "pdfpage_opaque",
  "page_number": 1,
  "page_content_kind": "text|mixed|image_only|layout_only|empty|partial",
  "rotation": 0,
  "media_box_ref": "bbox_opaque",
  "crop_box_ref": "bbox_opaque",
  "parser_stream_order_refs": [],
  "geometry_reading_order_refs": [],
  "text_fragment_refs": [],
  "parser_native_content_object_refs": [],
  "block_refs": [],
  "line_refs": [],
  "word_refs": [],
  "non_text_object_counts": {},
  "font_diagnostics": {},
  "content_stream_bytes": 0,
  "page_text_checksum_ref": "pdfpagechk_opaque",
  "page_projection_status": "complete|partial|blocked",
  "reason_codes": []
}
```

An empty page is complete only when its lack of extractable text is itself
accounted and no unresolved text operator/font/decode error exists.

## Text and layout inventories

Required for page-text capability:

- `text_fragment_ref`;
- owning `page_ref`;
- parser ordinal;
- private raw text path and checksum;
- canonical page character range;
- `character_span_ref`;
- optional matrix/bbox ref and coordinate confidence;
- extraction/normalization reason codes.

Optional when the backend provides layout capability:

- block, line, word and character refs;
- bounding-box refs using pinned coordinate precision;
- parser and geometry ordinals;
- contributing fragment/span refs;
- duplicate/hidden/rotated text diagnostics.

Coordinates are supporting evidence. A ref must remain reproducible through
page, ordinal, text checksum and parser policy even when coordinates are
unavailable.

Parser-native object/xref refs are optional private diagnostics. They must not
be the sole stable provenance identity because a byte-changing PDF rewrite may
renumber objects. Source checksum, page ordinal, parser policy, fragment
ordinal and text checksum remain authoritative.

## Source-value index

Every `source_value_ref` resolves to exactly one private payload path and
contains:

- page/fragment/line/word refs as available;
- character span ref in canonical page text;
- normalized private value path;
- raw fragment checksum ref;
- normalized value checksum ref;
- normalization policy ref.

Raw extracted text and normalized value are separate checksum domains.
Normalization cannot erase their linkage.

## Coverage

```json
{
  "schema_version": "pdf_text_layer_coverage_v0",
  "coverage_ref": "pdfcoverage_opaque",
  "declared_page_refs": [],
  "accounted_page_refs": [],
  "selected_text_refs": [],
  "text_candidate_refs": [],
  "blank_or_layout_refs": [],
  "non_text_page_refs": [],
  "table_candidate_refs": [],
  "table_fallback_text_refs": [],
  "partial_or_rejected_refs": [],
  "selected_total": 0,
  "accounted_total": 0,
  "all_declared_pages_accounted": false,
  "all_selected_refs_accounted": false,
  "duplicate_accounted_refs": [],
  "unaccounted_refs": []
}
```

Table candidate refs cannot double-count the same source words/lines as an
independent fact-bearing text unit. Candidate/fallback ownership is explicit
at source-unit construction.

## Completeness

```json
{
  "text_layer_projection_status": "complete|partial|blocked",
  "visible_content_coverage_status": "complete_text_only|partial_out_of_scope|unknown",
  "semantic_reconstruction_status": "not_claimed|candidate|validated_geometry",
  "reason_codes": []
}
```

The generic `parser_completeness_status=complete` requires:

- exact source checksum and pinned parser/version/config;
- all declared pages enumerated and accounted;
- no extraction error, hidden cap or budget overflow;
- no unresolved material font/CMap/operator decode issue;
- raw fragments reconciled to canonical page text;
- every emitted ref/path/checksum reproducible;
- page and payload checksums reproducible;
- exact coverage and no duplicate/unaccounted refs;
- privacy and no-RAG/vector guards passed.

Complete text-layer projection does not promote
`visible_content_coverage_status` for mixed/image content and does not imply
semantic reading-order/table correctness.

## Checksum policy

- `source_checksum_ref`: opaque ref to private raw PDF checksum;
- raw fragment checksum: parser-emitted text before value normalization;
- page checksum: parser identity/config, ordered fragments and page inventory;
- payload checksum: parser identity/config, projection policy and ordered page
  checksums;
- value checksum: normalized private value under a pinned normalization policy.

Canonical JSON ordering, LF normalization and coordinate precision are pinned
by `projection_policy_ref`. Parser/config changes create new payload refs; old
ArtifactStore records are never mutated.

## Typed limitation reasons

Minimum reasons:

```text
pdf_encrypted_without_key
pdf_corrupt_or_unreadable
pdf_page_parse_failed
pdf_content_stream_budget_exceeded
pdf_unknown_font_mapping
pdf_text_operator_decode_incomplete
pdf_page_projection_reconciliation_failed
pdf_layout_backend_unavailable
pdf_coordinate_projection_unverified
pdf_two_engine_material_mismatch
pdf_image_only_no_text_layer
pdf_mixed_visible_content_out_of_scope
```

## Privacy and persistence

- parent artifact type: `private_normalized_source_payload_v0`;
- visibility: `private_case`;
- backend: `project_artifact_payload`;
- resolver and owning scope required;
- no chat, Knowledge, RAG or vector backend;
- retention/expiry/purge inherited from the Gate 1 run;
- raw PDF text, names, ids, paths, accounts and personal data are forbidden in
  reports/chat.

## No-OCR boundary

`ocr_vlm_used=false` and `page_rendering_used_for_extraction=false` are
mandatory. Image-only pages/documents remain unsupported by this contract.

## Status

```text
PDF_TEXT_LAYER_PAYLOAD_CONTRACT_READY
PDF_TEXT_LAYER_PAYLOAD_RUNTIME_IMPLEMENTED
PDF_TEXT_LAYER_PYPDF_6_7_5_PINNED
PDF_TEXT_LAYER_COMPLETE_MEANS_DECLARED_PROJECTION_ONLY
PDF_TEXT_LAYER_NO_OCR_BOUNDARY_READY
```

## Slice 1 runtime profile (2026-07-10)

The implemented `PdfTextLayerParserFactory` supports only
`requested_capability=page_text` and requires exactly `pypdf==6.7.5`. Layout or
table capability requests fail closed; there is no silent downgrade.

The runtime materializes ordered page inventory, parser text fragments,
page-local line/text segments, character spans, source-value refs and index,
page/payload checksums, typed page diagnostics and exact page/text coverage.
Mixed text/image pages may remain complete for the text layer while visible
content is `partial_out_of_scope`. Image-only pages produce
`pdf_image_only_no_text_layer` and keep the document payload partial.

`block_inventory`, `word_inventory` and `table_candidate_inventory` remain
empty in Slice 1. They require the later layout-rich backend and do not affect
the proven page-text projection contract.

## Slice 2 layout-rich runtime profile (2026-07-10)

Layout requests require exactly `pdfplumber==0.11.10` and
`pdfminer.six==20260107`, while `pypdf==6.7.5` remains the independent page-text
baseline. The factory fails closed on import/version/capability drift.

Private char, word, line, block, bbox, vector and table-candidate inventories
carry stable refs and checksums. Page-local reconciliation and exact selected,
accounted and unaccounted ref sets control `complete|partial`; layout failure
never weakens page-text status. OCR/VLM and page rendering remain false.

```text
PDF_LAYOUT_BACKEND_RUNTIME_READY
PDF_LAYOUT_WORD_LINE_REFS_READY
PDF_LAYOUT_CHECKSUMS_READY
PDF_TABLE_CANDIDATES_REMAIN_NON_SEMANTIC
```
