# Broker Reports Workflow Goal 5H — Atomic Prompt Release Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5h-atomic-prompt-release-v1`

Correction family: atomic release and rollback tooling

Implementation status: PASSED

Live atomic release: PENDING AFTER MERGE

## Trigger

The Goal 5G release was rejected in static preflight because the atomic
releaser required the new managed prompt to exist before it could atomically
replace the Function set. The existing tool could not deliver a compatible
prompt/Function pair without a temporary partial deployment.

## Narrow correction

The existing manifest and remote releaser were extended; no parallel delivery
path was created.

- release manifest v2 carries the exact content, content hash, command,
  version and required metadata subset for all 12 maintained managed prompts;
- the remote candidate builder merges required metadata into each existing
  fixed prompt row and preserves unrelated operator metadata;
- unchanged prompt rows retain their exact content, metadata serialization and
  timestamp;
- all three Function rows and all managed prompt rows share one SQLite
  connection, one `BEGIN IMMEDIATE` transaction and one commit/rollback;
- function and prompt drift guards execute before either family is updated;
- rollback artifact v2 contains exact snapshots for both row families;
- rollback rehearsal restores and compares both families before restoring the
  candidate;
- candidate readback requires exact Function release identities and exact
  prompt content/version/metadata identities;
- the local driver now surfaces only a bounded typed remote error code instead
  of hiding it behind a generic SSH failure.

## Database safety

This is a fixed-ID release control-plane operation against the local OpenWebUI
database, not tenant-selected business data. No request or DTO supplies a user
or tenant identifier. All mutations are executed through the transaction
handle created inside the release repository function; no global connection is
used within that transaction. Tests exercise the real callback/transaction
path and do not weaken row guards.

## Failure semantics

Tests prove both cross-family terminal outcomes:

- a wrong Function hash leaves Function and prompt rows unchanged;
- a wrong prompt hash leaves Function and prompt rows unchanged;
- a successful candidate application updates both families;
- exact rollback restores both families;
- unchanged managed prompts are not mechanically rewritten;
- unsafe remote error text is reduced to a generic safe code.

If restart or post-start verification fails after a committed candidate, the
existing failure handler now restores both Function and prompt snapshots before
returning an error.

## Preserved boundaries

- Action, loader and image remain immutable static release checks;
- workload quiescence remains mandatory before and after every restart;
- release staging cleanup and strict SSH host-key checking remain mandatory;
- the Gate 2 semantic-selection contract and Gemini-master VLM contract are
  unchanged;
- no Knowledge, RAG, embeddings, vectorization, local OCR or provider bypass
  was added;
- legacy rollback artifacts remain readable by the unchanged verifier path.

## Verification

Terminal local results:

- focused atomic transaction, prompt identity and driver error tests: 27
  passed;
- full affected Gate 2, bundle, architecture, release and ArtifactStore
  regression: 127 passed;
- Ruff on changed surfaces with repository baseline import exceptions: passed;
- compile check: passed;
- `git diff --check`: passed;
- boundary-aware scan of sealed private labels and values: zero findings.

Tooling SHA-256 identities:

- release contracts: `a5f07440d81ff6c16bb105f8a1b03404e0ff9cd6685670e1a401aeafdf6fb26c`;
- remote transactional releaser: `2fce3ea55273b2029610ba2f0763d59c427fcf8483d0737df87c532535b0047f`;
- local release driver: `8151ce62afbd1775d9c201ff2667b8661fa9cab1d07f3bf303c9c1d34cc59959`;
- delivery contract assembler: `3cdb69230f8a064e6457871fd2144dc9311cbafd9fdb0387ecb21c7f6bfe8b24`.

## Acceptance disposition

- MANIFEST_SCHEMA: BROKER_REPORTS_ATOMIC_STAGE_RELEASE_V2
- FUNCTION_ROWS_IN_SHARED_TRANSACTION: THREE
- MANAGED_PROMPT_ROWS_IN_SHARED_TRANSACTION: TWELVE
- TRANSACTION_HANDLES_FOR_MUTATION: ONE
- FUNCTION_DRIFT_GUARD: PASSED
- PROMPT_DRIFT_GUARD: PASSED
- CROSS_FAMILY_PARTIAL_COMMIT: ZERO
- ROLLBACK_SNAPSHOT_FAMILIES: TWO
- ROLLBACK_REHEARSAL_FAMILIES: TWO
- UNCHANGED_PROMPT_REWRITES: ZERO
- ACTION_LOADER_IMAGE_MUTATION: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5H implementation is complete. Goal 2 remains pending for the exact merged
revision's atomic release and native workflow reproof.
