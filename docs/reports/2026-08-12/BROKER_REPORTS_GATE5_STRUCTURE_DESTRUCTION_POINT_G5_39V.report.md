# GOAL G5.39V — Financial Fact Structure Destruction-point Audit

Date: 2026-08-12
Mode: research-only
Product HEAD: 02659a9b0bdfb2f19171d2a070a660af85119d59
Product HEAD tree: 0a696522eb37eca13bb9224a41f7227823c8ce8c
Issue journal: https://github.com/Kwentin3/corp-openweb-ui/issues/278

## Outcome

G5.39V is complete with terminal finding **CANONICAL_STRUCTURE_LOSS**.

For both distributed real facts, the last representation that still exposes the
human-readable grouping is Stage C, the actual visual/table projection. The
first destructive transition is C → D, where CanonicalArtifact retains page
order and text but loses the table identity, headers, row/cell boundaries, and
column-to-literal bindings needed to close the event. LARGE_REAL_001 also has a
secondary Stage E loss: the three required pages become three independent
Gate 3 chunks.

The row-local holdout survives A → E. This control matters: the finding is not
that CanonicalArtifact always destroys tables, but that the current PDF route
does so for the two distributed target facts in this frozen corpus.

No production code, schema, heuristic, relation strategy, Gate 4+, tax,
declaration, or XML behavior was changed. G5.40 and every dependent GOAL remain
unauthorized.

## Frozen scope and method

The corpus was byte-identical to G5.39:

| Sample | Source SHA-256 | Frozen fact |
|---|---|---|
| DEV_PUBLIC_TBANK | 25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67 | distributed purchase, charge, and holding alignment |
| HOLDOUT_REAL_001 | 79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d | one row-local disposal |
| LARGE_REAL_001 | 7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015 | distributed dividend, withholding, and accrual alignment |
| NEGATIVE_AB_001 | synthetic control | two distinct events that must not be joined |

The oracle was physically separated from runtime input. Its SHA-256 was
d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85.
Exact customer values, excerpts, images, prompts, and provider traces are not
published in Git.

The fact, stages, success criteria, blind evaluation, negative control, and
single-call rule were frozen before inspection. Two superseding
preregistrations record only pre-run corrections:

1. v2 replaced an unavailable/unapproved model with the published and approved
   Gemini 3.5 Flash route.
2. v3 corrected a provider-adapter response-schema seam after v2 failed before
   all seven provider submissions. The representation bytes and facts were not
   changed.

No output was retried, repaired, merged, selected best-of-N, or manually
corrected.

## Actual A → E authority chain

The audit followed the existing owners, not a parallel parser or reader:

1. A — rendered source pages.
2. B — [PdfTextLayerParserFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py)
   plus [PdfVisualMemoryFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/pdf_visual_memory.py).
3. C — the frozen G5.39 semantic visual/table projections, independently
   checked against the rendered pages.
4. D — [CanonicalReaderFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py)
   reading the exact current CanonicalArtifact.
5. E — [Gate3ProjectionFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py)
   followed by
   [Gate3StructuralChunkFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_structural_chunking.py).

The live labeling path remains factory-routed through
[Gate3RoleLabelRuntimeFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_role_labeling.py)
and the existing model client. Nothing in this research bypassed those owners
to claim product behavior.

## Human forensic trace

| Sample | A rendered | B earliest extracted | C visual/table | D canonical | E Gate 3 | First loss |
|---|---:|---:|---:|---:|---:|---|
| DEV_PUBLIC_TBANK | YES | YES | YES | NO | NO | C → D |
| HOLDOUT_REAL_001 | YES | YES | YES | YES | YES | none observed |
| LARGE_REAL_001 | YES | YES, visual unit; layout inventory unavailable | YES | NO | NO | C → D |

### DEV_PUBLIC_TBANK

At A and B, the pages expose a wide trade table, cash-operation rows, a holdings
change, and a security directory. At C, the table/section identities, headers,
rows, shared instrument/date signals, and cross-table alignment make the
purchase/charge/holding grouping reviewable.

