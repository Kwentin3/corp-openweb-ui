# Broker Reports Intermediate Ledgers Contract v0 Proposal

Status: Intermediate ledgers contract proposal
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL source-facts-to-declaration bridge

## 1. Purpose

Intermediate ledgers are the layer between source facts and the declaration-oriented model.

They normalize source facts into reviewable tables, record calculation status, expose conflicts and preserve traceability. They do not claim final tax correctness and do not replace the declaration model.

## 2. Top-Level Shape

```json
{
  "schema_version": "broker_reports_intermediate_ledgers_v0_proposal",
  "intermediate_ledgers_id": null,
  "case_id": null,
  "document_inventory_ref": null,
  "source_facts_set_ref": null,
  "ledger_sets": {
    "income_ledger": [],
    "securities_operations_ledger": [],
    "fees_expenses_ledger": [],
    "withholding_ledger": [],
    "currency_conversion_ledger": [],
    "conflict_ledger": [],
    "calculation_trace": []
  },
  "ledger_summary": {
    "deterministic_calculation_performed": false,
    "customer_methodology_status": "missing | partial | approved",
    "ready_for_declaration_mapping": false
  }
}
```

## 3. Shared Ledger Item Envelope

Every ledger item should carry:

```json
{
  "ledger_item_id": null,
  "ledger_type": null,
  "source_fact_refs": [],
  "document_inventory_refs": [],
  "raw_fields": {},
  "normalized_fields": {},
  "calculated_fields": {},
  "calculation_status": "not_calculated | deterministic_required | calculated | blocked",
  "methodology_status": "not_applicable | requires_customer_methodology | approved | unknown",
  "official_requirement_refs": [],
  "declaration_candidate_refs": [],
  "consistency_checks": [],
  "review_notes": []
}
```

Rules:

- `raw_fields` preserve source labels/values through source fact refs.
- `normalized_fields` are mechanical normalization only.
- `calculated_fields` require deterministic calculation proof.
- `declaration_candidate_refs[]` may point forward to declaration model candidates, but ledgers do not own declaration output.

## 4. `income_ledger`

Purpose: normalize income facts before category/code mapping.

Inputs:

- `income_events[]` from source facts;
- dividend/coupon/source-country facts;
- withholding links where visible.

Required fields:

- `income_ledger_item_id`;
- `source_fact_refs[]`;
- `income_label_raw`;
- `income_kind_candidate`;
- `income_source_name`;
- `income_country`;
- `income_date`;
- `amount.raw_value`;
- `amount.normalized_value`;
- `amount.currency`;
- `methodology_status`;
- `official_requirement_refs[]`.

Calculated fields:

- declaration-currency amount;
- category totals;
- taxable income candidates.

Deterministic calculation required for:

- currency conversion;
- totals by income type;
- reconciliation against broker summary totals.

Customer methodology required for:

- income group/type codes;
- dividend/coupon/other income split;
- source precedence when summaries and details disagree.

Declaration candidates:

- `dividends_and_withholding[]`;
- `tax_base_items[]`;
- `income_categories[]` candidate links.

Consistency checks:

- source fact exists and has evidence;
- income date/currency present or issue created;
- summary/detail mismatch recorded in `conflict_ledger`.

## 5. `securities_operations_ledger`

Purpose: normalize buy/sell/corporate-action rows before tax-base candidates.

Example item:

```json
{
  "ledger_item_id": "sec_ledger_001",
  "ledger_type": "securities_operation",
  "source_fact_refs": [],
  "operation_type": "buy | sell | fee | corporate_action | unknown",
  "instrument": null,
  "trade_date": null,
  "settlement_date": null,
  "quantity": null,
  "amount": {
    "raw_value": null,
    "normalized_value": null,
    "currency": null
  },
  "calculation_status": "not_calculated | deterministic_required | calculated | blocked",
  "methodology_status": "requires_customer_methodology",
  "official_requirement_refs": [],
  "declaration_candidate_refs": [],
  "review_notes": []
}
```

Required fields:

- `operation_type`;
- instrument safe label or hashed identifier;
- trade date and settlement date where available;
- quantity;
- amount and currency;
- source fact refs.

Calculated fields:

