# Broker Reports Workflow Goal 4 — Product UX And Failure-Semantics Audit

Date: 2026-07-22

Branch: `codex/broker-reports-goal4-product-ux-audit-v1`

Reviewer status:

- `reviewer_kind: delegated_agent`
- `human_reviewed: false`
- `customer_accepted: false`

Status: PASSED

## Scope and method

The audit assessed the completed native Broker Reports workflow from the user
boundary. Built-in Playwright MCP tools were unavailable in this environment,
so the browser check used the repository's ignored local Playwright installation
with system Chrome.

The browser opened the existing authenticated OpenWebUI chat read-only. It did
not upload the private corpus again, send another model request, persist page
text, or create screenshots. Final-answer usability was evaluated from the
actual native chat-completion response already captured in the sealed private
checksum receipt. Failure, retry and cancellation semantics were corroborated
against maintained production contracts and focused tests.

## Actual browser evidence

- authenticated login: passed;
- existing chat route loaded: passed;
- authenticated chat API read: HTTP 200;
- chat payload present: yes;
- visible processing language: yes;
- visible completed language: yes;
- visible technical stack or internal artifact IDs: no;
- composer available after completion: yes;
- persisted page text or screenshot in evidence: no.

Private browser receipt SHA-256:
`156b0a2d5a6e3c1f2b04a16b5c77eb3a144acf4a7af8859b82593cf63e66edf5`.

The terminal view does not need to retain the original attachment card: source
eligibility and byte resolution were already established by the authenticated
private-intake smoke, while the visible workflow reports processing and its
terminal result without exposing source data.

## Answer and source-reference usability

The actual answer model response used normal Markdown rather than model-facing
JSON. It presented exactly three data rows and no extra control metrics. The
sealed deterministic comparison passed all requested fields:

| Check | Result |
|---|---:|
| Source label | 3/3 |
| Amount | 3/3 |
| Currency or unit | 3/3 |
| Sign | 3/3 |
| Period | 3/3 |
| Source page/reference | 3/3 |
| Arithmetic reconciliation | 1/1 |
| Semantic-table focused follow-up | passed |
| Duplicate counting findings | 0 |
| Invented control metrics | 0 |
| Technical JSON/internal IDs in chat | 0 |

Private rescored answer receipt SHA-256:
`9fd71077755df65450bb8c5dff163bc9736242d8485d8a5fa11b7dce1dbc1084`.

The period comparison applies presentation-only normalization for ISO, numeric
and unambiguous word-month dates. The answer itself was not repaired, and the
sealed reference was not modified.

## Failure, retry, cancellation and follow-up

- Upload and unsupported-format outcomes use short user messages with an
  explicit next action; private diagnostics remain outside model/user output.
- Queued, running and terminal states are persisted and emitted to the native
  OpenWebUI status channel.
- Success, partial and failure are distinct terminal outcomes. Unsupported or
  invalid scopes do not publish a false successful result.
- Cancellation reports that no partial success was published and cannot be
  converted into completion after the cancellation flag is observed.
- Retry is policy-bound to retryable terminal jobs, and Gate 1 idempotency
  reuses the existing workload for the same chat and source set.
- The focused follow-up used the already assembled answer context. It had no
  raw PDF, crop or sealed-reference access and produced zero Knowledge/RAG and
  vector delta; the document workflow was not rerun.

Focused regression:

```text
61 passed
```

The covered suites exercise safe file outcomes, workload admission and visible
terminal state, Gate 1 idempotency/cancellation, and file-processing
integration.

## Acceptance

| Invariant | Result |
|---|---|
| `UPLOAD_FEEDBACK` | `UNDERSTANDABLE` |
| `PROCESSING_PROGRESS` | `VISIBLE` |
| `TERMINAL_STATUS` | `UNAMBIGUOUS` |
| `ANSWER_READABILITY` | `PASSED` |
| `SOURCE_REFERENCE_USABILITY` | `PASSED` |
| `UNSUPPORTED_SCOPE_MESSAGE` | `FAIL_CLOSED_AND_UNDERSTANDABLE` |
| `FALSE_COMPLETION` | `ZERO` |
| `UNNECESSARY_DOCUMENT_REPROCESSING_ON_FOLLOWUP` | `ZERO` |

No material UX defect was found. No UI or runtime change is warranted by this
audit.
