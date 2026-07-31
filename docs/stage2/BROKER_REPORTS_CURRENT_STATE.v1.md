# Broker Reports Current State v1

Status: canonical entry point after inactive KT2.1 closure

Effective date: 2026-07-31

KT2 implementation merge: `16fe3d2b2dd68bbb6440ede3a9b7537849de7456`

KT2.1 implementation merge:
`a4ed4670d80d562fc866ae052d5a6e8d944e46d6`.

KT2.1 evidence merge: reported in the terminal response because a commit
cannot name its own future merge commit.

Current-state lifecycle corrective merge:
`24948360095a749e11b1b0bcedbb8ae871a6b7f8`.

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
- Fresh post-KT2.1 read-only delivery verification passed on 2026-07-31. All
  three Function bundles and 12 managed prompts were exact, and the repository
  factory boundary passed. The earlier atomic release receipt remains valid;
  it was not rerun because KT2 changed no generated or live bundle bytes.

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
  without merge; none of its implementation was imported. The current KT2
  proof is a separately implemented, reviewed and merged subordinate slice.
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

KT2 implemented Option A as one inactive subordinate capability inside the
existing source-fact boundary. It reused the existing Choice, Expansion,
validator, materializer, ArtifactStore, and evidence/replay owners. The proof
is not product- or provider-reachable. Model qualification and product
activation have not started.

KT2.1 adds one deterministic bounded-context builder and one post-response
context-sufficiency guard inside that same inactive proof. The builder follows
only document/table/row and explicit parent, footnote, or continuation links;
it neither sees Type Cards nor returns a financial type. The guard projects
required facets from the existing Pack metadata and fails closed with
`INSUFFICIENT_SEMANTIC_CONTEXT` before typed materialization.

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
current type authority. KT2.1 projects `required_context_facets` from the
Pack's required/identity roles and date/currency requirements, and projects
`context_disqualifiers` from its ambiguity guidance. Pack bytes, hash,
canonical types, meanings, admissions, prompts, valves, and runtime behavior
remain unchanged. The experimental PR #77 registry draft is not a runtime or
documentation authority.

## 9. Known semantic risks

KT2 proved one bounded false-singleton case observable and not typed. KT2.1
then found that the former positive singleton fixture had replaced a semantic
row label with values and that the real packages lacked meaningful raw headers,
section/table title, and reporting period. It is now honestly unclassified as
`INSUFFICIENT_SEMANTIC_CONTEXT`. A separately marked synthetic semantic
redaction proves the sufficient typed path. Corpus generalization and real
model qualification remain future risks.

## 10. Repository and live parity

`repository_debt = CLOSED`, `live_parity_debt = CLOSED`, and
`decision_gate_1 = CLOSED`. Generated bundles rebuild with zero diff and do not
contain the KT2 proof symbol. Fresh read-only verification matched all three
repository bundles to live, so the live bundles also do not contain the proof.
No deploy was required. A later bundle, prompt, valve, admission, or image
change invalidates that claim and requires a new governed release receipt.

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

## 13. KT2 closure and next gates

KT2 is complete at the mechanical inactive proof boundary. KT2.1 is also
complete at its inactive bounded-context and context-sufficiency boundary;
post-merge tests, fresh live readback, and closure evidence passed. Any model
qualification needs
a separately authorized exact candidate and four-disposition live gate. Any
product activation needs a later explicit product decision, fresh reachability
review, governed release, rollback proof, and independent live readback.

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
KT2_READY = FALSE_COMPLETED
KT2_SAME_SOURCE_TYPE_FIRST_PROOF = PASSED
TYPE_FIRST_PRODUCT_REACHABILITY = FALSE
KT2 = COMPLETE
KT21_BOUNDED_CONTEXT = PASSED_INACTIVE
CONTEXT_SUFFICIENCY_GUARD = PASSED
VALUES_ONLY_TYPED = 0
MISSING_REQUIRED_CONTEXT_TYPED = 0
MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
