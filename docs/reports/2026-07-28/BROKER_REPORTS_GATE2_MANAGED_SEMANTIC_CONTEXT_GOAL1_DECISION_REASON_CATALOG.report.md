# Broker Reports Gate 2 — Managed Semantic Decision Context GOAL 1 Decision Reason Catalog

Date: 2026-07-28

Status:
`PASSED_AS_INACTIVE_DRAFT_WITH_EXPLICIT_BENCHMARK_COMPATIBILITY_STOP`

Base revision: `cdde0965e946f39e00bb4cbb6a8225d2dc2816eb`

Branch:
`codex/broker-reports-gate2-managed-context-goal1-reason-catalog`

## 1. Outcome

GOAL 1 created one versioned, GUI-ready catalog for the human meaning of the
two `unclassified_financial_input` reason codes:

`broker_reports_gate2_financial_decision_reason_catalog@1.0.0`

The catalog is an additive dependency of semantic family version `1.1.0`
inside the already selected
`broker_reports_gate2_financial_domain_assets` family. It is:

- repository-managed;
- strict JSON with a Python-generated JSON Schema;
- human-readable and mechanically contrastive;
- lifecycle-versioned;
- `draft`;
- `runtime_activation=false`;
- absent from the current model-visible request.

The current v1 family manifest, Semantic Pack, managed Skill, managed Prompt,
Workspace Tool and closed-world runtime projection remain byte-exact.
Provider calls, stage mutations and production mutations are zero.

The result is intentionally not called benchmark-compatible. The new semantic
boundary exposes a real pre-existing mismatch with some frozen V6 expected
answers; section 10 records that stop without changing expectations, Prompt,
Pack or runtime.

## 2. Scope and authority

GOAL 1 changes only the managed human-meaning asset and its inactive family
composition.

| Concern | Authority after GOAL 1 |
| --- | --- |
| reason codes and response shape | existing financial decision contract and V6 Choice |
| human reason meaning | versioned catalog JSON |
| catalog schema/checking | build-time catalog contract factory |
| financial type/role meaning | unchanged Financial Semantic Pack |
| model-visible projection | future Context V2 in the existing packet owner |
| validation/materialization | unchanged existing backend factories |

No wording was added to a provider adapter, active Prompt, Packet, Choice,
runner, validator, materializer or Python catalog contract. No second Pack,
financial registry, packet builder, asset family, GUI or publication path was
created.

## 3. Exact managed assets

### 3.1 Catalog

Repository source:
[`broker_reports_gate2_financial_decision_reason_catalog.v1.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.json)

```text
CATALOG_ID:
broker_reports_gate2_financial_decision_reason_catalog

SEMANTIC_VERSION:
1.0.0

GIT_BLOB_SHA256:
e5ca49c436113d5eebec189dae26d5a289287c214292eb32c80b547c29e56a0a

SEMANTIC_INTEGRITY_SHA256:
d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15

CANONICAL_SEMANTIC_BYTES:
3603
```

The exact human wording is not duplicated in this report. It remains readable
in the linked catalog, whose hash is pinned above and in the family manifest.

### 3.2 Generated schema and Python checker

The generated schema is:
[`broker_reports_gate2_financial_decision_reason_catalog.v1.schema.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.schema.json).

Its Git-blob SHA-256 is:
`a2285297bc1332778293b24a195dcf0dc5631e3e62076185f7336442e250a68c`.

The maintained build-time checker is:
[`broker_reports_financial_decision_reason_catalog_contracts.py`](../../../services/broker-reports-gate1-proof/scripts/broker_reports_financial_decision_reason_catalog_contracts.py).

It receives the decision-contract source as input, AST-extracts
`UNCLASSIFIED_REASON_CODES`, generates the strict schema and validates the
catalog. It performs no filesystem, environment, network or provider access
itself. Its Git-blob SHA-256 is:
`999b5d3869a9b08755bc6697c10aa725f92527a65d0d484515651420d5a8d375`.

## 4. Complete reason-entry contract