- matched lot refs;
- cost-basis candidates;
- gain/loss candidates;
- declaration-currency values.

Deterministic calculation required for:

- buy/sell matching;
- lot-level aggregation;
- gain/loss;
- currency conversion;
- duplicate row detection beyond source hash checks.

Customer methodology required for:

- IIS/non-IIS treatment;
- corporate actions;
- conflict precedence;
- allowed source granularity.

Declaration candidates:

- `tax_base_items[]`;
- `fees_and_expenses[]` only when fee rows are linked and methodology permits.

## 6. `fees_expenses_ledger`

Purpose: preserve broker fees, commissions and expense-like facts without assuming eligibility.

Required fields:

- `fee_ledger_item_id`;
- `source_fact_refs[]`;
- `fee_label_raw`;
- `fee_category_candidate`;
- `fee_date`;
- amount and currency;
- `eligible_for_declaration_candidate`;
- `methodology_status`.

Raw fields:

- broker-visible fee label;
- source amount;
- source currency.

Normalized fields:

- date shape;
- parsed amount;
- fee type candidate.

Calculated fields:

- declaration-currency amount;
- allocation to operation or period;
- eligible expense candidate.

Customer methodology required for:

- whether the fee is source fact only or declaration candidate;
- Appendix 8 relevance;
- allocation rules.

Consistency checks:

- fee source fact exists;
- fee is not silently used as deductible;
- any eligibility claim has methodology ref.

## 7. `withholding_ledger`

Purpose: preserve withholding and foreign tax paid facts separately from income.

Required fields:

- `withholding_ledger_item_id`;
- `source_fact_refs[]`;
- `related_income_ledger_refs[]`;
- withholding source;
- country/source marker;
- date;
- amount and currency;
- `methodology_status`.

Deterministic calculation required for:

- currency conversion;
- reconciliation with related income;
- totals by source/country.

Customer methodology required for:

- foreign tax treatment;
- required supporting documents;
- whether unmatched withholding remains warning or blocking.

Declaration candidates:

- `dividends_and_withholding[]`;
- review-only withholding questions.

## 8. `currency_conversion_ledger`

Purpose: keep currency conversion inputs and calculation gaps explicit.

Required fields:

- `currency_ledger_item_id`;
- `source_fact_refs[]` or `ledger_item_refs[]`;
- source amount;
- source currency;
- rate date candidate;
- rate source ref;
- rate value;
- converted amount;
- `calculation_status`;
- `methodology_status`.

Deterministic calculation required for:

- rate lookup;
- conversion arithmetic;
- rounding;
- reconciliation with source-provided converted values.

Customer methodology required for:

- rate date policy;
- official rate source policy;
- treatment of source-provided converted amounts.

Consistency checks:

- no converted amount marked complete without rate/date policy;
- no rate source inferred from layout only;
- missing rate policy creates a review issue.

## 9. `conflict_ledger`

Purpose: collect row-level or aggregate-level disagreements before review state.

Required fields:

- `conflict_ledger_item_id`;
- conflict type;
- related source fact refs;
- related ledger item refs;
- candidate values;
- detected by parser/model/manual review;
- `resolution_status`;
- `question_to_specialist`.

Examples:

- summary total differs from detailed rows;
- report period conflicts across documents;
- currency label differs between table and summary;
- duplicate document hash with different modified time.

Conflicts are not resolved by LLM unless customer methodology explicitly allows a rule.

## 10. `calculation_trace`

Purpose: record deterministic calculation provenance.

Required fields:

- `calculation_trace_id`;
- input refs;
- formula or algorithm id;
- methodology ref;
- official requirement refs;
- output refs;
- execution status;
- validation status.

Rules:

- LLM-only arithmetic cannot produce `calculation_status = calculated`.
- A calculation trace may be `blocked` with a reason.
- The trace is input to review state and declaration candidates, not final tax proof.

## 11. Status

```text
INTERMEDIATE_LEDGERS_CONTRACT_PROPOSAL_READY
CUSTOMER_METHODOLOGY_REQUIRED
DETERMINISTIC_CALCULATION_REQUIRED_FOR_TAX_BASE
READY_FOR_NEXT_HUMAN_REVIEW
```
