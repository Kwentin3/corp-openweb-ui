# Broker Reports Architecture Authorities

Status: `GOAL_0_ARCHAEOLOGY_BASELINE`

This is the compact orientation index for maintained Broker Reports
implementation authorities. It supplements, and does not replace, the
[global gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md)
or the versioned data contracts linked below.

Use this order when sources appear to disagree:

1. the global gate architecture owns gate placement and product boundaries;
2. a versioned contract owns DTO meaning and invariants;
3. the maintained source factory owns object construction or execution;
4. a compatibility entrypoint may only adapt and delegate;
5. generated bundles project maintained source;
6. dated reports and receipts are historical evidence only.

## Archaeology inventory

| Domain / concern | Normative contract | Actual maintained owner | Current consumers | Finding |
| --- | --- | --- | --- | --- |
| Gate 1 evidence and provenance | [Gate 1 document memory](./BROKER_REPORTS_GATE1_DOCUMENT_MEMORY.v1.md), [full normalized payload](./BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md) | `Gate1BoundedGraphFactory.create` and `ArtifactResolver` in `broker_reports_gate1/bounded_graph.py` and `artifact_resolver.py` | Technical preparation and Gate 2 readiness | Sole source/provenance authority; Gate 2 must not read storage directly. |
| Technical preparation | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | `Gate2DeterministicFinancialScopeFromGate1V2Factory.create` then `Gate2FinancialEvidenceBundleFactory.create` | Candidate Compiler and technical preclose | Technical selectors may prepare evidence but may not assign financial meaning. |
| Financial Semantic Pack meaning | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | `Gate2FinancialSemanticContractFactory.create` over the verified managed asset in `gate2_financial_semantic_contract.py` | projection, compiler, validator, materializer, Financial Domain | Sole type/role/ambiguity authority. |
| Compact Semantic Pack projection | [Semantic Pack model input](./BROKER_REPORTS_GATE2_SEMANTIC_PACK_MODEL_INPUT.v1.md) | `Gate2FinancialSemanticV5ProjectionFactory.create` in `gate2_financial_semantic_v5_projection.py` | V5 decision packets and the V6 packet factory | Maintained cross-version projection; the `V5` name is documentation/naming debt, not a second Pack. |
| Evidence Bundle | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | `Gate2FinancialEvidenceBundleFactory.create` in `gate2_financial_semantic_v6_bundle.py` | Candidate Compiler, packet, expansion and replay | Sole sealed pre-semantic evidence representation. |
| Typed Option construction | [Typed Option](./BROKER_REPORTS_GATE2_FINANCIAL_TYPED_OPTION.v1.md) | `Gate2FinancialTypedOptionFactory.create` in `gate2_financial_semantic_v6_typed_option.py` | Candidate Compiler and decision expansion | Code owns type, roles, source refs and materializability. |
| Candidate compilation | [Candidate Compiler](./BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md) | `Gate2FinancialCandidateCompilerFactory.create` in `gate2_financial_semantic_v6_candidate_compiler.py` | V6 packet, qualification and replay | Sole compiler; it must contain no type-specific IDs or financial regex. |
| Prompt ownership | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) and [qualification harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) | `financial_semantic_v6_prompt` in `gate2_financial_semantic_v6_prompt.py` | request builder and qualification | Owns only semantic-choice instruction, not request transport or product records. |
| V6 semantic packet | [V6 packet](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md) | `Gate2FinancialSemanticV6PacketFactory.create` in `gate2_financial_semantic_v6_packet.py` | V6 Prompt, request builder and Choice Contract | Sole four-block model-visible packet. |
| Provider-neutral semantic choice | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) | `Gate2FinancialSemanticV6ChoiceContractFactory.create` in `gate2_financial_semantic_v6_choice.py` | request builder, expansion and evidence | Model owns only the minimal disposition/opaque-option selection. |
| Provider request construction | [V6 qualification harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) | `Gate2OpenWebUIRequestBuilder.build` in `gate2_model_requests.py` | `Gate2OpenWebUIStructuredModelClient` and delegating evidence helpers | Sole canonical provider request builder. |
| Provider schema projection and response parsing | Provider-neutral choice/request contracts | `Gate2ProviderAdapterFactory.create`, `_Gate2OpenWebUIProviderAdapter.prepare_form_data`, `extract_content` and provider subclasses in `gate2_provider_adapters.py` | structured model client | Sole owner of provider-specific schema adaptation, response shape and error interpretation. |
| Provider usage normalization | Provider execution metadata contract in `gate2_model_contracts.py` | `_Gate2OpenWebUIProviderAdapter.execution_metadata` in `gate2_provider_adapters.py` | model client, budget accounting and qualification evidence | Provider-specific token fields must not be parsed by qualification. |
| Budget admission and accounting | Economy budget v1 code contract | `Gate2EconomyBudgetSessionFactory.create` / `Gate2EconomyBudgetSession` in `gate2_economy_budget.py` | structured model client | Sole pre-transport admission and post-response accounting authority. |
| Canonical decision expansion | [V6 expansion](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_EXPANSION_V6.md) | `Gate2FinancialSemanticV6DecisionExpansionFactory.create` in `gate2_financial_semantic_v6_expansion.py` | total materializer, qualification and evidence replay | Sole minimal-choice to canonical-decision boundary. |
| Canonical validation | [Generic materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | `Gate2FinancialEvidenceValidatedDecisionFactory.create` plus `validate_financial_evidence_inputs` in `gate2_financial_evidence_materialization.py` | materializer, local proofs and qualification | Provider output remains a proposal until this boundary passes. |
| Canonical materialization | [Generic materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | `Gate2FinancialEvidenceMaterializerFactory.create().materialize` in `gate2_financial_evidence_materialization.py` | Financial Domain catalog and compatibility projections | Sole owner of canonical IDs, bindings, provenance, retention and terminal coverage. |
| Financial Domain snapshot | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | `Gate2FinancialDomainCatalogFactory.create` in `gate2_financial_domain_catalog.py` | query factory and serialization contract | Sole immutable snapshot construction authority. |
| Financial Domain persistence envelope | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | `Gate2FinancialDomainPersistenceFactory.serialize/restore` in `gate2_financial_domain_persistence.py` | local proof and future server storage adapter | Owns serialization only; the actual storage writer is intentionally outside this service contract. |
| Financial Domain query API | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) | `Gate2FinancialDomainQueryFactory.create` in `gate2_financial_domain_query.py` | Gate 3 consumer | Sole authorized bounded query entrypoint. |
| Gate 3 Financial Domain consumer | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) | `Gate3FinancialDomainContextFactory.create` in `gate3_financial_domain_context.py` | Gate 3 successor logic | Must consume only the query API; no ArtifactStore or source readers. |
| Qualification result | [V6 qualification harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) | `qualify_financial_semantic_v6` in `gate2_financial_semantic_v6_qualification_run.py` | qualification CLIs and safe receipts | Qualification-only terminal classifier; not a product authority. |
| Exact decision evidence and replay | [V6 exact evidence](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md) | `Gate2FinancialSemanticV6DecisionEvidenceFactory.create` and `replay_financial_semantic_v6_decision` in `gate2_financial_semantic_v6_evidence.py` | qualification and offline replay | Evidence records execution; it cannot change the product decision. |
| Compatibility reads | Version-pinned legacy and successor schemas | `Gate2FinancialEvidenceCompatibilityFactory.create`, `PinnedLegacySourceFactsValidatorFactory.create`, and `Gate2SuccessorCompatibilityReaderFactory.create` | successor local proofs and migration tooling | Explicit dual-read boundary; no silent rewrite or successor write admission. |

