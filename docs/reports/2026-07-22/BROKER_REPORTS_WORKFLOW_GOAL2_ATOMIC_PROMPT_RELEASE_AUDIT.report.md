# Broker Reports Workflow Goal 2 — Atomic Prompt Release Audit

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal2-atomic-prompt-release-audit-v1`

Audited source revision: `df22db91b85fe1d48d5d2973f3929ad7b9178457`

Status: NOT_CLOSED

## Trigger

Goal 5G was merged after proving that the Gate 2 source provider contract had
to become a compact semantic-selection projection. The new source Function and
its managed prompt must therefore be delivered together before the native Gate
2 reproof.

## Failed invariant

The maintained atomic release was invoked for the exact merged revision with
apply and rollback rehearsal enabled. It failed with
`stage_release_prompt_contract_mismatch` before candidate application. Two
subsequent read-only preflight/diagnostic invocations returned the same typed
error.

The release manifest contains the new managed-prompt identity, but the remote
releaser treats managed prompts as an immutable precondition. It atomically
replaces Function rows only. Consequently:

- updating the prompt first would create a prompt/Function compatibility gap;
- updating the source Function and prompt through the legacy updater would
  deploy a partial Function set;
- running the atomic releaser first is impossible because its static prompt
  check rejects the old live prompt.

No partial workaround was used.

## Stage safety evidence

The mismatch occurs in static preflight before rollback creation or Function
row replacement. Read-only inspection after all three invocations showed:

- all three live Function hashes remained the previously accepted hashes;
- the live source prompt retained the previously accepted content and version;
- Action, loader and image identities remained unchanged;
- workload nonterminal jobs: zero;
- owned temporary workload entries: zero;
- release staging entries: zero;
- live release revision markers remained on the previously accepted revision.

Thus the failed release did not leave a stage-ahead-of-main state and did not
partially activate Goal 5G.

## Ownership and narrowest corrective slice

- Failed invariant: `ATOMIC_FUNCTION_SET_AND_MANAGED_PROMPT_DELIVERY`.
- Measured evidence: one apply attempt plus two read-only confirmations, all
  rejected by the same prompt contract precondition; zero live row changes.
- Owning component: Broker Reports atomic stage release tooling.
- Blocker type: release/readback contract gap.
- Narrowest corrective slice: include the manifest-declared managed prompt
  rows in the same stopped-container database transaction as all Function
  rows. Snapshot both families in the rollback artifact, verify exact prompt
  content/version/metadata after restart, and include prompts in rollback
  rehearsal and restoration. Action, loader and image remain static checks.

The Gate 2 semantic-selection runtime, its prompt content, provider boundary,
private intake, WorkloadAuthority and ArtifactStore do not need another
semantic correction.

## Acceptance disposition

- GOAL5G_MERGED_REVISION: EXACT
- ATOMIC_RELEASE_PREFLIGHT: FAILED
- ERROR_CODE: STAGE_RELEASE_PROMPT_CONTRACT_MISMATCH
- PARTIAL_FUNCTION_DEPLOYMENT: ZERO
- PARTIAL_PROMPT_DEPLOYMENT: ZERO
- LIVE_FUNCTION_ROWS_CHANGED: ZERO
- LIVE_PROMPT_ROWS_CHANGED: ZERO
- WORKLOAD_QUIESCENT: PASSED
- RELEASE_STAGING_CLEAN: PASSED
- STAGE_AHEAD_OF_MAIN: ZERO
- CUSTOMER LABELS OR VALUES IN GIT: ZERO

Goal 2 remains NOT_CLOSED pending a separate release-tooling correction, a
successful atomic release and a fresh native workflow proof.
