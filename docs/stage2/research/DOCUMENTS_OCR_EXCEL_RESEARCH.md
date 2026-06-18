# Documents OCR Excel Research

## 1. Question

How should Stage 2 handle PDF/DOCX/XLSX documents, scanned PDFs and broker-report extraction without promising a production OCR/layout pipeline?

## 2. Research status

Status: researched from official OpenWebUI docs on 2026-06-18.

Result type: pilot scope input. No customer documents were processed.

## 3. Findings

- OpenWebUI has RAG/document extraction features and a Workspace Knowledge surface.
- Current docs describe multiple extraction engines, including Apache Tika, Docling, Azure, Mistral OCR and custom loaders.
- Apache Tika can be configured as an OpenWebUI context extraction engine through Admin Panel > Settings > Documents and a Tika URL.
- Docling is documented as a structured extraction path for PDFs, Word documents, spreadsheets, HTML and images into JSON/Markdown-style structured data.
- Mistral OCR is documented for scanned PDFs, images and handwritten documents into JSON/plain text.
- Troubleshooting docs recommend previewing extracted content; if key sections are blank/missing, extraction settings or engine choice must change.
- RAG quality depends on extraction quality, chunking and retrieval settings. It is not guaranteed tax/report understanding by itself.

## 4. PRD-1 interpretation

Practical Stage 2 should split document handling into three levels:

1. Basic native document handling.
   - Upload/read simple text PDFs, DOCX and possibly XLSX where extraction works.
   - Use OpenWebUI Knowledge/RAG and prompt templates.

2. OCR/layout pilot.
   - Test scanned PDFs and broker reports with one extraction engine path.
   - Include VL OCR / vision-language OCR candidates for scans, images, complex PDFs and table-heavy documents.
   - Record limitations honestly.
   - No production queue, no automated tax filing promise.

3. Future production pipeline.
   - Dedicated parser/OCR queue, validation UI, audit trail and human review.
   - Separate future slice after customer samples prove need.

## 5. Broker report implications

- Broker reports and 3-НДФЛ drafts are sensitive and error-prone.
- Output must be positioned as draft analysis for human review, not tax/legal guarantee.
- Quality cannot be accepted without real anonymized broker reports and an example of the "good result" currently produced in Claude API/Claude models.
- XLSX formulas/tables may need direct spreadsheet parsing rather than generic RAG extraction.

## 6. Recommended next step

Collect a test package before implementation:

- native text PDF;
- scanned PDF;
- PDF with tables;
- DOCX;
- XLSX with formulas/tables;
- broker report sample;
- expected structured result example.

Then run extraction preview tests and decide whether Tika, Docling, Mistral OCR, VL OCR candidate or custom parser is the first pilot engine.

See also: [VL_OCR_PROVIDER_RESEARCH](VL_OCR_PROVIDER_RESEARCH.md).

## 7. Sources

- https://docs.openwebui.com/features/chat-conversations/rag/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/apachetika/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/docling/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/mistral-ocr/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/troubleshooting/rag/
- https://docs.openwebui.com/troubleshooting/performance/
- https://docs.openwebui.com/reference/env-configuration/

## 8. Status

Research complete for planning. Implementation remains blocked by customer test documents.
