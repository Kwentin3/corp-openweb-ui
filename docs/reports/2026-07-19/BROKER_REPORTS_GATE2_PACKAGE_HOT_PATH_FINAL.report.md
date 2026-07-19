# Broker Reports Gate 2 package hot-path final report

Date: 2026-07-19
Status: accepted

## Acceptance summary

The deterministic package-preparation hot path is closed. On the same accepted
actual corpus, wall time improved from `3519.572 s` to `55.469930 s`
(`63.45x`). Provider/LLM calls during preparation are zero. No timeout,
truncation, concurrency or resumable-processing mechanism masks the result.

Correctness and accounting are explicit:

- one full validation per selected PDF parent identity/checksum and a
  structural/linkage check for every selected child;
- default unused projection full validations are zero while all projections
  remain inventoried;
- one-pass indexed/batch source lookup preserves terminal error semantics;
- `928` units reconcile to `667` packages, `194` blocked noncanonical table
  candidates and `67` blocked visual units;
- neutral XML packages state `financial_interpretation_allowed=false`;
- all remaining unavailable scopes fail closed;
- package preparation leaves ArtifactStore and Knowledge/RAG/vector state
  unchanged.

## Delivery slices

| Commit | Result |
| --- | --- |
| `b6bbf29` | Reuse validated PDF parents within one audit invocation |
| `f46b461` | Select ready inputs before validation and batch source lookup |
| `f117b70` | Refresh all autonomous function bundles |

The final contract/evidence commit adds no runtime or bundle drift.

## Evidence map

- Baseline diagnosis:
  `docs/reports/2026-07-19/OPENWEBUI_BROKER_REPORTS_GATE2_PACKAGE_PERFORMANCE_AUDIT.report.md`
- Optimized remeasurement:
  `docs/reports/2026-07-19/BROKER_REPORTS_GATE2_PACKAGE_HOT_PATH_PERFORMANCE_CLOSURE.report.md`
- Live delivery and parity:
  `docs/reports/2026-07-19/BROKER_REPORTS_GATE2_PACKAGE_HOT_PATH_STAGE_DELIVERY.report.md`
- Public readiness contract:
  `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_MEMORY.v1.md`

## Final status

```text
BROKER_REPORTS_GATE2_PACKAGE_HOT_PATH:
OPTIMIZED

PDF_PARENT_VALIDATION_REUSE:
ENFORCED

UNSELECTED_REPRESENTATION_VALIDATION:
ELIMINATED_WITH_ACCOUNTING_PRESERVED

SOURCE_VALUE_LOOKUP:
INDEXED_AND_EQUIVALENCE_PROVEN

READY_WITH_RESTRICTIONS:
SCOPE_LEVEL_CONTRACT_RECONCILED

ACTUAL_CORPUS_PERFORMANCE:
IMPROVED_AT_LEAST_10X

CANDIDATE_PACKAGE_ACCOUNTING:
PRESERVED_OR_INTENTIONALLY_RECONCILED

PROVIDER_LLM_CALLS_DURING_PREPARATION:
ZERO

CORRECTNESS_AND_ZERO_SILENT_LOSS:
PRESERVED

PRODUCTION_TIMEOUT_OR_TRUNCATION:
NOT_INTRODUCED

REGRESSION_AND_STAGE_VERIFICATION:
PASSED

REPOSITORY_LIVE_ALIGNMENT:
PROVEN

REPOSITORY_HYGIENE:
PROVEN
```
