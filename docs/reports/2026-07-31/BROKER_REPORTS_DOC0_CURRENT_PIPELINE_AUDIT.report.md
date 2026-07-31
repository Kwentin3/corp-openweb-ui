# Broker Reports DOC0 Current Pipeline Audit

Date: 2026-07-31

Status: completed research audit; delivery evidence is recorded separately

## 1. What happens to a PDF now

In simple terms, the system keeps the original PDF privately, reads page text
and layout, finds page-local table regions, and cuts the document into bounded
pieces. The released visual branch sends one table crop to Gemini and receives
only `description + rows`. Deterministic code validates that proposal, builds
one logical table and stores it beside the older text/layout pieces. Gate 2
then selects one bounded unit and one bounded segment by default for a model
request.

The system does not send the whole PDF to either table VLM or Gate 2 model.

## 2. Does a whole document exist after processing?

No single usable whole-document artifact exists.

The original PDF bytes remain available in private source storage. A rich
private PDF payload stores page text and layout inventories. A safe document
memory manifest stores refs and status. Separate source units store table
candidates, line clusters and visual pages. These pieces are source-bound and
replayable, but none of them represents headings, paragraphs, tables, notes and
page breaks in one source order.

```text
WHOLE_DOCUMENT_ARTIFACT = FRAGMENTED
```

## 3. Where the document becomes fragments

`FullSourceArtifactBuilder._build_pdf_document` asks
`PdfLayoutUnitBuilder._build_page_units` to partition each page. That builder
returns table units before remaining line-cluster units. Table and surrounding
text therefore stop being one ordered stream. Document memory subsequently
indexes those unit refs; it does not join their private content.

Gate 2 resolves and segments units. The released standalone semantic table is
additional: it does not replace or reassemble the maintained source units.

## 4. First irreversible context loss

```text
FIRST_IRREVERSIBLE_CONTEXT_LOSS =
  FullSourceArtifactBuilder._build_pdf_document
  -> PdfLayoutUnitBuilder._build_page_units
```

This is proven by code and real-PDF structure. On four readable PDFs, 22 pages
contained both table and line units; 16 had non-monotonic `line_start` order in
the emitted unit sequence. The builder creates no section, table-title,
neighboring-paragraph, note, footnote or cross-page continuation edge.

The richer parent payload still contains page/layout observations, so an
operator could reread it. Current Gate 2 does not reconstruct from that parent.
For the current downstream route, recovering the lost relation requires parent
payload reconstruction or rereading the PDF.

## 5. What can already be reused

Twenty-one components are reusable as isolated tools or adapters. The most
valuable are private file intake, format detection, page-text and layout
parsers, deterministic page/crop rendering, table candidate intake, the strict
one-crop VLM boundary, validators, provenance/checksums, ArtifactStore,
ArtifactResolver, bounded graph persistence and workload coordination.

The current orchestrator, document-memory index, logical-table materializer,
HTML extractor, XLSX extractor and Gate 2 table package need isolation or an
adapter. They should not define the next whole-document contract unchanged.

## 6. Is the current table format sufficient?

```text
CURRENT_LOGICAL_TABLE_FORMAT = FIT_WITH_EXPLICIT_GAPS
```

It is fit for one supported page-local numeric table crop. Frozen actual-corpus
evidence covers eight real table crops across at least four broker structures
and six layout families. The accepted profile preserved all 166 tested amounts
and all 156 tested row/value bindings, with no hallucinated labels or amounts.

It is not sufficient for document context. Ten explicit gaps include table
title, section, nearby text, header roles/hierarchy, row groups, total/subtotal
relations, notes/footnotes, cross-page continuation and unreadable-versus-empty
state. No real multi-page continuation or footnote case was qualified, so
`CORPUS_GAP=TRUE`.

## 7. Are there dangerous fallbacks?

Yes. Three current product-reachable automatic legacy/maintained fallbacks are
present:

1. absence/failure of a semantic visual table leaves maintained source units
   available to Gate 2;
2. absence of an eligible full-source unit selects legacy bounded previews;
3. legacy previews may receive an automatic provenance upgrade and proceed.

Four product-reachable paths can silently reduce downstream context: layout to
page-text units, visual-page fallback without Gate 2 semantics, semantic-table
absence with maintained-unit continuation, and full-source-to-legacy-preview
selection. Their transitions are recorded in artifacts/counters but are not a
specific user-facing warning. Financial results remain possible on the first,
third and fourth paths.