D contains five containers and seven nodes: one document, four pages, four text
nodes, three page breaks, and zero table nodes. The canonical JSON is 14,866
characters. E is one 8,036-character chunk. Page order, page text, and literal
presence survive, but the table identities, row/cell boundaries,
column-to-literal bindings, and cross-table alignment do not.

### HOLDOUT_REAL_001

At A through C, the disposal is one row under its table title and header. D
retains one document, six pages, 25 nodes, nine table nodes, 11 text nodes, and
five page breaks. E retains the table structure in one 30,537-character chunk.
The row-local fact therefore remains reviewable through E.

### LARGE_REAL_001

At A, the three source pages expose separate withholding, dividend, and accrual
tables. At C, table identities, headers, row/cell boundaries, and the repeated
instrument/security/date/rate/quantity relationships make the three matching
rows reviewable as one fact despite many similar rows.

The layout inventory subchannel at B stops at its document budget before the
three selected pages, but the actual PdfVisualMemoryFactory returns all three
visual page units. B is therefore YES for the human grouping through the visual
unit, with the structured layout inventory explicitly unavailable.

D contains 66 containers and 129 nodes: one document, 65 pages, 65 text nodes,
64 page breaks, and zero table nodes. The canonical JSON is 344,350 characters.
The table identities, headers, rows/cells, column bindings, and three-page
alignment are gone; page hierarchy, order, text, and literals survive.

E emits 66 actual chunks. The three required pages are separate chunks. The
selected after-context was the single actual page-54 chunk, not a forensic
three-page concatenation. Thus LARGE_REAL_001 has both the primary C → D
canonical structure loss and secondary Gate 3 page-chunk fragmentation.

## Context accounting

Large whole-document model context was not used. Character fractions below
show the actual bounded evidence surface and a post-oracle minimum fact-bearing
measurement. The minimum measurement is diagnostic only; it is not a proved
retrieval method.

| Sample | C whole chars | Reviewed C chars | Reviewed fraction | Minimum fact chars | Minimum fraction | Actual before input tokens | Actual E input tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| DEV_PUBLIC_TBANK | 29,336 | 29,244 | 99.6864% | 20,220 | 68.9256% | 13,501 | 3,854 |
| HOLDOUT_REAL_001 | 224,775 | 107,472 | 47.8131% | 1,736 | 0.7723% | 48,700 | 20,002 |
| LARGE_REAL_001 | 1,022,810 | 48,630 | 4.7545% | 2,794 | 0.2732% | 26,981 | 3,291 |

Additional extraction accounting:

| Sample | B layout | Selected layout chars | Visual units / bytes | C reviewed structure |
|---|---|---:|---:|---|
| DEV_PUBLIC_TBANK | complete | 1,357,039 | 2 / 326,339 | 4 tables, 16 rows, 274 cells |
| HOLDOUT_REAL_001 | complete | 1,418,216 | 1 / 341,332 | 1 table, 74 rows, 1,052 cells |
| LARGE_REAL_001 | partial, budget stop | 2,236 | 3 / 817,378 | 3 tables, 156 rows, 175 cells |

For LARGE_REAL_001, the three relevant actual E chunks contain 2,795, 4,688,
and 3,779 characters. Concatenating them would create an 11,262-character
forensic representation, but that representation is not an actual Gate 3
context and was not used as the after sample.

## One clean blind before/after diagnostic

Provider/model: the published, approved Gemini 3.5 Flash profile.
Calls: exactly seven v3 slots, exactly one provider submission per slot.
Policy: no retry, repair, follow-up correction, best-of-N, or result merge.
Evaluation: oracle applied only after all outputs were frozen.

The abandoned v2 slots produced seven local request-invalid results and zero
provider submissions because the existing Gemini adapter required the
target_alias response field. v3 changed only that response-schema seam. The
same representations were retained.

| Sample/stage | Result | Exact required ref+literal | Required literals | Event check |
|---|---|---:|---:|---|
| DEV before C | INVALID | 2/6 | 2/6 | returned bindings are within the expected event, but incomplete |
| DEV after E | INVALID | 0/6 | 1/6 | not resolvable from returned aliases |
| HOLDOUT before C | PROPOSED_CORRECT | 9/9 | 9/9 | same expected row/event |
| HOLDOUT after E | INVALID | 0/9 | 1/9 | not resolvable from returned aliases |
| LARGE before C | INVALID | 5/9 | 6/9 | returned bindings are within the expected event, but incomplete |
| LARGE after E | INVALID | 0/9 | 0/9 | selected a different row |
| negative A/B at C | UNRESOLVED | 0/6 | 0/6 | abstained; no false join |

