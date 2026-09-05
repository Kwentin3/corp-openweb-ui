# Broker Reports Document Pipeline Map v1

Status: `CURRENT_PDF_ROUTE_WITH_HISTORICAL_SCOPE`

Effective date: 2026-09-05

Normative gate authority: `BROKER_REPORTS_PIPELINE_GATES.v1.md`.

## Current PDF route

```text
ordinary authenticated user + native OpenWebUI file ID
  -> Files owner check -> Storage exact-byte read
  -> shared source custody and safe preflight
  -> PdfDocumentExtractorFactory.create()
     -> absent/unselected: PDF_DOCUMENT_AI_NOT_CONFIGURED
     -> configured Mistral adapter: exactly one call per accepted PDF
        -> provider-neutral PdfDocumentExtraction
        -> atomic private Markdown + image graph in existing ArtifactStore
        -> owner-scoped full-source.zip projection through Files/Storage
```

`PdfDocumentExtractorFactory` is the sole PDF-understanding composition point.
There is no admin qualification route, custom intake endpoint or Action. Pipe
receives native file IDs and trusts only the server-side owner-checked byte
read. `ArtifactStore` remains the sole Markdown/image authority;
`full-source.zip` is only a private delivery projection.

Pipe, Full Source, Canonical, financial mapping, Gate 4 and Gate 5 must not know
provider response schemas, OCR options, coordinates, crops, DPI,
table reconstruction, retry policy or fallback logic. Automatic engine or
provider fallback is forbidden.

OpenWebUI 0.9.6 lacks a per-model upload-processing policy. A temporary
frontend compatibility seam therefore sets `process=false` only for a native
PDF upload when the exact selected model ID is `broker_reports_gate1_pipe`.
It must be removed when upstream provides that policy. A core fork, global
bypass, DOM file mapping and RAG intake remain forbidden.

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
