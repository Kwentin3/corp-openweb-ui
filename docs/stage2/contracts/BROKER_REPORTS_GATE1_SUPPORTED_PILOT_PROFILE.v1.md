# Broker Reports Gate 1 supported pilot profile v1

Status: authoritative bounded contract

Runtime profile id: `broker_reports_gate1_source_evidence_profile_v1`

Runtime schema: `broker_reports_gate1_supported_pilot_profile_v1`

Owner: Gate 1 — Source Intake And Representation Normalization

## Purpose and boundary

This profile defines the source-evidence document variants that Gate 1 may mark
as accepted for the current Broker Reports pilot. It is deliberately bounded to
the required source-evidence classes recorded in the approved safe document
registry. It is not a claim of universal CSV, HTML, PDF, spreadsheet or office
document support.

Gate 1 preserves source representation, order, scope, provenance, structural
uncertainty and completeness. It must not assign financial or tax meaning.

Content detection and maintained parser evidence are authoritative. A filename
extension alone cannot promote an unsupported or malformed container into the
profile.

## Supported formats and limits

| Container | Supported variant | Hard profile limits | Normalized memory | Complete/review conditions |
| --- | --- | --- | --- | --- |
| CSV | `broker_reports_csv_supported_profile_v1`; UTF-8 with/without BOM or CP1251; comma, semicolon, tab or pipe delimiter | 5,000,000 input bytes; 10,000 rows; 256 columns; 100,000 cells; 32,000 characters per field; 20,000,000 materialized JSON bytes | private source payloads and row-window source units; validated `broker_reports_normalized_table_projection_v0` | `complete` only when the existing strict CSV profile and full-source/accounting validators pass |
| HTML | `static_html_text_and_tables_v1`; UTF-8 with/without BOM or CP1251 | 5,000,000 input bytes; 65 logical units; 10,000 rows and 100,000 cells per table; 200,000 text characters per unit | ordered private text/table payloads and source units; validated common table projections | static text/tables may be `complete`; scripts, embedded media, nested tables or other counted structural uncertainty produce `review_required`; unsupported encoding is `unsupported` |
| PDF | `complete_text_layer_and_layout_v1`; text-only visible content with a usable text layer | 50,000,000 input bytes; 2,000 pages; 10,000,000 content-stream bytes per page; 200,000 text characters, 50,000 layout characters, 10,000 words and 2,000 lines per page; 75,000 layout objects per document | private page/text payload, ordered layout units, table candidates and validated common table projections where deterministic | both text-layer and layout projections and page accounting must be complete; a table without a validated projection remains `review_required` with text fallback lineage, never a silently accepted canonical table |

For v1, each physical source file is exactly one logical document. One file
containing several logical documents, one logical document spread across
several files, and multi-sheet workbook semantics are outside this profile.

### HTML structural rules

- Ordinary static markup, text order and non-nested tables are supported.
- Style elements are excluded as non-content and counted.
- Comments, scripts, embedded media and nested tables are detected and
  accounted. They are not silently executed or materialized.
- Script/media/nested-table content prevents an unqualified `complete` claim
  and requires explicit review.
- Broken or truncated markup follows the parser completeness result; a bounded
  prefix is not promoted to complete memory.

### PDF structural rules

- Every page is counted as with-text or without-text. The sum must equal the
  declared page count.
- Image-only pages and mixed text/image pages are outside the complete
  text-only variant. OCR/VL output is not accepted as canonical memory in v1.
- Embedded attachments are detected and force explicit review; attachment
  bytes are not silently ignored as part of a complete claim.
- Text-layer tables converge on the common normalized-table contract only when
  geometry and coverage validation pass.
- When table topology remains unresolved, Gate 1 preserves the text/layout
  lineage and returns `review_required`; downstream code must not treat a
  raster candidate or unvalidated structure as a canonical table.
- The accepted PDF Table Intake child boundary remains unchanged. Its private
  raster candidates are evidence/lineage, not by themselves complete document
  memory.

## Explicitly outside v1

| Class | v1 behavior | Reason |
| --- | --- | --- |
| XLSX | `unsupported` / not accepted into Gate 2 memory | The two approved-pool workbooks are methodology/output artifacts, not source-evidence candidates. Formula, cached-value, merge, hidden-content and embedded-object memory is not closed. |
| ZIP | archive inventory only; members are not source memory | The approved registry marks archives conditional. Promotion and recursive unpacking require a separate approved contract. |
| Image-only PDF | `partial` or `review_required`, never complete | Canonical OCR/VL memory is not closed. |
| Mixed text/image PDF | `partial` or `review_required`, never complete | Visible image content is not fully normalized. |
| DOCX | not accepted | Existing body-only projection is partial. |
| TXT, XML, XLS | `unsupported` | No required source-evidence class exists in the approved pilot registry. |

If any excluded class becomes mandatory for the agreed pilot, this profile must
be versioned and that adapter must independently prove full-source accounting,
cohesion, persistence and lifecycle behavior before the class is called
supported.

## Terminal states

| State | Contract meaning | Gate 2 memory readiness |
| --- | --- | --- |
| `complete` | All declared profile scope is normalized and accounted, and the deterministic validator passes. | ready |
| `review_required` | Source memory and fallback lineage are complete, but structural interpretation remains explicitly unresolved. | ready with issues/restrictions; not a claim that an unresolved table is canonical |
| `partial` | Some declared source scope is not normalized or a completeness/accounting invariant failed. | blocked |
| `blocked` | Gate 1 could not produce usable bounded memory. | blocked |
| `unsupported` | The container or material variant is outside this versioned profile. | blocked |
| `unreadable` | Approved source bytes are unavailable or unreadable. | blocked |

There is no implicit fallback from a blocked state to `complete`. Over-limit,
unsupported, unreadable and unresolved scope is counted and accompanied by
reason codes.

## Actual-pool basis and proof boundary

The approved safe registry records 63 items: 2 CSV, 4 static HTML documents,
31 PDFs, 2 formula-bearing XLSX workbooks and 24 ZIP archives. Its declared
source-evidence subset is 2 CSV + 4 HTML + 18 text-layer PDFs. XLSX is marked
non-source methodology/output; ZIP is conditional. This is why v1 supports the
three source-evidence classes above and excludes the others.

The safe registry does not publish private payload paths. It is contract and
scope evidence, not a substitute for an executable representative corpus.
Current product closure therefore still requires an approved mixed-format
stage run and operator acceptance over accessible actual source bytes.

## Runtime authority

- Profile, state and limit authority:
  `broker_reports_gate1/document_memory.py`.
- Factory-only root construction:
  `Gate1DocumentMemoryFactory.create()`.
- Public validation and Gate 2 boundary:
  `broker_reports_gate1/gate1_public_contracts.py`.
- Regression proof:
  `tests/test_broker_reports_gate1_document_memory_v1.py` and the maintained
  mixed-profile proof script.

