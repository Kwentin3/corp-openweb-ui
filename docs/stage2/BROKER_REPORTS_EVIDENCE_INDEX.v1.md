# Broker Reports Evidence Index v1

Status: canonical evidence classification

Effective date: 2026-08-03

## Current authority

| Evidence family | Classification | Current authority |
| --- | --- | --- |
| Gate architecture and authorities | `CANONICAL_CURRENT` | `BROKER_REPORTS_GATE_ARCHITECTURE.md`; `BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md` |
| KT1 domain/route/owner context | `CANONICAL_CURRENT` | Domain Map; Route Status; Owner Context MD/JSON |
| Semantic convergence | `CANONICAL_CURRENT` | `adr/BROKER_REPORTS_GATE2_SEMANTIC_CONVERGENCE.v1.md` |
| Sole owners | `CANONICAL_CURRENT` | `contracts/BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md` |
| Agent context | `CANONICAL_CURRENT` | Pre-Task Context Protocol and Code Comment Policy |
| PR #232 disposition | `CANONICAL_CURRENT` | `architecture/BROKER_REPORTS_PR232_EXTRACTION_LEDGER.v1.md` |
| Current status and debts | `CANONICAL_CURRENT` | Current State, Debt Register, and Skip Audit MD/JSON |
| KT1.5 terminal closure | `CANONICAL_CURRENT` | 2026-07-31 final authority closure report, receipt, and brief |
| KT2 inactive same-source Type-First proof | `CANONICAL_CURRENT` | 2026-07-31 KT2 report, safe receipt, and brief |
| KT2.1 bounded context and sufficiency closure | `CANONICAL_CURRENT` | 2026-07-31 KT2.1 report, safe receipt, and brief |
| DOC0 current document-pipeline audit | `CANONICAL_CURRENT` | Pipeline Map, Context Loss Matrix, Legacy and Reusable Tooling, Logical Table Audit, and 2026-07-31 closure package |
| DOC1 universal managed document contract | `CANONICAL_CURRENT` | DOC1 Decision, Managed Document Contract MD/Schema, DOC0 Coverage Matrix, and 2026-08-01 closure package |
| DOC2 inactive PDF managed document proof | `CANONICAL_CURRENT` | DOC2 Decision, Coverage and Parity Contracts, sealed real-PDF summaries, and 2026-08-01 closure package |
| DOC3 inactive LLM Document View proof | `CANONICAL_CURRENT` | DOC3 Decision, View/Receipt/Checklist Contracts, DOC1 field coverage, sealed real-view summaries, and 2026-08-01 closure package |
| DOC4 PDF vs LLM View semantic experiment | `CANONICAL_CURRENT_TERMINAL_BLOCKER` | DOC4 Candidate and Equivalence Decisions, safe preflight/results/stability summaries, and 2026-08-01 blocked closure package |
| DOC4 manual Codex PDF vs View audit | `CANONICAL_CURRENT_MANUAL_EVIDENCE` | DOC4 Manual Codex Audit Decision and 2026-08-01 manual report/safe receipt |
| DOC5 geometry-backed table recovery | `CANONICAL_CURRENT_TERMINAL_BLOCKER` | DOC5 Decision, failure/results/parity safe summaries, proof contract, and 2026-08-02 blocked closure package |
| DOC6 inactive logical-row table recovery | `CANONICAL_CURRENT` | DOC6 Decision, Managed Document/View v2 contracts, recovery/parity safe summaries, and 2026-08-03 passed closure package |

## DOC6

