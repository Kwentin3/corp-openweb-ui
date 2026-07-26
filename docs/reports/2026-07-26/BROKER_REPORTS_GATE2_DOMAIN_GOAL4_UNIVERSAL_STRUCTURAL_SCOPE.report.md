# Broker Reports Gate 2 Domain — GOAL 4 Universal Structural Scope

Date: 2026-07-26.

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Base revision: `b62b6a8c2cb3daef2c2e0e30cf9c0c72177d86f2`.

Branch:
`codex/broker-reports-gate2-domain-goal4-universal-structural-scope`

## 1. Objective

Remove financial-language and type-specific admission predicates from the
successor target path. Deterministic code now filters types only by generic
structural conditions. Financial semantic selection belongs to the bounded
LLM decision.

## 2. Contract change

New target contract:
[`BROKER_REPORTS_GATE2_UNIVERSAL_STRUCTURAL_SCOPE.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_UNIVERSAL_STRUCTURAL_SCOPE.v1.md).

Versioned nested structural-filter identities:

```text
schema=broker_reports_gate2_financial_typed_admission_v2
policy=gate2_financial_generic_structural_filter_v1
filter_kind=generic_structural
semantic_selection_owner=llm
```

The enclosing deterministic scope remains v2. Historical Python and payload
names containing `typed_admission` remain compatibility surfaces; schema v2
defines `admitted_type_ids` as structurally eligible pass-through types, not
as a Python semantic classification.

## 3. Removed type-specific semantics

The maintained structural-filter source and generated OpenWebUI domain bundle
contain zero:

- cash signal regexes;
- printed-total signal regexes;
- printed/summary/subtotal row-role sets;
- cash-type admission branches;
- printed-metric admission branches;
- conflicting-positive-discriminator branches;
- type-specific positive-discriminator reason codes.

The structural-filter module contains neither
`cash_balance_snapshot_v1` nor `printed_financial_metric_v1`. Concrete type IDs
remain only in their versioned Registry/Semantic Pack authority, decision
schemas, fixtures, and expected semantic outputs.

## 4. Generic structural filter

For every active Registry declaration compatible with the bounded source
family, one common loop checks:

1. source-family membership and lifecycle;
2. required-role feasibility by Registry role/value type;
3. source-value/candidate identity parity;
4. ordinary source-value membership in the bounded Gate 1 package;
5. deterministic source-reference membership in allowed evidence;
6. surrounding Registry, source-package, decision, coverage, and integrity
   validation.

A required role is feasible when at least one package candidate has the
Registry role's value type and is allowed for that role. Multiple candidates
remain feasible and are left for the model. No uniqueness, label, heading,
literal meaning, row role, or expected answer selects a type.

All structurally eligible types are supplied to the strict decision contract.
The current synthetic structural scopes expose both active compatible types in
10 of 12 cases. The two technical terminal scopes have no feasible typed
branch. Semantic benchmark decisions remain four-disposition outcomes and do
not control structural availability.

## 5. Semantic invariance proof

The same bounded structure was tested with these visible text variants:

```text
Cash
Printed total
Cash total
Semantically unrelated heading
```

Every variant produced the same structurally eligible type set:

```text
cash_balance_snapshot_v1
printed_financial_metric_v1
```

Removing the generic `amount` role from otherwise package-valid candidates
excluded both declarations through one required-role-feasibility rule. No
type-specific branch was involved.

## 6. Bundle parity

The maintained source was projected into:

`services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate2_domain_source_fact_pipe_bundled.py`

The official builder was run twice with `--target gate2-domain`. The second
build was byte-identical:

```text
bundle_sha256=c4756ff1c99023499306dd9847c65b51593c6d7fbbd905e5f1fd46a0f0dfaf1f
bundle_rebuild=exact
type_specific_target_markers=0
```

No live OpenWebUI Function/Tool was installed or updated.

## 7. Honest qualification and budget boundary

The expanded strict schema invalidates earlier exact model qualification
identities because the structural-filter source hash and provider schema
changed. No earlier success/failure receipt is presented as current authority.

The existing financial-evidence economy cap is 3,072 estimated input tokens.
The new two-type dry build estimates 3,285 tokens and therefore fails closed
with:

`gate2_economy_input_token_budget_exceeded`.

The blocker authorizes zero provider calls. No model was called or requalified.
The cap was not widened in GOAL 4 because GOAL 5 will add the full Semantic
Pack and must establish the complete bounded input before setting an honest
budget. This is a non-blocking limitation for structural-scope acceptance and
a required GOAL 5 input-contract concern.

The prior terminal Haiku qualification blocker remains historical evidence.
The exact old candidate/contract was not rerun.

## 8. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- structural/successor/bundle/privacy focused tests:
  `95 passed in 10.33s`;
- budget-boundary focused tests: `19 passed in 6.47s`;
- final full Broker Reports suite:
  `1548 passed, 20 skipped, 5 warnings in 125.49s`;
- generated bundle rebuild: exact;
- target predicate-marker scan: zero;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- repository privacy guard: passed;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

The five warnings are unchanged third-party SWIG deprecations.

## 9. Explicit unchanged boundaries

This GOAL does not:

- assemble the GOAL 5 full Semantic Pack model input;
- change the Semantic Pack, managed Skill, or managed Prompt;
- change validator/materializer semantic independence owned by GOAL 6;
- change persistence, domain query APIs, or Gate 3 tooling;
- change model qualification admission or production routes;
- perform a provider/customer call;
- write customer/private values, raw provider output, secrets, or local paths
  to Git.

## 10. Acceptance markers

```text
TYPE_SPECIFIC_FINANCIAL_REGEX=ZERO_IN_TARGET
TYPE_SPECIFIC_ADMISSION_BRANCHES=ZERO_IN_TARGET
STRUCTURAL_FILTER=GENERIC
SEMANTIC_SELECTION=LLM_OWNED
```

Authoring status:
`IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Next permitted goal:
`GOAL_5_AFTER_GOAL_4_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.

## 11. Safe receipt

Repository-safe receipt:
[`BROKER_REPORTS_GATE2_DOMAIN_GOAL4_UNIVERSAL_STRUCTURAL_SCOPE.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL4_UNIVERSAL_STRUCTURAL_SCOPE.receipt.safe.json)

Its exact Git-blob SHA-256 is recorded here after committed-object
finalization:

`f71c438af388386c5d6642f961fa8fe7bcfe7d44e31d51833a0b2dfd4eb20d43`
