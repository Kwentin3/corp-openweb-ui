# Broker Reports PDF Compact Canonical Document v1

Status: implemented in Gate 1 dual-write shadow mode. The shadow is disabled by default.

Schema id: `broker_reports_pdf_compact_canonical_document_v1`.

## Purpose and authority

This private artifact is the bounded canonical PDF representation proposed for permanent retention. In Goal 1 it is not authoritative for Gate 2. The existing full parser payload and `broker_reports_normalized_table_projection_v0` remain authoritative during migration.

The artifact is built only through `PdfCompactCanonicalFactory.create()`. It consumes existing parser outputs and reuses their document, page, table, row, column, cell, word, source-value, bbox and checksum identities. It performs no semantic or business-domain analysis.

## Required document areas

| Area | Required content |
|---|---|
| Identity | `canonical_document_id`, `normalization_run_id`, `document_ref`, real `original_pdf_artifact_ref`, source SHA-256 and bytes. |
| Parser manifest | Parser/layout engines and versions, parser/config refs, table-detection policy and canonicalization policy. |
| Pages | Ordered page refs and ordinals, text/layout checksums, readiness, dimensions, rotation and coordinate space. |
| Table decisions | Exactly one ordered entry per detected table with bbox, current validation ref, decision path/status/reasons and reconstruction strategy. |
| Accepted tables | Ordered rows, columns and cells; counts; header hierarchy/repeated headers; spans; explicit current empty cells; source evidence. |
| Blocked tables | Identity, bbox, attempted path and reason codes; zero invented rows and cells. |
| Coverage | Exact table accounting, accepted source-ref count/set checksum, duplicate/unaccounted arrays and coverage checksum. |
| Roles and guards | Permanent/temporary lifecycle intent and all no-RAG/no-semantic/no-OCR guards. |

Rows, cells and selected source evidence use a `fields` plus `items` packed representation. This removes repeated JSON field names without dropping data. `source_value_index` deterministically maps each accepted `source_value_ref` to its evidence ordinal. The resolver reconstructs the named fields before returning a private value.

Sparse current table projections remain sparse: the builder preserves every current cell position, including every explicit empty cell, but does not invent cells for positions that the authoritative projection did not materialize.

## Validation and determinism

`PdfCompactCanonicalValidator` fails closed on:

- missing or duplicate table decisions;
- missing/duplicate/inconsistent source refs or owners;
- missing source words, bboxes or private values;
- duplicate/out-of-range row/column positions;
- table/source coverage or checksum mismatch;
- blocked tables containing rows/cells;
- a top-level unknown field;
- a forbidden field anywhere in the artifact;
- a guard that is not exactly `false`.

Canonical JSON uses UTF-8, sorted keys and compact separators. The checksum excludes only `canonical_document_checksum_ref`. Identical input, parser/config state and artifact refs produce identical bytes and checksum.

## Forbidden content

The validator rejects full char/glyph, word, line, block, vector and image inventories; parser fragments; full page text copies; raw crops; provider requests/outputs; business interpretation; tax calculation; full normalized projections; and any private full-source payload embedded under the compact artifact.

## Persistence

Visibility is `private_case`; backend is `project_artifact_payload`; access remains resolver-gated and bound to the original `source_file_ref_v0`. No Knowledge/RAG/vector backend is allowed.
