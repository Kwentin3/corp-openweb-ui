# Broker Reports Native Browser Click-through v3

Date: 2026-07-23

Branch: `codex/broker-reports-native-browser-clickthrough-v3`

Audit base revision: `f2dcd0814df4b89970d6a03cb44e066b2a963328`

Stage source revision: `f442a139a784f6918464bb15f709b684f4a6a8db`

Status: `NOT_CLOSED`

## Outcome

A single fresh native-browser run was performed after the server-side Gate 2
chat-to-DCP correction was released.

The live UI successfully completed:

- login through system Chrome;
- fresh-chat private PDF upload through the visible attachment control;
- the protected Broker Reports Action;
- visible `ready`, running and completed Action states;
- one native Gate 1 completion request with one private file reference;
- one completed Gate 1 workload;
- exactly one domain-context packet;
- terminal, non-error Gate 1 assistant output.

The Gate 2 continuation still failed before the released server correction
could execute. The UI visibly selected
`Broker Reports Gate 2 Source Facts`, the composer contained the continuation
message, and the send control was enabled and clicked. No
`POST /api/chat/completions` request followed within the 30-second observation
window.

Only one completion request existed in the full run, and it was the Gate 1
request. No Gate 2 source workload was created.

The required route

`upload -> Action -> Gate 1 -> Gate 2 -> answer context -> question -> answer`

therefore remains unavailable through the native UI.

## Primary browser evidence

| Field | Result |
|---|---|
| Browser harness | local Playwright with system Chrome |
| Fresh PDF attempts | `1` |
| Gate 1 chat | `46ccc8a0-f82e-4320-8f0b-adaca60f6504` |
| Gate 1 workload | `brjob_d40168c03a48e5b725535ed84a1f35f7` |
| Gate 1 terminal state | `completed` |
| Gate 1 workloads | `1` |
| Domain-context packets | `1` |
| Chat-scoped ArtifactStore records | `64` |
| Gate 2 model visibly selected | `true` |
| Gate 2 send control clicked | `true` |
| Gate 2 completion request observed | `false` |
| Gate 2 source workloads | `0` |
| Answer runs | `0` |
| Answer repairs | `0` |

The browser did not retry the PDF, create a second Gate 1 workload, or use a
transport-neutral substitute. This run has no unnecessary reprocessing.

## Why the server correction did not close the route

The released correction can resolve an owner-scoped DCP from the current chat
when a Gate 2 request reaches the server without an explicit DCP reference.
This browser run never reached that boundary: the native UI emitted no Gate 2
completion request.

The remaining defect is therefore narrower than the previously corrected
server contract. It is the model-selection/composer submission transition in
the native OpenWebUI surface after a successful private Gate 1 run.

## Cleanup and no-RAG boundary

The test-only OpenWebUI file and chat records were deleted. Post-cleanup live
counters were:

| Counter | Value |
|---|---:|
| OpenWebUI files | 272 |
| OpenWebUI documents | 0 |
| OpenWebUI Knowledge rows | 0 |
| Vector collections | 146 |
| Vector directories | 146 |
| Vector files | 595 |
| Vector bytes | 309,808,908 |
| ArtifactStore records | 16,992 |
| Completed workload jobs | 44 |
| Nonterminal workload jobs | 0 |
| Owned temporary entries | 0 |

File, document, Knowledge and every vector counter returned exactly to the
pre-run baseline. ArtifactStore grew by 64 immutable audit records and was
retained by policy.

No screenshot, DOM dump, source path, customer filename, customer value,
credential or provider raw response was persisted.

## Control-vector integrity

The three-metric source-only reference remained sealed:

- reference SHA-256:
  `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`;
- seal SHA-256:
  `607000fb3a42ba1cacfd081af29c2b6dbe79ad9d181bfa0a8b4de82a11d6431d`;
- metric count: `3`;
- reference mutation: `0`;
- answer run: `0`;
- answer repair: `0`.

Checksum comparison and semantic-table follow-up were not run because the
workflow failed closed before Gate 2.

## Failed invariant and ownership

- Violated invariant:
  `native_browser_gate2_model_selection_and_composer_send_must_emit_one_native_completion_in_the_gate1_chat`.
- Owning boundary:
  `openwebui_gate2_model_selection_and_composer_submission_boundary`.
- Blocker type: native UI Gate 2 composer-submission defect.
- Narrowest corrective slice: preserve the active Gate 1 chat after selecting
  the Gate 2 source model and emit exactly one native Gate 2 completion when
  the existing composer send control is clicked.

The correction must stay in the UI/loader boundary. It must not change Gate 1,
the released Gate 2 DCP resolver, the semantic JSON contract, VLM prompt,
provider policy, OCR boundary, Knowledge/RAG policy or source truth.

## Terminal classification

`BROWSER_UPLOAD`: `PASSED`

`BROKER_REPORTS_ACTION`: `INVOKED_NATIVELY`

`VISIBLE_GATE1_PROCESSING`: `PASSED`

`GATE1_TERMINAL_STATE`: `PASSED`

`SINGLE_GATE1_DCP`: `PASSED`

`GATE2_UI_MODEL_SELECTION`: `PASSED`

`GATE2_NATIVE_COMPLETION_REQUEST`: `FAILED`

`GATE2_SOURCE_WORKLOAD`: `NOT_RUN_FAIL_CLOSED`

`ANSWER_CONTEXT_ONLY`: `NOT_RUN_FAIL_CLOSED`

`CONTROL_VECTOR_COMPARISON`: `NOT_RUN_FAIL_CLOSED`

`SEMANTIC_TABLE_FOLLOWUP`: `NOT_RUN_FAIL_CLOSED`

`ANSWER_REPAIR`: `ZERO`

`REFERENCE_MUTATION`: `ZERO`

`KNOWLEDGE_RAG_VECTOR_DELTA`: `ZERO`

`UNNECESSARY_REPROCESSING`: `ZERO`

`CLEANUP`: `PASSED`

`GOAL_2_NATIVE_BROWSER_CLICKTHROUGH`: `NOT_CLOSED`
