# OpenWebUI Broker Reports PDF text-layer normalization Slice 1 report

Date: 2026-07-10
Repository scope: `corp-openweb ui`
Delivery: pypdf page-text runtime, private artifacts, validators and no-model readiness

## Outcome

PDF text-layer normalization Slice 1 is implemented and proven for
machine-readable page text. The runtime now transforms approved private PDF
bytes into:

```text
pypdf page-text projection
  -> ordered page inventory
  -> parser fragments and line/text segments
  -> character spans and source-value refs
  -> page/payload/unit checksums
  -> exact page/text coverage
  -> private_normalized_source_payload_v0
       + pdf_text_layer_projection_v0
  -> private_normalized_source_unit_v0
       + pdf_page_text_unit
  -> ArtifactStore resolver
  -> Gate 2 input-readiness package without a model call
```

This does not establish complete visible-document coverage, OCR/scanned-PDF
support, semantic reading order, table correctness, tax/declaration readiness
or Gate 2 source-fact extraction.

## Implemented runtime

### Parser factory and adapter

New module:
`services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py`.

It provides:

- `PdfTextLayerParserFactory` as the only production parser entrypoint;
- `PypdfParserAdapter` behind the factory;
- `PdfParserCapabilityRequest`;
- exact runtime pin `pypdf==6.7.5`;
- fail-closed module/version checks;
- `page_text` as the only Slice 1 capability;
- typed rejection of `layout`/`table_candidates` requests;
- document/page/content-stream/text budgets;
- encryption, corruption, page parse, font/decode and image-only diagnostics;
- no OCR/VLM and no page rendering path.

