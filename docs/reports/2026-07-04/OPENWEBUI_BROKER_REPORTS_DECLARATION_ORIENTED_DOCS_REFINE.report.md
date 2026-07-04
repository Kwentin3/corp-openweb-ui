# OpenWebUI Broker Reports Declaration-Oriented Docs Refine Report

Date: 2026-07-04
Scope: documentation refine for Stage 2 `Broker Reports / XLS NDFL`
Runtime changes: none
Customer documents: not used

Outputs:

- [BROKER_REPORTS_NDFL_REVERSE_DOMAIN_MODEL.md](../../stage2/domain/BROKER_REPORTS_NDFL_REVERSE_DOMAIN_MODEL.md)
- [BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0.md](../../stage2/contracts/BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0.md)
- [BROKER_REPORTS_EXTRACTION_TO_DECLARATION_MAPPING.v0.md](../../stage2/contracts/BROKER_REPORTS_EXTRACTION_TO_DECLARATION_MAPPING.v0.md)
- [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md](../../stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md)
- [BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.v0_1_PROPOSAL.md](../../stage2/domain/BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.v0_1_PROPOSAL.md)
- [BROKER_REPORTS_DECLARATION_ORIENTED_PROMPT_PACK_PROPOSAL.md](../../stage2/prompts/BROKER_REPORTS_DECLARATION_ORIENTED_PROMPT_PACK_PROPOSAL.md)
- [BROKER_REPORTS_DECLARATION_ORIENTED_EXTRACTION_SKILL_PROPOSAL.md](../../stage2/skills/BROKER_REPORTS_DECLARATION_ORIENTED_EXTRACTION_SKILL_PROPOSAL.md)
- [BROKER_REPORTS_SYNTHETIC_CASE_LEDGER_DESIGN.md](../../stage2/testdata/BROKER_REPORTS_SYNTHETIC_CASE_LEDGER_DESIGN.md)

## 1. What Was Studied

Local documents:

- broker reports PRD;
- JSON extraction contract v0;
- JSON extraction proof plan;
- structured-output modes research;
- synthetic fixtures plan;
- public artifact pool research;
- synthetic fixtures from public layouts proposal;
- domain knowledge pack;
- field mapping;
- review checklist;
- source registry;
- prompt pack;
- skill draft;
- broker/docs/OCR/security blueprints and acceptance docs.

Official sources:

- FNS 3-NDFL forms page.
- FNS order `20.10.2025 N ED-7-11/913@`.
- 2025 3-NDFL form attachment.
- 2025 3-NDFL filling procedure attachment.
- 2025 3-NDFL electronic format attachment.
- FNS tax/buh reporting page referencing Article 80 declaration concept.
- FNS examples page was checked; examples found there are deduction-focused and were not used as broker methodology.

## 2. Official FNS Sources Used

Used as authority:

- current 2025 form/order/procedure/format;
- previous-period index on the FNS forms page;
- form structure from the 2025 PDF;
- filling procedure text from official DOCX;
- electronic format structure from official DOCX;
- FNS explanation of tax declaration as formal taxpayer statement.

New official artifacts collected:

- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx`
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_3.docx`
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/artifact.metadata.json`

## 3. Declaration Requirements Extracted

Extracted at documentation level:

- 3-NDFL is a formal declaration model, not a broker-report model.
- The 2025 form is KND `1151020`.
- The form includes title sheet, Section 1, attachment to Section 1, Section 2, Appendices 1-8 and calculation attachments.
- Section 2 is the tax-base and tax amount calculation target.
- Appendix 1 covers income from Russian sources.
- Appendix 2 covers income from foreign sources.
- Appendix 8 is relevant to expenses/deductions for securities/PFI/DFA/digital-rights and investment partnership operations.
- Filling procedure contains official income group/type code tables.
- For broker-oriented review, official candidate signals include group `02` / type `001` for dividends, `003` for securities/PFI outside IIS-related scope and `034` for securities/PFI on IIS.
- Foreign-currency income/expenses require declaration-currency conversion using Bank of Russia rate on relevant income/expense date.

These are partial official requirements. They are not a full tax methodology.

## 4. Official vs Customer Methodology

Official/FNS/law layer:

- declaration form identity;
- KND;
- form sections;
- official filling procedure;
- official electronic format;
- official code table existence and selected candidate codes;
- foreign-currency conversion principle from the filling procedure;
- formal declaration concept from Article 80 reference.

Customer methodology required:

- which fields are mandatory for the customer workflow;
- source precedence;
- when broker report period maps to tax period;
- how to categorize broker rows;
- how to handle fees/commissions;
- how to handle IIS cases;
- how to handle foreign withholding/credit;
- how to validate rates and conversion;
- how to define expected review output;
- when later XLS stage may start.

## 5. Reverse Chain

Refined chain:

```text
3-NDFL declaration model
-> declaration fields and official form sections
-> tax bases and income group/type codes
-> intermediate ledgers for income, securities operations, withholding, fees and currency
-> source facts with evidence
-> broker/source documents
-> LLM extraction contract
```

This replaces the weaker chain:

```text
broker document -> any JSON -> possible XLS
```

## 6. JSON Extraction Contract Changes

Do not break `broker_reports_extraction_v0`.

Recommended v0.1 additions:

- `document_role`;
- `source_document_class`;
- `target_model_relevance`;
- `declaration_relevance`;
- `calculation_role`;
- `methodology_status`;
- `official_source_required`;
- `customer_methodology_required`;
- `source_granularity`;
- `raw_value`;
- `normalized_value`;
- `calculated_value`;
- `calculation_required`;
- `not_for_declaration`;
- `review_only`;
- source-fact ledgers for income, operations, withholding, fees and currency.

Key point: current totals in `extracted_tax_facts.operations` are too coarse for declaration-oriented modeling.

## 7. Prompt / Skill Changes

Prompts should lead the model through:

```text
classify documents
-> extract source facts
-> map to declaration model
-> identify calculation gaps
-> find missing methodology
-> detect conflicts
-> ask specialist questions
-> check declaration-oriented review readiness
```

Skill should separate:

- source facts;
- intermediate calculations;
- declaration-oriented target data;
- review-only context;
- unsupported tax logic.

## 8. Synthetic Fixtures Direction

Use `Synthetic economic case ledger` as independent truth.

Do not generate reports directly from extraction JSON.

New flow:

```text
synthetic economic case ledger
-> generated source documents
-> expected declaration-oriented assertions
-> expected extraction assertions
```

Validation should use semantic assertions, not full JSON snapshot equality.

## 9. Why Customer Sample Docs Were Not Used

They were not provided and the task forbids customer sample docs.

This refine is based on:

- official FNS sources;
- existing internal docs;
- public layout-only sources from the previous discovery pack;
- synthetic-only design.

Production acceptance still requires anonymized customer samples and expected outputs.

## 10. Next Steps

Recommended sequence:

1. Human review of reverse model and declaration data model.
2. Customer methodology request.
3. Official source review for exact period/codes needed by pilot.
4. Synthetic case ledger generation.
5. Generate source documents from ledger.
6. Prompt-only source-fact extraction proof.
7. Declaration mapping proof.
8. Decide whether v0.1 extraction schema or separate source-facts schema is cleaner.
9. Only after proof, consider staging Knowledge/Prompt/Skill load.

## 11. Status

Final statuses:

- `DECLARATION_ORIENTED_MODEL_DRAFT_READY`
- `OFFICIAL_REQUIREMENTS_PARTIAL`
- `CUSTOMER_METHODOLOGY_REQUIRED`
- `READY_FOR_HUMAN_REVIEW`

Not claimed:

- final tax correctness;
- automatic declaration;
- FNS filing;
- XLS/XLSX generation;
- implementation blueprint;
- production runtime change.

## 12. Sources

- https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/
- https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/
- https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf
- https://www.nalog.gov.ru/rn77/taxation/submission_statements/
- https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/primer_3ndfl/
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_2.docx`
- `docs/stage2/testdata/public_artifacts/fns_order_3_ndfl_2025/16589324_3.docx`
