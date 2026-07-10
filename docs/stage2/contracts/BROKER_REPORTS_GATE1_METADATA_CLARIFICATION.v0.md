# Broker Reports Gate 1 Metadata Clarification Contracts v0

Statuses:

- `GATE1_METADATA_GAP_REPORT_CONTRACT_READY`
- `GATE1_CLARIFICATION_REQUEST_CONTRACT_READY`
- `GATE1_CLARIFICATION_RESOLUTION_CONTRACT_READY`
- `GATE1_CLARIFICATION_CRITICALITY_CONTRACT_READY`

## Boundary

This contract adds a human-in-the-loop layer after passport-based source eligibility v2.

As of the 2026-07-09 domain-ingestion refactor, unanswered clarification
questions do not stop Gate 1 normalization or domain ingestion. They affect
stage-specific downstream readiness and must be carried in
`gate1_issue_ledger_v0` and `domain_context_packet_v0`.

Deterministic code owns:

- missing metadata detection;
- criticality, blocking scope and ask policy assignment;
- duplicate canonical-choice detection;
- safe gap report construction;
- answer validation;
- source eligibility v2 rerun;
- Gate 2 handoff rerun.

The LLM owns only wording safe questions from an already-safe gap report.
It cannot change `criticality`, `blocking_scope`, `blocks_gate2`,
`dependency_stage`, `blocking_reason_category`, `auto_resolution_policy`,
`resolution_required`, `can_proceed_with_warning`, `ask_policy`,
`answer_impact`, `priority`, `severity`, `required` or `reason_codes`.

The LLM must not:

- read raw documents;
- invent blockers;
- decide source eligibility;
- promote documents into Gate 2;
- extract source facts;
- calculate tax;
- generate declarations or XLS/XLSX;
- perform OCR/VLM.

## `gate1_metadata_gap_report_v0`

Producer: deterministic Gate 1 code.

Inputs:

- `document_metadata_passport_v0`;
- `document_source_eligibility_v0`;
- `gate2_handoff_v0`;
- safe blocker refs.

Required shape:

```json
{
  "schema_version": "gate1_metadata_gap_report_v0",
  "gap_report_id": "gapreport_<opaque>",
  "normalization_run_id": "normrun_<opaque>",
  "decision_version": "passport_based_source_eligibility_v2",
  "handoff_status": "blocked",
  "handoff_mode": "gate2_blocked_requires_metadata_review",
  "criticality_refinement_enabled": true,
  "gaps": [],
  "question_stubs": [],
  "question_groups": {
    "critical_questions_for_continuation": [],
    "useful_clarifications": [],
    "deferred_non_critical_notes": []
  },
  "summary": {}
}
```

Each gap describes:

- target safe document refs;
- gap type;
- source eligibility status that caused the gap;
- missing metadata fields;
- conflict flags;
- safe evidence refs;
- what the gap blocks;
- `criticality`: `critical`, `clarifying` or `non_critical`;
- `blocking_scope`: `gate2_handoff`, `source_eligibility`,
  `declaration_model` or `audit_only`;
- `dependency_stage`: `normalization`, `gate2_handoff`,
  `gate2_source_fact_extraction`, `declaration_model`, `output_review` or
  `audit_only`;
- `blocking_reason_category`: `source_scope`, `duplicate_risk`,
  `role_ambiguity`, `declaration_context`, `audit_quality` or
  `display_metadata`;
- `auto_resolution_policy`: `none`, `exact_duplicate_latest_wins`,
  `case_context_allows_warning` or `defer_to_gate2_dates`;
- `blocks_gate2`;
- `resolution_required`;
- `can_proceed_with_warning`;
- `ask_policy`: `ask_now`, `ask_if_user_available`, `defer` or `do_not_ask`;
- `answer_impact`: `unblocks_gate2`, `improves_confidence`,
  `adds_audit_context` or `specialist_note_only`;
- `reason_codes`;
- `safe_explanation`;
- whether it is resolvable by user/operator answer;
- answer type and allowed format.

Criticality policy:

- A question may block Gate 2 only when it affects whether a document is safe
  source evidence, no deterministic/case-level alternative basis exists and no
  safe deferred validation stage exists.
- `unclear_document_role` is critical when the document role is needed before
  source eligibility can be decided.
- `duplicate_canonical_choice` is critical only for semantic duplicates:
  different hashes, conflicting metadata/period/source roles or unclear
  same-source evidence. Exact duplicates are auto-canonicalized by deterministic
  code and must not create a user question.
- `missing_period` is critical only when it prevents safe Gate 2 source
  handoff. It is clarifying or non-critical when case/tax-year scope, broker or
  case scope, source-role evidence, later Gate 2 operation-date validation or
  declaration/output-only period context provides a safe alternative.
- `missing_account_or_contract` and `missing_broker_client_metadata` are
  normally clarifying unless they are required for source eligibility.
