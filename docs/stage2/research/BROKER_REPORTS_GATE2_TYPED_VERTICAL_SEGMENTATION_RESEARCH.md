# Broker Reports Gate 2 Typed Vertical Segmentation Research

Date: 2026-07-10

Scope: deterministic segmentation and routing refinement for one real
`case_group_002` typed Gate 2 vertical.

This note contains safe aggregate evidence only. It contains no customer
filename, OpenWebUI file id, private path, source row/text, account, personal
datum, secret, or environment value.

## Executive finding

The previous real Gate 2 vertical was unknown-only because the runtime treated
each bounded Gate 1 private slice as one extraction unit. All 16 primary units
were marked truncated at creation time, and the useful table units mixed typed,
unknown, summary, and no-fact rows.

Gate 2 package budgets were not the cause. The domain runtime permits 40 table
rows or 6000 text characters, while the relevant Gate 1 profilers persisted
much smaller bounded slices.

The safest real typed target is a one-ref `position_snapshot` derived unit. It
is high-confidence from an exact visible operation/category helper signal,
complete within a 10-ref parent projection, and carries three issue refs. The
parent remains truncated, so its unseen remainder must stay
`pending_gate1_reslice` and primary expansion must remain blocked.

## Audit answers

### 1. Why every real source unit was truncated

`source_slice_truncated` in Gate 2 copied the persisted Gate 1 private-slice
flag. The profiler bounds are:

| Shape | Gate 1 bound | Truncation condition |
| --- | ---: | --- |
| CSV table | first 5 rows | source has more than 5 rows |
| HTML table | first 10 rows | extracted table has more than 10 rows |
| TXT/HTML text | first 20 lines and first 2000 characters | additional lines or characters exist |
| PDF text | first 2000 characters | extracted text is longer |
| DOCX text | first 20 paragraphs and first 2000 characters | additional paragraphs or characters exist |

The real wave contained 12 primary documents and 16 source units: 6 table
units and 10 text units. All 16 inherited `truncated=true`.

### 2. Exact truncation boundary

The cause is Gate 1 profiling/slicing and report shape. It is not:

- the Gate 2 table budget of 40 rows;
- the Gate 2 text budget of 6000 characters;
- domain-package physical narrowing;
- the stitcher;
- model context pressure.

The old source-unit boundary equalled the entire bounded private slice. It had
no child-unit concept, so a useful row cluster remained coupled to unrelated
rows and to the parent truncation flag.

### 3. Clearest typed signals

The safe pre-refactor matrix showed:

- table units with exact high-confidence `cash_movement` helpers;
- table units with exact high-confidence `position_snapshot` helpers;
- high-confidence `document_summary_evidence` helpers;
- many low-confidence text segments defaulting to summary evidence;
- unknown rows without safe typed signals.

After deterministic segmentation, preflight found 122 typed candidate derived
units and 11 high-confidence typed derived units:

| Domain | High-confidence units |
| --- | ---: |
| `position_snapshot` | 2 |
| `cash_movement` | 3 |
| `document_summary_evidence` | 6 |

### 4. Units that become complete when split differently

Table units become useful when contiguous refs are partitioned by route kind,
uniform primary domain, confidence, and a non-overlapping row window. Text
units can be partitioned by safe section ref, route class, and bounded segment
window.

A derived unit is complete only for its selected parent refs. The plan accounts
for every ref visible in the parent projection and marks all unselected child
units deferred. If the parent slice was truncated, the unseen remainder is not
invented; it is an explicit pending coverage record.

### 5. Safe routing signals

High-confidence typed routing may use:

- normalized safe header descriptors;
- exact source-visible operation/category labels;
- existing deterministic `fact_type_hint`;
- safe value kinds;
- passport and usage-classification projections;
- issue refs;
- a uniform high-confidence derived-segment signal produced from the parent
  route.

`Identifier` is treated as a safe header synonym for `instrument`. Its value
still requires a whitelisted source-value ref and mechanical reproduction.
Regex and stems remain helper signals only, never source-of-record parsing.

### 6. Safest first domain

`position_snapshot` is the safest first target because:

- two real high-confidence derived candidates exist;
- the smallest candidate contains one selected ref;
- the route uses an exact visible domain helper;
- no second typed or unknown domain is required inside the selected child;
- the package is smaller than the cash/summary mixed parents;
- the target preserves all provenance, value, issue, and parent coverage refs.

This is a source-visible position fact only. It is not valuation, profit/loss,
tax, or consolidation.

### 7. Deterministic segmentation rule

The implemented v0 rule is:

1. Route every parent-selected ref deterministically.
2. Preserve parent order.
3. Start a new child when route kind, uniform primary domain, confidence, safe
   text section, or deterministic no-fact reason changes.
4. Split remaining groups into non-overlapping table/text windows.
5. Physically narrow rows/segments, provenance, source-value index, and issue
   context.
6. Rebase only private payload indices; preserve opaque provenance and checksum
   refs.
7. Partition every parent-selected ref exactly once.
8. Persist one safe plan and only selected private derived units.

Production ownership is:

```text
Gate2SourceUnitRouterFactory
  -> Gate2SourceUnitSegmenterFactory
  -> Gate2SourceUnitRouterFactory
  -> Gate2DomainPackageBuilderFactory
  -> Gate2DomainSourceFactRuntimeFactory
  -> Gate2SourceFactValidatorFactory
  -> Gate2SourceFactStitcherFactory
```

### 8. What remains unknown, no-fact, conflict, or pending

- Rows without a safe typed signal remain `unknown_source_row` child units.
- Header, blank, and layout refs remain deterministic no-fact child units.
- Ambiguous one/two-domain candidates remain separate bounded children and may
  still become explicit conflicts after validation.
- Failed domain packages remain uncovered; the stitcher cannot hide them.
- All unselected children are deferred, not dropped.
- The unseen remainder of every truncated parent is
  `pending_gate1_reslice`.

### 9. Issue carry-forward

Document-scoped issues remain available to every derived unit in that
document. Source-unit-scoped issues are retained only when their evidence refs
intersect the derived evidence whitelist. The selected real target carried all
three allowed issue refs, and the final stitch result contained three
issue/fact links.

### 10. Proof required before later primary expansion

The typed vertical proof gate requires:

- one primary document and one selected derived unit;
- one or two typed domains, no unknown-only result;
- at least one validator-passed typed fact;
- strict private raw output and private source-facts persistence;
- complete, conflict-free selected coverage;
- zero provenance, completeness, coverage, and issue carry-forward errors;
- zero Knowledge/RAG/vector/document/file regression;
- no non-primary extraction and no primary expansion in the proof run.

Later expansion additionally requires no truncated parent and no
`pending_gate1_reslice`. The completed bounded typed proof does not satisfy
that additional condition.

## Architecture boundary

New artifacts:

| Artifact | Visibility | Purpose |
| --- | --- | --- |
| `broker_reports_source_unit_segmentation_plan_v0` | `safe_internal` | parent-ref partition, selected/deferred child counts, explicit remainder state |
| `broker_reports_derived_source_unit_v0` | `private_case` | physically narrow resolver-gated child projection |

Gate 1 artifacts remain immutable. The broad extractor remains
compatibility/synthetic-only. Managed Prompt bodies remain in OpenWebUI. The
source-fact validator and stitch authority were not weakened.

## Decision

The real typed vertical is safe and was executed. Full primary expansion is
not safe because the parent source slices remain bounded/truncated and require
a future Gate 1 reslice/full-source coverage refinement.
