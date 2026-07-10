# OpenWebUI Broker Reports LLM Passport Structured Output Refactor Report

Date: 2026-07-09

## Result

Gate 1 `document_metadata_passport_v0` now uses OpenWebUI native structured output first:

- primary mode: `openwebui_response_format_json_schema`
- response format: `json_schema`
- schema id: `broker_reports.document_metadata_passport.schema.v0`
- schema version: `document_metadata_passport_v0`
- schema hash: `a5f7bd86e6dcf9655748287f08768bc04acf0cd1ca1643861ff2bf1b515d2894`
- fallback mode: `json_object` only when native schema call fails
- repair: one bounded repair attempt after strict validator error summary
- final authority: existing strict passport validator

No Gate 2 execution, Knowledge/RAG loading, OCR/VLM, tax calculation, declaration generation, or XLS generation was added.

## Implementation

Changed areas:

- `broker_reports_gate1/document_passport.py`: machine JSON Schema, schema hash/audit metadata, response format helpers, parsing, validation summaries, structured-output counters.
- `openwebui_actions/broker_reports_gate1_pipe.py`: schema-first OpenWebUI completion, JSON-object fallback, one validator repair attempt, explicit allowed evidence-ref whitelist, safer passport model-id lookup.
- `broker_reports_gate1/gate2_handoff.py`: ArtifactStore safe metadata for prompt/schema/model/mode/fallback/repair audit.
- live proof scripts: structured-output counters and schema-hash checks.
- tests: schema/response-format helpers, bounded repair, ArtifactStore metadata, bundled Pipe closed-world runtime check.

Live Function update:

- previous function SHA: `1b40276a3b53995b0c4d70537cd910dd80a797b879496d9fa4250727e3f11d52`
- deployed function SHA: `5fa12b4a2a0d156f8b72a894d327218f337a17bc8c6c4d37e77f0e8e5a0fa1af`
- managed prompt hash: `7b93fcf0f29402520d7c774da559df3deab26953686cb8cef67fd1b803dc997d`

After container restart, `/api/config` returned `404, 404, 200` during warm-up; proof runs started only after API readiness.

## Synthetic Proof

Command:

```powershell
python services\broker-reports-gate1-proof\scripts\live_process_false_private_intake_smoke.py --env-file .env --enable-llm-passport --timeout 300 --settle-seconds 6
```

Result: `status=passed`.

Key proof:

- passports: `2/2 passed`
- structured mode counts: `openwebui_response_format_json_schema=2`
- response format counts: `json_schema=2`
- fallback used: `0`
- repair attempted: `0`
- schema hash recorded: `2`
- Knowledge rows delta: `0`
- document rows delta: `0`
- vector deltas after upload/chat/delete: `0`
- source uploads deleted: `2`
- active private payload records after purge: `0`

This satisfied the required synthetic-first proof before customer case execution.

## case_group_002 Proof

Command:

```powershell
python services\broker-reports-gate1-proof\scripts\live_case_group_process_false_gate1_run.py --env-file .env --case-group-id case_group_002 --enable-llm-passport --timeout 300 --settle-seconds 6 --cleanup-source-uploads
```

Run id:

- case id: `customer_case_group_002_process_false_gate1_20260709093108`

LLM passport result:

- model: `gpt-5.4-mini-2026-03-17`
- files: `16`
- packages: `16`
- passports: `16/16 passed`
- structured mode counts: `openwebui_response_format_json_schema=16`
- response format counts: `json_schema=16`
- fallback used: `0`
- repair attempted: `0`
- schema hash recorded: `16`
- validation error summary: empty

Runtime boundary:

- process=false upload count: `16`
- uploaded file content endpoint payload count: `0`
- document rows delta after chat: `0`
- Knowledge rows delta after chat: `0`
- vector deltas after upload/chat: `0`
- source uploads deleted: `16`
- ArtifactStore records: `131`
- ArtifactStore Knowledge backend records: `0`
- retention policy: `customer_approved_test`, explicit for all `131` records
- chat-visible report: compact Russian report, no JSON fence, no private refs

The script exited with `status=partial` because `gate2_handoff_ready=false`. Safe report says:

- `gate2_handoff_status=blocked`
- `gate2_handoff_mode=gate2_blocked_requires_review`
- `run_status=completed_with_blockers`
- `validation_status=passed`

This is an out-of-scope Gate 2 readiness blocker, not an LLM passport structured-output failure. Gate 2 was not executed.

## Verification

Local verification:

```powershell
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_document_passport services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_stub -v
python -m unittest discover -s services\broker-reports-gate1-proof\tests -v
python -m compileall -q services\broker-reports-gate1-proof
python services\broker-reports-gate1-proof\scripts\build_openwebui_pipe_bundle.py
python -m py_compile services\broker-reports-gate1-proof\openwebui_actions\broker_reports_gate1_pipe_bundled.py
python -m unittest services.broker-reports-gate1-proof.tests.test_broker_reports_gate1_pipe_bundle -v
```

Observed results:

- focused passport/Pipe tests: OK in the pre-deploy pass
- full current service suite after evidence-ref whitelist hardening: `63 tests OK`
- compileall: OK
- bundled Pipe py_compile: OK
- bundled Pipe closed-world test: OK

Additional focused test after evidence-ref whitelist hardening:

- `test_pipe_passport_uses_json_schema_and_one_bounded_repair_attempt`: OK

## Current Boundary

Structured output for Gate 1 passport is proven on synthetic data and on `case_group_002`. Customer case remains blocked for Gate 2 by review/readiness policy, which is intentionally outside this refactor.
