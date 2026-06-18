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

OCR/layout-aware PDF pilot now explicitly includes VL OCR / vision-language OCR candidate evaluation. VL OCR may be useful for scans, images, complex PDFs and tables, but must be benchmarked. It is not a production OCR guarantee.

## 4. Target user workflow

User uploads document inside a scenario. System classifies file type, extracts safe representation, runs prompt/template, returns analysis with limitations and uncertain areas.

## 5. Native OpenWebUI first path

- File upload.
- Knowledge/RAG/full context if appropriate.
- Prompt templates for document questions.
- Clear limitations for scans/tables/formulas.

## 6. Integration / custom implementation path

- OCR/layout-aware pilot for scanned/complex PDF.
- VL OCR candidate evaluation for scans/images/complex PDFs/table-like documents.
- Table extractor for PDF if needed.
- XLSX parser/tool/code path for accurate sheets/formulas.
- Production document pipeline deferred.

## 6.1. VL OCR pilot boundary

Goal:

- evaluate whether vision-language OCR or document AI candidates improve extraction quality for scans, images, complex PDF, stamps/signatures and table-heavy broker reports.

Non-goal:

- no production OCR/layout pipeline;
- no "OCR works for everything" acceptance;
- no guarantee of deterministic extraction for every scan.

Input test documents:

- text PDF;
- scanned PDF;
- PDF with tables;
- PDF with stamps/signatures;
- broker report;
- poor scan/photo;
- table screenshot or XLSX-related visual sample if relevant.

Candidate models/providers:

- native OpenWebUI extraction engines;
- Apache Tika / text extraction baseline;
- Docling / structured document extraction;
- Mistral OCR / document AI;
- vision-language models with OCR capability;
- cloud OCR providers;
- local OCR / local VLM options.

Output comparison:

- extracted text quality;
- table structure;
- layout preservation;
- JSON/Markdown output quality;
- hallucinated or missing content;
- privacy/data policy fit;
- cost and latency.

Decision before implementation:

- classify each document type as native extraction works, needs OCR, needs VL OCR or not reliable in Stage 2.

## 7. Data and security notes

Documents may contain personal/financial/accounting data. Data policy decides provider use. Do not rely on future masking as current control.

External OCR/VL OCR provider tests require data policy approval and customer-confirmed test documents.

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
- [VL_OCR_PROVIDER_RESEARCH](../research/VL_OCR_PROVIDER_RESEARCH.md)
- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)

## 12. Acceptance signals

- Simple PDF/DOCX/XLSX examples produce useful output.
- Scan/complex PDF has OCR/VL OCR pilot result or documented limitation.
- OCR pilot results are classified by document type.
- Excel precision claims are limited to parser/tool path.
- Production OCR pipeline remains future unless separately approved.

## 13. Implementation readiness

Needs customer test data, data policy approval and OCR/VL OCR pilot-scope ADR before implementation.
