# Broker Reports Extraction To Declaration Mapping v0

Status: Draft mapping
Date: 2026-07-04
Source contract: `broker_reports_extraction_v0`
Target model: `broker_reports_ndfl_declaration_model_v0`

## 1. Purpose

This document maps the current source-fact extraction layer to the new declaration-oriented model.

The mapping is intentionally conservative:

- `broker_reports_extraction_v0` remains the evidence-first source layer.
- `broker_reports_ndfl_declaration_model_v0` becomes the target review model.
- No automatic declaration filling is claimed.
- No XLS/XLSX generation is included.

## 2. High-Level Mapping

| `broker_reports_extraction_v0` | Declaration model target | Mapping status | Notes |
| --- | --- | --- | --- |
| `schema_version` | `schema_version` | transform | Target uses its own version: `broker_reports_ndfl_declaration_model_v0`. |
| `run_summary` | `declaration_context.data_sources_summary` | partial | Needs tax period and methodology fields. |
| `document_manifest` | `source_evidence.document_inventory` | direct | Needs extra declaration relevance fields. |
| `document_quality_summary` | `source_evidence.document_inventory[].limitations` and `review_state` | partial | Quality should drive readiness. |
| `extracted_tax_facts.taxpayer` | `declaration_context.taxpayer_*` or review state | partial | Current model lacks explicit declaration-context target. |
| `extracted_tax_facts.broker` | `source_evidence.source_facts[]`, `declaration_context`, `tax_base_items[].income_source` | partial | Broker can be document source, income source or review context; role must be explicit. |
| `extracted_tax_facts.operations` | `tax_base_items[]`, `dividends_and_withholding[]`, `fees_and_expenses[]` | partial | Current totals are too coarse for declaration model. |
| `extracted_tax_facts.documents` | `source_evidence.document_inventory` and `review_state` | direct/partial | Useful for classification and completeness. |
| `aggregates.by_currency` | `currency_context[]` and `tax_base_items[]` | partial | Needs rate date/source and calculation status. |
| `aggregates.by_income_type` | `income_categories[]` and `tax_base_items[]` | partial | Needs official/customer-approved codes. |
| `aggregates.by_document` | `source_evidence.source_facts[]` | partial | Useful but not sufficient for tax-base mapping. |
| `missing_data` | `review_state.missing[]` | direct | Add target model path where possible. |
| `uncertain_data` | `review_state.uncertain[]` | direct | Add source fact / declaration target classification. |
| `conflicts` | `review_state.conflicts[]` | direct | Add conflict impact on declaration model. |
| `questions_to_specialist` | `review_state.questions_to_specialist[]` | direct | Add methodology vs data questions distinction. |
| `readiness` | `review_state.readiness` | direct/transform | Must remain specialist-review readiness. |
| `manual_review_warning` | `manual_review_warning` | direct | Preserve. |

## 3. Detailed Mapping

### 3.1. `document_manifest`

Maps to:

```text
source_evidence.document_inventory[]
```

Additional fields needed:

- `document_role`;
- `source_document_class`;
- `target_model_relevance`;
- `declaration_relevance`;
- `source_granularity_available`;
- `not_for_declaration`;
- `review_only`.

Rationale:

The declaration model needs to distinguish a broker report used as fact evidence from a tax form, help article, duplicate document or unrelated file.

### 3.2. `extracted_tax_facts.broker.report_period`

Maps to:

```text
declaration_context.tax_period_year
source_evidence.source_facts[]
review_state.uncertain[]
```

Current gap:

Broker report period may not equal tax period. The mapping needs:

- `raw_value`;
- `normalized_value`;
- `period_role`: `report_period`, `tax_period_candidate`, `operation_period`;
- `human_confirmation_required`.

### 3.3. `extracted_tax_facts.operations.sales_total`

Maps to:

```text
source_evidence.source_facts[]
tax_base_items[].income_amount
```

Current gap:

`sales_total` is too coarse. Declaration model needs event-level or category-level rows:

- sale date;
- settlement date where applicable;
- instrument;
- amount;
- currency;
- source row/table;
- whether sale belongs to securities/PFI/IIS/non-IIS category;
- calculation status.

### 3.4. `extracted_tax_facts.operations.purchases_total`

Maps to:

```text
source_evidence.source_facts[]
tax_base_items[].expense_amount
fees_and_expenses[]
```

Current gap:

Purchases/cost basis should not be treated as a final deductible amount without methodology and deterministic calculation.

### 3.5. `extracted_tax_facts.operations.fees_total`

Maps to:

```text
fees_and_expenses[]
tax_base_items[].expense_amount candidate
review_state.uncertain[]
```

Current gap:

Fee eligibility and classification require methodology.

### 3.6. `extracted_tax_facts.operations.dividends_total`

Maps to:

```text
dividends_and_withholding[]
tax_base_items[]
income_categories[]
```

Current gap:

Needs source, country, currency, date, gross/net/withheld split and candidate official income code/status.

### 3.7. `extracted_tax_facts.operations.tax_withheld_total`

Maps to:

```text
dividends_and_withholding[].tax_withheld_amount
tax_base_items[]
review_state
```

Current gap:

Needs source, period, withholding agent/source and whether withholding is Russian or foreign.

### 3.8. `extracted_tax_facts.operations.foreign_tax_withheld_total`

Maps to:

```text
dividends_and_withholding[].foreign_tax_paid_amount
currency_context[]
review_state.uncertain[]
```

Current gap:

Needs foreign currency amount, declaration-currency conversion, date paid, country/source and official/customer methodology.

### 3.9. `aggregates`

Maps to:

```text
tax_base_items[]
currency_context[]
income_categories[]
review_state.uncertain[]
```

Current gap:

Aggregates must include:

- calculation source;
- deterministic vs model-derived flag;
- formula/methodology reference;
- official/customer methodology status.

## 4. Current Contract Insufficiencies

The current extraction contract is sufficient for:

- document inventory;
- source evidence wrappers;
- missing/uncertain/conflict review states;
- prompt-only JSON proof;
- fail-closed safety.

It is insufficient for:

- declaration target roles;
- official income group/type codes;
- tax-base item modeling;
- event-level securities operation ledgers;
- foreign income/currency conversion ledger;
- distinction between raw, normalized and calculated values;
- methodology-required vs official-confirmed decisions;
- source fact vs intermediate calculation vs declaration target separation.

## 5. Required Mapping Additions

Recommended new concepts:

| Concept | Why |
| --- | --- |
| `document_role` | Distinguish primary evidence, supporting evidence, instruction, tax form, duplicate, unrelated. |
| `target_model_relevance` | Show whether document can affect declaration model. |
| `declaration_relevance` | `declaration_target`, `source_fact`, `intermediate_calculation`, `review_only`, `not_for_declaration`. |
| `calculation_role` | Raw source, normalized item, calculated total, review-only context. |
| `methodology_status` | `official_confirmed`, `requires_customer_methodology`, `unknown`, `not_applicable`. |
| `source_granularity` | Document/page/table/row/cell/text excerpt. |
| `raw_value`, `normalized_value`, `calculated_value` | Prevent raw broker labels from masquerading as calculated declaration fields. |
| `calculation_required` | Identify deterministic steps. |
| `official_source_required` | Mark fields that require official source authority. |
| `customer_methodology_required` | Mark fields blocked by customer methodology. |

## 6. Mapping Outcome

The next proof should not validate only:

```text
input documents -> extraction JSON
```

It should validate:

```text
input documents
-> source facts with evidence
-> declaration-oriented target candidates
-> calculation/methodology gaps
-> specialist questions
-> review readiness
```

## 7. Sources

- [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md](BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md)
- [BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0.md](BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0.md)
- [BROKER_REPORTS_NDFL_REVERSE_DOMAIN_MODEL.md](../domain/BROKER_REPORTS_NDFL_REVERSE_DOMAIN_MODEL.md)