Paths above are relative to
`services/broker-reports-gate1-proof/broker_reports_gate1` unless a full path is
shown.

## Duplicate, compatibility and history findings

- No proven active duplicate owns the same maintained product operation.
- `financial_semantic_v6_canonical_request` validates V6 inputs and delegates to
  `Gate2OpenWebUIRequestBuilder.build`; it is a wrapper, not a second builder.
  Its compatibility status is not yet marked with the required common marker.
- `Gate2FinancialSemanticV5ProjectionFactory` is intentionally consumed by V6.
  Renaming or replacing it would create migration risk; document the
  cross-version ownership instead of creating a V6 copy.
- `gate2_financial_evidence_compatibility.py`,
  `gate2_financial_evidence_legacy_validation.py` and
  `gate2_successor_compatibility.py` are active compatibility readers. Their
  schemas and validation policies are separate by version, but their
  delegation-only status needs a uniform marker and executable proof.
- `gate3_context_manifest.py` is the legacy bounded Gate 2 handoff root;
  `gate3_financial_domain_context.py` is the Financial Domain successor
  consumer. The successor is intentionally forbidden from importing the
  legacy manifest or Gate 1 readers.
- `openwebui_actions/*_bundled.py` are generated closed-world projections.
  `scripts/build_openwebui_pipe_bundle.py` and maintained package/action
  sources own their content; bundle files must not be edited as authorities.
- Files under `docs/reports/**`, benchmark sealed results and committed safe
  receipts are immutable historical evidence. They may identify a past
  revision but never override maintained code or contracts.
- V5 and earlier qualification runners remain readable for historical replay
  and version-pinned tests. New V6 work must not extend them as current
  qualification authority.

## Documentation drift and explicit debt

1. The global gate architecture remains normative but does not index the newer
   V6 compiler, choice, expansion, Managed Financial Domain and query owners.
2. No service-level `AGENTS.md` currently gives a zero-context agent the
   existing-owner-first sequence.
3. Critical modules use `FACTORY_REQUIRED` / `FORBIDDEN` anchors, but the
   requested `OWNER / REUSE / MUST NOT` comments are not yet uniform.
4. Compatibility readers are fail-closed, but the shared
   `COMPATIBILITY_WRAPPER_DELEGATES_ONLY` marker is absent.
5. Generated bundles are deterministically rebuilt and tested, but their file
   headers do not make generated-only status obvious.
6. Financial Domain persistence owns an envelope, not a storage backend. A
   future storage adapter must delegate serialization and may not mint snapshot
   authority.
7. The current qualification blocker
   `gate2_model_schema_response_format_rejected` is classified by the provider
   adapter. The safe evidence is insufficient at Goal 0 to decide whether the
   exact defect is canonical schema, provider projection or provider
   capability.

## Goal 0 acceptance

```text
DOMAINS: FULLY_INVENTORIED
AUTHORITIES: IDENTIFIED_OR_EXPLICITLY_AMBIGUOUS
DUPLICATES: IDENTIFIED
DOCUMENTATION_DRIFT: IDENTIFIED
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```
