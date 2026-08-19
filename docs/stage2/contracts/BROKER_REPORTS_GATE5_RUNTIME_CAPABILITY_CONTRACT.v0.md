# Broker Reports Gate 5 Runtime Capability Contract v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.15_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This contract defines the smallest current machine boundary between a future
Declaration Definition author and the deterministic Gate 5 runtime:

```text
future model author
        -> semantic capability IDs and conditions
        -> closed runtime resolver
        -> existing reviewed Gate 5 owners
```

A runtime capability is a stable semantic operation that has a proven
executable owner, closed inputs, explicit preconditions and failures, and a
defined provenance class. A useful Python function is not automatically a
capability. A scenario result is not automatically a reusable primitive.

This contract is not Tax Methodology, a Declaration Definition, a rules DSL,
Python API documentation or an inventory of project functions.

## Machine-readable authority

The sole contract resource is:

```text
gate5_runtime_capability_contract.v0.json
```

`Gate5RuntimeCapabilityContractFactory.create` loads it as a package resource,
checks its exact repository-pinned SHA-256, validates the closed shape and
requires exact conformance with the runtime binding table.
The resource is repository-normalized as LF so the raw-byte hash is stable
across Windows checkouts.

Every published capability contains only:

```text
capability_id
execution_phase
meaning
inputs
preconditions
output guarantees
failure conditions
provenance classes
supported value kinds
implementation status
internal conformance binding
```

The internal binding is a stable code-owned link. It is not a model-visible
Python module, class, function, path or constructor signature.

## Representative public capabilities

| Capability ID | Semantic meaning | Existing owner | Critical precondition |
| --- | --- | --- | --- |
| `resolve_required_values_v0` | resolve closed requirements from current Financial Case, then eligible same-run Supplemental Facts, with one tagged source | existing G5.5 runtime, delegating to G5.4/G5.3/G5.2 | trusted current case; no ambiguous supplemental match |
| `obtain_one_missing_money_input_v0` | ask for and accept one missing human money value, persist it and recheck | existing G5.6 runtime | exactly one current missing money requirement; strict model path |
| `execute_published_calculation_behavior_v0` | execute an already reviewed deterministic behavior named by an exact published methodology | existing G5.8 trusted calculation wrapper over G5.7 | published hash-pinned compatible methodology; supported behavior; satisfied inputs |
| `project_validated_declaration_fragment_v0` | mechanically project complete stable semantics through the current validated repository projection | existing G5.12 runtime | valid pinned evidence/spec and complete compatible semantic input |
| `aggregate_complete_category_scope_v0` | aggregate compatible complete operation models and admit complete category semantics only with exact completeness evidence | existing G5.14 runtime | at least two compatible operation models; exact scope/member binding for complete status |

The list is representative, not an automatic export of all Gate 5 code. A
future capability requires a separate reviewed contract and binding change.

## Explicit non-capabilities

- G5.2, G5.3 and G5.4 are implementation owners inside the public G5.5/G5.6
  semantics; raw selectors, artifact writes and caller-supplied artifact refs
  are not public model primitives.
- G5.9 proved that managed methodology publication is not justified yet and
  added no executable owner.
- G5.10 is architecture research, not runtime behavior.
- G5.11 prepares and accepts one fixed external rate-schedule proof, but does
  not perform research, provider transport or generic authoritative-fact
  acquisition. Publishing `research_authoritative_fact` would overclaim.
- G5.12 candidate validation remains an authoring support seam for one pinned
  evidence family. The public capability is only case-time projection through
  the already validated current resource.
- G5.13 `securities_disposal_operation_tax_model_v0` is a reviewed
  scenario-specific behavior and input producer, not a universal Tax Model
  primitive. G5.14 honestly exposes its compatible-member precondition.

No universal authoring-time executable capability is proven in the current
contour. All five published operations are `case_time`. A future Declaration
Definition author may inspect them, but G5.15 does not implement authoring,
research or compilation.

## Model-facing projection

`Gate5RuntimeCapabilityContract.model_projection()` returns the same semantic
contract without the internal `conformance` blocks. It retains IDs, meaning,
inputs, conditions, outputs, failures, supported kinds, provenance classes and
implementation status.

The exact canonical UTF-8 payload proven by G5.15 is `6,775` bytes for five
capabilities. It contains no:

```text
binding_id
owner_contract
Gate5 class name
RuntimeFactory name
Python module or path
database, SQL or artifact implementation detail
```

The payload is intentionally small enough to inspect as one model context. It
does not contain methodology bytes, tax formulas, declaration mappings or
case data.

## Runtime resolver

The sole resolver construction path is:

```python
Gate5RuntimeCapabilityResolverFactory.create()
```

It accepts only this closed reference:

```json
{
  "schema_version": "broker_reports_gate5_runtime_capability_ref_v0",
  "capability_id": "project_validated_declaration_fragment_v0"
}
```

Known IDs resolve to an internal binding that constructs the existing owner.
The binding validates its exact internal dependency set before factory
construction. Existing owner input/precondition checks remain unchanged after
resolution.

Unknown IDs raise:

```text
gate5_runtime_capability_unsupported
```

There is no aliasing, nearest-name match, implicit default, dynamic import or
fallback.

## Conformance and drift

Factory construction fails unless:

1. the package resource exists and matches the exact SHA-256 pin;
2. the resource is valid closed JSON with 4–7 unique capabilities;
3. contract capability IDs equal runtime binding IDs exactly;
4. every contract `binding_id` equals its code binding;
5. every bound factory still has `create`;
6. every bound runtime class still exposes every declared operation.

A code function may exist without becoming public. Only an explicit contract
entry plus an explicit binding publishes a capability. A contract-only or
binding-only addition fails with
`gate5_runtime_capability_contract_drift`.

## Failure and provenance semantics

The capability layer adds no error recovery. It rejects malformed references
and invalid binding dependencies before owner construction, then preserves the
existing owner's closed failures. In particular, missing projection inputs do
not produce a fragment and missing tax completeness does not become a complete
category result.

The contract keeps these meanings distinct:

```text
financial_case_evidence
user_case_evidence
user_verified_completeness
methodology_derived_result
declaration_projection
```

The representative subset does not publish external authoritative evidence as
an executable capability. G5.11 evidence remains a separate provenance class
inside its bounded proof and is not recast as user or Financial Case evidence.

## Hardcode boundary

```text
DECLARATION-SPECIFIC COMPOSITION
        future data / Declaration Definition
                    |
                    v
       Runtime Capability Contract
             stable semantic IDs
                    |
                    v
STABLE EXECUTION MECHANICS
        ordinary reviewed code
```

Changing a future declaration's order and composition should not require new
orchestration branches. Reviewed Decimal arithmetic, closed validators,
source/access checks, methodology hash pins, projection validation and exact
completeness checks correctly remain code.

G5.15 does not move formulas, rates, 3-NDFL codes, XML paths or declaration
workflow into this contract.

## KISS and stop condition

G5.15 adds one package JSON resource, one small resolver/contract module,
focused conformance tests, this contract and one dated report. It adds no DB,
table, service, plugin system, workflow engine, rules DSL, dynamic Python
loading, LLM compiler, Declaration Definition Package, GUI or product route.

The closed resource, five exact bindings, model projection and conformance
proof passed, so `G5.15_CLOSED`. No later Gate 5 slice is authorized by this
contract.
