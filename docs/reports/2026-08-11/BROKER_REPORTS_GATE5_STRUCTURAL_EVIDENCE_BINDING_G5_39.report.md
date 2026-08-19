# G5.39 — Structural Evidence Binding Research Tournament

Terminal: `NO_STRATEGY_PROVEN`
Date: `2026-08-11`
Mode: research only; no production architecture activated.

## Answer

None of the five tested strategies achieved the required combination:

```text
hard correctness
+ DEV
+ independent real holdout
+ large real document
+ bounded context
```

H1 was the only strategy with aggregate hard-invariant PASS, because it failed closed outside its row-local domain. It nevertheless proved only the row-local holdout and could not prove the real multi-row DEV or large cases. H2–H5 produced at least one invalid proof. Selecting any of them would violate the frozen winner rule.

Therefore no minimal production contract is selected and `G5.40 — Clean Structural Evidence Implementation` is **not authorized**.

## Frozen baseline and corpus

The baseline was G5.38C:

- public PDF SHA-256 `25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67`;
- G5.38C safe receipt SHA-256 `0c73e4ae741b15dc1c177aac4ddaf104b3afc5d6e06856a303f3639c594c5044`;
- two accepted page-region targets;
- one semantic plus one role call, zero retry/repair/merge;
- 4 diagnostic table projections, 16 rows, 274 cells;
- exact literals recovered, but one-row event provenance not proved.

The final common research baseline was commit `1fb05ed3e725ff27701d97b1136dcb7ca01aee7d`, tree `8370cebde17bcf6f0c39ea10b2f03c2cf4512ae5` in an ephemeral nested repository.

Corpus v3 safe manifest SHA-256: `dc9619eb446c01c82cbce538e01c70be7c170c25da95c4ef230efce217d61c2d`.

| Sample | Assignment | Complete structural pressure |
|---|---|---:|
| `DEV_PUBLIC_TBANK` | known official/public development case | 4 tables / 16 rows / 274 cells / 13,585 chars |
| `HOLDOUT_REAL_001` | independent real customer broker PDF | 6 pages / 12 tables / 212 rows / 1,927 cells / 525,510 chars |
| `LARGE_REAL_001` | distinct real customer broker PDF | 65 pages / 3,455 rows / 3,474 cells / 217,842 chars |
| `NEGATIVE_AB_001` | controlled A/B ambiguity and positive explicit relation | 2 tables / 4 rows / 18 cells |
| CSV / HTML / XLSX | existing disposal regressions | existing product route |

Private exact values and paths stayed under ignored `local/`. Only hashes and aggregate metrics are published.

Two corpus corrections happened before their affected comparisons:

1. v1 was invalidated before inference because the proposed holdout was a fee schedule, not a customer broker report.
2. v2 H1 was invalidated before H2 because the experimental DEV/holdout projections were oracle-filtered. V3 restarted all hypotheses with complete structural spaces.

## Frozen experiment profile

- Model: `gpt-5.4-mini-2026-03-17`.
- Temperature `0`, JSON object mode.
- Per case: at most 16,000 total input chars and 1,800 output tokens.
- H4: at most 3 calls, 2 retrieval rounds and 10,000 retrieved chars per case.
- H1/H2/H3: one call, zero retrieval rounds.
- H5: one call and one deterministic retrieval round.
- Retry `0`; repair `0`; best-of-N `false`; answer merge `false`.
- Whole-document context was forbidden for the large sample.

Two HTTP `400` responses occurred before semantic inference because the gateway required an explicit JSON-mode instruction. They were attributed as transport failures, the common profile was corrected, and no semantic answer was retried.

## Comparison matrix

Corrected deterministic adjudication is shown below. Cost numbers are totals over four assigned cases, while budget enforcement was per case.

| H | Contract | Proven / 4 | DEV | Holdout | Large | A/B | False joins | Hard invariants | Calls | Input chars / tokens | Output tokens | Rounds / retrieved chars | LOC / concepts | Verdict |
|---|---|---:|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| H1 | one row + cells | 1 | fail closed | **PROVEN** | fail closed | fail closed | 0 | **PASS** | 4 | 6,474 / 1,861 | 605 | 0 / 3,621 | 49 / 2 | reject: incomplete |
| H2 | one-pass closed multi-target bundle | 0 | invalid | budget blocked | budget blocked | invalid | 1 | **FAIL** | 2 | 10,915 / 3,894 | 448 | 0 / 0 | 80 / 2 | reject |
| H3 | deterministic proximity/containment neighborhood | 1 | invalid | **PROVEN** | fail closed | invalid | 0 | **FAIL** | 4 | 14,153 / 5,104 | 675 | 0 / 10,273 | 103 / 4 | reject |
| H4 | compact map + exact get-by-ref + H2 bundle | 0 | invalid | fail closed | budget guard | invalid | 0 | **FAIL** | 10 | 23,556 / 8,632 | 606 | 6 / 19,703 | 165 / 6 | reject |
| H5 | deterministic exact-literal closure + bundle | 1 | invalid | invalid | invalid | **PROVEN** | 2 | **FAIL** | 4 | 22,428 / 8,335 | 1,117 | 4 / 18,324 | 158 / 5 | reject |

