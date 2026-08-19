# Broker Reports G5.52 — PDF Table Structural Preservation at Gate 2

Date: `2026-08-14`

Status: `PARTIAL_PROOF_DOWNSTREAM_PREFLIGHT_BLOCKED`

## Outcome

The exact `pdf_table_projection_terminal_fallback_text` class localized by
G5.51 had source-proved geometry, rows and cells. Gate 2 discarded that
structure for two local reasons:

1. the existing normalized projection acceptance check required every row to
   have at least two cells, so one legitimate full-width structural row
   rejected an otherwise regular ruled table;
2. after acceptance, the Canonical handoff rectangularized a sparse projection
   and would have created five cells that did not exist in the source.

Both gaps are repaired in the existing owners. The real bounded projection is
now `ready`, with 42 rows, 6 columns and exactly 247 source cells. Canonical
materialization preserves all 247 cell identities and their individual source
provenance. It adds no financial labels or transaction meaning.

Proven terminals:

- `PDF_TABLE_STRUCTURAL_PRESERVATION_PROVEN`;
- `CANONICAL_ROW_CELL_IDENTITY_PROVEN`;
- `GATE2_TABLE_FALLBACK_DEFECT_REPAIRED`;
- `CROSS_DOMAIN_TABLE_REPAIR_CONSISTENCY_PROVEN`.

Not proven:

- `ONE_REAL_FACT_COMPLETED_FROM_RESTORED_STRUCTURE`.

The ordinary downstream replay stopped before provider transport with
`DOWNSTREAM_REPLAY_BLOCKED_MODEL_NOT_PUBLISHED`. Provider submissions,
retries, response repairs and special Gate 3 workarounds are all zero.

## Scope and authority

- The existing PDF text, layout, ruled-grid candidate, normalized projection,
  Canonical normalizer, Canonical store/reader and structural chunk factories
  were reused.
- The original PDF bytes were not reread; existing intermediate artifacts were
  sufficient to locate and reproduce both degradation points.
- The repair changes only Gate 2 structural acceptance and Canonical structural
  handoff. Gate 3 Role Pack, Gate 4, Gate 5, tax logic and declaration
  projection were not changed.
- No new parser, OCR/VLM path, schema generation, semantic reader, retry or
  relation inference was added.

## Path Receipt

| Layer | Had table identity? | Had rows? | Had cells? | Why degraded? |
| --- | ---: | ---: | ---: | --- |
| parser text/geometry | yes | 42 | 247 | ruled grid and exact geometry were retained |
| PDF table candidate unit | yes | 42 | 247 | one source-proved full-width structural row; the other 41 rows have 6 cells |
| normalized projection before | candidate only | 0 | 0 | `TABLE_PROJECTION_ACCEPTANCE_GAP`: acceptance used the minimum cells per row and rejected the full-width row |
| Canonical before | no | 0 | 0 | accepted the terminal text fallback because the projection was blocked |
| normalized projection after | yes | 42 | 247 | `ready / validated_geometry`; ownership and coverage validators pass |
| Canonical after | yes | 42 | 247 | sparse source cells and per-cell provenance are preserved; the target fallback issue is absent |

The first `structured -> fallback text` transition was therefore in the
existing normalized table projection acceptance owner. A second defect existed
at the Canonical handoff and was exposed only after the first repair.

## Exact diagnosis and repair

The target candidate owns all contributing geometry words exactly once. Its
row-cell distribution is one source cell in one full-width row and six source
cells in each of 41 ordinary rows. The old check rejected the table because it
tested the minimum row cell count. The bounded correction tests whether the
candidate has any multi-column row while retaining every existing confidence,
bounding-box, word-ownership, coverage, strategy and size guard.

The accepted projection is intentionally sparse: `42 x 6` describes its
coordinate space, while only 247 cells exist. The old Canonical matrix path
would materialize 252 cells. The repaired handoff is used only when the
projection is sparse and carries forward the existing cell coordinate,
bounding-box reference and literal source-value references. Already rectangular
tables continue through the old byte/behavior path.

Classification:

- first degradation: `TABLE_PROJECTION_ACCEPTANCE_GAP`;
- second degradation: `CANONICAL_STRUCTURAL_HANDOFF_GAP`;
- source insufficiency: not observed for this table class.

