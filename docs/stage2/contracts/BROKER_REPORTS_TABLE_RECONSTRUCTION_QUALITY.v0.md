# Broker Reports Table Reconstruction Quality v0

Status: implemented as deterministic structural quality metadata for normalized table projections.

## Purpose

`broker_reports_table_reconstruction_quality_v0` describes whether a source unit can be consumed as a bounded table structure. It is not model confidence and does not measure the truth of broker, tax or declaration facts.

## Required metrics

Every normalized table projection contains `quality` with:

- `row_alignment_score` from `0.0` to `1.0`;
- `column_alignment_score` from `0.0` to `1.0`;
- `header_confidence=high|medium|low|blocked`;
- `cell_boundary_confidence` from `0.0` to `1.0`;
- `coverage_completeness` from `0.0` to `1.0`;
- `duplicate_overlap_count`;
- `unaccounted_ref_count`;
- `fallback_required`;
- `reconstruction_quality=high|medium|low|blocked`.

Metrics are derived from deterministic counts, geometry and coverage only. They must not be supplied by an LLM.

## Native quality

For parser-native CSV/HTML/XLSX tables:

- row and column alignment compare observed cells per row with the table column count;
- cell-boundary confidence follows parser-native alignment;
- coverage completeness is `1.0` only when all selected refs and every row/cell/source-value relationship validate;
- missing/ambiguous headers reduce header status but do not invent a label;
- budget overflow forces `blocked`.

## PDF quality gate

For PDF candidates, geometry validation additionally requires:

- `geometry_confidence` at or above the configured threshold (`0.90` by default);
- supported strategy: `ruled_lines`, `aligned_words`, `mixed_geometry` or `repeated_x_columns`;
- stable table, row, cell and bbox refs;
- at least two rows and two columns;
- unique word-to-cell ownership;
- exact contributing-word coverage;
- line fallback refs preserved separately.

`validated_geometry` is the terminal positive structural state. It does not authorize semantic extraction and does not convert a header candidate into semantic truth.

## Reconstruction quality bands

- `high`: complete coverage, at least `0.95` row alignment and at least `0.90` cell-boundary confidence;
- `medium`: complete coverage and at least `0.75` row alignment;
- `low`: a projection exists but alignment/confidence is below the medium threshold;
- `blocked`: budget overflow, failed geometry checks, missing candidate inventory, duplicate ownership or another terminal structural violation.

The validator may fail a projection even if a computed band exists. A consumer must require both `validator_status=passed` and `projection_status=ready`.

## Fallback and coverage rules

For a ready PDF projection:

- contributing words belong to table cells;
- fallback lines remain separately owned fallback refs;
- duplicate and unaccounted lists are empty.

For a rejected PDF candidate:

- no table rows or cells are emitted;
- fallback lines remain in `fallback_text_refs`;
- candidate word refs remain explicit in `rejected_refs`;
- the coverage partition may still be complete even though reconstruction is blocked;
- Gate 2 uses the existing line-cluster fallback.

## Budget rules

Budgets cover row count, cell count, private serialized projection size and Gate 2 rows per package. Any overflow is `partial` or `blocked`; it is forbidden to truncate silently and emit `complete`.

## Safe reporting

Chat/report surfaces may expose only:

- projection/table/document counts;
- quality/status counts;
- row/cell/source-value counts;
- fallback, duplicate and unaccounted counts;
- typed reason codes;
- runtime and payload-size aggregates.

Raw filenames, file ids, paths, rows, cell values, PDF text, account identifiers, personal data, secrets and environment values are forbidden.
