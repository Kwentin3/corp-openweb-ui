# Broker Reports Gate 2 — GOAL 4 Slim View Model Diagnostic

This report records the bounded six-submission diagnostic over the two frozen synthetic smoke cases. Exact semantic input and output facts appear before interpretation.

- Safe receipt: [BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.receipt.safe.json](./BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.receipt.safe.json)
- Exact repository revision: `3f8ac7f6b4243bd85a1a0abd4e780c8fd80d473e`
- Request profile: `financial_semantic_v6_slim_linted_v1`
- Prompt, financial type meanings, frozen cases and expected answers: unchanged.
- Candidate Compiler, canonical expansion and materialization: existing authorities reused.
- Product runtime route: unchanged.
- Full V6 benchmark: not run.

## Acceptance

- `PROVIDER_SUBMISSIONS`: `SIX`
- `TECHNICAL_PIPELINE`: `PASSED`
- `HAIKU_TYPED`: `PASSED`
- `HAIKU_UNCLASSIFIED`: `FAILED_WITH_EXACT_EVIDENCE`
- `NANO_SLIM_TYPED`: `FAILED_WITH_EXACT_EVIDENCE`
- `NANO_SLIM_UNCLASSIFIED`: `FAILED_WITH_EXACT_EVIDENCE`
- `NANO_REVERSED_TYPED`: `FAILED_WITH_EXACT_EVIDENCE`
- `NANO_REVERSED_UNCLASSIFIED`: `PASSED`
- `NANO_DIAGNOSTIC_STATUS`: `NANO_MIXED_OR_ORDER_SENSITIVE`
- `MODEL_INPUT_VISIBLE`: `YES`
- `EXACT_MODEL_OUTPUT_VISIBLE`: `YES`
- `EXPECTED_VS_ACTUAL_DIFF`: `EXPLICIT`
- `FALLBACK_REPAIR_HIDDEN_RETRY`: `ZERO`
- `FULL_BENCHMARK`: `NOT_RUN`
- `DOCUMENTATION`: `UPDATED_IN_SAME_PR`

## Execution accounting

- Planned provider submissions: `6`
- Local invocations: `6`
- Provider submissions: `6`
- Provider responses: `6`
- Actual input tokens: `4753`
- Actual output tokens: `130`
- Actual cost: `$0.002818900`
- Total latency: `28095 ms`
- Average latency: `4682 ms`
- Maximum latency: `16281 ms`

## Primary evidence

### Call 1: `nano_slim` / `syn_successor_v2_unique_cash`

- Case purpose: Verify that the unambiguous synthetic cash-balance context selects the prebound cash_balance_snapshot_v1 typed option.
- Exact model: `gpt-5.4-nano-2026-03-17`
- Provider profile: `openai_gpt`
- Typed-option order: `canonical`
- Model-visible request hash: `02f69b3767139407a8ae0b7d45af24ebeec903e467f08ea838c21d69ded284d8`
- Model-visible UTF-8 bytes: `3427`
- Repository estimated input tokens: `921`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"-120.5000\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"RUB\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"as_of_date\",\"value\":\"2026-03-01\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Cash balance\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": null,
  "selected_local_alias": null
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "B"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"typed_input"` | `"unclassified_financial_input"` | `NO` |
| `typed_option_id` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | _absent_ | `NO` |
| `reason_code` | _absent_ | `"no_registry_type"` | `NO` |

Overall exact match: `NO`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `690`
- Output tokens: `25`
- Total tokens: `715`
- Actual cost: `$0.000169250`
- Latency: `16281 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`MODEL_SEMANTIC_ERROR` — The sealed Slim input parsed and materialized exactly, but the normalized semantic choice differs from the frozen expected answer.

### Call 2: `nano_slim` / `syn_successor_v2_no_registry_type`

