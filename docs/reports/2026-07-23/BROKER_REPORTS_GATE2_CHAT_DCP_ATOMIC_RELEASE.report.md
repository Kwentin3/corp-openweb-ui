# Broker Reports — Gate 2 Chat DCP Atomic Release

Date: 2026-07-23

Branch: `codex/broker-reports-gate2-chat-dcp-release-v1`

Status: `PASSED`

## Outcome

The server-side Gate 2 chat-to-DCP resolution correction was released from
the exact merged source revision
`f442a139a784f6918464bb15f709b684f4a6a8db`.

- Release ID: `broker-reports-f442a139a784`.
- Manifest SHA-256:
  `3236e836c5d62fe4c0670dabb6c8b336d3ce6dc780c4e6c1a1cd4074ee2531b7`.
- Rollback identity SHA-256:
  `289cec9c627a64b6993aed280f7ef1acb9089f3b530b98ee815c322c502f2444`.
- Atomic apply: passed.
- Independent verification: passed.

## Exact release boundary

Only the two Gate 2 Functions required a change:

| Runtime object | Before SHA-256 | Released SHA-256 |
|---|---|---|
| `broker_reports_gate2_source_fact_pipe` | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` | `45de78ac87f44a7f30d8dacc4d3d1bd3edbbafbc5002708776726d51edf2ce3e` |
| `broker_reports_gate2_domain_source_fact_pipe` | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` | `c26ae568bcaa8987abb581528abe20299ff50d3b853d402d31253211349be6dd` |

The following runtime identities were unchanged:

| Runtime object | SHA-256 |
|---|---|
| `broker_reports_gate1_pipe` | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| `broker_reports_private_intake_action` | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| loader | `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f` |

All 12 managed prompts and the configured image identity also remained exact.
This release did not mix the server correction with any UI or loader change.

## Release proof

The successful dry run confirmed:

- the source revision exactly matched repository `HEAD`;
- the worktree was clean and had no commits ahead of `origin/main`;
- only two Gate 2 Function updates were planned;
- the workload was quiescent;
- no owned temporary entries existed.

The maintained atomic release then proved the complete
candidate → previous state → candidate sequence:

- three Function health checks passed;
- rollback artifact created;
- previous Function and loader states restored exactly;
- candidate Function and loader states restored exactly;
- release staging removed;
- final candidate state active.

One earlier dry-run process was interrupted locally. A subsequent staging
preparation attempt returned a nonzero status before payload copy or apply.
Neither attempt changed the live stage. The successful dry run, atomic apply,
and independent verifier all completed afterward; the verifier found zero
release-staging entries.

## Counter invariants

Before and after values were identical:

| Counter | Before | After |
|---|---:|---:|
| Knowledge rows | 0 | 0 |
| Document rows | 0 | 0 |
| File rows | 272 | 272 |
| Vector files | 595 | 595 |
| Vector bytes | 309,808,908 | 309,808,908 |

No Knowledge/RAG/vector mutation occurred. Final nonterminal workload jobs and
owned temporary entries were both zero.

## Independent acceptance

The independent release verifier passed:

- all three live Function bundles exact;
- all 12 managed prompts exact;
- Action, loader, image, manifest and source revision exact;
- rollback identity and rollback loader hash exact;
- repository factory boundary passed;
- semantic contract identity exact;
- workload and temporary storage clean.

This closes the atomic release step only. Browser acceptance remains
`NOT_CLOSED` until a fresh native click-through proves the Gate 2 continuation
in the same chat.
