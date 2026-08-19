# G5.47 — Real Canonical Semantic Recovery & Fact Contract Consolidation

Date: 2026-08-14

Status: `PARTIAL — CANONICAL_PRESERVATION_GAP`

No ingestion rerun, source-byte read, Canonical mutation, persistence to the frozen store, product activation, declaration release, commit, push or PR was performed.

## Outcome

The contract consolidation and real provider pass are proven. Deterministic replay did not improve a current semantic blocker, so `REAL_EVIDENCE_REPLAY_IMPROVED` is not claimed.

Published terminals:

- `SOURCE_FACT_CONTRACT_CONSOLIDATION_PROVEN`
- `SHARED_FACT_MULTI_CONSUMER_BINDING_PROVEN`
- `TRUE_SOURCE_GAPS_LOCALIZED`
- `REAL_SEMANTIC_RECOVERY_CORE_PROVEN`
- `REAL_CANONICAL_SEMANTIC_RECOVERY_PROVEN`
- `CANONICAL_PRESERVATION_GAP_FOUND=[PARTIAL:pdf_table_projection_terminal_fallback_text]`

## Demand consolidation

The 32 G5.46 `SOURCE_FACT_CONTRACT_MISSING` rows were treated as consumer demands, not future DTOs.

```text
DEMAND_ROWS / UNIQUE_FACT_MEANINGS = 32 / 10
existing Gate 4 meanings reused     = 7
new distinct literal meanings       = 3
consumer-specific fact types        = 0
contract gaps remaining             = 0
```

The ten meanings are:

- `SECURITY_PURCHASE`
- `SECURITY_DISPOSAL`
- `DIVIDEND_INCOME`
- `COUPON_INCOME`
- `COMMISSION`
- `TAX_WITHHELD`
- `TAX_WITHHELD_TOTAL`
- `PAYER_ORGANIZATION_IDENTITY`
- `PAYER_ORGANIZATION_JURISDICTION`
- `REALIZATION_LOCATION_JURISDICTION`

`SECURITY_DISPOSAL` is shared by 13 demand rows and three consumers. `SECURITY_PURCHASE` is shared by 12 demand rows and three consumers. Four acquisition-basis findings reuse the one `SECURITY_PURCHASE` contract class; no finding-specific source fact was introduced.

Detail and aggregate withholding remain separate meanings because their source granularity differs. They were not reconciled.

## Existing fact reuse

Methodology inputs such as `disposal_date`, `income_or_expense_date`, `security_identity`, `source_amount`, `source_currency`, dividend roles and coupon currency bind back to roles of the existing Gate 4 financial observations.

The new proof-only projector re-resolves exact Canonical targets and delegates value normalization and fact validation to Gate 4. It creates no second financial normalizer or persistent fact store.

## Real Canonical pass

One clean inference was executed for each of the four supplied Canonical documents:

```text
provider calls          = 4
calls completed         = 4
retry count             = 0
best-of-N               = 1
input tokens reported   = 667,531
cached input tokens     = 0
output tokens reported  = 14,763
monetary cost           = not reported by provider
```

The provider model identifier was not emitted by the CLI and is recorded as `NOT_REPORTED_BY_PROVIDER` rather than guessed.

Batching was document-level with all compatible active meanings in one call. There was no `fact × page` loop. The pass is bounded but too token-heavy for a product path; the document-4 structural preservation defect must be resolved before considering a cheaper targeted runtime.

Private frozen requests, raw provider events, structured responses and exact source literals remain outside Git. Repository evidence contains aggregates and hashes only.

## Proposal audit

```text
provider proposals with exact provenance validated  = 54
provider-declared ambiguous role candidates          = 4
provider-declared incomplete required roles          = 9
provider-declared non-explicit literals               = 11
validator exact-literal rejections                    = 3
same-target conflict groups rejected                  = 5
no-active-consumer-role projections rejected          = 2
unique financial facts finally projected             = 2
```

