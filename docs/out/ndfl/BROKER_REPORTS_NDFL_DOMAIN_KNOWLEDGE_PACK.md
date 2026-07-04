# Broker Reports NDFL Domain Knowledge Pack

Status: Draft domain pack
Date: 2026-07-04
Scope: OpenWebUI Knowledge / Skill / Prompt base for `broker_reports_extraction_v0`

## 1. Purpose

This pack supports the JSON extraction MVP only.

It helps an LLM:

- understand broker-report inputs;
- classify documents;
- extract tax-relevant facts into the v0 JSON contract;
- mark missing and uncertain data;
- detect conflicts;
- ask specialist-facing questions;
- avoid inventing tax methodology;
- avoid final tax correctness claims.

It does not provide final tax consultation, final 3-NDFL preparation, filing support, FNS integration or autonomous decision-making.

## 2. Source Policy

Use:

- official sources;
- public broker help-center descriptions;
- public/demo broker layouts;
- internal contract documents;
- customer methodology placeholders.

Do not use random articles as tax-law source of truth.

Any rule not confirmed by official source or customer methodology must be marked:

```text
requires_customer_methodology
```

## 3. Domain Vocabulary

| Term | Meaning for JSON extraction MVP | Methodology status |
| --- | --- | --- |
| Broker report / брокерский отчет | Broker-provided report describing account, operations, cash, positions, fees, income or tax-related entries. | layout/extraction concept |
| Purchase operation / операция покупки | Transaction where an asset is bought. | requires_customer_methodology for tax treatment |
| Sale operation / операция продажи | Transaction where an asset is sold or disposed. | requires_customer_methodology for tax treatment |
| Dividends / дивиденды | Income distribution from shares/funds. | requires_customer_methodology |
| Coupons / купоны | Income from debt instruments. | requires_customer_methodology |
| Fees / комиссии | Broker/exchange/service charges visible in reports. | requires_customer_methodology |
| Tax withheld / налог удержан брокером | Amount marked as withheld by broker/tax agent. | requires_customer_methodology |
| Foreign tax / иностранный налог | Tax withheld or paid outside RU source context. | requires_customer_methodology |
| Operation currency / валюта операции | Currency code or label attached to amount/operation. | extraction concept |
| Trade date / дата операции | Date when trade/order is executed. | extraction concept |
| Settlement date / дата расчетов | Date when trade settles or cash/securities move. | extraction concept |
| Financial result / финансовый результат | Profit/loss summary or calculated outcome. | requires_customer_methodology |
| IIS / ИИС | Individual investment account marker. | requires_customer_methodology |
| Tax agent / налоговый агент | Entity that withholds/reports tax. | requires_customer_methodology |
| Foreign broker / иностранный брокер | Broker outside RU jurisdiction. | requires_customer_methodology |
| Reporting period / отчетный период | Period covered by document/report. | extraction concept |
| Income source / источник дохода | Payer/source label for income. | requires_customer_methodology |
| Transaction table | Table with operation rows and columns. | extraction concept |
| Realized gains/losses | Realized result labels in US/generic statements. | layout/extraction only |
| Withholding | Tax withheld labels. | extraction concept |
| Cashflow | Deposits, withdrawals, cash movements and income postings. | extraction concept |
| Positions | Holdings/portfolio snapshot. | extraction concept |
| Fees | Charges/commissions/transaction cost section. | extraction concept |

## 4. Document To Data Map

