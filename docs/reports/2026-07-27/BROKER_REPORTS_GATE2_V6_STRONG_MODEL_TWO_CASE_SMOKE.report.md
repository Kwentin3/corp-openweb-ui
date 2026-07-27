# Broker Reports — Gate 2 V6 Strong Model Semantic Smoke

- Exact model: `claude-haiku-4-5-20251001`
- Scope: the two frozen synthetic smoke cases only.
- Semantic Pack, Prompt, Semantic Packet, Candidate Compiler, Typed Options, Choice schema, expected answers, validator, materializer and smoke cases: unchanged.
- Safe receipt: [BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.receipt.safe.json](./BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.receipt.safe.json)
- Qualification benchmark: not run.

## Execution continuity

The first execute process checkpointed one successful typed provider response, then stopped locally because the new report projector rejected the adapter-extracted JSON string before rendering it as an object. The provider answer, normalized Choice, materialization and replay had already passed and were preserved.

- Interrupted one-case checkpoint: [BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE_INTERRUPTED_AFTER_TYPED.receipt.safe.json](./BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE_INTERRUPTED_AFTER_TYPED.receipt.safe.json)
- The continuation validated that checkpoint and current frozen-authority parity, skipped the completed typed case, and submitted only the missing unclassified case.
- This was one bounded continuation, not a retry of either provider submission.

## Acceptance

- `PROVIDER_SUBMISSIONS`: `TWO`
- `TECHNICAL_PIPELINE`: `PASSED`
- `TYPED_SMOKE`: `PASSED`
- `UNCLASSIFIED_SMOKE`: `PASSED`
- `MODEL_INPUT_VISIBLE`: `YES`
- `EXACT_MODEL_OUTPUT_VISIBLE`: `YES`
- `EXPECTED_VS_ACTUAL_DIFF`: `EXPLICIT`
- `FALLBACK_REPAIR_HIDDEN_RETRY`: `ZERO`
- `DOCUMENTATION`: `UPDATED_IN_SAME_PR`

## Case: `syn_successor_v2_unique_cash`

### 1. CASE PURPOSE

Verify that the unambiguous synthetic cash-balance context selects the prebound cash_balance_snapshot_v1 typed option.

### 2. WHAT THE MODEL SAW

#### Task instruction

```json
{
  "ambiguity_rule": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.",
  "semantic_operation": "select_prebound_typed_option_or_unclassified"
}
```

#### Source context

```json
{
  "associations": [
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "human_summary": "deterministic reference association linking 2 source values",
      "source_value_refs": [
        "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label",
        "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope"
      ]
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "human_summary": "table row association linking 4 source values",
      "source_value_refs": [
        "syn_successor_v2_unique_cash:primary:value:amount",
        "syn_successor_v2_unique_cash:primary:value:currency",
        "syn_successor_v2_unique_cash:primary:value:date",
        "syn_successor_v2_unique_cash:primary:value:label"
      ]
    }
  ],
  "source_values": [
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "-120.5000",
      "source_value_ref": "syn_successor_v2_unique_cash:primary:value:amount",
      "value_type": "source_decimal",
      "visible_context": {
        "column_meaning": "amount",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "RUB",
      "source_value_ref": "syn_successor_v2_unique_cash:primary:value:currency",
      "value_type": "source_currency",
      "visible_context": {
        "column_meaning": "currency",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "2026-03-01",
      "source_value_ref": "syn_successor_v2_unique_cash:primary:value:date",
      "value_type": "source_date",
      "visible_context": {
        "column_meaning": "as_of_date",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "Cash balance",
      "source_value_ref": "syn_successor_v2_unique_cash:primary:value:label",
      "value_type": "source_text",
      "visible_context": {
        "column_meaning": "description",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "row:syn_successor_v2_unique_cash:primary",
      "source_value_ref": "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label",
      "value_type": "source_reference",
      "visible_context": {
        "column_meaning": null,
        "row_role": null,
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_unique_cash:primary",
      "source_value": "row:syn_successor_v2_unique_cash:primary",
      "source_value_ref": "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope",
      "value_type": "source_reference",
      "visible_context": {
        "column_meaning": null,
        "row_role": null,
        "section_role": null,
        "visible_label": null
      }
    }
  ]
}
```

