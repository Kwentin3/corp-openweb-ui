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
| v4 owner-produced disposal with `position_effect=OPEN_SHORT` | `OPEN_SHORT_PROVEN` | open position retained; no `acquisition_missing` |
| partial FIFO close | closed disposal plus `OPEN_LONG_PROVEN` remainder | closed calculation retained; remainder stays open |
| mixed independent groups | per-group closed/open/unresolved states | closed groups calculate; unresolved group cannot erase them |
| incomplete source role | no position repair | remains `SOURCE_EVIDENCE_INSUFFICIENT` fail-closed |

Gate 3 role pack v4 publishes the optional exact `OPEN_SHORT` role, but v3
remains the active role pack. The current ordinary-table mapping therefore
cannot silently infer short semantics. Tests use a genuine v4 owner-produced
Fact to prove the positive path.

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
