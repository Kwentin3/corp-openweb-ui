# Broker Reports Workflow Goal 5L — Positional Coverage Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5l-positional-coverage-v1`

Correction family: Gate 2 source ownership and coverage

Implementation status: PASSED

Live release and reproof: PENDING AFTER MERGE

## Trigger

The Goal 5K native reproof proved that the capability-aware contract removed
the low-level metadata/value failure class. Six of ten packages passed, 119
facts were accepted, model-authored system metadata stayed at zero and all 16
provider outputs used strict JSON Schema with no fallback.

The remaining dominant failures were nine duplicate-source-ownership errors
and two coverage gaps. One required-value error and one cross-source binding
error remained secondary.

## Root cause

The v2 model-facing object had two independent arrays: `facts` and
`no_fact_results`. A source ref could therefore be returned in both arrays or
in neither. Standard strict JSON Schema can bound each ref enum but cannot
express the cross-array invariant “every ref occurs exactly once in exactly one
array.” Repair prompting reduced but did not eliminate the structural freedom.

## Narrow correction

- Replaced the two model-facing arrays with one ordered `decisions` array.
- Removed model-facing `source_ref` and source ownership entirely.
- Each decision contains only `decision_type` and `value_bindings`.
- The provider schema requires exactly N decisions for N model-decidable source
  refs with equal `minItems` and `maxItems`.
- Deterministic code maps decision index N to the authoritative source ref at
  index N, then separates facts from no-fact results and builds canonical
  coverage.
- A no-fact decision is represented by an allowed no-fact reason in
  `decision_type` and must have no value bindings.
- A wrong decision count fails closed with one typed
  `source_fact_selection_decision_count_mismatch` error.
- Field-aware mechanical value reproduction and capability-aware fact types
  from Goal 5K remain unchanged.
- Regenerated all maintained closed-world Function bundles.

The canonical `broker_reports_source_facts_v0` artifact, final validator,
Gemini semantic visual-table contract, crop extraction, Gate 1 representation
selection, model identities, storage boundaries and Knowledge/RAG policy are
unchanged.

## Evidence

- model-facing ownership fields: 1 → 0;
- model-facing decision fields: 2;
- independent model-facing coverage arrays: 2 → 1;
- exact positional decision cardinality: enforced;
- duplicate/gap ownership state after provider validation: unrepresentable;
- positional no-fact source mapping: tested;
- wrong decision count fail-closed: tested;
- focused and affected regression tests: 50 passed;
- Ruff: passed;
- Python compile check: passed;
- bundle rebuild reproducibility: 3 of 3 exact;
- `git diff --check`: passed;
- private source-label findings: 0;
- private source-value-literal findings: 0.

SHA-256:

- semantic-selection module:
  `81c2ef5139c6a6422fcaade39cff742d5c4835241e23283f64ba5ecfaa434486`
- prompt contract:
  `6c7b583f344c7ba658c2ad973a7a245e4d96607805e876ff92ee946e52ed9fa1`
- Gate 1 bundle:
  `c837f77ea6902a36fc255e373f61245ddc40cc32309c8eb2efbda590b770f028`
- Gate 2 source bundle:
  `048fe8c3703f1be5c8ad90215a8c8a5f7f0b6899afa3e28a479f5c0e8f015326`
- Gate 2 domain bundle:
  `d1e8e22ed667bab3f75c7dfc00149c4aec06d2861a4bd79ed599fab7f0bc9d14`

## Remaining live question

After atomic release of the exact merged revision, a new native Gate 2 source
run must prove all ten packages terminal or isolate any remaining binding-only
defect as a separate correction. This report makes no pre-release live claim.
