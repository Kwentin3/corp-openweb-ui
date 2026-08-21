# Broker Reports — Post-conformance architecture audit

## Terminal

`POST_CONFORMANCE_BOUNDARY_DEFECT_FOUND`

The terminal records that the audit found a real boundary defect. On the
audited working head the defect is remediated, but repository and production
delivery evidence is recorded only after the normal lifecycle completes.

## Executive result

The ordinary-trade architecture remains directionally correct:

```text
Canonical
→ exact qualified mapping
→ Source Observations
→ deterministic runtime records
→ Fact v2
→ deterministic Gate 5
```

Gate 3 is not in this active route and is not a fallback. However, the
implementation contained one relation heuristic that contradicted that design:
when a row exposed more than one currency, the compiler selected the currency
next to `gross_amount`. Column proximity was being used as semantic evidence.

The stricter and simpler form is now implemented: the qualified schema mapping
states the exact amount-column to currency-column bindings; the compiler only
executes those bindings and fails closed when they are absent or invalid.

## 1. Repository truth and lifecycle gap

Initial evidence on 2026-08-21:

- local branch: `agent/single-current-broker-reports-pipeline`;
- local head: `11be5b6a149dabb6f85a3d8d5bfbd7b943bdddfd`;
- `origin/main`: `c1602276655d0fbf375b01b40896fa258a05dc76`;
- branch divergence: 28 commits ahead, 0 behind;
- pull requests for the branch: 0;
- GitHub Actions runs for the branch: 0;
- production evidence names source revision
  `e3fd71f17047f18f7dcc13c22ad0efd0b975a6ec`, which is on the branch and
  ahead of `main`.

No architectural reason for keeping this split was found. It is the unfinished
delivery lifecycle of the preceding work: implementation and deployment were
completed, while PR, exact-head CI and merge were not. Therefore neither the
server nor a private branch should be the lasting repository authority.

Correct final state:

- `main` contains the maintained source, contracts and authority map;
- CI is green for the exact PR head;
- production carries an explicitly identified release derived from the merged
  source;
- historical reports remain evidence, not current architecture authorities.

Until that lifecycle is complete, a cold agent starting from `main` can obtain
an obsolete picture. The prior conformance result was valid for the audited
branch/runtime, but was not repository-wide closed.

## 2. Boundary defect: amount currency

### What was wrong

The qualified mapping assigned broad roles to columns, including multiple
`currency` columns. The compiler then inferred which currency belonged to the
gross amount from adjacency.

This is semantic binding, not parsing syntax. Reordering columns can preserve
the report's meaning while changing that heuristic's answer. In a source that
separately names price currency and settlement currency, adjacency cannot prove
which one denominates a gross amount or commission.

The consumer makes the error dangerous: Gate 5 groups and calculates money by
the emitted amount and currency. A wrong currency can therefore remain
well-typed, pass shape validation and silently change financial results.

### Correct owner and contract

- Canonical preserves the source and does not receive financial meaning.
- The qualified mapping owns the proven meaning of one exact source schema.
- The compiler executes the mapping; it does not rediscover relations.
- Fact v2 carries the result and producer identity.
- Gate 5 consumes facts and cannot repair source semantics.

The minimal contract is
`amount_currency_bindings[{amount_column, currency_column}]`. It covers every
emitted gross or commission amount. The mapping validator requires exactly one
binding for each such amount column, verifies both referenced column roles and
includes the bindings in mapping identity. Unknown or incomplete mappings fail
closed.

This does not introduce an ontology or a broker profile. It adds only the
source-schema relation required by the existing consumer.

## 3. Mapping boundary and anti-casuistic guard

The mapping continues to be selected only by exact title/header/column
fingerprint. It has no broker, year, filename, fuzzy matching or row-value
routing. Reordering columns creates a different fingerprint and requires new
qualification.

Profile creep is guarded by a closed mapping key set and tests that reject
extra profile keys, changed header order and missing amount/currency bindings.
The invariant for the third or hundredth schema is unchanged: new literal
shape and its exact source-semantic bindings may be added; runtime guesses and
consumer-specific repairs may not.

## 4. Active route, Gate vocabulary and compatibility names

The generic `GATE_OWNERSHIP` map remains a valid statement of responsibilities:
Gate 3 is the historical/general source-financial-labeling responsibility. It
is not a statement that its LLM implementation is active for ordinary trades.

To make this distinction machine-readable, the same architecture authority now
contains a separate closed `ACTIVE_PRODUCT_ROUTES` entry for ordinary trades.
It names the exact composition root, qualified mapping owner, mapping contract,
Fact v2 handoff, disabled semantic fallback and rollback-only Gate 3 role.

