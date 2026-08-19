# Broker Reports Gate 5 Runtime Capability Contract v2

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.23_CLOSED`

Proof outcome: `CARDINALITY_CORRECTED_WITHOUT_NEW_CAPABILITY`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

v2 publishes the current semantics of the same five Gate 5 case-time action
families. It changes only the precondition of:

```text
aggregate_complete_category_scope_v0
```

from:

```text
at_least_two_complete_operation_models
```

to:

```text
at_least_one_complete_operation_model
```

It also names `empty_operation_member_set` as a failure condition and clarifies
that the compatible set is non-empty. No capability ID or runtime owner is
added or replaced.

## Immutable machine authority

Resource:

```text
gate5_runtime_capability_contract.v2.json
```

Raw SHA-256:

```text
f35ca4cb5ef8a218b3eab0e287c76b69aeb687ad1741d6196ff6889d547209cc
```

Exact factories:

```python
Gate5RuntimeCapabilityContractV2Factory.create()
Gate5RuntimeCapabilityResolverV2Factory.create()
```

The resolver accepts only reference schema:

```text
broker_reports_gate5_runtime_capability_ref_v2
```

The model projection schema is:

```text
broker_reports_gate5_runtime_capability_model_projection_v2
```

## Closed capability basis

v2 contains exactly the same IDs as v1:

```text
resolve_required_values_v0
obtain_one_missing_money_input_v0
execute_published_typed_behavior_v1
project_validated_declaration_fragment_v0
aggregate_complete_category_scope_v0
```

The other four capability objects are byte-for-byte structurally equal after
removing the versioned contract envelope. The aggregation capability retains
the same inputs, output contract, provenance classes, supported value kinds,
conformance binding and implementation owner.

## Versioning decision

Accepting one member is a backward-compatible runtime bug fix: all valid v1
requests still behave the same. The published model contract nevertheless
cannot be silently edited because v1 bytes and hash already bind G5.18-G5.22
evidence. An additive v2 therefore exposes current truth while v0/v1 remain
exactly replayable.

No v1 compatibility wrapper rejects singleton input. A caller conforming to
the stricter v1 precondition remains valid; v2 is the current contract for
discovering the broadened accepted domain.

## Factory and closed-world boundary

Every v2 resolver binding delegates to the same reviewed runtime factory as
v1. There is no dynamic import, callable loading, caller-supplied schema/code,
filesystem lookup, fallback, alias or unknown-ID guessing. The package resource
is read through `importlib.resources` and hash-checked.

## Scope stop

v2 does not publish Section 2 projection, XML generation, rate/tax calculation,
case orchestration, a singleton primitive or a sixth capability family.