#### Available financial type cards

```json
[
  {
    "ambiguity_rule": "Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.",
    "input_type_id": "cash_balance_snapshot_v1",
    "key_semantic_distinctions": [
      {
        "against": "printed_financial_metric_v1",
        "rule": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
      },
      {
        "against": "cash_movement",
        "rule": "A movement is an event over time; this type is a state at one reporting date."
      }
    ],
    "optional_roles": [
      {
        "role_id": "balance_class",
        "value_type": "source_text"
      },
      {
        "role_id": "currency",
        "value_type": "source_currency"
      },
      {
        "role_id": "source_label",
        "value_type": "source_text"
      },
      {
        "role_id": "unit",
        "value_type": "source_unit"
      }
    ],
    "required_roles": [
      {
        "role_id": "amount",
        "value_type": "source_decimal"
      },
      {
        "role_id": "as_of_date",
        "value_type": "source_date"
      },
      {
        "role_id": "statement_scope",
        "value_type": "source_reference"
      }
    ],
    "short_meaning": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash."
  },
  {
    "ambiguity_rule": "Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.",
    "input_type_id": "printed_financial_metric_v1",
    "key_semantic_distinctions": [
      {
        "against": "cash_balance_snapshot_v1",
        "rule": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
      },
      {
        "against": "gate2_calculated_aggregate",
        "rule": "This type preserves a total printed by the source; a value calculated by Gate 2 is never this type."
      }
    ],
    "optional_roles": [
      {
        "role_id": "as_of_date",
        "value_type": "source_date"
      },
      {
        "role_id": "currency",
        "value_type": "source_currency"
      },
      {
        "role_id": "period",
        "value_type": "source_period"
      },
      {
        "role_id": "source_label",
        "value_type": "source_text"
      },
      {
        "role_id": "unit",
        "value_type": "source_unit"
      }
    ],
    "required_roles": [
      {
        "role_id": "amount",
        "value_type": "source_decimal"
      },
      {
        "role_id": "printed_label_evidence_ref",
        "value_type": "source_reference"
      },
      {
        "role_id": "statement_scope",
        "value_type": "source_reference"
      }
    ],
    "short_meaning": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2."
  }
]
```

#### All typed options

```json
[
  {
    "input_type_id": "printed_financial_metric_v1",
    "option_id": "financial-typed-option:744e3c95321e39b5f068c13cb76c72ae",
    "prebound_role_values": [
      {
        "human_summary": "amount is prebound to -120.5000",
        "role_id": "amount",
        "source_value": "-120.5000",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:amount",
        "value_type": "source_decimal",
        "visible_context": {
          "column_meaning": "amount",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "as_of_date is prebound to 2026-03-01",
        "role_id": "as_of_date",
        "source_value": "2026-03-01",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:date",
        "value_type": "source_date",
        "visible_context": {
          "column_meaning": "as_of_date",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "currency is prebound to RUB",
        "role_id": "currency",
        "source_value": "RUB",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:currency",
        "value_type": "source_currency",
        "visible_context": {
          "column_meaning": "currency",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "printed_label_evidence_ref is prebound to row:syn_successor_v2_unique_cash:primary",
        "role_id": "printed_label_evidence_ref",
        "source_value": "row:syn_successor_v2_unique_cash:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "source_label is prebound to Cash balance",
        "role_id": "source_label",
        "source_value": "Cash balance",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:label",
        "value_type": "source_text",
        "visible_context": {
          "column_meaning": "description",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "statement_scope is prebound to row:syn_successor_v2_unique_cash:primary",
        "role_id": "statement_scope",
        "source_value": "row:syn_successor_v2_unique_cash:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      }
    ]
  },
  {
    "input_type_id": "cash_balance_snapshot_v1",
    "option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f",
    "prebound_role_values": [
      {
        "human_summary": "amount is prebound to -120.5000",
        "role_id": "amount",
        "source_value": "-120.5000",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:amount",
        "value_type": "source_decimal",
        "visible_context": {
          "column_meaning": "amount",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "as_of_date is prebound to 2026-03-01",
        "role_id": "as_of_date",
        "source_value": "2026-03-01",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:date",
        "value_type": "source_date",
        "visible_context": {
          "column_meaning": "as_of_date",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "currency is prebound to RUB",
        "role_id": "currency",
        "source_value": "RUB",
        "source_value_ref": "syn_successor_v2_unique_cash:primary:value:currency",
        "value_type": "source_currency",
        "visible_context": {
          "column_meaning": "currency",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "statement_scope is prebound to row:syn_successor_v2_unique_cash:primary",
        "role_id": "statement_scope",
        "source_value": "row:syn_successor_v2_unique_cash:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      }
    ]
  }
]
```

