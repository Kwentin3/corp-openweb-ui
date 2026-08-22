# Broker Reports Gate 5 Tax-Period Category Aggregation v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.23_CLOSED`

Proof outcome: `PROVEN_FOR_NON_EMPTY_EXACT_SCOPE`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

Updated: 2026-08-22 (Issue #293 Tax-Model-only composition seam)

## Purpose

This contract corrects one cardinality error in the existing G5.14 boundary:

```text
explicit taxpayer/category/tax-period scope
+ one or more complete compatible operation models
+ optional completeness evidence bound to the exact member set
        -> known values for the non-empty set
        -> complete category result only with exact completeness evidence
```

The sole owner remains:

```python
Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
```

No singleton-specific capability, behavior, branch, Tax Model, service or DSL
exists.

Issue #293 adds `runtime.run_tax_model(...)` on that same owner. It validates
and aggregates through the unchanged scope/member/completeness core but stops
at the Category Tax Model. The existing `run(...)` delegates to this core and
retains its prior declaration-projection behavior. The new inactive bridge
uses only `run_tax_model`; no declaration semantics or projection is created.

For that bridge composition, `source_scope_ref` is admitted only when it equals
the current consumer result's exact case `scope_id`, and
`taxpayer_scope_ref` must equal the member operation Tax Model
`operation_scope.subject_ref`. The bridge performs these checks before calling
this owner. The generic historical aggregation contract continues to treat its
opaque identities as caller-supplied proof references; Issue #293 does not
silently redefine or migrate its existing callers.

## Cardinality decision

The valid member cardinality is:

```text
1..N
```

Zero members are invalid. One known member is not automatically a complete
category. Complete status still requires the same structured
`user_verified_fact` bound to the canonical scope and exact sorted member
hashes.

For one member, the mechanically aggregated gross income, related expenses and
allowable expenses equal that member's contributions. This is the identity
case of the same sum operation, not separate business logic.

## Origin of the old minimum

The G5.14 commit and report introduced `at least two` together with the
representative A+B proof. A and B were needed to demonstrate addition,
separate expense meanings, deterministic ordering and stale A+B versus A+B+C
binding. No code comment, schema, methodology, completeness rule or official
declaration source supplied a safety reason for rejecting an exact one-member
set.

The old minimum was therefore a research fixture assumption that escaped into
runtime and machine-readable contract semantics.

Official-source cross-check, verified 2026-08-10:

- [FNS order ED-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
  approves the 2025 form, procedure and electronic format;
- its published
  [XSD](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd)
  describes repeatable `ДохОперЦБ` category occurrences and the aggregate
  `ДохСовОпер` value but does not state a minimum of two source operations.

The XSD observation is supporting negative evidence, not a claim that the XSD
owns internal operation-member completeness.

## Unchanged safety boundary

The runtime still validates, before aggregation:

- exact scope schema and taxpayer/category/period identity;
- complete operation model shape;
- published methodology identity, version and hashes;
- period and category agreement with the scope;
- one currency and compatible loss state;
- unique operation references and unique model hashes;
- deterministic member ordering.

Completeness evidence still binds to the canonical SHA-256 of:

```text
scope
+ sorted operation_ref
+ sorted source_scope_ref
+ exact operation_model_sha256
```

Absent evidence returns `incomplete_scope`, known values and no Category Tax
Model or declaration projection. A stale binding is rejected. Changing the
only member's identity, model or scope therefore invalidates old evidence in
exactly the same way as changing a multi-member set.

## Compatibility

The correction is backward compatible for runtime callers:

- every previously valid two-or-more-member request remains valid;
- capability ID, input contracts, output contract and result schemas are
  unchanged;
- only the previously rejected identity case becomes valid.

The already frozen capability-contract v0/v1 resources are not edited. Current
model-visible truth is published additively as [Runtime Capability Contract
v2](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v2.md).

## Scope stop

This contract does not implement Section 2 projection, group classification,
rate, tax, electronic XML, case discovery, new input kinds or a new runtime
capability.

The Issue #293 composition is inactive/shadow. It does not activate the
ordinary product route, promote synthetic completeness evidence, or create a
second aggregation authority.
