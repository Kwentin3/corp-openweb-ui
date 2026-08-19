# G5.39R Source-authored Financial Event Relation Research — preregistration

Status: `FROZEN_BEFORE_HYPOTHESIS_IMPLEMENTATION_AND_SOURCE_VALUE_INSPECTION`
Date: `2026-08-12`
Mode: research only; no production implementation or G5.40 authorization.

## Research question

Can source structure provide a small, deterministic, source-verifiable witness
that proves that multiple structural elements belong to one source-side
financial event before LLM role binding, without broker templates, semantic
search, whole-document model context, or a generic graph?

The null result is allowed:

```text
NO_RELATION_STRATEGY_PROVEN
```

## Frozen baseline

- Product repository entry `HEAD`: `02659a9b0bdfb2f19171d2a070a660af85119d59`.
- Product repository entry `HEAD` tree: `0a696522eb37eca13bb9224a41f7227823c8ce8c`.
- The product tree was already dirty on entry and remains outside the
  experiment repository.
- G5.39 common research commit:
  `1fb05ed3e725ff27701d97b1136dcb7ca01aee7d`.
- G5.39 common research tree:
  `8370cebde17bcf6f0c39ea10b2f03c2cf4512ae5`.
- G5.39 terminal report SHA-256:
  `e89885ec9e6b7bc6796c59e5e6d8b0f619c7d7a61ed19b9b53674cc7921f44f1`.
- G5.39 safe ledger SHA-256:
  `f811a9831b7cec0790ad8a381cd78bebc363e9d41d89b03e834407388198d10d`.
- G5.39 safe receipt SHA-256:
  `24c12997ee04ed5321f7a36dcde325966d17606bcfab44c0c9edc2e2c292baf0`.
- G5.39 v3 preregistration SHA-256:
  `c25e7d3ab7c0af369356916abf0ae9144b2d6de62b0b4692ed9ca276c959bd99`.

The G5.39R experiment implementation will live in a new ignored nested Git
repository under `local/`. Its common baseline commit/tree will be recorded in
the safe ledger before the R1–R4 branches execute. Each branch must start at
that one commit. Private corpus, oracle, proposals, and exact adjudication stay
outside both product Git and experiment Git.

## Frozen corpus

The corpus is byte-identical G5.39 corpus v3. It must not be filtered or
changed after any hypothesis output is observed.

- Safe corpus manifest SHA-256:
  `dc9619eb446c01c82cbce538e01c70be7c170c25da95c4ef230efce217d61c2d`.
- Private reviewed corpus/oracle SHA-256:
  `d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85`.
- Assignments: `DEV_PUBLIC_TBANK`, `HOLDOUT_REAL_001`,
  `LARGE_REAL_001`, `NEGATIVE_AB_001`, plus existing CSV/HTML/XLSX
  regressions.
- G5.39 v1 remains invalidated before inference.
- G5.39 v2 H1 remains invalidated before comparison.

If the frozen v3 corpus is materially defective, this tournament is
invalidated, a new corpus version is required, and all affected strategies are
restarted. Silent correction is forbidden.

## Runtime/oracle separation

The strategy process receives only:

```text
sample_id
source_sha256
anchor structural ref
source tables/rows/cells
source-authored explicit relations
source-authored structural metadata
```

It must not receive:

```text
expected
event_group
required_evidence_refs
forbidden_mixed_refs
target financial type
target role profile
oracle-derived candidate filtering
```

The corpus preparation step writes a separate oracle-free runtime file and a
private evaluator file. Strategy execution reads only the runtime file.
Adjudication happens only after the proposal bytes are frozen and hashed.

## Minimal candidate witness

Every strategy returns either `UNRESOLVED` or exactly one proposal with:

```text
witness_id
relation_kind
anchor_ref
member_refs
source_constraints
verification_status
```

The witness contains no financial type, role value, tax meaning, broker rule,
LLM prose, or XML meaning. Member refs must exist in the source-derived
runtime structure.

## Frozen hypotheses

### R1 — explicit source relation / typed identity

R1 may use only an explicit source-authored relation edge or a structurally
typed identity attribute already present in the runtime source. Raw literal
equality and header-name inference cannot mint an identity. Starting from the
anchor, R1 computes a deterministic closed component. Ambiguous or absent
identity returns `UNRESOLVED`.

### R2 — source structural container

R2 may use the smallest source-authored event-granular container. In this
corpus a row and its cells are eligible; page and ordinary table membership
are not event-granular proof. A larger container is eligible only if the
source structure explicitly identifies a nested group/parent/container, not
because elements are visually close. If the eligible container does not
cover the required event relation, R2 returns `UNRESOLVED`.

### R3 — exact deterministic identity constraints

