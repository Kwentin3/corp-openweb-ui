# Broker Reports NDFL Official Requirements Registry

Status: Draft registry after human review
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL docs-only refine

## 1. Purpose

This registry records official requirements as checkable records.

It is not a free-form explanation of 3-NDFL and not a customer methodology. It gives the declaration-oriented model a period-aware authority layer:

```text
official source set for a tax year
-> requirement records
-> declaration model paths
-> extraction relevance
-> methodology gaps
```

Every pilot tax year must have its own `official_source_set_id`. The 2025 form/order can seed 2025 review only. It must not be treated as universal for all years.

## 2. Official Source Sets

| official_source_set_id | tax_year | form_year | status | official sources | notes |
| --- | --- | --- | --- | --- | --- |
| `ru_3ndfl_2025_fns_order_2025_10_20` | `2025` | `2025` | collected_partial_review | `fns_forms_page`, `fns_order_3ndfl_2025`, `fns_form_3ndfl_2025_pdf`, `fns_filling_procedure_2025_docx`, `fns_electronic_format_2025_docx`, `fns_tax_declaration_definition_page` | Use only for 2025-oriented draft records until specialist confirms applicability. |
| `pilot_year_pending` | `TBD` | `TBD` | missing | `TBD` | Required before synthetic or staging proof claims for any pilot tax year not explicitly set to 2025. |

## 3. Source IDs

| official_source_id | official_source_type | source path | authority | status |
| --- | --- | --- | --- | --- |
| `fns_forms_page` | `fns_page` | https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/ | `official_fns` | source index |
| `fns_order_3ndfl_2025` | `fns_page` | https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/ | `official_fns` | order page |
| `fns_form_3ndfl_2025_pdf` | `form` | `docs/stage2/testdata/public_artifacts/fns_form_3_ndfl_2025/16589324_1.pdf` | `official_fns` | collected |
| `fns_filling_procedure_2025_docx` | `filling_procedure` | `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx` | `official_fns` | collected |
| `fns_electronic_format_2025_docx` | `electronic_format` | `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_3.docx` | `official_fns` | collected |
| `fns_tax_declaration_definition_page` | `law` | https://www.nalog.gov.ru/rn77/taxation/submission_statements/ | `official_law` | FNS page citing tax declaration definition |

## 4. Requirement Records

