# ADR: PDF Document AI boundary

Status: `STATIC READY`

Decision date: 2026-09-04

PDF understanding belongs to one port in the existing source-normalization
domain: `PdfDocumentExtractor.extract(pdf_bytes, source_context) ->
PdfDocumentExtraction`. The immutable result is provider-neutral and carries
source/Markdown hashes, ordered pages, local image references with hashes,
provider provenance, qualification status, page usage, and a text-free safe
technical summary. It is transport evidence, not a second Canonical or a
financial-semantic authority.

Mistral Document AI is the first isolated adapter behind this port. Native
OpenWebUI `request.app.state.config` remains the sole runtime owner of
`CONTENT_EXTRACTION_ENGINE`, `MISTRAL_OCR_API_BASE_URL`, and
`MISTRAL_OCR_API_KEY`. Broker Reports does not copy these settings into Pipe,
valves, environment aliases, or another persistent store. Only
`PdfDocumentExtractorFactory` may select the adapter from the live native
configuration; Pipe and the downstream domains remain provider-neutral.

For one accepted PDF the adapter makes exactly one provider call. Retry,
automatic fallback, engine probing, and a second extraction path are
forbidden. Ordered page Markdown bytes are assembled with exactly two LF
bytes (`b"\n\n"`) between adjacent pages. Page bytes are not stripped,
trimmed, repaired, or otherwise normalized. Image references in the result
must be closed local relative references: no scheme, absolute path, drive,
root, or `..` segment; every reference remains hash-bound.

The architecture is statically ready, but live qualification and activation
remain blocked by the code-owned `PDF_DOCUMENT_AI_LIVE_QUALIFIED = False`
admission gate. Native configuration does not qualify or activate the route.
Until a separately authorized qualification changes that reviewed gate,
Mistral-selected production intake terminates with
`PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED` before the adapter import,
credential read, network access, image materialization, or downstream artifact
publication. An unselected or absent engine still terminates with
`PDF_DOCUMENT_AI_NOT_CONFIGURED`. The admission constant is release state, not
a second operator configuration surface. The API key must not enter logs,
errors, public results, technical summaries, receipts, Git, or Pipe state.
Before that gate can change, the qualification change must also bind successful
image batches to the existing ArtifactStore retention/purge lifecycle, verify
their hashes again on private read, and prove permissions plus reparse-point
containment in the target runtime. The adapter's current staging cleanup is a
static transport proof, not production lifecycle qualification.

PDFPlumber, pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox reconstruction,
hybrid/dual-engine execution, structural repair, and automatic fallback are
rejected product paths. An engine may be introduced only as one adapter behind
the same port and selected explicitly at the single composition point;
Pipe, Full Source, Canonical, financial mapping, Gate 4, and Gate 5 must not
gain provider-specific knowledge.
