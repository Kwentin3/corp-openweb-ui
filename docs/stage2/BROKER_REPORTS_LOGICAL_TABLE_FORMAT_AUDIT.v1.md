# Broker Reports Logical Table Format Audit v1

Status: current-format audit; no format change

Effective date: 2026-07-31

## Verdict

```text
CURRENT_LOGICAL_TABLE_FORMAT = FIT_WITH_EXPLICIT_GAPS
```

The format is fit for the released, bounded profile: one page-local crop with
one supported numeric table. It preserves source-visible strings/nulls, row
order and row/value binding well enough for that profile. It is not fit as a
complete table-with-document-context format. It has no explicit table title,
section, neighboring text, header hierarchy, group edges, note/footnote links
or cross-page continuation.

The verdict is deliberately scoped. It does not claim a universal table
parser, multi-page support or whole-document sufficiency.

## Format actually in use

The model-facing owner is
`semantic_visual_table_contracts.py::semantic_table_transcription_schema`.
The closed root has exactly:

```json
{
  "description": "short source-oriented observation",
  "rows": [["source-visible text", null]]
}
```

`SemanticVisualTableMaterializationFactory` deterministically pads short rows,
mints row/column/cell IDs, stores a canonical rectangular grid and creates a
Gate 2 normalized-table projection. It sets:

- `physical_geometry_claimed=false`;
- every cell span to `1`;
- every row role to `unknown_row_role`;
- `header_to_column_mapping_status=not_inferred`;
- `semantic_header_truth_claimed=false`;
- `semantic_table_truth_claimed=false`.

`description` remains in the private semantic envelope. The Gate 2 projection
and model source projection primarily carry rows/cells; the description is not
a substitute for table title or document context.

## Evidence used

The audit used two evidence layers without new provider calls:

1. Fresh read-only normalization of five real PDFs. Four readable PDFs produced
   31 page-local table candidates over 24 pages; one six-page encrypted PDF was
   correctly blocked with `pdf_encrypted_without_key`. Twenty-two pages had
   both table and line units and 16 had non-monotonic unit line order.
2. The frozen 2026-07-22 actual-corpus qualification: eight supported real
   source-bound table crops across at least four broker structures and six
   layout families. Gemini preserved 166/166 amounts and 156/156 tested
   row/value bindings, with zero hallucinated labels or amounts. One ninth
   long-form prose grid was fail-closed as unsupported.

Private crops, literal values, raw provider output, source refs, filenames and
local paths were not copied into Git.

## Required cases

| Case | Human-visible source | VLM/parser result | Logical format retained | Lost or unproven | Understandable without PDF |
| --- | --- | --- | --- | --- | --- |
| Simple table | ordinary labels and numeric cells | real accepted crop plus fresh parser candidates | row order, strings/nulls and binding | external title/section not retained | Yes, within the crop's bounded subject |
| Row labels | labels paired with values | real accepted crops preserved tested bindings | label remains in the logical row | no explicit `row_label` role | Usually; role is implicit in position |
| Multi-level header | multiple visible header lines/merged presentation | real `merged_headers` family passed content gate | visible header strings may remain as rows | levels, spans, header-to-column map and scope are absent | Partial; ambiguous headers require PDF |
| Row groups | group/section bands among rows | contract permits one text cell plus nulls | group text and order may remain | no parent/group relation or group role | Partial |
| Totals and subtotals | numeric total/subtotal labels and values | real `totals_subtotals` family passed literal/binding gate | literals and row order remain | subtotal/total semantic role is not materialized | Partial; printed words help, relations do not |
| Empty cells | visibly blank logical positions | `null` is required for no visible text | `semantic_null` or deterministic short-row padding | unreadable and blank cannot be distinguished by the two-value cell contract | Yes for ordinary blanks; no for unreadable source |
| Footnote | marker and related note near/below table | no qualified real footnote case; crop prompt excludes nearby non-table material | no explicit footnote field or link | marker-to-note relation and possibly note text | No; evidence gap and schema gap |
| Continued table | table fragments on multiple pages | intake and semantic transcription are page/crop-local | each accepted fragment could be a separate table | no continuation identity, repeated-header policy or joined order in current semantic projection | No; not qualified |
| Different broker/layout | at least four broker structures; borderless, simple grid, sparse, merged headers, totals/subtotals, limited complex layout | eight accepted, one prose grid unsupported | accepted-profile rows and bindings | outside-profile generalization remains unproven | Yes only for supported single-crop numeric layouts |

## Explicit gaps

The format has ten concrete gaps:

1. no authoritative table title;
2. no link to the containing document section;
3. no preceding or following paragraph relation;
4. no explicit raw-header role or header-to-column mapping;
5. no multi-level header hierarchy or spans;
6. no row-group parent/child relation;
7. no explicit total/subtotal semantic relation;
8. no note or footnote relation;
9. no cross-page continuation/fragment relation;
10. no distinction between unreadable content and an empty logical cell.

The first six and the document period/header gap observed in KT2.1 explain why
a mechanically accurate row/value table can still be semantically insufficient
for a financial type decision.

## What the format does well

- It keeps provider responsibility small: transcription, not geometry or
  financial interpretation.
- It is strict and bounded: exactly `description + rows`, strings/nulls only.
- It preserves row order and tested row/value binding for the accepted profile.
- Deterministic code owns IDs, padding, provenance, hashes and persistence.
- Unsupported layouts can fail closed instead of producing fake cells.

These are reusable properties. They do not cure the missing document context.

## Corpus limits

```text
REAL_PDFS_FRESHLY_AUDITED = 5
REAL_PDFS_READABLE = 4
REAL_PDFS_BLOCKED_AS_ENCRYPTED = 1
REAL_TABLE_CROPS_AUDITED = 8
MULTI_PAGE_TABLES_AUDITED = 0
DIFFERENT_BROKER_STRUCTURES = 4
CORPUS_GAP = TRUE
```

`CORPUS_GAP=TRUE` because no qualified real cross-page continuation or
footnote-bound table exists in the safe evidence used here. Synthetic fixtures
may test shapes but cannot close that real-corpus gap.

## Scope stop

No replacement format is proposed here. DOC1 may use these facts to define a
document contract; it must not silently promote this page-local logical table
into a whole-document abstraction.
