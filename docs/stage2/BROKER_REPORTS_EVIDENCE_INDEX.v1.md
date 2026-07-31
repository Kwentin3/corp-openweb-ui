# Broker Reports Evidence Index v1

Status: canonical evidence classification

Effective date: 2026-07-31

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
