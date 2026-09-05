# ADR: PDF Document AI boundary

Status: `CURRENT PRODUCT ROUTE`

Decision date: 2026-09-05

PDF understanding belongs to one port in the existing source-normalization
domain: `PdfDocumentExtractor.extract(pdf_bytes, source_context) ->
PdfDocumentExtraction`. The immutable result is provider-neutral and carries
source/Markdown hashes, ordered pages, opaque image references with hashes,
provider provenance, qualification status, page usage, and a text-free safe
technical summary. It is transport evidence, not a second Canonical or a
financial-semantic authority.

Mistral Document AI is the first isolated adapter behind this port. Its
production request is pinned to `mistral-ocr-4-1`; moving aliases are forbidden.
The adapter owns one versioned request contract and records its normalized
significant parameters, digest, adapter version, and provider-reported model.
Native
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
trimmed, repaired, or otherwise normalized. Image references in the result are
opaque ArtifactStore identifiers; every reference remains bound to its
page-scoped Markdown target and raw SHA-256. Decoded image bytes exist only in
the short-lived neutral extraction envelope until the existing bounded-graph
owner atomically publishes Markdown, its Full Source unit, and every image
through the existing ArtifactStore.

There is no separate admin qualification or activation route. When native
OpenWebUI configuration selects `mistral_ocr`, the ordinary authenticated
`broker_reports_gate1_pipe` path may select the adapter. An unselected or absent
engine terminates with `PDF_DOCUMENT_AI_NOT_CONFIGURED`. Invalid configuration
or provider failure terminates fail-closed; neither case permits retry,
fallback, repair, engine probing or downstream publication from an incomplete
extraction. The API key must not enter logs, errors, public results, technical
summaries, receipts, Git, Pipe state or browser code.

The source boundary is native OpenWebUI custody. The Pipe receives opaque file
IDs, resolves each row through `Files`, verifies the authenticated owner, and
reads the exact stored bytes through `Storage`. Caller-supplied filenames,
bytes, hashes or metadata cannot substitute for that owner read. There is no
custom intake endpoint or Action.

The existing ArtifactStore is the only lifecycle owner. It performs one atomic
private publication, checksum verification on reread, scoped resolution,
retention, expiry, purge and source-deletion cascade. Its private-root preflight
checks read/write/delete access and rejects root identity changes and
symlink/reparse roots. The adapter owns no filesystem path or staging area.

After successful persistence, the Pipe deterministically projects the stored
Markdown and every stored image into an owner-scoped `full-source.zip`. The ZIP
is a delivery projection, not a second authority: ArtifactStore remains the
source of truth, while native `Files`/`Storage` owns authenticated download
delivery. Cross-user or cross-case reads fail closed.

The 2026-09-02 Playground Markdown remains research reference material only.
Its exact model and parameters were not recorded, so it is not a byte oracle
and cannot define current product acceptance.

PDFPlumber, pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox reconstruction,
hybrid/dual-engine execution, structural repair, and automatic fallback are
rejected product paths. An engine may be introduced only as one adapter behind
the same port and selected explicitly at the single composition point;
Pipe, Full Source, Canonical, financial mapping, Gate 4, and Gate 5 must not
gain provider-specific knowledge.

## OpenWebUI 0.9.6 compatibility seam

OpenWebUI 0.9.6 has no supported per-model policy for upload processing. The
temporary frontend seam therefore changes only the native PDF upload URL to
`process=false`, and only when the exact selected model ID is
`broker_reports_gate1_pipe`. It does not add an endpoint, response contract,
file-identity mapper, Action, provider client or DOM-based source binding. The
Pipe still receives native file IDs and performs the server-side owner read.

This seam must be removed when upstream OpenWebUI exposes an equivalent
per-model upload-processing policy. A core fork and a global RAG/embedding
bypass are rejected: the former creates upgrade debt, while the latter changes
unrelated models and Knowledge workflows.
