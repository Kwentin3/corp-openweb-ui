# Broker Reports Synthetic Case 001 Source Documents Plan

Status: Source documents plan, generation not started
Date: 2026-07-04
Scope: planned synthetic documents for `synthetic_case_001`

## 1. Purpose

This document describes planned source documents for `synthetic_case_001`.

Do not generate PDF, XLSX or raster files in this step. The plan exists so the next review can approve document roles and intentional gaps before any fixture generation.

## 2. Planned Documents

| document_id | filename | document_taxonomy_class | can_be_source_evidence | can_be_methodology | declaration_relevance | source facts expected | intentional gaps/conflicts | safety notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `doc_sc001_broker_report_text` | `synthetic_case_001_broker_report_text_ru.txt` | `source_broker_report` | yes | no | source facts and review context | header, account `SYNTH-BROKER-0001`, broker `Synthetic Foreign Broker LLC`, period 2025, summary total `1245.00` in `SYNTH-FCY` | summary total conflicts with operations table sale total | synthetic text only; no customer data |
| `doc_sc001_operations_csv` | `synthetic_case_001_operations.csv` | `operations_table` | yes | no | securities operation events and fee events | buy `SYNTH-A`, sell `SYNTH-A`, buy fee, sell fee, row-level refs | table sale total `1250.00` conflicts with broker report summary | machine-readable table; no XLSX generated |
| `doc_sc001_dividends_report` | `synthetic_case_001_dividends_report.txt` | `dividends_report` | yes | no | income and withholding events | dividend `SYNTH-DIV`, foreign broker, withholding `6.25`, source date | tax identifier absent from all docs | synthetic text only |
| `doc_sc001_summary_conflict` | `synthetic_case_001_summary_conflict.txt` | `source_broker_report` | yes | no | conflict support | alternate summary value `1245.00`, source label, period | deliberately conflicts with operations CSV | supporting evidence, not methodology |
| `doc_sc001_negative_3ndfl_blank` | `synthetic_case_001_negative_3ndfl_blank.pdf` | `official_form` | no | conditional | official requirement / negative classification | no taxpayer source facts expected | must not become `source_broker_report` or taxpayer evidence | planned only; no PDF generated in this step |
| `doc_sc001_optional_raster_later` | `synthetic_case_001_raster_with_watermark_later.pdf` | `synthetic_fixture` | conditional | no | future OCR/raster experiment | optional low-confidence duplicate withholding value | raster uncertainty, not part of first proof | optional later, do not generate now |
| `doc_sc001_optional_xlsx_later` | `synthetic_case_001_workbook_later.xlsx` | `synthetic_fixture` | conditional | no | future parser/workbook experiment | optional operation table rendering | formula/mixed-cell parser risk | optional later, do not generate now |
| `doc_sc001_optional_mixed_later` | `synthetic_case_001_mixed_text_raster_later.pdf` | `synthetic_fixture` | conditional | no | future mixed representation experiment | text header plus raster table | source granularity uncertainty | optional later, do not generate now |

## 3. Generation Rules For Later Step

When generation is approved:

- every file must include `synthetic_case_001` marker;
- every person, broker, account and instrument identifier must be synthetic;
- generated documents must preserve the intentional missing taxpayer identifier;
- generated documents must preserve the summary/table conflict;
- official blank form must be used only as negative classification input;
- no customer sample docs may be used;
- no XLS/XLSX generation is part of this step.

## 4. Expected Document Manifest Assertions

- every planned generated document appears in `document_manifest`;
- `synthetic_case_001_broker_report_text_ru.txt` is classified as `source_broker_report`;
- `synthetic_case_001_operations.csv` is classified as `operations_table`;
- `synthetic_case_001_dividends_report.txt` is classified as `dividends_report`;
- `synthetic_case_001_negative_3ndfl_blank.pdf` is classified as `official_form`;
- `official_form` is not used as taxpayer source evidence;
- optional later documents are excluded from first proof unless explicitly generated.

## 5. Status

```text
SOURCE_DOCUMENTS_GENERATION_READY_AFTER_REVIEW
PDF_XLSX_GENERATION_NOT_STARTED
```
