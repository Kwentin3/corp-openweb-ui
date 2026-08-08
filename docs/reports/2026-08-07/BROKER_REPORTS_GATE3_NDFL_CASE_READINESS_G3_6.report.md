# Broker Reports G3.6 NDFL multi-document readiness

Status: `COMPLETED_INACTIVE`

Date: 2026-08-07

## GOAL_STATUS

`G3.6 = COMPLETED`; `ACCEPTANCE = PASS`.

One deterministic `NDFL` case read model now derives per-document and
case-level readiness from access-controlled existing artifacts. It persists no
workflow state and does not implement Gate 4.

## WHAT_WAS_ACHIEVED

- zero, one, many-ready and partial case states are deterministic;
- Gate 2 readiness comes only from the current active canonical version;
- Gate 3 readiness requires one readable complete sidecar bound to that exact
  version;
- stale, incomplete, blocked and missing sidecars never create completion;
- relabel sidecars remain immutable and the latest current record is selected
  deterministically;
- six fixed follow-up actions are code-owned;
- `PREPARE_DECLARATION` fails closed unless every non-empty case document is
  Gate 3 ready;
- authenticated user/case/workspace scope is enforced in the database query;
- the live proof left the existing ArtifactStore byte-identical.

## WHAT_WAS_REUSED

- authenticated `ArtifactAccessContext` as the sole case identity origin;
- existing `ArtifactResolver` and ArtifactStore lifecycle/access checks;
- active canonical pointers and immutable canonical versions;
- G3.5 `Gate3FinancialAnnotationsPersistenceFactory` validation/read boundary;
- existing annotation versions, retention and case purge behavior.

## WHAT_WAS_ADDED

- `Gate3NdflCaseReadinessFactory.create(context)` as the sole G3.6 entrypoint;
- one closed, non-persisted readiness DTO/schema;
- one tenant-scoped ArtifactStore metadata query across case runs;
- focused behavioral, schema, access and architecture tests;
- one read-only real-case proof and privacy-safe receipt.

## WHAT_WAS_NOT_NEEDED

- a workflow database, table, event log, graph or cache;
- a second orchestrator or second persistence framework;
- provider calls, LLM state decisions or financial classification;
- document-context combination, relabeling or repair;
- Gate 2 changes, product activation or Gate 4 tax logic.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| 0 documents | `PASS` |
| 1 ready document | `PASS` |
| N ready documents | `PASS` |
| partial N documents | `PASS` |
| Gate 2 ready / Gate 3 missing | `PASS` |
| incomplete labeling | `PASS` |
| new canonical version makes old sidecar stale | `PASS` |
| new annotation version / relabel | `PASS` |
| access denied / foreign-scope non-disclosure | `PASS` |
| deterministic, code-owned state | `PASS` |
| no phantom completion | `PASS` |
| Gate 4 action fail-closed | `PASS` |
| separate state database | `NONE` |

The live case result was correctly partial: 16 of 16 documents had an active
Gate 2 canonical version, one had a current complete Gate 3 annotation
sidecar, and `PREPARE_DECLARATION` remained disabled.

## RAW_EVIDENCE

- [safe receipt](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS_G3_6.receipt.safe.json);
- ArtifactStore tree SHA-256 before and after:
  `bb553be84297f167eafcad5127e88e005fdafc947402f6479726446f95622ff3`;
- deterministic private readiness snapshots had the same SHA-256:
  `b6aa994379298747394a7c9cdc9b2b426255130f2c86911dfef515f063c622d3`;
- exact private evidence remains outside Git: 6 files, 85,519 bytes; manifest
  SHA-256
  `20cb4e43caef92974d679275246d9c1076e47800b5cacd812ea3b10c79e8a2d8`;
- focused G3.6 contract/proof tests: `10 passed`;
- ArtifactStore, G3.5 regression and architecture checks: `53 passed`;
- maintained bundle parity/runtime checks: `42 passed`;
- targeted Ruff: passed.

## KNOWN_LIMITATIONS

- Readiness reports artifact truth; it does not make missing documents or
  annotations complete.
- The current real case is not ready for Gate 4 because only one of 16
  documents has a current complete Gate 3 sidecar.
- The read model is inactive and has no OpenWebUI product route.
- `PREPARE_DECLARATION` is only a handoff permission; no declaration or tax
  calculation exists in Gate 3.

## OBSERVATIONS

The existing store contained 16 distinct active canonical document identities.
The live read model derived this count from current case artifacts rather than
reusing a historical corpus count.

The first private-manifest write reused a helper whose metadata still named
G3.4C. This proof-only metadata defect was corrected to the G3.6 schema/goal;
the readiness snapshots, receipt and ArtifactStore were unchanged.

## KISS_CHECK

`PASS`.

The implementation is one derived read model over existing owners. It adds no
state authority, semantic subsystem or speculative workflow machinery.

## BLOCKING_OBSERVATIONS

`NONE` for G3.6 acceptance. The partial live case is real input state, not a
workflow implementation failure.

## ERROR_CLASSIFICATION

Private-manifest metadata mismatch: `TYPE 1 — IMPLEMENTATION BUG`, corrected
without rerunning or changing proof data. Final G3.6 result: no error.

## AUTO_CONTINUE

`YES`.

## NEXT_GOAL

`G3.7 — terminal Gate 3 end-to-end proof`.
