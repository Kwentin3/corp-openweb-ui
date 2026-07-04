# Broker Reports NDFL Declaration Data Model v0.1 Proposal

Status: Period-aware proposal, does not replace v0
Date: 2026-07-04
Base model: `broker_reports_ndfl_declaration_model_v0`

## 1. Purpose

This proposal makes the declaration data model period-aware without breaking v0.

The v0 model remains a useful declaration-oriented target. v0.1 adds explicit fields that prevent accidental reuse of the 2025 official source set for another tax year.

## 2. Compatibility Rule

Do not modify existing v0 semantics:

- keep v0 paths stable;
- add v0.1 fields as optional proposal fields;
- require human review before treating any v0.1 field as accepted contract;
- do not add XLS/XLSX generation or filing semantics.

## 3. Proposed Top-Level Additions

```json
{
  "schema_version": "broker_reports_ndfl_declaration_model_v0_1_proposal",
  "declaration_model_version": "v0.1-proposal",
  "period_applicability": {
    "tax_year": null,
    "form_year": null,
    "form_version": null,
    "official_source_set_id": null,
    "period_status": "missing | candidate | confirmed_for_review",
    "notes": []
  },
  "official_requirement_refs": [],
  "source_authority_refs": []
}
```

## 4. `period_applicability`

Purpose: make the target tax year and official form year explicit.

Suggested fields:

| Field | Meaning | Required before synthetic proof |
| --- | --- | --- |
| `tax_year` | Tax period being modeled. | Yes |
| `form_year` | Form/procedure/format year used as official source basis. | Yes |
| `form_version` | Human-readable form/order identifier. | Yes |
| `official_source_set_id` | Registry source set, for example `ru_3ndfl_2025_fns_order_2025_10_20`. | Yes |
| `period_status` | `missing`, `candidate`, or `confirmed_for_review`. | Yes |
| `period_mismatch_warning` | Warning when broker report period and tax year are not proven equivalent. | Conditional |

Rules:

- `tax_year` and `form_year` may match, but must still be recorded separately.
- `form_year=2025` is not a default for other pilot years.
- If the pilot year is unknown, readiness must remain `not_ready`.

## 5. Official Requirement References

Every declaration model item that relies on official structure should carry registry references.

Example:

```json
{
  "target_model_path": "tax_base_items[]",
  "official_requirement_refs": ["REQ-2025-TB-001", "REQ-2025-APP8-001"],
  "source_authority_refs": [
    {
      "official_source_set_id": "ru_3ndfl_2025_fns_order_2025_10_20",
      "official_source_id": "fns_form_3ndfl_2025_pdf",
      "requirement_id": "REQ-2025-TB-001"
    }
  ],
  "methodology_status": "requires_customer_methodology"
}
```

Rules:

- `official_requirement_refs` cite official structure or period applicability.
- `methodology_status` still controls whether the value can become a declaration assertion.
- Candidate code references must remain candidate signals until confirmed for the target period and methodology.

## 6. Changes To Existing v0 Areas

### `declaration_context`

Add:

```json
{
  "tax_year": null,
  "form_year": null,
  "form_version": null,
  "official_source_set_id": null,
  "official_requirement_refs": [],
  "period_applicability": {}
}
```

### `income_categories[]`

Add:

```json
{
  "official_requirement_refs": [],
  "candidate_signal": false,
  "confirmed_for_tax_year": false
}
```

Reason: observed 2025 income code signals are not automatic rules for other years.

### `tax_base_items[]`

Add:

```json
{
  "official_requirement_refs": [],
  "source_fact_schema_refs": [],
  "calculation_methodology_ref": null
}
```

Reason: tax-base items must cite both official target structure and source-fact inputs.

### `dividends_and_withholding[]`

Add:

```json
{
  "official_requirement_refs": [],
  "withholding_source_fact_refs": [],
  "foreign_tax_methodology_status": "requires_customer_methodology"
}
```

### `fees_and_expenses[]`

Add:

```json
{
  "official_requirement_refs": [],
  "expense_eligibility_status": "requires_customer_methodology",
  "appendix_8_relevance": "candidate | not_applicable | unknown"
}
```

### `currency_context[]`

Add:

```json
{
  "official_requirement_refs": [],
  "rate_policy_status": "requires_customer_methodology",
  "rate_source_ref": null
}
```

## 7. Readiness Refinement

Extend `review_state.readiness`:

```json
{
  "period_applicability_confirmed": false,
  "official_source_set_confirmed": false,
  "official_requirement_refs_present": false,
  "source_facts_schema_available": false,
  "customer_methodology_available": false,
  "ready_for_specialist_review": false
}
```

Readiness remains specialist-review readiness only. It is not tax correctness, filing readiness or XLS/XLSX readiness.

## 8. Relationship To Source Facts Schema

v0.1 declaration model should not absorb event-level extraction details.

Use:

```text
BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL
-> declaration model source_fact refs
-> declaration model target candidates
```

This keeps the declaration model focused on target data and review state.

## 9. Status

```text
DECLARATION_DATA_MODEL_V0_1_PROPOSAL_READY
PERIOD_AWARE_OFFICIAL_REGISTRY_REQUIRED
CUSTOMER_METHODOLOGY_REQUIRED
```
