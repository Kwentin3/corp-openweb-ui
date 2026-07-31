# Broker Reports Current State v1

Status: canonical entry point for pre-KT2 work

Effective date: 2026-07-31

Canonical consolidation merge: `277bfa95704397706b32c85962107cf7301c32d3`

This file routes an agent to the current authorities. It does not replace the
versioned contracts, domain map, sole-owner matrix, or historical receipts.

## 1. Product goal

Broker Reports converts bounded customer document evidence into reproducible,
source-grounded artifacts. Provider output is a proposal. Deterministic
validation, materialization, persistence, replay, and declared consumers own
canonical state.

## 2. Current operational authority

- Operational/live authority: `db009421b68c8b09df728239d23c217e5482d3a1`.
- Release: `broker-reports-db009421b68c`.
- KT1.5 evidence merge before the canonical evidence consolidation:
  `dd677feecb1c9a6adc0fa568045ee8782429834c`.
- Fresh read-only delivery and atomic verifiers passed on 2026-07-31. All
  three Function bundles, 12 managed prompts, valves, runtime identities,
  rollback identity, workload quiescence, and factory boundary were exact.

## 3. Gate 1 status

Gate 1 is active and closed at its released contract boundary. PDF semantic
visual processing stays bounded to crop transcription, deterministic
validation, and `description + rows` materialization. Native Knowledge/RAG,
whole-document provider upload, local OCR production, and canonical financial
meaning in the visual model remain forbidden.

## 4. Gate 2 current route

The current product route is the broad canonical source-fact route owned by
`Gate2DomainSourceFactRuntimeFactory`. It consumes the existing validated
Gate 2 package, routes through maintained factories, validates/materializes
canonical outputs, persists through ArtifactStore, and exposes only declared
AnswerContext/Gate 3 manifest inputs. Its exact reachability and exclusions
are in `architecture/BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md`.

## 5. Historical routes

- `source_fact_selection_v3`: `HISTORICAL_READ_ONLY`; the product containment
  guard is hard false.
- GOAL 17 / PR #232 Type-First V6: contract and proof evidence only; PR closed
  without merge; no implementation exists on current `main`.
- GOAL 18: `HISTORICAL_AUDIT_EVIDENCE`; its 2026-07-30 live drift finding was
  true at the report date and was later closed by KT1.5.
- PR #77 canonical-domain research: `HISTORICAL_RESEARCH_SUPERSEDED`; its
  machine registry draft was rejected as a competing current authority.

## 6. Accepted convergence

Option A is accepted: evolve the existing source-fact product boundary with a
small inactive, same-source, Pack-backed Type-First capability and reuse the
existing Choice, Expansion, canonical validator/materializer, ArtifactStore,
and evidence/replay owners. Option B is reserved only if a distinct business
domain is proven through a new ADR. A second active semantic route is rejected.

This decision establishes direction only. KT2 is ready to start after an
explicit authorization, but has not started and is not authorized by this
document.

## 7. Sole owners

The normative owner inventory is
`architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`; the responsibility matrix
is `contracts/BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md`. Load-bearing owners are:

- visual execution and validation: `PdfDualVlmRuntimeFactory` and
  `SemanticVisualTableValidatorFactory`;
- logical table and Gate 2 package: `SemanticVisualTableMaterializationFactory`
  and `Gate2TablePackageFactory`;
- product source facts: `Gate2DomainSourceFactRuntimeFactory`;
- Pack/type authority: `Gate2FinancialSemanticContractFactory`;
- choice/expansion: existing V6 Choice, Packet, and Expansion factories;
- canonical financial output:
  `Gate2FinancialEvidenceValidatedDecisionFactory` and
  `Gate2FinancialEvidenceMaterializerFactory`;
- persistence/replay: ArtifactStore/Resolver and
  `Gate2FinancialSemanticV6DecisionEvidenceFactory`;
- downstream selection: `AnswerContextSelectionFactory` and
  `Gate3ContextManifestFactory`;
- live parity: `live_verify_broker_reports_stage2_delivery.py`.

## 8. Semantic Pack status

The Financial Semantic Pack and its hash-pinned snapshot remain the sole
current type authority. KT1.6 changes no Pack bytes, types, admissions,
prompts, valves, or runtime behavior. The experimental PR #77 registry draft
is not a runtime or documentation authority.

## 9. Known semantic risks

False-singleton visibility, corpus generalization, source-to-type ambiguity,
and candidate/provider qualification remain future semantic risks. They are
the subject of bounded KT2 proof work, not an excuse to add a second route,
invent values, relax fail-closed validation, or claim production readiness.

## 10. Repository and live parity

`repository_debt = CLOSED`, `live_parity_debt = CLOSED`, and
`decision_gate_1 = CLOSED`. Generated bundles rebuild with zero diff. The live
authority is exact to the three committed bundle hashes recorded in the KT1.5
receipt. A later code, bundle, prompt, valve, admission, or image change
invalidates that claim and requires a new governed release receipt.

## 11. Canonical evidence

Use `BROKER_REPORTS_EVIDENCE_INDEX.v1.md` to distinguish current authority,
dated historical evidence, superseded research, and private-only evidence.
Historical reports must be read at their report date; they never override this
file or the current architecture documents.

## 12. Current debts

Use `BROKER_REPORTS_DEBT_REGISTER.v1.md` and its JSON companion. All debts are
classified and owned. There are no unknown, unowned, or KT2-blocking debts.
The repository-wide Ruff backlog, five final conditional/historical skips,
historical v3 defect, private old-trace bytes, retained evidence branches, and
stale inaccessible worktree metadata are explicit non-blocking debts with
reopening triggers.

## 13. KT2 prerequisites

Before any KT2 implementation: obtain explicit authorization; start from the
clean `main` worktree; read the ADR, route status, owner context, sole-owner
matrix, current debt register, and Pre-Task Protocol; define one inactive
same-source slice; identify exact owners and consumers; keep provider calls and
activation separately gated; and prove no new product route or materializer.

## 14. Forbidden shortcuts

Do not activate Type-First, revive PR #232 or `source_fact_selection_v3`, use
the PR #77 registry as authority, bypass factories, weaken terminal tests,
infer current state from a historical receipt, edit generated bundles by hand,
use customer/private bytes in Git, mutate live state, or begin Gate 3/4 work.

```text
REPOSITORY_DEBT = CLOSED
LIVE_PARITY_DEBT = CLOSED
DECISION_GATE_1 = CLOSED
CANONICAL_CONTEXT = COMPLETE
KT2_READY = TRUE
KT2_STARTED = FALSE
```
