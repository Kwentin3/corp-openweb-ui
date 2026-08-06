# Broker Reports DOC34 Repository Consolidation

Status: `STALE_BRANCH_CLEANUP_COMPLETE`; delivery merge is pending

Date: 2026-08-06

This report is the privacy-safe accounting record for Gate 2 repository
consolidation. It records repository facts, not customer payloads or private
evidence. The terminal post-merge state is verified in the DOC34 delivery
response because the delivery branch cannot delete itself before merge.

## Authority fixed before cleanup

| Boundary | Current authority |
| --- | --- |
| public schema | `CanonicalArtifactV1` / `canonical_artifact_v1` |
| normalization | `CanonicalNormalizerFactory.create` |
| storage lifecycle | `CanonicalArtifactStoreFactory.create` |
| public read | `CanonicalReaderFactory.create` |
| Gate 2 exit | `BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md` |
| completeness | `assess_canonical_completeness` plus format-specific source accounting |
| evidence | authenticated Gate 1 source and private Full Evidence; never a public reader surface |
| neutral projection | `render_neutral_canonical_projection`, reader-only diagnostic |
| lifecycle | immutable versions, validated reconstruction and CAS activation |
| deployment | closed service package, generated-bundle parity and existing durable data mount |

The current entry point is `docs/stage2/BROKER_REPORTS_GATE2.md`. Numbered DOC
reports, closed PRs, `BROKER_REPORTS_CURRENT_STATE.v1.*` and the checkpoint
below are historical evidence and cannot override the versioned contracts.

## Branch accounting snapshot

Snapshot base: `origin/main` at
`e85fc78e1dbf664c814e6b774122337e2fd8fb64`. Counts are the union of local
branches and `origin/*`, deduplicated by branch name. `ahead` and `behind` are
relative to that base before DOC34 integration.

| Branch | Head | Local / origin | Behind / ahead | Classification | Recovery and deletion decision |
| --- | --- | --- | ---: | --- | --- |
| `main` | `e85fc78e1dbf664c814e6b774122337e2fd8fb64` | yes / yes | 0 / 0 | `AUTHORITATIVE_MAINLINE` | retain; DOC34 merges here |
| `chore/broker-reports-doc34-repository-consolidation` | `0c46311b8837e34ff4367451e902e2ac9887c794` at snapshot | yes / no | 0 / 1 | `ACTIVE_AUTHORIZED_WORK` | delete local and remote after merge |
| `audit/broker-reports-goal-18-gate2-reconciliation` | `91095844bd131a42dc601676e8d03757376ab317` | yes / yes | 82 / 1 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | closed PR 233 preserves intent and head; delete branch |
| `codex/broker-reports-architecture-recovery-v1` | `230fd02d8ae5d6662957d75b3bb6de2c8d21f532` | yes / yes | 562 / 48 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | closed PR 1 preserves the historical recovery line; delete branch |
| `codex/broker-reports-blocker-closure-v1` | `21a08b5dc67f79843dbc4c5c00f96ecdc637e329` | yes / yes | 562 / 21 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | ancestor of PR 1 head; delete branch |
| `codex/broker-reports-gate2-canonical-domain-research-v1` | `38cce3f4f5b741600547af114fb8396becf7f0ae` | yes / yes | 378 / 5 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | closed PR 77 preserves non-authoritative research; delete branch |
| `codex/broker-reports-isolated-goal2-semantic-selection-reproof-v1` | `d65fe7c3b6df2fd1516d87fdf11712cf8f4c7c21` | no / yes | 379 / 0 | `MERGED_AND_DELETABLE` | merged PR 76; delete branch |
| `codex/broker-reports-runtime-audit-v1` | `7ba45b1d461a6b9056fe7cc1798ef79196edfa1a` | yes / yes | 562 / 37 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | ancestor of PR 1 head; delete branch |
| `codex/vlm-guided-intake-development-gate-repair` | `9d9139061edf6f249455a325557b7f4dace1da79` | yes / yes | 604 / 3 | `SUPERSEDED_AND_DELETABLE` | stopped development-gate experiment; retain one recovery tag, delete branch |
| `feat/broker-reports-doc5-1-span-aware-table-recovery` | `80947692366b639f5f00056972373557e99ad197` | yes / no | 9 / 1 | `SUPERSEDED_AND_DELETABLE` | stopped checkpoint superseded by DOC6; retain one recovery tag, delete branch |
| `feat/broker-reports-goal-17-type-first-inactive` | `d6954f401ae4734fc1573c7560c981cf084c278c` | yes / yes | 82 / 5 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | closed PR 232 preserves inactive proposal; delete branch |
| `refactor/broker-reports-kt1-architecture-stabilization` | `5125ebae590d5da9014a4cfe3392afc9231961ae` | yes / yes | 82 / 7 | `HISTORICAL_NEEDS_ARCHIVE_REFERENCE` | closed PR 234 preserves architecture package; delete branch |

Accounting: 12 of 12 branch names classified; 0 unclear owners; 0 unique
required product implementations exist only on a deletable branch. PR URLs are
available through repository PR numbers. The two no-PR stopped experiments use
annotated recovery tags, so branch retention is unnecessary.

The verified stale cleanup removed all ten non-delivery branch names: nine
local refs and nine `origin` refs. Immediately afterward, the only branch names
were `main` and the active DOC34 delivery branch. The latter is deleted after
merge, producing the contracted terminal result of 11 removed and 1 retained.

