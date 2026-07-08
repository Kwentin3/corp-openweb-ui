# OpenWebUI Broker Reports Gate 1 Backend Profiling Completion Report

Status: GATE1_BACKEND_PROFILING_COMPLETION_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports, Gate 1 backend-only profiling completion before GUI smoke

## 1. Implemented Profiling

Extended the existing backend-only Gate 1 contour:

```text
files
-> inventory/hash/container detection
-> technical profiles
-> private bounded slices
-> taxonomy candidates
-> typed blockers
-> validation
-> safe chat-visible report
```

The Pipe remains a thin adapter. Profiling logic stays in
`services/broker-reports-gate1-proof/broker_reports_gate1/`.

Implemented or extended:

- CSV profiling: encoding, delimiter, rows, columns, header candidate, bounded private table slice, truncation flag, source location.
- TXT profiling: encoding, line count, section count, clean text flag, bounded private text slice, truncation flag, source location.
- HTML-as-text profiling: stdlib HTML text cleanup, table candidate signal, bounded private text slice.
- XLSX workbook profiling: stdlib ZIP/XML workbook read, sheet count, hashed sheet ids, hidden sheet count, formulas, used ranges, table-like ranges, bounded private table slices.
- PDF profiling: stdlib heuristic page count, text-layer signal, raster/scan likelihood, weak table likelihood, bounded private text slices for text-layer PDFs.
- ZIP profiling: stdlib member inventory, extension counts, nested archive count, encrypted member count, oversized member count, corrupt handling, default `zip_requires_review`.
- DOCX profiling: stdlib ZIP/XML paragraph, heading and table counts, bounded private text slices.
- Image profiling: PNG/JPEG header metadata where available plus OCR/review blocker.
- Taxonomy: rule-assisted candidate classes from profile signals, still non-authoritative.
- Validation: private slices require `document_id`, `profile_id`, and source location; ZIP/PDF/Gate 2 blocker rules are checked.

## 2. Format Status

Contract-profiled formats:

- `csv`
- `txt`
- `html_text`
- `xlsx`
- `pdf`
- `zip`
- `docx`

Blocker/review formats:

- `image` - metadata only, OCR/review blocker, no OCR.
- `xls` - legacy XLS remains unsupported.
- `unknown` / unsupported / corrupt / encrypted - typed blockers.
- raster-like PDF - `raster_requires_ocr_or_review`, blocks Gate 2.
- ZIP packages - inventory plus `zip_requires_review` by default.

## 3. Dependencies

No new runtime dependency was added.

Reason: this proof can meet the Gate 1 contract surface with Python stdlib
profilers for XLSX, PDF, DOCX, ZIP, image headers, CSV, TXT, and HTML-as-text.
This avoids ghost dependencies and keeps the OpenWebUI function boundary closed.

Deferred dependency decisions:

- `openpyxl` can still replace or strengthen XLSX profiling later.
- `pypdf` or `PyMuPDF` can strengthen PDF parsing later.
- `python-docx` can strengthen DOCX parsing later.

None of those are required for this backend proof.

## 4. Synthetic Fixtures

Committed synthetic fixtures:

- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_broker_report.txt`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_broker_report.html`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_operations_duplicate.csv`
- `docs/stage2/testdata/broker_reports_gate1_normalization/synthetic_unknown.bin`

Generated inside tests:

- ZIP with synthetic PDF/XML/signature/nested archive members.
- XLSX workbook with multiple sheets, formula, hidden sheet, used ranges.
- text-layer PDF.
- raster-like PDF.
- corrupt PDF.
- encrypted-marker PDF.
- corrupt ZIP.
- DOCX package.
- PNG image header.

No real customer files were used. No local customer-approved folder was used.

## 5. Tests

Command:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
```

Result:

```text
Ran 36 tests in 0.144s
OK
```

Coverage includes:

