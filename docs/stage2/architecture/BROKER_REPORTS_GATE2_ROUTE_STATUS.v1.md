# Broker Reports Gate 2 Route Status v1

Status: normative reachability baseline  
Effective date: 2026-07-31  
Repository baseline: `origin/main@9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

## Interpretation

The allowed route statuses are `ACTIVE_PRODUCT`, `INACTIVE_CANDIDATE`,
`HISTORICAL_READ_ONLY`, `PROOF_ONLY`, `TO_BE_SUPERSEDED`,
`UNVERIFIED_LIVE`, and `CONTRACT_ONLY`.

Mergeability of a PR does not equal architecture acceptance.

Presence of code does not equal product reachability.

Historical execution does not equal current product activation.

## 1. Semantic Visual Table route

<!-- route_id=semantic_visual_table;status=ACTIVE_PRODUCT -->

- **Entrypoint:** `PdfTableIntakeRuntimeFactory` ->
  `PdfDualVlmRuntimeFactory.create_for_openwebui` ->
  `SemanticVisualTableMaterializationFactory.create`.
- **Imports:** the Gate 1 Pipe imports the maintained intake, VLM, validator,
  migration, and materialization factories.
- **Valve:** semantic visual table processing is repository-enabled by the
  released Pipe policy; the live copy is not trusted without parity.
- **Production reachability:** `true` in the committed product route.
- **Provider reachability:** `true` only for one bounded table crop under the
  visual VLM policy.
- **Exact consumer:** deterministic semantic visual-table materialization,
  ArtifactStore, then `Gate2TablePackageFactory`.
- **Evidence:** PRs #12, #13, #16, #18, and #19; maintained bundle tests and
  semantic visual materialization tests.
- **Rollback/historical purpose:** previous structural/review paths remain
  available as explicit terminal alternatives, not silent semantic fallback.
- **Forbidden actions:** financial classification, fact-type selection,
  canonical record creation, whole-document model upload.

## 2. Current broad canonical source-facts route

<!-- route_id=current_broad_source_facts;status=ACTIVE_PRODUCT -->

- **Entrypoint:** `broker_reports_gate2_domain_source_fact_pipe.Pipe.pipe` ->
  `Gate2DomainSourceFactRuntimeFactory.create`.
- **Imports:** product Pipe imports the domain runtime; the runtime imports
  readiness, segmentation, routing, domain packages, source-fact validation,
  stitching, ArtifactStore, and downstream AnswerContext.
- **Valve:** product route exists; optional candidate binding and financial
  evidence features retain their own false defaults.
- **Production reachability:** `true`.
- **Provider reachability:** `true` for the admitted broad/domain structured
  source-fact requests.
- **Exact consumer:** canonical source-fact validator/stitcher, ArtifactStore,
  AnswerContext, and Gate 3 manifest inputs.
- **Evidence:** source-fact runtime tests, Pipe factory tests, ArtifactStore
  tests, bundle parity tests.
- **Rollback/historical purpose:** deterministic and terminal source outcomes
  remain available without switching to `source_fact_selection_v3`.
- **Forbidden actions:** crop-byte input, Type-First activation, tax
  calculation, direct store reads, hidden fallback.

## 3. Historical `source_fact_selection_v3`

<!-- route_id=source_fact_selection_v3;status=HISTORICAL_READ_ONLY -->

- **Entrypoint:** `Gate2SourceFactRuntimeFactory.create` contains a versioned
  compatibility branch; `Gate2SourceFactSelectionFactory.create` validates and
  materializes the historical shape.
- **Imports:** the general source-fact runtime imports the historical module;
  the current domain product runtime does not.
- **Valve:** the source Pipe passes
  `_semantic_selection_containment_guard()`, which returns `False`; user valve
  value cannot make the path reachable.
- **Production reachability:** `false`.
- **Provider reachability:** `false` from product.
- **Exact consumer:** frozen historical replay, tests, and audit-only
  compatibility.
- **Evidence:** containment guard, historical selection tests, GOAL 18
  reconciliation evidence.
- **Rollback/historical purpose:** reproduce pinned `v3` artifacts and explain
  earlier executions.
- **Forbidden actions:** enabling a valve, adding a product caller, using it as
  fallback, expanding its fact vocabulary, calling it active.

## 4. GOAL 17 Type-First V6 route

<!-- route_id=goal17_type_first_v6;status=CONTRACT_ONLY -->

- **Entrypoint:** none on `main`; the fail-closed Type-First contract is the
  only admitted artifact. Draft PR #232 proposes additive candidate methods.
- **Imports:** no product Pipe on `main` imports a GOAL 17 Type-First request,
  parser, or execution coordinator.
- **Valve:** none on `main`.
- **Production reachability:** `false`.
- **Provider reachability:** `false`; KT1 provider calls are zero.
- **Exact consumer:** contract/audit tests on `main`; synthetic proof tests only
  in draft PR #232.
- **Evidence:** GOAL 16 fail-closed contract; GOAL 17 draft report/receipt and
  tests; GOAL 18 reconciliation audit.
- **Rollback/historical purpose:** preserve design/test evidence for extraction
  into a future same-source convergence slice.
- **Forbidden actions:** merge-as-is, product import, new valve, production
  admission, independent materializer, live qualification or release.

The out-of-main implementation in PR #232 is `INACTIVE_CANDIDATE`; its
zero-call execution evidence is `PROOF_ONLY`. Neither status changes the
`CONTRACT_ONLY` status of `main`.

PR #232 is not part of `main`.

## 5. Deterministic FNS 2-NDFL adapter

<!-- route_id=fns_2ndfl_adapter;status=ACTIVE_PRODUCT -->

- **Entrypoint:** `Gate2Fns2NdflAdapterFactory.create`.
- **Imports:** maintained Gate 2 contracts and deterministic normalization
  helpers; no model client.
- **Valve:** no semantic-model valve; use is explicit through its adapter
  caller.
- **Production reachability:** `true` as a deterministic adapter.
- **Provider reachability:** `false`.
- **Exact consumer:** canonical Gate 2 typed-fact validation and parity proof.
- **Evidence:** FNS adapter and parity tests/reports.
- **Rollback/historical purpose:** deterministic reprocessing from neutral
  source events.
- **Forbidden actions:** XML parser ownership, source download, provider call,
  tax calculation, semantic repair.

## 6. AnswerContext route

<!-- route_id=answer_context;status=ACTIVE_PRODUCT -->

- **Entrypoint:** `AnswerContextSelectionFactory.create`, invoked after a
  completed domain Gate 2 run.
- **Imports:** domain runtime imports AnswerContext; AnswerContext imports
  ArtifactResolver and validated table/stitch contracts.
- **Valve:** answer context is enabled in the current domain Pipe, but its
  precondition remains a completed terminal Gate 2 run.
- **Production reachability:** `true`, downstream only.
- **Provider reachability:** `false`.
- **Exact consumer:** final answer/report presentation.
- **Evidence:** answer-context selection tests and persisted selection receipt.
- **Rollback/historical purpose:** receipt makes selection reproducible without
  rerunning financial semantics.
- **Forbidden actions:** use as financial-model input, raw source/crop reads,
  incomplete-run selection, alternate fact authority.

## 7. Gate 3 input/manifest route

<!-- route_id=gate3_context_manifest;status=ACTIVE_PRODUCT -->

- **Entrypoint:** `Gate3ContextManifestFactory.create`.
- **Imports:** the manifest service reads only declared ArtifactStore ports and
  terminal Gate 2 contracts.
- **Valve:** none; construction is explicit.
- **Production reachability:** `true` as an input boundary, not as an implied
  expansion of Gate 3 business scope.
- **Provider reachability:** `false`.
- **Exact consumer:** declared Gate 3 query/business readers.
- **Evidence:** manifest validation, descendant-ref and append-only
  architecture tests.
- **Rollback/historical purpose:** reproduce the exact Gate 2 exit context.
- **Forbidden actions:** direct Gate 1/provider access, undeclared artifact
  reads, Gate 4 policy.

## 8. Gate 4 proposals/contracts

<!-- route_id=gate4_contracts;status=CONTRACT_ONLY -->

- **Entrypoint:** none admitted.
- **Imports:** no production module imports a Gate 4 calculation or declaration
  runtime.
- **Valve:** none.
- **Production reachability:** `false`.
- **Provider reachability:** `false`.
- **Exact consumer:** architecture and product planning only.
- **Evidence:** PRD/blueprint proposals, without production proof.
- **Rollback/historical purpose:** preserve proposed boundaries for a later
  checkpoint.
- **Forbidden actions:** direct source/provider reads, tax calculation claims,
  declaration generation, production admission.

## 9. Release/live bundle state

<!-- route_id=release_live_bundle_state;status=UNVERIFIED_LIVE -->

- **Entrypoint:** read-only
  `scripts/live_verify_broker_reports_stage2_delivery.py`.
- **Imports:** committed maintained sources, bundle builders, release
  configuration, and read-only live inspection helpers.
- **Valve:** not applicable; this is a verification route.
- **Production reachability:** repository routes are defined, but exact live
  reachability is not accepted while parity is unresolved.
- **Provider reachability:** not exercised by KT1.
- **Exact consumer:** release decision and audit report.
- **Evidence:** last read-only GOAL 18 snapshot found all three live Function
  bundle hashes different from current committed bundles and a failed adapter
  containment check.
- **Rollback/historical purpose:** live snapshots and previous release receipts
  are diagnostic inputs only.
- **Forbidden actions:** claim live parity, rebuild/deploy bundles, mutate
  Functions/prompts/valves, or repair drift during KT1.

Debt: `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`.

## PR_232_DISPOSITION

Recommendation: `CLOSE_AFTER_EXTRACTION`.

- **Preserve commits/ideas:** Pack-backed rich type cards; plural plausible
  types; local keys and exact mapping restoration; deterministic code-owned
  reason derivation; one-call/no-fallback accounting; exact evidence replay
  and comparator tests.
- **Exclude from the future product route:** synthetic source projection as a
  product input, a second Pipe/runtime, separate product request chain, new
  valve/admission, and any duplicate canonical materializer.
- **Historical evidence:** GOAL 17 report, safe receipt, inactive contract, and
  zero-call proofs remain pinned to PR #232/its branch.
- **New branch required:** yes, but only after KT1 and explicit KT2
  authorization; base it on current `main`, not on PR #232.
- **Reusable tests:** plural response totality, forbidden-field checks, exact
  restoration, deterministic decision-table reasons, one-call accounting,
  replay equality, no-new-factory/import reachability.
- **Second-route prevention:** evolve the existing source-fact product boundary
  and reuse current validators/materializer/evidence owners; do not merge or
  retarget PR #232 into product.

KT1 does not modify, close, retarget, or merge PR #232.