Names such as `gate3_binding`, `ordinary_trade_candidate_runtime` and
`ndfl_gate3` remain compatibility debt. No evidence was found that these names
currently select the old path: valves, factories and imports determine control
flow. Renaming them now would be a wide DTO/control migration without improving
the boundary. The natural removal point is a future major Fact/projection
contract version, where readers and writers can migrate together.

## 5. Producer identity and wrong-owner resistance

Fact v2 distinguishes the active ordinary producer through
`semantic_binding`. The Gate 4 adapter only accepts the qualified mapping
identity, while architecture tests protect factory composition and forbidden
imports.

The persistence boundary is now stricter: production callers cannot supply
their own mapping list to `compile_and_save`. The projection owner loads the
sole qualified mapping authority internally and invokes the compiler. The
lower-level compiler keeps explicit mappings only for qualification and unit
proofs; it is not a persistence entrypoint.

This does not make deliberate source-code violation impossible, but makes the
wrong owner non-accidental and test-visible.

## 6. Projection migration boundary

Changing amount/currency binding changes projection semantics. Reusing runtime
projection v2 would allow historical and new artifacts for the same active
Canonical to coexist under one current type and produce an ambiguity.

The corrected output is therefore
`broker_reports_ordinary_trade_runtime_projection_v3`. Historical v2 remains
registered for reading/audit but is excluded from the current v3 view. A
behavior test stores both and proves that only v3 is selected.

## 7. Cold-start and documentation

The intended cold-start remains:

```text
service AGENTS.md
→ Pipeline Gates v1
→ Architecture Authorities
→ exact versioned contract
→ named factory and tests
```

Historical reports are numerous and may contain words such as CURRENT, but
they are date-scoped evidence. A mass rename would damage audit history and
would not create a stronger authority. The active route map and authority
classification are the useful guard; no broader documentation rewrite is
required.

## 8. Verification

Local evidence on the audited change:

- before remediation: 52 relevant tests passed, proving the old suite did not
  detect adjacency semantics;
- after explicit bindings and projection v3: 79 relevant tests passed;
- the first full-service run found a real closed-world bundle ordering defect:
  the new mapping owner was embedded after its importer; the maintained bundle
  manifest was corrected and all three bundles rebuilt;
- that run also found four stale assertions requiring the retired Gate 3 route
  or architecture-policy v4; they now assert the active ordinary route and
  rollback-only Gate 3 boundary instead;
- post-correction bundle, architecture, ordinary-route and release set: 102
  tests passed;
- Ruff on all touched maintained Python and test files: passed;
- generated OpenWebUI bundles rebuilt deterministically from maintained source;
- `git diff --check`: no whitespace errors (Windows line-ending warnings only).

The full-service inventory result before those local test/bundle corrections
was `3843 passed, 5 skipped, 6 failed, 25 errors`. Two failures were the bundle
defect just fixed; four were the stale architecture assertions just fixed. The
25 errors are pre-existing frozen research builders that reject already-changed
provider/authority hashes. They are historical evidence, are not imported by
the active route and were not repaired or repinned in this audit.

The first exact-head CI run (`32518023096`) exposed the same lifecycle defect
before tests: current CI attempted to reconstruct a dated three-provider proof
through the later current Gemini adapter. Rebuilding would mutate historical
evidence; repinning would falsely make old evidence prove new code. Current CI
therefore no longer executes the three historical re-builders or their two
frozen builder-test modules. Their bytes remain unchanged in Git. Current
Context V2.1 contracts, provider adapters, evidence runtimes and active product
routes remain under executable CI checks.

CI, PR/merge and live release identities are appended only after they exist;
local success is not represented as repository or production proof.

Repository delivery evidence established during the audit:

- PR: `#289`;
- first fully green exact code/CI-policy head:
  `d26505d743a0b8674dbfed40ee6cee3f77a3f5be`;
- GitHub Actions run: `32518644796`;
- job: `broker-reports-ci`, terminal `success`, duration `6m56s`.

The final report-only head is checked again before merge. Merge and production
release identities are not claimed in this report until separately verified.

## Final architectural answer

The pipeline shape was right, but one old class of mistake survived inside the
deterministic compiler: an inferred relation based on physical closeness. The
system is simpler after moving the proven relation into the exact qualified
mapping and leaving the compiler as an executor. No new semantic layer,
ontology, broker profile or legacy fallback was added.
