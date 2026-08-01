# Broker Reports DOC4 Manual Codex PDF vs LLM View Audit

Status: `FAILED_STRICT_SEMANTIC_EQUIVALENCE`

Effective date: 2026-08-01

## 1. Plain result

The LLM Document View is like a careful text transcript of a spreadsheet: most
words and numbers are present, but some cell borders and column positions are
gone. It is good enough to understand what a document discusses and to find
many named values. It is not good enough to guarantee that every value remains
attached to the same row, column, subtotal or blank-cell meaning as in the PDF.

Therefore the manual result is:

```text
NARRATIVE_AND_HIGH_LEVEL_MEANING = LARGELY_PRESERVED
EXHAUSTIVE_FINANCIAL_FACT_EQUIVALENCE = FAILED
MANUAL_CODEX_STRICT_SEMANTIC_EQUIVALENCE = FAILED
```

## 2. Scope and method

Codex visually reviewed every page of the four frozen PDFs, reviewed every
complete View, reconciled all 461 sealed gold items, searched all 444 source
literals, and inspected the block type and source page for each matched fact.
The audit then checked the relationships that literal search cannot prove:
multi-column order, table title and row order, row/column binding, cross-page
continuation, blank-cell meaning and visual semantics.

The audit made zero provider calls. It did not use the failed provider outputs
and did not modify the frozen PDFs, Views or gold.

## 3. Aggregate evidence

| Measure | Result |
| --- | ---: |
| Frozen documents | 4 |
| Native PDF pages reviewed | 24 |
| Gold items | 461 |
| Critical gold items | 321 |
| Gold items with source literals | 444 |
| Raw exact source literals in View | 427 |
| Meanings manually found after formatting/OCR variance | 444 |
| Logical tables identified by gold | 28 |
| Validated TABLE blocks in View | 6 |
| Tables without a validated grid | 22 |
| Explicit UNKNOWN blocks | 26 |
| Gold financial facts | 276 |
| Matched gold financial facts in validated TABLE blocks | 17 |

The `444/444` result is content retention, not table equivalence. A flattened
sequence can contain every token and still lose which header owns which value.

## 4. Per-document conclusions

| Safe ID | Literal meaning | Validated tables / expected | Strict verdict | Decisive gap |
| --- | ---: | ---: | --- | --- |
| `real_pdf_1` | 37/37 | 0/4 | `FAILED` | the transaction-pricing columns are flattened, so fee-group membership is not source-bound |
| `real_pdf_2` | 43/43 | 0/0 | `FAILED` | multi-column/sidebar order is interleaved, one meaningful image is uninterpreted, and headings have OCR variance |
| `real_pdf_4` | 291/291 | 0/12 | `FAILED` | all financial grids are UNKNOWN raw text; wide matrix cell bindings cannot be reconstructed safely |
| `real_pdf_5` | 73/73 | 6/12 | `FAILED` | core valuation, portfolio, trade and final-tax tables are UNKNOWN; continuation and a critical blank cell lose semantics |

### `real_pdf_1`

All fees and rates remain readable. The transaction-pricing area originally
uses distinct trading-services and additional-services columns. The View keeps
their labels and row text but not a validated grid. A model may guess the
membership from sequence; the artifact does not prove it.

### `real_pdf_2`

The educational content remains readable and no account-specific values were
lost. However, the main column and sidebars are interleaved. At least one
critical checklist item is moved into the middle of main prose, and the
meaningful photograph is represented only as an uninterpreted visual object.

### `real_pdf_4`

Narrative notes and amounts are highly legible, including all literals that
initially appeared missing because of currency and decimal spacing. The hard
failure is structural: none of the 12 financial tables is a validated TABLE
block. Simple label/value lists remain understandable, but multi-column
netting and fair-value matrices do not retain source-bound cell coordinates.

### `real_pdf_5`

Six simpler tables are reconstructed correctly. The wide tables that carry
asset valuation, portfolio positions, trade rows and the final tax result are
not. Trade rows continue across pages without a validated continuation link.
The final-tax table also contains a critical blank cell whose meaning cannot be
distinguished from omitted text in the flattened representation.

## 5. Why the original gold and schema do not close the question

The gold checklist is strong evidence that source text survived, but it is not
an exhaustive semantic oracle for dense tables. The private brokerage report
contains many operation rows and fields; its gold records only 42 financial
items, mainly totals and selected endpoints.

The frozen LLM-View response contract also requires every financial fact to
cite an exact validated table cell. That rule excludes facts retained in
PARAGRAPH and UNKNOWN blocks. Only 17 of 276 matched gold financial facts were
located in validated TABLE blocks. This would make much of the View arm invalid
even if a model read the retained text correctly.

## 6. Safe conclusion and next move

Keep the View for narrative reading, search and high-level summaries with its
loss ledger visible. Do not use it alone as the canonical source for exhaustive
financial extraction while UNKNOWN tables remain.

The highest-value repair order is:

1. restore validated grids for wide UNKNOWN tables;
2. bind cross-page table continuations;
3. preserve explicit empty/unreadable cell state;
4. carry meaningful visual descriptions when they matter;
5. simplify the next experiment to bounded business questions or allow honest
   PARAGRAPH/UNKNOWN pointers instead of forcing every fact into a table cell.

The earlier external provider experiment remains
`INCONCLUSIVE_MODEL_OUTPUT_FAILURE`: it completed zero pairs. This manual audit
does not rebrand that run, but it does answer the practical representation
question: the current View is useful and substantially complete as text, yet
not strictly equivalent to the PDF.