1. CSV delimiter, rows, columns, header candidate.
2. CSV bounded private slice absent from safe report.
3. TXT line/section counts and bounded private text slice.
4. HTML-as-text clean text and table candidate.
5. XLSX sheet count.
6. XLSX formulas.
7. XLSX hidden sheet.
8. XLSX safe report does not leak sheet names or cell values.
9. PDF page count.
10. PDF text layer.
11. PDF private text slice absent from safe report.
12. Raster-like PDF creates `raster_requires_ocr_or_review`.
13. Corrupt PDF creates typed blocker.
14. Encrypted PDF creates typed blocker.
15. ZIP member extension counts.
16. ZIP `zip_requires_review`.
17. ZIP raw member names absent from safe report.
18. Corrupt ZIP creates typed blocker.
19. Unknown binary creates `unsupported_format`.
20. DOCX lightweight profile.
21. Image metadata plus OCR/review blocker.
22. Taxonomy candidates for supported documents.
23. Weak taxonomy defaults to `unknown_or_needs_review`.
24. Private slices absent from chat-visible report.
25. Raw filenames absent.
26. Raw file ids absent.
27. Private paths absent.
28. Account markers absent.
29. Full financial rows absent.
30. Privacy injection returns `privacy_failed`.
31. Full synthetic package validation passes.
32. Unsafe report validation fails closed.
33. Source-fact extraction flag remains false.
34. Tax/declaration/XLS/FNS/OCR flags remain false.
35. Existing Pipe tests remain passing.
36. Existing Action debug tests remain passing.

## 6. Compile And Hygiene

Command:

```text
python -m compileall services/broker-reports-gate1-proof
```

Result: passed.

Generated `__pycache__` folders under `services/broker-reports-gate1-proof`
were removed after compile verification.

Command:

```text
git diff --check
```

Result: passed. Git emitted only pre-existing CRLF warnings for unrelated files:

- `deploy/openwebui-static/loader.js`
- `services/stage2-stt/tests/test_loader_static.py`

Additional scans over touched Gate 1 code, tests, and fixtures:

```text
rg -n '[ \t]+$' <touched paths>
sensitive-value pattern scan over touched paths
closed-world path/dependency pattern scan over services/broker-reports-gate1-proof
```

Result: no findings.

## 7. Privacy Checks

Safe report remains whitelist-rendered and does not publish:

- raw file ids;
- raw filenames;
- private filesystem paths;
- sheet names;
- ZIP member names;
- raw TXT/PDF/DOCX text;
- CSV/XLSX rows or cell values;
- account markers;
- sensitive values or environment values.

Private slices are present only in the private package and referenced by safe ids.

## 8. Deferred

Still deferred:

- GUI smoke;
- OpenWebUI manual test;
- Action/button as primary path;
- DOM/static loader path;
- customer documents;
- customer Knowledge loading;
- OCR/VLM/OCR provider work;
- source-fact extraction;
- tax calculation;
- declaration generation;
- XLS/XLSX export;
- FNS filing.

## 9. GUI Smoke Recommendation

Backend profiling proof is now ready for GUI smoke.

Recommendation: run GUI/OpenWebUI smoke next, but only as a separate task. This
report did not perform GUI smoke or manual OpenWebUI testing.

## 10. Final Status

```text
GATE1_BACKEND_PROFILING_COMPLETION_READY
GATE1_CSV_TXT_HTML_PROFILING_READY
GATE1_XLSX_PROFILING_READY
GATE1_PDF_PROFILING_READY
GATE1_ZIP_PROFILING_READY
GATE1_DOCX_PROFILE_OR_BLOCKER_READY
GATE1_IMAGE_BLOCKER_READY
GATE1_TAXONOMY_PROFILE_SIGNALS_READY
GATE1_VALIDATION_PASSED
GATE1_PRIVACY_CHECKS_PASSED
GUI_SMOKE_DEFERRED
READY_FOR_GUI_SMOKE
```
