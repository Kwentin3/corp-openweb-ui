# Broker Reports Architecture Recovery v1 — final program report

Date: 2026-07-21

Authoritative candidate branch: `codex/broker-reports-architecture-recovery-v1`

Verified implementation revision: `d7cc52dfdac0e3fec3fedde98f10b13ec9b4ba99`

Program base: `7ba45b1d461a6b9056fe7cc1798ef79196edfa1a`

Release decision: `BLOCKED`

## Terminal status

`BROKER_REPORTS_ARCHITECTURE_RECOVERY_PROGRAM: PARTIALLY_COMPLETED`

| Goal | Terminal status |
| --- | --- |
| `GOAL_0_REPOSITORY_GOVERNANCE` | `NOT_CLOSED` |
| `GOAL_1_ARCHITECTURE_GUARDS` | `COMPLETED` |
| `GOAL_2_BOUNDED_VLM_VISUAL_TABLES` | `NOT_CLOSED` |
| `GOAL_3_PRIVATE_SOURCE_INTAKE` | `NOT_CLOSED` |
| `GOAL_4_ARTIFACT_LIFECYCLE` | `COMPLETED` |
| `GOAL_5_GATE1_BOUNDED_GRAPH` | `NOT_CLOSED` |
| `GOAL_6_CSV_PROJECTION` | `COMPLETED` |
| `GOAL_7_WORKLOAD_ORCHESTRATION` | `NOT_CLOSED` |
| `GOAL_8_SBER_CUSTOMER_DEBT` | `EXTERNALLY_BLOCKED_AND_RELEASE_GATED` |
| `GLOBAL_DELIVERY_AND_HYGIENE` | `NOT_CLOSED` |

`COMPLETED` above means the Goal's engineering contract passed on the named
candidate revision. It does not override the global delivery gate or claim that
the candidate is live. Stage promotion, merge to `main` and branch deletion are
forbidden while the release decision remains `BLOCKED`.

## Repository and release receipt

- The recovery branch was forked without rewrite from accepted audit revision
  `7ba45b1d461a6b9056fe7cc1798ef79196edfa1a` and is published as
  `origin/codex/broker-reports-architecture-recovery-v1`.
- At the verified implementation revision it is 47 commits ahead and zero
  commits behind `origin/main` at
  `cf158fd38e3fc0a1f195b885ba94cb0094f95537`.
- There is one registered worktree. It was clean when the implementation suite
  and candidate push completed. No temporary worktree, force push, history
  rewrite, merge to `main` or branch deletion was performed.
- The full local/remote branch classification and safe-delete conditions remain
  authoritative in
  `docs/stage2/operations/BROKER_REPORTS_RELEASE_GOVERNANCE.md`.
- Accepted audit/runtime history remains reachable. The failed three-commit
  guided-intake branch remains retained as experimental evidence and was not
  merged wholesale.
- Current index policy passes: no tracked `*.private.json` or
  `*.private.sha256.json`, and maintained safe outputs contain no local path.
- Reachable history is not clean. Commit `82313d8` contains the removed private
  reference, and commit `dcb2351` contains an absolute evidence path. Both are
  ancestors of the candidate. A deletion/redaction successor cannot remove
  those objects from reachable history, and shared-history rewriting is
  forbidden by the program.

Consequently `REPOSITORY_HYGIENE: PROVEN` and the full Goal 0 acceptance cannot
be asserted.

## Coherent program commits

| Commit | Goal/capability |
| --- | --- |
| `afbfd62` | Goal 0 current-tree quarantine, redaction, governance and privacy guards |
| `b365a5f` | Goal 1 authoritative architecture, ADR and anti-drift guards |
| `86b2f22` | Goal 6 batched source resolution for table projection |
| `d3a1267` | Goal 5 duplication reduction and safe actual-corpus profiler |
| `0f9c950` | Goal 3 receipt-backed private intake boundary and pinned-image patch |
| `1ea2f11` | Goal 4 trusted scope, indexed idempotent lifecycle and failure recovery |
| `37ff957` | Goal 8 default-off Sber holdout release policy |
| `f0e0c4a` | deterministic Gate 1/Gate 2 bundle rebuild |
| `a460c81` | Goal 7 single-scheduler admission contract scaffold |
| `d7cc52d` | Goal 2 bounded VLM proposal contract scaffold |

