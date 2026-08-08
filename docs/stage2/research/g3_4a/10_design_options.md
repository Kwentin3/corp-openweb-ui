# G3.4A — Minimal design options

Status: `REVIEW_ONLY`; no implementation is authorized.

## 1. Existing table/section partition — recommended first

Use existing canonical table or section boundaries. Each request keeps the
same renderer, dictionary, instruction and strict schema; only the document
slice changes. REPO already has 20 tables. Its largest measured first-to-last
alias span is 335,496 characters versus 3,884,393 for the full projection, so
existing boundaries have the strongest simple reduction signal. This span is a
diagnostic, not an exact future request measurement.

Risk: local section notes and cross-table relationships must be carried and
merge accounting must prevent duplicate accepted pairs.

## 2. Contiguous row groups for one oversized table

Use only when one canonical table itself exceeds the reviewed request budget.
Repeat the exact header plus table/section notes and select contiguous rows—no
semantic or keyword filtering. This is necessary for the single-table CSV if a
215,810-token one-shot is judged too large.

Risk: facts spanning groups, totals outside the group and repeated-context
targets need explicit uncertainty and deterministic merge rules.

## 3. Empty-cell alias hygiene

Keep display-empty cells and coordinates visible but research omission of their
target aliases. It is simple and reversible, and the frozen proposals targeted
zero such cells.

Risk and limit: target completeness must be re-proven. Even the maximum measured
REPO saving is only 8.1%; it does not replace partitioning.

## Deliberately not proposed

No second renderer, compact schema, semantic pre-classifier, keyword selector,
RAG/Knowledge route, provider retry or new domain. The options reuse current
owners and add at most one bounded partition policy plus merge accounting after
human approval.
