# Broker Reports PDF Normalization Acceptance v1

Status: implemented for the compact PDF dual-write shadow.

Schema id: `broker_reports_pdf_normalization_acceptance_v1`.

## Decision scope

The record is the safe acceptance act for one PDF document in one normalization run. It references the original PDF artifact and the persisted compact artifact. It contains metrics, refs, counts, statuses and reason codes, never raw customer values.

Allowed decisions:

- `accepted_complete`;
- `accepted_with_explicit_blocked_tables`;
- `human_review_required`;
- `blocked`.

Explicit blocked table decisions remain visible and may legitimately produce `accepted_with_explicit_blocked_tables`.

## Independent gates

1. `structural_correctness` — compact contract and checksums validate.
2. `provenance_correctness` — each selected evidence row has word/page/region and value/text checksum bindings plus the source checksum manifest.
3. `source_ref_accounting` — registered and accepted source refs are equal, without unexpected or unaccounted refs.
4. `storage_proportionality` — original PDF + compact + measured acceptance core stays within the configured 750,000-byte engineering envelope.
5. `reproducibility` — a second factory build is byte-identical.
6. `llm_projection_readiness` — the local compact-to-v0 adapter is accepted by the unchanged `TableProjectionValidator`.
7. `artifact_classification` — original/compact/acceptance/current projection/forensic working-state roles are complete.
8. `cleanup_readiness` — lifecycle intent is explicit; physical cleanup remains deferred and disabled in Goal 1.

No gate substitutes for another. A provenance pass cannot hide a storage failure, and storage success cannot hide a source-ref mismatch.

## Byte metrics

The record measures canonical JSON and gzip level 9 for the full forensic payload, normalized units, current table projections and compact artifact. It also records visible UTF-8 text bytes, duplicate-visible-text ratio, permanent and temporary totals, and ratios to source PDF and visible text.

`acceptance_record_core_bytes` is deliberately defined as canonical acceptance JSON with its self-size, permanent-total and checksum fields excluded/zeroed. This avoids a recursive self-size definition. The intended permanent total is original PDF + compact canonical JSON + that measured core.

The 22 MB full parser payload and normalized units are classified as temporary parser working/debug state. Existing table projections stay permanent only during migration because current Gate 2 still selects them.

## Persistence and guards

The acceptance record is `safe_internal` in `project_artifact_store`. It carries only safe metrics and opaque refs. It asserts no Knowledge/RAG/vector, OCR/VLM, raster rendering, provider-PDF transport, artifact deletion or Gate 2 selection change.
