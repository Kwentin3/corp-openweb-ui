# Broker Reports Gate 1 Document Source Eligibility Contract v0

Status: implemented in `services/broker-reports-gate1-proof/`.

## Purpose

Gate 1 must not treat every uploaded document as Gate 2 source evidence.
After profiling, taxonomy, blockers and optional validated
`document_metadata_passport_v0` records, Gate 1 emits an explicit
`document_source_eligibility_v0` compatibility artifact and a Gate 2 handoff
decision.

As of the 2026-07-09 domain-ingestion refactor, this artifact is not the
source of truth for complete Gate 1 ingestion/source readiness. The source of
truth is:

- `gate1_issue_ledger_v0`;
- `document_usage_classification_v0`;
- `domain_context_packet_v0`.

Gate 1 ingests every readable document and carries unresolved issues forward.
PDF/HTML source-role uncertainty, semantic duplicate selection and unanswered
questions do not stop domain ingestion.

Gate 1 still does not run source-fact extraction, tax calculation,
declaration generation, XLS/XLSX export, OCR, VLM or Knowledge upload.

## Per-Document Fields

Each eligibility entry contains:

- `document_id`
- `normalization_run_id`
- `source_eligibility`
- `can_enter_gate2`
- `reason_codes`
- `blocker_refs`
- `review_action`
- `ocr_policy_status`
- `source_role_policy_status`
- `document_metadata_passport_status`
- `document_metadata_passport_confidence`
- `document_metadata_passport_basis`
- `duplicate_auto_resolution`
- `clarification_criticality_basis`
- `included_in_reduced_subset`
- `exclusion_is_terminal`
- `requires_specialist_decision`

`clarification_criticality_basis` contains:

- `criticality_refinement_enabled`
- `unresolved_critical_fields`
- `unresolved_clarifying_fields`
- `unresolved_non_critical_fields`
- `unresolved_critical_count`
- `unresolved_clarifying_count`
- `unresolved_non_critical_count`
- `can_proceed_with_warning`
- `source_evidence_available`
- `period_scope_basis`

`duplicate_auto_resolution` is empty unless deterministic code resolved an
exact duplicate group. When present it contains only safe audit metadata:

- `auto_resolved`
- `auto_resolution_policy`
- `duplicate_kind`
- `duplicate_group_id`
- `canonical_document_id`
- `is_canonical`
- `excluded_document_ids`
- `canonical_selection_basis`
- safe reason codes and safe basis hashes

## Source Eligibility Statuses

Allowed `source_eligibility` values:

- `accepted_for_gate2`
- `accepted_as_source_candidate_for_gate2`
- `metadata_review_required`
- `source_policy_review_required`
- `duplicate_needs_canonical_choice`
- `methodology_or_output_artifact`
- `outside_case_scope`
- `requires_ocr_before_gate2`
- `unsupported_format`
- `excluded_from_gate2`

Legacy stored artifacts may contain older review names. New domain-ingestion
decisions should avoid `source_policy_review_required` as a Gate 1/Gate 1.5
ingestion blocker; PDF/HTML uncertainty is represented in
`gate1_issue_ledger_v0` as `source_role_policy_uncertainty`.

## Gate 2 Handoff Modes

Allowed `handoff_mode` values:

- `full_package_ready_for_gate2`
- `reduced_subset_ready_for_gate2`
- `gate2_blocked_requires_metadata_review`
- `gate2_blocked_requires_policy_review`
- `gate2_blocked_requires_duplicate_resolution`
- `gate2_blocked_requires_ocr`
- `gate2_blocked_no_eligible_sources`

`gate2_blocked_requires_review` is legacy-only and must not be emitted by the
passport-based v2 decision chain when a more specific blocker category exists.

When clarification criticality refinement is enabled:

- unresolved critical metadata gaps block Gate 2 with
  `gate2_blocked_requires_metadata_review`;
- unresolved clarifying or non-critical metadata gaps do not block Gate 2 when
  source-role evidence is sufficient and at least one source document is
  eligible;
- `reduced_subset_ready_for_gate2` is allowed only when included documents are
  valid and remaining gaps are warning/deferred gaps;
- no ready mode may be emitted when no eligible source document exists;
- OCR-required unreadable documents remain blocking before source extraction;
- source-policy uncertainty is carried forward as an issue and must not block
  Gate 1 ingestion or readable source extraction;
- semantic duplicate canonical choice is carried forward as an issue and may
  block consolidation/declaration-support, not ingestion;
- exact duplicates do not create a user question when the file hash is
  identical, the passport/metadata basis is equivalent and source role/status
  is equivalent. Deterministic code selects one canonical document and excludes
  non-canonical exact duplicates from Gate 2 refs.

Exact duplicate canonical selection order:

1. later document/report `created_at` from the passport when available;
2. later upload/ingest timestamp when available;
3. stable safe document id tie-breaker.

Period scope policy:

- document/report period, case/tax year, declaration/output period and
  operation-date evidence are separate concepts;
- `missing_period` is critical only when it prevents safe Gate 2 source
  handoff;
