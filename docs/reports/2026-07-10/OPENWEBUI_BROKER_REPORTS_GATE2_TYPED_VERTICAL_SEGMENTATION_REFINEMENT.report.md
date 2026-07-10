# OpenWebUI Broker Reports Gate 2 Typed Vertical Segmentation Refinement

Date: 2026-07-10

Scope: deterministic source-unit segmentation and typed routing refinement for
one real `case_group_002` Gate 2 vertical.

This report contains safe aggregates only. It contains no customer filename,
OpenWebUI file id, private path, raw row/text, account, personal datum, secret,
or environment value.

## Executive result

The slice passed.

One real primary document produced one complete bounded derived source unit,
one high-confidence `position_snapshot` domain package, one validator-passed
typed `broker_reports_source_facts_v0` set, and one complete stitch result.
There were zero provenance, completeness, coverage, issue carry-forward,
privacy, Knowledge, RAG, or vector violations.

Primary expansion is still not safe. The selected child is complete for its
one ref, but its parent Gate 1 slice remains truncated and its unseen remainder
is explicitly `pending_gate1_reslice`. Gate 3 remains false. No non-primary or
primary expansion run was performed.

## Why all real units were truncated

The flag originated in Gate 1 bounded profiling, not in Gate 2 package limits.

| Source shape | Gate 1 persisted bound |
| --- | ---: |
| CSV table | first 5 rows |
| HTML table | first 10 rows |
| TXT/HTML text | first 20 lines and 2000 characters |
| PDF text | first 2000 characters |
| DOCX text | first 20 paragraphs and 2000 characters |

Gate 2 permits 40 table rows and 6000 text characters. The real preflight
therefore confirmed that Gate 2 budgets, strict schema, stitcher, and model
context were not the truncation source.

The previous runtime equated one persisted bounded slice with one extraction
unit. Useful typed rows were coupled to unknown, summary, and no-fact rows, and
the whole unit inherited the parent truncation flag.

## Refined architecture

The customer path is now:

```text
Gate2InputReadinessFactory
  -> parent Gate2SourceUnitRouterFactory
  -> Gate2SourceUnitSegmenterFactory
  -> safe segmentation plan
  -> selected private derived source unit
  -> derived Gate2SourceUnitRouterFactory
  -> Gate2DomainPackageBuilderFactory
  -> OpenWebUI managed domain Prompt + strict JSON Schema
  -> unchanged Gate2SourceFactValidatorFactory
  -> Gate2SourceFactStitcherFactory
```

New artifacts:

| Artifact | Visibility | Backend |
| --- | --- | --- |
| `broker_reports_source_unit_segmentation_plan_v0` | `safe_internal` | `project_artifact_store` |
| `broker_reports_derived_source_unit_v0` | `private_case` | `project_artifact_payload` |

Gate 1 slices are immutable. The plan partitions every ref visible in the
parent projection exactly once and marks unselected children deferred. The
derived unit preserves the parent private-slice ref, source checksum,
slice-payload checksum, and original row/cell/segment/source-value refs. Only
private payload indices are rebased.

For a legacy truncated parent:

```text
derived source_slice_truncated = false
parent_source_slice_truncated = true
coverage_scope = complete_within_parent_projection
parent_remainder_status = pending_gate1_reslice
```

This distinction prevents bounded success from becoming a false whole-document
or expansion claim.

## Segmentation and routing rules

The segmenter preserves parent order and splits on:

- route kind;
- uniform primary domain;
- confidence;
- deterministic no-fact reason;
- safe text section;
- non-overlapping table/text window budget.

Every parent-selected ref belongs to exactly one derived unit. Unknown and
no-fact refs remain explicit child units. Ambiguous candidates remain bounded
and the stitcher still owns final conflict detection.

Routing policy advanced to `gate2_source_unit_domain_routing_v1`. It may reuse
a uniform high-confidence derived-segment signal only when that signal was
produced deterministically from the parent route and contains exactly one
typed domain. The model cannot create or modify it.

