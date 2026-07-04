# Broker Reports JSON Extraction Synthetic Fixtures Plan

Status: Test data plan
Date: 2026-07-04
Related contract: [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md](../contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md)

## 1. Boundary

Fixtures must be synthetic only. Do not use real personal, broker, tax, account or financial data.

Use obviously synthetic names and values:

- taxpayer: `Synthetic Person Alpha`;
- broker: `Synthetic Broker LLC`;
- account: `SYNTH-BROKER-0001`;
- identifiers: `SYNTH-TAX-ID-000000`;
- amounts: synthetic round numbers;
- dates: synthetic proof dates.

Fixtures are for prompt/validation mechanics, not tax correctness.

## 2. Fixture Set

### 2.1. `synthetic_broker_report_text_ru.txt`

Purpose:

- baseline prompt-only text extraction;
- document classification;
- missing-data behavior.

Container:

- `txt`

Content representation:

- `text_layer`

Expected extracted fields:

- broker name;
- report period;
- report currency;
- operations table present;
- dividends section absent or not found.

Expected missing:

- taxpayer tax identifier if omitted;
- foreign tax withheld if not present.

Expected uncertain:

- none for clean baseline.

Expected conflicts:

- none.

Expected `document_manifest`:

- `container_format: "txt"`;
- `content_representation: "text_layer"`;
- `readability_status: "readable"`;
- `processing_mode: "prompt_only_context"`.

Expected readiness:

- `needs_more_data` if identifier is missing;
- manual review required.

### 2.2. `synthetic_broker_report_text_pdf.md`

Purpose:

- text-layer PDF surrogate before generating a real PDF fixture;
- page/source reference behavior.

Container:

- Markdown surrogate for PDF fixture description.

Content representation:

- `text_layer`

Expected extracted fields:

- report period;
- broker name;
- operations totals;
- page-like section labels.

Expected missing:

- fields not present in the synthetic text.

Expected uncertain:

- table labels that are present but ambiguous.

Expected conflicts:

- none unless paired with another fixture.

Expected `document_manifest`:

- when used as surrogate: `container_format: "pasted_text"` or `txt`;
- when converted to PDF: `container_format: "pdf"`, `content_representation: "text_layer"`.

Expected readiness:

- `ready_for_specialist_review` only if no blocking field is missing.

### 2.3. `synthetic_operations.csv`

Purpose:

- machine-readable table path;
- column/source reference behavior.

Container:

- `csv`

Content representation:

- `machine_readable_table`

Expected extracted fields:

- sales total;
- purchases total;
- fees total;
- per-currency rows if present.

Expected missing:

- fields absent from CSV, such as taxpayer identity.

Expected uncertain:

- rows with unknown operation type.

Expected conflicts:

- duplicate rows with contradictory values if included.

Expected `document_manifest`:

- `tables_detected: 1`;
- `processing_mode: "native_table_extraction"` if parser is used, otherwise `prompt_only_context`.

Expected readiness:

- `needs_more_data` unless identity and required report metadata are supplied elsewhere.

### 2.4. `synthetic_operations_simple.xlsx`

Purpose:

- simple workbook classification;
- sheet count and table detection.

Container:

- `xlsx`

Content representation:

- `machine_readable_table`

Expected extracted fields:

- sheet names;
- operation totals;
- currency;
- fees.

Expected missing:

- hidden or absent tax fields.

Expected uncertain:

- formulas or cells whose result/source cannot be inspected in prompt-only mode.

Expected conflicts:

- optional conflict between summary sheet and operations sheet totals.

Expected `document_manifest`:

- `container_format: "xlsx"`;
- `sheets_count: 1` or more;
- limitations must mention formula/table parser gap if only prompt text is supplied.

Expected readiness:

- `needs_more_data` or `ready_for_specialist_review` depending on included metadata.

### 2.5. `synthetic_dividends_report_scan.png`

Purpose:

- raster/vision experimental path;
- lower trust marking.

Container:

- `image`

Content representation:

- `raster_scan`

Expected extracted fields:

- only visible dividend facts if vision model supports the input.

Expected missing:

- values unreadable due to scan quality.

Expected uncertain:

