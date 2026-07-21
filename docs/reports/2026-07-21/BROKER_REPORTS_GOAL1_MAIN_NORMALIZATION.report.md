# Broker Reports Goal 1 - Clean Integration Merge And Main Normalization

Status: `COMPLETED`

Evidence date: `2026-07-21`

Repository: `Kwentin3/corp-openweb-ui`

Delivery PR: `#2`

Approved base: `cf158fd38e3fc0a1f195b885ba94cb0094f95537`

Validated candidate head: `40fe47f3d24d75f05185ff0a0c239970c333f052`

Validated implementation head: `f94abcdeb94c0ae07ec09e137d646198c12d9018`

Current live runtime evidence owner:
`7ba45b1d461a6b9056fe7cc1798ef79196edfa1a`

## Terminal outcome

The clean integration is the reviewed development state selected for `main`.
It is a selective descendant of the approved base, not a wholesale merge of
the architecture-recovery or runtime-audit branches. The repository merge is
the only delivery operation in this goal. No stage deployment, Function
update, Action update, image change, prompt update or valve mutation belongs
to this receipt.

The receipt is committed as a documentation-only descendant of the validated
candidate. Its own descendant merge SHA is intentionally not embedded in its
contents; PR `#2` and the Git commit graph are the authoritative merge record.

## Retained clean scope

The selected tree retains:

- repository privacy guards and current-manifest private-link rejection;
- the authoritative Broker Reports architecture and anti-drift guards;
- batched CSV/table source resolution;
- context-bound, idempotent and append-only ArtifactStore lifecycle;
- the Sber actual-corpus implementation receipt, positive-holdout debt and
  default-off release gate;
- deterministic closed-world bundle generation;
- the maintained Gate 1, Gate 2 source and Gate 2 domain runtime contours.

Focused retained-capability verification covered architecture, privacy,
neutral table projection, ArtifactStore and lifecycle, retention scope, Sber
debt policy, Gate 1 pipe behavior and Gate 2 source-fact behavior:

`121 passed, 0 skipped, 0 failed`.

## Explicit exclusions

The selected tree excludes these recovery-only runtime routes:

- incomplete receipt-backed private intake;
- incomplete Gate 1 bounded-memory work;
- scheduler/admission scaffold;
- duplicate visual-table VLM proposal scaffold;
- audit-only visual promotion and handoff modules;
- mixed recovery bundles;
- PaddleOCR, PaddleOCR-VL and local-heavy-OCR production dependencies.

The historical proof script named `live_process_false_private_intake_smoke.py`
is not a server-side intake boundary and is not included in any production
bundle. It does not make the incomplete private-intake runtime deliverable.

## Exact test delta

Collection used the same Windows PowerShell and Python environment for both
trees. The recovery tree was read from an immutable `git archive` snapshot at
`230fd02`; the clean tree was the exact candidate checkout at `40fe47f`.

| Evidence | Recovery | Clean | Delta |
| --- | ---: | ---: | ---: |
| collected tests | 1055 | 950 | -105 |
| effective passed tests | 1035 | 930 | -105 |
| maintained skips | 20 | 20 | 0 |
| recovery-only node IDs | 106 | 0 | -106 |
| clean-only node IDs | 0 | 1 | +1 |

The clean-only test is
`RepositoryPrivacyGuardTest.test_benchmark_manifests_do_not_link_private_evidence`.
It closes a current-tree privacy gap and is additive coverage.

All 106 recovery-only tests have an explicit disposition:

| Allowed disposition | Tests | Exact owning test files |
| --- | ---: | --- |
| excluded experimental code | 60 | archive/XML visual additions (3); audit-only FNS 2-NDFL adapter/parity (12); visual-only input-readiness addition (1); incomplete private intake (12); audit-only visual handoff (5); audit-only visual neutral tables (14); scheduler scaffold (13) |
| rejected architecture | 32 | duplicate `test_broker_reports_visual_table_vlm.py` proposal stack |
| private proof tooling | 14 | Gate 1 actual phase profile (2); Gate 2 capacity (1); controlled benchmark (1); package performance probe (1); restricted-scope stage smoke (1); visual actual phase profile (1); live no-RAG smoke (3); visual byte/source-scope proof (3); actual-corpus reconciliation (1) |
| unavailable external environment | 0 removed | none |
| documented maintained skip | 20 skipped in both trees | offline private benchmark reference is required |

The audit-only FNS and visual tests remain reachable on the runtime-audit and
architecture-recovery evidence branches. They are not classified as accepted
clean-integration capability, so their exclusion is explicit rather than a
silent coverage loss.

### Recovery snapshot failure attribution

The first recovery snapshot execution reported:

`1033 passed, 20 skipped, 2 failed`.

