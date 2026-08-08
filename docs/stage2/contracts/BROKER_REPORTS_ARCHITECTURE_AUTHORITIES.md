# Broker Reports Architecture Authorities

Status: `CURRENT`

Classification: `CURRENT SUPPORTING DOC`; this file maps maintained owners and
does not define gate numbering or gate status.

Start at [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md). For Gate 3
or Gate 4 context, read the short
[Gate 3 handoff](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) next. Use the
[Gate 2 implementation map](../architecture/BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md)
and [safe-change guide](../operations/BROKER_REPORTS_GATE2_SAFE_CHANGE_GUIDE.v1.md)
only when the task reaches those implementation surfaces.

This is the compact orientation index for maintained Broker Reports
implementation authorities. Current gate numbering is owned by
[Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md). The older
[global gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md)
is `SUPERSEDED` for numbering and remains migration context only.

Use this order when sources appear to disagree:

1. Pipeline Gates v1 owns gate placement and product boundaries;
2. a versioned contract owns DTO meaning and invariants;
3. the maintained source factory owns object construction or execution;
4. a compatibility entrypoint may only adapt and delegate;
5. generated bundles project maintained source;
6. dated reports and receipts are historical evidence only.

## Documentation authority audit

The repository contains 594 Broker Reports Markdown files that mention the
audited gate, canonical, annotation, NDFL or financial-label terms. They are
classified by ownership and document family; they are not 594 independent
authorities.

| Classification | Documents or family | Rule |
| --- | --- | --- |
| `CURRENT AUTHORITY` | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) | the one current Gate 1-4 map and status owner |
| `CURRENT SUPPORTING DOC` | this map, [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md), [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md), [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md), Gate 2 Exit, Canonical Artifact/Reader and current Gate 3 versioned contracts | explain direct boundaries or own exact DTO/factory meaning; cannot renumber gates |
| `EVIDENCE` | dated reports/receipts, including corrected G3.7C and G3.C5 product-path proof | prove one revision and scope; never a current contract |
| `HISTORICAL` | dated research, proof plans, old current-state snapshots and evidence indexes | retained for audit or investigation only |
| `SUPERSEDED` | `BROKER_REPORTS_GATE_ARCHITECTURE.md`, `BROKER_REPORTS_3NDFL.blueprint.md`, the pre-Gate-3 Domain Map, Contract Flow Mapping and Data Contract Family | old gate meaning is preserved but cannot override Pipeline Gates v1 |
| `STALE / CONFLICTING` | any unqualified claim that current Gate 3 is unresolved, future case assembly or not implemented | must be treated as historical text and routed to Pipeline Gates v1 before use |

Research, proposals, drafts, Skills/Prompts and generated assets are not
architecture authority merely because they contain the same terms. Dated Gate
3 reports remain evidence even when their outcome is terminal. The earlier
G3.7 `NOT_READY` conclusion is superseded by corrected G3.7C evidence.

## Minimal domain responsibility map

