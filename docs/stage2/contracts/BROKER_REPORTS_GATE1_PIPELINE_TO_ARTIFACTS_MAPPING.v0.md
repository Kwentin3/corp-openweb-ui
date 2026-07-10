# Broker Reports Gate 1 Pipeline To Artifacts Mapping v0

Status: GATE1_PIPELINE_TO_ARTIFACTS_MAPPING_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 artifact contracts

## 1. Purpose

This mapping connects the Gate 1 normalization pipeline to concrete artifact contracts. It prevents the implementation from collapsing intake, profiling, taxonomy, blockers, source facts, ledgers, and chat reporting into one large JSON blob.

Gate 1 artifacts describe document package structure and technical readiness only. They do not contain source facts, tax-base calculations, declaration fields, or XLS/XLSX export rows.

As of the 2026-07-08 no-RAG source-intake proof, `customer_docs_loaded_to_knowledge=false` is not a complete source-intake guard. Gate 1 acceptance now also requires proving that raw case uploads are not extracted into OpenWebUI native file context and are not vectorized by OpenWebUI native RAG.

Required source-intake guard:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
gate1_pipe_receives_only_opaque_source_refs=true
```

If this guard is not proven, customer-authorized upload remains blocked even when all Gate 1 derived artifacts are safe.

## 2. Contract Visibility

| Artifact | Default visibility | Safe to reference in chat? | Notes |
| --- | --- | --- | --- |
| `normalization_run_v0` | Safe | Yes | Run id, status, counts, started/finished times. |
| `document_inventory_v0` | Safe with redaction | Yes by safe `document_id` only | No raw filenames, file ids, or private paths. |
| `technical_readability_profile_v0` | Safe with redaction | Yes in aggregate | Parser signals and counts only. |
| `private_normalized_text_slice_v0` | Private | No | Bounded text slices with stable segment/span/source-value refs; safe projection contains refs and counts only. |
| `private_normalized_table_slice_v0` | Private | No | Bounded table slices with stable table/row/cell/source-value refs; no financial rows in chat. |
| `zip_member_inventory_v0` | Safe with redaction | Yes in aggregate | Member extensions/counts only unless policy permits more. |
| `taxonomy_candidates_v0` | Safe | Yes | Labels, confidence, safe reason codes. |
| `normalization_blockers_v0` | Safe | Yes | Typed blocker codes and review actions. |
| `gate1_issue_ledger_v0` | Safe | Yes by issue id and summary | Unresolved/resolved issue refs; no raw payload. |
| `document_usage_classification_v0` | Safe | Yes by stage summary | Per-document downstream usage/readiness by safe refs. |
| `domain_context_packet_v0` | Safe | Yes by summary and opaque refs | Source-extraction handoff with unresolved issue context. |
| `chat_visible_normalization_report_v0` | Safe | Yes | Whitelisted summary only. |

## 3. Pipeline Mapping

| Pipeline step | Artifact contract | Required fields | Validation rules | Next gate refs |
| --- | --- | --- | --- | --- |
| Intake request | `normalization_run_v0` | `run_id`, `schema_version`, `trigger_type`, `entrypoint`, `run_status`, `requested_at`, `files_total` | `entrypoint=pipe` for primary route; no prompt text; no file ids. | `run_id` |
| Source upload guard | Runtime/source-intake proof, not a chat artifact | file/document/knowledge/vector deltas; file extraction check; model capabilities | `file_context=false` alone is not enough if native upload still processes/vectorizes files. | Blocks customer-authorized package |
| Private file registry | Private registry outside safe contract | original file refs, raw filename, upload path, access metadata | Private only; never copied into safe report. | Private resolver for byte access |
| Byte access and hashing | `document_inventory_v0` | `document_id`, `run_id`, `size_bytes`, `sha256`, `duplicate_group_id`, `container_format`, `detected_mime_type` | One inventory item per file; hash stable; duplicate groups explicit; no raw filename/path/id. | `document_id` |
| Container/MIME detection | `document_inventory_v0` | `extension_policy`, `container_format`, `mime_detection_method`, `confidence`, `warnings` | Unknown/unsupported formats create blockers. | `document_id` |
| CSV/TXT profile | `technical_readability_profile_v0` | `document_id`, `encoding`, `delimiter`, `rows_count`, `columns_count`, `machine_readable_table` | Supported readable files must have profile or blocker. | `profile_id`, private slice refs |
| XLSX profile | `technical_readability_profile_v0` | `sheets_count`, `sheet_name_policy`, `hidden_sheets_count`, `has_formulas`, `used_ranges`, `table_like_ranges` | Sheet names redacted/hashed unless proven safe. | `profile_id`, private slice refs |
| PDF profile | `technical_readability_profile_v0` | `pages_count`, `has_text_layer`, `probable_raster_or_scan`, `table_likelihood`, `ocr_or_review_needed` | Raster/scan-like PDFs create OCR/review blocker. | `profile_id`, private slice refs |
| HTML/TXT profile | `technical_readability_profile_v0` | `encoding`, `section_count`, `table_candidates`, `clean_text_available` | Scripts/raw HTML not emitted to chat. | `profile_id`, private slice refs |
| DOCX profile | `technical_readability_profile_v0` | `paragraphs_count`, `headings_count`, `tables_count`, `role_candidate` | Dependency must be proven before marking supported. | `profile_id`, private slice refs |
| ZIP inventory | `zip_member_inventory_v0` | `document_id`, `members_count`, `member_extension_counts`, `nested_archive_count`, `policy_status` | ZIP creates `zip_requires_review` unless policy permits direct use. | `zip_inventory_id` |
| Structural text slices | `private_normalized_text_slice_v0` | `slice_id`, `document_id`, `text_segment_refs`, `section_refs`, page/range refs where available, character span refs, `source_value_refs`, parser/source checksum refs, coverage | Private; bounded; every segment resolves by private span plus checksum; no raw text in safe output. | Resolver-gated source-unit refs |
| Structural table slices | `private_normalized_table_slice_v0` | `slice_id`, `table_ref`, `row_refs`, `row_range_ref`, cell/value refs, normalized header descriptors, ordinals, parser/source checksum refs, coverage | Private; every source value resolves by payload path plus checksum; no rows in safe output. | Resolver-gated source-unit/value refs |
| Taxonomy candidates | `taxonomy_candidates_v0` | `document_id`, `primary_class`, `alternatives`, `confidence`, `can_be_source_evidence`, `can_be_methodology`, `can_be_loaded_to_knowledge`, `declaration_relevance`, `safe_reason_codes` | Weak evidence maps to `unknown_or_needs_review`; LLM not authoritative. | `document_id`, `taxonomy_candidate_id` |
| Blockers | `normalization_blockers_v0` | `blocker_id`, `document_id`, `code`, `severity`, `review_action`, `safe_message`, `blocks_gate2` | Every failed step has a typed blocker. | `blocker_id` |
| Issue ledger | `gate1_issue_ledger_v0` | `issue_id`, `issue_type`, `target_document_refs`, `status`, `blocked_stages`, `stages_that_may_continue`, `provenance` | Skipped/unanswered questions remain unresolved; LLM cannot set criticality/readiness. | `issue_id` |
| Usage classification | `document_usage_classification_v0` | `document_ref`, `usage_modes`, `readiness_by_stage`, `issue_refs` | Readable docs can enter source extraction with issue context; final declaration use is not decided here. | `document_ref`, `issue_refs` |
| Domain context packet | `domain_context_packet_v0` | `document_refs`, `unresolved_issue_refs`, `document_issue_refs`, `stage_readiness`, `next_stage_refs`, `next_stage_ref_summary`, `artifact_logical_refs`, `vector_knowledge_guard` | No raw/private payload; no Knowledge/RAG/vector; unresolved issues carried forward; `dropped_source_ready_refs` must be empty. | downstream source-extraction packet |
| Safe report | `chat_visible_normalization_report_v0` | `run_id`, `files_total`, `container_counts`, `document_class_counts`, `blockers_total`, `case_groups`, `recommended_next_step`, `safety_statement` | Whitelist-only renderer; deny raw file ids/names/paths/rows/text. | Safe Gate 2 handoff refs |

## 4. Artifact Field Requirements

### `normalization_run_v0`

Required fields:

- `schema_version`;
- `run_id`;
- `entrypoint`;
- `trigger_type`;
- `run_status`;
- `started_at`;
- `finished_at`;
- `files_total`;
- `artifacts_created`;
- `privacy_validation_status`;
- `gate2_handoff_status`.

Allowed statuses:

- `started`;
- `completed`;
- `completed_with_blockers`;
- `failed_safe`;
- `privacy_failed`.

### `document_inventory_v0`

Required fields:

- `document_id`;
- `run_id`;
- `container_format`;
- `detected_mime_type`;
- `size_bytes`;
- `sha256`;
- `duplicate_group_id`;
- `readable`;
- `read_error_class`;
- `technical_profile_ref`;
- `taxonomy_candidate_ref`;
- `blocker_refs`.

Forbidden fields:

- raw filename;
- raw file id;
- local/private path;
- account number;
- raw customer text.

### `technical_readability_profile_v0`

Required common fields:

- `profile_id`;
- `document_id`;
- `container_format`;
- `parser`;
- `parser_version`;
- `profile_status`;
- `confidence`;
- `warnings`;
- `blocker_refs`.

Format-specific fields must stay nullable and format-scoped. Do not force PDF fields onto CSV or workbook fields onto PDF.

### `private_normalized_text_slice_v0`

Required fields:

- `slice_id`;
- `schema_version=private_normalized_text_slice_v0`;
- `source_unit_schema_version=source_unit_provenance_v0`;
- `normalization_run_id`;
- `document_id`;
- `profile_id`;
- `location`;
- `text`;
- `chars_count`;
- `truncated`;
- `parser`;
- `parser_ref`;
- `source_checksum_ref`;
- `slice_payload_checksum_ref`;
- `text_segment_refs`;
- `section_refs`;
- `page_refs` / `page_range_ref` where available;
- `character_span_refs`;
- `segment_provenance`;
- `source_value_refs` and `source_value_index`;
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`;
- `safe_section_labels`;
- `coverage` with every selected segment classified;
- `created_for_gate`;

