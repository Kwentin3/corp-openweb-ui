# Broker Reports — Final Evidence Closure

Date: 2026-07-23

Branch: `codex/broker-reports-final-evidence-closure-not-closed-v1`

Repository closure base:
`7f489d9c3282817609d176b44d288d1040964208`.

Live stage source revision:
`4f80f91c0427740f91acd3134c70d9271aab24bb`.

Program status: `NOT_CLOSED`

## Executive result

The repository, release and evidence archive are internally consistent, and
the measured browser transport defects were corrected and released.

The program is not complete because the required fresh native browser route
cannot yet deliver an answer from the assembled Broker Reports answer context.
The blocker is no longer the semantic visual-table contract, VLM provider,
private intake or same-chat transport. It is the final server-side handoff from
a complete answer context to the answering model.

No fresh PDF was reprocessed after this was proven deterministically.

## Repository and live parity

At the closure base:

- local `main` equalled `origin/main`;
- worktree was clean;
- live source revision was an ancestor of repository `main`;
- live release verifier passed after the last runtime release and after its
  native browser control;
- release staging entries were zero;
- nonterminal workload jobs were zero;
- owned temporary entries were zero.

Exact live identities:

| Runtime object | SHA-256 / identity |
|---|---|
| Gate 1 Function | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source Function | `45de78ac87f44a7f30d8dacc4d3d1bd3edbbafbc5002708776726d51edf2ce3e` |
| Gate 2 domain Function | `c26ae568bcaa8987abb581528abe20299ff50d3b853d402d31253211349be6dd` |
| Protected Action | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| Static loader | `51e836b02e2c71aa61e2ff4faff0e43f762b70d3ecf41fdbbffb73bf5d3891f7` |
| Managed prompts | 12 exact |
| Image | exact, running, restart count 0 |

Current release:

- release ID: `broker-reports-4f80f91c0427`;
- manifest SHA-256:
  `5f94335b9c61954df97b41d28b8f766a5eb4776c333d3d170f5910c778303615`;
- rollback identity SHA-256:
  `e2e6e5a5de12f3955b8bc8f54bfd9897392cd6fb81b7f93d3cd1633865b880c9`.

## Evidence completed

### Goal 0 — integrated regression

The final integrated regression receipt is present. Subsequent runtime
corrections also ran the complete affected Broker Reports suite:

- 1,147 passed;
- 20 skipped;
- 0 failed.

The Stage 2 suite passed 109 tests, loader behavioral coverage passed 5 tests,
and repository privacy guard passed 3 tests.

### Goal 1 — primary evidence archive

The Goal 0–2 primary archive is complete with explicit gaps. It preserves the
distinction between contemporaneous primary evidence and later completion
evidence. No late summary is labelled as a primary receipt.

### Released corrective slices

| PR | Result |
|---|---|
| #61 | Gate 2 resolves DCP from authenticated chat scope |
| #62 | atomic server release and rollback proof |
| #63 | native browser v3 evidence, terminally `NOT_CLOSED` |
| #64 | source Gate 2 model keeps the active chat |
| #65 | atomic loader release and native no-PDF proof |
| #66 | domain Gate 2 model keeps the active chat |
| #67 | atomic loader release and native no-PDF proof |
| #68 | final preflight blocker evidence |

The latest Chrome proof used the deployed loader without local injection and
showed the domain Gate 2 request, response and route remaining in the active
chat with zero page errors.

## Remaining blockers

### 1. Report-wide completeness

The native domain request contains no explicit batch configuration. Live
defaults select one document, one source unit and one segment, while the
measured authorized report has ten packageable source units.

The current runtime can publish a completed answer context for that selected
slice without proving that all deferred source scope was consumed.

Failed invariant:
`ANSWER_CONTEXT_REPORT_SCOPE_COMPLETE`.

Owning component:
Gate 2 domain Function/runtime completeness policy.

Narrowest correction:
full authorized customer scope, or fail closed before answer-context
publication whenever source scope remains deferred.

### 2. Native answer-context-only handoff

The protected answer-context resolver exists, but it has zero maintained
production call sites. The domain Function returns a compact processing
summary and does not pass the resolved context plus the user's question to an
answering model.

The earlier successful three-metric checksum used an out-of-browser harness
that supplied the answer context explicitly. That proves the data and model
contract, but not the required browser user journey.

Failed invariant:
`ANSWER_CONTEXT_ONLY_NATIVE_BROWSER_HANDOFF`.

Owning component:
maintained Gate 2 domain Function/native answer boundary.

Narrowest correction:
an authenticated chat-scoped answer-context-only mode inside a maintained
Function boundary, using the existing provider connection and
WorkloadAuthority, with no extraction on follow-up.

## Runtime counters

| Counter | Final measured value |
|---|---:|
| Knowledge rows | 0 |
| Document rows | 0 |
| File rows | 272 |
| Vector files | 595 |
| Vector bytes | 309,808,908 |
| Release staging entries | 0 |
| Nonterminal workload jobs | 0 |
| Owned temporary entries | 0 |

Knowledge/RAG/vector delta for the preflight and correction controls was zero.
No PDF, crop, DOM dump, literal customer value or provider raw response was
committed.

## Final status

| Goal | Status |
|---|---|
| `GOAL_0_FINAL_INTEGRATED_REGRESSION` | `COMPLETED` |
| `GOAL_1_PRIMARY_EVIDENCE_ARCHIVE` | `COMPLETED_WITH_EXPLICIT_GAPS` |
| `GOAL_2_NATIVE_BROWSER_CLICKTHROUGH` | `NOT_CLOSED` |
| `GOAL_3_CONDITIONAL_CORRECTIONS` | `NOT_CLOSED` |
| `GOAL_4_FINAL_EVIDENCE_CLOSURE` | `NOT_CLOSED` |

Final acceptance:

| Invariant | Result |
|---|---|
| `FINAL_FULL_SUITE_RECEIPT` | `PRESENT` |
| `GOAL_0_2_EVIDENCE_ARCHIVE` | `COMPLETE_WITH_EXPLICIT_GAPS` |
| `NATIVE_BROWSER_CLICKTHROUGH` | `NOT_CLOSED` |
| `SEMANTIC_CHECKSUM` | `PRIOR_MODEL_PROOF_3_OF_3; FRESH_BROWSER_NOT_RUN` |
| `DOUBLE_COUNTING` | `PRIOR_PROOF_ZERO; FRESH_BROWSER_NOT_RUN` |
| `KNOWLEDGE_RAG_VECTOR_DELTA` | `ZERO` |
| `REPOSITORY_LIVE_PARITY` | `EXACT` |
| `PRIVATE_EVIDENCE_IN_GIT` | `ZERO` |
| `PROGRAM_STATUS` | `NOT_CLOSED` |

Reporting `COMPLETED` would hide two measured product defects and would violate
the program's terminal-status contract.
