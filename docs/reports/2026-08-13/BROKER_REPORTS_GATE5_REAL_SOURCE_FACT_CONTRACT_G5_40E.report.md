# Broker Reports Gate 5 Real Source-Fact Contract — G5.40E

Date: 2026-08-13

## Result

```text
REAL_SOURCE_CONTRACT_PARTIALLY_PROVEN
UPSTREAM_SOURCE_FACT_LOSS_ELIMINATED
SOURCE_CONTEXT_PRESERVED
NO_UNSUPPORTED_SEMANTIC_INFERENCE
```

The bounded four-document corpus now reaches Gate 4 without known
source-present target loss: 2,906/2,906 canonical targets are covered in eight
full-document chunks, 186 frozen annotations become 186 Gate 4 facts, and the
case is `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`.

The primary terminal is partial because the sources do not jointly provide a
complete tax-input set. The gaps are explicit: no disposal in the TBank
development document, insufficient prior acquisition quantity in the bounded
Holdout source scope, mixed incomplete role authority/no safe direct-charge row
in the Large document, and partial dates plus symbol-only currency authority in
the Fidelity statement. None is filled by proximity, allocation, currency
mapping, a broker default, or a provider follow-up.

This is technical source-fact closure for the bounded corpus. It is not taxpayer
tax completeness, declaration activation, or a filing claim.

## Frozen replay

- Exact model: `models/gemini-3.5-flash` through the existing authenticated
  OpenWebUI completion boundary.
- Policy: one sequential full-document replay, no best-of-N, retry, repair,
  fallback, post-edit, or provider rerun.
- Provider submissions: 15; frozen maximum: 16.
- Documents complete: 4/4; chunks validated: 8/8; rejected/provider-failed: 0.
- Frozen plan SHA-256:
  `926e19265ff5b3a3e6107a57c8a86970c60223da8a4aae2c1123138abcc7cf6c`.
- Private provider payloads, literals, targets, and full facts remain outside
  Git. Only counts, statuses, sample IDs, and hashes are published.

## Real-document matrix

The machine-readable matrix is
`BROKER_REPORTS_GATE5_REAL_SOURCE_FACT_CONTRACT_G5_40E.matrix.safe.json`
(SHA-256
`9ddb17548453649e1b5ad2616d9098808bd42a1062f901f2d557621dc7f006c8`).

| Sample | Canonical | Gate 3 | Gate 4 | Deterministic outcome |
| --- | ---: | ---: | ---: | --- |
| `DEV_PUBLIC_TBANK` | 4 tables / 16 rows / 274 cells | 1 chunk / 294 targets / 21 facts | 21 facts; 5 ready purchases | disposal `MISSING_FROM_SOURCE`; commission detail preserved |
| `HOLDOUT_REAL_001` | 14 tables / 201 logical rows / 2,237 cells | 1 chunk / 2,444 targets / 63 facts | 63 facts; 20/20 security facts ready | hybrid commission preserved; FIFO stops on insufficient prior quantity |
| `LARGE_REAL_001` | complete page/text context; 204 nodes | 4 chunks / 140 targets / 90 facts | 90 facts; 8/21 security facts ready | mixed evidence is surfaced; no node-equality charge relation |
| `PUBLIC_FIDELITY_STATEMENT` | complete page/text context; 55 nodes | 2 chunks / 28 targets / 12 facts | 12 facts; symbol literals preserved | partial dates/non-ISO currency remain source gaps |

There are no `LOST_UPSTREAM` classifications in the final matrix. A fact is
`AVAILABLE` only when exact source bindings reach Gate 4. Missing or invalid tax
authority is `MISSING_FROM_SOURCE` or `SOURCE_EVIDENCE_INSUFFICIENT`.

## First-loss journal

| First loss | Minimal fix | Replay evidence |
| --- | --- | --- |
| semantic visual projections were omitted by Gate 2 canonical shadow persistence | pass existing semantic projections to the one canonical normalizer | TBank: 4 tables / 16 rows / 274 cells survive persisted Canonical |
| source-bound projection ref did not equal a parser-unit ref | admit it as a standalone source-bound table while retaining parser text | focused persisted Canonical regression is green |
| semantic cells used logical zero-based indexes unsupported by Canonical | accept logical row/column indexes without inventing a header | exact cells survive; no first-row header guess |
| PDF layout stopped at 75,000 objects and table units stopped at 1,000 words | bounded limits raised to 400,000 objects and 5,000 words | Large covers all 65 pages; no layout-tail budget stop |
| aliasless page breaks flushed every pending chunk | retain page/heading context inside the current bounded chunk | Large 66 -> 4 chunks; Fidelity 29 -> 2; 0 lost/duplicated targets |
| Gate 4 rejected partial dates and grouped real numeric literals, dropping whole documents | preserve non-tax-ready source literals and normalize only unambiguous grouping/date forms | all four frozen sidecars materialize; 186 facts reach Gate 4 |
| exact text-node equality was treated as an atomic transaction row | require one canonical table node and one row | page/coarse-node relation is rejected; supported same-row fixture stays green |

