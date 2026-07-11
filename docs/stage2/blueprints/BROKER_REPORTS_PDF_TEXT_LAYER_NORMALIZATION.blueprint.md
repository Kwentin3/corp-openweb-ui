# Broker Reports PDF text-layer normalization blueprint

Date: 2026-07-11
Status: Slices 1-4 implemented locally; current bundle deployed with SHA parity,
but native/PDF live rerun was not performed because no active DCP was available

## 1. Problem and risk

Gate 1 currently recognizes some PDF text but cannot prove page ownership,
ordering, complete decoding, stable value refs or full declared-range coverage.
Promoting that preview would let partial text look complete and could send
untraceable financial values to Gate 2.

The target is a private, deterministic, resolver-gated text-layer projection.
It must cover the declared parser projection without claiming image text,
visible-document completeness or semantic table truth.

## 2. Architecture decision

- Keep `private_normalized_source_payload_v0` and
  `private_normalized_source_unit_v0` as persistence boundaries.
- Add `pdf_text_layer_projection_v0` as a format-specific private projection,
  not a new parallel ArtifactStore family.
- Use `pypdf` as the phase-1 page/text baseline because `6.7.5` is present in
  the live container.
- Add a pinned `pdfplumber` / `pdfminer.six` backend in a separate slice for
  word/character geometry and table candidates.
- Keep PyMuPDF disabled until licensing and runtime-dependency decisions are
  explicit.
- Preserve the current heuristic profiler behind compatibility behavior until
  the new path is stage-proven.

## 3. Ownership map

| Owner | Owns | Must not own |
|---|---|---|
| `PdfParserAdapter` | open/decrypt status, pages, parser-native fragments/resources/diagnostics | source-unit policy, facts, tax |
| `PdfTextLayerParserFactory` | capability request, pinned backend/config selection, fail-closed availability | silent backend downgrade |
| `PdfProjectionValidator` | page inventory, parser diagnostics, canonical text/ref/checksum reconciliation | semantic table interpretation |
| `PdfLayoutNormalizer` | canonical page/block/line/word projection and spans | domain facts or issue resolution |
| `PdfTableCandidateBuilder` | deterministic geometry candidates and fallback text refs | declaring a candidate to be source truth |
| `PdfSourceUnitBuilder` | bounded units, declared ranges, source-value refs, coverage | model routing or facts |
| existing ArtifactStore factory | private persistence, resolver scope, retention/purge | Knowledge/RAG/vector storage |
| existing Gate 2 readiness/router/segmenter | resolver validation, bounded packages, exact partition | PDF parsing or hidden ref repair |
| existing Gate 2 validators/stitcher | fact/schema/provenance/coverage validation | weakening gates for PDFs |

The first implementation should keep these as a small parser adapter, one
normalizer/validator module and one source-unit builder module. A separate table
candidate module is added only with the layout backend slice.

## 4. Target flow

```text
approved private PDF bytes
  -> source checksum + content-kind preflight
  -> PdfTextLayerParserFactory
  -> page-native parser projection
  -> PdfProjectionValidator
  -> canonical ordered page projection
  -> page/block/line/word/span/value refs
  -> page and payload checksum reconciliation
  -> private_normalized_source_payload_v0
       pdf_text_layer_projection_v0
  -> PdfSourceUnitBuilder
  -> private_normalized_source_unit_v0
       pdf_page_text_unit / pdf_section_text_unit /
       pdf_line_cluster_unit / pdf_table_candidate_unit
  -> ArtifactStore resolver
  -> Gate2InputReadinessFactory
  -> existing routing, segmentation, domain extraction and validation
```

Failure at any parser/provenance/coverage gate emits a typed partial/blocked
payload and no extraction-grade source unit.

## 5. Boundary contracts

### 5.1 Parser request

