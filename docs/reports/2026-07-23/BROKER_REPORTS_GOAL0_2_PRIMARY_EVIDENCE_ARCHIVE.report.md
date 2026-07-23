# Broker Reports — Goal 0–2 Primary Evidence Archive

Date: 2026-07-23

Branch: `codex/broker-reports-goal0-2-evidence-archive-v1`

Archive status: `COMPLETED_WITH_EXPLICIT_GAPS`

## Archive rule

This report indexes the original evidence; it does not rewrite it. The Goal 1
and Goal 2 primary reports correctly recorded `NOT_CLOSED` outcomes at their
execution time. Their later correction and completion evidence is cross-linked
separately. No late summary is presented as a primary receipt.

All six original files still have the exact Git blobs introduced by their
original commits. SHA-256 values below are calculated from canonical Git blob
bytes, so they are independent of checkout line-ending conversion.

## Goal 0 — source-only control vector

Primary evidence: `FOUND`.

- Original branch:
  `codex/broker-reports-workflow-goal0-control-vector-v1`.
- Evidence commit:
  `427b66f67dc4071e42a95389816a5d28992326c1`.
- Commit time: `2026-07-22T18:38:47+03:00`.
- PR: `#21`; merged at `2026-07-22T15:39:28Z`.
- Merge commit:
  `4f7551f07f09ecec95030e5e0eadb771ed680d65`.
- Primary report Git blob:
  `e5c94a4b5639a3128e94a7e61ccee6400846990e`.
- Primary report SHA-256:
  `ba7833428fb8c7d2a1c10d1a9aaeac12fbca3e163cc4b98424b81c0273975291`.
- Safe receipt Git blob:
  `7482f652a0c0f826d7de2e4c0bfece56d8440c87`.
- Safe receipt SHA-256:
  `5770d805b3b870b22ebced1c2f3b2a818ea1b845a6515b900666297adbe196c8`.
- Private reference SHA-256:
  `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`.
- Private reference seal SHA-256:
  `607000fb3a42ba1cacfd081af29c2b6dbe79ad9d181bfa0a8b4de82a11d6431d`.
- Sealed at: `2026-07-22T15:36:12.210550Z`.
- `sealed_before_workflow_execution`: true.
- Runtime revision: not applicable; this was the pre-runtime source-only
  control operation.
- ArtifactStore refs: not applicable; the sealed reference is deliberately
  outside the runtime and ArtifactStore.

The primary report proves three metrics selected before the answer run,
delegated-agent authority, direct source review, semantic visual-table origin,
no provider-derived truth and no expected-value exposure to runtime.

Original files:

- [report](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL0_SOURCE_CONTROL_VECTOR.report.md)
- [safe receipt](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL0_CONTROL_VECTOR.receipt.safe.json)

## Goal 1 — representation selection

Primary evidence: `FOUND`, with the primary outcome preserved as `NOT_CLOSED`.

- Original branch:
  `codex/broker-reports-workflow-goal1-context-selection-v1`.
- Evidence commit:
  `68da7417a19aee410c12838db77d52692bfed3e3`.
- Commit time: `2026-07-22T18:52:09+03:00`.
- PR: `#22`; merged at `2026-07-22T15:54:30Z`.
- Merge commit:
  `6baa8e3fc3c892b4a48ac5ec5d7130ff49f28be9`.
- Primary report Git blob:
  `ea21417ae23f6481ee2a2abaa0c88ad1850ebaf4`.
- Primary report SHA-256:
  `7b0fccd7d4ac63bcff2edc0765fd335405238f89696db485690072cb43322963`.
- Safe receipt Git blob:
  `a3f82d78e6baa2947c5526a910cd029525f1a953`.
- Safe receipt SHA-256:
  `3e77a008b6a491e8650f7c377fcabaeb5bf4653515c747637f565d1c27303b64`.
- Private audit SHA-256:
  `6fbe5ec56cc8c5c9f46bbad23bca882ecd70736b3862f2cd57b116d94e492f04`.
- Audited repository/live runtime revision:
  `4f7551f07f09ecec95030e5e0eadb771ed680d65`.
- Exact execution time: `GAP`; the primary audit contains the date and the
  publication commit has an exact timestamp, but the audit payload has no
  immutable execution timestamp.
- Original answer-context ArtifactStore ref: none. The primary audit measured
  zero final answer-context payloads, which was the defect it reported.

The missing boundary was later implemented in Goal 5A, then validated in the
final live run. The later completion does not alter the original finding.

Original files:

- [report](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL1_CONTEXT_REPRESENTATION_SELECTION.report.md)
- [safe receipt](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL1_CONTEXT_SELECTION.receipt.safe.json)