The code also contains an explicit OpenAI table fallback, but released policy
is `disabled`; it is not counted as current product-reachable fallback.

## 8. Facts needed before the next design goal

- Decide whether the next document artifact must carry a single block order or
  an ordered graph with explicit relations.
- Define which of section, title, period, header hierarchy, notes, footnotes and
  continuation are mandatory versus explicitly unknown.
- Define how source bytes and rich parser observations remain resolvable without
  making the PDF itself model-visible.
- Define a document-quality decision that blocks reduced-context financial
  processing instead of silently continuing.
- Obtain real cross-page and footnote-bound table evidence before claiming a
  general table contract.

These are inputs to DOC1, not a DOC1 design.

## Technical pipeline

```text
OpenWebUI upload/private intake
-> broker_reports_gate1_pipe.Pipe._run_workload
-> Gate1Normalizer.normalize
-> ContainerDetector + profile_pdf
-> FullSourceArtifactFactory
-> PdfTextLayerParserFactory + PdfLayoutParserFactory
-> PdfLayoutUnitBuilder
-> NormalizedTableProjectionFactory
-> PdfTableIntakeRuntimeFactory
-> PdfDualVlmRuntimeFactory (Gemini master, one crop)
-> SemanticVisualTableMigrationFactory
-> SemanticVisualTableMaterializationFactory
-> persist_gate1_result / ArtifactStore
-> document-memory manifest + domain context packet
-> Gate2InputReadinessFactory
-> Gate2SourceUnitRouterFactory
-> Gate2SourceUnitSegmenterFactory
-> Gate2DomainPackageBuilderFactory
-> Gate2StructuredModelClient.extract
-> validators / stitcher / ArtifactStore
```

The exact stage contract, caller, input, output, persistence and fallback
status are in
`docs/stage2/BROKER_REPORTS_DOCUMENT_PIPELINE_MAP.v1.md`.

## Five most important losses

1. Original interleaving of tables and surrounding text is lost at page-unit
   partition.
2. Section and subsection identity are never extracted as document relations.
3. Table title and preceding/following paragraphs are not propagated into the
   semantic table or Gate 2 package.
4. Header levels, row groups, notes and footnotes may survive as text but are
   not addressable relations.
5. Cross-page table continuation is not created by the current page-local
   crop/table path.

## Real PDF audit

Five real PDFs were selected by SHA-256 from ignored local storage. No filename,
path or literal value was copied to Git.

| Safe corpus ID | Pages | Text/layout result | Table candidates | Unit result |
| --- | ---: | --- | ---: | --- |
| `real_pdf_1` | 1 | complete | 1 | 1 table, 2 line clusters |
| `real_pdf_2` | 2 | complete plus visual fallback | 2 | 2 table, 2 line, 2 visual |
| `real_pdf_3` | 6 source pages | blocked: encrypted without key | 0 | no source-ready units |
| `real_pdf_4` | 15 | complete plus one visual page | 14 | 14 table, 15 line, 1 visual |
| `real_pdf_5` | 6 | complete plus visual pages | 14 | 14 table, 6 line, 6 visual |

Aggregate:

```text
REAL_PDFS_AUDITED_TOTAL = 5
READABLE_REAL_PDFS_TOTAL = 4
BLOCKED_ENCRYPTED_PDFS_TOTAL = 1
PARSER_TABLE_CANDIDATES_TOTAL = 31
REAL_TABLE_CROPS_AUDITED_TOTAL = 8
MULTI_PAGE_TABLES_AUDITED_TOTAL = 0
DIFFERENT_BROKER_STRUCTURES_TOTAL = 4
CORPUS_GAP = TRUE
```

The document-memory safe summary reported zero silent loss only for accepted
profile documents. For the encrypted PDF, accepted documents were zero; the
summary still said `passed_for_all_profile_accepted_documents`. This is a
vacuous accepted-set statement, not proof that the encrypted document was
preserved. The document itself was correctly blocked from Gate 2.

## Context loss matrix

The machine-readable matrix audits 53 facets:

```text
PRESERVED = 7
PARTIALLY_PRESERVED = 20
LOST = 24
UNKNOWN = 2
```