Both failures were in `test_repository_privacy_guard.py`. Expected behavior
was a tracked-file list from `git ls-files`; actual behavior was exit 128,
`not a git repository`, because `git archive` intentionally contains no
`.git` directory. The test runner executed the complete suite; this was not an
assertion mismatch in product behavior and no test or expectation was edited.

A fresh snapshot was populated with a local Git index containing exactly the
archived tree. The same two tests then produced `2 passed`. The effective
recovery result is therefore `1035 passed, 20 skipped, 0 product failures`.
The isolation mechanism was a newly created temporary archive directory and
index; it was not a worktree and it did not alter any repository ref.

## Clean candidate regression result

The exact candidate runtime tree produced:

- `930 passed`;
- `20 skipped`;
- `0 failed`;
- `5` known PyMuPDF/SWIG deprecation warnings.

Every skip is in `test_broker_reports_pdf_table_strategy_benchmark.py` and has
the explicit reason `offline private benchmark reference is required`. The
private reference is deliberately absent from Git. No ENV values were required
or implicitly supplied for the regression run.

The tests assert observable results, persisted lifecycle state, typed terminal
outcomes and fail-closed validation. No tests or production logic were changed
to obtain this result. For this goal, the irreversible boundary is publication
of the merge to shared `main`; all runtime verification completed before that
boundary.

## Deterministic closed-world bundles

Two consecutive `--target all` builds produced identical UTF-8 bytes:

| Bundle | SHA-256 |
| --- | --- |
| Gate 1 | `de9709e78c7503f4a7277c5fad8285a79e3413b2005201a0d890f410c6b442ab` |
| Gate 2 source | `ffeff3c84d3c2a23ad3d6cfcb084d2072f752a5edce5551ffeb407a4efba4488` |
| Gate 2 domain | `9dc6ce4dc22ca0c810b36b1c77761f45b24e7cda7cd6a072738374ade0ec80ca` |

The generated module orders contain zero private-intake, workload-admission,
duplicate-VLM, visual-neutral/handoff or Paddle modules. Bundle requirements
contain no Paddle or other local-heavy-OCR framework. Regeneration produced no
semantic Git diff.

## Privacy verification

- `test_repository_privacy_guard.py`: `3 passed`;
- tracked `*.private.json` and `*.private.sha256.json`: `0`;
- open GitHub secret-scanning alerts: `0`;
- private benchmark values, provider responses and local evidence paths are
  absent from this receipt.

Historical shared commits are not rewritten. Current benchmark manifests use
the safe `external_private_evidence` state and cannot resolve a private file.

## Stage non-mutation receipt

A read-only live verifier ran immediately before repository delivery. It
confirmed all three Functions present and active, all 12 managed prompts
matching, PyMuPDF `1.26.5`, structural/guided/semantic shadows disabled and
table intake still enabled/configured.

| Live Function | Live SHA-256 before merge |
| --- | --- |
| Gate 1 | `9b3895b521d8ec82b486edfba7a3b29cbeb913217fa73aff18783915126bb1df` |
| Gate 2 source | `168a3095ca488f13736ea4655c54df5ec136ebf196c6ab7fa4e1e98f121a3f96` |
| Gate 2 domain | `eb1a98515743e8adda5fa57dfbe5c2f7a57753966fd1b0902f35300ab903a54e` |

These are intentionally the prior accepted runtime bytes owned by `7ba45b1`,
not the new repository bundle hashes. The mismatch is expected because Goal 1
normalizes Git only. No deploy-capable script was invoked.

## Evidence reachability and history policy

The following remote evidence owners were verified reachable before merge:

- runtime audit `7ba45b1`;
- architecture recovery `230fd02`;
- pre-drift dual-VLM tip `203d4ee`;
- guided-intake failed-gate evidence `9d91390`.

The pre-drift dual-VLM tip is also an ancestor of the approved base. No force
push, rebase of published commits, history rewrite or evidence-branch deletion
is part of this goal.

## Acceptance

`MAIN_CONTAINS_CLEAN_INTEGRATION: PASSED`

`DEVELOPMENT_SOURCE_OF_TRUTH: MAIN`

`TEST_DELTA: FULLY_EXPLAINED`

`ACCEPTED_CAPABILITY_COVERAGE_LOSS: ZERO`

`INCOMPLETE_SCAFFOLDS_IN_MAIN: ZERO`

`PADDLE_PRODUCTION_ASSUMPTIONS: ZERO`

`STAGE_MUTATION: ZERO`

`REPOSITORY_HYGIENE: PASSED`

`GOAL_1_MAIN_NORMALIZATION: COMPLETED`

Goals 2-6 are not claimed by this receipt. Sber customer acceptance remains an
external, default-off release gate.
