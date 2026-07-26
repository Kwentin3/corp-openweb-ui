# Broker Reports Gate 2 Managed Financial Domain Shadow Qualification v1

Status: normative qualification contract for GOAL 10.

## 1. Purpose

This contract qualifies one exact economy model for synthetic shadow use of
the managed Financial Domain V4 contour. It is not a production admission,
actual-corpus proof, customer acceptance, or release authorization.

The first and only candidate under this contract identity is:

`gpt-5.4-nano-2026-03-17`.

## 2. Exact authority

Qualification must bind all of the following:

- exact model and provider profile;
- qualification-only economy model and workload policy versions and hashes;
- frozen customer-free successor-v2 fixture identity;
- V4 model-input schema;
- exact Semantic Pack and managed-asset manifest identities;
- managed prompt identity and hash;
- provider response-format projection;
- canonical validator, materializer, context, and product-comparator
  revisions;
- passing GOAL 9 local domain proof identity.

A receipt from an older prompt, model-input, projection, validator, Pack, or
risk policy is not transferable.

## 3. Attempt policy

One live attempt is authorized for one exact contract identity.

Before the attempt, the harness must:

1. verify the qualification-only Action against repository bytes and policy
   hash;
2. verify that the exact model is published;
3. authorize the exact workload/model/provider tuple through
   `Gate2EconomyQualificationPolicyFactory`;
4. rebuild the current local domain proof;
5. dry-build every request under the current input, output, call, tool, and
   cost budgets with zero provider calls.

The live receipt path must be new, use the `.safe.json` suffix, and reside
under the Git-ignored service `local/` directory.

The harness must atomically persist an initial checkpoint, every completed
case, and the terminal result. A terminal receipt, partial receipt with
provider calls, interrupted attempt, or provider rejection consumes the
attempt. Retry, repair, fallback, hidden retry, and candidate search are
forbidden.

## 4. Canonical execution

Each frozen synthetic case is processed exactly once through:

1. current V4 model input;
2. managed prompt;
3. one strict structured provider call;
4. canonical decision validation;
5. deterministic materialization;
6. deterministic financial-context projection;
7. the product-invariant comparator.

Provider output is a proposal. It never becomes canonical authority without
the validator and materializer.

No customer data, production financial route, direct vendor SDK, Knowledge,
RAG, embedding, vectorization, paid tool, source model, domain model,
fallback, or repair is permitted.

## 5. Risk semantics

A typed result is safe only when the frozen reference expects a typed result
and the exact input type is correct.

- wrong typed classification is `unsafe_typed`;
- expected typed becoming unclassified is measured `safe_under_typing`;
- expected financial becoming no-financial or unsupported is `data_loss`;
- a valid conservative non-typed mismatch is a quality mismatch, not an
  automatic safety failure;
- canonical validation or materialization failure is a hard failure.

Safe under-typing must remain visible in the receipt and must reduce measured
typed recall. It must never be rewritten as a typed success.

## 6. Hard gates

`MODEL_SAFE_FOR_SHADOW=YES` requires all of:

- unsafe typed total: 0;
- value or provenance loss total: 0;
- invented values total: 0;
- invalid reference total: 0;
- wrong-role total: 0;
- duplicate and cross-scope binding totals: 0;
- terminal ownership gap total: 0;
- canonical and materialization error total: 0;
- product safety proof: passed.

Any failed hard gate makes the qualification terminally failed and forbids
shadow admission for the exact candidate and contract identity.

## 7. Required measurements

The terminal safe receipt records:

- typed expected, observed, and correct totals;
- typed precision and recall;
- safe under-typing total;
- unclassified total and rate;
- terminal disposition counts;
- exact quality-match rate;
- input and output tokens;
- actual provider cost;
- observed latency attempts, total, average, and maximum latency;
- provider, customer, fallback, repair, paid-tool, and expensive-model call
  accounting.

## 8. Privacy

The repository-safe receipt may contain only model and contract identities,
synthetic case identifiers, counts, rates, booleans, hashes, token/cost
totals, latency aggregates, and typed error categories.

It must not contain fixture literals, source-value references, source-scope
references, source groups, raw provider output, customer data, secrets,
tokens, private filesystem paths, or response payloads.

The full atomic checkpoint remains outside Git.

## 9. Acceptance and non-claims

GOAL 10 is accepted only when:

```text
MODEL_SAFE_FOR_SHADOW YES
UNSAFE_TYPED ZERO
DATA_LOSS ZERO
RECALL MEASURED
```

A terminal failed receipt is evidence, not acceptance. It must be preserved,
must not be retried under the same identity, and blocks dependent GOAL 11 and
production admission until the user authorizes a new candidate or a new
qualification-policy decision in a separate GOAL.
