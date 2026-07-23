# Broker Reports — Loader Git Blob Release Correction

Date: 2026-07-23

Branch: `codex/broker-reports-loader-git-blob-release-correction-v1`

Implementation commit:
`a3ec622b13968449f75c6cb5da258d719b96b897`

Status: `PASSED`

Live release status: `PENDING_AFTER_MERGE`

Stage mutation: `ZERO`

## Trigger

The atomic release v2 dry plan showed that a Windows working-tree copy of the
loader did not have the same byte identity as the accepted Git blob.

Primary trigger evidence:
[release v2 not closed](./BROKER_REPORTS_NATIVE_UI_PRIVATE_INTAKE_RELEASE_V2_NOT_CLOSED.report.md).

## Narrow correction

The exact Git blob at
`source_revision:deploy/openwebui-static/loader.js` is now the sole source for
the loader release object.

- a bounded source helper accepts only an exact 40-character revision and the
  fixed loader repository path;
- it reads the blob with `git cat-file blob`, preserving repository bytes;
- absent, empty, invalid-revision and invalid-path sources fail closed;
- manifest construction requires explicit non-empty loader bytes;
- local manifest validation checks the loader contract without consulting the
  platform-normalized working tree;
- the driver materializes exact blob bytes only in its ephemeral payload;
- the independent live verifier derives its expected loader identity from the
  same approved revision object.

The normal checkout file is no longer a release byte source. This removes the
effect of `core.autocrlf`, editor normalization and platform line endings from
the candidate identity.

Unchanged:

- loader JavaScript behavior and Git blob;
- remote stopped-runtime transaction and rollback implementation;
- Function bundles, Action and prompts;
- Gate 1 and Gate 2 business logic;
- semantic table and answer-context contracts;
- no-RAG/no-vector boundary.

## Verification

Focused atomic release suite:

```text
18 passed
0 failed
```

The new behavioral tests invoke the local release driver with transport
replaced by an in-memory capture and prove:

- the payload bytes equal the exact approved Git blob;
- the manifest loader hash equals those payload bytes;
- line-ending-converted bytes cannot change the manifest identity;
- a non-exact revision fails closed.

Complete Broker Reports service suite:

```text
collected: 1160
passed: 1140
failed: 0
skipped: 20
xfailed/xpassed: 0
warnings: 5
pytest duration: 94.38 s
process wall time: 95.60 s
```

All 20 skips are the declared offline private benchmark cases.

Additional checks:

- Ruff on all five changed Python files: passed;
- Python compile check on all five changed files: passed;
- repository privacy guard within the full suite: `3 passed`;
- `git diff --check`: passed.

## Deterministic identities

The accepted loader Git blob remains:
`5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f`.

Two consecutive `--target all` generations were byte-identical and produced no
bundle diff:

| Function bundle | SHA-256 |
|---|---|
| Gate 1 | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |

No workspace-only dependency was added to a Function runtime bundle. The new
Git source helper is used only by local release and verification scripts.

## Next required step

After merge, create a fresh release branch from exact approved `main` and run:

1. atomic dry validation, requiring candidate loader identity
   `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f`;
2. atomic apply with rollback proof;
3. independent live readback verification;
4. native browser click-through from a fresh chat.

