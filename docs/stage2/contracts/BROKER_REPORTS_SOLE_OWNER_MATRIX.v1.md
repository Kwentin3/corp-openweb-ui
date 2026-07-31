# Broker Reports Sole Owner Matrix v1

Status: normative ownership baseline

Effective date: 2026-07-31

## PROGRAM_OWNER_DECISIONS

```text
preferred_option = A
reserve_option = B_IF_DISTINCT_DOMAIN_IS_PROVEN
pr_232_disposition = CLOSE_AFTER_EXTRACTION
owner_context_policy = SIDECAR_OWNER_METADATA
live_parity_checkpoint_authorized = true
historical_v3_schema_hash_fix_deferred = true
kt2_authorized = false
```

## Rules

One responsibility has one maintained write authority. A historical,
compatibility, proof, generated, or proposed implementation is never a second
product owner. The allowed dispositions are:

- `KEEP_AS_SOLE_OWNER`
- `REUSE`
- `EXTEND`
- `HISTORICAL_READ_ONLY`
- `PROOF_ONLY`
- `TO_BE_SUPERSEDED`
- `DUPLICATE_DO_NOT_ACTIVATE`
- `REQUIRES_DECISION`

`Producer` means the component that supplies the owner's input, not an
alternate owner. `Consumer` means a declared downstream reader.

## Matrix

| Responsibility | Sole owner | Producer | Consumer | Current duplicates | Required disposition |
| --- | --- | --- | --- | --- | --- |
| `visual_transcription` | `PdfDualVlmRuntimeFactory` + contract validation by `SemanticVisualTableValidatorFactory` | bounded PDF crop intake | `SemanticVisualTableMaterializationFactory` | none | `KEEP_AS_SOLE_OWNER` |
| `logical_table_materialization` | `SemanticVisualTableMaterializationFactory.create` | validated `description + rows` | `Gate2TablePackageFactory`, ArtifactStore | none | `KEEP_AS_SOLE_OWNER` |
| `gate2_table_package` | `Gate2TablePackageFactory.create` | accepted Gate 1 projection | Gate 2 readiness/segmentation | none | `KEEP_AS_SOLE_OWNER` |
| `source_unit_segmentation` | `Gate2SourceUnitSegmenterFactory.create` | Gate 2 readiness | router/domain package builder | none | `KEEP_AS_SOLE_OWNER` |
| `financial_type_authority` | `Gate2FinancialSemanticContractFactory.create` | Financial Semantic Pack contract | candidate compiler, validator/materializer | GOAL 17 Type-First cards in PR #232 reuse this snapshot but add a parallel candidate surface | `REUSE` |
| `product_semantic_classification` | `Gate2DomainSourceFactRuntimeFactory.create` | Gate 2 domain packages | canonical source-fact validator/stitcher | `source_fact_selection_v3`; GOAL 17 Type-First PR #232 | `HISTORICAL_READ_ONLY` for v3; `DUPLICATE_DO_NOT_ACTIVATE` for PR #232 |
| `model_facing_response_schema` | current route contract selected by its admitted runtime; for V6 choice, `Gate2FinancialSemanticV6ChoiceContractFactory.create` | code-owned task/options | canonical parser | GOAL 17 plural plausible-type response profile in PR #232 | `PROOF_ONLY`; reuse its contract idea only in future convergence |
| `semantic_response_parser` | `Gate2FinancialSemanticV6ChoiceContractFactory.create` for V6 semantic choice; current source-fact contract parser for the active broad route | normalized provider result | expansion or source-fact validator | `source_fact_selection_v3` parser; GOAL 17 Type-First parser in PR #232 | `HISTORICAL_READ_ONLY` for v3; `DUPLICATE_DO_NOT_ACTIVATE` for PR #232 |
| `prebound_option_construction` | `Gate2FinancialSemanticV6PacketFactory.create` via `Gate2FinancialSemanticV5ProjectionFactory` | registry/Pack/source projection | V6 choice/linter | GOAL 17 type-card/mapping candidate in PR #232 | `PROOF_ONLY`; future route must `EXTEND` the existing owner |
| `exact_choice_restoration` | `Gate2FinancialSemanticV6ChoiceContractFactory.create` plus the packet-owned private mapping receipt | normalized bounded choice | V6 expansion | GOAL 17 local-key restoration in PR #232 | `PROOF_ONLY`; extract tests, do not activate |
| `reason_derivation` | `Gate2FinancialSemanticV6DecisionExpansionFactory.create` | validated choice and code-owned candidates | canonical validator | GOAL 17 decision-table expansion in PR #232 | `PROOF_ONLY`; future route must `EXTEND` this owner |
| `canonical_financial_validator` | `Gate2FinancialEvidenceValidatedDecisionFactory.create` and `validate_financial_evidence_inputs` | expanded decision + authoritative source package | canonical materializer | none | `KEEP_AS_SOLE_OWNER` |
| `canonical_financial_materializer` | `Gate2FinancialEvidenceMaterializerFactory.create().materialize` | validated financial decision | financial-domain persistence | no admitted duplicate; proposed GOAL 17 callers must reuse it | `KEEP_AS_SOLE_OWNER` |
| `financial_evidence_replay` | `Gate2FinancialSemanticV6DecisionEvidenceFactory` and `replay_financial_semantic_v6_decision` | governed private evidence | audit/qualification comparators | GOAL 17 evidence/replay additions in PR #232 | `PROOF_ONLY`; reuse the authority, not a new framework |
| `answer_context_selection` | `AnswerContextSelectionFactory.create` | completed Gate 2 run + stitch artifacts | final presentation | none | `KEEP_AS_SOLE_OWNER` |
| `artifact_persistence` | `ArtifactStoreFactory` + `ArtifactResolver` | validated domain artifacts | declared gate services | direct filesystem/store reads outside the port are forbidden, not owners | `KEEP_AS_SOLE_OWNER` |
| `gate3_context_manifest` | `Gate3ContextManifestFactory.create` | terminal Gate 2 refs | declared Gate 3 consumers | none | `KEEP_AS_SOLE_OWNER` |
| `release_parity` | `scripts/live_verify_broker_reports_stage2_delivery.py` for read-only verification | committed bundles + live readback | release decision | transport success or stale release reports | `TO_BE_SUPERSEDED` by exact current-head parity evidence before any live acceptance claim |

