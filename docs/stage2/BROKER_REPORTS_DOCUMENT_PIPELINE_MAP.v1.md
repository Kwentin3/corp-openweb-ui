# Broker Reports Document Pipeline Map v1

Status: current code and released-route audit

Effective date: 2026-07-31

## Plain-language result

The product keeps the original PDF outside the normalization package and can
store a rich private PDF payload containing page text and layout inventories.
It does not create one downstream document object in which headings,
paragraphs, tables, notes and page breaks remain in one source order.

For a readable PDF, the normalizer creates page/layout inventories and then
partitions each page into table-candidate units and line-cluster units. The
partition is complete for the parser-selected words and lines, but it is not a
document reading-order model: table units are emitted before the remaining
line clusters on the same page. Gate 2 consumes those units, or a standalone
semantic table projection, in bounded segments. The model does not receive the
whole PDF, the parent PDF payload or the document-memory graph.

```text
WHOLE_DOCUMENT_ARTIFACT = FRAGMENTED
FIRST_IRREVERSIBLE_CONTEXT_LOSS =
  FullSourceArtifactBuilder._build_pdf_document
  -> PdfLayoutUnitBuilder._build_page_units
```

The loss is irreversible for downstream consumers without resolving the
parent payload or rereading the PDF: the unit list no longer preserves one
interleaved order for table regions and surrounding text, and it never mints
explicit section, title, note, footnote or cross-page table relations.

## Current released contour

Current operational authority remains release `broker-reports-db009421b68c`
at repository revision `db009421b68c8b09df728239d23c217e5482d3a1`.
The released valves enable PDF table intake, Gemini semantic transcription,
semantic downstream materialization and standalone semantic projections.
OpenAI fallback and all visual shadow routes are disabled. Gate 2 retains the
maintained full-source units alongside standalone semantic projections.

This audit did not query a provider, mutate live state or alter a valve.

## Actual product call chain

| # | Stage and owner | Called by | Input | Output and persistence | Context effect | Product/fallback status |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `openwebui_actions/broker_reports_gate1_pipe.py::Pipe.pipe` | OpenWebUI Pipe runtime | visible upload refs and request metadata | bounded workload request | Collects refs; chat text is excluded from document packages | Product entrypoint |
| 2 | `Pipe._hydrate_private_intake_file_refs` and `Pipe._to_file_input` | `Pipe._run_workload` | OpenWebUI/private-intake file ref | `FileInput` with lazy byte provider | Original bytes remain in OpenWebUI upload/private-intake storage; filename remains private | Product; no parser fallback |
| 3 | `Gate1Normalizer.normalize` | `Pipe._run_workload` | `FileInput[]` | Gate 1 package and bounded graph | Detects format, profiles, normalizes and builds Gate 1 control artifacts | Product factory route |
| 4 | `ContainerDetector` plus `profile_pdf` | `Gate1Normalizer.normalize` | source bytes | container/profile and legacy bounded preview | Adds format/page diagnostics; preview is not coverage authority | Product; preview later forms a legacy fallback |
| 5 | `FullSourceArtifactFactory.create` / `FullSourceArtifactBuilder._build_pdf_document` | `Gate1Normalizer.normalize` | complete PDF bytes | one private source payload plus private units | Adds page text, fragments, words, lines, blocks, bboxes, page order and candidate inventories | Product; fails closed on encrypted/over-budget PDFs |
| 6 | `PdfTextLayerParserFactory.create` | full-source builder | complete PDF bytes | per-page text inventory | Preserves page number and parser text order, not semantic headings/sections | Product parser |
| 7 | `PdfLayoutParserFactory.create` and `PdfLayoutUnitBuilder.build` | full-source builder | pages and pdfplumber layout | layout inventory, table candidates, line/table/visual units | Adds geometry and ownership; `_build_page_units` partitions and reorders table versus non-table units | Product; layout-to-page-text fallback exists |
| 8 | `NormalizedTableProjectionFactory.create` | `Gate1Normalizer.normalize` | eligible native table unit | normalized table projection or explicit rejection | Adds deterministic rows/cells/header candidates where validation permits; never claims semantic PDF truth | Product maintained route |
| 9 | `PdfTableIntakeRuntimeFactory.create` | `Pipe._maybe_run_pdf_table_intake` | original PDF bytes matched by SHA-256 | private page proposals, crops and detection attempts | Finds page-local crop candidates; does not add document/section/continuation relations | Released active branch |
| 10 | `PdfDualVlmRuntimeFactory.create` | `Pipe._maybe_run_pdf_dual_vlm` | one immutable crop | validated private `{description, rows}` proposal and evidence | Model sees only a crop; nearby document material is deliberately excluded | Released active; Gemini master; OpenAI fallback disabled |
| 11 | `SemanticVisualTableMigrationFactory.create` -> `SemanticVisualTableMaterializationFactory.create` | `Pipe._maybe_migrate_pdf_semantic_tables` | accepted VLM decision | semantic envelope, logical table and Gate 2 projection | Adds deterministic IDs/grid/provenance; header roles, section links and continuation remain absent | Released active |
| 12 | `persist_gate1_result` and `ArtifactStoreFactory.create` | `Pipe._run_workload` | Gate 1 package and private semantic artifacts | resolver-gated SQLite metadata and private payload files | Persists payloads, units, projections, envelopes, manifest and handoff independently | Product system of record |
| 13 | `Gate1DocumentMemoryFactory.create` and `build_manifest` | `apply_domain_ingestion_artifacts` inside normalization | package artifact refs and safe summaries | safe document-memory manifest and domain context packet | Creates a graph/index only; copies no private content and cannot reconstruct the document by itself | Product canonical root, not a whole-document artifact |
| 14 | `Gate2InputReadinessFactory.create().audit_and_build` | `Gate2DomainSourceFactRuntimeFactory` | DCP ref and resolver context | one package per selected source unit/table projection | Selects standalone semantic tables plus maintained units; may fall back to legacy previews | Product; automatic legacy fallback exists |
| 15 | `Gate2SourceUnitRouterFactory` and `Gate2SourceUnitSegmenterFactory` | Gate 2 domain runtime | one selected package | bounded derived unit | Default runtime selects at most one base unit and one derived segment per invocation | Product; deferred segments are recorded |
| 16 | `Gate2DomainPackageBuilderFactory` and `Gate2StructuredModelClient.extract` | `Gate2DomainSourceFactRuntimeService` | model source projection, issues, prompt and schema | strict structured request/response artifacts | Model sees bounded rows or text, not the parent PDF/payload, complete unit set or document-memory graph | Current product model boundary |
| 17 | validators, stitcher, ArtifactStore and AnswerContext/Gate 3 selectors | Gate 2 runtime | bounded model output and allowed refs | canonical private facts and declared downstream refs | Fail-closed validation; cannot recreate missing document relationships | Product downstream |

