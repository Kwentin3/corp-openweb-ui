# OpenWebUI Broker Reports PDF text-layer normalization research report

Date: 2026-07-10
Repository scope: `corp-openweb ui`
Delivery type: research, contracts and implementation blueprint only

## Outcome

The PDF text-layer normalization design is ready for a bounded implementation
slice. This task did not implement or deploy a new PDF parser and did not claim
that any customer PDF already has a complete extraction-grade payload.

The research established:

- the current PDF parser is a bounded regex/stdlib preview heuristic;
- its output is correctly kept `partial` and cannot mint a full-source unit;
- the live OpenWebUI runtime already contains `pypdf 6.7.5`;
- all 8 approved `case_group_002` PDFs were opened by the live pypdf probe;
- 215 of 217 pages yielded text and 6 of 8 documents yielded text on every
  page;
- a local PyMuPDF control produced the same page/text-bearing-page counts;
- a deterministic text-layer payload/unit/coverage model can be added without
  OCR/VLM, Knowledge/RAG/vector loading or OpenWebUI core changes;
- the recommended target separates text-layer completeness from visible-page
  and semantic-table completeness.

## Current parser behavior

`services/broker-reports-gate1-proof/broker_reports_gate1/profilers_pdf.py`
currently:

- checks PDF header/EOF/encryption markers;
- estimates page count using a regex;
- extracts literal and hex `Tj`/`TJ` strings from raw and `FlateDecode` streams;
- caps extraction at 5,000 chunks / 100,000 characters;
- writes at most a 2,000-character legacy preview;
- has no authoritative page/object/font/CMap/layout/table model.

`full_source.py` therefore emits only an explicit partial PDF capability record
with `pdf_heuristic_parser_not_full_coverage` and
`pdf_full_text_not_reparsed_for_partial_payload`. It creates no
`private_normalized_source_unit_v0` for PDF.

The current code may lose or misrepresent page ownership, text operators,
fonts/CMaps, filter chains, form XObjects, reading order, coordinates, table
geometry and cap status. The page range attached to the preview is not derived
from actual page-local extraction. Adding more regex patterns would not close
those structural gaps.

## Runtime and safe probe evidence

### Dependency inventory

Read-only live-container inspection:

```text
pypdf: installed, 6.7.5
PyPDF2: absent
pymupdf/fitz: absent
pdfplumber: absent
pdfminer.six: absent
```

The Broker Reports Pipe metadata currently declares only `pydantic`. A new
layout dependency therefore needs an explicit bundled/stage runtime proof.

### `case_group_002` aggregate probe

The probe used only hash-verified approved private-registry PDFs. Files were
processed in memory. Output contained safe counts only.

| Measure | Result |
|---|---:|
| PDFs opened by live `pypdf 6.7.5` | 8/8 |
| Pages | 217 |
| Pages with extracted text | 215 |
| Documents with text on every page | 6/8 |
| Page extraction errors | 0 |
| Extracted replacement characters | 0 |
| Extracted text characters | 763,306 |
| Visitor text fragments with coordinates | 107,775 |

Local PyMuPDF control:

| Measure | Result |
|---|---:|
| PDFs opened | 8/8 |
| Pages / pages with words | 217 / 215 |
| Documents with words on every page | 6/8 |
| Page extraction errors | 0 |
| Words / text blocks | 105,704 / 9,841 |
| Replacement characters | 0 |
| Image occurrences | 46 |

Safety facts:

- raw text emitted: false;
- filenames/file ids/private paths emitted: false;
- ordinary upload used: false;
- ArtifactStore mutation: false;
- Knowledge/RAG/vector writes: false;
- OCR/VLM: false;
- model/Gate 2 extraction: false.

This is text-layer availability preflight, not deterministic completeness
proof. The two text-empty pages and all parser/font/order/coverage gates still
need classified outcomes.

## Parser options

| Candidate | Result |
|---|---|
| current stdlib heuristic | profiling compatibility only; cannot prove full source |
| `pypdf` | phase-1 baseline: already live, per-page text, layout mode and visitor diagnostics; no native word/table hierarchy and coordinates may be unreliable in complex PDFs |
| `pdfplumber` / `pdfminer.six` | recommended layout-rich backend: MIT, characters/words/bboxes, line/shape access and configurable table candidates; new pinned dependency and performance proof required |
| PyMuPDF | technically strong and fast with words/blocks/raw dictionaries/table finder; not default because AGPL/commercial licensing requires an explicit decision |

Primary references:

