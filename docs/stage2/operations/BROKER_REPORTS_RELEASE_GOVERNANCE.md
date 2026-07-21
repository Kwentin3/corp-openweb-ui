# Broker Reports Release Governance

Status: `AUTHORITATIVE_RELEASE_POLICY_V2`
Date: 2026-07-21

## Source of truth

The canonical working tree is the sole registered `corp-openweb ui` worktree.
Its absolute path is operational detail and must never enter safe reports. Only
one worktree is allowed for this program.

`main` is the authoritative accepted lineage. Each internal engineering goal is
implemented on its own branch, reviewed through its own pull request and merged
normally into `main`; force pushes and history rewrites are forbidden. A stage
release may use an immutable release-candidate commit whose parent is the current
`origin/main`, provided that commit is later made reachable from `main` through
the same reviewed delivery contour.

The accepted baseline and the exact ownership of completed capabilities are
recorded in:

- `docs/reports/2026-07-21/BROKER_REPORTS_GOAL0_ACCEPTED_BASELINE_CONSOLIDATION.report.md`;
- `docs/reports/2026-07-21/BROKER_REPORTS_ACCEPTED_BASELINE.v2.safe.json`.

The historical architecture-recovery branch is retained as evidence for
rejected and incomplete unique commits. It is not a development or release
source and must not be merged wholesale.

## Stage relationship

Stage is approved only when every project-owned live object has exact readback
against one declared release manifest and Git revision. Required objects are:

- the pinned OpenWebUI image and private-intake contract label;
- the protected Broker Reports private-intake Action;
- Gate 1, Gate 2 source and Gate 2 domain Function bundles;
- all managed Broker Reports prompts;
- the static loader;
- runtime dependency and provider-policy identities;
- release valve and workload-authority settings;
- a private rollback identity.

The maintained atomic procedure is
`docs/stage2/operations/BROKER_REPORTS_ATOMIC_STAGE_RELEASE.v1.md`. Independent
Functions must never be updated as three unrelated live mutations for a release.

The accepted private-intake image remains pinned unless a goal explicitly
requires a compatible replacement. Reusing the exact image is preferable when
all new runtime code is delivered as closed-world Function bundles and its
dependency contract still passes.

## Release decisions

- Visual VLM is default-off unless a release decision explicitly enables the
  accepted review-assisted contour.
- Provider output and provider consensus have zero canonical authority.
- Automatic visual-table publication remains disabled. A source-bound review
  receipt and valid seal are mandatory for canonical promotion.
- Sber remains default-off and customer-holdout-gated.
- Unfinished or externally blocked work is not included to manufacture a global
  success status.

## Privacy and evidence retention

- `.env`, `local/`, `audio/`, `_private_test_corpora/`, `secrets/` and
  `docs/out/` remain ignored and untracked.
- Raw provider responses, customer values, crops, ArtifactStore payloads,
  credentials, Function owner IDs and private paths are forbidden in commits and
  safe reports.
- The repository history disposition and its known historical private material
  are governed by the accepted Goal 0 receipt. Later deletion or redaction does
  not falsely claim that immutable reachable history was rewritten.
- Rollback content remains private on stage with restrictive permissions. Only
  its cryptographic identity is safe-reportable.
- A name/path scan cannot prove that an unknown binary is non-customer data
  without an authoritative customer hash registry; no stronger claim is made.

## Required release receipt

The final dated receipt records:

1. the release candidate revision, final `main` merge revision and pull request;
2. clean-tree and one-worktree status;
3. exact image, Function, Action, loader and prompt hashes;
4. provider-policy version, model IDs and release valve states;
5. atomic transaction and exercised rollback identities;
6. private-intake and bounded safe stage smoke results;
7. Knowledge, RAG, vector and repository-sink before/after deltas;
8. repository/live parity, cleanup and quiescence;
9. the independent Sber external holdout status.

Branch deletion, merge to `main` and cleanup are terminal delivery actions after
the safe receipt is complete. External customer acceptance debt remains separate
from internal release correctness.
