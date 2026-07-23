# Broker Reports — Atomic Loader Release Correction

Date: 2026-07-23

Branch: `codex/broker-reports-atomic-loader-release-correction-v1`

Implementation commit:
`7b835135c15bd89ec927ba34b425c971d817ffa5`

Status: `PASSED`

Live release status: `PENDING_AFTER_MERGE`

Stage mutation: `ZERO`

## Trigger

The approved native UI loader could not be released through the maintained
atomic stage boundary. The prior release validation stopped before mutation
with `stage_release_loader_contract_mismatch`.

Primary trigger evidence:
[release not closed](./BROKER_REPORTS_NATIVE_UI_PRIVATE_INTAKE_RELEASE_NOT_CLOSED.report.md).

## Narrow correction

The existing Broker Reports atomic stage release tooling now treats
`deploy/openwebui-static/loader.js` as a first-class release object.

- release manifest schema v3 contains the loader file name and exact SHA-256;
- the local driver includes the exact loader bytes in the restricted payload;
- the remote side validates the staged bytes before any mutation;
- dry validation compares current and candidate loader identities without
  requiring them to be equal;
- apply uses a hash precondition and same-directory atomic file replacement
  while OpenWebUI is stopped;
- the rollback artifact retains the exact previous loader bytes and commits
  their hash into its immutable metadata;
- failure recovery restores the previous Function rows, prompt rows and loader;
- rollback rehearsal proves both previous and candidate loader terminal states;
- the independent live verifier checks the retained rollback loader hash.

The stopped-runtime boundary is explicit: the loader replacement and the
existing SQLite transaction are coordinated while OpenWebUI is stopped, and
any later failure drives the whole managed release set back to its previous
state.

Unchanged:

- UI loader behavior and content;
- private-intake Action;
- Gate 1 and Gate 2 business logic;
- prompts and provider policy;
- semantic JSON contract;
- ArtifactStore and answer-context contracts;
- no-RAG/no-vector boundary.

## Verification

Focused atomic release suite:

```text
15 passed
0 failed
```

The focused suite proves:

- a different current loader is valid during dry planning;
- candidate mode requires the exact candidate hash;
- a stale loader precondition fails closed;
- successful replacement reaches exact candidate bytes;
- payload tampering is rejected;
- rollback retains exact prior bytes;
- rollback-byte tampering is rejected;
- Function and prompt transaction rollback remains exact.

Complete Broker Reports service suite:

```text
collected: 1157
passed: 1137
failed: 0
skipped: 20
xfailed/xpassed: 0
warnings: 5
pytest duration: 98.00 s
process wall time: 99.33 s
```

All 20 skips are the declared offline private benchmark cases.

Additional checks:

- Ruff on all five changed Python files: passed;
- Python compile check on all five changed files: passed;
- repository privacy guard within the full suite: `3 passed`;
- `git diff --check`: passed.

## Deterministic closed-world bundles

Two consecutive `--target all` generations were byte-identical and produced no
bundle diff:

| Function bundle | SHA-256 |
|---|---|
| Gate 1 | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |

Corrected loader content remains:
`5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f`.

No workspace-only import, filesystem path hack or ghost dependency was added to
the Function runtime bundles.

## Next required step

After this correction is merged, create a fresh release branch from the exact
approved `main` and run:

1. atomic dry validation;
2. atomic apply with rollback proof;
3. independent live readback verification;
4. the native browser click-through from a fresh chat.

