# Broker Reports PDF Compact Dual-Write Migration v1

Status: Goal 1 implemented; production selection remains unchanged.

## Runtime route

```text
process=false original PDF
-> Gate1Normalizer and current parser factories
-> current full payload, source units and table projections
-> persist_gate1_result obtains real source_file_ref_v0 id
-> PdfCompactCanonicalFactory
-> PdfCompactCanonicalValidator
-> PdfCompactGate2MappingValidator (proof only)
-> PdfNormalizationAcceptanceFactory
-> compact + acceptance persistence
```

Feature flag: `pdf_compact_canonical_dual_write`; default `false`. The OpenWebUI Pipe exposes it as an admin Valve and copies only its boolean value into Gate 1 input context.

When the flag is off, no compact, acceptance or compact-failure artifact is created. Non-PDF inputs are unchanged. When it is on, a typed build failure is stored as `broker_reports_pdf_compact_build_failure_v1`; current artifacts and current Gate 2 handoff remain available; no partial compact is persisted as accepted.

## Artifact roles

| Artifact | Goal 1 role | Cleanup now |
|---|---|---|
| Original PDF / `source_file_ref_v0` | permanent source evidence | no |
| Compact canonical PDF | intended permanent canonical normalization | no |
| Acceptance record | permanent decision/lifecycle record | no |
| Current normalized table projections | authoritative and permanent during migration | no |
| Full forensic payload and full source units | temporary working state / future TTL debug | no |
| Detailed rejected hypotheses and full geometry inventories | temporary/debug inside current working state | no |

Physical deletion and cleanup activation belong to Goal 4.

## Compact to normalized-table-projection v0 mapping

`PdfCompactGate2AdapterFactory` is a local proof adapter only. It reconstructs accepted v0 projections from packed rows/cells/evidence, including explicit empty cells, header models and a reproducible private source-value index. The unchanged `TableProjectionValidator` must accept every mapped projection.

The mapping validator compares every table identity and accepted/blocked status, and for accepted tables compares row/column/cell identities, source refs, header model, empty-cell flags and projection status. It does not write mapped projections and is not referenced by `gate2_handoff_v0`.

## Roll-forward boundary

Goal 2 may consume this foundation for the separately approved hybrid path. It must not assume cleanup, production Gate 2 selection, raster/VLM/provider transport or semantic correctness has been approved by Goal 1.
