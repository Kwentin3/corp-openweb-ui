# Broker Reports DOC1 Managed Document Contract Closure Report

Status: `PASSED`

Date: 2026-08-01

## 1. Closure boundary

DOC1 defines the universal, managed, machine-readable document artifact that a
future source normalizer must return. It is contracted and inactive. This goal
did not build a PDF, HTML, CSV, XLSX, or XLS normalizer and did not start DOC2,
DOC3, or DOC6.

Exact delivery chain:

- base commit: `7cbb62f39915fd1499aeb009aac6a41bab0accb0`;
- implementation commit: `c81d6d0d40e2f95e2eb9ca8020544744c9b717cf`;
- implementation PR: `#247`;
- implementation merge: `c4fa86d8229bc8afdd88bfd0371a96d260790942`;
- evidence merge: reported in the terminal response because a commit cannot
  name its own future merge commit.

## 2. Architectural decision

The primary document model is one ordered `blocks[]` stream. The stream is the
only primary reading order. Optional explicit relations express facts that
order alone cannot express, including a note or footnote target and table
continuation. This keeps source order obvious while avoiding independent text
and table fragments or an unnecessary graph database.

The strict top-level contract separates `CONTENT`, `PROVENANCE`, `CONTROL`, and
`PRIVATE_SOURCE`. It supports PDF, HTML, CSV, XLSX, XLS, and unknown sources
without broker-specific mandatory sections.

## 3. Context and unknowns

The artifact preserves the document passport, ordered headings, paragraphs,
lists, tables, notes, visuals, boundaries, and unknown elements. Typed source
anchors retain where each item came from without requiring common consumers to
interpret PDF coordinates, DOM paths, CSV ranges, or XLSX cell ranges.

Metadata values carry both a status and origin. `UNKNOWN`, `NOT_APPLICABLE`,
and `CONFLICTING` do not require fabricated values. `MODEL_PROPOSED` is
distinct from `SOURCE_EXPLICIT`; semantic validation rejects incompatible
origin/evidence combinations.

Unknown structures remain `UNKNOWN` blocks with available text or a private
artifact reference, source anchors, recovery status, and issues. They are not
dropped. Known losses are explicit ledger entries. Canonical artifacts always
require `unaccounted_context_loss_total = 0`.

## 4. Table contract

The existing `description + rows` logical content is reused inside each
`TABLE` block. The wrapper adds source parts, completeness, optional title,
logical header/group/total/unit annotations, cell-state annotations, relation
IDs, and known gaps. `EMPTY` and `UNREADABLE` are distinct annotations that
point to logical row/column coordinates.

The contract does not declare physical column widths, line thickness, pixel
position, or physical merged cells as canonical truth. A multi-part table may
be either one table with multiple source parts or multiple table blocks joined
by `CONTINUATION_OF` or `SAME_LOGICAL_OBJECT`.

## 5. DOC0 accounting

The machine-readable coverage matrix preserves the exact 53-facet DOC0 order.
Its terminal accounting is:

```text
doc0_context_facets_total = 53
doc0_context_facets_represented_total = 51
doc0_context_facets_explicit_unknown_total = 2
doc0_context_facets_loss_ledger_total = 0
doc0_context_facets_deferred_total = 0
doc0_context_facets_unaccounted_total = 0
```

Every row identifies its DOC1 contract location, representation, explicit
unknown policy, and loss policy. No facet is hidden in a generic extension
field and no architectural blocker remains.

## 6. Safe fixture corpus

Six hand-authored safe documents validate contract expressiveness:

1. ordinary PDF broker report with metadata, heading, paragraph, table, note,
   and source order;
2. PDF with an unknown structure, unknown heading level, and unknown relation;
3. two-page PDF with two continued table blocks, repeated header, footnote,
   and one unreadable cell;
4. CSV represented as one table with row/column anchors;
5. two-sheet XLSX with boundaries, ranges, and an unsupported formula loss;
6. HTML with DOM-path provenance.

Counts are PDF 3, HTML 1, CSV 1, XLSX 1. No fixture contains a customer file,
customer value, filename, local path, or provider payload. The fixtures prove
schema and semantic expressiveness only. They do not prove current PDF parsing;
`REAL_CORPUS_GAP = TRUE` remains explicit.

## 7. Deterministic authority and validation

`managed_document_contracts.py` is the sole inactive contract owner. It uses
the JSON Schema Draft 2020-12 validator plus fail-closed semantic checks for:

- duplicate JSON keys, schema version, and strict extra-property rejection;
- unique IDs and continuous ordered block ordinals;
- typed and source-compatible anchors;
- metadata status, origin, value, and evidence consistency;
- relation endpoints and evidence anchors;
- logical table annotation bounds and relation references;
- quality totals, status, conflicts, known losses, and blocking losses;
- canonical UTF-8 sorted JSON SHA-256 excluding the integrity field;
- absence of canonical financial type IDs and product activity.

The validator does not parse files, classify a document, infer financial
meaning, build relations, repair an artifact, call a provider, or write to a
product ArtifactStore.

## 8. Terminal verification

Final pre-merge local acceptance:

```text
full suite = 2336 passed, 5 historical skips, 0 failed, 0 errors
focused DOC1 suite = 30 passed
relevant regression suite = 72 passed
new_skips_total = 0
changed-file Ruff = PASSED
compileall = PASSED
git diff --check = PASSED
generated bundle diff = 0
privacy scan = PASSED
```

GitHub `broker-reports-ci` passed on implementation commit
`c81d6d0d40e2f95e2eb9ca8020544744c9b717cf` in 5:43. A formal review receipt
was anchored to that exact commit and found no actionable issue.

The exact merged main commit
`c4fa86d8229bc8afdd88bfd0371a96d260790942` then passed the full suite again:

```text
2336 passed, 5 historical skips, 5 warnings in 897.11s
test_failures_total = 0
test_errors_total = 0
new_skips_total = 0
```

On that same merged commit, focused DOC1 tests passed 30/30; changed-file Ruff,
compileall, privacy scan, `git diff --check`, and generated-bundle zero-diff
also passed.

An earlier non-acceptance diagnostic exposed an attempted central authority-map
registration conflict with a historical Type-First hash pin. The final change
removed that authority-map edit instead of weakening historical authorization.
The terminal implementation diff contains no Type-First or central
authority-map change.

## 9. Non-change proof

The implementation changed no current parser or legacy document builder, no
fallback, no Gate 1 or Gate 2 product route, no Semantic Pack, no Type-First
implementation, no financial fact validator/materializer, no Gate 3 or Gate 4
code, no provider configuration, no prompt, no valve, no admission, no live
state, and no generated Function bundle.

The module has no product or provider entrypoint and is absent from all three
generated Function bundles. Runtime product route changes, provider calls, and
live changes are all zero.

## 10. Artifact integrity

Implementation artifact SHA-256 values on the merged implementation tree:

```text
0bf0a8bbad6183f0d1ab87eb4dd83618eaddb0092f6af3aca3d4060cc5d99408  BROKER_REPORTS_DOC0_TO_DOC1_CONTEXT_COVERAGE.v1.json
aeac90def9d88bca65049ba09c0c40372e83ea2c24af7f2b95cabb84c8432153  BROKER_REPORTS_DOC1_DOCUMENT_CONTRACT_DECISION.v1.md
794f26c56931dbcf3e7094a1b25805bb8d17e9b39b02b35d8fdff2d53d9fcfa4  BROKER_REPORTS_MANAGED_DOCUMENT.v1.md
441ea942d564614e8a19ee501ad96ba872d6c558fc9c7c643d474f69932baad2  BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json
cba74e83f2898fc8f158257b02b3e8c0d470126ee46cecc3e405a6ac1f46de04  managed_document_contracts.py
b1d57db1008d8513e1223d18a5aa29645e155184c9ec4c40b34c3590e6834e1f  broker_reports_managed_document_v1_corpus.safe.json
3a235aaa0146a728ba8347bc6b75599cab9cb6292a921b823ed18ba0c725d241  test_broker_reports_managed_document_contract.py
```

## 11. Acceptance and stop

```text
DOC1_MANAGED_DOCUMENT_CONTRACT = PASSED
PRIMARY_DOCUMENT_MODEL = ORDERED_BLOCK_STREAM
EXPLICIT_RELATIONS = PRESENT
UNKNOWN_BLOCK = SUPPORTED
UNKNOWN_METADATA = SUPPORTED
SOURCE_PROVENANCE = PRESENT
LOSS_LEDGER = PRESENT
UNACCOUNTED_CONTEXT_LOSS_ALLOWED = 0
DOC0_CONTEXT_FACETS_UNACCOUNTED = 0
CURRENT_TABLE_CORE_REUSED = TRUE
PHYSICAL_TABLE_RECONSTRUCTION = NOT_REQUIRED
PDF_NORMALIZER = NOT_STARTED
LLM_FRIENDLY_RENDERER = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

DOC1 is closed. DOC2 is not started by this closure.
