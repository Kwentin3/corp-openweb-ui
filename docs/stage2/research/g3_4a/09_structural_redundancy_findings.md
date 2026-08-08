# G3.4A — Structural redundancy findings

Status: `RESEARCH_ONLY`

## Exact route

```text
CanonicalArtifactV1
-> CanonicalReaderFactory.create
-> Gate3ProjectionFactory.create
-> exact published dictionary rendering
-> one minimal instruction
-> existing structured request builder/provider adapter
-> exact final provider request
```

The frozen final request has three messages only: instruction, dictionary and
projection. There is no history, metadata or model-visible alias mapping. The
dictionary occurs once.

## What is not duplicated

- The 710-character provider schema declares only output shape. It contains no
  concrete alias, label value, canonical mapping, document ID or document
  value.
- The dictionary is not copied into the schema or instruction.
- The projection is not repeated in another message.
- The provider wrapper is 173 compact-JSON characters in both requests.

`SCHEMA_DUPLICATION = NOT_FOUND`. The frozen schema defect
`schema_version: {}` explains G3.4 validation rejection, but it does not explain
input size.

## What expands

1. The entire active document is rendered into one request.
2. Tables use a rectangular Markdown grid with generic `row`/`column N`
   scaffolding.
3. Every actual cell has a cell alias and every row with actual cells has a row
   alias.
4. Physically present but display-empty cells still receive aliases.

Alias markup is material—24.4% of compact HTML, 32.0% of large CSV and 39.4%
of REPO projection characters—but is not the whole root cause. Removing every
alias would still leave 216,738 characters for the large CSV and 2,352,917 for
REPO.

The rejected frozen large proposal used both granularities: 269 row targets
and 96 cell targets. The compact proposal used three cell targets. These raw
outputs are not accepted semantics, but they prove that neither row nor cell
addressing is merely dead technical decoration in the measured request shape.

## Earlier supplied prompt/skill material

One earlier managed skill contains a useful design rule: make one decision over
the entire supplied **bounded source context**, never over an isolated label.
The paired prompt narrows this further to one deterministically prepared
financial fragment. This supports deterministic partitioning that carries the
whole local table/section context.

That material is valuable as research evidence for context boundaries, not as
a second Gate 3 semantic authority. The older broad JSON/declaration extraction
drafts introduce different schemas, readiness workflows and methodology gates;
importing them into G3.4 would duplicate owners and enlarge the task. The
current nine-label dictionary is more precise for bounded labeling and remains
unchanged.

## Classification

### A — safe structural reduction candidates

- Do not repeat dictionary/schema/projection: already satisfied.
- Research suppressing aliases only on explicit display-empty cells while
  preserving their blank rendered positions. Exact maximum markup savings in
  this corpus: 426 chars compact (2.8%), 6,465 chars large (2.0%), 313,431 chars
  REPO (8.1%). No frozen proposal targeted an empty cell, but this is still a
  contract candidate, not an implemented guarantee.

### B — semantic filtering ideas, research only

- prioritise income/tax/charge-bearing sections;
- deprioritise positions, repeated totals or informational notes;
- use label-family hints to select candidate rows.

All three can remove relevant counterexamples or context. None is authorized
for runtime.

### C — document partitioning

- first use existing canonical section/table boundaries;
- for one oversized table, use bounded contiguous row groups with the exact
  table header and table/section notes repeated;
- preserve stable aliases and deterministic merge/duplicate accounting.

### D — unsafe or information-losing

- keyword-only row selection;
- dropping totals, footnotes or repeated rows without source semantics;
- removing all row aliases or all cell aliases;
- arbitrary token windows without headers and local notes;
- replacing the exact dictionary with older broad extraction prompts.
