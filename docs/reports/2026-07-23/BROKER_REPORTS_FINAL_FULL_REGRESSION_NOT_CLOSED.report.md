# Broker Reports — Final Full Regression Receipt

Date: 2026-07-23

Branch: `codex/broker-reports-final-full-regression-v1`

Status: `NOT_CLOSED`

## Immutable preflight

- exact revision: `137d324bbe1a777d2675c42b51742fe0ccb699d1`;
- local `main == origin/main`: yes;
- canonical worktree: one;
- worktree entries before test: 0;
- tracked files under repository `local/`: 0;
- test references to repository-local untracked evidence: 0;
- stage mutation: 0.

Execution environment:

- Windows `10.0.17763`;
- CPython `3.11.9`;
- pytest `8.4.2`;
- Ruff `0.14.11`;
- PyMuPDF `1.26.5`;
- pdfplumber `0.11.10`;
- pypdf `6.7.5`.

PowerShell command, run from repository root:

```text
python -m pytest services/broker-reports-gate1-proof/tests -ra
```

## Terminal pytest result

| Metric | Result |
|---|---:|
| Collected | 1154 |
| Passed | 1132 |
| Failed | 2 |
| Skipped | 20 |
| Xfailed | 0 |
| Xpassed | 0 |
| Warnings | 5 |
| Duration | 96.50 s |

All 20 skips belong to the explicitly offline private table-strategy benchmark
and report `offline private benchmark reference is required`. They are not
relabelled as passed.

The runner executed the full collection and reached a terminal test summary; it
did not abort during configuration or collection.

## Failure 1 — test execution-path portability

Test:
`test_broker_reports_gate2_fns_2ndfl_adapter.py::BrokerReportsGate2Fns2NdflAdapterTest::test_factory_route_import_isolation_and_integrity_tamper`

Primary assertion boundary: the test must read the maintained adapter source
and inspect its factory/forbidden anchors.

Observed result: `FileNotFoundError` for a path resolved relative to the shell
current directory.

Attribution:

- expected: source path resolves from any repository test invocation;
- actual: path resolves only when pytest starts in the service directory;
- owning component: test path construction;
- blocker type: test correctness / execution environment portability;
- product runtime defect: no;
- narrowest correction: anchor the source path to the test file/service root.

Diagnostic rerun from the service root passed this test. This proves that the
failure is a CWD assumption, not missing source or a shell/ENV mismatch.

## Failure 2 — reverse Gate dependency

Test:
`test_broker_reports_gate_architecture.py::BrokerReportsGateArchitectureTest::test_gate1_has_no_reverse_dependency_on_gate2_business_runtime`

Primary assertion failure:

```text
expected: []
actual: [answer_context_selection->gate2_source_fact_stitching]
```

Attribution:

- violated invariant: Gate 1/common answer-context code must not import Gate 2
  business runtime;
- owning component: `answer_context_selection` contract dependency;
- blocker type: product architecture / anti-drift;
- narrowest correction: move the shared stitch schema identity to a neutral
  contract module and make both consumers depend on that contract;
- weakening the architecture test is forbidden.

The same test failed from both repository root and service root, so it is not a
path, ENV or shell-context artifact.

## Blocked acceptance

Because the full suite has a real failure, later green checks cannot close this
GOAL. Ruff, compile/import, two-pass bundle regeneration and final privacy/
anti-drift receipts remain `NOT_RUN_AFTER_TERMINAL_SUITE_FAILURE` in this audit
branch. They must run after both defects are corrected on separate branches.

| Invariant | Result |
|---|---|
| `FINAL_MAIN_REVISION` | `EXACT` |
| `FULL_SERVICE_SUITE` | `FAILED_2` |
| `TEST_COLLECTION` | `COMPLETE` |
| `DETERMINISTIC_BUNDLES` | `BLOCKED` |
| `RUFF` | `BLOCKED` |
| `COMPILE_IMPORT` | `BLOCKED` |
| `PRIVACY_GUARD` | `BLOCKED` |
| `ARCHITECTURE_ANTI_DRIFT` | `FAILED` |
| `STAGE_MUTATION` | `ZERO` |

No runtime or test source was changed in this evidence branch.
