# Documents OCR Excel Blueprint

## 1. Purpose

Спланировать basic PDF/DOCX/XLSX handling, OCR/layout-aware PDF pilot and Excel constraints.

## 2. PRD-1 requirements covered

- Documents needed through broker reports and general work scenarios.
- PDF/DOCX/XLSX are supported with limitations.
- OCR/layout-aware PDF needed as pilot/research.
- Production-grade OCR/layout pipeline is not promised.
- Complex Excel parser is separate/future slice.

## 3. Current known context

PRD-1 explicitly warns that office files are not plain text. Accurate Excel handling requires parser/tool/code path, not pure LLM.

## 4. Target user workflow

User uploads document inside a scenario. System classifies file type, extracts safe representation, runs prompt/template, returns analysis with limitations and uncertain areas.

## 5. Native OpenWebUI first path

- File upload.
- Knowledge/RAG/full context if appropriate.
- Prompt templates for document questions.
- Clear limitations for scans/tables/formulas.

## 6. Integration / custom implementation path

- OCR/layout-aware pilot for scanned/complex PDF.
- Table extractor for PDF if needed.
- XLSX parser/tool/code path for accurate sheets/formulas.
- Production document pipeline deferred.

## 7. Data and security notes

Documents may contain personal/financial/accounting data. Data policy decides provider use. Do not rely on future masking as current control.

## 8. Dependencies

- Broker reports scenario.
- Data policy.
- Test data package.
- Provider catalog.

## 9. Risks and constraints

- Scanned PDF not readable.
- Tables lose structure.
- Excel formulas and hidden data lost.
- User assumes legal/tax accuracy.

## 10. Open questions

- Which document types dominate?
- How many are scans?
- What XLSX complexity exists?
- What quality threshold is enough for pilot?

## 11. Research links

- [DOCUMENTS_OCR_EXCEL_RESEARCH](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)

## 12. Acceptance signals

- Simple PDF/DOCX/XLSX examples produce useful output.
- Scan/complex PDF has OCR pilot result or documented limitation.
- Excel precision claims are limited to parser/tool path.
- Production OCR pipeline remains future unless separately approved.

## 13. Implementation readiness

Needs test data and OCR/parser research.
