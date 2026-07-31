# Broker Reports KT1 Architecture Stabilization Report

Date: 2026-07-31

Branch: `refactor/broker-reports-kt1-architecture-stabilization`

Base: `origin/main@9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

Status: `DECISION_PACKAGE_COMPLETE_WITH_DECLARED_BYTE_PARITY_GATES`

## 1. Executive result

KT1 establishes one domain map, one sole-owner matrix, one route-status
baseline, one accepted convergence direction, one pre-task protocol, one
comment policy, targeted owner comments, and 15 executable architecture
invariants.

The preferred future direction is Option A: evolve the existing source-fact
product boundary to consume Pack-backed Type-First capability while reusing
the current visual input, validated Gate 2 package, canonical
validator/materializer, ArtifactStore, and evidence/replay authorities.
Option B is reserve-only if a distinct business domain is proven. Options C
and D are rejected.

PR #232 recommendation is `CLOSE_AFTER_EXTRACTION`. KT1 did not modify, close,
retarget, or merge that PR.

No product behavior, runtime orchestration, provider call, OpenWebUI core,
Pipe/Action behavior, valve, production admission, Semantic Pack, financial
type, managed prompt, or live state changed.

## 2. Repository and PR snapshot

- The original working folder was on the GOAL 17 branch with six untracked
  GOAL 18/report artifacts. It was treated as read-only and left unchanged.
- KT1 work was isolated in one worktree created directly from current
  `origin/main`.
- Base commit: `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`
  (merged PR #231).
- PR #232 at inspection: Draft, head
  `d6954f401ae4734fc1573c7560c981cf084c278c`, base `main`, mergeable, one
  successful `broker-reports-ci` run for that head, no review/comment
  acceptance. Mergeability and a green historical check do not establish
  architecture acceptance.
- PR #233 is a separate open Draft containing the GOAL 18 documentation audit;
  it is not part of `main`.

Historical PRs inspected:

| PR | Maintained meaning in KT1 |
| --- | --- |
| #12 | semantic visual `description + rows` contract |
| #13 | bounded Gemini visual runtime/factory |
| #16 | historical three-table VLM qualification evidence |
| #18 | logical-table and Gate 2 projection migration |
| #19 | default-on atomic semantic visual release policy |
| #23 | deterministic post-Gate-2 AnswerContext |
| #35 | simplified source response; historical |
| #40 | semantic source selection; later contained |
| #231 | Type-First fail-closed contract, inactive |
| #232 | draft inactive GOAL 17 second-route proposal |
| #233 | draft GOAL 18 reconciliation audit |

## 3. Pre-task context actually read

Normative and product context:

- `BROKER_REPORTS_GATE_ARCHITECTURE.md`
- `BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`
- `BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- semantic visual transcription, validation, materialization, migration, and
  PDF VLM runtime contracts
- Gate 2 source-facts, extraction, and managed-prompt contracts
- Financial Semantic Pack, generic financial materialization, financial domain,
  and AnswerContext contracts
- GOAL 16 Type-First fail-closed Markdown/JSON contract
- GOAL 17 inactive implementation Markdown/JSON, report, receipt, tests, and
  PR diff
- GOAL 18 report, safe receipt, decision brief, and saved trace accounting

Maintained code and tests:

- visual intake/VLM/validator/materializer and Gate 2 package owners
- current domain source-fact Pipe/runtime, readiness, segmentation, routing,
  validation, stitching, and ArtifactStore consumers
- historical `source_fact_selection_v3` module, runtime import, and hard false
  product containment guard
- V6 packet/projection/choice/linter/expansion, canonical financial
  validator/materializer, evidence/replay, and financial-domain persistence
- deterministic FNS 2-NDFL adapter
- AnswerContext and Gate 3 manifest owners
- generated bundle builder/tests and read-only release/live verifier
- architecture, producer/consumer, historical containment, Type-First,
  ArtifactStore, AnswerContext, bundle, and atomic release tests

## 4. Domain map summary

Seventeen domains are declared:

1. document intake/detection;
2. structural PDF table recovery;
3. semantic visual transcription;
4. deterministic logical-table materialization;
5. Gate 2 table package;
6. source-fact extraction;
7. financial semantic decision;
8. canonical financial materialization;
9. ArtifactStore persistence;
10. replay/comparators;
11. AnswerContext;
12. Gate 3 context manifest;
13. Gate 4 calculation/declaration;
14. OpenWebUI adapter/Pipe boundary;
15. model/provider boundary;
16. release/parity verification;
17. historical/compatibility routes.

