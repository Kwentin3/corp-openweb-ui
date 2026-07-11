# OpenWebUI Broker Reports Table Representation And PDF Table Hardening

Date: 2026-07-11

Repository: `corp-openweb-ui`

Scope: Gate 1 / Gate 1.5 structural tables and Gate 2 no-model input readiness

Result: implementation and synthetic proof passed; approved `case_group_002` preflight passed with bounded blockers.

## Executive result

The repository now has one source-format-neutral private table artifact: `broker_reports_normalized_table_projection_v0`. Native CSV/HTML/XLSX tables and mechanically valid PDF geometry candidates map into the same rows/columns/cells/header/coverage/quality structure before Gate 2 business extraction.

This slice does not extract source facts, infer tax meaning, call an LLM, calculate tax, generate declarations or write XLS/XLSX output. PDF `validated_geometry` means only that deterministic structure and ownership checks passed; semantic table truth remains false.

The implementation is ready for a later bounded table-domain extraction slice on validator-passed, budget-fit projections. It is not ready for whole-corpus or whole-table model expansion: five approved documents remained partial/blocked and 24 approved table packages exceeded the current 250-row Gate 2 package budget.

## Contracts added

- `docs/stage2/contracts/BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md` defines identity, native/PDF mapping, rows, columns, cells, headers, private value paths, coverage, ArtifactStore and Gate 2 package rules.
- `docs/stage2/contracts/BROKER_REPORTS_TABLE_RECONSTRUCTION_QUALITY.v0.md` defines deterministic alignment, boundary, coverage, fallback and quality bands.

Existing normalization, full-source, extraction-unit, PDF source-unit, Gate 2 source-fact, router and domain-extractor contracts now point to this bridge and state that table reconstruction is not a Gate 2 model responsibility.

## Runtime implementation

Canonical source is `services/broker-reports-gate1-proof/broker_reports_gate1/table_projection.py`:

- `NormalizedTableProjectionFactory` is the production entrypoint;
- `CsvTableProjectionBuilder`, `HtmlTableProjectionBuilder` and `XlsxTableProjectionBuilder` reuse parser-native provenance;
- `PdfTableCandidateProjectionBuilder` validates geometry and fallback ownership;
- `TableProjectionValidator` checks the complete contract and checksum;
- `Gate2TablePackageFactory` builds a bounded no-model source-fact package;
- `validate_gate2_table_package` checks row/cell/source-value/issue/coverage and guard invariants.

The module is included in all three self-contained OpenWebUI bundles. It introduces no new runtime import or package dependency.

## Native table mapping

Native builders preserve the existing `table_ref`, `row_ref`, `cell_ref`, `cell_value_ref` and `source_value_ref` authority. Parser order becomes row/column order. Private values remain reachable through a private value path plus checksum; safe output exposes only counts/statuses.

Synthetic CSV proved `header_row`, `data_row` and `summary_row`; a quoted multi-line value proved `multi_line_cell`. HTML and XLSX-like fixtures produced the same projection schema. Empty XLSX cells represented as `None` remain valid private source values while structural hints use an empty safe representation; provenance is not changed.

## Header, merged and ambiguous cell representation

`header_model` records header/repeated-header rows, safe normalized labels, header-to-column mapping and confidence. PDF headers remain candidates even after geometry validation.

Cells support `row_span`, `column_span`, merged group refs, split candidates, multi-line/wrapped flags, ambiguous boundaries and explicit empty cells. The PDF wrapped-cell fixture uses two text lines inside one mechanically bounded cell. If PDF geometry is insufficient, the projection has no rows/cells; it is never padded with fake cells.

## PDF geometry hardening

A PDF candidate becomes `validated_geometry` only when:

- the parent candidate inventory resolves;
- confidence meets the `0.90` threshold;
- at least two rows and two columns exist;
- every cell has a bbox;
- every contributing word has exactly one cell owner;
- contributing-word coverage is exact;
- the strategy is supported (`ruled_lines`, `aligned_words`, `mixed_geometry` or `repeated_x_columns`).

Rejected candidates become `rejected_to_line_cluster`, `projection_status=blocked`, with zero rows/cells. Line fallback refs and rejected word refs remain an exact coverage partition.

## Coverage and source-value refs

Coverage records selected/accounted/table-owned/fallback/non-table/rejected/duplicate/unaccounted refs. The validator recomputes ownership rather than trusting supplied totals. Duplicate, unexpected or unaccounted refs fail validation.

Native source-value refs reproduce from existing table cells. PDF cell refs carry the existing contributing word source-value refs; fallback line source-value refs remain separate. No row, cell, word, line, source value, issue or fallback ref is silently dropped.

## ArtifactStore

Normalized projections persist as:

- artifact type: `broker_reports_normalized_table_projection_v0`;
- visibility: `private_case`;
- backend: `project_artifact_payload`;
- resolver-gated access;
- inherited explicit retention and purge lifecycle.

Blocked projections persist as blocked artifacts; legacy source records are not mutated. Safe metadata contains only schema/status/quality/counts/checksum refs. Knowledge/RAG/vector backends remain forbidden.

## Gate 2 no-model package proof

`Gate2InputReadinessConfig(prefer_table_projections=True)` is an explicit no-model opt-in. Default model-runtime behavior still consumes the prior full-source unit, preventing this slice from accidentally invoking existing source-fact model execution on the new contract.

The table package preserves headers, structural row roles, cells, source-value refs, issue refs, quality and PDF fallback metadata. Header/repeated-header/blank/layout rows are deterministic no-fact entries; other structural rows remain candidates for future Gate 2 classification. Whole PDF/page content is not included.

