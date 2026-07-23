# Broker Reports — Native Gate 2 Domain UI Chat Binding Atomic Release

Date: 2026-07-23

Branch: `codex/broker-reports-native-gate2-domain-ui-chat-binding-release-v1`

Status: `PASSED`

## Release

- Exact source revision:
  `4f80f91c0427740f91acd3134c70d9271aab24bb`.
- Release ID: `broker-reports-4f80f91c0427`.
- Manifest SHA-256:
  `5f94335b9c61954df97b41d28b8f766a5eb4776c333d3d170f5910c778303615`.
- Rollback identity SHA-256:
  `e2e6e5a5de12f3955b8bc8f54bfd9897392cd6fb81b7f93d3cd1633865b880c9`.

The release changed exactly one runtime object: the static loader.

| Runtime object | Before SHA-256 | Released SHA-256 |
|---|---|---|
| loader | `acfa00e051d9781552489df323a1d9520aa88bec248d8f7d89e447eba798e47a` | `51e836b02e2c71aa61e2ff4faff0e43f762b70d3ecf41fdbbffb73bf5d3891f7` |

The three Functions, protected Action, 12 managed prompts and image identity
were unchanged.

## Atomic proof

The dry run proved:

- exact clean source revision;
- a loader-only change plan;
- unchanged Function, Action, prompt and image identities;
- quiescent workload authority and clean owned temporary storage.

The atomic apply proved:

- three Function health checks passed;
- rollback artifact created;
- previous loader and Function states restored exactly;
- candidate loader and Function states restored exactly;
- release staging removed;
- final candidate state active.

The independent verifier passed immediately after release and again after the
post-release browser control.

## Post-release native control

A no-PDF system-Chrome control used the actually deployed loader with no local
loader injection.

| Invariant | Result |
|---|---:|
| Domain Gate 2 model selected in native UI | true |
| Top-level `chat_id` present | true |
| `metadata.chat_id` present | true |
| Completion response chat equals active chat | true |
| Route remains on active chat | true |
| Browser page errors | 0 |

The control invoked no PDF intake, visual provider, answer run or customer
value comparison. Its test chats were deleted.

## Runtime invariants

Atomic-release counters were identical before and after:

| Counter | Before | After |
|---|---:|---:|
| Knowledge rows | 0 | 0 |
| Document rows | 0 | 0 |
| File rows | 272 | 272 |
| Vector files | 595 | 595 |
| Vector bytes | 309,808,908 | 309,808,908 |

The final verifier reported:

- live loader exact;
- three Function bundles exact;
- 12 managed prompts exact;
- Action, image, manifest and source revision exact;
- release staging entries: 0;
- nonterminal workload jobs: 0;
- owned temporary entries: 0.

No Knowledge/RAG/vector mutation occurred.

## Remaining acceptance

This closes the loader release and domain same-chat no-PDF control. It does not
close the full PDF workflow.

The live domain Function still defaults to one document batch, one source unit
and one source segment when the browser supplies no explicit runtime
configuration. That scope is insufficient for a report-wide semantic checksum
and must be resolved separately before consuming another PDF run.

`GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` remains `NOT_CLOSED`.