The Goal 2 and Goal 7 commits are deliberately marked
`contract_scaffold_not_runtime_integrated` and `implementation_pending`. They
are preserved reviewable work, not production-closure claims.

## Completed engineering contracts

### Goal 1 — architecture guards

- One versioned authority defines the separate Broker Reports source pipeline,
  no-RAG/no-vector policy, Gate 1/Gate 2 ownership, bounded visual exception,
  Gemini/OpenAI provider family, Paddle/local-OCR exclusion, proposal-only model
  role, deterministic promotion authority, ArtifactResolver boundary and Sber
  debt separation.
- Entry-point, import, provider, bundle and configuration guards passed.
- Production model canonical authority remains zero.

### Goal 4 — artifact lifecycle

- Lifecycle operations require an exact trusted
  `ArtifactAccessContext`; request-body scope is ignored as authority.
- Claims use indexed predicates and atomic transaction-local transition claims.
  Repeated terminal transitions are typed no-ops, and concurrent callers cannot
  both claim the same transition.
- Failed filesystem deletion preserves recoverable pending state. Expired and
  purged payloads are unresolvable. Broad maintained active-record scans were
  removed.
- Goal-specific, affected-runtime and recovery audits passed. Live deployment
  remains governed by the separate global delivery blocker.

### Goal 6 — CSV table projection

The frozen two-CSV actual workload produced:

| Measure | Frozen baseline | Candidate | Result |
| --- | ---: | ---: | --- |
| projections | 2 | 2 | exact |
| rows | 2,597 | 2,597 | exact |
| cells | 27,241 | 27,241 | exact |
| source-value relationships | 27,241 | 27,241 | exact |
| projection wall time | 429.91 s | 5.488660 s | 78.33x faster |
| process peak RSS | 7,045,357,568 B | 7,041,015,808 B | -0.062%, no material increase |

Payload checksum-set digest remained
`936c3f21c6504144a2399e1c63d367a825e13627f405584951e0d53391601179`.
Projection checksum-set digest remained
`b4172dd56b0e7dff4b9834367e36e0523c3b0402c8ff63768f0be908082d84d1`.
The implementation performs one batched source-index resolution per projection;
the per-cell full-index scan is absent. No row sampling, cell omission, customer
value rule or validator weakening was introduced.

## Non-completed Goal receipts

### Goal 0 — repository governance

- Failed invariant: `REPOSITORY_HYGIENE: PROVEN`; full release-source/stage
  receipt also lacks an embedded exact deployed Git revision.
- Evidence: reachable commits `82313d8` and `dcb2351` retain forbidden historical
  material. The three live Function bytes are reproducible from approved
  revision `7ba45b1`, but the running deployment does not expose a definitive Git
  SHA. Candidate and live bundle hashes differ.
- Owner: Git/release governance and stage provenance.
- Blocker type: governance/architecture, with an approval dependency.
- Narrowest remaining work: approve an explicit non-rewrite disposition for the
  known reachable objects; then produce a clean final release receipt with exact
  image, Function, Action, prompt and source-revision provenance.

### Goal 2 — bounded VLM visual tables

- Failed invariant: production Gemini/OpenAI adapters, authenticated evidence
  origin, real provider compatibility, bundle integration and live proof are
  absent.
- Evidence: the committed scaffold accepts only a declared page or table crop,
  fully decodes PNG/JPEG input, caps request/response contracts, records lineage,
  validates ownership/order/headers/spans/totals/continuation and never promotes
  a model proposal. Self-asserted deterministic evidence can only produce
  `proposal_requires_review`; acceptance is
  `disabled_until_server_authenticated_evidence_binding`.
