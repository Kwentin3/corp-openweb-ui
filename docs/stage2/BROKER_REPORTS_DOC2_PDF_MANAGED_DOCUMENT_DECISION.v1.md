# Broker Reports DOC2 PDF to Managed Document Decision v1

Effective date: 2026-08-01
Status: accepted inactive implementation decision

## Decision

`ManagedPdfDocumentFactory` is the sole inactive PDF-to-Managed-Document-v1
owner. It observes PDF bytes through `PdfTextLayerParserFactory`, assembles
source order before page-local unit partitioning, materializes DOC1 blocks, and
reconciles every source observation through the Managed Document Coverage v1
receipt.

DOC1 and its schema remain unchanged.

## Ordering law

Per-page order is:

1. page boundary;
2. parser block order;
3. parser word order inside each block;
4. a table region at the first word owned by that region;
5. following source text after the table.

The implementation does not call or depend on
`PdfLayoutUnitBuilder._build_page_units`. A validated table owns its contributing
words, and those words cannot also appear in paragraph blocks. Parser block order
is the multi-column authority; overlapping candidate ownership, duplicate line
ownership, or incomplete block/line scope is terminal `BLOCKED` ambiguity.

## Table law

`NormalizedTableProjectionFactory` and its existing deterministic validator are
the only native PDF grid admission route. A `TABLE` requires validated geometry,
complete word ownership, a supported reconstruction strategy, deterministic
source-value paths, a passed checksum, and at least medium reconstruction
quality. The block claims no semantic table truth, header meaning, row-group
meaning, unit, or financial interpretation.

If the gate does not pass, the region becomes source-bound `UNKNOWN`; its text and
private location are retained and its missing logical structure is an accounted
DOC1 loss.

## Visual and blocked inputs

Source-visible image objects become private-source-bound `VISUAL` blocks with
explicit unprocessed-content and exact-placement losses. The page-tail visual is
a page container, not a claim about its order relative to text. DOC2 performs no
OCR, VLM, provider, Knowledge, RAG, embedding, or vector operation. Encrypted and parser-blocked PDFs return a
terminal blocked observation inventory and coverage receipt without minting a
Managed Document.

## Persistence and inactivity

The offline runner persists private results through `ArtifactStoreFactory` and
verifies them through `ArtifactResolver`. Its scoped, process-local DOC2
admission contains these types without changing product ArtifactStore admission:

- `private_broker_reports_managed_document_v1`;
- `private_broker_reports_source_observation_inventory_v1`;
- `private_broker_reports_managed_document_coverage_v1`;
- `private_broker_reports_managed_document_build_trace_v1`.

No product route imports this builder. Generated OpenWebUI bundles are out of
scope and remain unchanged.

## Acceptance boundary

Readable documents require a valid DOC1 artifact, `unresolved_total = 0`,
`unaccounted_context_loss_total = 0`, `invented_source_content_total = 0`, and
deterministic replay. The five-document private corpus and isolated parity
results are evidence, not repository fixtures. DOC3, DOC4, activation, Gate 2,
Semantic Pack, and Type-First advancement remain explicitly out of scope.
