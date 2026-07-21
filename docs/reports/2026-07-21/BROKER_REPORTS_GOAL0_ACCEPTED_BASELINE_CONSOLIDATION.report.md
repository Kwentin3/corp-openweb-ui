# Broker Reports Goal 0 - Accepted Baseline Consolidation

Status: `COMPLETED`

Evidence date: `2026-07-21`

Repository: `Kwentin3/corp-openweb-ui`

Delivery PR: `assigned on publication`

Machine receipt: `BROKER_REPORTS_ACCEPTED_BASELINE.v2.safe.json`

Authoritative capability source revision:
`3cb56847dd9a62dd539a327d9b3769c99bd065ed`

## Terminal verdict

The accepted Broker Reports development baseline is one selective, reviewable
`main` lineage. At freeze, local `main` and `origin/main` were exactly
`3cb56847dd9a62dd539a327d9b3769c99bd065ed`, the worktree was clean, and the
repository had one canonical worktree. PRs `#2`, `#3` and `#4` are the normal
merge contour for clean integration, private intake and maintained dual-VLM
runtime respectively.

This Goal 0 change adds only the baseline receipts. It does not change product
code, runtime assets, bundle contents or stage. The final normal merge of this
documentation branch becomes the new `main` tip without changing the accepted
capability tree described by the source revision above.

## Exact accepted capability ownership

| Capability | Authoritative owner revision(s) | Primary anchors |
| --- | --- | --- |
| repository privacy and governance guards | `113443b`, `9807b35` | privacy regression guard; release governance; private-link quarantine |
| architecture and anti-drift authority | `75e4dd8`, classification update `27bffa8` | architecture blueprint; `architecture_policy.py`; architecture test |
| batched CSV/table source resolution | `e2995aa` | `source_provenance.py`; `table_projection.py`; equivalence tests |
| ArtifactStore lifecycle and retention scope | `f72e63b`, `9fe7d5d` | artifact models/store/resolver; lifecycle and retention tests |
| Sber default-off release gate | `5e1d279`, `c62d25e` | customer-debt contract; `customer_debt_policy.py`; gate test |
| deterministic closed-world bundles | `f94abcd`, dual-VLM extension `27bffa8` | bundle builder and Gate 1/Gate 2 bundle tests |
| server-authoritative private intake | `e7ee80a` through `e6255bf`; receipt `eed4e2f`; merge `e16bca1` | intake contract/router/patcher; signed Action; delivery and invariant tests |
| maintained dual-provider VLM runtime | `27bffa8`; delegated seal `5781547`; merge `3cb5684` | runtime contract, provider factory, deterministic validator and reference tests |

Every listed owner is an ancestor of the authoritative source revision. The
machine receipt contains full SHAs and exact anchor paths.

The accepted `document_memory.py` lineage at `47255bf` and `a8d8b1f` remains
part of the longstanding Gate 1 supported source-evidence profile. It is not
the excluded optimization at `d3a1267`. Removing it by name would destroy an
accepted capability and is therefore explicitly rejected.

## Explicitly absent recovery work

The recovery evidence branch remains reachable, but these commits are not
ancestors of the authoritative source revision:

| Recovery revision | Disposition | Direct absence proof |
| --- | --- | --- |
| `d3a1267` | incomplete Gate 1 graph/memory optimization | current factory retains copy-on-write; no `copy_package` route |
| `a460c81` | scheduler/admission scaffold | `workload_admission.py` and its test are untracked/absent |
| `d7cc52d` | rejected duplicate VLM scaffold | `visual_table_vlm.py`, its parallel contracts and duplicate test are absent |

No generated bundle contains those module names. The earlier incomplete
private-intake prototype at `0f9c950` also remains outside `main`; the accepted
Goal 2 implementation is a separately reviewed, authenticated v2 lineage and
must not be confused with that rejected prototype.

Unfinished atomic-release artifacts are not claimed. Atomic stage delivery is
a later goal, and no partial release artifact was introduced here.

## Complete test-delta accounting

Collection was independently repeated from detached temporary worktrees for
all three accepted merge points; every temporary worktree was removed.

