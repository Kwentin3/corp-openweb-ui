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

This is a preparation assistant. It does not authenticate the taxpayer, submit
to FNS, or claim legal truth for user-attested values.

## Owner map and boundary

| Meaning | Single owner | Product seam |
| --- | --- | --- |
| authenticated user/case and private access | OpenWebUI server context plus `ArtifactStore` ACL | unchanged across upload, action, resume and output |
| taxpayer workflow slot | local product composition | opaque user+case+period slot; not INN, operation subject or authenticated identity; caller cannot supply it |
| INN/FIO, capacity, residency evidence, filing choices and fill values | existing `Gate5HumanGapClosureRuntime` | exact current request publication -> normalized answer -> `USER_ATTESTED_CASE_FACT` |
| current source assertions and identity candidate | existing `Gate3MetadataSourceFactRuntime` | only exact labelled facts from Canonical versions named by current whole-case coverage; no LLM execution |
| applicability, Russian-source classification, declarant category and Article 228 KBK | existing hash-pinned `Gate5TrustedMethodologyAuthority` | current source facts and user capacity are inputs; user answers cannot manufacture outputs |
| calculation, Scope/Package/release/XML | existing Tax Model, assembler, semantic and projection owners | the assembler exposes a narrow pre-Package preview for `DRAFT_READY`; full path is unchanged |
| private downloadable XML | OpenWebUI `Storage` plus `Files` | authenticated user header, byte hash check and private file record |

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
| Canonical synthetic INN/FIO candidate | masked in chat; `CONFIRM`, `CHANGE` or `DEFER` only through the current identity publication |
| `DEFER` identity, then publish three critical facts | `DRAFT_READY`; calculated 60/43/17/2 preview; identity remains in checklist; no XML |
| fill all remaining current actions in the same case | `DECLARATION_XML_READY`; XSD and released-semantic reconciliation pass; no placeholders |
| current Canonical identity candidate successor after XML | old identity fact becomes stale, prior XML is no longer produced, new current identity action appears; re-confirmation produces a distinct current XML |
| old publication answer after successor | `gate5_gap_request_stale` |
| same publication under another user/case/workspace/taxpayer slot/period | existing Human owner rejects the foreign binding |
| duplicate current confirmation/click | one byte-identical fact artifact; no conflict or duplicate |
| missing admitted-exchange source assertion | `REAL_SOURCE_EVIDENCE_MISSING`; Human action cannot close it; no XML |
| missing whole Canonical projection or `RELEVANT_UNMAPPED` row | existing completeness blocker before declaration |
| second disposal | exact one-disposal binding blocker; no operation can silently disappear |
| XSD-valid numeric XML mutations | independent serialized-value reconciliation rejects base, tax, payable/refund, source and budget mismatches |
| repeated unchanged full run | byte-stable XML/artifact identities; zero LLM/provider calls |

The safe representative sequence is retained beside this report in
`BROKER_REPORTS_ISSUE_304_INTERACTION_TRACE.safe.json`.

## Product boundary and limitations

The maintained Pipe plus regenerated closed-world bundle is the highest tested
entrypoint. The structured declaration action body is exercised through that
Pipe; no deployed OpenWebUI environment or browser-authenticated live case was
available, so this report does not claim a live deployment smoke.

Only synthetic Canonical labels prove the new identity/source assertions.
There is no claim that every real broker report contains those labels. Their
absence is an honest typed source blocker. The Issue #302 tax matrix remains
unchanged: one 2025 initial resident individual/self-signed ordinary organized
market disposal outside IIS in RUB; no multiple operations, acquisition
commission, foreign cases, representative, correction number, FNS transport
or broader tax coverage.

## Verification

The final exact-head CI receipt is recorded in the Issue/PR after publication
so it cannot point to a predecessor commit. Local receipts before publication:

- `181 passed`: the exact required active ordinary-trade workflow command,
  including declaration/XSD, Human publication/conflicts, maintained Pipe and
  frozen-evidence verification;
- `39 passed`: architecture/bundle parity plus trusted methodology;
- `10 passed`: trusted methodology and repository privacy guard;
- repeat bundle generation was byte-equal;
- Python compile, required Ruff correctness checks and `git diff --check`
  passed.

The pre-existing cross-gate Decimal-placement assertion is reported separately
if the unchanged `gate5_full_target_xml_projection.py` baseline remains red.
