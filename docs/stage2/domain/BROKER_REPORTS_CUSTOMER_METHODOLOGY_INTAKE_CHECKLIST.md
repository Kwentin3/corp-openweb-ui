# Broker Reports Customer Methodology Intake Checklist

Status: Draft intake checklist
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL methodology questions

## 1. Purpose

This checklist collects methodology decisions required before synthetic case generation or staging proof can claim readiness beyond source-fact extraction.

Do not use customer sample documents in this docs-only refine. This checklist is for structured questions and acceptance planning.

## 2. Pilot Scope

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-SCOPE-001` | Which tax years are in pilot scope? | Selects `official_source_set_id` and period-specific requirements. | yes |
| `METH-SCOPE-002` | Which brokers, countries and source systems are in scope? | Defines document classes and country/source handling. | yes |
| `METH-SCOPE-003` | Which account types are in scope, including IIS or non-IIS accounts? | Drives Appendix 8 and candidate code review. | yes |
| `METH-SCOPE-004` | Which income types are in scope: sales, dividends, coupons, securities operations, other income? | Defines source fact event coverage. | yes |
| `METH-SCOPE-005` | Which document types are required for a complete package? | Defines missing-data rules. | yes |

## 3. Income Categories And Codes

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-CODE-001` | Which income group/type codes does the customer methodology use for each in-scope income type? | Candidate official codes cannot be promoted without approval. | yes |
| `METH-CODE-002` | Are 2025 candidate code signals acceptable only for 2025, or should other years be separately reviewed? | Prevents cross-period assumptions. | yes |
| `METH-CODE-003` | How should mixed income rows be split or flagged? | Prevents invalid grouping. | yes |
| `METH-CODE-004` | Which source takes precedence when a broker summary and detailed rows disagree? | Controls conflict resolution. | yes |

## 4. Fees, Expenses And Securities Operations

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-EXP-001` | Which broker fees or commissions are treated as source facts only, and which may feed declaration review? | Avoids treating every fee as eligible. | yes |
| `METH-EXP-002` | Which expense categories require Appendix 8 review? | Connects fee events to official requirements. | yes |
| `METH-EXP-003` | What source granularity is sufficient for securities operation rows: summary, table row, cell, or statement section? | Sets evidence requirements. | yes |
| `METH-EXP-004` | Which intermediate ledgers does the specialist expect: income events, securities operations, fee events, withholding, currency, declaration assertions? | Defines review output. | yes |
| `METH-EXP-005` | How should corporate actions be represented: split, merger, redemption, spin-off, cancellation, reclassification? | Prevents unsupported operation treatment. | yes |

## 5. Dividends, Coupons And Withholding

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-WH-001` | How should dividends and coupons be separated from other income rows? | Defines income event classification. | yes |
| `METH-WH-002` | Which source is authoritative for withheld tax facts? | Defines evidence precedence. | yes |
| `METH-WH-003` | How should foreign tax paid be represented before specialist review? | Prevents final credit/treatment claims. | yes |
| `METH-WH-004` | What evidence is required for country/source attribution? | Supports Appendix 1/2 candidate mapping. | yes |

## 6. Currency Handling

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-CUR-001` | Which exchange-rate source and rate date rule should be used for each event type? | Required before currency calculations. | yes |
| `METH-CUR-002` | Should source documents' own converted values be preserved as source facts or ignored until deterministic calculation? | Defines currency event handling. | yes |
| `METH-CUR-003` | How should missing currency labels or mixed-currency summaries be treated? | Defines missing/uncertain states. | yes |

## 7. Readiness And Acceptance

| question_id | question | why it matters | blocking |
| --- | --- | --- | --- |
| `METH-READY-001` | What conditions make a result `ready_for_specialist_review`? | Defines readiness gate. | yes |
| `METH-READY-002` | Which official requirement refs must be present for acceptance? | Connects registry to model. | yes |
| `METH-READY-003` | What expected outputs are needed for acceptance: event ledgers, declaration candidates, questions, conflict report, or synthetic assertions? | Defines proof artifacts. | yes |
| `METH-READY-004` | Which unresolved issues are acceptable warnings, and which block the next step? | Defines review severity. | yes |
| `METH-READY-005` | Should the next step prioritize `synthetic_case_001` design or methodology intake completion? | Selects delivery path. | no |

## 8. Status

```text
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_CUSTOMER_INTAKE
```
