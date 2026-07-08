# Broker Reports Gate 1 Normalization Implementation Slices

Status: GATE1_NORMALIZATION_IMPLEMENTATION_SLICES_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, incremental Gate 1 implementation

## 1. Implementation Rule

Build the smallest reliable Gate 1 pipeline, not a universal broker-report parser.

Each slice must:

- keep the Pipe as the primary product entrypoint;
- preserve the Action path only as debug/secondary proof;
- avoid tax calculation and source-fact extraction;
- create typed artifacts or typed blockers;
- keep private data private;
- return only a safe chat-visible report;
- have tests that prove both success and fail-closed behavior.

## 2. Slice Overview

| Slice | Goal | Main proof |
| --- | --- | --- |
| 1 | Pipe receives files and creates inventory/hash/container counts. | Same-request files become safe inventory without raw names/ids. |
| 2 | CSV/TXT profiling and private slices. | Encoding/delimiter/row/column profile and bounded private slices. |
| 3 | XLSX profiling. | Sheet/formula/hidden-sheet/used-range profile. |
| 4 | PDF profiling. | Page/text-layer/raster/table-likelihood profile. |
| 5 | ZIP inventory and blockers. | Member inventory plus review blocker. |
| 6 | Taxonomy candidates. | Rule-assisted role labels with confidence and safe reason codes. |
| 7 | Safe report and validation rules. | Whitelisted chat report and Gate 2 handoff state. |

## 3. Slice 1 - File Intake, Hashing, Container Counts

Scope:

- keep `broker_reports_gate1_pipe` as the primary entrypoint;
- collect same-request file refs;
- create `normalization_run_v0`;
- create private file registry;
- access original bytes through approved OpenWebUI boundary;
- compute SHA-256 and size;
- detect duplicate content;
- detect container by extension, MIME and magic bytes where available;
- create `document_inventory_v0`;
- return safe report with counts and blockers only.

Input:

- OpenWebUI Pipe request body;
- `__files__`, metadata, messages;
- uploaded file refs;
- original bytes if accessible.

Output:

- `normalization_run_v0`;
- private file registry;
- `document_inventory_v0`;
- `normalization_blockers_v0`;
- minimal `chat_visible_normalization_report_v0`.

Tests:

- no files -> `no_files` blocker;
- files visible from same user message;
- byte access success produces stable SHA-256;
- byte access failure creates `bytes_unavailable`;
- duplicate bytes create duplicate group/review signal;
- PDF/CSV/TXT/XLSX/ZIP/image/unknown container counts;
- raw filenames and file ids absent from chat output;
- private path escape blocked.

Acceptance criteria:

- inventory exists for every uploaded test file or has an explicit blocker;
- hashes are stable across repeated runs;
- chat report includes only counts, safe ids and safety statement;
- no parser-specific dependencies are required yet.

Out of scope:

- CSV row parsing;
- workbook profiling;
- PDF text extraction;
- ZIP member extraction;
- taxonomy beyond `unknown_or_needs_review` or simple container hints;
- Gate 2 source facts.

## 4. Slice 2 - CSV/TXT Profiling And Private Slices

Scope:

- profile CSV and TXT/HTML-as-text files;
- detect encoding and delimiter;
- count rows and columns;
- detect header candidates;
- mark machine-readable table status;
- create bounded private text/table slices with source locations.

Input:

- Slice 1 inventory and bytes;
- CSV/TXT/HTML-as-text documents.

Output:

- `technical_readability_profile_v0`;
- private `normalized_text_slice_v0`;
- private `normalized_table_slice_v0`;
- `parser_failed` blockers where needed.

Tests:

- UTF-8 CSV with delimiter and headers;
- semicolon CSV;
- non-UTF fallback path or encoding blocker;
- large CSV slice truncation;
- TXT line slice;
- HTML-as-text table candidate;
- raw row content absent from chat report.

Acceptance criteria:

- CSV/TXT profiles include encoding, delimiter, row count and column count where applicable;
- private slices are bounded and source-located;
- unsafe or unreadable text fails closed.

Out of scope:

- tax event extraction;
- field normalization;
- currency/rate interpretation;
- full-row chat output.

## 5. Slice 3 - XLSX Profiling

Scope:

- profile XLSX workbooks with an approved dependency;
- count sheets;
- record redacted or hashed sheet-name policy;
- detect formulas;
- count hidden sheets;
- record used ranges and table-like ranges;
- create private table slices only when bounded and source-located.

Input:

- Slice 1 inventory and bytes;
- XLSX documents.

Output:

- workbook `technical_readability_profile_v0`;
- optional private table slices;
- blockers for unreadable/encrypted/corrupt/too-large workbooks.

Tests:

- multi-sheet workbook;
- formulas present;
- hidden sheet;
- very large used range with truncation;
- corrupt workbook;
- raw sheet names absent when not proven safe.

Acceptance criteria:

- every supported XLSX has a workbook profile or blocker;
- formula and hidden-sheet flags are reliable;
- private slices do not leak into chat.

Out of scope:

