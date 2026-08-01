# Broker Reports PDF to Managed Document Parity Checklist v1

Effective date: 2026-08-01
Status: inactive review contract reserved for future DOC4 use

The checklist separates three roles:

1. `PDF_ONLY` reads PDF bytes and parser outputs only. It must be sealed before
   any Managed Document artifact is opened.
2. `ARTIFACT_ONLY` reads the validated Managed Document JSON only. It must not
   read the PDF or the PDF-only checklist.
3. `COMPARISON` reads only the two sealed checklists. If a dimension disagrees,
   a targeted source reread is a separate, explicit review action.

The comparison dimensions are source identity, page boundaries, document order,
ordered and unordered source text coverage, table regions, per-table position
and structure, source-bound value samples, visuals, metadata discipline,
provenance, and unknown/loss accounting. Statuses are `MATCH`, `PARTIAL_MATCH`,
`MISSING_IN_ARTIFACT`, `EXTRA_IN_ARTIFACT`, `WRONG_ORDER`, `WRONG_RELATION`,
`WRONG_VALUE`, and `UNVERIFIABLE`.

Private PDF and artifact checklists retain a pointer for every structure item,
table, and sampled value. A one-page simple document samples every value; other
documents use 20 deterministic first/middle/last-spanning samples when at least
20 values are available. Full ordered and multiset hashes still cover all
source values, including unclassified dates, amounts, currencies, fees, taxes,
balances, and totals.

A DOC2 acceptance set requires zero critical mismatches. A full-parity document
also requires zero noncritical mismatches. Checklist values that could contain
private source content are represented by SHA-256, counts, or structural tokens;
the full checklists stay outside Git.

This contract does not implement DOC4 and does not authorize product activation,
provider calls, or model review.
