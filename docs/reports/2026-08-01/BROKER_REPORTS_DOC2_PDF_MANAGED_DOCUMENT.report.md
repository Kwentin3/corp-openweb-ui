# Broker Reports DOC2 PDF Managed Document Closure Report

Status: `PASSED`

Date: 2026-08-01

## 1. Closure boundary

DOC2 adds one inactive, deterministic PDF-to-Managed-Document-v1 builder before
the DOC0 loss point. It proves real-PDF source coverage and PDF-to-artifact
parity without activating a product route or starting DOC3/DOC4.

Exact implementation chain:

- base: `88e2b4931aee613ef64a187ba475ce3a367e4ca8`;
- implementation head: `a147adc8ad0f99f3f53bf7a4be09b4acdf4d6f2e`;
- implementation PR: `#249`;
- implementation merge: `0c986919296de16f42ec322400c85e5eee9914f1`;
- evidence merge: reported in the terminal response because a commit cannot
  name its own future merge commit.

The implementation head and merge commit have the same Git tree,
`c5170edbeae90302cbcbdc3ef777f09660e329e1`.

## 2. Builder position and reused owners

`ManagedPdfDocumentFactory` is the single builder owner. It observes original
PDF bytes through the existing `PdfTextLayerParserFactory` page-text and
table-candidate capabilities before
`PdfLayoutUnitBuilder._build_page_units`, the DOC0 first irreversible loss.
The old page-local units are not a document-order authority and no legacy
fallback is called.

The builder reuses the DOC1 schema/semantic validator, the existing
`NormalizedTableProjectionFactory` and deterministic native-table validator,
and `ArtifactStoreFactory`/`ArtifactResolver` for private offline
persistence/readback. No workspace-only import or path shim is used.

## 3. Inventory, reading order, and blocks

Before document materialization, each page boundary, parser text block, text
line, table region, validated logical table, page-level visual observation, or
terminal parser failure receives a stable source observation. Every private
observation stores available text when applicable, page/bbox or private refs,
checksum, parent/related/overlap IDs, exact parser provenance, and processing
status.

Order is page order, then parser block order, then parser word order. A table
is inserted at the first word it owns. Duplicate line ownership, orphan or
duplicate word scope, overlapping table ownership, missing candidate words,
or incomplete line scope is terminal `BLOCKED`.

Text outside table ownership becomes ordered `PARAGRAPH` blocks. A validated
native grid becomes `TABLE`; an invalid table region becomes source-bound
`UNKNOWN` plus a structure loss. Source-visible image objects become a
page-bound private `VISUAL` container with explicit content and exact-placement
losses. No semantic financial classification is claimed.

## 4. Table ownership and coverage

Table words have exactly one owner. Once a candidate is emitted, all later
parser blocks containing its words bind back to that same output block; those
words are never copied into paragraphs. A `TABLE` requires passed projection,
validated geometry/source binding, supported reconstruction, and medium/high
quality.

Every source observation has exactly one coverage disposition. Runtime and
JSON Schema validation require disposition-specific owners. All 112
`REPRESENTED_BY_TABLE` entries carry a block ID, anchor ID, table ID, and
`source_word_ownership_to_validated_table_block_v1` mapping method. Known
losses require a source-bound owner and DOC1 loss ID. Duplicate suppression
requires exact source-observation proof and a final block owner.

Terminal accounting:

```text
source_observations_total = 1207
represented_source_observations_total = 353
duplicate_suppressed_observations_total = 0
known_loss_observations_total = 853
blocked_source_observations_total = 1
unresolved_source_observations_total = 0
unaccounted_context_loss_total = 0
invented_source_content_total = 0
source_order_conflicts_total = 0
```

## 5. Real-PDF corpus

The same five private DOC0 PDFs were processed by SHA-256 identity. Bytes,
literal values, filenames, raw refs, and local paths remain outside Git.

| Safe ID | Pages | Result | Valid document | Validated tables | Unknown table regions | Visual blocks | Known losses |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| `real_pdf_1` | 1 | `PARTIAL` | yes | 0 | 1 | 0 | 1 |
| `real_pdf_2` | 2 | `PARTIAL` | yes | 0 | 2 | 2 | 6 |
| `real_pdf_3` | 6 | `BLOCKED` encrypted | no | 0 | 0 | 0 | 0 |
| `real_pdf_4` | 15 | `PARTIAL` | yes | 0 | 14 | 1 | 16 |
| `real_pdf_5` | 6 | `PARTIAL` | yes | 6 | 9 | 6 | 21 |

There are four readable/non-blocked valid documents across four broker
structures. The encrypted PDF produces only a blocked inventory, receipt, and
trace; no Managed Document is minted.

## 6. Safe structural examples

