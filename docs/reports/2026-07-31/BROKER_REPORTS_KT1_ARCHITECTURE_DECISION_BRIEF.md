# Broker Reports KT1 Architecture Decision Brief

Date: 2026-07-31

Decision state: `DECISION_GATE_1_CLOSED`; `KT2_NOT_STARTED`

## PROGRAM_OWNER_DECISIONS

```text
preferred_option = A
reserve_option = B_IF_DISTINCT_DOMAIN_IS_PROVEN
pr_232_disposition = CLOSE_AFTER_EXTRACTION
owner_context_policy = SIDECAR_OWNER_METADATA
live_parity_checkpoint_authorized = true
historical_v3_schema_hash_fix_deferred = true
kt2_authorized = false
```

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

PR #232 was closed without merge after the committed extraction ledger and
green KT1 acceptance. Its branch and commit references remain preserved. Any
separately authorized future implementation must start from then-current
`main`, not from PR #232.

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

Owner context is now carried by the versioned
`BROKER_REPORTS_OWNER_CONTEXT.v1.json` sidecar and its Markdown companion, not
by architecture blocks in hash-pinned production Python. No new owner module
was created.

## Evidence and constraints

The earlier KT1 draft demonstrated that architecture-only comments changed
hash-pinned production bytes and tripped generated-bundle and GOAL 16 source
authority checks. The remediation removes those KT1 blocks, restores the
production bytes, moves the context into sidecar metadata, and replaces
comment-presence assertions with owner-contract invariants. Pinned hashes and
historical contracts remain unchanged. GitHub run `30607772132` passed on
remediation head `6c447f4`: 338 passed / 3 existing skips in the anti-drift
selection, 9 passed / 41 intentionally deselected by the workflow's
`-k context_v2_1` slice, and 189 passed in the focused suite. Final evidence
is recorded in the Decision Gate 1 closure report and safe receipt.

Separately, the last read-only GOAL 18 check found all three live Function
bundle hashes different from `main` and a failed closed-world adapter check.
Debt is `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`. No live check or change was made
in KT1.

All product/runtime/provider/OpenWebUI core/Pipe behavior/valve/admission/Pack
and live-change counters are zero.

## Operational boundary

- Decision Gate 1 is closed after local and GitHub acceptance passed and
  PR #232 was closed without merge.
- The authorized live parity checkpoint remains separate and is not executed
  here.
- The historical v3 schema-hash fix remains deferred.
- KT2 remains unauthorized and unstarted.

STOP AT DECISION GATE 1.
