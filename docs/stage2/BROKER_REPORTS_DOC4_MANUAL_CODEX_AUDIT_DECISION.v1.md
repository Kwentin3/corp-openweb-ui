# Broker Reports DOC4 Manual Codex Source Audit Decision v1

Effective date: 2026-08-01

Status: `MANUAL_SOURCE_AUDIT_COMPLETE; STRICT_EQUIVALENCE_FAILED`

## Decision

Codex manually reviewed the same four frozen PDF/View pairs after the external
provider experiment stopped without one completed pair. The audit covered all
24 native PDF pages, all four complete LLM Document Views, the 461 sealed gold
items, and the View's explicit blocks, tables, unknowns, issues and losses.

This is a separate source-grounded audit. It is not RUN A, RUN B, RUN C or RUN
D of the frozen provider protocol, does not create missing provider responses,
and does not change the historical result
`INCONCLUSIVE_MODEL_OUTPUT_FAILURE`.

## Result

The View is useful for narrative reading, search and high-level summarization,
but it is not strictly semantically equivalent to the PDF for exhaustive
financial extraction.

All 444 gold items that carry a source literal retained their meaning after
manual review. Only 427 were byte-for-byte present because line wrapping, OCR
and numeric spacing changed some literals. That strong literal retention does
not preserve table semantics by itself.

The PDF-only gold identifies 28 logical tables. The Views contain six validated
TABLE blocks and leave the other 22 without a validated grid. Across the corpus,
26 UNKNOWN blocks retain raw text while explicitly disclaiming row/column
truth. The lost bindings include fee-group membership, wide financial-matrix
columns, cross-page trade-table continuation, and the meaning of a critical
blank tax cell.

```text
MANUAL_CODEX_SOURCE_AUDIT = COMPLETED
MANUAL_CODEX_STRICT_SEMANTIC_EQUIVALENCE = FAILED
SOURCE_LITERAL_MEANING_PRESENT = 444/444
RAW_EXACT_SOURCE_LITERALS = 427/444
EXPECTED_LOGICAL_TABLES_TOTAL = 28
VALIDATED_TABLE_BLOCKS_TOTAL = 6
LOGICAL_TABLES_WITHOUT_VALIDATED_GRID_TOTAL = 22
UNKNOWN_BLOCKS_TOTAL = 26
SUMMARY_AND_SEARCH_USEFULNESS = USABLE_WITH_EXPLICIT_LIMITATIONS
ORIGINAL_PROVIDER_EXPERIMENT = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
```

## Protocol findings

The frozen DOC4 task is also too strict in the wrong place. It requires every
LLM-View financial fact to cite an existing TABLE cell, even when the View
correctly exposes that fact in a PARAGRAPH or UNKNOWN block. Only 17 of the 276
matched gold financial facts were located in validated TABLE blocks. A valid
View-arm answer is therefore impossible for much of the frozen checklist even
when a human can read the value from retained text.

The sealed gold is useful as a bounded checklist but is not exhaustive for the
dense brokerage report: its 42 financial items sample totals and selected rows,
while the PDF contains many explicit operation rows and fields. It cannot prove
the task prompt's promise to extract every explicit financial field.

## Safe use boundary

Use the current View for narrative context, discovery and summaries that state
its known losses. Require a native-source reread for any UNKNOWN table, any
cross-page table, any empty-versus-missing distinction, any visual meaning, or
any answer whose correctness depends on row/column binding.

Before another provider experiment, either restore validated grids and
continuation relations or replace exhaustive enumeration with a bounded set of
business questions. The latter should compare final source-grounded answers
without requiring every narrative or UNKNOWN fact to pretend it came from a
TABLE cell.

No provider call, product route, bundle, prompt, valve, admission, live state
or customer artifact was changed by this audit.
