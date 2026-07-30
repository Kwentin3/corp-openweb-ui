# Broker Reports Gate 2 GOAL 16 Contract Report

Status: `COMPLETED_OFFLINE_INACTIVE_CONTRACT_EVIDENCE`.

## Outcome

Program decision `SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C` is now expressed as one normative versioned inactive contract: `broker_reports_gate2_type_first_fail_closed_v1`.

Canonical contract: [BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md](../../stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md).

Machine artifact: [BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json](../../stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json).

## Contract surface

```json
{
  "contract_identities": {
    "contract_identity": "broker_reports_gate2_type_first_fail_closed_v1",
    "context_profile": "broker_reports_gate2_type_first_context_v1_candidate",
    "response_profile": "broker_reports_gate2_type_first_plausible_types_response_v1",
    "decision_policy": "broker_reports_gate2_type_first_fail_closed_policy_v1"
  },
  "field_order": [
    "task",
    "source",
    "type_cards"
  ],
  "status": {
    "active": false,
    "transport_eligible": false,
    "runtime_activation": false,
    "provider_calls_total": 0,
    "fallback_allowed": false,
    "repair_allowed": false,
    "retry_allowed": false
  }
}
```

The model sees only `task`, `source`, and `type_cards`, in that order, and returns only `plausible_types`. Code owns mapping, reason derivation, exact option restoration, validation and materialization.

## Safety result

The nine-cell decision policy is total. Zero plausible types always gives `no_registry_type`; two or more always gives `ambiguous_registry_type`; a singleton types only when exactly one complete validly prebound option exists. Zero or multiple matching options fail closed.

The principal unresolved safety risk is `FALSE_SINGLETON_TYPED_RISK`. Model quality has not been qualified; all four future hard gates therefore remain requirements, not results.

## Evidence and verification

```json
{
  "governed_cases": 10,
  "response_negative_fixtures": 9,
  "contract_integrity_negative_fixtures": 5,
  "backend_restoration_negative_fixtures": 2,
  "historical_pins": 13,
  "active_pins": 23,
  "new_owners": 0
}
```

All ten governed cases reproduce the GOAL 15 Variant B matrix. Historical GOAL 12–15 outputs and active Context/Choice/Pack/projection/Prompt/adapter authorities are hash-pinned. The offline validator is standard-library-only and is not imported by runtime. A separate repository test rebuilds current local factory outputs to cross-check source/type-card parity and the four typed-option identities without provider calls.

## Byte and call boundary

```json
{
  "goal15_baseline_bytes": {
    "minimum": 2050,
    "maximum": 2208
  },
  "goal16_logical_bytes": {
    "minimum": 2052,
    "maximum": 2210
  },
  "future_max_bytes": 2500,
  "future_worst_case_calls_per_operation": 1,
  "provider_calls_executed": 0
}
```

GOAL 16 request hashes are newly derived because its exact task, root field names and schema differ from GOAL 15. The planning serializer preserves the normative `task`, `source`, `type_cards` order. The estimator is not a provider tokenizer. Full sealed-request proof is deferred.

## Remaining work and STOP

Variant C remains reserved and unimplemented. The type-first model has not been qualified. The future private mapping receipt does not yet exist.

Next: a separate non-active implementation GOAL, then sealed request/linter proof, then three-provider local end-to-end proof. No runtime implementation or provider smoke is authorized here.

**STOP AFTER GOAL 16.**
