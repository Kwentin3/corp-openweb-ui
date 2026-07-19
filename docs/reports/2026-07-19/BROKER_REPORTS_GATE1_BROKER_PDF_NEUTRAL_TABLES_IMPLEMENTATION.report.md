# Broker Reports Gate 1 — Broker PDF Neutral Tables v1

Date: 2026-07-19

Profile: `supported_broker_pdf_neutral_table_profile_v1`

Engineering status: `NOT_CLOSED`

## Outcome

The maintained pipeline now reconstructs and deterministically validates all 14 material broker-PDF regions in the accepted private corpus. They produce 14 physical canonical projections, 12 logical tables, and two validated two-page continuations. Gate 2 receives 14 new table packages through persisted typed refs; the other 180 withholding-PDF candidates remain blocked as required.

The goal is nevertheless not closed. No genuine previously unseen positive PDF from the same intended broker template/family was available. Synthetic reconstruction, a copy of the tuning document, and another broker's layout are not acceptable substitutes. No stage deployment or repository/live parity claim was made before that mandatory proof.

## Previous promotion gaps

The v0 projection validator established internal JSON shape, ref uniqueness, and geometry coverage. It did not establish a canonical header hierarchy, exact ordered leaf grid, structural totals, continuation identity, explicit merged-cell spans, complete selected-object ownership with controlled aliases, or a canonical integrity hash. Therefore `high` meant good geometry, not canonical truth.

The safe characterization register is:

| Opaque region | Previous result | Exact promotion gap | v1 result |
| --- | --- | --- | --- |
| `candidate_ad500e570b33c9d64b57` | high | Geometry-only projection; no canonical header/total/ownership authority | `canonical_table_accepted` |
| `candidate_833226bcd3febb379282` | high | Geometry-only projection; continuation was not a shared logical-table contract | `canonical_table_accepted` |
| `candidate_b681cb1056e55ae1067d` | high | Geometry-only projection; no deterministic header hierarchy and total inventory | `canonical_table_accepted` |
| `candidate_3406c5f4c0316c2845dd` | high | Geometry-only projection; canonical source membership was not proven | `canonical_table_accepted` |
| `candidate_3fd179a45b4e47467353` | high | Geometry-only projection; ordered canonical columns were not an enforced contract | `canonical_table_accepted` |
| `candidate_8158679be44d537eeddc` | high | Geometry-only projection; merged/layout rows and totals lacked v1 validation | `canonical_table_accepted` |
| `candidate_1e13c841402648d91321` | low | Non-uniform row widths from spanning headers; leaf-column ownership unresolved | `canonical_table_accepted` |
| `candidate_0a78b2f1bbc1e0149eb2` | low | Non-uniform header/data cell counts; header-to-column mapping unresolved | `canonical_table_accepted` |
| `candidate_e1b7d8494de003b9240e` | low | Headerless next-page fragment was not proven as one ordered continuation | `canonical_table_accepted` |
| `candidate_abe9e162c870cf91a929` | blocked | Full-width merged section/total rows defeated uniform-column inference | `canonical_table_accepted` |
| `candidate_2de199d238143454ec69` | blocked | Wide multi-row header and merged rows lacked an ordered leaf grid | `canonical_table_accepted` |
| `candidate_aec114c055952fed4403` | blocked | Headerless next-page fragment and final totals lacked continuation authority | `canonical_table_accepted` |
| `candidate_fa3c0a83359bd78f69be` | blocked | Merged rows hid the 11-column leaf grid from the v0 heuristic | `canonical_table_accepted` |
| `candidate_0a78ef663d9008314db5` | blocked | Merged rows hid the 8-column leaf grid from the v0 heuristic | `canonical_table_accepted` |

No existing v0 projection was directly promoted. All nine were replaced by v1 projections produced from original text/layout memory; all five unresolved regions used the same reconstruction path.

## Implementation

The new `BrokerPdfNeutralTableFactory` is called only by `NormalizedTableProjectionFactory`. It derives a leaf grid from ruled-cell coordinates, maps every cell edge to that grid, records spans explicitly, recognizes the complete ordinal marker row, assigns structural row roles, and joins only an unambiguous adjacent-page fragment with the same normalized column boundaries.

Selection is document-structural and fail-closed. The code has no filename, path, customer, document/region/artifact ID, hash, extracted-value, or page exception allowlist. All 24 other actual-corpus documents containing PDF table candidates received zero v1 promotions.

The canonical validator now checks:

- projection/contract identity and source document, page, region, parent, and checksum lineage;
- exact row, column, cell, ordinal, span, and merged-cell inventories;
- header nodes and one-to-one header-to-column mapping;
- total/subtotal inventory and non-clipped final rows;
- continuation count, page order, root relation, shared grid, and inherited header;
- every selected source object, explicit line alias, source-value index, and checksum;
- empty versus non-empty cells and unresolved ambiguity;
- neutral reconstruction method, no model authority, empty uncertainty ledger, and complete integrity hash.

