# Broker Reports Gate 1 Normalization Tooling Audit

Status: GATE1_TOOLING_AUDIT_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 tooling choices

## 1. Sources Reviewed

- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_PIPE_HANDOFF.report.md`
- `docs/stage2/blueprints/BROKER_REPORTS_DOCUMENT_NORMALIZATION_GATE.blueprint.md`
- `docs/stage2/ux/BROKER_REPORTS_OPENWEBUI_DOCUMENT_NORMALIZATION_UX.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`
- `docs/stage2/proof/BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_PROOF_PLAN.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_TAXONOMY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_DATA_CONTRACT_FAMILY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_CONTRACT_VALIDATION_RULES.v0.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INTAKE_INDEX.report.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json`
- `services/broker-reports-gate1-proof/`

Raw customer documents were not read.

## 2. Customer Source Index Format Summary

The safe customer source index currently records 63 documents:

| Container | Count | Notes |
| --- | ---: | --- |
| `csv` | 2 | Machine-readable table candidates with encoding/delimiter/row/column profile. |
| `pdf` | 31 | Mostly text-layer PDFs, with 4 raster/scan-like PDFs needing OCR/review blocker handling. |
| `txt` | 4 | HTML files represented as text/html in the safe index; table extraction remains conditional. |
| `xlsx` | 2 | Multi-sheet calculation-template/workbook candidates with formulas. |
| `zip` | 24 | Archive packages requiring member inventory and explicit review before extraction. |

Other observed safe-index facts:

- taxonomy classes include `operations_table`, `source_broker_report`, `dividends_report`, `fees_report`, `tax_base_calculation`, `calculation_template`, and `unknown_or_needs_review`;
- duplicate content exists and needs duplicate-review handling;
- ZIP packages dominate the unknown/review backlog;
- the safe index records prior local parser labels such as `pymupdf` and `openpyxl`, but those labels are not proof that these parsers are declared Gate 1 runtime dependencies.

## 3. Current Repo And Runtime Dependency Surface

Current reusable dependency evidence:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py` declares OpenWebUI function `requirements: pydantic` and uses stdlib `hashlib`, `json`, and `pathlib`.
- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_normalizer_action.py` uses the same baseline and has a proof-only upload-root byte probe.
- `services/stage2-stt/pyproject.toml` declares `fastapi`, `httpx`, `pydantic`, `python-docx`, `python-multipart`, `uvicorn`, and `pytest`.

Not currently declared as Gate 1 runtime dependencies:

- `openpyxl`;
- `pypdf`;
- `PyMuPDF`;
- `pdfplumber`;
- `charset-normalizer` or `chardet`;
- `beautifulsoup4`;
- `filetype` or `python-magic`;
- `pandas`;
- `xlrd`;
- Tika;
- Docling;
- LibreOffice conversion.

Conclusion: Slice 1 should use stdlib plus `pydantic`. Parser dependencies should be added one format at a time with proof.

## 4. Tooling Matrix

| Format / task | Preferred tool | Fallback | Reason | Risk | Proof status |
| --- | --- | --- | --- | --- | --- |
| Request/file-ref collection | Existing Pipe collection logic | Action stub for debug | Same-request file refs are already proven through Pipe. | OpenWebUI request shapes can drift. | Pipe proof exists; still stub-only. |
| Byte hashing | Python `hashlib` | None | Stable SHA-256 over original bytes. | Requires approved byte access boundary. | Action has proof-only local byte probe; Pipe still needs production byte access proof. |
| Container detection | Magic bytes + MIME + extension | Extension/MIME only | Avoid extension-only false positives. | `python-magic` native dependency friction on Windows/containers. | Proposed. |
| Safe IDs | SHA-256/HMAC scheme | Existing synthetic id pattern | Avoid raw filename/file id in safe surfaces. | HMAC salt must stay private. | Safe index uses hashed names/paths; Pipe uses synthetic ids. |
| CSV profiling | Python `csv` | `pandas` only after proof | Stdlib is enough for delimiter/rows/columns first. | Encoding/dialect ambiguity. | Proposed for Slice 2. |
| Encoding detection | `charset-normalizer` | `chardet` or UTF-8/default fallback with blocker | Needed for non-UTF-8 broker exports. | False confidence can corrupt text. | Proposed optional dependency. |
| TXT profiling | Stdlib decoding + line/section heuristics | Same as CSV encoding fallback | Low dependency surface. | Large file memory use. | Proposed for Slice 2. |
| HTML text/table profile | stdlib `html.parser` for baseline | BeautifulSoup if needed | Keep first pass conservative; table extraction can be conditional. | HTML can contain scripts/noisy layout. | Proposed. |
| XLSX profiling | `openpyxl` read-only/data-only modes | Block if dependency absent | Sheets, formulas, hidden sheets, used ranges. | Very large workbooks and formulas. | Proposed for Slice 3; safe index previously records local openpyxl readability. |
| XLS profiling | Separate `xlrd` proof or unsupported blocker | Request XLSX export from source system | XLS is not XLSX; avoid silent conversion. | Legacy binary format complexity. | Deferred. |
| PDF text-layer profile | `pypdf` or `PyMuPDF` | `pdfplumber` for tables only after proof | Page count, text layer, raster likelihood. | Table fidelity and scanned PDFs. | Proposed for Slice 4; safe index previously records local PyMuPDF profiling. |
| PDF table candidates | `pdfplumber` if required | `PyMuPDF` text blocks only | Better table-specific signals when needed. | False table extraction can create fake structure. | Deferred until Slice 4 proof needs it. |
| DOCX profile | `python-docx` | `zipfile` package-level metadata only | Paragraph/headings/table profile. | Existing `python-docx` belongs to STT sidecar, not Gate 1. | Deferred unless DOCX enters Slice 1 proof set. |
| ZIP inventory | Python `zipfile` | None | Member count/extensions/signature markers. | Recursive unpacking and embedded sensitive docs. | Proposed for Slice 5. |
| Image/raster handling | Metadata only | OCR blocker | Gate 1 should not OCR by default. | External OCR data policy. | Blocker-only in Gate 1. |
| Schema validation | Pydantic models | JSON Schema later | Contract enforcement and typed blockers. | Over-modeling too early. | Pydantic already available in proof functions. |
| Privacy validation | Denylist + whitelist renderer tests | Manual review only is insufficient | Prevent raw names/ids/paths/content leakage. | Denylist alone misses novel PII. | Existing tests check no raw names/file ids for stubs. |

## 5. Dependencies To Add By Slice

| Slice | Add now? | Dependency | Reason |
| --- | --- | --- | --- |
| Slice 1 | Yes | No new dependency beyond `pydantic` and stdlib | Inventory, hashing, container counts can be proven without parser dependencies. |
| Slice 2 | Conditional | `charset-normalizer` | Useful for CSV/TXT encoding; can be optional with fallback blocker. |
| Slice 3 | Yes when implementing XLSX | `openpyxl` | Required for workbook-level metadata without LibreOffice. |
| Slice 4 | Choose one | `pypdf` or `PyMuPDF` | PDF profile needs parser-backed page/text-layer signals. |
| Slice 4+ | Maybe | `pdfplumber` | Only if table candidates become a proof criterion. |
| Slice 5 | No | stdlib `zipfile` | ZIP inventory can start without new dependency. |
| Later DOCX | Maybe | `python-docx` | Already used by STT sidecar, but Gate 1 should still declare its own dependency if used. |

## 6. Dependencies Not To Add Without Proof

- `pandas`: useful for heavy table analytics, but too broad for initial delimiter/row/column profiling.
- LibreOffice conversion: operationally heavy and risky as a hidden dependency.
- Tika/Docling: broad extraction engines; only add after a bounded proof shows they improve a specific Gate 1 contract.
- External OCR/VLM/OCR-VL providers: data-policy and privacy review required before any customer document processing.
- LLM document parsing as the primary classifier: violates the Gate 1 boundary.

## 7. LLM Boundary

LLM may only help after deterministic parsing and privacy reduction. Acceptable uses:

- suggest non-authoritative taxonomy alternatives from safe slices;
- draft safe next-step wording;
- summarize already-safe aggregate artifacts.

LLM must not:

- read all raw customer documents as unbounded context;
- extract source facts in Gate 1;
- infer tax meaning;
- override parser failures;
- turn full financial rows into chat-visible text.

## 8. Large Row / Large Document Handling

Gate 1 should handle large files by design:

- stream or bounded-read where possible;
- store row counts and used ranges, not full rows in safe artifacts;
- cap private slices by chars/rows/cells;
- record `slice_truncated=true` with source location;
- fail closed with `parser_failed` or `file_too_large_for_profile` if a parser cannot profile safely;
- make table extraction confidence explicit.

## 9. Avoiding Context Loss

Do not delete structure as "noise" unless the structure is captured elsewhere.

Every normalized slice should preserve:

- `document_id`;
- page/sheet/table/section;
- row or character range;
- parser name/version if available;
- truncation flag;
- confidence;
- blocker or warning refs.

This lets Gate 2 cite the source location without re-reading the whole file into an LLM context.

## 10. Status

```text
GATE1_TOOLING_AUDIT_READY
STD_LIB_PLUS_PYDANTIC_SLICE1_CONFIRMED
FORMAT_PARSER_DEPENDENCIES_MUST_BE_ADDED_PER_SLICE
LLM_SOURCE_FACT_EXTRACTION_DEFERRED_TO_GATE2
```
