# Broker Reports Gate 5 Runtime Capability Contract v3

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.24_CLOSED`

Proof outcome: `PROJECT_VERSIONED_WITHOUT_NEW_CAPABILITY_FAMILY`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

v3 publishes current truth for the same five Gate 5 case-time action families.
It preserves the four non-PROJECT members from v2 exactly and version-replaces:

```text
project_validated_declaration_fragment_v0
  -> project_validated_declaration_fragment_v1
```

The action remains PROJECT. v1 can resolve one exact published projection and
accept its registered stable semantic input, so Section 2 does not require a
new base primitive or a sixth capability.

## Immutable machine authority

```text
resource  gate5_runtime_capability_contract.v3.json
sha256    34d3796054fc780b4c4937caf101b87224a64ed58b857ac9404a5c0b3438f438
contract  broker_reports_gate5_runtime_capability_contract_v3
ref       broker_reports_gate5_runtime_capability_ref_v3
model     broker_reports_gate5_runtime_capability_model_projection_v3
```

Exact factories:

```python
Gate5RuntimeCapabilityContractV3Factory.create()
Gate5RuntimeCapabilityResolverV3Factory.create()
```

## Closed capability basis

v3 contains exactly:

```text
resolve_required_values_v0
obtain_one_missing_money_input_v0
execute_published_typed_behavior_v1
project_validated_declaration_fragment_v1
aggregate_complete_category_scope_v0
```

The PROJECT inputs are one
`broker_reports_gate5_declaration_projection_ref_v1` and one
`registered_projection_input`. Its output is
`broker_reports_gate5_declaration_projection_fragment_v1`.

The resolver binds that member only to
`Gate5DeclarationProjectionRuntimeV1Factory.create`. It exposes no Python
implementation name to the model and performs no dynamic lookup, import,
registration, aliasing or fallback.

## Versioning decision

The old v0 member contract accepted only the synthetic Appendix 8 proof input
and returned the v0 flat fragment. Silently broadening those published bytes
would invalidate prior evidence. v3 therefore gives the changed PROJECT member
a v1 identity while keeping the semantic family count at five. Runtime
Capability Contracts v0, v1 and v2 remain exact replayable package resources.

## Scope stop

v3 does not add full declaration assembly, XML/XSD validation, calculation,
rate/tax, authoring execution, arbitrary projection programs, a service
registry, workflow, DB or product route.