## One real table and row/cell proof

The isolated private proof copy produced a validator-clean Canonical artifact:

- table identity: 1 repaired target table;
- row identity: 42 exact rows;
- cell identity: 247 exact and unique source coordinates;
- cell provenance: 247/247 cells have exact bounding-box provenance;
- literal provenance: 207/247 cells have non-empty literal source references;
- source-empty cells remain bounding-box-backed rather than inferred;
- one ordinary six-cell row has literal provenance for all six cells;
- target fallback issue references after materialization: 0;
- financial or tax fields introduced by Gate 2: 0.

The proof used an isolated copy of the private store and the public factory
route:

`NormalizedTableProjectionFactory.create` ->
`CanonicalNormalizerFactory.create` ->
`CanonicalArtifactStoreFactory.create` ->
`CanonicalReaderFactory.create` ->
`Gate3StructuralChunkFactory.create`.

The original private store was not mutated, and no private identifier, path,
literal, payload or provider trace is published in this report.

## Neighbor and black-box checks

- Existing good rectangular table: unchanged coordinate count and original
  coarse table provenance path.
- Target problematic table: fallback becomes source-proved table/row/cell
  structure.
- Ambiguous neighboring layout: the separate
  `pdf_table_geometry_word_coverage_mismatch` candidate remains blocked and
  falls back.
- Bounded neighbor inventory: 74 candidates are structurally ready and one
  unrelated ambiguous candidate remains blocked.
- Structure only: no `SECURITY_PURCHASE`, `SECURITY_DISPOSAL`, commission,
  currency inference or transaction matching is emitted by Gate 2.
- Adaptive context policy and its whole/chunk threshold are untouched.

## Downstream replay boundary

The G5.51 sale target with only `currency` missing was not produced by this
exact table-candidate transition: it came from a different coarse
`pdf_page_text_unit`. The exact fallback class in G5.51 belongs to the
corroborating purchase region. Treating them as the same structural target
would itself invent a source relation.

The repaired purchase table was activated only in an isolated proof-store copy
and reached the normal structural chunk owner. The approved provider model was
visible during the initial authenticated inventory, but the live replay
preflight immediately afterward saw only non-provider product wrappers and
stopped with `model_not_published`. No model request was submitted. Therefore
there is no honest Gate 3 annotation, Gate 4 fact, or role-complete financial
fact to claim from this run.

## Verification and guardrails

Pre-fix black-box evidence was captured for both defects:

- the full-width-row PDF fixture failed `ready` versus `blocked` before the
  acceptance repair;
- the sparse Canonical fixture produced 6 rectangular cells instead of 4
  source cells before the handoff repair.

Final focused behavioral and bundle regression is green: `79 passed`, with 5
external SWIG deprecation warnings. Targeted Ruff checks pass, and
`git diff --check` reports no whitespace defects (only Windows LF/CRLF notices).
An earlier expanded relevant selection was green at `806 passed` before the
final no-op-for-sparse narrowing was added; the two paths affected by that
narrowing were then rerun and passed.

A deliberately broader final sweep reported `1032 passed`, `1 skipped`,
`3 failed`, and `11 errors`. The three failures are frozen historical
inventory/bundle assertions already inconsistent with current G5.50 authority
and module changes in the pre-existing dirty tree. The eleven errors all share
one historical audit fixture whose pinned architecture-authority hash is stale.
They do not exercise the G5.52 acceptance or sparse-handoff behavior and were
not rewritten under this goal.

Factory-first, closed-world and cross-domain guards remain intact. Generated
Gate 1/Gate 2 bundles were rebuilt from their maintained source owner. No
workspace-only import or fake/mock-only terminal was added.

KISS is preserved: the implementation is one acceptance predicate correction
and one sparse-only Canonical cell handoff in existing owners.

## Stop and next allowed boundary

G5.52 closes the Gate 2 structural defect but stops at the external model
catalog preflight. It does not authorize a substitute model, wrapper call,
Gate 3 prompt patch, manual semantic repair, Gate 4/Gate 5 inference, commit,
push or PR.

The next allowed work is only a controlled continuation of the ordinary
downstream replay after the approved provider model is stably published. If
that replay still lacks currency, the next gap is downstream and must not be
repaired in Gate 2.