| requirement_id | tax_year | form_year | official_source_id | official_source_type | source_path_or_section | requirement_summary | declaration_model_path | applies_to | authority | extraction_relevance | methodology_status | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `REQ-2025-DECL-001` | `2025` | `2025` | `fns_order_3ndfl_2025` | `fns_page` | order metadata | The 2025 order approves the 3-NDFL form, filling procedure and electronic format for KND `1151020`. | `declaration_context.target_form` | `declaration_context` | `official_fns` | establish target form identity | `official_confirmed_for_2025_only` | Do not reuse for other tax years without a matching official source set. |
| `REQ-2025-DECL-002` | `2025` | `2025` | `fns_order_3ndfl_2025` | `fns_page` | order applicability statement | The collected 2025 source set applies from the 2025 tax period. | `declaration_context.period_applicability` | `declaration_context` | `official_fns` | blocks cross-year assumptions | `official_confirmed_for_2025_only` | Pilot tax year must be explicit before proof. |
| `REQ-2025-DECL-003` | `2025` | `2025` | `fns_tax_declaration_definition_page` | `law` | tax declaration definition | A declaration is an official taxpayer statement about taxable objects, income, expenses, income sources, tax base and calculation data. | `review_state.readiness.tax_correctness_claimed` | `review_state` | `official_law` | confirms that extraction output is not a final declaration | `official_confirmed_generic` | Use as boundary rule, not field mapping. |
| `REQ-2025-CTX-001` | `2025` | `2025` | `fns_form_3ndfl_2025_pdf` | `form` | title sheet | Title sheet contains period, correction, tax authority and taxpayer context. | `declaration_context` | `declaration_context` | `official_fns` | extract only visible period/context facts | `requires_customer_methodology` | Broker report period may not equal tax period. |
| `REQ-2025-CTX-002` | `2025` | `2025` | `fns_form_3ndfl_2025_pdf` | `form` | title sheet taxpayer status fields | Taxpayer status/residency-like context belongs to declaration context and requires confirmation. | `declaration_context.taxpayer_status` | `declaration_context` | `official_fns` | ask specialist if absent or inferred | `requires_customer_methodology` | Do not infer from broker layout. |
| `REQ-2025-RF-001` | `2025` | `2025` | `fns_form_3ndfl_2025_pdf` | `form` | Appendix 1 | Appendix 1 is the target area for income from sources in Russia. | `income_categories[]`, `dividends_and_withholding[]` | `income_category` | `official_fns` | classify candidate source facts by source jurisdiction | `requires_customer_methodology` | Broker name is not always the taxable income source. |
| `REQ-2025-FGN-001` | `2025` | `2025` | `fns_form_3ndfl_2025_pdf` | `form` | Appendix 2 | Appendix 2 is the target area for income from sources outside Russia and related foreign-source details. | `dividends_and_withholding[]`, `currency_context[]` | `income_category` | `official_fns` | preserve country/source/currency/date facts | `requires_customer_methodology` | Foreign tax treatment needs methodology. |
| `REQ-2025-TB-001` | `2025` | `2025` | `fns_form_3ndfl_2025_pdf` | `form` | Section 2 | Section 2 is a tax-base and tax amount calculation target, not a raw extraction target. | `tax_base_items[]` | `tax_base` | `official_fns` | source facts may feed it; LLM totals are not final | `requires_customer_methodology` | Deterministic calculation and review required. |
| `REQ-2025-WH-001` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | Section 2 / Appendices 1-2 relation | Withheld and foreign-paid tax values must preserve source and target calculation context. | `dividends_and_withholding[]` | `withholding` | `official_fns` | extract explicit withholding facts with evidence | `requires_customer_methodology` | Credit/treatment decisions are not LLM-only. |
| `REQ-2025-CUR-001` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | foreign-currency income/expenses rule | Foreign-currency income and deductible expenses require conversion using the official rate context for the relevant date. | `currency_context[]` | `currency` | `official_fns` | preserve currency, amount, date and rate-source gaps | `requires_customer_methodology` | This docs task does not implement rate lookup. |
| `REQ-2025-APP8-001` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | Appendix 8 purpose | Appendix 8 covers expenses/deductions for securities, derivative instruments and related operations. | `fees_and_expenses[]`, `tax_base_items[]` | `appendix_8` | `official_fns` | keep securities/fee/expense source facts event-level | `requires_customer_methodology` | Expense eligibility is methodology-heavy. |
| `REQ-2025-EFMT-001` | `2025` | `2025` | `fns_electronic_format_2025_docx` | `electronic_format` | XML structure nodes | Electronic format includes formal declaration structure nodes such as taxpayer, tax-base and income-source areas. | `source_authority_refs`, `declaration_model_path` | `declaration_context` | `official_fns` | supports field authority and path review | `requires_customer_methodology` | Do not map directly to production XML in Stage 2. |
| `REQ-2025-CODE-CAND-001` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | income group/type code table | Candidate signal: group `02`, type `001` may be relevant to dividend/equity participation review. | `income_categories[]` | `income_category` | `official_fns` | seed specialist question only | `candidate_signal_only` | Not an autonomous rule. Confirm for target pilot year and customer methodology. |
| `REQ-2025-CODE-CAND-002` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | income group/type code table | Candidate signal: group `02`, type `003` may be relevant to securities/PFI operations outside IIS-related scope. | `income_categories[]`, `tax_base_items[]` | `income_category` | `official_fns` | seed specialist question only | `candidate_signal_only` | Not exhaustive. Confirm before synthetic expected assertions. |
| `REQ-2025-CODE-CAND-003` | `2025` | `2025` | `fns_filling_procedure_2025_docx` | `filling_procedure` | income group/type code table | Candidate signal: group `02`, type `034` may be relevant to IIS-related securities/PFI operations. | `income_categories[]`, `tax_base_items[]` | `income_category` | `official_fns` | seed specialist question only | `candidate_signal_only` | IIS treatment requires customer methodology. |

## 5. Registry Rules

- `official_confirmed_for_2025_only` means the record is confirmed only for the 2025 source set.
- `candidate_signal_only` means the record can generate questions, not declaration assertions.
- `requires_customer_methodology` means official structure exists, but customer-approved business treatment is missing.
- Any synthetic case ledger must name the `official_source_set_id` it targets.
- Any staging proof must fail closed if `tax_year`, `form_year` or `official_source_set_id` is missing.

## 6. Status

```text
PERIOD_AWARE_OFFICIAL_REGISTRY_DRAFT_READY
CUSTOMER_METHODOLOGY_REQUIRED
```