- Case purpose: Verify that the synthetic broker-fee context, unsupported by every available registry type card, selects unclassified with no_registry_type.
- Exact model: `gpt-5.4-nano-2026-03-17`
- Provider profile: `openai_gpt`
- Typed-option order: `canonical`
- Model-visible request hash: `89fbaa2f2291e1d6487d9f5f36a615fb985879df2bc8e1776caf9aa99b4d0c54`
- Model-visible UTF-8 bytes: `3422`
- Repository estimated input tokens: `920`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"42.25\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"CHF\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"date\",\"value\":\"2026-03-04\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Broker fee detail\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{
  "choice": "unclassified",
  "reason": "ambiguous_registry_type"
}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "ambiguous_registry_type"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": null,
  "selected_local_alias": null
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"unclassified_financial_input"` | `"unclassified_financial_input"` | `YES` |
| `reason_code` | `"no_registry_type"` | `"ambiguous_registry_type"` | `NO` |

Overall exact match: `NO`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `686`
- Output tokens: `26`
- Total tokens: `712`
- Actual cost: `$0.000169700`
- Latency: `1953 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`UNCLASSIFIED_RULE_UNCLEAR` — The model selected the correct unclassified disposition but the wrong reason. The exact input exposes both reason-code labels without a readable rule that distinguishes no applicable registry type from multiple plausible types.

### Call 3: `haiku_slim` / `syn_successor_v2_unique_cash`

- Case purpose: Verify that the unambiguous synthetic cash-balance context selects the prebound cash_balance_snapshot_v1 typed option.
- Exact model: `claude-haiku-4-5-20251001`
- Provider profile: `anthropic_claude`
- Typed-option order: `canonical`
- Model-visible request hash: `02f69b3767139407a8ae0b7d45af24ebeec903e467f08ea838c21d69ded284d8`
- Model-visible UTF-8 bytes: `3427`
- Repository estimated input tokens: `921`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"-120.5000\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"RUB\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"as_of_date\",\"value\":\"2026-03-01\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Cash balance\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{"choice":"B"}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f",
  "selected_local_alias": "B"
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "B"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"typed_input"` | `"typed_input"` | `YES` |
| `typed_option_id` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | `YES` |

Overall exact match: `YES`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `1003`
- Output tokens: `8`
- Total tokens: `1011`
- Actual cost: `$0.001043000`
- Latency: `3563 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`NONE` — The normalized semantic answer exactly matches the frozen expected answer.

### Call 4: `haiku_slim` / `syn_successor_v2_no_registry_type`

- Case purpose: Verify that the synthetic broker-fee context, unsupported by every available registry type card, selects unclassified with no_registry_type.
- Exact model: `claude-haiku-4-5-20251001`
- Provider profile: `anthropic_claude`
- Typed-option order: `canonical`
- Model-visible request hash: `89fbaa2f2291e1d6487d9f5f36a615fb985879df2bc8e1776caf9aa99b4d0c54`
- Model-visible UTF-8 bytes: `3422`
- Repository estimated input tokens: `920`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"42.25\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"CHF\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"date\",\"value\":\"2026-03-04\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Broker fee detail\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{"choice":"unclassified","reason":"ambiguous_registry_type"}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "ambiguous_registry_type"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": null,
  "selected_local_alias": null
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"unclassified_financial_input"` | `"unclassified_financial_input"` | `YES` |
| `reason_code` | `"no_registry_type"` | `"ambiguous_registry_type"` | `NO` |

Overall exact match: `NO`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `998`
- Output tokens: `20`
- Total tokens: `1018`
- Actual cost: `$0.001098000`
- Latency: `2266 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`UNCLASSIFIED_RULE_UNCLEAR` — The model selected the correct unclassified disposition but the wrong reason. The exact input exposes both reason-code labels without a readable rule that distinguishes no applicable registry type from multiple plausible types.

### Call 5: `nano_slim_reversed` / `syn_successor_v2_unique_cash`

- Case purpose: Verify that the unambiguous synthetic cash-balance context selects the prebound cash_balance_snapshot_v1 typed option.
- Exact model: `gpt-5.4-nano-2026-03-17`
- Provider profile: `openai_gpt`
- Typed-option order: `reversed`
- Model-visible request hash: `5a04beb3a7256c9e5102db0979f49c56c2b6442fce6a3ac681d5e4f7e76a3244`
- Model-visible UTF-8 bytes: `3427`
- Repository estimated input tokens: `921`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"-120.5000\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"RUB\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"as_of_date\",\"value\":\"2026-03-01\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Cash balance\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{
  "choice": "unclassified",
  "reason": "ambiguous_registry_type"
}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "ambiguous_registry_type"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": null,
  "selected_local_alias": null
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "A"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"typed_input"` | `"unclassified_financial_input"` | `NO` |
| `typed_option_id` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | _absent_ | `NO` |
| `reason_code` | _absent_ | `"ambiguous_registry_type"` | `NO` |

Overall exact match: `NO`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `690`
- Output tokens: `26`
- Total tokens: `716`
- Actual cost: `$0.000170500`
- Latency: `2172 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`MODEL_SEMANTIC_ERROR` — The sealed Slim input parsed and materialized exactly, but the normalized semantic choice differs from the frozen expected answer.

