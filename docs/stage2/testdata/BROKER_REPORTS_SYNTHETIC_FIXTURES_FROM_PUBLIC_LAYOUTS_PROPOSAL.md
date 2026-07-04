# Broker Reports Synthetic Fixtures From Public Layouts Proposal

Status: Proposal
Date: 2026-07-04
Related:

- [BROKER_REPORTS_JSON_EXTRACTION_SYNTHETIC_FIXTURES_PLAN.md](BROKER_REPORTS_JSON_EXTRACTION_SYNTHETIC_FIXTURES_PLAN.md)
- [BROKER_REPORTS_PUBLIC_ARTIFACT_POOL_RESEARCH.md](BROKER_REPORTS_PUBLIC_ARTIFACT_POOL_RESEARCH.md)
- [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md](../contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md)

## 1. Principle

Use a hybrid corpus:

- public artifacts for layout realism;
- synthetic fixtures for controlled expected JSON;
- customer anonymized samples for production acceptance later.

Public documents must not supply real personal, broker, account, tax or financial facts. They only inform safe synthetic layout design.

## 2. Public Layout Patterns To Reuse

Observed patterns:

- header block: broker name, generated date, report period;
- customer/account block: investor name, account identifier, account type, IIS marker;
- portfolio summary block;
- operations/trades table;
- income/dividends/coupons summary;
- fees/charges summary;
- tax withheld / foreign tax withheld labels;
- cash movement/activity section;
- positions table;
- tax form transaction table with date/proceeds/basis/adjustment labels;
- blank official tax-form layout that should be classified as `tax_form`, not `broker_report`.

## 3. Fixture Updates

### 3.1. `synthetic_broker_report_text_ru.txt`

Update with:

- title: `Synthetic Broker Report`;
- broker: `Synthetic Broker LLC`;
- account: `SYNTH-BROKER-0001`;
- taxpayer: `Synthetic Person Alpha`;
- report period: synthetic closed period;
- generated date: synthetic date;
- operations summary;
- fees summary;
- explicit missing taxpayer identifier.

Expected JSON:

- `document_manifest[0].detected_document_type = "broker_report"`;
- `extracted_tax_facts.broker.broker_name.status = "extracted"`;
- `extracted_tax_facts.broker.report_period.status = "extracted"`;
- `extracted_tax_facts.taxpayer.tax_identifier.status = "missing"`;
- `missing_data` contains taxpayer identifier;
- `questions_to_specialist` asks for missing identifier;
- `readiness.status = "needs_more_data"`.

### 3.2. `synthetic_broker_report_text_pdf.md`

Update with page-like sections:

- page 1: header and account block;
- page 2: operations table;
- page 3: dividends/coupons section;
- page 4: fees and limitations.

Expected JSON:

- source wrappers include page/section labels;
- extracted facts from page-like text have `source_type = "text_layer"`;
- ambiguous table labels go to `uncertain_data`;
- no raster flags.

### 3.3. `synthetic_operations.csv`

Columns:

- `operation_id`;
- `operation_type`;
- `trade_date`;
- `settlement_date`;
- `asset`;
- `quantity`;
- `currency`;
- `gross_amount_synth`;
- `fee_synth`;
- `tax_withheld_synth`;
- `source_row_label`.

Expected JSON:

- `content_representation = "machine_readable_table"`;
- `processing_mode = "native_table_extraction"` if parsed by a tool, otherwise `prompt_only_context`;
- row-level source references are required for totals;
- unknown operation types become `uncertain_data`.

### 3.4. `synthetic_operations_simple.xlsx`

Sheets:

- `Summary`;
- `Operations`;
- optional `Dividends`;
- optional `Fees`.

Expected JSON:

- `sheets_count` reflects visible synthetic sheets;
- summary totals and operation-table totals are compared;
- if they disagree, create `conflicts`;
- formulas are marked uncertain unless deterministic parser proof exists.

### 3.5. `synthetic_dividends_report_scan.png`

Create a raster image with watermark:

```text
SYNTHETIC TEST IMAGE - NOT A REAL BROKER REPORT
```

Expected JSON:

- `content_representation = "raster_scan"`;
- `processing_mode = "vision_llm_experimental"` only when vision input is actually tested;
- otherwise `processing_mode = "unsupported"`;
- raster-derived fields are `uncertain` or `missing`, never high-confidence by default;
- `manual_review_required = true`.

### 3.6. `synthetic_broker_report_scan.pdf`

Create scanned-PDF-like raster pages from synthetic content.

Expected JSON:

- `container_format = "pdf"`;
- `content_representation = "raster_scan"`;
- `readability_status = "not_readable"` or `partially_readable`;
- no text-layer excerpts are claimed;
- unsupported runtime returns `not_ready` or `needs_more_data`.

### 3.7. `synthetic_mixed_pdf_case.md`

Design:

- text-layer page with clean header;
- raster-only image/table section;
- optional conflict between text summary and raster table.

Expected JSON:

- `content_representation = "mixed_text_and_raster"`;
- text-layer data extracted with medium/high confidence;
- raster-only values low confidence or missing;
- conflict record if summary and raster table disagree.

### 3.8. `expected_broker_reports_extraction_v0.json`

Expected output should include:

- one text document;
- one table document;
- one missing field;
- one uncertain field;
- one optional conflict;
- one specialist question;
- `manual_review_required = true`;
- `tax_correctness_claimed = false`;
- `fns_filing_claimed = false`;
- `can_proceed_to_xls_stage = false` unless a later proof explicitly changes it.

## 4. New Negative Cases

Add:

- `negative_official_blank_3ndfl_form.pdf`: classify as `tax_form`, not broker report.
- `negative_irs_8949_form.pdf`: classify as `tax_form`, not RU methodology source.
- `negative_bank_statement_like.txt`: classify as unrelated/cashflow-like, not broker report unless securities context exists.
- `negative_invoice_like.pdf`: classify as unrelated.
- `negative_broker_help_article.html`: classify as instructions/help, not input evidence.

## 5. Synthetic Identifiers

Use only:

- `Synthetic Person Alpha`;
- `Synthetic Broker LLC`;
- `SYNTH-BROKER-0001`;
- `SYNTH-TAX-ID-000000`;
- `SYN` currency;
- synthetic dates;
- synthetic operation IDs.

Do not use real broker account formats, real tax identifiers, real names, real addresses or real trade records.

## 6. Expected Ground Truth Strategy

For each fixture, prepare:

- fixture source file;
- expected `document_manifest`;
- expected extracted fields;
- expected `missing_data`;
- expected `uncertain_data`;
- expected `conflicts`;
- expected `questions_to_specialist`;
- expected `readiness`;
- negative assertions, such as no tax correctness and no filing claim.

## 7. Next Action

After human review of this proposal, generate synthetic files and expected JSON in a separate task. Do not use public broker samples as ground truth.
