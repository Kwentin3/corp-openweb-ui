# Broker Reports PDF layout-rich normalization Slice 2 notes

Date: 2026-07-10  
Scope: Gate 1 PDF text-layer geometry and bounded Gate 2 input only

## Decision

Keep `pypdf==6.7.5` as the page-text and content-stream baseline. Add an exact
layout backend pair: `pdfplumber==0.11.10` and its pinned
`pdfminer.six==20260107`. The factory rejects missing or mismatched versions and
never silently downgrades a layout request to page text.

The backend reads bytes through `BytesIO`; it does not render pages and does not
invoke OCR/VLM. It materializes private character, word, derived line/block,
bbox and vector inventories. Reading order is parser/geometry evidence, not a
claim of human semantic order.

## Reconciliation and terminal outcomes

Layout words and lines are reconciled page-locally against the independent
`pypdf` page text. Exact and normalized text matches are accepted. A line may
also resolve through all of its constituent word refs. Mismatch, budget
overflow or missing inventory produces explicit `partial` coverage with exact
unaccounted refs; it does not weaken the complete page-text projection.

Duplicate overlaid characters are retained with `duplicate_of_char_ref`.
Hidden-text classification remains unavailable. Rotation is recorded from
parser evidence. Page and parent layout checksums include the pinned parser
configuration and deterministic geometry inventories.

## Units and tables

The unit builder creates bounded `pdf_line_cluster_unit` and
`pdf_table_candidate_unit` artifacts. Each selected layout word/line ref has
one coverage owner. Conflicting or partial-line table candidates fall back to
line clusters without losing refs.

Table detection is preflighted only when ruling-line or repeated aligned-text
evidence exists. Candidates contain strategy, geometry, cells, contributing
refs and confidence. They are explicitly non-semantic: they do not establish
headers, account meaning, transaction facts or a correct reconstructed table.

## Resource policy

Per-page and per-document limits bound chars, words, lines, vector objects,
candidate count, table-detection input and elapsed time. Raw adapter pages are
closed after parsing and discarded after unit materialization. Case-group
proof uses one fresh worker per PDF so parser caches and private inventories do
not accumulate across customer documents.

## Gate 2 boundary

ArtifactStore remains the only private resolver boundary. Input readiness,
router and segmenter accept bounded layout units, preserve selected refs,
coverage and table-candidate metadata, and perform no model call. Whole-parent
PDF coverage is false. Knowledge, RAG, vectorization, source-fact persistence
and Gate 3 remain outside this slice.

## Evidence summary

- synthetic contract suite: passed;
- case group 002: 8 PDFs / 217 pages, page text complete 6 and partial 2;
- layout complete 1 document / 26 pages, partial 7 documents / 191 pages;
- 13,519 words, 1,326 lines, 40 high-confidence geometry candidates;
- 6 line-cluster, 14 table-candidate and 187 page-text fallback units;
- isolated-worker peak working set: 382,447,616 bytes, below 512 MiB;
- no-model Gate 2 dry run: 20 packages, passed, ArtifactStore unchanged.

The seven partial layout documents remain a real blocker for corpus-wide
layout completeness: five hit the document inventory budget and two have
page-text reconciliation mismatches. Their page-text baseline and fallback
units remain available; their layout refs are not promoted as complete.
