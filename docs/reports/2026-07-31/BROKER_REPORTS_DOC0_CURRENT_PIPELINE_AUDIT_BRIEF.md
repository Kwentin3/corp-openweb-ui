# Broker Reports DOC0 Current Pipeline Audit Brief

Date: 2026-07-31

## Decision

The current pipeline is mapped. It preserves exact private source bytes and
rich parser observations, but downstream document context is fragmented.

```text
WHOLE_DOCUMENT_ARTIFACT = FRAGMENTED
FIRST_IRREVERSIBLE_CONTEXT_LOSS = PdfLayoutUnitBuilder._build_page_units
CURRENT_LOGICAL_TABLE_FORMAT = FIT_WITH_EXPLICIT_GAPS
AUTOMATIC_LEGACY_FALLBACKS_TOTAL = 3
SILENT_CONTEXT_DEGRADATION_PATHS_TOTAL = 4
REUSABLE_TOOLS_TOTAL = 21
```

The first proven loss occurs when a PDF page becomes table units plus line
clusters without one interleaved block order or explicit section, title, note,
footnote and continuation relations. Gate 2 consumes bounded units/segments,
not the parent PDF payload or a whole-document object.

Five real PDFs were audited read-only. Four readable PDFs produced 31 table
candidates; one encrypted PDF was correctly blocked. Existing frozen evidence
adds eight accepted real table crops across at least four broker structures.
No real cross-page or footnote-bound table was qualified, so the corpus gap is
explicit.

The useful tools should be isolated and reused. The unit-only document route
and automatic degraded-context continuations should be frozen for expansion
and retired only after a later, independently proven cutover.

DOC0 changes documents only. It performs no provider call, live mutation,
pipeline implementation, model qualification or product activation. Do not
start DOC1 from this brief alone; use the pipeline map, context matrix,
logical-table audit and reusable-tooling inventory together.
