# OpenWebUI Broker Reports Gate 1 Normalization Slice 1 Report

Status: GATE1_SLICE1_IMPLEMENTED
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 contract-based normalization proof

## 1. Implemented

Implemented Slice 1 in the primary Pipe path:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`

The Pipe now creates a contract-shaped safe report for uploaded file refs:

```text
Pipe file refs
-> private file registry in memory
-> byte access when available
-> sha256
-> size
-> duplicate detection
-> container detection
-> safe document inventory
-> typed blockers
-> safe chat-visible report
```

Action/button remains a secondary/debug path and was not promoted.

## 2. Contracts Covered

Covered contracts:

- `normalization_run_v0`
- `document_inventory_v0`
- minimal `technical_readability_profile_v0`
- `normalization_blockers_v0`
- `chat_visible_normalization_report_v0`

The report keeps compatibility with the existing `summary_counts` shape while also exposing the required top-level safe fields:

- `run_status`
- `files_total`
- `container_counts`
- `document_class_counts`
- `duplicate_count`
- `blockers_total`
- `documents[].document_id`
- `recommended_next_step`
- `safety_statement`

## 3. Synthetic Inputs

Only synthetic/test data was used.

The tests use inline synthetic file bytes and a temporary upload root:

- synthetic TXT-like broker package text;
- synthetic operations CSV;
- duplicate copy of synthetic content;
- synthetic unknown binary payload;
- synthetic guarded upload-root file;
- synthetic path-escape file ref.

The existing fixture folder remains available:

- `docs/stage2/testdata/broker_reports_gate1_stub/`

No real customer documents were read or copied.

## 4. Tests Performed

Command:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
```

Result:

```text
Ran 13 tests in 0.020s
OK
```

Covered behavior:

1. No files returns `failed_safe` with `no_files`.
2. Synthetic TXT + CSV returns `files_total=2`.
3. SHA-256 is stable and matches the original bytes.
4. Duplicate bytes are detected with `duplicate_review`.
5. CSV/TXT container counts are correct.
6. Unknown/unsupported container creates `unsupported_format`.
7. Raw filename is absent from chat-visible output.
8. Raw file id is absent from chat-visible output.
9. Raw account marker is absent from chat-visible output.
10. Full CSV row content is absent from chat-visible output.
11. Upload-root path escape is blocked with `upload_path_escape_detected`.
12. Safety statement is included.
13. Tax calculation flags remain false.
14. Source-fact extraction flag remains false.

## 5. Compile And Hygiene

Command:

```text
python -m compileall services/broker-reports-gate1-proof
```

Result: passed.

Command:

```text
git diff --check
```

Result: passed. Git emitted CRLF warnings for unrelated existing files only:

- `deploy/openwebui-static/loader.js`
- `services/stage2-stt/tests/test_loader_static.py`

Additional checks for the new/updated Gate 1 code/tests:

```text
git -c core.autocrlf=false diff --no-index --check -- NUL <file>
rg -n '[ \t]+$' <touched Gate 1 files>
```

Result: no whitespace findings.

Secret-like scan over touched Gate 1 code/tests: no findings.

Closed-world path/import/config scan over `services/broker-reports-gate1-proof`: no findings.

## 6. Privacy Checks Passed

The safe report does not print:

- raw file ids;
- raw filenames;
- private paths;
- account numbers;
- personal identifiers;
- full CSV rows;
- raw parser text;
- secrets or env values.

The Pipe performs an internal private-marker scan before returning the chat-visible report. If a private marker is detected in the rendered JSON, the Pipe returns a `privacy_failed` report with a `privacy_violation` blocker instead of publishing the unsafe projection.

## 7. Not Implemented

Still out of scope:

- NDFL calculation;
- source-fact extraction;
- declaration generation;
- XLS/XLSX export;
- FNS filing;
- OCR;
- LLM reading of raw documents;
- customer docs ingestion into Knowledge;
- real customer document processing;
- PDF/XLSX/ZIP full parser proof;
- CSV/TXT Slice 2 profiling beyond Slice 1 metadata and byte-level proof.

## 8. Runtime Smoke

Runtime smoke not executed.

Reason: no live OpenWebUI runtime/API path and operator credentials were available in this turn. Local contract tests prove the Pipe behavior against synthetic request shapes and synthetic bytes, but they do not prove live OpenWebUI upload-byte access.

## 9. Slice 2 Readiness

Slice 1 is ready for Slice 2.

Recommended next slice:

```text
READY_FOR_GATE1_SLICE2_CSV_TXT_PROFILING
```

Slice 2 should add bounded CSV/TXT profiling and private slices only after preserving the current Slice 1 privacy and blocker guarantees.

## 10. Final Status

```text
GATE1_SLICE1_IMPLEMENTED
GATE1_SLICE1_TESTS_PASSED
GATE1_PIPE_SAFE_INVENTORY_READY
GATE1_BYTE_HASHING_READY
GATE1_CONTAINER_COUNTS_READY
GATE1_SAFE_CHAT_REPORT_READY
GATE1_PRIVACY_CHECKS_PASSED
READY_FOR_GATE1_SLICE2_CSV_TXT_PROFILING
RUNTIME_SMOKE_NOT_EXECUTED
```
