# Broker Reports Repository Archaeology And Git Hygiene v1

Status: `COMPLETED`

Evidence date: `2026-07-21`

Approved base: `cf158fd38e3fc0a1f195b885ba94cb0094f95537`

Verified candidate implementation:
`f94abcdeb94c0ae07ec09e137d646198c12d9018`

Machine classification:
`BROKER_REPORTS_REPOSITORY_ARCHAEOLOGY_CLASSIFICATION.v1.safe.json`

VLM report: `BROKER_REPORTS_PRE_DRIFT_VLM_RECOVERY_V1.report.md`

VLM machine map: `BROKER_REPORTS_PRE_DRIFT_VLM_RECOVERY_MAP.v1.safe.json`

## Outcome

Repository source of truth is established without rewriting shared history,
force-pushing, merging audit/recovery branches wholesale or changing stage.
The clean integration branch is
`codex/broker-reports-clean-integration-v1`, based directly on current approved
`origin/main` and selectively carrying only proven slices.

The source archaeology covers 135 unique path-scoped commits across every
local/remote Broker Reports ref. Each commit has an owner, classification and
family in the machine file. Unclassified relevant commits, accepted work
without an owner and unidentified stage sources are all zero.

## Repository freeze

At freeze time:

- local branches: 8;
- `origin` branches: 8;
- historical `old-origin/main`: 1;
- tags: 0;
- canonical worktrees: 1;
- dirty tracked files: 0;
- Git object garbage: 0.

A second worktree was created only for clean selective integration from
`origin/main`. It was never a second source of truth and is removed after
publication; final governance requires one canonical worktree.

## Branch topology and governance

| Branch/ref | Head at freeze | Relation to `origin/main` | State | Disposition |
| --- | --- | --- | --- | --- |
| `main` / `origin/main` | `cf158fd` | exact | authoritative | protected review boundary |
| `codex/broker-reports-clean-integration-v1` | implementation `f94abcd` | +10 / -0 before reports | active integration | development source of truth; publish, review, do not deploy here |
| `codex/broker-reports-runtime-audit-v1` | `7ba45b1` | +37 / -0 | retained evidence | blocked from deletion; exact current live Function source |
| `codex/broker-reports-architecture-recovery-v1` | `230fd02` | +48 / -0 | retained evidence | blocked from deletion; contains incomplete and rejected unique work |
| `codex/broker-reports-blocker-closure-v1` | `21a08b5` | +21 / -0 | safe to delete | all commits retained by runtime-audit history |
| `codex/pdf-dual-vlm-fact-benchmark` | `203d4ee` | ancestor, main +32 | safe to delete | exact VLM commits are in main and in the recovery map |
| `codex/pdf-table-intake-gate1-closure` | `6a48a43` | ancestor, main +27 | safe to delete | useful history retained by main |
| `codex/pdf-table-strategy-benchmark` | `4c32271` | ancestor, main +38 | safe to delete | useful history retained by main |
| `codex/vlm-guided-intake-development-gate-repair` | `9d91390` | +3 / -42, merge base `aade3c9` | retained evidence | blocked from deletion; three unique failed-gate commits |
| `old-origin/main` | `32eb38d` | historical ancestor | archived | not a release source |

No branch was deleted. The safe-delete list is a policy output, not an action.
The guided-intake branch cannot be deleted until its three unique commits
`9bd18dd`, `b31c80f` and `9d91390` have another durable reachable owner. The
audit branch cannot be deleted while the current stage receipt points to it.

## Clean integration receipt

No merge commit and no wholesale recovery/audit merge was used. The candidate
was built by selective cherry-pick with conflict resolution that omitted
audit-only visual modules, followed by clean bundle regeneration.

| Candidate commit | Source | Capability |
| --- | --- | --- |
| `113443b` | `afbfd62` | current-tree privacy quarantine and scanner |
| `75e4dd8` | `b365a5f` | authoritative architecture and anti-drift guards; audit visual files omitted |
| `e2995aa` | `86b2f22` | batched CSV/table source resolution |
| `f72e63b` | `c2f6662` | retention-scope prerequisite |
| `9fe7d5d` | `1ea2f11` | context-bound, idempotent ArtifactStore lifecycle |
| `5e1d279` | `31a66ce` | default-off Sber profile and debt registration |
| `c62d25e` | `37ff957` | Sber customer-debt release gate |
| `ee0d5de` | generated | first clean bundle regeneration, superseded by the closed-world correction |
| `9807b35` | governance follow-up | revoke current manifest links to external private evidence |
| `f94abcd` | selective part of `f0e0c4a` | include only architecture/customer policy modules in bundle builder and regenerate |

