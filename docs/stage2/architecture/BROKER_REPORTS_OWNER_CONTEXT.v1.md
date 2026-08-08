# Broker Reports Owner Context v1

Status: `HISTORICAL_PRE_GATE3_OWNER_SNAPSHOT`

This companion and its JSON describe the owner inventory at their dated
checkpoint. They do not own current gate placement or Gate 3 status. Use
[Pipeline Gates v1](../contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md) and
[Architecture Authorities](../contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
for current routing.

Machine authority:
`docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`

Policy: `SIDECAR_OWNER_METADATA`

## Purpose

This sidecar carries architecture and domain context that must not change
hash-pinned production Python bytes. Contracts own versioned payload and
boundary rules. Tests own behavioral verification. Source comments are
reserved for non-obvious local algorithmic invariants that cannot be expressed
here and that do not break source or bundle parity.

The JSON document is normative for owner IDs, modules, symbols, domains,
runtime status, inputs, outputs, ownership, exclusions, consumers, adjacent
historical routes, ADR links, tests, and change gates. This Markdown document
is a navigation surface only.

## Program-owner decisions

```text
preferred_option = A
reserve_option = B_IF_DISTINCT_DOMAIN_IS_PROVEN
pr_232_disposition = CLOSED_WITHOUT_MERGE
owner_context_policy = SIDECAR_OWNER_METADATA
live_parity_checkpoint = CLOSED_BY_KT1_5
historical_v3_schema_hash_fix_deferred = true
kt2_authorized = true
```

KT2 adds `Gate2SameSourceTypeFirstProof` as an inactive subordinate capability
of `current_source_fact_orchestration`. It is product- and provider-unreachable,
owns no canonical contract, and delegates parsing, validation, materialization,
evidence and persistence to the existing sole owners.

KT2.1 adds `Gate2BoundedSemanticContextFactory` beneath that same inactive
proof. It owns only deterministic, structure-based context projection. It
cannot see Type Cards, choose a type, call a provider, validate/materialize a
fact, or enter a product/Function route. Its sufficiency guard reuses the same
Pack, validator, materializer, and replay authorities.

## Owner index

| Owner ID | Primary module | Domain | Runtime status |
| --- | --- | --- | --- |
| `pdf_vlm_visual_execution` | `pdf_dual_vlm_runtime.py` | Semantic visual table transcription | `ACTIVE_PRODUCT` |
| `semantic_visual_validation` | `semantic_visual_table_validator.py` | Semantic visual table transcription | `ACTIVE_PRODUCT` |
| `logical_table_materialization` | `semantic_visual_table_materialization.py` | Deterministic logical table materialization | `ACTIVE_PRODUCT` |
| `gate2_table_package` | `gate2_table_packages.py` | Gate 2 table package | `ACTIVE_PRODUCT` |
| `current_source_fact_orchestration` | `gate2_domain_runtime.py` | Source-fact extraction | `ACTIVE_PRODUCT` |
| `historical_source_fact_selection` | `gate2_source_fact_selection.py` | Historical and compatibility routes | `HISTORICAL_READ_ONLY` |
| `financial_type_authority` | `gate2_financial_semantic_contract.py` | Financial semantic decision | `ACTIVE_PRODUCT` |
| `semantic_choice_and_expansion` | Choice + Expansion modules | Financial semantic decision | `ACTIVE_PRODUCT` |
| `canonical_financial_validator` | `gate2_financial_evidence_materialization.py` | Canonical financial materialization | `ACTIVE_PRODUCT` |
| `canonical_financial_materializer` | `gate2_financial_evidence_materialization.py` | Canonical financial materialization | `ACTIVE_PRODUCT` |
| `financial_evidence_replay` | `gate2_financial_semantic_v6_evidence.py` | Replay and comparators | `PROOF_ONLY` |
| `artifact_store_and_resolver` | ArtifactStore + Resolver modules | Artifact persistence | `ACTIVE_PRODUCT` |
| `answer_context_selection` | `answer_context_selection.py` | AnswerContext | `ACTIVE_PRODUCT` |
| `gate3_context_manifest` | `gate3_context_manifest.py` | Gate 3 context manifest | `ACTIVE_PRODUCT` |
| `release_live_parity_verifier` | `live_verify_broker_reports_stage2_delivery.py` | Release and parity verification | `VERIFIED_LIVE` |

## Historical containment

`historical_source_fact_selection` is retained only for replay, validation, and
historical evidence:

```text
runtime_status = HISTORICAL_READ_ONLY
product_reachability = FORBIDDEN
provider_reachability = FORBIDDEN
reactivation_requires = new ADR + qualification + explicit product decision
```

The product Pipe's hard containment guard and current domain-runtime imports
remain executable proof. This sidecar does not create or activate a route.

## PR #232 external candidate

```text
external_candidate_reference = PR_232
current_main_status = CLOSED_WITHOUT_MERGE_NOT_PRESENT_AS_IMPLEMENTATION
approved_reuse_scope = contract_and_test_ideas_only
```

PR #232 owner modules are not current `main` owners. The approved reusable
ideas are catalogued in
`BROKER_REPORTS_PR232_EXTRACTION_LEDGER.v1.md`. A future task must start from
then-current `main` and reuse the existing product boundary; the sidecar does
not authorize KT2.

## Change protocol

Before changing an owner:

1. locate its JSON entry;
2. read all input/output contracts and related tests;
3. confirm the current imports, guards, consumers, and runtime status;
4. update the matrix/route/ADR in the same PR if meaning changes;
5. prove no second owner or product route is introduced;
6. preserve source/bundle and immutable source-hash parity;
7. require a separate decision for activation or live mutation.