The two transient facts were one `DIVIDEND_INCOME` and one `TAX_WITHHELD`, both projected through the existing Gate 4 role/value owner and both replacing incomplete facts at the same Canonical target. Neither closed the global consumer demand because other required observations remained unproved.

No simple payer or realization-jurisdiction fact passed the explicit-label ceiling.

## Final classification

```text
FACT_RECOVERED_FROM_CANONICAL      = 0 demand rows
SOURCE_ROLE_AMBIGUOUS              = 0
SOURCE_DOES_NOT_PROVE_REQUIRED_FACT= 3
TRUE_SOURCE_ABSENCE                = 3
CANONICAL_PRESERVATION_GAP         = 29
CONTRACT_GAP_REMAINING             = 0
```

The three true source non-proofs are:

- `PAYER_ORGANIZATION_IDENTITY`
- `PAYER_ORGANIZATION_JURISDICTION`
- `REALIZATION_LOCATION_JURISDICTION`

All four documents completed the appropriate literal-role search before those outcomes were declared. Generic organization, broker, country and venue literals were not upgraded.

## Canonical preservation boundary

Document 4 contains 75 Canonical warnings:

```text
PARTIAL: pdf_table_projection_terminal_fallback_text
```

Fallback text remains, but the table structure needed to prove same-row financial roles is unavailable. This is sufficient evidence of an upstream structural preservation gap and prevents 29 financial demand rows from being called true source absence.

Because the defect is systematic rather than one malformed response or prompt, G5.47 stops at the allowed partial terminal. Original bytes were not reread or reparsed.

## Client actions

```text
before G5.47 client-required actions = 4 USER_FACT
after G5.47 client-required actions  = 4 USER_FACT
additional-document actions          = 0
```

The eight earlier document actions remain suppressed. They cannot be restored while the relevant financial gaps are blocked by Canonical preservation rather than proven source absence.

Required blockers remained 19; advisory findings remained 1. No finding is reported as closed merely because its hash changed after replay.

## Black-box A–I

The focused A–I suite contains nine tests and passes 9/9:

- A: one payer-jurisdiction meaning, multiple consumer bindings;
- B: one `SECURITY_DISPOSAL.date` role reused by two inputs;
- C: exact same-row financial proposal validates and satisfies the existing role contract;
- D: cross-document recovery retains document B provenance without a relation;
- E: generic `Country: US` cannot become payer jurisdiction;
- F: completed search can localize a source non-proof and closure;
- G: four acquisition findings share one purchase contract;
- H: an unrequested interesting literal is absent from the provider front;
- I: an additive demand reuses the existing disposal contract without orchestration change.

## Cross-domain invariants

The pass preserves:

- source granularity;
- zero financial-event relations;
- no reconciliation;
- commission selection ownership;
- acquisition-basis coverage ownership;
- residency evidence ownership;
- G5.45 Declaration Semantics;
- representation-only projection;
- the four open legal-methodology gaps.

## Verification

```text
focused G5.47 A-I and safe-evidence tests = 11 passed
targeted G5.47/G5.46/architecture suite  = 80 passed
all Gate 5 tests                         = 490 passed
all Gate 3/4 tests                       = 150 passed
cross-domain/architecture subset         = 68 passed
Ruff                                     = passed
Python compileall                        = passed
safe-evidence privacy scan               = passed
generated bundle parity                  = passed
```

The three intermediate full-Gate-5 failures were stale generated-bundle hashes only. The current G5.45 bundle receipt was refreshed mechanically, the dependent G5.46 receipt was regenerated, and the complete Gate 5 suite then passed 490/490.

## KISS check

There is one fact owner per source meaning, one document-batched provider boundary and one transient replay overlay. No universal ontology, graph, alternate normalizer, second Tax Model or per-finding DTO was introduced.

## Strategic stop and next allowed boundary

G5.47 is closed as an allowed partial result. The next work must be separately authorized and bounded to the document-4 Canonical table-preservation defect. It must not silently reparse all source documents or activate the recovery path in the product.
