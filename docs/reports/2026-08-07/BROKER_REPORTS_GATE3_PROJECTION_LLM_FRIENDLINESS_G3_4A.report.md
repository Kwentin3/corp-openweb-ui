# Broker Reports Gate 3 — G3.4A Projection LLM-friendliness audit

Status: `COMPLETED`

Date: 2026-08-07

## 1. Verdict

`Gate3ProjectionV1` is LLM-friendly as a **representation**, but not as a
bounded one-shot context for the full real corpus.

It is format-neutral Markdown, readable, deterministic and reversibly
addressable without exposing backend canonical IDs to the model. That is why
G3.2 was reasonably called LLM-friendly. The name must not be read as
“token-small”: the current factory renders the whole active document, including
table scaffolding plus row- and cell-level aliases, into one model message.

```text
ONE_SHOT = VIABLE_ONLY_FOR_SMALL_DOCUMENTS
G3_2_PROJECTION_FITNESS = FORMAT_FRIENDLY_NOT_CONTEXT_BOUNDED
```

## 2. Exact audited route

The implementation and frozen evidence agree on one route:

```text
CanonicalArtifactV1
-> CanonicalReaderFactory.create
-> Gate3ProjectionFactory.create
-> exact published dictionary rendering
-> one minimal instruction
-> existing structured request builder/provider adapter
-> final provider request
```

