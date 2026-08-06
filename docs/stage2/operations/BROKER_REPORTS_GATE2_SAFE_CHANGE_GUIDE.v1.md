# Broker Reports Gate 2 Safe-Change Guide v1

Status: `CURRENT`

Date: 2026-08-06

Use the existing authority, make the smallest contract-compatible extension,
and add a new mechanism only after a demonstrated blocker.

## Adding or changing a format adapter

1. Keep detection and source parsing inside Gate 1/Full Evidence boundaries.
2. Extend `CanonicalNormalizer`; do not add another public builder or schema.
3. Map source structure to the existing ordered container/node/table model.
4. Link every logical item to compact provenance and the authenticated source.
5. Represent unsupported material as an explicit issue; never silently drop it.
6. Add equivalent semantic fixtures to the cross-format tests.
7. Prove completeness before persistence and again through `CanonicalReader`.

For XLSX, retain streaming, bounded ZIP checks, distinct formula/cached-value
metadata and deterministic resume hashes. For PDF, retain terminal source-atom
and table-proposal accounting. An adapter must not expose its source format as
a required downstream branch.

## Schema and compatibility

An additive optional metadata field may remain in v1 only if entity meaning,
required fields, ordering, completeness and reader behavior do not change.
Changing any of those requires a new schema version, contract, compatibility
plan and migration proof. Never make an unknown version look compatible by
guessing or silent fallback.

Backward compatibility belongs in a versioned adapter that delegates to
`CanonicalReaderFactory.create`; it cannot read SQLite/payload paths or become
a second reader. Physical storage changes stay behind
`CanonicalArtifactStoreFactory` and must preserve immutable versions.

## Required verification

Run, at minimum:

```powershell
python -m pytest -q tests/test_broker_reports_doc34_repository_contract.py
python -m pytest -q tests/test_broker_reports_canonical_artifact_v1.py tests/test_broker_reports_canonical_multiformat.py
python -m pytest -q tests/test_broker_reports_canonical_storage_lifecycle_v1.py tests/test_broker_reports_pdf_canonical_roundtrip.py tests/test_broker_reports_xlsx_canonical_streaming.py
python -m pytest -q tests/test_broker_reports_canonical_consumer_compatibility.py tests/test_broker_reports_canonical_consumer_pipeline.py tests/test_broker_reports_canonical_machine_projection.py
```

Then run the repository privacy guard, generated-bundle parity checks and the
full service suite. A test is successful only at a terminal protocol outcome;
transport success or an updated snapshot is insufficient.

Durable round-trip means publish, activate, reconstruct through the public
reader, verify component/root hashes and logical counts, then repeat after the
relevant restart/restore contour. Format opacity means the consumer code and
output contract need no PDF/HTML/CSV/XLSX branch.

## Gate 2 / Gate 3 separation

Gate 2 may preserve literal content, structure, issues and provenance. It may
not assign financial roles, tax meaning, ontology, cross-document facts or
task-specific prompt semantics. Follow [Gate 3 handoff v1](../contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md)
for the future boundary.

If code conflicts with an authority document, stop the change and reconcile
the versioned contract first. Do not route around a factory, fork a reader or
introduce a parallel storage engine to make a test pass.