Gate 2 automatically selects only persisted validated PDF canonical projections. Each replaces its matching noncanonical source-unit anchor. Native table-selection behavior is unchanged unless the existing opt-in remains enabled. Geometry-only PDF projections still fail with `gate2_pdf_canonical_table_not_validated`.

The versioned contract is [BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.md](../../contracts/BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.md). Machine-readable evidence is [BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.safe.json](BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.safe.json).

## Actual-corpus proof

The full maintained normalizer was replayed into a new private append-only proof root. Its base acceptance result passed for 104 source documents with no failed checks. Private source values, filenames, paths, crops, and coordinates remain outside Git.

For the affected broker document:

- physical regions: 14/14 `canonical_table_accepted`;
- logical tables: 12;
- continued logical tables: 2;
- rows: 201;
- cells: 2,037;
- source-value refs: 2,984;
- source accounting: complete for every region;
- deterministic validators passed: 14/14;
- repeated reconstruction: 1.514 s and 1.535 s;
- validator for all regions: 0.471 s;
- repeated canonical bytes: identical;
- persisted versus replayed canonical bytes: identical;
- ArtifactStore before/after read-only proof: unchanged.

The full-corpus Gate 1 normalization was much more expensive: approximately 1,304 s observed wall time and 4,995,956,736 bytes observed peak RSS. Read-only isolation showed that v1 reconstruction itself is about 1.5 s for the affected document; provider/LLM calls were zero. The long full replay is existing source parsing and memory construction, not model latency and not a reason to add a timeout.

Technical comparison of original pages, text/layout memory, canonical topology, headers, totals, continuations, and source ownership was performed as `agent_operated_technical_review`. It is not customer acceptance.

## Holdouts

The negative holdout was a previously unused public broker-report sample embedded in an official materially different-layout PDF. The maintained FullSource path preserved complete source memory, found no v1 candidate region, and produced zero canonical promotions. Extraction took 37.776 s; projection took less than 1 ms; provider calls were zero. This is the expected fail-closed result.

The positive holdout result is `NOT_RUN`: no genuine unseen PDF from the same intended family was found in the accepted source roots, the wider local PDF inventory, or public-source search. The negative document and synthetic test PDFs cannot prove generalization within the intended family.

## Gate 2 accounting and performance

The corrected full-corpus reconciliation is exact:

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Packages | 667 | 681 | +14 |
| Canonical PDF packages | 0 | 14 | +14 |
| Blocked noncanonical PDF candidates | 194 | 180 | -14 |
| Fully validated table projections | 0 | 14 | +14 |
| Duplicate package IDs | 0 | 0 | 0 |
| Provider calls | 0 | 0 | 0 |

All 180 withholding-PDF candidates, 67 visual-consumer restrictions, and unrelated document-memory errors retained their prior terminal handling. The overall readiness report remains partial because of 29 pre-existing out-of-scope document errors; this task does not relabel them as solved.

On the same host with warm OS cache, the after contour took 53.147 s. Against the maintained 50.824 s reference this is about 1.046x, below the 1.25x guard (63.53 s). The 14 projections added approximately 0.994 s of projection validation and 0.575 s of package construction. Provider latency, tokens, retries, and estimated cost were all zero. ArtifactStore was unchanged.

Batch-index regression tests bound source-index traversal to a constant number of whole-index passes. There is no per-ref full-index scan, package truncation, timeout, concurrency concealment, or persistent cross-run cache.

## Tests and bundles

New tests cover canonical schema and integrity, source loss/duplication/checksum drift, parent/page membership, clipped row, missing total, reordered columns, header mismatch, merged-cell ambiguity, continuation order, ordinal header misclassification, non-table typed decisions, malformed detector authority, unsupported layout, deterministic model-free packaging, and bounded source-index passes.

Existing ArtifactResolver tests retain access-context, retention/purge, and source-deletion coverage. The full maintained service suite passed: 923 tests, zero failures (five dependency deprecation warnings). All three affected autonomous bundles were rebuilt from source. They were not deployed because the mandatory positive-holdout precondition is unresolved.

## Remaining out-of-profile debt

This implementation does not change the 180 paired withholding-PDF candidates, 67 unavailable visual-consumer units in the measured Gate 2 contour, XML semantics, OCR/VLM consumers, financial extraction, or the 29 unrelated readiness errors.

The narrowest remaining work is:

1. Obtain one genuine previously unseen PDF from the same intended broker template/family without changing the frozen rules.
2. Run the maintained path twice and perform original-to-canonical technical comparison of headers, rows, columns, totals, continuations, annotations, and source coverage.
3. If it passes, rebuild from the unchanged sources, deploy through maintained update scripts, re-read live functions/prompts, run safe stage smoke, and prove repository/live hashes and clean pushed Git state.

Until then, the exact unresolved acceptance item is `positive_unseen_same_family_holdout`; the failed invariant is evidence of generalization beyond the tuning document. Actual-corpus canonicalization itself has no unresolved region.
