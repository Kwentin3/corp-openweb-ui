# Broker Reports Current State v1

Status: canonical entry point after terminal DOC4 model-output closure

Effective date: 2026-08-01

DOC1 implementation merge:
`c4fa86d8229bc8afdd88bfd0371a96d260790942`.

DOC2 implementation merge:
`0c986919296de16f42ec322400c85e5eee9914f1`.

DOC3 implementation merge:
`ebe3d6a7e375ff97f0242c7ee5bfdd476d594500`.

DOC4 implementation merge:
`3251769728df224f79d085f508c3a47d4e0b8d23`.

DOC4 terminal harness merge:
`73a54d132648e62623a3c959aba54296390cb064`.

DOC4 minimal request-policy merge:
`2cb2926e74d6e9ce8f925a60cdfe319038c8609d`.

DOC4 strict schema-type merge:
`d43149eb96b92fe1090d1af7139ec322ba050503`.

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

## 12.1 DOC0 document-pipeline audit

The 2026-07-31 DOC0 research audit mapped the current PDF path from private
intake through Gate 1, semantic visual-table materialization, ArtifactStore,
Gate 2 segmentation and the model-visible package. It found
`WHOLE_DOCUMENT_ARTIFACT=FRAGMENTED` and proved the first irreversible
downstream context loss at
`FullSourceArtifactBuilder._build_pdf_document ->
PdfLayoutUnitBuilder._build_page_units`.

The existing `description + rows` logical table remains fit only for its
bounded single-crop numeric profile and has explicit document-context,
header-hierarchy, footnote and cross-page gaps. DOC0 made no runtime, bundle,
prompt, valve, admission or live change. The canonical audit artifacts are
`BROKER_REPORTS_DOCUMENT_PIPELINE_MAP.v1.md`,
`BROKER_REPORTS_CONTEXT_LOSS_MATRIX.v1.json`,
`BROKER_REPORTS_LEGACY_AND_REUSABLE_TOOLING.v1.json` and
`BROKER_REPORTS_LOGICAL_TABLE_FORMAT_AUDIT.v1.md`.

## 12.2 DOC1 managed document contract

DOC1 is complete at its contracted inactive boundary. The universal document
model is one ordered `blocks[]` stream with explicit optional relations,
typed source anchors, status-bearing metadata, a strict quality/loss ledger,
and canonical SHA-256 integrity. It supports PDF, HTML, CSV, XLSX, XLS, and an
unknown source without requiring broker-specific sections.

The existing `description + rows` logical table core is reused only inside a
full `TABLE` block. Optional logical-cell annotations distinguish empty from
unreadable cells without asserting physical table geometry. Unknown blocks,
unknown metadata, conflicting values, and incomplete recovery remain explicit;
`unaccounted_context_loss_total` is always zero.

All 53 DOC0 context facets are accounted for: 51 are represented directly and
2 are represented through explicit unknown states. The safe fixture corpus is
hand-authored synthetic evidence of contract expressiveness; the separate DOC2
real-PDF proof closes the PDF real-corpus gap without changing DOC1.

DOC1 added no parser, normalizer, renderer, product route, provider call,
generated bundle, live change, financial type, Semantic Pack, Type-First,
Gate 3, or Gate 4 behavior. DOC2 and DOC3 are later, separate inactive
implementations. DOC4 later passed preflight and closed on a model-output contract blocker; DOC6 has
not started.

## 12.3 DOC2 inactive PDF managed-document builder

DOC2 is complete at its inactive PDF boundary. `ManagedPdfDocumentFactory` is
the single builder owner before the DOC0 `PdfLayoutUnitBuilder` loss point. It
uses page, parser-block and parser-word order, inserts a table at its first
owned word, and rejects ambiguous line/word/table ownership. The old page-local
unit path is not reused as document authority.

Five private real PDFs produced four valid `PARTIAL` Managed Documents and one
terminal encrypted `BLOCKED` result. Across 1,207 source observations there are
0 unresolved, 0 unaccounted losses, 0 invented content, and 0 order conflicts.
Six native grids became validated `TABLE` blocks; 26 invalid regions remain
source-bound `UNKNOWN` blocks with explicit structure losses. Table text is not
duplicated into paragraphs.

