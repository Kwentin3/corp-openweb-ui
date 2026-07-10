# Broker Reports Domain Context Packet Contract v0

Status: `GATE1_DOMAIN_CONTEXT_PACKET_CONTRACT_READY`
Artifact: `domain_context_packet_v0`

## Purpose

`domain_context_packet_v0` is the safe handoff packet for downstream source-fact extraction with issue context. It is the Gate 1 domain-ingestion output.

It is the canonical next-stage context. `gate2_handoff_v0.included_document_refs`
and `included_in_reduced_subset` are primary-source compatibility refs only;
they are not the complete list of readable/source-ready documents.

## Required Fields

- `schema_version`
- `packet_id`
- `normalization_run_id`
- `domain_ingestion_status`
- `document_refs`
- `artifact_logical_refs`
- `issue_ledger_id`
- `document_usage_classification_id`
- `unresolved_issue_refs`
- `unresolved_issue_summary`
- `stage_readiness`
- `usage_summary`
- `next_stage_refs`
- `next_stage_ref_summary`
- `document_issue_refs`
- `known_assumptions`
- `forbidden_assumptions`
- `downstream_llm_instructions`
- `private_slice_access`
- `vector_knowledge_guard`
- `created_at`

## Stage Readiness

`stage_readiness.source_fact_extraction` may be:

- `ready`
- `ready_with_issue_context`
- `blocked`
- `blocked_no_documents`

When `ready_with_issue_context`, downstream extraction may start but must carry unresolved issue refs forward.

Full/reduced compatibility handoff status is separate from source-fact input
readiness. When DCP source-fact readiness is `ready` or
`ready_with_issue_context`, the ArtifactStore handoff manifest may remain
resolver-readable even if its compatibility `handoff_status` is blocked by
metadata needed only for later consolidation/declaration stages. The payload
must retain that blocker; resolver readability does not resolve it.

## Next-Stage Refs

`next_stage_refs` contains safe document refs only. Required buckets:

- `source_fact_ready_refs`
- `primary_source_extraction_refs`
- `secondary_source_extraction_refs`
- `cross_check_refs`
- `declaration_support_refs`
- `audit_reference_refs`
- `duplicate_or_non_primary_refs`
- `source_ready_not_primary_refs`
- `dropped_source_ready_refs`

No readable source-ready document may be silently lost:

- every `document_usage_classification_v0` entry with
  `readiness_by_stage.source_fact_extraction` equal to `ready` or
  `ready_with_issues` must appear in `source_fact_ready_refs`;
- every `source_fact_ready_refs` document must also appear in one of
  `primary_source_extraction_refs`, `secondary_source_extraction_refs`,
  `duplicate_or_non_primary_refs` or `audit_reference_refs`;
- `dropped_source_ready_refs` must be empty in a valid packet.

Bucket meaning:

- `primary_source_extraction_refs` are source-ready docs selected for the
  reduced/full primary source extraction path.
- `secondary_source_extraction_refs` are source-ready docs that may be read
  with issue context but are not primary refs.
- `cross_check_refs` are docs usable for reconciliation/checking.
- `declaration_support_refs` are docs that may later support declaration
  assembly, subject to their issues.
- `audit_reference_refs` are docs retained for traceability/audit context.
- `duplicate_or_non_primary_refs` are source-ready duplicates or non-primary
  refs that must not vanish just because they are outside the reduced subset.

`next_stage_ref_summary` mirrors these buckets as counts. It is safe for chat
and reports.

`document_issue_refs` maps each safe `document_ref` to safe issue ids from
`gate1_issue_ledger_v0`. It is the carry-forward bridge from issue ledger to
source extraction.

Unit-specific issue scope is derived later by intersecting ledger
`evidence_refs` with the selected slice/table/row/cell/value/text refs. If no
intersection exists, the issue remains document-scoped. The model cannot choose
or change this scope.

## Private Slice Access Contract

`private_slice_access` must declare:

- `source_unit_schema_version=source_unit_provenance_v0`;
- `table_slice_schema_version=private_normalized_table_slice_v0`;
- `text_slice_schema_version=private_normalized_text_slice_v0`;
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`;
- `row_segment_coverage_policy=source_unit_coverage_v0`;
- `dry_run_package_builder=Gate2InputReadinessFactory.create`;
- `raw_private_payload_in_packet=false`.

The DCP carries only safe contract metadata. Actual rows, cells, values and text
remain in resolver-gated `private_case` artifacts. Every downstream source-fact
package must use the stored refs; it must not mint replacement refs or parse
chat text.

## Forbidden Assumptions

The packet must explicitly prohibit:

- treating unanswered questions as resolved;
- treating PDF/HTML source-role uncertainty as a Gate 1 ingestion blocker;
- choosing final document use without deterministic stage policy;
- treating the reduced subset as the only next-stage document context;
- loading customer documents to Knowledge or vector store.

## Privacy and RAG Guard

`private_slice_access.raw_private_payload_in_packet=false`.

`vector_knowledge_guard` must keep:

- `customer_docs_loaded_to_knowledge=false`;
- `vectorization_performed=false`;
- `rag_used_for_gate1=false`.
