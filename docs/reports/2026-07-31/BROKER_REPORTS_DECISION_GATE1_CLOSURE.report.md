# Broker Reports Decision Gate 1 Closure Report

Date: 2026-07-31

Branch: `refactor/broker-reports-kt1-architecture-stabilization`

Base: `origin/main@9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

Remediation evidence head:
`6c447f431e6f998dc6e3222824f82afcddf6e6c8`

Closure state head:
`09e3c6903240924f94ef293f9520617a69b79bcb`

Status:

```text
DECISION_GATE_1: CLOSED
KT2: NOT_STARTED
```

## 1. Accepted program-owner decisions

```text
preferred_option = A
reserve_option = B_IF_DISTINCT_DOMAIN_IS_PROVEN
pr_232_disposition = CLOSE_AFTER_EXTRACTION
owner_context_policy = SIDECAR_OWNER_METADATA
live_parity_checkpoint_authorized = true
historical_v3_schema_hash_fix_deferred = true
kt2_authorized = false
```

Option A evolves the existing source-fact product boundary and reuses the
current Gate 2 package, source grounding, type authority, Choice/Expansion,
canonical validator/materializer, ArtifactStore, and evidence/replay owners.
Option B is reserve-only and requires proof of a distinct business domain.

This closure is not KT2. It adds no Type-First implementation or projection,
does not transfer PR #232 code, and changes no product/runtime/provider/live
route.

## 2. Production-source remediation

The earlier KT1 draft added nine architecture boundary blocks and one
historical containment block across nine production Python files. All ten
blocks were removed. Each affected production file now matches its
`origin/main` authority; executable logic was not edited.

No pinned hash was updated. No historical contract or evidence was rewritten.
The three generated Function bundles were rebuilt for verification and
produced an empty Git diff.

Accounting:

| Item | Result |
| --- | ---: |
| architecture boundary blocks removed | 9 |
| historical containment blocks removed | 1 |
| affected production files restored | 9 |
| production behavior changes | 0 |
| generated bundle changes | 0 |
| historical hash updates | 0 |

## 3. Owner-context authority

Architecture context moved to:

- `docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`;
- `docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.md`.

The JSON sidecar contains 15 complete owner entries. It covers visual
execution/validation, logical-table materialization, Gate 2 packaging,
current and historical source-fact routes, type and Choice/Expansion
authorities, canonical validation/materialization, evidence/replay,
ArtifactStore/Resolver, AnswerContext, Gate 3 manifest, and release/live
parity.

The historical `source_fact_selection_v3` entry is
`HISTORICAL_READ_ONLY`; product and provider reachability are `FORBIDDEN`;
only replay, validation, and historical evidence are allowed. Reactivation
requires a new ADR, qualification, and explicit product decision.

PR #232 is recorded only as an external candidate:

```text
external_candidate_reference = PR_232
current_main_status = NOT_PRESENT_AS_IMPLEMENTATION
approved_reuse_scope = contract_and_test_ideas_only
```

The Pre-Task protocol reads the sidecar, and the code-comment policy reserves
source comments for necessary non-obvious local invariants that preserve hash
and bundle parity.

## 4. Architecture invariants

`test_broker_reports_kt1_architecture_stabilization.py` now has 17 tests for:

1. sidecar existence;
2. all required owner entries;
3. symbols present in maintained code;
4. valid domain/status/ADR references;
5. matrix/sidecar consistency;
6. historical read-only status;
7. forbidden historical product/provider reachability;
8. GOAL 17 absent as a current main implementation;
9. PR #232 reuse limited to contract/test ideas;
10. one future semantic route;
11. one canonical materializer;
12. one type authority;
13. one evidence/replay authority;
14. AnswerContext after completed Gate 2;
15. live parity debt blocking qualification/activation claims;
16. no production boundary-comment requirement;
17. no new owner module.

Result: `17 passed`.

## 5. Test, byte-parity, and integrity evidence

Local mandatory evidence:

| Check | Result |
| --- | --- |
| eight generated managed-asset/source-authority builders | all `status=passed` |
| three generated Function bundles | rebuilt; exact Git diff empty |
| KT1 architecture suite | `17 passed` |
| ArtifactStore, Gate 1/2 bundle, historical, AnswerContext, visual-table, atomic-release, privacy/integrity affected selection | `200 passed, 5 warnings` |
| baseline Ruff correctness | passed |
| compileall | passed |
| `git diff --check` | passed |

The five warnings are existing SWIG/PyMuPDF deprecation warnings; they are not
skips or assertion failures.

GitHub Actions run
`https://github.com/Kwentin3/corp-openweb-ui/actions/runs/30607772132`
completed `SUCCESS` on exact remediation head `6c447f4`:

| CI selection | Result |
| --- | --- |
| generated assets | passed |
| generated Function bundle parity | passed |
| Ruff | passed |
| Context V2.1 / GOAL 16 anti-drift | `338 passed, 3 skipped` |
| explicit workflow `-k context_v2_1` slice | `9 passed, 41 deselected` |
| focused Broker Reports selection | `189 passed, 5 warnings` |

The 41 deselections are the workflow's explicit `-k context_v2_1` selection,
not failure suppression. The three existing skips are historical builder
guards outside the complete GOAL 14, GOAL 15, and GOAL 16 change sets. KT1
adds no skip.

Acceptance totals:

```text
byte_parity_failures = 0
goal16_source_hash_failures = 0
architecture_failures = 0
setup_errors = 0
```

## 6. PR #232 extraction and closure

The 20-row extraction ledger is committed at:

`docs/stage2/architecture/BROKER_REPORTS_PR232_EXTRACTION_LEDGER.v1.md`

It preserves useful contract/test ideas and all five historical commit
references while forbidding the synthetic projection, separate runtime/Pipe/
coordinator, generated bundles, valves/admissions, and duplicate authorities.

PR #232 final state: `CLOSED_WITHOUT_MERGE`.

Closing comment:
`https://github.com/Kwentin3/corp-openweb-ui/pull/232#issuecomment-5139774270`

The comment records Option A, preserved ideas, that closure is not a code
quality rejection, that the separate route is rejected, and that any future
KT2 must start from then-current `main`. The historical branch is retained.

## 7. Live parity and KT2 boundary

Live debt remains:

```text
LIVE_BUNDLE_PARITY_REPAIR_REQUIRED
```

The program owner authorized a separate live parity checkpoint; this package
does not execute it. There were no live reads, rebuilds, deployments,
Function changes, prompt/valve/admission changes, or provider calls.

The architecture is ready for a future KT2 task to be formulated against
then-current `main`, but KT2 is not authorized and no KT2 implementation has
started.

## 8. Dirty-tree and canonical report delivery

The primary Workspace checkout was already dirty on
`feat/broker-reports-goal-17-type-first-inactive`, with six unrelated
untracked 2026-07-30 report artifacts and an untracked 2026-07-31 report
directory. It was not cleaned, switched, rebased, merged, or used for code
edits.

Closure work was isolated in the existing KT1 delivery worktree. The two
updated KT1 reports and the three Decision Gate 1 closure artifacts are copied
into the canonical `docs/reports/2026-07-31/` directory in the primary
Workspace. Unrelated dirty-tree artifacts remain untouched.

## 9. Final accounting

| Category | Total |
| --- | ---: |
| provider calls | 0 |
| product logic changes | 0 |
| runtime changes | 0 |
| OpenWebUI core changes | 0 |
| Pipe/Action behavior changes | 0 |
| feature valve changes | 0 |
| production admission changes | 0 |
| Semantic Pack changes | 0 |
| generated bundle changes | 0 |
| historical hash updates | 0 |
| live changes | 0 |
| KT2 implementation changes | 0 |

```text
DECISION_GATE_1: CLOSED
KT2: NOT_STARTED
```
