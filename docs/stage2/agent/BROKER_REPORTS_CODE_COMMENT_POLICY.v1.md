# Broker Reports Code Comment Policy v1

Status: normative comment policy  
Effective date: 2026-07-31

## Allowed comments

### Boundary comment

Place one short boundary block near the beginning of a key owner module:

```text
Domain:
Input contract:
Output contract:
Owns:
Does not own:
Allowed consumers:
Runtime status:
Related ADR:
Contract tests:
```

The block must name a stable contract, symbol, or test module. It must explain
a real boundary that is not obvious from a function name. It must not change
executable behavior.

### Invariant comment

Place an invariant comment next to non-obvious logic only when it says:

- which error or authority bypass is prevented;
- which contract fixes the rule;
- which executable test protects it.

### Historical containment comment

Place one containment block near the beginning of a historical route:

```text
Why retained:
Why product reachability is forbidden:
Allowed consumers:
ADR required to change status:
```

The block must agree with current imports and guards. A historical route can
be retained for replay, migration, audit, or pinned compatibility; those uses
do not authorize product execution.

## Forbidden comments

- restating a function or class name;
- narrating obvious code;
- embedding long architecture documentation in Python;
- copying a contract field list;
- claiming active status without checking imports, guards, and consumers;
- text that must change whenever a financial type is added;
- temporary agent reasoning;
- a GOAL number without a stable ADR or contract reference;
- a comment used in place of an executable architecture test.

## Placement for KT1

Boundary comments are required only in these maintained owners:

- semantic visual transcription contract/validator boundary;
- deterministic semantic logical-table materialization;
- Gate 2 table package;
- current source-fact product orchestration;
- canonical financial validator/materializer;
- financial evidence/replay;
- AnswerContext selection;
- read-only release/live parity verifier.

A historical containment comment is required in
`gate2_source_fact_selection.py`.

GOAL 17 Type-First candidate comments are not added because its implementation
is not on `main`. Generated bundles, fixtures, reports, and OpenWebUI core are
not comment targets. KT1 must not comment the repository broadly.

## Verification

`test_broker_reports_kt1_architecture_stabilization.py` checks:

- selected modules contain a complete marker block;
- the historical selection module contains its containment block;
- comments agree with import/guard reachability;
- no KT1 owner module was added.

Comments explain ownership; contract tests enforce it.
