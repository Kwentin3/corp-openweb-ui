# Broker Reports Gate 1 supported pilot profile v1

Status: authoritative bounded contract; actual-corpus accepted

Runtime profile id: `broker_reports_gate1_source_evidence_profile_v1`

Runtime schema: `broker_reports_gate1_supported_pilot_profile_v1`

Owner: Gate 1 — Source Intake And Representation Normalization

## Purpose and boundary

This contract defines the exact source representations that Gate 1 accepts for
the current Broker Reports pilot. It is not universal document support. Gate 1
preserves source bytes as normalized memory, order, structure, lineage,
provenance, completeness and unresolved scope. It does not assign financial or
tax meaning.

Content detection and maintained parser evidence are authoritative. An
extension alone cannot promote a malformed or unsupported container.

## Actual-corpus basis

The authoritative customer corpus was recovered and reconciled against the
approved safe registry:

- 63 physical files and 18,872,606 bytes;
- authoritative-source, private-copy and registry SHA-256 multisets match;
- two duplicate groups, each with one extra copy, remain explicitly represented;
- 56 top-level inputs are required source evidence for Gate 1;
- 24 of those inputs are ZIP containers;
- the ZIPs promote 48 required PDF/XML members and account for 24 P7S sidecars;
- the accepted graph contains 104 source records and 80 logical documents.

The two XLSX workbooks are formula-heavy derived calculation workbooks. Five
additional PDFs are derived tax-calculation outputs. They are not relabelled as
unsupported to obtain closure; they are excluded from the source-evidence pool
because actual-container/content inspection confirms that they are downstream
outputs rather than source evidence.

## Supported formats and limits

| Container | Supported variant | Hard limits | Memory and acceptance rule |
| --- | --- | --- | --- |
| CSV | `broker_reports_csv_supported_profile_v1`; UTF-8/BOM/CP1251; comma, semicolon, tab or pipe | 5 MB; 10,000 rows; 256 columns; 100,000 cells; 32,000 chars/field; 20 MB materialized JSON | Ordered rows/source values plus validated common table projection. `complete` only after strict profile and accounting validation. |
| static HTML | `static_html_text_and_tables_v1`; UTF-8/BOM/CP1251 | 5 MB; 65 logical units; 10,000 rows and 100,000 cells/table; 200,000 text chars/unit; 16 embedded data images; 2 MB/image; 10 MB images/document | DOM-ordered text/table blocks, common table projections and bounded visual-media units. Captured images require `review_required`; scripts, nested tables, external/unbounded media or exceeded budgets fail closed. |
| PDF | `text_layout_and_bounded_visual_fallback_v1` | 50 MB; 2,000 pages; 10 MB content stream/page; 200,000 text chars/page; 50,000 layout chars, 10,000 words and 2,000 lines/page; 75,000 layout objects/document | Page text/layout plus bounded rendered visual-page memory where needed. A validated table may be canonical; unresolved topology remains `review_required` with explicit text/visual fallback scope. |
| XML | `neutral_ordered_xml_event_memory_v1` | 5 MB; depth 64; 100,000 events; 100,000 attributes; DTD/entities forbidden | Ordered neutral element/attribute/text-event memory and neutral event table. Financial semantics and canonical financial table scope remain unavailable, so accepted XML is `review_required`. |
| ZIP | `bounded_source_container_v1` | 10 MB archive; 100 members; 20 MB/member; 50 MB expanded total; ratio 100:1 | ZIP is a lineage container, not a financial document. PDF/XML members are promoted to normal Gate 1 processing; P7S is an accounted sidecar. The container has zero logical documents; promoted members each have one. |

Runtime values in `document_memory.py` are the executable authority when a
summary in this document becomes stale.

## ZIP safety contract

The archive factory must reject or explicitly account for:

- relative traversal and absolute member paths;
- symlinks, devices and other special files;
- encrypted members;
- nested archive recursion;
- excessive members, member size, expanded size or compression ratio;
- duplicate/case-colliding member names;
- unsupported member formats;
- any member without an explicit promoted, sidecar or blocked disposition.

No archive member may disappear silently. The actual 24-archive pool passed
these checks: 72 members were accounted, 48 were promoted and 24 were P7S
sidecars; there were no blocked or omitted members.

## Logical-document rules

- A supported non-ZIP source file is one logical document.
- A ZIP container is lineage-only and has zero logical documents.
- Every promoted PDF/XML member is one logical document with parent archive,
  member-index and safe member-reference lineage.
- An exact duplicate remains a separate source identity until downstream code
  selects a canonical copy. Gate 1 must not silently drop or double-interpret it.

## Scope readiness

`review_required` means that source memory is complete and accounted, not that
every artifact is canonical. The public root independently reports:

- text scope readiness;
- visual scope readiness and visual-consumer requirement;
- canonical table scope;
- unresolved table topology;
- neutral XML structure scope;
- archive lineage scope;
- restrictions on financial interpretation.

Gate 2 cannot infer `document review_required -> every table is canonical`.

## Explicitly outside v1

| Class | Behavior | Reason |
| --- | --- | --- |
| XLSX | not accepted into Gate 1 source memory | The actual pilot workbooks are derived formula-heavy calculation outputs; formula/cached-value/merge/object memory is not closed. |
| derived calculation PDF | excluded from the approved source-evidence set | Actual-content inspection identifies downstream tax-calculation output, not missing parser support. |
| DOCX | not accepted | Existing body-only projection is partial. |
| TXT and legacy XLS | not accepted | No required source-evidence class exists in the approved pilot pool. |
| ZIP members other than PDF/XML/P7S | blocked and accounted | No other member format is approved by this version. |

If a future required customer source falls outside these variants, this profile
must be versioned and the new adapter must independently prove bounded intake,
full-source accounting, persistence, lifecycle and operator acceptance.

## Terminal states

| State | Meaning | Gate 2 readiness |
| --- | --- | --- |
| `complete` | All declared scope is normalized/accounted and validators pass. | ready for declared scopes |
| `review_required` | Memory and fallback lineage are complete; structural interpretation remains explicit. | ready only for named scopes/restrictions |
| `partial` | Some declared scope or an accounting invariant is missing. | blocked |
| `blocked` | No usable bounded memory was produced. | blocked |
| `unsupported` | Container/variant is outside this version. | blocked |
| `unreadable` | Approved bytes are unavailable or unreadable. | blocked |

There is no fallback from a blocked state to `complete`.

## Proof authority

- Safe actual-corpus result:
  `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`.
- Closure report:
  `docs/reports/2026-07-18/OPENWEBUI_BROKER_REPORTS_GLOBAL_GATE1_DOCUMENT_MEMORY_CLOSURE_V1.report.md`.
- Runtime profile and state authority:
  `broker_reports_gate1/document_memory.py`.
- ZIP/XML/visual factories:
  `archive_intake.py`, `xml_source.py`, `pdf_visual_memory.py`.
- Actual-corpus proof tool:
  `scripts/prove_gate1_actual_customer_corpus.py`.
- Regression coverage:
  `tests/test_broker_reports_gate1_archive_xml_visual_v1.py` and
  `tests/test_broker_reports_gate1_document_memory_v1.py`.
