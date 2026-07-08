# OpenWebUI Broker Reports Gate 1 Backend Contract Proof Report

Status: GATE1_BACKEND_CONTRACT_PROOF_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports, Gate 1 backend-only document intake and normalization proof

## 1. Implemented

Implemented a backend contract contour behind the primary Pipe path:

```text
OpenWebUI Pipe adapter
-> FileInput
-> backend normalizer core
-> document_inventory_v0
-> technical_readability_profile_v0
-> private_normalized_slices_v0
-> taxonomy_candidates_v0
-> normalization_blockers_v0
-> chat_visible_normalization_report_v0
-> validation_result_v0
```

Main code:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/`

The Pipe is now an adapter. It collects OpenWebUI file refs, builds private
`FileInput` objects, delegates to `Gate1Normalizer`, and returns only the
chat-visible safe report.

## 2. Backend Modules

Created backend modules:

- `contracts.py` - schema names, safety flags, artifact refs, stable ids, blocker ids.
- `inputs.py` - `FileInput`, byte provider boundary, typed byte access failure.
- `detectors.py` - extension, MIME, and magic-byte container detection.
- `profilers_csv_txt.py` - CSV/TXT profiling and bounded private slices.
- `profilers_zip.py` - stdlib ZIP inventory without public recursive unpack.
- `profilers_xlsx.py` - optional `openpyxl` profiling, typed blocker when unavailable or failed.
- `profilers_pdf.py` - optional PDF text parser profiling, no OCR.
- `taxonomy.py` - rule-assisted taxonomy candidates, no LLM.
- `blockers.py` - typed blocker factory helpers.
- `validators.py` - artifact and safe-report validation.
- `safe_report.py` - chat-visible report rendering and privacy fail-closed report.
- `normalizer.py` - backend orchestration.

## 3. Contract Coverage

Covered contracts:

- `normalization_run_v0`
- `document_inventory_v0`
- `technical_readability_profile_v0`
- `private_normalized_slices_v0`
- `taxonomy_candidates_v0`
- `normalization_blockers_v0`
- `chat_visible_normalization_report_v0`
- `validation_result_v0`

Inventory includes document id, sha256, size, duplicate group, container,
container confidence, byte status, profile ref, taxonomy ref, and blocker refs.

CSV profiling includes encoding, delimiter, row count, column count, header
candidate, machine-readable table flag, and bounded private table slice.

TXT profiling includes encoding, line count, section count, and bounded private
text slice.

ZIP profiling uses only stdlib `zipfile` and reports member count, extension
counts, nested archive count, encrypted count, corrupt status, and safe member
ids. ZIP receives `zip_requires_review` by default.

Taxonomy is rule-assisted only. It does not use LLM parsing and does not produce
tax facts.

## 4. Synthetic Test Data

Added synthetic-only fixtures:

- `docs/stage2/testdata/broker_reports_gate1_normalization/README.md`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_broker_report.txt`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations_duplicate.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_unknown.bin`

ZIP fixture bytes are generated inside tests with stdlib `zipfile`, so no binary
archive was committed.

No customer documents were read, copied, or loaded into Knowledge.

## 5. Tests

Command:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
```

Result:

```text
Ran 25 tests in 0.058s
OK
```

Added backend contract test coverage for:

1. No files -> `failed_safe` and `no_files`.
2. TXT + CSV inventory, hashes, profiles, taxonomy, validation pass.
3. CSV delimiter, rows, columns, header candidate, private bounded table slice.
4. TXT line count, section count, private bounded text slice.
5. Duplicate bytes -> duplicate group and `duplicate_review`.
6. Unsupported binary -> `unsupported_format` and `unknown_role`.
7. ZIP member inventory, extension counts, nested archive count, `zip_requires_review`.
8. Bytes unavailable -> typed blocker and validation pass.
9. Safe report excludes private slices, raw rows, text, file refs, and filenames.
10. Safe-report validator fails closed with `privacy_violation`.
11. Safe report is JSON serializable and contains contract refs.
12. Local private file paths do not appear in chat-visible output.

Existing Action and Pipe proof tests remain passing.

## 6. Compile And Hygiene

Command:

```text
python -m compileall services/broker-reports-gate1-proof
```

Result: passed.

Generated `__pycache__` folders under `services/broker-reports-gate1-proof` were
removed after compile verification.

Command:

```text
git diff --check
```

Result: passed. Git emitted only pre-existing CRLF warnings for unrelated files:

- `deploy/openwebui-static/loader.js`
- `services/stage2-stt/tests/test_loader_static.py`

Additional checks over touched Gate 1 code, tests, and fixtures:

```text
rg -n '[ \t]+$' <touched paths>
rg -n -i 'api[_-]?key|secret|token|password|BEGIN (RSA|OPENSSH|PRIVATE) KEY|sk-[A-Za-z0-9]' <touched paths>
rg -n 'services/.*/src|\.\./\.\./|process\.cwd\(|path\.resolve\(process\.cwd|config/.*\.json|secrets/.*\.json|dev\.json|prod\.json' services/broker-reports-gate1-proof
```

Result: no findings after wording cleanup of the encrypted-file review action.

## 7. Privacy And Safety

The safe report does not publish:

- raw file ids;
- raw filenames;
- private filesystem paths;
- private CSV rows;
- private TXT excerpts;
- private normalized slices;
- raw ZIP member names;
- customer data;
- secrets or environment values.

If a private marker appears in the chat-visible report, validation returns
`privacy_failed` with a `privacy_violation` blocker.

Safety flags remain false:

- tax correctness claimed;
- source-fact extraction performed;
- declaration generated;
- XLS/XLSX generated;
- FNS filing claimed;
- OCR performed;
- customer docs loaded to Knowledge.

## 8. Deferred

Deferred by design:

- GUI smoke;
- DOM/static loader proof;
- customer document processing;
- OCR;
- NDFL/tax calculation;
- source fact extraction;
- declaration generation;
- XLS/XLSX export;
- Knowledge loading;
- LLM parsing of raw documents.

## 9. Final Status

```text
GATE1_BACKEND_CONTRACT_PROOF_READY
GATE1_BACKEND_TESTS_PASSED
GATE1_DOCUMENT_INVENTORY_READY
GATE1_CSV_TXT_PROFILING_READY
GATE1_PRIVATE_SLICES_READY
GATE1_ZIP_INVENTORY_READY
GATE1_TAXONOMY_CANDIDATES_READY
GATE1_VALIDATION_READY
GATE1_PRIVACY_CHECKS_PASSED
GUI_SMOKE_DEFERRED
READY_FOR_GATE1_XLSX_OR_PDF_SLICE
READY_FOR_GUI_SMOKE_AFTER_BACKEND_PROOF
```
