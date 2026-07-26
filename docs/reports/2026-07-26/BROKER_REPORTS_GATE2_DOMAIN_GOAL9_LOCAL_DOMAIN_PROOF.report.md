# Broker Reports Gate 2 — GOAL 9 Local Domain Proof

Date: 2026-07-26

Branch: `codex/broker-reports-gate2-domain-goal9-local-e2e-proof`

Base revision: `27ee880c30fd5b90bf82528ecb6400c4dc54de96`

Authoring status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

## 1. Outcome

The frozen synthetic managed financial domain contour passed end to end:

```text
LOCAL_DOMAIN_PROOF PASSED
LITERAL_LOSS ZERO
QUERY_GAPS ZERO
PROVIDER_CALLS ZERO
```

This is local, deterministic evidence only. It is not live economy-model
qualification, actual-corpus proof, Gate 3 acceptance, stage activation, or
release acceptance.

## 2. Implemented boundary

GOAL 9 adds:

1. a normative local-proof contract;
2. a composition-only local proof factory;
3. a versioned immutable snapshot persistence codec;
4. focused terminal and fail-closed tests;
5. this report and a repository-safe receipt.

The proof composes the accepted factories for deterministic scope, managed
assets, V4 model input, decision validation, materialization, domain catalog,
query, provenance, and coverage. It does not create another semantic
authority.

## 3. Frozen proof corpus

The input is the existing customer-free
`gate2_financial_successor_v2` manifest:

- cases: 12;
- typed decisions: 4;
- unclassified financial decisions: 6;
- no-financial decisions: 1;
- unsupported decisions: 1;
- manifest SHA-256:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`.

The accepted successor-v2 Q0/Q1 proof runs first as a prerequisite. GOAL 9
then rebuilds current V4 model inputs and the materialized domain from the
same frozen cases.

Expected fixture decisions are introduced only after model-input
construction. The no-call client is never invoked.

## 4. Current authority binding

The proof binds the current contracts:

- model input:
  `broker_reports_gate2_financial_evidence_successor_model_input_v4`;
- managed prompt:
  `broker_reports_gate2_financial_evidence_managed_prompt_v1`;
- snapshot:
  `broker_reports_managed_financial_domain_snapshot_v1`;
- persistence:
  `broker_reports_managed_financial_domain_persistence_v1`;
- query response:
  `broker_reports_gate2_financial_domain_api_response_v1`;
- query policy:
  `broker_reports_gate2_financial_domain_query_v2`.

Exact identities:

- Semantic Pack integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- managed identities Git-blob SHA-256:
  `a8de2b91f4cbde77bc2215ffb85b726e7b963dc77d6eb1a86e0b3e80499509a4`;
- managed manifest SHA-256:
  `b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59`;
- prompt SHA-256:
  `3f169c79a9bf6f0eb1b476853ed1ace50cca9b2f7fd2d2fe3394f2ab3f6d5a2e`.

The two managed-asset hashes are deliberately labelled by different
boundaries: one hashes the exact Git blob, the other is the manifest's
canonical family identity.

## 5. Persistence contract

`Gate2FinancialDomainPersistenceFactory` serializes the complete immutable
snapshot into a closed canonical JSON envelope. Before serialization and
after restoration it verifies:

- the snapshot's structural and cross-entity integrity;
- the envelope payload SHA-256;
- the server-authoritative snapshot HMAC.

The restored dataclass is exactly equal to the original snapshot. The codec
does not select or call a storage adapter and records zero writes.

Evidence:

- snapshot integrity SHA-256:
  `74a369622397cfab87ddd94626901dbe583ab0667bdf1d1b4f499906a71bfa77`;
- serialized envelope SHA-256:
  `390be395bde51e0c0a17611e3653030ce4edff7b9e62ac6ad38e4825a5e31ebc`.

The internal envelope contains an HMAC attestation but never the HMAC key.
Neither value is copied into user-facing responses.

## 6. Catalog and query proof

The immutable domain contains:

- typed records: 4;
- unclassified records: 6;
- coverage records: 12;
- provenance records: 12;
- declared types: 2.

Every API capability was paged with `limit=1`:

- `describe_domain`;
- `query_typed_records`;
- `query_unclassified_records`;
- `get_coverage`;
- `get_provenance`.

Across 36 pages, each query maintained stable matching counts, reached a
terminal final page, returned no duplicate, and matched the exact snapshot
projection by complete record hashes.

Query result-set SHA-256:
`8bb7a3dc83a8231b8f11c5eb5e1156cbb0ed8b80e02531c33ec52f6f6db069f6`.

## 7. Product invariants

The existing product comparator reported:

- literal loss: 0;
- invented values: 0;
- duplicate bindings: 0;
- cross-scope bindings: 0;
- terminal ownership gaps: 0.

Coverage gaps, provenance gaps, and query gaps are all zero.

## 8. Fail-closed negatives

Executed negatives reject:

- managed asset drift in V4 model input;
- tampered materialized artifacts;
- tampered persistence payloads;
- restoration with the wrong snapshot-authority key;
- query creation with a wrong access scope;
- tampered continuation;
- a deliberately omitted query result.

All seven checks passed. The prerequisite successor-v2 proof additionally
covers invalid binding, unknown-field, literal, integrity, and ownership
negatives.

## 9. Closed-world and privacy accounting

The new proof and codec import no provider adapter, model client, production
runtime, ArtifactStore, filesystem reader, Knowledge/RAG, embedding, or
vectorization boundary.

Execution accounting:

- provider/model/customer calls: 0;
- fallback/repair/hidden retry: 0;
- persistence writes: 0;
- stage mutations: 0;
- production changes: 0;
- tokens and provider cost: 0.

The receipt contains only frozen-manifest identities, counts, contract
versions, booleans, and hashes. It contains no fixture literal, source-value
reference, customer data, raw provider output, secret, server-held key,
private path, or live-stage value.

## 10. Verification

Run from `services/broker-reports-gate1-proof`:

- focused local proof plus direct dependencies:
  `39 passed in 16.48s`;
- full suite:
  `1614 passed, 20 skipped, 5 warnings in 153.95s`;
- repository privacy guard:
  `3 passed in 0.74s`;
- targeted Ruff: passed;
- targeted `py_compile`: passed;
- `git diff --check`: passed.

The five full-suite warnings are the pre-existing SWIG deprecation warnings;
there are no test failures.

## 11. Deliverables

- [`BROKER_REPORTS_GATE2_LOCAL_DOMAIN_PROOF.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_LOCAL_DOMAIN_PROOF.v1.md)
- `broker_reports_gate1/gate2_financial_domain_local_proof.py`
- `broker_reports_gate1/gate2_financial_domain_persistence.py`
- `tests/test_broker_reports_gate2_financial_domain_local_proof.py`
- [`BROKER_REPORTS_GATE2_DOMAIN_GOAL9_LOCAL_DOMAIN_PROOF.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL9_LOCAL_DOMAIN_PROOF.receipt.safe.json)

The receipt pins exact staged Git-blob SHA-256 for the normative contract,
both implementation modules, and the focused test file.

Exact staged safe-receipt Git-blob SHA-256:

`d8be5e3859f5db24c399ff92371d40baa3226d26e5f31505bab3361ee0c1a5e0`.

## 12. Scope stops

GOAL 9 does not change:

- Semantic Pack or managed asset bytes;
- the four-disposition decision contract;
- provider admission;
- production or stage routing;
- live model configuration;
- the Gate 3 consumer;
- customer data or private evidence.

Next permitted goal:
`GOAL_10_AFTER_GOAL_9_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.
