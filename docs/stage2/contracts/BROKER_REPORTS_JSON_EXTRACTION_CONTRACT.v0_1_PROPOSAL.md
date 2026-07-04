# Broker Reports JSON Extraction Contract v0.1 Proposal

Status: Contract refinement proposal
Date: 2026-07-04
Base contract: `broker_reports_extraction_v0`
Target: declaration-oriented source-fact extraction

## 1. Purpose

This proposal does not replace `broker_reports_extraction_v0`.

It describes changes needed so the extraction contract can better support the declaration-oriented model:

```text
source documents
-> source facts
-> intermediate calculations
-> declaration-oriented target data
-> specialist review
```

## 2. Compatibility Rule

Do not break v0:

- keep `schema_version: broker_reports_extraction_v0` for existing proof;
- create a later version only after human review;
- keep all current top-level keys;
- add optional fields first;
- preserve fail-closed behavior and manual review warning.

## 3. Proposed New Top-Level Field

Add optional:

```json
{
  "declaration_model_alignment": {
    "target_model_version": "broker_reports_ndfl_declaration_model_v0",
    "alignment_status": "not_started | source_facts_only | partially_mapped | mapped_with_gaps | failed",
    "official_requirements_status": "partial | sufficient_for_synthetic_proof | insufficient",
    "customer_methodology_status": "missing | partial | approved",
    "notes": []
  }
}
```

Rationale:

The extraction output should say whether it is merely a source-fact extraction or already mapped toward declaration review.

## 4. `document_manifest` Refinement

Add optional fields to each document:

```json
{
  "document_role": "primary_evidence | supporting_evidence | tax_form | instruction | help_article | duplicate | unrelated | unknown",
  "source_document_class": "broker_report | tax_form | broker_help | official_instruction | customer_methodology | synthetic_fixture | unknown",
  "target_model_relevance": "high | medium | low | none | unknown",
  "declaration_relevance": "source_fact | intermediate_calculation | declaration_target | review_only | not_for_declaration | unknown",
  "source_granularity_available": ["document", "page", "table", "row", "cell", "text_excerpt"],
  "not_for_declaration": false,
  "review_only": false
}
```

Why:

The current manifest records document format/readability. It does not say how the document participates in the declaration-oriented model.

## 5. Evidence Wrapper Refinement

Add optional fields to every evidence wrapper:

```json
{
  "raw_value": null,
  "normalized_value": null,
  "calculated_value": null,
  "calculation_role": "source_fact | normalized_fact | intermediate_calculation | declaration_target_candidate | review_only",
  "calculation_required": false,
  "methodology_status": "official_confirmed | requires_customer_methodology | not_applicable | unknown",
  "official_source_required": false,
  "customer_methodology_required": false,
  "source_granularity": "document | page | table | row | cell | text_excerpt | inferred"
}
```

Rules:

- `raw_value` is copied from source evidence.
- `normalized_value` is standardized without tax-base calculation.
- `calculated_value` requires deterministic calculation proof.
- `source_fact` may be LLM-extracted if evidence is visible.
- `declaration_target_candidate` requires specialist review.

## 6. `extracted_tax_facts` Refinement

Current fields are total-oriented. Add source-fact ledgers:

```json
{
  "source_facts": {
    "income_events": [],
    "operation_events": [],
    "withholding_events": [],
    "fee_events": [],
    "currency_events": []
  }
}
```

Each event should carry:

- event ID;
- source document ID;
- raw labels;
- source refs;
- amount;
- currency;
- date;
- confidence;
- declaration relevance;
- methodology status.

Why:

Declaration-oriented review needs event-level facts before totals.

## 7. `aggregates` Refinement

Add:

```json
{
  "calculation_trace": [],
  "calculation_required": true,
  "deterministic_calculation_performed": false,
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- LLM-only totals are review candidates, not final calculations.
- If deterministic calculation was not performed, readiness cannot imply declaration readiness.

## 8. Review State Refinement

Extend missing/uncertain/conflict/question items with:

```json
{
  "target_model_path": null,
  "source_fact_id": null,
  "methodology_gap": false,
  "official_source_gap": false,
  "declaration_impact": "blocking | warning | none | unknown"
}
```

Why:

The reviewer must know whether a gap blocks extraction, declaration mapping or only later XLS work.

## 9. `readiness` Refinement

Add:

```json
{
  "source_fact_readiness": "ready | needs_more_data | not_ready | failed",
  "declaration_mapping_readiness": "ready_for_specialist_review | needs_methodology | needs_calculation | not_ready | failed",
  "calculation_readiness": "not_started | deterministic_required | partial | complete_for_synthetic_assertions",
  "staging_load_readiness": "not_ready | ready_for_human_review | ready_for_synthetic_proof"
}
```

Preserve:

- `manual_review_required = true`;
- `tax_correctness_claimed = false`;
- `fns_filing_claimed = false`;
- no XLS/XLSX generation claim.

## 10. Fields Requested By The Refine Task

| Requested field | Proposal status |
| --- | --- |
| `document_role` | Add to `document_manifest`. |
| `source_document_class` | Add to `document_manifest`. |
| `target_model_relevance` | Add to `document_manifest`. |
| `declaration_relevance` | Add to document and fact wrappers. |
| `calculation_role` | Add to fact wrappers/events. |
| `methodology_status` | Add to facts/aggregates/review state. |
| `official_source_required` | Add to fact/review state. |
| `customer_methodology_required` | Add to fact/review state. |
| `source_granularity` | Add to fact wrapper. |
| `raw_value` | Add to fact wrapper/events. |
| `normalized_value` | Add to fact wrapper/events. |
| `calculated_value` | Add to fact wrapper/events; requires deterministic proof. |
| `calculation_required` | Add to fact wrapper/events/aggregates. |
| `not_for_declaration` | Add to document/fact. |
| `review_only` | Add to document/fact. |

## 11. Non-Goals

This proposal does not:

- define final 3-NDFL output;
- define XLS/XLSX columns;
- implement calculations;
- choose provider/model;
- load prompts/Knowledge into OpenWebUI;
- claim production tax correctness.

## 12. Next Step

After human review, create either:

- `broker_reports_extraction_v0_1` as an additive proof schema; or
- a separate source-facts schema feeding `broker_reports_ndfl_declaration_model_v0`.

Prefer the separate source-facts schema if v0 becomes too broad.
