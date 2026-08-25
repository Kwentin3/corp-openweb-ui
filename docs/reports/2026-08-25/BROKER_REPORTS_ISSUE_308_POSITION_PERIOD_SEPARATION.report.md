# Broker Reports Issue #308: position, source and tax-period separation

Status: implemented and ready for independent review. PR and Issue remain
open; no merge or production deployment was performed.

## Exact identity

- Base `main`: `cf8e9bf2d13354588f569994953e97d8b2daf218` (merge of PR #307).
- Live-tested implementation commit:
  `310f5837d19d85eb590ee5892b6f12a15c6ccd89`.
- Safe live trace:
  `BROKER_REPORTS_ISSUE_308_INTERACTION_TRACE.safe.json`.
- Live trace receipt:
  `277cc8f31e6541432a4ec6b344b4c2880a26118b64c6c984447ce7cc2f536368`.

## Result

The production composition no longer lets an operation-local pair check
overwrite the grouped position result. Source completeness, position state,
tax activation, selected tax period, exact profile support and filing release
are separate outputs.

No new parser, tax owner, declaration path, registry, workflow engine or LLM
authority was added. The route still composes the existing Canonical, Gate 4,
Gate 5 Human Fact, Tax Model and XML owners.

## Owner map

| Meaning | Single owner | Boundary |
| --- | --- | --- |
| Canonical coverage | ordinary-trade projection owner | complete, relevant-unmapped or missing Canonical evidence |
| operation dates and observed years | deterministic source-fact consumer | exact source-bound Fact roles only |
| document reporting period | current Fact contract | explicitly not proven; no filename/broker inference |
| position state and evidence horizon | deterministic source-fact consumer | per exact `(asset, currency)` group |
| selected tax period | Gate 5 Human Fact owner | owner-published `selected_tax_period` request in pre-period scope `0000` |
| exact declaration profile | trusted methodology owner plus XML Definition owner | selected year must equal the exact supported profile |
| profile-mismatch choice | Gate 5 Human Fact owner | `ANALYSIS_ONLY`, `SURROGATE_DRAFT` or `STOP_RESUMABLE` |
| tax calculation | existing Tax Model/FIFO owners | closed owner-produced consumption only |
| filing XML and XSD identity | existing XML projection owner | exact 2025 profile only |
| final user note | production composition projection of owner outputs | no reclassification in Pipe |

## Position matrix

| Genuine evidence | Position result | Tax/result behavior |
| --- | --- | --- |
| purchase only | `OPEN_LONG_PROVEN` | `OPEN_POSITION_RETAINED`; no `disposal_missing`, no source-insufficient label |
| sale only, no exact short role | `UNRESOLVED_DISPOSAL_EVIDENCE_HORIZON` | typed `gate5_source_fact_acquisition_evidence_horizon_unproven`; no invented short |
| v4 owner-produced disposal with `position_effect=OPEN_SHORT` on the deterministic compatibility port | `OPEN_SHORT_PROVEN` | Gate 5 contract proof only; when the current active projection produces no security Fact, production stops with typed `gate4_ordinary_trade_security_position_source_contract_missing` instead of claiming an empty open position |
| partial FIFO close | closed disposal plus `OPEN_LONG_PROVEN` remainder | closed calculation retained; remainder stays open |
| mixed independent groups | per-group closed/open/unresolved states | closed groups calculate; unresolved group cannot erase them |
| incomplete source role | no position repair | remains `SOURCE_EVIDENCE_INSUFFICIENT` fail-closed |

Gate 3 role pack v4 publishes the optional exact `OPEN_SHORT` role, but the
active qualified ordinary-table mappings do not emit that role. The current
production port therefore cannot silently infer short semantics or reuse the
historical Gate 4 store as a fallback. A genuine v4 owner-produced Fact proves
only the deterministic Gate 5 compatibility path. A separate active-factory
test proves that the same historical Fact is not consumed by production and
does not produce a false `OPEN_SHORT_PROVEN` claim. The active owner now also
returns an exact source-contract blocker when its current projections yield no
security Fact, so the product cannot combine `OPEN_POSITION_RETAINED` with
`NO_SECURITY_OPERATIONS` and an empty position list.

## Period and profile matrix

| Case | Result |
| --- | --- |
| observed operation years, no user selection | owner request shows detected years; no profile resolution or XML |
| selected supported 2025 | existing deterministic 2025/XSD 5.20 route remains available |
| unsupported year + `ANALYSIS_ONLY` | calculations/note retained, terminal `ordinary_trade_analysis_only_non_filing`, no XML |
| unsupported year + `SURROGATE_DRAFT` | explicit `NON_FILING_SURROGATE_READY`, no filing XML/download |
| unsupported year + `STOP_RESUMABLE` | exact case retained with `STOPPED_RESUMABLE`, no invented facts |
| acquisition before selected disposal year | acquisition remains eligible evidence for that disposal; document is not rejected by year alone |

The selected year never defaults to 2025. Profile mode and period are
request-bound Human Facts; detected-year successors stale the previous period
selection in the same semantic lane.

## Adversarial proofs

- Changing filename years to 2022 or 2099 does not change owner-observed
  operation years.
- Changing operation dates does change the owner observation and creates a
  genuine same-case successor; an old period choice becomes stale.
- Changing selected period changes profile resolution, never Fact dates.
- Replacing the exact profile-mismatch mode with another state changes only
  the non-filing outcome; it cannot produce filing XML.
- Removing the exact short role changes proven open short to the evidence-
  horizon blocker; sale quantity/sign alone cannot repair it.
- Removing a close preserves open-long state; adding a close produces only
  the owner-calculated closed quantity and remainder.
- Cross-run/hybrid XML validation from Issue #306 remains fail-closed.
- A generic stop with a wrong reason does not satisfy the representative-source
  receipt validator.
- Generated OpenWebUI bundles remain mechanically byte-equal to their source
  modules and declared closed-world resources.

## Representative T-Bank live clean-room proof

The public corpus metadata describes a 2022 purchase, but the actual active
OpenWebUI source path did not produce Canonical evidence for this PDF. The
runtime therefore correctly did not claim the corpus metadata as live Fact
evidence and did not evaluate position or profile.

The browser-only run on the isolated OpenWebUI v0.9.6 staging instance returned:

- exact status `PREPARATION_INCOMPLETE`;
- terminal/reason `ordinary_trade_canonical_evidence_missing`;
- source completeness `CANONICAL_EVIDENCE_MISSING`;
- position `NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE`;
- detected years `[]`, selected tax period `null`;
- profile `NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE`;
- filing eligible `false`, XML/download `false`.

This rejects the earlier tempting but false explanations `disposal_missing`,
open long, 2022 profile mismatch, or generic stop. The trace binds the public
source owner's exact bytes, browser driver, generated bundle, control script,
tested commit and restored-control predecessor chain. It records no taxpayer
data, document contents, secrets or hidden refs.

The temporary staging container and dedicated volume were removed after the
restored receipt was written. The production OpenWebUI container remained
healthy and was not restarted.

## Verification summary

Focused suites cover position matrices, period/profile choices, Human Fact
staleness, production composition, Pipe rendering, live receipt mutation and
bundle/architecture parity. The exact-head CI result is reported in PR #309
and Issue #308 after GitHub evaluates the final pushed head.

Known limit: the current live T-Bank route proves an extraction boundary, not
an open position or a 2022 declaration analysis. The implementation exposes
that limit instead of filling it with fixture/corpus knowledge.

## Independent-review stabilization follow-up

The follow-up starts from reviewed PR head
`3919878a07dbc033b5e2768691b07493ef45f85c` and changes only the two Issue #308
boundaries.

- Exact profile absence is now decided from `supported_profile()` identities
  returned by the existing full-target Definition owner. A 2025 methodology
  resource failure or source-assertion mismatch retains its original typed
  Gate 5 reason and cannot enter the unsupported-year Human choice flow.
- `0000` remains an internal Human scope sentinel and is rejected both during
  answer normalization and when validating a persisted selected-period fact.
- Period and mismatch-mode corrections clone the current owner request into an
  immutable same-lane successor in the real scope. The old publication/fact is
  stale; a mode fact left in the former year cannot control the newly selected
  year.
- The mismatch question lists the Definition owner's actual available profile
  ID/version/year/form/format. `SURROGATE_DRAFT` is now a distinct structured
  non-filing template with confirmed source/position/calculation fields,
  placeholders/checks, an explicit year mismatch and no XML/download.
- Source assessment now retains the same exact `position_effect` consumed by
  grouped assembly when its Fact port supplies that owner-produced role. This
  proves the deterministic Gate 5 compatibility seam, not active production
  reachability. The active ordinary mapping has no qualified short literal;
  disposal-only therefore remains the acquisition-horizon/semantic blocker.

The representative T-Bank live trace and receipt were not rewritten: they
still prove only the earlier Canonical-missing stop. Period/profile/position
follow-up branches are integration proofs over repository-owned synthetic
artifacts and the production runtime/action seams; they are not claimed as a
new live T-Bank result. Final exact head and CI receipt are recorded only after
the branch is committed and GitHub checks that exact head.

## Second independent-review follow-up

The second follow-up starts from reviewed exact head
`e113c9125faaef39f7f765fc32533a80c373641a`.

- The representation-only chat adapter now validates and displays the exact
  Definition-owner available profile labels, including profile ID and 2025.
- `NON_FILING_SURROGATE_READY` now renders the existing owner-produced preview
  through both the standalone formatter and ordinary Pipe interaction flow:
  profile/year mismatch, confirmed fields, placeholders, checks and an
  explicit filing prohibition are visible; XML/download remain absent.
- The trusted methodology owner carries the pinned rule's
  `REAL_SOURCE_EVIDENCE_MISSING` classification with the exact
  `gate5_ordinary_trade_product_source_evidence_unresolved` error. Case Inputs
  no longer relabels that source gap as missing methodology.
- Each mismatch-mode request binds the exact current selected-period fact ref.
  Period correction makes the old request/fact stale, and a
  `2022 -> 2025 -> 2022` round-trip requires a fresh mode answer.
- No active production short owner was invented. An active
  `OrdinaryTradeProductionRuntimeFactory.create` proof shows that an injected
  historical v4 `OPEN_SHORT` Fact is outside the current ordinary projection
  port and cannot support a production `OPEN_SHORT_PROVEN` claim. The positive
  open-short result remains explicitly limited to the deterministic Fact v2
  compatibility consumer until a source-qualified active mapping exists.

Local verification on the final working tree before commit:

- the four reproduced user/owner failures changed from `4 failed` to
  `4 passed` after the boundary fixes;
- the combined owner, declaration, Pipe and production-candidate set passed
  `114` tests;
- the exact active ordinary-trade CI guard passed `271` tests with five
  existing SWIG deprecation warnings;
- Ruff E9/F63/F7/F82, generated bundle parity and `git diff --check` passed.

The final exact head and GitHub CI receipt are published in PR #309 and Issue
#308 only after the commit is pushed and GitHub evaluates that exact SHA.

## Third independent-review follow-up

The third follow-up starts from reviewed exact head
`5db41c2768ebe8c865af43da0c9479ae9eca5a56` and closes the two remaining
observable boundary defects.

- The maintained file-processing branch and the resume branch now call one
  `_ndfl_non_ready_product_content` representation helper. A real public
  `Pipe.pipe` sequence processes a genuine CSV, selects 2022 and
  `SURROGATE_DRAFT`, then repeats a turn carrying the file; the returned public
  text contains the validated owner profile/preview and no XML link. The test
  no longer substitutes a private standalone formatter for the public result.
- `Gate4OrdinaryTradeCandidateRuntime.current_fact_set` is the single owner of
  active Fact-set availability. When current ordinary projections have no
  prior `RELEVANT_UNMAPPED` observation but yield no security-position Fact, it
  returns typed blocker
  `gate4_ordinary_trade_security_position_source_contract_missing`, owned by
  `Gate4OrdinaryTradeCandidateRuntime` and classified
  `INTERNAL_CONTRACT_OR_PIPELINE_DEFECT`.
- Production preserves that blocker as `PREPARATION_INCOMPLETE`, terminal,
  Gate 5 blocker accounting, internal owner action and final-note check. Source
  completeness is `ACTIVE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING`, position
  evaluation is `NOT_EVALUATED_SOURCE_CONTRACT_MISSING`, and positions remain
  empty without an `OPEN_POSITION_RETAINED` claim.
- A prior Canonical coverage blocker remains primary, and a genuine
  purchase-only Fact still reaches `OPEN_POSITION_RETAINED`. No historical
  Gate 4 read, fallback, short inference, provider call or second authority was
  added.

Verification on the final working tree before commit:

- the two exact public/product probes failed before implementation and pass
  after it; together with the two preserved precedence regressions the focused
  set is `4 passed`;
- the exact active ordinary-trade production guard is `272 passed` with five
  existing SWIG deprecation warnings;
- architecture plus Gate 1/Gate 2 bundle tests are `45 passed` with the same
  existing warnings;
- Ruff E9/F63/F7/F82, generated bundle parity/idempotence and
  `git diff --check` pass.

The new exact head and exact-head CI receipt are published in PR #309 and Issue
#308 only after commit/push and GitHub evaluation of that exact SHA.