```text
STATUS = PASSED_INACTIVE
CANONICAL_TABLE_MODEL = ORDERED_LOGICAL_ROWS
EXPECTED_LOGICAL_TABLES_TOTAL = 28
REPRESENTED_LOGICAL_TABLES_TOTAL = 28
VISUAL_GOLD_ROWS_TOTAL = 357
MANAGED_DOCUMENT_ROWS_MATCHED_TOTAL = 357
VISUAL_GOLD_ENTRIES_TOTAL = 2338
MANAGED_DOCUMENT_ENTRIES_MATCHED_TOTAL = 2338
BASELINE_TABLES_TOTAL = 6
BASELINE_TABLES_REGRESSED_TOTAL = 0
CONTINUED_TABLES_TOTAL = 2
UNKNOWN_ROW_ROLES_TOTAL = 1
UNRESOLVED_COLUMN_BINDINGS_TOTAL = 0
UNRESOLVED_ROW_PARENTS_TOTAL = 1
RAW_BASE_CRITICAL_MISMATCHES_TOTAL = 29
ERRATA_ENTRIES_TOTAL = 27
ERRATA_ENTRIES_RESOLVED_TOTAL = 27
CRITICAL_ROW_MISMATCHES_TOTAL = 0
CRITICAL_ENTRY_MISMATCHES_TOTAL = 0
PDF_TO_MANAGED_DOCUMENT_V2_ROW_PARITY = PASSED
MANAGED_DOCUMENT_V2_TO_LLM_VIEW_V2_PARITY = PASSED
PDF_TO_LLM_VIEW_V2_ROW_PARITY = PASSED
PROVIDER_CALLS_TOTAL = 0
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The frozen precomparison gold remains byte-unchanged. Its raw comparisons
preserve 29 mismatches: 27 entry surfaces and two derived header paths. The
independent sealed errata resolves all 27 recorded surface entries; terminal
adjudicated comparisons have zero critical mismatches. This distinction is
part of the acceptance proof, not a hidden rewrite of the raw result.

Managed Document/View v2 are inactive proof artifacts. Managed Document/View
v1 and the current product route remain authoritative; no provider,
qualification, activation, generated bundle or live-state change occurred.

## DOC5

```text
STATUS = BLOCKED_DOC1_BODY_CELL_SPAN_UNREPRESENTABLE
EXPECTED_LOGICAL_TABLES_TOTAL = 28
BASELINE_VALIDATED_TABLE_BLOCKS_TOTAL = 6
FAILED_TABLES_CLASSIFIED_TOTAL = 22
UNCLASSIFIED_FAILED_TABLES_TOTAL = 0
RULED_FRAGMENTS_SPAN_AUDITED_TOTAL = 14
PHYSICAL_SPAN_CELLS_TOTAL = 33
CONFIRMED_BODY_SPAN_CELLS_MINIMUM_TOTAL = 23
DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
DOC1_SCHEMA_CHANGED = FALSE
PROVIDER_CALLS_TOTAL = 0
```

Independent review invalidated the experimental recovered grids before they
entered the canonical implementation. The source-geometry audit then proved
that DOC1 v1 cannot represent body-cell spans or distinguish a real empty cell
from a coordinate covered by a neighboring merged cell. DOC5 therefore stopped
under its contract instead of claiming false table parity.

The DOC4 `444/444` readable-meaning baseline remains closed and valid. DOC5
remains terminal evidence against rectangular grid-first recovery. DOC6 used a
distinct row-first v2 and did not revive the stopped DOC5.1 implementation.

## DOC4

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
INDEPENDENT_REVIEW = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
GOLD_CHECKLISTS_TOTAL = 4
GOLD_CHECKLIST_ITEMS_TOTAL = 461
GOLD_CRITICAL_FACTS_TOTAL = 321
CONTEXT_PREFLIGHT = PASSED
SUCCESSFUL_TOKEN_COUNT_CALLS_TOTAL = 8
PREFLIGHT_INPUT_TOKENS_TOTAL = 152573
ELIGIBLE_DOCUMENTS_TOTAL = 4
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
FAILED_ARM = real_pdf_1/PDF
FAILED_ARM_RETURNED_RESPONSES_TOTAL = 2
PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

Four independent PDF-only gold checklists were sealed before provider calls.
After explicit new policy authorization, PR #257 minimized request fields and
PR #258 fixed provider-strict schema types. The v5 preflight passed all eight
exact counts. The first PDF arm and its exact replay then both failed local
semantic validation, so fail-closed execution stopped before any accepted arm.

Stability, comparison and adjudication did not complete. Historical primary
usage and HTTP-attempt totals were not persisted; future failures are now
preserved privately. All private PDFs, Views, gold, plans, authorizations and
provider payloads remain outside Git. The safe closure does not claim zero
semantic gaps or full equivalence; those values are not evaluated.

The later manual Codex source audit is separate from that provider protocol. It
reviewed all 24 PDF pages and all four Views, reconciled 461 gold items, and
then checked table, order, blank-cell and visual relations directly.

```text
MANUAL_CODEX_SOURCE_AUDIT = COMPLETED
MANUAL_CODEX_STRICT_SEMANTIC_EQUIVALENCE = FAILED
SOURCE_LITERAL_MEANING_PRESENT = 444/444
RAW_EXACT_SOURCE_LITERALS = 427/444
EXPECTED_LOGICAL_TABLES_TOTAL = 28
VALIDATED_TABLE_BLOCKS_TOTAL = 6
LOGICAL_TABLES_WITHOUT_VALIDATED_GRID_TOTAL = 22
UNKNOWN_BLOCKS_TOTAL = 26
SUMMARY_AND_SEARCH_USEFULNESS = USABLE_WITH_EXPLICIT_LIMITATIONS
```

The manual evidence proves strong textual retention but rejects strict
equivalence because row/column, continuation, blank-cell, reading-order and
visual semantics are not fully preserved. It also finds that the frozen View
pointer rule is incompatible with financial facts retained outside TABLE
blocks and that the dense-report gold is not exhaustive. The provider result
remains `INCONCLUSIVE_MODEL_OUTPUT_FAILURE`; the manual audit does not create
or substitute missing model arms.

## DOC3

```text
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
PDF_TO_LLM_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE (LATER DOC4)
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The DOC3 evidence family binds four private valid DOC2 Managed Documents to one
factory-owned deterministic UTF-8 tagged-text view. All 131 blocks, 6 tables,
82 rows, 467 cells, 26 UNKNOWN blocks, 9 VISUAL blocks, 35 issues and 44 known
losses remain visible. Private refs, checksums, paths and access context remain
outside the view and Git.

