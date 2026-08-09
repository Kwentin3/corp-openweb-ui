# Broker Reports Gate 5 Tax-Period Category Aggregation v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.14_CLOSED`

Proof outcome: `PROVEN_WITH_USER_VERIFIED_COMPLETENESS`

Product status: `INACTIVE PROOF`

Date: 2026-08-09

## Purpose

This contract owns one narrow boundary:

```text
explicit taxpayer/category/tax-period scope
+ at least two complete G5.13 operation models
+ completeness evidence bound to that exact member set
        -> complete or incomplete category result
        -> existing G5.12 projection only when complete
```

It proves aggregation and honest completeness semantics for one securities
category. It does not discover a yearly portfolio, calculate a tax base, rate
or tax, or create a Tax Case.

## Repository-truth scope finding

Gate 4 `CASE_COMPLETE_FOR_CURRENT_INPUT_SET` proves only that every current
readiness-visible document has a current Gate 3 sidecar and the cache matches
that technical set. Gate 4 explicitly does not prove that every required
document was uploaded or that the taxpayer's economic history is complete.

Therefore G5.14 does not promote Gate 4 technical completeness. The minimal
tax completeness representation contains:

- one opaque taxpayer scope reference;
- one explicit tax period;
- one methodology-stable operation category;
- one exact sorted set of operation references, source-scope references and
  complete operation-model hashes;
- one separately source-tagged completeness assertion bound to the SHA-256 of
  that exact scope and member set.

The representative authority is a structured `user_verified_fact`. No current
document-derived or external source in repository truth proves that all of the
taxpayer's relevant operations for 2025 are present. A system-derived statement
could prove only a bounded uploaded-document set and is not accepted by this
proof as taxpayer-period completeness.

## Public boundary and existing owners

The sole aggregation construction entrypoint is:

```python
Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
```

The runtime exposes:

```python
runtime.describe_scope(scope=..., members=...)
runtime.run(
    scope=...,
    members=...,
    completeness_evidence=...,
)
```

`describe_scope` validates and deterministically closes the scope/member set.
It does not assert completeness. `run` computes known totals and admits a
complete category model only when the supplied evidence binds to that exact
closed scope.

The factory composes:

- `Gate5TrustedMethodologyAuthorityFactory.create` to validate every member's
  exact methodology identity, version and package hashes;
- `Gate5DeclarationProjectionRuntimeFactory.create` to project a complete
  category result without copying declaration paths, attributes or codes.

The aggregator imports no Gate 4, Supplemental Fact, ArtifactStore/Resolver,
SQL, source reader, provider or model client.

## Additive G5.13 operation seam

The existing G5.13 factory now exposes `run_operation`. It resolves Financial
Case and Supplemental inputs through the unchanged G5.5 path and applies the
same reviewed category and expense logic, but returns:

```text
broker_reports_gate5_securities_disposal_operation_tax_model_v0
```

The operation model has `aggregation_kind = single_operation_only`. It has no
category completeness and no declaration fragment.