### Call 6: `nano_slim_reversed` / `syn_successor_v2_no_registry_type`

- Case purpose: Verify that the synthetic broker-fee context, unsupported by every available registry type card, selects unclassified with no_registry_type.
- Exact model: `gpt-5.4-nano-2026-03-17`
- Provider profile: `openai_gpt`
- Typed-option order: `reversed`
- Model-visible request hash: `1a856ab09a31ac2b1e8097124f6b2bc24a369da83deb9c921a628d561cde546e`
- Model-visible UTF-8 bytes: `3422`
- Repository estimated input tokens: `920`

#### 1. EXACT MODEL-VISIBLE INPUT

```json
{
  "messages": [
    {
      "content": "Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.",
      "role": "system"
    },
    {
      "content": "{\"task\":\"Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.\",\"source\":{\"document\":{\"children\":[{\"alias\":\"t1\",\"kind\":\"table\",\"children\":[{\"alias\":\"r1\",\"kind\":\"row\",\"values\":[{\"alias\":\"v1\",\"meaning\":\"amount\",\"value\":\"42.25\",\"type\":\"decimal\"},{\"alias\":\"v2\",\"meaning\":\"currency\",\"value\":\"CHF\",\"type\":\"currency\"},{\"alias\":\"v3\",\"meaning\":\"date\",\"value\":\"2026-03-04\",\"type\":\"date\"},{\"alias\":\"v4\",\"meaning\":\"description\",\"value\":\"Broker fee detail\",\"type\":\"text\"}],\"row_role\":\"fact_candidate\"}]}]}},\"type_cards\":[{\"alias\":\"T1\",\"meaning\":\"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.\",\"distinctions\":[{\"against\":\"T2\",\"rule\":\"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.\"},{\"against\":\"cash movement\",\"rule\":\"A movement is an event over time; this type is a state at one reporting date.\"}],\"unclassified_when\":\"Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.\"},{\"alias\":\"T2\",\"meaning\":\"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.\",\"distinctions\":[{\"against\":\"T1\",\"rule\":\"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.\"},{\"against\":\"gate2 calculated aggregate\",\"rule\":\"This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.\"}],\"unclassified_when\":\"Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.\"}],\"choices\":[{\"alias\":\"A\",\"type\":\"T1\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"statement_scope=r1\"]},{\"alias\":\"B\",\"type\":\"T2\",\"bindings\":[\"amount=v1\",\"as_of_date=v3\",\"currency=v2\",\"printed_label_evidence_ref=r1\",\"source_label=v4\",\"statement_scope=r1\"]}],\"unclassified\":[\"ambiguous_registry_type\",\"no_registry_type\"]}",
      "role": "user"
    }
  ],
  "response_format": {
    "json_schema": {
      "name": "semantic_choice",
      "schema": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "A",
                  "B"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice"
            ],
            "type": "object"
          },
          {
            "additionalProperties": false,
            "properties": {
              "choice": {
                "enum": [
                  "unclassified"
                ],
                "type": "string"
              },
              "reason": {
                "enum": [
                  "ambiguous_registry_type",
                  "no_registry_type"
                ],
                "type": "string"
              }
            },
            "required": [
              "choice",
              "reason"
            ],
            "type": "object"
          }
        ],
        "title": "Semantic choice"
      },
      "strict": true
    },
    "type": "json_schema"
  }
}
```

#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

#### 3. NORMALIZED ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

Normalization facts:

```json
{
  "first_visible_choice_alias": "A",
  "first_visible_choice_selected": false,
  "post_response_repair_total": 0,
  "selected_exact_typed_option_id": null,
  "selected_local_alias": null
}
```

#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF

Expected model-facing Local Choice JSON:

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

Expected canonical semantic answer:

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