## Table, currency, and source context

Canonical retains proven tables for TBank and Holdout. Large and Fidelity retain
complete ordered page/text context but do not claim a table row when no safe
table projection exists. Gate 3 chunk coverage is exact and order-preserving.

Gate 4 keeps both the exact `source_literal` and the deterministic value. A
partial date remains partial; a currency symbol remains a symbol. Only valid ISO
calendar dates are indexed by the SQL cache. Gate 5 requires ISO currency and a
valid full calendar date for tax inputs and therefore fails closed where source
authority is weaker.

## Commission proof

Across real facts the deterministic assessment preserves:

- 47 detail facts (`COMMISSION` plus source-authored
  `TRANSACTION_CHARGE`), 41 role-complete and 6 role-incomplete;
- 7 aggregate `COMMISSION_TOTAL` facts, 6 role-complete and 1
  role-incomplete;
- mode `hybrid`;
- `reconciliation = not_performed`.

Detail and aggregate remain independent even when they disagree. The existing
regression keeps detail amounts and an intentionally different aggregate
unchanged; it neither repairs nor allocates the difference. A charge can become
direct disposal expense only on the same explicit canonical table row. Ordinary
text nodes, page identity, date, asset, proximity, and literal equality are
insufficient.

## Second-domain proof

Withheld tax follows the same source-faithful rule:

- 37 `TAX_WITHHELD` detail facts, 13 role-complete and 24
  role-incomplete;
- 3 `TAX_WITHHELD_TOTAL` aggregate facts, 1 role-complete and 2
  role-incomplete;
- mode `hybrid`;
- `reconciliation = not_performed`.

No commission-specific reader, allocation, or reconciliation subsystem was
copied into this domain.

## Deterministic consumer and FIFO

The read-only assessment processes all 186 real facts. It reports 33/48
security facts tax-input-ready and 15 as `SOURCE_EVIDENCE_INSUFFICIENT` (13
missing required bindings, one partial/invalid date, one invalid quantity).
It does not drop the 15 facts to manufacture a complete FIFO case.

The full mixed case and each document-local attempt fail closed for explicit
source sufficiency reasons. The existing supported FIFO regression remains
green and proves date-ordered lot consumption without a stored
purchase-to-sale event. Stored financial-event relations in the real assessment:
zero.

## Supported declaration/XML replay

The existing complete supported vertical remains green. The broad regression
included declaration semantic input, scope, tax settlement, income sources,
financial investment results, definition, projection, resolved package, full
target XML, XSD validation, consumer-first source facts, and bundle parity.

```text
520 passed, 5 warnings in 99.27s
```

The warnings are existing SWIG deprecation warnings; there were no assertion
failures. Final bundle SHA-256 pins:

- Gate 1:
  `db806278055a33c3a762a0b054c11a95dd8f82d2a8923acb30636a7e9013807f`;
- Gate 2 source fact:
  `b45075e3170064f21d3c1d1a5bd4f9ad72fcb3853975392ee9c9922bcc9654f4`;
- Gate 2 domain source fact:
  `03921a3810116c6fabb93b344377d2c756377a75a835395ca33251804f9de120`.

## KISS audit

Consciously not built:

- event/relation graph;
- purchase-to-sale or charge-to-disposal persistence;
- generic reconciliation engine;
- commission allocation;
- broker-specific currency defaults;
- symbol-to-ISO guessing;
- a second source reader, table authority, role schema, SQL database, or case
  registry;
- LLM reasoning after normalization;
- retry, repair, best-of-N, or expected-output injection.

The retained changes reuse existing factories and add only bounded source
projection persistence, chunk packing, literal normalization/preservation, and
one deterministic sufficiency assessment.

## Evidence and scope stop

- Safe receipt SHA-256:
  `a2b055c5954af99600936a0f0261e1bcd3acdc08ef55e19aa6363dcfec2f1f9e`.
- Published proof-only methodology SHA-256:
  `06947c90e1a24ff7ec62f893eff582e9de4e637a6173bd1a4b027eb783045091`.
- `git diff --check`: exit 0; Windows line-ending warnings only.
- Existing dirty worktree content was preserved.
- No commit, push, PR, stage mutation, product activation, or dependent GOAL was
  performed.

```text
NEXT_ALLOWED_GOAL = NONE_WITHOUT_USER_AUTHORIZATION
```

GitHub research journal:
[`#278` safe closeout comment](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5278093722).