R3 may use exact source attributes classified by a frozen broker-neutral
header vocabulary into these kinds:

```text
explicit event identity
instrument identity
exact quantity
exact operation date/time
exact source-side reference
unit price
gross/net/fee amount
```

An explicit event identity may relate rows only when it is unique at the
candidate-event boundary. Without it, relation requires the exact composite
`instrument identity + quantity + operation date/time + source-side
reference`. Missing or non-unique components return `UNRESOLVED`. Numeric or
literal equality alone never creates membership. Decimal arithmetic may only
validate an already selected candidate.

The exact vocabulary and normalization rules are committed on the common
experiment baseline before any strategy result is run. They may not change
per source or after adjudication.

### R4 — hybrid minimal witness

R4 requires at least two independent source-authored constraint families:

```text
explicit relation or typed identity
+ event-granular structural container
```

or:

```text
exact composite identity constraints
+ exact Decimal consistency
```

The second family can validate or narrow membership but cannot replace a
missing identity by proximity, page, table, or literal equality. Any
non-unique candidate set returns `UNRESOLVED`.

R5 is forbidden unless R1–R4 evidence reveals a mechanism not expressible by
these four definitions. It cannot be added merely to improve coverage.

## Deterministic relation evaluation

One expected target event is evaluated per assigned case. A proposal is:

- `CORRECT` when all required oracle refs are covered, every member belongs to
  that event, every source constraint validates, and no foreign event ref is
  included;
- `INCOMPLETE` when it covers only a strict subset without a foreign ref;
- `FALSE_RELATION` when any member belongs to another oracle event;
- `AMBIGUOUS` when the strategy reports multiple indistinguishable candidates;
- `UNRESOLVED` when it safely declines.

The controlled A/B fixture is also checked against its complete frozen
forbidden mixed pattern. A witness containing A and B event members is a hard
failure. Silent first-match is forbidden.

Primary metrics:

```text
events expected
correct witnesses
false relations
cross-event joins
ambiguous
unresolved
precision
recall
```

Secondary metrics:

```text
refs examined
source chars examined
largest witness refs/chars
runtime operations
index/lookups
```

Complexity diagnostics are `LOC`, new concepts, schemas, indexes, and
persistence. Persistence is fixed at zero.

## Hard failures

A strategy is rejected if it:

1. relates refs from different oracle events;
2. uses a broker/source name, page rule, or layout template;
3. treats page/table/proximity as sufficient proof;
4. treats literal or arithmetic equality as sufficient proof;
5. relies on an LLM assertion for relation authority;
6. invents a structural ref;
7. silently chooses the first ambiguous match;
8. needs whole-document model context;
9. uses prior-case evidence;
10. needs retry, repair, best-of-N, consensus, or answer merge;
11. reads any oracle-only field during proposal construction;
12. adds persistent relation storage or a generic graph.

## Winner rule

Order is lexicographic:

1. zero false relations;
2. independent real holdout generalization;
3. large-document bounded behavior;
4. relation coverage;
5. role usability;
6. cost;
7. KISS.

A production candidate requires:

```text
DEV relation PASS
real holdout relation PASS
large real PASS or honest bounded UNRESOLVED
A/B cross-event joins = 0
broker-specific logic = 0
practical advantage over the G5.39 H1 fail-closed baseline
```

An explicit-when-present partial candidate is allowed only if it has useful
real-document coverage, zero false relations, and an exact fail-closed domain.
Synthetic-only coverage cannot select a partial winner.

## Role and downstream pressure

No LLM participates in relation correctness. Only a relation finalist that
passes the required relation boundary may receive one bounded role-labeling
pass through the existing Gate 3 factory/provider route. The finalist profile
is production-equivalent, frozen across finalists, and has retry/repair/
best-of-N/merge all zero.

If no relation finalist exists, provider calls and downstream finalist
execution are `0`, recorded as `NOT_RUN_NO_RELATION_FINALIST`. Existing
CSV/HTML/XLSX and related-securities regression tests still run read-only
against the unchanged product tree.

## Production freeze and stop

No experiment may edit CanonicalArtifact, Gate 3/Gate 4 production owners,
Tax Models, related-securities semantics, Declaration Definition, supplied-case
completeness, Resolved Package, Declaration Semantic Input, projection, or XML.

Allowed terminal outcomes:

```text
SOURCE_RELATION_STRATEGY_SELECTED
EXPLICIT_RELATION_WHEN_PRESENT_PROVEN
NO_RELATION_STRATEGY_PROVEN
UPSTREAM_STRUCTURE_RELATION_LOSS
```

Even a winner remains isolated experimental code. G5.40 is not started or
authorized by this research execution; it is only the next separately
authorizable goal if the final evidence selects a production candidate.