Every catalog reason contains:

1. stable `code`;
2. `display_order`;
3. `human_title`;
4. `meaning`;
5. `use_when`;
6. `do_not_use_when`;
7. `positive_example`;
8. reciprocal `contrast_with_neighbouring_reasons`;
9. a data-owned `selection_boundary`.

The GUI contract declares the stable item key, label field, ordering field,
editable human fields and immutable code/boundary fields.

The closed code set is still obtained from the decision contract:

```text
ambiguous_registry_type
no_registry_type
```

The catalog does not define a new code and does not become code-set authority.

## 5. Mechanical distinction proof

The catalog uses one explicit metric:

`plausible_distinct_available_financial_type_count`

Its two data-owned intervals are:

```text
0..0
2..unbounded
```

The Python factory does not map a named reason to either interval. It checks
that:

- the exact decision-contract code set is present once;
- the two required intervals are present and do not overlap;
- every reason contrasts against every other reason exactly once;
- self-contrast is forbidden;
- human fields are non-empty, normalized and mutually non-duplicate;
- display order is complete and unique;
- canonical semantic integrity is exact.

The code-to-meaning mapping and all human formulations therefore remain data,
not Python policy.

Count `1` is deliberately not absorbed into either unclassified reason. A
single plausible type with unresolved values or bindings needs an explicit
contract decision elsewhere; this GOAL does not silently broaden
`ambiguous_registry_type`.

## 6. Same-family immutable v2 composition

New manifest:
[`broker_reports_financial_domain_assets.v2.manifest.json`](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v2.manifest.json)

New manifest schema:
[`broker_reports_financial_domain_assets.v2.manifest.schema.json`](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v2.manifest.schema.json)

```text
FAMILY_ID:
broker_reports_gate2_financial_domain_assets

FAMILY_SEMANTIC_VERSION:
1.1.0

MANIFEST_SHA256:
4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d

MANIFEST_GIT_BLOB_SHA256:
4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586

MANIFEST_SCHEMA_GIT_BLOB_SHA256:
dde15c7d523141b0301dfe8721b2eb2746d043e19768db14d40206545f4dbfd7
```

The v2 manifest contains the same three v1 managed assets and the same first
four dependencies. It appends exactly the catalog, generated catalog schema
and catalog contract source. It remains
`target_normative_not_live`, `draft` and `runtime_activation=false`.
The v2 schema preserves the complete v1 `api_identity` object contract:
mandatory `id` and `name`, the same optional fields, and no additional
properties. An arbitrary two-field object is rejected.

The existing builder was extended additively. Its public v1 `build()` result
remains the same two byte-exact outputs; the new v2 path adds the catalog
schema, v2 manifest and v2 manifest schema. No second builder exists.

## 7. Lifecycle and rollback

Catalog draft rollback is:

`discard_without_runtime_mutation`

Family v2 pins the exact prior repository baseline:

```text
V1_FAMILY_SEMANTIC_VERSION:
1.0.0

V1_MANIFEST_SCHEMA_VERSION:
broker_reports_financial_domain_managed_asset_manifest_v1

V1_MANIFEST_SHA256:
b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59

V1_MANIFEST_GIT_BLOB_SHA256:
2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315
```

Because no runtime pointer changed, GOAL 1 draft rollback requires no runtime
mutation. Future active rollback is defined as selecting the previous
validated immutable family version.

This is not a false live rollback claim. The complete Skill/Prompt/Tool/Pack
family publisher, full candidate readback and live restore remain the explicit
GOAL 0 lifecycle gap.

## 8. Type and runtime freeze proof

Pinned unchanged identities:

```text
V1_TOOL_GIT_BLOB_SHA256:
e7c1a49cc8988e88a16a0696c03ec7469c961a838fd22dd315257e50815ffaee

PACK_GIT_BLOB_SHA256:
ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f

PACK_SEMANTIC_INTEGRITY_SHA256:
ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8

CURRENT_RUNTIME_MODEL_ASSETS_GIT_BLOB_SHA256:
e6fcaab0c323dcc88959bcccbb16a6d4b40986f9308e2ecbd65dd1a09a85dd75
```

