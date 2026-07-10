# OpenWebUI Broker Reports Gate 1 Blocking Policy Refinement

Date: 2026-07-09

Repository cwd: `corp-openweb ui` repository root

## Result

Gate 1 / Gate 1.5 blocking policy was refined so a clarification can block only the pipeline stage it actually affects.

Proven statuses:

- `GATE1_DUPLICATE_AUTO_CANONICAL_POLICY_READY`
- `GATE1_PERIOD_SCOPE_POLICY_REFINED`
- `GATE1_BLOCKING_POLICY_REFINED`
- `GATE1_BLOCKING_POLICY_SYNTHETIC_PASSED`
- `CASE_GROUP_002_BLOCKING_POLICY_RERUN_READY`
- `CASE_GROUP_002_ACTIONABLE_CRITICAL_QUESTIONS_REDUCED`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `CASE_GROUP_002_GATE2_HANDOFF_BLOCKED_BY_TRUE_CRITICAL_QUESTIONS`

Not proven and intentionally not claimed:

- `CASE_GROUP_002_HANDOFF_READY_WITH_WARNINGS`
- `READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF`

Gate 2 source fact extraction, tax calculation, declaration generation, XLS/XLSX generation, OCR, and VLM were not run.

## What Changed

Exact duplicates are now auto-canonicalized only when all deterministic checks agree:

- identical `sha256`;
- equivalent passport metadata basis;
- equivalent source role/status basis.

Canonical selection is deterministic:

1. later document/report `created_at` when available;
2. later upload/ingest timestamp;
3. stable safe document id tie-breaker.

Non-canonical exact duplicates are excluded from Gate 2 refs and recorded in safe audit metadata. Semantic duplicates remain critical because they can double count source facts.

Period criticality now separates:

- document report period;
- case/tax-year scope;
- declaration/output period;
- operation/table/date evidence that can be validated during Gate 2 extraction.

`missing_period` is critical only when it prevents safe Gate 2 handoff. If case/provider scope or later operation-date evidence is available, it stays visible as a clarification/deferred note, not a Gate 2 blocker.

Contracts and artifacts now carry deterministic policy fields:

- `dependency_stage`;
- `blocking_reason_category`;
- `auto_resolution_policy`.

LLM output cannot override these policy fields.

## Local Verification

Commands run in PowerShell:

- `python -m py_compile services/broker-reports-gate1-proof/broker_reports_gate1/clarification.py services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_clarification_loop.py`
- `python services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_clarification_loop.py`
  - 12 tests passed.
- `python -m unittest discover -s services/broker-reports-gate1-proof/tests -v`
  - 88 tests passed.
- `python -m compileall services/broker-reports-gate1-proof`
- `python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py`
- `python -m py_compile services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py`
- `python -m py_compile services/broker-reports-gate1-proof/scripts/live_case_group_process_false_gate1_run.py`

Relevant behavioral tests include:

- exact duplicate auto-canonicalization without a user question;
- semantic duplicate remains critical;
- period without alternative scope remains critical;
- period with case scope / operation-date evidence is deferred;
- unresolved critical basis fields are not hidden by other metadata gaps;
- LLM cannot override deterministic criticality/blocking fields;
- blocked handoff does not expose private refs.

## Runtime Deploy

Live OpenWebUI Function/Prompt update passed.

- Function id: `broker_reports_gate1_pipe`
- Bundle/live sha256: `5f137a65b0033b3bf6326863038ea225937212237cc81f9f3fb17916af2574a1`
- Passport schema hash: `a5f7bd86e6dcf9655748287f08768bc04acf0cd1ca1643861ff2bf1b515d2894`
- Clarification schema hash: `23896f7b816e7a09cf6a99667820126947175a14c5c972aa9a8e68e011a810f7`
- Passport prompt hash: `7b93fcf0f29402520d7c774da559df3deab26953686cb8cef67fd1b803dc997d`
- Clarification prompt hash: `f16e07393070cb697fe76f1da2af2d800234b2cd0246669e290e90a0185757ac`

OpenWebUI was restarted after the update and reported healthy before live proof.

## Synthetic Proof

Command:

```powershell
python services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py --env-file .env --synthetic-fixture-mode blocking_policy --enable-llm-passport --passport-max-documents 10 --enable-clarification --settle-seconds 6
```

Result: `status=passed`.

Safe aggregate result:

- process=false uploads: 3;
- passport validator: 3 passed, 0 failed;
- clarification request: 7 questions total;
- critical: 1;
- clarifying: 5;
- non-critical: 1;
- critical gap: semantic `duplicate_canonical_choice=1`;
- `missing_period=2` stayed non-blocking/clarifying;
- Gate 1 no-RAG guards passed:
  - document rows delta: 0;
  - Knowledge rows delta: 0;
  - vector collections/files/size delta after upload/chat/delete: 0;
  - source uploads deleted and file rows returned to baseline.

Exact duplicate auto-canonicalization is proven by deterministic synthetic unit coverage. The live synthetic fixture intentionally retained a semantic duplicate, and it correctly remained a critical user/operator choice.

## case_group_002 Proof

Command:

```powershell
python services/broker-reports-gate1-proof/scripts/live_case_group_process_false_gate1_run.py --env-file .env --case-group-id case_group_002 --enable-llm-passport --passport-max-documents 40 --enable-clarification --settle-seconds 6 --cleanup-source-uploads
```

Final live run:

- `status=passed`;
- case id: `customer_case_group_002_process_false_gate1_20260709144502`;
- files total: 16;
- process status values: all `null`;
- passport validator: 16 passed, 0 failed;
- clarification validator: passed;
- ArtifactStore records for the case: 135;
- retention mode: `customer_approved_test` for all 135 records;
- OpenWebUI Knowledge backend records: 0;
- cleanup deleted 16 source uploads.

Question count comparison:

- Original strict baseline: 35 questions.
- Previous refinement baseline: 25 questions, 6 critical:
  - `duplicate_canonical_choice=1`;
  - `missing_period=5`.
- Current final run: 10 questions:
  - critical: 2;
  - clarifying: 6;
  - non-critical: 2.

Current question/gap types:

- `duplicate_canonical_choice=1` critical;
- `unclear_document_role=1` critical;
- `missing_period=1` clarifying, not blocking;
- `missing_account_or_contract=3` clarifying;
- `missing_broker_client_metadata=1` clarifying;
- `other_metadata_conflict=3`, split into clarifying/non-critical by impact.

The period policy is now behaving as intended. Period-scope reason-code counts in source eligibility:

- `broker_provider_provides_scope=7`;
- `case_context_provides_scope=7`;
- `document_period_missing_but_not_blocking=7`;
- `period_deferred_to_gate2_operation_dates=3`;
- `source_table_dates_available=3`.

The final `missing_period` question had:

- `criticality=clarifying`;
- `blocks_gate2=false`;
- `dependency_stage=declaration_model`;
- `blocking_reason_category=declaration_context`;
- `auto_resolution_policy=case_context_allows_warning`.

The duplicate in `case_group_002` was not exact:

- auto-resolved exact duplicate groups: 0;
- auto-resolved exact duplicate documents: 0;
- semantic duplicate remained `duplicate_needs_canonical_choice=1`;
- reason codes included `semantic_duplicate_requires_user_choice` and `duplicate_can_double_count_source_facts`.

Final Gate 2 handoff:

- `handoff_status=blocked`;
- `handoff_mode=gate2_blocked_requires_metadata_review`;
- included document refs in payload: 0;
- included private refs in payload: 0.

Handoff blocker counts:

- `critical_metadata_review_required=1`;
- `duplicate_needs_canonical_choice=1`;
- `source_policy_review_required=8`;
- `excluded_from_gate2=4`;
- `requires_ocr_before_gate2=0`;
- `auto_resolved_exact_duplicate_groups=0`;
- `auto_resolved_exact_duplicate_documents=0`.

There are 2 accepted-for-Gate-2 documents, but the handoff correctly does not proceed while true blockers remain.

## No-RAG / Privacy Guard

Final `case_group_002` counters:

- document rows delta after chat: 0;
- Knowledge rows delta after chat: 0;
- vector collections delta after chat: 0;
- vector dir delta after chat: 0;
- vector file delta after chat: 0;
- vector size delta after chat: 0;
- source file rows returned to baseline after cleanup;
- private refs were not present in chat-visible report;
- safety flags remained false for source fact extraction, tax, declaration, XLS/XLSX, OCR, and Knowledge loading.

## Remaining Blockers

Gate 2 is still blocked, but not by period over-blocking.

Remaining actionable blockers:

- user/operator must choose the canonical semantic duplicate document;
- user/operator must resolve one unclear document role before source eligibility can safely include that document;
- specialist/source-policy review remains required for PDF/HTML source-role acceptance because this proof used `pdf_html_source_policy=review_required`.

Next step: answer the two critical Gate 1 clarification questions and make/record the source-policy decision for PDF/HTML source roles before running any Gate 2 source-fact proof.