Synthetic native and PDF packages both passed `Gate2TablePackage` validation, deterministic router coverage and source-unit segmentation. ArtifactStore ids before/after the dry run were identical; no model call or source-fact persistence occurred.

## Synthetic proof

Test file: `services/broker-reports-gate1-proof/tests/test_broker_reports_table_projection.py`.

Native fixtures:

- CSV with header/data/summary and a multi-line cell;
- HTML table;
- XLSX-like ZIP/XML workbook with multiple sheets and empty cells.

PDF text-layer fixtures:

- ruled table;
- aligned borderless table;
- repeated header plus footer fallback;
- wrapped/multi-line cell;
- ambiguous borderless table rejected to line cluster;
- non-table line cluster;
- forced confidence rejection proving no fake cells and complete fallback coverage.

Full backend result:

```text
py -3.11 -m unittest discover -s services/broker-reports-gate1-proof/tests -v
Ran 165 tests in 21.961s
OK
```

`py -3.11 -m compileall -q services/broker-reports-gate1-proof` also passed.

## Approved case_group_002 table preflight

The local proof used only files resolved by the ignored private registry and safe case/source registries. Each document ran in an isolated worker. There was no ordinary upload, model call, OCR/VLM, rendering, Knowledge/RAG or vector path.

Safe aggregate:

| Metric | Result |
| --- | ---: |
| Approved documents inspected | 16 |
| Formats | 2 CSV / 4 HTML / 8 PDF / 2 XLSX |
| Documents with projections | 9 |
| Documents partial/blocked | 5 |
| PDF table candidates found | 40 |
| Total projections | 81 |
| Native / PDF projections | 67 / 14 |
| Quality high / medium / low / blocked | 28 / 6 / 42 / 5 |
| Rows / cells | 54,939 / 275,259 |
| Source-value refs | 275,732 |
| Fallback refs | 228 |
| Duplicate / unaccounted refs | 0 / 0 |
| Gate 2 no-model packages built | 52 |
| Gate 2 packages budget-blocked | 24 |
| Projection artifacts persisted in isolated stores | 81 |
| Knowledge backend records | 0 |

The preflight status is `passed` for contract validation, coverage and guards. It is not a claim that every approved document is ready for model extraction.

## Performance and budgets

Whole approved preflight:

- total isolated-worker runtime: `1030.143 s`;
- maximum document runtime: `381.256 s`;
- total serialized projection payload: `394,941,933 bytes`;
- maximum single projection payload: `20,167,808 bytes`;
- that over-budget projection was `blocked`, not truncated-complete.

Worst-case approved XLSX timing probe:

- 13 projections;
- 26,011 rows and 122,766 cells;
- 122,766 source-value refs;
- table-projection layer runtime: `260.197797 s`;
- full worker runtime including parse/persistence: `382.741 s`;
- total projection payload: `176,270,539 bytes`;
- largest projection: `18,210,433 bytes`;
- 2 bounded Gate 2 packages built and 11 row-budget blocked.

The result is functionally correct but performance-sensitive. Later expansion should stream or window very large native tables instead of raising current budgets or sending whole tables to a model.

## Closed-world and anti-drift proof

Production, control and smoke routes use the same factory path. The new anti-drift anchors explicitly forbid direct ref minting and PDF semantic promotion. Self-contained bundles include `table_projection`; bundle tests prove operation without repo-package imports. No workspace-only import, filesystem path hack, undeclared dependency or environment assumption was added.

Test isolation uses temporary SQLite ArtifactStores and payload roots. The irreversible boundary is private artifact persistence; tests assert resolver-gated records, no Knowledge backend, and unchanged store state during Gate 2 dry-run. No executable HTTP handler path was changed.

## Guard result

Proven false throughout synthetic and approved proofs:

- ordinary processed upload used;
- Knowledge/RAG used;
- vectorization performed;
- OCR/VLM used;
- page rendering used for extraction;
- Gate 2 model called;
- source facts persisted;
- tax/declaration/XLS work performed;
- PDF semantic table truth claimed.

## Readiness decision

Ready next step: a separately authorized, bounded Gate 2 table-domain extraction slice may consume only projections where `validator_status=passed`, `projection_status=ready`, quality/fallback metadata is preserved and package budgets pass.

Not ready: automatic default model-runtime switch, whole-table model input, whole-corpus expansion, or treating all 40 PDF candidates as semantic tables.

## Final statuses

```text
TABLE_REPRESENTATION_CONTRACT_READY
TABLE_RECONSTRUCTION_QUALITY_CONTRACT_READY
NATIVE_TABLE_PROJECTION_READY
PDF_TABLE_PROJECTION_READY
PDF_TABLE_CANDIDATES_HARDENED
TABLE_COVERAGE_VALIDATOR_READY
TABLE_SOURCE_VALUE_REFS_READY
TABLE_SYNTHETIC_NATIVE_PASSED
TABLE_SYNTHETIC_PDF_PASSED
CASE_GROUP_002_TABLE_PREFLIGHT_READY
PDF_TABLE_GATE2_NO_MODEL_DRY_RUN_PASSED
NATIVE_TABLE_GATE2_NO_MODEL_DRY_RUN_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_TABLE_BOUNDED_GATE2_DOMAIN_EXTRACTION_SLICE
```

Bounded blockers retained:

```text
CASE_GROUP_002_TABLE_DOCUMENTS_PARTIAL_OR_BLOCKED=5
CASE_GROUP_002_GATE2_TABLE_PACKAGES_BUDGET_BLOCKED=24
AUTOMATIC_TABLE_MODEL_RUNTIME_SWITCH_NOT_AUTHORIZED
```
