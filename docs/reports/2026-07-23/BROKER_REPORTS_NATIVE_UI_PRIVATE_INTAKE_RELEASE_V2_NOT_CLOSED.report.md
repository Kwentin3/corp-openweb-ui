# Broker Reports — Native UI Private Intake Release V2 Not Closed

Date: 2026-07-23

Branch: `codex/broker-reports-native-ui-private-intake-release-v2`

Approved main revision:
`a839fb7f6d03b2520b4be8741fa8575202424747`

Status: `NOT_CLOSED`

Stage mutation: `ZERO`

## Objective

Release the native UI private-intake correction through the newly extended
atomic loader boundary.

## Primary evidence

The maintained release driver completed dry validation:

```text
status: validated
applied: false
staging removed: true
workload nonterminal jobs: 0
owned temporary entries: 0
Function changes required: 0
managed prompt changes required: 0
loader change required: true
```

The dry plan exposed an identity mismatch before apply:

| Loader object | SHA-256 |
|---|---|
| Accepted Git blob at approved revision | `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f` |
| Candidate produced from Windows working tree | `9c03605c361e119be01eb89f9f31bfbd7bc47c071adbb47139023a9c9fbc1614` |

The repository has `core.autocrlf=true`. The working-tree loader has converted
line endings, while the accepted Git blob retains the exact bytes reviewed and
proved by the UI correction.

No apply command was issued.

## Violated invariant

The release payload must be derived from the exact approved source revision,
not from a platform-normalized working-tree copy.

The v3 tooling correctly stages and atomically manages loader bytes, but the
local driver currently obtains those bytes from `LOADER_PATH.read_bytes()`.
On a checkout with line-ending conversion, that byte sequence is not the Git
blob at the approved revision.

Releasing it would make live stage differ from the accepted repository object
and from the previously recorded loader identity.

## Classification

- owning component: Broker Reports atomic stage release tooling;
- blocker type: cross-platform source-identity defect;
- loader behavior defect: no;
- stage drift: no;
- hidden correction in this branch: zero;
- runtime or stage mutation: zero.

## Narrowest corrective slice

The release driver and verifier must derive the loader bytes from the exact Git
blob at `source_revision:deploy/openwebui-static/loader.js`.

The correction must:

1. fail if the requested blob is absent or empty;
2. build the manifest from those exact bytes;
3. materialize those exact bytes only inside the ephemeral release payload;
4. make local manifest validation independent of checkout line endings;
5. make the independent verifier build the same expected manifest;
6. prove in tests that CRLF working-tree bytes cannot alter the candidate hash.

This correction belongs in a separate branch and PR. The atomic dry/apply and
rollback proof must then be repeated from the next approved `main`.

