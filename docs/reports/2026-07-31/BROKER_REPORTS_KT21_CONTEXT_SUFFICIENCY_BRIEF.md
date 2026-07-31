# Broker Reports KT2.1 — Closure Brief

Date: 2026-07-31

Status: `PASSED`

KT2.1 closes the unsafe assumption that a unique simulated model option is
enough to create a typed fact. A deterministic subordinate builder now exposes
bounded document, section, table, target-row, local-structure, and quality
context. A Pack-backed guard then blocks typed materialization whenever the
selected type's required facets are missing, truncated, stale, cross-document,
tampered, or restricted.

The three old real-source units lack meaningful raw headers, section/table
title, and reporting scope. They now honestly terminate as
`INSUFFICIENT_SEMANTIC_CONTEXT → unclassified_financial_input`. A separate,
explicitly synthetic semantic redaction proves the sufficient typed path.

Six deterministic ablations prove that values only, normalized roles only,
raw headers, section/table, or local context alone never produce a typed fact.
Only the full source-bound context is sufficient. Exact replay matches.

Implementation PR [#244](https://github.com/Kwentin3/corp-openweb-ui/pull/244)
merged as `a4ed4670d80d562fc866ae052d5a6e8d944e46d6`. Hosted CI passed.
Post-merge verification returned `33 passed` focused and `2306 passed, 5
skipped` full. Three generated bundles have zero diff. Fresh read-only live
parity passed, with zero KT2.1 proof symbols in live bundles and no deploy.

No provider call, real model qualification, product activation, live mutation,
new canonical type, route, validator, materializer, or replay authority was
introduced.

```text
KT2_MECHANICAL_VERTICAL = PASSED
BOUNDED_SEMANTIC_CONTEXT = PASSED
CONTEXT_SUFFICIENCY_GUARD = PASSED
VALUES_ONLY_TYPED = 0
MISSING_REQUIRED_CONTEXT_TYPED = 0
CONTEXT_ABLATION_SAFETY = PASSED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
