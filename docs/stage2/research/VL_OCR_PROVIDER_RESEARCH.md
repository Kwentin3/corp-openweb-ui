# VL OCR Provider Research

## 1. Question

Какие vision-language OCR / document AI подходы стоит протестировать для Stage 2 OCR/layout-aware
PDF pilot?

## 2. Why it matters for PRD-1

У заказчика значимая доля задач может быть связана со сканами, картинками, сложными PDF, табличными
документами и брокерскими отчетами. Обычный text extraction может не хватить: PDF может быть
визуальной страницей, таблицы могут потерять структуру, а печати/подписи/сканы могут не попасть в
текстовый слой.

VL OCR может лучше работать с layout, таблицами, печатями, сканами, изображениями и визуальными
документами. Но это не равно production OCR pipeline и не доказывает юридически надежное извлечение
данных без пилота.

## 3. Current assumptions

- OCR/layout-aware PDF pilot входит в Practical Stage 2.
- Production OCR/layout pipeline остается future.
- Тестировать нужно на реальных документах заказчика.
- Broker reports are primary test corpus.
- Exact provider/model is selected after research, data policy and customer test data.
- External OCR/VL OCR tests require approval on whether the sample can be sent to
  foreign/Russian/cloud providers.

## 4. Candidate classes

- Native OpenWebUI extraction engines.
- Apache Tika / text extraction baseline.
- Docling / structured document extraction.
- Mistral OCR / document AI.
- Vision-language models with OCR capability.
- Cloud OCR providers.
- Local OCR / local VLM options.
- Hybrid pipeline: OCR/layout extraction + LLM analysis.

## 5. Evaluation criteria

- Russian text quality.
- Tables.
- Scans/photos.
- PDF with stamps/signatures.
- Broker reports.
- Excel/table-like layouts.
- Layout preservation.
- JSON/Markdown output quality.
- Cost.
- Latency.
- Privacy/data policy fit.
- API maturity.
- File size limits.
- Ability to run pilot without production commitment.

## 6. Test data needed

- Text PDF.
- Scanned PDF.
- PDF with tables.
- PDF with stamps/signatures.
- Broker report.
- Poor scan/photo.
- DOCX with table, if relevant.
- XLSX / table screenshot, if relevant.
- Expected good output from Claude API / Claude models or manual sample.
- Customer answer whether each file may be used with foreign providers.
- Customer answer whether anonymization is required before OCR provider tests.

## 7. Pilot design

1. Select 2-3 candidates.
2. Run the same test set through all candidates.
3. Compare extracted text, table structure, layout preservation and errors.
4. Classify documents:
   - works in native extraction;
   - needs OCR;
   - needs VL OCR;
   - not reliable in Stage 2.
5. Produce OCR pilot decision before implementation.

## 8. Risks

- Hallucinated OCR.
- Wrong table structure.
- Privacy/cross-border issue.
- High cost.
- Latency.
- No deterministic extraction.
- Poor handwriting/signature handling.
- No auditability.
- Vendor lock-in.

## 9. Decision options

- Native extraction only.
- Docling/Tika baseline + selective VL OCR.
- Mistral/other OCR provider pilot.
- Local OCR/VLM future.
- Defer production OCR.

## 10. Recommended next step

- Create ADR `OCR / VL OCR pilot scope`.
- Collect customer documents.
- Select candidate list.
- Run controlled pilot.

## 11. Status

Planned / needs customer test data.
