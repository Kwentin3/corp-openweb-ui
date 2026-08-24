# Broker Reports Issue #304: OpenWebUI declaration preparation product

Status: `IMPLEMENTED; OPEN FOR INDEPENDENT REVIEW`

Exact base `main`: `6366c02619b4bfcab63399b18cf6c9ad5464a758`

## Result

The maintained bundled `broker_reports_gate1_pipe.Pipe` now composes the
bounded Issue #302 declaration path through the sole production root,
`OrdinaryTradeProductionRuntimeFactory.create`. An authenticated case can stop
honestly at `INPUT_REQUIRED`, continue to a calculated `DRAFT_READY` without
XML, and reach `DECLARATION_XML_READY` after all current required facts exist.
The final XML is stored through the authenticated private OpenWebUI File owner
and is returned as a download URL, never pasted into chat.

The public bundled path now asks one current question through OpenWebUI's
native `__event_call__`. The current Human publication stays in the server call
stack, so the browser sees no request ref or fact key and ordinary chat text
cannot select an old or foreign request.

This is a preparation assistant. It does not authenticate the taxpayer, submit
to FNS, or claim legal truth for user-attested values.

## Owner map and boundary

| Meaning | Single owner | Product seam |
| --- | --- | --- |
| authenticated user/case and private access | OpenWebUI server context plus `ArtifactStore` ACL | unchanged across upload, action, resume and output |
| taxpayer workflow slot | local product composition | opaque user+case+period slot; not INN, operation subject or authenticated identity; caller cannot supply it |
| INN/FIO, capacity, residency evidence, filing choices and fill values | existing `Gate5HumanGapClosureRuntime` | exact current request publication -> normalized answer -> `USER_ATTESTED_CASE_FACT` |
| browser question/answer representation | maintained bundled Pipe plus local declaration chat adapter | owner request -> safe question/masked candidate -> native `__event_call__` response; no persistence, currentness or semantic authority |
| current source assertions and identity candidate | existing `Gate3MetadataSourceFactRuntime` | only exact labelled facts from Canonical versions named by current whole-case coverage; no LLM execution |
| applicability, Russian-source classification, declarant category and Article 228 KBK | existing hash-pinned `Gate5TrustedMethodologyAuthority` | current source facts and user capacity are inputs; user answers cannot manufacture outputs |
| calculation, Scope/Package/release/XML | existing Tax Model, assembler, semantic and projection owners | the assembler exposes a narrow pre-Package preview for `DRAFT_READY`; full path is unchanged |
| private downloadable XML | OpenWebUI `Storage` plus `Files` | deterministic user+case+receipt+XML file identity, existing record/byte verification, one upload/record, partial-failure cleanup |

The composition adapter is local to the product boundary. Universal Scope,
Package, release and projection modules do not import the ordinary-trade
compiler or product factory. No second questionnaire, identity provider,
external-authority dictionary, workflow engine, registry, receipt engine or
calculator was added.

## Product states

| State | Exact condition | Output |
| --- | --- | --- |
| `PREPARATION_INCOMPLETE` | current Canonical/source/methodology owner gap | typed internal blocker; no calculated result and no XML |
| `INPUT_REQUIRED` | capacity, complete residency evidence or bounded zero-scope confirmation missing | current user actions; no calculated result and no XML |
| `DRAFT_READY` | calculation-critical facts complete, one or more fill-only facts absent/deferred | owner-produced Tax Model/Category/Tax Base/settlement preview plus checklist; no Package/release/XML |
| `DECLARATION_XML_READY` | all ten facts and all source/methodology bindings current | private official-XSD-valid XML and safe summary |

Fill-only facts are identity, filing instance/date/destination, signer,
disposition and OKTMO. They never become placeholders in wire XML. Critical
facts are capacity, residency evidence and the closed bounded zero-scope
confirmation.

## Source and methodology authority

The product methodology resource is hash-pinned at
`ca38485830352e6de49765c3ea20e38082dc3d3a7bf82bbe210477512bb7fae7`.
It accepts only the exact supported source assertions and emits the already
bounded applicability/source outputs plus payment KBK
`18210102030011000110`.

Primary references:

- [FNS Order ED-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
  establishes KND 1151020, the electronic format and applicability beginning
  with tax period 2025;
- the [FNS Article 228 KBK table](https://www.nalog.gov.ru/rn77/taxation/kbk/fl/ndfl/)
  lists the payment code used by the pinned rule.

An explicit source assertion is evidence to a reviewed rule, not a legal
conclusion by itself. Missing or ambiguous source labels remain
`REAL_SOURCE_EVIDENCE_MISSING`; there is no Human Fact key capable of closing
them.

## Adversarial experiments

| Genuine owner-produced experiment | Result |
| --- | --- |
| initial maintained Pipe run with no Human Facts | ten current actions, `INPUT_REQUIRED`, no XML, zero provider calls |
| actual regenerated bundle loaded, then public `Pipe.pipe` called with realistic OpenWebUI payload and `__event_call__` double | visible current question; all answers traverse the Human owner; same case reaches `DRAFT_READY` then private `DECLARATION_XML_READY` without source reread |
| old plain chat answer presented without the current interactive call | no fact is created; the same owner publication remains current |
| Canonical synthetic INN/FIO candidate | masked in chat; `CONFIRM`, `CHANGE` or `DEFER` only through the current identity publication |
| `DEFER` identity, then publish three critical facts | `DRAFT_READY`; calculated 60/43/17/2 preview; identity remains in checklist; no XML |
| fill all remaining current actions in the same case | `DECLARATION_XML_READY`; XSD and released-semantic reconciliation pass; no placeholders |
| current Canonical identity candidate successor after XML | old identity fact becomes stale, prior XML is no longer produced, new current identity action appears; re-confirmation produces a distinct current XML |
| old publication answer after successor | `gate5_gap_request_stale` |
| same publication under another user/case/workspace/taxpayer slot/period | existing Human owner rejects the foreign binding |
| duplicate current confirmation/click | one byte-identical fact artifact; no conflict or duplicate |
| invalid `2025-99-99` and 12-digit INN with wrong control digits | rejected before persistence; the current action remains usable and a later valid response proceeds |
| explicit date or INN change after XML | Human owner publishes an immutable same-lane successor; old fact/output become stale, corrected value produces a new current result |
| missing admitted-exchange source assertion | `REAL_SOURCE_EVIDENCE_MISSING`; Human action cannot close it; no XML |
| missing whole Canonical projection or `RELEVANT_UNMAPPED` row | existing completeness blocker before declaration |
| second disposal | exact one-disposal binding blocker; no operation can silently disappear |
| XSD-valid numeric XML mutations | independent serialized-value reconciliation rejects base, tax, payable/refund, source and budget mismatches |
| repeated final answer, refresh and unchanged full run | byte-stable XML/artifact identities and the same OpenWebUI file ID; exactly one Storage upload/File record; zero LLM/provider calls |
| Files record failure after Storage upload | typed failure and the partial stored object is deleted |

The safe representative sequence is retained beside this report in
`BROKER_REPORTS_ISSUE_304_INTERACTION_TRACE.safe.json`.

## Product boundary and limitations

The actual regenerated closed-world module loaded from
`broker_reports_gate1_pipe_bundled.py` and its public `Pipe.pipe` method are the
highest tested entrypoint. The test uses realistic OpenWebUI payloads, native
interactive-event and Files/Storage boundary doubles, and genuine artifacts
from the existing owners. No deployed OpenWebUI environment or
browser-authenticated live case was available, so this report does not claim a
live deployment smoke.

Only synthetic Canonical labels prove the new identity/source assertions.
There is no claim that every real broker report contains those labels. Their
absence is an honest typed source blocker. The Issue #302 tax matrix remains
unchanged: one 2025 initial resident individual/self-signed ordinary organized
market disposal outside IIS in RUB; no multiple operations, acquisition
commission, foreign cases, representative, correction number, FNS transport
or broader tax coverage.

## Verification

The final exact-head CI receipt and exact local counts are recorded in the
Issue/PR only after publication so neither can point to a predecessor commit.
The verification set includes the active ordinary-trade workflow,
Human-publication/currentness/correction, public bundled chat traversal,
idempotent private delivery and cleanup, architecture/bundle parity, pinned
methodology, privacy guards, repeat byte-equal bundle generation, Python
compile, Ruff and `git diff --check`.

The pre-existing cross-gate Decimal-placement assertion is reported separately
if the unchanged `gate5_full_target_xml_projection.py` baseline remains red.