#### Unclassified selection

```json
{
  "disposition": "unclassified_financial_input",
  "reason_codes": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

### 3. EXPECTED ANSWER

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

### 4. EXACT MODEL ANSWER

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

### 5. NORMALIZED ANSWER

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

### 6. MECHANICAL COMPARISON

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"typed_input"` | `"typed_input"` | `YES` |
| `typed_option_id` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | `YES` |

Overall exact match: `YES`.

### 7. DIAGNOSIS

`NONE` — The normalized semantic answer exactly matches the frozen expected answer.

Technical pipeline: `PASSED`.

## Case: `syn_successor_v2_no_registry_type`

### 1. CASE PURPOSE

Verify that the synthetic broker-fee context, unsupported by every available registry type card, selects unclassified with no_registry_type.

### 2. WHAT THE MODEL SAW

#### Task instruction

```json
{
  "ambiguity_rule": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.",
  "semantic_operation": "select_prebound_typed_option_or_unclassified"
}
```

#### Source context

```json
{
  "associations": [
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "human_summary": "deterministic reference association linking 2 source values",
      "source_value_refs": [
        "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label",
        "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope"
      ]
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "human_summary": "table row association linking 4 source values",
      "source_value_refs": [
        "syn_successor_v2_no_registry_type:primary:value:amount",
        "syn_successor_v2_no_registry_type:primary:value:currency",
        "syn_successor_v2_no_registry_type:primary:value:date",
        "syn_successor_v2_no_registry_type:primary:value:label"
      ]
    }
  ],
  "source_values": [
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "42.25",
      "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:amount",
      "value_type": "source_decimal",
      "visible_context": {
        "column_meaning": "amount",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "CHF",
      "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:currency",
      "value_type": "source_currency",
      "visible_context": {
        "column_meaning": "currency",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "2026-03-04",
      "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:date",
      "value_type": "source_date",
      "visible_context": {
        "column_meaning": "date",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "table_row",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "Broker fee detail",
      "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:label",
      "value_type": "source_text",
      "visible_context": {
        "column_meaning": "description",
        "row_role": "fact_candidate",
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "row:syn_successor_v2_no_registry_type:primary",
      "source_value_ref": "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label",
      "value_type": "source_reference",
      "visible_context": {
        "column_meaning": null,
        "row_role": null,
        "section_role": null,
        "visible_label": null
      }
    },
    {
      "association_kind": "deterministic_reference",
      "association_ref": "row:syn_successor_v2_no_registry_type:primary",
      "source_value": "row:syn_successor_v2_no_registry_type:primary",
      "source_value_ref": "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope",
      "value_type": "source_reference",
      "visible_context": {
        "column_meaning": null,
        "row_role": null,
        "section_role": null,
        "visible_label": null
      }
    }
  ]
}
```

#### Available financial type cards

