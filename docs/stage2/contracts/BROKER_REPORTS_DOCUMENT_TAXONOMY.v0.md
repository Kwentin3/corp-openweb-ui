# Broker Reports Document Taxonomy v0

Status: Draft taxonomy after human review
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL document classification

## 1. Purpose

This taxonomy prevents the workflow from mixing document roles.

The same corpus may contain broker evidence, official forms, instructions, examples, templates, public layouts and synthetic fixtures. Only some classes can support source facts; fewer can support methodology.

## 2. Taxonomy Table

| class | role in workflow | can_be_source_evidence | can_be_methodology | can_be_loaded_to_knowledge | declaration_relevance | safety notes |
| --- | --- | --- | --- | --- | --- | --- |
| `source_broker_report` | Primary evidence document from a broker or tax agent. | yes | no | after_review | source facts and conflicts | Customer sample handling policy required for real documents. |
| `operations_table` | Table of trades, operations or security movements. | yes | no | after_review | securities operation events | Do not infer tax base directly from operation rows. |
| `dividends_report` | Source rows or summary for dividends/coupons/income. | yes | no | after_review | income and withholding events | Mixed income types require specialist review. |
| `withholding_report` | Explicit withholding or foreign tax paid facts. | yes | no | after_review | withholding events | Treatment is methodology-dependent. |
| `fees_report` | Fees, commissions and expense-like rows. | yes | no | after_review | fee events and Appendix 8 candidates | Eligibility is not automatic. |
| `currency_rate_table` | Source or official table with currency/rate context. | conditional | conditional | after_review | currency events | Must preserve rate source/date; do not perform unapproved lookup. |
| `official_form` | Official declaration form or blank. | no | conditional | yes | target structure | Official form is authority for fields, not taxpayer source evidence. |
| `official_filling_instruction` | Official filling procedure/instruction. | no | conditional | yes | official requirements | Use for official requirement refs; not source facts. |
| `official_electronic_format` | Official exchange/XML format. | no | conditional | yes | formal structure | Do not imply production XML generation. |
| `methodology_instruction` | Customer-approved methodology. | no | yes | after_review | mapping and calculation rules | Required before methodology-dependent readiness. |
| `calculation_template` | Customer or internal calculation workbook/template. | no | conditional | after_review | intermediate ledgers | Template is not evidence unless it contains approved source facts. |
| `tax_base_calculation` | Specialist-produced or deterministic calculation output. | conditional | conditional | after_review | tax-base candidates | Must cite source facts and method. |
| `explanation_template` | Narrative/explanation skeleton. | no | no | after_review | review output only | Never treat wording template as tax rule. |
| `expected_output_example` | Example of desired output. | no | conditional | after_review | acceptance shape | Can define format expectations, not source facts. |
| `broker_help_article` | Broker help page about reports or sections. | no | no | yes | layout/context only | Useful for labels; not tax methodology. |
| `public_layout_sample` | Public sample statement/form layout. | no | no | after_review | parser/layout tests | Avoid real-person data and usage-restricted samples. |
| `synthetic_fixture` | Generated fixture for test/proof. | yes | no | yes | controlled proof source facts | Must be labeled synthetic and not customer evidence. |
| `customer_sample_pending_review` | Customer-provided sample not cleared for use. | no | no | no | blocked | Do not load or use in this task. |
| `unrelated` | Document unrelated to broker/NDFL workflow. | no | no | no | none | Keep in manifest and exclude from extraction. |
| `unsupported` | Unreadable, unsafe or unsupported document. | no | no | no | none | Mark blocker or request readable replacement. |

## 3. Classification Rules

- Classify before extraction.
- A document can have one primary class and optional secondary tags.
- `official_form`, `official_filling_instruction` and `official_electronic_format` can support `official_requirement_refs`, but not taxpayer source facts.
- `broker_help_article`, `public_layout_sample`, `expected_output_example` and `explanation_template` must not become source evidence.
- `methodology_instruction` must be customer-approved before it can drive mappings or calculation rules.
- `synthetic_fixture` can be source evidence only inside synthetic proof.
- `customer_sample_pending_review` remains blocked until policy and approval are explicit.

## 4. Manifest Fields

Document classification should expose:

```json
{
  "document_id": null,
  "document_taxonomy_class": null,
  "secondary_tags": [],
  "can_be_source_evidence": "yes | no | conditional",
  "can_be_methodology": "yes | no | conditional",
  "can_be_loaded_to_knowledge": "yes | no | after_review",
  "declaration_relevance": "source_fact | official_requirement | methodology | review_output | layout_only | none",
  "safety_notes": []
}
```

## 5. Status

```text
DOCUMENT_TAXONOMY_READY
CUSTOMER_METHODOLOGY_REQUIRED
```
