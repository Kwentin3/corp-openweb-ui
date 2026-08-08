# Broker Reports Gate 3 Structural Bounded Context Chunking - G3.4B

Date: 2026-08-07

Status: `COMPLETED`

Runtime status: `IMPLEMENTED_INACTIVE`

## Outcome

One active canonical document can now be transformed deterministically into an
ordered set of bounded structural contexts without financial logic, a second
renderer, a second alias owner, persistence or provider execution.

The implementation reuses this exact authority chain:

```text
CanonicalReaderFactory.create
-> Gate3ProjectionFactory exact render plan
-> Gate3StructuralChunkFactory.create
-> ordered non-persisted Gate3StructuralChunkSetV1
```

The default bound is 60,000 Python characters in the final chunk
`model_view.content`, including context. This is a deterministic pre-provider
bound, not a token estimate.

## Representative real-corpus results

| Shape | Old projection | Old aliases | Historical full-request input tokens | Chunks | Chunk chars min / median / max | Targets min / median / max | Maximum one-request reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| compact HTML | 15,042 | 612 | 10,386 | 1 | 15,042 / 15,042 / 15,042 | 612 / 612 / 612 | 0 (0.000000%) |
| large one-table CSV | 318,684 | 14,118 | 215,810 | 6 | 21,738 / 59,889 / 59,992 | 290 / 2,788.5 / 3,081 | 258,692 chars (81.175083%) |
| REPO XLSX | 3,884,393 | 182,497 | not sent | 76 | 825 / 59,923.5 / 59,999 | 25 / 2,542 / 4,980 | 3,824,394 chars (98.455383%) |

The token values are reused from the earlier G3.4A frozen one-shot proof. They
are provider-reported totals for the complete historical requests, not
projection-only counts and not estimates for these chunks. G3.4B made zero new
provider calls and makes no future token claim. This earlier evidence remains
valuable because it proves why bounded partitioning is necessary; it is not
used as chunk-boundary logic.

The compact projection remained byte-for-byte the same one-chunk model view.
The CSV became six contiguous whole-row groups. REPO partitioned by table
first: 4 target-bearing tables fit whole and 15 oversized tables became 72 row
groups. Twenty alias-free structural units (19 sheet breaks and one empty
table) were retained as context on the next target-bearing table, rather than
becoming empty working requests.

## Coverage and order

| Shape | Eligible | Working | Lost | Duplicated working | Context-only aliases | Row overlap | Order |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| compact HTML | 612 | 612 | 0 | 0 | 0 | 0 | preserved |
| large CSV | 14,118 | 14,118 | 0 | 0 | 0 | 0 | preserved |
| REPO XLSX | 182,497 | 182,497 | 0 | 0 | 0 | 0 | preserved |

Every visible G3.2 target alias maps to the same canonical target in exactly
one working chunk. Context copies have aliases stripped. Row-split tables are
validated for consecutive one-based ranges without gaps or overlap. Each call
binds every chunk to one input document and the same active canonical version;
the two-document behavior test proves that identities do not cross documents.

## Context envelope review

For oversized tables, each row group contains existing structural context:
ancestor headings, table heading, generic Markdown grid headings, the canonical
header row on later groups, and structurally attached notes when present. No
relationship is inferred when the canonical structure does not attach it.

Exact private first/middle/last and adjacent-boundary chunks were inspected for
the CSV and workbook cases. Boundary rows were not bare: both sides retained
their table/grid context and the next chunk began with the next canonical row
range. The privacy-safe synthetic examples in
`docs/stage2/research/g3_4b/04_context_envelope_examples.safe.md` make the
envelope and target/context separation visible without customer values.

Measured context-envelope characters total 0 for compact HTML, 2,897 for the
CSV and 21,523 for REPO. The net increase over the original projection is
respectively 0, 2,563 and 17,511 characters. The latter is the conservative
combined cost of wrappers plus repeated structural context; it is not presented
as a tokenizer or provider cost.

## Implementation boundary

`Gate3ProjectionFactory` now exposes one package-internal render plan produced
by the same render pass as the public G3.2 projection. Public G3.2 bytes and
target mappings remain unchanged. `Gate3StructuralChunkFactory` only chooses
structural boundaries and ordered subsets of those existing mappings.

The closed chunk schema is reusable by later code but is not an ArtifactStore
type. There is no CLI, workflow, OpenWebUI route, batch runner, retry, merge,
provider, annotation persistence or product activation.

