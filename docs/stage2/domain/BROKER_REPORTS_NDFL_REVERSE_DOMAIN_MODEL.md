# Broker Reports NDFL Reverse Domain Model

Status: Draft reverse model
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL documentation refine

## 1. Purpose

This document reverses the Broker Reports epic from document-first extraction to declaration-oriented data modeling.

The working chain is:

```text
3-NDFL / declaration data model
-> declaration fields and official form sections
-> tax bases and income codes
-> intermediate calculation tables
-> source facts
-> source documents
-> LLM extraction contract
```

The goal is not automatic declaration filing. The goal is to prepare checkable declaration-oriented data for human specialist review.

## 2. Source Authority Legend

| Authority | Meaning |
| --- | --- |
| `official_fns` | Confirmed by FNS form, order, filling procedure or electronic format. |
| `official_law` | Confirmed by statutory/legal reference. |
| `customer_methodology_required` | Needs customer-approved methodology before use as a rule. |
| `layout_only` | Useful for finding facts in broker documents, not tax methodology. |
| `unknown` | Not confirmed; do not use for readiness. |

## 3. Official Source Baseline

| Source | Use in this model | Authority |
| --- | --- | --- |
| FNS 3-NDFL forms page | Confirms current and previous forms, filling procedures and electronic formats are separate official artifacts. | `official_fns` |
| FNS order `20.10.2025 N ED-7-11/913@` | Approves 2025 form, filling procedure and electronic format; KND `1151020`. | `official_fns` |
| 2025 3-NDFL form attachment | Confirms declaration title sheet, section 1, section 2, appendices and visible field labels. | `official_fns` |
| 2025 filling procedure attachment | Confirms declaration composition, appendix purpose, income group/code tables, foreign currency conversion rule and Appendix 8 securities scope. | `official_fns` |
| 2025 electronic format attachment | Confirms XML exchange format and formal nodes such as `NDFL3`, `SvNP`, `NalBaza`, `DohodIstRF`, `DohodIstIno`. | `official_fns` |
| FNS tax/buh reporting page | Defines tax declaration as official taxpayer statement about taxable objects, income, expenses, income sources, tax base, benefits and tax due/refund data. | `official_law` via FNS reference to Article 80 |
| Broker help pages | Explain broker report layout and vocabulary only. | `layout_only` |

## 4. Reverse Chain Overview

| Chain layer | Role | LLM may extract directly | Deterministic calculation required | Specialist confirmation required |
| --- | --- | --- | --- | --- |
| Declaration target | Data that can map to 3-NDFL fields/sections. | No, not without evidence and mapping. | Often yes. | Always for MVP. |
| Tax base | Income/expense/base amounts by official group/type. | Source components only; base result needs validation. | Yes. | Always. |
| Intermediate calculation | Normalized tables by source, currency, income type, expense category and period. | Partial draft only. | Yes for totals/conversions. | Always. |
| Source fact | Explicit fact from broker/source document. | Yes, if source evidence exists. | No, unless normalized. | Yes. |
| Source document | Broker report, operations table, tax withholding report, dividend report, tax form, help/instruction, unrelated. | Classification yes. | No. | Yes for ambiguous docs. |
| LLM extraction contract | Evidence-first JSON extraction layer. | Yes. | No final tax calculations. | Always. |

## 5. Declaration Model Elements

| Element | Official anchor | Target role | LLM direct extraction | Calculation required | Human confirmation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Tax period / reporting year | Title sheet and declaration context fields. | declaration target | Yes, from form/report labels. | No | Yes | Broker report period may not equal tax period. |
| Taxpayer identity | Title sheet taxpayer fields. | declaration target | Only from provided documents/user context. | No | Yes | Real personal data is not used in this task. |
| Taxpayer status/residency | Title sheet status fields and official codes. | declaration target | No, unless explicitly supplied. | No | Yes | Current broker report extraction should ask specialist. |
| Income source in RF | Appendix 1. | declaration target / source fact | Yes, if broker/tax agent source is explicit. | Maybe | Yes | Broker name is not always the taxable income source. |
| Foreign income source | Appendix 2. | declaration target / source fact | Yes, if source country/source name/currency are explicit. | Yes | Yes | Country, currency, date and tax paid details need exact evidence. |
| Tax base calculation | Section 2. | declaration target | No | Yes | Yes | Section 2 is a calculation target, not raw extraction. |
| Income amount | Section 2 / Appendices 1-2. | source fact / intermediate calculation | Yes, if explicitly visible. | Yes for grouping/normalization. | Yes | Amount must carry source, period and currency. |
| Expense amount | Section 2 / Appendix 8 for securities-related scope. | intermediate calculation / source fact | Yes for source fact, not deductibility. | Yes | Yes | Applicability requires methodology. |
| Withheld tax | Section 2 / Appendices 1-2. | source fact / declaration target | Yes, if explicit. | Maybe | Yes | Needs source and period. |
| Foreign tax paid | Section 2 / Appendix 2. | source fact / declaration target candidate | Yes, if explicit. | Yes | Yes | Credit/treatment requires official/customer methodology. |
| Currency conversion | Filling procedure rule for foreign-currency income/expenses. | intermediate calculation | No | Yes | Yes | Requires currency, date, rate source and methodology. |
| Securities / PFI / IIS operations | Appendix 8 and income code table. | intermediate calculation / source fact | Source facts yes. | Yes | Yes | Tax-base construction is not an LLM-only step. |
| Dividends | Appendix 1/2 and income group/code table. | source fact / declaration target candidate | Yes, if explicit. | Maybe | Yes | Code and rate mapping must follow official/customer methodology. |
| Fees and commissions | Appendix 8 expenses scope may be relevant. | source fact / intermediate calculation | Yes as source fact. | Yes | Yes | Whether included requires methodology. |

