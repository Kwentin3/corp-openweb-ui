# OpenWebUI Broker Reports Gate 1 Live Pipe Update And Smoke Report

Status: LIVE_GATE1_PIPE_UPDATED
Date: 2026-07-08
Scope: Stage 2 Broker Reports, Gate 1 live OpenWebUI Pipe Function update and synthetic Workspace Model API smoke.

## 1. Live State Found

Live OpenWebUI host was reachable and protected:

- `GET /health` returned HTTP 200.
- Unauthenticated `GET /api/models` and `GET /api/v1/functions/` returned HTTP 401.
- Admin API signin succeeded. No auth value was printed.

Installed Function:

- id: `broker_reports_gate1_pipe`
- type: `pipe`
- active: `True`
- global: `False`
- previous source metadata version: `0.1.0-proof`
- previous source contained `trigger_type = pipe_stub`
- previous source did not contain `Gate1Normalizer`
- previous source did not contain `from broker_reports_gate1 import`
- previous display name was mojibake-corrupted

Workspace/API model inventory after update included:

- Pipe model id: `broker_reports_gate1_pipe`
- Workspace Model id: `test`
- Workspace Model base model: `broker_reports_gate1_pipe`

## 2. Update Applied

Updated the live Function through:

```text
POST /api/v1/functions/id/broker_reports_gate1_pipe/update
```

Payload shape matched the OpenWebUI frontend API helper:

```text
{ id, name, meta, content }
```

Uploaded Function content:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py
```

Live verification after update:

- live content SHA-256 matched local bundled artifact SHA-256:
  `25c62e77dfebb31341570bc6d9806c2d80f3dfb82724e2f664e786191b10e67d`
- live source contains `_BUNDLED_MODULES`
- live source contains `gate1_backend_profiling_completion_v1`
- live source contains `pipe_backend_normalizer`
- live source no longer contains `pipe_stub`
- live display name is readable: `НДФЛ. Брокерские отчеты / Gate 1`

## 3. Runtime Module Availability

Deployment option used: Option B, OpenWebUI-compatible bundled Pipe.

Reason: API access was available, but local Docker/runtime filesystem access was not available in this workstation session. OpenWebUI Functions are uploaded as Function source, so the safe practical update was a self-contained bundle.

How backend modules are available:

- generated bundle embeds the current `broker_reports_gate1` package into `_BUNDLED_MODULES`;
- bundle installs those modules into `sys.modules` before the Pipe adapter imports them;
- no OpenWebUI container mount is required;
- no workspace absolute path is used;
- no customer docs, env values, credentials, or test fixture bytes are embedded;
- runtime requirements remain `pydantic` plus Python stdlib.

Generation script:

```text
services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py
```

## 4. Local Checks

Commands run:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
python -m compileall services/broker-reports-gate1-proof
git diff --check
```

Results:

- unit tests: `Ran 37 tests ... OK`
- bundle-specific test passed against `broker_reports_gate1_pipe_bundled.py`
- compileall passed
- generated `__pycache__` folders were removed after compile verification
- `git diff --check` passed; it printed only pre-existing CRLF warnings for unrelated files:
  - `deploy/openwebui-static/loader.js`
  - `services/stage2-stt/tests/test_loader_static.py`

Additional scans over touched Gate 1 files:

```text
rg -n '[ \t]+$' <touched Gate 1 files>
credential-pattern scan over touched Gate 1 files
closed-world path/config scan over services/broker-reports-gate1-proof
```

Results: no findings.

## 5. Smoke Method

Smoke method: API smoke through the Workspace Model.

This was not a manual browser GUI smoke. It still exercised the live Workspace Model route:

```text
OpenWebUI API upload
-> model_id = test
-> Workspace Model base_model_id = broker_reports_gate1_pipe
-> Pipe Function broker_reports_gate1_pipe
-> bundled backend normalizer
-> safe chat-visible report
```

Prompt:

```text
нормализуй
```

Synthetic input files:

- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_broker_report.txt`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_broker_report.html`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations_duplicate.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_unknown.bin`

Uploads were deleted after smoke: `deleted_upload_count=5`.

## 6. Smoke Output Summary

Observed safe report summary:

- `file_ref_visibility = visible`
- `files_total = 5`
- `trigger_type = pipe_backend_normalizer`
- `normalizer_version = gate1_backend_profiling_completion_v1`
- `run_status = completed_with_blockers`
- `validation_result.status = passed`
- `container_counts = {"csv": 2, "html_text": 1, "txt": 1, "unknown": 1}`
- `duplicate_count = 1`
- blocker codes: `duplicate_review`, `unsupported_format`
- `source_fact_extraction_performed = False`
- `tax_correctness_claimed = False`
- `declaration_generated = False`
- `xlsx_generated = False`
- `ocr_performed = False`

The old marker is gone:

```text
trigger_type=pipe_stub absent
```

## 7. Privacy Check

The smoke script scanned the chat-visible response for forbidden markers and upload ids.

Result:

- `forbidden_hit_count = 0`
- `file_id_leak_count = 0`
- no raw OpenWebUI upload ids were printed in this report
- no raw live chat JSON was copied into this report

Checked forbidden classes included:

- raw synthetic filenames;
- raw uploaded file ids;
- synthetic account marker;
- full CSV row marker;
- raw text/table slice fields.

## 8. Remaining Actions

Manual browser GUI smoke was not run in this turn. If browser-level proof is required, run the same synthetic files through the visible OpenWebUI chat UI and record only a safe summary, not the raw report or upload ids.

No customer documents were used. No customer documents were loaded into Knowledge.

## 9. Final Status

```text
LIVE_GATE1_PIPE_UPDATED
PIPE_STUB_REPLACED
BACKEND_NORMALIZER_AVAILABLE_IN_OPENWEBUI_RUNTIME
GATE1_API_SMOKE_PASSED
GATE1_PRIVACY_CHECKS_PASSED
READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE
```
