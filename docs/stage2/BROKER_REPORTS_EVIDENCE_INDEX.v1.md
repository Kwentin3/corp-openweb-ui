# Broker Reports Evidence Index v1

Status: canonical evidence classification

Effective date: 2026-08-01

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
PDF_NORMALIZER = NOT_STARTED
LLM_FRIENDLY_RENDERER = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The DOC1 evidence family defines and validates one universal inactive document
artifact for PDF, HTML, CSV, XLSX, XLS, and unknown sources. Its primary reading
order is `blocks[]`; explicit relations supplement but never replace that
order. Unknown content and every known loss remain visible and provenance is
partitioned from future model-visible content.

The six safe fixtures are hand-authored synthetic expressiveness evidence.
They do not prove a PDF parser or normalizer, real model qualification, product
reachability, activation, or deployment. `REAL_CORPUS_GAP = TRUE` remains
explicit, and DOC2, DOC3, and DOC6 are not started.

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
