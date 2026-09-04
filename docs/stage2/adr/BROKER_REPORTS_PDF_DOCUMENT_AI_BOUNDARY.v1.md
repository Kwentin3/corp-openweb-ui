# ADR: PDF Document AI boundary

Status: `LIVE QUALIFICATION READY / OWNER INPUT REQUIRED`

Decision date: 2026-09-04

PDF understanding belongs to one port in the existing source-normalization
domain: `PdfDocumentExtractor.extract(pdf_bytes, source_context) ->
PdfDocumentExtraction`. The immutable result is provider-neutral and carries
source/Markdown hashes, ordered pages, opaque image references with hashes,
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
trimmed, repaired, or otherwise normalized. Image references in the result are
opaque ArtifactStore identifiers; every reference remains bound to its
page-scoped Markdown target and raw SHA-256. Decoded image bytes exist only in
the short-lived neutral extraction envelope until the existing bounded-graph
owner atomically publishes Markdown, its Full Source unit, and every image
through the existing ArtifactStore.

The architecture is statically ready, but live qualification and activation
remain blocked by the code-owned `PDF_DOCUMENT_AI_LIVE_QUALIFIED = False`
admission gate. Native configuration does not qualify or activate the route.
Until a separately authorized activation changes that reviewed gate, ordinary
Mistral-selected production intake terminates with
`PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED` before the adapter import,
credential read, network access, image materialization, or downstream artifact
publication. The one qualification-only capability is the sole exception: it
admits only one of the two repository-pinned public PDF hashes, verifies the
actual bytes before URL/key access, and still routes through the same Pipe,
Normalizer, factory, adapter and ArtifactStore. An unselected or absent engine
still terminates with
`PDF_DOCUMENT_AI_NOT_CONFIGURED`. The admission constant is release state, not
a second operator configuration surface. The API key must not enter logs,
errors, public results, technical summaries, receipts, Git, or Pipe state.
The existing ArtifactStore is the only lifecycle owner. It performs one atomic
private publication, checksum verification on reread, scoped resolution,
retention, expiry, purge and source-deletion cascade. Its private-root preflight
checks read/write/delete access and rejects root identity changes and
symlink/reparse roots. The adapter owns no filesystem path or staging area.

PDFPlumber, pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox reconstruction,
hybrid/dual-engine execution, structural repair, and automatic fallback are
rejected product paths. An engine may be introduced only as one adapter behind
the same port and selected explicitly at the single composition point;
Pipe, Full Source, Canonical, financial mapping, Gate 4, and Gate 5 must not
gain provider-specific knowledge.

## Qualification-only operator path

Qualification preparation has one operator entrypoint:
`services/broker-reports-gate1-proof/scripts/live_pdf_document_ai_qualification.py`.
Its default/preflight mode
uses only the two repository-pinned public PDF hashes (DriveWealth
`738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57`
and Fidelity
`36a166a5a13e6d6d86b391233023f83f6f7b4d268a4a23fbae01cb81290e3b96`),
requires a clean committed HEAD and the exact successful `broker-reports-ci`
check, and reports zero config/key reads, provider calls and external sends.
It accepts no caller PDF/path, URL, key, model or hash. Eventual execution can
only consume two durable one-shot slots and delegate the exact bytes to an
injected existing-Pipe runner; a timeout or failure consumes its slot and is
not retried. This seam neither constructs the adapter nor admits production.

`CONTENT_EXTRACTION_ENGINE=mistral_ocr` is global OpenWebUI state and also
affects ordinary Knowledge/RAG PDF processing. A separately authorized live
qualification therefore requires an isolated maintenance window with no
parallel PDF uploads. The operator records the prior engine, enters the key in
the native Admin configuration, selects Mistral, runs the single qualification
entrypoint, and restores the prior engine in `finally` even after failure.
The script must not toggle this setting itself. Source uploads are made with
`process=false`; after private Full Source/image readback they are deleted via
the existing source-deletion lifecycle and purge/read denial is verified.
`PDF_DOCUMENT_AI_LIVE_QUALIFIED` remains false throughout; activation requires
a later owner-approved change.
