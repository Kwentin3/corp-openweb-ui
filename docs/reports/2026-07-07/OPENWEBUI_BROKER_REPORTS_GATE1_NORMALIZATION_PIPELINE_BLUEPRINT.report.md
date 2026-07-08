# OpenWebUI Broker Reports Gate 1 Normalization Pipeline Blueprint Report

Status: GATE1_NORMALIZATION_PIPELINE_BLUEPRINT_REPORT_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 research + blueprint

## 1. What Was Studied

Reviewed current Gate 1 docs, contracts, proof files, and the safe customer source index:

- Gate 1 Pipe handoff report from 2026-07-06;
- document normalization gate blueprint and UX;
- artifact, taxonomy, data-contract-family, and validation-rule contracts;
- Gate 1 proof plan;
- customer source documents safe index report and safe JSON index;
- existing `services/broker-reports-gate1-proof/` Pipe and Action stubs/tests.

Raw customer documents were not read. Code and runtime were not changed.

## 2. Why Gate 1 Is Technical And Structural

Gate 1 must make the document package knowable before any tax interpretation starts.

The safe index already shows a mixed corpus:

- 63 documents total;
- 2 CSV;
- 31 PDF;
- 4 HTML/TXT;
- 2 XLSX;
- 24 ZIP;
- 4 raster/scan-like PDFs needing OCR/review blockers;
- duplicate content requiring duplicate review.

That shape requires byte access, hashing, format detection, profiling, blockers, private slices, and safe reporting before any source-fact extraction can be trustworthy.

## 3. Why Gate 1 Does Not Extract Tax Facts

Gate 1 stops before tax facts because extraction needs different authority:

- customer methodology;
- document role approval;
- source precedence rules;
- currency/rate treatment;
- withholding treatment;
- specialist review;
- deterministic ledger and declaration contracts.

Gate 1 produces the map. Gate 2 reads from the map under approved contracts.

## 4. Proposed Pipeline Stages

```text
OpenWebUI Pipe request with files
-> file refs / original bytes access
-> normalization run
-> document inventory
-> format-specific technical profiling
-> structural slices
-> taxonomy candidates
-> blockers/review issues
-> safe report
-> handoff to next gate
```

Each stage now has explicit goal, input, output, preferred tool, fail-closed behavior, private data, safe/chat-visible data, and checks in:

- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_NORMALIZATION_PIPELINE.blueprint.md`

## 5. Tool Choices

The conservative tooling decision is:

- Slice 1: stdlib plus existing `pydantic`;
- CSV/TXT: Python `csv`, bounded decoding, optional `charset-normalizer`;
- XLSX: `openpyxl` when Slice 3 starts;
- PDF: choose `pypdf` or `PyMuPDF` when Slice 4 starts;
- PDF tables: `pdfplumber` only if table candidate quality becomes a proof criterion;
- HTML/TXT: stdlib first, BeautifulSoup only if needed;
- DOCX: `python-docx` only when Gate 1 explicitly supports DOCX;
- ZIP: stdlib `zipfile`;
- OCR/VLM, Tika, Docling, LibreOffice, pandas: deferred until a specific proof justifies them.

Detailed audit:

- `docs/stage2/research/BROKER_REPORTS_GATE1_NORMALIZATION_TOOLING_AUDIT.md`

## 6. Artifacts Created By Gate 1

Gate 1 should create:

- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `normalized_text_slice_v0`;
- `normalized_table_slice_v0`;
- `zip_member_inventory_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `chat_visible_normalization_report_v0`.

Pipeline-to-artifact mapping:

- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`

## 7. Privacy Model

Private by default:

- original file ids;
- raw filenames;
- upload/local/private paths;
- raw parser text;
- raw rows/cells;
- private text/table slices;
- parser diagnostics that can expose content.

Safe/chat-visible:

- run id;
- safe document ids;
- container counts;
- document class counts;
- blocker counts;
- case group ids;
- recommended next step;
- safety statement.

The chat report must be whitelist-rendered. If privacy validation fails, the report is not published.

## 8. LLM Boundary

LLM is deferred for source facts.

Allowed in Gate 1 only after deterministic parsing and privacy reduction:

- non-authoritative taxonomy suggestions;
- safe aggregate summary wording;
- operator next-step wording.

Forbidden in Gate 1:

- source-fact extraction;
- tax meaning inference;
- raw-document bulk reading;
- overriding parser or blocker results;
- filling declaration fields.

## 9. Implementation Slices

Recommended implementation order:

1. Pipe receives files and creates inventory/hash/container counts.
2. CSV/TXT profiling and private slices.
3. XLSX profiling.
4. PDF profiling.
5. ZIP inventory and blockers.
6. Taxonomy candidates.
7. Safe report and validation rules.

Full slice plan:

- `docs/stage2/proof/BROKER_REPORTS_GATE1_NORMALIZATION_IMPLEMENTATION_SLICES.md`

## 10. What To Do Next

Start Slice 1 only.

Required first proof:

- Pipe receives same-request files;
- original bytes are accessible under approved boundary;
- SHA-256 and size are stable;
- duplicate content is detected;
- container counts are produced;
- no raw filename, file id, private path, prompt text, account number, raw row, or parser text appears in chat;
- no parser dependencies are added before inventory/hash/container proof is stable.

## 11. Statuses

```text
GATE1_NORMALIZATION_PIPELINE_BLUEPRINT_READY
GATE1_TOOLING_AUDIT_READY
GATE1_TECHNICAL_STRUCTURAL_NORMALIZATION_CONFIRMED
LLM_SOURCE_FACT_EXTRACTION_DEFERRED_TO_GATE2
PIPE_PRIMARY_ENTRYPOINT_CONFIRMED
READY_FOR_GATE1_IMPLEMENTATION_SLICE_1
```
