# Broker Reports Debt Register v1

Status: canonical pre-KT2 debt register

Effective date: 2026-07-31

Machine authority: `BROKER_REPORTS_DEBT_REGISTER.v1.json`

## Terminal summary

```text
debts_total = 10
unknown_debts = 0
unowned_debts = 0
kt2_blocking_debts = 0
```

An open debt is not silently accepted: every entry below has one owner, a
reason it does not block KT2, and an exact reopening or resolution trigger.

| Debt ID | Domain / owner | Status | Severity | Blocks KT2 | Resolution or reopening trigger |
| --- | --- | --- | --- | ---: | --- |
| `BR-DEBT-SKIP-001` | Tests / Broker Reports Test Maintainers | `PARTIALLY_RESOLVED_NON_BLOCKING` | low | no | Reopen if the private benchmark becomes an approved CI asset, an old GOAL change-set is rebuilt, or a skip masks failure. |
| `BR-DEBT-RUFF-001` | Quality / Repository Quality Maintainers | `OPEN_NON_BLOCKING` | low | no | Fix per touched file or by a dedicated migration before enforcing full Ruff. Baseline: 264 findings in 42 files; mandatory correctness profile passes. |
| `BR-DEBT-V3-001` | Historical compatibility / Gate 2 Historical Compatibility Owner | `DEFERRED_NON_BLOCKING` | medium | no | Reopen for authorized v3 repair, replay incompatibility, or reactivation proposal. |
| `BR-DEBT-PRIVATE-001` | Evidence / Broker Reports Evidence Custodian | `ACCEPTED_PRIVATE_ONLY` | low | no | Resolve privately only when an authorized replay needs exact old crop bytes. |
| `BR-DEBT-WORKSPACE-001` | Git / Repository Operations | `CLOSED` | low | no | Reopen if unclassified reports or dirty user changes appear. |
| `BR-DEBT-BRANCH-001` | Git / Repository Operations | `ACCEPTED_NON_BLOCKING` | low | no | Remove cited historical branches only after an explicit durable-archive decision. |
| `BR-DEBT-REPORT-001` | Docs / Broker Reports Documentation Maintainers | `CLASSIFIED_NON_BLOCKING` | low | no | Reopen if dated evidence is cited as current authority or an unclassified generated report appears. |
| `BR-DEBT-EVIDENCE-001` | Architecture / Broker Reports Architecture Owner | `CLOSED_BY_CONSOLIDATION` | high | no | Reopen if a canonical artifact disappears, diverges, or exists only in a PR/worktree. |
| `BR-DEBT-PR-001` | GitHub / Broker Reports Program Owner | `CLOSED_BY_KT1_6_GITHUB_CLEANUP` | high | no | Reopen for any ambiguous new or reopened Broker Reports PR. |
| `BR-DEBT-WORKTREE-001` | Git / Repository Operations | `OPEN_NON_BLOCKING` | low | no | Remove the inaccessible unregistered metadata with host permission if prune/add fails or before relocation. |

## Skip baseline

The original baseline was 23 skipped tests. The audit found 18
`REMOVE_NOW` cases caused by a class-wide private-reference decorator. The
decorator was narrowed to the two tests that actually require the private
reference. The final baseline is five: two justified conditional private-data
tests and three historical change-set guards. See
`BROKER_REPORTS_SKIP_AUDIT.v1.md`.

## Ruff baseline

Repository-wide Ruff on 2026-07-31 produced 264 findings in 42 files:
`E402=161`, `F401=99`, `F841=4`. The enforced
`E9,F63,F7,F82` correctness profile passes. This is an owned legacy cleanup,
not a hidden KT2 acceptance exception; full Ruff applies to changed Python
files.

## Historical and private boundaries

The v3 schema-hash defect stays isolated behind a hard-false product guard.
Old private crop bytes stay out of Git. Historical branches stay as evidence
anchors. Dated reports remain immutable and are classified by the Evidence
Index. None is a current product or type authority.
