# Broker Reports Gate 5 — Published Typed Behavior Execution (G5.18)

Date: `2026-08-10`

Status: `G5.18_CLOSED`

Outcome: `PROVEN_WITH_TWO_REGISTERED_TYPED_OUTPUTS`

Product status: `INACTIVE PROOF`

## Answer

Да. Один closed versioned capability
`execute_published_typed_behavior_v1` безопасно исполняет два заранее
опубликованных deterministic behaviors с различными typed outputs:

1. `security_disposal_net_result_v0` возвращает прежний trusted calculation
   result с semantic parity;
2. `securities_disposal_operation_tax_model_v0` возвращает exact Operation Tax
   Model, который напрямую принимает existing G5.14 aggregation boundary.

Доказанная public composition:

```text
Gate5RuntimeCapabilityResolverV1Factory.create
-> execute_published_typed_behavior_v1
-> broker_reports_gate5_securities_disposal_operation_tax_model_v0
-> aggregate_complete_category_scope_v0
-> complete category aggregation
```

Новый primitive не добавлен. v1 version-replaces только слишком узкий execute
member в contract из пяти action families. Runtime не стал generic plugin
runner: caller не может передать schema contents, implementation, callable,
module, path или code; исполняются только две exact static combinations.

## Before / After

### До G5.18

```text
Runtime:
«агрегировать Operation Tax Model умею,
но публично создать его не умею».
```

G5.13 имел reviewed `run_operation`, G5.14 принимал его model, но G5.15
публиковал только calculation-only output contract. G5.16 поэтому честно
возвращал `missing_runtime_capability` для operation members.

### После G5.18

```text
Runtime:
«умею исполнить опубликованный typed behavior;

один из опубликованных behaviors
создаёт Operation Tax Model;

его result_payload принимает aggregator».
```

Это расширение прежней primitive family, потому что stable runtime action не
изменился: разрешить exact published behavior, выполнить reviewed deterministic
owner и вернуть validated result. Изменился только разрешённый output contract
shape. Tax classification, expense allowability и model meaning остаются в
G5.13 behavior/methodology, а не в capability.

## Delivered boundary

| Deliverable | Result |
| --- | --- |
| versioned runtime contract | [Runtime Capability Contract v1](../../stage2/contracts/BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v1.md) |
| machine authority | `gate5_runtime_capability_contract.v1.json`, LF SHA-256 `e5134005e3715e70249f14dd1918ce4d110e70bb6eba1304ccbd9204c1531e8f` |
| typed execution owner | `gate5_published_typed_behavior.py` |
| consumer compatibility owner | additive `validate_operation_member` on existing G5.14 factory-created runtime |
| public resolver | additive v1 contract/resolver factories in existing G5.15 owner |
| tests | one focused typed-execution test module plus architecture allowlist update |
| authority routing | existing capability row advanced to v1; no second tax/domain authority |

The previous [Runtime Capability Contract v0](../../stage2/contracts/BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v0.md)
and its resource remain unchanged and replayable.

## Version coexistence

| Surface | v0 | v1 |
| --- | --- | --- |
| reference schema | `broker_reports_gate5_runtime_capability_ref_v0` | `broker_reports_gate5_runtime_capability_ref_v1` |
| contract factory | `Gate5RuntimeCapabilityContractFactory.create` | `Gate5RuntimeCapabilityContractV1Factory.create` |
| resolver factory | `Gate5RuntimeCapabilityResolverFactory.create` | `Gate5RuntimeCapabilityResolverV1Factory.create` |
| execute ID | `execute_published_calculation_behavior_v0` | `execute_published_typed_behavior_v1` |
| execute output | one trusted calculation result | common envelope with registered typed payload |
| family count | `5` | `5` |

v0 canonical model projection remains exactly `6,775` bytes. v1 model
projection is `7,461` bytes. The versioned resolvers reject the other version's
reference/capability combination rather than aliasing or upgrading it.

## Exact registry/binding boundary

The static binding has exactly two entries:

| Published identity | Input contract | Output contract | Trusted owner |
| --- | --- | --- | --- |
| `ru-ndfl-securities-proof@2026.0-experimental / security_disposal_net_result_v0` | `broker_reports_gate5_no_additional_behavior_input_v1` plus trusted case context | `broker_reports_gate5_trusted_calculation_result_v0` | G5.8 wrapper -> G5.7 calculator |
| `ru-ndfl-securities-tax-model-proof@2026.1-experimental / securities_disposal_operation_tax_model_v0` | `broker_reports_gate5_securities_disposal_resolved_inputs_v0` plus trusted case context | `broker_reports_gate5_securities_disposal_operation_tax_model_v0` | G5.13 operation runtime |

Each internal entry additionally pins one code-owned implementation binding and
the existing repository methodology authority. Caller sees neither Python owner
nor implementation ID. There is no registration API, DB, catalog service,
plugin loader or runtime package manager.

The existing Python implementation
`securities_disposal_tax_model_v0@2026.0-experimental` is intentionally absent
from this map. A request for it fails `unsupported`. This proves that code
existence is not public execution authority.

## Typed result envelope

The common `broker_reports_gate5_typed_behavior_result_v1` contains only:

```text
schema_version
status = executed
behavior_binding
  methodology_id/version
  behavior_id
  input_contract_id
  output_contract_id
artifact_binding
provenance retention inventory
result_payload
```

It does not know `proceeds`, category, related/allowable expenses or any other
Tax Model field. Concrete fields remain in the registered payload contract.
Complete source structures are retained in `result_payload`; `source_kinds` is
only an inventory and does not replace provenance.

## Conformance A — G5.7 semantic parity

Both legacy v0 and v1 were executed over the same current synthetic Financial
Case and Supplemental Facts.

v1 `result_payload` equals the unchanged G5.8 trusted result:

```text
proceeds                100.00 RUB
recognized expense       72.00 RUB
net result                28.00 RUB
```

Preserved exactly:

- methodology and behavior identity;
- raw resource and canonical projection hashes;
- calculation/rule binding;
- input requirement refs;
- Financial Case fact provenance;
- Supplemental Fact scope and user-provided provenance;
- deterministic Decimal outputs.

The typed wrapper creates no writes and adds no fallback.

## Conformance B — real execute -> aggregate

Two independent operation cases were prepared with existing case/fact owners.
Each Operation Tax Model was produced only through:

```text
v1 capability resolver
-> resolved typed runtime
-> runtime.execute
-> result_payload
```

The test did not call G5.13 `run_operation` directly.

Static compatibility:

```text
registry output_contract_id
== G5.13 producer contract
== G5.14 accepted member contract
== broker_reports_gate5_securities_disposal_operation_tax_model_v0
```

The two exact payloads were passed to the G5.14 capability as members. With an
exact user-verified completeness binding, the existing aggregator returned:

```text
status              complete
gross income        150.00 RUB
related expenses    102.00 RUB
allowable expenses  100.00 RUB
```

The `102.00` versus `100.00` distinction proves that typed execution reused
G5.13 allowability semantics rather than reconstructing them in the adapter.

## Provenance proof

The operation payloads retain distinct observed source kinds:

```text
financial_case
supplemental_fact
user_provided_supplemental
proof_assumption
methodology_derived
```

The methodology binding retains authority owner, methodology identity/version,
raw resource hash, canonical projection hash, behavior ID and applicability
rule. Typed execution is not listed as a source of facts.

Removing every source provenance marker from an otherwise registered payload
fails `gate5_published_typed_behavior_provenance_missing`.

## Fail-closed proof

