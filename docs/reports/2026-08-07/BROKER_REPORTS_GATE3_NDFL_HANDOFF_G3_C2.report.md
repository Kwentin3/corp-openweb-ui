# Broker Reports NDFL Gate 2 to Gate 3 handoff — G3.C2

Date: 2026-08-07

Status: `COMPLETED`

## Plain-language result

Gate 2 is finished for a document only when its validated
`CanonicalArtifactV1` version is the explicit `ACTIVE` version. A candidate or
validated-but-not-active version is not ready.

The stable NDFL workflow owner `broker-reports-ndfl`, implemented by
`NdflWorkflowFactory.create`, decides whether Gate 3 may run. Gate 2 does not
call Gate 3. The workflow gives Gate 3 only the stable `document_id` and the
server-authenticated access context. Gate 3 then reads the active canonical
document itself through `CanonicalReaderFactory`.

The completed full-document result is saved by the existing
`Gate3FinancialAnnotationsPersistenceFactory` as a separate
`FinancialAnnotationsV1` sidecar bound to the exact active canonical version.

## Exact chain

```text
Gate 2
-> CanonicalArtifactStoreFactory.put_candidate
-> validated immutable canonical version
-> explicit CanonicalReader.activate
-> ACTIVE ready signal

NDFL workflow (stable ID broker-reports-ndfl)
-> decide_gate3(document_id, authenticated context)
-> CanonicalReaderFactory.read_active_envelope
-> exact document_id + canonical_version_id decision

Gate 3
-> receives document_id + authenticated context only
-> Gate3ChunkBatchLabelingFactory.create
-> CanonicalReaderFactory through projection/chunk owner
-> complete validated merge
-> Gate3FinancialAnnotationsPersistenceFactory.create
-> immutable FinancialAnnotationsV1 sidecar for exact version
```

There is no CanonicalArtifact copy, hidden text transfer, LLM-to-LLM handoff,
Pipe-to-Pipe chat or direct physical-store read in this route.

## Version proof

The executable integration proof covered both required cases:

1. Version A active -> NDFL decision A -> complete annotations A -> sidecar A.
2. Version B becomes active -> the A sidecar is reported stale -> B is Gate 2
   ready but Gate 3 missing -> a new NDFL decision names B.

It also forced B to become active while A was being labeled. The workflow
detected the pre/post-label version mismatch and failed before writing any
sidecar. The existing persistence owner repeats the active-binding check as a
second fail-closed boundary.

## Evidence

- focused handoff/workflow/readiness/persistence/batch suite: `32 passed`;
- expanded handoff plus Gate 3/canonical/architecture regressions: `99 passed`;
- the real factories and SQLite ArtifactStore were executed; only the model
  transport was a deterministic integration double;
- one complete workflow call produced one provider call and one sidecar;
- active canonical version before and after successful Gate 3 was identical;
- race proof produced zero sidecars;
- static anti-drift checks prove Gate 2 owners do not import the NDFL workflow,
  and the workflow has no `put_record`, ArtifactStore factory, OpenWebUI action,
  parallel execution or display-name dependency.

The safe receipt is
[BROKER_REPORTS_GATE3_NDFL_HANDOFF_G3_C2.receipt.safe.json](./BROKER_REPORTS_GATE3_NDFL_HANDOFF_G3_C2.receipt.safe.json).

## Limit

G3.C2 supplies the missing orchestration owner but does not yet bind it to a
single live OpenWebUI Workspace Model. That is G3.C3. No Gate 4 work was done.

```text
GOAL_G3_C2=COMPLETED
GATE2_READY_SIGNAL=ACTIVE_VALIDATED_CANONICAL_VERSION
HANDOFF_OWNER=broker-reports-ndfl
HANDOFF_PAYLOAD=DOCUMENT_ID_PLUS_AUTHENTICATED_ACCESS
CANONICAL_READER=REQUIRED
EXACT_VERSION_BINDING=PASS
GATE2_DIRECT_GATE3_CALLS=0
AUTO_CONTINUE=G3.C3
```
