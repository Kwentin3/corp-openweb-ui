# G5.57 — Visual Qualification Loop for Source-Truth Role Mapping

Date: 2026-08-15

Status: `COMPLETE`

## Result

The exact five purchase rows now have one source-qualified role mapping through
the ordinary Gate 3 Role Pack path. G5.55 non-destructive recovery preserves
the five purchases and all 16 unrelated facts; Gate 4 and Gate 5 consume the
recovered current view without role repair, deduplication, or inferred
relations.

Visual inspection remained qualification-only. Runtime uses Canonical
structure, Adaptive Context, the published Role Pack, existing Gate 3
factories, immutable persistence, Gate 4, and Gate 5.

## Visual source qualification

The real source page was inspected repeatedly. It contains five executed
purchase rows, and Canonical contains the corresponding five rows without a
column shift. Financial values were not used to choose column meaning.

| Source column | Source header meaning | Qualified role |
| ---: | --- | --- |
| 4 | transaction date | `date` |
| 9 | shortened asset name | not the current identifier role |
| 10 | asset code | `asset` |
| 11 | unit price | `unit_price` |
| 12 | price currency | not settlement amount currency |
| 13 | quantity | `quantity` |
| 14 | amount excluding accrued coupon component | not deal amount |
| 15 | accrued coupon component | separate source component |
| 16 | deal amount | `amount` |
| 17 | settlement currency | `currency` |

The old mapping was correct for the disputed fields:

```text
amount:   old 16, G5.54 new 14
currency: old 17, G5.54 new 12
verdict:  NEW_MAPPING_WRONG
```

All five rows share the final mapping:

```text
date=4, asset=10, quantity=13, unit_price=11, amount=16, currency=17
```

## First wrong owners

### Amount and currency

Gate 2 retained source row 1 with its column labels, while correctly making no
semantic-header claim. `Gate3RoleContextFactory` discarded that row because it
previously retained only generated `header` lines. It was the first wrong
owner.

The minimal correction permits source row 1 from the same accepted table to be
copied as context-only text with aliases removed. It is not classified as a
header and none of its targets becomes selectable.

### Asset

With header context restored, clean runs alternated between the shortened asset
name and asset code. The source visibly contains both, while Role Pack `2.0.0`
defined only a generic `asset`. This was `ROLE_CONTRACT_TOO_COARSE`, owned by
the existing Role Pack.

Published Role Pack `3.0.0` narrows `asset` to a source-authored code or other
unambiguous identifier. Versions `1.0.0` and `2.0.0` remain immutable and
hash-pinned. No broker name, language-specific header, column number, or source
value entered production code.

## Same-fact authority replay

A full type rediscovery was rejected because it proposed one additional
unrelated commission. The final path does not weaken recovery or delete that
proposal manually.

Instead, the immutable current `2.0.0` sidecar supplies only its accepted
`(canonical target, financial label)` set. Old role bindings are discarded.
The existing `Gate3RoleLabelingFactory.create_from_chunk` replays Role Pass for
all 21 accepted facts under Role Pack `3.0.0`, repeating chunk, alias, target
closure, Role Pack, literal, and Canonical validation. The result is persisted
as one immutable FULL current baseline through the existing persistence owner.

This is a bounded replay through existing owners, not a new migration runtime:

```text
21 immutable accepted facts
-> 0 type-discovery calls
-> 1 ordinary Role Pass call
-> same 21 targets and labels under Role Pack 3.0.0
-> immutable FULL baseline
```

## Clean demand recovery replay

The same private copied store then ran the ordinary demand route:

```text
5 requested purchases
-> Gate3ChunkBatchLabelingFactory
-> type pass + role pass
-> G5.55 save_recovery against the same-authority FULL baseline
```

The clean run used three provider calls in two distinct batches and no retry,
best-of-N, correction pass, or semantic repair.

Recovery receipt:

```text
annotations before:       21
annotations after:        21
purchases after:           5
unrelated after:          16
added:                     0
superseded:                5
preserved unrelated:      16
deleted:                   0
```

The original source store remained byte-unchanged. Both G5.56 lineage records
remain present in the private copied store; the corrected FULL baseline and
recovery sidecar are additive immutable records.

## Gate 4 and Gate 5

- Gate 4 rebuilt 21 document facts and returned
  `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`. It exposes exactly five purchase facts;
  each has six source-backed role values at columns `4/10/13/11/16/17` and
  semantic Role Pack `3.0.0`.
- Gate 5 consumed 48 security source facts and returned
  `SOURCE_FACT_ASSERTIONS_PRESERVED`.
- Stored financial-event relations: `0`.
- Gate 5 contains no role selection, deduplication, or source repair.

## Verification

- Focused Gate 3, persistence, Gate 4, Gate 5, architecture, cross-gate,
  live-script anti-drift, and bundled-pipe suite: `136 passed`.
- The new boundary tests assert exact accepted-fact reconstruction, no copied
  roles, foreign-target fail-closed behavior, zero baseline type calls, and the
  canonical factory route.
- Three OpenWebUI bundles were rebuilt twice with byte-identical SHA-256.
- `git diff --check`: passed; only pre-existing line-ending warnings remain.
- Privacy scan: passed. No customer literals, source image, values, or private
  evidence paths are stored in the report or receipt.

## Finish-contract terminals

```text
SOURCE_TABLE_ROLE_MAPPING_VISUALLY_QUALIFIED
AMOUNT_ROLE_BINDING_PROVEN
CURRENCY_ROLE_BINDING_PROVEN
ROLE_MAPPING_OWNER_DEFECT_REPAIRED
FIVE_PURCHASE_SOURCE_ASSERTIONS_STABLE
NON_DESTRUCTIVE_RECOVERY_AFTER_ROLE_FIX_PROVEN
```

## KISS and scope stop

The solution reuses existing Gate 3 context, Role Pack, Role Pass, batch,
persistence, Gate 4, Gate 5, and bundle owners. It adds no parser,
table-understanding engine, identity graph, role inference graph, dedup logic,
generic migration framework, or visual runtime dependency.

No commit, push, PR, or product activation was performed. G5.57 stops here.