## Artifact authorities

| Authority | Owner | Contains | Location/lifetime | Whole-document use |
| --- | --- | --- | --- | --- |
| Original file bytes | OpenWebUI file storage or private-intake storage | exact PDF bytes and private filename metadata | outside the normalization package; retained by its own policy | Exact source, but requires rereading PDF |
| `private_normalized_source_payload_v0` | `FullSourceArtifactFactory` | page text plus PDF layout inventories and extraction-unit refs | private ArtifactStore payload; resolver-gated | Richest derived artifact, but not one ordered semantic document |
| `private_normalized_source_unit_v0` | `PdfLayoutUnitBuilder` / full-source builder | bounded page text, line cluster, table candidate or visual page | private ArtifactStore payload through Gate 2 | Fragment, not whole document |
| `broker_reports_gate1_document_memory_manifest_v1` | `Gate1DocumentMemoryFactory` | safe identities, status, scope and artifact refs | safe ArtifactStore record through DCP | Index only; private values deliberately absent |
| semantic envelope and normalized table projection | semantic materializer | one crop-derived logical table and lineage | private ArtifactStore payload; optionally Gate 2 selected | Table-only, page-local object |

There are five relevant authorities, but none is
`PRESENT_AND_USABLE` as a complete downstream document. The original PDF is
complete source evidence; the payload is rich but fragmented by representation;
the manifest is only a safe graph; units and table projections are bounded
parts.

## Why the first loss point is proven

`FullSourceArtifactBuilder._build_pdf_document` retains a page inventory but
chooses extraction units as follows:

```text
layout units when layout is complete
otherwise provisional page-text units
plus visual-page units
```

`PdfLayoutUnitBuilder._build_page_units` returns
`[table_units, line_units]` for a page. This ordering is not the original block
order. The builder also assigns no section, heading level, table title,
preceding/following paragraph, note/footnote or cross-page continuation edge.
Gate 2 resolves units, not the parent payload as model context.

The real-PDF read-only run found 22 pages containing both table and line units;
16 of those pages had non-monotonic unit `line_start` order. This is structural
proof, not a semantic guess. Recovery is possible only by resolving the richer
parent layout payload and reconstructing relationships or by rereading the
PDF. Neither occurs in the current model route.

## Fallback routes

