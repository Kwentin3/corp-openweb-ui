# Broker Reports Gate 2 Managed Financial Domain — Goal 2 Financial Semantic Pack

Date: 2026-07-26

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

Base revision: `86d7c3ca722f31f3dc251596d65371abe2d7b865`

Branch: `codex/broker-reports-gate2-domain-goal2-financial-semantic-pack`

## 1. Outcome

GOAL 2 creates the machine-readable, versioned target semantic authority:

- Pack schema: `broker_reports_financial_semantic_pack_v1`;
- Pack ID: `broker_reports_managed_financial_semantic_pack`;
- semantic version: `1.0.0`;
- consumer contract:
  `broker_reports_managed_financial_domain_contract_v1`;
- canonical bytes: `9404`;
- integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- authority status: `target_normative_not_live`;
- runtime activation: false.

The full compact snapshot contains exactly two evidence-backed active types:

1. `cash_balance_snapshot_v1`;
2. `printed_financial_metric_v1`.

No research candidate was promoted.

## 2. Type contract

Every Pack type has:

- stable `input_type_id`, title, definition, and semantic class;
- required, optional, and forbidden roles;
- role value types, cardinalities, and mandatory source-ref policy;
- date/period, currency/unit, sign, and identity rules;
- safe examples and counterexamples;
- synonyms;
- semantic distinctions;
- fail-safe ambiguity guidance;
- lifecycle, deprecation, retirement, and replacement metadata;
- operational contract IDs, safe evidence refs, test refs, and migration
  fingerprints.

The complete type objects are the `full_compact_snapshot`; no second reduced
semantic copy can drift.

## 3. Conservative admission boundary

The source baseline remains:

- Registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- Registry SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`.

Ten statement/schedule candidates remain explicit
`deferred_candidate_ids`. Deferred does not mean admitted. Broad legacy fact
IDs, router domains, source labels, evidence kinds, and technical dispositions
are not Pack type IDs.

The current runtime still contains two legacy Python type declarations. This
GOAL does not hide that fact. The target `semantic_packs/` authority contains
zero Python files and zero Python-authored type meaning.

## 4. Tenant overlay

The same strict JSON Schema defines
`broker_reports_financial_semantic_pack_tenant_overlay_v1`.

An overlay is optional, versioned, disabled by default, scoped by an opaque
tenant ref, and pinned to the exact base Pack semantic version and integrity
hash.

Allowed:

- guidance augmentation;
- a complete experimental tenant type.

Forbidden:

- base definition, role, or identity modification;
- base type removal;
- unqualified type activation;
- tax methodology.

Schema probes accepted a valid versioned guidance overlay and rejected:

- an empty no-op overlay;
- an active, unqualified tenant type.

## 5. Canonical serialization

Pack integrity uses canonical UTF-8 JSON without BOM or whitespace, with
lexicographically sorted object keys, normative array order, and the top-level
`integrity_sha256` field omitted.

Changing any semantic or overlay-policy material changes the Pack hash.
Breaking meaning also requires a new semantic version.

## 6. Explicit non-goals

This GOAL adds no:

- production/runtime behavior;
- live OpenWebUI Skill, Prompt, Function, Tool, or Knowledge asset;
- provider/customer/source/domain model call;
- fallback or repair;
- stage mutation;
- tax, declaration, ledger, cost-basis, P/L, netting, or FX methodology;
- current runtime Registry removal.

## 7. Deliverables

1. `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.json`
   - SHA-256:
     `ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f`
2. `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.schema.json`
   - SHA-256:
     `cea99c199ba6b20905fd988fed481e963a999d1a74464a0af055d38eb0c76b9e`
3. `docs/stage2/contracts/BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md`
   - SHA-256:
     `3f326a6c2da1baf4b636689648e6f6eabca5ff24850edd2a64f69929f11c76c6`
4. `services/broker-reports-gate1-proof/tests/test_broker_reports_financial_semantic_pack.py`
   - SHA-256:
     `765f9710938d9a553a06a2ffe64f5f9f1e7f9551b6dfe6198be078df9daab71b`
5. repository-safe receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL2_FINANCIAL_SEMANTIC_PACK.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL2_FINANCIAL_SEMANTIC_PACK.receipt.safe.json)
   - SHA-256:
     `49607beee66ae8ce4c6b5f2cbbe2dec964893dac1fc24d040061aad0f76f5fdf`

## 8. Fresh review correction

The first remote PR-head review returned `CHANGES_REQUIRED`: both base type
definitions had been semantically rephrased instead of copied exactly from the
accepted Registry baseline. IDs, roles, and policies were exact, but silent
definition wording drift is not allowed during authority migration.

Both definitions now have byte-exact Registry parity (`2/2`). Synonyms,
distinctions, and ambiguity guidance remain separate Pack fields. A dedicated
test prevents future definition drift.

## 9. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- Pack tests: `8 passed in 0.33s`;
- focused Pack/consumer/Registry/materialization tests:
  `99 passed in 1.10s`;
- full Broker Reports suite:
  `1536 passed, 20 skipped, 5 warnings in 113.07s`;
- JSON Schema meta-validation: passed;
- Pack instance validation: passed;
- Pack integrity recomputation: passed;
- tenant overlay positive/negative probes: passed;
- targeted Ruff: passed;
- targeted compileall: passed;
- accepted Registry definition parity: `2/2`;
- repository privacy guard: `3 passed in 0.87s`;
- provider/customer/model calls: 0;
- stage/production mutations: 0.

## 10. Acceptance markers

```text
SEMANTIC_PACK: VALIDATED_AND_VERSIONED
TYPE_MEANINGS_IN_PYTHON: ZERO_IN_TARGET
FULL_PACK_DELIVERY: SUPPORTED
TENANT_EXTENSION: EXPLICIT_AND_VERSIONED
RUNTIME_ACTIVATION: FALSE
NEXT_PERMITTED_GOAL: GOAL_3_AFTER_GOAL_2_REVIEW_ACCEPTANCE_AND_MERGE
```