Experiment and immutable evidence identities are in `BROKER_REPORTS_GATE5_STRUCTURAL_EVIDENCE_BINDING_G5_39.ledger.safe.json`.

## Experiment ledger conclusions

### H1 — canonical row/cell targets

Commit: `483284897851fa1216274062aaecfe398c03b639`.

H1 correctly proved the real row-local holdout and failed closed on the three non-row-local cases. It is the simplest safe strategy, but it does not answer the research question. The real DEV and large facts require evidence outside one row.

### H2 — closed multi-target evidence bundle

Commit: `1a9c829d6e3d372acebf2301cea5015223408c8d`.

A closed bundle is a plausible final proof shape, but it is not a discovery mechanism. The complete real holdout and large spaces exceeded the one-pass budget. On bounded DEV and A/B contexts the model still emitted invalid literals/refs and one cross-event join.

### H3 — deterministic bounded neighborhood

Commit: `d89c24c3fafc754d7367d9c126655b79ef844442`.

Containment/proximity was useful for the row-local holdout and safely stopped on the remote large evidence. It did not reach the cross-page DEV witness and allowed invalid/out-of-space refs on DEV and A/B. Structural proximity is not event identity.

### H4 — compact map plus bounded get-by-ref

Commit: `3c8c348a4b9065497d2024d324b692cc45378d8b`.

The retrieval mechanism remained bounded, but model navigation was not reliable enough. DEV requested only four rows and missed the aggregate witness. Holdout reached exact rows but returned ambiguous. The large map requested the correct dividend/tax pages plus a wrong accrual page and an extra page; the frozen budget guard stopped before the row-index call. A/B reached two rows but returned an invalid ref bundle.

Thus H4 retrieval plus H2 proof is not proven by this tournament.

### H5 — deterministic exact-key closure

Commit: `f7fc8be01b97e275a0ebf001b0323c686205bf66`.

H5 was a substantive post-H4 alternative: runtime, not the model, selected rows through exact source-literal equality or explicit source relations. It proved the explicit A/B positive case, but its frozen closure omitted 3 of 24 DEV witness refs and it joined unrelated rows on holdout and large. Literal equality is still not financial-event identity.

## Validator correction

The initial evaluator treated any ref from the forbidden A+A+B+B pattern as a false join. That incorrectly included legitimate A refs. Commit `4e815d9d40d137f15dc78a7faeacd266e1e9282b` corrected the predicate to require the complete forbidden pattern, added a positive Transaction-A test, and re-adjudicated immutable model outputs without replaying inference.

Validator tests: `3 passed`. The correction changed false-join counts and allowed H5's correct A/B fact, but did not create a winner.

## What the tournament proved

These are constraints, not a selected production design:

1. First-class exact row/cell refs are necessary for literal verification but insufficient for distributed facts.
2. A closed multi-target bundle remains a necessary final proof boundary, but it cannot decide which refs belong to one event.
3. Proximity, page membership, model navigation and raw literal equality are all weaker than financial-event identity.
4. Retrieval correctness and provenance correctness are separate contracts.
5. `one fact = one row` is a research scar from a proof fixture, not a valid general rule.
6. The missing authority is an explicit, source-verifiable relation/aggregation witness whose origin is not broker-specific and is not invented by the LLM.

No generic graph, persistent database or service is justified by these results. A small typed relation witness may be enough, but this tournament did not prove how to author it.

## Downstream and regression pressure

Relevant unchanged product-path tests:

```text
python -m pytest -q \
  tests/test_broker_reports_gate5_coverage_expansion.py \
  tests/test_broker_reports_gate5_related_securities_events.py

8 passed in 3.87s
```

This includes CSV/HTML/XLSX convergence through Gate 4, declaration semantics and XSD-valid XML, plus exact whole-quantity related-event behavior and ambiguity negatives.

An expanded run with the standalone disposal tax-model file produced `13 passed, 3 failed`; all three failures were the same pre-existing isolated fixture initialization error `gate4_cache_missing`. No assertion regression or G5.39 production change was involved.

Gate 4, Tax Models, declaration owners and XML were not edited by G5.39. The product repository was already dirty on entry; that pre-existing state was preserved.

## Cleanup and repository discipline

- All H1–H5 worktrees and experiment branches were removed.
- The ephemeral nested research Git repository and all generator/strategy code were deleted.
- Private corpus and immutable raw/adjudicated results remain only under ignored `local/`.
- No experimental factory, feature flag, schema, runtime or persistence surface remains in the product tree.
- No commit, push, PR, GitHub issue or product activation was performed.
- The only retained product-repository artifacts are safe reports/manifests/ledger/receipt under `docs/reports/2026-08-11/`.

KISS check: no strategy that passed the mandatory correctness/generalization boundary exists, so simplicity cannot select a winner. H1 is simpler and safer than the rest, but incomplete; it is not promoted.

## Scope stop and next allowed goal

`G5.40 — Clean Structural Evidence Implementation` is blocked because there is no selected contract.

The next allowed research boundary is:

```text
G5.39R — Source-authored Structural Relation Proof
```

Its question should be narrower: can a minimal typed relation/aggregation witness be derived from source structure and exact arithmetic/identity constraints before LLM role binding, without broker templates, semantic search or a generic graph?

Nothing from that follow-up is implemented here.
