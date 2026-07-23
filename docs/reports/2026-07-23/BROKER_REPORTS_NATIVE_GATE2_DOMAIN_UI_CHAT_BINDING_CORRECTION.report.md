# Broker Reports — Native Gate 2 Domain UI Chat Binding Correction

Date: 2026-07-23

Branch: `codex/broker-reports-native-gate2-domain-ui-chat-binding-correction-v1`

Base revision: `bd0a448dd31439aa13dc1830aadcfd44a8d7da09`

Status: `PASSED_IMPLEMENTATION`

## Problem

The production loader preserved the active chat for the Gate 2 source-fact
model, but not for the following Gate 2 domain model.

A no-PDF native Chrome control reproduced the defect on an existing chat:

- the visible model selector selected the domain model;
- the native completion body had neither top-level `chat_id` nor
  `metadata.chat_id`;
- the completion response referred to a different chat;
- the browser route moved away from the existing chat;
- no browser page error occurred.

The control did not process a PDF, invoke a visual provider or create a
customer evidence run.

## Correction

`deploy/openwebui-static/loader.js` now applies the existing persistent-chat
binding to the two maintained Gate 2 models:

- `broker_reports_gate2_source_fact_pipe`;
- `broker_reports_gate2_domain_source_fact_pipe`.

For an eligible `POST /api/chat/completions`, the loader copies the validated
UUID from the active `/c/{id}` or `/chat/{id}` route to top-level `chat_id` and
`metadata.chat_id`.

The correction remains inside OpenWebUI's native fetch transport. It does not
create a second completion client, call a provider directly, inject answer
content, parse report data or change Gate 1, Gate 2 Functions, Action, prompts,
semantic contracts, provider policy or image code.

Fail-closed behavior remains unchanged:

- non-Gate 2 models are not rewritten;
- non-completion requests are not rewritten;
- a new-chat route is not rewritten;
- an invalid or missing persistent chat UUID is not rewritten;
- both string-body and native `Request` transports remain supported.

Candidate loader SHA-256:
`152f74d6a19f07d3cb5cc74ca50a15c8f77d1baf4af28ea48c71c7b40363e9de`.

## Live browser control

| Invariant | Production before candidate | Candidate |
|---|---:|---:|
| Domain Gate 2 model selected | true | true |
| Top-level `chat_id` present | false | true |
| `metadata.chat_id` present | false | true |
| Response chat equals active chat | false | true |
| Route remains on active chat | false | true |
| Browser page errors | 0 | 0 |

The candidate control used the visible model selector and composer send
control. The candidate loader was injected before page startup only for this
bounded proof.

## Verification

- Loader behavioral tests: 5 passed.
- Stage 2 suite: 109 passed.
- Full Broker Reports suite: 1,147 passed, 20 skipped, 0 failed.
- Loader and behavioral-test JavaScript syntax checks: passed.
- Repository diff check: passed.

The new behavioral test executes the real loader and asserts the request body
received at the downstream native fetch boundary. It is not snapshot-only.

## Remaining acceptance

This implementation is not a production release and does not close the native
browser acceptance.

Required next steps:

1. merge this correction in its own PR;
2. release the exact merged loader revision atomically;
3. separately resolve or explicitly close the incomplete default scope of the
   domain extraction Function;
4. run one fresh end-to-end native browser route only after those preconditions
   pass.

`GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` remains `NOT_CLOSED`.
