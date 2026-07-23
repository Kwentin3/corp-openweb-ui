# Broker Reports — Native Browser Preflight v4

Date: 2026-07-23

Branch: `codex/broker-reports-native-browser-preflight-v4-not-closed`

Repository revision:
`2a468000b7f13307e7bfe3d8dd024e47ddc74f5a`.

Live release source revision:
`4f80f91c0427740f91acd3134c70d9271aab24bb`.

Status: `NOT_CLOSED`

## Outcome

The final PDF click-through was not started.

The no-PDF preflight found two deterministic product blockers after the
same-chat browser corrections were released:

1. the native domain run defaults to an incomplete source scope but may still
   publish a completed answer context;
2. no maintained production path passes that answer context to an answering
   model from the native browser chat.

A fresh PDF run could therefore not satisfy the strict answer boundary or the
three-metric checksum. Starting it would only create unnecessary processing
and private artifacts.

## What is now proven

The two maintained Gate 2 model requests are bound to the active persistent
chat by the released loader.

The post-release domain-model control used:

- system Chrome;
- the visible model selector;
- the visible composer send control;
- the deployed loader without local injection;
- native `POST /api/chat/completions`.

It proved:

| Invariant | Result |
|---|---:|
| Domain Gate 2 model selected | true |
| Top-level `chat_id` present | true |
| `metadata.chat_id` present | true |
| Completion response chat equals active chat | true |
| Route remains on active chat | true |
| Browser page errors | 0 |

No PDF or visual provider was used in this preflight.

The atomic verifier also proved exact live identities for the loader, three
Functions, protected Action, 12 managed prompts and image. Workload authority
was quiescent and owned temporary storage was clean.

## Blocker 1 — incomplete native domain scope

The native OpenWebUI completion body supplies no
`broker_reports_gate2_domain` configuration.

The maintained domain Function therefore uses these live defaults:

- `default_document_batch_limit = 1`;
- `default_source_unit_limit = 1`;
- `default_source_segment_limit = 1`.

Primary code evidence:

- `openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py:83`;
- `openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py:84`;
- `openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py:91`;
- the fallback application at lines 253, 258 and 295.

The previously measured authorized report scope contains one source-ready
document and ten packageable source units. A native default run therefore
cannot cover the report.

The runtime currently treats a run as completed when its selected slice is
complete; it does not require all deferred documents, source units and
segments to be exhausted before building an answer context. This creates a
false-complete risk for a browser request without explicit batch controls.

Failed invariant:
`ANSWER_CONTEXT_REPORT_SCOPE_COMPLETE`.

Owning component:
`broker_reports_gate2_domain_source_fact_pipe` and domain runtime completeness
policy.

Blocker type:
product runtime completeness.

## Blocker 2 — no native answer-context handoff

Answer-context construction and protected resolution exist:

- the domain runtime builds and persists an answer context after a completed
  extraction;
- `AnswerContextSelectionService.resolve_for_answer` validates and resolves it
  under private access control.

However, repository-wide production search found no call to
`resolve_for_answer` outside tests. The maintained domain Function returns
only `result.compact_russian_summary` and does not send the user's natural
question plus resolved answer context to an answering model.

Primary code evidence:

- `broker_reports_gate1/answer_context_selection.py:239`;
- `openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py:358`;
- production call sites for `resolve_for_answer`: zero.

An ordinary model selected afterward receives the visible chat history, not
the private assembled answer context. The previously successful semantic
checksum used an out-of-browser harness that manually supplied the resolved
context to `/api/chat/completions`; that is valid model evidence but not a
native user click-through.

Failed invariant:
`ANSWER_CONTEXT_ONLY_NATIVE_BROWSER_HANDOFF`.

Owning component:
the maintained Gate 2 domain Function/native answer integration boundary.

Blocker type:
missing product integration, not browser transport, VLM, semantic JSON,
provider availability, test fixture or environment.

## Narrowest corrective slices

These must remain separate from evidence branches and from each other:

1. make customer-mode domain completion either cover the complete authorized
   report scope or fail closed before answer-context publication when any
   source scope remains deferred;
2. add an answer-context-only mode inside a maintained Function boundary that:
   resolves the latest complete context by authenticated chat scope, passes
   only that context and the current user question through the existing
   OpenWebUI provider connection under WorkloadAuthority, and reuses the same
   context for follow-up without extraction;
3. keep the answer instruction managed, prevent technical JSON/internal IDs
   from user-visible output, and persist only safe execution evidence;
4. release each runtime correction atomically, then run exactly one fresh
   PDF click-through.

No semantic visual-table contract, crop extraction, Gemini-master policy,
Knowledge/RAG/vector path, OCR stack or Markdown runtime needs to change.

## Runtime state after preflight

| Invariant | Result |
|---|---:|
| Knowledge rows | 0 |
| Document rows | 0 |
| File rows | 272 |
| Vector files | 595 |
| Vector bytes | 309,808,908 |
| Release staging entries | 0 |
| Nonterminal workload jobs | 0 |
| Owned temporary entries | 0 |
| PDF reprocessing in this preflight | 0 |

## Goal status

| Goal | Status |
|---|---|
| `GOAL_0_FINAL_INTEGRATED_REGRESSION` | `COMPLETED` |
| `GOAL_1_PRIMARY_EVIDENCE_ARCHIVE` | `COMPLETED_WITH_EXPLICIT_GAPS` |
| `GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` | `NOT_CLOSED` |
| `GOAL_3_CONDITIONAL_CORRECTIONS` | `NOT_CLOSED` |
| `GOAL_4_FINAL_EVIDENCE_CLOSURE` | `NOT_CLOSED` |

The program must not report overall completion while these two product
invariants remain unproved.
