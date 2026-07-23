# Broker Reports — Final Full Regression Reproof

Date: 2026-07-23

Branch: `codex/broker-reports-final-full-regression-reproof-v2`

GOAL status: `PASSED`

Repository revision under test:
`07bbea8f7f81f4381b98a8809bfa560918be23a8`

Released runtime source revision:
`287d2bd255a8023b076a3fa0e688f18e3f509a04`

## Result

The full maintained Broker Reports service suite passed after the two defects
found by the first audit were corrected in separate branches:

- the regression test now resolves its source file independently of the shell
  working directory;
- the shared answer-context layer uses the neutral stitch-result contract and
  no longer imports Gate 2 business runtime.

The runtime correction was delivered separately through the atomic stage
release and rollback/readback proof. This reproof branch contains no runtime or
stage mutation.

## Full regression

Command, run from the service root:

```text
python -m pytest tests -ra
```

Terminal result:

```text
collected: 1154
passed: 1134
failed: 0
skipped: 20
xfailed: 0
xpassed: 0
warnings: 5
pytest duration: 90.91 s
process wall time: 92.3 s
```

All 20 skips are explicit cases in the table-strategy benchmark which require
an offline private benchmark reference. No skip masks a product regression.

## Independent checks

- Ruff on the four maintained Python files touched by the two corrections:
  passed.
- `compileall` for `broker_reports_gate1` and `openwebui_actions`: passed.
- Neutral contract import and legacy schema alias equality: passed.
- Privacy, architecture, answer-context and integrated reproof selection:
  `17 passed`.
- Repository privacy guard within the full suite: `3 passed`.
- Architecture and anti-drift tests within the full suite: passed.
- `git diff --check`: passed.
- Working tree after verification: clean.

The repository has no global Broker Reports Ruff configuration. The accepted
lint contract is the maintained changed-file contour; an unrelated legacy
repo-wide lint rewrite is outside this closure.

## Deterministic closed-world bundles

Two consecutive `--target all` generations were byte-identical and produced no
tracked diff:

| Function bundle | SHA-256 |
|---|---|
| Gate 1 | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |

The bundle boundary remains closed-world: no workspace-only import or
filesystem path dependency was introduced.

## Privacy and mutation statement

No customer label, customer value, document name, credential, provider payload
or private reference content is stored in this report or its receipt.

Stage mutations in this branch: `0`.

GOAL_0_FINAL_INTEGRATED_REGRESSION: `PASSED`.
