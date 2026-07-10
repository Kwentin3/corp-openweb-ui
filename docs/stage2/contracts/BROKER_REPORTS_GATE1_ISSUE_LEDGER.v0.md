# Broker Reports Gate 1 Issue Ledger Contract v0

Status: `GATE1_ISSUE_LEDGER_CONTRACT_READY`
Artifact: `gate1_issue_ledger_v0`

## Purpose

`gate1_issue_ledger_v0` is the deterministic ledger for unresolved and resolved Gate 1 issues. It preserves ambiguity as issue context instead of collapsing uncertainty into a hidden stop/continue decision.

The ledger must not contain raw filenames, file ids, private paths, raw rows, raw text, account numbers or personal data.

## Producer

Deterministic Gate 1 code after profiling, taxonomy, passports, eligibility compatibility view and optional clarification stages.

The LLM does not decide:

- issue type;
- criticality;
- blocked stages;
- readiness;
- resolution state.

## Entry Fields

Each entry contains:

- `issue_id`
- `normalization_run_id`
- `issue_type`
- `target_document_refs`
- `criticality`
- `affected_stage`
- `blocked_stages`
- `stages_that_may_continue`
- `status`
- `unresolved_reason`
- `user_was_asked`
- `answer_supplied`
- `ask_policy`
- `resolution_refs`
- `evidence_refs`
- `blocker_refs`
- `reason_codes`
- `provenance`
- `created_at`
- `updated_at`
- `safe_explanation`

Allowed `status` values:

- `unresolved`
- `resolved`

Skipped/unasked questions remain `status=unresolved` with `unresolved_reason=skipped_question`.

## Carry-Forward Contract

The ledger is not a terminal stop list. Unresolved issues must be carried
forward to downstream stages that may continue with issue context.

Required carry-forward links:

- `document_usage_classification_v0.issue_refs`
- `document_usage_classification_v0.warning_issue_refs`
- `domain_context_packet_v0.unresolved_issue_refs`
- `domain_context_packet_v0.document_issue_refs`
- `gate2_handoff_v0.document_issue_refs`

Every issue ref in those artifacts must resolve to a ledger entry. Skipped,
unanswered and warning/deferred questions remain visible by issue id even when
source extraction may start.

## Issue Types

Initial issue types:

- `readability_blocker`
- `no_files`
- `normalization_warning`
- `metadata_gap`
- `unclear_document_role`
- `duplicate_canonical_choice`
- `source_role_policy_uncertainty`
- `outside_scope_confirmation`

PDF/HTML source-role uncertainty is represented as `source_role_policy_uncertainty`; it is not an ingestion blocker.

## Summary

The artifact summary contains:

- `issues_total`
- `unresolved_issues_total`
- `resolved_issues_total`
- `skipped_unresolved_issues_total`
- `status_counts`
- `issue_type_counts`
- `criticality_counts`
- `affected_stage_counts`
- stage blocking totals.
