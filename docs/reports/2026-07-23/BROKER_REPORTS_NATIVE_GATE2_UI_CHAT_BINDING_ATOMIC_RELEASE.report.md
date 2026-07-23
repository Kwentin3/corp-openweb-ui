# Broker Reports — Native Gate 2 UI Chat Binding Atomic Release

Date: 2026-07-23

Branch: `codex/broker-reports-native-gate2-ui-chat-binding-release-v1`

Status: `PASSED`

## Release

- Exact source revision:
  `37c21d11e574bebe6fc564ba7ad77bb6f68b789b`.
- Release ID: `broker-reports-37c21d11e574`.
- Manifest SHA-256:
  `12968e2a613cd5b6583613b33976c6b7da0fd56f3cd11e193f793eeb66636f4e`.
- Rollback identity SHA-256:
  `ea7c8e880cc9df4e0b235cbd3084d148d26d714be5c00600cdd34b4915a2d8a4`.

The release changed exactly one runtime object: the static loader.

| Runtime object | Before SHA-256 | Released SHA-256 |
|---|---|---|
| loader | `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f` | `acfa00e051d9781552489df323a1d9520aa88bec248d8f7d89e447eba798e47a` |

All three Functions, the protected Action, 12 managed prompts and the image
identity were unchanged.

## Loader byte identity clarification

The correction report recorded
`399b20cd3a81ca365bca5a487b76f55d7bad6fc4421d44b6f0a87e385c0818d8`
from the Windows working-tree representation, where Git may expose CRLF line
endings.

That value is not the release identity.

The atomic release correctly read
`37c21d11e574bebe6fc564ba7ad77bb6f68b789b:deploy/openwebui-static/loader.js`
as an exact Git blob. Its SHA-256 is
`acfa00e051d9781552489df323a1d9520aa88bec248d8f7d89e447eba798e47a`,
which now matches the live stage and the independent verifier.

## Atomic proof

The successful dry run proved:

- exact clean source revision;
- loader-only change plan;
- unchanged Function, Action and prompt identities;
- quiescent workload and clean temporary storage.

The atomic apply then proved:

- three Function health checks passed;
- rollback artifact created;
- previous loader and Function states restored exactly;
- candidate loader and Function states restored exactly;
- release staging removed;
- final candidate state active.

The independent verifier passed twice: immediately after release and again
after the post-release browser control.

## Post-release native control

A no-PDF system-Chrome control used the actually deployed loader, with no
local script injection.

| Invariant | Result |
|---|---:|
| Gate 2 model selected in native UI | true |
| Top-level `chat_id` present | true |
| `metadata.chat_id` present | true |
| Completion response chat equals active chat | true |
| Route remains on active chat | true |
| Browser page errors | 0 |

The control invoked no PDF intake, VLM provider, answer run or customer-value
comparison. Its test chat records were deleted.

## Runtime invariants

Atomic-release counters were identical before and after:

| Counter | Before | After |
|---|---:|---:|
| Knowledge rows | 0 | 0 |
| Document rows | 0 | 0 |
| File rows | 272 | 272 |
| Vector files | 595 | 595 |
| Vector bytes | 309,808,908 | 309,808,908 |

The final post-control verifier reported:

- live loader exact;
- three Function bundles exact;
- 12 managed prompts exact;
- Action, image, manifest and source revision exact;
- release staging entries: 0;
- nonterminal workload jobs: 0;
- owned temporary entries: 0.

No Knowledge/RAG/vector mutation occurred.

## Remaining acceptance

This closes the atomic loader release and same-chat no-PDF control. It does
not yet close the full PDF workflow.

`GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` remains `NOT_CLOSED` until one fresh
native PDF run proves Gate 1 terminal UI state, same-chat Gate 2 source
completion, answer context, user question and source-only checksum checks.
