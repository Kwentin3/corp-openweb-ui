# Broker Reports NDFL Declaration Data Model v0

Status: Draft declaration-oriented data model

Global owner: Gate 4 — Tax and Declaration Output Preparation. Gate 3 supplies
the accepted case-assembly/ledger root; this contract must not become a bypass
from one Gate 2 fact set around cross-document scope and reconciliation.
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL documentation refine

This is not the JSON extraction contract and not an XLS/XLSX template. It defines the target data layer that should exist before any later declaration/XLS work is considered.

## 1. Model Boundary

The model is declaration-oriented:

```text
source facts from documents
-> normalized intermediate records
-> declaration-oriented data
-> review state
```

The model does not assert:

- final tax correctness;
- automatic 3-NDFL generation;
- FNS filing;
- XLS/XLSX generation;
- production OCR.

## 2. Authority Fields

Every model item should carry:

| Field | Meaning |
| --- | --- |
| `source_authority` | `official_fns`, `official_law`, `customer_methodology_required`, `layout_only`, `internal_contract`, `unknown`. |
| `model_role` | `declaration_target`, `intermediate_calculation`, `source_fact`, `review_only_context`. |
| `methodology_status` | `official_confirmed`, `requires_customer_methodology`, `not_applicable`, `unknown`. |
| `calculation_required` | Whether deterministic calculation is required before review. |
| `human_confirmation_required` | Always true for this MVP. |

## 3. Top-Level Shape

```json
{
  "schema_version": "broker_reports_ndfl_declaration_model_v0",
  "declaration_context": {},
  "income_categories": [],
  "tax_base_items": [],
  "dividends_and_withholding": [],
  "fees_and_expenses": [],
  "currency_context": [],
  "source_evidence": {},
  "review_state": {},
  "manual_review_warning": ""
}
```

## 4. `declaration_context`

Purpose: hold context that frames declaration-oriented review.

Suggested fields:

```json
{
  "tax_period_year": null,
  "tax_period_code": null,
  "taxpayer_status": {
    "value": null,
    "source_authority": "official_fns",
    "methodology_status": "requires_customer_methodology",
    "human_confirmation_required": true
  },
  "residency_status": {
    "value": null,
    "source_authority": "official_fns",
    "methodology_status": "requires_customer_methodology",
    "human_confirmation_required": true
  },
  "data_sources_summary": [],
  "target_form": {
    "form": "3-NDFL",
    "knd": "1151020",
    "period_basis": "2025 form/order where applicable"
  },
  "draft_only": true
}
```

Officially anchored:

- 3-NDFL form identity;
- KND `1151020`;
- taxpayer/title-sheet concepts;
- tax period/reporting year concepts.

Requires customer methodology:

- which period to prepare;
- taxpayer status/residency handling;
- whether a broker report period maps directly to tax period.

## 5. `income_categories`

Purpose: represent official/customer-approved categories used to group source facts.

Suggested item:

```json
{
  "category_id": "income_category_001",
  "income_group_code": null,
  "income_type_code": null,
  "income_type_label": null,
  "source_authority": "official_fns",
  "methodology_status": "requires_customer_methodology",
  "applies_to": [],
  "notes": null
}
```

Officially observed candidate signals for broker-related review:

- group `02`, type `001`: dividends / equity participation income;
- group `02`, type `003`: securities/PFI operations outside IIS-related scope;
- group `02`, type `034`: securities/PFI operations on IIS.

These are candidate mapping anchors, not final autonomous tax rules.

## 6. `tax_base_items`

Purpose: hold declaration-oriented tax-base candidates and calculation state.

Suggested item:

```json
{
  "item_id": "tax_base_item_001",
  "income_category_id": null,
  "income_amount": null,
  "expense_amount": null,
  "profit_or_loss_amount": null,
  "declaration_currency_code": null,
  "declaration_currency_amount": null,
  "income_source": null,
  "income_date": null,
  "expense_date": null,
  "source_fact_refs": [],
  "source_evidence_refs": [],
  "calculation_status": "not_calculated",
  "calculation_required": true,
  "methodology_status": "requires_customer_methodology",
  "human_confirmation_required": true
}
```

Rules:

- income/expense/profit fields must not be final if they come only from LLM aggregation;
- source facts may be extracted by LLM;
- final base values require deterministic calculation and specialist review;
- securities-related expenses and losses require official/customer methodology review.

## 7. `dividends_and_withholding`

Purpose: separate dividend/income and withholding facts from broader securities-operation facts.

Suggested item:

```json
{
  "item_id": "dividend_withholding_001",
  "income_source": null,
  "income_country": null,
  "income_date": null,
  "gross_income_amount": null,
  "currency": null,
  "declaration_currency_amount": null,
  "tax_withheld_amount": null,
  "foreign_tax_paid_amount": null,
  "income_group_code": null,
  "income_type_code": null,
  "source_fact_refs": [],
  "source_evidence_refs": [],
  "methodology_status": "requires_customer_methodology",
  "calculation_required": true,
  "human_confirmation_required": true
}
```

Official anchors:

- Appendix 1 includes Russian-source income and withheld tax fields.
- Appendix 2 includes foreign-source income, currency, income date, foreign tax paid and declaration-currency conversion fields.
- Section 2 includes withheld tax and foreign tax credit-related aggregate fields.

## 8. `fees_and_expenses`

Purpose: hold source facts and methodology status for broker fees, commissions and expenses.

Suggested item:

```json
{
  "expense_id": "expense_001",
  "expense_type": null,
  "raw_label": null,
  "amount": null,
  "currency": null,
  "declaration_currency_amount": null,
  "source_fact_refs": [],
  "source_evidence_refs": [],
  "eligible_for_declaration_model": null,
  "methodology_status": "requires_customer_methodology",
  "calculation_required": true,
  "human_confirmation_required": true
}
```

Official anchors:

- Section 2 includes expenses accepted in reduction of income.
- Appendix 8 covers expenses/deductions for securities/PFI and related operations.

Do not treat every broker fee as declaration-eligible without methodology.

## 9. `currency_context`

Purpose: hold foreign-currency conversion facts and gaps.

Suggested item:

```json
{
  "currency_context_id": "currency_001",
  "source_currency": null,
  "declaration_currency_code": null,
  "rate_date": null,
  "official_rate_source": null,
  "rate_value": null,
  "source_amount": null,
  "converted_amount": null,
  "source_fact_refs": [],
  "methodology_status": "requires_customer_methodology",
  "calculation_required": true,
  "human_confirmation_required": true
}
```

Official anchor:

- The filling procedure states foreign-currency income and deductible expenses are converted to declaration currency using the Bank of Russia exchange rate on the relevant income/expense date.

This model does not implement rate lookup.

## 10. `source_evidence`

Purpose: preserve traceability from declaration-oriented items back to documents.

Suggested shape:

```json
{
  "document_inventory": [],
  "source_facts": [],
  "source_links": []
}
```

`document_inventory` should be mapped from `document_manifest`.

`source_facts[]` item:

```json
{
  "source_fact_id": "fact_001",
  "fact_type": "income_amount",
  "raw_value": null,
  "normalized_value": null,
  "currency": null,
  "document_id": null,
  "page": null,
  "sheet": null,
  "row": null,
  "column": null,
  "visible_label": null,
  "source_granularity": "document|page|table|row|cell|text_excerpt",
  "confidence": "high|medium|low|not_available",
  "review_only": false
}
```

## 11. `review_state`

Purpose: hold human-review blockers and proof status.

Suggested shape:

```json
{
  "missing": [],
  "uncertain": [],
  "conflicts": [],
  "questions_to_specialist": [],
  "readiness": {
    "status": "not_ready",
    "manual_review_required": true,
    "tax_correctness_claimed": false,
    "fns_filing_claimed": false,
    "xlsx_generation_claimed": false
  }
}
```

Readiness remains specialist-review readiness, not declaration filing readiness.

## 12. Status

Recommended status:

```text
DECLARATION_ORIENTED_MODEL_DRAFT_READY
OFFICIAL_REQUIREMENTS_PARTIAL
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_HUMAN_REVIEW
```

## 13. Sources

- https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/
- https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/
- https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx`
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_3.docx`
- https://www.nalog.gov.ru/rn77/taxation/submission_statements/
