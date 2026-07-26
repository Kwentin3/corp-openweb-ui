# Broker Reports Gate 2 Local Managed Financial Domain Proof v1

Status: normative proof contract for GOAL 9.

## 1. Purpose

This contract defines a deterministic, customer-free, provider-free proof of
the complete local managed financial domain contour:

1. deterministic Gate 1 financial scope;
2. the complete managed Financial Semantic Pack;
3. the managed OpenWebUI asset identity manifest;
4. current V4 model input;
5. all four terminal decision branches;
6. canonical decision validation;
7. authoritative materialization;
8. immutable snapshot persistence serialization and restoration;
9. domain catalog construction;
10. typed and unclassified record queries;
11. coverage and provenance queries;
12. fail-closed negative checks.

The proof is a release prerequisite. It is not production activation, live
model qualification, actual-corpus acceptance, or Gate 3 acceptance.

## 2. Authority and composition

`Gate2FinancialDomainLocalProofFactory.create` is the proof entrypoint. It
composes existing authorities and must not replace them:

- `Gate2DeterministicFinancialScopeFromGate1V2Factory`;
- `load_gate2_financial_semantic_model_assets`;
- `Gate2FinancialEvidenceSuccessorRunner.model_input`;
- `Gate2FinancialEvidenceValidatedDecisionFactory`;
- `Gate2FinancialEvidenceMaterializerFactory`;
- `Gate2FinancialDomainCatalogFactory`;
- `Gate2FinancialDomainPersistenceFactory`;
- `Gate2FinancialDomainQueryFactory`;
- the existing product comparator and canonical validators.

The frozen synthetic successor-v2 benchmark remains the fixture authority.
Expected dispositions are used only after model-input construction. They are
never included in a model input and no model is called.

## 3. Current exact contracts

The proof must bind:

- model input:
  `broker_reports_gate2_financial_evidence_successor_model_input_v4`;
- prompt:
  `broker_reports_gate2_financial_evidence_managed_prompt_v1`;
- source context:
  `broker_reports_gate2_financial_evidence_source_context_v2`;
- domain snapshot:
  `broker_reports_managed_financial_domain_snapshot_v1`;
- persistence:
  `broker_reports_managed_financial_domain_persistence_v1`;
- query response:
  `broker_reports_gate2_financial_domain_api_response_v1`;
- query policy:
  `broker_reports_gate2_financial_domain_query_v2`.

The receipt records the exact Pack integrity SHA-256, managed identities
Git-blob SHA-256, managed manifest SHA-256, prompt SHA-256, model-input hashes,
and source-context hashes.

## 4. Persistence contract

`Gate2FinancialDomainPersistenceFactory` is a pure serialization boundary. It:

1. accepts only a validated immutable domain snapshot;
2. verifies the server-authoritative snapshot HMAC before serialization;
3. emits a closed, versioned canonical JSON envelope;
4. binds the complete snapshot payload with SHA-256;
5. verifies envelope shape, payload hash, snapshot integrity, and authority
   HMAC on restoration;
6. restores the exact immutable snapshot value.

It does not choose a storage engine, open files, write a database, mint new
authority, or expose the server-held authority key. The local proof records
`persistence_writes_total=0`.

The HMAC attestation may exist inside the internal persistence envelope. The
server-held HMAC key must never appear in the envelope, query response, report,
or safe receipt.

## 5. Query completeness

The proof pages every query with `limit=1` through the terminal response:

- `describe_domain`;
- `query_typed_records`;
- `query_unclassified_records`;
- `get_coverage`;
- `get_provenance`.

For every query, the proof requires:

- stable `matching_records_total` on every page;
- bounded positive progress;
- a terminal `complete_final_page`;
- returned count equal to matching count;
- no duplicates;
- exact record-hash equality with the immutable snapshot projection.

Thus query completeness covers values and provenance, not only IDs or counts.

## 6. Required negative checks

At minimum, the proof must execute and pass checks that reject:

- managed asset identity drift in V4 model input;
- materialized artifact tampering;
- persistence envelope or payload tampering;
- restoration with the wrong snapshot-authority key;
- query creation with the wrong access scope;
- continuation-token tampering;
- an omitted query result.

Existing successor-v2 prerequisite checks continue to cover invalid decision
bindings, unknown fields, artifact integrity drift, literal invention, and
cross-scope ownership failures.

A negative passes only when the intended operation raises its exact declared
terminal error code. An unrelated validation error must not satisfy a
fail-closed check.

## 7. Acceptance

GOAL 9 is accepted only when the safe receipt states:

```text
LOCAL_DOMAIN_PROOF PASSED
LITERAL_LOSS ZERO
QUERY_GAPS ZERO
PROVIDER_CALLS ZERO
```

It must also show all four terminal dispositions, exact persistence
round-trip, complete catalog/coverage/provenance, all negative checks passing,
zero fallback/repair/hidden retry, zero persistence writes, and zero production
route activation.

## 8. Privacy and closed world

Only the frozen synthetic manifest may be used. The safe receipt contains
counts, versions, booleans, and hashes only. It must contain no fixture
literals, source-value references, document references, customer data, raw
provider output, secrets, server-held keys, private paths, or live-stage
values.

The proof modules must not import provider adapters, model clients, production
runtime routes, storage adapters, Knowledge/RAG, embeddings, or vectorization.
The manifest is supplied by the caller; the proof performs no runtime
filesystem discovery.

## 9. Explicit non-claims

A passing local receipt does not claim:

- that an economy model passed live qualification;
- actual-corpus generalization;
- stage or production deployment;
- production provider admission;
- Gate 3 consumer acceptance;
- customer acceptance;
- release readiness or rollback proof.

Those remain separately gated by later goals.
