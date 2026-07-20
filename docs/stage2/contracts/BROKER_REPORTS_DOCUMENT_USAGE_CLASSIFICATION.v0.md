# Broker Reports Document Usage Classification Contract v0

Status: `GATE1_DOCUMENT_USAGE_CLASSIFICATION_CONTRACT_READY`
Artifact: `document_usage_classification_v0`

## Purpose

`document_usage_classification_v0` classifies each ingested document by downstream stage usage. It does not decide final tax/declaration use.

This artifact is exhaustive for ingested documents: every safe document ref
from `document_inventory_v0` must have one classification entry. It describes
stage readiness; it does not choose the primary reduced subset.

## Entry Fields

Each entry contains:

- `document_ref`
- `inferred_role`
- `source_eligibility_compat_status`
- `usage_modes`
- `issue_refs`
- `warning_issue_refs`
- `issue_refs_by_stage`
- `readiness_by_stage`
- `private_payload_access`
- `raw_private_payload_in_classification`
- `deterministic_basis`

## Usage Modes

Initial usage modes:

- `ingested`
- `source_extraction_candidate`
- `cross_check_candidate`
- `consolidation_candidate`
- `declaration_support_reference`
- `audit_reference`
- `archive_lineage`

Readable PDF/HTML documents with source-like evidence can be `source_extraction_candidate` even when source-role policy is uncertain. That uncertainty must point to `gate1_issue_ledger_v0`.

## Stage Readiness

`readiness_by_stage` covers:

- `domain_ingestion`
- `source_fact_extraction`
- `cross_check`
- `consolidation`
- `declaration_support`

Allowed values:

- `completed`
- `ready`
- `ready_with_issues`
- `blocked_unreadable`
- `blocked_unresolved_issues`
- `not_applicable`
- `not_applicable_lineage_only`

An accepted ZIP container is `archive_lineage`, not a source-extraction
candidate. Its source-fact and interpretation stages are
`not_applicable_lineage_only`; it remains an `audit_reference`. Promoted PDF/XML
members are independent source records and retain their ordinary readiness.

Semantic duplicates and unclear roles may be ready for source extraction but blocked for consolidation/declaration-support.

`source_fact_extraction=ready` and `source_fact_extraction=ready_with_issues`
mean the document is source-fact-ready for the next stage with the stated issue
context. Such a document may later be placed in the primary, secondary,
duplicate/non-primary, cross-check, declaration-support or audit bucket by
`domain_context_packet_v0`. Reduced-subset inclusion is therefore not required
for source readiness.

No-loss invariant:

- every classification entry must flow into `domain_context_packet_v0.document_refs`;
- every `ready` or `ready_with_issues` source-fact entry must flow into
  `domain_context_packet_v0.next_stage_refs.source_fact_ready_refs`;
- the same ref must then be classified into an explicit next-stage bucket, not
  omitted because it is non-primary, duplicate, warning-only or audit-only.

## Privacy

The artifact may reference safe document ids and safe issue ids only. Private payload access must be expressed as `resolver_required`; raw private payload must not be embedded.