Four Managed Document-only and four independent view-only checklists were
sealed in separate process passes. Four checklist-only comparisons reached full
parity across 52/52 dimensions with zero critical or noncritical findings. Two
complete runs compared 24 private proof files with zero hash mismatches.

The exact offline reference tokenizer is
`broker_reports_utf8_byte_bpe_v1` on `tiktoken==0.12.0`. The four views total
289,670 reference tokens and the largest is 161,367. These are reference
counts, not model-context qualification.

DOC3 changes no DOC1 schema, DOC2 builder, prompt, provider/model path, product
route, generated bundle or live state. It did not by itself authorize DOC4 or
PDF-to-LLM semantic equivalence. The later authorized DOC4 attempt passed
context preflight but closed on a first-arm model-output contract failure; it did not start qualification or
activation.

## DOC2

```text
DOC2_PDF_MANAGED_DOCUMENT_BUILDER = PASSED_INACTIVE
REAL_PDF_TO_MANAGED_DOCUMENT = PROVEN
PRIMARY_READING_ORDER = PRESERVED
TABLES_INSIDE_DOCUMENT_ORDER = TRUE
UNKNOWN_CONTENT_PRESERVED = TRUE
SOURCE_COVERAGE_RECONCILIATION = PASSED
READABLE_REAL_PDFS_TOTAL = 4
NON_BLOCKED_READABLE_DOCUMENTS_TOTAL = 4
UNRESOLVED_SOURCE_OBSERVATIONS_TOTAL = 0
UNACCOUNTED_CONTEXT_LOSS_TOTAL = 0
INVENTED_SOURCE_CONTENT_TOTAL = 0
PDF_ARTIFACT_PARITY_REVIEW = PASSED
CRITICAL_PARITY_MISMATCHES_TOTAL = 0
REAL_PDF_REPLAY_HASH_MISMATCHES_TOTAL = 0
DOC1_SCHEMA_CHANGED = FALSE
LEGACY_FALLBACK_USED = FALSE
PRODUCT_ACTIVATION = NOT_STARTED
```

The DOC2 evidence family binds five private real PDFs to one inactive builder,
complete source-observation inventories, fail-closed coverage receipts, four
valid `PARTIAL` Managed Documents, and one encrypted terminal `BLOCKED` result.
Private bytes, literal values, names, raw refs, paths, full inventories, and
checklists remain outside Git.

Four PDF-only and four artifact-only checklists were sealed in isolated passes;
four checklist-only comparisons reached full parity with zero critical or
noncritical findings. The simple one-page PDF checks every value, the
table-heavy PDF checks all tables plus 20 source-bound samples per pass, and
full ordered/unordered hashes cover all values. Two builds matched over all 38
private JSON outputs.

DOC2 changes no DOC1 schema, product route, provider/model path, generated
bundle, or live state. The later DOC3 family is a separate inactive view proof;
DOC2 alone does not authorize DOC4, real model qualification or activation.

## DOC1

