# Broker Reports Normalized Table Projection v0

Status: implemented for native CSV/HTML/XLSX tables and mechanically validated PDF table candidates.

## Purpose

`broker_reports_normalized_table_projection_v0` is the source-format-neutral structural bridge between Gate 1 document normalization and Gate 2 source-fact extraction.

It answers only: "Can this bounded source unit be represented safely as rows, columns and cells?" It does not identify trades, income, tax, fees, cash movements or positions. It does not calculate tax and never claims semantic table truth for PDF.

## Ownership and factory route

The production route is:

`Gate1Normalizer -> FullSourceArtifactFactory -> NormalizedTableProjectionFactory -> TableProjectionValidator -> ArtifactStoreFactory -> Gate2InputReadinessFactory(prefer_table_projections=True) -> Gate2TablePackageFactory -> Gate2SourceUnitRouterFactory -> Gate2SourceUnitSegmenterFactory`.

Only `NormalizedTableProjectionFactory.create` may create normalized table projections. Builders reuse existing `row_ref`, `cell_ref`, `cell_value_ref` and `source_value_ref` authority. They must not mint replacement source provenance.

## Required identity and origin

Every projection contains:

- `schema_version=broker_reports_normalized_table_projection_v0`;
- `table_projection_id`, `table_ref` and `table_projection_checksum_ref`;
- `source_format=csv|html|xlsx|pdf|txt|unknown`;
- `table_origin=native_table|parser_table|reconstructed_candidate|geometry_candidate|line_cluster_fallback|legacy_preview`;
- `source_document_ref`, `source_unit_ref` and `parent_payload_ref`;
- `normalization_run_id`;
- `parser_ref`, parser engine/version/config refs where available;
- `source_checksum_ref`, `payload_checksum_ref` and `source_unit_checksum_ref`;
- `visibility=private_case` and `storage_backend=project_artifact_payload`.

The artifact is resolver-gated, retention-controlled and purgeable. It is forbidden in Knowledge, RAG or vector storage.

## Structural model

Required structural fields are:

- ordered `row_refs`, `column_refs`, `cell_refs`, `cell_value_refs` and `source_value_refs`;
- `row_count`, `column_count` and `cell_count`;
- `row_order_policy=source_order_preserved`;
- `column_order_policy=source_order_preserved`;
- `rows`, `cells`, `private_values` and `source_value_index`;
- `table_bbox_ref`, `page_refs`, `sheet_refs` and `section_refs` when available.

Every row owns only its `cell_refs`. Every cell points to exactly one row and column and carries one or more existing `source_value_refs`. Private values are reachable only through `normalized_private_value_path`; safe reports contain counts/statuses/reason codes, never customer values.

## Structural row roles

Allowed roles are:

- `header_row`;
- `data_row`;
- `summary_row`;
- `subtotal_row`;
- `footer_row`;
- `repeated_header_row`;
- `blank_row`;
- `layout_row`;
- `unknown_row_role`.

These roles describe table structure only. Business roles such as `trade_operation`, `income`, `withholding_tax`, `fee_commission`, `cash_movement` and `position_snapshot` are forbidden here.

## Header model

`header_model` contains:

- `header_row_refs` and `repeated_header_row_refs`;
- `multi_row_header`;
- `column_labels` with `header_ref`, `column_ref`, `cell_ref`, source-value refs, safe normalized label, confidence and mapping status;
- `header_to_column_mapping_status=mapped|missing_or_ambiguous|candidate_rejected`;
- `pdf_header_candidate`;
- `semantic_header_truth_claimed=false`.

Safe normalized labels are bounded descriptors such as `date`, `amount`,
`currency`, `operation`, `market`, `quantity`, `instrument` or `unknown`.
Exact composite native headers such as operation description, trading venue,
credit amount and debit amount may map to those bounded descriptors. This is a
mechanical header dictionary only; it does not classify the row as a business
fact. PDF labels remain structural candidates even when geometry is validated.

## Cell model

Each cell contains:

- `cell_ref`, `row_ref`, `column_ref`, row/column ordinals;
- `source_value_refs` and `cell_value_ref`;
- `normalized_private_value_path` and `value_checksum_ref`;
- safe `value_kind_hints`;
- `bbox_ref` when available;
- `row_span`, `column_span` and `merged_cell_group_ref`;
- `split_cell_candidate`, `multi_line_cell`, `wrapped_text_cell` and `ambiguous_cell_boundary`;
- `empty_cell`, confidence and reason codes.

Uncertain boundaries are candidates. A builder must not invent empty/fake PDF cells to make a rectangle complete.

