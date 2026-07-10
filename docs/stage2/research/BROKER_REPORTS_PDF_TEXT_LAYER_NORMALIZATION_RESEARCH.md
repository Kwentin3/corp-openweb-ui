# Broker Reports PDF text-layer normalization research

Date: 2026-07-10
Status: research ready; implementation not started

## Conclusion

Machine-readable Broker Reports PDFs can become extraction-grade Gate 2 input
without OCR, but only through a new page-aware text-layer projection. The
current stdlib parser cannot be promoted to that role: it is a bounded preview
heuristic, not a PDF object/layout parser.

The recommended route is deliberately incremental:

1. use the already-present `pypdf` runtime as the zero-new-dependency page/text
   baseline and structural control;
2. add `pdfplumber` / `pdfminer.six` as the proposed layout-rich backend for
   character/word geometry and table candidates after a closed-world
   dependency and performance proof;
3. keep PyMuPDF behind an explicit legal/commercial-license decision;
4. mint extraction units only after deterministic page, ref, checksum and
   coverage reconciliation passes;
5. call a table a `candidate` until geometry validation proves the candidate;
6. never use OCR/VLM or page rendering in this pipeline.

`parser_completeness_status=complete` means complete for the declared PDF
text-layer projection under the pinned parser/configuration. It does not mean
complete visible-page content, correct semantic reading order, correct table
semantics, or support for text that exists only in images.

## Current implementation

### What the profiler extracts

`profilers_pdf.py` currently:

- checks `%PDF-`, `%%EOF` and `/Encrypt` markers;
- estimates page count with a `/Type /Page` regex;
- regex-scans raw bytes and decoded streams for literal/hex `Tj` and `TJ`
  operands;
- decodes only directly visible streams and `FlateDecode` streams;
- caps collection at 5,000 chunks or 100,000 characters;
- joins chunks into one global string;
- persists at most the first 2,000 characters as a legacy preview slice;
- derives raster/table likelihood from marker and punctuation heuristics.

It does not parse xref/object graphs, resource dictionaries, inherited page
resources, font encodings/CMaps, all stream filter chains, form XObjects,
incremental updates, coordinates or the real content ownership of each page.
The preview labels pages 1-3, but the regex output is not actually mapped back
to those pages.

### Why it remains partial

`full_source.py` intentionally does not repeat the heuristic pass. For PDF it
emits a partial capability descriptor with:

- `pdf_heuristic_parser_not_full_coverage`;
- `pdf_full_text_not_reparsed_for_partial_payload`.

No `private_normalized_source_unit_v0` may be created from that descriptor.
The restriction is correct because the current output cannot prove:

- all pages and page content streams were processed;
- all text-showing operators were decoded;
- text belongs to the asserted page/range;
- ordering or character spans are stable;
- the 5,000/100,000 caps were not hit;
- values are reproducible through page-local payload paths;
- selected and non-selected page content is fully accounted.

The current parser is useful for profiling only. Extending its regex set would
still leave object, font, page ownership and layout correctness unresolved.

## Safe evidence gathered in this research

### Live dependency inventory

Read-only inspection of the deployed `openwebui` container found:

| Package/module | Live result |
|---|---|
| `pypdf` | installed, version `6.7.5` |
| `PyPDF2` | absent |
| `pymupdf` / `fitz` | absent |
| `pdfplumber` | absent |
| `pdfminer.six` | absent |

The bundled Broker Reports Pipes currently declare only `pydantic`, so a new
layout backend must be declared and stage-proven; a developer-workstation
installation is not runtime evidence.

### Approved `case_group_002` aggregate probe

A read-only, in-memory probe used the hash-verified private registry. It emitted
aggregate counts only: no raw text, filename, file id, path, account or personal
value. It performed no upload, ArtifactStore mutation, Knowledge/RAG/vector
write, OCR/VLM or model call.

| Measure | Runtime `pypdf 6.7.5` | Local PyMuPDF control |
|---|---:|---:|
| PDF documents opened | 8/8 | 8/8 |
| Pages enumerated | 217 | 217 |
| Pages with extracted text/words | 215 | 215 |
| Documents with text on every page | 6/8 | 6/8 |
| Page extraction errors | 0 | 0 |
| Replacement characters | 0 | 0 |
| Text characters / words | 763,306 chars | 105,704 words |
| Coordinate-bearing visitor fragments / text blocks | 107,775 fragments | 9,841 blocks |
| Images observed | not used as completeness proof | 46 image occurrences |

