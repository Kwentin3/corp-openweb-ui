# Broker Reports — V6 qualification Goal 3 budget contract

Date: 2026-07-27  
Base revision: `ade2875206be2d1b1958a3ef556835e8bf3a62d0`

## Result

| Acceptance item | Result |
| --- | --- |
| `PRECALL_ADMISSION` | `EXPLICIT` |
| `POSTCALL_ACCOUNTING` | `NON_DESTRUCTIVE` |
| `VALID_RESPONSE_DROPPED_BY_ESTIMATE_DRIFT` | `ZERO` |
| `BUDGET_AUTHORITY` | `ONE_EXISTING_POLICY_PATH` |
| `PROVIDER_CALLS` | `ZERO` |
| New policy/schema/factory paths | `ZERO` |
| Stage mutations | `ZERO` |

The existing `Gate2EconomyBudgetSession` remains the only budget authority.
It now names three previously conflated concepts in request metadata and the
safe execution receipt:

| Concept | Existing authority | Enforcement |
| --- | --- | --- |
| `HARD_PROVIDER_LIMIT` | provider transport | provider accepts or rejects the request |
| `QUALIFICATION_TARGET_BUDGET` | workload `maximum_estimated_input_tokens` | pre-call admission |
| `ACTUAL_COST_OBSERVATION` | normalized reported usage | post-response accounting |

## Pre-call admission

Before provider authorization, the existing session records:

- estimated input tokens;
- the existing maximum qualification target;
- the nonnegative safety margin between target and estimate;
- the authorization decision.

An estimated request above the target still fails closed before transport and
does not increment the provider authorization counter. Existing output,
reasoning, paid-tool, per-operation cost, full-run cost, call and fallback
guards are unchanged.

## Post-response accounting

Once the provider has returned a response, reported input above the
qualification estimate target no longer destroys that response. The receipt
records:

- actual normalized usage;
- actual cost;
- `actual_input_above_target` when applicable;
- `accepted_response` for the provider-enforced hard-limit observation.

The hard requested output cap, execution identity, usage completeness,
nonnegative token accounting, cached-token accounting and reasoning policy
continue to fail closed.

The canonical model-client test returns a valid structured decision with
reported input `3200` against target `3072`. The decision content is preserved
and extracted, while the safe receipt records the above-target observation.
No semantic result is converted into a model-safety failure by estimate drift.

## Closed-world parity correction

Regenerating the canonical OpenWebUI bundles exposed a source-only bundle
dependency introduced by the preceding request-builder change: the shared
builder imported a financial materialization module only to compute canonical
JSON SHA-256. The builder now computes that same deterministic hash locally,
without a workspace-only or financial runtime dependency. All three canonical
bundles were regenerated and their closed-world tests pass.

## Verification

```text
Budget focused tests: 17 passed
Budget/client/provider/bundle tests: 55 passed
Full service suite: 1817 passed, 20 skipped
Targeted Ruff: All checks passed
```

No provider transport was invoked. Tokens and cost incurred by this Goal are
zero. Retry, fallback and repair counts are zero. No customer bytes, raw
provider output, provider response identifiers, credentials or private paths
were added to Git.

## Unchanged contracts

Model policy declarations, workload policy schema, provider adapters, V6
Prompt/packet/choice, expansion, validator/materializer, product scorer,
Managed Domain, Domain API and stage Action remain unchanged.

## Next permitted goal

Goal 4 may implement terminal outcome classification and attempt accounting.
Provider calls remain forbidden.