- XLS legacy parsing unless separately approved;
- formula evaluation;
- tax-base calculation;
- generated XLS/XLSX output.

## 6. Slice 4 - PDF Profiling

Scope:

- profile PDF page count;
- detect text layer;
- detect raster/scan likelihood;
- create bounded page text slices when text layer exists;
- mark table likelihood without claiming table extraction as fact;
- create OCR/review blockers for raster PDFs.

Input:

- Slice 1 inventory and bytes;
- PDF documents.

Output:

- PDF `technical_readability_profile_v0`;
- private text slices;
- `raster_requires_ocr_or_review`, `parser_failed`, `encrypted_file`, or `corrupt_file` blockers.

Tests:

- text-layer PDF;
- raster/scan PDF;
- encrypted PDF;
- corrupt PDF;
- multi-page PDF with bounded page slices;
- no raw page text in chat.

Acceptance criteria:

- PDF profiles include pages, text-layer and raster likelihood;
- raster files do not silently proceed to Gate 2;
- OCR is not performed by this slice.

Out of scope:

- external OCR;
- table extraction as source facts;
- layout-perfect reconstruction.

## 7. Slice 5 - ZIP Inventory And Blockers

Scope:

- profile ZIP archives without recursive public extraction;
- count members;
- count member extensions;
- detect nested archives;
- detect encrypted/oversized members where possible;
- create `zip_requires_review`.

Input:

- Slice 1 inventory and bytes;
- ZIP documents.

Output:

- `zip_member_inventory_v0`;
- `normalization_blockers_v0`.

Tests:

- ZIP with PDF/XML/signature members;
- nested archive;
- encrypted member;
- oversized member;
- corrupt ZIP;
- no member filenames in chat unless explicitly proven safe.

Acceptance criteria:

- every ZIP produces member inventory or blocker;
- ZIP never advances to Gate 2 as source evidence without review.

Out of scope:

- recursive extraction;
- signature validation;
- source-fact extraction from XML/PDF members.

## 8. Slice 6 - Taxonomy Candidates

Scope:

- implement rule-assisted taxonomy candidates using safe structural signals;
- assign primary class, alternatives and confidence;
- set `can_be_source_evidence`, `can_be_methodology`, `can_be_loaded_to_knowledge`, and `declaration_relevance`;
- create `unknown_role` blockers for weak classification.

Input:

- inventory;
- technical profiles;
- safe structural summaries;
- existing taxonomy contract.

Output:

- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`.

Tests:

- operations table candidate;
- source broker report candidate;
- dividends/fees/withholding candidate;
- calculation template candidate;
- official/methodology candidate;
- unknown or unsupported candidate;
- duplicate candidate handling;
- LLM is not required and not authoritative.

Acceptance criteria:

- candidates use only safe reason codes in public surfaces;
- weak evidence defaults to review;
- no source facts are extracted.

Out of scope:

- tax meaning;
- official correctness;
- customer methodology decisions;
- LLM-only classification as final.

## 9. Slice 7 - Safe Report And Validation Rules

Scope:

- implement contract validation;
- render chat-visible safe report;
- enforce privacy denylist and field whitelist;
- report Gate 2 handoff state;
- make blockers terminal for affected documents.

Input:

- all prior Gate 1 artifacts.

Output:

- `chat_visible_normalization_report_v0`;
- validation result;
- Gate 2 handoff refs or blocked state.

Tests:

- safe happy path;
- no-file blocker path;
- bytes unavailable;
- parser failure;
- raster blocker;
- ZIP review blocker;
- privacy violation blocks report publication;
- raw filename/file id/path/account/financial-row denylist checks;
- schema validation;
- Gate 2 handoff blocked until validation passes.

Acceptance criteria:

- chat report contains files total, container counts, class counts, blocker count, case groups if available, recommended next step and safety statement;
- forbidden raw data is absent;
- validation failure is explicit and fail-closed;
- Gate 2 receives only safe refs plus approved private slice refs.

Out of scope:

- UI sidecar;
- export/download workflow;
- source facts;
- declaration/XLS output.

## 10. Cross-Slice Verification

Run after every slice:

- focused unit tests for changed Gate 1 modules;
- no raw filename/file id/private path in chat content tests;
- schema/contract validation tests;
- synthetic fixture proof;
- `git diff --check`;
- secret-like scan over touched docs/code;
- manual note of runtime assumptions when live OpenWebUI proof is not run.

## 11. Ready Starting Point

Start with Slice 1.

Reason:

- the Pipe primary entrypoint is already proven for file-ref visibility;
- current Pipe output is still stub-only;
- byte access, hashing, duplicate detection and container inventory are the smallest missing proof that unlocks the rest of Gate 1;
- no parser dependencies are needed before Slice 1 is stable.

## 12. Status

```text
GATE1_NORMALIZATION_IMPLEMENTATION_SLICES_READY
READY_FOR_GATE1_IMPLEMENTATION_SLICE_1
PIPE_PRIMARY_ENTRYPOINT_CONFIRMED
SOURCE_FACT_EXTRACTION_OUT_OF_SCOPE_FOR_ALL_SLICES
```
