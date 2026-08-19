# Broker Reports G5.48 — Existing Pipeline Reconnection

Date: `2026-08-14`

Status: `PARTIAL_PROOF_FAIL_CLOSED`

## Outcome

The architecture defect is confirmed and removed. G5.46/G5.47 made Gate 5 a
second document-semantic reader/provider and added a transient Gate 4 projector.
The maintained path now treats Evidence Demand as a request and binds known
financial meanings to the existing Gate 3 Dictionary, Role Pack, structural
chunking, type pass and exact role-context pass.

The bounded live execution succeeded as an owner-path proof but did not recover
one Role-Pack-complete gap. Consequently no full-document persistence,
Gate 4 materialization or Gate 5 tax replay was run.

Proven terminals:

- `EXISTING_EXTRACTION_PIPELINE_RECONNECTED`;
- `G5_47_PARALLEL_RECOVERY_PATH_REMOVED`;
- `METHODOLOGY_DEMAND_TO_SOURCE_OWNER_BOUNDARY_PROVEN`;
- `BOUNDED_CONTEXT_EXECUTION_PROVEN`;
- `PRESERVATION_GAPS_RECLASSIFIED`.

Not proven: `BOUNDED_CONTEXT_RECOVERY_PROVEN`.

## Path forensics

| Boundary | G5.47 path | G5.48 maintained path |
| --- | --- | --- |
| demand owner | Gate 5 | Gate 5 |
| source/Canonical reader | Gate 5 whole-document atom rebuild | none in Gate 5 |
| semantic execution | four document-wide Gate 5 calls | existing Gate 3 bounded chunk/type/role owner |
| meaning/role authority | copied G5.47 contracts and Gate 5 validation | current Gate 3 Dictionary and Role Pack |
| Gate 4 | transient recovery projector | persisted validated `FinancialAnnotationsV2` only |
| downstream | transient overlay | official `Gate4FinancialCaseRuntimeFactory.create` only |

The removed G5.47 code used 4 provider calls and 667,531 input tokens. The final
one-gap G5.48 execution used one 58,149-character chunk, 40 aliases, 2 calls and
61,670 input tokens. The 90.76% ratio proves a bounded one-gap context, not a
same-scope corpus cost comparison.

## Reconnection

`Gate5EvidenceDemandRuntimeFactory.create` now:

- checks existing normalized/user/external/methodology evidence;
- emits deduplicated `broker_reports_source_fact_demand_v1` requests;
- never accepts Canonical documents or a semantic adapter;
- records zero source reads and provider calls.

`Gate3EvidenceDemandAdapterFactory.create` checks the requested fact type and
roles against the published Dictionary/Role Pack. Known financial labels bind
to `Gate3ChunkBatchLabelingFactory.create`; the three new payer/realization
meanings fail closed as upstream contract gaps.

The batch owner accepts an optional, contract-validated
`requested_financial_labels` hint inside its existing three-message request.
The hint does not add a label, assert source presence, alter structural chunks,
change schemas, weaken validators, retry or repair.

The G5.47 `Gate5RealSemanticRecoveryRuntime`, live script and tests were removed.
`Gate4CanonicalRecoveryProjector` was removed from source and the generated
closed-world OpenWebUI bundle.

## One-gap live audit

Five bounded diagnostic cycles were allowed; no best-of-N winner was selected:

1. A structurally plausible but wrongly selected chunk completed both phases;
   it did not emit the demanded disposal fact.
2. Exact upstream binding moved the proof to document 4/chunk 2; the requested
   purchase fact was still absent.
3. The one independently bound disposal gap in another document also remained
   incomplete.
4. The first demand-aware envelope was rejected before transport because it
   added a fourth message. Factory anti-drift worked; provider calls were zero.
5. The hint was folded into the existing document-context message. Both phases
   validated and emitted 8 requested `SECURITY_PURCHASE` annotations, but 0 were
   Role-Pack complete. Six exact gap targets were re-emitted with 0 added roles.

Every cycle had zero retry, zero repair, zero persistence and an unchanged
ArtifactStore. Private requests, responses, source literals, IDs and values stay
outside Git; only aggregate receipts are published.

## Reclassification of G5.47 gaps

The blanket 29-row `CANONICAL_PRESERVATION_GAP` conclusion is invalid. A table
fallback warning on one document cannot classify every financial demand.

| G5.48 classification | Rows | Meaning |
| --- | ---: | --- |
| `EXISTING_PIPELINE_ROLE_EXTRACTION_GAP` | 13 | exact current Gate 4 fact binding exists; bounded Gate 3 replay did not add the required roles |
| `RECOVERY_PATH_BYPASSED_EXISTING_OWNER` | 16 | G5.47 did not execute the authoritative owner, so preservation was never tested |
| `UPSTREAM_FACT_CONTRACT_GAP` | 3 | payer/realization meanings are not in the published financial Dictionary/Role Pack |
| `TRUE_CANONICAL_PRESERVATION_GAP` | 0 proven | no row has sufficient evidence for this classification |

This is not a claim that Canonical has no preservation defects. It is a claim
that G5.47 did not prove them.

## Verification and KISS

Targeted contract/factory/integrity regression is green: `50 passed`. Ruff
lint is green and the generated closed-world bundle contains neither the
transient projector nor the removed G5.47 runtime.

The 3,492-test full suite is not green and is not reported as such. Its first
fail-fast run exposed two unrelated dirty-baseline failures: PDF dual-VLM
`actual_corpus_runtime_budget_drift`, and a documentation guard that still
expects `Gate4FinancialCaseFactV1` while the current branch already carries V2.
After excluding exactly those baselines, the remaining suite exceeded the
603-second runner limit without another assertion summary. This is a runner
timeout, not proof that the remaining tests passed.

KISS is preserved: one demand DTO, one thin contract adapter, the existing Gate
3 semantic owner, the existing Gate 4 materializer/runtime and no new reader,
store, provider client, ontology, graph, relation model or recovery projector.

## Stop and next allowed boundary

G5.48 stops here. It does not authorize a full-document provider rerun,
persistence, product activation, declaration release, push, PR or dependent
Gate goal.

The next allowed work, only if explicitly authorized, is a bounded Gate 3 role-
context diagnosis for one exact re-emitted target. Its acceptance condition must
be one newly complete Role-Pack fact without retry/repair; only then may an
isolated full-document persistence -> Gate 4 -> Gate 5 replay be considered.
