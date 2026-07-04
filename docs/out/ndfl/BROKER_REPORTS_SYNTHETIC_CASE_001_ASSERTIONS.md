# Broker Reports Synthetic Case 001 Assertions

Status: Semantic assertions draft
Date: 2026-07-04
Scope: expected assertions for future prompt-only staging proof

## 1. Purpose

These assertions validate behavior semantically.

Do not use full JSON snapshot equality. The proof should check that the workflow preserves source facts, separates methodology gaps and avoids final tax/declaration claims.

## 2. Document Classification Assertions

- Every generated synthetic document appears in `document_manifest`.
- `synthetic_case_001_broker_report_text_ru.txt` is classified as `source_broker_report`.
- `synthetic_case_001_operations.csv` is classified as `operations_table`.
- `synthetic_case_001_dividends_report.txt` is classified as `dividends_report`.
- `synthetic_case_001_summary_conflict.txt` is classified as source evidence or supporting evidence for conflict review.
- `synthetic_case_001_negative_3ndfl_blank.pdf` is classified as `official_form`.
- The blank 3-NDFL form is not classified as `source_broker_report`.
- The blank 3-NDFL form is not used as taxpayer source evidence.
- Instruction, template, example, help article and public layout sample documents are not used as source evidence.

## 3. Source Facts Assertions

- Sale row `operation_sell_001` is extracted as `securities_operation_event`.
- Buy row `operation_buy_001` is extracted as `securities_operation_event`.
- Buy and sell fee rows are extracted as `fee_events`.
- Dividend row `income_001` is extracted as `income_event`.
- Withholding row `withholding_001` is extracted as `withholding_event`.
- Currency context `currency_001` is extracted as `currency_event`.
- Every extracted event has `document_inventory_refs`.
- Every extracted event has `source_evidence_refs` where visible source content exists.
- `raw_value` is preserved.
- `normalized_value` is mechanical only.
- No calculated final tax base is produced by source facts extraction.
- Fee eligibility is not resolved inside source facts extraction.
- Currency conversion is not resolved inside source facts extraction.

## 4. Declaration Mapping Assertions

- Source facts map only to declaration-oriented candidates.
- `official_requirement_refs` are present where official structure is used.
- `tax_year=2025` is marked as synthetic proof year, not customer scope.
- `official_source_set_id=ru_3ndfl_2025_fns_order_2025_10_20` is present in period applicability.
- Securities operation candidates cite `REQ-2025-TB-001` and `REQ-2025-APP8-001` where applicable.
- Foreign income/dividend candidates cite `REQ-2025-FGN-001`.
- Withholding candidates cite `REQ-2025-WH-001`.
- Currency context candidates cite `REQ-2025-CUR-001`.
- Income code remains candidate if customer methodology is absent.
- Fees remain `requires_customer_methodology`.
- Currency conversion remains `calculation_required`.
- No final declaration, filing instruction or XLS/XLSX artifact is produced.

## 5. Review State Assertions

- Missing taxpayer identifier appears in missing/review state.
- Summary/table mismatch appears in conflicts.
- Fee treatment appears as methodology gap.
- Currency conversion appears as calculation gap.
- Questions to specialist include data questions.
- Questions to specialist include methodology questions.
- Questions to specialist include calculation questions.
- Official-source gaps and methodology gaps are separated.
- Readiness is for specialist review only.
- `tax_correctness_claimed` is false.
- `fns_filing_claimed` is false.
- `xlsx_generation_claimed` is false.

## 6. Negative Assertions

The proof must fail if:

- source facts are produced without evidence refs;
- an official blank form becomes taxpayer source evidence;
- fee eligibility is treated as resolved without customer methodology;
- currency conversion is treated as complete without deterministic rate/date rule;
- income code is promoted from candidate to final without customer methodology;
- readiness implies final tax correctness;
- readiness implies FNS filing readiness;
- readiness implies XLS/XLSX generation readiness.

## 7. Status

```text
SYNTHETIC_CASE_001_ASSERTIONS_READY
CUSTOMER_METHODOLOGY_REQUIRED
```
