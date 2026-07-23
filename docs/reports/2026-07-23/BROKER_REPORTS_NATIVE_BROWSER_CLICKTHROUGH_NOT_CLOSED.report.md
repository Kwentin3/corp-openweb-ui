# Broker Reports — Native Browser Clickthrough Not Closed

Date: 2026-07-23

Branch: `codex/broker-reports-native-browser-clickthrough-v1`

GOAL status: `NOT_CLOSED`

Stage runtime source revision:
`287d2bd255a8023b076a3fa0e688f18e3f509a04`

## First violated invariant

A Broker Reports PDF selected through the real OpenWebUI attachment control
must enter the server-authoritative private-intake route and the visible Broker
Reports button must invoke the protected private-intake Action.

The live browser route instead did this:

```text
UI attachment input
  -> POST /api/v1/files/ (200)
  -> ordinary non-reserved file id
  -> visible Gate 1 button
  -> POST /api/chat/actions/broker_reports_gate1_normalizer_action (200)
```

It did not call:

```text
POST /api/v1/broker-reports/intake
POST /api/chat/actions/broker_reports_private_intake_action
```

The browser visibly moved through `ready`, `broker_gate1_running` and
`broker_gate1_completed`, so the incorrect boundary was presented as success.
The audit stopped before any chat completion, Gate 1 Function run, answering
model call or checksum comparison.

## Primary browser evidence

- Browser harness: local Playwright with system Chrome.
- Built-in Playwright MCP tools: unavailable in the current session.
- Login: passed.
- Fresh New Chat surface: passed; no chat record was created before the stop.
- Real hidden UI file input: used.
- Upload HTTP status: `200`.
- Visible Broker Reports/Gate 1 button: present and clicked.
- Action HTTP status: `200`.
- Protected private-intake Action invoked: false.
- Legacy normalizer Action invoked: true.
- Answer run started: false.
- Answer repair: zero.
- Sealed reference mutation: zero.
- Private browser receipt SHA-256:
  `bf5fc789722eb731d06410b209abb1afacf104a1e6f10643b00841c92f80b53e`.

No DOM dump, screenshot, source path, customer label, customer value, credential
or provider response was persisted.

## Measured no-RAG violation and cleanup

Baseline:

| Counter | Value |
|---|---:|
| ArtifactStore records | 16330 |
| file rows | 272 |
| document rows | 0 |
| knowledge rows | 0 |
| vector collections | 146 |
| vector directories | 146 |
| vector files | 595 |
| vector bytes | 309808908 |

The uploaded file was deleted through the supported file API with status
`200`. File/document/knowledge counters returned to baseline, but native
background processing had raced with deletion and created one vector
collection containing 26 embeddings. Its physical delta was one directory,
four files and 168100 bytes.

Cleanup was exact and fail-closed:

1. The collection was identified as the only collection with the audit-time
   timestamp and its expected hashed identity.
2. Chroma collection identity, embedding count and time were checked.
3. The collection was deleted through the OpenWebUI Chroma client.
4. The single remaining physical directory was verified to be unreferenced,
   to resolve directly below `vector_db`, and to contain exactly the four
   measured files before removal.
5. A new runtime snapshot matched every baseline counter exactly.

Final cleanup state:

- ArtifactStore records: `16330`;
- file rows: `272`;
- document rows: `0`;
- knowledge rows: `0`;
- vector collections/directories/files/bytes:
  `146 / 146 / 595 / 309808908`;
- nonterminal workload jobs: `0`;
- owned temporary entries: `0`;
- test-only file removed: yes;
- test-only chat created: no;
- immutable ArtifactStore audit evidence deleted: no.

## Attribution

- Owning component: deployed OpenWebUI static loader, Broker Reports document
  upload and Action wiring.
- Blocker type: `NATIVE_UI_PRIVATE_INTAKE_ACTION_INTEGRATION_DEFECT`.
- This is not a semantic JSON, Gemini policy, crop, OCR, Gate 1 extraction,
  Gate 2 or answer-context defect.

The deployed loader currently:

- leaves Broker Reports document uploads on ordinary `/api/v1/files/`;
- publishes the global proof-only `broker_reports_gate1_normalizer_action`;
- does not route the button through the protected
  `broker_reports_private_intake_action`.

## Narrow corrective slice

A separate correction branch must:

- redirect eligible Broker Reports document uploads selected in the OpenWebUI
  attachment control to `/api/v1/broker-reports/intake` with a fresh
  idempotency identity;
- retain the response as a normal attachment whose source id is in the
  reserved private family;
- invoke `broker_reports_private_intake_action` from the visible Broker Reports
  button;
- show truthful accepted/running/completed or failed states;
- remove the legacy normalizer Action from this UI route;
- add loader tests proving no native processing, Knowledge, RAG, embeddings or
  vectorization;
- atomically release and roll back/read back the exact correction;
- repeat the complete browser clickthrough from a fresh chat.

No runtime correction is included in this audit branch.

GOAL_2_NATIVE_BROWSER_CLICKTHROUGH: `NOT_CLOSED`.
