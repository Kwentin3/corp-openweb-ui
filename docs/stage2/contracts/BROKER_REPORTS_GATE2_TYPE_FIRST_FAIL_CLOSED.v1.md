# Broker Reports Gate 2 Type-First Fail-Closed Contract v1

Status: normative inactive candidate. Contract identity: `broker_reports_gate2_type_first_fail_closed_v1`.

Context profile: `broker_reports_gate2_type_first_context_v1_candidate`. Response profile: `broker_reports_gate2_type_first_plausible_types_response_v1`. Decision policy: `broker_reports_gate2_type_first_fail_closed_policy_v1`.

For every profile: `active = false`, `transport_eligible = false`, `runtime_activation = false`, `provider_calls_total = 0`, `fallback_allowed = false`, `repair_allowed = false`, and `retry_allowed = false`.

Machine-readable contract: [BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json](BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json).

GOAL 16 evidence: [report](../../reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16.report.md) and [safe receipt](../../reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16.receipt.safe.json).

## 1. Purpose

This contract normatively fixes Variant B, `ONE_CALL_TYPE_FIRST_FAIL_CLOSED`, as the MVP contract. It defines one model decision and a closed backend policy. It does not implement or activate runtime behavior and does not qualify a model.

## 2. Semantic responsibility boundary

The model returns only the ordered set of plausible local financial type keys. It never sees constructible choices and never chooses a reason, record, value, ref or binding.

Code validates the response without repair, restores the private local-to-canonical mapping, derives the reason from cardinality, filters complete validly prebound options for a singleton type, and permits typed materialization only for exactly one matching code-owned option. Constructibility is not semantic evidence.

## 3. Exact model-visible context

The system message remains exactly:

> Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.

The user message has exactly three ordered root fields:

1. `task`
2. `source`
3. `type_cards`

The semantic task is exactly:

> Return every type_key from type_cards whose financial meaning remains plausible for the visible source. Return all plausible types, not only the best one. Judge type plausibility independently of whether code can construct a complete record. Preserve type_cards order.

Representative governed logical context:

```json
{
  "task": "Return every type_key from type_cards whose financial meaning remains plausible for the visible source. Return all plausible types, not only the best one. Judge type plausibility independently of whether code can construct a complete record. Preserve type_cards order.",
  "source": {
    "children": [
      {
        "children": [
          {
            "kind": "row",
            "values": [
              {
                "literal": "-120.5000",
                "meaning": "amount"
              },
              {
                "literal": "RUB",
                "meaning": "currency"
              },
              {
                "literal": "2026-03-01",
                "meaning": "as of date"
              },
              {
                "literal": "Cash balance",
                "meaning": "description"
              }
            ]
          }
        ],
        "kind": "table"
      }
    ]
  },
  "type_cards": [
    {
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "nearest_competitor": {
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
        "type_key": "type_2"
      },
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "title": "Cash balance snapshot",
      "type_key": "type_1"
    },
    {
      "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "nearest_competitor": {
        "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.",
        "type_key": "type_1"
      },
      "negative_signal": "A total calculated by Gate 2 from child rows.",
      "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
      "title": "Printed financial metric",
      "type_key": "type_2"
    }
  ]
}
```

`source` is the byte-equivalent semantic projection of current Context V2.1: every governed source literal is retained exactly, the real hierarchy is retained, no association is invented, and no backend ref or option-construction signal is visible. `type_cards` are the exact current managed minimal cards in current order, with local keys only and no Python copy of their wording.

The future candidate reuses without semantic change the current Context V2.1 `source` and `type_cards`, managed minimal projection, Semantic Pack, source hierarchy, and exact source literals. Only the semantic task, response schema, and absence of record-construction signals change.

Concurrent changes to type-card wording, source grouping, type boundaries, the Semantic Pack, or expected answers are forbidden. Choices, complete options, differentiators, unclassified reasons, Typed Option IDs, canonical IDs, compiler counts, bindings, refs, hashes, and materialization metadata are absent from the model-visible scope.

