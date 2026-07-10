# Broker Reports Document Normalization Artifacts v0 Proposal

Status: GATE1_ARTIFACT_CONTRACTS_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 artifact contracts

## 1. Purpose

This proposal defines Gate 1 "Document Intake & Normalization" artifacts.

The artifacts sit between raw OpenWebUI uploads and source-fact extraction:

```text
uploaded files
-> normalization run
-> safe inventory/profile/slices/taxonomy/blockers
-> case package refs
-> next gate: source-fact extraction
```

These contracts are proof contracts, not production implementation code.

## 2. Relation To Existing Contract Family

Gate 1 artifacts connect to:

- `BROKER_REPORTS_DATA_CONTRACT_FAMILY.v0.md`
- `BROKER_REPORTS_CASE_PACKAGE_CONTRACT.v0_PROPOSAL.md`
- `BROKER_REPORTS_DOCUMENT_TAXONOMY.v0.md`
- `BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL.md`
- `BROKER_REPORTS_INTERMEDIATE_LEDGERS_CONTRACT.v0_PROPOSAL.md`
- `BROKER_REPORTS_REVIEW_STATE_CONTRACT.v0_PROPOSAL.md`
- `BROKER_REPORTS_CONTRACT_VALIDATION_RULES.v0.md`

Gate 1 produces `document_inventory_ref`, `document_id`, `case_group_id`, taxonomy candidates and blocker refs. Source-facts contracts consume selected safe document refs later. Ledgers and declaration-oriented contracts do not consume raw Gate 1 slices directly.

## 3. Shared Rules

Visibility values:

- `private`: internal artifact, not shown in chat, not committed.
- `safe`: may be used in repo docs/reports if it contains only safe ids and aggregates.
- `chat-visible`: safe summary intended for OpenWebUI chat.

ID pattern recommendations:

- `normalization_run_id`: `normrun_<date>_<short_hash>`
- `document_inventory_id`: `docinv_<short_hash>`
- `document_id`: existing safe `brdoc_*` or generated `brdoc_<ordinal>_<hash>`
- `slice_id`: `txtslice_*` or `tblslice_*`
- `blocker_id`: `blocker_*`
- `report_id`: `normreport_*`

All public refs must use safe ids. Private OpenWebUI file ids, original filenames and local paths stay private.

## 4. Privacy Rules

Forbidden in safe/chat-visible artifacts:

- raw customer filenames if they may contain PII;
- private local paths;
- raw account numbers;
- addresses, phones, emails and passport/ID data;
- full financial operation rows;
- secrets, keys and environment values.

Private by default:

- `broker_reports_normalized_text_slice_v0`
- `broker_reports_normalized_table_slice_v0`
- original OpenWebUI file refs;
- parser diagnostics that include raw text or filenames.

Safe projections of slices are allowed only after review/redaction.

## 5. Artifact: `broker_reports_normalization_run_v0`

Purpose: identify one Gate 1 run and connect input refs to output artifact refs.

Visibility: private with safe projection.

Required fields:

- `schema_version`
- `normalization_run_id`
- `created_at`
- `trigger_type`
- `run_status`
- `input_document_count`
- `artifact_refs`
- `safety_flags`

Allowed fields:

- `case_id`
- `case_group_id`
- `openwebui_context_ref_private`
- `normalizer_version`
- `parser_engine_versions`
- `completed_at`
- `error_summary_safe`

Forbidden fields in safe projection:

- raw OpenWebUI file ids if treated as private;
- raw filenames;
- local paths;
- raw text/table rows.

Shape:

```json
{
  "schema_version": "broker_reports_normalization_run_v0",
  "normalization_run_id": null,
  "case_id": null,
  "case_group_id": null,
  "created_at": null,
  "completed_at": null,
  "trigger_type": "action | tool | slash_prompt | openapi_tool_server",
  "run_status": "completed | completed_with_blockers | failed_safe",
  "input_document_count": 0,
  "artifact_refs": {
    "document_inventory_ref": null,
    "technical_readability_profile_ref": null,
    "text_slices_ref_private": null,
    "table_slices_ref_private": null,
    "zip_member_inventory_ref": null,
    "taxonomy_candidates_ref": null,
    "normalization_blockers_ref": null,
    "chat_visible_report_ref": null
  },
  "safety_flags": {
    "tax_correctness_claimed": false,
    "source_fact_extraction_performed": false,
    "declaration_generated": false,
    "xlsx_generated": false,
    "manual_review_required": true
  }
}
```

