# Broker Reports Synthetic Case 001 Ledger

Status: Synthetic economic ledger draft
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL prompt-only proof preparation

## 1. Purpose

`synthetic_case_001` is an independent synthetic economic ledger.

It is not:

- extraction JSON output;
- declaration JSON output;
- broker report rendering;
- XLS/XLSX artifact;
- real customer data;
- final tax calculation.

It is a controlled truth source for later generated source documents and semantic assertions.

## 2. Period And Authority

```json
{
  "case_id": "synthetic_case_001",
  "case_version": "v0",
  "tax_year": 2025,
  "official_source_set_id": "ru_3ndfl_2025_fns_order_2025_10_20",
  "methodology_assumptions_status": "placeholder"
}
```

2025 is the synthetic proof year only. It is not a customer scope assertion.

The 2025 official source set is used because the period-aware registry already contains draft requirement records for it. All customer-specific methodology assumptions remain `placeholder` or `requires_customer_methodology`.

## 3. Top-Level Ledger

```json
{
  "case_id": "synthetic_case_001",
  "case_version": "v0",
  "tax_year": 2025,
  "official_source_set_id": "ru_3ndfl_2025_fns_order_2025_10_20",
  "methodology_assumptions_status": "placeholder",
  "synthetic_identity": {
    "person_label": "Synthetic Person Alpha",
    "tax_identifier": null,
    "tax_identifier_placeholder": "SYNTH-TAX-ID-000000",
    "taxpayer_identifier_intentionally_absent": true,
    "residency_status": "requires_customer_methodology"
  },
  "accounts": [
    {
      "account_id": "SYNTH-BROKER-0001",
      "broker_name": "Synthetic Foreign Broker LLC",
      "broker_country": "SYNTH-FOREIGN-COUNTRY",
      "account_type": "non_iis_candidate",
      "account_type_methodology_status": "requires_customer_methodology"
    }
  ],
  "income_events": [
    {
      "ledger_event_id": "income_001",
      "income_label_raw": "Synthetic dividend for SYNTH-DIV",
      "income_kind_candidate": "dividend",
      "instrument_id": "SYNTH-DIV",
      "income_source_name": "Synthetic Foreign Broker LLC",
      "income_country": "SYNTH-FOREIGN-COUNTRY",
      "income_date": "2025-06-15",
      "amount": {
        "raw_value": "40.00",
        "normalized_value": "40.00",
        "currency": "SYNTH-FCY"
      },
      "official_requirement_refs": ["REQ-2025-FGN-001", "REQ-2025-WH-001", "REQ-2025-CODE-CAND-001"],
      "methodology_status": "requires_customer_methodology"
    }
  ],
  "securities_operations": [
    {
      "ledger_event_id": "operation_buy_001",
      "operation_label_raw": "BUY SYNTH-A",
      "instrument_id": "SYNTH-A",
      "operation_type": "buy",
      "trade_date": "2025-02-10",
      "settlement_date": "2025-02-12",
      "quantity": "10",
      "amount": {
        "raw_value": "900.00",
        "normalized_value": "900.00",
        "currency": "SYNTH-FCY"
      },
      "related_operation_refs": ["operation_sell_001"],
      "official_requirement_refs": ["REQ-2025-TB-001", "REQ-2025-APP8-001"],
      "calculation_required": true,
      "methodology_status": "requires_customer_methodology"
    },
    {
      "ledger_event_id": "operation_sell_001",
      "operation_label_raw": "SELL SYNTH-A",
      "instrument_id": "SYNTH-A",
      "operation_type": "sell",
      "trade_date": "2025-09-20",
      "settlement_date": "2025-09-22",
      "quantity": "10",
      "amount": {
        "raw_value": "1250.00",
        "normalized_value": "1250.00",
        "currency": "SYNTH-FCY"
      },
      "related_operation_refs": ["operation_buy_001"],
      "official_requirement_refs": ["REQ-2025-TB-001", "REQ-2025-APP8-001", "REQ-2025-CODE-CAND-002"],
      "calculation_required": true,
      "methodology_status": "requires_customer_methodology"
    }
  ],
  "fee_events": [
    {
      "ledger_event_id": "fee_buy_001",
      "fee_label_raw": "Buy commission SYNTH-A",
      "fee_date": "2025-02-10",
      "related_operation_refs": ["operation_buy_001"],
      "amount": {
        "raw_value": "5.00",
        "normalized_value": "5.00",
        "currency": "SYNTH-FCY"
      },
      "eligible_for_declaration_candidate": null,
      "official_requirement_refs": ["REQ-2025-APP8-001"],
      "calculation_required": true,
      "methodology_status": "requires_customer_methodology"
    },
    {
      "ledger_event_id": "fee_sell_001",
      "fee_label_raw": "Sell commission SYNTH-A",
      "fee_date": "2025-09-20",
      "related_operation_refs": ["operation_sell_001"],
      "amount": {
        "raw_value": "6.00",
        "normalized_value": "6.00",
        "currency": "SYNTH-FCY"
      },
      "eligible_for_declaration_candidate": null,
      "official_requirement_refs": ["REQ-2025-APP8-001"],
      "calculation_required": true,
      "methodology_status": "requires_customer_methodology"
    }
  ],
  "withholding_events": [
    {
      "ledger_event_id": "withholding_001",
      "withholding_label_raw": "Foreign tax withheld for SYNTH-DIV",
      "withholding_source": "Synthetic Foreign Broker LLC",
      "withholding_country": "SYNTH-FOREIGN-COUNTRY",
      "withholding_date": "2025-06-15",
      "amount": {
        "raw_value": "6.25",
        "normalized_value": "6.25",
        "currency": "SYNTH-FCY"
      },
      "related_income_event_refs": ["income_001"],
      "official_requirement_refs": ["REQ-2025-WH-001"],
      "methodology_status": "requires_customer_methodology"
    }
  ],
  "currency_events": [
    {
      "ledger_event_id": "currency_001",
      "source_currency": "SYNTH-FCY",
      "declaration_currency": "DECL-CCY",
      "source_amount_refs": ["operation_sell_001", "operation_buy_001", "fee_buy_001", "fee_sell_001", "income_001", "withholding_001"],
      "rate_date_candidate": "event_date",
      "rate_source_ref": null,
      "converted_amount": null,
      "official_requirement_refs": ["REQ-2025-CUR-001"],
      "calculation_required": true,
      "methodology_status": "requires_customer_methodology"
    }
  ],
  "intended_gaps": [
    {
      "gap_id": "gap_missing_tax_identifier",
      "type": "missing_data",
      "description": "Taxpayer identifier is intentionally absent.",
      "expected_review_state": "missing",
      "blocking": true
    },
    {
      "gap_id": "gap_currency_rate_rule",
      "type": "calculation_gap",
      "description": "Foreign-currency conversion requires deterministic rate source and date rule.",
      "expected_review_state": "calculation_gap",
      "blocking": true
    },
    {
      "gap_id": "gap_fee_eligibility",
      "type": "methodology_gap",
      "description": "Fee eligibility requires customer methodology.",
      "expected_review_state": "methodology_gap",
      "blocking": true
    }
  ],
  "intended_conflicts": [
    {
      "conflict_id": "conflict_summary_vs_operations_total",
      "description": "Broker summary sale total differs from operation table sale total.",
      "summary_value": "1245.00",
      "operation_table_value": "1250.00",
      "currency": "SYNTH-FCY",
      "expected_review_state": "conflict",
      "blocking": true
    }
  ],
  "expected_source_fact_assertions": [],
  "expected_declaration_model_assertions": [],
  "expected_review_state_assertions": []
}
```