```text
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
PDF_NORMALIZER = PRESENT_INACTIVE_BY_DOC2
LLM_FRIENDLY_RENDERER = PRESENT_INACTIVE_BY_DOC3
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The DOC1 evidence family defines and validates one universal inactive document
artifact for PDF, HTML, CSV, XLSX, XLS, and unknown sources. Its primary reading
order is `blocks[]`; explicit relations supplement but never replace that
order. Unknown content and every known loss remain visible and provenance is
partitioned from future model-visible content.

The six safe fixtures are hand-authored synthetic expressiveness evidence and
do not themselves prove a PDF parser or normalizer. The later DOC2 family is
the separate real-PDF proof; DOC3 is the separate inactive deterministic view.
DOC4 remains terminally blocked. DOC6 later supplies a separate inactive v2
recovery and representation-parity proof. Real model qualification, product
reachability, activation, and deployment remain not started.

## DOC0

```text
CURRENT_DOCUMENT_PIPELINE = MAPPED
WHOLE_DOCUMENT_ARTIFACT = FRAGMENTED
FIRST_IRREVERSIBLE_CONTEXT_LOSS = IDENTIFIED
CURRENT_LOGICAL_TABLE_FORMAT = FIT_WITH_EXPLICIT_GAPS
AUTOMATIC_LEGACY_FALLBACKS_TOTAL = 3
SILENT_CONTEXT_DEGRADATION_PATHS_TOTAL = 4
NEW_PIPELINE_IMPLEMENTATION = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

DOC0 is a research-only current-code audit. It binds five read-only real-PDF
normalization observations and the existing frozen eight-table actual-corpus
evidence to a privacy-safe route map and loss matrix. It does not reopen KT2 or
KT2.1, implement a new document pipeline, qualify a model or activate a route.

## KT2

```text
KT2_SAME_SOURCE_TYPE_FIRST_PROOF = PASSED
TYPE_FIRST_PRODUCT_REACHABILITY = FALSE
PROVIDER_CALLS = 0
LIVE_CHANGES = 0
MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The KT2 evidence family binds one real Gate 2 package and three real source
units to privacy-safe structural copies, a Pack-backed Type Card projection,
sealed prebound options, four human-reviewable traces, exact replay, and a
false-singleton comparator. Private values and raw refs remain ignored under
`local/`; only hashes, structure, safe fixtures, and aggregate outcomes are in
Git. The proof is current repository evidence, not product activation or model
qualification evidence.

## KT2.1

```text
BOUNDED_SEMANTIC_CONTEXT = PASSED
CONTEXT_SUFFICIENCY_GUARD = PASSED
VALUES_ONLY_TYPED = 0
MISSING_REQUIRED_CONTEXT_TYPED = 0
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The KT2.1 evidence family records the three-unit context-flow audit, one
structure-only bounded-context owner, Pack-backed context requirements, six
deterministic ablations, typed and fail-closed traces, exact replay, post-merge
tests, and fresh read-only live parity. It is inactive repository evidence;
it does not authorize provider execution, model qualification, product
reachability, activation, or deployment.

## GOAL 18

```text
GOAL18 = HISTORICAL_AUDIT_EVIDENCE
decision_adopted_by = Semantic Convergence ADR
live_parity_statements = historical_as_of_2026_07_30
current_live_parity = CLOSED_BY_KT1_5
```

The full reconciliation report, safe receipt, and decision brief are preserved
unchanged in `docs/reports/2026-07-30/`. They were already copied exactly to
`main` by PR #238. The private trace pack remains private/local and is
`PRIVATE_ONLY`; no customer values or raw provider payloads are in Git.

## PR #77 research

Ten safe, dated human-readable research reports/receipt are content-preserved
under `docs/reports/2026-07-23/` as
`HISTORICAL_RESEARCH_SUPERSEDED`. Markdown line-end whitespace was normalized
for current CI; historical wording and the JSON receipt are unchanged. These
files are useful for archaeology, safe corpus
accounting, rejected alternatives, and decision provenance. They do not define
current architecture, operational risk, or a runtime registry.

The machine-readable
`BROKER_REPORTS_GATE2_CANONICAL_FACT_REGISTRY_DRAFT.safe.json` is `REJECT` for
current `main`: despite its explicit experimental flag, copying it would create
an attractive competing type authority beside the current Semantic Pack. Its
exact blob remains recoverable from PR #77 commit
`38cce3f4f5b741600547af114fb8396becf7f0ae`.

The per-artifact decision is in
`architecture/BROKER_REPORTS_PR77_EXTRACTION_LEDGER.v1.md`.

## Reading rule

`CANONICAL_CURRENT` overrides `HISTORICAL_EVIDENCE` and
`HISTORICAL_RESEARCH_SUPERSEDED` for present-tense state. Historical files are
immutable evidence of what was observed or proposed on their dates. No entry
is `UNKNOWN`.