| Snapshot | Collected | Passed | Maintained skips |
| --- | ---: | ---: | ---: |
| recovery evidence `230fd02` | 1055 | 1035 effective | 20 |
| clean integration `8037f7d` | 950 | 930 | 20 |
| private intake `e16bca1` | 967 | 947 | 20 |
| dual-VLM baseline `3cb5684` | 991 | 971 | 20 |

The recovery-to-clean transition is the already proven `-105` net delta: 106
recovery-only node IDs received explicit dispositions (60 excluded
experimental, 32 rejected duplicate architecture, 14 private proof tooling),
and one current-tree privacy regression test was added.

Private intake then added 17 node IDs and removed none. Dual-VLM added 26 node
IDs and replaced two names, for a net `+24`:

- broad visual classification became exact visual-component classification;
- research allowlist rejection became qualification-allowlist rejection.

Those are strengthened in-place checks, not lost behavior. Therefore the
end-to-end collection identity is `1055 - 105 + 17 + 24 = 991`, with no silent
coverage loss.

Current-tree verification:

- full suite: `971 passed`, `20 skipped`, `0 failed`, 5 known SWIG/PyMuPDF
  deprecation warnings;
- focused privacy, architecture, table projection, ArtifactStore, retention,
  Sber gate, private intake, dual-VLM and closed-world bundle suite:
  `145 passed`, `0 skipped`, `0 failed`.

All 20 skips retain the explicit offline-private-benchmark reason. No test,
expectation, timeout, validator or terminal outcome was weakened.

## Deterministic closed-world bundle proof

Two consecutive maintained `--target all` generations produced identical LF
bytes:

| Bundle | SHA-256 |
| --- | --- |
| Gate 1 | `0b9020a7f8deceb0d1639e2038850b84c2fd26fd80a0028322f5c93189988442` |
| Gate 2 source | `f11ace003701dd1001c119efe599ae283ffa8d5caf9ab8a7c1824ac62c69b458` |
| Gate 2 domain | `3193b8b4b4cd154ba40550b51ac3c3b31d587a87016c7d4d90f0f39b2e72b50a` |

The generated bytes match the last accepted dual-VLM receipt. Windows checkout
bytes initially used CRLF; generation normalized them to LF, so raw worktree
hashes changed while `git diff --ignore-space-at-eol` remained empty. The three
EOL-only worktree changes were restored exactly, leaving no product diff.

All bundle requirements remain closed:

- Gate 1: `pydantic`, `pypdf==6.7.5`, `pdfplumber==0.11.10`,
  `pdfminer.six==20260107`, `PyMuPDF==1.26.5`;
- Gate 2 source/domain: `pydantic` only.

Production Python, Dockerfile, compose and bundle scans found zero PaddleOCR,
PaddlePaddle or Torch imports, installs or requirements. Historical research
reports are evidence, not production dependencies.

## Repository and stage governance

The architecture-recovery branch at `230fd02` is retained as historical
evidence because it owns rejected and incomplete unique commits; it is not a
development or release source. Its old draft PR is superseded by the accepted
normal-merge contour and is closed during Goal 0 publication without deleting
the evidence branch.

Read-only stage inspection reported:

| Item | Value |
| --- | --- |
| configured image | `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f` |
| image ID | `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83` |
| restart count | `0` |
| state | `running`, `healthy` |

No deploy-capable script, Function/Action/prompt update, valve change, image
switch, compose mutation or customer-data operation was invoked.

## Acceptance

`AUTHORITATIVE_DEVELOPMENT_BASELINE: ESTABLISHED`

`COMPLETED_CAPABILITIES: CONSOLIDATED`

`INCOMPLETE_SCAFFOLDS: ABSENT`

`TEST_DELTA: FULLY_EXPLAINED`

`ACCEPTED_CAPABILITY_COVERAGE_LOSS: ZERO`

`DETERMINISTIC_BUNDLES: PASSED`

`PADDLE_PRODUCTION_DEPENDENCY: ZERO`

`STAGE_MUTATION: ZERO`

`GOAL_0_ACCEPTED_BASELINE_CONSOLIDATION: COMPLETED`

Goal 1 of the remaining engineering set was not started by this receipt.
