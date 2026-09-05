# Broker Reports Current State v1

Status: `CURRENT_WITH_HISTORICAL_APPENDIX`

Effective date: 2026-09-05

[Pipeline Gates v1](contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md) is the
current normative route authority. Issue #374 updates the PDF portion of the
older state inventory. PDF source custody and safe preflight remain active.
PDF understanding is isolated behind the single `PdfDocumentExtractor` port
and one composition factory. For an ordinary authenticated user, native
OpenWebUI file IDs are owner-checked through `Files` and read through `Storage`;
a configured Mistral adapter makes exactly one provider call per accepted PDF.
The provider-neutral Markdown/image graph is atomically persisted by the sole
`ArtifactStore`, then projected as an owner-scoped `full-source.zip`. There is
no admin qualification route, custom intake/action, RAG route, retry, repair or
fallback. An absent or unselected engine terminates with
`PDF_DOCUMENT_AI_NOT_CONFIGURED`. PDFPlumber,
pdfminer, PyMuPDF, Camelot, Docling, VLM/bbox, hybrid, dual-engine and repair
routes are retired with no fallback. CSV, TXT, HTML, XML, XLSX, DOCX,
archive/ZIP and image boundaries retain their existing status.

On pinned OpenWebUI 0.9.6, the native `MessageInput` upload call sets
`process=false` only for PDF uploads when its authoritative selected-model
state contains exactly `broker_reports_gate1_pipe`. A fail-fast image overlay
applies that source-level intent to the pinned bundle. It must be removed when
upstream provides an equivalent per-model upload-processing policy; it owns
neither file identity nor server-side processing.

The material below is the DOC6-era historical appendix, not the current Broker
Reports entrypoint.
For downstream boundaries, continue with the
[Gate 3 handoff](contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md). Statements below
remain evidence of their dated scope and cannot override current Gate 3 status.

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

DOC5 diagnostic implementation commit:
`512cd07cb425fda32ef1272d0b4d2e5c10b71f93`.

DOC5 diagnostic implementation merge:
`feac6765f5acd4b402d312f2efdd68ea93358c08`.

DOC5 evidence merge: reported in the terminal response because a commit cannot
name its own future merge commit.

DOC6 implementation commit:
`85b238f751e01c4223a548fd9872638c6cf4d2ce`.

