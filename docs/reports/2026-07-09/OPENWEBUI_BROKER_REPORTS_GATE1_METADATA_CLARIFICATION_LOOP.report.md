# OpenWebUI Broker Reports Gate 1 Metadata Clarification Loop Report

Date: 2026-07-09

Status: passed.

## Proven Statuses

- `GATE1_METADATA_GAP_REPORT_CONTRACT_READY`
- `GATE1_CLARIFICATION_REQUEST_CONTRACT_READY`
- `GATE1_CLARIFICATION_RESOLUTION_CONTRACT_READY`
- `GATE1_CLARIFICATION_PROMPT_READY`
- `GATE1_CLARIFICATION_STRUCTURED_OUTPUT_READY`
- `GATE1_CLARIFICATION_ARTIFACTSTORE_READY`
- `GATE1_CLARIFICATION_SYNTHETIC_LOOP_PASSED`
- `CASE_GROUP_002_CLARIFICATION_REQUEST_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `CASE_GROUP_002_GATE2_HANDOFF_BLOCKED_WITH_ACTIONABLE_QUESTIONS`

Not claimed: `READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF`.
The live `case_group_002` run ended in the intended actionable clarification
state, not in Gate 2 source-fact readiness.

## Implementation Anchors

- Contracts and deterministic loop live in `services/broker-reports-gate1-proof/broker_reports_gate1/clarification.py`:
  - schema constants: lines 28-30;
  - managed Prompt factory: line 154;
  - deterministic gap report: line 400;
  - answer resolution ingestion: line 642;
  - eligibility rerun: line 714;
  - safe question projection: line 736.
- OpenWebUI Pipe integration lives in `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`:
  - clarification valves: line 92;
  - clarification stage orchestration: line 329;
  - OpenWebUI structured-output call: line 607;
  - controlled answer ingestion: line 963;
  - Gate 2 private/ref smoke checks: lines 1208-1215.
- ArtifactStore and Gate 2 handoff persistence live in `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_handoff.py`:
  - gap report artifact: line 317;
  - raw clarification output artifact: line 370;
  - clarification request artifact: line 407;
  - clarification resolution artifact: line 439;
  - usable resolution refs only: line 467;
  - `clarification_resolution_refs` in handoff: line 524.
- Contract docs:
  - `docs/stage2/contracts/BROKER_REPORTS_GATE1_METADATA_CLARIFICATION.v0.md`;
  - `docs/stage2/contracts/BROKER_REPORTS_GATE1_METADATA_CLARIFICATION_PROMPT.v0.md`;
  - `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`.

## Contract Boundary

The deterministic code decides metadata gaps, duplicate canonical-choice gaps,
answer validation, resolution usability, eligibility rerun, and Gate 2 handoff.

The LLM only rewrites the safe gap report into structured clarification
questions. It does not read raw documents, decide eligibility, extract source
facts, calculate tax, generate declarations/XLSX, perform OCR, or write to
Knowledge/RAG.

OpenWebUI managed Prompt is used for clarification. The final prompt body is
not hardcoded in Python; the Pipe resolves it through
`ClarificationPromptResolverFactory`.

## Live Deployment

Updated OpenWebUI Function:

- function id: `broker_reports_gate1_pipe`
- live content sha256: `70f8ed9d70854e280718d76ed4d8621fe0de3797f322394cb454a2bee10ad670`
- contains document passport code: true
- contains metadata clarification code: true

Managed clarification Prompt:

- prompt ref: `broker_reports_gate1_clarification_prompt_v0`
- command: `broker_gate1_clarification_request`
- version: `clarification-v0-2026-07-09-implementation`
- output schema version: `gate1_clarification_request_v0`
- output schema hash: `ceeaa01d01e609270f713a8673b0ee80283dcdf3b5338a4031da90a6a5984f26`
- updater prompt hash: `268b139f43c7e053f567af65f5f0ce27fcb36fb8e7e301db937b874bc746691c`
- live ArtifactStore prompt hash observed in runs:
  `9fa559039dd226ada66ed6b8dda4c72fe7291665d04f1458dbcd33a8b27b45a3`

The live hash difference is expected: ArtifactStore hashes the exact stored
Prompt row content, including OpenWebUI formatting.

## Synthetic Proof

Command:

```powershell
python services\broker-reports-gate1-proof\scripts\live_process_false_private_intake_smoke.py --env-file .env --synthetic-fixture-mode clarification_gap --enable-llm-passport --enable-clarification --clarification-synthetic-answers --timeout 300 --settle-seconds 6
```

Result: `status=passed`.

Key evidence:

- metadata gap report created: 2 blocking gaps;
- gap types: `missing_account_or_contract=1`, `missing_period=1`;
- clarification request validated: 2 required questions;
- structured output mode: `openwebui_response_format_json_schema`;
- response format type: `json_schema`;
- clarification schema hash recorded:
  `ceeaa01d01e609270f713a8673b0ee80283dcdf3b5338a4031da90a6a5984f26`;
- resolution artifacts persisted: 6 total, 3 usable, 3 failed/unmatched audit
  records;
- Gate 2 handoff reran to `ready_with_safe_refs` /
  `full_package_ready_for_gate2`;
- handoff exposes only usable resolution refs, not failed resolution refs;
- chat visible report is compact Russian text, no JSON fence;
- no private slices in chat;
- source fact extraction, tax declaration, XLS/XLSX and OCR flags stayed false;
- `document_rows` delta after cleanup: 0;
- `knowledge_rows` delta after cleanup: 0;
- vector deltas after upload/chat/delete: 0;
- uploaded source file rows returned to baseline after delete;
- private payloads purged/tombstoned.

## Case Group 002 Proof

Command:

```powershell
python services\broker-reports-gate1-proof\scripts\live_case_group_process_false_gate1_run.py --env-file .env --case-group-id case_group_002 --enable-llm-passport --enable-clarification --timeout 300 --settle-seconds 6 --cleanup-source-uploads
```

Result: `status=passed`.

Case evidence:

- files uploaded with `process=false`: 16;
- case group broker/provider candidate: `Interactive Brokers / IBKR`;
- document metadata passports: 16 passed, 0 failed;
- passport structured output mode: `openwebui_response_format_json_schema`;
- clarification model call: passed;
- clarification structured output mode: `openwebui_response_format_json_schema`;
- metadata gap report: 35 blocking gaps;
- metadata-review documents: 13;
- duplicate group count: 1;
- clarification request: 35 required questions;
- gap types:
  - `duplicate_canonical_choice=1`;
  - `missing_account_or_contract=8`;
  - `missing_broker_client_metadata=11`;
  - `missing_period=5`;
  - `other_metadata_conflict=10`;
- no operator answers supplied;
- resolution count: 0;
- no auto-resolution occurred;
- Gate 2 handoff status: `blocked`;
- Gate 2 handoff mode: `gate2_blocked_requires_metadata_review`;
- actionable clarification questions are present in the compact Russian report;
- private refs are not in chat;
- ArtifactStore records: 135;
- private case records: 89;
- Knowledge backend records: 0;
- customer retention mode: `customer_approved_test`, explicit true;
- `document_rows` delta after cleanup: 0;
- `knowledge_rows` delta after cleanup: 0;
- vector deltas after upload/chat/cleanup: 0.

## Tests

Local shell: Windows PowerShell from
the `corp-openweb ui` repository root.

Commands:

```powershell
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_clarification_loop services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_artifact_store services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_stub -v
python services\broker-reports-gate1-proof\scripts\build_openwebui_pipe_bundle.py
python -m py_compile services\broker-reports-gate1-proof\openwebui_actions\broker_reports_gate1_pipe.py services\broker-reports-gate1-proof\openwebui_actions\broker_reports_gate1_pipe_bundled.py services\broker-reports-gate1-proof\scripts\live_process_false_private_intake_smoke.py services\broker-reports-gate1-proof\scripts\live_case_group_process_false_gate1_run.py services\broker-reports-gate1-proof\scripts\live_update_function_and_passport_prompt.py
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_bundle -v
python -m unittest discover -s services\broker-reports-gate1-proof\tests -v
python -m compileall -q services\broker-reports-gate1-proof
git diff --check
```

Outcomes:

- focused clarification/artifact/pipe tests: 30 OK;
- bundle smoke: 1 OK;
- full broker-reports-gate1-proof test discovery: 78 OK;
- `compileall`: passed;
- `git diff --check`: no whitespace errors; only existing LF-to-CRLF warnings.

## Notes

- Failed or unmatched controlled answers are persisted as private blocked audit
  resolution artifacts, but are not placed in Gate 2 handoff
  `clarification_resolution_refs`.
- `private_slice_refs` remains scoped to included source documents only.
- `clarification_resolution_refs` carries only usable private answer artifacts
  consumed by the eligibility rerun.
- If clarification is disabled or managed Prompt/LLM clarification fails, the
  deterministic metadata gap report remains the safe fallback path.
