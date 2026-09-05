# Broker Reports Document Pipeline Map v1

Status: `CURRENT_PDF_ROUTE_WITH_HISTORICAL_SCOPE`

Effective date: 2026-09-03

Normative gate authority: `BROKER_REPORTS_PIPELINE_GATES.v1.md`.

## Current PDF route

```text
authenticated PDF bytes
  -> shared source custody and safe preflight
  -> PdfDocumentExtractorFactory.create()
     -> absent/unselected: PDF_DOCUMENT_AI_NOT_CONFIGURED
     -> ordinary selected/unqualified: PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED
     -> exact two-fixture qualification capability
        -> Mistral adapter -> PdfDocumentExtraction
        -> atomic private Full Source + image graph in existing ArtifactStore
        -> source PDF vs live Markdown/images substantive private review
        -> safe OCR 4.1 baseline candidate -> purge private review graph
```

`PdfDocumentExtractorFactory` is the sole PDF-understanding composition point.
The current ordinary product route performs no provider call. The implemented
adapter remains production-blocked; only the closed two-public-hash
qualification capability can reach it before a later activation review, and it
returns only the provider-neutral `PdfDocumentExtraction` envelope.

Pipe, Full Source, Canonical, financial mapping, Gate 4 and Gate 5 must not know
provider response schemas, OCR options, coordinates, crops, DPI,
table reconstruction, retry policy or fallback logic. Automatic engine or
provider fallback is forbidden.

The governing decision is
[PDF Document AI boundary](adr/BROKER_REPORTS_PDF_DOCUMENT_AI_BOUNDARY.v1.md).
Gate meaning remains owned by
[Pipeline Gates v1](contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md), and current
implementation ownership remains in
[Architecture Authorities](contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).

## Non-PDF continuity

Supported non-PDF formats continue through their existing deterministic
normalization and downstream contracts. This map does not change Canonical,
financial-semantic, ArtifactStore, AnswerContext, Gate 3, Gate 4 or Gate 5
ownership.

The extraction envelope and Full Source may carry provider-neutral execution
evidence (requested model, reported model, safe normalized parameters, adapter
version and digests). Downstream financial and Canonical domains must not
interpret it. Markdown-to-Canonical parsing is a separate future goal.

## Historical research

The retired local PDF parser, layout, raster, VLM, reconstruction, repair and
logical-row families are not current routes and are intentionally not
reproduced here. Their surviving research record is
[Issue #317 PDF table R&D synthesis](../reports/2026-09-02/BROKER_REPORTS_ISSUE317_PDF_TABLE_RND_SYNTHESIS.report.md).
It is historical evidence only and cannot authorize product reachability,
dependencies, fallback, qualification or release state.
