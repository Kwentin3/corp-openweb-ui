# Broker Reports Issue #310 — OpenWebUI product gate

## Result

Issue #310 was exercised as a first-time tax specialist through the actual
OpenWebUI browser surface. The maintained route now reaches one honest end:
private XML for the supported case, an explicit non-filing result for open or
unsupported cases, or a plain-language fail-closed stop for an unsupported
source. The accepted browser matrix contains seven isolated users/cases and no
direct runtime or app-API shortcut.

The investigation started from `main`
`ddd528e60f6edc0b7d3dd8b898a80f6ae855a166`. The accepted code head before
this report-only commit is
`e07db4391406ab23fded9f97755df49b6ee201b7`; its generated bundle is
`6fe828fe5583c37f7f403791a76a381e9b4c281f4d8bf58c9bad7a87259cfbb8`.
The final report successor SHA and exact-head CI receipt are published in the
PR and Issue after GitHub evaluates that immutable head.

## Initial black-box finding

The production card named `NDFL` was bound to the legacy
`broker-reports-ndfl` workflow rather than the maintained
`broker_reports_ndfl` OpenWebUI model. A real upload therefore returned Gate 1
engineering output, run/job identifiers and DOCX-oriented handoff details
instead of the 3-NDFL product. No production state was changed during this
first pass.

The correction stays source-owned: the existing workspace-model publisher now
describes and publishes the stable product route, while an attested request to
the legacy id fails closed before reading the uploaded file. The PR is not a
production deployment; after merge, the normal publisher remains the only
activation route.

## User-route matrix

| Route | What the user sees and answers | Actual end | Rating / class |
|---|---|---|---|
| Supported closed trade | One Russian question at a time; year, presence periods, taxpayer capacity, bounded zero-scope, filing data, signer, identity and budget fields | XSD-valid XML, private download, provenance summary and filing warning | Clear / product goal met |
| Missing filling fields | Invalid INN/date are rejected; identity can be deferred; draft names fields still required | No XML until required facts are current; correction produces one current XML | Clear / semantic safety |
| Unsupported 2022 — analysis | The chat names selected 2022 and available 2025 form 5.20; user chooses analysis | Analysis only, no XML/download | Clear / non-filing |
| Unsupported 2022 — surrogate | Same context; user chooses a visible non-filing draft | Surrogate explicitly marked not for filing, placeholders visible, no XML/download | Clear / non-filing |
| Unsupported 2022 — stop | User chooses stop, then changes `2022 -> 2025 -> 2022` | Resumable stop; the old mode does not reappear | Clear / state-currentness |
| Open long | Chat calls it an open long position and explains that it is not in the tax base | Analysis without XML; next action visible | Clear / non-filing |
| Sale only | No invented purchase or short; chat asks for position history or an earlier report | Source-history gap without XML | Clear / source gap |
| Representative T-Bank PDF | The document cannot produce a confirmed complete operation set; the chat recommends a fuller supported report or specialist review | Fail-closed, zero calculated sales, no XML/download | Clear / source evidence |
| Open short | No active source-qualified owner can currently produce the needed position-effect fact | No fabricated browser success; exact Gate4 contract blocker retained | Architectural blocker |

The accepted safe trace with receipt hashes is
`BROKER_REPORTS_ISSUE_310_INTERACTION_TRACE.safe.json`. It records no
credentials, raw taxpayer values, chat ids, file ids or document contents.

## Safe interaction journal

The supported path was judged from visible content only:

| Visible stage | Natural user action | What a new user can understand | Expected / actual | Assessment |
|---|---|---|---|---|
| Tax period question | Select 2025 | The report contains 2024/2025 operations and the declaration needs a selected year | Next current question / matched | Clear |
| Residency evidence | Supply presence and absence date ranges, not a ready tax conclusion | The methodology will derive residency from supplied dates | Derived status remains methodology-owned / matched | Clear |
| Taxpayer and zero-scope questions | Choose ordinary individual; confirm bounded absence of other values | Which facts are user-attested and why zeroes cannot be guessed | Facts published through Human Fact owner / matched | Clear |
| Draft fields | First provide an invalid value, defer identity, then provide valid values | Invalid input is not saved; missing fields keep XML closed | Rejection and current successor / matched | Clear |
| Ready result | Correct date, download XML, reload, retry and re-upload same source | What came from the report, Tax Model, methodology and user; XML was not filed | One current logical XML / matched | Clear |
| Other user | Attempt model/file/chat access | Private result is not shared | Model hidden and file/chat denied / matched | Clear |