## 4. Exact response schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "plausible_types": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "type_1",
          "type_2"
        ]
      },
      "minItems": 0,
      "maxItems": 2,
      "uniqueItems": true
    }
  },
  "required": [
    "plausible_types"
  ]
}
```

A valid singleton response is:

```json
{
  "plausible_types": [
    "type_1"
  ]
}
```

The array is an ordered set and must be an exact subsequence of `type_cards`. Empty is valid. Null, duplicates, unknown keys, extra fields, free text and backend IDs are invalid. Out-of-order keys fail technically; code must not sort, deduplicate or retry.

For every real inactive profile instance, `enum` is derived from the exact visible `type_cards[*].type_key` sequence and `maxItems` equals the number of visible cards. The two-card schema above is the exact governed v1 baseline.

## 5. Private mapping

The backend-only baseline mapping used by the ten-case contract matrix is:

```json
{
  "type_1": "cash_balance_snapshot_v1",
  "type_2": "printed_financial_metric_v1"
}
```

The future profile must create its own sealed private mapping receipt bound to Context profile, visible card order, Semantic Pack, managed projection, Evidence Bundle and Candidate Compilation scopes, plus its `integrity_sha256`. Unknown, removed, reordered, or resealed mappings fail closed as a technical contract failure. GOAL 16 does not create that receipt. The model sees neither the mapping nor canonical IDs.

## 6. Deterministic decision table

Only complete, validly prebound options of the mapped singleton type count. Option counts do not modify the plausible type set.

| Plausible types | Matching complete options | Result | Reason/restoration |
|---|---|---|---|
| `zero` | `zero` | `unclassified_financial_input` | `no_registry_type` |
| `zero` | `one` | `unclassified_financial_input` | `no_registry_type` |
| `zero` | `two_or_more` | `unclassified_financial_input` | `no_registry_type` |
| `one` | `zero` | `unclassified_financial_input` | `single_registry_type_no_safe_record` |
| `one` | `one` | `typed_input` | `exact_code_owned_typed_option` |
| `one` | `two_or_more` | `unclassified_financial_input` | `single_registry_type_no_safe_record` |
| `two_or_more` | `zero` | `unclassified_financial_input` | `ambiguous_registry_type` |
| `two_or_more` | `one` | `unclassified_financial_input` | `ambiguous_registry_type` |
| `two_or_more` | `two_or_more` | `unclassified_financial_input` | `ambiguous_registry_type` |

Zero types always yields `no_registry_type`. Two or more types always yields `ambiguous_registry_type`. A singleton with zero or multiple matching options yields `single_registry_type_no_safe_record`. Only singleton plus one matching option restores the unchanged V6 typed Choice; the typed result contains no reason code.

## 7. Technical failures

Technical failures are not semantic answers. They write no terminal Financial Domain result, materialize no record, retain technical evidence and perform no retry, repair or fallback.

| Failure class | Exact error code |
|---|---|
| `malformed_json` | `malformed_json` |
| `missing_plausible_types` | `missing_plausible_types` |
| `plausible_types_null` | `plausible_types_null` |
| `plausible_types_not_array` | `plausible_types_not_array` |
| `unknown_type_key` | `unknown_type_key` |
| `duplicate_type_key` | `duplicate_type_key` |
| `out_of_order_type_keys` | `out_of_order_type_keys` |
| `extra_response_field` | `extra_response_field` |
| `backend_type_id_forbidden` | `backend_type_id_forbidden` |
| `mapping_receipt_mismatch` | `mapping_receipt_mismatch` |
| `context_profile_schema_hash_mismatch` | `context_profile_schema_hash_mismatch` |
| `pack_projection_drift` | `pack_projection_drift` |
| `evidence_bundle_scope_mismatch` | `evidence_bundle_scope_mismatch` |
| `candidate_compilation_scope_mismatch` | `candidate_compilation_scope_mismatch` |
| `missing_exact_code_owned_typed_option` | `exact_code_owned_typed_option_mismatch` |
| `mismatched_exact_code_owned_typed_option` | `exact_code_owned_typed_option_mismatch` |

## 8. False singleton risk

`FALSE_SINGLETON_TYPED_RISK` is the primary safety risk. If the true set is `["type_1", "type_2"]`, but the model incorrectly returns `["type_1"]`, one complete option for `type_1` can produce a semantically wrong typed record. Backend cardinality checks cannot detect this model error.

```json
{
  "true_plausible_types": [
    "type_1",
    "type_2"
  ],
  "incorrect_model_output": [
    "type_1"
  ],
  "unsafe_path": "one_matching_complete_option_can_materialize_a_wrong_typed_record"
}
```

## 9. Retention and ownership

Every unclassified route retains the full Evidence Bundle, all source literals, provenance and ownership. It performs no cross-scope movement, duplicate binding or source-value loss. The typed route restores only an exact code-owned option; existing validation and materialization remain the authorities. Raw provider payloads never enter product paths.

## 10. Qualification counters and hard gates

Future qualification must count:

- `plausible_type_set_exact_total` — responses whose ordered plausible type set exactly equals the audited ordered set.
- `false_empty_total` — empty model sets when the audited set is non-empty.
- `false_singleton_total` — singleton model sets when the audited set cardinality is not one.
- `false_superset_total` — model sets that are strict supersets of the audited set.
- `wrong_singleton_type_total` — singleton model and audited sets whose sole type keys differ.
- `false_singleton_typed_total` — false singleton responses that reach a typed outcome.
- `unsafe_typed_total` — typed outcomes that do not equal the audited exact safe code-owned option.
- `safe_under_typing_total` — unclassified outcomes where the audited singleton type had exactly one complete validly prebound option.
- `invalid_response_total` — responses rejected as technical contract failures.

Hard gates:

```json
{
  "unsafe_typed_total": 0,
  "false_singleton_typed_total": 0,
  "wrong_singleton_type_total": 0,
  "invalid_response_total": 0
}
```

GOAL 16 defines these counters and gates only. It performs no provider qualification and proves no model quality.

## 11. Ten-case matrix

| Case | Local plausible set | Canonical set | Options type_1/type_2 | Route | Outcome | Retention |
|---|---|---|---:|---|---|---|
| `syn_successor_v2_unique_cash` | `["type_1"]` | `["cash_balance_snapshot_v1"]` | `1/1` | `singleton_type_one_complete_option` | `financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f` | `existing_typed_evidence_path_unchanged` |
| `syn_successor_v2_unique_printed_total` | `["type_2"]` | `["printed_financial_metric_v1"]` | `1/1` | `singleton_type_one_complete_option` | `financial-typed-option:9c6b9a796d36dc2cde5b073c9d397622` | `existing_typed_evidence_path_unchanged` |
| `syn_successor_v2_multiple_compatible` | `["type_1","type_2"]` | `["cash_balance_snapshot_v1","printed_financial_metric_v1"]` | `0/0` | `multiple_plausible_types` | `ambiguous_registry_type` | `full_evidence_bundle_retained` |
| `syn_successor_v2_no_registry_type` | `[]` | `[]` | `1/1` | `zero_plausible_types` | `no_registry_type` | `full_evidence_bundle_retained` |
| `syn_successor_v2_missing_discriminator` | `["type_1","type_2"]` | `["cash_balance_snapshot_v1","printed_financial_metric_v1"]` | `1/1` | `multiple_plausible_types` | `ambiguous_registry_type` | `full_evidence_bundle_retained` |
| `syn_successor_v2_detail_vs_subtotal` | `["type_2"]` | `["printed_financial_metric_v1"]` | `0/0` | `singleton_type_no_safe_record` | `single_registry_type_no_safe_record` | `full_evidence_bundle_retained` |
| `syn_successor_v2_adjacent_equal` | `["type_1"]` | `["cash_balance_snapshot_v1"]` | `0/0` | `singleton_type_no_safe_record` | `single_registry_type_no_safe_record` | `full_evidence_bundle_retained` |
| `syn_successor_v2_adjacent_fx` | `["type_1"]` | `["cash_balance_snapshot_v1"]` | `0/0` | `singleton_type_no_safe_record` | `single_registry_type_no_safe_record` | `full_evidence_bundle_retained` |
| `syn_successor_v2_optional_missing` | `["type_1"]` | `["cash_balance_snapshot_v1"]` | `1/1` | `singleton_type_one_complete_option` | `financial-typed-option:2913ae6d06a3bc248adabfd7ff9ed411` | `existing_typed_evidence_path_unchanged` |
| `syn_successor_v2_forbidden_neighbour` | `["type_1"]` | `["cash_balance_snapshot_v1"]` | `1/1` | `singleton_type_one_complete_option` | `financial-typed-option:73ec7a290138fbd81b6bdc7f61d739ec` | `existing_typed_evidence_path_unchanged` |

This matrix is frozen mechanical contract evidence copied from pinned GOAL 15 inputs. It is not model qualification. One typed-option ID was explicit in historical evidence. Three additional IDs are current-factory observations frozen normatively by GOAL 16 and independently cross-checked by the GOAL 16 repository test. The stdlib-only builder does not import runtime or claim to rederive those three IDs.

## 12. Authority map

| Concern | Existing owner | Future change | New owner |
|---|---|---|---:|
| `packet_context_construction` | `Gate2FinancialSemanticV6PacketFactory.create` | `additive_inactive_profile` | `false` |
| `type_projection` | `Gate2FinancialSemanticV5ProjectionFactory.create_minimal_managed_projection` | `unchanged` | `false` |
| `candidate_compilation` | `Gate2FinancialCandidateCompilerFactory.create` | `unchanged` | `false` |
| `response_contract_parser` | `Gate2FinancialSemanticV6ChoiceContractFactory.create` | `additive_inactive_profile` | `false` |
| `context_validation_sealing` | `Gate2FinancialSemanticV6ContextLinterFactory` | `additive_inactive_profile` | `false` |
| `request_construction` | `Gate2OpenWebUIRequestBuilder` | `additive_inactive_profile` | `false` |
| `provider_adaptation` | `Gate2ProviderAdapterFactory.create` | `unchanged_semantic_behavior` | `false` |
| `decision_expansion` | `Gate2FinancialSemanticV6DecisionExpansionFactory` | `additive_type_first_profile` | `false` |
| `validation` | `Gate2FinancialEvidenceValidatedDecisionFactory.create` | `unchanged` | `false` |
| `materialization` | `Gate2FinancialEvidenceMaterializerFactory.create` | `unchanged` | `false` |
| `decision_evidence_replay` | `Gate2FinancialSemanticV6DecisionEvidenceFactory` | `additive_single_stage_profile` | `false` |
| `economy_accounting` | `Gate2EconomyBudgetSessionFactory` | `existing_one_call_limit_retained` | `false` |

The exact existing Prompt owner remains `V6_SEMANTIC_SYSTEM_PROMPT` / `financial_semantic_v6_prompt` in `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_prompt.py`. It is not a new routing authority. Total new owners required: `0`.

## 13. Byte budget

GOAL 15 Variant B was a design baseline of 2,050–2,208 provider-neutral logical request bytes and 577–616 planning tokens. GOAL 16 changes field names, task text and schema, so its request hashes are newly calculated rather than reused.

```json
{
  "goal16_logical_request_utf8_bytes": {
    "minimum": 2052,
    "maximum": 2210
  },
  "goal16_estimated_planning_tokens": {
    "minimum": 577,
    "maximum": 617
  },
  "target_max_utf8_bytes": 2500,
  "provider_tokenizer_measurement": false
}
```

The estimator is planning-only. Full provider-specific sealed request cost is deferred. Any governed logical request above 2,500 bytes requires STOP and a separate review.

## 14. Variant C reservation

Variant C is not implemented. Variant B has no Stage 2, no second call, no `selected_choice`, no multi-stage replay and no same-type record selection. Multiple complete options of one type fail closed as `single_registry_type_no_safe_record`. Economy Policy stays one-call.

Variant C may be reconsidered only with accepted real same-type/multiple-option evidence, proof that the options are one mutually exclusive record choice, proven frequency, separate Stage 2 safety qualification and measurable net completeness gain.

## 15. Activation boundary

All GOAL 16 profiles remain inactive and transport ineligible. Runtime, active Context V2.1, active Choice, Prompt runtime, Pack, projection, adapters and product logic are unchanged. Provider calls are zero.

The next separate GOAL is `NON-ACTIVE TYPE-FIRST CONTRACT IMPLEMENTATION`. Provider smoke remains forbidden until non-active implementation, sealed request/linter proof and three-provider local end-to-end proof all exist.

**STOP AFTER GOAL 16.**
