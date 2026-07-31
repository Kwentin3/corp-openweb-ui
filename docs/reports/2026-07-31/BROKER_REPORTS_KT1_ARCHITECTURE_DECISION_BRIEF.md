# Broker Reports KT1 Architecture Decision Brief

Date: 2026-07-31  
Decision state: ready for program-owner review

## Decision

Choose **Option A**: evolve the existing source-fact product boundary to a
Pack-backed Type-First capability. Keep the existing visual input, validated
Gate 2 package, source grounding, canonical financial
validator/materializer, ArtifactStore, and evidence/replay authorities.

Keep **Option B** only as a reserve. A separate V6 route is acceptable only if
a future contract proves a distinct business responsibility and prevents a
second product classifier.

Reject Option C because it discards useful GOAL 17 design: rich Pack-backed type
cards, plural plausible types, exact local-key restoration, and deterministic
reason derivation. Reject Option D because two product semantic routes would
create competing owners, divergent evidence, ambiguous rollback, and ongoing
release drift.

The future target is:

```text
existing visual input
-> existing validated Gate 2 package
-> one Pack-backed Type-First capability in the existing product boundary
-> deterministic prebound options
-> one existing canonical validator/materializer
-> one evidence/replay authority
```

This is an architecture direction, not an implementation or activation.

## Current route truth

- Semantic Visual Table is active in repository product code; exact live parity
  is not proven.
- The broad canonical source-fact domain runtime is the current product route.
- `source_fact_selection_v3` is historical and hard-contained from product.
- GOAL 17 Type-First is contract-only on `main`; PR #232 is an inactive,
  synthetic, zero-call candidate outside `main`.
- FNS 2-NDFL is a deterministic adapter, not a model route.
- AnswerContext runs after completed Gate 2 and is never financial-model input.
- Gate 3 manifest is an active input boundary.
- Gate 4 remains contract-only.
- Live/repository bundle parity is failed/unverified.

Presence of code does not equal product reachability. Mergeability of PR #232
does not equal architecture acceptance. Historical execution does not equal
current activation.

## PR #232 recommendation

Recommend `CLOSE_AFTER_EXTRACTION`.

Extract only the contract and test ideas that strengthen the chosen same-source
route:

- rich Pack-backed type cards;
- plural plausible-type response;
- local choice keys with exact restoration;
- code-owned reason table;
- one-call/no-retry/no-fallback accounting;
- exact replay/comparator and no-new-owner tests.

Do not transfer its synthetic source projection as product input, separate
runtime/Pipe/coordinator, new valve/admission, duplicate request or
materialization authority, or implied provider qualification.

PR #232 was not changed by KT1. A future KT2 implementation should start from
then-current `main`, not from PR #232.

## Ownership baseline

The important sole owners remain:

- visual execution/validation: `PdfDualVlmRuntimeFactory` and
  `SemanticVisualTableValidatorFactory`;
- logical table: `SemanticVisualTableMaterializationFactory`;
- Gate 2 package: `Gate2TablePackageFactory`;
- product source facts: `Gate2DomainSourceFactRuntimeFactory`;
- Pack/type policy: `Gate2FinancialSemanticContractFactory`;
- semantic choice/expansion: existing V6 Choice and Expansion factories;
- canonical financial validation/materialization: existing financial evidence
  factories;
- persistence: ArtifactStore/Resolver;
- replay: existing V6 evidence/replay authority;
- presentation: `AnswerContextSelectionFactory`;
- Gate 3 input: `Gate3ContextManifestFactory`;
- release verification: read-only stage2 delivery verifier.

No new owner module was created.

## Evidence and constraints

The new architecture suite has 15 passing invariants. The existing behavioral
suite has 167 passing tests with one byte-parity test intentionally excluded.
The diagnostic full selection found that authorized comment bytes trip exact
generated-bundle equality and GOAL 16 source-authority hashes. KT1 did not
regenerate bundles, change pinned hashes, weaken tests, or rewrite historical
evidence. The Draft PR therefore carries a declared byte-parity gate.

Separately, the last read-only GOAL 18 check found all three live Function
bundle hashes different from `main` and a failed closed-world adapter check.
Debt is `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`. No live check or change was made
in KT1.

All product/runtime/provider/OpenWebUI core/Pipe behavior/valve/admission/Pack
and live-change counters are zero.

## Owner approvals requested

1. Approve Option A and reserve-only Option B.
2. Approve `CLOSE_AFTER_EXTRACTION` for PR #232.
3. Choose a policy for comment-only source bytes versus exact generated bundle
   and source-pin hashes.
4. Authorize a separate live parity repair checkpoint.
5. Authorize KT2 only as an inactive same-source proof slice; activation must
   remain a later decision.

STOP AT DECISION GATE 1.
