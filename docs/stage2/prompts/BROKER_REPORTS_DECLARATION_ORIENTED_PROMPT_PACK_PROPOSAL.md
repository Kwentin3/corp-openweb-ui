# Broker Reports Declaration-Oriented Prompt Pack Proposal

Status: Prompt refinement proposal, not loaded
Date: 2026-07-04
Base prompt pack: [BROKER_REPORTS_JSON_EXTRACTION_PROMPT_PACK.md](BROKER_REPORTS_JSON_EXTRACTION_PROMPT_PACK.md)

## 1. Purpose

Refine broker prompts from plain JSON extraction toward:

```text
classify documents
-> extract source facts
-> map source facts to declaration-oriented data model
-> identify intermediate calculations needed
-> mark missing methodology
-> ask specialist questions
-> produce readiness for specialist review
```

Do not load these prompts into OpenWebUI before human review.

## 2. Shared Safety Frame

Every prompt must include:

- no final tax correctness claim;
- no automatic declaration generation claim;
- no FNS filing claim;
- no XLS/XLSX generation in this task;
- source evidence required for extracted facts;
- official/customer methodology required for tax-base decisions;
- human review mandatory.

## 3. `/broker_classify_documents`

Purpose:

- classify every input before extraction.

Input requirements:

- filenames/source labels;
- readable text/table snippets or processing notes;
- whether input is synthetic/public/customer-approved.

Expected output:

- `document_manifest`;
- `document_role`;
- `source_document_class`;
- `declaration_relevance`;
- unsupported/unrelated/help/tax-form classifications.

Contract/model sections:

- `broker_reports_extraction_v0.document_manifest`;
- `source_evidence.document_inventory`.

Failure behavior:

- if unreadable or raster without approved vision path, mark unsupported/experimental and stop source fact extraction.

## 4. `/broker_extract_source_facts`

Purpose:

- extract raw source facts with evidence, not declaration targets.

Input requirements:

- classified documents;
- visible source content;
- source granularity available.

Expected output:

- source fact ledger;
- raw labels/values;
- source refs;
- confidence;
- methodology status.

Contract/model sections:

- `extracted_tax_facts`;
- proposed `source_facts`;
- `source_evidence.source_facts`.

Failure behavior:

- if a value lacks source evidence, mark inferred/review-only or omit as extracted.

## 5. `/broker_map_to_declaration_model`

Purpose:

- map source facts to declaration-oriented target candidates.

Input requirements:

- source fact ledger;
- declaration data model;
- official source registry;
- customer methodology if available.

Expected output:

- candidate `declaration_context`;
- candidate `income_categories`;
- candidate `tax_base_items`;
- candidate `dividends_and_withholding`;
- candidate `fees_and_expenses`;
- candidate `currency_context`;
- mapping gaps.

Contract/model sections:

- `BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0`.

Failure behavior:

- if official/customer methodology is missing, mark `requires_customer_methodology` and ask questions.

## 6. `/broker_identify_calculation_gaps`

Purpose:

- identify deterministic calculations needed before specialist review.

Input requirements:

- source fact ledger;
- mapped declaration target candidates;
- current calculation trace.

Expected output:

- missing calculation inputs;
- required calculation type;
- whether calculation can be synthetic proof only;
- whether a tool/parser is required later.

Typical gaps:

- securities operation totals;
- cost basis;
- fee eligibility;
- foreign-currency conversion;
- foreign tax paid conversion;
- income category/code selection;
- report period vs tax period mismatch.

Failure behavior:

- do not compute final values if deterministic calculation is not available.

## 7. `/broker_find_missing_methodology`

Purpose:

- separate data gaps from methodology gaps.

Input requirements:

- mapped model;
- source facts;
- official source notes;
- customer methodology status.

Expected output:

- methodology gaps;
- official source gaps;
- customer questions;
- blocked model paths.

Failure behavior:

- if a tax rule is not in official/customer sources, mark `requires_customer_methodology`.

## 8. `/broker_detect_conflicts`

Purpose:

- identify conflicts across source facts and declaration candidates.

Input requirements:

- source facts;
- document inventory;
- mapped declaration target candidates.

Expected output:

- conflicts with source refs;
- conflict impact: source fact, calculation, declaration model or review-only;
- questions for specialist.

Failure behavior:

- do not resolve conflicts without precedence rules.

## 9. `/broker_questions_to_specialist`

Purpose:

- generate human-review questions from data, methodology and calculation gaps.

Input requirements:

- missing data;
- uncertain facts;
- conflicts;
- calculation gaps;
- methodology gaps.

Expected output:

- prioritized questions;
- category: data, methodology, calculation, source conflict, official-source gap;
- blocking flag.

Failure behavior:

- do not ask specialists to confirm invented values.

## 10. `/broker_declaration_readiness_check`

Purpose:

- decide whether the package is ready for specialist review of declaration-oriented data.

Input requirements:

- extraction JSON;
- declaration model draft;
- validation/gap lists.

Expected output:

- source fact readiness;
- declaration mapping readiness;
- calculation readiness;
- methodology readiness;
- next step.

Readiness is not:

- final tax correctness;
- FNS filing readiness;
- XLS generation readiness.

## 11. Old Prompt Mapping

| Current prompt | Refine action |
| --- | --- |
| `/broker_intake` | Keep, but add declaration target period/methodology status. |
| `/broker_classify_documents` | Extend with document role and declaration relevance. |
| `/broker_extract_json` | Split into `/broker_extract_source_facts` and `/broker_map_to_declaration_model`. |
| `/broker_find_missing_data` | Extend with missing methodology and missing calculation inputs. |
| `/broker_detect_conflicts` | Keep, add declaration impact. |
| `/broker_questions_to_specialist` | Keep, add question category. |
| `/broker_readiness_check` | Replace/extend with `/broker_declaration_readiness_check`. |
| `/broker_raster_extraction_experiment` | Keep as Track B only; never production OCR. |

## 12. Load Gate

Do not load into staging until:

- official source review is accepted;
- customer methodology placeholders are approved;
- declaration model v0 is reviewed;
- synthetic case ledger design is accepted;
- prompt wording is reviewed for overclaiming.