The `f0e0c4a` mixed recovery bundles were not cherry-picked. Only its two
closed-world module-list lines were reconstructed after the full suite proved
they were required. The final bundles were generated from the clean candidate,
not copied from recovery.

Explicit exclusions:

- `d3a1267` Gate 1 graph/memory work: incomplete;
- `0f9c950` private intake: delivery/readback incomplete;
- `a460c81` scheduler admission: scaffold only;
- `d7cc52d` duplicate VLM scaffold: rejected architecture;
- audit visual/OCR runtime commits: accepted evidence but not selected here;
- PaddleOCR/PaddleOCR-VL/local-heavy-OCR production assumptions: zero;
- private-intake Action/image/compose changes: zero.

## Candidate verification

Final full suite:

- 930 passed;
- 20 skipped;
- 0 failed;
- 5 warnings, all the known PyMuPDF/SWIG deprecation class.

Focused integration suite before the full run: 96 passed. Privacy/VLM manifest
follow-up: 25 passed. Closed-world bundle correction: 17 passed.

Two consecutive bundle builds were byte-identical. Final candidate SHA-256:

| Bundle | SHA-256 |
| --- | --- |
| Gate 1 | `de9709e78c7503f4a7277c5fad8285a79e3413b2005201a0d890f410c6b442ab` |
| Gate 2 source fact | `ffeff3c84d3c2a23ad3d6cfcb084d2072f752a5edce5551ffeb407a4efba4488` |
| Gate 2 domain | `9dc6ce4dc22ca0c810b36b1c77761f45b24e7cda7cd6a072738374ade0ec80ca` |

Forbidden symbols for intake, scheduler, the new VLM scaffold and Paddle were
absent from all three generated bundles.

## Historical privacy non-rewrite disposition

History contains known exceptions and is intentionally not rewritten:

1. `82313d87ca33ed8fa662db3df24e422f550865bf` introduced two reachable
   versions of a file named as a private reference. Its eight cases are the
   frozen public-broker development benchmark, not the customer corpus.
2. `dcb23512802a976c94482437398b8b8cc73e8945` recorded an absolute local
   evidence path. The path string does not carry credentials or artifact
   bytes.

The historical reference has 8 public-benchmark SHA identities. Comparison
against 61 unique SHA-256 identities in the safe customer indexes produced
zero overlap. The historical file contains public benchmark literals but no
customer documents, customer values, customer source identifiers or
credentials.

Five exact ignored/untracked external evidence targets referenced by old links
were hash/scope checked and purged. All were inside the ignored local evidence
root; none was tracked. Current manifests now retain only immutable hashes and
the marker `external_private_evidence`. Resolution count for those historical
targets is zero.

Reachable-history scanning covered 2,390 blobs with no size skips. Six secret
signatures were found and classified: two explicit synthetic `sk-` examples
and four variable references to `api_key`; none is a literal credential.
Private-key, AWS, GitHub, Google, Slack and JWT credential findings were zero.
GitHub secret scanning reports zero open alerts.

The broad path scan reported historical examples, code/test fixtures, ignored
evidence-link strings and false binary matches. It does not justify claiming
that history has no path exceptions. The two material Broker Reports exceptions
above are bounded and cannot resolve private evidence.

Current and future protection consists of:

- no tracked `*.private.json` or `*.private.sha256.json`;
- maintained safe-output absolute/local-path scanning;
- benchmark-manifest private-link scanning;
- ignored `.env`, `local/`, `_private_test_corpora/`, `secrets/` and other
  evidence roots;
- green `test_repository_privacy_guard.py` on the clean candidate.

Disposition: `DOCUMENTED_NON_REWRITE`. Rewriting and force-pushing shared
history would be higher risk and are forbidden.

## Main, candidate and stage provenance

| Role | Revision/source | Authority |
| --- | --- | --- |
| approved integration base | `origin/main` at `cf158fd` | review boundary |
| development source of truth | `codex/broker-reports-clean-integration-v1` | clean selectively integrated candidate |
| current approved live runtime | `codex/broker-reports-runtime-audit-v1` at `7ba45b1` | exact live Function bytes |
| recovery evidence | `codex/broker-reports-architecture-recovery-v1` at `230fd02` | not a release source |
| VLM recovery | commit set ending at `203d4ee`, already in main | benchmark/live-provider evidence only |
| external customer debt | Sber positive holdout | default-off and release-gated |

Read-only stage evidence after candidate verification:

- image ID:
  `sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175`;
- static loader SHA-256:
  `28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2`;
- normalizer Action SHA-256:
  `e36f05b38a858eeea3a9bfdded2145bb407394c85483686f526e8241d1162e3e`;