## Native table mapping

CSV, HTML and XLSX builders map parser-native logical table units into this contract:

- original table/row/cell/source-value refs remain authoritative;
- parser order remains row and column order;
- native values stay private and checksum-reproducible;
- header/repeated-header/blank/summary/subtotal roles are deterministic structural labels;
- coverage must remain complete even for empty cells and summary rows.

XLSX is supported only through the existing stdlib ZIP/XML parser path. No new spreadsheet dependency is introduced.

## PDF mapping

`PdfTableCandidateProjectionBuilder` accepts only a `pdf_table_candidate_unit` and its resolver-matched private parent payload. It checks:

- candidate inventory presence;
- geometry confidence threshold;
- at least two rows and two columns;
- deterministic cell bbox presence;
- one owner per contributing word;
- exact contributing-word coverage;
- supported reconstruction strategy.

`table_candidate_status=validated_geometry` means those structural checks passed. It never means business or semantic truth.

If checks fail, the projection is `blocked` with `table_candidate_status=rejected_to_line_cluster`, no rows/cells, explicit rejected refs and preserved line fallback refs. Gate 2 continues through the existing line-cluster unit; it must not receive fake cells.

## Coverage

`coverage.schema_version=broker_reports_table_projection_coverage_v0` and includes:

- `selected_source_refs` and `accounted_source_refs`;
- `table_owned_refs`;
- `fallback_text_refs`;
- `non_table_refs`;
- `rejected_refs`;
- `duplicate_accounted_refs`;
- `unaccounted_refs`;
- selected/accounted totals;
- `coverage_status=complete|partial` and `all_selected_refs_accounted`.

The owner buckets form an exact partition of selected refs. Fallback refs never double-own table refs. Duplicate, unexpected or unaccounted refs fail validation; no row, cell, word, line or source value may disappear silently.

## Gate 2 bounded table package

`Gate2TablePackageFactory` produces `broker_reports_source_fact_package_v0` with mode `gate2_normalized_table_projection_no_model_call`.

The package contains bounded rows, repeated headers, selected cells, source-value refs, issue refs, quality metadata and PDF fallback metadata. Header/repeated-header/blank/layout rows are explicit deterministic no-fact coverage entries. Data/summary/subtotal/footer/unknown rows remain candidates for later Gate 2 classification.

Gate 2 table package eligibility is strict:

- `projection_status=ready`;
- `reconstruction_quality=high|medium`;
- `coverage.coverage_status=complete`;
- `coverage.duplicate_accounted_refs=[]`;
- `coverage.unaccounted_refs=[]`;
- `semantic_table_truth_claimed=false`.

Anything else is rejected with a typed package error, for example `gate2_table_projection_quality_not_eligible` or `gate2_table_projection_coverage_not_eligible`.

When a document has mixed-quality projections, Gate 2 readiness may skip ineligible projection candidates and continue with validator-passed eligible projections from the same document. Skipped candidates are not silently promoted, and a document with no eligible table package remains unpackageable.

The slice-level readiness flag `prefer_table_projections=True` is explicit. Default model-runtime behavior remains on the prior full-source unit unless the Gate 2 caller opts in through `Gate2DomainSourceFactRuntimeConfig.prefer_table_projections` or the OpenWebUI domain pipe `prefer_table_projections` config.

## Budgets and terminal behavior

Rows, cells and serialized payload size have deterministic budgets. Overflow produces `projection_status=blocked` and `reconstruction_quality=blocked` with a typed `*_budget_exceeded` reason. It must never be reported as truncated-complete.

## Privacy and non-goals

Always false:

- `semantic_table_truth_claimed`;
- `source_facts_extracted`;
- `tax_meaning_inferred`;
- `knowledge_rag_used`;
- `vectorization_performed`;
- `ocr_vlm_used`;
- `page_rendering_used_for_extraction`.

No OpenWebUI core patch, ordinary processed upload, OCR, VLM, page rendering, model extraction, source facts, tax calculation, declaration generation or XLS/XLSX output belongs to this contract.

## Candidate-discovery boundary

An eligible bounded projection may feed deterministic Gate 2 candidate
discovery. Stable row/cell/source-value/header refs and mechanically
reproducible values may become private candidates and same-row relations.
Structural row roles, column order, value-kind hints and composite-header
descriptors remain evidence only: they do not assign amount meaning,
gross/net, base/quote, fee/tax, trade/settlement or any final fact field.

Candidate discovery does not alter this projection and must fail rather than
truncate when candidate/relation budgets are exceeded.