If a single indivisible row/block plus its required context exceeds the bound,
the factory fails closed with
`gate3_structural_chunk_indivisible_unit_exceeds_budget`; it does not split or
drop the unit. Empty-cell alias removal was deferred because the current G3.2
target contract addresses every canonical cell and changing that authority is
not necessary to solve G3.4B.

## Anti-smart-runtime audit

```text
financial keyword rules = 0
financial label decisions = 0
dictionary imports = 0
old Gate 2 semantic imports = 0
semantic ranking paths = 0
LLM/provider calls = 0
embedding/RAG paths = 0
tokenizer dependencies = 0
persistence writes = 0
```

The only compiled regex recognizes the existing G3.2 target alias grammar so
that repeated context can be made non-targetable. Boundaries depend only on
canonical structure, document order and exact character size.

## Evidence

Privacy-safe tracked evidence:

- `docs/stage2/research/g3_4b/01_algorithm_and_invariants.md`
- `docs/stage2/research/g3_4b/02_representative_size_matrix.safe.csv`
- `docs/stage2/research/g3_4b/03_target_coverage.safe.json`
- `docs/stage2/research/g3_4b/04_context_envelope_examples.safe.md`
- `docs/stage2/research/g3_4b/05_anti_smart_runtime_audit.safe.json`
- `docs/stage2/research/g3_4b/PRIVATE_EVIDENCE_MANIFEST_G3_4B.safe.json`

Exact customer-bearing evidence is outside Git. Its safe manifest pointer
records 26 files, 195,011,912 bytes and manifest SHA-256
`79bdcabdd7a3e0d9e96bc897fb40b0d7b430d5989355e717867ea3452c5c3320`.
It includes original projections, complete chunk sets, first/boundary/last
examples, REPO whole-table and oversized-row evidence, per-document matrices,
and before/after store snapshots. The source ArtifactStore remained
byte-identical (174 files, 109,059,448 bytes) across the read-only evidence run.

## Verification

Behavior tests use a real canonical store, normalizer, reader and factories;
they do not mock the chunker or canonical read path. They cover compact,
large-table, workbook/table-first, ordinary text, exactly-once reverse mapping,
determinism, document separation, context-only sheet breaks, schema validation,
anti-smart constraints and indivisible-unit failure.

Final command results:

- focused Gate 3 projection/chunking/labeling/contracts plus architecture:
  `61 passed`;
- package-module/CI declaration guard: `1 passed`;
- Ruff over the touched Python implementation/tests: `All checks passed`;
- package `compileall`: passed;
- all three existing projected bundle facades parsed and compiled with the
  inactive Gate 3 module correctly absent: passed;
- scoped private-marker scan over new tracked evidence: 0 findings.

## KISS check

1. Existing Gate 2/G3.2 structure reused: `YES`.
2. Semantic decision inside chunker: `NO`.
3. Second renderer, dictionary or alias owner: `NO`.
4. Data overlap without evidence: `NO`.
5. New infrastructure beyond the current problem: `NO`; one inactive factory,
   one closed schema and focused tests only. Existing bundle facades remain
   closed-world and do not acquire a ghost Gate 3 import.
6. Plain explanation remains accurate: a small document/table stays whole; an
   oversized table is split into contiguous whole rows, with its existing
   headings and structural context repeated alias-free.

## Limitations and stop

- Character bounding does not prove a particular provider token limit.
- No live quality result exists for chunk-by-chunk labeling because provider
  execution is explicitly outside G3.4B.
- An indivisible over-budget row remains an explicit blocker, not a silent
  fallback.
- Empty-cell target reduction remains deferred.
- No batching, provider execution, merge or persistence has started.

## Final status

```text
GOAL_G3_4B = COMPLETED
STRUCTURAL_CHUNKING = PROVEN
SEMANTIC_LOGIC_IN_CHUNKER = NONE
DOCUMENT_MIXING = NONE
WORKING_TARGET_COVERAGE = EXACTLY_ONCE
DATA_ROW_OVERLAP = NONE
CONTEXT_ENVELOPE = SUFFICIENT
LARGE_CSV = BOUNDED
REPO_XLSX = BOUNDED
MAX_CONTEXT_REDUCTION = LARGE_CSV_258692_CHARS_81.175083_PERCENT; REPO_XLSX_3824394_CHARS_98.455383_PERCENT
RAW_CHUNK_EVIDENCE = AVAILABLE
KISS_CHECK = PASS
NEXT_ALLOWED_GOAL = G3.4C_AFTER_HUMAN_REVIEW
```

G3.4C has not been started.