## 6. Officially Observed Relevant 2025 Form Sections

| Section | Declaration orientation | Broker-report relevance |
| --- | --- | --- |
| Title sheet | Taxpayer, period, correction, tax authority, status. | Mostly customer/user context, not broker report. |
| Section 1 | Tax payable/refund summary. | Downstream output only, not extraction target for first MVP. |
| Section 2 | Tax base and tax amount calculation. | Main declaration target for normalized data. |
| Appendix 1 | Income from sources in Russia. | Candidate target for RU broker/tax agent facts. |
| Appendix 2 | Income from sources outside Russia. | Candidate target for foreign broker/dividend/withholding facts. |
| Appendix 8 | Expenses/deductions for securities, PFI, digital financial assets/rights and investment partnerships. | Important for broker operations, but methodology-heavy. |

## 7. Officially Observed Income Code Signals

The 2025 filling procedure contains income group/type code tables. For broker-oriented modeling, only a small subset is relevant enough to seed review questions.

| Code group / type | Official meaning summary | Use now |
| --- | --- | --- |
| group `02`, type `001` | Resident tax base for equity participation income, including dividends. | Candidate for dividend-related mapping; confirm with specialist. |
| group `02`, type `003` | Resident tax base for securities/PFI operations not accounted on IIS, and related material benefit cases. | Candidate for securities operations mapping; methodology required. |
| group `02`, type `034` | Resident tax base for securities/PFI operations accounted on IIS. | Candidate for IIS-related mapping; methodology required. |

Do not treat this table as exhaustive. Add codes only after official source review and customer methodology review.

## 8. Intermediate Tables Needed

| Intermediate table | Why needed | Source authority | Deterministic calculation |
| --- | --- | --- | --- |
| Document inventory | Trace every source. | `official_fns` for declaration support docs concept; internal contract for manifest. | No |
| Source fact ledger | Preserve raw facts with evidence. | Internal extraction contract. | No |
| Income event ledger | Normalize income events by source, date, currency, income type and document. | `customer_methodology_required` | Yes |
| Securities operation ledger | Normalize purchases, sales, fees, quantities, instruments, dates and broker/source rows. | `official_fns` for Appendix 8 relevance; methodology for treatment. | Yes |
| Withholding ledger | Separate withheld tax by source, period, currency and country. | `official_fns` for Section 2 / Appendices 1-2. | Yes |
| Currency conversion ledger | Store currency, date, official rate source and declaration-currency amount. | `official_fns` filling procedure; official rate source/methodology required. | Yes |
| Declaration assertion ledger | Check semantic assertions instead of raw JSON equality. | Internal proof design. | Yes |

## 9. Source Facts From Broker Documents

LLM may extract these as source facts when evidence exists:

- broker/source name;
- report period;
- account/IIS marker;
- operation rows;
- income/dividend/coupon rows;
- fee/commission rows;
- tax withheld rows;
- currency labels;
- dates;
- section/table/source labels;
- page/sheet/row/column references.

LLM must not decide alone:

- final income code;
- final tax base;
- final deductibility of expenses;
- final currency conversion;
- final foreign tax credit;
- final readiness for declaration filing.

## 10. Required Refine Direction

The current `broker_reports_extraction_v0` remains useful as a source-fact layer. It should not become the declaration model.

The next layer should be:

```text
source evidence
-> source facts
-> normalized/intermediate calculation ledgers
-> declaration-oriented assertions
-> specialist review state
```

Status:

```text
DECLARATION_ORIENTED_MODEL_DRAFT_READY
OFFICIAL_REQUIREMENTS_PARTIAL
CUSTOMER_METHODOLOGY_REQUIRED
```

## 11. Sources

- https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/
- https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/
- https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx`
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_3.docx`
- https://www.nalog.gov.ru/rn77/taxation/submission_statements/
