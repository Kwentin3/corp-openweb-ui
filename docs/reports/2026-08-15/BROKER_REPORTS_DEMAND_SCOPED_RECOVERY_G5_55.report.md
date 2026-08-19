# Broker Reports G5.55 — Demand-Scoped Semantic Recovery

Date: `2026-08-15`

Status: `PROVEN`

## Outcome

Proven terminals:

- `DEMAND_SCOPED_RECOVERY_CONTRACT_PROVEN`;
- `NON_DESTRUCTIVE_SEMANTIC_UPDATE_PROVEN`;
- `SAME_TARGET_FACT_SUPERSESSION_PROVEN`;
- `UNRELATED_FACT_PRESERVATION_PROVEN`;
- `GATE4_GATE5_NON_DESTRUCTIVE_REPLAY_PROVEN`.

Demand-driven recovery is now an explicit delta operation. It cannot enter the
ordinary FULL save path and cannot delete a validated fact by omission.

## Current semantics and defect localization

`FinancialAnnotationsV2` is an immutable versioned artifact representing the
current logical semantic projection for one active Canonical version. It is
not an append log. Gate 3 readiness selects the latest validated V2 artifact
bound to the active Canonical version; Gate 4 materializes that selected full
view.

Before G5.55, `Gate3ChunkBatchLabelingResult` retained chunk coverage but lost
the requested-label scope. A one-chunk demand run therefore reported both
`selection_mode=full_document` and `document_status=complete`.
`Gate3FinancialAnnotationsPersistenceFactory.save` accepted those two fields
as sufficient FULL-publication evidence. The resulting five-fact G5.54
sidecar consequently became current and hid 16 unrelated facts. The defect was
at semantic publication admission, not in Gate 3 extraction or Gate 4.

## Minimal contract refinement

The batch-result schema is now v3 and carries one exact `semantic_scope`:

- `publication_mode` (`FULL` or `DEMAND_SCOPED`);
- document identity;
- requested published meanings and their Role Pack role scope;
- selected structural chunk ordinals.

The existing persistence owner now exposes two distinct operations:

- `save`: FULL, successful all-chunk publication only;
- `save_recovery`: validated DEMAND_SCOPED delta plus an explicit current base
  and demand request identity.

Recovery produces a new immutable full-current-view V2 sidecar. Its exact
source-assertion identity is Canonical target plus financial label under the
same document/version. Unrelated facts are preserved; a different target is
added; an exact-target assertion is superseded only by a strictly more complete
compatible role set. Bound-value changes, regressions, duplicate assertions,
stale bases, authority drift and source-version changes fail before write.

The receipt records aggregate add/supersede/preserve/conflict/delete counts.
There is no recovery delete operation and every successful receipt has
`deleted_total=0`.

## Executable scenarios

Black-box tests use the real SQLite ArtifactStore adapter and public factories:

| Scenario | Result |
| --- | --- |
| demand result through FULL save | rejected by scope guard |
| new exact source assertion | added |
| same target/type, missing role becomes bound | one current assertion, superseded |
| different target, same type | added, not overwritten |
| unrelated commission/withholding/charge | preserved |
| empty demand result | identical full view, zero deletions |
| conflicting bound value/target | fail closed, zero ArtifactStore writes |
| stale base | fail closed |
| different Canonical version | fail closed |
| ordinary Gate 4/Gate 5 replay | full current view observed |

The controlled 21-to-5 fixture ends with 21 Gate 4 facts: five purchases and
16 commission/charge facts. Gate 5 observes all 21 and returns
`SOURCE_FACT_ASSERTIONS_PRESERVED`.

## Frozen G5.54 replay

The frozen clean G5.54 provider result was replayed without a new provider call
and without editing its semantic output. A separate private copy of the proof
store was used; the original store database hash remained unchanged. The old
21-fact full sidecar was the recovery base and the defective five-fact proof
sidecar was excluded only in that copied fixture.

The exact result is intentionally not collapsed by equal dates, amounts or
other economic values:

- base: 21 annotations, including five purchases and 16 commission/charge;
- delta: five complete purchases;
- exact purchase-target overlap: zero;
- recovery: five added, zero superseded, 16 unrelated preserved, zero deleted;
- next current document view: 26 facts, including ten source assertions typed
  as purchase and all 16 prior commission/charge facts;
- Gate 4: `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`, 26 facts for the document;
- Gate 5: 53 security facts in the full case and
  `SOURCE_FACT_ASSERTIONS_PRESERVED`;
- stored financial-event relations: zero.

The increase from five to ten purchase assertions is required by the G5.55
identity law: the recovered assertions use different exact Canonical targets.
Treating equal values as one transaction would introduce forbidden economic
identity. The five G5.54 purchases remain proven and none of the earlier
commission/charge semantics is lost.

Safe aggregate evidence is in
[`BROKER_REPORTS_DEMAND_SCOPED_RECOVERY_G5_55.receipt.safe.json`](./BROKER_REPORTS_DEMAND_SCOPED_RECOVERY_G5_55.receipt.safe.json).
Customer-bearing targets, role values, artifact IDs and full traces remain
outside Git.

## Architecture and KISS

The implementation remains inside
`Gate3FinancialAnnotationsPersistenceFactory.create`, delegates storage to the
existing ArtifactStore, and leaves Gate 4 and Gate 5 unchanged. No second
store, mutable overwrite, event sourcing, generic merge engine, version graph,
economic identity, relation inference, retry, repair or product activation was
introduced. The generated Gate 1 bundle was rebuilt from maintained source.

`FULL_REPROCESSING_RICH_CANONICAL_COST` is registered in the architecture debt
section with demand-driven bounded recovery as the current mitigation and real
latency/cost pressure or an explicit full-republication requirement as its
future trigger. G5.55 does not optimize it.

Verification:

- focused recovery, Gate 3, Gate 4, Gate 5, bundle and architecture suite:
  `154 passed`;
- targeted Ruff checks: passed;
- frozen private replay: passed with zero provider calls and unchanged source
  store.

G5.55 stops here. It does not authorize product activation, commit, push, PR,
declaration release or a dependent GOAL.