Four isolated PDF-only checklists, four artifact-only checklists, and four
sealed comparisons all reached full parity. Critical and noncritical findings
are zero. Two builds matched across all 38 private JSON outputs. The full proof
is private; only aggregate sealed summaries and the dated closure package are
in Git.

DOC2 changes no DOC1 schema, product route, provider/model path, Knowledge/RAG,
embedding/vector path, generated bundle, or live state. DOC3 is the later,
separate inactive LLM Document View implementation. The later DOC4 experiment
closed as `INCONCLUSIVE_MODEL_OUTPUT_FAILURE`; real model qualification and product
activation have not started.

## 12.4 DOC3 inactive LLM Document View

DOC3 is complete at its inactive Managed Document-to-view boundary.
`ManagedDocumentLlmViewFactory` is the single renderer owner for canonical
`broker_reports_llm_document_view_v1` UTF-8 tagged text. Every source-derived
value is compact JSON on one physical line; the fixed trust header and strict
end marker prevent source content from creating renderer delimiters.

The view retains every status-bearing metadata field, safe anchor, ordered
block, TABLE row/cell and structure record, UNKNOWN/VISUAL placeholder,
relation, issue and known loss. A sealed DOC1 field-disposition authority
accounts for all 737 concrete fields exercised by the real corpus with zero
unaccounted paths. Private refs, checksums, paths and access context do not
enter the view.

The same four valid DOC2 Managed Documents rendered 131/131 blocks, 6/6
tables, 82/82 rows, 467/467 cells, 26/26 UNKNOWN blocks, 9/9 VISUAL blocks,
35/35 issues and 44/44 known losses. Four Managed Document-only and four
independent view-only checklists produced four full-parity comparisons: 52/52
dimensions match, with zero critical or noncritical findings. Two runs matched
across all 24 private proof files.

The pinned offline reference tokenizer is
`broker_reports_utf8_byte_bpe_v1` on `tiktoken==0.12.0`. The four views total
289,670 reference tokens; the largest is 161,367. These are model-independent
reference counts, not a context-window or real-model qualification claim.

DOC3 changes no DOC1 schema, DOC2 builder, prompt, valve, provider/model path,
admission, product route, generated bundle or live state. DOC4 later attempted
the separate provider experiment described below.

## 12.5 DOC4 PDF vs LLM Document View semantic experiment

The inactive DOC4 harness implementation passed isolated review, exact-head CI
and merged-main validation. The operator later authorized the same four frozen
documents and OpenAI `gpt-5.4-2026-03-05` with a minimal request: `store`,
sampling and reasoning parameters were omitted, and provider-default retention
was acknowledged. Separate PDF-only agents had already sealed four gold
checklists before provider calls: 461 items and 321 critical facts.

PR #257 implemented the minimal request policy. The next preflight proved that
`store` was not the blocker: OpenAI returned a strict-schema type error. PR
#258 added explicit types without changing the accepted response values. The
new v5 preflight then passed eight exact token counts and all four PDF/View
pairs fit the frozen context budget.

The paired run stopped fail-closed on the first `real_pdf_1/PDF` arm. The
initial response and its one permitted exact replay both failed local semantic
validation. No primary arm was accepted, so no pair, stability replay,
comparison or adjudication completed. Historical failure metadata was not
persisted, so the exact primary HTTP-call and usage totals are not
reconstructible; the harness now preserves that private receipt prospectively.
No private artifact entered Git, and no product route or live state changed.

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
INDEPENDENT_REVIEW = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
STORE_PARAMETER = OMITTED
GOLD_CHECKLISTS_TOTAL = 4
CONTEXT_PREFLIGHT = PASSED
SUCCESSFUL_TOKEN_COUNT_CALLS_TOTAL = 8
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
ELIGIBLE_DOCUMENTS_TOTAL = 4
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

## 13. KT2, DOC1, DOC2, DOC3, DOC4, and next gates

KT2 is complete at the mechanical inactive proof boundary. KT2.1 is also
complete at its inactive bounded-context and context-sufficiency boundary;
post-merge tests, fresh live readback, and closure evidence passed. Any model
qualification needs
a separately authorized exact candidate and four-disposition live gate. Any
product activation needs a later explicit product decision, fresh reachability
review, governed release, rollback proof, and independent live readback.

