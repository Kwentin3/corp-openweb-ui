# Broker Reports Gate 5 Runtime Capability Contract v1

Status: `SUPERSEDED SUPPORTING CONTRACT`

Goal status: `G5.18_CLOSED`

Proof outcome: `PROVEN_WITH_TWO_REGISTERED_TYPED_OUTPUTS`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

Superseded by [v2](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v2.md)
after G5.23 corrected the aggregation precondition from two members to a
non-empty exact member set. The v1 resource and hash remain immutable replay
evidence.

## Purpose

This contract version-replaces only the public execution member of the five
Gate 5 semantic action families:

```text
execute_published_calculation_behavior_v0
        -> execute_published_typed_behavior_v1
```

The new capability executes one exact statically registered published behavior
and returns its exact registered typed output inside one common envelope. It
does not add a sixth primitive and does not reinterpret the other four G5.15
capabilities.

The immutable v0 resource, reference, factory, resolver, model projection and
calculation-result meaning remain available for exact replay. v1 is additive;
it does not mutate v0 bytes or silently widen the v0 output contract.

## Machine-readable authority

The v1 resource is:

```text
gate5_runtime_capability_contract.v1.json
```

Its raw LF-normalized SHA-256 is:

```text
e5134005e3715e70249f14dd1918ce4d110e70bb6eba1304ccbd9204c1531e8f
```

`Gate5RuntimeCapabilityContractV1Factory.create` loads only this package
resource, checks the raw hash, validates its closed schema and requires exact
parity with the v1 runtime binding map. The v1 resolver accepts only:

```json
{
  "schema_version": "broker_reports_gate5_runtime_capability_ref_v1",
  "capability_id": "execute_published_typed_behavior_v1"
}
```

The legacy `Gate5RuntimeCapabilityContractFactory.create` and
`Gate5RuntimeCapabilityResolverFactory.create` continue to own v0.

## Five-family publication

v1 contains exactly:

```text
resolve_required_values_v0
obtain_one_missing_money_input_v0
execute_published_typed_behavior_v1
project_validated_declaration_fragment_v0
aggregate_complete_category_scope_v0
```

Only the execute member changed. The new model projection is canonical UTF-8,
`7,461` bytes, and still excludes conformance blocks, factory/class/function
names, module/filesystem paths and implementation binding IDs.

## Public typed execution boundary

The v1 resolver returns the existing semantic capability wrapper. Its factory
creates the typed runtime only through:

```python
Gate5PublishedTypedBehaviorRuntimeFactory(...).create()
```

The sole published execution method is:

```python
runtime.execute(
    behavior_ref=...,
    input_contract_id=...,
    output_contract_id=...,
    behavior_input=...,
    context=trusted_artifact_access_context,
)
```

The caller supplies semantic identities and data only. The signature has no
implementation, callable, Python module, function, filesystem path, schema
content, plugin or fallback parameter.

`behavior_ref` is exactly:

```text
schema_version
methodology_id
methodology_version
behavior_id
```

Extra fields or an unknown tuple fail closed.

## Closed static binding

The maintained owner contains three immutable code-reviewed entries. The third
was appended by G5.22 without changing this capability contract resource:

| Methodology/version | Behavior | Input contract | Output contract | Existing execution owner |
| --- | --- | --- | --- | --- |
| `ru-ndfl-securities-proof@2026.0-experimental` | `security_disposal_net_result_v0` | `broker_reports_gate5_no_additional_behavior_input_v1` plus trusted case context | `broker_reports_gate5_trusted_calculation_result_v0` | G5.8 trusted calculation wrapper over G5.7 |
| `ru-ndfl-securities-tax-model-proof@2026.1-experimental` | `securities_disposal_operation_tax_model_v0` | `broker_reports_gate5_securities_disposal_resolved_inputs_v0` plus trusted case context | `broker_reports_gate5_securities_disposal_operation_tax_model_v0` | G5.13 operation-only Tax Model owner |
| `ru-ndfl-securities-tax-model-proof@2026.2-experimental` | `securities_income_group_tax_base_v0` | `broker_reports_gate5_income_group_tax_base_input_v0` plus trusted case context | `broker_reports_gate5_income_group_tax_base_model_v0` | G5.22 stable income-group Tax Base owner |

An entry also binds one code-owned implementation identity and the existing
repository methodology authority. Those details remain internal and are not in
the model projection or result envelope.

The map is not a service, DB, plugin catalog or dynamic registry. There is no
runtime registration API. Python code existing elsewhere in the package does
not make a behavior executable: the existing G5.13 legacy
`securities_disposal_tax_model_v0` implementation is deliberately not a v1
entry and fails as unsupported when requested through typed execution.

## Existing-owner composition

The factory composes existing owners:

- `Gate5TrustedMethodologyCalculationRuntimeFactory.create` owns the G5.7
  behavior and exact G5.8 artifact/hash resolution;
- `Gate5SecuritiesDisposalTaxModelRuntimeFactory.create` owns G5.13
  classification, expense allowability and operation-model construction;
- `Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` owns exact G5.14
  member validation.
- `Gate5IncomeGroupTaxBaseRuntimeFactory.create` owns the G5.22 stable
  income-group calculation and deterministic result validation.

The typed layer performs only:

```text
resolve exact static binding
-> compare exact requested input/output contract IDs
-> call the bound existing owner
-> validate the registered output through its consumer boundary
-> return a common envelope
```

It does not copy or rebuild tax formulas, classification, expense rules,
methodology resources or Operation Tax Model fields.

## Typed result envelope

`broker_reports_gate5_typed_behavior_result_v1` has:

```json
{
  "schema_version": "broker_reports_gate5_typed_behavior_result_v1",
  "status": "executed",
  "behavior_binding": {
    "methodology_id": "<exact>",
    "methodology_version": "<exact>",
    "behavior_id": "<exact>",
    "input_contract_id": "<exact registered ID>",
    "output_contract_id": "<exact registered ID>"
  },
  "artifact_binding": {
    "authority_owner": "<existing owner>",
    "methodology_id": "<exact>",
    "methodology_version": "<exact>",
    "resource_sha256": "<exact>",
    "projection_sha256": "<exact>"
  },
  "provenance": {
    "retention": "exact_in_result_payload",
    "source_kinds": ["<observed exact kinds>"],
    "includes_methodology_derived_result": true
  },
  "result_payload": "<registered typed object>"
}
```

The common envelope does not define `proceeds`, expense fields, operation
category or any other Tax Model property. Those remain inside the registered
output contract. Complete source structures remain in `result_payload`; the
small `source_kinds` list is an inventory, not flattened replacement
provenance.

## Conformance case A — G5.7 parity

For `security_disposal_net_result_v0`, v1 delegates to the unchanged G5.8/G5.7
route. The registered payload is the exact existing
`broker_reports_gate5_trusted_calculation_result_v0` object.

The proof preserves:

```text
proceeds                100.00 RUB
recognized expense       72.00 RUB
net result                28.00 RUB
```

It also preserves methodology/behavior identity, raw and canonical artifact
hashes, Financial Case evidence and Supplemental Fact evidence. v0 remains
separately executable and its canonical model projection remains `6,775`
bytes.

## Conformance case B — Operation Tax Model composition

For `securities_disposal_operation_tax_model_v0`, v1 delegates to the existing
G5.13 `run_operation` owner. The owner result wrapper is checked, then its exact
Tax Model payload is validated by G5.14's consumer-owned member validator.

Static compatibility is:

```text
registered output_contract_id
== broker_reports_gate5_securities_disposal_operation_tax_model_v0
== G5.14 accepted operation member contract
```

The real proof creates two members through the public v1 capability and passes
their `result_payload` objects directly to the existing public G5.14
aggregation capability. With exact completeness evidence the unchanged
aggregator returns:

```text
gross income        150.00 RUB
related expenses    102.00 RUB
allowable expenses  100.00 RUB
status              complete
```

No test or production composition calls G5.13 directly to bypass the public
typed capability.

## Conformance case C — stable income-group Tax Base

G5.22 appends `securities_income_group_tax_base_v0`. The typed owner delegates
to the new narrow behavior owner, which reuses the public G5.14 complete
category validator and G5.8 methodology authority. Its input/output contract
identities and `2026.2-experimental` methodology hashes are exact static
registry data.

The representative real route is:

```text
typed operation models -> complete category aggregation -> typed tax-base behavior
```

It returns a source-retaining stable income-group model, not a declaration
fragment. The v1 capability resource/model projection and five action families
remain unchanged.

## Provenance boundary

Typed execution does not become a fact source. The exact payload retains:

- Financial Case facts and identities;
- Supplemental Fact values, scope and user-provided provenance;
- proof/user/external context values accepted by the existing G5.13 contract;
- methodology-derived classification and allowability decisions;
- repository methodology identity and raw/canonical hashes.

Missing all registered source provenance fails before the envelope is
returned. G5.14 independently validates the Operation Tax Model's complete
source and methodology structure.

## Fail-closed boundary

The runtime rejects:

- malformed or unknown behavior identity;
- known behavior with invalid, unknown or other-entry input/output contract;
- arbitrary schema text instead of a registered contract identity;
- invalid behavior input through the existing owner validator;
- malformed registered output;
- output methodology/behavior identity mismatch;
- missing required source provenance;
- missing, unknown, malformed or hash-drifted methodology artifacts;
- an existing Python behavior that is not in the static binding;
- an attempt to supply implementation/code through the public method
  signature.

There is no alias, nearest match, default behavior or fallback.

## Anti-generic-runner boundary

Maintained execution code contains no:

```text
import by string
eval / exec
caller callable
caller schema contents
dynamic plugin loading or registration
model-generated Python
behavior fallback
```

The only ordinary-code dispatch is over the two internal constant binding IDs.
Any third behavior requires an explicit reviewed code/resource/contract/test
change.

## Closed-world and factory parity

The module and v1 JSON live inside `broker_reports_gate1`. Runtime resources are
loaded with package resources, not repository-relative paths. A copied isolated
package resolves the v1 contract and both registry identities without workspace
imports. Tampering with a copied methodology resource reaches the existing G5.8
raw-hash failure through the v1 execute path before case reads.

The canonical route is identical for proof and maintained runtime:

```text
Gate5RuntimeCapabilityResolverV1Factory.create
-> Gate5PublishedTypedBehaviorRuntimeFactory.create
-> existing behavior owner factory
-> existing authority/consumer validation
```

No UI, control endpoint or smoke script exists for this inactive proof, so no
parallel path was created.

## KISS and stop condition

G5.18 adds one v1 contract resource, one small static two-entry execution owner,
one additive G5.14 member-validation method, focused tests, this contract and a
dated report.

It adds no sixth primitive, behavior service, DB, plugin catalog, dynamic
registration, new tax behavior, group-level tax base, generic user input,
research capability, workflow DSL, Declaration Definition runner, clean-context
LLM trial, XML/PDF, GUI or product activation.

The two typed outputs, v0 parity and real `execute -> operation model ->
aggregate` route passed, so `G5.18_CLOSED`. The next slice is not authorized by
this contract.

G5.22 later appended a third static entry and one behavior owner under this
unchanged v1 contract. That additive proof is owned by
[Gate 5 Stable Income-Group Tax Base v0](./BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS.v0.md);
it does not alter the historical G5.18 closure claim.
