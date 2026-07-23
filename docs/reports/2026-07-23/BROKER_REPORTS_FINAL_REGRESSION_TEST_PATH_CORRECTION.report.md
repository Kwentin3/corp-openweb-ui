# Broker Reports — Final Regression Test Path Correction

Date: 2026-07-23

Branch: `codex/broker-reports-final-regression-test-path-v1`

Status: `PASSED`

## Failure attribution

The full-suite test
`test_factory_route_import_isolation_and_integrity_tamper` failed when invoked
from the repository root because it resolved a maintained source file relative
to the shell current directory.

- expected observable behavior: the test reads the production adapter source
  and validates factory/forbidden anti-drift anchors;
- actual behavior: `FileNotFoundError` before those assertions;
- owning component: test path construction;
- product runtime impact: none;
- shell/ENV mismatch: not the primary cause.

## Narrow correction

The test now resolves the adapter from `Path(__file__)` and the service root.
No assertion, factory anchor, production module, fixture payload or expected
behavior changed.

The test remains isolated through its existing per-test temporary ArtifactStore
state. Its irreversible boundary is validation of a deliberately tampered typed
fact; the observable terminal outcome remains validator status `failed` with
the integrity-mismatch error.

## Verification

PowerShell, repository root with an explicit service `PYTHONPATH`:

```text
8 passed in 6.50s
```

PowerShell, service root without additional ENV:

```text
8 passed in 7.54s
```

Ruff: passed.

`git diff --check`: passed.

Runtime changes: 0.

Stage mutations: 0.

This correction closes only the test-portability defect. The separate
production architecture anti-drift failure remains owned by its own corrective
branch.