DOC1 remains the contract authority. DOC2 provides the separately reviewed
inactive PDF builder and real-corpus coverage/parity proof. DOC3 provides the
separately reviewed deterministic full-context view and representation parity
proof. DOC4 passed exact context preflight, then reached a terminal first-arm
model-output contract blocker. It establishes model-task inadequacy for the
frozen DOC4 protocol but no PDF/View semantic-equivalence result. Real model qualification,
product reachability and activation remain not started.

## 14. Forbidden shortcuts

Do not activate Type-First, revive PR #232 or `source_fact_selection_v3`, use
the PR #77 registry as authority, bypass factories, weaken terminal tests,
infer current state from a historical receipt, edit generated bundles by hand,
use customer/private bytes in Git, mutate live state, activate DOC2 or DOC3,
restart DOC4 provider attempts without an explicit new model-or-policy
decision, begin DOC6, or begin Gate 3/4 work.

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
DOC0_CURRENT_PIPELINE_AUDIT = PASSED
WHOLE_DOCUMENT_ARTIFACT = FRAGMENTED
FIRST_IRREVERSIBLE_CONTEXT_LOSS = IDENTIFIED
CURRENT_LOGICAL_TABLE_FORMAT = FIT_WITH_EXPLICIT_GAPS
DOC1_MANAGED_DOCUMENT_CONTRACT = PASSED
PRIMARY_DOCUMENT_MODEL = ORDERED_BLOCK_STREAM
EXPLICIT_RELATIONS = PRESENT
UNKNOWN_BLOCK = SUPPORTED
UNKNOWN_METADATA = SUPPORTED
SOURCE_PROVENANCE = PRESENT
LOSS_LEDGER = PRESENT
UNACCOUNTED_CONTEXT_LOSS_ALLOWED = 0
DOC0_CONTEXT_FACETS_UNACCOUNTED = 0
CURRENT_TABLE_CORE_REUSED = TRUE
PHYSICAL_TABLE_RECONSTRUCTION = NOT_REQUIRED
DOC2_PDF_MANAGED_DOCUMENT_BUILDER = PASSED_INACTIVE
REAL_PDF_TO_MANAGED_DOCUMENT = PROVEN
SOURCE_COVERAGE_RECONCILIATION = PASSED
PDF_ARTIFACT_PARITY_REVIEW = PASSED
READABLE_REAL_PDFS_TOTAL = 4
UNRESOLVED_SOURCE_OBSERVATIONS_TOTAL = 0
UNACCOUNTED_CONTEXT_LOSS_TOTAL = 0
INVENTED_SOURCE_CONTENT_TOTAL = 0
CRITICAL_PARITY_MISMATCHES_TOTAL = 0
REAL_PDF_REPLAY_HASH_MISMATCHES_TOTAL = 0
PDF_NORMALIZER = PRESENT_INACTIVE
LLM_FRIENDLY_RENDERER = PRESENT_INACTIVE
DOC3_LLM_DOCUMENT_VIEW = PASSED_INACTIVE
MANAGED_DOCUMENT_TO_LLM_VIEW = PROVEN
PRIMARY_BLOCK_ORDER_PRESERVED = TRUE
REAL_MANAGED_DOCUMENTS_TOTAL = 4
LLM_VIEWS_RENDERED_TOTAL = 4
CONTENT_BLOCKS_OMITTED_TOTAL = 0
TABLE_CELLS_OMITTED_TOTAL = 0
UNKNOWN_BLOCKS_OMITTED_TOTAL = 0
KNOWN_LOSSES_OMITTED_TOTAL = 0
UNACCOUNTED_RENDER_OMISSIONS_TOTAL = 0
PRIVATE_SOURCE_FIELDS_RENDERED_TOTAL = 0
TRUNCATED_DOCUMENTS_TOTAL = 0
FULL_VIEW_PARITY_DOCUMENTS_TOTAL = 4
CRITICAL_VIEW_PARITY_MISMATCHES_TOTAL = 0
VIEW_REPLAY_HASH_MISMATCHES_TOTAL = 0
DOC4_HARNESS_IMPLEMENTATION = PASSED
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
GOLD_CHECKLISTS_TOTAL = 4
ELIGIBLE_DOCUMENTS_TOTAL = 4
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
DOC4_PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
REAL_MODEL_QUALIFICATION = NOT_STARTED
DOC4 = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
```
