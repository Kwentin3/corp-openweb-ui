# Broker Reports Gate 2 Financial Semantic V6 Exact Evidence

Status: Goal 9 contract for Candidate Records By Construction.

## Private evidence

`Gate2FinancialSemanticV6DecisionEvidenceFactory.create` is the only V6
semantic-call evidence boundary. For each call it preserves privately:

- the exact canonical request and full response-format identity;
- the canonical provider schema hash;
- the normalized minimal semantic choice and its hash;
- the complete deterministic expansion and canonical validated decision;
- the validator and total-materializer result;
- the exact materialized artifact and integrity hashes;
- token, cost and latency metadata through the normalized provider execution
  identity.

Private evidence is returned to the caller. This module has no repository
writer and must never publish raw evidence, source literals or source refs.

## Safe receipt

The repository-safe receipt contains only bounded classifications, counts,
provider metrics and cryptographic hashes. It does not contain the canonical
request, semantic choice, expanded decision, provider response ID, source
literals or source refs.

`private_evidence_hash` is present in the safe receipt and links the two
representations exactly.

## Offline replay

`replay_financial_semantic_v6_decision` accepts the private evidence, its safe
receipt and the same code-owned authorities. It performs:

1. normalized semantic choice;
2. deterministic expansion;
3. canonical validation;
4. total materialization;
5. exact artifact-hash comparison.

Replay performs no provider call, repair, fallback or hidden retry. Any
authority, identity, expansion, validator, artifact or private/safe hash-link
mismatch fails closed.

## Goal 2 provider-smoke evidence

The two-case provider smoke checkpoints every returned response immediately.
Its first terminal receipt remains immutable and records the execution-identity
failure seen by the executed revision. Two exact private failure checkpoints
outside Git preserve the canonical request, normalized provider output,
execution metadata and hash links; neither their paths nor raw values are
published.

After the existing execution-identity owner was corrected for adapter `1.1.0`,
an offline-only diagnostic verified both source private hashes and canonical
request/response-format identities, then rebuilt decision evidence through the
same factory and performed exact replay. The diagnostic made zero provider
submissions and did not repair or alter either provider output.

The repository-safe supplemental receipt records only case IDs, boolean
technical/semantic outcomes, counts and cryptographic hashes. It shows exact
technical replay for both responses but failed typed and unclassified smoke
expectations. The evidence therefore does not publish precision, recall,
product admission or a model-safety verdict.
