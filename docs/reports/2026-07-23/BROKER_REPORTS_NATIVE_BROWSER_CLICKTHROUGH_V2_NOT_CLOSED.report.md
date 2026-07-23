# Broker Reports Native Browser Click-through v2

Date: 2026-07-23

Branch: `codex/broker-reports-native-browser-clickthrough-v2`

Audit base revision: `ee5be6cdd25318a2394b9250f126ca9ed68e01fd`

Stage source revision: `7176aaf0b3c22f96b9331a73d2b6a87ed2793b08`

Status: `NOT_CLOSED`

## Outcome

The released private-intake correction works in the live native browser:

- system Chrome and the local Playwright harness logged into the existing
  account;
- a fresh OpenWebUI chat surface was used;
- the real UI attachment control sent the selected authorized PDF to
  `POST /api/v1/broker-reports/intake`;
- the response used a reserved private source identity;
- the visible Broker Reports button invoked only
  `broker_reports_private_intake_action`;
- the composer submitted the source to `broker_reports_gate1_pipe`;
- the latest measured run produced one completed Gate 1 workload and exactly
  one domain-context packet;
- Knowledge, document and vector counters stayed at their no-RAG baseline;
- test-only OpenWebUI chat and file records were deleted;
- no nonterminal workload or owned temporary entry remained.

The route cannot proceed natively from successful Gate 1 to Gate 2.

After Gate 1 reaches its terminal state, the UI visibly selects
`Broker Reports Gate 2 Source Facts` and exposes an enabled send button.
Clicking it does not emit `POST /api/chat/completions`. The browser harness
waited 120 seconds and stopped at the safe phase `gate2_send`. No Gate 2
workload was created.

A transport-neutral empty-chat control isolated a second boundary condition:
when the same model switch is exercised without the successful Broker Reports
attachment state, the request is accepted with the correct Gate 2 model ID,
but it has no `broker_reports_gate2` configuration and the server creates a
different chat. It therefore cannot bind the Gate 1 chat's DCP.

The required single route

`upload -> Action -> Gate 1 -> Gate 2 -> answer context -> question -> answer`

is not available to a user through the current native UI.

## Primary evidence

Latest successful Gate 1 execution:

| Field | Result |
|---|---|
| Browser harness | local Playwright with system Chrome |
| Gate 1 workload | `brjob_caa69deffe4f49e87a3b2125f03082ed` |
| Gate 1 chat | `e7e27dab-7caf-461b-85f2-a3c13efd0a75` |
| Workload sequence | `27` |
| Terminal state | `completed` |
| Domain-context packets | `1` |
| Chat-scoped ArtifactStore records | `64` |
| Gate 2 workloads for this chat | `0` |
| Browser terminal phase | `gate2_send` |
| Completion request observed after Gate 2 send | `false` |
| Wait before fail-closed | `120 seconds` |

The Gate 1 transition history included queued, source intake, normalization,
document-memory construction, validation, provider waits and completed
terminal state. No client values or provider output were read into the report.

Empty-chat control:

| Invariant | Result |
|---|---|
| Gate 2 model selected in the UI | `true` |
| Completion HTTP status | `200` |
| Request model | `broker_reports_gate2_source_fact_pipe` |
| `broker_reports_gate2` config present | `false` |
| Gate 1 and Gate 2 response chat equal | `false` |

This control is diagnostic only. It did not process a PDF and did not start a
Gate 2 workload.

## Cleanup and no-RAG boundary

Post-cleanup live counters:

| Counter | Value |
|---|---:|
| OpenWebUI files | 272 |
| OpenWebUI documents | 0 |
| OpenWebUI Knowledge rows | 0 |
| Vector collections | 146 |
| Vector directories | 146 |
| Vector files | 595 |
| Vector bytes | 309808908 |
| ArtifactStore records | 16640 |
| Nonterminal workloads | 0 |
| Owned temporary entries | 0 |

The file, document, Knowledge and vector values equal the established
pre-run baseline. ArtifactStore growth is immutable audit evidence and was
retained according to policy.

The test-only OpenWebUI file and chat records were deleted after each attempt.
No screenshot, DOM dump, source path, customer filename, customer value or
provider raw response was persisted.

## Control-vector integrity

The three-metric source-only reference was sealed before the browser work:

- reference SHA-256:
  `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`;
- seal SHA-256:
  `607000fb3a42ba1cacfd081af29c2b6dbe79ad9d181bfa0a8b4de82a11d6431d`;
- metric count: `3`;
- reference mutation: `0`;
- answer runs: `0`;
- answer repair: `0`.

The checksum comparison and semantic-table follow-up were not run because the
workflow failed closed before Gate 2.

## Harness attempts

Four fresh PDF attempts completed Gate 1 while the browser harness was being
narrowed:

1. the first stopped on an overly strict model-option locator;
2. the next three reached `gate2_send` but observed no completion request.

Each attempt used a fresh chat and performed supported cleanup. These attempts
are not presented as a passed workflow. The resulting unnecessary
reprocessing count is `3`, so the acceptance invariant is explicitly not met.
The immutable ArtifactStore records are retained and not erased.

## Failed invariant and ownership

- Violated invariant:
  `native_browser_gate2_source_request_must_remain_in_the_gate1_chat_and_bind_its_unique_owner_scoped_dcp`.
- Primary evidence: successful single-workload Gate 1 browser run followed by
  no completion request at `gate2_send`, plus the empty-chat model-switch
  control.
- Owning boundary:
  `openwebui_broker_reports_model_switch_and_gate2_native_chat_binding_boundary`.
- Blocker type: native UI and Gate 2 chat-context binding defect.
- Narrowest corrective slice: preserve the completed Gate 1 chat scope for the
  Gate 2 UI continuation and resolve its unique owner-scoped DCP on the server
  when an explicit ref is absent.

The correction must not change the semantic JSON contract, VLM prompt,
provider policy, OCR boundary, Knowledge/RAG policy or source truth.

## Terminal classification

`BROWSER_UPLOAD`: `PASSED`

`BROKER_REPORTS_ACTION`: `INVOKED_NATIVELY`

`VISIBLE_GATE1_PROCESSING`: `PASSED`

`GATE1_TERMINAL_STATE`: `PASSED`

`SINGLE_GATE1_DCP`: `PASSED`

`GATE2_NATIVE_CONTINUATION`: `FAILED`

`ANSWER_CONTEXT_ONLY`: `NOT_RUN_FAIL_CLOSED`

`CONTROL_VECTOR`: `NOT_RUN_FAIL_CLOSED`

`SEMANTIC_TABLE_FOLLOWUP`: `NOT_RUN_FAIL_CLOSED`

`ANSWER_REPAIR`: `ZERO`

`REFERENCE_MUTATION`: `ZERO`

`KNOWLEDGE_RAG_VECTOR_DELTA`: `ZERO`

`UNNECESSARY_REPROCESSING`: `FAILED`

`CLEANUP`: `PASSED`

`GOAL_2_NATIVE_BROWSER_CLICKTHROUGH`: `NOT_CLOSED`