```json
[
  {
    "ambiguity_rule": "Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.",
    "input_type_id": "cash_balance_snapshot_v1",
    "key_semantic_distinctions": [
      {
        "against": "printed_financial_metric_v1",
        "rule": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
      },
      {
        "against": "cash_movement",
        "rule": "A movement is an event over time; this type is a state at one reporting date."
      }
    ],
    "optional_roles": [
      {
        "role_id": "balance_class",
        "value_type": "source_text"
      },
      {
        "role_id": "currency",
        "value_type": "source_currency"
      },
      {
        "role_id": "source_label",
        "value_type": "source_text"
      },
      {
        "role_id": "unit",
        "value_type": "source_unit"
      }
    ],
    "required_roles": [
      {
        "role_id": "amount",
        "value_type": "source_decimal"
      },
      {
        "role_id": "as_of_date",
        "value_type": "source_date"
      },
      {
        "role_id": "statement_scope",
        "value_type": "source_reference"
      }
    ],
    "short_meaning": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash."
  },
  {
    "ambiguity_rule": "Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.",
    "input_type_id": "printed_financial_metric_v1",
    "key_semantic_distinctions": [
      {
        "against": "cash_balance_snapshot_v1",
        "rule": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
      },
      {
        "against": "gate2_calculated_aggregate",
        "rule": "This type preserves a total printed by the source; a value calculated by Gate 2 is never this type."
      }
    ],
    "optional_roles": [
      {
        "role_id": "as_of_date",
        "value_type": "source_date"
      },
      {
        "role_id": "currency",
        "value_type": "source_currency"
      },
      {
        "role_id": "period",
        "value_type": "source_period"
      },
      {
        "role_id": "source_label",
        "value_type": "source_text"
      },
      {
        "role_id": "unit",
        "value_type": "source_unit"
      }
    ],
    "required_roles": [
      {
        "role_id": "amount",
        "value_type": "source_decimal"
      },
      {
        "role_id": "printed_label_evidence_ref",
        "value_type": "source_reference"
      },
      {
        "role_id": "statement_scope",
        "value_type": "source_reference"
      }
    ],
    "short_meaning": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2."
  }
]
```

#### All typed options

```json
[
  {
    "input_type_id": "printed_financial_metric_v1",
    "option_id": "financial-typed-option:5dc5d8caadb90fa381f3e2b7cd42d52a",
    "prebound_role_values": [
      {
        "human_summary": "amount is prebound to 42.25",
        "role_id": "amount",
        "source_value": "42.25",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:amount",
        "value_type": "source_decimal",
        "visible_context": {
          "column_meaning": "amount",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "as_of_date is prebound to 2026-03-04",
        "role_id": "as_of_date",
        "source_value": "2026-03-04",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:date",
        "value_type": "source_date",
        "visible_context": {
          "column_meaning": "date",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "currency is prebound to CHF",
        "role_id": "currency",
        "source_value": "CHF",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:currency",
        "value_type": "source_currency",
        "visible_context": {
          "column_meaning": "currency",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "printed_label_evidence_ref is prebound to row:syn_successor_v2_no_registry_type:primary",
        "role_id": "printed_label_evidence_ref",
        "source_value": "row:syn_successor_v2_no_registry_type:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "source_label is prebound to Broker fee detail",
        "role_id": "source_label",
        "source_value": "Broker fee detail",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:label",
        "value_type": "source_text",
        "visible_context": {
          "column_meaning": "description",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "statement_scope is prebound to row:syn_successor_v2_no_registry_type:primary",
        "role_id": "statement_scope",
        "source_value": "row:syn_successor_v2_no_registry_type:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      }
    ]
  },
  {
    "input_type_id": "cash_balance_snapshot_v1",
    "option_id": "financial-typed-option:c123e84fef9c627b68c06341410c35a7",
    "prebound_role_values": [
      {
        "human_summary": "amount is prebound to 42.25",
        "role_id": "amount",
        "source_value": "42.25",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:amount",
        "value_type": "source_decimal",
        "visible_context": {
          "column_meaning": "amount",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "as_of_date is prebound to 2026-03-04",
        "role_id": "as_of_date",
        "source_value": "2026-03-04",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:date",
        "value_type": "source_date",
        "visible_context": {
          "column_meaning": "date",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "currency is prebound to CHF",
        "role_id": "currency",
        "source_value": "CHF",
        "source_value_ref": "syn_successor_v2_no_registry_type:primary:value:currency",
        "value_type": "source_currency",
        "visible_context": {
          "column_meaning": "currency",
          "row_role": "fact_candidate",
          "section_role": null,
          "visible_label": null
        }
      },
      {
        "human_summary": "statement_scope is prebound to row:syn_successor_v2_no_registry_type:primary",
        "role_id": "statement_scope",
        "source_value": "row:syn_successor_v2_no_registry_type:primary",
        "source_value_ref": "value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope",
        "value_type": "source_reference",
        "visible_context": {
          "column_meaning": null,
          "row_role": null,
          "section_role": null,
          "visible_label": null
        }
      }
    ]
  }
]
```

