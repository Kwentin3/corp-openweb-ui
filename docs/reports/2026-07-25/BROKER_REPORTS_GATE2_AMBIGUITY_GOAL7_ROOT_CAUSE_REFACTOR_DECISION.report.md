# Broker Reports — Gate 2 ambiguity discipline, Goal 7

Дата: 2026-07-25

Статус: `IMPLEMENTATION_ROAD: APPROVED`

## Decision

Root cause не принадлежит одному layer.

Unsafe result возникает по цепочке:

1. deterministic scope сохраняет literals, но теряет bounded
   row/header/value associations;
2. `allowed_type_ids` остаётся `None`;
3. eligibility использует только broad source family;
4. Registry semantic preconditions не имеют machine admission predicates;
5. provider schema делает typed branches representable по value-type roles;
6. prompt v2 пытается компенсировать отсутствующий code guard;
7. exact model выбирает первый structurally valid cash branch;
8. validator/materializer корректно принимают решение, разрешённое contract.

Benchmark правильно обнаружил два unsafe typed outcomes, но v1 не pin-ит
typed-admission identity и имеет один adjacent under-grounded typed fixture.

## Layer contribution

| Layer | Contribution | Decision |
|---|---|---|
| Deterministic scope | Drops association context; does not narrow IDs | Primary refactor owner |
| Model input context | Flat values insufficient for multiple hypotheses | Versioned enrichment |
| Eligibility | Broad source family only | Primary safety defect |
| Registry | Definitions correct; machine admission metadata absent | Keep v1; separate policy |
| Prompt v2 | Exact-pair shift toward typed; prose/schema conflict | Replace only after guard |
| Provider schema | Unsafe typed branches structurally present and first | Generate from admitted IDs |
| Exact model | Over-types, ignores optional disconfirming label | Requalify after refactor |
| Benchmark/comparator | Two expectations correct; admission checks absent | Benchmark v2 |

## Ownership map

### Gate 1

Owns neutral source evidence:

- literals;
- visible labels/headers;
- row/section role;
- source-value association;
- lineage.

Gate 1 не назначает Financial Evidence type.

### Typed-admission policy

Owns:

- positive discriminator predicates keyed existing Registry type IDs;
- ambiguity/conflict detection;
- unique association requirement;
- admitted type IDs;
- value-free admission receipt.

Default: not admitted.

### Deterministic scope

Owns:

- bounded source grouping;
- admission policy invocation;
- `allowed_type_ids`;
- admission identity/hash in scope v2;
- package-specific decision schema boundary.

### Model

Выбирает terminal disposition/type/roles только внутри schema, уже
ограниченной code-owned admission.

### Validator/materializer

Validator rechecks admitted IDs/refs/roles and admission identity.
Materializer remains deterministic and unchanged.

## Approved minimal refactoring set

### Goal 8 — typed-admission core

New versioned contracts:

- `broker_reports_gate2_financial_typed_admission_v1`;
- deterministic financial scope/package v2;
- explicit v1/v2 read boundary where needed.

Implementation:

- `Gate2FinancialEvidenceTypedAdmissionFactory`;
- consume authoritative Gate 1 structure already available to scope factory;
- conservative type-specific predicates;
- positive evidence + unique association required;
- conflicts/multiple types/missing discriminator → no admitted types;
- pass admitted IDs via existing
  `FinancialEvidenceDecisionPackage.allowed_type_ids`;
- no typed branch when admitted IDs empty;
- validator verifies scope admission receipt and eligible IDs;
- no model call.

Initial safe positive evidence:

- cash: authoritative cash/position discriminator, reporting date/scope and
  unique associated amount;
- printed metric: authoritative total/subtotal/summary discriminator,
  reporting scope/date-or-period and unique associated amount.

Unknown labels, generic amount/date shape and conflicting hypotheses fail
closed to unclassified.

### Goal 9A — bounded source context v2

Separate PR:

- successor model-input schema v2;
- nested package-owned source groups;
- per-value visible label/column meaning;
- authoritative row/section role when available;
- no document paths/graphs/audit/system IDs;
- no expected answer;
- strict input limits and privacy tests.

Context improves semantic matching but не решает admission safety.

### Goal 9B — prompt/provider projection v3

Separate PR:

- concise prompt v3;
- no fixture-specific rules;
- explicit unclassified normal outcome;
- no claim that prompt enforces admission;
- exact prompt/schema/provider identity;
- typed variants only for policy-admitted IDs.

Registry v1 definitions may be projected as concise guidance, but
counterexamples are not safety authority and must fit existing token budget.

### Goal 10 — successor benchmark v2

New frozen manifest and exact identity:

- positive typed discriminator cases;
- multiple compatible types;
- no Registry match;
- missing/sufficient discriminator;
- structural total/detail and adjacent associations;
- over-typing negative tests;
- admission receipt/schema assertions;
- local Q0/Q1 provider calls 0.

`missing_optional` must either receive positive cash evidence or become
unclassified.

### Goal 11 — exact model requalification

Only after Goals 8–10 merged:

- primary remains `gpt-5.4-nano-2026-03-17`;
- one exact attempt;
- no fallback/repair/expensive model;
- failure terminal for that revision.

Model replacement is not part of current refactor.

## Contract and migration impact

Changed in implementation:

- new typed-admission policy/receipt;
- deterministic scope v2;
- successor model input v2;
- prompt v3;
- benchmark v2;
- successor artifact identity/version where scope-v2 reference requires it.

Explicitly unchanged:

- Gate 1 contracts;
- Registry v1/type meanings;
- Financial Evidence decision v1/four dispositions;
- deterministic materializer;
- financial context v1;
- comparator principles;
- legacy immutable artifacts;
- Gate 2 checksum boundary;
- source/domain model authority remains zero.

Migration:

- persisted v1 artifacts immutable/readable;
- no rewrite/upcast;
- new qualification receipts never inherit v1/v2 prompt receipts;
- production admission remains false until Goal 14.

## Rejected alternatives

- prompt-only correction;
- typed → unclassified post-response conversion;
- validator weakening;
- default type;
- new Registry type for fixture;
- semantic drift under Registry v1/type IDs;
- expected-answer/admission flag in model input;
- broad single-type filter without positive evidence;
- exact-model replacement before structural refactor;
- expensive model;
- source/domain LLM authority;
- exact internal graph as primary quality metric;
- comparator expectation relaxation.

## Tests and acceptance plan

Required Goal 8 observable tests:

- positive cash admission;
- positive printed-metric admission;
- multiple hypotheses → typed schema absent;
- missing discriminator → typed schema absent;
- conflicting positive evidence → typed schema absent;
- admission receipt/hash tamper rejected;
- typed output rejected when ID not admitted;
- no post-response conversion;
- v1 artifacts remain readable;
- factory/anti-drift anchors.

Research PR validation:

- audit harness direct: `7 passed in 5.61s`;
- focused successor/admission surfaces:
  `82 passed in 12.35s`;
- full Broker Reports suite:
  `1464 passed, 20 skipped, 5 warnings in 104.03s`;
- Ruff: passed;
- new provider/customer calls: 0;
- stage mutations: 0.

## Repository boundary

- base:
  `ebf6d94d1c66bbe34a2790c192aa166d3b24f36c`;
- branch:
  `codex/broker-reports-gate2-ambiguity-research-goals0-7`;
- PR:
  `https://github.com/Kwentin3/corp-openweb-ui/pull/133`;
- production/runtime contracts changed: 0;
- research harness/tests/reports only.

## Acceptance

- `ROOT_CAUSE: LOCALIZED`
- `REFACTORING_SET: MINIMAL_AND_EVIDENCE_DRIVEN`
- `REJECTED_ALTERNATIVES: EXPLICIT`
- `IMPLEMENTATION_ROAD: APPROVED`

Следующий разрешённый шаг только после merge PR #133:
Goal 8 branch от нового `origin/main`.
