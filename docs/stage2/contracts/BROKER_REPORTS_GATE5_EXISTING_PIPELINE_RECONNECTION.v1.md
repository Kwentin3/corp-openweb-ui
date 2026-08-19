# Broker Reports Gate 5 Existing Pipeline Reconnection v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.48`

Architecture placement is owned by the current
[Pipeline Architecture v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md). This file
owns the exact G5.48 reconnection evidence, not a second pipeline map.

## Ownership

`Gate5EvidenceDemandRuntimeFactory.create` owns only consumer demand
compilation, existing-fact checks and `source_fact_demand_v1` request emission.
It must not read source or Canonical data, choose extraction strategy, call a
provider, validate source proposals or project Gate 4 facts.

`Gate3EvidenceDemandPortFactory.create` validates that a requested
`financial_label` and its consumer-required roles exist in the current
published Gate 3 Dictionary and Role Pack. A known request binds to
`Gate3ChunkBatchLabelingFactory.create`; an unknown label or role fails closed.
The adapter reads no source and calls no provider.

`Gate3ChunkBatchLabelingFactory.create` remains the sole execution owner. Its
optional `requested_financial_labels` argument may prioritize already
published labels inside the existing three-message request envelope. It does
not add taxonomy, assert source presence, change chunking, weaken validation,
retry, repair or persist a partial result. Its result marks such execution as
`DEMAND_SCOPED`; whole-document chunk coverage does not turn that delta into a
`FULL` publication.

Gate 4 continues to materialize only validated, persisted
`FinancialAnnotationsV2`. The G5.47 transient Canonical projector is removed.
Gate 5 continues to consume facts only through
`Gate4FinancialCaseRuntimeFactory.create`.

## Call direction

```text
Gate 5 methodology consumer
  -> Evidence Demand request (meaning, roles, scope)
  -> Gate 3 Evidence Demand public port (published-contract check only)
  -> Gate 3 structural chunk + type pass + exact role context/role pass
  -> Gate 3 persistence owner non-destructively merges a validated demand delta
     with the explicit current FinancialAnnotationsV2 base
  -> Gate 4 deterministic materialization/runtime
  -> Gate 5 deterministic replay
```

No reverse Gate 5-to-Canonical reader edge exists.

## Reclassification law

A document-wide provider miss cannot establish a Canonical preservation gap.
G5.47's 29 financial rows are reclassified as either an exact existing-pipeline
role-extraction gap (where an existing Gate 4 fact binding is known) or a
recovery path that bypassed the existing owner. The three non-financial
meanings are upstream fact-contract gaps because they are absent from the
published financial Dictionary/Role Pack. G5.48 proves zero true Canonical
preservation gaps; that is a non-claim, not proof that none exist.

## Live proof boundary

The final one-gap run used one 58,149-character structural chunk, 40 target
aliases and two provider submissions. The demand-aware type pass returned eight
requested `SECURITY_PURCHASE` annotations, but the role pass produced zero
Role-Pack-complete facts and added no missing roles on the six exact gap
targets. The ArtifactStore was byte-for-byte unchanged.

Therefore `BOUNDED_CONTEXT_EXECUTION_PROVEN` is current, while
`BOUNDED_CONTEXT_RECOVERY_PROVEN` is explicitly not proven. A full-document
persist/Gate4/Gate5 replay is forbidden until one exact gap becomes complete
through this owner without retry or repair.

Once a gap is complete, publication follows
[Gate 3 Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md):
unrelated facts are preserved, exact same-source incomplete facts may be
superseded only by strictly more complete compatible facts, and conflicts fail
closed.
