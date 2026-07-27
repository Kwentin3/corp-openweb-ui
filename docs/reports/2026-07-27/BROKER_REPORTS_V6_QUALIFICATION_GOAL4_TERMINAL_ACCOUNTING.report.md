# Broker Reports — V6 qualification Goal 4 terminal accounting

Date: 2026-07-27  
Base revision: `f18c1bb93bf131b9d989a8b89646295f42530e19`

## Result

| Acceptance item | Result |
| --- | --- |
| `HARNESS_FAILURE_AS_MODEL_FAILURE` | `ZERO` |
| `PRETRANSPORT_ATTEMPT_CONSUMPTION` | `ZERO` |
| `MODEL_METRICS_WITHOUT_DECISIONS` | `NOT_PUBLISHED` |
| `FAILURE_CLASSES` | `EXPLICIT` |
| `PROVIDER_CALLS` | `ZERO` |
| Stage mutations | `ZERO` |

The existing canonical model client and V6 terminal runner now expose one
monotonic lifecycle:

```text
local invocation
  -> provider transport submission
  -> provider response
  -> technically admitted semantic decision
  -> product-admitted decision
```

A model attempt is consumed only when
`provider_submissions_total > 0`. Request building, Prompt/schema checks,
budget admission, provider configuration and local preflight do not consume a
model attempt.

## Terminal taxonomy

The V6 qualification run v2 receipt permits exactly:

1. `LOCAL_PREFLIGHT_FAILED`
2. `REQUEST_BUILD_FAILED`
3. `PROVIDER_TRANSPORT_FAILED`
4. `PROVIDER_RESPONSE_INVALID`
5. `PROVIDER_USAGE_METADATA_INCOMPLETE`
6. `MODEL_OUTPUT_SCHEMA_FAILED`
7. `MODEL_SEMANTIC_GATE_FAILED`
8. `PRODUCT_VALIDATION_FAILED`
9. `PRODUCT_MATERIALIZATION_FAILED`
10. `MODEL_SAFE_FOR_SHADOW`

Request builder, transport, adapter, provider response, usage metadata, budget,
validation and materialization defects leave `product_gate` unset. The
compatibility value `MODEL_NOT_SAFE_FOR_SHADOW` is emitted only when all
semantic decisions and product decisions were technically admitted and the
complete benchmark fails the model semantic gate.

## Attempt accounting

The safe receipt separately records:

- `local_invocations_total`;
- `provider_submissions_total`;
- `provider_responses_total`;
- `semantic_decisions_total`;
- `product_admitted_decisions_total`;
- `model_attempts_consumed_total`.

The model client increments submission immediately before its one canonical
transport invocation and response only after transport returns. Native invalid
JSON and response-budget failures are accounted as received responses, while
configuration and transport failures are not.

Both live V6 CLIs write an initial `pretransport_authorized` receipt with all
attempt counters at zero. The terminal runner replaces it with monotonic safe
checkpoints. There is no initial hard-coded consumed attempt.

## Model metrics

Typed precision, typed recall and unclassified-rate metrics are published only
when all semantic decisions and product decisions cross their technical
admission boundaries. Otherwise:

```text
quality: null
model_metrics_status: NOT_PUBLISHED
```

This prevents request, provider, metadata, schema or product defects from
creating synthetic zero precision/recall or a model-safety verdict.

## Terminal proof

Real deterministic V6 fixture, expansion, validation, materialization and
evidence replay paths prove:

- valid complete execution: `MODEL_SAFE_FOR_SHADOW`;
- valid but wrong typed choice: `MODEL_SEMANTIC_GATE_FAILED`;
- local identity failure: `LOCAL_PREFLIGHT_FAILED`, zero submissions;
- request-build failure: `REQUEST_BUILD_FAILED`;
- provider invocation failure: `PROVIDER_TRANSPORT_FAILED`;
- returned invalid response: `PROVIDER_RESPONSE_INVALID`;
- missing budget/usage metadata: `PROVIDER_USAGE_METADATA_INCOMPLETE`;
- invalid minimal choice: `MODEL_OUTPUT_SCHEMA_FAILED`;
- all-pretransport run: zero submissions and zero consumed model attempts.

External boundaries alone are synthetic. Product stages run through their real
factories and terminal outputs.

## Verification

```text
Model-client lifecycle tests: 23 passed
Terminal/client/provider/bundle tests: 51 passed
All V6 tests: 118 passed
Full service suite: 1823 passed, 20 skipped
Targeted Ruff: All checks passed
Live V6 CLI import/help: passed
```

No provider transport was invoked. Tokens and cost incurred by this Goal are
zero. Retry, fallback and repair counts are zero. No customer bytes, exact
model choices, raw provider payloads, credentials or private paths were added
to Git.

## Unchanged contracts

V6 Prompt, Semantic Pack, four-block packet, minimal choice, deterministic
expansion, generic validator/materializer, product scorer, Managed Domain,
Domain API, provider selection, stage Action and production admissions remain
unchanged.

## Next permitted goal

Goal 5 may run exactly two authorized Nano smoke submissions: one typed case
and one unclassified case. No full benchmark is permitted before that smoke
passes.