## Duplicate responsibility register

### Historical `source_fact_selection_v3`

- **Overlap:** semantic classification and response parsing.
- **Current product owner:** the broad canonical source-fact product route
  orchestrated by `Gate2DomainSourceFactRuntimeFactory`.
- **Disposition:** `HISTORICAL_READ_ONLY`.
- **Reason:** it remains useful for frozen replay and compatibility evidence,
  but the product Pipe's containment guard is always false.
- **Forbidden:** new product consumer, valve activation, semantic expansion,
  fallback.

### GOAL 17 Type-First implementation in PR #232

- **Overlap:** model-facing schema, parsing, type-card construction, exact
  restoration, reason derivation, evidence/replay, and a complete second
  semantic execution chain.
- **Current location:** draft PR #232 only; it is not part of `main`.
- **Disposition:** `DUPLICATE_DO_NOT_ACTIVATE`, with reusable contracts and
  tests classified `PROOF_ONLY`.
- **Preserve:** plural plausible-type response, rich Pack-backed type cards,
  local keys with exact restoration, deterministic reason derivation,
  one-call/no-fallback accounting, exact replay/comparator tests.
- **Do not preserve as product route:** synthetic source projection, separate
  product entrypoint, independent request route, production valve or admission.

### Stale live Function bundles

- **Overlap:** they may execute older copies of maintained factory code.
- **Current owner:** committed maintained source and exact generated bundles.
- **Disposition:** `TO_BE_SUPERSEDED` by a separately authorized parity repair
  and atomic release.
- **Debt:** `LIVE_BUNDLE_PARITY_REPAIR_REQUIRED`.

## Sole-owner decisions for future convergence

The future semantic route must reuse the existing visual input, Gate 2 package,
canonical source grounding, canonical financial validator/materializer,
ArtifactStore, and evidence/replay authorities. Pack-backed Type-First may be
added only as an evolution inside the existing source-fact product boundary.
It cannot establish a second product runtime.

No new owner is introduced by KT1.

The machine-readable owner authority is
`docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`. Every matrix
owner must map to that sidecar; the matrix does not authorize an owner that is
absent from it.