Relation: referenced by the case package as the intake run behind `document_inventory_ref`.

## 6. Artifact: `broker_reports_document_inventory_v0`

Purpose: safe inventory of uploaded documents and their technical identity.

Visibility: safe.

Required fields:

- `schema_version`
- `document_inventory_id`
- `normalization_run_id`
- `documents[]`

Required `documents[]` fields:

- `document_id`
- `sanitized_filename` or `original_filename_hash`
- `sanitized_relative_path` or `relative_path_hash`
- `extension`
- `detected_mime`
- `size_bytes`
- `modified_time`
- `sha256`
- `readable`
- `container_format`

Allowed fields:

- `duplicate_of_document_id`
- `source_upload_order`
- `parser_status`
- `safe_label`
- `case_group_id`

Forbidden fields:

- raw filename when it may contain PII;
- private local path;
- full raw relative path;
- raw account number.

Shape:

```json
{
  "schema_version": "broker_reports_document_inventory_v0",
  "document_inventory_id": null,
  "normalization_run_id": null,
  "documents": [
    {
      "document_id": null,
      "original_filename_hash": null,
      "sanitized_filename": null,
      "relative_path_hash": null,
      "sanitized_relative_path": null,
      "extension": null,
      "detected_mime": null,
      "size_bytes": null,
      "modified_time": null,
      "sha256": null,
      "readable": "yes | no",
      "container_format": "pdf | xlsx | xls | csv | txt | docx | image | zip | unknown",
      "duplicate_of_document_id": null,
      "case_group_id": null
    }
  ]
}
```

Relation: extends the existing document inventory/manifest concept in the contract family. Source facts later reference `document_id`, not raw filenames.

## 7. Artifact: `broker_reports_technical_readability_profile_v0`

Purpose: describe parser suitability and technical blockers per document.

Visibility: safe with redaction.

Required fields:

- `schema_version`
- `profile_id`
- `normalization_run_id`
- `profiles[]`

Required `profiles[]` fields:

- `document_id`
- `container_format`
- `parser_status`
- `machine_readable`
- `confidence`

Allowed fields:

- `pdf`
- `workbook`
- `csv_txt`
- `docx`
- `image`
- `zip`
- `unsupported_reason`

Forbidden fields:

- raw text excerpts;
- raw table rows;
- raw sheet names if they contain PII;
- parser logs containing private paths.

Shape:

```json
{
  "schema_version": "broker_reports_technical_readability_profile_v0",
  "profile_id": null,
  "normalization_run_id": null,
  "profiles": [
    {
      "document_id": null,
      "container_format": null,
      "parser_status": "readable | partially_readable | unreadable | unsupported | blocked",
      "machine_readable": "yes | no | conditional",
      "confidence": "high | medium | low",
      "pdf": {
        "pages_count": null,
        "text_layer": "yes | no | unknown",
        "raster_likelihood": "yes | no | unknown",
        "tables_detected": "yes | no | unknown",
        "ocr_needed": "yes | no | conditional"
      },
      "workbook": {
        "sheets_count": null,
        "safe_sheet_names": [],
        "sheet_names_redacted": true,
        "formulas_present": "yes | no | unknown",
        "hidden_sheets_count": null,
        "readable_by_openpyxl_or_pandas": "yes | no | unknown",
        "workbook_role_candidate": "source_input | calculation_template | output_artifact | unknown"
      },
      "csv_txt": {
        "encoding": null,
        "delimiter": null,
        "rows_count": null,
        "columns_count": null,
        "columns_summary_safe": [],
        "machine_readable_table": "yes | no | conditional"
      },
      "docx": {
        "paragraph_estimate": null,
        "headings_summary_safe": [],
        "document_role_candidate": "explanation_template | methodology | output_example | unknown"
      },
      "zip": {
        "members_count": null,
        "requires_review": true
      }
    }
  ]
}
```

Relation: feeds taxonomy candidates, blockers and proof readiness.