Visibility: private by default.

### `private_normalized_table_slice_v0`

Required fields:

- `slice_id`;
- `schema_version=private_normalized_table_slice_v0`;
- `source_unit_schema_version=source_unit_provenance_v0`;
- `normalization_run_id`;
- `document_id`;
- `profile_id`;
- `location`;
- `rows_count`;
- `columns_count`;
- `row_range`;
- `table_ref`;
- `row_refs` and stable row ordinals;
- `row_range_ref`;
- `cell_refs` and stable column ordinals;
- `cell_value_refs`;
- `source_value_refs` and `source_value_index`;
- `normalized_header_descriptors`;
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`;
- `parser_ref`;
- `source_checksum_ref`;
- `slice_payload_checksum_ref`;
- `coverage` with header/blank/layout/fact-candidate buckets;
- `column_policy`;
- `cells`;
- `truncated`;
- `parser`;
- `created_for_gate`.

Visibility: private by default.

`NormalizedSliceProvenanceFactory.create` is the only production ref-minting
entrypoint. Profilers produce bounded payloads; the factory adds deterministic
source-unit/value refs before Gate 1 validation and persistence. Validators
recompute the complete ref projection and fail closed on missing, foreign or
tampered refs.

### `zip_member_inventory_v0`

Required fields:

- `zip_inventory_id`;
- `document_id`;
- `members_count`;
- `member_extension_counts`;
- `nested_archive_count`;
- `encrypted_member_count`;
- `oversized_member_count`;
- `policy_status`;
- `blocker_refs`.

Default `policy_status`: `requires_review`.

### `taxonomy_candidates_v0`

Required fields:

- `taxonomy_candidate_id`;
- `document_id`;
- `primary_class`;
- `alternative_classes`;
- `confidence`;
- `can_be_source_evidence`;
- `can_be_methodology`;
- `can_be_loaded_to_knowledge`;
- `declaration_relevance`;
- `safe_reason_codes`;
- `classifier_type`;
- `requires_review`.

`classifier_type` should start as `rules`.

### `normalization_blockers_v0`

Required fields:

- `blocker_id`;
- `run_id`;
- `document_id`;
- `code`;
- `severity`;
- `blocks_gate2`;
- `safe_message`;
- `review_action`;
- `created_by_step`.

Allowed initial codes:

- `no_files`;
- `bytes_unavailable`;
- `unsupported_format`;
- `encrypted_file`;
- `corrupt_file`;
- `parser_failed`;
- `raster_requires_ocr_or_review`;
- `zip_requires_review`;
- `unknown_role`;
- `privacy_violation`;
- `duplicate_review`.

### `chat_visible_normalization_report_v0`

Required fields:

- `schema_version`;
- `run_id`;
- `run_status`;
- `files_total`;
- `container_counts`;
- `document_class_counts`;
- `blockers_total`;
- `case_groups`;
- `recommended_next_step`;
- `safety_statement`;
- `gate2_handoff_status`.

Forbidden fields:

- raw filename;
- raw file id;
- local/private path;
- account number;
- personal identifier;
- full financial row;
- raw parser text;
- env value or secret.

## 5. Gate 2 Handoff Contract

Gate 2 may receive:

- `run_id`;
- safe `document_id`;
- `taxonomy_candidate_id`;
- safe profile refs;
- private slice refs through an authorized resolver;
- blocker refs;
- readiness labels.

Gate 2/source-fact extraction must receive:

- `domain_context_packet_v0.next_stage_refs`;
- `domain_context_packet_v0.document_issue_refs`;
- `gate2_handoff_v0.next_stage_refs`;
- `gate2_handoff_v0.private_slice_refs_by_next_stage_bucket`.

`gate2_handoff_v0.included_document_refs` remains the primary reduced subset.
It must not be interpreted as the only source-ready input.

Gate 2 must not receive:

- raw OpenWebUI file ids directly from chat output;
- raw filenames from safe artifacts;
- all raw documents as a prompt;
- unvalidated table/text slices.

## 6. Validation Rules

Minimum validation:

1. Every `document_inventory_v0` item belongs to one `normalization_run_v0`.
2. Every supported readable document has a technical profile or a blocker.
3. Every private slice references exactly one safe `document_id`.
4. Every taxonomy candidate references one inventory item.
5. Every blocker references a run and, when applicable, a document.
6. Every ZIP has either `zip_member_inventory_v0` or `parser_failed`/`unsupported_format`.
7. Raster PDFs have `raster_requires_ocr_or_review` unless OCR policy permits direct use.
8. Chat report is rendered from whitelisted fields only.
9. Privacy validation failure blocks report publication.
10. Gate 2 handoff is `blocked` until Gate 1 validation passes.
11. Customer-authorized source upload is blocked unless the no-RAG/no-vector source-intake guard is proven on synthetic files.
12. Knowledge row delta `0` is necessary but not sufficient; vector DB delta and extracted file-content checks are required.

## 7. Status

```text
GATE1_PIPELINE_TO_ARTIFACTS_MAPPING_READY
NORMALIZATION_ARTIFACT_BOUNDARY_CONFIRMED
SOURCE_FACT_ARTIFACTS_OUT_OF_GATE1_SCOPE
NO_RAG_SOURCE_INTAKE_GUARD_REQUIRED
```

## 8. Full-source extraction mapping (2026-07-10)

| Pipeline step | Private output | Safe output |
|---|---|---|
| parser full logical projection | `private_normalized_source_payload_v0` | format/status/counts only |
| complete payload provenance | `private_normalized_source_unit_v0` | unit/count/coverage status only |
| preview/profile | legacy private table/text slice | compact preview counts only |
| Gate 2 input readiness | resolver-read full unit; legacy fallback only if absent | input mode and expansion-ready count |

The DCP advertises `source_input_priority=full_source_unit_then_legacy_preview`.
It carries no raw payload. `private_normalized_source_unit_v0` is the preferred
source, while `source_unit_provenance_v0` remains the row/cell/text ref schema.
