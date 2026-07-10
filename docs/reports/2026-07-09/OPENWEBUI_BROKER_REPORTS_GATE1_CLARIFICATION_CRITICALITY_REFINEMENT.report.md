# OpenWebUI Broker Reports Gate 1 Clarification Criticality Refinement

Date: 2026-07-09

## Statuses

- `GATE1_CLARIFICATION_CRITICALITY_CONTRACT_READY`
- `GATE1_GAP_BLOCKING_POLICY_REFINED`
- `GATE1_CLARIFICATION_GROUPED_QUESTIONS_READY`
- `GATE1_CLARIFICATION_CRITICALITY_SYNTHETIC_PASSED`
- `CASE_GROUP_002_CLARIFICATION_CRITICALITY_RERUN_READY`
- `CASE_GROUP_002_ACTIONABLE_CRITICAL_QUESTIONS_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `CASE_GROUP_002_GATE2_STILL_BLOCKED_ON_UNRESOLVED_CRITICAL_GAPS`

## Implemented Contract

Deterministic code now assigns every Gate 1 metadata gap/question:

- `criticality`
- `blocking_scope`
- `blocks_gate2`
- `resolution_required`
- `can_proceed_with_warning`
- `ask_policy`
- `answer_impact`
- `priority`
- `reason_codes`
- `safe_explanation`

Only unresolved `critical` gaps block Gate 2. `clarifying` and `non_critical`
gaps remain visible as warnings or deferred notes when source eligibility has a
valid path. The LLM can rewrite only `question_text` and `why_asked`; the
canonicalizer restores all deterministic fields from question stubs.

Compact report grouping is:

- `Критично для продолжения`
- `Желательно уточнить`
- `Можно отложить`

## Verification

Local tests:

```text
python -m unittest discover services\broker-reports-gate1-proof\tests
Ran 84 tests in 4.826s
OK
```

Bundle/prompt deploy:

- previous Function SHA256: `70f8ed9d70854e280718d76ed4d8621fe0de3797f322394cb454a2bee10ad670`
- live Function SHA256: `54fb06ea1b506cc86536799a0f47e9a837d736065f77236f64fbb8065a6ecafc`
- clarification schema hash: `39d710f4632b3c3af37aa962cf63ab6735a3f96c7e4b4669324df93b0a91e3bd`
- clarification prompt hash: `1a29b5e2f23695b0aecb136b3bf3377ee4acaa2066883038f82d735c5e6ad3ef`

Synthetic live run:

- command: `live_process_false_private_intake_smoke.py --synthetic-fixture-mode clarification_gap --enable-llm-passport --enable-clarification --clarification-synthetic-answers`
- status: `passed`
- criticality refinement: enabled
- gap counts: `critical=1`, `clarifying=1`, `non_critical=0`
- question counts: `critical=1`, `clarifying=1`, `non_critical=0`
- synthetic answers supplied only for critical `missing_period`
- usable resolutions: `2` period fields
- handoff after critical answer: `full_package_ready_for_gate2`
- document rows delta: `0`
- Knowledge rows delta: `0`
- vector delta after upload/chat/delete: `0`
- source upload cleanup: `1/1`

Synthetic local contract test covered the non-critical branch:

- `test_refined_gap_report_groups_critical_clarifying_and_noncritical_stubs`
- deterministic gap counts: `critical=1`, `clarifying=1`, `non_critical=2`
- outside-scope gap: non-critical and not emitted as a user question unless explicitly required
- LLM override test passed: deterministic criticality/blocking fields were restored by canonicalization

case_group_002 live run:

- command: `live_case_group_process_false_gate1_run.py --case-group-id case_group_002 --enable-llm-passport --enable-clarification --cleanup-source-uploads`
- status: `passed`
- files: `16`
- passports validated: `16/16`
- previous strict clarification baseline: `35` questions
- refined questions: `25`
- refined critical questions: `6`
- refined clarifying questions: `19`
- refined non-critical questions: `0`
- required questions: `6`
- no auto-resolution: `0` clarification resolutions
- handoff: `gate2_blocked_requires_metadata_review`
- reason: unresolved critical gaps remain; no Gate 2 source-fact extraction was run
- document rows delta: `0`
- Knowledge rows delta: `0`
- vector delta after upload/chat: `0`
- ArtifactStore records for case: `135`
- ArtifactStore records using `openwebui_knowledge`: `0`
- source upload cleanup: `16/16`

case_group_002 refined gap type counts:

- `duplicate_canonical_choice`: `1`
- `missing_period`: `5`
- `missing_account_or_contract`: `7`
- `missing_broker_client_metadata`: `6`
- `other_metadata_conflict`: `6`

Critical blocker counts:

- critical gaps total: `6`
- blocking gaps total: `6`
- advisory/clarifying gaps total: `19`

## Negative Scope Proof

Not performed:

- Gate 2 source-fact extraction
- trade/operation/dividend/coupon/cashflow extraction
- tax calculation
- declaration generation
- XLS/XLSX generation
- OCR/VLM
- ordinary processed upload
- Knowledge/RAG load for customer documents, slices, packages, clarifications or answers

All proof outputs above are aggregate counters, hashes and safe status labels.
No raw private document text, filenames, account numbers, personal data or
private paths are recorded in this report.
