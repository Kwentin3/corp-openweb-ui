# Broker Reports Release Governance

Status: `AUTHORITATIVE_RELEASE_POLICY_V1`; repository-governance gate: `NOT_CLOSED`
Date: 2026-07-21

## Source of truth

The canonical working tree is the sole registered `corp-openweb ui` worktree.
Its absolute path is operational detail and must never be copied into safe
runtime reports.  Only one worktree is allowed for this program.

The authoritative recovery integration branch is
`codex/broker-reports-architecture-recovery-v1`, forked without rewriting from
accepted audit revision `7ba45b1d461a6b9056fe7cc1798ef79196edfa1a`.
All implementation, verification, bundle generation and delivery must use this
same tree and branch.  `main` remains the upstream review boundary until the
release branch passes every internal goal that can be closed; landing is a
fast-forward/normal reviewed merge, never a force push or history rewrite.
This branch is a release candidate, not an approved release, while the
reachable-history privacy blocker below remains open.

Stage runtime may be called approved only when every deployed project-owned
file or managed bundle has an exact SHA-256 match to this release branch and its
generating commit is reachable from the branch.  The pinned upstream OpenWebUI
image is a separately identified build input; managed Function records are not
permission to deploy source from an unnamed branch.

## Branch and commit ownership

Inventory at the recovery fork point:

| Branch/ref | Relation to `7ba45b1` | Classification | Disposition |
| --- | --- | --- | --- |
| `codex/broker-reports-runtime-audit-v1` | exact fork point; 37 commits ahead of `origin/main` | accepted audit and measured baseline | retained until recovery release lands |
| `codex/broker-reports-blocker-closure-v1` | ancestor, 16 commits behind | accepted runtime/visual closure | fully integrated; safe to delete after release lands |
| `codex/pdf-table-intake-gate1-closure` | ancestor, 64 commits behind | accepted bounded intake capability | fully integrated; safe to delete after release lands |
| `codex/pdf-dual-vlm-fact-benchmark` | ancestor, 69 commits behind | accepted research evidence, no production authority | history integrated; branch safe to delete after release lands |
| `codex/pdf-table-strategy-benchmark` | ancestor, 75 commits behind | accepted research evidence | history integrated; branch safe to delete after release lands |
| `codex/vlm-guided-intake-development-gate-repair` | diverged: 79 release commits absent, 3 unique commits | failed/experimental guided-intake evidence | retained and archived as evidence; never merged wholesale |
| `main` / `origin/main` | `cf158fd`; ancestor, 37 commits behind fork point | upstream review boundary | fast-forward or reviewed merge only after program acceptance |
| `old-origin/main` (`corp-hermes`) | `32eb38d`; ancestor, 227 commits behind | historical predecessor remote | historical only; not a release source |

The three unique commits on the retained experimental branch are
`9bd18dd`, `b31c80f` and `9d91390`.  Its terminal report explicitly records a
failed development gate.  Useful research remains reachable; its assumptions
are superseded by the bounded Gemini/OpenAI production policy.  No branch may
be deleted until the release receipt recomputes these reachability relations.

## Stage relationship

The last accepted live readback before this program identified the stage
container fingerprint
`sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175`
and exact repository/live parity for the three maintained Broker Reports
Function bundles plus the static loader.  Those bundle-generating commits are
reachable from the release branch; later documentation/audit commits do not
claim a different runtime.

Any runtime-affecting recovery commit invalidates that receipt until bundle
rebuild, maintained delivery, live readback and exact SHA-256 parity are rerun.
Until then the relationship is `stage = previous accepted runtime`,
`release branch = candidate runtime`, and must not be reported as final parity.

## Privacy and evidence retention

- `.env`, `local/`, `audio/`, `_private_test_corpora/`, `secrets/` and
  `docs/out/` remain ignored and untracked.
- The current candidate tree removes the tracked
  `benchmarks/pdf_table_strategy_v1/reference.private.json` and redacts known
  absolute/local evidence paths from maintained safe outputs.
- Reachable history is **not clean**: commit `82313d8` introduced two reachable
  versions of that private reference, and commit `dcb2351` recorded an absolute
  local path in `probe_summary.json`.  The private reference contains reviewed
  financial-table values and source-reference metadata.
- The program forbids force-push and history rewriting, so a later deletion or
  redaction commit cannot satisfy the reachable-history closure criterion.
  `GOAL_0_REPOSITORY_GOVERNANCE` therefore remains `NOT_CLOSED` unless an
  explicitly approved, non-rewrite disposition is added to the release policy.
- A name/path scan cannot prove that an unknown binary is non-customer data
  without an authoritative registry of customer hashes.  No stronger claim is
  made.
- Raw provider responses, customer values, crops, ArtifactStore payloads and
  local paths are forbidden in commits and safe reports.
- The frozen Sber implementation and its positive-holdout debt remain preserved
  by `docs/contracts/BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md`; branch cleanup
  cannot remove that release gate.

## Release receipt requirements

The final dated governance report must record:

1. authoritative branch HEAD, `origin/main` and ahead/behind counts;
2. all local/remote refs and worktrees, including the retained failed branch;
3. integrated commit ranges and any branch safe-delete decision;
4. stage container/source revision and exact repo/live bundle hashes;
5. prompt parity where prompts changed;
6. clean-tree status and verified-tree = deliverable-tree equality;
7. current-index and reachable-history privacy scans;
8. independent status for the Sber external holdout.

Branch deletion, main integration and stage promotion are terminal release
actions.  They occur only after the receipt can be completed without hiding a
failed internal goal.
