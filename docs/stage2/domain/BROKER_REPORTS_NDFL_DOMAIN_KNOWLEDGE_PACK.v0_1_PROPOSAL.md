# Broker Reports NDFL Domain Knowledge Pack v0.1 Proposal

Status: Domain knowledge refinement proposal
Date: 2026-07-04
Base document: [BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.md](BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.md)

## 1. Purpose

Refocus the domain pack from:

```text
what broker reports look like
```

to:

```text
what declaration-oriented data is needed
-> how source facts appear in broker documents
-> what calculations/methodology are missing
-> what specialist questions are required
```

## 2. New Top-Level Frame

Add a declaration-oriented frame at the start:

```text
The broker report is not the target. The declaration-oriented data model is the target. Broker reports are evidence sources for source facts that may feed intermediate calculation ledgers and specialist-reviewed declaration target fields.
```

## 3. Revised Knowledge Layers

| Layer | Description | Authority |
| --- | --- | --- |
| Official declaration model | 3-NDFL form, filling procedure and electronic format. | `official_fns` |
| Declaration target fields | Tax period, income source, tax base, withholding, foreign income and Appendix 8-related items. | `official_fns` / `customer_methodology_required` |
| Intermediate calculation ledgers | Income events, securities operations, withholding, fees, currency conversion. | `customer_methodology_required` |
| Source facts | Values from broker reports and other documents with evidence refs. | extraction contract |
| Document layouts | Broker report sections, operations tables, dividends/fees/withholding sections. | `layout_only` |
| Review state | Missing, uncertain, conflicts, questions and readiness. | internal contract |

## 4. Terms To Add

Add these terms:

- declaration target;
- source fact;
- intermediate calculation;
- declaration-oriented assertion;
- income group code;
- income type code;
- tax base item;
- foreign income source;
- currency conversion context;
- Appendix 8 securities/PFI expense context;
- methodology gap;
- official source gap;
- semantic assertion.

## 5. Terms To Reframe

| Current term | Refine |
| --- | --- |
| Broker report | Evidence source, not target model. |
| Operations table | Source fact ledger seed, not final tax-base table. |
| Dividends report | Source for dividend/withholding facts; code/treatment requires review. |
| Fees | Source fact; declaration eligibility requires methodology. |
| Financial result | Intermediate calculation candidate, not LLM final output. |
| Foreign tax | Source fact plus currency/country/date context; credit treatment requires methodology. |

## 6. New Document-To-Declaration Map

Add table:

| Source document pattern | Source facts | Intermediate ledger | Declaration target candidate | Methodology gap |
| --- | --- | --- | --- | --- |
| Broker report header | broker name, account, period | document inventory | context only | report period vs tax period |
| Operations table | operation rows, dates, amounts, currency | securities operation ledger | tax base candidate | cost basis/tax code |
| Dividends section | income amount, source, withholding | dividend/withholding ledger | Appendix 1/2 candidate | source country/code/treatment |
| Fees section | fee rows/amounts | fees/expenses ledger | expense candidate | eligibility |
| Foreign income section | country, currency, date, foreign tax | currency/foreign withholding ledger | Appendix 2 candidate | conversion/credit rules |
| Tax form | official/form labels | review-only or supporting evidence | depends on jurisdiction | foreign forms not RU methodology |

## 7. New Extraction Rules

Add:

- extract source facts first;
- keep raw labels and raw values;
- only normalize when transformation is mechanical and visible;
- mark calculation-needed fields;
- never turn LLM totals into final tax base;
- ask methodology questions separately from data questions;
- classify every value as source fact, intermediate calculation candidate, declaration target candidate or review-only context.

## 8. Revised Refusal Rules

Add refusal/limitation cases:

- user asks to infer final income code without official/customer methodology;
- user asks to compute final tax base from unclear broker rows;
- user asks to treat broker help page as tax law;
- user asks to use US/foreign forms as Russian NDFL methodology;
- user asks to proceed to XLS/final declaration from source facts only.

## 9. Knowledge Pack Load Recommendation

For future OpenWebUI staging:

1. Load official-source registry and reverse domain model first.
2. Load declaration data model.
3. Load source-fact extraction rules.
4. Load customer methodology only after approval.
5. Keep broker help pages as layout vocabulary, not methodology.

## 10. Next Step

Human reviewer should decide whether this proposal becomes:

- `BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.v0_1.md`; or
- a separate declaration-model Knowledge document alongside the existing pack.