This path uses a new hash-pinned methodology version:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.1-experimental
behavior_id         = securities_disposal_operation_tax_model_v0
```

The new applicability rule omits `scope_completeness`; category completeness
is not an operation-classification prerequisite. The original G5.13
`2026.0-experimental` resource and `run` behavior remain unchanged.

## Closed inputs

### Scope

`broker_reports_gate5_tax_period_category_scope_v0` has exactly:

```text
scope_ref
taxpayer_scope_ref
tax_period
operation_category
```

The references are opaque proof identities. They are not storage authority or
caller-supplied ACL fields.

### Members

Each member has exactly:

```text
operation_ref
source_scope_ref
tax_model
```

`tax_model` must be a complete G5.13 operation model. The runtime validates its
published methodology through G5.8, computes canonical JSON SHA-256, sorts by
stable references and rejects duplicate references or duplicate model hashes.

### Completeness evidence

`broker_reports_gate5_tax_period_completeness_evidence_v0` has:

```text
status = asserted_complete
coverage_kind = all_operations_in_taxpayer_category_period_scope
scope_binding_sha256
provenance.source_kind = user_verified_fact
provenance.source_ref
provenance.input_channel = tax_period_scope_completeness
```

The hash is over the canonical scope plus the sorted triples:

```text
operation_ref
source_scope_ref
operation_model_sha256
```

This is an identity binding, not a signature or generic evidence system.

## Aggregation semantics

Aggregation starts only after every member is a complete, methodology-bound,
classified operation model. It never sums raw Gate 4 facts.

The runtime requires consensus on:

- exact tax period;
- exact stable category;
- currency;
- methodology binding;
- compatible loss-treatment state.

It then independently sums Decimal values for:

```text
gross income
related expenses
allowable expenses
```

The aggregator never re-runs expense allowability. A related but unproven
component remains excluded from the operation's allowable total before
aggregation.

Aggregate derivation contains one contribution per sorted operation, its model
hash, operation value and original Financial Case or Supplemental evidence.
No graph database is introduced.

## Complete and incomplete outcomes

Without completeness evidence the runtime returns:

```text
status = incomplete_scope
known_values = mechanically aggregated values
category_tax_model = null
declaration_semantics = null
declaration_fragment = null
```

The known values are not named complete category totals.

With exact valid evidence it returns:

```text
status = complete
category_tax_model = broker_reports_gate5_tax_period_category_tax_model_v0
declaration_fragment = existing G5.12 result
```

The representative result is:

```text
gross income        150.00 RUB
related expenses    102.00 RUB
allowable expenses  100.00 RUB
loss treatment      none
```

The two expense totals intentionally differ because one operation has a
related but undocumented fee. This proves that aggregation preserves the
G5.13 allowability decision instead of reconstructing it.

G5.12 emits one Appendix 8 occurrence with `150.00`, `102.00` and `100.00` for
the corresponding existing mappings. G5.14 contains no declaration-owned
attributes or codes.

## Fail-closed boundary

The runtime rejects:

- fewer than two members;
- missing, duplicate or ambiguous operation identity;
- duplicate operation-model content;
- incomplete or malformed operation models;
- unknown, stale or mixed methodology bindings;
- period or category mismatch;
- mixed currency;
- incompatible loss treatment;
- invalid completeness provenance;
- a completeness hash made for a different scope or member set.

Input order does not change the output. Adding, removing or changing a member
changes the closed binding and the old assertion fails.

## Completeness Audit

### What is complete?

All operations in category
`organized_market_securities_outside_iis` for tax period `2025` and opaque
taxpayer scope `taxpayer-proof-1`, limited to the exact operation models named
by the binding.

### Who asserts it?

The representative proof uses a user/case assertion tagged
`user_verified_fact`. Gate 4, the aggregator and the LLM do not assert it.

### What supports the assertion?

A closed structured statement references the exact scope/member SHA-256. The
proof does not claim documentary corroboration beyond the operation-level
Financial/Supplemental provenance.

### What if another document or operation appears?

Its operation model changes the member-set hash. The old assertion no longer
matches; the runtime fails closed and cannot reuse the old complete result.

### Is the old aggregate still complete?

No. A new exact completeness assertion is required for the new set.

## Run and lifecycle boundary

The proof builds each operation through G5.13 in its own current trusted source
scope, then aggregates the resulting immutable structured model. G5.14 neither
discovers Supplemental Facts across runs nor rebinds them. The historical
`normalization_run_id` risk does not block this representative post-resolution
aggregation, and cross-run discovery/rebinding remains out of scope.

## KISS and stop condition

G5.14 adds one operation-only compatibility path to the current G5.13 owner,
one hash-pinned methodology version, one scope/aggregation module, one focused
test file, this contract and one report. It adds no DB/table, Tax Case,
TaxPortfolio, TaxLedger, workflow, relation graph, LLM, generic query language
or aggregation engine.

The representative positive, incomplete and fail-closed proofs passed, so
`G5.14_CLOSED`. No later Gate 5 slice is authorized by this contract.
