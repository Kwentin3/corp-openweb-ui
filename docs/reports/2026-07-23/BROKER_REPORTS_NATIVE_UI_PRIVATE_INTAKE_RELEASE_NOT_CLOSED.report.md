# Broker Reports — Native UI Private Intake Release Not Closed

Date: 2026-07-23

Branch: `codex/broker-reports-native-ui-private-intake-release-v1`

Status: `NOT_CLOSED`

Stage mutation: `ZERO`

## Objective

Atomically release approved main revision
`dad87fec9a877f7eaefd422221daab981a74e507` after the native UI private-intake
correction, with maintained release tooling and rollback proof.

## Primary evidence

The maintained release driver was invoked in validation mode before any apply:

```text
python services/broker-reports-gate1-proof/scripts/live_release_broker_reports_atomic_stage.py \
  --env-file .env \
  --source-revision dad87fec9a877f7eaefd422221daab981a74e507
```

It terminated with the safe error code:

```text
stage_release_remote_failed:stage_release_loader_contract_mismatch
```

The remote transaction stops at its pre-mutation static-contract assertion.
No Function, Action, prompt, loader, image or database state was changed.

## Violated invariant

The approved loader change cannot be released through the maintained atomic
boundary.

The release driver builds the target loader hash into the manifest, but its
payload contains only the manifest, remote transaction script and Function
bundles. The remote transaction does not stage, replace or restore
`deploy/openwebui-static/loader.js`. Instead, before apply it requires the live
loader hash to equal the target loader hash.

Consequently, a loader correction can pass validation only after an out-of-band
loader mutation, which would bypass the required atomic release and rollback
boundary.

## Classification

- owning component: Broker Reports atomic stage release tooling;
- blocker type: release-tooling product defect;
- loader implementation defect: no;
- environment drift: no;
- hidden correction in this branch: zero;
- runtime or stage mutation: zero.

## Narrowest corrective slice

Extend the maintained atomic release transaction so that it:

1. includes the exact loader bytes in the staged payload;
2. distinguishes the current loader contract from the candidate contract;
3. applies the loader together with managed Function and prompt state;
4. records the previous loader in the immutable rollback artifact;
5. restores both previous and candidate loader states during rollback proof;
6. verifies hashes and counter/quiescence invariants after every transition;
7. cleans staging without exposing private evidence.

This correction must be delivered in a separate branch and PR. After merge,
the approved main revision must receive a fresh validation, apply, rollback
proof and live browser rerun.