- The Gemini request and provider-facing structured-output subset were checked
  against the official
  [Interactions API](https://ai.google.dev/api/interactions-api-v1) and
  [structured-output contract](https://ai.google.dev/gemini-api/docs/structured-output).
- Owner: `visual_table_vlm*`, future provider boundary, Gate 1 Pipe/bundle and
  delivery tooling.
- Blocker type: implementation, architecture and environment.
- Narrowest remaining work: implement real streaming/byte/deadline-aware Gemini
  and OpenAI boundaries; bind deterministic evidence to trusted server intake;
  add refusal/incomplete handling; package Pillow in a proven closed-world image;
  route through the canonical factory and bundle; validate on authorized actual
  evidence and stage. Until then no accepted terminal or canonical promotion is
  permitted.

### Goal 3 — private source intake

- Failed invariant: the final maintained stage does not yet make the new
  receipt-backed endpoint and protected Action authoritative.
- Evidence: candidate code rejects generic native refs, requires a persistent
  server receipt and idempotency key, blocks native document/Knowledge/RAG/vector
  choke points, and passed focused tests and patch simulation. The running stage
  still uses the legacy image; the candidate image is absent, the intake module
  and route are absent, and no maintained protected-Action installer/readback or
  endpoint smoke exists.
- Owner: pinned OpenWebUI image patch, protected Action and stage delivery.
- Blocker type: implementation/environment/delivery.
- Narrowest remaining work: add maintained image and Action delivery/readback;
  build on the qualified Linux host; recreate only OpenWebUI with rollback
  identity; prove route, receipt, Action body SHA, zero native/RAG/vector deltas,
  cleanup and quiescence with synthetic data.

### Goal 5 — Gate 1 bounded graph lifetime

- Failed invariants: `GATE1_PEAK_RSS: AT_OR_BELOW_5_GIB` and
  `INTERMEDIATE_GRAPH_LIFETIME: BOUNDED`; complete old/new artifact equivalence
  is also not yet proven.
- Evidence: the clean actual-corpus profile passed terminal accounting but peaked
  at 7,041,015,808 bytes (6.557 GiB), only 0.062% below the frozen historical
  peak and above the 5 GiB ceiling. Normalization improved from 1,167.199 s to
  705.168564 s, so no wall-time regression was hidden.
- The maintained normalizer still accumulates run-wide payload, source-unit,
  provenance and projection graphs; persistence starts after normalization;
  ArtifactStore serializes whole JSON buffers; the proof retains/reloads the
  private graph. `copy_package=False` removes one copy but does not establish a
  bounded unit lifetime.
- Owner: Gate 1 normalizer/full-source builders, persistence sink and
  actual-corpus proof runner.
- Blocker type: architecture/implementation.
- Narrowest remaining work: process one bounded document/source-family unit,
  seal and persist through an `ArtifactStoreFactory` sink, retain only compact
  refs/counts/hashes, release source/parser graphs, stream canonical JSON and
  compare complete old/new artifact identities, hash multisets, manifests,
  terminal outcomes, RSS and wall time.

### Goal 7 — workload orchestration

- Failed invariants: class limits are not process-wide/multi-worker enforced;
  typed progress/cancel APIs, real Gate 1 checkpoints and production cleanup are
  not integrated.
- Evidence: the scaffold fixes queued/admitted cancellation leaks, enforces the
  measured 1/2 Gate 1/Gate 2 caps within one scheduler instance, preserves FIFO
  waiting, requires explicit cleanup policy and has terminal state tests. It is
  not imported by Gate 1/Gate 2 Pipes or bundles; each factory could still own
  independent state; Gate 1 remains synchronous and no persisted authenticated
  job API emits UI-visible progress.
- Owner: Broker Reports runtime coordinator and Gate 1/Gate 2 Pipes.
- Blocker type: architecture/implementation.
- Narrowest remaining work: one authenticated persisted coordinator shared by
  workers, factory-routed Pipe integration, cooperative normalizer checkpoints,
  sealed-result publication, private-artifact cleanup, typed status/cancel API,
  bundle delivery and concurrent stage proof.

### Goal 8 — external Sber debt

- `SBER_BROKER_PROFILE_IMPLEMENTATION: ACTUAL_CORPUS_PROVEN`
- `SBER_BROKER_PROFILE_GENERALIZATION: AWAITING_CUSTOMER_POSITIVE_HOLDOUT`
- `SBER_BROKER_PROFILE_RELEASE: GATED`
- Evidence: the profile remains default-off. Ordinary Pipe input cannot supply
  the proof scope, and only the exact server-side approved evidence scopes can
  enable an authorized proof.
- Owner: customer acceptance and release governance.
- Blocker type: external.
- Narrowest remaining work: receive one authorized genuine unseen same-family
  PDF; run frozen rules without tuning before first result; prove deterministic
  double replay, source-to-canonical review and Gate 2 accounting; record an
  explicit release decision.

## Actual-corpus safe profile

The safe profile is tied to runtime/bundle revision
`f0e0c4a023f3e5bcf85c5797f039b102c11702f2`. Later commits add only non-integrated
Goal 2/Goal 7 scaffolds and do not alter the profiled execution path.

- Status: `passed`
- Top-level inputs: 56
- Document sources: 104
- Logical documents: 80
- Archive containers: 24
- Promoted archive members: 48
- Terminal outcomes: 26 `complete`, 78 `review_required`
- Zero silent loss: passed for every accepted profile document
- Knowledge/RAG absence: true
- Artifact records: 1,531
- Persisted payload bytes: 1,462,961,495
- Profile wall time: 854.291930 s
- Normalization wall time: 705.168564 s
- Peak process RSS: 7,041,015,808 B (6.557 GiB)
- Safe output contains no customer values, private paths, source refs or artifact
  refs.

## Bundle, stage and prompt readback

| Runtime object | Candidate repository SHA-256 | Live SHA-256 | Parity |
| --- | --- | --- | --- |
| Gate 1 Function | `9a5ac9acec123519d539e3d6b9dafa20d241380a8729d2291506bd358b8ae338` | `9b3895b521d8ec82b486edfba7a3b29cbeb913217fa73aff18783915126bb1df` | failed |
| Gate 2 source-fact Function | `88f9cb606c286f4962b2df24cca9609a41b4ecbf633b553459f2832c9799d628` | `168a3095ca488f13736ea4655c54df5ec136ebf196c6ab7fa4e1e98f121a3f96` | failed |
| Gate 2 domain Function | `d5e6d96d507cb11b45e844fc1e0157d8d3a6650ab39464263cff1ef85dd07420` | `eb1a98515743e8adda5fa57dfbe5c2f7a57753966fd1b0902f35300ab903a54e` | failed |

The live Function hashes exactly match the three files at approved audit
revision `7ba45b1`; the stage therefore remains on the previous accepted runtime,
not an unidentified OCR experiment. It is not the recovery candidate.

- Candidate protected intake Action repository SHA-256:
  `3577e6bdd7cbdf63f072810d97c86a43ce14bffe0370165c854cbaa5accac543`.
- Static loader repository SHA-256 (unchanged):
  `28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2`.
- Running stage image fingerprint:
  `sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175`.
- Candidate intake image is absent from the stage image store. The running image
  has no patched intake module/route.
- All 12 managed prompts passed present/active/version/content SHA/metadata
  repo-live parity. No program commit changed their content.
- Provider, factory-boundary, valve, shadows-off, Sber release-gate and required
  renderer checks passed during readback.
- The verifier correctly returned failed because the three Function hashes
  differ. No candidate Function, image, Action or prompt mutation was attempted.

Partial Function-only delivery would create a mixed runtime without the new
intake boundary. It was therefore rejected. The maintained route must first add
image/Action readback and synthetic endpoint smoke, then deliver image, Action
and all three Functions as one candidate receipt with rollback and cleanup.

## Verification

- Baseline before recovery: 976 passed, 5 warnings.
- Final candidate suite: 1,035 passed, 20 skipped, 5 existing SWIG deprecation
  warnings in 75.26 s.
- Goal 2 focused: 32 passed; architecture/bundle/Pipe affected set: 72 passed,
  5 warnings; Ruff and formatting checks passed.
- Goal 7 focused: 13 passed; Ruff and formatting checks passed.
- Actual-corpus profile: terminal `passed` with the safe aggregates above.
- Deterministic bundle regeneration matched the three committed bundle files.
- Read-only stage delivery audit focused suite: 32 passed, 5 warnings.

The skipped tests were not counted as passes. No timeout, truncation, sampling,
snapshot-only assertion or weakened validator was used to obtain a successful
status.

## Final disposition

The recovery branch is a published review candidate, not an approved release.
Useful implementation work is preserved in coherent commits, Goal 1/4/6
candidate contracts are proven, and Goal 8 is correctly isolated as external
debt. Internal Goals 0/2/3/5/7 and the global delivery receipt remain open.

Do not merge to `main`, delete classified evidence branches, deploy the
candidate, or enable the Sber profile until the corresponding receipts above
are closed explicitly.
