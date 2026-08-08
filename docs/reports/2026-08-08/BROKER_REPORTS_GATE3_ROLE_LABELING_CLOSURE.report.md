# Broker Reports Gate 3 Role Labeling Closure

Status: `PASS`

Date: 2026-08-08

## GOAL_STATUS

`GATE3_ROLE_LABELING = CLOSED_FOR_ROLE_COMPLETE_FACTS`.

For a fact already selected by Gate 3, ordinary code can now obtain the
financial label and every applicable source-local value through canonical
role bindings. It does not need an LLM or a broker-format adapter to decide
which field is the date, asset, quantity, unit price, amount or currency.

This is not a claim that sparse Gate 3 labeling found every financial fact in
the document.

## What was reused

- exact active `CanonicalArtifactV1` reads through
  `CanonicalReaderFactory.create`;
- `Gate3ProjectionV1`, structural chunks, target aliases and canonical target
  grammar;
- the published financial-label dictionary and pass-1 validator;
- the existing `Gate2StructuredModelClientFactory.create` provider path and
  provider adapters;
- immutable ArtifactStore sidecars, `ArtifactResolver`, access control,
  retention and exact canonical-version binding.

## What was added

- one hash-pinned Role Pack, `broker-reports-financial-roles@1.0.0`, owning
  exactly six roles and all nine required/optional profiles;
- one pass-2 proposal for all pass-1 facts in a non-empty chunk;
- fail-closed restoration and validation of fact aliases, labels, roles,
  cardinality, canonical targets and literal `exact_text`;
- `FinancialAnnotationsV2`, the next version of the same logical sidecar;
- one deterministic role-value resolver for validation and downstream code;
- current NDFL product-path, persistence, readiness, bundle and authority-doc
  updates.

Historical V1 sidecars remain readable. New writes and current readiness use
role-complete-capable V2 only.

## Representative proof

The executable proof builds one canonical table through the production
canonical factory/read boundary, sends pass 1 and pass 2 through the existing
structured model-client path with controlled responses, persists canonical
targets, and then resolves all role bindings using ordinary code.

| Fact | Required/applicable values resolved by ordinary code | Result |
| --- | --- | --- |
| `SECURITY_PURCHASE` | date `2026-01-10`; asset `ACME`; quantity `10`; amount `125.00`; currency `USD`; optional unit price `12.50` | `PASS` |
| `SECURITY_DISPOSAL` | date `2026-02-11`; asset `ACME`; quantity `4`; amount `60.00`; currency `USD`; optional unit price `15.00` | `PASS` |
| `DIVIDEND_INCOME` | date `2026-03-12`; amount `8.00`; currency `USD`; optional asset `ACME` extracted as literal `exact_text` from a larger description target | `PASS` |
| `TRANSACTION_CHARGE` | date `2026-02-11`; amount `1.25`; currency `USD`; optional asset explicitly `missing` | `PASS` |
| `TAX_WITHHELD` | date `2026-03-12`; amount `1.20`; currency `USD`; optional asset explicitly `missing` | `PASS` |

The single representative chunk made exactly two provider-path calls: one
type pass and one role pass for five facts. It did not make one call per fact.
An empty pass-1 result is separately proved to skip pass 2 and emit an empty,
validated V2 payload.

Prior real representative-corpus evidence established that all five required
labels occur under the final strict pass-1 contract. This GOAL does not repeat
the private corpus or provider calls; its new proof isolates the role contract,
source binding and deterministic materialization boundary without committing
private report values or raw provider payloads.

## Fail-closed evidence

Tests reject:

- an unknown, missing or duplicated fact alias;
- a changed financial label;
- an unknown/disallowed/duplicated role or wrong role cardinality;
- an unknown target alias or canonical target;
- non-literal `exact_text`;
- a composite target without an unambiguous scalar or literal `exact_text`;
- an incomplete batch, stale canonical binding or mismatched dictionary,
  Role Pack, instruction or model identity.

Persistence repeats target, role-profile and literal-source validation before
save. Raw provider output is not placed in the product sidecar.

## Test evidence

- focused role-pack, role-pass, batch, persistence and NDFL regression:
  `61 passed`;
- final generated-bundle, role and architecture parity smoke: `47 passed`;
- successor-hash and new-module/CI inventory anti-drift regression:
  `44 passed, 2 skipped`;
- full service suite: `2948 passed, 5 skipped, 6 warnings`;
- Ruff on all changed maintained Python and tests: `PASS`;
- `git diff --check`: `PASS`.

The proof uses synthetic values only and performs zero external provider
calls.

The starting `main` CI had one documentation guard failure because its current
Canonical Reader/Pipeline authorities omitted two already-asserted global
default-policy strings. Those strings were restored without changing reader or
valve runtime; the formerly failing selector and the full suite now pass.

## KISS and non-goals

There is one Role Pack owner, one added role pass inside the existing batch,
one V2 sidecar, and one resolver. `related_fact` is absent. No retrieval,
RAG, embeddings, new provider adapter, broker-specific runtime logic,
database or orchestration framework was added.

Gate 4, SQL schema/cache, cross-fact or cross-document relations, dividend to
tax linking, purchase to sale linking, FIFO, cost basis and tax calculations
remain outside this GOAL.

## Remaining limitation

A binding with `status=missing` is intentionally not a value. Downstream code
can detect that condition mechanically and must not treat the fact as
role-complete for a calculation requiring that role. No further document
interpretation is hidden in the next layer.

Historical evidence reused:

- [representative semantic quality proof](../2026-08-07/BROKER_REPORTS_GATE3_REPRESENTATIVE_SEMANTIC_QUALITY_G3_7B.report.md);
- [current role-labeling contract](../../stage2/contracts/BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md).
