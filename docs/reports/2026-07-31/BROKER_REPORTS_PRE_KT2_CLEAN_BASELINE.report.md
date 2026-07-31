# Broker Reports — Pre-KT2 clean baseline closure

Date: 2026-07-31

Status: `PASSED`

Scope: documentation, GitHub authority, repository baseline, tests, and clean
worktree consolidation. KT2 implementation was not started.

## Terminal result

```text
CANONICAL_CONTEXT = COMPLETE
AMBIGUOUS_OPEN_BROKER_REPORTS_PRS = 0
UNKNOWN_DEBTS = 0
UNOWNED_DEBTS = 0
KT2_BLOCKING_DEBTS = 0
KT2_READY = TRUE
KT2_STARTED = FALSE
```

## Authority timeline

| Boundary | Commit / result |
| --- | --- |
| Goal start `origin/main` | `cf84128e54692d541c000ad26c6d35fbcc1afe2f` (PR #238 merge) |
| Operational/live authority | `db009421b68c8b09df728239d23c217e5482d3a1` |
| Prior KT1.5 evidence merge | `dd677feecb1c9a6adc0fa568045ee8782429834c` |
| Consolidation PR | #239, merged |
| Consolidation merge | `277bfa95704397706b32c85962107cf7301c32d3` |
| Evidence closure PR | #240, merged before terminal response |
| Final `origin/main` | reported in the terminal response because the evidence merge commit cannot self-reference |

Repository debt, live parity debt, and Decision Gate 1 remain closed. Fresh
read-only delivery and atomic release verifiers passed against operational
authority `db009421...`; no live mutation or provider call was performed.

## Material actually read

### Repository and task authority

- the KT1.6 task attachment;
- current `origin/main`, branches, worktrees, primary Workspace status, open PR
  inventory, full skip sources, CI workflow, Ruff baseline, and existing
  architecture/debt documents;
- `services/broker-reports-gate1-proof/AGENTS.md` and root instructions;
- `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md`;
- `docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`.

### KT1.5 and Decision Gate evidence

- `BROKER_REPORTS_KT15_FINAL_AUTHORITY_CLOSURE.report.md`;
- its safe receipt and brief;
- Decision Gate 1 report, safe receipt, and brief;
- KT1 Architecture Stabilization report, receipt, and decision brief.

### PR review sources

- PR #238 full 12-file diff and merge `cf84128...`;
- PR #234 head `5125ebae590d5da9014a4cfe3392afc9231961ae`:
  Domain Map, Sole Owner Matrix, Route Status, Semantic Convergence ADR, Owner
  Context MD/JSON, Pre-Task Protocol, Code Comment Policy, PR #232 ledger,
  invariant tests, workflow, reports, and receipts;
- PR #233 head `91095844bd131a42dc601676e8d03757376ab317`:
  GOAL 18 full report, safe receipt, and decision brief;
- PR #77 head `38cce3f4f5b741600547af114fb8396becf7f0ae`:
  all nine research reports, safe receipt, and experimental registry draft.

### Load-bearing symbols inspected

`Gate2DomainSourceFactRuntimeFactory`, `Gate2TablePackageFactory`,
`Gate2FinancialSemanticContractFactory`,
`Gate2FinancialSemanticV6PacketFactory`,
`Gate2FinancialSemanticV6ChoiceContractFactory`,
`Gate2FinancialSemanticV6DecisionExpansionFactory`,
`Gate2FinancialEvidenceValidatedDecisionFactory`,
`Gate2FinancialEvidenceMaterializerFactory`,
`Gate2FinancialSemanticV6DecisionEvidenceFactory`,
`ArtifactStoreFactory`, `ArtifactResolver`, `AnswerContextSelectionFactory`,
`Gate3ContextManifestFactory`, `PdfDualVlmRuntimeFactory`,
`SemanticVisualTableValidatorFactory`, and
`SemanticVisualTableMaterializationFactory`.

## Exact authority snapshot

- Initial primary Workspace: branch `main`, exact
  `cf84128e54692d541c000ad26c6d35fbcc1afe2f`, clean.
- Consolidation worktree: isolated branch from exact initial `origin/main`.
- Generated bundle parity: all three rebuilds produced zero diff.
- Live parity: fresh delivery verifier `PASSED`; fresh atomic verifier `PASSED`;
  all three bundle hashes, 12 prompts, valves, rollback identity, image,
  loader, factory boundary, and workload quiescence were exact.
- Initial related open PRs: #234, #233, #77; PR #238 was already merged.
- Final open PR inventory: empty.
- A stale inaccessible `.git/worktrees/corp-openweb-ui-kt1-worktree`
  directory is unregistered and does not affect Git operations; it remains an
  owned, triggered, non-blocking operations debt.

## Artifact matrix

| Artifact family | Current main | PR #238 | PR #234 | PR #233 | PR #77 | Primary Workspace | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| KT1.5 final closure report/receipt/brief | yes | no | no | no | no | tracked | `CANONICAL_CURRENT` |
| GOAL 18 report/receipt/brief | yes | exact source | no | exact source | no | tracked | `HISTORICAL_EVIDENCE` |
| NDFL Epic Context audit trio | yes | exact source | no | no | no | tracked | `HISTORICAL_EVIDENCE` |
| Decision Gate 1 trio | yes | exact source | duplicate identical | no | no | tracked | `CANONICAL_CURRENT`; PR copy `DUPLICATE_IDENTICAL` |
| KT1 architecture report/receipt/brief | yes | exact source | duplicate identical | no | no | tracked | `HISTORICAL_EVIDENCE`; PR copy `DUPLICATE_IDENTICAL` |
| Domain Map, Route Status, ADR, Owner Context, owner matrix, agent protocols | yes | no | extracted and updated | no | no | tracked | `CANONICAL_CURRENT` |
| PR #232 extraction ledger and architecture invariant test | yes | no | extracted and updated | no | no | tracked | `CANONICAL_CURRENT` |
| Current State, Evidence Index, Debt Register, Skip Audit | yes | no | no | no | no | tracked | `CANONICAL_CURRENT` |
| PR #77 nine reports plus receipt | yes | no | no | no | source | tracked | `HISTORICAL_EVIDENCE` / `HISTORICAL_RESEARCH_SUPERSEDED` |
| PR #77 experimental registry JSON | no | no | no | no | source only | no | `REJECT`; recoverable at source commit |
| GOAL 18 private trace pack/customer bytes | no | no | no | private only | no | private/local only | `PRIVATE_ONLY` |

No artifact remains `UNKNOWN`. The nine PR #77 Markdown reports retain their
historical wording with only line-end whitespace normalized for current CI;
the staged safe receipt Git blob is exact to PR #77.

## PR terminal decisions

- PR #238: `MERGED` as `cf84128e...`; 12 evidence files reviewed and
  preserved.
- PR #239: `MERGED` as `277bfa957...`; canonical architecture/context and
  tests are present on current main.
- PR #234: `CLOSED / SUPERSEDED_BY_CANONICAL_CONSOLIDATION`. Nine canonical
  documents plus its invariant test/CI route were transferred and current
  statuses corrected. Six duplicate report artifacts were not imported again.
- PR #233: `CLOSED / MERGED_VIA_CONSOLIDATION`. Its three exact artifacts are
  on main and indexed as dated historical evidence; private trace material
  remains private.
- PR #77: `CLOSED_AFTER_SUPERSESSION_AUDIT`. Nine reports and one receipt are
  historical; the competing experimental registry JSON is rejected.

Historical branches referenced by evidence were not deleted.

## Canonical architecture context

The canonical set now includes:

- Current State MD/JSON and Evidence Index;
- Debt Register MD/JSON and Skip Audit MD/JSON;
- Semantic Convergence ADR;
- Domain Map and Gate 2 Route Status;
- Owner Context MD/JSON;
- Sole Owner Matrix;
- Pre-Task Context Protocol and Code Comment Policy;
- PR #232 and PR #77 ledgers;
- global gate architecture and architecture authorities.

Current state is explicit:

```text
repository_debt = CLOSED
live_parity_debt = CLOSED
decision_gate_1 = CLOSED
pr_232 = CLOSED_WITHOUT_MERGE
preferred_convergence = A
operational_authority = db009421b68c8b09df728239d23c217e5482d3a1
kt2 = NOT_STARTED
```

## Debt register

Ten debts are registered. All have an owner, evidence, non-blocking reason, and
reopening trigger. Counts are:

```text
unknown_debts = 0
unowned_debts = 0
kt2_blocking_debts = 0
```

Open non-blocking debt is limited to the repository-wide Ruff backlog, five
conditional/historical skips, the isolated historical v3 defect, private old
trace bytes, retained evidence branches, dated report wording, and stale
unregistered worktree metadata. The former missing-evidence and ambiguous-PR
debts are closed by this terminal sequence.

Repository-wide Ruff baseline is 264 findings in 42 files:
`E402=161`, `F401=99`, `F841=4`. The mandatory correctness profile and full
Ruff for changed Python files pass.

## Skip audit

All 23 original skips were classified individually:

- 18 `REMOVE_NOW`: fixed by removing the class-wide private-reference skip;
- 2 `JUSTIFIED_CONDITIONAL_SKIP`: exact private reference binding/scoring;
- 3 `HISTORICAL_GUARD`: GOAL 14/15/16 exact-diff guards;
- 0 `PLATFORM_UNAVAILABLE`;
- 0 `TEST_DEBT`;
- 0 unclassified or KT2-blocking skips.

Final full-suite skip total is five. No skip, xfail, or deselection was added.

## Verification

| Check | Result |
| --- | --- |
| Managed builders | 8/8 passed |
| Function bundle rebuilds | 3/3, zero diff |
| Fresh live delivery verifier | passed, read-only |
| Fresh atomic verifier | passed, read-only |
| Architecture/current-state/debt/skip tests | passed |
| Receipt integrity (GOAL 18, KT1.5, new JSON authorities) | passed |
| Full suite | `2273 passed, 5 skipped`, 0 failed/errors |
| Full suite with `--cache-clear` | `2273 passed, 5 skipped`, 0 failed/errors |
| GitHub PR #239 CI | passed, run `30629585992`, job `91152588755` |
| Mandatory Ruff | passed |
| Changed-file full Ruff | passed |
| Repository-wide Ruff inventory | 264 owned non-blocking findings |
| `compileall` | passed |
| Privacy/integrity | passed |
| `git diff --check` | passed |
| Generated bundle diff | 0 |

## Change accounting

```text
runtime_changes = 0
live_changes = 0
product_logic_changes = 0
openwebui_core_changes = 0
provider_calls = 0
customer_documents_used = 0
semantic_pack_changes = 0
financial_type_changes = 0
type_first_activation = 0
historical_receipt_rewrites = 0
operational_bundle_hash_changes = 0
gate3_changes = 0
gate4_changes = 0
```

The only Python behavior change is test-only: 18 previously hidden benchmark
tests now execute. No application/runtime Python changed.

## Worktree closure

The temporary KT1.6 worktree is removed after the evidence merge. The final
KT2 authority is created at `../corp-openweb-ui-kt2` with branch `main`, exact
`HEAD == origin/main`, clean status, and generated bundle diff zero. The
primary Workspace is not the KT2 authority.

## Final assertion

```text
PR_238 = MERGED
PR_234 = CLOSED_AFTER_CANONICAL_EXTRACTION
PR_233 = CLOSED_AFTER_CANONICAL_PRESERVATION
PR_77 = CLOSED_AFTER_SUPERSESSION_AUDIT
CANONICAL_ARCHITECTURE_CONTEXT = PRESENT_ON_MAIN
CANONICAL_GOAL18_EVIDENCE = PRESENT_ON_MAIN
CURRENT_STATE_INDEX = PRESENT_AND_VALID
DEBT_REGISTER = COMPLETE
UNKNOWN_DEBTS = 0
UNOWNED_DEBTS = 0
KT2_BLOCKING_DEBTS = 0
UNCLASSIFIED_SKIPS = 0
AMBIGUOUS_OPEN_BROKER_REPORTS_PRS = 0
FULL_SUITE_FAILURES = 0
FULL_SUITE_ERRORS = 0
GENERATED_BUNDLE_DIFF = 0
KT2_AUTHORITY_WORKTREE = CLEAN
KT2_READY = TRUE
KT2_STARTED = FALSE
```
