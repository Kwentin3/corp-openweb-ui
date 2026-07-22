# Broker Reports Workflow Goal 5M — Domain Text Label Candidates Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5m-domain-text-label-candidates-v1`

Correction family: Gate 2 domain text-value binding

Implementation status: PASSED

Live release and reproof: PENDING AFTER MERGE

## Trigger

The first full native domain run after Goal 5L completed with rejections. Of 39
domain packages, 37 passed and two `document_summary_evidence` packages were
rejected. All 41 provider calls used strict JSON Schema, with no fallback and
no provider failures.

Both rejected packages were full-source text units with one selected text ref
and no deterministic value candidates. The initial answer invented a
normalized label that code could not reproduce. The repair answer removed the
binding, after which canonical validation correctly rejected the required
label and provenance gap.

## Root cause

The domain router legitimately recognizes summary/total semantics in text
segments. The deterministic candidate builder, however, returned early when a
unit had no table rows. Therefore text packages could be routed to
`document_summary_evidence` while the model-facing schema offered no
mechanically reproducible label/value pair.

## Narrow correction

- Removed the table-row-only early return from deterministic candidate
  construction.
- Passed normalized text into the existing mechanical value reproduction
  boundary.
- Added `label` candidates for `document_summary_evidence` text segments only
  when `trimmed_text` reproduction succeeds.
- Bound the provider schema to those exact normalized values and source-value
  refs even for full-source text units.
- Kept absent fields open for non-table packages unless deterministic
  candidates exist; normalized table projections retain their existing
  fail-closed null behavior.
- Regenerated all three maintained closed-world Function bundles.

The canonical `broker_reports_source_facts_v0` artifact, final validator,
source positional-selection contract, Gemini semantic visual-table contract,
Gate 1 representation selection, model identities, storage boundaries and
Knowledge/RAG policy are unchanged.

## Evidence

- failing domain packages isolated: 2 of 39;
- accepted packages before correction: 37 of 39;
- provider fallback outputs: 0;
- provider failures: 0;
- deterministic text-label candidate policy: present;
- provider-normalized label enum: candidate-bound;
- provider original-value refs: candidate-bound;
- focused and affected regression tests: 63 passed;
- Ruff: passed;
- Python compile check: passed;
- bundle rebuild reproducibility: 3 of 3 exact;
- `git diff --check`: passed;
- private source-label findings: 0;
- private source-value-literal findings: 0.

SHA-256:

- domain package builder:
  `dc9091cea7986a9c18bb3a1668013e57302fc278864eef4ceb6e6e1bfc1bad52`
- provider source-fact contract:
  `d7e9f4599a7c8e4eb02506e721049f2d1f9ffc9bda9f0f4b39b9c6f1bb2823f8`
- Gate 1 bundle:
  `4fdfb2199c5b6dfa055b240a430ec6791357a95a5d83b67227bf43bc077a5ec9`
- Gate 2 source bundle:
  `c4fe5122a6a935033353c077851fb593f507441d8087afadc99d2e190b95a599`
- Gate 2 domain bundle:
  `056d01c1a0a4efc9ad104a404f4f8994afae98941d394518383c8019c9cb01fc`

## Remaining live question

After atomic release of the exact merged revision, the same native full-domain
workflow must prove 39 of 39 packages accepted and produce the answer-context
selection plus Gate 3 context manifest. This report makes no pre-release live
claim.
