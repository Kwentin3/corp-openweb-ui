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
     `9538ccb8f2111efa24e25d1b7b10145ccff8ca4e3c655cdc6d71b916d926c3fd`
2. `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.schema.json`
   - SHA-256:
     `833b1d15b0e383ee80220ba5f347b4009d150ff8ce19336e17aff3c805d70385`
3. `docs/stage2/contracts/BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md`
   - SHA-256:
     `a34f3ab1db3f9cbfb92541b5045b5425b5547dec52f17e08d97525e49490305f`
4. `services/broker-reports-gate1-proof/tests/test_broker_reports_financial_semantic_pack.py`
   - SHA-256:
     `62ff2dad6bfade42e9f0c553a72f55ae9b5ac67f70f24f3f717607ea978db4a4`
5. repository-safe receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL2_FINANCIAL_SEMANTIC_PACK.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL2_FINANCIAL_SEMANTIC_PACK.receipt.safe.json)
   - SHA-256:
     `31b8a9709f39d5014ccadcf9a0ff13fabad923488ff3d82ed339318d998bd3cf`

## 8. Fresh review correction

The first remote PR-head review returned `CHANGES_REQUIRED`: both base type
definitions had been semantically rephrased instead of copied exactly from the
accepted Registry baseline. IDs, roles, and policies were exact, but silent
definition wording drift is not allowed during authority migration.

Both definitions now have byte-exact Registry parity (`2/2`). Synonyms,
distinctions, and ambiguity guidance remain separate Pack fields. A dedicated
test prevents future definition drift.

## 9. Evidence reconciliation

The semantic-definition correction changed all four hashed GOAL 2
deliverables after their initial report/receipt hashes had been calculated.
The stale pre-correction SHA-256 values were discovered after merge during the
next fresh repository pass.

Corrective GOAL 2C replaces all four stale values with hashes of the merged
artifacts and adds
`test_goal2_safe_receipt_hashes_current_deliverables`, which recomputes every
declared deliverable hash from repository bytes. The Pack semantic integrity
hash, canonical semantic bytes, authority boundary, and production state did
not change.

## 10. Verification

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

## 11. Acceptance markers

```text
SEMANTIC_PACK: VALIDATED_AND_VERSIONED
TYPE_MEANINGS_IN_PYTHON: ZERO_IN_TARGET
FULL_PACK_DELIVERY: SUPPORTED
TENANT_EXTENSION: EXPLICIT_AND_VERSIONED
RUNTIME_ACTIVATION: FALSE
NEXT_PERMITTED_GOAL: GOAL_3_AFTER_GOAL_2_REVIEW_ACCEPTANCE_AND_MERGE
```