- `other_metadata_conflict` is split by impact: source-role, case-scope or
  duplicate conflicts may be critical; broker/client/account confidence
  improvement is clarifying; display metadata such as title, language or
  created-at uncertainty is non-critical/audit-only.
- `outside_scope_confirmation` is non-critical and excluded from user
  questions unless a deterministic reason code explicitly requires
  confirmation.
- skipped or unasked gaps are not resolved. They remain issue-ledger entries
  with unresolved status and are carried into the domain context packet.

Period reason codes:

- `period_required_for_gate2_scope`
- `period_deferred_to_gate2_operation_dates`
- `period_deferred_to_declaration_context`
- `case_tax_year_provides_scope`
- `case_context_provides_scope`
- `broker_provider_provides_scope`
- `source_table_dates_available`
- `document_period_missing_but_not_blocking`

Only unresolved critical gaps block Gate 2. Clarifying or non-critical gaps may
remain as warnings when at least one eligible source document exists; they must
not create a ready state when no eligible source documents exist.

Allowed `gap_type` values:

- `missing_period`;
- `missing_account_or_contract`;
- `unclear_document_role`;
- `missing_broker_client_metadata`;
- `duplicate_canonical_choice`;
- `outside_scope_confirmation`;
- `other_metadata_conflict`.

Privacy rule: no raw filenames, OpenWebUI file ids, private paths, source rows, full source text, account numbers or personal data.

## `gate1_clarification_request_v0`

Producer: LLM through OpenWebUI managed Prompt, then deterministic canonicalizer/validator.

Input to LLM:

- managed Prompt instruction;
- safe `gate1_metadata_gap_report_v0`;
- strict JSON schema;
- safe document refs and allowed question ids.

Each question contains:

- `question_id`;
- `target_document_refs`;
- `gap_type`;
- `question_text`;
- `answer_type`;
- `allowed_answer_format`;
- `required_for`;
- `why_asked`;
- `safe_evidence_refs`;
- `criticality`;
- `blocking_scope`;
- `dependency_stage`;
- `blocking_reason_category`;
- `auto_resolution_policy`;
- `blocks_gate2`;
- `resolution_required`;
- `can_proceed_with_warning`;
- `ask_policy`;
- `answer_impact`;
- `priority`;
- `severity`;
- `required`;
- `reason_codes`;
- `safe_explanation`.

The request also contains deterministic grouping:

- `question_groups.critical_questions_for_continuation`;
- `question_groups.useful_clarifications`;
- `question_groups.deferred_non_critical_notes`.

The compact Russian report renders those as:

- `Критично для продолжения`;
- `Желательно уточнить`;
- `Можно отложить`.

Allowed `answer_type` values:

- `text`;
- `date`;
- `date_range`;
- `single_choice`;
- `multi_choice`;
- `confirm_true_false`;
- `select_canonical_document`;
- `mark_as_outside_scope`;
- `mark_as_not_source`;
- `provide_account_or_contract`;
- `provide_report_period`.

The canonicalizer rebuilds the final request from deterministic question stubs.
LLM text may supply only `question_text` and `why_asked`; all deterministic
fields and `question_groups` are copied or rebuilt from the gap report.

## `gate1_clarification_resolution_v0`

Producer: deterministic answer ingestion path.

Source:

- `user_confirmed`;
- `operator_confirmed`.

Each resolution contains:

- `question_id`;
- `target_document_ref`;
- `resolved_field`;
- `answer_value`;
- `answer_type`;
- `answered_by`;
- `answered_at`;
- `source`;
- `validation_status`;
- `safe_audit_refs`;
- `usable_by_source_eligibility_v2`.

Storage rule:

- `gate1_metadata_gap_report_v0`: `safe_internal`;
- `gate1_clarification_request_v0`: `safe_internal`;
- `gate1_clarification_resolution_v0`: `private_case`, because answers can contain account or contract identifiers;
- raw LLM clarification output: `private_case`;
- no Knowledge/RAG backend is allowed.

## Rerun

Eligibility/domain-context rerun consumes validated resolutions only.

Supported deterministic effects:

- resolved period fields can clear `report_period_start` / `report_period_end` gaps;
- resolved account/contract can clear `account_or_contract_candidate` gaps;
- resolved role can clarify source/non-source/outside-scope state;
- duplicate canonical answer can exclude non-canonical duplicates and allow the chosen document to continue if no other blocker remains.

Rerun must not alter original passport records. It creates a new eligibility decision using passport data plus audited resolution basis.

Rerun must not mark skipped or unanswered questions as resolved. An issue can
move out of unresolved state only when a validated resolution artifact exists
for the question/gap.

When the rerun changes Gate 2 readiness, `gate2_handoff_v0` keeps
`private_slice_refs` scoped to included source documents only and carries
private answer artifacts separately as opaque `clarification_resolution_refs`.
