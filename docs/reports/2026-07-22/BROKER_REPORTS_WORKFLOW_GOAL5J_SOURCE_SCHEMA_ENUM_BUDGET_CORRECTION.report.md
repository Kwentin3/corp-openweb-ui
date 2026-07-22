# Broker Reports Workflow Goal 5J — Source Schema Enum-Budget Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5j-source-schema-enum-budget-v1`

Correction family: Gate 2 semantic-selection provider schema

Implementation status: PASSED

Live release and reproof: PENDING AFTER MERGE

## Trigger

The first native Gate 2 source run after Goal 5G reached the approved OpenWebUI
answer-model connection with strict JSON Schema and no fallback, but six model
calls were rejected before inference. The provider reported 1001–1037 enum
values per schema against a hard limit of 1000.

## Root cause

The compact response shape was already correct, but its schema represented
each fact type as an `anyOf` branch. Every branch repeated the same bounded
source-ref and source-value-ref enums. The duplication was provider-facing
schema overhead; it added no semantic information to the model result.

## Narrow correction

- Replaced the repeated per-type `anyOf` branches with one strict fact object.
- Kept the response object and every fact field unchanged.
- Kept type/subtype compatibility in the deterministic validator, where it was
  already enforced.
- Retained strict JSON Schema, `additionalProperties: false`, bounded arrays,
  package-scoped source refs and the existing canonical materializer.
- Regenerated all maintained Function bundles from the shared module so an
  atomic release cannot deploy a mixed bundle set.

This does not change the Gemini semantic visual-table JSON contract, prompt,
model selection, crop extraction, private intake, Gate ownership or storage
architecture.

## Evidence

- failing live schemas: 6;
- observed live enum totals: 1001–1037;
- representative bounded schema after correction: 514 enum values;
- provider limit: 1000;
- provider schema `anyOf`: absent;
- focused and affected regression tests: 49 passed;
- Ruff: passed;
- Python compile check: passed;
- `git diff --check`: passed.

SHA-256:

- semantic-selection module:
  `7770419861bfa41ee967ca2c4d19217fd1678fedcf23b8b298251109cff9d212`
- Gate 1 bundle:
  `3465800155ec42e256e1dfe3ca248876767a0b483b2bea6c6110238eee8b14f7`
- Gate 2 source bundle:
  `57364f8a9f188f59c386afa6c5262c9c9a8c62a3f5df148fb5c0c64a3da976b8`
- Gate 2 domain bundle:
  `4a804689caedb0a8702e5af8f7501b5939ac3267c5b1298c65e3c89061ad328b`

## Remaining measured defect

This slice intentionally does not hide or combine the separate non-atomic
value-binding defect observed in the same live run. That defect remains
NOT_CLOSED and requires its own corrective branch after Goal 5J is released and
reproved.
