# Broker Reports G3.5 FinancialAnnotationsV1 persistence

Status: `COMPLETED_INACTIVE`

Date: 2026-08-07

## GOAL_STATUS

`G3.5 = COMPLETED`; `ACCEPTANCE = PASS`.

One complete G3.4D compact-document result was stored as an immutable private
`FinancialAnnotationsV1` sidecar and read back byte-equivalently. The exact
Gate 2 canonical version and root hash were unchanged.

## WHAT_WAS_ACHIEVED

- save and read-back passed for five validated annotations;
- wrong-user access failed closed with `artifact_access_denied`;
- overwrite failed with `artifact_immutable`;
- exact canonical, dictionary, instruction, model and provider bindings passed;
- retention was inherited from the canonical manifest;
- existing `ArtifactStore.purge_case` remains the purge owner;
- relabel creates another immutable sidecar without Gate 2 mutation;
- no database, workflow state or product route was added.

## WHAT_WAS_REUSED

- `ArtifactStoreFactory` and the existing SQLite/payload adapter;
- `ArtifactResolver` access/lifecycle checks;
- `Gate3StructuralChunkFactory` for full-document and target membership proof;
- `Gate3FinancialLabelDictionaryFactory` for exact published identity/labels;
- existing artifact immutability, retention and case purge;
- the closed `FinancialAnnotationsV1` payload schema.

## WHAT_WAS_ADDED

- `Gate3FinancialAnnotationsPersistenceFactory` as the sole thin G3.5 facade;
- one ArtifactStore allowlisted type:
  `broker_reports_financial_annotations_v1`;
- one bounded live persistence proof and privacy-safe receipt;
- focused behavioural and architecture tests.

## WHAT_WAS_NOT_NEEDED

- a new database or table family;
- a second ArtifactStore, resolver or persistence framework;
- changes to `CanonicalArtifactV1`, Gate 2 parsers or active pointer;
- semantic classification, retry, repair or provider call;
- workflow DB, events, graph or product activation.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| save | `PASS` |
| read | `PASS` |
| access control | `PASS` |
| exact canonical binding | `PASS` |
| exact dictionary binding | `PASS` |
| instruction/model/provider provenance | `PASS` |
| immutable sidecar | `PASS` |
| Gate 2 unchanged | `PASS` |
| relabel without Gate 2 mutation | `PASS` |
| existing retention/purge reused | `PASS` |
| new DB | `NONE` |

Provider profile identity is immutable ArtifactStore envelope metadata. It is
not added to the closed `FinancialAnnotationsV1` payload, whose existing
`model_identity` intentionally contains only exact `model_id`.

## RAW_EVIDENCE

- [safe receipt](./BROKER_REPORTS_GATE3_FINANCIAL_ANNOTATIONS_G3_5.receipt.safe.json)
- exact input batch SHA-256:
  `c5be4f6a2e1728d04be10155787b02a1ef2fe0a3054e3530d4e72aba91555595`;
- stored/read-back payload SHA-256:
  `06ba501e5d81102fcc6f2ac5642ccb46904b629c8a1917872b546cc944264e70`;
- artifact-id SHA-256:
  `2f408b0d883361a07649dec6edaaade82f1a121027c9cea0214737019aa42079`;
- exact private evidence: 5 files, 7,907 bytes, aggregate SHA-256
  `a56472db9d66293bf4fa09171a4e4a34dff1ffabe7230dd35aba5ade85231b8d`;
- private payload, canonical IDs and artifact ID remain outside Git.

Verification:

- focused persistence/proof seam: `12 passed`;
- complete current Gate 3 regression: `75 passed`;
- architecture guards and maintained/bundle parity: `29 passed`;
- Gate 1/Gate 2 bundle runtime checks: `13 passed`;
- targeted Ruff and compile: passed.

## KNOWN_LIMITATIONS

- The live persistence specimen is the complete compact document; the frozen
  large-CSV specimen remains a representative subset and is intentionally not
  published as a complete sidecar.
- Only published dictionary `1.0.0` exists today. The writer loads by explicit
  version, so later reviewed versions can create new sidecars without rewrite.
- G3.5 does not compute multi-document readiness; that belongs to G3.6.

## OBSERVATIONS

The first live proof attempt stopped before `put_record`: its adapter preserved
the G3.4D private wrapper schema id instead of restoring the runtime batch
result identity. This `TYPE 1` proof-only bug was fixed by an explicit,
hash-checked identity restoration; semantic payload/status/metrics were not
changed. The successful attempt used a fresh external evidence directory.

## KISS_CHECK

`PASS`.

One small facade validates admission and delegates all physical storage,
immutability, access, retention and purge to existing owners. No second state
authority or future-only abstraction was introduced.

## BLOCKING_OBSERVATIONS

`NONE`.

## ERROR_CLASSIFICATION

Initial proof adapter mismatch: `TYPE 1 — IMPLEMENTATION BUG`, fixed before any
sidecar write. Final persistence result: no error.

## AUTO_CONTINUE

`YES`.

## NEXT_GOAL

`G3.6 — NDFL Multi-Document Workflow`.