The current model-assets builder remains pinned to family v1 and its
`--check` passes. No file under the active packet/request/provider path imports
the catalog contract. Pack/type bytes and meanings are unchanged.

Historical GOAL 3, GOAL 9, GOAL 10, Nano and GOAL 0 receipts remain untouched;
their v1 hashes continue to describe the exact historical/current baseline.

## 9. Negative-path evidence

Tests fail closed for:

- invented or missing reason codes;
- duplicate code membership;
- missing required human fields;
- self-contrast;
- incomplete neighbour contrast;
- changed selection boundaries;
- invalid display order;
- additional schema fields;
- invalid or weakened v2 `api_identity` projections;
- catalog integrity tampering;
- generated-schema drift;
- generated-family-manifest drift;
- v1 Pack/Tool/manifest/runtime projection drift.

No mocks or provider responses are used. The tests execute the real builder,
factory, JSON schemas and committed assets.

## 10. Frozen benchmark compatibility stop

The catalog's required distinction counts distinct plausible financial type
meanings/cards, never Typed Options, aliases, values or bindings.

The frozen V6 benchmark contains four `ambiguous_registry_type` cases with
`expected_typed_options=0`:

- `syn_successor_v2_multiple_compatible`;
- `syn_successor_v2_detail_vs_subtotal`;
- `syn_successor_v2_adjacent_equal`;
- `syn_successor_v2_adjacent_fx`.

The current packet derives `available_type_cards` only from type IDs present
in compiled Typed Options. Those four cases therefore do not yet prove that
the model will see two or more plausible distinct type meanings. Historical
evidence also describes some of them as value-association ambiguity.

Consequences:

- the catalog draft is valid and useful;
- frozen expected answers are not changed;
- Context V2 and benchmark conformance are not claimed;
- the full benchmark is not run;
- no corrective Prompt/Pack change is made automatically;
- a later explicit compatibility audit must decide whether context coverage,
  expected-answer policy or the reason vocabulary is the proven problem.

## 11. Verification

Executed from `services/broker-reports-gate1-proof`:

```text
python scripts/build_openwebui_managed_financial_assets.py --check
PASSED

python scripts/build_gate2_financial_semantic_model_assets.py --check
PASSED

focused pytest
84 passed

full service pytest
1887 passed, 20 skipped, 5 warnings
```

Repository checks:

```text
provider calls: 0
provider responses: 0
runtime source files changed: 0
stage mutations: 0
production mutations: 0
customer inputs read: 0
credentials read: 0
historical receipts modified: 0
```

## 12. Documentation

Canonical documentation updated in the same change:

- architecture authority map;
- global Gate architecture component map;
- Financial Decision Reason Catalog v1 contract;
- OpenWebUI Financial Domain Asset Family v1 predecessor note;
- OpenWebUI Financial Domain Asset Family v2 contract;
- LLM Semantic Context ownership/status;
- V6 Choice catalog link;
- Stage 2 Context Index;
- this report and its safe receipt.

No document was moved or renamed, so no redirect entry is required.

## 13. Acceptance

```text
REASON_MEANINGS: HUMAN_READABLE
REASONS_MUTUALLY_DISTINGUISHABLE: YES
LIFECYCLE_VERSIONED: YES
DRAFT_MUTATES_ACTIVE_RUNTIME: NO
ROLLBACK: DEFINED_WITH_EXACT_V1_BASELINE
TYPE_MEANINGS_CHANGED: NO
PYTHON_FINANCIAL_FORMULATIONS: ZERO
SECOND_SEMANTIC_AUTHORITY: ZERO
PROVIDER_CALLS: ZERO
DOCUMENTATION: UPDATED_IN_SAME_CHANGE
BENCHMARK_CONFORMANCE: NOT_CLAIMED
```

GOAL 2 may start only after this GOAL is reviewed, accepted, green and merged.