## 8. Artifact: `private_normalized_text_slice_v0`

Purpose: store bounded parser-produced text slices for the next gate.

Visibility: private by default.

Required fields:

- `schema_version`
- `source_unit_schema_version=source_unit_provenance_v0`
- `slice_id`
- `normalization_run_id`
- `document_id`
- `source_location`
- `text`
- `text_segment_refs`
- `section_refs`
- `page_refs` and `page_range_ref` where the parser provides page location
- `character_span_refs`
- `segment_provenance`
- `source_value_refs`
- `source_value_index`
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`
- `parser_ref`
- `source_checksum_ref`
- `slice_payload_checksum_ref`
- `safe_section_labels`
- `safe_coverage_refs`
- `coverage`

Allowed fields:

- `language_hint`
- `char_count`
- `parser`
- parser-produced profile and extraction metadata already allowed by the Gate 1
  private-slice payload

Forbidden fields in chat-visible output:

- full raw text pages;
- personal identifiers;
- account numbers;
- raw filenames or private paths.

Shape:

```json
{
  "schema_version": "private_normalized_text_slice_v0",
  "source_unit_schema_version": "source_unit_provenance_v0",
  "slice_id": null,
  "normalization_run_id": null,
  "document_id": null,
  "source_location": {
    "page": null,
    "section": null,
    "paragraph_index": null
  },
  "text": null,
  "text_segment_refs": [],
  "section_refs": [],
  "page_refs": [],
  "page_range_ref": null,
  "character_span_refs": [],
  "segment_provenance": [
    {
      "text_segment_ref": null,
      "section_ref": null,
      "safe_section_label": "section_001",
      "page_ref": null,
      "page_range_ref": null,
      "character_span_ref": null,
      "character_start": 0,
      "character_end": 0,
      "segment_kind": "blank | text_candidate",
      "source_value_ref": null,
      "value_checksum_ref": null
    }
  ],
  "source_value_refs": [],
  "source_value_index": [],
  "source_value_projection_policy": "private_payload_path_plus_checksum_v0",
  "parser_ref": null,
  "source_checksum_ref": null,
  "slice_payload_checksum_ref": null,
  "safe_section_labels": [],
  "safe_coverage_refs": [],
  "coverage": {
    "schema_version": "source_unit_coverage_v0",
    "coverage_ref": null,
    "unit_kind": "text_slice",
    "selected_source_refs": [],
    "blank_refs": [],
    "text_candidate_refs": [],
    "selected_total": 0,
    "accounted_total": 0,
    "all_selected_refs_accounted": true
  }
}
```

Relation: can become input to source-fact extraction only through approved
private access. It is not a source fact. Every selected segment is represented
exactly once in `blank_refs` or `text_candidate_refs`. Original values are
resolved by the indexed character span plus checksum; raw text is never copied
into a safe projection.

## 9. Artifact: `private_normalized_table_slice_v0`

Purpose: store bounded parser-produced table slices for the next gate.

Visibility: private by default.

Required fields:

- `schema_version`
- `source_unit_schema_version=source_unit_provenance_v0`
- `slice_id`
- `normalization_run_id`
- `document_id`
- `source_location`
- bounded private `cells` payload
- `table_ref`
- `row_refs`
- `row_range_ref`
- `cell_refs`
- `cell_value_refs`
- `source_value_refs`
- `normalized_header_descriptors`
- `row_provenance`
- `cell_provenance`
- `source_value_index`
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`
- `parser_ref`
- `source_checksum_ref`
- `slice_payload_checksum_ref`
- `safe_coverage_refs`
- `coverage`

Allowed fields:

- `columns_summary_safe`
- `header_confidence`
- `parser`
- parser-produced profile and extraction metadata already allowed by the Gate 1
  private-slice payload

Forbidden fields in chat-visible output:

- full financial operation rows;
- full securities operation ledgers;
- account identifiers;
- raw filenames or paths.

Shape:

```json
{
  "schema_version": "private_normalized_table_slice_v0",
  "source_unit_schema_version": "source_unit_provenance_v0",
  "slice_id": null,
  "normalization_run_id": null,
  "document_id": null,
  "source_location": {
    "page": null,
    "sheet_index": null,
    "table_index": null,
    "row_range": null
  },
  "cells": [],
  "table_ref": null,
  "row_refs": [],
  "row_range_ref": null,
  "cell_refs": [],
  "cell_value_refs": [],
  "source_value_refs": [],
  "normalized_header_descriptors": [],
  "row_provenance": [
    {
      "row_ref": null,
      "row_range_ref": null,
      "row_ordinal": 1,
      "row_kind": "header | blank | layout | fact",
      "row_checksum_ref": null,
      "cell_refs": [],
      "source_value_refs": []
    }
  ],
  "cell_provenance": [
    {
      "cell_ref": null,
      "cell_value_ref": null,
      "source_value_ref": null,
      "row_ref": null,
      "row_ordinal": 1,
      "column_ordinal": 1,
      "value_checksum_ref": null
    }
  ],
  "source_value_index": [],
  "source_value_projection_policy": "private_payload_path_plus_checksum_v0",
  "parser_ref": null,
  "source_checksum_ref": null,
  "slice_payload_checksum_ref": null,
  "safe_coverage_refs": [],
  "coverage": {
    "schema_version": "source_unit_coverage_v0",
    "coverage_ref": null,
    "unit_kind": "table_row_window",
    "selected_source_refs": [],
    "header_candidate_refs": [],
    "blank_refs": [],
    "layout_candidate_refs": [],
    "fact_candidate_refs": [],
    "selected_total": 0,
    "accounted_total": 0,
    "all_selected_refs_accounted": true
  }
}
```

Relation: source-fact extraction may reference table source-unit refs, but
extracted source facts must still carry evidence wrappers, original-value refs
and deterministic validation. Each selected row is accounted exactly once as a
header, blank, layout or fact candidate. Original values resolve through a
private row/column payload path and checksum.

`NormalizedSliceProvenanceFactory.create` is the only production entrypoint
that may mint these table/text provenance refs. Profilers, Gate 2 builders and
smoke scripts consume or validate them; they must not independently construct
row, cell, segment or source-value refs.

## 10. Artifact: `broker_reports_zip_member_inventory_v0`

Purpose: safely describe archive contents before unpack/review.

Visibility: safe if member names are hashed/sanitized.

Required fields:

- `schema_version`
- `zip_inventory_id`
- `normalization_run_id`
- `zip_document_id`
- `members[]`

Required `members[]` fields:

- `member_id`
- `member_path_hash` or `sanitized_member_path`
- `extension`
- `size_bytes`
- `container_candidate`
- `review_action`

Allowed fields:

- `compressed_size_bytes`
- `sha256`
- `nested_archive`
- `signature_file_candidate`

Forbidden fields:

- raw archive member path if it contains PII;
- extracted member content;
- private extraction path.

Shape:

```json
{
  "schema_version": "broker_reports_zip_member_inventory_v0",
  "zip_inventory_id": null,
  "normalization_run_id": null,
  "zip_document_id": null,
  "members": [
    {
      "member_id": null,
      "member_path_hash": null,
      "sanitized_member_path": null,
      "extension": null,
      "size_bytes": null,
      "compressed_size_bytes": null,
      "sha256": null,
      "container_candidate": "pdf | xml | signature | archive | unknown",
      "nested_archive": false,
      "review_action": "block_until_review | allow_after_policy | unsupported"
    }
  ]
}
```

Relation: ZIP archives remain conditional under validation rules until unpack/review is explicit.

## 11. Artifact: `broker_reports_document_taxonomy_candidates_v0`

Purpose: provide conservative primary and alternative document class candidates.

Visibility: safe if reasons do not include raw snippets.

Required fields:

- `schema_version`
- `taxonomy_candidates_id`
- `normalization_run_id`
- `candidates[]`

Required `candidates[]` fields:

- `document_id`
- `primary_class`
- `alternative_classes`
- `confidence`
- `can_be_source_evidence`
- `can_be_methodology`
- `can_be_loaded_to_knowledge`
- `declaration_relevance`

Allowed fields:

- `safe_reason_codes`
- `requires_human_review`
- `taxonomy_version_ref`

Forbidden fields:

- raw text excerpts;
- raw filenames;
- full operation rows.

Shape:

```json
{
  "schema_version": "broker_reports_document_taxonomy_candidates_v0",
  "taxonomy_candidates_id": null,
  "normalization_run_id": null,
  "taxonomy_version_ref": "BROKER_REPORTS_DOCUMENT_TAXONOMY.v0",
  "candidates": [
    {
      "document_id": null,
      "primary_class": "source_broker_report | operations_table | dividends_report | withholding_report | fees_report | currency_rate_table | official_form | official_filling_instruction | official_electronic_format | methodology_instruction | calculation_template | tax_base_calculation | explanation_template | expected_output_example | broker_help_article | public_layout_sample | synthetic_fixture | customer_sample_pending_review | unrelated | unsupported | unknown_or_needs_review",
      "alternative_classes": [],
      "confidence": "high | medium | low",
      "safe_reason_codes": [],
      "can_be_source_evidence": "yes | no | conditional",
      "can_be_methodology": "yes | no | conditional",
      "can_be_loaded_to_knowledge": "yes | no | after_review",
      "declaration_relevance": "source_fact | official_requirement | methodology | review_output | layout_only | none",
      "requires_human_review": true
    }
  ]
}
```

Relation: uses the document taxonomy contract. Source facts later reference approved evidence documents only.

## 12. Artifact: `broker_reports_normalization_blockers_v0`

Purpose: collect blockers and review issues created during Gate 1.

Visibility: safe.

Required fields:

- `schema_version`
- `blockers_id`
- `normalization_run_id`
- `blockers[]`

Required `blockers[]` fields:

- `blocker_id`
- `document_id`
- `blocker_type`
- `severity`
- `safe_message`
- `blocks_next_gate`
- `next_action`

Allowed fields:

- `review_state_issue_ref`
- `related_member_id`
- `resolved_status`

Forbidden fields:

- raw snippets;
- raw filenames;
- private paths;
- full parser logs.

Shape:

```json
{
  "schema_version": "broker_reports_normalization_blockers_v0",
  "blockers_id": null,
  "normalization_run_id": null,
  "blockers": [
    {
      "blocker_id": null,
      "document_id": null,
      "related_member_id": null,
      "blocker_type": "zip_requires_review | raster_requires_ocr_or_review | unsupported_format | encrypted_file | corrupt_file | parser_failed | unknown_role | privacy_violation | duplicate_review | missing_case_group",
      "severity": "blocking | warning",
      "safe_message": null,
      "blocks_next_gate": true,
      "next_action": "review | request_replacement | approve_unpack | approve_ocr | exclude | retry_parser",
      "review_state_issue_ref": null,
      "resolved_status": "open | resolved | deferred"
    }
  ]
}
```

Relation: blocker records may be summarized into `broker_reports_review_state_v0_proposal` issue groups.

## 13. Artifact: `broker_reports_chat_visible_normalization_report_v0`

Purpose: safe report returned to the same OpenWebUI chat.

Visibility: chat-visible.

Required fields:

- `schema_version`
- `report_id`
- `normalization_run_id`
- `run_status`
- `summary_counts`
- `case_groups`
- `blocker_summary`
- `recommended_next_step`
- `safety_statement`

Allowed fields:

- `safe_artifact_refs`
- `selected_case_group_prompt`
- `document_class_counts`
- `container_counts`

Forbidden fields:

- raw customer filenames;
- private paths;
- account numbers;
- full financial operation rows;
- full text/table slices;
- secrets, keys or environment values.

Shape:

```json
{
  "schema_version": "broker_reports_chat_visible_normalization_report_v0",
  "report_id": null,
  "normalization_run_id": null,
  "run_status": "completed | completed_with_blockers | failed_safe",
  "summary_counts": {
    "files_total": null,
    "container_counts": {},
    "document_class_counts": {},
    "blockers_total": null
  },
  "case_groups": [
    {
      "case_group_id": null,
      "readiness": "partial | needs_review | blocked | unknown",
      "safe_summary": null,
      "recommended_for_next_proof": false
    }
  ],
  "blocker_summary": [],
  "safe_artifact_refs": {
    "document_inventory_ref": null,
    "technical_readability_profile_ref": null,
    "taxonomy_candidates_ref": null,
    "normalization_blockers_ref": null
  },
  "recommended_next_step": null,
  "safety_statement": "Gate 1 did not calculate tax, extract source facts through LLM, generate declaration, generate XLS/XLSX or file with FNS."
}
```

