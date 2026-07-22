# Broker Reports Workflow Goal 5K — Capability-Aware Semantic Selection v2

Date: 2026-07-22

Branch: `codex/broker-reports-goal5k-capability-aware-selection-v2`

Correction family: Gate 2 source semantic-selection contract

Implementation status: PASSED

Live release and reproof: PENDING AFTER MERGE

## Trigger

The Goal 5J live reproof removed all provider enum-budget failures: 20 of 20
strict-schema calls reached the model with no fallback. The run still ended with
semantic rejections. The dominant failures were 88 missing required values, 65
unreproducible values and 35 invalid subtypes; coverage and source-ownership
errors remained separately measurable.

## Root cause

The model-facing fact object still mixed two responsibilities. The model had to
select business meaning while also writing canonical-system metadata such as
subtype, confidence, completeness and uncertainty. Its value-binding schema
also exposed a broad field/ref cross-product even when a ref could not be
mechanically reproduced as the chosen field. In the observed source packages,
many refs represented whole text spans rather than atomic amount/date values.

That contract asked the model to manufacture low-level structure that the code
could derive or reject deterministically.

## Narrow correction

- Reduced each model-facing fact from seven fields to three:
  `source_ref`, `fact_type`, `value_bindings`.
- Moved subtype, confidence, completeness and uncertainty construction to the
  deterministic materializer.
- Made binding alternatives field-aware. A field/ref pair is exposed only after
  the existing source-value reproducer succeeds for that exact field.
- Made fact-type availability capability-aware. A typed fact is exposed only
  when the package contains the mechanically reproducible fields needed for its
  minimum canonical validity; `unknown_source_row` remains fail-safe.
- Kept source ownership, complete coverage, no-fact decisions, strict JSON
  Schema, final canonical validation and artifact persistence fail-closed.
- Kept the canonical `broker_reports_source_facts_v0` artifact unchanged.
- Regenerated all maintained closed-world Function bundles.

The Gemini semantic visual-table `description + rows` contract, crop extraction,
Gate 1 representation selection, model identities, storage boundaries and
Knowledge/RAG policy are unchanged.

## Evidence

- model-facing fact fields: 7 → 3;
- field/ref alternatives: mechanically reproduced before schema exposure;
- invalid cross-field binding: rejected before canonical materialization;
- model-authored system metadata fields: 0;
- focused and affected regression tests: 49 passed;
- Ruff: passed;
- Python compile check: passed;
- bundle rebuild reproducibility: 3 of 3 exact;
- `git diff --check`: passed;
- private source-label findings: 0;
- private source-value-literal findings: 0.

SHA-256:

- semantic-selection module:
  `f63b4606ea1451a82617b5013c8a43683d654a04bbf418b0da9cb82996804cbf`
- prompt contract:
  `fbac2033038053cc6bc027bb8c0b5945c290514c8f7488d93293725646ad2095`
- Gate 1 bundle:
  `05b19d392cc9aeac1ef0d0014a5899ee7b24b553686efd4a15310778c513ebb3`
- Gate 2 source bundle:
  `da0b0e4fff1c0102c9cd863b0a9ea90c3dfd6911dca6ed88b534128bcd7cbe1f`
- Gate 2 domain bundle:
  `ad0500bf87e743e40506f9df99b3bd3dfbc8d4e720d24bc48a7334d305b00095`

## Remaining live question

This slice does not claim the coverage/ownership defect closed. After the exact
merged revision is atomically released, a new native Gate 2 source run must
measure whether the three-field contract closes value/subtype failures and
whether a separate coverage correction is still required.