```json
{
  "document_ref": "brdoc_opaque",
  "source_checksum_ref": "srcsum_opaque",
  "requested_projection": "page_text|layout_words|table_candidates",
  "parser_policy_ref": "pdf_text_layer_parser_policy_v0",
  "budgets": {
    "max_document_bytes": 0,
    "max_page_content_stream_bytes": 0,
    "max_pages": 0,
    "max_runtime_ms": 0
  },
  "ocr_vlm_allowed": false,
  "rendering_allowed_for_extraction": false
}
```

The factory returns a backend only when its declared capability satisfies the
request. `layout_words` cannot silently become `page_text`.

### 5.2 Parser result

The adapter returns private parser-native data plus safe diagnostics:

- parser engine/version/config ref;
- encryption/corruption state;
- exact page count;
- per-page media/crop/rotation metadata;
- text fragments and matrices;
- resource/font/content-stream diagnostics and optional parser-native
  object/xref refs;
- optional characters/words/lines/shapes;
- extraction errors and budget decisions.

It does not mint Gate 1 source-value refs or decide completeness.

### 5.3 Canonical projection

The normalizer produces `pdf_text_layer_projection_v0` under the generic
payload. Canonicalization pins:

- page order by PDF page index;
- parser order and geometry order as separate fields;
- LF line endings;
- stable numeric coordinate precision under the parser policy;
- canonical JSON key/order policy;
- raw extracted fragment checksums and normalized value checksums separately;
- parser engine/version/config in every page/payload checksum.

Normalization never overwrites raw parser text. A source value points to a
private normalized value and carries raw fragment/span refs.

### 5.4 Completeness result

```json
{
  "parser_completeness_status": "complete|partial|blocked",
  "text_layer_projection_status": "complete|partial|blocked",
  "visible_content_coverage_status": "complete_text_only|partial_out_of_scope|unknown",
  "semantic_reconstruction_status": "not_claimed|candidate|validated_geometry",
  "reason_codes": [],
  "declared_pages_total": 0,
  "accounted_pages_total": 0,
  "all_declared_refs_accounted": false
}
```

Only `text_layer_projection_status=complete` may support a generic complete
payload. Image-bearing pages may still set
`visible_content_coverage_status=partial_out_of_scope`.

### 5.5 Source unit

The unit follows the existing generic contract and the PDF-specific extension.
It always includes:

- parent payload/parser/source/page checksums;
- unit type and contiguous declared page/block/line range;
- selected page/block/line/word/span/value refs;
- private source-value index paths with value checksums;
- selected/accounted coverage buckets;
- `declared_range_complete=true`;
- `source_slice_truncated=false`;
- `parent_source_slice_truncated=false`;
- `parent_remainder_status=not_applicable_parent_complete`.

No unit is minted from a partial parent payload.

## 6. Content-kind policy

| Kind | Rule |
|---|---|
| `text_layer_pdf` | text-layer projection may become complete |
| `mixed_pdf_with_text` | text-layer projection may become complete; visible content remains partial/out of scope |
| `raster_pdf_or_image_only` | no unit; `pdf_image_only_no_text_layer` |
| encrypted/corrupt | blocked unless an explicitly approved key/path exists |
| `parser_partial_pdf` | partial payload, no unit |
| `pdf_text_layer_complete_candidate` | pre-validation state only; not persisted as final complete without all gates |

An empty page is not automatically an error. It must be accounted as
`no_text_operators`, `image_only_page`, `layout_only_page` or typed partial.

## 7. Page and value provenance

For every page:

1. mint `page_ref` from source checksum ref and one-based page ordinal;
2. store parser fragments in deterministic parser order;
3. build canonical page text and character offsets;
4. mint fragment/block/line/word refs from page ref, ordinal, geometry policy and
   raw checksum;
5. mint character-span refs from page ref, offsets and value checksum;
6. mint source-value refs from source/page/span refs and normalized checksum;
7. index each source value to exactly one private payload path;
8. reproduce page checksum from ordered inventories;
9. reproduce payload checksum from parser identity/config and ordered page
   checksums.

