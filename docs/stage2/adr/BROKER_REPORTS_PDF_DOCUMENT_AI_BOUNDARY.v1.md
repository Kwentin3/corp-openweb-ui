# ADR: PDF Document AI boundary

Status: `GOAL #391 SELECTED CANDIDATE — NOT LIVE ACCEPTANCE`

Decision date: 2026-09-12

PDF understanding belongs to one port in the existing source-normalization
domain: `PdfDocumentExtractor.extract(pdf_bytes, source_context) ->
PdfDocumentExtraction`. The immutable result is provider-neutral and carries
source/Markdown hashes, ordered pages, opaque image references with hashes,
opaque provider-native HTML table references with hashes and exact page Markdown anchors,
provider provenance, qualification status, page usage, and a text-free safe
technical summary. It is transport evidence, not a second Canonical or a
financial-semantic authority.

Goal #391 selects the deterministic `pdfplumber` native-text adapter behind
this port for PDF with a usable embedded text layer. The adapter records only
the source-bound ordered page text, its deterministic parameters and hashes.
It does not render pages, run OCR, call a provider, or treat table geometry as
financial meaning. `PdfDocumentExtractorFactory` is the only composition
point; Pipe and downstream domains remain parser-neutral.

There is no provider call. Retry, automatic fallback, engine probing and a
second extraction path are forbidden. Page text is emitted in physical order
and joined with exactly two LF bytes (`b"\n\n"`). The adapter makes no attempt
to repair, join or semantically interpret tables: a broken visual table stays
a broken representation whose literals and order are available to the later
financial-role owner. An unusable embedded text layer terminates typed and
creates no downstream source facts or provider work.

The ordinary authenticated `broker_reports_gate1_pipe` path selects this
adapter solely through the factory. It does not read a PDF-provider
configuration or key. Missing/dependent-parser failure and unusable native text
terminate fail-closed; neither permits retry, fallback, repair, engine probing
or downstream publication from an incomplete extraction.

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

Mistral OCR, pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox reconstruction,
hybrid/dual-engine execution, structural repair, table-specific profiles and
automatic fallback are rejected product paths. Historical Mistral artifacts are
R&D only and cannot be activated by changing a key or engine setting. The
factory admits one deterministic adapter; Pipe, Full Source, Canonical,
financial mapping, Gate 4 and Gate 5 must not gain adapter-specific knowledge.

## OpenWebUI 0.9.6 compatibility seam

OpenWebUI 0.9.6 has no supported per-model policy for upload processing. The
pinned native `MessageInput` adaptation therefore passes `process=false` only
for a PDF whose authoritative selected-model state contains exactly
`broker_reports_gate1_pipe`. It does not add an endpoint, response contract,
file-identity mapper, Action, provider client or DOM-based source binding. The
Pipe still receives native file IDs and performs the server-side owner read.

This seam must be removed when upstream OpenWebUI exposes an equivalent
per-model upload-processing policy. A core fork and a global RAG/embedding
bypass are rejected: the former creates upgrade debt, while the latter changes
unrelated models and Knowledge workflows.
