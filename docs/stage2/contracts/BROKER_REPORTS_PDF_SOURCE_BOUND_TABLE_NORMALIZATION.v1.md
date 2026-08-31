# Broker Reports PDF Source-Bound Table Normalization v1

Status: `CURRENT PRODUCT CONTRACT`.

## Problem

The PDF parser preserves source literals but can flatten table structure. A
vision model sees the visual boundary but is not a reliable source of exact
amounts, dates or symbols. Neither side may replace the other.

## One product route

```text
current full PDF page image, plus the previous full page after page 1
  -> one VLM call returns current-page title/header/table boxes and one boundary decision
  -> deterministic normalized-coordinate to PDF-point projection
  -> pdfplumber reconstructs rows, cells and original PDF literals at each box
  -> existing NormalizedTableProjection validator
  -> canonical Gate 1 publication
```

The maintained entrypoints are
`PdfTableIntakeRuntimeFactory.create_for_openwebui`,
`PdfTableLocatorProjectionFactory.create`, the existing
`PdfTextLayerParserFactory`/`PdfPlumberLayoutAdapter`, and
`PdfSourceBoundTableAssemblerFactory.create`, then `Gate1Normalizer.normalize`.
The OpenWebUI Pipe and the server release stand
must use these owners. A smoke script may call the Pipe or those same factories;
it may not recreate the algorithm.

## VLM contract

Page 1 receives its unmodified full-page PNG. Page N receives the unmodified
full-page PNGs for N-1 and N, in that order. The same single page call returns:

```json
{"tables": [{"table_box_2d": [0, 0, 1000, 1000], "title_box_2d": null, "header_box_2d": null}], "boundary_from_previous": {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"}}
```

Coordinates are integers in Gemini native order
`[ymin, xmin, ymax, xmax]`, normalized to `0..1000` relative to the full image.
Every visually independent grid gets one box. Zero tables is a valid result.

The model must not return or choose text, values, rows, columns, cells,
financial meaning, PDF points, pixels, or pdfplumber settings. The boundary
decision can only be `CONTINUATION`, `INDEPENDENT`, `AMBIGUOUS`, or
`NOT_APPLICABLE`; runtime binds it only to previous-last and current-first.
There is one
call per page, with no hidden retry, best-of-N, provider merge or transcription
fallback.

## Deterministic source binding

`PdfTableLocatorProjectionFactory` validates the full-page raster manifest and
maps normalized coordinates back to the PDF top-left point space. For each
validated region, the locator box remains the authority for word ownership.
The parser crop alone expands by one PDF point on every bounded side so a
slightly clipped outer ruling cannot remove the last row or column. Words whose
centres are outside the original locator box never become table values.

Pdfplumber must produce exactly one validator-eligible table candidate with
complete word ownership. Its native row slots, missing slots and cell spans are
preserved; the adapter must not flatten `table.cells` and re-number cells by
proximity. Parser-created axes containing no source word anywhere are removed
mechanically. No non-empty row or column may be removed.

All cell literals and source refs come from the original PDF bytes. Model text
is never source evidence. The existing normalized-table projection owner is
the only publisher; the locator creates no parallel canonical schema.

## Adjacent-page continuation

The source-bound locator is the only identity owner. A `CONTINUATION` decision
connects only the previous page's last validated table to the current page's
first validated table. The assembler verifies adjacent pages and compatible
atomic column edges, then emits one logical projection per connected component
before Canonical. Repeated continuation headers are removed from the logical
body only through their validated source-bound header refs. Their original
values remain exactly once in the existing `source_value_refs`,
`private_values`, and `source_value_index` custody containers. Canonical and
the semantic mapper do not repair the table.

`INDEPENDENT` leaves both tables separate. `AMBIGUOUS`, a provider/schema
failure, or a `CONTINUATION` with an incompatible grid blocks the whole
document before Canonical and facts.

## Fail closed

Missing or failed locator pages, overlapping/invalid boxes, zero or ambiguous
native candidates inside a claimed region, incomplete source coverage, or a
projection-count mismatch produce terminal blocker
`pdf_table_normalization_incomplete`. Partial tables and model-transcribed
values are not published.

Line-cluster text retained after a failed table projection is source evidence,
not a table fallback and not a successful normalization result. Historical
field names containing `fallback` do not change that rule. The former legacy
route must not be activated as a substitute for this product path.

The former dual-VLM semantic transcription and semantic-visual migration
routes are inactive for new writes. Their code and dated evidence may remain
for historical replay only.

## Frozen research lessons

- direct VLM construction of pdfplumber plans was too permissive;
- an added visual coordinate grid did not solve the task;
- native Gemini coordinates removed axis/pixel ambiguity;
- explicitly requesting one box per independent table prevented adjacent
  tables from being merged;
- a one-point parser-only crop margin recovered rulings clipped by locator
  coordinates without expanding source-word ownership;
- preserving native row slots and spans retained merged headers and totals;
- removing only globally empty parser axes eliminated false spacer rows and
  columns in borderless and shaded tables;
- the useful split of responsibility is visual location by VLM and exact
  extraction by pdfplumber.

No claim is made for arbitrary PDFs. Product operation must retain per-page
status, region/projection counts, typed blockers, runtime/cost telemetry and a
review path for unsupported pages. Wrapped text may remain represented as
multiple physical rows when the PDF contains no unambiguous logical row
boundary; low reconstruction quality must stay visible rather than being
repaired by semantic guessing.
