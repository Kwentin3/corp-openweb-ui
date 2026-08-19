# Broker Reports Gate 5 End-to-End Full-target XML v0

Goal: `G5.35`
Terminal: `END_TO_END_FULL_TARGET_XML_VALID`
Status: inactive supplied-case proof

## Boundary

This contract proves one complete replay:

```text
authenticated supplied source
→ Gate 1 custody
→ Gate 2 CanonicalArtifactV1
→ Gate 3 FinancialAnnotationsV2
→ Gate 4 Financial Case
→ existing Gate 5 tax/declaration owners
→ Declaration Semantic Input
→ G5.34 full-target projection
→ official XSD validation
```

The replay starts from source bytes. It must not accept a caller-provided
CanonicalArtifact, FinancialAnnotations payload, Gate 4 fact, Tax Model, Scope
Receipt, Resolved Package or Declaration Semantic Input.

## Representative input

The single proof case is the packaged resource
`gate5_end_to_end_supplied_case.proof.v0.json`:

```text
schema version       broker_reports_gate5_end_to_end_supplied_case_v0
case fact set        g535_supplied_broker_source_2025
version              2026-08-11.0-proof
resource SHA-256     f02611964fee15986fbec157253607a46b18db3a8459f659ae8ecc16529b3148
source SHA-256       6b4ff0453368df9d7ab09293b1276e49ed5f66d45cadb4bf38a3cd7407163cbb
tax period           2025
```

The source and all filing/case values are synthetic. The resource binds
`synthetic_proof_evidence = true` and `real_user_fact = false`. Raw synthetic
input remains only in that hash-pinned proof resource; it is not duplicated in
the safe receipt/report, and generated XML is not stored in Git evidence.

## Owners and factory route

| Stage | Sole route used by G5.35 |
| --- | --- |
| Gate 1 | `Gate1Normalizer.normalize` plus `persist_gate1_result` |
| Gate 2 | canonical publication performed by Gate 1 handoff; activation/read through `CanonicalReaderFactory.create` |
| Gate 3 | `Gate3ChunkBatchLabelingFactory.create` plus `Gate3FinancialAnnotationsPersistenceFactory.create` |
| Gate 4 | `Gate4FinancialCaseRuntimeFactory.create` |
| Gate 5 | previously published methodology, aggregation, Declaration component, scope, package and semantic-input factories |
| Target | `Gate5FullTargetXmlProjectionRuntimeFactory.create` |

The Gate 3 external model boundary is replayed deterministically in tests. Its
two responses remain untrusted proposals: the normal Gate 3 schema, literal
binding, role-pack, canonical-binding and persistence checks still execute.
No FinancialAnnotations or Gate 4 fixture is injected.

## Supplied facts versus case facts

The broker CSV contributes the disposal row and reaches Gate 4 through the
normal source path. Genuine filing/user facts enter through the separate
hash-pinned case resource and the existing trusted Gate 5 boundaries.

The resource classifies the critical values as:

- `SOURCE / FINANCIAL FACT`;
- `USER / CASE FACT`;
- `EXTERNAL REFERENCE FACT`;
- `DECLARATION / FILING CONTEXT`;
- `METHODOLOGY-DERIVED TAX FACT`.

Each audit row binds the source value hash to its owner, sealed component
contract/hash, semantic path, Projection Definition mapping ID and XML target.
Target names and codes are still owned only by the G5.34 Projection Definition.

## Missing-source behavior

If Gate 3 observes a tax-relevant row but Gate 4 materializes a required role
as missing, G5.35 creates the existing supplied-case missing-source indication
and resolves it through `Gate5DeclarationScopeResolutionRuntimeFactory.create`.
The terminal blocker contains the normal acquisition action
`provide_missing_source_or_values`; no fallback or default reaches XML.

No activation evidence and no missing-source clue retain
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`; the proof does not open a universal taxpayer
questionnaire.

## Hash-chain receipt

The compact receipt binds, in order:

```text
source bytes
→ Gate 1 custody projection
→ Gate 2 canonical root
→ Gate 3 annotation payload
→ Gate 4 Financial Case
→ operation/category/income-group Tax Models
→ trusted Declaration components
→ Full Declaration Definition
→ Scope Receipt
→ Resolved Package
→ Declaration Semantic Input
→ Projection Definition
→ XML
→ official XSD
```

Each row hashes its stage identity, artifact hash and previous chain hash.
Receipt validation recomputes the complete chain and final receipt hash.

## Determinism

Two full replays with identical source bytes, case resource and trusted
artifacts must produce the same target-independent semantic result hash and
byte-identical XML. Storage-owned `artifact_id`, `canonical_version_id` and
`created_at` are declared external identities and excluded from the stable
semantic comparison, but remain bound in each run-specific receipt.

## Required negative proofs

1. A structurally missing supplied amount stops at Gate 4 with a machine
   acquisition request before XML.
2. A missing mandatory filing value stops at the filing/case boundary without
   placeholder or default.
3. A changed sealed Semantic Input and a changed receipt-chain row both fail
   closed.

## Success receipt

```text
source-to-XSD chain       complete
Gate 4 fixture injection  absent
Tax Model fixture         absent
Semantic Input fixture    absent
mapping proof             passed
official XSD              passed
blockers                  0
terminal                  END_TO_END_FULL_TARGET_XML_VALID
```

Safe evidence is recorded in
[`BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML_G5_35.receipt.safe.json`](../../reports/2026-08-11/BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML_G5_35.receipt.safe.json).

## Stop

This is an inactive synthetic proof. It does not authorize PDF generation,
filing, product UX, activation, push or pull-request publication. A second
target or real-user workflow requires separate authorization.
