# Broker Reports PDF Source-Bound Table Normalization v1

Status: `CURRENT PRODUCT CONTRACT`.

## Problem

The PDF parser preserves source literals but can flatten table structure. A
vision model sees the visual boundary but is not a reliable source of exact
amounts, dates or symbols. Neither side may replace the other.

## One product route

```text
one full PDF page image
  -> VLM returns one box_2d per visible table
  -> deterministic normalized-coordinate to PDF-point projection
  -> pdfplumber reconstructs rows, cells and original PDF literals in each box
  -> existing NormalizedTableProjection validator
  -> canonical Gate 1 publication
```

The maintained entrypoints are
`PdfTableIntakeRuntimeFactory.create_for_openwebui`,
`PdfTableLocatorProjectionFactory.create`, the existing
`PdfTextLayerParserFactory`/`PdfPlumberLayoutAdapter`, and
`Gate1Normalizer.normalize`. The OpenWebUI Pipe and the server release stand
must use these owners. A smoke script may call the Pipe or those same factories;
it may not recreate the algorithm.

## VLM contract

The model receives exactly one full-page lossless render and returns only:

```json
{"tables": [{"box_2d": [0, 0, 1000, 1000]}]}
```

Coordinates are integers in Gemini native order
`[ymin, xmin, ymax, xmax]`, normalized to `0..1000` relative to the full image.
Every visually independent grid gets one box. Zero tables is a valid result.

The model must not return or choose text, values, rows, columns, cells,
financial meaning, PDF points, pixels, or pdfplumber settings. There is one
call per page, with no hidden retry, best-of-N, provider merge or transcription
fallback.

## Deterministic source binding

`PdfTableLocatorProjectionFactory` validates the full-page raster manifest and
maps normalized coordinates back to the PDF top-left point space. For each
validated region, pdfplumber works only inside that region. It must produce
exactly one validator-eligible table candidate with complete word ownership.

All cell literals and source refs come from the original PDF bytes. Model text
is never source evidence. The existing normalized-table projection owner is
the only publisher; the locator creates no parallel canonical schema.

## Fail closed

Missing or failed locator pages, overlapping/invalid boxes, zero or ambiguous
native candidates inside a claimed region, incomplete source coverage, or a
projection-count mismatch produce terminal blocker
`pdf_table_normalization_incomplete`. Partial tables and model-transcribed
values are not published.

The former dual-VLM semantic transcription and semantic-visual migration
routes are inactive for new writes. Their code and dated evidence may remain
for historical replay only.

## Frozen research lessons

- direct VLM construction of pdfplumber plans was too permissive;
- an added visual coordinate grid did not solve the task;
- native Gemini coordinates removed axis/pixel ambiguity;
- explicitly requesting one box per independent table prevented adjacent
  tables from being merged;
- the useful split of responsibility is visual location by VLM and exact
  extraction by pdfplumber.

No claim is made for arbitrary PDFs. Product operation must retain per-page
status, region/projection counts, typed blockers, runtime/cost telemetry and a
review path for unsupported pages.