| Case | Terminal result |
| --- | --- |
| unknown/unregistered behavior | `gate5_published_typed_behavior_unsupported` |
| invalid input contract identity | `..._input_contract_invalid` |
| known behavior + unknown/wrong input contract | `..._input_contract_mismatch` |
| known behavior + unknown/wrong output contract | `..._output_contract_mismatch` |
| arbitrary schema text | rejected before owner execution |
| malformed registered payload | `..._output_validation_failed` |
| missing required provenance | `..._provenance_missing` |
| methodology resource hash drift | existing `gate5_trusted_methodology_resource_hash_mismatch` propagates through v1 before case reads |
| Python behavior exists but is not registered | unsupported |
| arbitrary implementation/code reference | impossible in exact public signature; no `**kwargs` |

Unknown combinations never select a nearest behavior and never reach a domain
owner.

## Anti-generic-runner proof

AST/source checks confirm maintained typed execution has no:

```text
dynamic import APIs / import by string
eval / exec / __import__
entry-point or plugin discovery
caller callable or implementation ref
caller-supplied schema contents
fallback behavior
```

`importlib.resources` remains the existing closed-world package-resource loader;
it is not a code/module loader.

Ordinary dispatch has exactly two internal constant identities. Adding a third
entry requires a reviewed source/contract/test change; it cannot happen at
case time.

## Factory and closed-world proof

Canonical route:

```text
Gate5RuntimeCapabilityResolverV1Factory.create
-> Gate5RuntimeCapabilityContractV1Factory.create
-> Gate5PublishedTypedBehaviorRuntimeFactory.create
-> G5.8/G5.7 or G5.13 existing factory
-> G5.14 member validation for operation output
```

The code uses package imports/resources only. An isolated copied package:

- loaded and hash-validated the v1 resource;
- resolved its five capabilities;
- described the registered calculation output contract;
- failed on a tampered copied methodology resource through the real v1 path.

No new dependency, environment variable, workspace-source import, filesystem
path lookup or generated bundle was introduced. This inactive proof has no UI,
control-check or smoke path, so no parallel execution route exists.

## Model-visible capability

The v1 model projection tells the future author:

- select an exact published behavior ref;
- supply exact registered input/output contract IDs;
- supply the behavior input and trusted case context;
- expect a typed result envelope whose output type is fixed by the binding;
- expect unsupported, contract mismatch, validation, provenance and artifact
  failures.

It omits `conformance`, implementation IDs, factory/classes, modules/functions,
`.py` names and filesystem paths.

## Verification

Execution shell: PowerShell, commands run from
`services/broker-reports-gate1-proof`. No test ENV was required.

Terminal results:

```text
focused G5.18
12 passed

G5.7/G5.8/G5.13/G5.14/G5.15/G5.18 combined
39 passed

all test_broker_reports_gate5_*.py
83 passed

KT1 architecture stabilization
18 passed, 1 unrelated existing DeprecationWarning

all Gate 5 + KT1 combined after final code/test edits
101 passed, 1 unrelated existing DeprecationWarning

authority-map-sensitive contract suites
49 passed

ruff check (touched maintained/test modules)
passed
```

The full service command `python -m pytest -q --tb=short` reached the external
`604s` command timeout without stdout, assertion diff or pytest summary. It has
no terminal verdict and is not reported as green or as a test assertion
failure. Focused, entire Gate 5 and architecture suites all produced terminal
green summaries.

Test isolation uses a fresh pytest `tmp_path` ArtifactStore/SQLite/payload root
per test and `monkeypatch` only for existing synthetic Gate 4 fixture data.
Core typed execution, registry, behavior owners and aggregator are not mocked.
The irreversible boundary is trusted case/artifact persistence performed by
existing setup owners; assertions check returned calculation/model/aggregate
results and verify the typed executor adds no writes.

## KISS and stop

- capability family count: `5 -> 5`;
- new registered behaviors: exactly `2`, both pre-existing;
- new tax behavior/formula: none;
- static binding: one in-process closed map;
- DB/service/plugin/dynamic registration: none;
- generic schema/code execution: none;
- G5.13 tax behavior rewrite: none;
- group-level tax base: not implemented;
- human value-kind generalization: not implemented;
- clean-context LLM trial: not run;
- product activation/GUI/XML/PDF: none.

G5.18 stops here. No next slice was started or authorized.