The three 2022 choices, open-long, sale-only and representative-source runs
each used a separate authenticated user. Every non-filing route returned zero
XML links and zero private downloads.

## Problems found and fixed

1. **P0 — wrong public composition.** The visible production card invoked the
   legacy workflow. The stable publisher/model binding is now explicit, and
   the stale id fails closed before source processing.
2. **P1 — public architecture leakage.** Statuses, reason codes, fact keys,
   profile ids and source-owner vocabulary escaped through progress, draft and
   final notes. Rendering now translates already-owned results without moving
   decisions into Pipe.
3. **P1 — resume treated historical files as a new upload.** Native OpenWebUI
   retains all chat attachments in top-level `files`. `_current_turn_has_files`
   incorrectly used that case collection, so a later Human Fact answer could
   fall into workload idempotency instead of resuming the declaration. The
   seam now uses owner-produced `user_message.files`; older transports use the
   latest user message. A public bundled regression carries the historical
   top-level file through the whole question sequence and still reaches XML.
4. **P1 — proof control drift.** Redeploy could change the bundle while leaving
   a prepared receipt bound to prior bytes. Deploy now emits a successor
   receipt with the new bundle hash and predecessor hash.
5. **P1 — period/profile corrections were incomplete at the chat surface.**
   Human labels now show year, form and 5.20; the public route accepts explicit
   tax-period correction and preserves `2022 -> 2025 -> 2022` currentness.
6. **P2 — generated-bundle EOL drift.** Generated bundles are pinned to LF so
   clean Linux checkout bytes equal locally built and deployed bytes.
7. **Proof-only races.** The browser driver previously could read the preceding
   assistant turn or test reloaded history before it rendered. The driver now
   binds each assertion to an advanced/stable DOM turn and waits for the XML
   link after reload. These failures were not counted as product passes.

## Owner and boundary map

- OpenWebUI publisher owns the visible model binding and grants.
- Gate 1/Canonical owners read the source and preserve completeness; Pipe does
  not reinterpret omitted or unmapped rows.
- `OrdinaryTradeProductionRuntimeFactory.create` remains the composition root
  for active projection, Gate4 facts and declaration preparation.
- Gate5 Human Gap Closure owns request publication, current Human Facts,
  conflict/staleness and period/profile choices.
- Tax Model, declaration assembly, XML projection and XSD owners retain their
  existing meanings; Pipe only presents their validated result.
- OpenWebUI Files owns private XML persistence and authenticated download.
- `Gate4OrdinaryTradeCandidateRuntime.current_fact_set` owns the active missing
  position-contract blocker. No historical v4 fact, new parser, mapping or
  second authority was introduced to manufacture `OPEN_SHORT`.

## Open-short boundary

The deterministic compatibility consumer can represent an owner-produced
`OPEN_SHORT`, but the active exact-qualified projection does not currently
carry a source-qualified position-effect contract. The adversarial production
test injects a valid historical v4 short fact and proves that it cannot cross
the active projection port. The retained blocker is
`gate4_ordinary_trade_security_position_source_contract_missing`, classified
internally as an active pipeline contract gap. This is the smallest honest
answer: adding a broker mapping or source authority is outside Issue #310.

## Verification

- actual isolated OpenWebUI browser matrix: seven accepted routes;
- supported path: one private XML, correction, reload/resume, same-source
  re-upload, concurrent retry and second-user ACL denial;
- active ordinary-trade CI command: `280 passed`, five existing SWIG warnings;
- bundle/architecture subset: `22 passed`, same existing warnings;
- generated bundle rebuild: byte-equal;
- Ruff `E9,F63,F7,F82`, JavaScript syntax and `git diff --check`: passed;
- runtime LLM/provider calls: zero.

The staging control is cleaned after the final exact-head proof. PR and Issue
remain open; merge is not performed.

## Self-review

1. A new user can answer the visible questions without internal codes.
2. Questions are current Human Fact requests, not speculative future fields.
3. Final text separates report inputs, Tax Model calculation, methodology
   result and user-attested facts.
4. Every safe stop has a next action.
5. Empty operations are never described as an open position.
6. Surrogate appears in the actual primary chat branch.
7. Internal refs/statuses are rejected by public-surface tests and driver.
8. Placeholders remain visibly unconfirmed and cannot release XML.
9. Corrections and resume select current publications only.
10. Answers are natural Russian phrases.
11. Open positions do not erase independent closed calculations.
12. Public explanations match the owner-produced terminal class.