## Goal 2 — native user workflow

Primary evidence: `FOUND`, with the primary outcome preserved as `NOT_CLOSED`.

- Original branch:
  `codex/broker-reports-workflow-goal2-native-user-workflow-v1`.
- Evidence commit:
  `4516778d45da9c5bdf56e626013eaac9348f1aa4`.
- Commit time: `2026-07-22T19:46:17+03:00`.
- PR: `#24`; merged at `2026-07-22T16:47:22Z`.
- Merge commit:
  `62fa71e4f401a8fd04b795688c0c17567a5c6d68`.
- Primary report Git blob:
  `e60b4d50449fb10fdb4834ee426ca34c3e4b28cd`.
- Primary report SHA-256:
  `0e7e78179912896284eb62f33367bb05a72afd862e7d399a18dd4a449c65d304`.
- Safe receipt Git blob:
  `6905223e34650e0655d15670ab2928e9b6d36b20`.
- Safe receipt SHA-256:
  `04902d703ce6022d0a854ed439477fb68fc6461d56386764b8b052bcf348bbf4`.
- Repository audit revision:
  `a68ac222ec77b034990625a6e275ce1648f7be51`.
- Private source identity: present in the safe receipt as a SHA-256 only.
- Separate private run-receipt identity: `GAP`.
- Exact execution time: `GAP`; only the date and publication time are
  retained.
- Exact live runtime source revision: `GAP`; the primary receipt stores the
  repository audit revision, not an independently attested live source
  revision.
- Original ArtifactStore refs: `GAP`; the receipt safely preserves the
  measured delta of 40 records and two domain-context packets, but not their
  individual refs.

Those gaps prevent reconstruction of the exact failed-run object identities.
They do not change its primary conclusion: one native task admitted two Gate 1
workloads, so the audit failed closed before the control question.

The duplicate execution was addressed by later isolated correction slices and
the final live run proved one authoritative path, zero duplicate presented
facts and zero Knowledge/RAG/vector delta.

Original files:

- [report](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL2_NATIVE_USER_WORKFLOW.report.md)
- [safe receipt](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL2_NATIVE_USER_WORKFLOW.receipt.safe.json)

## Later completion chain

The later evidence is closure evidence, not a substitute for the primary
reports:

- Goal 1 correction:
  [Goal 5A report](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL5A_CONTEXT_SELECTION_CORRECTION.report.md).
- Authoritative checksum:
  [Goal 3 receipt](../2026-07-22/BROKER_REPORTS_WORKFLOW_GOAL3_SEMANTIC_CHECKSUM.receipt.safe.json),
  introduced by PR `#45`.
- Final prior-program closure:
  [closure receipt](../2026-07-22/BROKER_REPORTS_WORKFLOW_FINAL_LIVE_REPROOF_AND_CLOSURE.receipt.safe.json),
  introduced by PR `#46`.

Cross-hashed late evidence:

| Evidence | Git blob | SHA-256 |
|---|---|---|
| Goal 3 semantic checksum receipt | `92a6da957447f2483a6b196db44e3f01b90211c2` | `1278e65c9ab71c3baa69f63378667777d988665b72338948dba9b71ecf623750` |
| Final live closure receipt | `4ea4f2e91f99f9f1a53bade7481409de07d5dcf2` | `a982cae7a8349ee57b769f5f5e37ddf6bf055b3bdfc05993f2fbc1d4230f5897` |

The later completed run links:

- Gate 2 run ref: `art_TnEoBnCY04zQWaBHoXABfd4IAZHQJnNF`;
- answer-context ref: `answerctx_9c3d061c120cb6e4ad76c3f6`;
- answer-context integrity hash:
  `b422b312b6f7f3de2c6911c17f83a7b6af2c62a62549f10a65eb55a00fafeef8`;
- private checksum receipt SHA-256:
  `9fd71077755df65450bb8c5dff163bc9736242d8485d8a5fa11b7dce1dbc1084`.

These refs belong to the later successful run and are not attributed to the
earlier failed Goal 1 or Goal 2 executions.

## Privacy and integrity

- All three private identities that can be independently checked match the
  hashes in the primary reports.
- Private evidence remains under ignored `local/`.
- Tracked files below `local/`: `0`.
- Repository privacy guard: `3 passed`.
- Original primary evidence files modified by this archive: `0`.
- Late summary presented as primary: `0`.
- Customer labels or values added to Git: `0`.
- Final receipt cross-hash: `PASSED`.

GOAL_1_PRIMARY_EVIDENCE_ARCHIVE:
`COMPLETED_WITH_EXPLICIT_GAPS`.