`Identifier` was added as a safe header synonym for `instrument`. The value
still requires its original source-value ref and mechanical `trimmed_text`
reproduction.

## Domain package and prompt/schema alignment

The selected derived unit is physically narrowed before the domain builder
performs a second domain-only narrowing. The model receives only:

- selected candidate rows/segments;
- whitelisted evidence refs;
- whitelisted source-value refs;
- relevant whitelisted issue refs;
- explicit selected coverage expectation;
- safe segmentation status.

Deferred, unknown, no-fact, and unrelated rows are not sent to the selected
typed extractor.

The source-fact validator, provenance requirements, issue carry-forward rules,
and provider-native strict schema were not weakened. Final Prompt bodies remain
OpenWebUI managed Prompts. Python, Pipe, Valves, and chat text contain prompt
identity/policy only.

Canonical source-facts schema SHA-256 remained:

```text
2fcf8ef920e7aceae6fef898d4a4c375db7ab0cd73416bd9e19f76d57bff6da4
```

## Local verification

Baseline before this slice: 115/115 tests passed.

Final verification:

```text
python -m unittest discover -s tests
Ran 119 tests
OK

python -m compileall broker_reports_gate1 openwebui_actions scripts
passed
```

New terminal-outcome tests cover:

- a large/truncated parent partitioned into complete typed, unknown, and
  deterministic no-fact children;
- exact ordered parent-ref coverage with no duplicates or gaps;
- row/cell/source-value/checksum ref survival;
- repeated physical narrowing with original row ordinals and rebased payload
  indices;
- issue carry-forward and unrelated-row exclusion;
- resolver-gated private derived-unit persistence;
- factory-backed domain runtime, strict validation, stitch completion, and
  expansion fail-closed behavior;
- `Identifier` safe header normalization;
- closed-world bundled Function execution and factory anti-drift anchors.

The unit under test and core domain/runtime services were not mocked. Only the
structured-model boundary was synthetic in the local runtime test.

## Live Function and managed Prompts

Installed Function:

```text
broker_reports_gate2_domain_source_fact_pipe
active = true
final bundle SHA-256 = 25ebe37ae267f971e4dc1f692b9c30b526abb93ccefe336efead83b1e09220c1
live content SHA-256 = 25ebe37ae267f971e4dc1f692b9c30b526abb93ccefe336efead83b1e09220c1
```

All nine managed domain Prompts were active and contract-matched. The real
typed proof ran on the immediately preceding function bundle
`ef2378fc2302baa1a71884c723e25d8da611ffb15e64593b3aff6c2b9a92343d`.
The final bundle changes only the safe compact-summary wording after that real
proof; final runtime parity was re-proven by the synthetic smoke.

## Synthetic proof

The final live synthetic fixture used one truncated table parent with more rows
than the Gate 1 CSV bound. Non-overlapping one-ref windows produced a smallest
typed `position_snapshot` child while keeping other children deferred.

| Metric | Result |
| --- | ---: |
| parent selected refs | 5 |
| derived units planned | 5 |
| selected derived units | 1 |
| deferred derived units | 4 |
| selected refs | 1 |
| domain packages | 1 total / 1 accepted / 0 rejected |
| strict raw outputs | 1 private / fallback 0 |
| validated private fact sets | 1 |
| typed facts | 1 `position_snapshot` |
| stitch results | 1 complete |
| coverage | 1 typed / 0 unknown / 0 no-fact / 0 conflict / 0 uncovered |
| issue/fact links | 1 |
| parent remainder | `pending_gate1_reslice` |

Infrastructure delta:

```text
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge-backend records: 0
```

The final synthetic case created 25 scoped ArtifactStore records and was
purged through the ArtifactStore lifecycle.

Two earlier fail-closed diagnostic iterations exposed a two-row consolidation
coverage gap and an unrecognized safe `Identifier` header. They were fixed by
smaller deterministic row windows and the safe header synonym; no validator or
schema rule was removed.

## Real preflight

Read-only preflight used the existing process=false `case_group_002` artifacts.
It performed no model call or persistence.

