# G5.77 — Contract Composition & Stage-Aware Anti-Drift Hardening

## Outcome

The maintained architecture now states one composition rule: a requirement has
a named consumer, an earliest required stage and a minimal blocking scope. A
local requirement cannot become a global pipeline blocker without a documented
dependency. Closure-action order is not a dependency graph.

```text
BROKER_REPORTS_MENTAL_MODEL_COMPOSITION_HARDENED
STAGE_AWARE_CONSUMER_MAP_PROVEN
REQUIREMENT_NOT_GLOBAL_BLOCKER_FROZEN
CLOSURE_ORDER_NOT_DEPENDENCY_ORDER_FROZEN
EVIDENCE_HORIZON_SEMANTICS_FROZEN
USER_FACT_STAGE_CONSUMERS_EXPLICIT
BLOCKING_GRANULARITY_AUDITED
SOURCE_HAS_IT_ROUTING_CONTRACT_HARDENED
METADATA_SUPPORTING_ONLY_PRESERVED
RESEARCH_AUTHORITY_DRIFT_BLOCKED
COLD_AGENT_ANTI_DRIFT_10_OF_10
```

Product semantics were not changed. The only maintained-code change is a short
Declaration Preparation comment that records the already-observed ordering
invariant. Gate 5 calculation, source facts, metadata, projection and release
behavior were not changed.

## Stage-aware result

| Input or gap | Earliest actual consumer | Minimal scope |
| --- | --- | --- |
| `taxpayer_identity_confirmed` | declaration identity in Declaration Preparation | taxpayer-period identity and later release |
| `residency_evidence` | residency methodology where period status matters | residency-dependent tax semantics |
| `signer_and_representation` | declaration semantics / release | signer obligation and release only |
| `filing_instance_identity` | declaration semantics / release / target context | filing instance, release and projection context |
| historical acquisition outside supplied window | Gate 5 calculation | dependent exact `(asset, currency)` group |
| source literal with missing role | Gate 3 -> Gate 4 production owner | one source fact |
| present literal with decimal failure | Gate 4 normalization owner | one source value/fact |

No authority conflict was found among the named maintained contracts. Pipeline
Gates is the navigation authority; domain contracts narrow it; factories/public
APIs are executable boundaries; dated G5.x reports remain evidence only.

## Granularity and source routing audit

The current securities unit is an exact `(asset, currency)` group. The existing
independence guard proves that one incomplete group does not erase a calculation
from another complete group. Therefore `80 ready / 16 incomplete / 0
calculations` in G5.76 is not itself a granularity violation: none of the active
groups had a complete required FIFO input set.

The read-only current-case replay still localizes a separate runtime violation:

| Current reason | Findings | Current closure | Contract owner |
| --- | ---: | --- | --- |
| `gate5_source_fact_required_role_missing` | 13 | `ADDITIONAL_DOCUMENT` | Gate 3 -> Gate 4 source-fact production |
| `gate5_source_fact_decimal_invalid` | 3 | `ADDITIONAL_DOCUMENT` | Gate 4 normalization |

G5.77 intentionally does not repair these 16 incidents. The maintained contract
now makes the wrong user/document route explicit and reserves
`UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW` and
`NORMALIZATION_OWNER_REVIEW` for the bounded remediation. The observable
runtime fix and its runtime guard belong to the next feature GOAL.

## Verification

- Cold agent: `10/10`, no G5.x reports or conversation history used.
- Focused composition suite: `66 passed`.
- Exact high-risk checks: `3 passed` for independent-group granularity,
  signer/filing actions with a preserved calculation, and G5.74 metadata
  non-authority.
- Python compile and Ruff: passed. The two known `F402` findings in the
  pre-existing deterministic module were excluded from this scoped lint run.
- Financial canary through
  `Gate4FinancialCaseRuntimeFactory.create.rebuild_case`: Holdout A `39 -> 39`,
  Holdout B `129 -> 129`, exact hashes unchanged at the frozen valid clock.
- Current routing replay was read-only: source store unchanged; `13 + 3`
  findings reproduced.
- Expanded legacy suite: `68 passed`; six failures and six fixture errors all
  stop before G5.77 at `gate5_e2e_gate2_canonical_missing`. The affected fixture
  files are pre-existing untracked work and were not changed in G5.77.

Safe replay artifacts:

- `BROKER_REPORTS_CONTRACT_COMPOSITION_G5_77.current-routing.safe.json`
- `BROKER_REPORTS_CONTRACT_COMPOSITION_G5_77.current-actions.safe.json`

Private evidence remains outside Git under
`.codex/private-evidence/broker-reports-g5.77-20260816-v1/`.

## Focused commit preparation

The focused commit cannot be attached safely to the current branch yet. The required
Gate 5 contracts, runtime modules and tests are still untracked prerequisites
from earlier GOALs, while Pipeline Gates and Architecture Authorities already
contain large unrelated user-owned modifications. Committing whole files would
pull prior work into G5.77; staging only G5.77 hunks would create a commit whose
parent lacks its dependencies.

No main-worktree files were staged, no branch commit was created and no push was
attempted. Instead, Finish Contract item 29 is prepared as one isolated real Git
commit plus a verified `git format-patch`:

The subject is `docs(broker-reports): harden stage-aware consumer contracts`.
The exact commit identity, file count and patch hashes are kept in the private
focused-commit manifest so the report itself does not create a self-referential
commit hash. `git am` and result-tree equality both pass.

The raw focused patch also passed reverse-check against the current selected
files, forward-check against the reconstructed prerequisite baseline, and exact
round-trip comparison. The main index stayed untouched. The commit manifest and
patches live in the private G5.77 evidence bundle; the public allowed/excluded
scope remains in
`BROKER_REPORTS_CONTRACT_COMPOSITION_G5_77.commit-plan.safe.json`.

```text
FOCUSED_ARCHITECTURE_HARDENING_COMMIT_PREPARED
MAIN_BRANCH_APPLICATION_PENDING_PREREQUISITE_BASELINE
```
