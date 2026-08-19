# Broker Reports Gate 5 G5.38C — Deterministic Row-bound Role Context

Date: 2026-08-11

Status: `STRATEGIC_STOP`

Terminal: `STRATEGIC_STOP`

## Outcome

Gate 3 now constructs role input only from the current validated semantic
fact's exact canonical row/region closure. Canonical table-row/table-cell
targets retain the exact row, same-row cells and context-only headers. Node or
list targets retain only the exact accepted region. Unrelated chunk targets
are excluded, cross-row aliases are rejected, and role provenance contains
literal hashes and exact canonical targets without source values.

The public PDF cannot complete G5.38C honestly. Its accepted semantic targets
are page-level canonical `node` regions, not canonical table rows. The current
semantic visual table projections contain useful rows, but they do not contain
a deterministic binding from an accepted semantic annotation to one exact
projection row. A page match is not such a binding.

## Row-context contract

Sole owner:
`Gate3RoleContextFactory.create_from_accepted_facts`.

The deterministic closure is:

```text
accepted canonical table row/cell
-> same canonical node + row
-> same-row cells
-> necessary header/title text without role targets

accepted canonical node/list item
-> that exact accepted canonical region only
```

The role model may bind only aliases in the per-fact closure. Backend
validation restores exact canonical targets and verifies exact source
literals. It does not normalize, compute, guess, retry, merge or repair.

The final implementation does not pass same-page visual table projections to
the role stage. Expanding a coarse page node to all projected rows would ask
the role model to rediscover which row is the financial event, which the
contract forbids.

## Clean inference evidence

Official/public source SHA-256:
`25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67`.

Both experiments used new temporary users, a new case and a new audit ID. No
prior private fact, target ID or annotation was reused. Each experiment had
one semantic pass and one role pass. Provider retry/merge/repair/best-of-N was
zero. Both stopped before controlled disposal.

### Experiment 001 — accepted-region closure

- semantic status: `validated`;
- accepted facts: 4 over 2 accepted targets;
- unrelated targets excluded: 2;
- source chunk: 8,036 chars;
- role context: 5,467 chars;
- `t001` purchase: required `quantity` and `amount` missing;
- `t001` charge: required `amount` missing;
- `t002` purchase: required `quantity` missing;
- `t002` charge: required roles complete;
- purchase-only XML: not created.

This clean inference established the exact remaining blocker: the canonical
accepted page region does not expose an accepted row identity.

### Experiment 002 — diagnostic same-page projection exposure

A separate clean diagnostic exposed 4 current validated projections, 16 rows
and 274 cells inside the two accepted page regions. It reduced the prompt to
5,228 chars and produced superficially complete required roles for the `t002`
purchase and charge.

The private hash-only provenance rejected that as row-bound proof:

| Fact | Required-role result | Row provenance |
| --- | --- | --- |
| `t001` purchase | incomplete | multiple candidate rows |
| `t001` charge | incomplete | multiple candidate rows |
| `t002` purchase | complete by literals | no single structural row |
| `t002` charge | complete by literals | no single structural row |

Representative `t002` literal hashes demonstrate the split without exposing
values:

| Fact / role | Literal SHA-256 | Matching rows |
| --- | --- | ---: |
| purchase / date | `369b02db8bb39f5803504e00582ae0dd4cc4fe45082a6d1c30e528a7b700c97e` | 2 |
| purchase / quantity | `7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451` | 1 |
| purchase / amount | `129d701946de48349a0d24021ebc45b7ece8ca1761183e3306917fae5faeb3d9` | 1 |
| charge / amount | `e35141ecfad55057e41df43e44f6234250fd3ae4942faeba433223a7a8388613` | 1 |
| purchase and charge / currency | `60dc1e3084d82b9597446ce0ef957b38dd037a4a7918f4056ebf5de67ae934ac` | 2 |

For the purchase, date/amount and asset/quantity were taken from different
tables/rows; their row intersection was empty. The charge also had no common
row for all required role literals. The diagnostic bundle was therefore not
accepted as the product result. The final bundle removes this projection
plumbing and preserves the exact region boundary.

## Relation and full-product result

Not run for the fresh public-PDF case. Gate 4, the existing purchase-charge
relation owner, the controlled synthetic disposal, Tax Model, declaration,
XML projection and XSD validation are downstream of a valid row-bound role
fact. Continuing with the cross-row diagnostic output would turn invalid
evidence into a false economic-coverage proof.

The controlled disposal fixture remains explicitly synthetic and was not
used to supplement or repair the public source.

## Regression and integrity evidence

Final bundle SHA-256:
`7718c36492f2d8ebe5306af4e896336cb4143c5c062def0b5081c8f6836d7305`.

Final targeted run: `76 passed`.

Coverage included:

- Gate 3 role-context and exact-literal validation;
- chunk batching and the real NDFL product pipe;
- architecture/factory anti-drift and bundle parity;
- existing related-securities-event relation;
- G5.36 CSV baseline;
- G5.37 HTML/XLSX coverage expansion;
- existing end-to-end supplied-case full-target XML proof.

An additional isolated full-target projection run had 7 known fixture setup
errors, all `gate4_cache_missing`; no XML/XSD assertion failed. The integrated
end-to-end file passed in the final 76-test run. This unrelated cache-order
issue was not changed under G5.38C.

Live cleanup completed with `state_restored=true`: the previous bundle,
valves and access grants were restored and both proof users were removed.

## Anti-drift audit

- no T-Bank adapter or broker-specific vocabulary rule;
- no page-number business rule;
- no historical target/fact reuse;
- no store scan or cross-run structural lookup;
- no retry, repair, merge or best-of-N;
- no manual supplemental financial fact;
- canonical artifact remains immutable;
- one context owner and the existing role/value validators remain in force.

KISS: the implementation adds one deterministic context factory and a private
hash-only provenance receipt to the existing Gate 3 role path. It does not add
a parallel reader, schema authority, relation owner, tax model or broker
template.

## Exact strategic blocker

The current PDF canonical artifact represents each accepted page as one text
node. Semantic labeling therefore accepts a page region, while the usable
purchase/charge values exist across multiple visual table rows. Current
artifacts have no authorized deterministic identity connecting that accepted
semantic annotation to one exact row.

Closing this requires an upstream document/canonical boundary that exposes
visual table rows as exact canonical row/region targets before semantic
labeling, or an equivalently authorized deterministic accepted-row binding.
Selecting a row downstream would require renewed LLM discovery or
broker-specific logic.

Therefore the requested chain

```text
REAL PUBLIC PDF
-> ACCEPTED SEMANTIC ROW
-> ROW-BOUND ROLE CONTEXT
-> ROLE-COMPLETE FINANCIAL FACTS
-> EXISTING TAX PIPELINE
-> VALID XML
```

is not proven in G5.38C.

Final terminal:

```text
STRATEGIC_STOP
```

Scope stops here. G5.39 or a new document-architecture goal is not started.
