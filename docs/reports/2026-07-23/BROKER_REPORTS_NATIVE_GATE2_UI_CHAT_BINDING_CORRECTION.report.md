# Broker Reports — Native Gate 2 UI Chat Binding Correction

Date: 2026-07-23

Branch: `codex/broker-reports-native-gate2-ui-submit-correction-v1`

Status: `PASSED_IMPLEMENTATION`

## Problem

The native model-switch continuation did not preserve the completed Gate 1
chat.

A transport-neutral browser control showed the exact request defect:

- the selected model was `broker_reports_gate2_source_fact_pipe`;
- the native completion body had neither top-level `chat_id` nor
  `metadata.chat_id`;
- the server response created a different chat;
- the browser route then moved away from the Gate 1 chat.

The v3 PDF click-through also observed a native send that produced no
completion request. Inspection of the deployed OpenWebUI frontend showed that
a message is queued instead of submitted while its in-memory latest assistant
state is still nonterminal. The full acceptance rerun must therefore wait for
the visible native assistant terminal state, not only for the server task
counter.

## Correction

`deploy/openwebui-static/loader.js` now binds only the Gate 2 source-model
completion to the persistent chat ID in the active `/c/{id}` or `/chat/{id}`
route.

The loader adds the same validated UUID to:

- top-level `chat_id`;
- `metadata.chat_id`.

The correction stays inside the existing fetch patch and forwards the request
through OpenWebUI's native completion transport. It does not create a second
Gate 2 client, call a provider directly, synthesize an assistant answer, or
parse private report contents.

Fail-closed boundaries:

- only `POST /api/chat/completions` is eligible;
- only `broker_reports_gate2_source_fact_pipe` is eligible;
- only a persistent UUID chat route is accepted;
- a new-chat route is left unchanged;
- Gate 1 and every non-Gate 2 model request are left unchanged;
- both string-body and native `Request` transports are covered.

Candidate loader SHA-256:
`399b20cd3a81ca365bca5a487b76f55d7bad6fc4421d44b6f0a87e385c0818d8`.

No Gate 1 Function, Gate 2 Function, Action, managed prompt, semantic JSON
contract, provider policy or image code changed.

## Live browser control

The same no-PDF control was run before and with the candidate loader:

| Invariant | Before candidate | Candidate |
|---|---:|---:|
| Gate 2 model selected | true | true |
| Top-level `chat_id` present | false | true |
| `metadata.chat_id` present | false | true |
| Response chat equals active chat | false | true |
| Route remains on active chat | false | true |
| Browser page errors | 0 | 0 |

The candidate control used the visible model selector and composer send
control. It processed no PDF, invoked no visual provider, and created no Gate 1
reprocessing.

## Verification

- Node behavioral tests: 4 passed.
  - active Gate 2 chat is bound;
  - non-Gate 2 request is unchanged;
  - new-chat Gate 2 request remains unchanged;
  - native `Request` body is bound without replacing the transport.
- Stage 2 suite: 109 passed.
- Atomic-release and privacy focus: 21 passed.
- Full Broker Reports suite: 1,147 passed, 20 skipped, 0 failed.
- Changed Python contour Ruff: passed.
- Loader and behavioral-test JavaScript syntax checks: passed.
- Repository diff check: passed.

The behavioral tests execute the real loader in a bounded JavaScript runtime
and assert the body received by the downstream native fetch boundary. They are
not snapshot-only tests.

## Remaining acceptance

This implementation is not yet a production browser closure.

Mandatory next steps are:

1. merge this correction as its own PR;
2. release the exact merged loader revision atomically without changing
   Functions, Action, prompts or image;
3. run one fresh native PDF click-through;
4. wait for the visible native Gate 1 assistant terminal state before the
   Gate 2 send;
5. require one same-chat Gate 2 source workload before any answer run.

Until those steps pass, `GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` remains
`NOT_CLOSED`.