#### Unclassified selection

```json
{
  "disposition": "unclassified_financial_input",
  "reason_codes": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

### 3. EXPECTED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

### 4. EXACT MODEL ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

### 5. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

### 6. MECHANICAL COMPARISON

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"unclassified_financial_input"` | `"unclassified_financial_input"` | `YES` |
| `reason_code` | `"no_registry_type"` | `"no_registry_type"` | `YES` |

Overall exact match: `YES`.

### 7. DIAGNOSIS

`NONE` — The normalized semantic answer exactly matches the frozen expected answer.

Technical pipeline: `PASSED`.

## Continuation

Both semantic smoke cases passed. The exact model is eligible for a separately authorized full V6 qualification benchmark; that benchmark was not run here.

## Evidence boundary

The full context below is repository-safe because both cases are synthetic. No credentials, provider response identifiers, raw provider envelope, filesystem path or hidden reasoning trace is included. Future actual-corpus exact context and raw values remain outside Git and are linked only by safe hashes.

Report schema: `broker_reports_gate2_financial_semantic_v6_transparent_smoke_report_v1`.

## Implementation and audit summary

The semantic execution authority remained
`smoke_financial_semantic_v6`; provider transport remained behind the
configured model-client and provider-adapter factories. The implementation
added only:

- a fixed exact-candidate selector and zero-call preflight mode to the
  existing two-case CLI;
- an allowlisted synthetic report projector;
- a fail-closed one-case continuation for the local report-projector stop;
- exact restoration of persisted private JSON before the existing replay
  validator.

No Financial Semantic Pack, Prompt, Packet, Candidate Compiler, Typed Option,
Choice schema, expected answer, validator, materializer, or smoke fixture file
was changed. The continuation compared the current exact identity with the
started identity after excluding only repository revision and its derived
identity hash; every frozen authority field remained equal.

The first live process made one provider submission. A later zero-call
preflight start failed at CLI import, and one continuation start failed while
restoring persisted evidence; both stopped locally before provider transport
while the continuation contract was being hardened. The final continuation
replayed the typed checkpoint with zero provider calls and made exactly the
one missing unclassified submission. Therefore total provider submissions
and responses remain exactly two; neither case was retried.

Verification performed after the continuation implementation:

- full service suite: `1846 passed, 20 skipped, 5 warnings`;
- focused evidence/qualification/architecture regression: `57 passed`;
- terminal receipt integrity hash: verified;
- both persisted private evidence objects: restored, hash-linked, and replayed
  as `EXACT` with zero provider calls;
- exact normalized answer versus frozen expected answer: match for both
  cases;
- repository-safe receipt/report privacy scan: no provider response ID,
  credential, raw envelope, hidden reasoning trace, private evidence path, or
  internal absolute path found.