This proves that a material text layer is available across the approved PDF
set and that `pypdf` can enumerate it in the live runtime. It does not prove
that any of the eight documents already satisfies the proposed completeness
contract. In particular, the two pages without extracted text require page
classification, text-operator/font diagnostics and coverage accounting.

## Candidate evaluation

### `pypdf`

Strengths:

- already installed in the live container;
- pure Python and BSD-licensed;
- deterministic page enumeration and per-page text extraction;
- layout extraction mode and visitor callbacks for text fragments, matrices,
  fonts and PDF drawing operators;
- suitable for preflight, page text payloads, resource diagnostics and a
  second-engine control.

Limitations:

- no native word/block hierarchy or table finder;
- visitor coordinates are not reliable for every complicated form/transform;
- PDF itself has no guaranteed semantic layer, table model or reading order;
- full content streams can require extreme memory, so byte budgets are
  mandatory.

The official pypdf documentation explicitly warns that visitor coordinates
may be wrong in complicated documents and that one page content stream can
require very large memory. It also states that pypdf is not OCR and cannot
extract image-only text:
[pypdf text extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

Decision: use as the phase-1 baseline and preflight/control engine. A
`pypdf`-only payload may be complete for `page_text_projection_v0` when all
text-layer gates pass, but must declare `layout_capability=fragment_only` and
must not emit an authoritative table structure.

### `pdfplumber` / `pdfminer.six`

Strengths:

- MIT-licensed;
- exposes characters, words and bounding boxes;
- supports word grouping, character return, duplicate-character removal,
  lines/rectangles and configurable table finding;
- pdfminer layout analysis groups characters into words, lines and text boxes;
- best fit for stable page/word/line provenance and geometry-based table
  candidates without a copyleft licensing decision.

Limitations:

- absent from the live runtime and must be explicitly packaged;
- slower and more memory-intensive than PyMuPDF;
- reading order and tables are heuristic and configuration-sensitive;
- experimental line/layout APIs cannot be treated as stable source semantics
  without pinned version/config fixtures.

Official references:

- [pdfplumber word and table APIs](https://github.com/jsvine/pdfplumber/blob/stable/README.md?plain=1);
- [pdfplumber MIT license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt);
- [pdfminer.six layout analysis](https://pdfminersix.readthedocs.io/en/latest/topic/converting_pdf_to_text.html).

Decision: recommended layout-rich backend, introduced in a separate dependency
slice. Its output still creates table candidates, not guaranteed semantic
tables.

### PyMuPDF / `fitz`

Strengths:

- page text, blocks, words, raw character dictionaries and bounding boxes;
- `sort=True` support and fast extraction;
- built-in `Page.find_tables()`;
- the local control probe processed the approved set without page errors.

Official references:

- [PyMuPDF TextPage words/blocks/raw dictionaries](https://pymupdf.readthedocs.io/en/latest/textpage.html);
- [PyMuPDF table finder](https://pymupdf.readthedocs.io/en/latest/page.html#tables-and-related-classes).

Blocking concern: PyMuPDF is offered under AGPL or a commercial license. The
official product page describes the commercial option for proprietary use:
[PyMuPDF licensing](https://pymupdf.io/).

Decision: technically strong alternative, but not the default recommendation.
It can replace the layout backend only after an explicit legal/license decision
and closed-world runtime proof.

### Current stdlib heuristic

Decision: retain only for backward-compatible profiling while the new parser
is feature-gated. It cannot become extraction-grade through incremental regex
patches.

## Recommended parser policy

The parser selection is capability-based, not a silent fallback chain:

| Projection | Required backend | Allowed status |
|---|---|---|
| page text and page inventory | pinned `pypdf` | complete candidate after all text-layer gates |
| fragment coordinates | `pypdf` visitor | optional, `parser_reported_unverified` unless reconciled |
| characters/words/lines | pinned `pdfplumber` | complete candidate for declared layout projection |
| table geometry candidates | pinned `pdfplumber` | candidate only; separate confidence/coverage |
| PyMuPDF layout path | pinned PyMuPDF | disabled until licensing gate passes |
| image-only text | none | unsupported; no OCR/VLM |

The factory must fail closed when the requested capability is unavailable. It
must not silently downgrade a layout/table request to plain page text while
retaining a `complete` status.

## Completeness model

Three independent statuses are required:

1. `text_layer_projection_status`: did the pinned parser enumerate and account
   for the declared text-layer projection?
2. `visible_content_coverage_status`: are all visible information-bearing
   elements represented? In this no-OCR pipeline, mixed/image pages are
   `partial_out_of_scope` even when text-layer projection is complete.
3. `semantic_reconstruction_status`: are reading order, sections and table
   semantics proven? Usually `candidate` or `not_claimed`.

`parser_completeness_status=complete` is allowed only when all of these
text-layer gates pass:

- source checksum, parser engine/version/config and page count are pinned;
- document is not encrypted without an approved key and is not corrupt;
- every declared page is opened exactly once and has a page inventory entry;
- every page ends in one of `text_extracted`, `no_text_operators`, or a typed
  non-text classification; no extraction exception remains;
- content-stream size and runtime budgets are checked before extraction;
- no page output is silently capped or truncated;
- unresolved fonts/CMaps, unknown-font text fragments, decode failures and
  unsupported operations are zero or explicitly proven non-material;
- raw parser fragments reconcile with the canonical page text projection;
- each emitted page/block/line/word/value ref has one payload path and
  reproducible checksum;
- page refs form an ordered, duplicate-free page inventory;
- selected text refs plus non-selected layout/blank/non-text refs equal the
  declared inventory;
- page checksums reproduce the canonical page projections;
- the payload checksum reproduces from parser identity, policy and ordered page
  checksums;
- privacy and no-Knowledge/no-vector guards pass.

Any failed gate produces `partial` or `blocked` with typed reasons, for example:

- `pdf_encrypted_without_key`;
- `pdf_page_parse_failed`;
- `pdf_content_stream_budget_exceeded`;
- `pdf_unknown_font_mapping`;
- `pdf_text_operator_decode_incomplete`;
- `pdf_page_projection_reconciliation_failed`;
- `pdf_layout_backend_unavailable`;
- `pdf_coordinate_projection_unverified`;
- `pdf_two_engine_material_mismatch`;
- `pdf_image_only_no_text_layer`;
- `pdf_mixed_visible_content_out_of_scope`.

The last reason may coexist with a complete text-layer projection, but it
prevents any claim of complete visible-document coverage.

## Proposed private payload

Keep the ArtifactStore type `private_normalized_source_payload_v0`. Add a
format-specific `pdf_text_layer_projection` with schema
`pdf_text_layer_projection_v0`; do not create a parallel persistence family.

The projection contains:

- safe document/parser/config refs;
- declared page range and ordered page inventory;
- per-page content classification and extraction diagnostics;
- canonical page text plus raw fragment inventory in private storage;
- optional block/line/word inventories with bounding boxes and confidence;
- optional parser-native content object/xref refs for private diagnostics;
- table candidate refs and reconstruction diagnostics;
- text/page/fragment/character-span/source-value refs;
- raw-fragment, normalized-value, page, payload and source checksum refs;
- coverage buckets for text candidates, blanks/layout, non-text pages,
  deferred table semantics and rejected/partial fragments;
- the three independent completeness statuses.

Normative proposal:
`../contracts/BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md`.

## Proposed source units

Supported unit types:

- `pdf_page_text_unit`: default bounded unit, usually one page;
- `pdf_section_text_unit`: deterministic contiguous block/line range with an
  explicit section-detection policy;
- `pdf_line_cluster_unit`: contiguous line/fragment range when section or table
  semantics are not safe;
- `pdf_table_candidate_unit`: geometry-qualified candidate with row/cell refs
  and fallback text refs.

`pdf_summary_block_unit` is deferred. A semantic summary block would require a
domain interpretation that Gate 1 must not invent.

Each unit is built from a complete parent payload and carries the generic
source-unit contract plus page, block/line/word/span/value refs. Its declared
range is complete only when every selected ref is in exactly one accounted
bucket. A table candidate must preserve fallback text refs; if table geometry
is rejected, Gate 2 consumes line/text units instead of pretending the table is
real.

Normative proposal:
`../contracts/BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md`.

## Provenance and checksums

The existing source-provenance model remains authoritative, extended with
page-local PDF paths:

```text
source checksum ref
  -> page ref
  -> parser fragment ref
  -> block/line/word ref (when available)
  -> character span ref in canonical page text
  -> source value ref
  -> private payload path + value checksum ref
```

Rules:

- raw source checksum stays private; downstream sees an opaque ref;
- parser version/config is part of every page/payload checksum;
- parser-native PDF object/xref numbers are optional audit metadata, never the
  sole stable identity because rewriting a PDF may renumber objects;
- canonical JSON, ordered inventories and LF line endings are pinned;
- raw parser text and normalized value are separately checksummed;
- normalization may not erase the raw fragment/value relation;
- changing parser version/config produces a new payload, never in-place
  mutation of a legacy artifact;
- two-engine checks are diagnostics only; agreement is not proof of PDF truth.

## Table candidate policy

A table candidate is allowed only from deterministic geometry evidence such as
intersecting page lines/rectangles or repeated aligned word bands under a pinned
policy. The candidate records:

- `table_reconstruction_status=candidate`;
- strategy and tolerance policy ref;
- page/bbox, row/cell and contributing word/line refs;
- geometry confidence and rejection reasons;
- fallback ordered text refs;
- duplicate/overlap accounting with surrounding text units.

Gate 1 does not assert that candidate rows are economically or semantically
correct. Low-confidence or conflicting geometry emits no table unit. The text
remains covered by `pdf_line_cluster_unit`. Gate 2 may emit
`unknown_source_row` / text-based facts with exact provenance; it cannot upgrade
the candidate to source truth.

## Gate 2 input policy

Gate 2 may consume a PDF unit only after resolver, provenance, source-value,
checksum and coverage validation. Routing uses only bounded private
projections. It may use safe layout kinds and candidate strategy/confidence,
but not raw filenames or unseen pages.

Whole PDFs are never sent to the model. Suggested budgets are policy inputs,
not contract constants:

- page unit first;
- deterministic section/table candidate only when smaller and complete;
- line-cluster windows for oversized pages;
- selected refs partitioned exactly once across derived units;
- explicit deferred unit refs and no hidden remainder.

A PDF unit may participate in a limited Gate 2 vertical while the containing
case remains partial. Gate 3/full-case readiness still requires all selected
case coverage and issue rules; one valid PDF unit does not promote the package.

## Proof required before implementation can claim readiness

### Synthetic

Use a generated text-layer PDF containing two pages, repeated headers, a plain
paragraph, a ruled table candidate, an unruled table-like area, blank/layout
text and an image-only page marker. Prove:

- deterministic page count and page-local extraction;
- page/text/span/value refs and checksum reproduction;
- complete selected/accounted coverage;
- ruled table candidate and safe fallback for unruled ambiguity;
- budget overflow and unknown-font fixtures fail closed;
- no OCR/VLM and no page rendering for extraction;
- no upload, Knowledge, document or vector delta;
- deterministic rerun under the pinned engine/config.

### `case_group_002`

Run only after synthetic proof and dependency/runtime closure. Report safe
aggregates only:

- PDFs and pages with/without text layer;
- complete/partial/blocked payload counts and reason counts;
- whether at least one complete source unit validates;
- page/source-value/coverage checksum reproduction totals;
- optional table candidate counts, never raw cells;
- one bounded Gate 2 domain vertical only after unit validation;
- before/after Knowledge, document and vector deltas of zero.

The current aggregate probe is preflight evidence, not this acceptance proof.

## Risks and blockers

| Risk | Control |
|---|---|
| reading order differs from visible intent | store parser order and geometry order separately; never claim semantic order without policy proof |
| hidden/duplicate text | dedupe policy is explicit; raw fragments remain accounted |
| unknown fonts/CMaps | fail partial, do not substitute guessed text |
| huge content streams/OOM | preflight byte budgets and typed budget blocker |
| table hallucination | candidate-only contract and fallback text coverage |
| mixed text/images | separate text-layer from visible-content status |
| backend version drift | pin version/config and checksum parser identity |
| PyMuPDF licensing | legal/commercial gate before use |
| new dependency absent in Pipe | declare, bundle and stage-prove pdfplumber/pdfminer.six |
| dirty repository/current work | scope validation to the new/updated docs; do not claim unrelated tree cleanliness |

## Non-goals

- OCR/VLM or scanned-PDF support;
- page rendering as an extraction source;
- semantic repair of corrupted PDFs;
- tax, declaration, consolidation or XLS/XLSX;
- free-form LLM source facts;
- OpenWebUI core patch;
- Knowledge/RAG/vector loading;
- automatic promotion of `case_group_002` to full coverage.

## Research statuses

```text
PDF_TEXT_LAYER_NORMALIZATION_RESEARCH_READY
PDF_TEXT_LAYER_PIPELINE_BLUEPRINT_READY
PDF_TEXT_LAYER_CONTRACTS_PROPOSED
PDF_TEXT_LAYER_NO_OCR_BOUNDARY_READY
PDF_TEXT_LAYER_GATE2_INPUT_PLAN_READY
READY_FOR_PDF_TEXT_LAYER_NORMALIZATION_IMPLEMENTATION_SLICE
```