Five outputs used a status outside the frozen canonical enum after ten
provider-schema transformations. They are INVALID and would fail closed under
canonical runtime validation. They were not repaired or rerun.

This diagnostic supports neither an LLM grouping authority nor an activation
candidate. It gives one clean positive on the row-local before sample, partial
same-event recovery on both distributed before samples, degradation after E,
and a safe abstention on the negative sample. The causal destruction-point
finding comes from the deterministic A → E structure trace, not from treating
these proposals as truth.

## Verdict table

| Question | Verdict | Evidence |
|---|---|---|
| Does the human-readable distributed grouping survive A → C? | YES on both distributed samples | rendered-page and exact visual/table review |
| Is the first loss C → D? | YES on both distributed samples | C has table/row/cell/header structure; D has zero table nodes |
| Does row-local structure survive? | YES on the holdout | nine canonical table nodes and one actual Gate 3 table-bearing chunk |
| Is there additional E loss? | YES for LARGE_REAL_001 | three required pages become independent chunks |
| Do tables/headers/rows/cells materially preserve the needed grouping? | SUPPORTED_ON_BOUNDED_CORPUS | distributed and row-local controls retain grouping at C |
| Is blind LLM event grouping reliable? | NOT_PROVEN | only the row-local before sample is fully correct; distributed outputs are incomplete/invalid |

## Existing map → region by ref

The existing CanonicalReader can resolve container and table references. That
is sufficient for HOLDOUT_REAL_001 because D actually contains table nodes.
For DEV_PUBLIC_TBANK and LARGE_REAL_001, D exposes only page/text references;
there is no retained reference from D/E back to the rich Stage C table regions,
and no existing composite selector joins the required tables/pages. Therefore:

- direct ref → canonical container/table lookup: available;
- ref → rich Stage C region for the two distributed facts: unavailable;
- exact composite event region from existing refs alone: not demonstrated.

No new retrieval mechanism was designed or implemented.

## Narrow next research question

Given the same frozen C regions plus only an existing accepted target alias
(no oracle role rows or values), can a provider/profile that preserves the
canonical response schema recover all distributed DEV and LARGE roles with
exact refs while the A/B negative sample remains non-mixed?

This is a question, not authorization. No next GOAL is opened by this report.

## Verification, privacy, and KISS

- Existing model-client and bounded-labeling tests: 40 passed in 2.88s.
- Existing projection, structural-chunking, and role-labeling tests: 25 passed
  in 4.52s.
- Exact private trace SHA-256:
  18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766.
- Exact private evaluation SHA-256:
  8936763a5d5dcf666cc331801d806a70bbd277e353dd5e9fe7c398430b245587.
- Frozen v3 probe aggregate SHA-256:
  210a282bc05593d967aba4db1e3e556ce5d5885d97a796e5314371a265f3e0d9.
- Safe evaluation SHA-256:
  b4abe8d1bc3c3971045403abf1ba3975ff75b6d9050ee2c39681e40bc0ae0f55.
- Exact source/oracle evidence remains ignored and outside Git.
- Research code is removed at closeout; only safe reports remain in the
  product checkout.
- KISS: one existing parser/visual owner, one canonical reader, one Gate 3
  projection/chunk route, one clean probe per frozen slot, and no new
  production abstraction.

## Limitations

The verdict is bounded to the four frozen samples and current exact artifacts.
The LARGE layout subchannel did not process the selected pages, so its B-stage
YES is specifically the production visual-memory unit, not a claim about
layout inventory completeness. The Stage C minimum fragments are
post-adjudication measurements, not an available production selector.

The dirty product worktree predated G5.39V and was not normalized. This GOAL
adds only safe report artifacts and the requested issue-journal entry; it does
not stage, commit, push, open a PR, or modify the pre-existing changes.
