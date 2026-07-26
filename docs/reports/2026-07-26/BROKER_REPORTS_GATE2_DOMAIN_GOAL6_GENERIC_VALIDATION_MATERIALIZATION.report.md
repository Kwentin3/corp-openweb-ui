# Broker Reports Gate 2 Domain — GOAL 6 Generic Validation and Materialization

Date: 2026-07-26.

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Base revision: `258c3d6356ae46efe02e409b493923d007a220bd`.

Branch:
`codex/broker-reports-gate2-domain-goal6-generic-materialization`

## 1. Objective

Remove concrete financial type IDs and source vocabulary from the canonical
validator, materializer, and financial-context branch logic while preserving
strict source-package ownership and v1 read compatibility.

Target contract:
[`BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md).

## 2. Versioned result

New canonical records are versioned rather than silently changing v1:

```text
validated_decision=broker_reports_financial_evidence_validated_decision_v2
financial_inputs=broker_reports_financial_evidence_inputs_v2
materialization_policy=broker_reports_financial_evidence_materialization_v2
financial_context=broker_reports_gate2_financial_context_v2
context_projection_policy=broker_reports_gate2_financial_context_projection_v2
```

The production runtime binds artifact types to these source constants and
keeps `write_policy=new_schema_only`.

Frozen v1 financial-input and context artifacts remain validator/read
compatible. A v1 payload is rejected by the write contract. The historical
successor ambiguity audit can reconstruct a frozen v1 integrity hash locally
from a current deterministic candidate, but it cannot write that projection.

## 3. Pack-authoritative runtime contract

`Gate2FinancialSemanticContractFactory` is a new closed-world boundary between
the complete managed Pack and the Registry. It rejects any difference in:

- active type membership;
- title, lifecycle, semantic class, or source-family compatibility;
- required, optional, or forbidden roles;
- role value type, cardinality, and source-ref policy;
- date/period, currency/unit, and sign policies;
- identity roles and source identity flags;
- materialization, validation, and context profiles.

Exact Pack identity:

```text
pack_id=broker_reports_managed_financial_semantic_pack
semantic_version=1.0.0
integrity_sha256=ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8
```

The Pack bytes, managed Skill bytes, and managed Prompt bytes are unchanged.

## 4. Pack hash on records

Every v2 root financial-input artifact and context carries the exact Pack
identity. Every typed and unclassified terminal record carries
`semantic_pack_integrity_sha256`.

The same Pack hash participates in:

- validated-decision authority;
- typed and unclassified terminal IDs;
- root artifact ID;
- terminal and root integrity validation;
- context input-type projection.

Tampered Pack identity or Pack/Registry drift fails closed before a record is
accepted.

## 5. Generic validation

The validator now derives type, role, value, cardinality, identity, dimension,
sign, and operational rules from the Pack-backed runtime contract. On the
canonical materializer path it also receives the authoritative Source Package
and proves:

- exact package projection;
- source-value ref membership;
- literal, type, evidence, and lineage equality;
- no duplicate bindings;
- exact normalization run, document, package, and scope ownership.

The four terminal dispositions and coverage closure remain unchanged. IDs,
values, comparison projections, dimensions, provenance, restrictions,
validation refs, and integrity remain code-owned.

## 6. Removed type-specific branch

The former branch:

```text
printed_financial_metric_v1 -> source_printed
```

is absent from the runtime. One schema rule now maps the Pack-owned
`semantic_class`:

```text
aggregate -> source_printed
state | event | attribute -> not_aggregate
```

An unsupported semantic class fails closed. The AST/source proof covers the
semantic contract, materializer, materialization validator, context projector,
and context validator:

```text
concrete_type_ids_total=0
source_printed_schema_rules_total=1
```

## 7. Closed-world bundle

The official Gate 2 domain bundle now installs modules in dependency order:

1. exact semantic model assets;
2. generic semantic runtime contract;
3. materialization and validation;
4. context and successor consumers.

Two official rebuilds were byte-exact:

```text
bundle_sha256=b96dd3c0db149f507753936f587161df7cd0ab263fa87eb279997b4170d9d7ef
bundle_rebuild=exact
```

Bundle loading and the existing single factory-backed provider route both
pass. No workspace-only import, filesystem fallback, network call, RAG, or
vectorization was introduced.

## 8. Verification

Explicit PowerShell test cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- focused generic/compatibility/runtime/bundle/replay suite:
  `128 passed in 23.66s`;
- corrected regression recheck: `9 passed in 19.36s`;
- final full Broker Reports suite:
  `1561 passed, 20 skipped, 5 unchanged warnings in 140.44s`;
- repository privacy guard: `3 passed in 0.86s`;
- official bundle rebuild: exact;
- targeted Ruff: passed;
- package-facade Ruff: passed with historical `F401` excluded;
- targeted compileall: passed;
- staged `git diff --check`: passed;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

The first full run after the schema change exposed an obsolete static v1 write
assertion and four frozen v1 hash-replay expectations. The final implementation
keeps v2-only writes and handles frozen v1 replay explicitly; the final full
run above is after those corrections.

## 9. Privacy and scope boundary

No customer/private document, value, source ref, raw provider output, secret,
or private path was added to Git or the safe evidence.

This GOAL does not:

- activate the v2 schemas on stage or production;
- claim live stage migration or customer acceptance;
- change Pack, Skill, or Prompt bytes;
- widen workload budgets or production admissions;
- create the GOAL 7 domain catalog/query API;
- add Gate 3 ArtifactStore access or tools.

## 10. Acceptance

```text
VALIDATOR_FINANCIAL_LANGUAGE_KNOWLEDGE=ZERO
MATERIALIZER_TYPE_BRANCHES=ZERO_OR_SCHEMA_JUSTIFIED
PACK_HASH_ON_RECORD=REQUIRED
```

Authoring status:
`IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Next permitted goal:
`GOAL_7_AFTER_GOAL_6_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.

## 11. Safe receipt

Repository-safe receipt:
[`BROKER_REPORTS_GATE2_DOMAIN_GOAL6_GENERIC_VALIDATION_MATERIALIZATION.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL6_GENERIC_VALIDATION_MATERIALIZATION.receipt.safe.json)

Exact staged Git-blob SHA-256:

`92e57f10820ef04805b34a1d3ee7feae273c01c373659f9a634cae935d012d8d`