| Document type | Typical data present | JSON extraction use | Warnings |
| --- | --- | --- | --- |
| `broker_report` | Broker name, account, report period, operation sections, income, fees, taxes, positions/cash sections. | Primary input for `document_manifest`, broker facts, operations and missing/uncertain/conflict checks. | Do not infer tax correctness from report alone. |
| `operations_table` | Rows with operation type, dates, asset, quantity, amount, fees, currency. | Machine-readable source for operations totals and source references. | Formulas/hidden sheets require deterministic parser proof. |
| `dividends_report` | Income entries, payer/source, date, currency, withheld tax labels. | Source for dividends/coupons/withholding facts. | Foreign withholding and credit treatment require customer methodology. |
| `tax_withholding_report` | Tax withheld by broker/tax agent, period, source. | Source for `tax_withheld_total` candidate. | Must be linked to period and source. |
| `cashflow_report` | Deposits, withdrawals, income postings, transfers. | Completeness support and possible source for dividends/coupons. | Not every cash movement is taxable income. |
| `positions_report` | Holdings at date, market values, asset identifiers. | Context only unless methodology requires positions. | Do not use as proof of sale/income without operations. |
| `fees_report` | Broker/exchange/service charges. | Source for fees candidate. | Deductibility/treatment requires customer methodology. |
| `consolidated_statement` | Multiple sections: portfolio, activity, income, fees, taxes. | Useful single source if readable and sectioned. | Must keep section-level evidence references. |
| `tax_form` | Official or broker-generated tax fields. | Classification, negative case or supporting source if customer methodology says so. | US/EU forms are not RU NDFL methodology. |
| `unrelated` | Bank statement, invoice, generic article, help page. | Negative classification. | Must not fabricate broker facts. |

## 5. Data To JSON Map

Detailed field mapping is maintained in:

- [BROKER_REPORTS_NDFL_FIELD_MAPPING.md](BROKER_REPORTS_NDFL_FIELD_MAPPING.md)

Core target sections:

- `document_manifest`;
- `extracted_tax_facts.taxpayer`;
- `extracted_tax_facts.broker`;
- `extracted_tax_facts.operations`;
- `extracted_tax_facts.documents`;
- `aggregates`;
- `missing_data`;
- `uncertain_data`;
- `conflicts`;
- `questions_to_specialist`;
- `readiness`.

## 6. Extraction Rules

Evidence-first:

- every extracted value must have an evidence wrapper;
- every document must appear in `document_manifest`;
- unsupported documents still appear in `document_manifest`;
- source references must match actual input representation.

Missing:

- if a required field is absent, write `missing_data`;
- ask a specialist question when missing data blocks readiness;
- do not infer missing identifiers from context.

Uncertain:

- ambiguous labels, weak OCR, unclear periods or conflicting table labels go to `uncertain_data`;
- do not promote low-trust raster reads to high confidence.

Conflict:

- if documents disagree, write `conflicts`;
- do not silently choose one value unless customer methodology defines a precedence rule.

Not applicable:

- if a field is irrelevant for a document/run, mark it `not_applicable`;
- do not treat `not_applicable` as missing.

## 7. Raster / Vision Boundary

Raster/photo/scanned PDFs are not production OCR support.

Behavior:

- classify as `raster_scan`, `photo` or `mixed_text_and_raster`;
- set `processing_mode` to `vision_llm_experimental` only when a vision path is actually used;
- otherwise use `unsupported` or `failed`;
- set `requires_manual_review = true`;
- avoid exact text-layer excerpts if no text layer exists;
- low-quality raster should produce missing/uncertain values, not invented facts.

## 8. Customer Methodology Placeholders

The customer still must provide:

- current CloudCowork/Claude prompts;
- current specialist methodology;
- required fields;
- accepted source-reference rules;
- examples of good output;
- anonymized broker reports;
- expected JSON and later expected XLS/XLSX artifacts;
- provider/data policy for broker/tax/financial documents;
- retention and access rules.

Until then:

```text
DOMAIN_CONTEXT_NEEDS_CUSTOMER_METHODOLOGY
```

## 9. Refusal And Limitation Rules

Refuse or limit:

- final tax advice;
- final declaration generation;
- FNS filing/submission claims;
- XLS/XLSX generation in the current JSON proof;
- unsupported scans as production extraction;
- use of real public personal/account documents;
- rules not present in official/customer methodology.

Safe response pattern:

```text
Current scope is JSON extraction draft support for specialist review. The output is not final tax advice, not a final 3-NDFL declaration and not an FNS submission.
```

## 10. OpenWebUI Packaging Recommendation

Later staging load should split content into:

- Knowledge: this domain pack, field mapping, review checklist, source registry and approved customer methodology;
- Prompts: prompt pack drafts after human review;
- Skill: extraction playbook after human review;
- Workspace Model instructions: compact responsibility boundary plus prompt references.

Do not load this pack into production Knowledge before human review.