| ID | Trigger | Caller -> target | Product reachable now | User-visible | Logged | Context consequence | Can contribute to financial result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FB-PDF-LAYOUT-TEXT` | layout projection is not complete while text-layer status remains complete | full-source builder -> provisional page-text units | Yes | No specific chat warning | layout status/reason codes | loses geometry/table partition and explicit visual relations | Yes |
| `FB-PDF-VISUAL-PAGE` | no/unsafe text on a page or visible-content reconciliation requires rendering | full-source builder -> `PdfVisualMemoryFactory` | Yes | No specific chat warning | visual fallback status/reasons | preserves pixels but supplies no OCR/semantic text; visual units are Gate 2 restricted | No, not from the visual unit itself |
| `FB-SEMANTIC-MAINTAINED` | intake/VLM/materialization yields no accepted standalone semantic projection | Gate 1 pipe continues -> maintained full-source units | Yes | Only aggregate stage status | safe summaries and zero projection count | downstream proceeds on fragments without crop-derived logical table | Yes |
| `FB-GATE2-LEGACY-PREVIEW` | an eligible document has no selected full-source unit | Gate 2 readiness -> legacy normalized slice | Yes | No specific chat warning | `legacy_fallback_documents_total` and input mode | bounded preview replaces full-source unit and blocks expansion | Yes |
| `FB-LEGACY-PROVENANCE-UPGRADE` | selected legacy slice lacks current provenance schema | Gate 2 readiness -> `NormalizedSliceProvenanceFactory.enrich_slice` | Yes | No | `legacy_provenance_upgrade_total` | does not restore missing content; makes the legacy fragment acceptable | Yes |
| `FB-OPENAI-VLM` | Gemini terminal failure and explicit invocation policy | PDF dual VLM runtime -> OpenAI | No; released valve is `disabled` | N/A | explicit provider role and counter | same crop-only context | Potentially, if separately activated |
| `FB-PASSPORT-SAFE-CONTINUE` | managed passport prompt/model is unavailable | Gate 1 pipe -> base Gate 1 result | No; passport is released off | Status event if enabled | stage output | metadata enrichment absent; base units remain | Potentially via base route |
| `FB-SHADOW-SAFE` | non-authoritative repair shadow fails | Gate 1 pipe -> empty safe shadow summary | No; shadows are released off | No | safe shadow summary | no production selection change | No |
| `FB-PDF-COMPAT-PREVIEW` | direct compatibility call to legacy PDF extractor | full-source `_extract_pdf` -> profiler preview | No production call path | No | bounded preview reason | preview only; cannot mint source units | No |

Counting rules:

- automatic legacy fallbacks count current product-reachable routes that can
  automatically consume a maintained pre-semantic or legacy representation;
- silent degradation counts current product-reachable routes that can reduce
  model-visible context without a specific user-facing warning;
- dormant valve-controlled and non-production compatibility code is inventoried
  but excluded from current totals.

```text
AUTOMATIC_LEGACY_FALLBACKS_TOTAL = 3
PRODUCT_REACHABLE_LEGACY_FALLBACKS_TOTAL = 3
SILENT_CONTEXT_DEGRADATION_PATHS_TOTAL = 4
```

The nearest follow-up after DOC0 should isolate these fallbacks behind an
explicit document-quality decision before any new document contract is made
product-reachable. This is a recommendation only; DOC0 changes no route.

## Other input formats

| Format | Current entry/parser | Whole-source behavior | Same downstream | Reusable boundary |
| --- | --- | --- | --- | --- |
| HTML | `profile_txt(...html_text)` then `FullSourceArtifactBuilder._extract_html` | emits ordered text/table blocks using `content_block_ordinal`; embedded data media is bounded; DOM semantics and external media are incomplete | Yes, through full-source units and Gate 2 | decoder, ordered-block extractor and provenance can be adapted |
| CSV | `profile_csv` then `CsvSupportedProfileFactory.parse` / `_extract_csv` | one logical table with all accepted rows/cells under explicit budgets | Yes | parser, delimiter/encoding evidence, row/cell provenance |
| XLSX | `profile_xlsx` then `_extract_xlsx` | one unit per sheet; cell values/coordinates preserved within limits; formulas make status partial and workbook semantics are incomplete | Same persistence/readiness mechanics, but XLSX is outside the accepted document-memory pilot profile | ZIP/XML reader and sheet-coordinate extraction need a wrapper |
| XLS | container detector only | explicitly unsupported | No source-ready route | none beyond format detection |

There is no single common semantic document contract across these formats.
They share orchestration, provenance, persistence and Gate 2 packaging, not a
whole-document representation.

## Repeatability and source binding

Every material artifact is bound to stable refs/checksums and can be replayed
from retained private bytes under the relevant retention and access policy.
Deterministic validators can reproduce projections and integrity checks. A
complete semantic document cannot be replayed because the current pipeline
never creates that artifact; replay reproduces the same fragments.

## Scope stop

This map does not design a replacement document contract, parser, renderer or
cutover. It records the current facts needed by a later DOC1 decision.