- case/tax-year scope, broker/provider/case scope, source-role evidence,
  source table/date evidence or later Gate 2 operation-date validation can
  downgrade missing document period to a warning/deferred question;
- declaration/output-only period context is deferred to declaration/output
  review and does not block Gate 2 source refs;
- no ready mode is allowed when there is no eligible source document.

Legacy `gate2_handoff_status` remains present for compatibility:

- `ready_with_safe_refs` for full package handoff
- `ready_with_reduced_subset` for validated reduced subset handoff
- `blocked` when no eligible Gate 2 source subset exists

## Clarification Resolution Input

`document_source_eligibility_v0` remains the deterministic owner of Gate 2
eligibility decisions. `gate1_clarification_resolution_v0` artifacts can be
used only as audited metadata overrides during a rerun:

- they do not mutate the original `document_metadata_passport_v0`;
- they do not bypass passport validation;
- they can clear missing metadata fields only when `validation_status=passed`
  and `usable_by_source_eligibility_v2=true`;
- duplicate answers can select the canonical document, while non-canonical
  duplicates remain excluded from Gate 2;
- the LLM clarification request generator cannot promote documents.

## OCR Policy Contract

Gate 1 supports OCR policy status only. It does not execute OCR.

Allowed `ocr_policy_status` values:

- `disabled`
- `enabled-not-executed`
- `required-before-gate2`
- `manual-review-only`

Raster or scan-like documents are not included in Gate 2 refs while OCR is not
executed. They receive `requires_ocr_before_gate2` and are routed to future OCR
or specialist review.

Text-layer PDFs must not be routed to OCR only because the PDF also contains
images, logos or signatures. Gate 1 distinguishes:

- `text_layer_pdf`;
- `mixed_pdf_with_text`;
- `raster_pdf_or_image_only`;
- `pdf_requires_parser_review`.

Only PDFs without detected text layer are eligible for
`requires_ocr_before_gate2`. PDFs with a detected text layer but insufficient
taxonomy evidence remain reviewable source candidates rather than OCR-required
documents.

HTML broker reports must preserve table evidence as private bounded table
slices when `<table>` structures are present. The chat-visible report may show
only counts and eligibility summaries; table rows remain private ArtifactStore
payloads.

## PDF/HTML Source Role Policy Compatibility

PDF/HTML broker reports are ingested when readable. Gate 1 distinguishes:

- text-layer PDF or mixed PDF with text evidence;
- raster/image-only PDF requiring OCR before Gate 2;
- HTML/PDF with table/text evidence but no explicit source-role policy;
- methodology/output artifacts;
- duplicates and canonical-choice candidates;
- unknown-role documents.

For PDF/HTML documents with text/table evidence and a source-like role signal,
Gate 1 emits an issue-ledger entry instead of blocking on source-role policy:

- `issue_type=source_role_policy_uncertainty`;
- source extraction may continue with issue context when the document is
  readable;
- consolidation/declaration-support must still respect the issue.

In the customer-authorized private package mode, safe registry role hints may be
used as classification hints only when the request explicitly enables
private-registry role hints; they do not by themselves decide final document
use.

## Reduced Subset Rule

A reduced subset is valid only when:

- at least one document has `can_enter_gate2=true`;
- every included document has `included_in_reduced_subset=true`;
- no included document has a terminal Gate 2 blocker;
- excluded, OCR, duplicate and issue-context documents are represented
  separately in handoff/domain-context refs.

The reduced subset is a primary source-extraction compatibility subset. It is
not the full next-stage source-fact input. Downstream source-fact extraction
must consume `domain_context_packet_v0.next_stage_refs` and
`gate2_handoff_v0.next_stage_refs` to see primary, secondary, duplicate,
cross-check, declaration-support and audit refs.

Terminal-blocker documents may remain persisted under retention, but they must
not be passed as Gate 2 private slice refs.

## ArtifactStore Handoff Payload

`gate2_handoff_v0` contains opaque ArtifactStore refs, not chat JSON:

- `eligibility_ref`
- `included_document_refs`
- `excluded_document_refs`
- `pending_review_refs`
- `source_policy_review_refs`
- `metadata_review_refs`
- `ocr_required_refs`
- `duplicate_review_refs`
- `accepted_source_candidate_refs`
- `private_slice_refs` for included documents only
- `clarification_resolution_refs` for private answer artifacts consumed by the
  eligibility rerun, when present
- `reason_codes`
- `decision_status_counts`
- `handoff_blocker_counts`
- `handoff_mode`
- `reduced_subset_validated`
- `criticality_refinement_enabled`
- `critical_metadata_review_document_ids`
- `advisory_metadata_review_document_ids`
- `warning_document_ids`
- `can_proceed_with_warnings`
- `warning_counts`
- `auto_resolved_duplicate_document_ids`
- `auto_canonical_duplicate_groups`
- `next_stage_refs`
- `next_stage_ref_summary`
- `document_issue_refs`
- `private_slice_refs_by_next_stage_bucket`

Private payloads remain resolver-gated and are not stored in Knowledge.
