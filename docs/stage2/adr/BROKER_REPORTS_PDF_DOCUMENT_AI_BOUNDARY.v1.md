# ADR: PDF Document AI boundary

Status: `CURRENT`

Decision date: 2026-09-03

PDF understanding belongs to one port in the existing source-normalization
domain: `PdfDocumentExtractor.extract(pdf_bytes, source_context) ->
PdfDocumentExtraction`. The immutable result is provider-neutral and carries
source/Markdown hashes, ordered pages, local image references with hashes,
provider provenance, qualification status, page usage, and a text-free safe
technical summary. It is transport evidence, not a second Canonical or a
financial-semantic authority.

Mistral Document AI is the first intended future adapter. Its transport and
qualification are not implemented by this decision. Until a separately
authorized integration is configured, the production composition point uses
the unconfigured extractor and terminates PDF intake with
`PDF_DOCUMENT_AI_NOT_CONFIGURED` before network access or downstream artifact
publication.

PDFPlumber, pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox reconstruction,
hybrid/dual-engine execution, structural repair, and automatic fallback are
rejected product paths. A future engine may be introduced only as one adapter
behind the same port and selected explicitly at the single composition point;
Pipe, Full Source, Canonical, financial mapping, Gate 4, and Gate 5 must not
gain provider-specific knowledge.