- [pypdf text extraction, visitors, memory and OCR limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html);
- [pdfplumber words and table finding](https://github.com/jsvine/pdfplumber/blob/stable/README.md?plain=1);
- [pdfminer.six layout analysis](https://pdfminersix.readthedocs.io/en/latest/topic/converting_pdf_to_text.html);
- [PyMuPDF text blocks/words/raw dictionaries](https://pymupdf.readthedocs.io/en/latest/textpage.html);
- [PyMuPDF licensing](https://pymupdf.io/).

## Recommended pipeline

```text
private PDF bytes
  -> source checksum and content-kind preflight
  -> capability-gated parser factory
  -> per-page parser projection
  -> page/layout normalizer and validator
  -> page/block/line/word/span/value refs
  -> page and payload checksums
  -> exact coverage reconciliation
  -> private_normalized_source_payload_v0
       + pdf_text_layer_projection_v0
  -> private_normalized_source_unit_v0
       + PDF unit metadata
  -> ArtifactStore resolver
  -> existing Gate 2 readiness/router/segmenter/validators/stitcher
```

`pypdf` supplies the first page-text slice and the structural control. A pinned
`pdfplumber`/`pdfminer.six` backend is introduced separately for layout-rich
word/character provenance and table candidates. The parser factory fails closed
when the requested capability is unavailable; it does not silently downgrade
layout/table extraction while preserving `complete`.

## Completeness decision

The design defines three independent statuses:

- `text_layer_projection_status`;
- `visible_content_coverage_status`;
- `semantic_reconstruction_status`.

The generic parser may be complete only for the declared text-layer projection
when every page, parser fragment, source value, checksum and coverage bucket
reconciles under a pinned engine/config. Mixed text/image PDFs may still be
complete for text-layer projection while visible content is
`partial_out_of_scope`. Reading order and table semantics stay
`not_claimed`/`candidate` unless separately proven.

Partial/blocked reasons cover encryption/corruption, page errors, budgets,
unknown fonts/CMaps, operator decode gaps, reconciliation mismatch, unavailable
layout backend, unverified coordinates, engine mismatch and image-only pages.

## Contracts proposed

New normative proposals:

- `docs/stage2/contracts/BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md`;
- `docs/stage2/contracts/BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md`.

The design keeps the existing ArtifactStore types:

- `private_normalized_source_payload_v0` contains nested
  `pdf_text_layer_projection_v0`;
- `private_normalized_source_unit_v0` contains PDF unit metadata.

Proposed unit types:

- `pdf_page_text_unit`;
- `pdf_section_text_unit`;
- `pdf_line_cluster_unit`;
- `pdf_table_candidate_unit`.

`pdf_summary_block_unit` is deferred because Gate 1 must not invent semantic
summary ownership.

Updated contract family:

- `BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md`;
- `BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md`;
- `BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`;
- `BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md`;
- `BROKER_REPORTS_GATE2_SOURCE_UNIT_ROUTING.v0.md`.

All updates are proposals and explicitly preserve the current
runtime-not-implemented status.

## Provenance and source values

The PDF chain is page-local:

```text
source checksum ref
  -> page ref
  -> raw parser fragment ref
  -> optional block/line/word ref
  -> character span ref
  -> source value ref
  -> one private payload path + value checksum
```

Page checksums bind parser identity/config and ordered fragment inventories.
The payload checksum binds ordered page checksums and projection policy. Raw
parser text and normalized values use separate checksums. A parser/config
change creates a new payload; legacy ArtifactStore records are not mutated.
Optional PDF object/xref refs are private diagnostics only and are not used as
the sole stable identity.

## Table strategy

Table-shaped text is not automatically a table. A
`pdf_table_candidate_unit` requires deterministic geometry, strategy/tolerance
refs, contributing word/line refs, bbox, confidence, row/cell refs and fallback
text refs. Low-confidence/conflicting geometry creates no table unit; the text
remains covered by page/line units.

Gate 2 may produce a validated text-backed fact or `unknown_source_row`, but it
cannot promote candidate geometry to source truth. Coverage ownership prevents
candidate and fallback representations from double-counting one source ref.

## Gate 2 use

The resolver must validate parent payload/unit completeness, page/source/value
refs, checksums, coverage and no-RAG/no-OCR guards before package creation. The
model receives one bounded page/section/line cluster/table candidate, never the
whole PDF.

Existing Gate 2 domain schemas, source-value validation, issue handling,
coverage, conflict rules and stitcher remain unchanged. A valid PDF unit may
support one limited vertical; it does not prove whole PDF or whole-case
readiness.

## Recommended implementation slices

1. `pypdf` page-text foundation, page/value refs, checksums and validators.
2. Pinned `pdfplumber`/`pdfminer.six` dependency and layout-rich projection.
3. Deterministic table candidates with fallback coverage.
4. Bounded Gate 2 integration using unchanged validators/stitcher.
5. Controlled safe-aggregate `case_group_002` proof.
6. Optional PyMuPDF evaluation only after licensing approval.

Each slice has synthetic acceptance gates before customer proof. The first
customer model call is forbidden until at least one complete PDF unit validates
mechanically.

## Risks and blockers

- PDF has no guaranteed semantic text/table layer;
- reading order can differ from visible intent;
- hidden/duplicate text and font mappings can distort projection;
- large content streams require preflight budgets;
- layout backend is not yet in the live Pipe dependency boundary;
- PyMuPDF has an unresolved license decision;
- current `case_group_002` evidence proves text availability, not complete
  payload/unit eligibility;
- the repository contains pre-existing unrelated changes, so this task does
  not claim a clean tree.

## Files delivered

- `docs/stage2/research/BROKER_REPORTS_PDF_TEXT_LAYER_NORMALIZATION_RESEARCH.md`;
- `docs/stage2/blueprints/BROKER_REPORTS_PDF_TEXT_LAYER_NORMALIZATION.blueprint.md`;
- `docs/stage2/contracts/BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md`;
- `docs/stage2/contracts/BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md`;
- five updated Gate 1/Gate 2 contract docs listed above;
- this report.

## Boundaries

No OpenWebUI core patch, parser implementation, ordinary upload, Knowledge/RAG,
vectorization, OCR/VLM, page rendering for extraction, tax, declaration,
consolidation, XLS/XLSX or free-form source-fact extraction was performed.

## Final statuses

```text
PDF_TEXT_LAYER_NORMALIZATION_RESEARCH_READY
PDF_TEXT_LAYER_PIPELINE_BLUEPRINT_READY
PDF_TEXT_LAYER_CONTRACTS_PROPOSED
PDF_TEXT_LAYER_NO_OCR_BOUNDARY_READY
PDF_TEXT_LAYER_GATE2_INPUT_PLAN_READY
READY_FOR_PDF_TEXT_LAYER_NORMALIZATION_IMPLEMENTATION_SLICE
```
