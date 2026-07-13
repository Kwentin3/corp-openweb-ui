# Broker Reports PDF Hybrid Shadow Migration v1

Status: Goal 2 implemented; production selection remains unchanged.

## Runtime route

```text
process=false original PDF
-> current Gate1Normalizer and current table projections
-> Goal 1 compact dual-write (independent flag)
-> PdfHybridShadowFactory (default disabled)
-> classifier for all detected PDF tables
-> crop/evidence/provider/materialization/validation for hybrid-selected tables
-> private shadow decisions and proposed compact revision
-> unchanged gate2_handoff_v0
```

The Pipe invokes only `PdfHybridShadowFactory`. Stage services are not called directly. The source PDF is reread only while the hybrid flag is enabled and remains inside existing private resolver and ArtifactStore scope.

## Feature flags

All Goal 2 behavior is disabled by default:

- `pdf_hybrid_shadow_enabled=false`;
- `pdf_hybrid_shadow_table_allowlist`;
- `pdf_hybrid_provider_profile`;
- `pdf_hybrid_model_id`;
- `pdf_hybrid_max_candidates`;
- `pdf_hybrid_max_context_bytes`;
- `pdf_hybrid_primary_dpi=150`;
- `pdf_hybrid_escalation_dpi=200`.

No flag selects a hybrid result for production Gate 2. Provider credentials are not Valve fields.

## Persistence

Classification, crop, evidence, raw provider response, provider attempt, binding, materialization, validation, decision and proposed revision are versioned artifacts. Customer values, crop bytes and raw responses use `private_case` visibility and `project_artifact_payload`; the aggregate shadow summary is safe internal metadata.

The proposed compact revision is a construction proof only. It references current versus proposed decisions, never mutates the Goal 1 compact artifact and remains non-authoritative.

## Failure and retry policy

- A raster/candidate/context hard failure terminates only that table.
- A provider failure does not erase sibling evidence.
- HTTP success with malformed or contract-invalid output is failed.
- Same-evidence attempts are explicit and limited to two.
- A 200-DPI escalation requires a typed reason and creates a new crop/package task.
- Unknown candidates, missing grid positions, duplicate use, checksum mismatch, unresolved ambiguity and non-repeatability fail closed.

## Roll-forward boundary

Goal 3 may consume only tables whose contract validation, provisional structural diagnostics and class/model repeatability are acceptable. Goal 2 does not approve:

- Gate 2 selection changes;
- authoritative hybrid tables;
- cleanup or deletion;
- OCR or raster-only facts;
- business-domain extraction;
- CSV/HTML/XLSX refactors;
- OpenWebUI core changes.

The wide and continuation classes remain research blockers when the provisional strict scorer disagrees with structural placement, even if provenance and rectangular-grid gates pass.