The complete six-page block-order example for the table-heavy document is:

```text
P1 PAGE -> TEXT -> TEXT -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> VISUAL
P2 PAGE -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> VISUAL
P3 PAGE -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> VISUAL
P4 PAGE -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> VISUAL
P5 PAGE -> TEXT -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> TABLE_REGION -> TEXT -> TEXT -> VISUAL
P6 PAGE -> TABLE_REGION -> TEXT -> TEXT -> TEXT -> TEXT -> VISUAL
```

One redacted validated `TABLE` example is on page 1 at structure ordinal 6:
10 rows, 3 columns, 0 empty/unreadable cells. Title, header hierarchy, row
groups, units, footnotes, and continuation remain `UNKNOWN`; totals remain
`NOT_CLASSIFIED`. Its pointer contains block ID, table ID, anchor IDs, page,
and row/column bounds, while values stay private.

One known-loss example is an invalid parser table region retained as an
`UNKNOWN` block with source text/private location and a DOC1
`pdf_table_grid_not_validated` structure loss. It is not promoted to table
truth and not discarded.

## 7. Three-pass parity review

Four readable PDFs received three isolated passes:

1. `PDF_ONLY`: PDF bytes/parser outputs only, sealed before artifact access;
2. `ARTIFACT_ONLY`: validated Managed Document only;
3. `COMPARISON`: the two sealed checklists only.

The checklists cover passport discipline, every structural item, full block
order, ordered and unordered hashes of all values, every table's position and
structure, visuals, unknown/loss accounting, and provenance. Each structure
item, table, and sample has a pass-specific source pointer. The one-page simple
PDF checks all 463 value tokens per pass. The table-heavy PDF checks 20
deterministic source-bound samples per pass in addition to full-value hashes
and every table.

Results:

```text
pdf_only_checklists_total = 4
artifact_only_checklists_total = 4
parity_comparisons_total = 4
full_parity_documents_total = 4
table_heavy_parity_documents_total = 1
critical_parity_mismatches_total = 0
noncritical_parity_findings_total = 0
all_comparison_dimensions = MATCH
```

An earlier diagnostic oracle compared raw parser-word order with validated
table grid order and reported three table-heavy mismatches. Values and
multisets were exact. The PDF-only oracle was corrected to derive validated
row/cell order independently from PDF cell inventory, after which all ordered
hashes, table signatures, and value samples matched. No builder value was
changed to close that diagnostic.

## 8. Persistence and replay

The offline runner writes private Managed Documents, inventories, coverage
receipts, build traces, and checklists under ignored local storage. Its scoped
DOC2 artifact types are admitted only during the offline operation, persisted
through `ArtifactStoreFactory`, and independently read back through
`ArtifactResolver`. The product artifact registry remains unchanged.

Two independent builds were made for every PDF. All 38 JSON outputs in run A
and run B matched byte-for-byte; replay mismatches are zero.

## 9. Review, tests, and CI

Independent review found and closed three actionable gaps: missing
disposition-specific owner laws, incomplete explicit inventory fields/word
scope, and an under-specified parity oracle. Final verification is:

```text
targeted DOC2/contract/architecture tests = 44 passed
full local suite = 2349 passed, 5 historical skips, 0 failed, 0 errors
warnings = 5
targeted Ruff = PASSED
Draft 2020-12 schemas = PASSED
private receipt/checklist validation = PASSED
safe summary seals = PASSED
git diff --check = PASSED
generated bundle diff = 0
```

GitHub `broker-reports-ci` passed on exact implementation head
`a147adc8ad0f99f3f53bf7a4be09b4acdf4d6f2e` in 5m45s. PR #249 was then merged.
The merged-main tree is byte-identical to the tested implementation tree.

## 10. Non-change proof and stop

DOC1 schema, generated bundles, product routes, provider/model execution,
Knowledge/RAG, embeddings, vectorization, prompts, valves, admissions, and
live state did not change. Provider calls, product route changes, live changes,
legacy fallbacks, and generated bundle diffs are zero.

```text
DOC2_PDF_MANAGED_DOCUMENT_BUILDER = PASSED
REAL_PDF_TO_MANAGED_DOCUMENT = PROVEN
PRIMARY_READING_ORDER = PRESERVED
TABLES_INSIDE_DOCUMENT_ORDER = TRUE
UNKNOWN_CONTENT_PRESERVED = TRUE
SOURCE_COVERAGE_RECONCILIATION = PASSED
PDF_ARTIFACT_PARITY_REVIEW = PASSED
DOC1_SCHEMA_CHANGED = FALSE
LEGACY_FALLBACK_USED = FALSE
LLM_FRIENDLY_RENDERER = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

DOC2 stops here. DOC3 and DOC4 are not started.