## 4. Expected Source Fact Assertions

- `operation_buy_001` is extractable as `securities_operation_event`.
- `operation_sell_001` is extractable as `securities_operation_event`.
- `fee_buy_001` and `fee_sell_001` are extractable as `fee_events`.
- `income_001` is extractable as `income_event`.
- `withholding_001` is extractable as `withholding_event`.
- `currency_001` is extractable as `currency_event`.
- `raw_value` must be preserved for all visible source amounts.
- `normalized_value` must be mechanical only.
- No final tax base is produced by source fact extraction.

## 5. Expected Declaration Model Assertions

- `tax_year=2025` maps to period-aware declaration context only as synthetic proof year.
- `official_source_set_id=ru_3ndfl_2025_fns_order_2025_10_20` is present.
- Securities operation facts may map to tax-base candidates with `REQ-2025-TB-001` and `REQ-2025-APP8-001`.
- Dividend/withholding facts may map to dividend and withholding candidates with `REQ-2025-FGN-001` and `REQ-2025-WH-001`.
- Income code remains candidate because customer methodology is absent.
- Fees remain `requires_customer_methodology`.
- Currency conversion remains `calculation_required`.

## 6. Expected Review State Assertions

- Missing taxpayer identifier appears in `missing`.
- Summary/table mismatch appears in `conflicts`.
- Fee eligibility appears as methodology gap.
- Currency conversion appears as calculation gap.
- Questions to specialist include separate data, methodology and calculation questions.
- Readiness is only `ready_for_specialist_review` or lower.
- `tax_correctness_claimed=false`.
- `fns_filing_claimed=false`.
- `xlsx_generation_claimed=false`.

## 7. Status

```text
SYNTHETIC_CASE_001_LEDGER_DRAFT_READY
CUSTOMER_METHODOLOGY_REQUIRED
```
