# Broker Reports Source Facts Schema v0 Proposal

Status: Source-facts contract proposal
Date: 2026-07-04
Related contracts:
- `BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md`
- `BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md`
- `BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0_1_PROPOSAL.md`

> 2026-07-10 status note: retained as historical domain input. The canonical
> Gate 2 execution and system-of-record design is now
> `BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md` plus
> `BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md`. This older proposal must not be
> used as the Gate 2 run/package, issue carry-forward, validator, persistence,
> or prompt contract.

## 1. Purpose

This schema extracts event-level facts from source documents without turning the extraction contract into a broad declaration model.

Preferred layering:

```text
document taxonomy
-> document inventory
-> source facts schema
-> intermediate ledgers
-> declaration model
-> specialist review
```

## 2. Why Separate Source Facts

Do not expand `broker_reports_extraction_v0` into one large contract that tries to cover:

- file intake;
- source document classification;
- event-level facts;
- tax-base methodology;
- declaration target fields;
- review readiness.

That would make the contract hard to validate and too easy to overclaim.

A separate source facts schema is better because:

- source extraction remains evidence-first;
- declaration mapping can cite source-fact IDs instead of raw document rows;
- methodology gaps can be separated from official-source gaps;
- synthetic cases can assert event semantics without snapshotting a giant JSON object;
- future deterministic calculations can consume a stable event ledger.

## 3. Top-Level Shape

```json
{
  "schema_version": "broker_reports_source_facts_v0_proposal",
  "source_facts_set_id": null,
  "document_inventory_refs": [],
  "source_fact_events": {
    "income_events": [],
    "securities_operation_events": [],
    "fee_events": [],
    "withholding_events": [],
    "currency_events": []
  },
  "source_evidence_refs": [],
  "review_state": {
    "missing": [],
    "uncertain": [],
    "conflicts": []
  }
}
```

## 4. Shared Event Envelope

Every event should carry:

```json
{
  "source_fact_id": "sf_001",
  "event_type": null,
  "document_inventory_refs": [],
  "source_evidence_refs": [],
  "raw_value": null,
  "normalized_value": null,
  "source_granularity": "document | page | table | row | cell | text_excerpt | mixed | unknown",
  "confidence": "high | medium | low | not_available",
  "methodology_status": "not_applicable | requires_customer_methodology | official_confirmed | unknown",
  "declaration_relevance": "source_fact | intermediate_calculation_input | declaration_candidate | review_only | not_for_declaration | unknown",
  "review_only": false,
  "calculation_required": false,
  "notes": []
}
```

Rules:

- `raw_value` must be copied from visible source evidence or marked unavailable.
- `normalized_value` may only perform mechanical normalization, such as date shape or numeric parsing.
- `calculation_required=true` means downstream deterministic calculation is needed.
- `review_only=true` prevents direct declaration mapping.

## 5. Document Inventory References

`document_inventory_refs[]` points to classified documents from the extraction manifest or taxonomy layer.

Required reference fields:

```json
{
  "document_id": null,
  "document_taxonomy_class": null,
  "document_role": null,
  "can_be_source_evidence": null
}
```

Instruction/template/example documents must not be referenced as source evidence unless the taxonomy class allows it.

## 6. `income_events[]`

Purpose: capture explicit income facts before category/code mapping.

Suggested fields:

```json
{
  "source_fact_id": "income_event_001",
  "event_type": "income_event",
  "income_label_raw": null,
  "income_kind_candidate": null,
  "income_source_name": null,
  "income_country": null,
  "income_date": null,
  "amount": {
    "raw_value": null,
    "normalized_value": null,
    "currency": null
  },
  "official_requirement_refs": [],
  "methodology_status": "requires_customer_methodology"
}
```

Examples: dividends, coupons, sale income rows, other broker-reported income rows.

## 7. `securities_operation_events[]`

Purpose: capture operation rows used later by deterministic ledgers.

Suggested fields:

```json
{
  "source_fact_id": "securities_operation_001",
  "event_type": "securities_operation_event",
  "operation_label_raw": null,
  "instrument_name": null,
  "instrument_identifier": null,
  "operation_date": null,
  "settlement_date": null,
  "quantity": null,
  "amount": {
    "raw_value": null,
    "normalized_value": null,
    "currency": null
  },
  "account_marker": null,
  "official_requirement_refs": [],
  "calculation_required": true,
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- do not calculate final gain/loss in this schema;
- preserve source rows even when income code is unknown;
- mark IIS/account-specific treatment as methodology-dependent.

## 8. `fee_events[]`

Purpose: capture broker fees, commissions and expense-like rows as source facts.

Suggested fields:

```json
{
  "source_fact_id": "fee_event_001",
  "event_type": "fee_event",
  "fee_label_raw": null,
  "fee_category_candidate": null,
  "fee_date": null,
  "amount": {
    "raw_value": null,
    "normalized_value": null,
    "currency": null
  },
  "eligible_for_declaration_candidate": null,
  "official_requirement_refs": [],
  "calculation_required": true,
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- a fee source fact is not automatically declaration-eligible;
- eligibility requires official/customer methodology.

## 9. `withholding_events[]`

Purpose: capture explicit tax withheld or foreign tax paid facts.

Suggested fields:

```json
{
  "source_fact_id": "withholding_event_001",
  "event_type": "withholding_event",
  "withholding_label_raw": null,
  "withholding_source": null,
  "withholding_country": null,
  "withholding_date": null,
  "amount": {
    "raw_value": null,
    "normalized_value": null,
    "currency": null
  },
  "related_income_event_refs": [],
  "official_requirement_refs": [],
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- preserve withheld tax separately from income;
- do not decide final treatment without methodology.

## 10. `currency_events[]`

Purpose: capture currency facts and conversion inputs.

Suggested fields:

```json
{
  "source_fact_id": "currency_event_001",
  "event_type": "currency_event",
  "source_currency": null,
  "source_amount": null,
  "rate_date_candidate": null,
  "rate_source_ref": null,
  "converted_amount": null,
  "official_requirement_refs": [],
  "calculation_required": true,
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- this schema may preserve a visible converted amount if the document contains one;
- it does not implement rate lookup;
- rate date selection remains methodology-dependent unless explicitly confirmed.

## 11. Review State

Review items should include:

```json
{
  "issue_id": null,
  "issue_type": "missing | uncertain | conflict",
  "source_fact_refs": [],
  "document_inventory_refs": [],
  "official_requirement_refs": [],
  "methodology_gap": false,
  "official_source_gap": false,
  "blocking": true,
  "question_to_specialist": null
}
```

## 12. Status

```text
SOURCE_FACTS_SCHEMA_PROPOSAL_READY
CUSTOMER_METHODOLOGY_REQUIRED
```