| Domain | Owns | Does not own | Public entrypoint | Normative contracts | Allowed consumers | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- | --- |
| Gate 1 Intake | authenticated upload custody, access, format detection, original storage and routing | canonical normalization, financial meaning or product cutover | existing intake/ArtifactStore factories and `ArtifactResolver` | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) | Gate 2 canonical extraction | native document processing, Knowledge/RAG/vectorization or caller tenant authority |
| Gate 2 Canonical | format extraction, deterministic non-financial `CanonicalArtifactV1`, provenance/issues, immutable versions, shared completeness and shadow comparison | product/task-specific LLM projection, financial type/role meaning or product cutover | `FullSourceArtifactFactory`, `CanonicalNormalizerFactory.create`, `CanonicalArtifactStoreFactory.create`, `CanonicalReaderFactory.create` | [Canonical Artifact v1](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md), Storage, Reader and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | shadow/read-only proof and the explicitly authorized NDFL Gate 3 exact-manifest route | a second schema/parser/store/reader, direct component access or canonical product reads outside an authorized route |
| Gate 2 Consumer Compatibility | consumer-specific, versioned structural projection over an active canonical version; aggregate safe read telemetry; one non-active format-neutral proof renderer | global read enable, legacy fallback, private evidence, financial semantics or consumer selection | four explicit factories plus `render_neutral_canonical_projection` in `canonical_consumer_migration.py`, all consuming `CanonicalReaderFactory.create` output | [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md), [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md), [Migration Strategy](./BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md), [Consumer Matrix](./BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md) | isolated Wave 0 tests, retained-cohort proof and shadow-only Wave 2 | format-branch consumer API, direct ArtifactStore/SQLite/payload access, global flag or silent fallback |
| Technical Preparation | deterministic financial scope, technical preclose and sealed Evidence Bundle | financial classification or provider choice | `Gate2DeterministicFinancialScopeFromGate1V2Factory.create`, `Gate2FinancialEvidenceBundleFactory.create` | Evidence Bundle | Candidate Compiler, Qualification | a second source/provenance projection |
| Financial Semantic Pack | type/role meaning, ambiguity rules and lifecycle | source binding, provider transport or materialization | `Gate2FinancialSemanticContractFactory.create` | Financial Semantic Pack | projection, compiler, validation, materialization, Financial Domain | type-specific Python or a second registry |
| Candidate Compiler | complete code-owned Typed Options from Pack plus technical evidence | semantic selection or invented bindings | `Gate2FinancialCandidateCompilerFactory.create` | Candidate Compiler and Typed Option | Semantic Matcher, replay | financial regex, known type IDs or provider-built records |
| Semantic Matcher | current four-block packet, versioned model-visible context boundary and field-eligibility policy, semantic instruction, complete-request lint, provider-neutral minimal choice and deterministic choice expansion | source refs/provenance ownership, Pack/Reason meaning, canonical acceptance or persistence | V6 packet/Prompt/Choice factories, `Gate2FinancialSemanticV6ContextLinterFactory.create` plus additive `create_context_v2_1`, and `Gate2FinancialSemanticV6DecisionExpansionFactory.create` | V6 Packet, LLM Semantic Context, [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), Choice and Expansion | Qualification, Validation, Evidence | model-generated records, copied semantic wording, second packet builder or alternative choice schema |
| Provider Integration | canonical request construction, provider-specific projection, transport response parsing and usage normalization | financial semantics, budget policy or product validation | `Gate2StructuredModelClientFactory.create` using request builder and adapter factories; additive Context V2.1 one-attempt seam remains under that factory | provider-neutral request/choice plus execution metadata contracts and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | maintained runtime and qualification | direct provider request/response parsing outside builder/adapters |
| Budget | pre-transport admission and post-response usage/cost accounting | request shape, provider parsing or semantic verdict | `Gate2EconomyBudgetSessionFactory.create` | economy budget v1 code contract | structured model client | token/cost policy in callers |
| Validation | canonical decision parsing, Pack/Registry/source authority checks and accepted-decision validation | provider adaptation, ID minting or persistence | `Gate2FinancialEvidenceValidatedDecisionFactory.create`, `validate_financial_evidence_inputs` | Generic Financial Materialization | Materialization, Qualification | local validators that weaken the canonical contract |
| Materialization | canonical IDs, bindings, ownership, provenance, retention and terminal coverage | type semantics, provider choice or storage | `Gate2FinancialEvidenceMaterializerFactory.create().materialize` | Generic Financial Materialization | Financial Domain and explicit compatibility projections | materialization in qualification/evidence/consumer code |
| Financial Domain | immutable historical snapshot, bounded query semantics and serialization envelope | current Gate 3 or Gate 4 fact meaning, raw source/provider reads or workflow state | catalog, query and persistence factories | Managed Financial Domain and Query API | historical compatibility only; any later adapter requires its own explicit Gate 4 Goal | direct record catalogs, query facades or snapshot minting presented as current Gate 4 |
| Gate 3 Minimal Labeling Contract | DTO meaning for one canonical-bound projection, sparse label proposal, role proposal and validated annotation sidecar; exact traversal/alias rule and bare-alias model-facing schema projection | dictionary/Role Pack meaning, provider execution, persistence, workflow or activation | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and their closed schemas | current Gate 3 contracts | projection, type pass, role pass, persistence and NDFL workflow | a second target grammar, alias parser/normalizer, rewritten canonical artifact or Financial Domain on the current Gate 3 route |
| Gate 3 Projection | deterministic Markdown and backend-only reversible aliases over the exact active canonical version | source parsing, financial meaning, model execution, storage, workflow or activation | [`Gate3ProjectionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py) via `CanonicalReaderFactory.create().read_active_envelope` | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) and [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) | NDFL product workflow plus retained proofs | raw artifact input, source-format branch, second renderer, projection persistence or model-visible canonical IDs |
| Gate 3 Structural Chunking | ordered bounded model contexts, structural context repetition and exactly-once projection of existing G3.2 targets | financial/keyword selection, model execution, batching, annotation merge, persistence, overlap or product activation | [`Gate3StructuralChunkFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_structural_chunking.py) over the exact package-internal render plan owned by `Gate3ProjectionFactory` | [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md), [Structural Chunk Set schema](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json) and [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) | NDFL product workflow plus retained proofs | second renderer or alias issuer, financial labels/dictionary, arbitrary token windows, row overlap, provider call, ArtifactStore registration or workflow |
| Gate 3 Financial Label Dictionary | exact published label IDs and meanings, immutable version identity, draft/diff/approval/publish-preparation lifecycle and deterministic full model view | source/canonical reads, target selection, provider execution, annotations, workflow or activation | [`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py) loading the exact-file-hash-pinned package resource; generated OpenWebUI Skill/Tool are inspection/delivery projections only | [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) | G3.C1 managed OpenWebUI binding and G3.4 composition | independently authored meaning in Prompt/Skill/Tool/Knowledge/renderer, RAG/lazy retrieval, mutable published version, registry, database or second publisher system |
| Gate 3 Bounded Labeling | pass-1 exact three-part model context, one sparse financial-type proposal, closed response validation and backend-only alias restoration | role binding, deterministic semantic classification, alias normalization, retry/repair/fallback, persistence, workflow or activation | [`Gate3BoundedLabelingFactory.create/create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py) using the existing `Gate2StructuredModelClientFactory.create` provider path | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | Gate 3 role pass through the batch owner | second prompt/dictionary/projection/validator/alias grammar, model-provided canonical refs, code-owned financial classifier or annotation storage |
| Gate 3 Financial Role Pack | exact role IDs/meanings, per-label required/optional profiles, literal source-value policy and maximum-one cardinality | financial labels, source reads, model execution, persistence or relations | [`Gate3FinancialRolePackFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.py) loading the exact hash-pinned package resource | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Role Pack schema](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json) | Gate 3 role pass and persistence validation | role/profile copies in Python, prompt, Skill, adapter, RAG, database or broker-specific mapping |
| Gate 3 Role Labeling | one pass-2 proposal for all validated pass-1 facts in a non-empty chunk, fact/label equality, allowed-role/cardinality checks, target restoration, literal `exact_text` validation and mechanical source-value resolution | relabeling, normalized/computed values, one call per fact, retry/repair/fallback, persistence, relations or Gate 4 | [`Gate3RoleLabelingFactory.create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_role_labeling.py) plus `Gate3RoleValueResolverFactory.create/create_from_active_canonical` in the same module, reusing `Gate2StructuredModelClientFactory.create` and `CanonicalReaderFactory.create` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), Role Pack and role-response schemas | batch owner, persistence and deterministic downstream code | second projection/chunker/provider adapter, broker-column rules, normalized values, relation ontology or parallel sidecar |
| Gate 3 Chunk Batch Labeling | sequential pass 1 then pass 2 per selected chunk, pass-2 skip for empty pass 1, and deterministic in-memory V2 merge | chunk boundaries, label/role meaning, provider adaptation, retry/repair, per-fact calls, persistence or activation | [`Gate3ChunkBatchLabelingFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_chunk_batch_labeling.py) calling the structural, bounded-label and role-label factories | [Chunk Batch Labeling v1](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md) | NDFL product workflow plus retained proofs | second provider/validator/classifier, semantic deduplication, concurrency/retry infrastructure, persistence or product route |
| Gate 3 FinancialAnnotations Persistence | admission of a complete validated document result, exact active canonical/dictionary/Role Pack/instruction/model/provider binding, repeated target/profile/literal checks and immutable private V2 sidecar save/read | labeling, canonical mutation, physical storage, retention/purge policy, workflow or activation | [`Gate3FinancialAnnotationsPersistenceFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_annotations_persistence.py) delegating to `ArtifactStore` and `ArtifactResolver` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) and the existing Artifact Lifecycle contract | NDFL product workflow and artifact-derived G3.6 readiness | incomplete sidecar publication, parallel V1/V2 current writes, second database/store/resolver, mutable overwrite, copied financial meaning, Gate 2 mutation or workflow state |
| Gate 3 NDFL Case Readiness | deterministic per-document/case readiness and fixed follow-up permissions derived from existing artifacts | Gate 3 semantic-system acceptance, persisted workflow state, labeling, financial meaning, tax decisions or Gate 4 execution | [`Gate3NdflCaseReadinessFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_case_readiness.py) through `ArtifactResolver`, active canonical pointers and G3.5 reads | [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md) | inactive G3.6 downstream proof and corrected G3.7C case-status audit | caller tenant/case ids, cross-document labeling, phantom completion, second workflow owner/database or LLM-owned state |
| NDFL Gate 2 to Gate 3 Workflow | exact validated-manifest selection, compare-and-swap activation, full-document Gate 3 coordination and exact sidecar publication | canonical construction, projection/chunk/label meaning, provider adaptation, persistence mechanics, case-readiness meaning or Gate 4 | [`NdflWorkflowFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_workflow.py), delegating every stage operation to its existing factory | [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md), [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) and exact-version sidecar contracts | stable-ID NDFL product route | Gate 2 calling Gate 3, copied canonical/text handoff, Pipe-to-Pipe chat, display-name routing, direct store read/write, retry/repair or second stage owner |
| Gate 4 Financial Case Fact Contract | one minimal immutable fact shape: deterministic identity, trusted case/chat binding, exact Gate 3 artifact/annotation/canonical binding, typed role values with source literals, explicit missing and role completeness status | financial type/role meaning, source parsing, persistence, SQL, multi-document assembly, relations, tax logic, API or activation | [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) and its closed schema | [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) | current G4.2 deterministic materializer and future Gate 4 consumers | a second fact/locator/role schema, historical Financial Domain activation, caller-owned case registry, new ACL/store, broker adapter or type/profile copy |
| Gate 4 Deterministic Materialization and SQL Cache | mechanical V2-to-G4.1 projection, typed normalization, exact fact identity, same-ArtifactStore SQL projection, explicit scoped reads, rebuild and freshness/lifecycle enforcement | financial type/role meaning, source-format parsing, separate storage/ACL/case lifecycle, multi-document reconciliation, relations, tax logic, API or product activation | [`Gate4FinancialCaseMaterializerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py) plus composed [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), reusing Gate 3 resolver/readiness and the existing ArtifactStore adapter | [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) | ordinary deterministic Gate 4 code and future separately approved case assembly | second DB/store/resolver, caller tenant/case IDs, SQL-owned meaning, raw broker reads, provider/LLM calls, generic query language, relations or tax logic |
| Historical Financial Domain Consumer | checked consumption of the historical Financial Domain query API | current Gate 3 type/role route, current Gate 4 facts, Gate 1/Gate 2 storage, source parsing or domain snapshot mutation | `Gate3FinancialDomainContextFactory.create` | Query API and superseded global gate architecture | compatibility/history only | treating the historical consumer as current Gate 3 or Gate 4 authority |
| Qualification | frozen fixture/preflight and slot plan, terminal classification, metrics and product-gate evaluation | product contracts, provider-specific parsing or production admission | V6 qualification fixture/preflight factories, `qualify_financial_semantic_v6`, and additive `Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory` / thin coordinator | V6 qualification harness, execution identity and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification CLIs and Evidence | a parallel qualification framework |
| Evidence | exact private execution evidence, safe receipts, integrity and offline replay | product decisions, retries or canonical request construction | `Gate2FinancialSemanticV6DecisionEvidenceFactory.create`, additive Context V2.1 local/live success/failure methods, and their versioned restore/replay entrypoints | V6 Exact Evidence and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | Qualification and offline audit | evidence-driven product mutation or raw private Git evidence |
| Compatibility | version-pinned read dispatch and explicit legacy validation | silent rewrite, new writes, semantic policy or current product logic | financial-evidence and successor compatibility factories | pinned legacy/successor schemas | migration/local-proof tooling | reimplemented current authorities behind a legacy facade |

These domains are code responsibilities, not new product gates or packages.
One domain may coordinate several distinct operation authorities listed below;
that does not permit a second owner for any operation.

Rows using historical `Gate2*` financial-semantic class/module names below are
legacy code-identity maps, not current gate-number definitions. Under Pipeline
Gates v1, product/task-specific LLM-friendly projection, sparse financial-type
labeling and source-bound role labeling belong to the current Gate 3 contour.
The current batch performs one type proposal and, when facts exist, one role
proposal per chunk. G3.C5 activates these owners only inside the stable NDFL
product route. DOC33's neutral reader-only renderer remains completeness proof
tooling, not a product or persisted stage output.
DOC27 likewise creates no Gate 3 projection and switches no background or
primary product consumer.

## Operation authority map

| Concern | Sole authority | Contract | Consumers | Compatibility | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- |
| Gate 2 whole-document canonical construction | [`CanonicalNormalizerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_artifact.py) consuming only Gate 1-authorized refs, FullSource outputs and validated table projections | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md), [Canonical Artifact v1](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md), [schema](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json) and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | controlled Gate 2 shadow write and compare | `gate2_handoff_v0` remains product compatibility authority; DOC23/DOC24 are regression evidence, not runtime owners | a second schema/parser, financial fields, provider output as canonical authority or direct consumer construction |
| Gate 2 canonical version lifecycle and private read | [`CanonicalArtifactStoreFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) delegating to the ArtifactStore-created adapter; [`CanonicalReaderFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) stays disabled by default and is enabled only for explicit consumers | [Canonical Storage Lifecycle v1](./BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md), [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | controlled shadow/storage proof and stable NDFL exact-manifest product route | immutable cross-run versions, chunks, CAS activation/rollback and receipts are additive; source and legacy handoff remain resolvable | direct SQLite/file access, caller tenant identity, overwrite, implicit promotion or reads outside an authorized consumer |
| Consumer-specific canonical compatibility read | [`Gate1ArtifactStoreCanonicalAdapterFactory`, `PdfCompactCanonicalAdapterFactory`, `LocalPdfCompactResearchCanonicalAdapterFactory` and `render_neutral_canonical_projection`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_consumer_migration.py), all consuming `CanonicalReaderFactory.create` output | [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md), [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) and [Consumer Migration Matrix v1](./BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md) | isolated Wave 0 tests, retained-cohort proof and six Wave 2 shadows | each mapping has one flag/output version; the neutral renderer is non-active proof-only; flag-off rollback restores external legacy authority without changing active pointer | direct store/component reads, format-branch consumer API, one global flag, private evidence, silent fallback or primary product use |
| Gate 3 current DTO meaning | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) plus [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), shared target/projection, both response schemas and [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | projection, type pass, role pass, persistence and NDFL workflow | V1 label-only payload remains historical and immutable; current writes use V2 | a second locator grammar, model-provided canonical refs, rewritten canonical source, parallel sidecar or Financial Domain on the current route |
| Gate 3 projection construction | [`Gate3ProjectionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py) calling [`CanonicalReaderFactory.create().read_active_envelope`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) and [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) | NDFL product workflow plus retained G3.2/G3.4 proofs | DOC33 neutral renderer remains independent proof tooling; no source-format or storage-layout branch | direct artifact input, a second alias issuer/renderer, raw/private reads, projection persistence, provider call or another product route |
| Gate 3 structural chunk construction | [`Gate3StructuralChunkFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_structural_chunking.py) reusing the exact package-internal structural plan of `Gate3ProjectionFactory` | [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md), [Structural Chunk Set schema](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | NDFL product workflow plus retained G3.4B proofs | exact 60,000-character default bound, whole natural units first, contiguous whole-row groups only, zero data-row overlap and exactly-once existing target mappings | semantic/keyword filtering, second renderer/alias authority, tokenizer infrastructure, provider/batching/merge/persistence or another product route |
| Gate 3 financial-label dictionary lifecycle, rendering and managed binding | [`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py) loading [`gate3_financial_label_dictionary.v1.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json) through package resources and one exact file-hash pin; the deterministic managed-assets builder and stable-ID publisher project it to OpenWebUI | [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) | G3.C1 operator inspection through Skill `broker-reports-financial-labels`, exact byte delivery through Tool `broker_reports_financial_label_dictionary`, and runtime context construction through the same factory | Skill is generated from the exact model view, Tool embeds the exact verified resource bytes, no Prompt carries definitions and Knowledge/RAG is absent | second meaning owner, name-based lookup, workspace path import, RAG/lazy load, unreviewed activation, overwrite, provider call or annotation persistence |
| Gate 3 bounded semantic-label proposal and validation | [`Gate3BoundedLabelingFactory.create/create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py) composing the exact projection/chunk, published dictionary, versioned minimal instruction and response schema, then calling the existing `Gate2StructuredModelClientFactory.create` seam | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | NDFL product workflow plus retained G3.4 proofs and human review | schema description and instruction project the sole G3.1/G3.2 alias grammar; empty annotations are valid; omissions remain non-claims; only exact validated aliases are restored | regex/keyword classifier, alias repair/extraction, copied dictionary meaning, hidden history/metadata, retry/repair/fallback, canonical refs from the model, persistence outside its owner or another product route |
| Gate 3 financial Role Pack | [`Gate3FinancialRolePackFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.py) over one hash-pinned package resource | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Role Pack schema](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json) | role pass and persistence | exact dictionary-label coverage is validated; model view is generated from the pack | role/profile definitions in Python, prompt, Skill, adapter, RAG or database |
| Gate 3 source-bound role proposal and validation | [`Gate3RoleLabelingFactory.create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_role_labeling.py) and mechanical `Gate3RoleValueResolverFactory.create/create_from_active_canonical` in the same module | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), role response schema and FinancialAnnotationsV2 | batch, persistence and downstream deterministic code | uses the existing three-message request builder/adapter path and same chunk aliases; empty pass 1 skips provider | relabeling, normalized/computed values, broker-column rules, per-fact calls, retry/repair/fallback or Gate 4 logic |
| Gate 3 chunk batch labeling and merge | [`Gate3ChunkBatchLabelingFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_chunk_batch_labeling.py) over exact chunks, pass-1 bounded labeling and pass-2 role labeling | [Chunk Batch Labeling v1](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md) | NDFL product workflow plus retained proofs | a selected subset is never complete; any pass rejection/failure makes the result incomplete; empty pass 1 skips pass 2; V2 merge preserves deterministic order | changed chunk/dictionary/Role Pack baseline, direct provider call, per-fact call, retry/repair/fallback, semantic dedup, concurrency, persistence outside its owner or another route |
| Gate 3 FinancialAnnotations sidecar save/read | [`Gate3FinancialAnnotationsPersistenceFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_annotations_persistence.py), delegating record writes to the injected ArtifactStore, reads/access to `ArtifactResolver` and active canonical value checks to `Gate3RoleValueResolverFactory.create_from_active_canonical` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) and [Artifact Lifecycle](./BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md) | NDFL workflow and artifact-derived readiness | only a complete all-chunk V2 result is admitted for new writes; historical V1 remains readable; fact and role targets, profiles and exact text are rechecked; provider stays immutable envelope metadata | direct SQLite/files, parallel V1 current write, new DB, partial write, active-version mismatch, alias persistence, semantic repair or activation outside NDFL |
| Gate 3 NDFL case-readiness derivation | [`Gate3NdflCaseReadinessFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_case_readiness.py), reading case metadata through `ArtifactResolver` and sidecars through the G3.5 owner | [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md), [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) and ArtifactStore access scope | inactive G3.6 downstream proof and corrected G3.7C case-status audit | state is recomputed; only an exact current-canonical sidecar is ready; stale/incomplete records are explicit; declaration preparation is a fail-closed permission only; current-case completion is not Gate 3 system acceptance | direct SQL/files, caller-provided tenant/case identity, persisted state, event sourcing, cross-document labeling, provider call or Gate 4 execution |
| NDFL Gate 2 to Gate 3 handoff and execution | [`NdflWorkflowFactory.create().run_product_path`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_workflow.py) resolving one exact manifest through `CanonicalReaderFactory.read_envelope`, compare-and-swap activating it when needed, calling `Gate3ChunkBatchLabelingFactory.create`, then `Gate3FinancialAnnotationsPersistenceFactory.create` | [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md), [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) and [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md) | single stable-ID NDFL product route plus exact-version tests | the exact manifest ref selects the Gate 2 result; only `document_id` plus authenticated `ArtifactAccessContext` enters downstream Gate 3; post-label version/root/payload equality is required | Gate 2 import/call, document payload transfer, direct ArtifactStore access, name lookup, Pipe-to-Pipe chat, incomplete persistence, retry/repair/fallback, another product route or Gate 4 |
| Gate 4 deterministic fact materialization | [`Gate4FinancialCaseMaterializerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py), reading V2 through its persistence owner, resolving values through `Gate3RoleValueResolverFactory.create_from_active_canonical` and profiles through the exact Role Pack factory | [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md), [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) | composed G4.2 runtime and direct ordinary-code materialization | exact ISO/DMY date and ungrouped dot/comma decimal grammars only; source literal remains exact; missing is preserved | source-format/broker adapters, label/role choice, guessed locale/grouping, copied profiles, LLM, relations or tax meaning |
| Gate 4 SQL cache rebuild and explicit reads | [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), composing the materializer and `Gate4FinancialCaseSqlCacheFactory.create` over the existing `SqliteArtifactStoreAdapter` | [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md), [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) and Artifact Lifecycle | ordinary code queries by case, fact ID, financial type, asset and period | exact current selection comes from `Gate3NdflCaseReadinessFactory`; cached generations fail closed; upstream lifecycle triggers delete projections; cache can be removed/rebuilt | second database, direct global DB handle, caller tenant/case scope, cache as source of truth, ORM/event store, generic query API, product route, relations or tax logic |
| PDF table candidate -> canonical crop region | [`PdfTableRasterFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/pdf_table_raster.py) | [PDF Table Intake Gate 1 v2](./BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v2.md) | PDF Table Intake runtime, image crop, future source-text projection, provenance and diagnostics | `render_detected_region` delegates; v1 fixed-padding evidence remains historical; legacy padding valves are accepted but not applied | consumer-local crop/padding, a second resolver, issuer/table/page-coordinate exceptions, provider-owned final geometry or semantic reconstruction in the crop owner |
| Inactive Managed Document v2 validation and sealing | [`ManagedDocumentContractV2Validator`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_contracts_v2.py) | [Managed Document v2](./BROKER_REPORTS_MANAGED_DOCUMENT.v2.md) and its exact-`$id`, canonical-SHA-pinned [Draft 2020-12 schema](./BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json) | inactive DOC6 document builder, contract tests and offline parity | additive only; Managed Document v1 validator/schema/bytes remain unchanged | a weaker local validator, same-`$id` schema substitution, schema rewrite in a builder, implicit v1-to-v2 upgrade or validator-owned source recovery |
| Inactive DOC6 logical-row table recovery | [`LogicalRowTableFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/logical_row_table_recovery.py) | [Managed Document v2](./BROKER_REPORTS_MANAGED_DOCUMENT.v2.md) and [DOC6 logical-row decision](../BROKER_REPORTS_DOC6_LOGICAL_ROW_MODEL_DECISION.v1.md) | `ManagedPdfDocumentV2Factory` only, then the v2 validator | consumes only established FullSource PDF projections/observations; historical grid and visual-table paths remain unchanged | grid/cell/span-first canonical builder, parser-owned TABLE emission, helper-built TABLE or source-specific hardcoding |
| Inactive PDF -> Managed Document v2 orchestration | [`ManagedPdfDocumentV2Factory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/managed_pdf_document_v2.py) | [Managed Document v2](./BROKER_REPORTS_MANAGED_DOCUMENT.v2.md); public builder input is raw PDF bytes plus a required private source-artifact identity, followed by internal FullSource invocation and sole-complete-projection consumption | offline DOC6 recovery proof and row-oriented view only | additive non-product contour; v1 `ManagedPdfDocumentFactory`, FullSource owner, product routes and generated bundles stay unchanged | caller-supplied parallel projection, raw-PDF parallel parser, direct `LogicalRowTableFactory` consumer, unvalidated v2 artifact or product-route bypass |
| Inactive LLM Document View v2 projection | [`ManagedDocumentLlmViewV2Factory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_llm_view_v2.py) | [LLM Document View v2](./BROKER_REPORTS_LLM_DOCUMENT_VIEW.v2.md) over validated [Managed Document v2](./BROKER_REPORTS_MANAGED_DOCUMENT.v2.md) | offline independent auditor and DOC6 parity only | deterministic derived view; v1 view and current model/request paths remain unchanged | view built from PDF/parser output, renderer inference/repair, private geometry/model input or provider-owned projection |
| Independent LLM Document View v2 audit | [`ManagedDocumentLlmViewV2Auditor`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_llm_view_audit_v2.py) | [LLM Document View v2](./BROKER_REPORTS_LLM_DOCUMENT_VIEW.v2.md) | DOC6 parity/evidence | reads and reconstructs View v2 bytes independently; imports neither renderer nor Managed Document validator and cannot construct or repair either representation | renderer-shared audit logic, snapshot-only approval, audit repair or private-field allowlisting |
| Independent Managed Document v2 -> View v2 parity | [`managed_document_llm_view_parity_v2`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_llm_view_parity_v2.py) | sealed, inner-hashed checklists over independently supplied Managed Document v2 and audited View v2 surfaces | DOC6 offline parity/evidence only | checklist comparison reads neither PDF nor renderer internals; exact equality is required for every declared dimension | renderer-owned comparison, unchecked inner inventories, snapshot-only equality or calling row-only parity whole-document parity |
| Prompt ownership | [`financial_semantic_v6_prompt`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_prompt.py) | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) | request builder, qualification | version-pinned older prompts only | semantic instruction in request, adapter or runner |
| Managed model-facing asset-family identity and composition | additive [`broker_reports_financial_domain_assets.v3.manifest.json`](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v3.manifest.json), immutable v1/v2 predecessors, their one deterministic builder and single closed-world `load_gate2_financial_semantic_model_assets` entrypoint | [OpenWebUI Financial Domain Asset Family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md), historical [family v2](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v2.md) and [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) | active v1 consumers, historical non-active Context V2.0 assets and the non-active GOAL 7 minimal managed profile | family v1/v2 and Context V2.0 remain immutable; family v3 packages catalog v2 and identifies one transport-ineligible profile without changing full Pack/catalog bytes | parallel asset-family/manifest authority, in-place historical manifest rewrite, second catalog loader, financial-semantic registry, custom asset GUI or adapter-owned semantic text |
| Human decision-reason meaning | immutable historical [`broker_reports_gate2_financial_decision_reason_catalog.v1.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.json) plus additive inactive [`broker_reports_gate2_financial_decision_reason_catalog.v2.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v2.json), each under the same catalog ID and versioned validator boundary | [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md), [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) and [family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md) | v1 remains the historical non-active [Context V2.0 candidate](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md); family v3 packages v2 for the inactive minimal projection and Choice-owned V2.1 profile | active V6 decision/Choice still accepts only two reasons; the inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) accepts all three without activation | human wording in Python, Prompt, Packet, adapter, report projector, Pack, an in-place catalog edit or a second active catalog/loader |
| Model-visible semantic context | [`Gate2FinancialSemanticV6PacketFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py); managed Pack/reason subprojection remains [`Gate2FinancialSemanticV5ProjectionFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v5_projection.py) | implemented historical [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md), historical non-active [Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md), current non-active [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md), [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), and [current V6 Packet](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md) | the historical active request-builder path consumes only active `packet.payload`; the current Packet path builds one V2.1 candidate plus private exact receipt from the GOAL 7 projection; inactive Choice/Linter paths and the additive zero-call request-builder proof path consume exact V2.1 artifacts | V2.1 candidate, Choice profile, sealed provider-neutral request and local provider projections are all `active=false` and transport-ineligible; current four-block V6 packet stays exact | second Packet/context/projection builder, per-request historical V2.0 construction, unallowlisted model-visible field or provider-side semantic context rewrite |
| Complete model-visible request lint | [`Gate2FinancialSemanticV6ContextLinterFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) for historical Slim plus additive [`create_context_v2_1`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) under the same authority | implemented [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)/[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md) and current non-active [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md) constrained by the [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md) and [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | exact version-pinned provider-neutral request before provider projection/transport | historical `create` unchanged; `create_context_v2_1` consumes exact Prompt, candidate, private mapping receipt and Choice-owned schema, then emits a private sealed-request receipt without inventing schema | direct candidate transport, a second packet/Choice/linter authority, context repair, an unsealed request, a linter that cements V2.0, or linter-built/invented Choice schema |
| Provider transport-request construction | [`Gate2OpenWebUIRequestBuilder.build`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py) plus additive `build_from_sealed_context_v2_1` under the same owner | provider/model request profiles consuming an already linted logical request | structured model client; GOAL 11 zero-call proof; GOAL 12 immutable plan/client | historical profiles validate then delegate; local proof remains transport-ineligible; the GOAL 12 profile attaches only its frozen exact model ID and `stream=false` before budget/adapter controls | direct `form_data` assembly in evidence or qualification, or provider fields added by the Context Linter |
| Provider response-format projection | [`Gate2ProviderAdapterFactory.create`, adapter `prepare_form_data`, and `Gate2PreparedProviderRequest.validate_schema_binding`/`canonical_schema_is_bound` plus versioned Context V2.1 binding methods](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | canonical choice schema projected to the provider-supported subset | structured model client; GOAL 11 zero-call proof; GOAL 12 immutable plan/evidence replay | provider profile selects one adapter; each Context V2.1 binding rebuilds the complete request through the canonical builder, budget where applicable and exact repository adapter/profile, then requires whole-object equality across messages, model, top-level shape, metadata, complete schema projection, wrapper/name/strictness, transform count and hashes | provider-layout parsing or schema rewrites in request, qualification, evidence, report or build code |
| Provider response parsing | [`Gate2ProviderAdapterFactory.create`, legacy adapter `extract_content` / `provider_error_code`, and versioned Context V2.1 prepared-content methods](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2StructuredModelResult`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) or exact Context V2.1 candidate content | structured model client; GOAL 11 zero-call proof; GOAL 12 live evidence path | legacy active extraction is unchanged; candidate extraction first proves exact prepared-request binding and requires one terminal envelope: `finish_reason=stop` for OpenAI/Google or `stop_reason=end_turn` for Anthropic | provider payload parsing in qualification or product code, or candidate extraction from an unbound/non-terminal/multiple-result envelope |
| Provider usage normalization | [adapter `execution_metadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2ProviderExecutionMetadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | model client, budget, evidence | adapter normalizes provider variants | provider token-field reads outside adapters |
| Budget admission/accounting | [`Gate2EconomyBudgetSessionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_budget.py) | economy budget v1 code contract | structured model client | none | token or cost policy in callers/adapters |
| Semantic Pack meaning | [`Gate2FinancialSemanticContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_contract.py) | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | projection, compiler, validator, materializer, Financial Domain | V5-named projection is shared by V6 | financial type IDs, roles or ambiguity rules in Python |
| Evidence Bundle | [`Gate2FinancialEvidenceBundleFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_bundle.py) | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | compiler, packet, expansion, replay | none | second sealed source/provenance projection |
| Typed Option compilation | [`Gate2FinancialCandidateCompilerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py) using [`Gate2FinancialTypedOptionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_typed_option.py) | [Candidate Compiler](./BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md), [Typed Option](./BROKER_REPORTS_GATE2_FINANCIAL_TYPED_OPTION.v1.md) | packet, qualification, replay | none | financial regex, known type IDs or provider-built options |
| Semantic choice | [`Gate2FinancialSemanticV6ChoiceContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py) | active [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md), historical [Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md), inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | active request builder/expansion/evidence; inactive V2.1 linter and GOAL 11 local adapter proof | active exact-ID bytes and historical Local v1 remain pinned; V2.1 restores only through its private receipt and public validation pins exact model-order schema bytes | alternative Choice factory/schema authority, index-derived restoration or model-generated records/bindings |
| Canonical decision expansion | [`Gate2FinancialSemanticV6DecisionExpansionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py) plus additive `create_from_context_v2_1_candidate` under the same owner | [V6 Expansion](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_EXPANSION_V6.md) and inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | materializer, qualification, replay, GOAL 11 local proof | active path remains byte/hash exact; candidate path alone accepts the third V2.1 reason and still delegates to the canonical validator | choice-to-record expansion in runner/evidence code |
| Validator | [`Gate2FinancialEvidenceValidatedDecisionFactory.create` and `validate_financial_evidence_inputs`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | materializer, qualification, local proofs | legacy validators remain version-pinned | weaker local acceptance or provider output as authority |
| Materializer | [`Gate2FinancialEvidenceMaterializerFactory.create().materialize`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | Financial Domain, explicit compatibility projections | projections read canonical output | ID, binding, provenance or retention minting elsewhere |
| Persistence | [`Gate2FinancialDomainPersistenceFactory.serialize/restore`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_persistence.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | local proof, future storage adapter | restore validates the current envelope | a storage adapter reimplementing serialization or minting snapshots |
| Financial Domain snapshot | [`Gate2FinancialDomainCatalogFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_catalog.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | query and persistence factories | explicit legacy/successor readers only | direct record catalogs or mutable snapshots |
| Historical Financial Domain Query API | [`Gate2FinancialDomainQueryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_query.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) | historical Financial Domain consumer | none | treating query results as current Gate 3 labeling input or adding facades over raw records/sources |
| Historical Financial Domain consumer | [`Gate3FinancialDomainContextFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_domain_context.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) and superseded global gate architecture | compatibility/history only | legacy context manifest remains separate | current Gate 3 authority, ArtifactStore, Gate 1 reader or provider access |
| Qualification result | [`qualify_financial_semantic_v6`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_qualification_run.py) plus additive [`Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory` and thin coordinator](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_v2_1_budget_smoke.py) | [V6 Qualification Harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification CLI, safe receipt and transparent synthetic report | older runners are replay-only; GOAL 12 cannot admit production | parallel result classifier or production admission |
| Evidence storage and local replay | [`Gate2FinancialSemanticV6DecisionEvidenceFactory` Context V2.1 local/live methods and the versioned private-evidence serialize/restore/replay entrypoints](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py); additive zero-call composition [`Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` and canonical proof validator](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_v2_1_provider_proof.py); atomic external private checkpointing in the [GOAL 12 CLI](../../../services/broker-reports-gate1-proof/scripts/live_gate2_financial_semantic_v6_context_v2_1_three_provider_smoke.py); public synthetic projection/aggregate and privately issued case evidence under [`Gate2FinancialSemanticV6TransparentSmokeReportFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_smoke_report.py) | [V6 Exact Evidence](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md) and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification, offline audit, synthetic smoke/provider report | replay restores serialized private evidence and checks the validated sealed request, trusted plan/profile, projection policy, exact rebuilt prepared request and schema before reconstruction; private actual evidence stays outside Git; safe reports contain only approved synthetic evidence, hashes, verdicts and metrics | raw private evidence in Git, public case projection treated as issued evidence, raw or resealed proof dictionaries as report authority, actual-corpus transparent projection, evidence-driven product mutation, retry or production admission |

## Duplicate, compatibility and history findings

- No proven active duplicate owns the same maintained product operation.
- `financial_semantic_v6_canonical_request` validates V6 inputs and delegates to
  `Gate2OpenWebUIRequestBuilder.build`; it is a wrapper, not a second builder.
  It is marked `COMPATIBILITY_WRAPPER_DELEGATES_ONLY` and has a delegation test.
- `Gate2FinancialSemanticV5ProjectionFactory` is intentionally consumed by V6.
  Renaming or replacing it would create migration risk; document the
  cross-version ownership instead of creating a V6 copy. Keep it as the one
  shared maintained projection authority.
- `gate2_financial_evidence_compatibility.py`,
  `gate2_financial_evidence_legacy_validation.py` and
  `gate2_successor_compatibility.py` are active compatibility readers. Their
  readers are marked `COMPATIBILITY_WRAPPER_DELEGATES_ONLY` and delegate to
  canonical or pinned validators. The pinned legacy validator is explicitly a
  `HISTORICAL_VERSION_PINNED_AUTHORITY`; it is read-only and cannot define
  current meaning or writes.
- `gate3_context_manifest.py` is the legacy bounded Gate 2 handoff root;
  `gate3_financial_domain_context.py` is the historical Financial Domain
  successor consumer. Neither is the current Gate 3 type-and-role authority. The
  historical consumer remains forbidden from importing the legacy manifest or
  Gate 1 readers.
- `openwebui_actions/*_bundled.py` are generated closed-world projections.
  `scripts/build_openwebui_pipe_bundle.py` and maintained package/action
  sources own their content; bundle files must not be edited as authorities.
- Files under `docs/reports/**`, benchmark sealed results and committed safe
  receipts are immutable historical evidence. They may identify a past
  revision but never override maintained code or contracts.
- V5 and earlier qualification runners remain readable for historical replay
  and version-pinned tests. New V6 work must not extend them as current
  qualification authority.

## Managed Semantic Decision Context GOAL 0 authority audit

The existing
[OpenWebUI Financial Domain Asset Family](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v1.md)
is the sole reusable managed-asset mechanism for the next context program.
It already pins one Skill, one Prompt, one exact Semantic Pack Tool, the Pack
dependency and their composition in one manifest. The program must extend this
family; it must not create another registry, packet builder, parallel
asset-family/manifest authority or GUI framework. New immutable version
manifests inside the selected family remain allowed and required.

Concern ownership is fixed as follows:

| Concern | Owner and required placement |
| --- | --- |
| financial type semantics | the existing Financial Semantic Pack; no Prompt, adapter or runner copy |
| decision reason semantics | the closed code set remains in Choice/decision contracts; human meanings live in one versioned catalog dependency inside the same managed asset family, not a second registry or Pack |
| model-visible presentation | the managed Skill/Prompt plus the existing V6 packet owner's versioned context projection |
| exact refs, provenance, aliases, bindings, retention and materialization | existing backend authorities; never managed semantic content |
| future asset-version lifecycle and active pointer | a planned extension of the selected asset-family version manifest and release receipt will select one immutable active version; no family active pointer exists today |

The repository and pinned OpenWebUI `v0.9.6` provide only a partial lifecycle
today:

- the asset-family manifest provides semantic versions, exact Git-blob hashes,
  deterministic composition and inactive target status;
- native OpenWebUI Prompt records provide history entries, a production-version
  pointer, active toggling and restoration of a selected history version, but
  every update overwrites the current Prompt row content even when
  `is_production=false`; this is not an isolated runtime-safe draft;
- native Skill records expose content and active state plus API update/toggle
  operations, but no version history or restore endpoint;
- native Tool records expose content plus an overwrite update operation, but no
  version history or active-version selector;
- the repository atomic stage release snapshots every Function/Prompt field it
  mutates and proves exact snapshot restoration during rollback rehearsal, but
  candidate readback is only a contracted projection and automatic failure
  restoration has a known pre-`modified` loader window; it does not publish or
  restore the Skill/Tool/Pack family, and direct Prompt-row updates do not
  create native Prompt history.

Primary upstream evidence for the pinned distribution:

- [Prompt version/history/production fields](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L23-L93),
  [current-row update with conditional history creation](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L481-L554)
  and [selected-version restoration](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L585-L622);
- Prompt [version-selection](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L360-L397),
  [active-toggle](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L454-L492)
  and [history-read endpoints](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L533-L616);
- [Skill fields](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/skills.py#L20-L52),
  [Skill API update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L253-L320)
  and [toggle endpoint](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L376-L410);
- [Tool fields without version or activation state](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L20-L52)
  and [Tool overwrite update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L291-L304).

Therefore isolated draft storage, hardened full candidate readback/rollback
and a complete family-level `draft → validated → active → retired → rollback`
publisher are explicit implementation gaps, not a second authority to invent
in GOAL 0. Later work must extend the existing manifest/release contour and may
reuse the existing OpenWebUI Workspace GUI/API only as an
authoring/inspection surface behind that guarded lifecycle. Until exact
readback and rollback exist for the full family, the managed assets remain
non-active and the current V6 route remains unchanged.

## Managed Semantic Decision Context GOAL 1 catalog status

GOAL 1 adds one immutable same-family draft:

- family v2 keeps `family_id=broker_reports_gate2_financial_domain_assets`,
  advances only the family semantic version to `1.1.0`, and remains
  `runtime_activation=false`;
- all v1 Skill, Prompt, Tool and Pack assets remain byte-exact; GOAL 4 later
  changes only the generated container bytes additively to package the inactive
  snapshot, while the default active semantic/default loader payload remains
  exact;
- the decision contract remains the sole reason-code owner;
- the
  [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md)
  becomes the sole human-meaning owner;
- its build-time factory derives the code set from the maintained decision
  source, generates the strict schema and checks meaning-field completeness,
  reciprocal contrasts, non-overlapping boundaries and canonical integrity;
- draft rollback discards v2 without runtime mutation; the exact immutable v1
  manifest is pinned as the prior baseline.

This establishes a GUI-ready repository asset, not live GUI publication.
Full-family publishing/readback/rollback remains the lifecycle gap above.
The catalog is not visible on the active model route. Managed Semantic
Decision Context GOAL 4 projects it only into the non-active Context V2.0 packet
sidecar; this does not claim compatibility with frozen V6 expected answers,
especially for cases whose current active packet exposes no type cards.

## Managed Semantic Decision Context GOAL 2 alias audit

The
[alias necessity and readability audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL2_ALIAS_NECESSITY_AND_READABILITY_AUDIT.report.md)
changes no operation authority. It refines only the requirements for a future
versioned projection inside the existing packet and Choice owners:

- a local value or structural reference is visible only when another
  model-visible field consumes it;
- exact refs and the complete binding table remain Evidence Bundle, Candidate
  Compiler and Typed Option authority;
- deterministic local keys are paired with readable evidence-owned labels;
- readable type and choice labels come from the existing Financial Semantic
  Pack title; Context V2.0 uses no choice-label qualifier because relationships
  already carry the evidence distinction;
- Context V2.0 versioned/extended the existing type-card projection to carry
  Pack title; packet code may not read the asset through a bypass;
- positional `A/B` and numeric `TN` are not future semantic label
  authorities, though unique local response/cross-reference keys remain
  required;
- semantically indistinguishable choices remain distinct by key;
  `unclassified` is truthful for two or more plausible distinct types, while
  same-type indistinguishability hits the explicit count-one compatibility
  stop; only mapping/integrity defects are technical failures;
- provider adapters perform no naming, binding filtering or semantic repair.

The 10-case frozen census records 45 value aliases, 20 structural aliases, 12
type aliases, 12 choice aliases and 59 visible bindings. Twenty-two value
aliases and 14 structural aliases have no inbound reference. Only five
`source_label` relations and six printed-label-evidence predicates distinguish
options. Factoring common eligibility relationships yields 35 readable
relations and removes 24 duplicate occurrences; all 59 exact bindings remain
backend-owned and reconstructable.

The GOAL 2 census above was documentation-only. Managed Semantic Decision
Context GOAL 4 now implements its factoring and mapping rules as a non-active
packet sidecar. The active V6 payload, Choice and request/provider route remain
unchanged; V2.0 runtime activation and provider calls are zero, and the four
zero-option expected-answer concerns remain an explicit compatibility stop.

## Managed Semantic Decision Context GOAL 3 contract

The versioned
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
closed the historical completeness-candidate model-visible boundary in GOAL 3:

- the current system Prompt, generic task, option order, Pack wording and
  reason wording are unchanged;
- the available type set comes from active Pack/Registry contracts compatible
  with the Evidence Bundle source family; Compiler Typed Options and blocked
  bindings are only a private parity signal, so a zero-choice semantic case no
  longer implies zero type meanings in the V2.0 completeness view;
- type titles/definitions/distinctions come only through a versioned extension
  of the existing Pack projection;
- complete human-readable reason cards come only from the managed catalog;
- repeated option bindings become factored readable relationships with an
  explicit local-choice subset when they are not global, while the exact
  complete binding table remains private;
- `value_N`, `type_N` and `choice_N` keys are request-local and separate from
  readable labels; structural keys appear only for necessary cross-reference;
- the packet-owned private mapping receipt binds every visible
  key/relationship and every hidden exact binding to existing Registry,
  Evidence Bundle, Compilation and Typed Option authorities without importing
  Prompt or Choice; the historical V2.0 design assigned separate complete
  Prompt + Context + response-format sealing to the existing Context Linter,
  but that extension was not implemented.

## Managed Semantic Decision Context GOAL 4 non-active implementation

Managed Semantic Decision Context GOAL 4 consumes that contract only inside
the existing packet authority. The single managed-assets loader packages an
inactive candidate snapshot; the existing projection owner produces
Pack/reason projections; and the packet factory returns the deterministic V2.0
candidate plus private mapping receipt. The V2.0 Choice profile,
complete-request linter, request route, provider compatibility,
persistence/replay and benchmark compatibility remain unimplemented or
unproven. Count `1` remains outside the two reason boundaries. Provider calls
and runtime activation remain zero.

Repository-safe implementation evidence:

- [analytical report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.report.md);
- [safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.receipt.safe.json).

## Minimal Semantic Model Surface GOAL 5 contract

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes Context V2.0 as the field-eligibility policy for the current
non-active
[Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
Context V2.0 remains exact, implemented, non-active, version-pinned
completeness evidence; GOAL 8 does not rewrite its bytes or historical
receipts.

GOAL 5 is documentation-only. It changes no Prompt, Pack, reason catalog,
managed asset, projection, Packet, Choice, linter, request/provider route,
expected answer or runtime byte. The ordered successor program is:

1. GOAL 5 defines the minimal field allowlist, default-forbidden fields,
   field-by-field necessity and exact managed-string selection rules;
2. GOAL 6 audits outcome taxonomy, the count-one stop and frozen benchmark
   expectations;
3. GOAL 7 implements the exact versioned minimal managed projection through
   the existing Pack/reason projection and loader authorities;
4. GOAL 8 builds only one non-active Context V2.1 candidate plus private
   mapping receipt in the existing Packet factory;
5. the later governing program separately authorizes GOAL 9 to add one
   versioned inactive V2.1 response profile/parser in the existing Choice
   authority;
6. GOAL 10 adds only the V2.1 linter/budget guard and provider-neutral sealed
   request through additive `create_context_v2_1`, consuming the P01-P18
   Prompt, Packet candidate, mapping receipt and Choice-owned schema;
7. GOAL 11 proves OpenAI, Anthropic and Google projection plus extraction,
   materialization, persistence/restore and exact replay on four synthetic
   fixtures with zero provider calls;
8. GOAL 12 froze one budget candidate per provider and at most 12 live
   qualification slots under the existing owners, using exact direct-provider
   transport resolved from the enabled OpenWebUI connection, a committed
   pre-call plan, exact open-PR/Actions provenance and one-shot external
   execution claims; the run completed with `8` submissions, OpenAI and
   Anthropic semantic failures, and four Google pretransport failures;
9. **STOP before GOAL 13:** GOAL 12 produced no eligible provider/model.
   Further attempts require a separate explicit candidate or policy decision.

The minimal contract selects existing semantic wording; it does not author it.
`positive_signal` is exact Pack `examples[0]`, `negative_signal` is exact
`counterexamples[0]`, and nearest distinction is the unique direct rule
against the only other current visible type. Reason `use_when` is the exact
first sentence of catalog `meaning` under the closed sentence rule. GOAL 7
only implements those mappings and may not embed replacement wording.

GOAL 8 is implemented at that exact boundary. The current Packet factory calls
the GOAL 7 minimal projection, constructs one five-block V2.1 candidate and
one exact private receipt, and leaves historical V2.0 off the current
per-request path. Frozen proof preserves all ten active packet hashes, all 45
semantic literal occurrences and all 59 compiled bindings. Aggregate V2.1
payload is 26,211 UTF-8 bytes versus historical V2.0 at 78,621 bytes. Runtime
activation, provider calls and full-benchmark runs are zero.

The former post-GOAL-8 STOP was cleared by the later explicit program. GOAL 9
now implements the inactive profile through the existing Choice owner. It
leaves active V6 bytes, Context candidate/receipt, Expansion, linter, request
builder, adapters and provider routes unchanged.

## Context V2.1 Local Choice response profile GOAL 9

The existing `Gate2FinancialSemanticV6ChoiceContractFactory.create` adds one
inactive response profile pinned to the Context V2.1 candidate, its private
mapping receipt and the unchanged active Choice hash. Its parser restores
`choice_N` only through the exact receipt row and preserves any of the three
allowed V2.1 reasons without repair.

The profile has two inactive consumers:
`Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1` and the
GOAL 11 local proof coordinator. The third reason remains outside active V6
Expansion/materialization and is accepted only by the additive candidate path.
Provider calls, managed-asset changes, benchmark runs and runtime activation
are zero.

## Context V2.1 three-provider local proof GOAL 11

`Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` is a
bounded coordinator, not a new semantic authority. It delegates request
sealing, provider projection/extraction, Choice restoration, candidate
Expansion, canonical materialization, Financial Domain snapshot/persistence
and transparent reporting to the owners listed above. For each synthetic path
it serializes one exact private-evidence document, restores that document,
replays from its preserved adapter output, validates the sealed request, exact
repository profile and whole prepared-request rebuild, and reconstructs the
Financial Domain snapshot. Candidate-only extraction first requires one
terminal provider envelope.

The public report method `create_context_v2_1_provider_case` returns only the
raw closed projection and cannot mint evidence. ProviderProofFactory first
creates an unissued full proof, independently recomputes the same unissued proof
from governed inputs and requires exact equality. Only then does its private
report-module authority issue the opaque immutable case-evidence token.
Independent canonical full-proof validation follows. The aggregate accepts only
that issued token and revalidates its closed projection when read; raw or
resealed proof dictionaries are not report evidence and fail closed.

The proof covers three profiles by four semantic fixtures, including
`single_registry_type_no_safe_record`. The candidate decision contract extends
the unclassified reason enum only through the existing decision/Expansion
factories; the active Choice schema/hash remains unchanged during the proof.
The non-active
`broker_reports_gate2_context_v2_1_local_schema_projection_v1` identity binds
OpenAI/Anthropic/Google projection behavior and preserves the `choice` and
`reason` enums, including Gemini, while canonical adapter versions stay
unchanged. No transport function is called.

## Outcome Taxonomy and Benchmark Audit GOAL 6

The
[Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md)
closes the count-one vocabulary gap additively:

- semantic truth is evaluated by plausible distinct type count plus uniquely
  safe complete-choice count, never by raw Compiler option/block counts;
- the semantic rows are typed `1/1`, no type `0/0`, ambiguous type `2+/0`,
  and single type without a safe record `1/0`;
- the count-one row uses the new inactive managed candidate reason
  `single_registry_type_no_safe_record`;
- insufficient source context and technical failure remain non-semantic
  preclose/fail-closed rows and never force a semantic reason;
- the four frozen zero-choice audits have plausible-type counts `2,1,1,1`;
  three historical `ambiguous_registry_type` expectations are proven errors;
  and
- the corrections live in a new frozen outcome-audit identity. Historical
  successor/V6 manifests, local proof, reports and receipts remain unchanged.

Catalog v2 is an additive successor under the existing catalog ID. It remains
inactive and is not accepted by the active V6 Choice. GOAL 7 packages it in
inactive family v3 and implements only its exact managed minimal projection
through the existing loader/projection owner. The current non-active V2.1
Packet construction, Choice-owned response profile, provider-neutral Context
Linter, GOAL 11 zero-call local proof and the terminal GOAL 12 qualification
plan/evidence path are its only consumers. None is product runtime. GOAL 12
completed with `8` submissions, no benchmark-eligible provider/model and no
activation.
Current non-active V2.1 uses the Minimal Model Surface instruction, not the historical
V2.0 complete-prebound task.

## Documentation drift and explicit debt

1. The global gate architecture remains normative but does not index the newer
   V6 compiler, choice, expansion, Managed Financial Domain and query owners.
2. Generated bundles are deterministically rebuilt and tested, but their file
   headers do not make generated-only status obvious.
3. Financial Domain persistence owns an envelope, not a storage backend. A
   future storage adapter must delegate serialization and may not mint snapshot
   authority.
4. The OpenAI root-object projection is implemented locally in the existing
   adapter. GOAL 12 passed its separately enforced pre-call Actions gate and
   completed without admitting a provider/model; its terminal final head still
   requires its own green Actions check and fresh review before merge.

## Historical LLM Semantic Context v1 candidate boundary

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
was the closed target for the historical Slim candidate profile. It requires
readable evidence-derived hierarchy, exactly one rendered occurrence per
authoritative semantic source value, omitted nulls, local request-bound aliases
and zero opaque global IDs across messages and response schema. The
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
is the additive historical successor. Its packet-owned candidate and private
mapping receipt are implemented but non-active; its complete Prompt + Context
+ response-format request was not implemented. The future field-eligibility
target is the
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md),
not completion of the V2.0 surface.

The current active V6 four-block packet and V6 Choice do not claim this
conformance: they expose exact source/option identities by their historical
contracts. The historical staged GOAL 0 defined the v1 boundary; its GOAL 1/2
implemented a non-active local projection, and its GOAL 3 enforces that profile
at the candidate request boundary.
Slim construction remains inside
`Gate2FinancialSemanticV6PacketFactory.create`, and the separate
[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
remains inside the current Choice authority. No provider adapter may remove
IDs or repair semantic meaning to simulate conformance.

```text
CONTEXT_CONTRACT: DEFINED
CURRENT_PACKET_CHANGED: NO
CURRENT_CHOICE_CHANGED: NO
RUNTIME_ROUTE_CHANGED: NO
SECOND_PACKET_BUILDER: ZERO
CONTEXT_LINTER: IMPLEMENTED_FOR_CANDIDATE_PROFILE
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 1 non-active Slim View implementation

`Gate2FinancialSemanticV6PacketFactory.create` now constructs the inactive
Slim View and private alias receipt alongside the unchanged active four-block
packet. No second module, packet factory, Candidate Compiler, semantic
projection or Choice schema was introduced.

The maintained request builder, qualification and evidence paths continue to
consume only `packet.payload`. Candidate renderers are local-proof surfaces;
they do not create a provider route. Exact source/type identities, lineage,
bindings and deterministic-reference values stay in the private receipt and
existing authorities.

Executable architecture and packet tests prove:

- all 10 frozen active packet hashes and UTF-8 byte counts are exact;
- each semantic value has one local alias and one rendered occurrence;
- structure and non-null metadata are retained;
- every displayed binding resolves through the receipt to its exact compiled
  option binding;
- candidate/receipt tampering fails closed;
- the candidate is always inactive and provider-call accounting is zero;
- no `gate2_financial_semantic_v6*slim*.py` module or Slim factory exists.

```text
SLIM_VIEW_OWNER: EXISTING_V6_PACKET_FACTORY
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
SLIM_VIEW_ACTIVE: FALSE
PRIVATE_ALIAS_RECEIPT: INTEGRITY_BOUND
CURRENT_REQUEST_ROUTE_CHANGED: NO
CURRENT_CHOICE_CHANGED: NO
SECOND_PACKET_BUILDER: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 2 non-active Local Choice implementation

`Gate2FinancialSemanticV6ChoiceContractFactory.create` now returns the
unchanged active exact-ID Choice plus one inactive versioned local candidate.
Slim View v2 removes canonical `return_id`; the packet private receipt retains
the exact A/B-to-option mapping.

`Gate2FinancialSemanticV6DecisionExpansionFactory.create_from_local_candidate`
normalizes the local closed answer and delegates to the same canonical
expansion used by `create`. It is not called by the request builder,
qualification run or evidence runtime.

Executable tests prove:

- all 10 active Choice schema hashes remain exact;
- exact messages plus local response schema contain zero opaque IDs;
- option permutation moves the visible record and private mapping together
  while active packet payload/hash remain exact;
- every local typed and unclassified answer expands and materializes
  identically to the current path;
- unclassified retention remains the complete Evidence Bundle retention set;
- unknown/extra/duplicate/tampered choices fail closed;
- no second Choice factory or local-choice module exists;
- provider calls, fallback, repair, retry and runtime-route changes are zero.

```text
LOCAL_CHOICE_OWNER: EXISTING_V6_CHOICE_FACTORY
LOCAL_EXPANSION_OWNER: EXISTING_V6_DECISION_EXPANSION_FACTORY
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
FULL_MODEL_VISIBLE_OPAQUE_IDS: ZERO
CANONICAL_EXPANSION_MATERIALIZATION_PARITY: EXACT
LOCAL_CHOICE_ACTIVE: FALSE
CURRENT_REQUEST_ROUTE_CHANGED: NO
SECOND_CHOICE_FACTORY: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 3 pre-transport Context Linter and local totality

`Gate2FinancialSemanticV6ContextLinterFactory.create` validates the complete
Prompt + Slim View + Local Choice projection after the existing packet and
Choice authorities have constructed their parts. This downstream position is
intentional: the packet owner cannot inspect Prompt or Choice without becoming
a second authority for them.

The linter verifies zero opaque IDs, duplicate literal occurrences, nulls,
unmapped aliases, orphan aliases and alias collisions; it also proves complete
literal coverage, valid evidence-derived hierarchy, exact option coverage and
the full private alias-receipt integrity. It records exact model-visible UTF-8
bytes plus the repository estimator result and seals one request-bound
receipt.

The existing `Gate2OpenWebUIRequestBuilder.build` remains the sole provider
request constructor. Its non-active
`financial_semantic_v6_slim_linted_v1` profile checks the sealed receipt before
returning `form_data`. It imports no qualification-only V6 module, is rebuilt
inside all generated bundles and fails closed there when a receipt is absent.

Executable proof over all 10 frozen semantic cases records:

```text
SEMANTIC_LITERAL_COVERAGE: 100_PERCENT
DUPLICATE_LITERALS: ZERO
NULL_FIELDS: ZERO
OPAQUE_IDS: ZERO
UNMAPPED_ALIASES: ZERO
ORPHAN_ALIASES: ZERO
ALIAS_COLLISIONS: ZERO
STRUCTURAL_HIERARCHY: VALID
EXACT_OPTION_COVERAGE: COMPLETE
ALIAS_RECEIPT_INTEGRITY: VALID
EXACT_REPLAY: 10_OF_10
LOCAL_TOTAL_MATERIALIZATION: 32_OF_32
MODEL_VISIBLE_UTF8_BYTES_TOTAL: 26404
REPOSITORY_ESTIMATED_INPUT_TOKENS_TOTAL: 7247
CURRENT_RUNTIME_ROUTE_CHANGED: NO
PROVIDER_CALLS: ZERO
```

This adds one validation operation authority, not another context
construction authority. It performs no provider call, fallback, repair,
semantic rewrite, production admission or stage mutation.

### Historical Slim-program GOAL 4 bounded model diagnostic

`Gate2FinancialSemanticV6SlimDiagnosticFactory.create` is the
qualification-only orchestration owner for the exact six-cell experiment:
Nano canonical order, Haiku canonical order and Nano reversed order, each on
the frozen typed and unclassified smoke cases. It reuses the existing packet,
Local Choice, Context Linter, structured model client, expansion and total
materialization authorities. The reversed cells ask the existing
`Gate2FinancialSemanticV6PacketFactory` for a permutation; the active packet
payload/hash and canonical Choice schema remain exact.

The one authorized execution is terminal and must not be rerun:

```text
PROVIDER_SUBMISSIONS: SIX
PROVIDER_RESPONSES: SIX
TECHNICAL_PIPELINE: PASSED
HAIKU_TYPED: PASSED
HAIKU_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_UNCLASSIFIED: PASSED
FALLBACK_REPAIR_HIDDEN_RETRY: ZERO
FULL_BENCHMARK: NOT_RUN
RUNTIME_ROUTE_CHANGED: NO
```

The exact safe receipt and evidence-first
[report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md)
are the result authority. The report's post-execution layer audit localizes
the shared unclassified miss to the readable reason-code boundary:
`ambiguous_registry_type` and `no_registry_type` were exposed as bare labels
without an explicit distinction. This evidence owner records facts and
diagnosis only; it does not become a packet, Choice, provider or admission
authority.

## OpenAI projection decision and local completion

- `Gate2FinancialSemanticV6ChoiceContractFactory.create` owns the canonical
  minimal choice schema. Its top-level `anyOf` remains product-neutral contract
  meaning and is not a provider projection.
- `Gate2OpenAIResponseFormatAdapter.prepare_form_data` owns the OpenAI schema
  projection; `extract_content` owns inverse normalization and
  `provider_error_code` owns parsing provider rejection. Adapter version
  `1.1.0` wraps canonical root `anyOf` under one required provider-only root
  object property and removes that envelope before canonical parsing.
- The [safe two-case smoke](../../reports/2026-07-27/BROKER_REPORTS_V6_QUALIFICATION_GOAL5_TWO_CASE_SMOKE.report.md)
  records two provider responses rejected before any semantic decision.
  OpenAI's [Structured Outputs schema rules](https://developers.openai.com/api/docs/guides/structured-outputs#root-objects-must-not-be-anyof-and-must-be-an-object)
  require a root object rather than root `anyOf`. Both V6 smoke shapes have
  root `anyOf`, no root `type`, equal canonical/adapted hashes and transform
  count zero. Therefore the actionable root-cause layer is the existing
  provider projection, not Prompt, Pack, Choice meaning or qualification.
- OpenAI permits
  [nested `anyOf` schemas](https://developers.openai.com/api/docs/guides/structured-outputs#for-anyof-the-nested-schemas-must-each-be-a-valid-json-schema-per-this-subset)
  when every variant follows the supported subset. The provider-only envelope
  therefore preserves both closed V6 variants instead of flattening or
  weakening their semantic constraints.
- The corrective slice is now implemented inside
  `Gate2OpenAIResponseFormatAdapter`. Tests prove exact typed and unclassified
  choice parity, unchanged canonical input, a distinct adapted schema hash and
  exactly one recorded schema transform before transport.
- No product contract change or new qualification framework is required. The
  existing two-case smoke path can be used only after the local adapter seam
  passes and a new explicit authorization is granted; consumed submissions
  must not be retried or reused.

## V6 completion Goal 0 acceptance

```text
OPENAI_ROOT_OBJECT_PROJECTION: PASSED
TYPED_SEMANTIC_PARITY: EXACT
UNCLASSIFIED_SEMANTIC_PARITY: EXACT
CANONICAL_CHOICE_CHANGED: NO
SECOND_AUTHORITY_CREATED: NO
ADAPTER_VERSION: 1.1.0
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
DOCUMENTATION_IMPACT: AUTHORITY_MAP_UPDATED
DOCUMENTATION: CURRENT
```

## V6 completion Goal 1 local response seam

`Gate2FinancialSemanticV6LocalProofFactory.create` now routes every frozen
semantic benchmark choice through the existing canonical request builder,
`Gate2ProviderAdapterFactory.create`, OpenAI root-object projection, simulated
provider-shaped JSON content and adapter inverse normalization before invoking
the existing V6 expansion, validator and total materializer.

The local proof receipt/policy revision is `v2`. It separately accounts for
ten simulated provider-shaped responses while preserving zero provider
submissions and zero provider responses. Four typed and six unclassified
semantic cases traverse the seam; the two technical-preclose cases never enter
the provider branch.

```text
TYPED_LOCAL_SEAM: PASSED
UNCLASSIFIED_LOCAL_SEAM: PASSED
OPENAI_ROOT_OBJECT_PROJECTION: PASSED
EXPANSION: PASSED
VALIDATION: PASSED
MATERIALIZATION: PASSED
PROVIDER_CALLS: ZERO
PROVIDER_RESPONSES: ZERO
SECOND_AUTHORITY_CREATED: NO
DOCUMENTATION_IMPACT: AUTHORITY_MAP_UPDATED
DOCUMENTATION: CURRENT
```

## V6 completion Goal 2 provider smoke

The bounded smoke reuses `smoke_financial_semantic_v6` in the existing
qualification runner and `Gate2StructuredModelClientFactory.create`. It owns
no request builder, provider adapter, validator or materializer. The only
selected cases are the frozen unambiguous typed case
`syn_successor_v2_unique_cash` and frozen unambiguous unclassified case
`syn_successor_v2_no_registry_type`.

The exact Nano smoke consumed two provider submissions and received two
responses. Both responses first stopped at
`Gate2FinancialSemanticV6ExecutionIdentityFactory.create` because that owner
still expected pre-projection metadata (`canonical == adapted`, transform
count zero). Adapter `1.1.0` correctly supplied distinct canonical/adapted
hashes and transform count one.

The execution-identity owner now derives its exact expected hashes and
transform count through `Gate2ProviderAdapterFactory.create`; the synthetic
preflight and tests use the same factory route. Exact offline processing of
both preserved responses then passed schema identity, parsing, normalization,
usage normalization, validation/materialization and evidence replay without a
provider call. The typed response selected the wrong exact option and the
unclassified response did not select the required unclassified disposition,
so both semantic smoke cases remain failed.

The canonical live receipt and supplemental offline diagnostic are
[repository-safe evidence](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE.report.md).
No precision, recall or model-safety verdict is published. Goal 2 is not
accepted and Goal 3 must not run.

```text
PROVIDER_SUBMISSIONS: TWO
PROVIDER_RESPONSES: TWO
TECHNICAL_PIPELINE_AFTER_IDENTITY_CORRECTION: PASSED
TYPED_SMOKE: FAILED
UNCLASSIFIED_SMOKE: FAILED
USAGE_NORMALIZATION_AFTER_IDENTITY_CORRECTION: PASSED
OFFLINE_REPLAY_AFTER_IDENTITY_CORRECTION: EXACT
FALLBACK_REPAIR_RETRY: ZERO
MODEL_QUALIFICATION_PERFORMED: FALSE
MODEL_SAFETY_VERDICT: NONE
SECOND_AUTHORITY_CREATED: NO
GOAL3: BLOCKED
DOCUMENTATION_IMPACT: RUNTIME_EVIDENCE_UPDATED
DOCUMENTATION: CURRENT
```

## Zero-context orientation proof

Status: `HISTORICAL_EVIDENCE` for the legacy pre-Pipeline-Gates-v1 naming below.

A fresh read-only agent with no conversation history, Codex memory, report
archaeology or internet access followed service `AGENTS.md` to this map,
versioned contracts and maintained code. It correctly identified:

- the current Gate 1 → technical preparation → Typed Options → minimal semantic
  choice → deterministic expansion → validation/materialization → Financial
  Domain → Query API → Gate 3 consumer path;
- the sole request, provider projection/parsing, budget, financial semantics,
  source-binding, materialization and query authorities;
- the provider-projection blocker and
  `Gate2OpenAIResponseFormatAdapter` as the only next corrective component;
- Prompt, Pack, canonical Choice, request builder, budget, qualification,
  materialization, domain/query contracts and generated bundles as forbidden
  direct corrective targets.

No second authority or qualification framework was proposed. The only
orientation drift found was the stale resolved-debt text removed above.

## Goal 0 acceptance

```text
DOMAINS: FULLY_INVENTORIED
AUTHORITIES: IDENTIFIED_OR_EXPLICITLY_AMBIGUOUS
DUPLICATES: IDENTIFIED
DOCUMENTATION_DRIFT: IDENTIFIED
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Goal 2 acceptance

```text
AUTHORITY_MAP: COMPACT_AND_ACTIONABLE
EXACT_CODE_REFERENCES: PRESENT
FULL_CONTRACT_DUPLICATION: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Goal 5 acceptance

```text
ACTIVE_DUPLICATE_AUTHORITIES: ZERO
COMPATIBILITY_REIMPLEMENTATION: ZERO
PRODUCT_BEHAVIOR_CHANGE: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Historical architecture-map program Goal 8 acceptance

```text
RESPONSE_FORMAT_OWNER: IDENTIFIED
ROOT_CAUSE_LAYER: IDENTIFIED
ROOT_CAUSE: PROVIDER_PROJECTION
NEXT_CORRECTIVE_SLICE: ONE_EXISTING_AUTHORITY
CORRECTIVE_AUTHORITY: GATE2_OPENAI_RESPONSE_FORMAT_ADAPTER
PRODUCT_CONTRACT_CHANGE: ZERO
NEW_QUALIFICATION_FRAMEWORK: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Historical architecture-map program Goal 9 acceptance

```text
ZERO_CONTEXT_AGENT_ORIENTATION: PASSED
AUTHORITIES_FOUND_WITHOUT_REPORT_ARCHAEOLOGY: YES
WRONG_SECOND_PATH_PROPOSED: ZERO
DOCUMENTATION_DRIFT_FOUND: ONE_STALE_RESOLVED_DEBT_BLOCK
DOCUMENTATION_DRIFT_CORRECTED: YES
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
FINAL_STATUS: ARCHITECTURE_MEMORY_REFINED_WITH_EXPLICIT_DEBT
```

## DOC28 durable deployment authority status

No new owner was introduced. `ArtifactStoreFactory` remains the metadata and
payload owner, `CanonicalArtifactStoreFactory` remains the version/lifecycle
facade, and `CanonicalReaderFactory` remains the sole read boundary. The
existing `openwebui_data` mount is only a deployment candidate until an
authorized runtime proves restart, backup/restore, capacity and retention.
DOC28 created no durable store, active pointer, Wave 2 adapter or product read.

DOC29 retained these owners and introduced no engine. It identified the live
`openwebui_data` mount, reused the Broker namespace, and added only a bounded
job plus factory-routed Wave 2 shadow contracts. STT's named-volume and factory
patterns are reusable; its schema, nullable tenant field, inline payload model,
missing rotation worker and backup omission are not canonical authority.
Target ownership remains unadmitted until host recovery and post-job
durability/restore accounting. Global and primary canonical reads remain off.

At the DOC30 checkpoint, DOC30 made no authority change. It recovered the target, accounted the DOC29
OOM and selected `RETAIN` after current Broker/STT integrity and zero-write
proof. Its closed-world resource-bounded entrypoint routes normalization,
publish/activate and readback through the existing factories, one document per
checkpoint. Two canaries and 8 target versions passed; an XLSX then reached
the frozen memory cgroup and triggered the mandatory stop with zero partial
persisted state. `ArtifactStoreFactory`, `CanonicalArtifactStoreFactory` and
`CanonicalReaderFactory` remained the only storage/lifecycle/read owners. Wave 2
and primary reads were off, target durability/restore were unconfirmed, and
Gate 3 was then unstarted. This is historical checkpoint state, not the current
Gate 3 status.

DOC32 also creates no second authority. `CanonicalNormalizerFactory` remains
the sole logical builder, `CanonicalArtifactStoreFactory` the lifecycle facade,
and `CanonicalReaderFactory` the sole consumer query boundary. The PDF adapter
now accounts every source atom and emits a counts-only completeness receipt;
the store refuses non-empty zero-node PDF candidates. The research projector is
inside the existing consumer adapter and accepts only a reader envelope. The
bounded republisher, backup/restore command and Wave 2 shadow orchestrate these
owners; they do not become new parsing, storage, reader or product authorities.

At the DOC33 checkpoint, DOC33 confirmed those same owners across PDF, HTML,
CSV and XLSX. It refined the
existing validator with one format-neutral completeness rule, generalizes the
existing research renderer over common container/node semantics, and removes
source format from Wave 2 shadow output. `canonical_artifact_v1` remains the
only schema, `CanonicalReaderFactory.create` remains the only reader, and the
[Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) summarizes
the boundary without creating another DTO or execution authority. Product
cutover and Gate 3 were then unstarted; current status is owned by Pipeline
Gates v1.
