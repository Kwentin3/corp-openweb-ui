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

Persisted private JSON is restored through
`restore_financial_semantic_v6_private_evidence` before replay. The restorer
accepts only the exact private field set, verifies `private_evidence_hash`,
and reinstates canonical contract order after ordinary JSON writers sort
object keys. It does not change values or weaken replay validation.

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

## Transparent synthetic smoke projection

The repository-safe aggregate receipt remains unchanged and continues to
exclude semantic choices and source values. A separate transparent report is
allowed only for the two frozen synthetic smoke cases. Its sole projector is
`Gate2FinancialSemanticV6TransparentSmokeReportFactory`.

For each allowlisted synthetic case the report copies the exact semantic
decision surface from the already-built canonical packet and Choice:

- task instruction;
- source context, including synthetic values;
- all available financial type cards;
- all Typed Options;
- the unclassified disposition and reason codes;
- exact returned semantic JSON;
- normalized semantic Choice;
- explicit expected-versus-actual field comparison;
- technical status and bounded diagnosis.

The projection does not include credentials, provider response IDs, hidden
reasoning, raw provider envelopes, internal filesystem paths, or execution
metadata. It neither changes nor substitutes the exact private evidence and
safe hash link. Actual-corpus values and exact context are never eligible for
this projection.
