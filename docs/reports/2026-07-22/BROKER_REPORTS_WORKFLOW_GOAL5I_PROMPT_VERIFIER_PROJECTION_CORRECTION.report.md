# Broker Reports Workflow Goal 5I — Prompt Verifier Projection Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5i-prompt-verifier-projection-v1`

Correction family: independent live verification

Implementation status: PASSED

Live re-verification: PENDING AFTER MERGE

## Trigger

The Goal 5H atomic release passed its transactional checks and rollback
rehearsal. The independent verifier then reported one metadata-subset mismatch
for the newly revised source-fact prompt while its content, command, version,
active state, Function bundles, runtime identities and rollback identity were
exact.

## Root cause

The shared read-only prompt probe projected a fixed safe metadata subset. The
source prompt contract had gained `provider_output_schema_version`, but the
probe did not include that key in its projection. The release wrote and checked
the metadata correctly; the independent verifier discarded the field before
performing the comparison.

## Narrow correction

- Added `provider_output_schema_version` to the safe live-prompt metadata
  projection.
- Added a regression assertion that the remote probe carries this field.
- Did not mutate Functions, Prompts, Action, loader, image, data stores,
  workload state, RAG/vector state or OCR configuration.

## Verification

- focused verifier tests: 7 passed;
- Ruff: passed;
- Python compile check: passed;
- `git diff --check`: passed;
- private source-label findings: 0;
- private formatted-value findings: 0.

Verifier SHA-256:
`a9f0a515999e6090d22dc654e182b39ec2754947fd203bab469d35552119435c`

## Decision

The production release is retained. After this correction is merged, the same
independent verifier must be rerun against release
`broker-reports-3e59ddcdf063` and the existing rollback identity. Goal 5I closes
only when that read-only run passes.