Relation: this is a user-visible projection of Gate 1 artifacts, not the artifact store itself.

## 14. Validation Rules

Gate 1 artifact validation extends existing validation rules:

1. Every safe document reference uses `document_id`.
2. Every public case reference uses `case_group_id`.
3. Every uploaded file has one inventory record.
4. Every inventory record has `sha256` and `container_format`.
5. Every readable supported file has a technical profile.
6. Every private slice references one `document_id`.
7. ZIP archives create ZIP member inventory or blocker records.
8. Raster PDFs create OCR/review blockers unless OCR is approved.
9. Unknown roles use `unknown_or_needs_review`.
10. Chat-visible report contains only safe aggregates and refs.
11. `source_fact_extraction_performed` remains false.
12. `tax_correctness_claimed`, `declaration_generated` and `xlsx_generated` remain false.

Any privacy violation is blocking.

## 15. Gate 2 derived segmentation of legacy bounded slices

Gate 1 private slices remain immutable source artifacts. Gate 2 may create a
new resolver-gated derived projection without modifying a legacy slice.

The derived projection must preserve:

- parent private-slice artifact ref;
- source checksum and parent slice-payload checksum refs;
- original row/cell/segment/source-value refs;
- parser/table/section/page refs when present;
- relevant issue refs and parent coverage ref.

It may rebase only the private payload row or character indices needed to make
the selected projection physically narrow. A segmentation plan must partition
all refs visible in the parent projection. When the parent profiler bounded
the original source, the unseen remainder is explicit as
`pending_gate1_reslice`; it is never silently treated as covered.

## 16. Status

```text
GATE1_ARTIFACT_CONTRACTS_READY
DOCUMENT_NORMALIZATION_ARTIFACTS_V0_PROPOSAL
NORMALIZED_SLICES_PRIVATE_BY_DEFAULT
CHAT_VISIBLE_REPORT_SAFE_ONLY
READY_FOR_GATE1_PROOF_PLAN
```

## 17. Full-source reslice refinement (2026-07-10)

Preview slices remain valid artifacts but are not extraction coverage authority.

Gate 1 additionally persists:

- `private_normalized_source_payload_v0` for one parser logical unit;
- `private_normalized_source_unit_v0` only when that payload is complete;
- `full_source_coverage_summary_v0` as safe counts/statuses only.

Both new private artifacts use `project_artifact_payload`, resolver-only access,
the owning retention/purge policy, and no Knowledge/RAG/vector backend. A
truncated preview never becomes complete merely because a downstream segment
is bounded. Gate 2 prefers complete source units and labels preview use as
`legacy_bounded_preview_fallback` with expansion readiness false.

Normative details:

- `BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md`;
- `BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md`.

## 18. PDF text-layer normalization Slice 1 (2026-07-10)

The existing heuristic PDF preview remains unchanged and partial. The
implemented extraction-grade page-text path reuses:

- `private_normalized_source_payload_v0` with nested
  `pdf_text_layer_projection_v0`;
- `private_normalized_source_unit_v0` with PDF-specific page/section/line/table
  candidate unit metadata;
- `full_source_coverage_summary_v0` for safe aggregate counts and reason codes.

The private PDF projection carries page inventory, parser fragments, optional
block/line/word geometry, source-value paths, page/payload checksums and exact
coverage. Complete text-layer coverage is independent from visible-content and
semantic-reconstruction status. Mixed text/image content therefore cannot be
misreported as complete visible-document coverage.

The same ArtifactStore, resolver, retention, expiry and purge boundaries apply.
No raw PDF text, filenames, file ids, paths or values enter chat/reports. OCR,
VLM, page rendering for extraction, ordinary processed upload, Knowledge/RAG
and vectorization remain forbidden.

Normative contracts:

- `BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md`;
- `BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md`.

```text
PDF_TEXT_LAYER_CONTRACTS_READY
PDF_TEXT_LAYER_PAGE_TEXT_RUNTIME_IMPLEMENTED
PDF_TEXT_LAYER_LAYOUT_TABLE_RUNTIME_DEFERRED
```
