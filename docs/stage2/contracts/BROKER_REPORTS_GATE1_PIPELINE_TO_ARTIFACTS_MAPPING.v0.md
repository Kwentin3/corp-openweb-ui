# Broker Reports Gate 1 Pipeline To Artifacts Mapping v0

Status: GATE1_PIPELINE_TO_ARTIFACTS_MAPPING_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 artifact contracts

## 1. Purpose

This mapping connects the Gate 1 normalization pipeline to concrete artifact contracts. It prevents the implementation from collapsing intake, profiling, taxonomy, blockers, source facts, ledgers, and chat reporting into one large JSON blob.

Gate 1 artifacts describe document package structure and technical readiness only. They do not contain source facts, tax-base calculations, declaration fields, or XLS/XLSX export rows.

## 2. Contract Visibility

| Artifact | Default visibility | Safe to reference in chat? | Notes |
| --- | --- | --- | --- |
| `normalization_run_v0` | Safe | Yes | Run id, status, counts, started/finished times. |
| `document_inventory_v0` | Safe with redaction | Yes by safe `document_id` only | No raw filenames, file ids, or private paths. |
| `technical_readability_profile_v0` | Safe with redaction | Yes in aggregate | Parser signals and counts only. |
| `normalized_text_slice_v0` | Private | No | Bounded text slices; safe projection requires review. |
| `normalized_table_slice_v0` | Private | No | Bounded table slices; no full financial rows in chat. |
| `zip_member_inventory_v0` | Safe with redaction | Yes in aggregate | Member extensions/counts only unless policy approves more. |
| `taxonomy_candidates_v0` | Safe | Yes | Labels, confidence, safe reason codes. |
| `normalization_blockers_v0` | Safe | Yes | Typed blocker codes and review actions. |
| `chat_visible_normalization_report_v0` | Safe | Yes | Whitelisted summary only. |

## 3. Pipeline Mapping

| Pipeline step | Artifact contract | Required fields | Validation rules | Next gate refs |
| --- | --- | --- | --- | --- |
| Intake request | `normalization_run_v0` | `run_id`, `schema_version`, `trigger_type`, `entrypoint`, `run_status`, `requested_at`, `files_total` | `entrypoint=pipe` for primary route; no prompt text; no file ids. | `run_id` |
| Private file registry | Private registry outside safe contract | original file refs, raw filename, upload path, access metadata | Private only; never copied into safe report. | Private resolver for byte access |
| Byte access and hashing | `document_inventory_v0` | `document_id`, `run_id`, `size_bytes`, `sha256`, `duplicate_group_id`, `container_format`, `detected_mime_type` | One inventory item per file; hash stable; duplicate groups explicit; no raw filename/path/id. | `document_id` |
| Container/MIME detection | `document_inventory_v0` | `extension_policy`, `container_format`, `mime_detection_method`, `confidence`, `warnings` | Unknown/unsupported formats create blockers. | `document_id` |
| CSV/TXT profile | `technical_readability_profile_v0` | `document_id`, `encoding`, `delimiter`, `rows_count`, `columns_count`, `machine_readable_table` | Supported readable files must have profile or blocker. | `profile_id`, private slice refs |
| XLSX profile | `technical_readability_profile_v0` | `sheets_count`, `sheet_name_policy`, `hidden_sheets_count`, `has_formulas`, `used_ranges`, `table_like_ranges` | Sheet names redacted/hashed unless proven safe. | `profile_id`, private slice refs |
| PDF profile | `technical_readability_profile_v0` | `pages_count`, `has_text_layer`, `probable_raster_or_scan`, `table_likelihood`, `ocr_or_review_needed` | Raster/scan-like PDFs create OCR/review blocker. | `profile_id`, private slice refs |
| HTML/TXT profile | `technical_readability_profile_v0` | `encoding`, `section_count`, `table_candidates`, `clean_text_available` | Scripts/raw HTML not emitted to chat. | `profile_id`, private slice refs |
| DOCX profile | `technical_readability_profile_v0` | `paragraphs_count`, `headings_count`, `tables_count`, `role_candidate` | Dependency must be proven before marking supported. | `profile_id`, private slice refs |
| ZIP inventory | `zip_member_inventory_v0` | `document_id`, `members_count`, `member_extension_counts`, `nested_archive_count`, `policy_status` | ZIP creates `zip_requires_review` unless approved. | `zip_inventory_id` |
| Structural text slices | `normalized_text_slice_v0` | `slice_id`, `document_id`, `location`, `text`, `chars_count`, `truncated`, `parser` | Private; bounded; source-located. | Private `text_slice_ref` |
| Structural table slices | `normalized_table_slice_v0` | `slice_id`, `document_id`, `location`, `row_range`, `columns_count`, `rows_count`, `cells`, `truncated`, `parser` | Private; no full rows in chat-visible report. | Private `table_slice_ref` |
| Taxonomy candidates | `taxonomy_candidates_v0` | `document_id`, `primary_class`, `alternatives`, `confidence`, `can_be_source_evidence`, `can_be_methodology`, `can_be_loaded_to_knowledge`, `declaration_relevance`, `safe_reason_codes` | Weak evidence maps to `unknown_or_needs_review`; LLM not authoritative. | `document_id`, `taxonomy_candidate_id` |
| Blockers | `normalization_blockers_v0` | `blocker_id`, `document_id`, `code`, `severity`, `review_action`, `safe_message`, `blocks_gate2` | Every failed step has a typed blocker. | `blocker_id` |
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

### `normalized_text_slice_v0`

Required fields:

- `slice_id`;
- `document_id`;
- `profile_id`;
- `location`;
- `text`;
- `chars_count`;
- `truncated`;
- `parser`;
- `created_for_gate`;

Visibility: private by default.

### `normalized_table_slice_v0`

Required fields:

- `slice_id`;
- `document_id`;
- `profile_id`;
- `location`;
- `rows_count`;
- `columns_count`;
- `row_range`;
- `column_policy`;
- `cells`;
- `truncated`;
- `parser`;
- `created_for_gate`.

Visibility: private by default.

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
- private slice refs through an approved resolver;
- blocker refs;
- readiness labels.

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
7. Raster PDFs have `raster_requires_ocr_or_review` unless OCR policy is approved.
8. Chat report is rendered from whitelisted fields only.
9. Privacy validation failure blocks report publication.
10. Gate 2 handoff is `blocked` until Gate 1 validation passes.

## 7. Status

```text
GATE1_PIPELINE_TO_ARTIFACTS_MAPPING_READY
NORMALIZATION_ARTIFACT_BOUNDARY_CONFIRMED
SOURCE_FACT_ARTIFACTS_OUT_OF_GATE1_SCOPE
```
