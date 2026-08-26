# Broker Reports Issue #310 — OpenWebUI product gate follow-up

## Result

The revised task was implemented in the same PR #311. The active OpenWebUI
chat now uses a bounded LLM presentation layer for ordinary Russian dialogue,
while the existing runtime and Human Fact owner retain every business
decision. The PR and Issue remain open and unmerged.

The follow-up started from PR head
`15b580c259d56fdc9bcd3a1fbd064dddb9cec8ed`. The code head before this
report-only successor is `4a82228`; the final immutable Git head and exact-head
CI receipt are published in PR #311 and Issue #310 after GitHub evaluates it.

## Boundary implemented

- The runtime builds one safe public context: outcome, owner-produced summary,
  provenance, one current question and allowed next actions.
- The context contains no artifact refs, fact keys, owner names, reason codes,
  internal statuses, XSD names or private URLs.
- The LLM may phrase the public message and interpret an ordinary answer only
  as a candidate. It has no calculation, source, tax, methodology or release
  authority.
- The existing Human Fact owner rebinds the candidate to the current
  `request_publication_ref`, validates it and publishes the fact. A delegated
  choice, an ungrounded candidate or invalid syntax fails closed.
- Directly accepted owner syntax bypasses the interpretation call; presentation
  still uses the LLM. If the model is unavailable, times out or violates the
  public contract, the deterministic formatter is used only as a safe fallback.
- Production presentation calls use the authenticated native OpenWebUI
  `/api/chat/completions` boundary. No second provider adapter or domain
  authority was introduced.

## Adversarial findings and fixes

1. A model could answer “choose the year for me”. This is now rejected before
   the Human Fact owner; the current question remains current.
2. The old owner syntax rejected the natural truthful answer
   `отсутствие: нет` and common en/em-dash interval separators. The same owner
   now maps an explicit no-absence statement to an empty typed interval list;
   `не знаю` and `не помню` remain rejected. Residency classification still
   belongs to the methodology owner.
3. The production presentation route could deadlock through an in-process
   recursive completion. The call now goes through the authenticated OpenWebUI
   HTTP boundary with a bounded timeout. A sanitized live canary returned 200.
4. Free LLM wording exposed weaknesses in the browser proof: it relied on
   decorative headings, classified an earlier summary mention as the current
   question, read progress text before completion, and sent before upload
   processing settled. The driver now waits for owner-required question/outcome
   text, selects the last semantic question, reads only after completion and
   gives upload processing a visible bounded window.
5. The supported profile was shown as only `5.20`. The safe context now requires
   the full user label `3-НДФЛ за 2025 год, электронный формат 5.20`.

## Live evidence

The accepted clean-room happy run at code head
`4de3d4a8097fdd4be99a8fb57ae5ecf973971656` produced 20 safe journal events:
delegated-choice rejection, current year selection, natural Human Fact answers,
invalid date and identity rejection, visible non-filing draft, private XML,
correction, reload/resume, same-source retry and second-user denial. Receipt:
`308927bea977d4c8c068d61a01ab734aef739b72d4530e9da2ddb268d4aa151c`.

Two later browser runs at `239886c72ea4d9311d38a8b97866bc909b2475db`
proved the non-filing routes independently:

| Route | Result | Receipt |
|---|---|---|
| open long | position retained outside tax base; no XML | `765a80697fff05cd214aa2f028f588b4a74fe841fe520d57222d2a730510d9f3` |
| sale only | missing position history explained; no XML | `02c0e95b97e39f905c512111df2dc6d9d3afc45898bbcfae5e6eb8f90a68d950` |

The final exact-head happy proof is rerun after this report commit so the proof
can bind the immutable Git head. Its receipt is published externally; embedding
that SHA into the commit itself would create a self-reference.

## Verification

- public dialogue, NDFL Pipe, bundle, residency and control subset:
  `75 passed`, five existing SWIG warnings;
- focused public/Pipe subset after the supported-profile change:
  `63 passed`, the same five warnings;
- focused residency/public adversarial subset: `32 passed`;
- Ruff and JavaScript syntax: passed;
- generated Gate 1 bundle rebuilt and deployed by the existing proof control;
- no runtime domain-provider call was added; the presentation model is a local
  `PRESENTATION_ADAPTER` with `business_authority = false`.

An expanded declaration suite was also sampled: `471 passed, 55 failed`.
The 55 failures are the pre-existing unpublished trusted-methodology baseline
and two existing exact-assertion mismatches; they are not represented as green
and were not broadened into this change.

## Route status

- supported closed trade: private XML reached in the real browser;
- ambiguous/delegated answer: rejected without publishing a fact;
- unsupported year: analysis, surrogate and resumable stop remain owner-owned;
- `2022 -> 2025 -> 2022`: current request is republished; an old mode is not
  reused;
- open long and sale-only: browser-proven non-filing outcomes;
- representative T-Bank PDF: source gap remains fail-closed;
- open short: the existing exact production-owner blocker remains visible in
  plain language; no source mapping or second authority was invented.

## KISS and owner check

No workflow framework, registry, generic request engine, new source authority,
Tax Model owner or release owner was added. The only new seam is the narrow
public dialogue adapter plus the native OpenWebUI completion boundary. Domain
owners still decide facts, current request, allowed answer, tax result and
release eligibility.
