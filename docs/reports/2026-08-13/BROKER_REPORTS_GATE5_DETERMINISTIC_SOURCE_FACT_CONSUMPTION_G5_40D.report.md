# Broker Reports G5.40D — Deterministic Tax Input Sufficiency from Real Source Facts

Date: 2026-08-13

Status: `CORE_PROOF_COMPLETE; REAL_DOCUMENT_VERTICAL_PARTIAL`

```text
DETERMINISTIC_SOURCE_FACT_CONSUMPTION_PROVEN
FIFO_WITHOUT_STORED_EVENT_PROVEN
SOURCE_GRANULARITY_PRESERVED
OVERALL_TERMINAL = UPSTREAM_SOURCE_FACT_GAP_LOCALIZED
```

The ordinary-code consumer is proven for complete Gate 4 normalized facts and
reaches the existing securities Tax Model and declaration fragment. The real
document part of the G5.40D success contract is not closed: no inspected real
statement currently reaches Gate 4 with every required purchase, disposal,
charge and ISO-currency role. The first losses are localized below; no value,
currency, event, or relation was repaired after the run.

Safe machine-readable evidence:

- [tax-demand and real-document matrix](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_G5_40D.matrix.safe.json);
- [proof receipt](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_G5_40D.receipt.safe.json).

## Consumer-first chain

The implemented path starts at the existing declaration consumer:

```text
declaration fragment
<- existing securities-disposal Tax Model
<- gross income + FIFO acquisition cost + exact-target transaction expense
<- Gate4FinancialCaseFactV2 normalized source facts
```

`Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` composes the
official Gate 4 runtime and the existing hash-pinned methodology authority.
The existing Tax Model factory composes that consumer and
`Gate5SecuritiesDisposalTaxModelRuntime.run_from_current_source_facts` invokes
it directly before reusing the existing Tax Model and declaration projector.
No caller-supplied consumption payload is accepted. There is no second reader,
calculator, Tax Model, store, or schema family.

The proof-only methodology
`ru-ndfl-securities-source-fact-consumption-proof@2026.4-experimental` is pinned
to resource SHA-256
`ed541a77f390cd7ee787f5ff179208545df6ef0c66d6e2d02c106cdc54a98ac7`.

## FIFO without a stored event

The controlled full Gate 3 sidecar -> Gate 4 Fact v2 -> Gate 5 integration
fixture contains two acquisition lots and one disposal. Date-ordered FIFO
consumes the first lot and part of the second, producing deterministic
declaration values through the existing model. The output retains acquisition
fact IDs only as calculation provenance; it creates no purchase-to-sale event,
relation, membership edge, or persisted record.

The method fails closed for insufficient acquisition quantity, a non-minor-unit
proportional amount, and same-date ambiguity when missing source order would
change per-disposal cost attribution. A fact-ID hash is never used to decide a
material same-date economic order.

## Commission and withheld-tax pressure

The pressure fixture preserves commission details `10` and `15` beside a
source-authored total `40`. It also preserves withheld-tax detail `4` beside
source total `7`. Both domains report `hybrid`; every fact keeps its own Gate 3
and canonical provenance and `reconciliation=not_performed`. Detail-only and
aggregate-only modes are separately exercised. No total is recomputed,
allocated, replaced, or repaired.

The disposal expense is narrower: only a `TRANSACTION_CHARGE` on the exact same
canonical binding and annotation target is admitted. If absent, the source
consumer reports an explicit missing expense and the Tax Model adapter raises
`gate5_source_fact_direct_expense_missing`; it never defaults to zero.

Partial acquisition commission remains `METHODOLOGY_UNRESOLVED`. The corrected
contract does not claim that relation evidence is necessarily required for a
future authorized method.

## Real-document coverage and first loss

Four hash-identified broker statements were inspected. Private values and
filesystem paths remain outside Git; the matrix contains only safe sample IDs,
hashes and structural findings.

| Sample | Source evidence | First loss | Required-input result |
| --- | --- | --- | --- |
| `DEV_PUBLIC_TBANK` | purchase and commission observations | table row/cell/column binding is lost from visual projection to Canonical; no supported disposal detail is present | disposal/charge `MISSING_FROM_SOURCE`; acquisition `LOST_UPSTREAM` |
| `HOLDOUT_REAL_001` | purchase, disposal, commission, withholding and totals | trade rows survive, but current exact-row role binding has no row-local ISO currency | required money facts `LOST_UPSTREAM` |
| `LARGE_REAL_001` | purchase, disposal, commission, withholding and totals | Canonical loses table identity, rows, headers and column bindings; later relevant pages are split | required money facts `LOST_UPSTREAM` |
| `PUBLIC_FIDELITY_STATEMENT` | purchase, disposal, commission, withholding and totals | transaction rows use a currency symbol; symbol-to-ISO inference is not authorized | required money facts `LOST_UPSTREAM` |

For the preserved-row holdout, the first semantic loss is the current
same-target Gate 3 role boundary: currency outside the accepted row cannot be
bound to that fact. Promoting a report-level base currency or mapping a symbol
to an ISO code would be a new upstream methodology, not simple selection. The
consumer therefore does not run on those real facts.

## Contract and compatibility changes

- Source-Fact Domain Boundaries v1 now states that partial acquisition
  commission is a methodology gap without pre-judging relation necessity.
- Deterministic Source-Fact Consumption v0 owns the new proof-only consumer.
- The trusted methodology registry adds one immutable package resource.
- The generated Gate 1 bundle includes the new module/resource; no workspace
  import or filesystem path is required at runtime.
- The G5.40C report corrects its original `10 + 15` versus `30` disagreement
  claim; G5.40D supplies an actual `40` pressure value.

No Gate 4 field or schema change was required. Fact v2, existing explicit
supplemental Tax Model replay, and the full declaration/XML route remain
compatible.

## Verification

```text
focused source-fact consumer suite: 6 passed
supported declaration/XML + architecture/bundle replay: 72 passed, 6 warnings
Gate 1 generated bundle SHA-256:
64d8b9019a2eadb640774f0df4dd008966af7300ee2cce739992a24a422cd246
```

The initial relevant run executed assertions and found two expected bundle-hash
pin mismatches after the maintained bundle was rebuilt. The pins were updated
to the new generated byte hash and the same relevant command then passed.
Warnings are existing SWIG/Python deprecations and do not change outcomes.

The broad service suite collected `3405` tests but did not produce an assertion
result within either a 364-second or a 904-second runner window. Both attempts
ended as process timeouts with no failure output. They are not counted as a
pass or assertion failure; the completed 72-test supported vertical is the
terminal regression evidence for this Goal.

## KISS and stop boundary

One new consumer module and one immutable methodology resource reuse the
official Gate 4 runtime, trusted methodology authority, existing Tax Model and
existing declaration projector. The change adds no event graph, relation
ontology, reconciliation engine, generic rules framework, broker-specific
adapter, database, persistence route, or provider call.

The core architectural proof is complete, but the real-document vertical stops
at `UPSTREAM_SOURCE_FACT_GAP_LOCALIZED`. Fixing Canonical/Gate 3 currency and
row preservation is a separate upstream Goal. Projector cutover, public
activation, legacy deletion, filing, push, and PR are not authorized here.

## Research journal

The single journal remains `Kwentin3/corp-openweb-ui#278`. The G5.40D comment
is [`issuecomment-5276735983`](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5276735983).
No commit, push, or PR is created by this Goal.
