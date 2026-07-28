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

The 2026-07-27 strong-model smoke evidence is:

- [terminal safe receipt](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.receipt.safe.json);
- [immutable interrupted one-case receipt](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE_INTERRUPTED_AFTER_TYPED.receipt.safe.json);
- [transparent synthetic report](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.report.md).

The terminal receipt records exactly two submissions/responses, both case
passes, exact replay, zero hidden retry/fallback/repair and no qualification
attempt. The interrupted receipt proves the first process stopped with one
passed typed case before the continuation submitted only the missing case.

## Nano zero-call forensic

The 2026-07-28
[Nano zero-call forensic](../../reports/2026-07-28/BROKER_REPORTS_GATE2_NANO_ZERO_CALL_FORENSIC.report.md)
uses the already-preserved private checkpoints and published exact replay. It
performs no provider call and changes no execution authority.

For both frozen smoke cases it exposes the repository-safe synthetic semantic
surface, exact Nano answer, normalized answer, field-level expected diff and
the exact Haiku answer on the same workload. A field-level comparison proves
that the Nano and Haiku canonical requests differ only at `$.model`; Prompt,
Semantic Packet and response format are exact matches. The report diagnoses
the typed observation as `OPTION_CONFUSION` and the unclassified observation
as `MODEL_IGNORED_UNCLASSIFIED`, while withholding any general causal or
packet-refinement claim from the two-case sample.

This is documentation over existing evidence. It does not reconstruct a
missing answer, activate a slim packet, change Prompt or Pack meaning, add an
adapter, alter normalization or authorize another provider submission.

## GOAL 4 Slim diagnostic evidence

The 2026-07-28 GOAL 4 execution uses a dedicated repository-safe synthetic
receipt because all six model inputs are projections of the two frozen
non-customer cases. The receipt checkpoints after every call and contains:

- the sealed exact messages plus strict response schema;
- exact adapter-extracted semantic output;
- deterministic Local Choice normalization;
- field-level expected diff;
- context-lint and canonical materialization status;
- actual input/output tokens, cost and latency;
- per-call submission/response accounting.

It excludes credentials, provider response IDs, raw provider envelopes,
filesystem paths and hidden reasoning. The receipt is immutable execution
evidence; the report projector may refine a first-pass diagnosis from the same
exact facts but does not rewrite receipt bytes.

Evidence:

- [terminal safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.receipt.safe.json);
- [transparent analytical report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md).

The terminal receipt records exactly six submissions/responses, a passed
technical pipeline, failed Haiku unclassified acceptance, zero
fallback/repair/hidden retry, and no full benchmark, qualification verdict,
runtime activation or production admission.