- private-intake Action: absent from the live Function inventory;
- required/live PyMuPDF: `1.26.5` / `1.26.5`;
- Gate 1 bundle requirements:
  `pydantic`, `pypdf==6.7.5`, `pdfplumber==0.11.10`,
  `pdfminer.six==20260107`;
- Gate 2 bundle requirement: `pydantic`.

| Live Function | Live SHA-256 | Exact repository owner |
| --- | --- | --- |
| Gate 1 | `9b3895b521d8ec82b486edfba7a3b29cbeb913217fa73aff18783915126bb1df` | `7ba45b1` |
| Gate 2 source fact | `168a3095ca488f13736ea4655c54df5ec136ebf196c6ab7fa4e1e98f121a3f96` | `7ba45b1` |
| Gate 2 domain | `eb1a98515743e8adda5fa57dfbe5c2f7a57753966fd1b0902f35300ab903a54e` | `7ba45b1` |

All three Functions were present, active and contained their required modules.
They intentionally differ from the clean candidate hashes. This is a candidate
versus live difference, not mixed deployment and not a defect to repair during
archaeology.

All 12 managed prompts passed presence, active-state, version, content hash and
metadata parity:

| Prompt | SHA-256 |
| --- | --- |
| document metadata passport | `1f9827ad62e1f20c5187f92aa3814f2c149f28148a61356b52850afc301f2de6` |
| Gate 1 clarification | `7fd0b6dc935395bfb61aeabd24194941ed32b590ba58af03ff1581849dc2048a` |
| cash movement | `c9394d07189cd3aec476a27a2fd2f3cc4b3e7883e3abaa6d43066902060d7e0e` |
| currency/FX | `917c1cae378223bdd2316dc8ec7d317352107943dd5988360e7572719e1bb715` |
| summary evidence | `9bad1a06bb8556e0fa62f1f47de73c7d7b1d41e57aa752de9206c0749133088d` |
| fee/commission | `1d7b5c5e25f1e520d55ef8e9c84d323e6a27d73da392b428a74e95a0af6910fc` |
| income | `af7fcd78f4533d0f5a1f8bcef58ad113f72f102e58f547f0c30f8810ddced187` |
| position snapshot | `b250663fc078782b28dfb530f10e99ee13f97789a12d4e67852938b3088c36fd` |
| source fact | `8ae7e4c49b987f8098540235b46381ae7c7ad7e021a417f975807ac1ea3083c9` |
| trade operation | `e819ded91b58bea3012e9bd9cde0444b63427d60120ef6712e33a4d8b515c0d1` |
| unknown source row | `776a7574542cba7b77b2c5e7686af5990c652420823bbea9a78749ac12428aa1` |
| withholding tax | `e952e09ab395d21093102e9264effd0d8fce54e5b913b57c046538168d3eb228` |

Operational state remained: table intake enabled and configured; structural,
guided-intake and semantic-header shadows disabled; Sber profile disabled;
provider profiles and factory boundary passed. Stage mutation count is zero.

## Recommended next VLM goal

Run `Broker Reports Pre-Drift Dual-VLM Selective Runtime Integration And
Current-Model Requalification v1` from the clean candidate. It should reuse the
recovered adapters and contracts, requalify current model IDs, build a
contract-compatible human reference, create one maintained dual-provider
decision envelope, regenerate closed-world bundles and prove candidate/live
parity in a separate explicit deployment goal.

It must not add a third adapter family, revive OCR-first/Paddle production,
activate Sber, merge recovery wholesale, or deploy partial Functions.

## Final status

`BROKER_REPORTS_REPOSITORY_ARCHAEOLOGY_AND_HYGIENE: COMPLETED`

`REPOSITORY_SOURCE_OF_TRUTH: ESTABLISHED`

`CLEAN_INTEGRATION_BRANCH: PROVEN`

`PRE_DRIFT_DUAL_VLM_PIPELINE: LOCATED_AND_CLASSIFIED`

`VLM_RECOVERY_COMMIT_SET: READY`

`NEW_VLM_SCAFFOLD: COMPARED_AND_DISPOSITIONED`

`GIT_HISTORY_POLICY: DOCUMENTED_NON_REWRITE`

`HISTORICAL_PRIVATE_REFERENCES: UNRESOLVABLE`

`CURRENT_TREE_PRIVACY: PASSED`

`CURRENT_STAGE: UNCHANGED_AND_TRACEABLE`

`UNCLASSIFIED_RELEVANT_BRANCHES: ZERO`

`NEXT_VLM_INTEGRATION_GOAL: READY`