DOC6 implementation merge:
`4d1e6297a93893fefafc23fab3b8d8ed47b435e4` (PR #263; CI run 30770742050).

DOC6 evidence merge: reported in the terminal response because a commit cannot
name its own future merge commit.

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

- PDF understanding: `PdfDocumentExtractor`, selected only by
  `PdfDocumentExtractorFactory` and fail-closed while unconfigured;
- provider-neutral non-PDF table package: `Gate2TablePackageFactory`;
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
`BROKER_REPORTS_CONTEXT_LOSS_MATRIX.v1.json` and
`BROKER_REPORTS_LEGACY_AND_REUSABLE_TOOLING.v1.json`.

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
implementations. DOC4 later closed on a model-output blocker; DOC6 later added a
separate inactive v2 without changing DOC1.

## 12.3 DOC2 inactive PDF managed-document builder

DOC2 is complete at its inactive PDF boundary. `ManagedPdfDocumentFactory` is
the builder owner before the DOC0 loss point. Four readable PDFs produced four
source-complete `PARTIAL` artifacts; one encrypted PDF stopped as `BLOCKED`.
All 1,207 source observations are accounted for, with no invention, order
conflict or table/paragraph duplication. Six native grids became TABLE blocks;
the remaining structure stayed explicit UNKNOWN. Four sealed PDF/artifact
comparisons passed. DOC2 changes no DOC1 schema, product route, provider,
bundle or live state.

## 12.4 DOC3 inactive LLM Document View

DOC3 is complete at its inactive Managed Document-to-view boundary.
`ManagedDocumentLlmViewFactory` is the single renderer owner for canonical
`broker_reports_llm_document_view_v1`. It retains all ordered blocks, tables,
UNKNOWN/VISUAL placeholders, relations, issues and known losses while excluding
private refs and access context. All 737 exercised field paths are accounted
for. Four independent comparisons passed all 52 dimensions; replay was exact.
Reference token counts are offline measurements, not qualification. DOC3
changes no DOC1/DOC2, provider, admission, product route, bundle or live state.

## 12.5 DOC4 PDF vs LLM Document View semantic experiment

The inactive DOC4 harness, review and context preflight passed. Four PDF-only
gold checklists were sealed before calls. The authorized first PDF arm and its
one exact replay both failed the structured local output contract, so execution
stopped before an accepted pair or semantic comparison. Exact historical call
and usage totals are not reconstructible; no private artifact entered Git and
no product or live state changed.

```text
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
ELIGIBLE_DOCUMENTS_TOTAL = 4
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

## 12.6 DOC4 manual Codex source audit

Codex separately reviewed all 24 pages and four Views. All 444 gold literals
retained readable meaning, but strict equivalence failed because only 6 of 28
logical tables had validated structure. This audit does not replace the missing
model arms.

```text
MANUAL_CODEX_SOURCE_AUDIT = COMPLETED
MANUAL_CODEX_STRICT_SEMANTIC_EQUIVALENCE = FAILED
EXPECTED_LOGICAL_TABLES_TOTAL = 28
VALIDATED_TABLE_BLOCKS_TOTAL = 6
LOGICAL_TABLES_WITHOUT_VALIDATED_GRID_TOTAL = 22
ORIGINAL_PROVIDER_EXPERIMENT = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
```

## 12.7 DOC5 geometry-backed table recovery

All 22 failures were classified. Review withdrew rectangular experimental
grids after two counterexamples. Geometry found 33 spans in 14 fragments,
including at least 23 body spans across seven tables; DOC1 cannot express that
coverage. DOC5 remains terminal evidence against grid-first recovery.

```text
DOC5_FAILURES_CLASSIFIED_TOTAL = 22
DOC5_UNCLASSIFIED_FAILURES_TOTAL = 0
DOC5_DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
DOC5_PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
DOC5_DOC1_SCHEMA_CHANGED = FALSE
DOC5 = BLOCKED_DOC1_BODY_CELL_SPAN_UNREPRESENTABLE
```

DOC6 did not merge or revive the stopped DOC5.1 rectangular implementation.

## 12.8 DOC6 inactive logical-row recovery

DOC6 adds inactive Managed Document v2 and LLM Document View v2. A TABLE is an
ordered collection of rows with role, order, hierarchy, entries and optional
logical-column bindings. Geometry is secondary evidence, not table meaning.

Across four readable PDFs, all 28 tables, 357 rows and 2,338 entries match the
sealed adjudicated gold. The preserved raw comparison has 29 mismatches: 27
entry surfaces and two derived header paths; all 27 errata entries resolved.
Terminal critical, value-accounting, exact-once ownership and column-binding
mismatches are zero. One row role and one parent link remain explicit
noncritical uncertainties. v1, product, providers, bundles and live state are
unchanged.

```text
DOC6_LOGICAL_ROW_TABLE_MODEL = PASSED
DOC6_CANONICAL_TABLE_MODEL = ORDERED_LOGICAL_ROWS
EXPECTED_LOGICAL_TABLES_TOTAL = 28
REPRESENTED_LOGICAL_TABLES_TOTAL = 28
VISUAL_GOLD_ROWS_TOTAL = 357
MANAGED_DOCUMENT_ROWS_MATCHED_TOTAL = 357
VISUAL_GOLD_ENTRIES_TOTAL = 2338
MANAGED_DOCUMENT_ENTRIES_MATCHED_TOTAL = 2338
UNKNOWN_ROW_ROLES_TOTAL = 1
UNRESOLVED_COLUMN_BINDINGS_TOTAL = 0
UNRESOLVED_ROW_PARENTS_TOTAL = 1
CRITICAL_ROW_MISMATCHES_TOTAL = 0
CRITICAL_ENTRY_MISMATCHES_TOTAL = 0
INVENTED_SOURCE_VALUES_TOTAL = 0
DROPPED_SOURCE_VALUES_TOTAL = 0
DUPLICATED_SOURCE_VALUES_TOTAL = 0
PDF_TO_MANAGED_DOCUMENT_V2_ROW_PARITY = PASSED
MANAGED_DOCUMENT_V2_TO_LLM_VIEW_V2_PARITY = PASSED
PDF_TO_LLM_VIEW_V2_ROW_PARITY = PASSED
DOC6_PROVIDER_CALLS_TOTAL = 0
DOC6_PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
DOC6_PRODUCT_ACTIVATION = NOT_STARTED
```

## 13. Current product boundary

DOC1/View v1 and the current Gate 2 route remain product authority. DOC2,
DOC3, KT2/KT2.1 and DOC6 are inactive proofs. DOC4 remains inconclusive; DOC5
remains a historical blocker. No route, bundle, live, qualification or
activation change occurred.

## 14. Forbidden shortcuts

Do not activate Type-First, revive PR #232 or `source_fact_selection_v3`, use
the PR #77 registry as authority, bypass factories, weaken terminal tests,
infer current state from a historical receipt, edit generated bundles by hand,
use customer/private bytes in Git, mutate live state, activate DOC2 or DOC3,
restart DOC4 provider attempts without an explicit new model-or-policy
decision, resume DOC5 or change DOC1/DOC3 span semantics without an explicit
new contract goal, activate DOC6 v2, treat v2 as the current product route,
revive the DOC5 grid-first model, or begin Gate 3/4 work.

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
MANUAL_CODEX_SOURCE_AUDIT = COMPLETED
MANUAL_CODEX_STRICT_SEMANTIC_EQUIVALENCE = FAILED
SOURCE_LITERAL_MEANING_PRESENT_TOTAL = 444
SOURCE_LITERALS_TOTAL = 444
EXPECTED_LOGICAL_TABLES_TOTAL = 28
VALIDATED_TABLE_BLOCKS_TOTAL = 6
LOGICAL_TABLES_WITHOUT_VALIDATED_GRID_TOTAL = 22
SUMMARY_AND_SEARCH_USEFULNESS = USABLE_WITH_EXPLICIT_LIMITATIONS
GOLD_CHECKLISTS_TOTAL = 4
ELIGIBLE_DOCUMENTS_TOTAL = 4
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
DOC4_PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
REAL_MODEL_QUALIFICATION = NOT_STARTED
DOC4 = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
DOC5_FAILURES_CLASSIFIED_TOTAL = 22
DOC5_UNCLASSIFIED_FAILURES_TOTAL = 0
DOC5_DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
DOC5_PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
DOC5_DOC1_SCHEMA_CHANGED = FALSE
DOC5 = BLOCKED_DOC1_BODY_CELL_SPAN_UNREPRESENTABLE
```
