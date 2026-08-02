# Broker Reports Managed Document v2

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_managed_document_v2`

Owner: `services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_contracts_v2.py`

Schema: `BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json`

## 1. Additive version boundary

Managed Document v2 is the smallest span-aware revision of the inactive v1
contract. All non-table fields, ordered block semantics, provenance, relations,
quality accounting, canonical JSON rules and integrity sealing retain their v1
meaning.

The v1 markdown, schema, module, fixtures and historical artifacts are frozen.
They are not migrated or mutated in place. A geometry-backed producer may emit
v2, but this contract does not parse a PDF, recover a table, render an LLM view,
call a provider, activate a product route or enter a generated bundle.

For a table without spans, v2 differs structurally only by:

```json
{
  "cell_spans": [],
  "cell_annotations": [
    {
      "span_id": null
    }
  ]
}
```

Removing those additive fields and changing the version produces the exact v1
representation, including its canonical integrity hash.

## 2. TABLE span model

Every v2 TABLE requires `cell_spans`, including when it is empty. A span is a
logical rectangle with one value coordinate and at least one covered
coordinate:

```json
{
  "span_id": "span_example_header",
  "value_row_index": 0,
  "value_column_index": 0,
  "row_start": 0,
  "row_end": 0,
  "column_start": 0,
  "column_end": 2,
  "origin": "DETERMINISTIC_DERIVED",
  "evidence_anchor_ids": ["anchor_example_table"],
  "issue_ids": []
}
```

The inclusive rectangle may be a column span, row span, or combined row and
column span. `value_row_index` and `value_column_index` locate the sole cell
that retains the source value. The other coordinates are explicit covered
coordinates; they are not empty cells.

`SOURCE_EXPLICIT` and `DETERMINISTIC_DERIVED` spans require at least one valid
source anchor. All span issue and anchor references must resolve within the
document registries.

## 3. Cell states and rows

The closed v2 state set is:

```text
PRESENT EMPTY UNREADABLE UNKNOWN COVERED_BY_SPAN
```

Every v2 cell annotation contains `span_id`. Its meaning is fixed:

| State | `rows[row][column]` | `span_id` |
| --- | --- | --- |
| `PRESENT` | source string | `null` |
| `EMPTY` | `null` | `null` |
| `UNREADABLE` | `null` | `null` |
| `UNKNOWN` | v1 rules | `null` |
| `COVERED_BY_SPAN` | `null` | referenced span ID |

`COVERED_BY_SPAN` is never interpreted as `EMPTY`, `UNREADABLE`, or
`UNKNOWN`. A covered annotation has no source evidence anchors. The span owns
the merged-cell evidence and the value coordinate owns any source value. This
is the contract-visible fail-closed rule preventing the same source words from
being assigned to both the value cell and covered cells.

## 4. Validator invariants

After strict Draft 2020-12 validation and the complete v1 compatibility
invariants, `ManagedDocumentContractV2Validator` rejects a table unless all of
the following hold:

1. Every `span_id` is unique within its table.
2. Each rectangle has ordered bounds within the table dimensions.
3. The value coordinate lies inside its span rectangle.
4. A span covers at least two logical coordinates.
5. The value coordinate is not `COVERED_BY_SPAN`.
6. Every other coordinate in the rectangle has a matching
   `COVERED_BY_SPAN` annotation and span ID.
7. Every `COVERED_BY_SPAN` annotation references an existing span.
8. Every covered coordinate is owned by exactly its referenced span.
9. No two span rectangles overlap, including at a value coordinate.
10. Every covered coordinate contains `null` in `rows`.
11. Every non-covered state has `span_id=null`.
12. Every source-derived span has at least one valid evidence anchor.
13. Every coordinate in a span exists in its concrete logical row; ragged rows
    cannot hide an absent column.
14. Covered cells own no source evidence, preventing value/covered double
    ownership at the contract boundary.
15. A span intersecting a header-hierarchy entry must originate on that
    header row and have the same inclusive column range. Body spans cannot
    contradict header coverage.

Violation of any invariant fails closed. The validator does not repair,
truncate, split or guess a span.

## 5. Header and body responsibility

`header_hierarchy.entries[].column_start/column_end` remains the semantic
description of header levels and the logical columns they label.
`cell_spans[]` records cell coverage in `rows`. A physical multi-column header
may therefore have both a header-hierarchy entry and a cell span, but their
coordinates must be compatible.

Spans that do not intersect a header entry are body spans. Header and body
rectangles remain subject to the same non-overlap and covered-cell invariants.

## 6. Deterministic validation and sealing

The public owner surface is:

```python
validator = ManagedDocumentContractV2Validator(v2_schema, v1_schema=None)
document = validator.validate(candidate)
sealed = validator.seal(unsigned_candidate)
parsed = validator.parse_json(raw_utf8_json)
```

The optional explicit v1 schema is a compatibility input for offline callers.
If omitted, the validator deterministically derives the frozen v1 shape from
the v2 schema. JSON parsing rejects duplicate keys. Canonical serialization is
UTF-8 JSON with sorted keys and compact separators. `integrity_sha256` is the
SHA-256 of the canonical document without that field.

## 7. Explicit v1 compatibility projection

`project_managed_document_v2_to_v1(payload)` returns a sealed deep copy and
never mutates the v2 input. It:

1. changes the schema identity to v1;
2. removes `cell_spans`;
3. removes every annotation `span_id`;
4. maps `COVERED_BY_SPAN` to `UNKNOWN`; and
5. recalculates the v1 integrity hash.

The covered-state mapping is deliberately lossy and exists only so frozen v1
codecs can process an additive v2 document. It is not table parity and must not
be persisted as recovered truth. `UNKNOWN` is used because mapping a covered
coordinate to `EMPTY` or `UNREADABLE` would assert a false source meaning.

For spanless v2 tables the projection is exact: starting from a sealed v1
document, adding empty `cell_spans`, adding null `span_id` values and sealing as
v2 projects back to the original canonical v1 bytes.

## 8. Inactive scope stop

This revision establishes only the versioned document contract. LLM Document
View v2, geometry-backed table recovery, private visual gold, PDF parity,
provider qualification and product activation are separate goals. Contract
acceptance does not claim that any PDF table has been recovered.