Each domain records purpose, business meaning, input/output, owner, allowed
consumers, forbidden knowledge, runtime/evidence status, debt, adjacency, and
completion criterion.

## 5. Sole owners and duplicate responsibilities

The matrix declares 18 responsibilities. Central product owners are:

- visual execution/validation:
  `PdfDualVlmRuntimeFactory` / `SemanticVisualTableValidatorFactory`;
- logical materialization:
  `SemanticVisualTableMaterializationFactory`;
- Gate 2 package: `Gate2TablePackageFactory`;
- segmentation: `Gate2SourceUnitSegmenterFactory`;
- product source-fact orchestration:
  `Gate2DomainSourceFactRuntimeFactory`;
- Pack/type authority: `Gate2FinancialSemanticContractFactory`;
- V6 choice/expansion:
  `Gate2FinancialSemanticV6ChoiceContractFactory` /
  `Gate2FinancialSemanticV6DecisionExpansionFactory`;
- canonical financial validation/materialization:
  `Gate2FinancialEvidenceValidatedDecisionFactory` /
  `Gate2FinancialEvidenceMaterializerFactory`;
- evidence/replay:
  `Gate2FinancialSemanticV6DecisionEvidenceFactory` /
  `replay_financial_semantic_v6_decision`;
- persistence: `ArtifactStoreFactory` / `ArtifactResolver`;
- AnswerContext: `AnswerContextSelectionFactory`;
- Gate 3 manifest: `Gate3ContextManifestFactory`;
- release parity: read-only
  `scripts/live_verify_broker_reports_stage2_delivery.py`.

Nine matrix rows have a duplicate, historical, proof, or stale counterpart:
type surface, product semantic classification, model response schema, parser,
prebound options, exact restoration, reason derivation, evidence/replay, and
release parity. The two material duplications are:

- `source_fact_selection_v3`: `HISTORICAL_READ_ONLY`, product guard false;
- PR #232 GOAL 17 chain: `DUPLICATE_DO_NOT_ACTIVATE`, reusable ideas/tests
  `PROOF_ONLY`.

No new owner module was added.

## 6. Route baseline

| Route | Status | Product/provider reachability |
| --- | --- | --- |
| Semantic Visual Table | `ACTIVE_PRODUCT` repository; live unverified | product yes; bounded crop provider yes |
| Broad canonical source facts | `ACTIVE_PRODUCT` | product yes; admitted structured provider yes |
| `source_fact_selection_v3` | `HISTORICAL_READ_ONLY` | product no; provider no |
| GOAL 17 Type-First V6 | `CONTRACT_ONLY` on main; PR #232 `INACTIVE_CANDIDATE` / `PROOF_ONLY` | no / no |
| deterministic FNS 2-NDFL | `ACTIVE_PRODUCT` | explicit deterministic caller; provider no |
| AnswerContext | `ACTIVE_PRODUCT` downstream | post-Gate-2 only; provider no |
| Gate 3 manifest | `ACTIVE_PRODUCT` boundary | explicit consumer; provider no |
| Gate 4 | `CONTRACT_ONLY` | no / no |
| release/live bundle state | `UNVERIFIED_LIVE` | exact live parity not accepted |

## 7. Convergence decision

Preferred: **Option A**. Add a future inactive Pack-backed Type-First capability
inside the existing source-fact product boundary and reuse every current
canonical downstream authority.

Reserve: **Option B**, only if a separately approved contract proves a distinct
business domain and one non-duplicate owner.

Rejected:

- Option C loses useful plural-plausibility and exact-restoration design.
- Option D institutionalizes two semantic product routes.

Future target:

`existing visual input -> validated Gate 2 package -> one Pack-backed
Type-First capability -> deterministic prebound options -> existing canonical
validator/materializer -> existing evidence/replay authority`.

## 8. PR #232 disposition

Recommendation: `CLOSE_AFTER_EXTRACTION`.

Preserve as ideas/tests: rich Pack-backed type cards, plural plausible types,
local keys and exact restoration, code-owned reason table, one-call/no-fallback
accounting, exact replay/comparator, and no-new-owner tests.

Do not carry into the product route: synthetic source projection, a separate
Pipe/runtime/coordinator, new valve/admission, duplicate request or
materialization authority, or implied qualification.

GOAL 17 contracts/reports/receipts remain historical evidence on its branch. A
future KT2 branch must start from then-current `main`.