The official pypdf extraction contract exposes page text and visitor fragments
and recommends checking content-stream size before extraction:
[pypdf text extraction](https://pypdf.readthedocs.io/en/6.7.0/user/extract-text.html).

Anti-drift anchors:

```text
PdfTextLayerParserFactory.create is the only production PDF text-layer parser entrypoint
Full-source builders, profilers, Gate 2 callers and smoke scripts must not instantiate PypdfParserAdapter directly
```

Production route:

```text
Gate1 Pipe
  -> Gate1Normalizer
  -> FullSourceArtifactFactory.create()
  -> PdfTextLayerParserFactory.create(page_text)
  -> PypdfParserAdapter
```

The controlled proof script uses the same `Gate1Normalizer` and factory path.

### Closed-world dependency

Gate 1 Pipe metadata now declares:

```text
requirements: pydantic,pypdf==6.7.5
```

The bundle builder includes `pdf_text_layer` before `full_source` and renders
the pinned requirement into the Gate 1 bundle. Gate 2 bundles keep only their
existing `pydantic` requirement because they validate persisted PDF units but
do not invoke the parser adapter.

Read-only final bundle execution inside the deployed OpenWebUI container proved:

- runtime pypdf version: `6.7.5`;
- pypdf resolved from the runtime package environment;
- final bundle contains `pdf_text_layer`;
- final bundle declares the exact pin;
- both anti-drift anchors are present;
- synthetic bundled PDF payload status: `complete`;
- payload validation: `passed`;
- one `pdf_page_text_unit` minted;
- OCR/VLM/rendering/model/Knowledge/vector use: false.

No workspace-only import or source-path fallback was introduced.

## PDF payload

`FullSourceArtifactFactory` now uses a dedicated PDF build branch. The legacy
regex profiler remains unchanged as a compatibility preview and is not coverage
authority.

The private payload keeps generic schema
`private_normalized_source_payload_v0` and nests
`pdf_text_layer_projection_v0` with:

- parser engine/version/config and policy refs;
- source/document/profile refs;
- declared ordered page range;
- page refs and page inventory;
- parser text fragments and raw fragment checksums;
- page-local text segment and character-span refs;
- source-value refs and private payload index;
- page checksum refs and parent payload checksum;
- parser diagnostics and typed reasons;
- page/text coverage;
- independent completeness statuses;
- explicit no-OCR/no-rendering flags.

Private raw text exists only in resolver-gated payloads/units. Safe metadata and
reports contain counts, statuses and reason codes only.

## Refs and checksums

### Page refs

`page_ref` is deterministically derived from the opaque source checksum ref and
one-based page ordinal. Identical source/run scope produces identical page refs.

### Text fragments and spans

Parser fragments receive stable refs from page ref, parser ordinal and raw text
checksum. The existing `NormalizedSliceProvenanceFactory` remains the authority
for line/text segment, section, character-span and source-value refs.

### Source values

Every page-unit `source_value_ref` resolves to one page-local text span and its
value checksum. The parent PDF payload rebases the same ref to:

```text
pdf_page_text_span(page_number, character_start, character_end)
```

Both unit and parent payload validators reproduce the private value and
checksum mechanically.

### Checksums

- raw fragment checksum binds parser-emitted text;
- page checksum binds parser ref, page identity/status, text, fragments,
  segment/span/value refs and page diagnostics;
- payload checksum binds source/parser/config/policy, completeness, ordered page
  checksums and coverage ref;
- unit checksum binds unit ref, parent payload checksum, slice checksum and
  coverage ref.

Parser/config changes create new projections. Legacy ArtifactStore records are
not mutated.

## Completeness

The runtime computes independently:

- `text_layer_projection_status`;
- `visible_content_coverage_status`;
- `semantic_reconstruction_status`.

`complete` means only complete for the declared pypdf page-text projection.

Rules proven in Slice 1:

- all declared pages must be ordered and accounted;
- parser/page errors, unresolved material font mapping, decode mismatch,
  replacement characters or budget overflow keep the payload partial/blocked;
- no hidden cap or truncated complete projection is permitted;
- a true blank page is explicitly accounted and may remain complete;
- an image-only page produces `pdf_image_only_no_text_layer` and makes the
  parent partial;
- a mixed text/image page may have complete text-layer status while visible
  content remains `partial_out_of_scope`;
- table/semantic reconstruction is always `not_claimed` in Slice 1;
- partial/blocked parent payloads mint no extraction-grade units.

## PDF source units

For each text-bearing page of a complete parent payload, Gate 1 mints one
`private_normalized_source_unit_v0` with
`pdf_unit_type=pdf_page_text_unit`.

Each unit includes:

- parent payload, parser, source, payload and unit checksum refs;
- declared/page/text/section/span/value refs;
- source-value index and mechanically reproducible values;
- exact selected/accounted unit coverage;
- `declared_range_complete=true`;
- `source_slice_truncated=false`;
- `parent_source_slice_truncated=false`;
- `parent_remainder_status=not_applicable_parent_complete`;
- `ocr_vlm_used=false`;
- `page_rendering_used_for_extraction=false`;
- private visibility and no Knowledge/vector flags.

`pdf_line_cluster_unit` was not needed: no complete synthetic or approved page
exceeded the configured page-text budget. Budget overflow fails partial rather
than truncating. Table candidate and semantic summary units remain deferred.

## ArtifactStore and Gate 2 readiness

PDF payloads and units persist as:

| Artifact | Visibility | Backend | Access |
|---|---|---|---|
| `private_normalized_source_payload_v0` | `private_case` | `project_artifact_payload` | resolver required |
| `private_normalized_source_unit_v0` | `private_case` | `project_artifact_payload` | resolver required |

Retention, expiry and purge follow the owning Gate 1 run. Knowledge storage is
forbidden.

`Gate2InputReadinessFactory` now resolves the parent PDF payload for every PDF
unit and validates:

- complete parent projection;
- parent/unit ref and checksum binding;
- page/text/span/value provenance;
- source-value reproduction;
- exact coverage;
- no truncation/remainder;
- no OCR/VLM/rendering;
- no Knowledge/RAG/vector path.

The produced package carries PDF unit/status fields and is no-model only. No
source fact was extracted or persisted.

## Synthetic proof

Synthetic text-layer PDFs were generated with the pinned pypdf runtime. Tests
assert observable payload/unit/readiness results and do not mock parser,
normalizer, ArtifactStore or Gate 2 readiness logic.

Passed scenarios:

- deterministic two-page text + blank PDF;
- stable page/segment/span/value refs across repeated runs;
- page/payload/unit checksum reproduction;
- source-value path/checksum reproduction;
- complete page unit minting;
- explicit blank page accounting;
- content-stream budget overflow -> partial, no unit;
- image-only page -> partial, no unit;
- encrypted PDF -> blocked, no unit;
- corrupt PDF -> blocked, no unit;
- pinned-version mismatch -> factory rejection;
- table capability request -> typed rejection, no downgrade;
- private ArtifactStore persistence;
- no-model Gate 2 input-readiness package;
- ArtifactStore unchanged during dry-run;
- Knowledge records: 0;
- OCR/VLM/rendering/vector/model calls: false.

Focused PDF/full-source tests: `7/7` passed.
Final PDF/bundle tests after bundle regeneration: `5/5` passed.

## Full regression suite

Shell/runtime context:

- PowerShell;
- isolated temporary Python venv;
- `pypdf==6.7.5`;
- existing test dependencies `pydantic`, `requests`, `tzdata`;
- explicit `PYTHONPATH=services/broker-reports-gate1-proof`.

Final result:

```text
Ran 126 tests in 18.978s
OK
```

One preliminary test assertion expected a trailing newline on the last parser
segment, while pypdf correctly preserved the final line without it. Only the
incorrect expectation was corrected. A separate preliminary full-suite run
aborted one unrelated timezone test because the isolated venv lacked `tzdata`;
adding the existing test-runtime dependency produced the final 126/126 result.

Test isolation uses per-test temporary directories and ephemeral SQLite/payload
roots. The irreversible boundary for persistence tests is ArtifactStore record
creation; assertions verify stored visibility/backend/access and the subsequent
read-only readiness result.

## Approved `case_group_002` proof

The controlled proof used the approved hash-verified private registry. It used
synthetic aliases internally and emitted aggregates only. There was no ordinary
upload, raw text/name/id/path output, external persistence, OCR/VLM, rendering,
Knowledge/RAG/vector write or model call.

Results:

| Measure | Result |
|---|---:|
| PDFs inspected | 8 |
| pages total | 217 |
| pages with text | 215 |
| pages without text | 2 |
| complete payloads | 6 |
| partial payloads | 2 |
| blocked payloads | 0 |
| complete page units minted | 193 |
| source-value refs in complete units | 18,605 |
| payload validations passed | 8/8 |
| unit validations passed | 193/193 |
| persisted PDF payload records | 8 |
| persisted PDF unit records | 193 |
| Knowledge backend records | 0 |

Reason codes:

```text
pdf_image_only_no_text_layer: 2
```

The two partial documents contain one image-only/no-text page each. Their other
text-bearing pages are retained in the private partial payload, but no
extraction-grade child units are minted because the parent document projection
is not complete.

At least one approved PDF has complete page-text units. In fact, six documents
do. Therefore `CASE_GROUP_002_PDF_COMPLETE_UNIT_AVAILABLE` is proven.

### No-model readiness

One complete approved PDF was re-intaken through the canonical path and passed
Gate 2 input readiness:

- source input mode: `full_source_unit`;
- unit type: `pdf_page_text_unit`;
- packages built: 33 page units;
- validator status: passed;
- ArtifactStore unchanged during readiness;
- Knowledge records: 0;
- model call performed: false.

This proves readiness package construction, not source-fact extraction.

## Safety guards

```text
ordinary_upload_used=false
knowledge_rag_used=false
vectorization_performed=false
ocr_vlm_used=false
page_rendering_used_for_extraction=false
model_calls=false
tax_calculation=false
declaration_generation=false
xls_xlsx_generation=false
```

No raw filenames, OpenWebUI ids, private paths, PDF text, account values,
personal data, secrets or environment values are present in this report.

## Remaining work and blockers

- layout-rich character/word/block geometry is not implemented;
- geometry reading order is not claimed;
- table candidates and semantic table reconstruction are not implemented;
- PyMuPDF remains outside runtime and behind its licensing decision;
- the two partial approved PDFs require OCR/manual review for their image-only
  pages; OCR is outside this pipeline;
- Gate 2 domain router/model source-fact extraction from PDF units was not run;
- no Gate 3, tax, consolidation, declaration or XLS/XLSX readiness is claimed.

The next safe slice is either the optional no-model routing/segmentation proof
on one selected page unit or the separately planned layout-rich dependency
slice. Model extraction should remain a distinct explicit request.

## Final statuses

```text
PDF_TEXT_LAYER_PYPDF_RUNTIME_READY
PDF_TEXT_LAYER_PAYLOAD_RUNTIME_IMPLEMENTED
PDF_TEXT_LAYER_SOURCE_UNITS_RUNTIME_IMPLEMENTED
PDF_TEXT_LAYER_SOURCE_VALUE_REFS_READY
PDF_TEXT_LAYER_COVERAGE_VALIDATOR_READY
PDF_TEXT_LAYER_SYNTHETIC_PASSED
CASE_GROUP_002_PDF_TEXT_LAYER_PREFLIGHT_READY
CASE_GROUP_002_PDF_COMPLETE_UNIT_AVAILABLE
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
PDF_GATE2_INPUT_READINESS_DRY_RUN_PASSED
READY_FOR_PDF_GATE2_INPUT_READINESS_DRY_RUN
```