| Field | Expected | Normalized actual | Match |
|---|---|---|---|
| `disposition` | `"unclassified_financial_input"` | `"unclassified_financial_input"` | `YES` |
| `reason_code` | `"no_registry_type"` | `"no_registry_type"` | `YES` |

Overall exact match: `YES`.

#### 5. ACTUAL PROVIDER METRICS

- Input tokens: `686`
- Output tokens: `25`
- Total tokens: `711`
- Actual cost: `$0.000168450`
- Latency: `1860 ms`

#### 6. TECHNICAL PIPELINE

- Context lint: `PASSED`
- Local Choice parser: `PASSED`
- Canonical expansion/materialization: `PASSED`
- Overall: `PASSED`
- Failure code: `NONE`

#### 7. DIAGNOSIS

`NONE` — The normalized semantic answer exactly matches the frozen expected answer.

## Interpretation

Haiku did not preserve both frozen semantic decisions under the Slim View. The full benchmark remains blocked.
Nano produced a mixed/order-sensitive result. The exact calls above must be audited before selecting a corrective slice.
GOAL 7 is not authorized. First audit the Slim source hierarchy, type cards, local choices and exact Haiku answers.

### Joint layer audit

The immutable execution receipt retains the runner's first-pass mechanical
classification. The repository-safe report projector refines only the two
reason-only mismatches to `UNCLASSIFIED_RULE_UNCLEAR` after comparing the
exact input, expected disposition and normalized answer; no input, output,
metric or receipt byte was rewritten.

The six exact calls separate the observed failures as follows:

| Evidence | Observation | Most likely layer |
|---|---|---|
| Haiku typed, canonical order | Exact `{"choice":"B"}`; canonical cash option selected and fully materialized | Slim source, cash type card, typed choices and alias restoration are sufficient for this case |
| Haiku unclassified | Correct `unclassified` disposition, wrong `ambiguous_registry_type` reason | `UNCLASSIFIED_RULE_UNCLEAR` |
| Nano typed, both orders | Returned unclassified in both permutations and never selected the first typed option | Nano semantic capability/type interpretation; first-option bias is not supported |
| Nano unclassified | Wrong reason in canonical order, correct reason in reversed order | Mixed/order-sensitive reason selection; not an order-independent type-card failure |
| All six calls | Strict schema, Local Choice parsing, canonical expansion/materialization, usage and lifecycle accounting passed | Technical pipeline is not the failure source |

The unclassified source context is adequate to establish the frozen expected
answer: `Broker fee detail` is neither an ordinary cash-class balance nor a
source-printed total/metric under the two visible cards. Therefore
`no_registry_type` remains the defensible expected reason. The exact model
input, however, exposes only the bare reason labels
`ambiguous_registry_type` and `no_registry_type`; it does not state the
decision boundary between “more than one visible registry type is plausible”
and “none of the visible registry types applies.” Both Nano canonical and
Haiku chose the former while preserving the correct unclassified disposition.

The typed cash evidence does not support a first-choice-bias diagnosis. Nano
returned unclassified when the expected cash option was second and again when
the same exact option was first. Haiku selected the cash option correctly from
the same canonical Slim input, so a general source-context insufficiency is
also not supported.

### Narrow continuation

The published GOAL 5 prerequisite is not met: Nano did not fail the
unclassified case independently of option order, and the strongest shared
failure is the unclassified reason boundary rather than type-card wording
alone. Do not start GOAL 5, GOAL 6 or the full benchmark from this receipt.

The narrow evidence-backed corrective candidate is a separate zero-provider
research slice for human-readable, non-active unclassified reason semantics
while keeping Prompt, Semantic Pack, type meanings, source context, typed
choices, cases and expected answers frozen. Because this would change the
model-facing Local Choice/context contract, it requires an explicit new GOAL
and its own versioned candidate; it must not be smuggled into this failed
diagnostic or implemented in the provider adapter.

## Evidence and privacy boundary

Both cases are frozen synthetic fixtures, so their complete semantic context, local options and exact semantic JSON answers are repository-safe. The receipt and this report exclude credentials, provider response IDs, raw provider envelopes, internal filesystem paths and hidden reasoning.

Future actual-corpus customer context and raw values remain outside Git; repository-safe projections are linked to private evidence by hashes only.

Report schema: `broker_reports_gate2_financial_semantic_v6_slim_diagnostic_report_v1`.
