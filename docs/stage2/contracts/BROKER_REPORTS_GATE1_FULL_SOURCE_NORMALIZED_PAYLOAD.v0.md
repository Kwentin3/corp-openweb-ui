# Broker Reports Gate 1 full-source normalized payload v0

Status: implemented
Schema id: `private_normalized_source_payload_v0`

## Purpose

Private normalization artifact for one parser-produced logical source unit. It is distinct from a preview slice and is never chat-visible.

## Required fields

| Field | Contract |
|---|---|
| `schema_version` | exactly `private_normalized_source_payload_v0` |
| `source_payload_ref` | stable ref scoped to run, document, logical identity and source checksum |
| `normalization_run_id` | owning Gate 1 run |
| `document_ref` | safe document ref |
| `profile_ref` | technical profile ref |
| `container_format` | detected parser container |
| `logical_identity` | safe parser logical-unit identity; no raw sheet/file name |
| `parser`, `parser_version`, `parser_ref` | parser provenance |
| `source_checksum_ref` | opaque ref derived from source checksum; raw checksum need not be exposed downstream |
| `payload_checksum_ref` | checksum of materialized normalized projection and parser identity |
| `parser_completeness_status` | `complete`, `partial`, or `blocked` |
| `parser_completeness_reason_codes` | explicit limitations; empty only for complete |
| `normalized_projection` | private rows or text when materialized |
| `normalized_projection_status` | `materialized` or `omitted_budget_exceeded` |
| `source_location` | safe logical range/location |
| `rows_total`, `cells_total`, `text_characters_total` | safe counts |
| `row_inventory`, `cell_inventory`, `text_segment_inventory` | full ref inventories for complete payloads |
| `source_value_index` | ref-to-private-payload path and checksum index |
| `coverage_index` | selected/accounted refs and full-coverage availability |
| `extraction_unit_refs` | child `private_normalized_source_unit_v0` refs |
| `visibility` | exactly `private_case` |
| `knowledge_rag_used`, `vectorization_performed` | exactly `false` |

## Completeness rules

- `complete`: parser consumed the full declared logical unit and the normalized projection is within configured materialization budgets.
- `partial`: parser cannot prove full logical coverage, formulas/auxiliary structures remain unresolved, or a materialization budget is exceeded.
- `blocked`: parser could not produce a safe normalized projection.
- `partial` and `blocked` payloads MUST NOT produce extraction-grade child units.
- Budget overflow MUST NOT be represented as a truncated `complete` payload. The projection is omitted explicitly and reason-coded.

## Current logical units

- CSV: one table projection;
- plain text: one text projection;
- HTML: outside-table text plus one logical unit per parsed table;
- XLSX: one safe-id sheet projection;
- PDF: pinned pypdf page-text projection when complete; legacy heuristic
  preview remains partial and is not coverage authority;
- DOCX: partial body text projection only.

## Storage and access

- ArtifactStore type: `private_normalized_source_payload_v0`;
- visibility: `private_case`;
- backend: `project_artifact_payload`;
- access policy: `requires_gate2_resolver=true`;
- inherits case/chat/user/workspace scope, retention, expiry and purge cascade;
- forbidden backends: `openwebui_chat`, `openwebui_knowledge`, vector stores.

Safe reports may expose counts, format status and reason codes only. Raw normalized projection, source-value index, filenames, file ids, paths, account values and personal data are forbidden in chat/report output.

## Stability

Payload refs/checksums are deterministic for unchanged run scope, logical identity, parser projection and source checksum. Legacy records are never mutated in place; a re-slice creates new artifacts.

## Status

`GATE1_FULL_SOURCE_PAYLOAD_CONTRACT_READY`

## PDF text-layer Slice 1 runtime (2026-07-10)

The extraction-grade PDF path now reuses this artifact type with nested
`pdf_text_layer_projection_v0` and satisfies the format-specific contract in
`BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md`. The separate heuristic profiler
still produces only a compatibility preview and never becomes coverage
authority.

For PDF, `parser_completeness_status=complete` means complete for the declared,
pinned text-layer projection. It does not mean all visible page content,
semantic reading order, or true table structure is complete. The payload must
therefore carry independent:

- `text_layer_projection_status`;
- `visible_content_coverage_status`;
- `semantic_reconstruction_status`.

All declared pages must be inventoried, ordered and accounted. Page-local
fragment/span/value refs, page checksums and the parent payload checksum must
reproduce. Extraction errors, unresolved material font/CMap/operator decoding,
hidden caps, budget overflow or unaccounted refs keep the payload partial or
blocked. Mixed text/image PDFs may have a complete text-layer projection while
visible-content coverage remains `partial_out_of_scope`.

No PDF payload may use OCR/VLM or page rendering for extraction. Image-only
documents remain unsupported. Runtime, bundled dependency, synthetic and
controlled customer proofs have passed for page-text capability only.

```text
PDF_TEXT_LAYER_PAYLOAD_CONTRACT_READY
PDF_TEXT_LAYER_PAYLOAD_RUNTIME_IMPLEMENTED
PDF_TEXT_LAYER_LAYOUT_TABLE_RUNTIME_DEFERRED
```