| Metric | Result |
| --- | ---: |
| primary documents | 12 |
| parent source units | 16 |
| truncated parent units before segmentation | 16 |
| derived units planned | 188 |
| truncated derived units | 0 |
| typed candidate derived units | 122 |
| high-confidence typed derived units | 11 |
| high-confidence `position_snapshot` | 2 |
| high-confidence `cash_movement` | 3 |
| high-confidence `document_summary_evidence` | 6 |

Selected smallest safe target:

```text
primary documents selected: 1
parent source units selected: 1
derived source units selected: 1
domains: position_snapshot only
selected refs: 1
model candidates: 1 high-confidence
issue refs: 3
parent projection coverage: 10 / 10 partitioned
derived source_slice_truncated: false
parent_source_slice_truncated: true
parent remainder: pending_gate1_reslice
non-primary run: false
primary expansion run: false
```

`position_snapshot` was selected before cash/summary candidates because it is a
typed source fact, has an exact visible helper, fits one ref, and requires no
second typed or unknown domain in the selected child.

## Real typed vertical

Exactly one smallest real typed vertical was run.

| Metric | Result |
| --- | ---: |
| primary documents in wave | 12 |
| selected / deferred documents | 1 / 11 |
| parent units selected | 1 |
| derived units planned | 8 |
| selected / deferred derived units | 1 / 7 |
| selected derived refs | 1 |
| domain packages | 1 total / 1 accepted / 0 rejected |
| strict raw outputs | 1 private / fallback 0 |
| validations | 1 passed / 0 errors |
| private validated source-facts sets | 1 |
| facts | 1 `position_snapshot` |
| unknown / no-fact / conflict / uncovered | 0 / 0 / 0 / 0 |
| stitch results | 1 complete |
| selected coverage | 1 typed-owned / 1 selected |
| route issue refs / issue-fact links | 3 / 3 |
| Gate 3 ready | false |
| primary expansion ready | false |

Validation error counts:

```text
source_fact_provenance_missing: 0
source_fact_completeness_overstated: 0
source_fact_coverage_gap: 0
source_fact_issue_not_carried: 0
all other validation errors: 0
```

Infrastructure delta:

```text
ArtifactStore records: +11 expected scoped records
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge-backend records: 0
```

Raw model output and canonical source facts remained private. The compact
Russian summary contained safe counts/status only. No tax, declaration,
XLS/XLSX, OCR/VLM, ordinary upload, Knowledge/RAG, vector search, duplicate
consolidation, or non-primary extraction was performed.

## Expansion decision

Not ready for full `case_group_002` primary domain extraction expansion.

The typed vertical proof gate passed, but the source-completeness gate did not:

1. all 16 parent source units are still bounded/truncated Gate 1 slices;
2. the selected typed child is complete only within its 10-ref parent
   projection;
3. the parent remainder remains `pending_gate1_reslice`;
4. whole-document coverage and repeated typed execution across primary sources
   are not proven;
5. Gate 3 and non-primary extraction remain out of scope.

The next safe slice is a Gate 1 full-source/reslice coverage contract and proof,
followed by a limited primary typed expansion using the same segmenter/runtime.

Not emitted:

```text
READY_FOR_CASE_GROUP_002_GATE2_PRIMARY_DOMAIN_EXTRACTION_EXPANSION
```

## Proven statuses

```text
GATE2_TYPED_VERTICAL_SEGMENTATION_RESEARCH_READY
GATE2_SOURCE_UNIT_SEGMENTATION_REFINED
GATE2_TYPED_ROUTING_REFINED
GATE2_TYPED_DOMAIN_PACKAGE_READY
GATE2_TYPED_VERTICAL_SYNTHETIC_PASSED
CASE_GROUP_002_TYPED_VERTICAL_PREFLIGHT_READY
CASE_GROUP_002_REAL_TYPED_VERTICAL_PASSED
GATE2_ROW_SEGMENT_COVERAGE_PROVEN
GATE2_ISSUE_CARRY_FORWARD_PROVEN
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
```