The configured `old-origin` points to another repository and its `main` is not
a Gate 2 branch. It is excluded from the 12-name project accounting and removed
from the local configuration after verifying its URL and refs. Canonical
`origin` remains `Kwentin3/corp-openweb-ui` and is now the only configured
remote.

## Unique-work checkpoint and artifact hygiene

Before cleanup, safe accumulated DOC7-DOC33 work was preserved as commit
`0c46311b8837e34ff4367451e902e2ac9887c794`: 399 changed paths, comprising 36
modified and 363 added paths. This makes cleanup reviewable and recoverable
without keeping the material in the product tree.

Two historical files failed the repository privacy boundary before that commit.
They were excluded from Git and moved unchanged to the ignored private evidence
contour. Their SHA-256 values are:

- `b291931929ca29b1c476233034e48a02f191e5ac75c36bafcc81b01bf1066e3b`
- `a1140c3e3289ab5222b4340670f14a2dba781857fd7de3a5456934587955f805`

From the checkpoint, 333 reproducible or superseded paths were removed:

| Class | Removed paths |
| --- | ---: |
| numbered reports and safe run receipts | 83 |
| intermediate stage2 JSON/projections | 199 |
| historical snapshot/receipt tests | 31 |
| one-shot research/proof scripts | 13 |
| superseded operations documents | 2 |
| DOC-specific Docker/debug build files | 5 |
| **total** | **333** |

Thirty checkpoint-added product/contract/test paths were retained. Current
contracts and runbooks were reduced to present-tense requirements instead of
DOC29-DOC33 narratives. The immutable GOAL12 execution-lock tag and all
historical builder pins/receipts remain unchanged; only the existing authorized
successor pointer for the maintained authority document was advanced.

## Product and research separation

No product runtime import from historical reports, temporary artifacts or
one-shot proof scripts was found. Cleanup exposed three non-product couplings:

1. an XLSX test imported a DOC30 one-shot helper;
2. PDF tests asserted deleted DOC32 Docker/script snapshots;
3. a dead DOC22 receipt adapter remained in the consumer inventory.

These couplings were removed while the underlying behavioral tests remained.
`canonical_wave2_shadow.py` is explicitly diagnostic and side-effect-free.
Legacy-named financial-semantic and historical PDF modules remain classified
as `LEGACY_PRODUCT_COMPATIBILITY` or `RESEARCH_PROTOTYPE`; legacy removal is
outside DOC34, and the repository guard prevents them from becoming canonical
authority dependencies.

## Documentation, comments and guards

DOC34 adds:

- one current entry page;
- an implementation map from architecture to actual modules/factories;
- a safe-change guide;
- a branch lifecycle contract;
- a Gate 3 boundary handoff;
- focused repository guards wired into `broker-reports-ci`.

High-risk factory, schema, adapter, PDF/XLSX assembly, completeness,
provenance, immutable publication, CAS activation, reader-layout and neutral
projection boundaries now explain the invariant that must be preserved.

The guard blocks a second schema/reader, authority factory bypass, downstream
format branching, empty active artifacts, unresolved provenance, lost content
after persistence, private evidence access, unversioned logical changes,
cross-format table drift, silent fallback and canonical runtime imports from
research/proof/Gate 3 paths.

## Terminal validation before Git closure

- generated managed assets: 10 checks passed, 0 provider calls;
- generated Function bundles: three repeated-build SHA-256 pairs identical;
- Ruff `E9,F63,F7,F82`: passed;
- current Context V2.1 contour: 338 passed, 3 skipped;
- Context V2.1 architecture selection: 9 passed, 41 deselected;
- focused Broker Reports compatibility contour: 615 passed;
- canonical/DOC34 architecture guard: 89 passed;
- full service suite: 2814 passed, 5 skipped, 6 deprecation warnings;
- new unexplained failures: 0.

GitHub exact-head CI and the terminal branch/working-tree counts are recorded
after publication and merge. Wave 2 cutover was not performed and Gate 3 was
not started.

## Strategic answers

1. All 12 Gate 2 branch names are classified in the table above.
2. Eleven are scheduled for deletion: ten stale branches plus the DOC34 branch after merge.
3. Only `main` is intended to remain; no ambiguous active branch exists.
4. Safe DOC7-DOC33 work was checkpointed before cleanup; current product code, adapters, factories, guards and tests remain in the delivery diff.
5. The 333-path aggregate above was removed as reproducible or superseded material.
6. Versioned authority, behavioral tests, immutable tags, checkpoint commit, closed PR refs and two minimal recovery tags are retained.
7. No product runtime research dependency remained; three test/inventory couplings were removed.
8. `docs/stage2/BROKER_REPORTS_GATE2.md` is the entry point.
9. Pipeline Gates, Canonical Artifact, Reader, Storage/Lifecycle and Gate 2 Exit v1 are normative.
10. Comments were added only at contract-sensitive boundaries listed above.
11. The twelve do-not-break invariants are mapped to focused tests and CI.
12. Extend through the existing factories, smallest compatible adapter change, versioned contract and durable/cross-format proof.
13. Gate 3 receives a reader-returned validated artifact and builds its own task-specific projection without source-format knowledge.
14. Intentional debt remains: global canonical reads and Wave 2 are disabled; legacy compatibility modules still exist and are explicitly classified.
15. The repository is prepared for a separately authorized Wave 2 decision and later Gate 3 work; neither is authorized or performed by DOC34.
