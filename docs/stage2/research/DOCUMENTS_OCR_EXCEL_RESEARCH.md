# Documents OCR Excel Research

## 1. Question

What document handling can be delivered in Practical Stage 2 without promising production document pipeline?

## 2. Why it matters for PRD-1

Broker reports and office docs are core scenarios, but PDF/DOCX/XLSX are not plain text.

## 3. Current assumptions

- Basic text extraction may be enough for some docs.
- OCR/layout-aware PDF pilot is required.
- Complex Excel parser is future/separate unless precision is required.

## 4. What to verify

- OpenWebUI file handling.
- Text PDF extraction quality.
- Scanned PDF OCR options.
- PDF table extraction.
- DOCX structure extraction.
- XLSX parser/tool/code path options.

## 5. Sources to check

- PRD-1.
- Customer test documents.
- OpenWebUI document/file features.
- Candidate OCR/parser libraries/tools only during research.

## 6. Test plan / proof plan

Use simple PDF, scanned PDF, PDF with tables, DOCX, XLSX, complex XLSX. Compare output to expected result.

## 7. Risks

- Skipped rows/tables.
- OCR errors.
- Lost formulas.
- User assumes legal/tax correctness.

## 8. Decision options

- Native file handling only for simple docs.
- OCR pilot for scanned PDFs.
- Parser/tool path for XLSX precision.
- Production pipeline deferred.

## 9. Recommended next step

Collect customer test documents before implementation planning.

## 10. Status

Blocked by customer test data.