Coordinates are supporting provenance, not the only identity. A coordinate
change under a new parser/config creates a new projection.
Parser-native object/xref numbers are private audit metadata and are never the
sole ref identity because PDF rewrites may renumber objects.

## 8. Reading order and segmentation

Store at least two orderings when available:

- `parser_stream_order`: exact parser callback/object order;
- `geometry_reading_order`: deterministic policy result using page coordinates.

Neither is called semantic truth. The source-unit policy prefers:

1. deterministic table candidate smaller than the page;
2. deterministic section smaller than the page;
3. page text unit;
4. contiguous line clusters for oversized pages.

Every parent selected ref appears exactly once in the derived-unit partition.
Repeated headers/footers may be put in a deterministic layout bucket, but their
refs remain accounted and auditable.

## 9. Table candidate boundary

`PdfTableCandidateBuilder` is introduced only with the layout backend. It may
use page lines/rectangles and aligned words under a pinned tolerance policy.

A candidate is emitted only when:

- page bbox and contributing geometry are valid;
- row/cell areas do not overlap illegally;
- contributing word refs resolve exactly once;
- candidate and surrounding text coverage do not double-count refs;
- fallback ordered text refs exist;
- confidence/reason codes are deterministic.

Low-confidence, conflicting or borderless ambiguity produces no table unit.
Those refs remain in a line-cluster/page unit. Gate 2 cannot convert candidate
geometry into authoritative table semantics without source-fact validation.

## 10. Persistence and privacy

- Generic payload/unit types remain `private_case` in
  `project_artifact_payload`.
- Safe diagnostics and coverage summaries may be `safe_internal` in
  `project_artifact_store`.
- No raw text, words, values, filenames, OpenWebUI ids or paths enter chat or
  reports.
- No PDF source or projection enters Knowledge/RAG/vector storage.
- Retention, expiry and purge cascade follow the parent Gate 1 run.
- Legacy artifacts are immutable; a new parser version creates new refs.

## 11. Implementation slices

### Slice 1: pypdf page-text foundation

Scope:

- parser factory and `pypdf` adapter using the live dependency;
- exact page inventory, per-page raw/normalized text and diagnostics;
- source/page/payload checksums;
- page/text/span/value refs and coverage;
- `pdf_page_text_unit` and bounded `pdf_line_cluster_unit`;
- synthetic fixtures and fail-closed validators;
- no table candidate implementation.

Acceptance:

- all synthetic refs/checksums reproduce on two identical runs;
- blank/image-only page accounting is explicit;
- unknown-font, extraction error, cap/budget and encrypted fixtures cannot mint
  complete units;
- no OCR/VLM/rendering/Knowledge/vector path exists;
- bundled/stage runtime proves pinned parser availability.

### Slice 2: layout-rich dependency

Scope:

- declare and pin `pdfplumber` / `pdfminer.six` in the Pipe/runtime boundary;
- add characters/words/lines/bboxes and duplicate-character diagnostics;
- reconcile layout text to the phase-1 page projection;
- create section and geometry-order policies.

Acceptance:

- closed-world import works in the bundled live runtime;
- synthetic rotated/multi-column/duplicate text fixtures pass or fail with typed
  reasons;
- memory/runtime budgets are measured;
- no silent `pypdf` downgrade retains layout-complete status.

### Slice 3: table candidates

Scope:

- deterministic geometry candidate builder;
- ruled and aligned-text strategies with pinned tolerances;
- candidate/fallback coverage and table unit contract;
- no economic/domain interpretation.

Acceptance:

- ruled synthetic table yields reproducible row/cell/word refs;
- ambiguous unruled layout falls back to line clusters;
- no source ref is dropped or double-counted;
- table status remains candidate.

### Slice 4: Gate 2 bounded integration

Scope:

- readiness resolver accepts complete PDF units;
- existing router/segmenter preserves PDF refs and candidate metadata;
- one synthetic domain extractor package and existing validators/stitcher;
- no validator weakening.

Acceptance:

- whole PDF is never sent to the model;
- one bounded unit produces validated fact or `unknown_source_row` with complete
  unit coverage;
- partial parent payloads cannot enter Gate 2;
- no tax/Gate 3 claim.

### Slice 5: controlled `case_group_002` proof

Scope:

- approved private registry only;
- safe aggregate payload/unit/reason counts;
- at most one smallest validated PDF vertical after synthetic proof;
- before/after ArtifactStore/Knowledge/document/vector snapshots.

Acceptance:

- all eight PDFs have explicit complete/partial/blocked reasoned outcomes;
- at least one complete PDF unit validates before any model call;
- raw content is absent from report/chat;
- Knowledge/document/vector deltas are zero;
- case status is not promoted beyond proven coverage.

### Optional Slice 6: PyMuPDF evaluation

Only after legal/commercial-license approval. Compare capability, performance
and deterministic output against the same fixtures. Do not mix the engine into
production before parser-version-specific contract proof.

## 12. Test and proof matrix

| Risk | Required proof |
|---|---|
| false page completeness | page count/inventory/accounting mismatch test |
| text decode loss | unknown font/CMap/operator typed failure fixtures |
| hidden truncation | content budget/cap tests; no complete payload on overflow |
| unstable refs | identical rerun checksum/ref equality |
| parser drift | version/config change creates new payload refs/checksums |
| wrong reading order | parser and geometry order stored separately |
| table overclaim | ambiguous table fallback test |
| duplicate refs | exact selected/accounted partition validator |
| source-value drift | private path and checksum reproduction test |
| mixed/image content overclaim | independent visible-content status test |
| runtime ghost dependency | bundled/stage import and version proof |
| private leakage | safe-report whitelist and marker scan |
| RAG contamination | zero Knowledge/document/vector deltas |

## 13. Operational gates

Before production enablement:

- parser engine and transitive dependencies are pinned;
- memory/time/content-stream budgets are configured;
- stage container import/version equals the bundled requirement;
- synthetic suite passes under the same image;
- safe runtime metrics expose only counts, timings and reason codes;
- rollback disables the new feature flag and restores heuristic profiling;
- no legacy ArtifactStore record is mutated.

## 14. Non-goals and deferred work

- OCR/VLM, image transcription or scanned-PDF support;
- page rendering for extraction;
- semantic document understanding in Gate 1;
- guaranteed visual reading order;
- guaranteed semantic table reconstruction;
- free-form LLM facts;
- tax, declaration, consolidation, XLS/XLSX or Gate 3;
- OpenWebUI core patch;
- full-package `case_group_002` readiness from one successful PDF unit;
- semantic `pdf_summary_block_unit` in v0.

## 15. Readiness

The earlier `runtime not implemented` statement is obsolete. The repository
implements the pinned page-text and layout-rich paths, bounded line/table
candidate units, format-neutral normalized table projections and Gate 2 input
routing. Local contract, provenance, quality and bundle-parity checks pass.

The current bundle is deployed with repo/live SHA parity, but the controlled
case had no active source records or DCP, so the native/PDF vertical was not
rerun. The GPT canary stopped on provider quota before accepting facts. This is
not live semantic acceptance of the current PDF path, all layouts or a customer
corpus. OCR/VLM, scans and image-only pages remain unsupported here.

```text
PDF_TEXT_LAYER_NORMALIZATION_RESEARCH_READY
PDF_TEXT_LAYER_PIPELINE_BLUEPRINT_READY
PDF_TEXT_LAYER_CONTRACTS_IMPLEMENTED_LOCAL
PDF_TEXT_LAYER_NO_OCR_BOUNDARY_READY
PDF_TEXT_LAYER_GATE2_INPUT_IMPLEMENTED_LOCAL
PDF_NORMALIZED_TABLE_PROJECTION_IMPLEMENTED_LOCAL
PDF_CURRENT_BUNDLE_DEPLOYED_SEMANTIC_ACCEPTANCE_NOT_PROVEN
```
