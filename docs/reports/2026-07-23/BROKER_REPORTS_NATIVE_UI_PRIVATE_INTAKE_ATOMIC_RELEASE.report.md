# Broker Reports — Native UI Private Intake Atomic Release

Date: 2026-07-23

Branch: `codex/broker-reports-native-ui-private-intake-release-v3`

Status: `PASSED`

Released source revision:
`7176aaf0b3c22f96b9331a73d2b6a87ed2793b08`

Release id: `broker-reports-7176aaf0b3c2`

## Outcome

The approved native UI private-intake loader was released through the
maintained atomic stage boundary. The exact accepted Git blob was applied,
previous state was restored, and the candidate state was restored again.

No Function bundle or managed prompt content change was required. Their
release metadata now identifies the approved source revision and manifest.

## Pre-apply validation

Dry validation passed before mutation:

- source revision equals local `HEAD`;
- worktree clean;
- source revision is based on `origin/main`;
- commits ahead of `origin/main`: `0`;
- Function content changes required: `0`;
- managed prompt changes required: `0`;
- loader change required: `1`;
- nonterminal workload jobs: `0`;
- owned temporary entries: `0`;
- staging removed: yes.

Candidate loader SHA-256:
`5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f`.

## Apply and rollback proof

Atomic apply status: `PASSED`.

- health checks passed: `3`;
- previous Function/prompt state restored: yes;
- previous loader state restored: yes;
- candidate Function/prompt state restored: yes;
- candidate loader state restored: yes;
- immutable rollback artifact created: yes;
- staging removed: yes;
- final workload nonterminal jobs: `0`;
- final owned temporary entries: `0`.

Manifest SHA-256:
`9927b131499694018c30929e93da02cfec0c55c459bbfe53545ce63d3fa4b701`.

Rollback identity SHA-256:
`2b09fccd771dacd9e01fc090ea6e63fc456ffbb3828c6edb993c9e5aa8f43e36`.

## Repository sink counters

| Counter | Before | After | Delta |
|---|---:|---:|---:|
| document rows | 0 | 0 | 0 |
| file rows | 272 | 272 | 0 |
| knowledge rows | 0 | 0 | 0 |
| vector files | 595 | 595 | 0 |
| vector bytes | 309808908 | 309808908 | 0 |

Knowledge/RAG/vector mutation: `ZERO`.

## Released identities

| Object | Identity |
|---|---|
| Gate 1 Function | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source Function | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain Function | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |
| Private-intake Action | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| UI loader Git blob | `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f` |
| Runtime image | `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83` |
| Image source revision | `8e6a71f13cf4f9cec0e5be191fac924548050e48` |

All three Functions are active, non-global pipes. The private-intake Action is
active and non-global. All 12 managed prompts are present, active and exact.

## Independent readback

The independent live verifier passed after apply.

- all Function bundles exact: yes;
- private-intake Action exact: yes;
- all managed prompts exact: yes;
- loader hash exact: yes;
- image identity and runtime state exact: yes;
- rollback metadata identity exact: yes;
- rollback loader bytes exact: yes;
- release staging clean: yes;
- workload and temporary storage quiescent: yes;
- repository factory boundary: passed;
- no Paddle/local OCR production dependency: passed;
- Knowledge/RAG/vectorization forbidden: passed;
- qualified semantic VLM defaults active: passed.

No private document, customer value, source filename, provider response or
browser data was stored in this report.

Next required step: repeat the native browser click-through from a fresh chat
against this released revision.

