# Broker Reports Gate 2 Managed Financial Domain — Goal 2D Portable Git-Blob Evidence

Date: 2026-07-26

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

Base revision: `85c61d545269c0e66f6700298b429fc9ed06132b`

Branch:
`codex/broker-reports-gate2-domain-goal2d-portable-blob-evidence`

## 1. Outcome

GOAL 2D corrects an evidence-boundary error introduced by GOAL 2C.

The original GOAL 2 report and receipt used portable SHA-256 values of Git
blob bytes. A later check ran on Windows with `core.autocrlf=true`, hashed raw
CRLF-expanded working-tree files, compared those values to the LF-normalized
Git blobs, and incorrectly classified all four differences as stale evidence.
GOAL 2C then replaced correct repository hashes with checkout-specific hashes.

GOAL 2D:

- restores the three unchanged original GOAL 2 deliverable blob hashes;
- pins the new test-file blob hash after the guard correction;
- updates the GOAL 2 report-to-receipt blob hash;
- changes the guard to hash staged Git objects via `git show :<path>`;
- marks GOAL 2C `SUPERSEDED_INCORRECT_HASH_BOUNDARY` and not current
  authority.

The Financial Semantic Pack, its schema, semantic meaning, canonical
9,404-byte material, semantic integrity hash, and runtime/stage state are
unchanged.

## 2. Correct hash boundary

Repository evidence uses SHA-256 over Git blob bytes. This boundary is:

- stable across Windows and Linux checkouts;
- independent of `core.autocrlf`;
- the exact content stored in the current staged/committed repository object;
- distinct from a platform-expanded working-tree byte stream.

The GOAL 2 receipt now explicitly declares `hash_boundary=git_blob_bytes`.

Exact current GOAL 2 deliverable blob hashes:

| Deliverable | Git-blob SHA-256 |
|---|---|
| Financial Semantic Pack | `ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f` |
| Financial Semantic Pack schema | `cea99c199ba6b20905fd988fed481e963a999d1a74464a0af055d38eb0c76b9e` |
| Financial Semantic Pack contract | `3f326a6c2da1baf4b636689648e6f6eabca5ff24850edd2a64f69929f11c76c6` |
| Financial Semantic Pack tests | `c88b9eb317ae826fe02788520f569140a4c8a4a28f1fe275358c534d7a2fdbe8` |

The reconciled GOAL 2 receipt Git-blob SHA-256 is
`1e166f561af894dd1fc0102abd2b7f0bd069e273ceeb90ac8f8d14c31d6cabe6`.

## 3. Regression guard

`test_goal2_safe_receipt_hashes_current_git_blobs`:

1. requires the receipt hash boundary to be `git_blob_bytes`;
2. resolves every declared repository-relative path;
3. reads the staged Git object with `git show :<path>`;
4. computes SHA-256 over those exact bytes;
5. reports every mismatch.

In a clean checkout the index and `HEAD` contain the same blobs. During a
corrective change, staging the intended files lets the test validate the
exact next-commit objects before commit.

## 4. GOAL 2C status

GOAL 2C remains in Git as transparent audit history, but both its report and
receipt now state:

```text
GOAL2C_STATUS: SUPERSEDED_NOT_AUTHORITY
PORTABLE_HASH_BOUNDARY: FAILED
```

Its historical Windows CRLF hashes are labelled superseded and cannot be
presented as current authority.

## 5. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- focused Pack/evidence tests: `9 passed in 0.44s`;
- full Broker Reports suite:
  `1537 passed, 20 skipped, 5 warnings in 112.14s`;
- repository privacy guard: `3 passed in 0.76s`;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- GOAL 2 declared Git-blob hash mismatches: 0;
- GOAL 2 report contains exact current receipt Git-blob hash: yes;
- Windows working-tree bytes used as authority: no;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

## 6. Scope and rollback

This corrective GOAL changes five prior evidence/test files and adds this
report/receipt. It changes no runtime code, Semantic Pack content, OpenWebUI
asset, provider policy, model admission, stage, or production state.

Rollback is a repository revert only. No production rollback is involved.

## 7. Deliverables

1. corrected GOAL 2 report and receipt;
2. supersession-labelled GOAL 2C report and receipt;
3. checkout-independent Git-blob regression guard;
4. this corrective report;
5. repository-safe corrective receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL2D_PORTABLE_GIT_BLOB_EVIDENCE.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL2D_PORTABLE_GIT_BLOB_EVIDENCE.receipt.safe.json)
   - Git-blob SHA-256:
     `d53bb03f78d92b82e10345df15b8fae67aeb204b44f68aec05e01dc9f0c904fe`

## 8. Acceptance markers

```text
PORTABLE_HASH_BOUNDARY: GIT_BLOB_BYTES
GOAL2_GIT_BLOB_HASH_MISMATCHES: ZERO
GOAL2C_CURRENT_AUTHORITY: FALSE
SEMANTIC_AUTHORITY_CHANGE: ZERO
STAGE_PRODUCTION_CHANGE: ZERO
NEXT_PERMITTED_GOAL: GOAL_3_AFTER_GOAL_2D_REVIEW_ACCEPTANCE_AND_MERGE
```
