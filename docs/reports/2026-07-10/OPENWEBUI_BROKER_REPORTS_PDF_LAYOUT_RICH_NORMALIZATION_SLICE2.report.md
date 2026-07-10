# OpenWebUI Broker Reports PDF layout-rich normalization Slice 2

Date: 2026-07-10
Repository: `corp-openweb ui`
Outcome: implemented, locally verified and deployed to the Gate 1 Function

## Delivered

- Exact dependency contour: `pypdf==6.7.5`, `pdfplumber==0.11.10`,
  `pdfminer.six==20260107`.
- Factory-only `page_text`, `layout_words`, `layout_lines` and
  `table_candidates` capabilities with fail-closed import/version checks.
- Private char/word/line/block/bbox/vector/table-candidate inventories,
  deterministic order refs, configuration refs and page/parent checksums.
- Page-local word/line reconciliation with explicit complete, partial and
  unaccounted coverage outcomes.
- Bounded `pdf_line_cluster_unit` and non-semantic
  `pdf_table_candidate_unit` creation with exact ref ownership.
- ArtifactStore-backed Gate 2 readiness, router and segmenter support without
  model execution or store mutation.
- Isolated-worker customer-case preflight and reusable live runtime proof.

No OCR/VLM, page rendering, ordinary processed upload, Knowledge/RAG,
vectorization, source-fact model call or Gate 3 work was performed.

## Dependency and factory proof

The live Gate 1 Function metadata carries the exact three dependencies. The
post-update live content SHA-256 equals the local generated bundle SHA-256:

`6f8d62998c2ca5597669190c13ec5ae8a351e12fc2c5fd1f79434843eb9e29c7`

The initial update request timed out while OpenWebUI processed the new
requirements. A separate read-only readback proved that the update completed;
the write was not repeated.

Inside the bundled OpenWebUI container, the runtime proof imported the exact
versions and executed a synthetic in-memory one-page PDF through the
`table_candidates` factory capability:

- bundle: `gate1_pdf_layout_rich_slice2_v0`;
- versions match: true;
- layout status: complete;
- pages: 1;
- customer documents: false;
- OCR/VLM: false;
- page rendering: false.

## Provenance and coverage behavior

Page text and layout are independent projections. Layout content can be
complete only when page-local words/lines reconcile to the `pypdf` page text
and every selected ref has one owner. Normalized whitespace/control matching
is recorded; a line may resolve through all its constituent word refs.

Overlaid duplicate characters retain `duplicate_of_char_ref`. In the synthetic
duplicate fixture, `pypdf` and geometry words disagree, so layout is correctly
partial and every selected word/line ref appears in `unaccounted_refs`. The
page-text baseline remains available and unchanged.

Table candidates retain strategy, confidence, bbox/cell/contributing refs and
fallback refs. They are geometry candidates only. No header meaning, monetary
fact, account classification or semantic table truth is asserted.

## Synthetic verification

The final local suite passed:

- `python -m compileall`: passed;
- full service test suite: 133 passed;
- focused PDF Slice 1/Slice 2/bundle suite: 12 passed;
- factory pin/no-downgrade, duplicate chars, geometry/checksums, ruled/aligned
  candidates, ambiguity fallback, budgets, multi-column reconciliation,
  ArtifactStore and no-model Gate 2 paths: passed.

## Case group 002 aggregate

The controlled preflight processed each approved PDF in a fresh worker to
bound parser caches and private inventory lifetime.

| Measure | Result |
|---|---:|
| PDFs / pages | 8 / 217 |
| Page-text documents | 6 complete / 2 partial |
| Layout documents | 1 complete / 7 partial |
| Layout pages | 26 complete / 191 partial |
| Words / lines | 13,519 / 1,326 |
| High-confidence geometry candidates | 40 |
| Line-cluster / table-candidate / fallback page units | 6 / 14 / 187 |
| Layout / generic source refs | 3,567 / 18,569 |
| Total / maximum PDF runtime | 208.809 s / 33.292 s |
| Maximum layout parser page | 2.844 s |
| Maximum worker working set | 382,447,616 bytes |
| Memory guard | passed, below 512 MiB |

All safe aggregate coverage and validators passed. ArtifactStore contained 8
payloads and 207 units, with zero Knowledge records.

The bounded Gate 2 dry run selected a `pdf_table_candidate_unit`, built 20
packages, preserved layout refs/coverage/candidate metadata, kept whole-parent
and whole-PDF coverage false, and left ArtifactStore unchanged. Model call,
source-fact persistence, Knowledge/RAG and vectorization were all false.

## Honest remaining blockers

Only one of eight PDFs is layout-complete. Five documents exceeded the
document inventory budget; two have page-text word/line reconciliation
mismatches. These are terminal `partial` outcomes, not hidden truncation. Their
page-text baseline and page fallback units remain usable, while their layout
inventories are not promoted as complete.

Therefore this slice is ready for bounded Gate 2 domain extraction from
validated complete layout units. It does not establish corpus-wide layout
coverage, semantic table reconstruction or source-fact correctness.

## Final statuses

```text
PDF_LAYOUT_BACKEND_RUNTIME_READY
PDF_LAYOUT_WORD_LINE_REFS_READY
PDF_LAYOUT_CHECKSUMS_READY
PDF_LINE_CLUSTER_UNITS_READY
PDF_TABLE_CANDIDATE_UNITS_READY
PDF_TABLE_CANDIDATES_REMAIN_NON_SEMANTIC
PDF_LAYOUT_SYNTHETIC_PASSED
CASE_GROUP_002_PDF_LAYOUT_PREFLIGHT_READY
CASE_GROUP_002_PDF_LAYOUT_UNITS_AVAILABLE
PDF_GATE2_LAYOUT_INPUT_READINESS_DRY_RUN_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_PDF_BOUNDED_GATE2_DOMAIN_EXTRACTION_SLICE
```