`PRESERVED` means the usable facet/relation reaches the model-visible route,
not merely that bytes exist somewhere. Source bytes and rich page payloads are
therefore correctly classified as stored but not propagated.

## Legacy and reusable tooling

```text
REUSE_AS_TOOL = 14
REUSE_AFTER_ISOLATION = 4
WRAP_OR_ADAPT = 3
FREEZE = 4
RETIRE_AFTER_CUTOVER = 3
REUSABLE_TOOLS_TOTAL = 21
```

Freeze now:

- table-first/line-cluster partition as a document abstraction;
- geometric PDF table projection as semantic document truth;
- default-off passport/clarification enrichment as a context repair strategy;
- all disabled shadow routes as parallel document pipelines.

Retire only after a proven cutover:

- legacy bounded previews;
- source-unit-only document analysis;
- automatic maintained-unit continuation when semantic context is absent.

Nothing was retired or changed in DOC0.

## Other formats

| Format | Current state | Whole document | Downstream |
| --- | --- | --- | --- |
| HTML | ordered text/table blocks with bounded embedded data media | partial; DOM semantics/external media incomplete | current full-source/Gate 2 mechanics |
| CSV | one complete accepted logical table under budgets | yes for the flat table, not a general document | current full-source/Gate 2 mechanics |
| XLSX | sheet rows/cell coordinates; formulas make status partial | fragmented by sheet; workbook semantics incomplete; outside accepted pilot profile | persistence/readiness mechanics exist |
| XLS | explicitly unsupported | no | blocked |

## Preliminary next-goal chain

| Goal | Plain purpose | Accepts | Creates | Does not do | Completion criterion | Known blocker |
| --- | --- | --- | --- | --- | --- | --- |
| DOC1 | define one machine-readable document contract | DOC0 map/matrix/gaps | versioned contract and invariants | no parser or product route | every required facet has explicit representation/unknown policy | relation and ordering choice |
| DOC2 | map PDF into that contract | accepted DOC1 | inactive deterministic PDF normalizer | no model qualification/cutover | real PDFs yield source-bound documents with explicit loss accounting | encrypted and complex PDFs |
| DOC3 | create bounded LLM-friendly rendering | DOC2 artifact | deterministic model view with budgets | no provider call | full required context survives view construction | token budget and privacy |
| DOC4 | compare PDF to document artifact | DOC2/DOC3 | independent parity and loss validator | no repair | real corpus has explicit per-facet parity | cross-page/footnote corpus gap |
| DOC5 | close proven losses | DOC4 failures | bounded corrections only | no activation | targeted gaps close without regression | evidence availability |
| DOC6 | qualify one real model | DOC3-5 accepted | four-disposition qualification receipt | no product activation | exact candidate passes governed gate | candidate/policy authorization |
| DOC7 | adapt HTML/CSV/XLSX | stable document contract | format adapters | no PDF redesign | each adapter passes common contract | XLS unsupported/library decision |
| DOC8 | governed product cutover | qualified pipeline | released route and rollback proof | no legacy deletion | CI, release, rollback and readback pass | explicit activation decision |
| DOC9 | remove legacy | proven stable cutover | retirement/removal evidence | no new behavior | no legacy reachability or fallback remains | observation window/policy |

The chain is preliminary and may change after DOC1. DOC0 does not begin DOC1.

## Verification scope

The audit requires and records:

- exact code symbol/import/call-chain inspection;
- read-only real-PDF normalization and frozen actual table evidence;
- released route/readback authority inspection without live mutation;
- fallback and product-reachability inspection;
- JSON schema/integrity and privacy scans;
- managed bundle rebuild with zero diff;
- relevant architecture/current-state tests;
- one full repository suite;
- `git diff --check`;
- docs-only diff and zero new skips.

Final command outcomes, PR and merge evidence are recorded in the safe receipt
and terminal handoff after delivery.

## Scope and non-actions

```text
NEW_PIPELINE_CODE_CHANGES_TOTAL = 0
RUNTIME_CODE_CHANGES_TOTAL = 0
PRODUCT_ROUTE_CHANGES_TOTAL = 0
PROVIDER_CALLS_TOTAL = 0
LIVE_CHANGES_TOTAL = 0
NEW_PIPELINE_IMPLEMENTATION = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
