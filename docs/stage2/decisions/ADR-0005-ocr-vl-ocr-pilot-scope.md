# ADR-0005 OCR / VL OCR Pilot Scope

Status: Proposed

## 1. Context

Practical Stage 2 includes OCR/layout-aware PDF discovery and pilot on real
customer documents. Production OCR/layout pipeline remains future.

VL OCR / vision-language OCR may help with scans, images, complex PDFs and
table-heavy broker reports, but must be benchmarked.

## 2. Problem

Without a pilot boundary, OCR can be misread as a promise that every PDF, scan,
table and broker report will be reliably processed in production.

## 3. Decision needed

Approve OCR/VL OCR pilot scope, candidate classes, test set and per-document
acceptance before implementation.

## 4. Options

Option 1. Native extraction only.

- Lowest integration risk.
- May fail scans and complex PDFs.

Option 2. Tika/Docling baseline plus selective VL OCR.

- Gives baseline and escalation path.
- Recommended pilot shape if data policy allows provider tests.

Option 3. Production OCR/layout pipeline now.

- Too large for Practical Stage 2.
- Keep deferred unless separately approved.

## 5. Recommended option

Use Option 2 for the pilot. Compare 2-3 candidates on the same customer test set.

Pilot must include:

- OCR pilot, not production OCR pipeline;
- VL OCR candidates;
- test set;
- quality comparison;
- per-document-class acceptance;
- privacy/provider data policy dependency.

## 6. Consequences

- Customer documents are required before implementation.
- External OCR/VL OCR tests depend on ADR-0001 data policy.
- Acceptance is per document class, not "OCR works".
- XLSX remains parser/tool/code path, not pure LLM/OCR.

## 7. Runtime proof needed

- Run extraction preview on approved test documents.
- Compare native extraction, baseline extraction and VL OCR candidate output.
- Record missing text, wrong tables, hallucinated content and latency/cost.
- Classify document types as native, OCR, VL OCR or unreliable in Stage 2.

## 8. Customer input needed

- Text PDF.
- Scanned PDF.
- PDF with tables.
- PDF with stamps/signatures.
- Broker report.
- Poor scan/photo.
- Expected good output.
- Permission for foreign/Russian/cloud provider tests.

## 9. Acceptance signals

- Candidate list selected.
- Test set collected.
- Results classified by document type.
- Production OCR/layout pipeline remains future unless separately approved.

## 10. Links

- [DOCUMENTS_OCR_EXCEL](../blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [DOCUMENTS_OCR_EXCEL_RESEARCH](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](../research/VL_OCR_PROVIDER_RESEARCH.md)
- [TEST_DATA_REQUIREMENTS](../acceptance/TEST_DATA_REQUIREMENTS.md)