- all raster-derived numeric values unless image quality is excellent and provider policy allows vision proof.

Expected conflicts:

- none by default.

Expected `document_manifest`:

- `processing_mode: "vision_llm_experimental"` if processed by vision model;
- `processing_mode: "unsupported"` if no vision support is available;
- `requires_manual_review: true`.

Expected readiness:

- never fully ready without specialist review.

### 2.6. `synthetic_broker_report_scan.pdf`

Purpose:

- scanned PDF classification;
- avoid false text-layer claims.

Container:

- `pdf`

Content representation:

- `raster_scan`

Expected extracted fields:

- none if no vision/OCR proof path is active;
- low-confidence values if vision experiment is active.

Expected missing:

- all required fields if unsupported.

Expected uncertain:

- visible but weak fields.

Expected conflicts:

- none by default.

Expected `document_manifest`:

- `container_format: "pdf"`;
- `content_representation: "raster_scan"`;
- `readability_status: "not_readable"` or `partially_readable`;
- `processing_mode: "unsupported"` or `vision_llm_experimental`.

Expected readiness:

- `not_ready` or `needs_more_data`.

### 2.7. `synthetic_mixed_pdf_case.md`

Purpose:

- mixed text and raster classification;
- partial-readability behavior.

Container:

- Markdown fixture description first; can later be rendered into PDF.

Content representation:

- `mixed_text_and_raster`

Expected extracted fields:

- text-layer fields;
- no high-confidence values from raster-only sections.

Expected missing:

- fields present only in raster area when no vision/OCR proof is active.

Expected uncertain:

- raster-only table values.

Expected conflicts:

- optional conflict between text summary and raster table.

Expected `document_manifest`:

- `readability_status: "partially_readable"`;
- limitations list both readable text and unsupported raster sections.

Expected readiness:

- `needs_more_data`.

### 2.8. `expected_broker_reports_extraction_v0.json`

Purpose:

- contract validation fixture;
- static validation smoke;
- expected top-level key and enum behavior.

Container:

- `json`

Content representation:

- expected output, not input.

Must include:

- all top-level keys;
- one text document;
- one missing field;
- one question to specialist;
- `manual_review_required: true`;
- `tax_correctness_claimed: false`;
- `fns_filing_claimed: false`.

Negative companion fixture:

- omit `document_manifest` or set `manual_review_required: false` to prove validation fails.

## 3. Fixture Generation Notes

Do not generate real-looking identity numbers, account numbers or transaction records from a real broker.

For text fixtures, use clearly synthetic labels:

```text
Synthetic Broker LLC
Synthetic report period: 2026-Q1
Synthetic account: SYNTH-BROKER-0001
Synthetic operation total sales: 1000 SYN
Synthetic operation total purchases: 700 SYN
Synthetic fees: 10 SYN
Taxpayer identifier: not provided
```

For raster fixtures, add visible watermark text:

```text
SYNTHETIC TEST IMAGE - NOT A REAL BROKER REPORT
```

## 4. Proof Mapping

| Fixture | Track | Primary check | Expected status |
| --- | --- | --- | --- |
| `synthetic_broker_report_text_ru.txt` | A | prompt-only JSON baseline | required |
| `synthetic_broker_report_text_pdf.md` | A | PDF text-layer surrogate | required |
| `synthetic_operations.csv` | A | machine-readable table | required |
| `synthetic_operations_simple.xlsx` | A | simple workbook | optional but recommended |
| `synthetic_dividends_report_scan.png` | B | raster/vision experiment | optional until model supports images |
| `synthetic_broker_report_scan.pdf` | B | scanned PDF refusal/vision path | optional until model supports images |
| `synthetic_mixed_pdf_case.md` | B | partial readability | optional |
| `expected_broker_reports_extraction_v0.json` | validation | static validation | required |

## 5. Customer Data Gate

Synthetic fixtures can prove mechanics only. They do not close production acceptance.

Before customer-grade proof, request:

- customer methodology;
- anonymized broker documents;
- expected JSON or XLS/XLSX outputs;
- required fields;
- provider/data policy;
- secure transfer method;
- specialist reviewer;
- acceptance criteria.
