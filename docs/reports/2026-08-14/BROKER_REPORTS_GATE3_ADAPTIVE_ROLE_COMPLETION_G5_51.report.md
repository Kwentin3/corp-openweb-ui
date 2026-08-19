# Broker Reports G5.51 — Adaptive Context & Role Completion

Date: `2026-08-14`

Status: `PARTIAL_PROOF_FAIL_CLOSED`

## Outcome

The adaptive Gate 3 path is working as designed for both compact and large
documents. One real `SECURITY_DISPOSAL` target was traced through the existing
source -> Canonical -> structural chunk -> type pass -> role pass -> validator
-> Gate 4 boundary. The target already has exact values for `date`, `asset`,
`quantity`, `amount` and optional `unit_price`; only `currency` is missing.

No safe Gate 3 fix exists for this target. The exact accepted Canonical target
is a coarse multi-event `TEXT` region rather than a table row or cell. A
currency symbol exists elsewhere in the visual region, but the Canonical
artifact exposes no deterministic relation from that symbol to the selected
disposal event. Importing it through proximity, page membership or another
field would invent the forbidden transaction relation.

Proven terminal:

- `ADAPTIVE_CONTEXT_PIPELINE_PROVEN`.

Localized blocker:

- `ROLE_COMPLETION_BLOCKER_LOCALIZED=UPSTREAM_DOCUMENT_TO_CANONICAL_PDF_TABLE_PROJECTION/pdf_table_projection_terminal_fallback_text/no_exact_row_or_cell_target_identity`.

Not proven:

- `ONE_REAL_ROLE_PACK_COMPLETE_FACT_PROVEN`;
- `GATE3_ROLE_COMPLETION_PATH_PROVEN`.

## Context bootstrap

- Domain: current Gate 3 structural context and source-bound role labeling.
- Normative authority: Gate 3 Role Labeling v1 and the architecture map.
- Sole runtime owner: `Gate3ChunkBatchLabelingFactory.create`.
- Consumers: `FinancialAnnotationsV2`, then the official Gate 4 runtime.
- Compatibility/generated paths were not changed.
- Exact planned change was conditional on a proven Gate 3 loss point.
- The trace proved no Gate 3 loss point, so runtime and contracts remain exact.
- No second reader, projection, validator, dictionary or role authority was added.

## Exact target trace

The safe alias `security_disposal_target_1` replaces all private document,
artifact, source and target identifiers. No source literal or customer value is
published.

| Layer | Observed result |
| --- | --- |
| source | a visual multi-event securities table region contains currency notation, but not an exact event-bound currency target |
| Canonical | one `TEXT` node, 1,765 characters and 64 lines; no table-row/cell targets and no currency code in the accepted node |
| adaptive context | large-document `structural_blocks`; selected chunk 1 of 2, 51,874 characters and 27 targets |
| type pass | existing accepted `SECURITY_DISPOSAL` fact on the exact Canonical node |
| role context | 1,870 characters, exactly 1 bindable target, 26 chunk targets excluded, 0 structural sources |
| role pass | `date`, `asset`, `quantity`, `amount`, `unit_price` are exact values; `currency` remains missing |
| validator | accepts only literal source-bound values and does not infer or repair the missing role |
| Gate 4 | fact remains `role_incomplete`; no new materialization or persistence was attempted |

The adaptive context did not truncate the accepted target, switch targets or
lose a previously bindable currency value. The missing relation is already
absent at the Canonical target boundary.

## Corroborating purchase trace

The exact G5.48 large-document chunk is 58,149 characters with 40 targets. Its
six incomplete `SECURITY_PURCHASE` targets are also coarse `TEXT` regions and
all required roles remain missing. The inspected exact fallback unit has 58
fallback text references, 0 rows and 0 cells. Its safe reason codes are:

- `geometry_only_non_semantic_candidate`;
- `ruling_line_grid_detected`.

The corresponding Canonical issue is
`pdf_table_projection_terminal_fallback_text`. Re-labeling one purchase inside
that multi-event region would require Gate 3 to reconstruct transaction
identity, which this goal expressly forbids.

## Adaptive mode proof

A read-only inventory of four active real documents found:

- 2 compact documents emitted exactly one `whole_document` chunk;
- 2 large documents emitted structural chunks (4 and 2 respectively);
- the selected real target used the large-document path and never used a
  whole-document model call.

The maintained threshold remains `60,000` characters. No threshold, splitter,
prompt or context owner was changed.

## Live preflight and irreversible boundary

One authorized live attempt stopped before provider transport with
`model_not_published`. The authenticated published inventory had no model that
matched the approved Google profile. Provider submissions, retries, repairs,
fallbacks and store mutations were all `0`; no private evidence directory or
safe diagnosis receipt was created by the aborted script.

The irreversible boundary for this goal was persistence of a new
`FinancialAnnotationsV2` result and its downstream Gate 4 materialization. It
was not crossed: persisting a currency inferred from another line would turn
an unproven relation into canonical financial evidence. Consequently no Gate 4
or Gate 5 replay was run.

## Verification and guardrails

Focused behavioral regression is green: `86 passed` across structural
chunking, bounded type labeling, role labeling, chunk-batch orchestration,
Gate 4 contract, Gate 5 Evidence Demand, cross-gate architecture and generated
bundle parity.

The expanded relevant service regression is also green: `716 passed` across
66 Gate 3-5, Canonical pipeline, semantic-table, architecture, atomic-release
and bundle test files. An initial identical run was stopped by the command
runner at 123 seconds without an assertion summary; the completed rerun used a
sufficient timeout and is the reported result. The five warnings are external
SWIG deprecation warnings.

Factory routing remains:

`Gate3ChunkBatchLabelingFactory.create` -> `Gate3StructuralChunkFactory.create`
-> `Gate3BoundedLabelingFactory.create_from_chunk` ->
`Gate3RoleLabelingFactory.create_from_accepted_facts`.

The existing tests prove that non-accepted chunk targets are removed from role
context and that a role target outside the accepted fact closure fails closed.
No mock-only success, snapshot-only claim or workspace-only dependency was
introduced.

KISS is preserved: no prompt synonym, regex vocabulary, broker rule, retry,
best-of-N selection, post-model repair, relation heuristic, second reader or
new abstraction was added.

## Stop and next allowed boundary

G5.51 ends at the authorized strategic stop. It does not authorize a prompt
tweak, full-document rerun, unsafe role persistence, Gate 4/Gate 5 replay,
activation, commit, push or PR.

The next allowed goal, only if explicitly authorized, is a narrow upstream
document-to-Canonical preservation slice for this exact table class: expose a
deterministically source-bound row/cell target or prove that the source cannot
support one. It must not become a new semantic reader or general table-parser
epic.
