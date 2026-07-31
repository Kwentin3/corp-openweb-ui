# Broker Reports Gate 2 Reconciliation — Decision Brief

Date: 2026-07-30
Decision requested: choose one convergence direction before merging GOAL 17

## Decision

Choose **Option A: evolve the existing source-fact product boundary to Type-First behavior**, while preserving the existing visual-table input, Gate 2 package, segmentation, ArtifactStore, validators, materializer, and AnswerContext.

Do **not** merge Draft PR #232 as-is before this direction is approved. Retarget its useful Type-First pieces into the converged boundary or supersede the draft.

Reserve **Option B** only if the program explicitly establishes that V6 Financial Semantic classification is a different business decision from source-fact typing. Do not retain both routes merely because both already exist.

## What the audit proved

The visual-table path is already implemented:

```text
PDF
→ bounded page/table detection
→ immutable PNG crop
→ Gemini master VLM
→ exact description + rows
→ deterministic semantic envelope and logical table
→ ArtifactStore
→ Gate 2 package
```

The provider receives one crop, not the whole document. It does not create indexes, geometry, canonical facts, or financial meaning. The released profile admits only bounded numeric tables and fails closed on invalid schema, visual uncertainty, missing labels/amounts, review-required output, more than 64 rows, more than four columns, or cells longer than 256 characters.

Historical ArtifactStore evidence proves the complete chain. Current live valves for intake, dual VLM, and semantic downstream are enabled. However, a fresh read-only parity check found all three live Function bundles different from `main`; current repository/live equivalence is therefore not proven.

The presumed old production `source_fact_selection_v2` is actually saved as `broker_reports_source_fact_selection_v3`, and it is no longer product-reachable. It ran historically at `ba1eb134…`; the next-day containment commit `d14bb700…` classified it as regressive. Current `main` hard-wires the source-Pipe guard to `False`, and the current domain runtime no longer imports that selection route. Product extraction currently uses the broader canonical source-facts response plus deterministic validation.

## What the old model really saw

The global nine-type Python enum was not the actual model-visible list.

Across 35 exact saved historical requests:

- 26 schemas exposed only `unknown_source_row`;
- 9 exposed exactly `document_summary_evidence + unknown_source_row`;
- 12 packages proposed `position_snapshot`, but the schema removed it;
- 6 proposed `fee_commission`, but the schema removed it;
- 2 proposed `income`, but the schema removed it.

The capability filter required exact reproducible fields derived from hardcoded header labels and deterministic candidates. The inspected requests exposed one or two fact types, never a broad taxonomy.

No semantic regex or synonym engine formed the type list. The decisive mechanisms were:

- domain routing and allowlists;
- exact hardcoded header-label → field mapping;
- required-field filters;
- source-shape/reproducibility filters;
- dynamic JSON Schema generation.

The exact domain prompts contained type names and generic rules, not rich per-type definitions, negative signals, nearest competitors, or counterexamples. An enum is not a Semantic Pack.

Adding a managed-dictionary term would not automatically expose it. Old code would also require changes to global/domain types, required fields, header/capability mapping, schema generation, Prompt registration, finalizer/materializer/validator branches, tests, generated bundles, and release evidence.

## What GOAL 17 adds

GOAL 17’s useful new work is:

- versioned rich type cards;
- opaque local type keys;
- plural `plausible_types`;
- code-owned empty/multiple/singleton reasons;
- deterministic prebound options and exact unchanged restoration;
- sealed request/mapping receipt;
- exact replay;
- explicit false-singleton comparator counters.

Trace D proves the key limit honestly: when the oracle set has two types but the simulated response returns one type with one matching option, the record still materializes. The comparator records `false_singleton_typed=1` and `unsafe_typed=1`. Exact value restoration prevents value drift; it cannot correct semantic under-classification.

GOAL 17 does not solve visual reading. Its proof uses synthetic benchmark fixtures through `Gate2DeterministicFinancialScopeFromGate1V2Factory`. It does not consume the saved `semantic_visual_logical_table` Gate 2 package. It creates an inactive second semantic path through additive Packet, Choice, Context Linter, Expansion, evidence, and proof orchestration.

## Duplication

The two routes overlap in:

- model-facing type classification;
- bounded type enum/schema;
- parser/Choice;
- code-owned canonical decision;
- value/fact restoration;
- deterministic materialization;
- evidence persistence and replay concerns.

The existing components that should remain single authorities are:

- PDF crop and Gemini transcription;
- semantic envelope/logical projection;
- Gate 2 package and segmentation;
- ArtifactStore;
- provider request/adapter factory;
- canonical source-fact validator/materializer;
- downstream `AnswerContextSelectionFactory`.

`AnswerContextSelectionFactory` is not a Gate 2 financial-input linter. It runs only after a completed Gate 2 run and prepares one interpretation-bearing representation for the subsequent answer model, with other artifacts as provenance-only links.

## Options

### A — preferred

Bring Pack-backed Type-First choice into the existing source-fact owner. Use existing Gate 2 packages as input, deterministically prebind options, expose plural local types, derive reasons in code, restore exact options, and reuse the existing canonical materializer. Keep inactive until same-source and live qualification pass.

Why: fewest lasting owners, maximum reuse of production evidence, no second materializer, best rollback boundary, and preservation of GOAL 17’s real semantic improvements.

### B — reserve

Connect the existing visual/Gate 2 package to the V6 Type-First route with one bounded adapter.

Use only if V6 classification is proven to be a distinct downstream domain. Otherwise this preserves unnecessary parallel orchestration.

### C — reject

Keep only the old product route and close GOAL 17.

This avoids immediate integration but discards rich type cards, plural choice, exact replay, and false-singleton observability.

### D — reject

Keep both.

No distinct-task evidence currently justifies two dictionaries, two model-choice contracts, and two semantic orchestration paths.

## Exactly one next GOAL

**GOAL 19 — Inactive same-source converged Type-First adapter proof.**

Inside the existing source-fact owner, consume an already validated Gate 2 package—including a semantic visual logical table—and produce Type-First cards plus deterministically prebound options. Run the same saved source through the historical reconstruction and new inactive projection; prove exact value restoration, plural-choice and false-singleton counters, privacy-safe replay, and one canonical materializer.

Required counters remain:

- provider calls `0`;
- runtime/product/OpenWebUI changes `0`;
- valves/admissions `0`;
- activation `0`.

Stop after that inactive proof and request a separate activation decision.

## Evidence

Public:

- full GOAL 18 report;
- GOAL 18 safe receipt;
- this brief.

Private ignored review pack:

```text
local/goal18-private/BROKER_REPORTS_GATE2_RECONCILIATION_PRIVATE_EVIDENCE/
```

It contains two exact historical provider chains, two exact simulated GOAL 17 chains, the 35-request schema matrix, and four human-review forms. Historical crop bytes were not available; crop hashes, geometry, exact provider response, logical table, and downstream artifacts were available.
