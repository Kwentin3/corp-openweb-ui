# ADR: Broker Reports Gate 2 Semantic Convergence v1

- **Status:** accepted architecture direction; implementation not authorized
- **Date:** 2026-07-31
- **Decision owner:** Broker Reports program
- **Scope:** future Gate 2 semantic route only

## Context

The repository has a released semantic visual-table route and an active broad
canonical source-fact product route. Historical
`source_fact_selection_v3` remains executable only behind a hard product
containment guard. The Financial Semantic V6 family owns existing Pack,
packet, choice, expansion, canonical validation/materialization, and replay
authorities. GOAL 16 defined a Type-First fail-closed contract. Draft PR #232
implemented an inactive synthetic GOAL 17 chain, but it is not part of `main`
and does not consume the current validated Gate 2 package.

GOAL 18 showed that useful Type-First ideas can reduce false-singleton risk,
but the proposed implementation would coexist with the product source-fact
route instead of converging it. KT1 must select an architecture direction
without activating, porting, qualifying, or deploying it.

## Options

### Option A — evolve the existing source-fact product boundary

The current source-fact product boundary consumes the existing validated Gate 2
package. Inside that boundary, a future inactive slice may project Pack-backed
Type-First cards and plural plausible types, then reuse existing choice,
expansion, canonical validator/materializer, persistence, and replay
authorities.

### Option B — connect the existing Gate 2 package to a separate V6 Type-First route

A separately named V6 route consumes the current Gate 2 package and delegates
to existing financial owners. It remains inactive until separately qualified.

### Option C — reject GOAL 17 and keep the current product route unchanged

No Type-First capability is retained beyond historical evidence.

### Option D — retain two routes

The broad source-fact product route and a second V6 Type-First route coexist as
independent product paths.

## Comparison

| Criterion | Option A | Option B | Option C | Option D |
| --- | --- | --- | --- | --- |
| Business responsibility | one source-fact boundary evolves | separate semantic responsibility must be justified | responsibility remains broad | overlapping responsibilities |
| Owner count | preserves one product orchestrator | risks a second orchestrator | preserves current count | creates two product owners |
| Product evidence reuse | strongest: current package/runtime evidence | reuses package but not orchestration evidence | reuses all current evidence | splits evidence |
| Migration risk | bounded additive inactive slice | medium/high routing migration | lowest short-term | highest long-term |
| OpenWebUI impact | no core change; later one existing Pipe boundary | likely new routing/valve pressure | none | multiple Pipe/valve paths |
| Pack updatability | Pack snapshot remains data authority | Pack remains usable | Type-First benefits lost | divergent update paths |
| Value correctness | preserves source-grounded product inputs | must prove synthetic-to-real binding | current correctness unchanged | inconsistent value authority risk |
| False-singleton visibility | plural plausible types can be added | plural types can be added | risk remains | differs by route |
| Replay | reuses one evidence/replay authority | must bridge separate coordinator | current replay retained | parallel replay pressure |
| Rollback | remove inactive slice; current route remains | disconnect separate route | no migration | route selection rollback is complex |
| Live delivery | one future atomic route change | extra Function/config surface likely | none | two routes to release and verify |
| Historical compatibility | v3 and GOAL 17 remain contained | same, but new route resembles GOAL 17 | historical only | historical boundaries blur |
| Technical debt | lowest sustainable debt | acceptable reserve if domain is proven distinct | preserves semantic limitation | permanent duplicate debt |

## Decision

**Preferred option: Option A.**

Evolve the existing source-fact product boundary to a Pack-backed Type-First
capability in small, inactive, same-source slices. Preserve the current Gate 2
package and source grounding. Reuse all existing semantic choice, expansion,
canonical validation/materialization, ArtifactStore, and evidence/replay
authorities. No new product Pipe, valve, admission, provider call, or
materializer is allowed merely to introduce Type-First.

**Reserve option: Option B.**

Use Option B only if a future contract proves that Type-First has a distinct
business responsibility that cannot live inside the current source-fact
orchestrator. That decision requires a new ADR, an explicit sole-owner change,
producer/consumer evidence, and proof that the separate route cannot become a
duplicate product classifier.

**Option C is rejected** because it discards validated architectural value:
Pack-backed rich type cards, plural plausible types, exact local-key
restoration, and code-owned reason derivation directly address the
false-singleton visibility problem.

**Option D is rejected** because two product semantic routes create competing
owners, divergent evidence and release paths, ambiguous rollback, and lasting
drift.

## Target boundary

Confirmed as the future target:

```text
existing visual input
-> existing validated Gate 2 package
-> one Pack-backed Type-First classifier inside the existing product boundary
-> deterministic prebound options
-> one existing canonical validator/materializer
-> one evidence/replay authority
```

“Classifier” here is a bounded capability, not permission to create a second
runtime owner. Source values remain authoritative and canonical promotion
remains deterministic.

## Sole-owner consequences

- `Gate2DomainSourceFactRuntimeFactory` remains the product orchestration owner.
- `Gate2TablePackageFactory` remains the package owner.
- `Gate2FinancialSemanticContractFactory` remains the Pack/type authority.
- Existing packet/projection owners build any future prebound candidate.
- Existing Choice and Expansion owners parse and derive decisions.
- `Gate2FinancialEvidenceValidatedDecisionFactory` and
  `Gate2FinancialEvidenceMaterializerFactory` remain canonical.
- `Gate2FinancialSemanticV6DecisionEvidenceFactory` remains evidence/replay
  authority.
- ArtifactStore and AnswerContext boundaries do not change.

## PR_232_DISPOSITION

Recommendation: `CLOSE_AFTER_EXTRACTION`.

PR #232 should not be merged as-is and should not be retargeted into the
product route. After KT1, and only under an authorized KT2, preserve the
following ideas/tests by re-expressing them against current `main` and the
existing source-fact boundary:

- Pack-backed rich type cards;
- plural plausible-type response;
- local choice keys with exact mapping restoration;
- deterministic code-owned reason table;
- one-call/no-retry/no-fallback accounting;
- exact evidence serialization, replay, and comparator checks;
- forbidden-field, no-new-factory, and product-unreachable tests.

Do not carry forward the synthetic source projection as product input, a
separate execution coordinator/Pipe, a new valve or admission, duplicated
request/materialization authority, or any implied live qualification.

The GOAL 17 contract, report, receipt, and zero-call evidence remain historical
evidence on PR #232 and its branch. A future implementation requires a fresh
branch from then-current `main`. This avoids importing the complete second
semantic route while retaining its useful contract and test design.

KT1 makes no state change to PR #232.

## Consequences

- Architecture direction is decided, but no convergence code exists.
- Current product/runtime/provider/OpenWebUI behavior remains unchanged.
- `source_fact_selection_v3` remains historical and product-unreachable.
- GOAL 17 remains contract/proof evidence, not mainline runtime.
- Live parity remains separately blocked by
  `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`.
- KT2 may start only with explicit authorization and must begin with an
  inactive same-source contract/proof slice, not route activation.