## 9. Comments added

Nine boundary blocks were added to:

- semantic visual transcription contract;
- semantic logical-table materializer;
- Gate 2 table package;
- current domain source-fact orchestration;
- historical source selection validator;
- canonical financial validator/materializer;
- V6 evidence/replay;
- AnswerContext selection;
- read-only release/live verifier.

One historical containment block was added to
`gate2_source_fact_selection.py`. It states why v3 is retained, why product
reachability is forbidden, allowed consumers, and the ADR required to change
status.

All Python production-file changes are comments only.

## 10. Architecture and test evidence

New invariant suite:

```text
15 passed in 2.38s
```

It checks the 15 required facts: sole-owner uniqueness; v3 and GOAL 17
unreachability; visual/financial byte separation; one canonical materializer;
post-Gate-2 AnswerContext; route/import/guard consistency; historical wording;
PR #232 exclusion from main; OpenWebUI core scope; symbol existence; boundary
and containment comments; no new owner module; and CI registration.

Existing behavior/consumer suite, excluding the one byte-exact generated-bundle
comparison:

```text
167 passed, 1 deselected
```

The broader diagnostic run produced:

```text
183 passed, 1 skipped, 1 failed, 14 setup errors
```

The single failure is exact maintained-source/generated-bundle byte equality.
The 14 setup errors are one GOAL 16 source-authority SHA guard repeated across
its generated-contract tests. Both are caused by authorized comment bytes, not
behavior changes:

- generated Function bundles still contain the pre-comment module sources;
- GOAL 16 pins exact SHA-256 for the canonical materialization and evidence
  owner files.

KT1 did not regenerate Function bundles, update pinned historical/contract
hashes, weaken exact tests, or rewrite evidence. Therefore the Draft PR must
not be treated as CI-green until the program chooses how comment-only authority
metadata is carried without violating exact bundle and source-pin policy.

## 11. Live parity debt

Debt: `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`.

The last read-only evidence is GOAL 18 on 2026-07-30:

- 12 managed prompt contracts matched;
- all three live Function bundle hashes differed from repository `main`;
- Gate 1: live `a042ff14…f70519`, repository `a685e1c9…e836af`;
- Gate 2 source: live `d3ba38ed…83d503`, repository
  `aa49f3be…07eef8`;
- Gate 2 domain: live `4f5424f2…3bb0d5`, repository
  `21ab2062…629ace`;
- `provider_adapters_stay_inside_openwebui=false`.

KT1 did not reconnect to live. This drift blocks qualification or activation
because neither the exact deployed code nor the closed-world boundary equals
the intended repository authority. Repair requires a separate checkpoint with
an exact committed head, regenerated canonical bundles, atomic stage,
rollback, and independent readback.

## 12. Change accounting

| Category | Total |
| --- | ---: |
| provider calls | 0 |
| product behavior changes | 0 |
| runtime orchestration changes | 0 |
| OpenWebUI core changes | 0 |
| Pipe/Action behavior changes | 0 |
| managed prompt changes | 0 |
| feature valve changes | 0 |
| production admission changes | 0 |
| Semantic Pack changes | 0 |
| financial types / regex / synonym / shortlist / subagent changes | 0 |
| live changes or deployments | 0 |
| GOAL 17 activation or code transfer | 0 |

## 13. Program-owner decisions still required

1. Approve Option A and reserve-only Option B as the Gate 2 direction.
2. Approve `CLOSE_AFTER_EXTRACTION` for PR #232 after useful ideas/tests are
   catalogued.
3. Decide whether a dedicated comment-metadata mechanism or a separately
   authorized deterministic bundle/hash refresh should resolve the
   comment-only byte-parity gate.
4. Authorize a separate live parity repair checkpoint and identify the intended
   deployed commit.
5. Decide whether the historical v3 schema-hash defect receives a separate
   maintenance task.

## 14. Proposed KT2 structure (not implemented)

1. Reconfirm live/repository authority and resolve comment-byte parity policy.
2. Freeze one same-source input contract from the existing Gate 2 package.
3. Add one inactive Pack-backed Type-First projection through existing owners.
4. Reuse plural-response, exact-restoration, and reason-table tests extracted
   from PR #232.
5. Prove one canonical validator/materializer and evidence/replay chain.
6. Keep provider calls, product imports, valves, admissions, and live changes
   at zero.
7. Present a separate activation decision; do not combine it with proof.

STOP AT DECISION GATE 1.