The projection factory reads through the sole canonical reader
([factory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py#L35));
the G3.4 composer loads the exact projection/dictionary/schema and performs one
request audit
([composer](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py#L104),
[request composition](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py#L211)).

No direct SQLite/component read was used to construct the REPO projection. The
audit created no provider call and the 174-file, 109,059,448-byte store tree had
the same path/size/SHA-256 snapshot before and after.

## 3. Exact request decomposition

Counts below are exact characters, UTF-8 bytes and `splitlines` counts from the
two actually sent frozen requests. Provider tokens are reported only for the
whole request; no per-component tokenizer estimate is presented as fact.

| Part | Compact chars / bytes / lines | Large chars / bytes / lines |
| --- | ---: | ---: |
| instruction | 356 / 576 / 1 | 356 / 576 / 1 |
| dictionary | 3,670 / 5,631 / 172 | 3,670 / 5,631 / 172 |
| projection | 15,042 / 18,773 / 158 | 318,684 / 376,214 / 1,261 |
| response schema, compact JSON | 710 / 710 / 1 | 710 / 710 / 1 |
| provider wrapper and other, compact JSON | 173 / 173 / 1 | 173 / 173 / 1 |
| exact final request, compact JSON | 20,305 / 26,217 / 1 | 325,064 / 384,775 / 1 |
| provider-reported input tokens | **10,386** | **215,810** |
| provider duration | 14,031 ms | 136,968 ms |

JSON escaping makes the exact wire contribution of a string slightly larger
than its raw character count. In the large request, projection contribution is
319,979 of 325,064 compact-JSON characters (98.44%); dictionary is 1.18%, schema
0.22%, instruction 0.11%, wrapper/other 0.05%.

Instruction, dictionary, provider schema and wrapper are byte-identical between
the requests. The exact deltas are therefore 303,642 projection characters and
205,424 provider-reported input tokens. This isolates the document projection
as the scale driver without inventing token counts for individual parts.

The complete safe accounting is in
[01_context_breakdown.safe.json](../../../docs/stage2/research/g3_4a/01_context_breakdown.safe.json).

## 4. Compression matrix

| Shape | Canonical JSON chars | Projection chars | Aliases | Projection without alias markup | Final request chars | Actual input tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| compact HTML | 164,389 | 15,042 | 612 | 11,370 | 20,305 | 10,386 |
| large CSV | 3,691,196 | 318,684 | 14,118 | 216,738 | 325,064 | 215,810 |
| REPO XLSX | 42,575,234 | 3,884,393 | 182,497 | 2,352,917 | N/A | N/A — not sent |

The projection is only 8.6–9.2% of canonical JSON, so it is genuinely a useful
consumer projection. Nevertheless, REPO remains 3.88 million characters and
29,687 lines. Compression relative to a storage artifact is not the same as a
bounded LLM request.

Exact CSV evidence is in
[08_projection_size_matrix.safe.csv](../../../docs/stage2/research/g3_4a/08_projection_size_matrix.safe.csv).

## 5. Schema and request duplication

The frozen provider response format is 710 compact-JSON characters. It declares
the fields `target_alias` and `financial_label`, but contains:

- zero concrete aliases and no alias enum;
- zero values from the nine-label dictionary;
- zero canonical target mappings;
- zero document IDs or document values.

The dictionary appears once, projection appears once, hidden history is absent,
and backend mappings are not model-visible. Therefore:

```text
SCHEMA_DUPLICATION = NOT_FOUND
STRUCTURAL_DUPLICATION = NO_REQUEST_LEVEL_CONTENT_DUPLICATION
```

The frozen schema's empty `schema_version` property caused the known G3.4
validation failures, but is unrelated to request size. See
[05_provider_schema_exact.safe.json](../../../docs/stage2/research/g3_4a/05_provider_schema_exact.safe.json).

## 6. Alias and table expansion

The renderer deliberately issues a row alias for every row with cells and a
cell alias for every actual cell
([table renderer](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py#L232),
[row alias](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py#L288),
[cell alias](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py#L307)).

| Shape | Row aliases | Cell aliases | Alias share of projection | Explicit empty aliased cells |
| --- | ---: | ---: | ---: | ---: |
| compact HTML | 63 | 533 | 24.4% | 71 |
| large CSV | 1,255 | 12,863 | 32.0% | 922 |
| REPO XLSX | 29,145 | 153,352 | 39.4% | 39,499 |

This is a real alias explosion, but not the sole root. Removing all alias
markup would still leave 216,738 characters for the CSV and 2,352,917 for
REPO. The remainder is visible values, Markdown escaping, rectangular grid,
coordinate headings and row/column separators.

Both row and cell targets are practically used: the rejected frozen large
proposal addressed 269 rows and 96 cells; the compact proposal addressed three
cells. Those responses are not accepted financial semantics, but they disprove
the claim that either granularity is unused. Broad row-only or cell-only
compression is not safe without changing the targeting contract.

Exact aggregate inventory and table shapes are in
[06_alias_inventory.safe.csv](../../../docs/stage2/research/g3_4a/06_alias_inventory.safe.csv)
and [07_table_expansion_examples.safe.md](../../../docs/stage2/research/g3_4a/07_table_expansion_examples.safe.md).

## 7. Human audit

- Compact HTML (15,042 chars, 158 lines): readable as a whole; 12 small tables
  remain navigable.
- Large CSV (318,684 chars): structurally understandable, but the single
  1,255-row table is not a practical whole-document review unit and consumed
  215,810 input tokens.
- REPO XLSX (3,884,393 chars): deterministic and inspectable in a file, but not
  realistically human- or one-shot-model-friendly as one context. It was never
  sent, so no token or provider-limit claim is made.

Thus the exact scale failure is at the **full-document one-shot boundary**, not
at canonical fidelity or schema strictness.

## 8. Earlier supplied information

The earlier managed financial skill and prompt do contain one useful design
idea that should not be lost: decide over the complete **bounded source
context**, not an isolated label, and prepare one deterministic financial
fragment per decision. That supports partitioning on existing table/section
boundaries while carrying the full local header and notes.

The broader early JSON/declaration extraction drafts are not reused here. They
own different schemas, readiness stages and methodology questions, so importing
them would create a parallel workflow and more prompt context. They do not
improve the current nine-label dictionary, which remains the more precise and
convenient authority for G3.4.

This assessment is recorded in
[09_structural_redundancy_findings.md](../../../docs/stage2/research/g3_4a/09_structural_redundancy_findings.md).

## 9. Reduction classification

### A — safe structural candidate

Research omission of aliases for physically present but display-empty cells,
while keeping their blank rendered coordinates. Measured maximum markup saving:
426 chars compact (2.8%), 6,465 chars CSV (2.0%), 313,431 chars REPO (8.1%). No
frozen proposal targeted an empty cell. This still needs a target-contract proof
before implementation and does not solve scale alone.

### B — semantic filtering, research only

Selecting rows by income/tax/fee keywords, discarding positions or totals, or
using label-family hints could reduce size, but can remove counterexamples,
footnotes and cross-row meaning. No such runtime filtering is recommended.

### C — document partitioning

Use existing canonical table/section boundaries first. Only when a single table
is still oversized, use contiguous row groups with exact header and local notes.
This is structural partitioning, not semantic selection.

### D — unsafe/information loss

Dropping repeated rows, totals, headers or notes; arbitrary token windows;
removing all row or all cell aliases; replacing the exact dictionary with older
broad prompts.

## 10. Minimal next design options

No more than three options are justified:

1. **Existing table/section partition** — recommended first. REPO has 20 tables;
   the maximum measured table alias span is 335,496 chars versus 3,884,393 for
   the whole projection. This is a strong reduction signal, not an exact future
   request measurement.
2. **Contiguous row groups for one oversized table** — only when option 1 cannot
   bound a single table, as with the large one-table CSV under a stricter budget.
3. **Empty-cell alias hygiene** — small complementary saving, never a substitute
   for partitioning.

Owners remain unchanged: one canonical reader, one renderer/alias issuer, one
dictionary, one provider route. Details and risks are in
[10_design_options.md](../../../docs/stage2/research/g3_4a/10_design_options.md).

## 11. Evidence, limits and stop

The private bundle outside Git contains numbered exact context breakdown,
compact input, large input, REPO projection, provider schema, alias inventory,
table excerpts, size matrix, findings and options. Exact model inputs and
customer values are not copied into Git. The safe hash/size ledger is
[PRIVATE_EVIDENCE_MANIFEST_G3_4A.safe.json](../../../docs/stage2/research/g3_4a/PRIVATE_EVIDENCE_MANIFEST_G3_4A.safe.json),
and the safe terminal receipt is
[the G3.4A receipt](BROKER_REPORTS_GATE3_PROJECTION_LLM_FRIENDLINESS_G3_4A.receipt.safe.json).

Limits:

- two exact provider requests, not a provider-wide tokenizer benchmark;
- one additional exact REPO projection, never sent;
- no exact measurement of a future partitioned request;
- rejected raw proposals used only for addressing-shape diagnostics;
- no provider limit, price or maximum-context claim;
- no runtime, schema, dictionary, renderer, adapter or workflow change.

## 12. Final status

```text
GOAL_G3_4A = COMPLETED
EXACT_CONTEXT_AUDIT = PASSED_2_SENT_REQUESTS_1_UNSENT_EXACT_PROJECTION
ROOT_CAUSE = FULL_DOCUMENT_ONE_SHOT_TABLE_GRANULARITY_PLUS_DENSE_ROW_CELL_ADDRESSING_AND_MARKDOWN_SCAFFOLDING
LARGEST_CONTEXT_CONTRIBUTORS = PROJECTION_98_44_PERCENT_OF_LARGE_REQUEST; ALIAS_MARKUP_31_99_PERCENT_OF_LARGE_PROJECTION_AND_39_43_PERCENT_OF_REPO
STRUCTURAL_DUPLICATION = NO_REQUEST_LEVEL_CONTENT_DUPLICATION; ROW_PLUS_CELL_ADDRESSABILITY_AND_GRID_SCAFFOLDING_CONFIRMED
SCHEMA_DUPLICATION = NOT_FOUND_710_CHARS_ZERO_ALIAS_LABEL_MAPPING_OR_DOCUMENT_VALUES
ALIAS_EXPLOSION = CONFIRMED_MATERIAL_BUT_NOT_SOLE_ROOT
ONE_SHOT = VIABLE_ONLY_FOR_SMALL_DOCUMENTS
G3_2_PROJECTION_FITNESS = FORMAT_FRIENDLY_NOT_CONTEXT_BOUNDED
SAFE_STRUCTURAL_REDUCTIONS = EMPTY_DISPLAY_CELL_ALIAS_SUPPRESSION_CANDIDATE_ONLY_CONTRACT_PROOF_REQUIRED
SEMANTIC_FILTERING_IDEAS = RESEARCH_ONLY_NOT_RECOMMENDED_FOR_RUNTIME
MINIMAL_NEXT_OPTIONS = EXISTING_TABLE_SECTION_PARTITION; CONTIGUOUS_ROW_GROUPS_FOR_OVERSIZED_TABLE; EMPTY_CELL_ALIAS_HYGIENE
KISS_CHECK = PASSED_REUSE_CURRENT_OWNERS_NO_SECOND_RENDERER_SCHEMA_DICTIONARY_OR_DOMAIN
NEXT_STEP_RECOMMENDATION = REVIEW_ONLY
```

G3.4A stops here. No implementation or dependent Gate 3 goal was started.
